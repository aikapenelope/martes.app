"""Definicion del meta-agente Agno para martes.app.

Este agente gestiona tenants Hermes via Telegram. El admin le habla
y el agente ejecuta operaciones de Docker, configuracion y base de datos.
"""

from agno.agent import Agent
from agno.db.postgres import PostgresDb
from agno.models.openai import OpenAIChat

from src.config import settings
from src.tools.docker_ops import (
    create_tenant_container,
    list_tenant_containers,
    remove_tenant_container,
    restart_tenant_container,
    stop_tenant_container,
)
from src.tools.health import (
    check_all_health,
    check_tenant_health,
    get_tenant_logs,
    get_tenant_stats,
)
from src.tools.tenant_config import (
    inject_credential,
    update_tenant_config,
    write_tenant_config,
)
from src.tools.tenant_db import (
    create_tenant_record,
    get_all_tenants,
    register_payment,
    update_tenant_status,
)

# Instrucciones del meta-agente
AGENT_INSTRUCTIONS = """\
Eres el meta-agente de martes.app, una plataforma SaaS que gestiona agentes Hermes para PYMEs.

Tu rol es gestionar la infraestructura de tenants: crear, pausar, reactivar, monitorear y \
configurar agentes Hermes que corren en containers Docker.

## Flujo para crear un tenant nuevo:
1. Recibe los datos: nombre, plan (basico/equipo/pro), bot token de Telegram
2. Crea el registro en la base de datos (create_tenant_record)
3. Escribe la configuracion en disco (write_tenant_config)
4. Crea el container Docker (create_tenant_container)
5. Actualiza el estado a 'active' (update_tenant_status)
6. Confirma que todo esta OK

## Planes disponibles:
- **basico** ($30/mo): 1 plataforma (Telegram), DeepSeek V4, 512MB RAM
- **equipo** ($100/mo): 2 plataformas (Telegram + Discord), DeepSeek V4, 768MB RAM
- **pro** ($200/mo): Todas las plataformas, Claude Haiku, 1GB RAM

## Reglas:
- Siempre confirma antes de ejecutar acciones destructivas (stop, remove)
- Reporta errores de forma clara y sugiere soluciones
- Cuando listes tenants, incluye dias restantes de pago
- Si un tenant tiene 0 dias restantes, sugiere pausarlo
- Responde en espanol por defecto
"""


def create_meta_agent() -> Agent:
    """Crea y configura el meta-agente de martes.app."""
    # Modelo via OpenRouter
    model = OpenAIChat(
        id=settings.default_model,
        api_key=settings.openrouter_api_key,
        base_url="https://openrouter.ai/api/v1",
    )

    # Base de datos PostgreSQL para sesiones, memoria y traces
    db = PostgresDb(
        db_url=settings.database_url,
        session_table="meta_agent_sessions",
        memory_table="meta_agent_memories",
    )

    agent = Agent(
        name="Martes Meta-Agent",
        model=model,
        instructions=AGENT_INSTRUCTIONS,
        db=db,
        tools=[
            # Docker operations
            create_tenant_container,
            stop_tenant_container,
            restart_tenant_container,
            list_tenant_containers,
            remove_tenant_container,
            # Tenant config
            write_tenant_config,
            inject_credential,
            update_tenant_config,
            # Database
            create_tenant_record,
            update_tenant_status,
            register_payment,
            get_all_tenants,
            # Health
            check_all_health,
            check_tenant_health,
            get_tenant_logs,
            get_tenant_stats,
        ],
        add_history_to_context=True,
        num_history_runs=5,
        add_datetime_to_context=True,
        markdown=True,
    )

    return agent
