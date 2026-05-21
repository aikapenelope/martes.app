"""Shared infrastructure — DB, models, knowledge, learning.

Patrón: Scout (ContextProviders) + Coda (coordinate Team + shared learnings)
Instanciado una vez al importar. Todos los agentes comparten estos objetos.
"""

from pathlib import Path

from agno.compression.manager import CompressionManager
from agno.db.postgres import PostgresDb
from agno.learn import (
    DecisionLogConfig,
    EntityMemoryConfig,
    LearnedKnowledgeConfig,
    LearningMode,
    SessionContextConfig,
    UserMemoryConfig,
)
from agno.learn.machine import LearningMachine
from agno.models.openai import OpenAIChat
from agno.skills import LocalSkills, Skills

from src.config import settings

# ---------------------------------------------------------------------------
# Database — sesiones, memoria, traces
# ---------------------------------------------------------------------------
db = PostgresDb(
    db_url=settings.database_url,
    session_table="martes_sessions",
    memory_table="martes_memories",
    traces_table="martes_traces",
)

# ---------------------------------------------------------------------------
# Modelos — DeepSeek V4 via OpenRouter
# ---------------------------------------------------------------------------
MODEL = OpenAIChat(
    id=settings.default_model,
    api_key=settings.openrouter_api_key,
    base_url="https://openrouter.ai/api/v1",
)

FAST_MODEL = OpenAIChat(
    id="deepseek/deepseek-chat",
    api_key=settings.openrouter_api_key,
    base_url="https://openrouter.ai/api/v1",
)

# ---------------------------------------------------------------------------
# Learning Machine — self-improving (patrón Coda)
# Recuerda: tenants, incidentes, preferencias del admin, patrones operativos
# ---------------------------------------------------------------------------
learning = LearningMachine(
    model=FAST_MODEL,
    user_memory=UserMemoryConfig(mode=LearningMode.AGENTIC),
    entity_memory=EntityMemoryConfig(mode=LearningMode.AGENTIC, namespace="martes"),
    learned_knowledge=LearnedKnowledgeConfig(mode=LearningMode.AGENTIC),
    decision_log=DecisionLogConfig(mode=LearningMode.AGENTIC),
    session_context=SessionContextConfig(enable_planning=True),
)

# ---------------------------------------------------------------------------
# Compression — ahorra tokens en outputs largos de tools
# ---------------------------------------------------------------------------
compression = CompressionManager(model=FAST_MODEL, compress_tool_results=True)

# ---------------------------------------------------------------------------
# Skills — lazy-loaded desde src/skills/
# El agente ve un resumen en el system prompt.
# Carga el SKILL.md completo solo cuando lo necesita.
# ---------------------------------------------------------------------------
_SKILLS_DIR = Path(__file__).parent / "skills"
skills = Skills(loaders=[LocalSkills(str(_SKILLS_DIR))]) if _SKILLS_DIR.exists() else None
