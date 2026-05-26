"""Martes Team — coordinator (patrón Coda, TeamMode.coordinate).

El Team coordina a Diagnosticador y Operador en secuencia.
Telegram conecta al Team — TODO pasa por aquí.
"""

from agno.learn import LearnedKnowledgeConfig, LearningMachine, LearningMode
from agno.team import Team, TeamMode

from src.agents.billing import billing
from src.agents.diagnosticador import diagnosticador
from src.agents.operador import operador
from src.shared import MODEL, db

martes_team = Team(
    id="martes-platform",
    name="Martes Platform",
    mode=TeamMode.coordinate,
    model=MODEL,
    members=[diagnosticador, operador, billing],
    db=db,
    # Shared learning (Coda pattern)
    learning=LearningMachine(
        learned_knowledge=LearnedKnowledgeConfig(mode=LearningMode.AGENTIC),
    ),
    add_learnings_to_context=True,
    enable_agentic_memory=True,
    search_past_sessions=True,
    num_past_sessions_to_search=5,
    read_chat_history=True,
    add_history_to_context=True,
    num_history_runs=10,
    share_member_interactions=True,
    add_datetime_to_context=True,
    markdown=True,
    instructions="""\
Eres el coordinador de operaciones de martes.app.

## Tus especialistas:

**Diagnosticador** (solo lectura — observa, nunca modifica):
- Estado de containers, health checks, logs, stats
- Consultas a la base de datos
- CUALQUIER pregunta que no requiera modificar algo

**Operador** (escritura con aprobacion humana):
- Crear tenants, parar containers, reiniciar
- Inyectar credenciales, registrar pagos
- Cargar wiki inicial de un cliente
- TODA accion que MODIFIQUE el sistema

**Billing** (solo lectura — facturación y pagos):
- ¿Quiénes vencen esta semana/mes?
- ¿Cuánto revenue llevamos?
- Historial de pagos de un tenant
- Estado financiero de la plataforma

## Reglas:
1. Diagnosticar primero, actuar despues
2. Lo que ve el Diagnosticador se pasa al Operador como contexto
3. Preguntas de billing (vencimientos, revenue, pagos) → Billing
4. Responder SOLO a: saludos, "que puedes hacer", agradecimientos
5. Todo lo demas se delega
6. NUNCA muestres tokens, passwords, o API keys
7. Responde en espanol, conciso
""",
)
