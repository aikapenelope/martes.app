"""Entry point del meta-agente martes.app.

Levanta AgentOS con interfaces condicionales:
- API HTTP siempre activa (health checks, testing)
- Telegram solo si META_AGENT_TELEGRAM_TOKEN esta configurado
"""

from agno.os.app import AgentOS
from agno.os.interfaces.telegram import Telegram

from src.agent import create_meta_agent
from src.config import settings

# Crear el meta-agente
meta_agent = create_meta_agent()

# Interfaces condicionales
interfaces = []

# Telegram: solo si hay un token valido
if settings.telegram_token and ":" in settings.telegram_token:
    interfaces.append(
        Telegram(
            agent=meta_agent,
            token=settings.telegram_token,
            reply_to_mentions_only=False,
            streaming=True,
            start_message=(
                "Meta-agente martes.app activo. "
                "Puedo gestionar tenants Hermes. Escribe 'lista tenants' para empezar."
            ),
            help_message=(
                "Comandos disponibles:\n"
                "- Crea tenant [nombre] plan [basico/equipo/pro] token [bot_token]\n"
                "- Lista tenants\n"
                "- Pausa tenant [codigo]\n"
                "- Reactiva tenant [codigo]\n"
                "- Health check\n"
                "- Registra pago [codigo] $[monto] [metodo]\n"
                "- Logs [codigo]\n"
                "- Stats [codigo]"
            ),
        )
    )

# AgentOS: API siempre activa, Telegram condicional, scheduler habilitado
agent_os = AgentOS(
    agents=[meta_agent],
    interfaces=interfaces,
    scheduler=True,
    scheduler_poll_interval=60,  # Revisa jobs cada 60 segundos
)

# FastAPI app
app = agent_os.get_app()

if __name__ == "__main__":
    agent_os.serve(app="src.main:app", reload=(settings.app_env == "development"))
