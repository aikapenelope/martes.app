---
title: "22 Plataformas de mensajería"
description: "Hermes funciona en Telegram, WhatsApp, Discord, Slack y 18 plataformas más."
order: 3
section: "Hermes Agent"
---

## Plataformas soportadas en v0.14.0

Hermes corre en 22 plataformas desde un único proceso gateway. El cliente activa las que necesita con `/auth` desde su chat.

| Plataforma | Notas para uso comercial |
|---|---|
| **Telegram** | El más robusto — webhooks, grupos, canales, bots inline, voz |
| **WhatsApp** | Via Business API — principal canal comercial en LATAM |
| **Discord** | Comunidades, servidores, canales privados, bots |
| **Slack** | Entornos corporativos, workspaces |
| **Signal** | Alta privacidad — popular en periodismo y activismo |
| **SMS (Twilio)** | Alcance máximo — sin necesidad de app |
| **Email** | Gmail, cualquier IMAP/SMTP |
| **Matrix** | Protocolo abierto federado |
| **Mattermost** | Self-hosted para empresas que no quieren Slack |
| **Microsoft Teams** | Integración corporativa via webhook |
| **WeChat/Weixin** | Mercado chino (860M usuarios activos) |
| **DingTalk / Feishu** | Herramientas corporativas chinas |
| **LINE** | Japón, Corea, Tailandia (220M usuarios) |
| **SimpleX Chat** | Zero-metadata, máxima privacidad |
| **QQBot** | Mercado chino |
| **Yuanbao (Tencent 元宝)** | Plataforma china |
| **BlueBubbles** | iMessage en Android y Web |
| **Home Assistant** | Smart home, domótica, automatización |
| **Webhook** | Integración con cualquier sistema externo |
| **API Server** | OpenAI-compatible en puerto 8642 |
| **CLI** | Terminal interactivo directo |
| **TUI** | Interfaz de terminal completa con historial |

---

## Configuración desde Telegram

El cliente configura plataformas adicionales con comandos nativos de Hermes:

```
/auth                  → menú de autenticación
/auth whatsapp         → conectar WhatsApp Business API
/auth discord          → conectar Discord bot
/sethome               → cambiar canal de notificaciones por defecto
```

No hay configuración manual de archivos. Hermes guía al cliente paso a paso.

---

## Multi-platform continuity

Hermes mantiene el contexto entre plataformas. Si el cliente empieza una tarea en Telegram y la continúa en Discord, Hermes recuerda el estado completo. El historial de sesiones es buscable con FTS5 semántico cross-platform.

---

## Para martes.app

En el tier actual, cada tenant arranca con **Telegram** configurado por defecto (el bot token del cliente). Las otras plataformas están disponibles — el cliente las activa desde su propio chat cuando las necesite.

El admin no necesita hacer nada adicional para habilitar plataformas adicionales. Hermes lo gestiona internamente.
