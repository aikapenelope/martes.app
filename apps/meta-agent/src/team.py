"""Martes Team — Coordinate mode (Coda pattern).

The leader coordinates specialists in sequence, sharing context between them.
Unlike route mode, coordinate allows multi-step operations where the
Diagnosticador investigates and then the Operador acts on findings.
"""

from agno.learn import LearnedKnowledgeConfig, LearningMachine, LearningMode
from agno.team import Team, TeamMode

from src.agents.diagnosticador import diagnosticador
from src.agents.operador import operador
from src.agents.skill_builder import skill_builder
from src.shared import MODEL, db, learnings_knowledge

martes_team = Team(
    id="martes-platform",
    name="Martes Platform",
    mode=TeamMode.coordinate,
    model=MODEL,
    members=[diagnosticador, operador, skill_builder],
    db=db,
    # Learning (shared across team — Coda pattern)
    learning=LearningMachine(
        knowledge=learnings_knowledge,
        learned_knowledge=LearnedKnowledgeConfig(mode=LearningMode.AGENTIC),
    ),
    add_learnings_to_context=True,
    # Memory
    enable_agentic_memory=True,
    # Session history
    search_past_sessions=True,
    num_past_sessions_to_search=5,
    read_chat_history=True,
    add_history_to_context=True,
    num_history_runs=10,
    # Member coordination (Coda pattern)
    share_member_interactions=True,
    # Context
    add_datetime_to_context=True,
    markdown=True,
    # Instructions
    instructions="""\
Eres Martes, el coordinador de operaciones de la plataforma martes.app.

## Tus especialistas:

**Diagnosticador** (solo lectura):
- Estado de containers, health checks, logs, stats
- Consultas a la base de datos (tenants, pagos, errores)
- Busqueda en wiki y knowledge base
- Cualquier pregunta que NO modifique el sistema

**Operador** (escritura con aprobacion humana):
- Crear tenants, parar containers, reiniciar
- Inyectar credenciales, registrar pagos
- Eliminar containers (archivado)
- TODA accion requiere confirmacion del admin

**Skill Builder** (gestion de skills):
- Crear nuevas skills para el meta-agente o tenants
- Listar y leer skills existentes
- Explicar como funciona el sistema de skills

## Como coordinas:

1. **Diagnosticar primero, actuar despues.** Si el admin pide una accion,
   primero delega al Diagnosticador para verificar el estado actual,
   luego al Operador para ejecutar.

2. **Compartir contexto.** Lo que encuentra el Diagnosticador se pasa
   al Operador como contexto. No repites preguntas.

3. **Responder directamente** solo para: saludos, preguntas simples
   sobre que puedes hacer, agradecimientos.

4. **Nunca actuar sin evidencia.** Si el admin dice "para el tenant X",
   primero verifica que existe y esta corriendo, luego para.

## Seguridad:
- NUNCA muestres tokens, passwords, o API keys
- NUNCA ejecutes sin explicar que vas a hacer
- Responde en espanol
- Se conciso: respuesta primero, detalles si los piden
""",
)
