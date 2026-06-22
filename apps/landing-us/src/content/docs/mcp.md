---
title: "MCP — Model Context Protocol"
description: "Conecta Hermes con cualquier herramienta externa: GitHub, Linear, Figma, Stripe y más."
section: "Core"
order: 2
---

## MCP — Model Context Protocol

MCP (Model Context Protocol) es el estándar abierto que usa Hermes para conectarse a herramientas externas. Cualquier servidor MCP compatible funciona con Hermes sin código custom.

### Servidores MCP incluidos

martes.app viene con 6 servidores MCP pre-instalados:

- **GitHub** — issues, PRs, actions, releases
- **Linear** — issues, proyectos, roadmaps
- **Figma** — leer designs, extraer assets
- **Stripe** — customers, subscriptions, invoices
- **Notion** — pages, databases, comments
- **Slack** — channels, messages, threads

### Servidores MCP custom

Puedes anadir tus propios servidores MCP. Hay 3 formas:

1. **npm** — instala cualquier paquete del MCP registry
2. **Docker** — corre tu servidor como container
3. **HTTP/SSE** — conecta a un servidor remoto

En el dashboard de martes.app: Settings → MCP Servers → Add.

### Ejemplo: anadir Linear

```json
{
  "name": "linear-mcp",
  "transport": "stdio",
  "command": "npx",
  "args": ["-y", "@linear/mcp-server"],
  "env": {
    "LINEAR_API_KEY": "lin_api_xxxxx"
  }
}
```

Click "Test connection" y listo. Hermes ya puede crear issues, comentar en PRs, etc. desde una conversacion de WhatsApp.
