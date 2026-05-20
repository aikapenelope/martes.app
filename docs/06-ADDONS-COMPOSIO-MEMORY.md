# Martes.app — Add-ons, Composio, y Memoria (Decisiones)

> **Status**: Aprobado
> **Date**: May 2026

---

## Decisiones Rápidas

| Pregunta | Respuesta |
|----------|-----------|
| ¿Honcho para todos? | No. Memoria built-in suficiente. Honcho como upgrade futuro. |
| ¿Composio? | Sí como add-on. Hermes se conecta directo via MCP. Meta-agente inyecta config. |
| ¿LLM Wiki para todos? | Sí. Activado por defecto. Meta-agente inyecta contenido inicial. |
| ¿Quién conecta Composio? | Hermes directamente. Solo necesita URL + API key en config.yaml. |
| ¿El meta-agente puede inyectar markdowns? | Sí. Escribe directamente en el volumen del tenant. |
| ¿OpenRouter compartido? | Sí. DeepSeek V4 incluido en el precio. |

---

## Composio: Hermes Lo Hace Solo

Configuración que el meta-agente inyecta:

```yaml
# config.yaml del tenant
mcp_servers:
  composio:
    url: "https://connect.composio.dev/mcp"
    headers:
      x-consumer-api-key: "COMPOSIO_KEY_DEL_TENANT"
    connect_timeout: 60
    timeout: 180
```

Después de esto, el tenant le dice a su Hermes "conecta mi Slack" y Hermes usa Composio para gestionar el OAuth automáticamente.

---

## Lo Que Viene Gratis en Cada Tenant

1. LLM Wiki (conocimiento acumulativo)
2. MEMORY.md (memoria por usuario)
3. Todo tool (tareas)
4. Session search (buscar en historial)
5. Cron jobs (automatizaciones)
6. Skills auto-creados (el agente aprende)
7. Vision/OCR (analizar imágenes)
8. Web search (buscar en internet)
9. DeepSeek V4 (LLM incluido)

---

## Add-ons (Activados por el Meta-Agente)

1. Composio MCP (1000+ integraciones)
2. Browser Playwright (navegación completa)
3. Modelo premium (Claude/GPT)
4. Dashboard web (UI via subdominio)
5. Honcho (memoria avanzada, futuro)
