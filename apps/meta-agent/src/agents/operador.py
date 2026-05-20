"""Operador — Agente de escritura con Human in the Loop.

Todas sus acciones requieren aprobacion humana antes de ejecutarse.
Crea tenants, para containers, inyecta config, registra pagos.
"""

from agno.agent import Agent

from src.shared import (
    PRIMARY_MODEL,
    compression,
    db,
    knowledge_base,
    learning,
    skills,
)
from src.tools.read_ops import container_health, get_tenant_detail, list_containers
from src.tools.write_ops import (
    create_tenant,
    inject_credential,
    register_payment,
    remove_tenant,
    restart_tenant,
    stop_tenant,
)

operador = Agent(
    name="Operador",
    id="operador",
    role="Infrastructure operator. Executes approved actions on tenants.",
    description=(
        "Ejecuta acciones sobre la infraestructura: crear tenants, parar containers, "
        "inyectar credenciales, registrar pagos. TODAS las acciones requieren "
        "aprobacion humana antes de ejecutarse."
    ),
    model=PRIMARY_MODEL,
    tools=[
        # Write (all require approval)
        create_tenant,
        stop_tenant,
        restart_tenant,
        remove_tenant,
        inject_credential,
        register_payment,
        # Read (for verification after actions)
        list_containers,
        container_health,
        get_tenant_detail,
    ],
    tool_call_limit=5,
    retries=1,
    # Knowledge & Learning
    knowledge=knowledge_base,
    search_knowledge=True,
    learning=learning,
    # Skills (lazy-loaded)
    skills=skills,
    # Context
    db=db,
    add_history_to_context=True,
    num_history_runs=5,
    add_datetime_to_context=True,
    markdown=True,
    compression_manager=compression,
    # Instructions
    instructions=[
        "Eres el operador de infraestructura de martes.app.",
        "Ejecutas acciones sobre tenants Hermes.",
        "TODAS tus acciones de escritura requieren aprobacion humana.",
        "",
        "## Workflow",
        "1. **Entender**: que se necesita hacer y por que",
        "2. **Buscar**: consulta knowledge para el procedimiento correcto",
        "3. **Explicar**: di al admin que vas a hacer, por que, y el riesgo",
        "4. **Ejecutar**: la accion (se pedira aprobacion automaticamente)",
        "5. **Verificar**: confirma que la accion funciono (usa tools de lectura)",
        "",
        "## Para crear un tenant:",
        "Necesitas: nombre, plan (basico/equipo/pro), bot_token de Telegram.",
        "Usa create_tenant() que hace todo el flujo completo.",
        "",
        "## Para pausar un tenant (no pago):",
        "Usa stop_tenant(tenant_code). Preserva datos.",
        "",
        "## Para reactivar:",
        "Usa restart_tenant(tenant_code). Verifica health despues.",
        "",
        "## Para conectar integraciones:",
        "Usa inject_credential(tenant_code, tipo, valor).",
        "Despues restart_tenant() para que Hermes cargue la credencial.",
        "",
        "## Reglas",
        "- NUNCA ejecutes sin explicar primero que vas a hacer",
        "- Despues de cada accion, VERIFICA que funciono",
        "- Si algo falla, reporta el error y sugiere solucion",
        "- Responde en espanol",
    ],
)
