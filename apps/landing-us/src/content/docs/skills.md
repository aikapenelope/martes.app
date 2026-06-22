---
title: "Skills de Hermes"
description: "Skills built-in activos por defecto y skills opcionales instalables."
section: "Avanzado"
order: 1
---

## Skills de Hermes

Las skills son herramientas que Hermes puede usar en sus conversaciones. Hay dos tipos: built-in (siempre activas) y opcionales (instalables).

### Skills built-in (15, siempre activas)

1. `web_search` — busqueda con grounding (Bing + Brave)
2. `web_browse` — navegación completa (CDP, 180x más rápido desde v0.14)
3. `code_exec` — ejecución de Python en sandbox seguro
4. `pdf_reader` — extracción de tablas y texto
5. `image_gen` — DALL-E 3, SDXL, Ideogram
6. `calendar` — Google + Outlook (read/write)
7. `email` — SMTP generico (envio y lectura IMAP)
8. `spreadsheet` — Google Sheets + Excel
9. `translate` — DeepL + Google Translate
10. `summarize` — extracción de puntos clave
11. `sentiment` — análisis de tono
12. `ocr` — Tesseract + Google Vision
13. `transcribe` — Whisper (audio → texto)
14. `shell` — ejecución de comandos en sandbox
15. `http` — llamadas HTTP genéricas

### Skills opcionales (instalables via MCP)

Cualquier servidor MCP compatible. Algunos populares:

- `@linear/mcp-server` — gestion de issues
- `@github/mcp-server` — repos, PRs, issues
- `@figma/mcp-server` — leer designs
- `@stripe/mcp-server` — clientes y suscripciones
- `@notion/mcp-server` — paginas y databases

Instala via Settings → MCP Servers en el dashboard.

### Skills custom (las que tu escribes)

Si necesitas algo especifico, escribes tu propia skill en Python o TypeScript. El SDK es minimo:

```python
# mi_skill.py
from hermes import skill

@skill(name="mi_herramienta", description="Hace algo util")
def mi_herramienta(param1: str, param2: int) -> str:
    # tu logica aqui
    return f"Resultado: {param1} {param2}"
```

Sube el archivo a `skills/` en tu panel, reinicia el bot, y Hermes ya la tiene disponible.

### Limites

- **Plan Starter**: hasta 3 skills custom
- **Plan Pro**: skills custom ilimitadas
- **Plan Business**: skills custom + skills privadas del equipo (no compartidas con otros tenants)
