"""Operador — Write agent with @approval (Coda pattern).

All write operations require human confirmation. Uses DockerTools
for container management and custom tools for tenant lifecycle.
"""

from agno.agent import Agent
from agno.tools.docker import DockerTools

from src.shared import (
    MODEL,
    compression,
    db,
    knowledge_base,
    learning,
    skills,
)
from src.tools.write_ops import (
    create_tenant,
    inject_credential,
    register_payment,
    remove_tenant,
    restart_tenant,
    stop_tenant,
)

# DockerTools — write operations (start/stop/run)
_docker_write = DockerTools(
    include_tools=[
        "list_containers",
        "start_container",
        "stop_container",
        "run_container",
        "get_container_logs",
        "inspect_container",
    ]
)

operador = Agent(
    name="Operador",
    id="operador",
    role="Infrastructure operator. Executes approved actions on tenants.",
    description=(
        "Ejecuta acciones: crear tenants, parar containers, inyectar config, "
        "registrar pagos. TODAS requieren aprobacion humana."
    ),
    model=MODEL,
    tools=[
        # Custom write tools (all with @approval)
        create_tenant,
        stop_tenant,
        restart_tenant,
        remove_tenant,
        inject_credential,
        register_payment,
        # Docker (for verification after actions)
        _docker_write,
    ],
    tool_call_limit=5,
    retries=1,
    # Knowledge
    knowledge=knowledge_base,
    search_knowledge=True,
    # Learning
    learning=learning,
    add_learnings_to_context=True,
    # Skills
    skills=skills,
    # Context
    db=db,
    enable_agentic_memory=True,
    add_history_to_context=True,
    num_history_runs=5,
    add_datetime_to_context=True,
    markdown=True,
    compression_manager=compression,
    # Instructions
    instructions=[
        "Eres el operador de infraestructura de martes.app.",
        "TODAS tus acciones de escritura requieren aprobacion humana.",
        "",
        "## Workflow (Coda pattern):",
        "1. Entender que se necesita",
        "2. Buscar en knowledge el procedimiento",
        "3. Explicar al admin que vas a hacer y el riesgo",
        "4. Ejecutar (se pide aprobacion automaticamente)",
        "5. Verificar que funciono",
        "",
        "## Tools disponibles:",
        "- create_tenant: flujo completo (DB + config + container)",
        "- stop_tenant / restart_tenant: lifecycle",
        "- remove_tenant: eliminar (archivado)",
        "- inject_credential: inyectar tokens/keys",
        "- register_payment: registrar pago manual",
        "- DockerTools: start/stop/run containers directamente",
        "",
        "## Reglas:",
        "- NUNCA ejecutes sin explicar primero",
        "- Despues de cada accion, VERIFICA que funciono",
        "- Si falla, reporta error y sugiere solucion",
        "- Responde en espanol",
    ],
)
