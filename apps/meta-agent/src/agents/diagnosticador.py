"""Diagnosticador — agente de solo lectura (patrón Scout).

Acceso a: containers, health, logs, stats, base de datos.
Nunca modifica nada. Reporta y sugiere.
"""

from agno.agent import Agent
from agno.tools.docker import DockerTools

from src.shared import MODEL, compression, db, learning, skills
from src.tools.read_ops import (
    check_all_health,
    container_health,
    container_logs,
    container_stats,
    get_all_tenants,
    list_containers,
)

# DockerTools oficial de Agno — subset de solo lectura
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
        "Observa containers, health, logs, base de datos. "
        "Nunca modifica nada. Reporta problemas y sugiere acciones al Operador."
    ),
    model=MODEL,
    tools=[
        list_containers,
        container_health,
        container_logs,
        container_stats,
        check_all_health,
        get_all_tenants,
        _docker_read,
    ],
    tool_call_limit=10,
    retries=1,
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
        "Eres un especialista en diagnostico de infraestructura de martes.app.",
        "Tienes acceso de SOLO LECTURA a todos los sistemas.",
        "NUNCA modificas nada — solo observas, analizas, y reportas.",
        "",
        "## Workflow",
        "1. Busca en learnings si ya viste este patron",
        "2. Recopila datos (containers, health, logs, DB)",
        "3. Analiza y correlaciona",
        "4. Reporta con evidencia (numeros reales, log lines)",
        "",
        "## Queries SQL utiles:",
        "- SELECT tenant_code,name,plan,status,paid_until FROM tenants",
        "- SELECT * FROM tenants WHERE paid_until < CURRENT_DATE",
        "- SELECT * FROM error_logs WHERE resolved=false ORDER BY created_at DESC LIMIT 10",
        "",
        "## Reglas:",
        "- Si hay un problema que necesita accion: di "
        "'El Operador puede arreglar esto con: [accion]'",
        "- Responde en espanol, conciso, evidencia primero",
    ],
)
