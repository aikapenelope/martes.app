"""Entry point del meta-agente martes.app.

AgentOS con:
- Team (Diagnosticador + Operador) como punto de entrada
- Telegram conectado al Team (patrón correcto de Agno)
- Webhook mode en producción (APP_ENV=production)
- Polling en desarrollo (APP_ENV=development)
- Scheduler habilitado
- Tracing habilitado
"""

import json
import logging

from agno.os.app import AgentOS
from agno.os.interfaces.telegram import Telegram
from fastapi.responses import JSONResponse

from src.agents.diagnosticador import diagnosticador
from src.agents.operador import operador
from src.config import settings
from src.shared import _KNOWLEDGE_DIR, db, knowledge_base
from src.team import martes_team

logger = logging.getLogger(__name__)

# Telegram interface — conectada al TEAM (no a un agente individual)
# El Team coordina Diagnosticador + Operador según la intención del mensaje
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
# Esto garantiza que cambios en los archivos .md se reflejen en la DB
# sin necesidad de borrar manualmente el knowledge previo.
# Ref: https://docs.agno.com/knowledge/introduction
for _doc in ["hermes_reference.md", "procedures.md"]:
    knowledge_base.add_content(
        path=str(_KNOWLEDGE_DIR / _doc),
        upsert=True,
    )

# AgentOS — Agents + Team + Telegram + Scheduler
# db: requerido para HITL approvals (@approval decorator en tools).
#     Sin db, create_tenant/stop_tenant/backup devuelven 503 en lugar de pausar.
#     Ref: https://docs.agno.com/agent-os/approvals
# agents: expuestos individualmente en os.agno.com para control y monitoreo
# teams: entrada unificada para Telegram (coordinate mode — routing dinámico)
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


# =============================================================================
# Maintenance endpoints — llamados por el Agno scheduler (0 tokens, sin LLM)
#
# El scheduler llama POST /maintenance/backup-all cada noche a las 3 AM UTC.
# No pasa por ningún agente LLM — ejecuta el backup directamente.
# Ref Agno scheduler: https://docs.agno.com/agent-os/scheduler
# =============================================================================

@app.post("/maintenance/backup-all")
async def run_daily_backups() -> JSONResponse:
    """Backup automático de todos los tenants activos. Sin LLM, 0 tokens.

    Llamado por el Agno scheduler (POST /maintenance/backup-all).
    Ejecuta backup_tenant() para cada tenant con status='active'.
    """
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
            results["backed_up"].append({
                "tenant": code,
                "file": result.get("backup_file"),
                "size_mb": result.get("size_mb"),
                "storage": result.get("storage"),
            })
        else:
            results["failed"].append({"tenant": code, "error": result.get("error")})
            logger.error("Backup failed for tenant %s: %s", code, result.get("error"))

    logger.info(
        "Daily backup complete: %d ok, %d failed, %d skipped",
        len(results["backed_up"]), len(results["failed"]), len(results["skipped"]),
    )
    status_code = 200 if not results["failed"] else 207
    return JSONResponse(status_code=status_code, content=results)


@app.on_event("startup")
async def register_maintenance_schedules() -> None:
    """Registra el schedule de backup diario en el Agno scheduler al arrancar.

    Solo crea el schedule si no existe ya (idempotente — seguro en redeployos).
    El scheduler llama POST /maintenance/backup-all cada noche a las 3 AM UTC.
    Ref: https://docs.agno.com/examples/agent-os/scheduler/schedule-management
    """
    import httpx

    schedule_name = "daily-backup-all"
    base = "http://localhost:7777"

    try:
        async with httpx.AsyncClient(base_url=base, timeout=10) as client:
            # Verificar si el schedule ya existe
            # El API de Agno devuelve {"data": [...], "meta": {...}} no un array plano
            # Ref: https://docs.agno.com/examples/agent-os/scheduler/schedule-management
            resp = await client.get("/schedules")
            if resp.status_code == 200:
                payload = resp.json()
                schedules = payload.get("data", []) if isinstance(payload, dict) else payload
                existing = [s["name"] for s in schedules if isinstance(s, dict)]
                if schedule_name in existing:
                    logger.info("Schedule '%s' ya existe — sin cambios.", schedule_name)
                    return
            # Crear el schedule
            resp = await client.post("/schedules", json={
                "name": schedule_name,
                "cron_expr": "0 3 * * *",          # 3 AM UTC diario
                "endpoint": "/maintenance/backup-all",
                "method": "POST",
                "timezone": "UTC",
                "max_retries": 2,
                "retry_delay_seconds": 300,         # 5 min entre reintentos
            })
            if resp.status_code in (200, 201):
                data = resp.json()
                logger.info(
                    "Schedule '%s' creado. Próxima ejecución: %s",
                    schedule_name, data.get("next_run_at"),
                )
            else:
                logger.warning(
                    "No se pudo crear schedule '%s': %s %s",
                    schedule_name, resp.status_code, resp.text[:200],
                )
    except Exception as e:
        # No es fatal — el sistema funciona sin el schedule automático.
        # El admin puede crear el schedule manualmente via Agno UI.
        logger.warning("Error registrando schedule de backup: %s", e)


if __name__ == "__main__":
    agent_os.serve(
        app="src.main:app",
        host="0.0.0.0",
        port=7777,
        reload=(settings.app_env == "development"),
    )
