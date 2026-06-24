---
title: "Hermes Capabilities"
description: "Everything Hermes can do: tools, memory, scheduler, API and more."
order: 2
section: "Hermes Agent"
---

## Hermes v0.14.0 — Full Capabilities

Hermes is not a ChatGPT wrapper. It is an autonomous agent with a closed learning loop that becomes more capable the more it is used.

**3 key differences:**
1. **Closed learning loop** — creates skills from experience, improves them, builds a model of the user
2. **Real autonomy** — executes complex tasks without supervision and reports results
3. **Multi-platform native** — 22 platforms from a single process

---

## Built-in native tools

### Terminal and code
- Python, JavaScript, Bash execution
- 7 backends: local, Docker, SSH, Singularity, Modal, Daytona, Vercel Sandbox
- Full file manager (read, write, patch, search)
- Integrated Git · Ripgrep for code search

### Web and browser
- **Web search**: Firecrawl, Tavily, SearXNG, Brave, DuckDuckGo (no API key)
- **Browser automation**: Playwright, direct CDP — 180x faster in v0.14.0
- **Web vision**: screenshot, visual analysis of pages
- **Computer use**: mouse/keyboard control (works with GPT-4o, Gemini — not just Anthropic)
- **Scraping**: any page, structured extraction

### Multimedia
- **Images**: FAL.ai (Flux, SDXL and more)
- **Text-to-speech**: OpenAI, xAI Custom Voices with voice cloning
- **Transcription**: voice → text from Telegram/WhatsApp memos
- **Video**: pluggable backends (Higgsfield, RunwayML)
- **Visual analysis**: image → description, OCR, document analysis

### Automation
- **Cron scheduler**: tasks in natural language — "every Monday at 9am send me a summary"
- **Subagents**: delegate tasks to parallel agents in their own context
- **Multi-agent Kanban**: board with heartbeat, zombie detection, automatic retries
- **MCP**: connect any MCP server with OAuth 2.1

---

## Memory System

| Type | What it remembers |
|---|---|
| **UserMemory** | Who you are, your preferences, working style, team |
| **EntityMemory** | Companies, clients, projects, third-party systems |
| **LearnedKnowledge** | Complex procedures it solved before |
| **DecisionLog** | Why it made certain decisions (auditable) |
| **SessionContext** | Multi-step work plan within a session |
| **FTS5 Search** | Semantic search across all past conversations |

---

## Scheduled automations

The native scheduler understands natural language:

```
"Every Monday at 8am: analyze news in the retail sector and send me a summary"
"Daily at 6pm: if BTC dropped >5% notify me"
"On the 1st of each month: generate sales report from Airtable and send it by email"
```

Delivery via any platform: Telegram, WhatsApp, Discord, Email.

---

## API Server (port 8642)

When `API_SERVER_ENABLED=true`, Hermes exposes an OpenAI-compatible API:

```
GET  /health                    — health check
GET  /v1/models                 — available models
POST /v1/chat/completions       — Chat Completions (stateless)
POST /v1/responses              — Responses API (stateful)
POST /v1/runs                   — run async
GET  /v1/runs/{id}/events       — SSE stream
POST /v1/runs/{id}/approval     — resolve approval
```

Any OpenAI-compatible client can connect: Open WebUI, LibreChat, Cursor, Aider.

---

## v0.14.0 exclusive capabilities

- **OpenAI-compatible local proxy** — Cursor, Codex or Cline can use Claude Pro or Grok models without additional API keys
- **Microsoft Teams end-to-end** — read and reply to Teams messages
- **Computer use with non-Anthropic models** — GPT-4o and Gemini control the desktop
- **Cross-session Claude prompt caching** — -60% cost on long conversations
- **xAI Grok 4.3 at 1M tokens** of context
- **LSP semantic diagnostics** — verifies semantic errors in code before ending the turn
- **`/handoff`** — transfers an active session to another model without losing context
- **`pip install hermes-agent`** — available on PyPI