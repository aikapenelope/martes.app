---
title: "22 Messaging Platforms"
description: "Hermes works on Telegram, WhatsApp, Discord, Slack and 18 more platforms."
order: 3
section: "Hermes Agent"
---

## Platforms supported in v0.14.0

Hermes runs on 22 platforms from a single gateway process. The client activates the ones they need with `/auth` from their chat.

| Platform | Notes for commercial use |
|---|---|
| **Telegram** | The most robust — webhooks, groups, channels, inline bots, voice |
| **WhatsApp** | Via Business API — main commercial channel in LATAM |
| **Discord** | Communities, servers, private channels, bots |
| **Slack** | Corporate environments, workspaces |
| **Signal** | High privacy — popular in journalism and activism |
| **SMS (Twilio)** | Maximum reach — no app needed |
| **Email** | Gmail, any IMAP/SMTP |
| **Matrix** | Open federated protocol |
| **Mattermost** | Self-hosted for companies that don't want Slack |
| **Microsoft Teams** | Corporate integration via webhook |
| **WeChat/Weixin** | Chinese market (860M active users) |
| **DingTalk / Feishu** | Chinese corporate tools |
| **LINE** | Japan, Korea, Thailand (220M users) |
| **SimpleX Chat** | Zero-metadata, maximum privacy |
| **QQBot** | Chinese market |
| **Yuanbao (Tencent 元宝)** | Chinese platform |
| **BlueBubbles** | iMessage on Android and Web |
| **Home Assistant** | Smart home, domotics, automation |
| **Webhook** | Integration with any external system |
| **API Server** | OpenAI-compatible on port 8642 |
| **CLI** | Direct interactive terminal |
| **TUI** | Full terminal interface with history |

---

## Configuration from Telegram

The client configures additional platforms with native Hermes commands:

```
/auth                  → authentication menu
/auth whatsapp         → connect WhatsApp Business API
/auth discord          → connect Discord bot
/sethome               → change default notification channel
```

There is no manual file configuration. Hermes guides the client step by step.

---

## Multi-platform continuity

Hermes maintains context between platforms. If the client starts a task on Telegram and continues it on Discord, Hermes remembers the full state. Session history is searchable with semantic FTS5 cross-platform.

---

## For martes.app

In the current tier, each tenant starts with **Telegram** configured by default (the client's bot token). The other platforms are available — the client activates them from their own chat when they need them.

The admin does not need to do anything additional to enable additional platforms. Hermes handles it internally.