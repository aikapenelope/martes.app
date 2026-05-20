# Hermes Agent — Guia de Optimizacion y Configuracion por Caso de Uso

> **Fuente**: Repo `nousresearch/hermes-agent` v0.14.0 (May 2026)
> **Audiencia**: Admin de martes.app

---

## 1. Instalacion en v0.14.0: Lo que cambio completamente

### Antes (hasta v0.13)
```bash
git clone https://github.com/NousResearch/hermes-agent
cd hermes-agent && uv sync
hermes gateway run
```
Clonabas todo el repo (~500MB), instalabas todas las dependencias, y todo cargaba en memoria.

### Ahora (v0.14.0) — Lazy-deps system

```bash
# Forma 1: PyPI (nueva)
pip install hermes-agent
hermes gateway run

# Forma 2: Docker (nuestro modo para SaaS)
docker run nousresearch/hermes-agent:0.14.0 gateway run
```

**Como funciona el sistema lazy**:
```
hermes gateway run
├── Carga: gateway core, LLM client, SQLite
├── NO carga: Slack adapter, Discord SDK, image gen, TTS, Matrix...
│
├── Usuario conecta Telegram → lazy-instala python-telegram-bot
├── Usuario usa browser → lazy-instala playwright
└── Usuario usa TTS → lazy-instala edge-tts
```

Controlado por `security.allow_lazy_installs` en `config.yaml`:
```yaml
security:
  allow_lazy_installs: true   # Permite instalar backends bajo demanda
  # allow_lazy_installs: false  # Solo lo que ya esta instalado
```

**Para SaaS**: `false` en basico/equipo (no queremos que los tenants
instalen cosas), `true` en pro (mas libertad).

---

## 2. Toolsets: La lista completa de lo disponible

### Toolsets individuales (atomos)

| Toolset | Tools incluidos | Token overhead aprox |
|---------|----------------|---------------------|
| `web` | web_search, web_extract | ~800 tokens |
| `search` | web_search (solo) | ~400 tokens |
| `terminal` | terminal, process | ~1200 tokens |
| `file` | read_file, write_file, patch, search_files | ~1000 tokens |
| `browser` | browser_navigate, snapshot, click, type, scroll, back, press, get_images, vision, console, cdp, dialog, web_search | ~3500 tokens |
| `vision` | vision_analyze | ~500 tokens |
| `image_gen` | image_generate | ~600 tokens |
| `skills` | skills_list, skill_view, skill_manage | ~700 tokens |
| `tts` | text_to_speech | ~400 tokens |
| `todo` | todo | ~500 tokens |
| `memory` | memory | ~600 tokens |
| `session_search` | session_search | ~700 tokens |
| `clarify` | clarify | ~400 tokens |
| `cronjob` | cronjob | ~800 tokens |
| `moa` | mixture_of_agents | ~600 tokens |
| `safe` | incluye: web, vision, image_gen | sin terminal |
| `debugging` | incluye: terminal, web, file | para devs |

### Presets (bundles)

| Preset | Incluye | Token overhead |
|--------|---------|----------------|
| `hermes-telegram` | TODOS los core tools (terminal, file, web, browser, vision, image_gen, tts, skills, todo, memory, session_search, clarify, execute_code, delegate, cronjob, send_message, + HA, kanban) | ~13,900 tokens |
| `hermes-discord` | mismo + discord, discord_admin | ~14,500 tokens |
| `hermes-cli` | igual a telegram pero sin send_message | ~13,500 tokens |

**El preset completo consume 8-14K tokens de tool definitions FIJOS por request.**
Con cache de DeepSeek (90% descuento en cache hits), el costo real es mucho menor.
Con Claude (1h cross-session cache), el tool overhead se cachea entre sesiones.

---

## 3. Skills incluidas en Hermes (del repo oficial)

Hermes trae skills pre-instaladas organizadas por categoria.
Se instalan en `/opt/data/skills/` via `tools/skills_sync.py` al bootear.

### Productividad (las mas relevantes para nuestro SaaS)

| Skill | Que hace | Requiere |
|-------|----------|----------|
| `google-workspace` | Gmail, Calendar, Drive, Docs, Sheets via OAuth | google_token.json |
| `notion` | Notion API + CLI `ntn` | NOTION_API_KEY |
| `airtable` | Airtable REST API | AIRTABLE_API_KEY |
| `linear` | Linear issues, cycles, projects | LINEAR_API_KEY |
| `ocr-and-documents` | OCR, PDF extraction, document parsing | — |
| `nano-pdf` | PDF lightweight reader | — |
| `powerpoint` | Crear/editar presentaciones | — |
| `maps` | Google Maps, navegacion | — |

### Research

| Skill | Que hace |
|-------|----------|
| `llm-wiki` | Karpathy LLM Wiki (knowledge base acumulativo) |
| `arxiv` | Busqueda de papers academicos |
| `blogwatcher` | Monitorear RSS/blogs via cron |
| `research-paper-writing` | Escribir papers estructurados |

### Email

| Skill | Que hace | Requiere |
|-------|----------|----------|
| `himalaya` | Email IMAP/SMTP (alternativa a Google) | EMAIL_ADDRESS, EMAIL_PASSWORD |

### Dev

| Skill | Que hace |
|-------|----------|
| `github-pr-workflow` | PR lifecycle, reviews |
| `github-issues` | Issue management |
| `github-code-review` | Code review automatizado |
| `github-repo-management` | Gestionar repos |
| `test-driven-development` | TDD workflow |
| `subagent-driven-development` | Delegar a subagentes |

### Agentes autonomos

| Skill | Que hace |
|-------|----------|
| `kanban-orchestrator` | Coordinar multi-agentes via kanban |
| `kanban-worker` | Ser un worker de un kanban |
| `webhook-subscriptions` | Suscribirse a eventos via webhook |

---

## 4. Configuraciones optimas por caso de uso

### Caso A: Asistente personal (un solo usuario, Telegram)
**Perfil**: Freelancer o persona individual

```yaml
model:
  default: deepseek/deepseek-chat
  provider: openrouter
  base_url: "https://openrouter.ai/api/v1"

platform_toolsets:
  telegram: [web, memory, todo, cronjob, clarify, session_search]

skills:
  disabled: []  # Todos los skills disponibles

compression:
  enabled: true
  threshold: 0.30

memory:
  memory_char_limit: 2200
  user_char_limit: 1375

session_reset:
  mode: both
  idle_minutes: 1440
  at_hour: 4

agent:
  max_turns: 40
  reasoning_effort: "low"

tool_loop_guardrails:
  hard_stop_enabled: true
  hard_stop_after:
    exact_failure: 3
```

### Caso B: Asistente de equipo PYME (5-10 personas, Telegram + Discord)
**Perfil**: Startup, agencia digital

```yaml
model:
  default: deepseek/deepseek-chat

platform_toolsets:
  telegram: [web, memory, todo, cronjob, clarify, vision, skills,
             session_search, tts]
  discord: [web, memory, todo, cronjob, clarify, vision, skills,
            session_search]

skills:
  disabled: [github-pr-workflow, test-driven-development]  # Solo si no son devs

session_reset:
  mode: both
  idle_minutes: 720  # Reset mas frecuente en equipo
  at_hour: 4

agent:
  max_turns: 50

group_sessions_per_user: true  # Clave: aislamiento entre miembros del equipo
```

### Caso C: Asistente dev team (devs, GitHub heavy)
**Perfil**: Dev team, manejo de codigo y PRs

```yaml
model:
  default: anthropic/claude-3.5-haiku  # Claude para mejor razonamiento de codigo

platform_toolsets:
  telegram: [web, memory, todo, cronjob, clarify, vision, skills,
             session_search, browser]
  discord: [web, memory, todo, cronjob, clarify, vision, skills,
            session_search, browser]

skills:
  disabled: []  # Habilitar todas, especialmente github-*

mcp_servers:
  github:
    command: npx
    args: ["-y", "@modelcontextprotocol/server-github"]
    env:
      GITHUB_PERSONAL_ACCESS_TOKEN: "${GITHUB_TOKEN}"

agent:
  max_turns: 60
  reasoning_effort: "medium"

delegation:
  max_iterations: 40
  max_spawn_depth: 1
```

### Caso D: Agente de atencion al cliente (WhatsApp, alto volumen)
**Perfil**: Negocio con muchos clientes

```yaml
model:
  default: deepseek/deepseek-chat

platform_toolsets:
  whatsapp: [web, memory, todo, clarify]  # Minimo para respuesta rapida
  # Sin browser, sin image_gen, sin tts — velocidad maxima

memory:
  memory_char_limit: 1500
  nudge_interval: 0  # No guardar memories automaticamente (privacidad)

session_reset:
  mode: idle
  idle_minutes: 60   # Reset rapido para limpiar contexto entre clientes

agent:
  max_turns: 20  # Conversaciones cortas de soporte
  reasoning_effort: "low"

tool_loop_guardrails:
  hard_stop_enabled: true
  hard_stop_after:
    exact_failure: 2  # Fail fast en soporte
```

### Caso E: Agente de investigacion (research-heavy)
**Perfil**: Analistas, investigadores, content creators

```yaml
model:
  default: anthropic/claude-3.5-haiku  # Mejor sintesis

platform_toolsets:
  telegram: [web, browser, memory, skills, session_search, vision,
             todo, cronjob]

skills:
  disabled: [github-pr-workflow, kanban-orchestrator]  # No relevante

# Habilitar llm-wiki para knowledge acumulativo
# wiki se construye automaticamente via skills

agent:
  max_turns: 60
  reasoning_effort: "medium"

compression:
  threshold: 0.50  # Permitir mas contexto para investigacion profunda
  protect_last_n: 25
```

---

## 5. Skills: Como funcionan internamente y como configurarlas

### Ciclo de vida de una skill en Hermes

```
Boot del container
└── skills_sync.py escanea /opt/hermes/skills/ (bundled)
    └── Copia a /opt/data/skills/ (volumen) si no existe
        └── No sobreescribe skills editadas por el usuario

Sesion de usuario
└── system_prompt.py construye el system prompt
    └── Incluye lista de skills disponibles (solo names + descriptions)
        └── Agente ve: "Tienes estos skills disponibles: X, Y, Z"
            └── Cuando el agente usa skill_view:
                └── Carga el SKILL.md completo en contexto
```

### Formato correcto de SKILL.md (v0.14.0)

El repo trae skills con campos adicionales que Agno no soporta.
Para NUESTRO sistema de skills del meta-agente, usar el subset valido:

```markdown
---
name: nombre-skill        # obligatorio, slug
description: "texto"     # obligatorio
license: MIT             # recomendado
metadata:
  tags: [tag1, tag2]
  category: operations
---

# Titulo

## Cuando usar esta skill
Describe el trigger exacto.

## Scripts (opcional)
Comandos que el agente puede ejecutar.

## Procedimiento
Pasos numerados.
```

### Inline shell en skills

Skills pueden ejecutar comandos al cargarse:
```markdown
Fecha actual: !`date +%Y-%m-%d`
Espacio en disco: !`df -h /opt/data | tail -1`
```

### Variables de template
```markdown
Directorio de la skill: ${HERMES_SKILL_DIR}
Session ID actual: ${HERMES_SESSION_ID}
```

### Deshabilitar skills por plataforma

```yaml
skills:
  disabled: [github-pr-workflow, kanban-worker]  # Global
  platform_disabled:
    telegram: [powerpoint, arxiv]  # Solo en Telegram
    discord: []                    # Ninguna en Discord
```

---

## 6. Configuracion de cron (automatizaciones sin usuario)

Hermes tiene cron nativo. Los jobs se guardan en `/opt/data/cron/jobs.json`.

### Crear via Telegram
```
/cron create "0 9 * * 1-5" "Resume las noticias de AI de esta semana y enviamelas" --name "briefing-semanal"
```

### Crear via CLI (en el container)
```bash
docker exec hermes-t001 hermes cron create "0 9 * * *" \
  "Haz un resumen de los emails no leidos y envialo por Telegram" \
  --name "daily-digest" \
  --deliver telegram
```

### Delivery a canales especificos
```yaml
# En .env
TELEGRAM_HOME_CHANNEL=123456789  # ID del chat donde entregar cron outputs
TELEGRAM_CRON_THREAD_ID=789      # Thread ID si usa forum topics
```

---

## 7. Optimizacion de tokens: estrategia por plan

### El problema
- `hermes-telegram` preset: ~13,900 tokens fijos por request
- Con DeepSeek V4 ($0.30/M input, 90% cache): ~$0.00042/request con cache
- Sin cache (primera vez): ~$0.0042/request

### Estrategia de cache

DeepSeek y Claude cachean el prefix del system prompt automaticamente.
El cache se activa cuando el mismo prefix se envía dos veces.

Para maximizar cache hits:
1. El system prompt (SOUL.md + tools definitions) debe ser **estable** entre requests
2. Evitar fechas o datos dinamicos en el system prompt
3. `add_datetime_to_context=True` va al final del prompt (no rompe cache del prefix)

### Calculo de costo real por plan

| Plan | Toolset | Tokens fijos | Costo con cache | Costo sin cache |
|------|---------|-------------|-----------------|-----------------|
| Basico | 6 tools | ~3,000 | $0.00009/req | $0.0009/req |
| Equipo | 8 tools | ~4,500 | $0.00014/req | $0.0014/req |
| Pro | sin terminal | ~8,000 | $0.00024/req | $0.0024/req |

Con 100 mensajes/dia:
- Basico: ~$0.009-0.09/dia → $0.27-2.70/mes (cabe bien en $30/mo)
- Equipo: ~$0.014-0.14/dia → $0.42-4.20/mes (cabe en $100/mo)
- Pro: ~$0.024-0.24/dia → $0.72-7.20/mes (cabe en $200/mo)

---

## 8. Perfiles de Hermes (feature avanzada)

Hermes soporta multiples perfiles independientes:
```bash
hermes profile create cliente-xyz --clone  # Clonar config base
hermes -p cliente-xyz gateway run
```

Para nuestro SaaS esto equivale a tener containers separados (lo que ya hacemos).
No necesitamos perfiles — un container = un tenant = un perfil aislado.

La feature de perfiles es util para un solo usuario que quiere
compartimentos (trabajo, personal, investigacion).
