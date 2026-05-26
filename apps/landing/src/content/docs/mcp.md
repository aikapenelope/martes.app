---
title: "MCP — Model Context Protocol"
description: "Conecta Hermes con cualquier herramienta externa: GitHub, Linear, Figma, Stripe y más."
order: 4
section: "Integraciones"
---

## ¿Qué es MCP?

El **Model Context Protocol** (MCP) es un estándar abierto creado por Anthropic que define cómo los agentes IA se conectan con herramientas y datos externos. Es como un sistema de plugins universal: cualquier servidor MCP expone herramientas que Hermes descubre y usa automáticamente.

Hermes soporta MCP con **OAuth 2.1 completo** — descubrimiento dinámico, registro de cliente, PKCE, token exchange, refresh automático.

---

## Servidores MCP populares

### Productividad
| Servidor MCP | Qué habilita | Paquete |
|---|---|---|
| **Filesystem** | Leer/escribir archivos, listar directorios | `@modelcontextprotocol/server-filesystem` |
| **GitHub** | Repos, PRs, issues, CI/CD | `@modelcontextprotocol/server-github` |
| **Linear** | Issues, proyectos, ciclos (OAuth) | `https://mcp.linear.app/mcp` |
| **Asana** | Tareas, proyectos, equipos (OAuth) | OAuth MCP |
| **Figma** | Diseños, componentes, assets (OAuth) | OAuth MCP |

### Búsqueda e investigación
| Servidor MCP | Qué habilita | Paquete |
|---|---|---|
| **Tavily** | Búsqueda web optimizada para IA | `tavily-mcp` |
| **Exa** | Neural search, investigación académica | `exa-mcp-server` |
| **Firecrawl** | Web scraping, extracción estructurada | `firecrawl-mcp` |
| **Playwright** | Browser automation, screenshots | `@playwright/mcp` |

### Negocio y DevOps
| Servidor MCP | Qué habilita | Paquete |
|---|---|---|
| **Sentry** | Errores, issues, performance (OAuth) | OAuth MCP |
| **Atlassian** | Jira, Confluence (OAuth) | OAuth MCP |
| **Stripe** | Pagos, clientes, invoices (OAuth) | OAuth MCP |
| **Slack** | Mensajes, canales (OAuth) | OAuth MCP |

---

## Tipos de conexión

### Servidores stdio (local)
Corren como subprocesos en el mismo servidor que Hermes:

```yaml
# config.yaml del tenant
mcp_servers:
  github:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-github"]
    env:
      GITHUB_PERSONAL_ACCESS_TOKEN: "ghp_xxx"

  filesystem:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/home/user/projects"]
```

### Servidores HTTP remotos
Se conectan a endpoints externos:

```yaml
mcp_servers:
  company_api:
    url: "https://mcp.internal.example.com"
    headers:
      Authorization: "Bearer xxx"
```

### Servidores OAuth 2.1
Para plataformas como Linear, Sentry, Figma — Hermes maneja todo el flujo automáticamente:

```yaml
mcp_servers:
  linear:
    url: "https://mcp.linear.app/mcp"
    auth: oauth
```

En el primer uso, Hermes imprime una URL de autorización. El cliente la abre en su browser, aprueba, y los tokens quedan en caché. Los siguientes usos son silenciosos.

---

## Cómo el cliente activa MCPs

El cliente puede configurar servidores MCP desde Telegram editando su `config.yaml`:

```
"añade el servidor MCP de GitHub a mi configuración"
→ Hermes edita /opt/data/config.yaml y recarga las conexiones
```

O puede pedirle al admin que lo configure vía `inject_wiki_content()` o editando el volumen directamente.

---

## Filtrado por herramienta

Hermes permite exponer solo las herramientas MCP que quieres:

```yaml
mcp_servers:
  github:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-github"]
    tools:
      create_issue:    { enabled: true }
      list_repos:      { enabled: true }
      delete_repo:     { enabled: false }  # bloqueado
```
