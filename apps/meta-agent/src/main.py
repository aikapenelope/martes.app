"""Entry point de martes.app meta-agente.

AgentOS con:
- Team (Diagnosticador + Operador) como agente principal
- Skill Builder agent (crea y gestiona skills)
- Knowledge base expuesta para upload via UI
- Telegram interface (condicional)
- Scheduler habilitado para jobs periodicos
- Tracing para audit trail
"""

from agno.os.app import AgentOS
from agno.os.interfaces.telegram import Telegram

from src.agents.skill_builder import skill_builder
from src.config import settings
from src.shared import knowledge_base
from src.team import martes_team

# Interfaces condicionales
interfaces = []

# Telegram: solo si hay un token valido
if settings.telegram_token and ":" in settings.telegram_token:
    interfaces.append(
        Telegram(
            team=martes_team,
            token=settings.telegram_token,
            reply_to_mentions_only=False,
            streaming=True,
            start_message=(
                "Meta-agente martes.app activo.\n"
                "Puedo diagnosticar y operar tenants Hermes.\n"
                "Escribe 'health check' o 'lista tenants' para empezar."
            ),
            help_message=(
                "Diagnostico (sin restriccion):\n"
                "- health check / status\n"
                "- lista tenants\n"
                "- logs [codigo] / stats [codigo]\n\n"
                "Operaciones (requieren aprobacion):\n"
                "- crea tenant [nombre] plan [plan] token [token]\n"
                "- pausa [codigo] / reactiva [codigo]\n"
                "- registra pago [codigo] $[monto] [metodo]\n"
                "- conecta [servicio] a [codigo] token [valor]"
            ),
        )
    )

# AgentOS: expone Knowledge para upload via UI (os.agno.com)
agent_os = AgentOS(
    teams=[martes_team],
    agents=[skill_builder],
    knowledge=[knowledge_base],
    interfaces=interfaces,
    scheduler=True,
    scheduler_poll_interval=60,
    tracing=True,
)

# FastAPI app
app = agent_os.get_app()

if __name__ == "__main__":
    agent_os.serve(app="src.main:app", reload=(settings.app_env == "development"))
