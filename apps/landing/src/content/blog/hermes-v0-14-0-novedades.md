---
title: "Hermes v0.14.0 — Lo que cambió y por qué importa"
description: "La versión más importante de Hermes en 2026: 180x más rápido en browser, computer use en GPT-4o y Gemini, Microsoft Teams, y más."
date: "2026-05-20"
tags: ["Hermes", "Producto", "Actualización"]
author: "martes.app"
---

## Hermes v0.14.0 ya está en producción

NousResearch acaba de publicar la versión 0.14.0 de Hermes Agent (tag Docker: `v2026.5.16`). Es la actualización más significativa del año. Los tenants de martes.app están corriendo esta versión desde el día del lanzamiento.

Estas son las novedades que más importan para uso empresarial.

---

## 180x más rápido en automatización de browser

El motor CDP (Chrome DevTools Protocol) fue completamente reescrito. Las interacciones con páginas web — navegación, clicks, extracción de datos, captura de pantallas — son ahora 180 veces más rápidas que en v0.13.x.

En la práctica: lo que antes tardaba 3 minutos en raspar datos de una tabla web ahora tarda 1 segundo.

---

## Computer use sin necesidad de Claude

Hasta v0.13.x, el control de mouse y teclado (computer use) solo funcionaba con modelos de Anthropic. En v0.14.0 funciona con **cualquier modelo**:

- GPT-4o ✓
- Gemini 2.0 Flash ✓
- DeepSeek V4 Flash ✓ (y es mucho más barato)

Esto significa que tus automatizaciones de pantalla ya no están atadas a los precios de Anthropic.

---

## Microsoft Teams end-to-end

Hermes ahora puede leer mensajes de Teams y responder desde el mismo agente que ya usas en Telegram. Un solo Hermes, todos los canales.

Especialmente útil para empresas con parte del equipo en Teams y los clientes en WhatsApp.

---

## Más novedades

**`/handoff`** — transfiere una sesión activa (con todo el contexto) a otro modelo sin perder nada. Empezaste con DeepSeek, necesitas el razonamiento de Claude para esta parte específica, y vuelves a DeepSeek. Sin perder el hilo.

**Claude prompt caching cross-session** — si usas Claude para conversaciones largas, -60% en el costo. Los prompts de sistema y contexto se cachean entre sesiones.

**Grok 4.3 a 1M tokens** — documentos enteros, repositorios completos, bases de datos grandes en una sola consulta.

**LSP semantic diagnostics** — cuando Hermes escribe código, ahora verifica errores semánticos antes de terminar el turno. Menos iteraciones de "arregla este error".

**pip install hermes-agent** — disponible en PyPI. Ya no hace falta clonar el repo.

---

## Para los tenants de martes.app

Todos los containers ya corren `v2026.5.16`. No hay ninguna acción requerida de tu parte.

Si quieres probar `/handoff` o las nuevas capacidades de computer use, solo pídeselo a tu agente desde Telegram.
