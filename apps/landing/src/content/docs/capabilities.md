---
title: "Capacidades de Hermes"
description: "Todo lo que Hermes puede hacer: herramientas, memoria, scheduler, API y más."
order: 2
section: "Hermes Agent"
---

## Hermes v0.14.0 — Capacidades completas

Hermes no es un wrapper de ChatGPT. Es un agente autónomo con bucle de aprendizaje cerrado que se vuelve más capaz cuanto más se usa.

**3 diferencias clave:**
1. **Bucle de aprendizaje cerrado** — crea skills desde la experiencia, las mejora, construye un modelo del usuario
2. **Autonomía real** — ejecuta tareas complejas sin supervisión y reporta resultados
3. **Multi-plataforma nativo** — 22 plataformas desde un solo proceso

---

## Herramientas nativas (built-in)

### Terminal y código
- Ejecución de Python, JavaScript, Bash
- 7 backends: local, Docker, SSH, Singularity, Modal, Daytona, Vercel Sandbox
- File manager completo (read, write, patch, search)
- Git integrado · Ripgrep para búsqueda en código

### Web y navegador
- **Búsqueda web**: Firecrawl, Tavily, SearXNG, Brave, DuckDuckGo (sin API key)
- **Automatización de navegador**: Playwright, CDP directo — 180x más rápido en v0.14.0
- **Vision web**: captura de pantalla, análisis visual de páginas
- **Computer use**: control de mouse/teclado (funciona con GPT-4o, Gemini — no solo Anthropic)
- **Scraping**: cualquier página, extracción estructurada

### Multimedia
- **Imágenes**: FAL.ai (Flux, SDXL y más)
- **Text-to-speech**: OpenAI, xAI Custom Voices con clonación de voz
- **Transcripción**: voz → texto desde memos de Telegram/WhatsApp
- **Video**: backends pluggables (Higgsfield, RunwayML)
- **Análisis visual**: imagen → descripción, OCR, análisis de documentos

### Automatización
- **Cron scheduler**: tareas en lenguaje natural — "cada lunes a las 9am envíame un resumen"
- **Subagentes**: delega tareas a agentes paralelos en su propio contexto
- **Kanban multi-agente**: tablero con heartbeat, zombie detection, retries automáticos
- **MCP**: conecta cualquier servidor MCP con OAuth 2.1

---

## Sistema de memoria

| Tipo | Qué recuerda |
|---|---|
| **UserMemory** | Quién eres, tus preferencias, estilo de trabajo, equipo |
| **EntityMemory** | Empresas, clientes, proyectos, sistemas de terceros |
| **LearnedKnowledge** | Procedimientos complejos que resolvió antes |
| **DecisionLog** | Por qué tomó ciertas decisiones (auditable) |
| **SessionContext** | Plan de trabajo multi-paso dentro de una sesión |
| **FTS5 Search** | Búsqueda semántica en todas las conversaciones pasadas |

---

## Automatizaciones programadas

El scheduler nativo entiende lenguaje natural:

```
"Cada lunes a las 8am: analiza noticias del sector retail y envíame un resumen"
"Diariamente a las 6pm: si el BTC cayó >5% notifícame"
"El 1ro de cada mes: genera informe de ventas desde Airtable y envíalo por email"
```

Entrega vía cualquier plataforma: Telegram, WhatsApp, Discord, Email.

---

## API Server (puerto 8642)

Cuando `API_SERVER_ENABLED=true`, Hermes expone una API OpenAI-compatible:

```
GET  /health                    — health check
GET  /v1/models                 — modelos disponibles
POST /v1/chat/completions       — Chat Completions (stateless)
POST /v1/responses              — Responses API (stateful)
POST /v1/runs                   — run async
GET  /v1/runs/{id}/events       — SSE stream
POST /v1/runs/{id}/approval     — resolver approval
```

Cualquier cliente OpenAI-compatible puede conectarse: Open WebUI, LibreChat, Cursor, Aider.

---

## Capacidades exclusivas de v0.14.0

- **OpenAI-compatible proxy local** — Cursor, Codex o Cline pueden usar los modelos de Claude Pro o Grok sin API key adicional
- **Microsoft Teams end-to-end** — leer y responder mensajes de Teams
- **Computer use con modelos no-Anthropic** — GPT-4o y Gemini controlan el escritorio
- **Cross-session Claude prompt caching** — -60% costo en conversaciones largas
- **xAI Grok 4.3 a 1M tokens** de contexto
- **LSP semantic diagnostics** — verifica errores semánticos en código antes de terminar el turno
- **`/handoff`** — transfiere una sesión activa a otro modelo sin perder contexto
- **`pip install hermes-agent`** — disponible en PyPI
