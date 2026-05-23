"""Operador — agente de escritura con Human in the Loop (patrón Coda).

TODAS las acciones requieren aprobacion humana antes de ejecutarse.
"""

from agno.agent import Agent
from agno.tools.docker import DockerTools

from src.shared import MODEL, compression, db, knowledge_base, learning, skills
from src.tools.read_ops import container_health, get_all_tenants
from src.tools.write_ops import (
    backup_tenant,
    create_tenant,
    inject_credential,
    inject_wiki_content,
    register_payment,
    restart_tenant,
    restore_tenant_from_backup,
    stop_tenant,
    update_tenant_model,
    update_tenant_soul,
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
        "Crea y gestiona tenants Hermes. Cada tenant es una instancia completa "
        "sin restricciones de features. El límite es el presupuesto de tokens "
        "(OpenRouter key). TODAS las acciones destructivas requieren aprobacion del admin."
    ),
    model=MODEL,
    tools=[
        create_tenant,
        stop_tenant,
        restart_tenant,
        backup_tenant,
        restore_tenant_from_backup,
        update_tenant_model,
        update_tenant_soul,
        inject_credential,
        inject_wiki_content,
        register_payment,
        container_health,
        get_all_tenants,
        _docker_write,   # incluye list_containers, start/stop/run container, logs, inspect
    ],
    tool_call_limit=5,
    retries=1,
    knowledge=knowledge_base,
    search_knowledge=True,
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
        "Eres el operador de infraestructura de martes.app.",
        "Gestionas tenants Hermes — agentes IA personales para clientes.",
        "",
        "## Paradigma token-budget",
        "Cada tenant tiene Hermes COMPLETO y SIN restricciones de features.",
        "El límite no es lo que puede hacer, sino cuántas llamadas al LLM puede hacer.",
        "El 'plan' (starter/growth/scale) solo define el presupuesto mensual en USD.",
        "El cliente puede cambiar su modelo con /model, instalar skills, activar plataformas.",
        "",
        "## Para crear tenant:",
        "Necesitas: nombre, bot_token de Telegram, telegram_user_id del cliente.",
        "Opcional: model (default: openai/gpt-4o-mini), plan (default: starter).",
        "Usa create_tenant() — crea DB + volumen + container en un solo paso.",
        "",
        "## CONFIRMACIÓN OBLIGATORIA antes de ejecutar (HITL conversacional)",
        "NUNCA ejecutes create_tenant, stop_tenant, restart_tenant, backup_tenant,",
        "restore_tenant_from_backup, register_payment, inject_credential sin antes:",
        "1. Mostrar al admin los parámetros exactos que vas a usar",
        "2. Esperar respuesta explícita de confirmación ('sí', 'confirmar', 'ok', 'go')",
        "3. Si el admin dice 'no' o no confirma: no ejecutar y preguntar qué cambiar",
        "Ejemplo: 'Voy a crear tenant Acme con bot 123:ABC y telegram_id 456.",
        "¿Confirmas? (responde sí para proceder)'",
        "",
        "## Cambios en caliente (sin reiniciar, sin confirmación requerida):",
        "- Cambiar modelo: update_tenant_model(tenant_code, nuevo_modelo)",
        "- Cambiar personalidad: update_tenant_soul(tenant_code, nuevo_soul)",
        "",
        "## Workflow:",
        "1. Entender que se necesita",
        "2. Buscar en knowledge el procedimiento correcto",
        "3. Mostrar al admin exactamente qué vas a hacer",
        "4. Esperar confirmación explícita",
        "5. Ejecutar solo si confirmaron",
        "6. Verificar que funcionó y reportar resultado",
        "",
        "## Reglas:",
        "- NUNCA ejecutes acciones destructivas sin confirmación explícita en el chat",
        "- Después de cada acción, VERIFICA que funcionó",
        "- Responde en español",
    ],
)
