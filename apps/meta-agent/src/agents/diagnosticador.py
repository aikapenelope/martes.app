"""Diagnosticador — Read-only agent with Context Providers (Scout pattern).

Uses ContextProviders that auto-generate query_<id> tools:
- query_crm: SQL queries to tenant database
- query_knowledge: search the platform wiki
- Plus DockerTools for container inspection
"""

from agno.agent import Agent
from agno.tools.docker import DockerTools

from src.shared import (
    MODEL,
    compression,
    db,
    db_provider,
    knowledge_base,
    learning,
    skills,
    wiki_provider,
)

# Context providers generate tools automatically
_context_tools: list = []
_context_tools.extend(wiki_provider.get_tools())
_context_tools.extend(db_provider.get_tools())

# DockerTools — read-only subset
_docker_read = DockerTools(
    include_tools=[
        "list_containers",
        "get_container_logs",
        "inspect_container",
        "list_networks",
        "list_images",
    ]
)

diagnosticador = Agent(
    name="Diagnosticador",
    id="diagnosticador",
    role="Infrastructure diagnostics. Read-only. Observes, analyzes, reports.",
    description=(
        "Observa containers, health, logs, base de datos, y wiki. "
        "Nunca modifica nada. Usa ContextProviders para acceso directo."
    ),
    model=MODEL,
    tools=[
        *_context_tools,  # query_knowledge, update_knowledge, query_crm, update_crm
        _docker_read,     # Docker inspection
    ],
    tool_call_limit=10,
    retries=1,
    # Knowledge (RAG)
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
        "Eres un especialista en diagnostico de infraestructura.",
        "Tienes acceso de SOLO LECTURA a todo el sistema.",
        "",
        "## Tus herramientas:",
        "- **query_crm**: SQL directo a la DB de tenants (SELECT only)",
        "- **query_knowledge / update_knowledge**: wiki de la plataforma",
        "- **DockerTools**: inspeccionar containers, logs, redes",
        "- **Knowledge search**: buscar en docs indexados (RAG)",
        "",
        "## Workflow (Scout pattern):",
        "1. Busca en learnings si ya viste este patron",
        "2. Consulta la fuente relevante (DB, Docker, wiki)",
        "3. Analiza y correlaciona",
        "4. Reporta con evidencia (numeros, logs, queries)",
        "",
        "## Queries utiles:",
        "- Tenants activos: SELECT tenant_code, name, plan, status, paid_until FROM tenants",
        "- Sin pago: SELECT * FROM tenants WHERE paid_until < CURRENT_DATE",
        "- Errores recientes: SELECT * FROM error_logs WHERE resolved = false "
        "ORDER BY created_at DESC LIMIT 10",
        "- Health: SELECT * FROM health_checks ORDER BY checked_at DESC LIMIT 20",
        "",
        "## Reglas:",
        "- NUNCA uses UPDATE/DELETE/INSERT en query_crm",
        "- Si identificas un problema, di: 'El Operador puede arreglar esto'",
        "- Responde en espanol, conciso, evidencia primero",
    ],
)
