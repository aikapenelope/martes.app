"""Entry point del meta-agente martes.app.

Levanta AgentOS con la interface de Telegram para recibir
comandos del admin y gestionar tenants Hermes.
"""

from agno.os.app import AgentOS
from agno.os.interfaces.telegram import Telegram

from src.agent import create_meta_agent
from src.config import settings

# Crear el meta-agente
meta_agent = create_meta_agent()

# Configurar AgentOS con Telegram interface
agent_os = AgentOS(
    agents=[meta_agent],
    interfaces=[
        Telegram(
            agent=meta_agent,
            token=settings.telegram_token,
            reply_to_mentions_only=False,  # Responde a todos los mensajes (bot privado)
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
    ],
)

# FastAPI app (para health checks y webhook de Telegram)
app = agent_os.get_app()

if __name__ == "__main__":
    agent_os.serve(app="src.main:app", reload=(settings.app_env == "development"))
