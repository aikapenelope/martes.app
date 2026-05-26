---
title: "¿Qué es martes.app?"
description: "Plataforma SaaS que despliega agentes Hermes personales para empresas."
order: 1
section: "Inicio"
---

## martes.app — Hermes como servicio

**martes.app** es una plataforma que le da a cada cliente de empresa un agente IA completo basado en [Hermes Agent](https://github.com/nousresearch/hermes-agent) (NousResearch, +165K ⭐ en GitHub), corriendo 24/7 en infraestructura propia.

No es un chatbot. Es un agente autónomo que aprende, recuerda y actúa.

## Cómo funciona

Cada cliente recibe:

- **Un bot de Telegram** (o WhatsApp, Discord, Slack — 22 plataformas disponibles)
- **Hermes completo y sin restricciones** — el agente puede instalar skills, conectar integraciones, programar tareas, ejecutar código, navegar la web
- **Memoria persistente** — recuerda todo entre sesiones: quién eres, tu empresa, tus proyectos
- **Modelos de IA intercambiables** — 200+ modelos via OpenRouter con un solo `/model`

El límite del cliente es su presupuesto de tokens en OpenRouter, no las features.

## Arquitectura

```
Cliente (Telegram/WhatsApp/etc.)
    ↓
Container Docker — Hermes Agent v0.14.0
    ↓ usa
OpenRouter API (200+ modelos)
    ↓ conecta con
MCPs, Skills, APIs del cliente
```

Cada tenant es un container Docker aislado con:
- Su propio volumen de datos (`/opt/data`)
- Su propio bot token de Telegram
- Su propia API key de OpenRouter
- Su propia red Docker bridge

## Precio

**$30 / mes** — Hermes completo, sin restricciones de features.

Incluye:
- 30 días de trial con platform key (el cliente configura su propia key antes del vencimiento)
- Backup diario automático a SeaweedFS
- Health monitoring cada 5 minutos
- Soporte vía el mismo bot de Telegram del admin

## Primer cliente

```bash
# Desde Telegram al meta-agente:
"crea tenant Acme Corp, token 123456:ABC, telegram_id 987654"

→ En ~30 segundos:
  - Container Hermes corriendo
  - Bot activo en Telegram
  - Trial 30 días iniciado
```
