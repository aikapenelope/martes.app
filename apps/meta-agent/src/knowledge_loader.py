"""Carga knowledge base del meta-agente desde archivos markdown."""

from pathlib import Path

_KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"


def load_knowledge() -> str:
    """Lee todos los archivos .md del directorio knowledge/ y los concatena.

    Este contenido se inyecta en las instructions del agente como contexto
    de referencia. No usa embeddings ni RAG — es contexto directo.

    Returns:
        String con todo el knowledge concatenado, separado por headers.
    """
    sections: list[str] = []

    if not _KNOWLEDGE_DIR.exists():
        return ""

    for md_file in sorted(_KNOWLEDGE_DIR.glob("*.md")):
        content = md_file.read_text(encoding="utf-8").strip()
        if content:
            sections.append(content)

    return "\n\n---\n\n".join(sections)
