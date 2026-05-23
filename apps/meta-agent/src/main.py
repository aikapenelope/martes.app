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
from src.shared import _KNOWLEDGE_DIR, knowledge_base
from src.team import martes_team

# Telegram interface — conectada al TEAM (no a un agente individual)
# El Team coordina Diagnosticador + Operador según la intención del mensaje
interfaces = []

if settings.telegram_token and ":" in settings.telegram_token:
    interfaces.append(
        Telegram(
            team=martes_team,                   # ← TEAM, no agent
            token=settings.telegram_token,
            reply_to_mentions_only=False,
            streaming=True,
            start_message=(
                "Meta-agente martes.app activo.\n"
                "Tengo acceso a: diagnostico, tenants, health, logs, pagos.\n"
                "Escribe 'health check' para empezar."
            ),
            help_message=(
                "Sin restriccion (diagnostico):\n"
                "- health check / status\n"
                "- lista tenants\n"
                "- logs [codigo] / stats [codigo]\n\n"
                "Con aprobacion (operaciones):\n"
                "- crea tenant [nombre] plan [plan] token [token]\n"
                "- pausa [codigo] / reactiva [codigo]\n"
                "- registra pago [codigo] $[monto] [metodo]\n"
                "- conecta [servicio] a [codigo] token [valor]"
            ),
        )
    )

# Indexar knowledge base al arranque — idempotente.
# add_content(skip_if_exists=True): sube embedding solo si el documento
# no existe aún en martes_knowledge. Arranques posteriores son no-op.
# API documentada: Knowledge.add_content(path, skip_if_exists)
# Ref: https://docs.agno.com/knowledge/introduction
for _doc in ["hermes_reference.md", "procedures.md"]:
    knowledge_base.add_content(
        path=str(_KNOWLEDGE_DIR / _doc),
        skip_if_exists=True,
    )

# AgentOS — Agents + Team + Telegram + Scheduler
# agents: expuestos individualmente en os.agno.com para control y monitoreo directo
# teams: entrada unificada para Telegram (coordinate mode — routing dinámico)
# Ref: https://docs.agno.com/agent-os/overview
agent_os = AgentOS(
    agents=[diagnosticador, operador],
    teams=[martes_team],
    interfaces=interfaces,
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
