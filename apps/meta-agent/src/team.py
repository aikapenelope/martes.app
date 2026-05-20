"""Martes Team — Router que dirige al Diagnosticador o al Operador.

El Team decide a quien enviar cada request basandose en la intencion:
- Preguntas, status, health → Diagnosticador (read-only)
- Acciones, crear, parar, config → Operador (write con approval)
"""

from agno.team import Team, TeamMode

from src.agents.diagnosticador import diagnosticador
from src.agents.operador import operador
from src.shared import PRIMARY_MODEL, db

martes_team = Team(
    id="martes-platform",
    name="Martes Platform",
    description=(
        "Equipo de operaciones de martes.app. Gestiona tenants Hermes "
        "con separacion estricta entre lectura y escritura."
    ),
    members=[diagnosticador, operador],
    mode=TeamMode.route,
    respond_directly=True,
    tool_call_limit=1,
    model=PRIMARY_MODEL,
    db=db,
    # Routing instructions
    instructions=[
        "Eres el router del equipo de operaciones de martes.app.",
        "Decides a quien enviar cada request del admin.",
        "",
        "## Reglas de routing (elige UN miembro):",
        "",
        "### → Diagnosticador (solo lectura):",
        "- 'como estan los tenants', 'health check', 'status'",
        "- 'muestra logs de X', 'stats de X', 'que tiene X'",
        "- 'cuantos tenants hay', 'quien no ha pagado'",
        "- Cualquier pregunta que NO requiera modificar nada",
        "",
        "### → Operador (escritura con aprobacion):",
        "- 'crea tenant', 'para tenant', 'reactiva tenant'",
        "- 'conecta Google a X', 'inyecta token'",
        "- 'registra pago', 'elimina tenant'",
        "- Cualquier accion que MODIFIQUE el sistema",
        "",
        "## Regla de oro:",
        "Si dudas entre lectura y escritura, elige Diagnosticador.",
        "Es mejor observar primero que actuar sin informacion.",
        "",
        "NO agregues comentarios. Devuelve la respuesta del miembro directamente.",
    ],
    # Team config
    determine_input_for_members=False,
    enable_session_summaries=False,
    show_members_responses=False,
    add_history_to_context=False,
    add_datetime_to_context=True,
    markdown=True,
)
