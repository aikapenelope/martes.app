# Sprint G — install_skill_in_tenant()

> **Único item activo de este sprint**  
> **Estado**: pendiente de implementación  
> **Nota**: el plan original de PocketBase CRM fue descartado. Ver `docs/10-ROADMAP.md` sección "Descartado".  
> El CRM se implementará en Sprint H cuando PocketBase alcance v1.0.0.

---

## Problema que resuelve

El cliente de Hermes no puede instalar skills por sí mismo desde Telegram porque
`hermes skills install X` es un comando CLI que requiere detener y reiniciar el
gateway — y el gateway ES el proceso que está corriendo.

El meta-agente SÍ puede hacerlo: tiene acceso al volumen del tenant via Docker SDK
y puede copiar archivos + reiniciar el container.

---

## G1 — `install_skill_in_tenant()`

**Archivo**: `apps/meta-agent/src/tools/write_ops.py`  
**Archivo**: `apps/meta-agent/src/agents/operador.py`

```python
@tool
def install_skill_in_tenant(tenant_code: str, skill_name: str) -> str:
    """Instala una skill en el tenant de Hermes desde el hub oficial.

    El cliente no puede instalar skills directamente — el CLI requiere
    reiniciar el gateway, que es el proceso principal del container.
    El meta-agente copia los archivos al volumen y hace el restart.

    Fuentes de skills:
    - Hub oficial: https://agentskills.io
    - Hermes built-in optional skills: skills/ del repo NousResearch/hermes-agent
    - Skills conocidas: airtable, notion, google-workspace, stocks, shopify, solana

    Flujo:
    1. Descargar SKILL.md (y archivos adicionales) de la fuente
    2. Copiar a /var/lib/martes/tenants/{code}/skills/{skill_name}/
    3. Reiniciar hermes-{code} para que cargue la nueva skill
    4. Verificar health OK

    Requiere aprobación — reinicia el container del cliente.
    """
```

### Implementación

```python
# Fuentes de skills conocidas en el repo oficial de Hermes:
_KNOWN_SKILLS: dict[str, str] = {
    "airtable":         "skills/productivity/airtable",
    "notion":           "skills/productivity/notion",
    "google-workspace": "skills/productivity/google-workspace",
    "stocks":           "optional-skills/finance/stocks",
    "shopify":          "optional-skills/productivity/shopify",
    "solana":           "optional-skills/blockchain/solana",
    "evm":              "optional-skills/blockchain/evm",
}
_HERMES_REPO = "https://raw.githubusercontent.com/NousResearch/hermes-agent/main"

def install_skill_in_tenant(tenant_code: str, skill_name: str) -> str:
    tenant_path = Path(settings.tenants_base_path) / tenant_code
    skills_dir = tenant_path / "skills" / skill_name

    if skill_name not in _KNOWN_SKILLS:
        return json.dumps({
            "error": f"Skill '{skill_name}' no reconocida.",
            "available": list(_KNOWN_SKILLS.keys()),
        })

    # Crear directorio de la skill
    skills_dir.mkdir(parents=True, exist_ok=True)

    # Descargar SKILL.md desde GitHub
    skill_path = _KNOWN_SKILLS[skill_name]
    url = f"{_HERMES_REPO}/{skill_path}/SKILL.md"
    response = requests.get(url, timeout=15)
    if response.status_code != 200:
        return json.dumps({"error": f"No se pudo descargar la skill: HTTP {response.status_code}"})

    (skills_dir / "SKILL.md").write_text(response.text)
    _chown(skills_dir)

    # Reiniciar el container para que Hermes cargue la skill
    c = _docker()
    try:
        c.containers.get(f"hermes-{tenant_code}").restart(timeout=30)
    except NotFound:
        return json.dumps({"error": f"Container hermes-{tenant_code} no encontrado."})

    # Verificar health tras restart (hasta 30s)
    time.sleep(5)
    health_result = container_health(tenant_code)
    health_data = json.loads(health_result)

    return json.dumps({
        "success": True,
        "tenant": tenant_code,
        "skill": skill_name,
        "path": str(skills_dir),
        "health_after_restart": health_data.get("status"),
        "message": (
            f"Skill '{skill_name}' instalada en {tenant_code}. "
            f"El container fue reiniciado y cargó la nueva skill. "
            f"El cliente ya puede usarla desde Telegram."
        ),
    })
```

### Registro en el Operador

```python
# agents/operador.py — añadir a imports y tools list:
from src.tools.write_ops import install_skill_in_tenant

# tools=[...]:
install_skill_in_tenant,
```

### Instrucción al Operador

```
"Si el cliente quiere usar una skill nueva (airtable, notion, stocks, etc.):",
"  usa install_skill_in_tenant(tenant_code, skill_name).",
"  Requiere confirmación — reinicia el container del cliente.",
"  Skills disponibles: airtable, notion, google-workspace, stocks, shopify, solana, evm",
```

---

## Orden de implementación

```
1. Escribir install_skill_in_tenant() en write_ops.py
2. Añadir import + tool en operador.py
3. Añadir instrucción al bloque de instructions del Operador
4. Validar pyright + ruff
5. PR → merge
```
