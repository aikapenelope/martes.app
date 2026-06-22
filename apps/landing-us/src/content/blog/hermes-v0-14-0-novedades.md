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

En la práctica: tareas que tardaban 3 minutos ahora tardan 1 segundo. Esto hace viable el uso de Hermes para scraping de alta frecuencia, monitoring de precios, y QA automatizado sobre aplicaciones web.

---

## Computer Use en GPT-4o y Gemini

Hermes ahora puede controlar interfaces gráficas completas (no solo APIs) usando computer use. GPT-4o y Gemini son los modelos soportados en esta versión.

Casos de uso empresarial:
- Llenar formularios en sistemas legacy sin API
- Automatizar tareas en ERPs viejos
- Pruebas E2E sobre interfaces reales

---

## Microsoft Teams

Nos lo pidieron durante 18 meses. Ya está. El módulo `teams` se configura igual que `slack` o `discord` en el archivo de tenants.

---

## Skills built-in actualizadas

El módulo `skills` ahora trae 12 skills built-in activas por defecto (antes 6):

1. `web_search` — búsqueda con grounding
2. `code_exec` — ejecución de Python en sandbox
3. `pdf_reader` — extracción de tablas y texto
4. `image_gen` — DALL-E 3 y SDXL
5. `calendar` — Google + Outlook
6. `email` — SMTP genérico
7. `spreadsheet` — Google Sheets + Excel
7. `translate` — DeepL + Google
9. `summarize` — extracción de puntos clave
10. `sentiment` — análisis de tono
11. `ocr` — Tesseract + cloud vision
12. `transcribe` — Whisper

---

## ¿Cómo actualizar?

Si eres tenant de martes.app, no tienes que hacer nada. Tu instancia ya corre v0.14.0 desde el 16 de mayo.

Si corres Hermes self-hosted:
```bash
docker pull nousresearch/hermes-agent:v2026.5.16
docker compose restart
```

El upgrade es backward-compatible. Tus skills personalizados siguen funcionando.
