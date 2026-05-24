"""Shared infrastructure — DB, models, knowledge, learning.

Patrón: Scout (ContextProviders) + Coda (coordinate Team + shared learnings)
Instanciado una vez al importar. Todos los agentes comparten estos objetos.
"""

from pathlib import Path

from agno.compression.manager import CompressionManager
from agno.db.postgres import PostgresDb
from agno.knowledge.embedder.openai import OpenAIEmbedder
from agno.knowledge.knowledge import Knowledge
from agno.knowledge.reader.markdown_reader import MarkdownReader
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
from agno.vectordb.pgvector import PgVector

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
# Modelos — DeepSeek V4 Flash via OpenRouter
# deepseek/deepseek-v4-flash: 1M tokens contexto, verificado mayo 2026
# Ref: https://openrouter.ai/deepseek/deepseek-v4-flash
# ---------------------------------------------------------------------------
MODEL = OpenAIChat(
    id=settings.default_model,  # deepseek/deepseek-v4-flash desde config
    api_key=settings.openrouter_api_key,
    base_url="https://openrouter.ai/api/v1",
)

FAST_MODEL = OpenAIChat(
    id="deepseek/deepseek-v4-flash",
    api_key=settings.openrouter_api_key,
    base_url="https://openrouter.ai/api/v1",
)

# ---------------------------------------------------------------------------
# Learning Machine — self-improving (patrón Coda)
# Recuerda: tenants, incidentes, preferencias del admin, patrones operativos
#
# db=db es necesario para que entity_memory_store.create_entity() funcione
# cuando se llama directamente desde tools (fuera del contexto de un agente).
# Sin db, LearningMachine._create_entity_memory_store() recibe config.db=None
# y el store no puede conectar a Postgres.
# Ref: agno==2.6.8 learn/machine.py:_create_entity_memory_store()
# ---------------------------------------------------------------------------
learning = LearningMachine(
    db=db,
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

# ---------------------------------------------------------------------------
# Knowledge Base — documentación de Hermes y procedimientos operativos
#
# Embedder: OpenAILikeEmbedder con OpenRouter (misma API key que los agentes).
# Verificado: openrouter.ai/api/v1/embeddings soporta text-embedding-3-small.
# Vector store: PgVector en la misma PostgreSQL del sistema (pgvector ya instalado).
# Carga: idempotente — primer arranque indexa los docs, arranques posteriores son no-op.
#
# Ref embedder: https://openrouter.ai (probado con text-embedding-3-small, 1536 dims)
# Ref knowledge: https://docs.agno.com/knowledge/introduction
# ---------------------------------------------------------------------------
_KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"

knowledge_base = Knowledge(
    vector_db=PgVector(
        table_name="martes_knowledge",
        db_url=settings.database_url,
        # OpenAIEmbedder (no OpenAILikeEmbedder) — la clase base inicializa
        # el cliente OpenAI con api_key y base_url correctamente.
        # OpenAILikeEmbedder sobreescribe __post_init__ con pass y nunca
        # instancia el cliente, causando 401 al llamar a OpenRouter.
        # Ref: agno==2.6.8 source, knowledge/embedder/openai_like.py
        embedder=OpenAIEmbedder(
            id="openai/text-embedding-3-small",
            api_key=settings.openrouter_api_key,
            base_url="https://openrouter.ai/api/v1",
        ),
    ),
    # readers: Dict[str, Reader] — mapea extensión de archivo a reader.
    # ".md" es el ContentType correcto para MarkdownReader.
    # Ref: agno==2.6.8 source, knowledge/types.py (ContentType enum)
    readers={".md": MarkdownReader()},
)
