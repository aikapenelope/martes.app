---
name: hermes-config
description: "Configuracion avanzada de agentes Hermes: toolsets, modelos, compression, MCP"
license: MIT
metadata:
  tags: [hermes, config, toolsets, models, optimization]
  category: operations
---

# Configuracion Avanzada de Hermes

## Cambiar modelo LLM de un tenant

Editar `config.yaml` del tenant:
```yaml
model:
  provider: openrouter
  default: deepseek/deepseek-chat  # o anthropic/claude-3.5-haiku
  base_url: "https://openrouter.ai/api/v1"
```

Modelos recomendados por plan:
- Basico: `deepseek/deepseek-chat` (barato, rapido)
- Equipo: `deepseek/deepseek-chat` (balance)
- Pro: `anthropic/claude-3.5-haiku` (mejor razonamiento)

Despues de cambiar: restart del container.

## Ajustar toolsets

Los toolsets controlan que herramientas tiene el agente.

### Toolsets individuales disponibles:
- `web`: web_search, web_extract
- `terminal`: terminal, process (PELIGROSO en multi-tenant)
- `file`: read_file, write_file, patch, search
- `browser`: navegacion web (requiere Browserbase/Playwright)
- `vision`: analisis de imagenes
- `image_gen`: generacion de imagenes (requiere FAL_KEY)
- `skills`: carga de skills bajo demanda
- `todo`: planificacion de tareas
- `tts`: text-to-speech
- `cronjob`: tareas programadas
- `memory`: memoria persistente
- `session_search`: buscar en conversaciones pasadas

### Presets (bundles):
- `hermes-telegram`: todo excepto terminal
- `hermes-discord`: igual que telegram
- `hermes-whatsapp`: igual que telegram

### Configuracion por plan recomendada:
```yaml
# Basico — minimo overhead de tokens
platform_toolsets:
  telegram: [web, memory, todo, cronjob, clarify]

# Equipo — balance
platform_toolsets:
  telegram: [web, memory, todo, cronjob, clarify, vision, skills]
  discord: [web, memory, todo, cronjob, clarify, vision, skills]

# Pro — todo incluido
platform_toolsets:
  telegram: [hermes-telegram]
  discord: [hermes-discord]
```

## Configurar compression

La compression reduce el contexto cuando se acerca al limite del modelo.

```yaml
compression:
  enabled: true
  threshold: 0.50    # comprimir al 50% del contexto
  target_ratio: 0.20 # mantener 20% como mensajes recientes
  protect_last_n: 20 # nunca comprimir los ultimos 20 mensajes
```

Ajustes por plan:
- Basico: threshold 0.30 (comprime antes, ahorra tokens)
- Equipo: threshold 0.40
- Pro: threshold 0.50 (mas contexto disponible)

## Agregar MCP servers

MCP (Model Context Protocol) conecta herramientas externas:

```yaml
mcp_servers:
  notion:
    url: https://mcp.notion.com/mcp
    headers:
      Authorization: "Bearer ${NOTION_API_KEY}"
  github:
    command: npx
    args: ["-y", "@modelcontextprotocol/server-github"]
    env:
      GITHUB_PERSONAL_ACCESS_TOKEN: "${GITHUB_TOKEN}"
```

Despues de agregar: restart del container.

## Configurar session reset

Controla cuando se limpia el contexto automaticamente:

```yaml
session_reset:
  mode: both       # both, idle, daily, none
  idle_minutes: 1440  # 24h sin actividad = reset
  at_hour: 4         # reset diario a las 4 AM
```

- `both`: reset por inactividad O por hora fija (recomendado)
- `idle`: solo por inactividad
- `daily`: solo a hora fija
- `none`: nunca (contexto crece indefinidamente, caro)

## Habilitar streaming

```yaml
streaming:
  enabled: true
  edit_interval: 0.3    # segundos entre ediciones del mensaje
  buffer_threshold: 40  # caracteres antes de flush
```

## Configurar tool loop guardrails

Protege contra loops infinitos del agente:

```yaml
tool_loop_guardrails:
  warnings_enabled: true
  hard_stop_enabled: true  # IMPORTANTE para tenants autonomos
  hard_stop_after:
    exact_failure: 3       # 3 fallos identicos = stop
    same_tool_failure: 5   # 5 fallos del mismo tool = stop
```
