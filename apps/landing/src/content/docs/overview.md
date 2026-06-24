---
title: "What is martes.app?"
description: "SaaS platform that deploys personal Hermes agents for companies."
order: 1
section: "Introduction"
---

## martes.app — Hermes as a service

**martes.app** is a platform that gives each enterprise client a complete AI agent based on [Hermes Agent](https://github.com/nousresearch/hermes-agent) (NousResearch, +165K ⭐ on GitHub), running 24/7 on its own infrastructure.

It is not a chatbot. It is an autonomous agent that learns, remembers and acts.

## How it works

Each client receives:

- **A Telegram bot** (or WhatsApp, Discord, Slack — 22 platforms available)
- **Full and unrestricted Hermes** — the agent can install skills, connect integrations, schedule tasks, execute code, browse the web
- **Persistent memory** — remembers everything between sessions: who you are, your company, your projects
- **Interchangeable AI models** — 200+ models via OpenRouter with a single `/model`

The client's limit is their OpenRouter token budget, not features.

## Architecture

```
Client (Telegram/WhatsApp/etc.)
    ↓
Docker Container — Hermes Agent v0.14.0
    ↓ uses
OpenRouter API (200+ models)
    ↓ connects to
MCPs, Skills, Client APIs
```

Each tenant is an isolated Docker container with:
- Its own data volume (`/opt/data`)
- Its own Telegram bot token
- Its own OpenRouter API key
- Its own Docker bridge network

## Pricing

**$30 / month** — Full Hermes, no feature restrictions.

Includes:
- 30 days of trial with platform key (client configures their own key before expiration)
- Automatic daily backup to SeaweedFS
- Health monitoring every 5 minutes
- Support via the admin's same Telegram bot

## First client

```bash
# From Telegram to the meta-agent:
"create tenant Acme Corp, token 123456:ABC, telegram_id 987654"

→ In ~30 seconds:
  - Hermes container running
  - Bot active on Telegram
  - 30-day trial started
```