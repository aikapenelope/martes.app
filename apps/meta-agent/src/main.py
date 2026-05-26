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

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

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


# =============================================================================
# Lifespan — registro de schedules de mantenimiento
#
# Bug que esto resuelve: @app.on_event("startup") ejecuta las llamadas HTTP
# antes de que el servidor esté aceptando conexiones → ConnectionRefused →
# el except trag el error → los schedules nunca se crean.
#
# Solución documentada por Agno: pasar lifespan= al constructor de AgentOS.
# asyncio.create_task() agenda la función para después del primer event loop
# tick, cuando el servidor ya está aceptando conexiones.
#
# Ref: https://docs.agno.com/agent-os/lifespan
# =============================================================================

_SCHEDULES_TO_CREATE = [
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
        "max_retries": 0,
    },
    {
        "name": "billing-check",
        "cron_expr": "0 9 * * *",  # 9 AM UTC diario
        "endpoint": "/maintenance/billing-check",
        "method": "POST",
        "timezone": "UTC",
        "max_retries": 0,
    },
    {
        "name": "expire-platform-keys",
        "cron_expr": "*/30 * * * *",  # cada 30 minutos
        "endpoint": "/maintenance/expire-platform-keys",
        "method": "POST",
        "timezone": "UTC",
        "max_retries": 0,
    },
    {
        "name": "docker-cleanup",
        "cron_expr": "0 4 * * 0",  # domingos 4 AM UTC
        "endpoint": "/maintenance/docker-cleanup",
        "method": "POST",
        "timezone": "UTC",
        "max_retries": 0,
    },
    {
        "name": "prune-old-data",
        "cron_expr": "0 2 * * 0",  # domingos 2 AM UTC — antes del backup
        "endpoint": "/maintenance/prune-old-data",
        "method": "POST",
        "timezone": "UTC",
        "max_retries": 0,
    },
]


async def _register_schedules_when_ready() -> None:
    """Espera a que /health responda antes de registrar schedules.

    Reintenta cada 5s hasta 60s. Si el servidor no responde en ese tiempo,
    loguea error y retorna — los schedules se registrarán en el siguiente deploy.
    """
    import httpx

    base = "http://localhost:7777"

    # Esperar hasta 60s (12 reintentos × 5s) a que el servidor esté listo
    for attempt in range(12):
        await asyncio.sleep(5)
        try:
            async with httpx.AsyncClient(base_url=base, timeout=5) as c:
                resp = await c.get("/health")
                if resp.status_code == 200:
                    logger.info("Servidor listo (intento %d) — registrando schedules.", attempt + 1)
                    break
        except Exception:
            continue
    else:
        logger.error(
            "register-schedules: servidor no respondió en 60s — schedules no registrados. "
            "Se registrarán en el siguiente deploy."
        )
        return

    try:
        async with httpx.AsyncClient(base_url=base, timeout=10) as client:
            resp = await client.get("/schedules")
            existing: set[str] = set()
            if resp.status_code == 200:
                payload = resp.json()
                raw = payload.get("data", []) if isinstance(payload, dict) else payload
                existing = {s["name"] for s in raw if isinstance(s, dict)}

            for sched in _SCHEDULES_TO_CREATE:
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


@asynccontextmanager
async def _maintenance_lifespan(app: object) -> AsyncGenerator[None, None]:
    """Registra schedules de mantenimiento después de que el servidor esté listo.

    asyncio.create_task() schedula la tarea para ejecutar en el event loop
    existente. El servidor arranca, empieza a aceptar conexiones, y entonces
    el task corre — evitando el ConnectionRefused del patrón @on_event("startup").

    Ref: https://docs.agno.com/agent-os/lifespan
    """
    asyncio.create_task(_register_schedules_when_ready())
    yield


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
    lifespan=_maintenance_lifespan,  # registra schedules cuando el servidor esté listo
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

    from src.tools.read_ops import _record_error_log, check_all_health

    result = json.loads(check_all_health())
    alerts: list[str] = []

    # Tenants con problema real — excluir "starting" (container recién levantado, es normal)
    # FIX: antes incluía "starting" en las alertas, disparando falsos positivos tras create_tenant.
    truly_unhealthy = [
        t for t in result.get("tenants", []) if t.get("status") in ("unhealthy", "stopped")
    ]
    if truly_unhealthy:
        tenant_list = ", ".join(f"{t['tenant']}({t['status']})" for t in truly_unhealthy)
        alerts.append(f"⚠️ {len(truly_unhealthy)} tenant(s) unhealthy: {tenant_list}")
        logger.warning("Health check: unhealthy tenants: %s", tenant_list)
        # Persistir en error_logs: source='system' porque fue el scheduler quien lo detectó
        for t in truly_unhealthy:
            _record_error_log(
                tenant_code=t["tenant"],
                source="system",
                severity="warning",
                message=f"Container unhealthy detectado por scheduler (status: {t['status']})",
                details={"detected_by": "health-check-all", "status": t["status"]},
            )

    # Disco en /var/lib/martes — alerta si > 80% y persiste en server_metrics
    try:
        import psycopg

        disk = shutil.disk_usage("/var/lib/martes")
        disk_pct = round(disk.used / disk.total * 100, 1)
        used_gb = round(disk.used / (1 << 30), 2)
        total_gb = round(disk.total / (1 << 30), 2)
        result["disk_pct"] = disk_pct
        result["disk_used_gb"] = used_gb

        # Persistir en server_metrics para historial en Metabase
        _pg_url = settings.database_url.replace("+psycopg", "")
        try:
            with psycopg.connect(_pg_url) as conn:
                conn.execute(
                    "INSERT INTO server_metrics (disk_used_gb, disk_total_gb, disk_pct)"
                    " VALUES (%s, %s, %s)",
                    (used_gb, total_gb, disk_pct),
                )
                conn.commit()
        except Exception as db_exc:
            logger.debug("server_metrics write failed: %s", db_exc)

        if disk_pct > 80:
            alerts.append(f"💾 Disco al {disk_pct}% ({used_gb}GB / {total_gb}GB)")
            logger.warning("Health check: disk usage at %.1f%%", disk_pct)
    except OSError as exc:
        logger.debug("Disk usage check failed: %s", exc)

    if alerts:
        await _send_telegram_alert("🔔 martes.app\n" + "\n".join(alerts))

    status_code = 200 if not truly_unhealthy else 207
    return JSONResponse(status_code=status_code, content=result)


@app.post("/maintenance/billing-check")
async def run_billing_check() -> JSONResponse:
    """Ciclo de billing SaaS para todos los tenants activos. Sin LLM, 0 tokens.

    Flujo de alertas diario (9 AM UTC):
    - N días antes de paid_until (configurable: BILLING_ALERT_DAYS, default 7 y 3):
        → Recordatorio: "Acme vence en N días"
    - Día 0 (paid_until = hoy):
        → "Acme vence HOY — gracia de X días antes de suspensión"
    - Pasado BILLING_GRACE_DAYS días sin pago:
        → stop_tenant() automático si BILLING_AUTO_SUSPEND=True
        → "Acme SUSPENDIDO — pago vencido hace X días"

    El admin reactiva con: restart_tenant() después de register_payment().
    Ref: ciclo inspirado en SaaS billing estándar (Stripe, Recurly, etc.)
    """

    from src.tools.read_ops import get_all_tenants
    from src.tools.write_ops import stop_tenant

    tenants_data = json.loads(get_all_tenants())
    if "error" in tenants_data:
        return JSONResponse(status_code=500, content=tenants_data)

    # Parsear configuración de billing
    alert_days: list[int] = []
    for d in settings.billing_alert_days.split(","):
        d = d.strip()
        if d.isdigit():
            alert_days.append(int(d))
    grace_days = settings.billing_grace_days
    auto_suspend = settings.billing_auto_suspend

    result: dict = {
        "alerted": [],
        "suspended": [],
        "skipped_no_paid_until": [],
        "ok": [],
    }

    for t in tenants_data.get("tenants", []):
        code = t["code"]
        name = t["name"]
        status = t.get("status", "")
        days_remaining = t.get("days_remaining")  # None si paid_until es NULL
        paid_until_str = t.get("paid_until")

        # Solo procesamos tenants activos
        if status != "active":
            continue

        # Tenant sin paid_until — no tiene ciclo de billing aún
        if days_remaining is None or paid_until_str is None:
            result["skipped_no_paid_until"].append(code)
            continue

        # === SUSPENSIÓN AUTOMÁTICA ===
        # days_remaining < 0 significa que paid_until ya pasó.
        # Si lleva más de grace_days vencido → suspender.
        if days_remaining < -grace_days:
            days_overdue = abs(days_remaining)
            if auto_suspend:
                suspend_result = json.loads(stop_tenant(code))
                if suspend_result.get("success"):
                    msg = (
                        f"🚫 martes.app — SUSPENSIÓN AUTOMÁTICA\n"
                        f"{name} ({code}) suspendido.\n"
                        f"Pago vencido hace {days_overdue} días "
                        f"(gracia: {grace_days} días).\n"
                        f"Para reactivar: register_payment + restart_tenant"
                    )
                    await _send_telegram_alert(msg)
                    result["suspended"].append(
                        {"tenant": code, "name": name, "days_overdue": days_overdue}
                    )
                    logger.warning(
                        "Billing: auto-suspended %s (%s) — overdue %d days",
                        code,
                        name,
                        days_overdue,
                    )
                else:
                    logger.error("Billing: failed to suspend %s: %s", code, suspend_result)
            else:
                # Auto-suspend desactivado — solo alertar
                msg = (
                    f"🔴 martes.app — PAGO VENCIDO (sin suspensión automática)\n"
                    f"{name} ({code}) lleva {days_overdue} días sin pago.\n"
                    f"paid_until fue: {paid_until_str}"
                )
                await _send_telegram_alert(msg)
                result["alerted"].append(
                    {
                        "tenant": code,
                        "name": name,
                        "days_remaining": days_remaining,
                        "alert_type": "overdue_no_suspend",
                    }
                )
            continue

        # === ALERTA DÍA 0 — vence hoy, empieza la gracia ===
        if days_remaining == 0:
            msg = (
                f"🔴 martes.app — Vence HOY\n"
                f"{name} ({code}) — paid_until: {paid_until_str}\n"
                f"Gracia: {grace_days} días. "
                f"Se suspenderá el {paid_until_str} + {grace_days} días "
                f"si no hay pago."
            )
            await _send_telegram_alert(msg)
            result["alerted"].append(
                {"tenant": code, "name": name, "days_remaining": 0, "alert_type": "expires_today"}
            )
            continue

        # === ALERTAS PREVENTIVAS (7, 3 días antes) ===
        for threshold in sorted(alert_days, reverse=True):
            if days_remaining == threshold:
                msg = (
                    f"⏰ martes.app — Recordatorio de pago\n"
                    f"{name} ({code}) vence en {threshold} días "
                    f"({paid_until_str}).\n"
                    f"Registra el pago con: register_payment {code}"
                )
                await _send_telegram_alert(msg)
                result["alerted"].append(
                    {
                        "tenant": code,
                        "name": name,
                        "days_remaining": threshold,
                        "alert_type": f"reminder_{threshold}d",
                    }
                )
                break
        else:
            result["ok"].append({"tenant": code, "days_remaining": days_remaining})

    suspended_count = len(result["suspended"])
    alerted_count = len(result["alerted"])
    logger.info(
        "Billing check: %d alerted, %d suspended, %d ok, %d no_paid_until",
        alerted_count,
        suspended_count,
        len(result["ok"]),
        len(result["skipped_no_paid_until"]),
    )
    status_code = 200 if not suspended_count else 207
    return JSONResponse(status_code=status_code, content=result)


@app.post("/maintenance/docker-cleanup")
async def run_docker_cleanup() -> JSONResponse:
    """Limpia imágenes Docker de Hermes que ya no están en uso. Sin LLM, 0 tokens.

    Elimina imágenes de nousresearch/hermes-agent que no están siendo usadas
    por ningún container (running o stopped). Las imágenes en uso se conservan.
    Seguro: solo toca imágenes del repo de Hermes — no afecta Coolify, PostgreSQL,
    SeaweedFS ni ninguna otra imagen del host.

    Llamado por el scheduler semanalmente (domingos 4 AM UTC).

    Ref: https://docker-py.readthedocs.io/en/stable/images.html
    """
    import docker

    c_client = docker.from_env()

    # Imágenes actualmente usadas por algún container de tenant
    # Docker SDK: Container.image y Image.id son Optional — se guarda solo si no None.
    used_image_ids: set[str] = set()
    for container in c_client.containers.list(all=True, filters={"label": "martes.tenant"}):
        if container.image and container.image.id:
            used_image_ids.add(container.image.id)

    # También proteger la imagen actual configurada en HERMES_IMAGE
    try:
        current = c_client.images.get(settings.hermes_image)
        if current.id:
            used_image_ids.add(current.id)
    except Exception:
        pass  # Si no existe localmente, no hay nada que proteger

    # Buscar imágenes de Hermes no usadas
    hermes_images = c_client.images.list(name="nousresearch/hermes-agent")
    removed: list[dict] = []
    errors: list[dict] = []
    freed_bytes = 0

    for img in hermes_images:
        img_id: str = img.id or ""
        if not img_id or img_id in used_image_ids:
            continue
        img_id_short = img_id[:12]
        tags = img.tags or [img_id_short]
        size_mb = round(img.attrs.get("Size", 0) / (1 << 20), 1)
        try:
            c_client.images.remove(img_id, force=False)
            removed.append({"id": img_id_short, "tags": tags, "size_mb": size_mb})
            freed_bytes += img.attrs.get("Size", 0)
            logger.info("Docker cleanup: removed image %s (%s MB)", img_id_short, size_mb)
        except Exception as exc:
            errors.append({"id": img_id_short, "tags": tags, "error": str(exc)})
            logger.debug("Docker cleanup: could not remove %s: %s", img_id_short, exc)

    freed_mb = round(freed_bytes / (1 << 20), 1)
    logger.info(
        "Docker cleanup: removed %d image(s), freed %.1f MB, %d errors",
        len(removed),
        freed_mb,
        len(errors),
    )
    if removed:
        await _send_telegram_alert(
            f"🐳 martes.app — Docker cleanup\n"
            f"{len(removed)} imagen(es) Hermes huérfana(s) eliminada(s). "
            f"Liberado: {freed_mb} MB"
        )

    return JSONResponse(
        content={"removed": len(removed), "freed_mb": freed_mb, "images": removed, "errors": errors}
    )


@app.post("/maintenance/expire-platform-keys")
async def run_expire_platform_keys() -> JSONResponse:
    """Blanquea platform keys de OpenRouter expiradas en todos los tenants. Sin LLM.

    Para cada tenant activo con marker .platform_key_expires:
    - Si la key en .env ya es la propia del cliente → limpia el marker, no modifica.
    - Si la platform key está expirada → blanquea OPENROUTER_API_KEY en .env.
    - Hermes recarga .env en cada turno → efecto en el próximo mensaje, sin restart.

    Llamado por el scheduler cada 30 minutos.
    Ref: hermes/gateway/run.py:_reload_runtime_env_preserving_config_authority()
    """
    from pathlib import Path as _Path

    from src.tools.write_ops import _PLATFORM_KEY_EXPIRES_FILE, expire_platform_key

    tenants_dir = _Path(settings.tenants_base_path)
    if not tenants_dir.exists():
        return JSONResponse(status_code=200, content={"checked": 0})

    results: dict = {"blanked": [], "client_key": [], "not_expired": [], "errors": []}

    for tenant_dir in sorted(tenants_dir.iterdir()):
        if not tenant_dir.is_dir():
            continue
        marker = tenant_dir / _PLATFORM_KEY_EXPIRES_FILE
        if not marker.exists():
            continue  # Sin marker → no hay platform key temporal

        code = tenant_dir.name
        result = json.loads(expire_platform_key(code, dry_run=False))
        status = result.get("status", "error")

        if status == "expired_and_blanked":
            results["blanked"].append(code)
            msg = (
                f"🔑 martes.app — Platform key expirada\n"
                f"OPENROUTER_API_KEY blanqueada para {code}.\n"
                f"El cliente debe configurar su propia key en OpenRouter."
            )
            await _send_telegram_alert(msg)
            logger.info("expire-platform-keys: blanked key for %s", code)
        elif status == "client_key_active":
            results["client_key"].append(code)
            logger.info("expire-platform-keys: %s already has own key", code)
        elif status == "not_expired":
            results["not_expired"].append(code)
        else:
            results["errors"].append({"tenant": code, "error": result.get("error", status)})

    total = sum(len(v) for v in results.values())
    logger.info(
        "expire-platform-keys: %d total — blanked=%d, own_key=%d, not_expired=%d, errors=%d",
        total,
        len(results["blanked"]),
        len(results["client_key"]),
        len(results["not_expired"]),
        len(results["errors"]),
    )
    return JSONResponse(content=results)


@app.post("/maintenance/prune-old-data")
async def run_prune_old_data() -> JSONResponse:
    """Limpieza semanal de tablas que crecen indefinidamente. Sin LLM, 0 tokens.

    Elimina registros antiguos de tres tablas:
    - ai.martes_traces   → cada llamada LLM genera una traza. Retención: 30 días.
    - ai.martes_sessions → sesiones inactivas más de 90 días.
    - public.health_checks → 5 min × N tenants = cientos de filas/día. Retención: 90 días.

    Llamado por el scheduler los domingos a las 2 AM UTC (antes del backup de las 3 AM).
    """
    import psycopg

    from src.config import settings as _s

    def _pg_url() -> str:
        url = _s.database_url
        return url.replace("+psycopg", "") if "+psycopg" in url else url

    deleted: dict[str, int] = {}
    errors: list[str] = []

    queries = [
        (
            "martes_traces",
            "DELETE FROM ai.martes_traces WHERE created_at < NOW() - INTERVAL '30 days'",
        ),
        (
            "martes_sessions",
            "DELETE FROM ai.martes_sessions WHERE updated_at < NOW() - INTERVAL '90 days'",
        ),
        (
            "health_checks",
            "DELETE FROM public.health_checks WHERE checked_at < NOW() - INTERVAL '90 days'",
        ),
    ]

    try:
        with psycopg.connect(_pg_url()) as conn:
            for table, query in queries:
                try:
                    cur = conn.execute(query)
                    deleted[table] = cur.rowcount
                    conn.commit()
                except Exception as e:
                    errors.append(f"{table}: {e}")
                    conn.rollback()
    except Exception as e:
        errors.append(f"connection: {e}")

    total_deleted = sum(deleted.values())
    logger.info(
        "prune-old-data: eliminados %d registros — traces=%d sessions=%d health_checks=%d",
        total_deleted,
        deleted.get("martes_traces", 0),
        deleted.get("martes_sessions", 0),
        deleted.get("health_checks", 0),
    )
    if total_deleted > 0:
        await _send_telegram_alert(
            f"🧹 Pruning semanal completado:\n"
            f"  traces: {deleted.get('martes_traces', 0)} registros\n"
            f"  sessions: {deleted.get('martes_sessions', 0)} registros\n"
            f"  health_checks: {deleted.get('health_checks', 0)} registros"
        )
    return JSONResponse(content={"deleted": deleted, "errors": errors})


if __name__ == "__main__":
    agent_os.serve(
        app="src.main:app",
        host="0.0.0.0",
        port=7777,
        reload=(settings.app_env == "development"),
    )
