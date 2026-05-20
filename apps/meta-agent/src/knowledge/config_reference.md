# Hermes config.yaml — Referencia Completa

## Estructura del config.yaml

El archivo `config.yaml` controla todo el comportamiento de un agente Hermes.
Se ubica en `/opt/data/config.yaml` dentro del container.

## Secciones principales

### model (LLM)
```yaml
model:
  provider: openrouter
  default: deepseek/deepseek-chat
  base_url: "https://openrouter.ai/api/v1"
```

### platform_toolsets (herramientas por plataforma)
```yaml
platform_toolsets:
  telegram: [hermes-telegram]  # preset completo
  # O toolsets individuales:
  telegram: [web, memory, todo, cronjob, clarify, vision, skills]
```

Toolsets disponibles:
- web: web_search, web_extract
- terminal: terminal, process
- file: read_file, write_file, patch, search
- browser: navegacion web completa (requiere Browserbase o Playwright)
- vision: vision_analyze
- image_gen: image_generate (requiere FAL_KEY)
- skills: skills_list, skill_view
- todo: task planning
- tts: text-to-speech
- cronjob: scheduled tasks
- memory: persistent memory
- session_search: buscar en conversaciones pasadas

Presets:
- hermes-telegram: terminal, file, web, vision, image_gen, tts, browser, skills, todo, cronjob
- hermes-discord: igual que telegram
- hermes-whatsapp: igual que telegram

### compression (manejo de contexto largo)
```yaml
compression:
  enabled: true
  threshold: 0.50    # comprimir al 50% del limite de contexto
  target_ratio: 0.20 # preservar 20% como tail reciente
  protect_last_n: 20 # proteger ultimos 20 mensajes
```

### memory (memoria persistente)
```yaml
memory:
  memory_enabled: true
  user_profile_enabled: true
  memory_char_limit: 2200   # ~800 tokens
  user_char_limit: 1375     # ~500 tokens
  nudge_interval: 10        # recordar guardar cada 10 turnos
```

### session_reset (reset automatico en messaging)
```yaml
session_reset:
  mode: both           # both, idle, daily, none
  idle_minutes: 1440   # 24 horas
  at_hour: 4           # 4 AM
```

### agent (comportamiento)
```yaml
agent:
  max_turns: 60        # iteraciones maximas por conversacion
  reasoning_effort: "medium"  # xhigh, high, medium, low, minimal, none
```

### streaming (respuestas en tiempo real)
```yaml
streaming:
  enabled: true
  edit_interval: 0.3
  buffer_threshold: 40
```

### tool_loop_guardrails (proteccion contra loops)
```yaml
tool_loop_guardrails:
  warnings_enabled: true
  hard_stop_enabled: true
  hard_stop_after:
    exact_failure: 5
    same_tool_failure: 8
```

### code_execution (sandbox de codigo)
```yaml
code_execution:
  timeout: 300
  max_tool_calls: 50
```

### delegation (subagentes)
```yaml
delegation:
  max_iterations: 50
  max_spawn_depth: 1
```

### mcp_servers (Model Context Protocol)
```yaml
mcp_servers:
  notion:
    url: https://mcp.notion.com/mcp
  github:
    command: npx
    args: ["-y", "@modelcontextprotocol/server-github"]
    env:
      GITHUB_PERSONAL_ACCESS_TOKEN: "${GITHUB_TOKEN}"
```

### stt (speech-to-text)
```yaml
stt:
  enabled: true
  # provider: "local" (faster-whisper, gratis)
```

## Configuracion por plan en martes.app

| Setting | Basico | Equipo | Pro |
|---------|--------|--------|-----|
| toolsets | web,memory,todo,cronjob,clarify | +vision,skills | hermes-telegram (todo) |
| compression threshold | 0.30 | 0.40 | 0.50 |
| memory_char_limit | 1500 | 2200 | 2200 |
| max_turns | 30 | 50 | 60 |
| reasoning_effort | low | medium | medium |
| streaming | true | true | true |
| hard_stop | true | true | true |
| code_execution | no | no | si (timeout 30s) |
| delegation | no | no | si (depth 1) |
| browser | no | firecrawl | playwright |
