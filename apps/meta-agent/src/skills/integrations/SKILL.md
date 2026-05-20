---
name: integrations
description: "Como conectar integraciones a tenants Hermes: Google, Notion, GitHub, MCP"
license: MIT
metadata:
  tags: [integrations, oauth, mcp, google, notion, github]
  category: operations
---

# Integraciones de Tenants Hermes

## Integraciones nativas (via .env o archivos)

### Google Workspace (Gmail, Calendar, Drive, Sheets, Docs)

**Tipo**: OAuth token (JSON)
**Archivo**: `/opt/data/google_token.json`

Pasos:
1. El cliente autoriza la app OAuth de Google
2. Se obtiene el token JSON (ya29.xxx...)
3. Inyectar: `inject_credential(code, "google_token", token_json)`
4. Restart del container

**Nota**: El token expira. Hermes lo renueva automaticamente si tiene
`google_client_secret.json` tambien inyectado.

### Notion

**Tipo**: API key
**Archivo**: Se agrega al `.env`

Pasos:
1. Cliente crea integracion en notion.so/my-integrations
2. Copia el Internal Integration Token (ntn_xxx)
3. Inyectar: `inject_credential(code, "notion_key", "ntn_xxx")`
4. Restart del container

### Airtable

**Tipo**: API key
**Archivo**: Se agrega al `.env`

Pasos:
1. Cliente va a airtable.com/account → API
2. Copia el Personal Access Token
3. Inyectar: `inject_credential(code, "airtable_key", "pat_xxx")`
4. Restart del container

### GitHub

**Tipo**: Personal Access Token
**Archivo**: Se agrega al `.env`

Pasos:
1. Cliente va a github.com/settings/tokens
2. Crea Fine-grained token con permisos necesarios
3. Inyectar: `inject_credential(code, "github_token", "ghp_xxx")`
4. Restart del container

### Linear

**Tipo**: API key
**Archivo**: Se agrega al `.env`

Pasos:
1. Cliente va a linear.app/settings/api
2. Crea Personal API Key
3. Inyectar: `inject_credential(code, "linear_key", "lin_api_xxx")`
4. Restart del container

## Integraciones via MCP (Model Context Protocol)

MCP permite conectar cualquier servicio externo sin codigo custom.
Se configura en `config.yaml` del tenant.

### Agregar MCP server a un tenant

Editar config.yaml:
```yaml
mcp_servers:
  nombre_servicio:
    url: https://mcp.servicio.com/mcp
    # O para servidores locales:
    command: npx
    args: ["-y", "@paquete/mcp-server"]
    env:
      API_KEY: "${VARIABLE_EN_ENV}"
```

### MCP servers populares

| Servicio | Paquete | Requiere |
|----------|---------|----------|
| Notion | `url: https://mcp.notion.com/mcp` | NOTION_API_KEY |
| GitHub | `@modelcontextprotocol/server-github` | GITHUB_TOKEN |
| Slack | `@anthropic/mcp-server-slack` | SLACK_BOT_TOKEN |
| Filesystem | `@modelcontextprotocol/server-filesystem` | path |
| PostgreSQL | `@modelcontextprotocol/server-postgres` | connection string |

### Composio (1000+ apps)

Composio MCP da acceso a 1000+ apps (HubSpot, Salesforce, Trello, Jira, etc.):

```yaml
mcp_servers:
  composio:
    command: npx
    args: ["-y", "composio-mcp"]
    env:
      COMPOSIO_API_KEY: "${COMPOSIO_API_KEY}"
```

## Verificar integracion activa

Despues de inyectar credenciales y restart:
1. Revisar logs: `docker logs hermes-{code} 2>&1 | grep -i "google\|notion\|github"`
2. Pedirle al agente que use la integracion: "Lista mis eventos de Google Calendar"
3. Si falla: verificar que el token es valido y tiene permisos correctos
