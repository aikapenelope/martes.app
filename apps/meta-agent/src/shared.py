"""Shared infrastructure: DB, models, knowledge, learning, compression.

All agents share these components. Initialized once at import time.
"""

from pathlib import Path

from agno.compression.manager import CompressionManager
from agno.db.postgres import PostgresDb
from agno.knowledge.embedder.openai import OpenAIEmbedder
from agno.knowledge.knowledge import Knowledge
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
from agno.vectordb.lancedb import LanceDb, SearchType

from src.config import settings

# ---------------------------------------------------------------------------
# Database (PostgreSQL — sessions, memory, traces)
# ---------------------------------------------------------------------------

db = PostgresDb(
    db_url=settings.database_url,
    session_table="martes_sessions",
    memory_table="martes_memories",
    traces_table="martes_traces",
)

# ---------------------------------------------------------------------------
# Models (DeepSeek V4 via OpenRouter)
# ---------------------------------------------------------------------------

# Primary model: tool calling, reasoning, general use
PRIMARY_MODEL = OpenAIChat(
    id=settings.default_model,
    api_key=settings.openrouter_api_key,
    base_url="https://openrouter.ai/api/v1",
)

# Fast model: compression, learning, background tasks
FAST_MODEL = OpenAIChat(
    id="deepseek/deepseek-chat",
    api_key=settings.openrouter_api_key,
    base_url="https://openrouter.ai/api/v1",
)

# ---------------------------------------------------------------------------
# Knowledge Base (LanceDB local + OpenAI embeddings via OpenRouter)
# ---------------------------------------------------------------------------
# LanceDB stores vectors locally (like SQLite for vectors).
# OpenAI embeddings via OpenRouter for generating vectors.
# Docs in knowledge/ are indexed on startup.

_DATA_DIR = Path("/var/lib/martes/meta-agent")
_DATA_DIR.mkdir(parents=True, exist_ok=True)

embedder = OpenAIEmbedder(
    id="openai/text-embedding-3-small",
    dimensions=512,
    api_key=settings.openrouter_api_key,
    base_url="https://openrouter.ai/api/v1",
)

vector_db = LanceDb(
    uri=str(_DATA_DIR / "lancedb"),
    table_name="martes_knowledge",
    search_type=SearchType.hybrid,
    embedder=embedder,
)

knowledge_base = Knowledge(
    name="Martes Knowledge",
    description=(
        "Infrastructure documentation: Hermes agent reference, "
        "operational procedures, troubleshooting guides."
    ),
    vector_db=vector_db,
    contents_db=db,
)

# Learnings: what the agents learn over time (incidents, patterns, tenant info)
learnings_db = LanceDb(
    uri=str(_DATA_DIR / "lancedb"),
    table_name="martes_learnings",
    search_type=SearchType.hybrid,
    embedder=embedder,
)

learnings_knowledge = Knowledge(
    name="Martes Learnings",
    description="Accumulated operational patterns, incident resolutions, tenant history.",
    vector_db=learnings_db,
    contents_db=db,
)

# Index knowledge docs on import
_KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"
if _KNOWLEDGE_DIR.exists():
    for _file in sorted(_KNOWLEDGE_DIR.iterdir()):
        if _file.suffix.lower() in {".md", ".txt"}:
            knowledge_base.insert(path=_file, skip_if_exists=True)

# ---------------------------------------------------------------------------
# Learning Machine (self-improving across sessions)
# ---------------------------------------------------------------------------
# Remembers: tenants, incidents, admin preferences, operational patterns.
# Uses AGENTIC mode: the agent decides what to learn via tool calls.

learning = LearningMachine(
    model=FAST_MODEL,
    knowledge=learnings_knowledge,
    user_memory=UserMemoryConfig(mode=LearningMode.AGENTIC),
    entity_memory=EntityMemoryConfig(mode=LearningMode.AGENTIC, namespace="martes"),
    learned_knowledge=LearnedKnowledgeConfig(mode=LearningMode.AGENTIC),
    decision_log=DecisionLogConfig(mode=LearningMode.AGENTIC),
    session_context=SessionContextConfig(enable_planning=True),
)

# ---------------------------------------------------------------------------
# Compression (saves tokens on long tool outputs)
# ---------------------------------------------------------------------------

compression = CompressionManager(
    model=FAST_MODEL,
    compress_tool_results=True,
)

# ---------------------------------------------------------------------------
# Skills (lazy-loaded domain knowledge)
# ---------------------------------------------------------------------------
# Skills are loaded on demand: agents see summaries in their system prompt,
# then load full instructions only when relevant. Saves tokens.

_SKILLS_DIR = Path(__file__).parent / "skills"
skills = Skills(loaders=[LocalSkills(str(_SKILLS_DIR))]) if _SKILLS_DIR.exists() else None
