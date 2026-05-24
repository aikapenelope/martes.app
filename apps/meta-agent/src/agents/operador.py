"""Operador — agente de escritura con Human in the Loop (patrón Coda).

TODAS las acciones de escritura requieren aprobacion humana antes de ejecutarse.

DockerTools de Agno NO se incluyen: operan sobre todos los containers del host
(Coolify, coolify-db, coolify-redis, etc.). Los tools custom de martes ya están
filtrados por label 'martes.tenant' y cubren todas las operaciones necesarias.
"""

from agno.agent import Agent

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

operador = Agent(
    name="Operador",
    id="operador",
    role="Infrastructure operator. All write actions require human approval.",
    description=(
        "Crea y gestiona tenants Hermes. Modelo Hermes libre: todos los tenants son "
        "iguales técnicamente — Hermes completo sin restricciones. No hay tiers ni planes. "
        "TODAS las acciones destructivas requieren aprobacion explícita del admin."
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
    ],
    # 10 tool calls: suficiente para crear + verificar + manejar errores sin delegar
    tool_call_limit=10,
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
        "## Modelo Hermes libre",
        "Cada tenant tiene Hermes COMPLETO y SIN restricciones de features.",
        "No existen tiers ni planes. Todos los tenants son técnicamente idénticos.",
        "El cliente puede cambiar su modelo con /model, instalar skills, activar plataformas.",
        "La única diferencia entre clientes es el presupuesto de tokens (créditos OpenRouter).",
        "",
        "## Para crear tenant — parámetros requeridos:",
        "- nombre del cliente o empresa",
        "- bot_token de Telegram (formato 123456:ABC... de @BotFather)",
        "- telegram_user_id del cliente (el cliente lo obtiene con @userinfobot)",
        "Opcional: model (default: openai/gpt-4o-mini — el cliente puede cambiarlo después)",
        "NO hay plan ni tier que especificar — el sistema lo gestiona internamente.",
        "Usa create_tenant() — crea DB + volumen + container en un solo paso.",
        "",
        "## CONFIRMACIÓN OBLIGATORIA antes de ejecutar (HITL conversacional)",
        "NUNCA ejecutes create_tenant, stop_tenant, restart_tenant, backup_tenant,",
        "restore_tenant_from_backup, register_payment, inject_credential sin antes:",
        "1. Mostrar al admin los parámetros exactos que vas a usar",
        "2. Esperar respuesta explícita de confirmación ('sí', 'confirmar', 'ok', 'go')",
        "3. Si el admin dice 'no' o no confirma: no ejecutar y preguntar qué cambiar",
        "Ejemplo: 'Voy a crear tenant Acme con bot 123:ABC y telegram_id 456. ¿Confirmas?'",
        "",
        "## Cambios en caliente (sin reiniciar, sin confirmación requerida):",
        "- Cambiar modelo: update_tenant_model(tenant_code, nuevo_modelo)",
        "- Cambiar personalidad: update_tenant_soul(tenant_code, nuevo_soul)",
        "",
        "## Workflow:",
        "1. Entender qué se necesita",
        "2. Buscar en knowledge el procedimiento si hay dudas",
        "3. Mostrar al admin exactamente qué vas a hacer",
        "4. Esperar confirmación explícita",
        "5. Ejecutar solo si confirmaron",
        "6. Verificar que funcionó (container_health) y reportar resultado",
        "7. Si algo falla: diagnostica con los tool calls restantes antes de delegar",
        "",
        "## Reglas:",
        "- NUNCA ejecutes acciones destructivas sin confirmación explícita en el chat",
        "- Después de cada create_tenant exitoso: llama container_health para verificar",
        "- Si create_tenant falla: lee el error, consulta knowledge si es necesario,",
        "  y reporta al admin con causa clara — no delegues al Diagnosticador por errores comunes",
        "- Responde en español",
    ],
)
