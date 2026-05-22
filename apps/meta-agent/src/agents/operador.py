"""Operador — agente de escritura con Human in the Loop (patrón Coda).

TODAS las acciones requieren aprobacion humana antes de ejecutarse.
"""

from agno.agent import Agent
from agno.tools.docker import DockerTools

from src.shared import MODEL, compression, db, knowledge_base, learning, skills
from src.tools.read_ops import container_health, get_all_tenants, list_containers
from src.tools.write_ops import (
    create_tenant,
    inject_credential,
    inject_wiki_content,
    register_payment,
    restart_tenant,
    stop_tenant,
)

_docker_write = DockerTools(
    include_tools=["list_containers", "start_container", "stop_container",
                   "run_container", "get_container_logs", "inspect_container"]
)

operador = Agent(
    name="Operador",
    id="operador",
    role="Infrastructure operator. All write actions require human approval.",
    description=(
        "Crea tenants, para containers, inyecta config, registra pagos. "
        "TODAS las acciones requieren aprobacion del admin."
    ),
    model=MODEL,
    tools=[
        create_tenant,
        stop_tenant,
        restart_tenant,
        inject_credential,
        inject_wiki_content,
        register_payment,
        list_containers,
        container_health,
        get_all_tenants,
        _docker_write,
    ],
    tool_call_limit=5,
    retries=1,
    knowledge=knowledge_base,
    search_knowledge=True,   # Agentic RAG: busca procedimientos antes de actuar
    learning=learning,
    add_learnings_to_context=True,
    skills=skills,
    db=db,
    enable_agentic_memory=True,
    add_history_to_context=True,
    num_history_runs=5,
    add_datetime_to_context=True,
    markdown=True,
    compression_manager=compression,
    instructions=[
        "Eres el operador de infraestructura de martes.app.",
        "TODAS tus acciones de escritura requieren aprobacion humana.",
        "",
        "## Workflow (Coda pattern)",
        "1. Entender que se necesita",
        "2. Buscar en knowledge el procedimiento correcto",
        "3. Explicar al admin que vas a hacer y el riesgo",
        "4. Ejecutar (aprobacion pedida automaticamente)",
        "5. Verificar que funciono",
        "",
        "## Para crear tenant:",
        "Necesitas: nombre, plan (basico/equipo/pro), bot_token de Telegram.",
        "Usa create_tenant() — hace todo el flujo completo.",
        "",
        "## Reglas:",
        "- NUNCA ejecutes sin explicar primero",
        "- Despues de cada accion, VERIFICA que funciono",
        "- Responde en espanol",
    ],
)
