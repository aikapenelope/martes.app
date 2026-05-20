"""Skill Builder — Agente experto en crear, configurar y gestionar skills.

Este agente sabe como funciona el sistema de skills de Agno/Hermes y puede:
- Crear nuevos SKILL.md con el formato correcto
- Listar skills existentes
- Explicar como se conectan y se cargan (lazy-loading)
- Guardarlos en el directorio correcto

Las skills se guardan en src/skills/ (para el meta-agente) o se inyectan
en el volumen del tenant (para agentes Hermes).
"""

import json
import os
from pathlib import Path

from agno.agent import Agent
from agno.tools.decorator import tool

from src.config import settings
from src.shared import MODEL, db, knowledge_base, learning, skills

# Directorio de skills del meta-agente
_META_SKILLS_DIR = Path(__file__).parent.parent / "skills"

# Directorio base de tenants (para inyectar skills a Hermes)
_TENANTS_DIR = Path(settings.tenants_base_path)


@tool()
def list_skills() -> str:
    """Lista todas las skills disponibles en el sistema del meta-agente."""
    results = []
    if _META_SKILLS_DIR.exists():
        for item in sorted(_META_SKILLS_DIR.iterdir()):
            skill_file = item / "SKILL.md"
            if item.is_dir() and skill_file.exists():
                # Leer nombre y descripcion del frontmatter
                content = skill_file.read_text()
                name = item.name
                desc = ""
                for line in content.split("\n"):
                    if line.startswith("description:"):
                        desc = line.split(":", 1)[1].strip().strip('"')
                        break
                results.append({"name": name, "description": desc, "path": str(item)})
    return json.dumps({"count": len(results), "skills": results})


@tool()
def read_skill(skill_name: str) -> str:
    """Lee el contenido completo de una skill existente.

    Args:
        skill_name: Nombre de la skill (nombre de la carpeta).
    """
    skill_path = _META_SKILLS_DIR / skill_name / "SKILL.md"
    if not skill_path.exists():
        return json.dumps({"error": f"Skill '{skill_name}' no encontrada."})
    return json.dumps({"name": skill_name, "content": skill_path.read_text()})


@tool(requires_confirmation=True)
def create_skill(
    skill_name: str,
    description: str,
    content: str,
    target: str = "meta-agent",
    tenant_code: str = "",
) -> str:
    """Crea una nueva skill con formato SKILL.md valido.

    Args:
        skill_name: Nombre de la skill (slug, sin espacios, con guiones).
        description: Descripcion corta de la skill.
        content: Contenido markdown de la skill (instrucciones, procedimientos).
        target: Donde guardar: 'meta-agent' o 'tenant'.
        tenant_code: Codigo del tenant (solo si target='tenant').
    """
    # Validar nombre
    if " " in skill_name or not skill_name.replace("-", "").isalnum():
        return json.dumps({
            "error": "Nombre invalido. Usar slug con guiones: 'mi-skill-nueva'"
        })

    # Determinar directorio destino
    if target == "tenant" and tenant_code:
        skill_dir = _TENANTS_DIR / tenant_code / "skills" / skill_name
    else:
        skill_dir = _META_SKILLS_DIR / skill_name

    # Crear directorio
    skill_dir.mkdir(parents=True, exist_ok=True)

    # Construir SKILL.md con frontmatter valido
    skill_md = f"""---
name: {skill_name}
description: "{description}"
license: MIT
metadata:
  tags: [custom]
  category: operations
---

{content}
"""

    # Escribir
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(skill_md)

    # Si es para un tenant, ajustar permisos
    if target == "tenant" and tenant_code:
        try:
            os.chown(skill_dir, 1000, 1000)
            os.chown(skill_file, 1000, 1000)
        except PermissionError:
            pass

    return json.dumps({
        "success": True,
        "skill_name": skill_name,
        "target": target,
        "tenant_code": tenant_code or "n/a",
        "path": str(skill_file),
        "message": (
            f"Skill '{skill_name}' creada. "
            + ("Reinicia el meta-agente para cargarla." if target == "meta-agent"
               else f"Reinicia el container de {tenant_code} para activarla.")
        ),
    })


@tool()
def list_tenant_skills(tenant_code: str) -> str:
    """Lista las skills instaladas en un tenant Hermes especifico.

    Args:
        tenant_code: Codigo del tenant (e.g. t001).
    """
    skills_dir = _TENANTS_DIR / tenant_code / "skills"
    if not skills_dir.exists():
        return json.dumps({"tenant": tenant_code, "count": 0, "skills": []})

    results = []
    for item in sorted(skills_dir.iterdir()):
        if item.is_dir() and (item / "SKILL.md").exists():
            results.append({"name": item.name})
    return json.dumps({"tenant": tenant_code, "count": len(results), "skills": results})


# ---------------------------------------------------------------------------
# Agent definition
# ---------------------------------------------------------------------------

skill_builder = Agent(
    name="Skill Builder",
    id="skill-builder",
    role="Expert in creating, configuring, and managing Agno/Hermes skills.",
    description=(
        "Crea y gestiona skills para el meta-agente y para tenants Hermes. "
        "Sabe el formato correcto de SKILL.md, como se cargan (lazy-loading), "
        "y donde guardarlas."
    ),
    model=MODEL,
    tools=[
        list_skills,
        read_skill,
        create_skill,
        list_tenant_skills,
    ],
    tool_call_limit=5,
    knowledge=knowledge_base,
    search_knowledge=True,
    learning=learning,
    skills=skills,
    db=db,
    add_history_to_context=True,
    num_history_runs=3,
    add_datetime_to_context=True,
    markdown=True,
    instructions=[
        "Eres un experto en el sistema de Skills de Agno y Hermes.",
        "",
        "## Como funcionan las Skills",
        "- Una skill es una carpeta con un archivo SKILL.md dentro",
        "- El SKILL.md tiene frontmatter YAML (name, description, license, metadata)",
        "- El contenido es markdown con instrucciones que el agente sigue",
        "- Se cargan LAZY: el agente ve un resumen, carga completo solo cuando necesita",
        "- No consumen tokens hasta que se activan",
        "",
        "## Frontmatter valido (SOLO estos campos):",
        "```yaml",
        "---",
        "name: nombre-con-guiones",
        "description: \"Descripcion corta\"",
        "license: MIT",
        "metadata:",
        "  tags: [tag1, tag2]",
        "  category: operations",
        "---",
        "```",
        "",
        "## Campos NO permitidos en frontmatter:",
        "- version, author, platforms (causan error de validacion)",
        "",
        "## Donde se guardan:",
        "- Meta-agente: src/skills/{nombre}/SKILL.md",
        "- Tenant Hermes: /var/lib/martes/tenants/{code}/skills/{nombre}/SKILL.md",
        "",
        "## Para el meta-agente:",
        "Despues de crear una skill, hay que reiniciar para que se cargue.",
        "",
        "## Para tenants Hermes:",
        "Las skills se guardan en el volumen del tenant.",
        "Hermes las detecta automaticamente sin reiniciar.",
        "",
        "## Reglas:",
        "- Nombres en slug (minusculas, guiones, sin espacios)",
        "- Descripcion clara y concisa",
        "- Contenido con instrucciones paso a paso",
        "- Incluir ejemplos cuando sea posible",
        "- Responde en espanol",
    ],
)
