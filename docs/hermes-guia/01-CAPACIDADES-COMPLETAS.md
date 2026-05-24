# Hermes Agent v0.14.0 — Capacidades Completas

> **Fuente**: NousResearch/hermes-agent · MIT License  
> **Versión analizada**: v0.14.0 (tag Docker: `v2026.5.16`)  
> **Fecha de análisis**: junio 2026  
> **165,000+ estrellas en GitHub · 27,000+ forks**

---

## Qué es Hermes

Hermes es un agente de IA autónomo y autoevolutivo. No es un chatbot ni un copiloto de IDE — es un agente que vive en un servidor, recuerda lo que aprende, y se vuelve más capaz cuanto más se usa. Se diferencia de cualquier otro agente disponible en tres capacidades únicas:

1. **Bucle de aprendizaje cerrado**: crea skills desde la experiencia, las mejora durante el uso, y construye un modelo progresivo del usuario y su empresa a lo largo de sesiones
2. **Autonomía real**: puede ejecutar tareas complejas sin supervisión — búsqueda web, escritura de código, automatización de navegador, generación de contenido — y reportar resultados
3. **Multi-plataforma nativo**: funciona en Telegram, WhatsApp, Discord, Slack, Signal, Email y 15+ plataformas más desde un solo proceso

---

## 1. Plataformas de Mensajería (22 en v0.14.0)

| Plataforma | Notas para uso comercial |
|---|---|
| **Telegram** | El más robusto — webhooks, grupos, canales, bots inline |
| **WhatsApp** | Via Business API — principal canal comercial en LATAM |
| **Discord** | Comunidades, servidores, canales privados |
| **Slack** | Entornos corporativos |
| **Signal** | Alta privacidad, popular en periodismo y activismo |
| **SMS (Twilio)** | Alcance máximo — sin necesidad de app |
| **Email** | Gmail, cualquier IMAP/SMTP |
| **Matrix** | Protocolo abierto federado |
| **Mattermost** | Self-hosted para empresas |
| **Microsoft Teams** | Integración corporativa via webhook |
| **WeChat/Weixin** | Mercado chino |
| **DingTalk/Feishu** | Herramientas corporativas chinas |
| **LINE** | Japón, Corea, Tailandia (220M usuarios) |
| **SimpleX Chat** | Zero-metadata, máxima privacidad |
| **QQBot** | Mercado chino |
| **Yuanbao (Tencent元宝)** | Plataforma china |
| **BlueBubbles** | iMessage en Android/Web |
| **Home Assistant** | Smart home, domótica |
| **Webhook** | Integración con cualquier sistema externo |
| **API Server** | OpenAI-compatible en puerto 8642 |
| **CLI** | Terminal directo |
| **TUI** | Interfaz de terminal completa |

---

## 2. Modelos de IA disponibles

### Via OpenRouter (200+ modelos, una sola API key)
- OpenAI: GPT-4o, GPT-4o-mini, o1, o3
- Anthropic: Claude Opus 4.6, Claude Sonnet 3.5, Claude Haiku
- Google: Gemini 2.0 Flash, Gemini Pro 1.5
- Meta: Llama 3.3, Llama 3.1
- Mistral: Large, Medium, Small
- DeepSeek: DeepSeek V4 Flash, V3 (1M contexto, muy económico)
- xAI: Grok 4.3 (1M contexto)
- Qwen, Phi, Gemma, y más

### Via Nous Portal (suscripción única)
- 300+ modelos bajo una sola suscripción
- Tool Gateway incluido: búsqueda web (Firecrawl), generación de imágenes (FAL), TTS (OpenAI), navegador cloud (Browser Use)

### Proveedores directos
- NovitaAI (90+ modelos, pago por uso)
- NVIDIA NIM (Nemotron)
- Google AI Studio / Gemini nativo
- Ollama (modelos locales)
- LM Studio (modelos locales)
- Hugging Face (Inference API)
- Y 15+ más

**Cambio de modelo**: `/model <nombre>` — sin reiniciar, sin cambiar código

---

## 3. Herramientas nativas (built-in)

### Terminal y código
- Ejecución de código Python, JavaScript, Bash
- 7 backends: local, Docker, SSH, Singularity, Modal, Daytona, Vercel Sandbox
- File manager completo (read, write, patch, search)
- Git integrado
- Ripgrep (búsqueda ultrarrápida en código)

### Web y navegador
- **Búsqueda web**: Firecrawl (default), Tavily, SearXNG, Brave (free tier), DuckDuckGo (sin key)
- **Automatización de navegador**: Playwright, CDP directo — 180x más rápido en v0.14.0
- **Vision web**: captura de pantalla, análisis visual de páginas
- **Computer use**: control de mouse/teclado (funciona con modelos no-Anthropic desde v0.14.0)
- **Scraping**: cualquier página web, extracción de datos

### Multimedia
- **Generación de imágenes**: FAL.ai (Flux, SDXL, etc.)
- **Text-to-speech**: OpenAI, xAI Custom Voices (con clonación de voz)
- **Transcripción de audio**: voz a texto desde memos de voz
- **Generación de video**: backends pluggables (Higgsfield, RunwayML, etc.)
- **Análisis visual**: imagen → descripción, OCR, análisis

### Automatización
- **Cron scheduler**: tareas en lenguaje natural — "cada lunes a las 9am envíame un resumen de ventas"
- **Subagentes**: delega tareas a agentes paralelos en su propio contexto
- **Kanban multi-agente**: tablero de tareas con heartbeat, zombie detection, retries automáticos
- **MCP (Model Context Protocol)**: conecta cualquier servidor MCP con OAuth 2.1

---

## 4. Sistema de Skills

### Skills Built-in (activos por defecto)

**Productividad**
- **Notion**: lectura/escritura de páginas y bases de datos
- **Airtable**: CRUD completo, filtros, upserts
- **Google Workspace**: Gmail, Calendar, Drive, Docs, Sheets, Contacts
- **Linear**: issues, proyectos, ciclos
- **Maps/Rutas**: Google Maps, geocoding, distancias
- **OCR y documentos**: extracción de texto de PDFs, imágenes, documentos escaneados
- **PowerPoint**: creación y edición de presentaciones
- **Teams Meeting Pipeline**: automatización de reuniones de Microsoft Teams

**Social Media**
- **X/Twitter**: búsqueda, análisis de tweets (OAuth o API key)

**Investigación**
- Búsqueda académica (ArXiv, papers)
- Vigilancia de contenido (RSS, HTTP JSON, GitHub)
- OSINT básico (dominio, organización)

**Desarrollo**
- GitHub (repos, PRs, issues, CI/CD via gh CLI)
- MLOps (entrenamiento, evaluación, modelos de inferencia, bases de datos vectoriales)

**Creative**
- Diagramas (Excalidraw, UML, arquitectura)
- Arte ASCII, diseño visual

### Skills Opcionales (instalar via `hermes skills install`)

**Finanzas**
- `stocks` — Cotizaciones, historial, crypto via Yahoo Finance (sin API key)
- `3-statement-model` — Estado de resultados, balance, flujo de caja
- `dcf-model` — Valoración por flujos descontados
- `comps-analysis` — Análisis comparativo de empresas
- `lbo-model` — Leveraged buyout modeling
- `merger-model` — Análisis de fusiones
- `hyperliquid` — DeFi perpetuos y spot via Hyperliquid SDK

**Blockchain**
- `solana` — Wallets, tokens, transacciones, NFTs, whale detection (sin API key)
- `evm` — Ethereum + L2s + Base (multi-chain)

**Comunicación**
- `telephony` — Llamadas de voz programáticas

**E-commerce**
- `shopify` — Admin API + Storefront GraphQL (productos, órdenes, inventario)
- `shop-app` — Asistente de compras personal

**Productividad adicional**
- `memento-flashcards` — Tarjetas de memoria espaciada
- `here-now` — Localización y contexto
- `canvas` — Lienzo de trabajo visual

---

## 5. Memoria y aprendizaje

### Memoria de usuario (UserMemory)
Hermes aprende quién eres a lo largo de sesiones: tus preferencias, proyectos, estilo de trabajo, equipo. No necesitas repetirlo cada vez.

### EntityMemory
Construye perfiles de terceros: empresas, clientes, proyectos, sistemas. Cuando dices "¿qué pasó con el cliente Acme?", Hermes lo recuerda.

### LearnedKnowledge
Documenta procedimientos complejos que resolvió — la próxima vez los aplica directamente sin rehacer el trabajo.

### DecisionLog
Registra por qué tomó ciertas decisiones. Auditable, mejorable.

### SessionContext
Planificación dentro de una sesión — mantiene el hilo de trabajo multi-paso.

### Búsqueda de sesiones (FTS5)
Busca en todas las conversaciones pasadas con relevancia semántica: "¿cuándo configuramos el servidor en mayo?"

### Auto-creación de skills
Después de resolver una tarea compleja, Hermes crea automáticamente una skill que encapsula ese conocimiento para futuras ejecuciones.

---

## 6. Seguridad y aprobaciones

### Modos de aprobación
- **Auto**: ejecuta todo sin preguntar (para automatizaciones confiables)
- **Smart**: solo pide aprobación para operaciones riesgosas
- **Manual**: aprueba cada acción antes de ejecutar

### HITL (Human in the Loop)
- Cola de aprobaciones en el dashboard o via Telegram
- Comandos `/approve` y `/deny` desde cualquier plataforma
- Timeout configurable

### Seguridad del código
- Namespace isolation en Docker
- No puede escalar privilegios (`sudo -S` bloqueado en v0.14.0)
- Sanitización de errores (previene prompt injection via output de tools)
- Tool override: plugins pueden reemplazar herramientas nativas de forma limpia

---

## 7. Automatizaciones programadas (Cron)

Hermes tiene un scheduler nativo que funciona en lenguaje natural:

```
"Cada lunes a las 8am: analiza las noticias del sector de retail en Venezuela y envíame un resumen por Telegram"

"Diariamente a las 6pm: revisa el precio del BTC/USDT y si cayó más del 5% notifícame"

"El primer día de cada mes: genera un informe de ventas del mes anterior desde Airtable y envíalo por email"
```

Entrega via cualquier plataforma conectada: Telegram, WhatsApp, Discord, Email, etc.

---

## 8. Capacidades únicas de v0.14.0

Añadidas en la versión actual (no disponibles en versiones anteriores):

- **OpenAI-compatible local proxy**: cualquier app que use OpenAI API (Cursor, Codex, Cline) puede conectarse a Hermes usando los modelos de Claude Pro, ChatGPT Pro o SuperGrok sin API key adicional
- **Microsoft Teams end-to-end**: leer mensajes de Teams, responder desde Hermes
- **LINE + SimpleX Chat**: dos nuevas plataformas (total: 22)
- **Computer use con modelos no-Anthropic**: GPT-4o, Gemini pueden controlar el escritorio
- **180x más rápido en browser CDP**: interacciones web casi instantáneas
- **Cross-session Claude prompt caching**: -60% costo en conversaciones largas con Claude
- **xAI Grok 4.3 a 1M tokens de contexto**: documentos enteros en una sola consulta
- **LSP semantic diagnostics**: cuando escribe código, verifica errores semánticos antes de terminar el turno
- **`/handoff`**: transfiere una sesión activa (con todo el contexto) a otro modelo sin perder nada
- **`/subgoal`**: añade criterios a una tarea en curso sin reiniciarla
- **Native Windows beta**: funciona en cmd.exe y PowerShell
- **pip install hermes-agent**: disponible en PyPI sin necesidad de clonar el repo

---

## 9. API Server (puerto 8642)

Cuando `API_SERVER_ENABLED=true`:

```
GET  /health                    — health check
GET  /health/detailed          — estado rico para integración
GET  /v1/models                 — lista de modelos disponibles
POST /v1/chat/completions       — OpenAI Chat Completions (stateless)
POST /v1/responses              — OpenAI Responses API (stateful)
POST /v1/runs                   — iniciar run async, devuelve run_id
GET  /v1/runs/{id}              — estado del run
GET  /v1/runs/{id}/events       — SSE stream de eventos del run
POST /v1/runs/{id}/approval     — resolver approval pendiente
POST /v1/runs/{id}/stop         — interrumpir run
```

**Cualquier cliente OpenAI-compatible puede conectarse**: Open WebUI, LobeChat, LibreChat, AnythingLLM, Cursor, Aider, scripts propios.

---

## 10. Despliegue

### Opciones de hosting
| Opción | Costo estimado | Ideal para |
|---|---|---|
| VPS $5-10/mes (Hetzner, Contabo, etc.) | ~$5-10/mes | Producción, 24/7 |
| Raspberry Pi / equipo propio | Hardware existente | Testing, personal |
| Modal / Daytona (serverless) | Pay-per-use, casi cero idle | Uso esporádico |
| Vercel Sandbox | Gratis tier | Prototyping |
| Docker local | Gratis | Desarrollo |

### Requerimientos mínimos
- Python 3.11+
- 512MB RAM (1GB recomendado para uso intensivo)
- Cualquier sistema operativo (Linux, macOS, Windows, Android/Termux)

### martes.app (esta plataforma)
Hermes como SaaS multi-tenant: cada cliente tiene su instancia aislada en un container Docker con 768MB RAM / 0.75 CPU. El meta-agente gestiona el ciclo de vida completo vía Telegram.
