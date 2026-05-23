"""Entry point del meta-agente martes.app.

AgentOS con:
- Team (Diagnosticador + Operador) como punto de entrada
- Telegram conectado al Team (patrón correcto de Agno)
- Webhook mode en producción (APP_ENV=production)
- Polling en desarrollo (APP_ENV=development)
- Scheduler habilitado
- Tracing habilitado
"""

from agno.os.app import AgentOS
from agno.os.interfaces.telegram import Telegram

from src.agents.diagnosticador import diagnosticador
from src.agents.operador import operador
from src.config import settings
from src.shared import _KNOWLEDGE_DIR, db, knowledge_base
from src.team import martes_team

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

if __name__ == "__main__":
    agent_os.serve(
        app="src.main:app",
        host="0.0.0.0",
        port=7777,
        reload=(settings.app_env == "development"),
    )
