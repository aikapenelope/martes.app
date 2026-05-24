"""Diagnosticador — agente de solo lectura (patrón Scout).

Acceso a: containers, health, logs, stats, base de datos.
Nunca modifica nada. Reporta y sugiere.

DockerTools de Agno NO se incluyen: listan todos los containers del host
(Coolify, coolify-db, coolify-redis, etc.) sin filtro. Los tools custom de
martes están filtrados por label 'martes.tenant' — solo ven tenants Hermes.
"""

from agno.agent import Agent

from src.shared import MODEL, compression, db, knowledge_base, learning, skills
from src.tools.read_ops import (
    check_all_health,
    check_backup_status,
    container_health,
    container_logs,
    container_stats,
    diagnose_container_error,
    get_all_tenants,
    get_server_capacity,
    list_backups,
    list_containers,
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
        diagnose_container_error,
        get_all_tenants,
        get_server_capacity,
        list_backups,
        check_backup_status,
    ],
    tool_call_limit=10,
    retries=1,
    knowledge=knowledge_base,
    search_knowledge=True,  # Agentic RAG: el agente decide cuándo buscar
    learning=learning,
    add_learnings_to_context=True,
    skills=skills,
    db=db,
    # enable_agentic_memory desactivado — LearningMachine con UserMemoryConfig
    # ya gestiona la memoria del usuario. Activar ambos registra 'update_user_memory'
    # dos veces y genera duplicate tool warning en logs.
    add_history_to_context=True,
    num_history_runs=5,
    add_datetime_to_context=True,
    markdown=True,
    compression_manager=compression,
    instructions=[
        "Eres un especialista en diagnóstico de infraestructura de martes.app.",
        "Tienes acceso de SOLO LECTURA a todos los sistemas.",
        "NUNCA modificas nada — solo observas, analizas, y reportas.",
        "",
        "## Modelo Hermes libre",
        "Cada tenant tiene Hermes COMPLETO. No existen tiers ni planes.",
        "El campo 'plan' en DB siempre es 'basico' — etiqueta interna de billing.",
        "Lo que monitorizas: salud del container, backups, estado de pagos.",
        "",
        "## Resolución nombre → código de tenant",
        "Cuando el admin mencione un tenant por nombre (ej: 'logs de Acme', 'estado de XYZ'):",
        "1. Llama get_all_tenants() para obtener la lista con códigos",
        "2. Identifica el tenant_code (tXXX) que corresponde al nombre mencionado",
        "3. Usa SIEMPRE el tenant_code en los tools — NUNCA el nombre del cliente",
        "4. Menciona ambos en tu respuesta: 'Acme (t001)' para que el admin valide",
        "Si el nombre no coincide: muestra la lista de tenants y pide aclaración.",
        "",
        "## Workflow",
        "1. Busca en learnings si ya viste este patrón",
        "2. Recopila datos (containers, health, logs, DB)",
        "3. Analiza y correlaciona",
        "4. Reporta con evidencia (números reales, log lines)",
        "",
        "## Queries SQL útiles:",
        "- SELECT tenant_code,name,status,paid_until FROM tenants",
        "- SELECT * FROM tenants WHERE status='paused'",
        "- SELECT * FROM tenants WHERE paid_until < CURRENT_DATE",
        "",
        "## Reglas:",
        "- Si hay un problema que necesita acción: di "
        "'El Operador puede arreglar esto con: [acción]'",
        "- Responde en español, conciso, evidencia primero",
    ],
)
