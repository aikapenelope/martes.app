---
title: "MCP — Model Context Protocol"
description: "Connect Hermes to any external tool: GitHub, Linear, Figma, Stripe and more."
order: 4
section: "Integrations"
---

## What is MCP?

The **Model Context Protocol** (MCP) is an open standard created by Anthropic that defines how AI agents connect to external tools and data. It is like a universal plugin system: any MCP server exposes tools that Hermes discovers and uses automatically.

Hermes supports MCP with **full OAuth 2.1** — dynamic discovery, client registration, PKCE, token exchange, automatic refresh.

---

## Popular MCP servers

### Productivity
| MCP Server | What it enables | Package |
|---|---|---|
| **Filesystem** | Read/write files, list directories | `@modelcontextprotocol/server-filesystem` |
| **GitHub** | Repos, PRs, issues, CI/CD | `@modelcontextprotocol/server-github` |
| **Linear** | Issues, projects, cycles (OAuth) | `https://mcp.linear.app/mcp` |
| **Asana** | Tasks, projects, teams (OAuth) | OAuth MCP |
| **Figma** | Designs, components, assets (OAuth) | OAuth MCP |

### Search and research
| MCP Server | What it enables | Package |
|---|---|---|
| **Tavily** | Web search optimized for AI | `tavily-mcp` |
| **Exa** | Neural search, academic research | `exa-mcp-server` |
| **Firecrawl** | Web scraping, structured extraction | `firecrawl-mcp` |
| **Playwright** | Browser automation, screenshots | `@playwright/mcp` |

### Business and DevOps
| MCP Server | What it enables | Package |
|---|---|---|
| **Sentry** | Errors, issues, performance (OAuth) | OAuth MCP |
| **Atlassian** | Jira, Confluence (OAuth) | OAuth MCP |
| **Stripe** | Payments, customers, invoices (OAuth) | OAuth MCP |
| **Slack** | Messages, channels (OAuth) | OAuth MCP |

---

## Connection types

### Stdio servers (local)
Run as subprocesses on the same server as Hermes:

```yaml
# tenant config.yaml
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

### Remote HTTP servers
Connect to external endpoints:

```yaml
mcp_servers:
  company_api:
    url: "https://mcp.internal.example.com"
    headers:
      Authorization: "Bearer xxx"
```

### OAuth 2.1 servers
For platforms like Linear, Sentry, Figma — Hermes handles the full flow automatically:

```yaml
mcp_servers:
  linear:
    url: "https://mcp.linear.app/mcp"
    auth: oauth
```

On first use, Hermes prints an authorization URL. The client opens it in their browser, approves, and the tokens are cached. Subsequent uses are silent.

---

## How the client activates MCPs

The client can configure MCP servers from Telegram by editing their `config.yaml`:

```
"add the GitHub MCP server to my configuration"
→ Hermes edits /opt/data/config.yaml and reloads the connections
```

Or they can ask the admin to configure it via `inject_wiki_content()` or by editing the volume directly.

---

## Tool filtering

Hermes allows exposing only the MCP tools you want:

```yaml
mcp_servers:
  github:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-github"]
    tools:
      create_issue:    { enabled: true }
      list_repos:      { enabled: true }
      delete_repo:     { enabled: false }  # blocked
```