"""Shared infrastructure: DB, models, context providers, learning.

Pattern: Scout (ContextProviders) + Coda (coordinate mode + learnings).
"""

from pathlib import Path

from agno.compression.manager import CompressionManager
from agno.context.database import DatabaseContextProvider
from agno.context.wiki import FileSystemBackend, WikiContextProvider
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
# Database
# ---------------------------------------------------------------------------

db = PostgresDb(
    db_url=settings.database_url,
    session_table="martes_sessions",
    memory_table="martes_memories",
    traces_table="martes_traces",
)

# SQLAlchemy engines for DatabaseContextProvider
from sqlalchemy import create_engine  # noqa: E402

_pg_url = settings.database_url  # postgresql+psycopg://...
sql_engine = create_engine(_pg_url)
readonly_engine = create_engine(_pg_url, execution_options={"postgresql_readonly": True})

# ---------------------------------------------------------------------------
# Models
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
# Context Providers (Scout pattern)
# ---------------------------------------------------------------------------
# Each provider auto-generates query_<id> + update_<id> tools.

_DATA_DIR = Path("/var/lib/martes/meta-agent")
_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Wiki: persistent knowledge the agent reads and writes
_WIKI_PATH = _DATA_DIR / "wiki"
_WIKI_PATH.mkdir(parents=True, exist_ok=True)

wiki_provider = WikiContextProvider(
    id="knowledge",
    name="Platform Knowledge",
    backend=FileSystemBackend(path=_WIKI_PATH),
    model=MODEL,
    read_instructions=(
        "Search the platform wiki for operational knowledge: "
        "procedures, troubleshooting, tenant history, incident reports."
    ),
    write_instructions=(
        "Save important findings to the wiki: new procedures discovered, "
        "incident resolutions, tenant-specific notes. Use descriptive filenames."
    ),
)

# Database: direct SQL access to tenants, payments, health
_DB_SCHEMA = """
Tables:
- tenants (id, tenant_code, name, email, plan, status, container_name, paid_until)
- instance_configs (tenant_id, template, platforms, skills, model, memory_limit_mb, cpu_limit)
- payments (tenant_id, amount, currency, method, reference, period_start, period_end)
- health_checks (tenant_id, status, response_ms, checked_at)
- error_logs (tenant_id, source, severity, message, resolved, created_at)
"""

db_provider = DatabaseContextProvider(
    id="crm",
    name="Tenant Database",
    sql_engine=sql_engine,
    readonly_engine=readonly_engine,
    schema=_DB_SCHEMA,
    model=MODEL,
    read_instructions=(
        "Query the tenant database for: tenant info, payment status, "
        "health history, error logs. Use tenant_code to identify tenants."
    ),
    write_instructions=(
        "Insert records for: new tenants, payments, health checks, error logs. "
        "NEVER delete or drop tables. Only INSERT and UPDATE."
    ),
)

# ---------------------------------------------------------------------------
# Knowledge Base (LanceDB + embeddings for RAG)
# ---------------------------------------------------------------------------

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
    description="Hermes reference, operational procedures, config documentation.",
    vector_db=vector_db,
    contents_db=db,
)

# Index docs on startup
_KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"
if _KNOWLEDGE_DIR.exists():
    for _file in sorted(_KNOWLEDGE_DIR.iterdir()):
        if _file.suffix.lower() in {".md", ".txt"}:
            knowledge_base.insert(path=_file, skip_if_exists=True)

# Learnings
learnings_db = LanceDb(
    uri=str(_DATA_DIR / "lancedb"),
    table_name="martes_learnings",
    search_type=SearchType.hybrid,
    embedder=embedder,
)

learnings_knowledge = Knowledge(
    name="Martes Learnings",
    description="Operational patterns, incident resolutions, tenant history.",
    vector_db=learnings_db,
    contents_db=db,
)

# ---------------------------------------------------------------------------
# Learning Machine (Coda pattern)
# ---------------------------------------------------------------------------

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
# Compression
# ---------------------------------------------------------------------------

compression = CompressionManager(model=FAST_MODEL, compress_tool_results=True)

# ---------------------------------------------------------------------------
# Skills (lazy-loaded)
# ---------------------------------------------------------------------------

_SKILLS_DIR = Path(__file__).parent / "skills"
skills = Skills(loaders=[LocalSkills(str(_SKILLS_DIR))]) if _SKILLS_DIR.exists() else None
