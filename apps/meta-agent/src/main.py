"""Entry point del meta-agente martes.app.

AgentOS con:
- Team (Diagnosticador + Operador) como punto de entrada
- Telegram conectado al Team (patrón correcto de Agno)
- Webhook mode en producción (APP_ENV=production)
- Polling en desarrollo (APP_ENV=development)
- Scheduler habilitado
- Tracing habilitado
- Guardrail de Telegram: solo responde a IDs autorizados
"""

import json
import logging

from agno.os.app import AgentOS
from agno.os.interfaces.telegram import Telegram
from fastapi.requests import Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

from src.agents.diagnosticador import diagnosticador
from src.agents.operador import operador
from src.config import settings
from src.shared import _KNOWLEDGE_DIR, db, knowledge_base
from src.team import martes_team

logger = logging.getLogger(__name__)


# =============================================================================
# Guardrail de Telegram — capa dura de seguridad, independiente del LLM
#
# El middleware inspecciona cada update de Telegram ANTES de que Agno lo
# procese. Si el from.id del remitente no está en la lista de IDs autorizados,
# responde 200 OK a Telegram (para que no reintente) y descarta el mensaje.
#
# Esto no es una instrucción al LLM — es una barrera a nivel HTTP que ningún
# usuario puede bypassear desde Telegram.
#
# Ref: patrón "Custom Middleware" documentado en Agno AgentOS:
# https://docs.agno.com/agent-os/overview (BYO FastAPI App section)
# =============================================================================


class TelegramAllowlistMiddleware(BaseHTTPMiddleware):
    """Descarta updates de Telegram de usuarios no autorizados.

    Sólo actúa en POST /telegram/webhook. Todos los demás paths pasan sin
    modificación. Si TELEGRAM_ADMIN_IDS está vacío (desarrollo), permite todo.
    """

    def __init__(self, app, allowed_ids: frozenset[str]) -> None:
        super().__init__(app)
        self.allowed_ids = allowed_ids

    async def dispatch(self, request: Request, call_next: object) -> Response:
        if "/telegram/webhook" in str(request.url.path) and request.method == "POST":
            body = await request.body()

            if self.allowed_ids:
                try:
                    update = json.loads(body)
                    # El update puede venir de message, edited_message, callback_query, etc.
                    from_id: int | None = None
                    for field in (
                        "message",
                        "edited_message",
                        "callback_query",
                        "inline_query",
                        "my_chat_member",
                        "chat_member",
                    ):
                        if field in update:
                            from_id = update[field].get("from", {}).get("id")
                            break

                    if from_id is not None and str(from_id) not in self.allowed_ids:
                        logger.warning(
                            "Telegram update descartado: user_id=%s no autorizado", from_id
                        )
                        # Responder 200 para que Telegram no reintente
                        return Response(status_code=200)
                except (json.JSONDecodeError, AttributeError):
                    # Payload malformado — dejamos que Agno lo maneje
                    pass

            # Re-inyectar body en el request (fue consumido por await request.body())
            # Necesario porque Starlette/FastAPI solo permite leer el body una vez.
            async def receive() -> dict:
                return {"type": "http.request", "body": body, "more_body": False}

            request._receive = receive  # type: ignore[attr-defined]

        return await call_next(request)  # type: ignore[arg-type]


# =============================================================================
# Telegram interface — conectada al TEAM (no a un agente individual)
# =============================================================================
interfaces = []

if settings.telegram_token and ":" in settings.telegram_token:
    interfaces.append(
        Telegram(
            team=martes_team,
            token=settings.telegram_token,
            reply_to_mentions_only=False,
            streaming=True,
            start_message=(
                "Meta-agente martes.app activo.\n"
                "Gestiono tenants Hermes — agentes IA completos y sin restricciones.\n"
                "Escribe 'health check' para empezar o 'ayuda' para ver opciones."
            ),
            help_message=(
                "Diagnóstico (sin aprobación):\n"
                "- health check / status\n"
                "- lista tenants\n"
                "- logs [codigo] / stats [codigo]\n"
                "- cuanto hemos gastado\n\n"
                "Operaciones (con aprobación):\n"
                "- crea tenant [nombre] token [bot_token] telegram_id [id]\n"
                "- cambia modelo [codigo] a [modelo]\n"
                "- pausa [codigo] / reactiva [codigo]\n"
                "- registra pago [codigo] $[monto] [metodo]\n"
                "- backup [codigo] / restaura [codigo] desde [archivo]"
            ),
        )
    )

# Indexar knowledge base al arranque.
# upsert=True: si el documento ya existe con ese ID, actualiza el contenido.
# Ref: https://docs.agno.com/knowledge/introduction
for _doc in ["hermes_reference.md", "procedures.md"]:
    knowledge_base.add_content(
        path=str(_KNOWLEDGE_DIR / _doc),
        upsert=True,
    )

# AgentOS
# Ref: https://docs.agno.com/agent-os/overview
agent_os = AgentOS(
    agents=[diagnosticador, operador],
    teams=[martes_team],
    interfaces=interfaces,
    db=db,
    scheduler=True,
    scheduler_poll_interval=60,
    tracing=True,
)

app = agent_os.get_app()

# Añadir guardrail DESPUÉS de get_app() para que envuelva al router de Agno.
# Si TELEGRAM_ADMIN_IDS está vacío → frozenset vacío → middleware permite todo.
_allowed_ids: frozenset[str] = (
    frozenset(uid.strip() for uid in settings.telegram_admin_ids.split(",") if uid.strip())
    if settings.telegram_admin_ids
    else frozenset()
)
app.add_middleware(TelegramAllowlistMiddleware, allowed_ids=_allowed_ids)

if _allowed_ids:
    logger.info("Telegram guardrail activo — IDs autorizados: %s", _allowed_ids)
else:
    logger.warning("Telegram guardrail DESACTIVADO — TELEGRAM_ADMIN_IDS no configurado")


# =============================================================================
# Helpers internos
# =============================================================================


async def _send_telegram_alert(message: str) -> None:
    """Envía un mensaje a todos los admin IDs de Telegram configurados.

    Fallo silencioso — si Telegram no está disponible o el token es inválido,
    el error se loguea pero no interrumpe el flujo del llamador.

    Ref Telegram Bot API: https://core.telegram.org/bots/api#sendmessage
    """
    import httpx

    if not settings.telegram_token or not settings.telegram_admin_ids:
        return
    for raw_id in settings.telegram_admin_ids.split(","):
        admin_id = raw_id.strip()
        if not admin_id:
            continue
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(
                    f"https://api.telegram.org/bot{settings.telegram_token}/sendMessage",
                    json={"chat_id": admin_id, "text": message},
                )
        except Exception as exc:
            logger.debug("Telegram alert failed for %s: %s", admin_id, exc)


# =============================================================================
# Maintenance endpoints — llamados por el Agno scheduler (0 tokens, sin LLM)
# =============================================================================


@app.post("/maintenance/backup-all")
async def run_daily_backups() -> JSONResponse:
    """Backup automático de todos los tenants activos. Sin LLM, 0 tokens."""
    from src.tools.read_ops import get_all_tenants
    from src.tools.write_ops import backup_tenant

    tenants_data = json.loads(get_all_tenants())
    if "error" in tenants_data:
        return JSONResponse(status_code=500, content=tenants_data)

    results = {"backed_up": [], "failed": [], "skipped": []}
    for t in tenants_data.get("tenants", []):
        code = t["code"]
        if t["status"] != "active":
            results["skipped"].append(code)
            continue
        result = json.loads(backup_tenant(code))
        if result.get("success"):
            results["backed_up"].append(
                {
                    "tenant": code,
                    "file": result.get("backup_file"),
                    "size_mb": result.get("size_mb"),
                    "storage": result.get("storage"),
                }
            )
        else:
            results["failed"].append({"tenant": code, "error": result.get("error")})
            logger.error("Backup failed for tenant %s: %s", code, result.get("error"))

    logger.info(
        "Daily backup complete: %d ok, %d failed, %d skipped",
        len(results["backed_up"]),
        len(results["failed"]),
        len(results["skipped"]),
    )
    status_code = 200 if not results["failed"] else 207
    return JSONResponse(status_code=status_code, content=results)


@app.post("/maintenance/health-check-all")
async def run_health_check() -> JSONResponse:
    """Health check global de todos los tenants. Sin LLM, 0 tokens.

    Envía alerta Telegram si hay tenants unhealthy o el disco supera el 80%.
    Llamado por el scheduler cada 5 minutos.

    Ref Agno scheduler: https://docs.agno.com/examples/agent-os/scheduler/schedule-management
    """
    import shutil

    from src.tools.read_ops import check_all_health

    result = json.loads(check_all_health())
    alerts: list[str] = []

    # Tenants que no están healthy
    unhealthy = [t for t in result.get("tenants", []) if t.get("status") != "healthy"]
    if unhealthy:
        tenant_list = ", ".join(f"{t['tenant']}({t['status']})" for t in unhealthy)
        alerts.append(f"⚠️ {len(unhealthy)} tenant(s) unhealthy: {tenant_list}")
        logger.warning("Health check: unhealthy tenants: %s", tenant_list)

    # Disco en /var/lib/martes — alerta si > 80%
    try:
        disk = shutil.disk_usage("/var/lib/martes")
        disk_pct = round(disk.used / disk.total * 100, 1)
        result["disk_pct"] = disk_pct
        if disk_pct > 80:
            used_gb = round(disk.used / (1 << 30), 1)
            total_gb = round(disk.total / (1 << 30), 1)
            alerts.append(f"💾 Disco al {disk_pct}% ({used_gb}GB / {total_gb}GB)")
            logger.warning("Health check: disk usage at %.1f%%", disk_pct)
    except OSError as exc:
        logger.debug("Disk usage check failed: %s", exc)

    if alerts:
        await _send_telegram_alert("🔔 martes.app\n" + "\n".join(alerts))

    status_code = 200 if not unhealthy else 207
    return JSONResponse(status_code=status_code, content=result)


@app.post("/maintenance/billing-check")
async def run_billing_check() -> JSONResponse:
    """Verifica paid_until de todos los tenants activos. Sin LLM, 0 tokens.

    Envía alerta Telegram si algún tenant vence en los próximos 5 días.
    Llamado por el scheduler diariamente a las 9 AM UTC.
    """
    from src.tools.read_ops import get_all_tenants

    tenants_data = json.loads(get_all_tenants())
    if "error" in tenants_data:
        return JSONResponse(status_code=500, content=tenants_data)

    expiring_soon: list[dict] = []
    for t in tenants_data.get("tenants", []):
        if t.get("status") != "active":
            continue
        days_remaining = t.get("days_remaining")
        if days_remaining is not None and days_remaining <= 5:
            expiring_soon.append(
                {
                    "tenant": t["code"],
                    "name": t["name"],
                    "days_remaining": days_remaining,
                }
            )

    if expiring_soon:
        lines = [
            f"- {t['name']} ({t['tenant']}): {t['days_remaining']} días" for t in expiring_soon
        ]
        msg = "💳 martes.app — Pagos próximos a vencer:\n" + "\n".join(lines)
        await _send_telegram_alert(msg)
        logger.info("Billing check: %d tenant(s) vencen pronto", len(expiring_soon))

    return JSONResponse(content={"expiring_soon": expiring_soon, "total": len(expiring_soon)})


@app.on_event("startup")
async def register_maintenance_schedules() -> None:
    """Registra todos los schedules de mantenimiento al arrancar. Idempotente.

    Solo crea los schedules que no existan todavía — seguro en redeploys.
    Ref: https://docs.agno.com/examples/agent-os/scheduler/schedule-management
    """
    import httpx

    # Definición de todos los schedules de mantenimiento.
    # Orden: backup primero (existente), luego los nuevos de Sprint B.
    schedules_to_create = [
        {
            "name": "daily-backup-all",
            "cron_expr": "0 3 * * *",  # 3 AM UTC
            "endpoint": "/maintenance/backup-all",
            "method": "POST",
            "timezone": "UTC",
            "max_retries": 2,
            "retry_delay_seconds": 300,
        },
        {
            "name": "health-check-all",
            "cron_expr": "*/5 * * * *",  # cada 5 minutos
            "endpoint": "/maintenance/health-check-all",
            "method": "POST",
            "timezone": "UTC",
            "max_retries": 0,  # sin reintento — próximo ciclo cubre
        },
        {
            "name": "billing-check",
            "cron_expr": "0 9 * * *",  # 9 AM UTC diario
            "endpoint": "/maintenance/billing-check",
            "method": "POST",
            "timezone": "UTC",
            "max_retries": 0,
        },
    ]
    base = "http://localhost:7777"

    try:
        async with httpx.AsyncClient(base_url=base, timeout=10) as client:
            # Obtener schedules existentes
            resp = await client.get("/schedules")
            existing: set[str] = set()
            if resp.status_code == 200:
                payload = resp.json()
                raw = payload.get("data", []) if isinstance(payload, dict) else payload
                existing = {s["name"] for s in raw if isinstance(s, dict)}

            # Crear solo los que no existen
            for sched in schedules_to_create:
                name = sched["name"]
                if name in existing:
                    logger.info("Schedule '%s' ya existe — sin cambios.", name)
                    continue
                create_resp = await client.post("/schedules", json=sched)
                if create_resp.status_code in (200, 201):
                    logger.info(
                        "Schedule '%s' creado. Próxima ejecución: %s",
                        name,
                        create_resp.json().get("next_run_at"),
                    )
                else:
                    logger.warning(
                        "No se pudo crear schedule '%s': %s %s",
                        name,
                        create_resp.status_code,
                        create_resp.text[:200],
                    )
    except Exception as e:
        logger.warning("Error registrando schedules de mantenimiento: %s", e)


if __name__ == "__main__":
    agent_os.serve(
        app="src.main:app",
        host="0.0.0.0",
        port=7777,
        reload=(settings.app_env == "development"),
    )
