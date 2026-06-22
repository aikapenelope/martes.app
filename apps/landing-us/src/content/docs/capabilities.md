---
title: "Capacidades de Hermes"
description: "Todo lo que Hermes puede hacer: herramientas, memoria, scheduler, API y más."
section: "Core"
order: 1
---

## Capacidades de Hermes

Hermes es un agente AI completo. Estas son sus capacidades nativas:

### Herramientas (tools)

- **web_search** — búsqueda con grounding (Bing + Brave)
- **web_browse** — navegación completa de páginas (CDP)
- **code_exec** — ejecución de Python en sandbox seguro
- **pdf_reader** — extracción de tablas y texto de PDFs
- **image_gen** — DALL-E 3, SDXL, Ideogram
- **calendar** — Google + Outlook (read/write)
- **email** — SMTP genérico (envío y lectura IMAP)
- **spreadsheet** — Google Sheets + Excel (read/write)
- **translate** — DeepL + Google Translate
- **summarize** — extracción de puntos clave de textos largos
- **sentiment** — análisis de tono
- **ocr** — Tesseract + Google Vision
- **transcribe** — Whisper (audio → texto)
- **shell** — ejecución de comandos en sandbox
- **http** — llamadas HTTP genéricas

### Memoria

Hermes mantiene 3 tipos de memoria:

- **Conversacional** — historial del chat actual
- **Episódica** — resumen de interacciones pasadas con cada usuario
- **Semántica** — base de conocimiento persistente (RAG sobre tus docs)

### Scheduler

- Tareas recurrentes (cron-style)
- Tareas one-shot
- Triggers basados en eventos externos (webhooks, emails, etc.)

### API

- REST API en `https://api.martes.app/v1/`
- Compatible con OpenAI function calling
- Webhooks salientes para integraciones
