# Martes.app — Architecture Plan

> **Status**: Planning  
> **Date**: May 2026  
> **Scope**: SaaS platform that provides Hermes Agent as a managed service, with an Agno meta-agent for operations.

---

## 1. What We're Building

A **multi-tenant SaaS** where each customer gets their own Hermes Agent instance (containerized), managed by a meta-agent (Agno) that can:
- Create/destroy/restart Hermes instances
- Update configurations (model, skills, personality)
- Manage OAuth credentials (Google, Notion, etc.)
- Monitor health and auto-heal
- Update env vars, enable/disable APIs
- Scale instances up/down

### User Flow

```
User signs up → Chooses plan → Gets a Hermes instance
  → Connects platforms (Telegram, Discord, WhatsApp)
  → Connects integrations (Google, Notion, Airtable) via OAuth
  → Agent starts working
  → Meta-agent monitors and maintains
```

---

## 2. Key Architecture Decisions

### 2.1 Container Per Tenant (Fully Isolated)

Each tenant gets their own Docker container running `nousresearch/hermes-agent`.

**Why**:
- Complete data isolation (sessions, memories, skills, credentials)
- Independent model/skill configuration per tenant
- One tenant crashing doesn't affect others
- Hermes stores all state in `/opt/data` — one volume per tenant
- Hermes explicitly warns: "Never run two gateway containers against the same data directory"

**Capacity** (CX43: 16 GB RAM):
- Hermes image includes Playwright/Chromium (CamoFox browser) — ~800MB-1.2GB per instance
- With infra overhead (PostgreSQL, Redis, Traefik, Agno): **10-12 instances per server**
- Without browser tasks active (idle gateway): ~400-500MB → **15-20 instances**
- The browser is included in all instances (it's part of the image), but RAM usage spikes only when browser tools are actively used

**Scaling path**:
- 1 server: 10-12 tenants
- 2 servers + load balancer: 20-24 tenants
- Serverless backends (Modal/Daytona) for code execution: 30-50 tenants per server (gateway-only containers ~200MB)

### 2.2 OAuth/API Credentials: Hermes Manages Directly

Hermes already handles OAuth flows for Google Workspace, Notion, etc. internally:
- Google: `google_token.json` + `google_client_secret.json` in `~/.hermes/`
- Notion: `NOTION_API_KEY` in `~/.hermes/.env`
- Airtable: API key in `.env`
- Any MCP server: configured in `~/.hermes/mcp.json`

**Our role in the SaaS**:
1. User initiates OAuth flow in our web dashboard
2. Our API handles the OAuth redirect/callback
3. We write the resulting token into the tenant's Hermes data volume
4. Hermes picks it up automatically (token refresh is handled by Hermes)

**No external credential proxy needed.** Hermes is the credential manager.

For users who want **Composio MCP** (250+ integrations, managed OAuth):
- Optional add-on (higher tier plan)
- We configure the MCP server URL in their Hermes instance
- Composio handles the OAuth and token refresh externally
- User pays Composio separately (or we resell)

### 2.3 Meta-Agent (Agno) — The Operations Brain

The Agno meta-agent is NOT customer-facing. It's the **internal operations agent** that:

| Capability | How |
|-----------|-----|
| Create tenant instance | `docker run` with pre-configured volume |
| Configure model/provider | Write to `~/.hermes/config.yaml` |
| Add/remove skills | Copy skill files to `~/.hermes/skills/` |
| Update env vars | Write to `~/.hermes/.env` |
| Inject OAuth tokens | Write token files to volume |
| Health monitoring | Poll `/health` endpoint on each instance |
| Auto-restart on failure | Docker restart policy + active monitoring |
| Log analysis | Read container logs, detect patterns |
| Version updates | Pull new image, recreate container |
| Capacity planning | Monitor RAM/CPU, suggest scaling |

**Knowledge base**:
- Hermes documentation (full)
- Skills catalog (what each skill needs)
- Troubleshooting patterns (from Hermes GitHub issues)
- Platform-specific configs (Telegram bot setup, Discord bot setup, etc.)

### 2.4 Coolify Stays (Optional PaaS Layer)

Coolify provides:
- Visual dashboard for container management
- GitHub webhook for auto-deploy of the platform itself
- SSL certificate management
- Log viewer

But it's **not required**. The system works with just Docker Compose + Traefik.

---

## 3. System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        martes.app (Platform)                      │
│                                                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐  ┌───────────┐  │
│  │  Web UI  │  │   API    │  │ Meta-Agent   │  │ Credential│  │
│  │ (Nuxt)   │  │  (Hono)  │  │   (Agno)    │  │  Handler  │  │
│  │          │  │          │  │              │  │  (OAuth)  │  │
│  │ - Signup │  │ - Tenants│  │ - Docker mgmt│  │           │  │
│  │ - Config │  │ - Billing│  │ - Config mgmt│  │ - Google  │  │
│  │ - Status │  │ - Health │  │ - Health mon │  │ - Notion  │  │
│  │ - OAuth  │  │ - OAuth  │  │ - Log analysis│ │ - Airtable│  │
│  └──────────┘  └──────────┘  └──────────────┘  └───────────┘  │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    Shared Infrastructure                      ││
│  │  PostgreSQL (platform DB) │ Redis │ Traefik │ Watchtower    ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    Tenant Containers                          ││
│  │                                                               ││
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         ││
│  │  │ hermes-t001 │  │ hermes-t002 │  │ hermes-t003 │  ...    ││
│  │  │ /opt/data   │  │ /opt/data   │  │ /opt/data   │         ││
│  │  │ :8642 (API) │  │ :8643 (API) │  │ :8644 (API) │         ││
│  │  │ Telegram    │  │ Discord     │  │ WhatsApp    │         ││
│  │  │ Google WS   │  │ Notion      │  │ Airtable    │         ││
│  │  └─────────────┘  └─────────────┘  └─────────────┘         ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Data Model

### Platform DB (PostgreSQL)

```sql
-- Tenants (customers)
CREATE TABLE tenants (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    plan TEXT NOT NULL DEFAULT 'starter',  -- starter, pro, business
    status TEXT NOT NULL DEFAULT 'active',
    container_id TEXT,                      -- Docker container ID
    container_port INTEGER,                 -- Exposed API port
    data_volume TEXT,                       -- Host path to /opt/data
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Integrations (OAuth tokens per tenant)
CREATE TABLE integrations (
    id UUID PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    provider TEXT NOT NULL,                 -- google, notion, airtable, composio
    status TEXT NOT NULL DEFAULT 'pending', -- pending, active, expired, revoked
    token_data JSONB,                       -- Encrypted OAuth tokens
    scopes TEXT[],                          -- Granted scopes
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Instance configs (what's deployed)
CREATE TABLE instance_configs (
    id UUID PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    model_provider TEXT DEFAULT 'openrouter',
    model_id TEXT DEFAULT 'openai/gpt-4o-mini',
    skills TEXT[] DEFAULT '{}',
    platforms TEXT[] DEFAULT '{}',          -- telegram, discord, whatsapp, etc.
    personality TEXT,                        -- SOUL.md content
    cron_jobs JSONB DEFAULT '[]',
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

### Hermes Data Volume (per tenant)

```
/var/lib/martes/tenants/{tenant_id}/
├── .env                    # API keys, model config
├── config.yaml             # Hermes configuration
├── SOUL.md                 # Personality/identity
├── sessions/               # Conversation history
├── memories/               # Persistent memory
├── skills/                 # Installed skills
├── cron/                   # Scheduled jobs
├── google_token.json       # Google OAuth (if connected)
├── google_client_secret.json
├── mcp.json                # MCP server configs
└── logs/                   # Runtime logs
```

---

## 5. OAuth Flow for Integrations

### Google Workspace Example

```
1. User clicks "Connect Google" in martes.app dashboard
2. Our API generates OAuth URL (using our Google Cloud OAuth client)
3. User authorizes in browser → redirect to our callback
4. Our API receives the auth code, exchanges for tokens
5. Tokens stored encrypted in `integrations` table
6. Meta-agent writes token files to tenant's Hermes volume:
   - /var/lib/martes/tenants/{id}/google_token.json
   - /var/lib/martes/tenants/{id}/google_client_secret.json
7. Hermes picks up tokens automatically on next API call
8. Token refresh handled by Hermes internally
9. If refresh fails → Meta-agent detects, notifies user to re-auth
```

### Notion Example

```
1. User clicks "Connect Notion" in dashboard
2. User creates Notion integration, pastes API key
3. Our API stores key encrypted
4. Meta-agent writes to tenant's .env:
   NOTION_API_KEY=ntn_xxx
5. Meta-agent restarts Hermes container (to pick up new env)
6. Notion skill is now active
```

### Composio MCP (Optional, Premium)

```
1. User enables Composio add-on
2. User connects accounts in Composio's UI
3. Our API gets Composio MCP server URL for this user
4. Meta-agent writes to tenant's mcp.json:
   {"composio": {"url": "https://mcp.composio.dev/user/xxx"}}
5. Hermes connects to Composio MCP on next session
6. All 250+ Composio integrations available via MCP tools
```

---

## 6. Pricing Tiers

| Feature | Starter ($15/mo) | Pro ($35/mo) | Business ($75/mo) |
|---------|-------------------|--------------|---------------------|
| Hermes instance | 1 | 1 | 1 |
| Platforms | 1 (Telegram OR Discord) | 3 | Unlimited |
| Skills | 5 | 15 | Unlimited |
| Integrations (OAuth) | 2 | 5 | Unlimited |
| Composio MCP | No | No | Yes |
| Cron jobs | 3 | 10 | Unlimited |
| Model | gpt-4o-mini | Any OpenRouter | Any + custom endpoint |
| Memory | 30 days | 90 days | Unlimited |
| Dashboard | Basic | Full | Full + API access |
| Support | Community | Email | Priority |

---

## 7. Capacity & Cost Analysis

### Per Server (Hetzner CX43: 8 vCPU, 16 GB RAM, ~$16/mo)

| Scenario | Instances | Revenue (at avg $35/tenant) | Margin |
|----------|-----------|----------------------------|--------|
| Conservative | 10 | $350/mo | 95% |
| Normal | 15 | $525/mo | 97% |
| Optimized (Modal backend) | 25 | $875/mo | 98% |

### External Costs Per Tenant

| Service | Cost | Who Pays |
|---------|------|----------|
| LLM tokens (OpenRouter) | $5-50/mo | Tenant (via their API key) |
| Hermes image (GHCR) | $0 | Us (free for public images) |
| Storage (volume) | ~$0.01/GB | Us (included in server) |
| Composio (if enabled) | $20-50/mo | Tenant |

---

## 8. Research Findings: Industry Patterns

### Multi-Tenant AI Agent Best Practices (2026)

From research (Fast.io, Scalekit, Petronella):

1. **Container-per-tenant is the gold standard** for AI agents because agents access files, memories, and credentials that can't be safely shared via row-level security alone.

2. **Five identity layers** matter in multi-tenant agents (Scalekit):
   - Trigger identity (who caused the action)
   - Execution identity (whose credentials are used)
   - Authorization identity (who granted access)
   - Tenant identity (which org boundary)
   - Attribution identity (who gets credit in audit logs)

3. **OAuth token isolation is critical** — a shared token across tenants is the #1 cause of cross-tenant data leaks in agent systems.

4. **Hermes already solves most isolation problems** by design:
   - Each instance has its own `/opt/data` volume
   - Credentials are per-instance
   - Sessions/memories are per-instance
   - No shared state between instances

5. **Managed Hermes deployments** are already being sold ($5K-$40K by Petronella Technology Group), validating the market for "Hermes as a Service."

### What We Do Differently

- **Self-service** (not consulting): user signs up, gets instance in minutes
- **Meta-agent operations** (not manual): Agno handles maintenance
- **OAuth proxy** (not manual setup): user clicks "Connect Google", we handle the rest
- **Multi-platform from day 1**: Telegram, Discord, WhatsApp, Slack, Email

---

## 9. Technical Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| Web UI | Nuxt 3 | SSR, Vue ecosystem, fast |
| API | Hono (Node.js) | Lightweight, fast, same as Nova |
| Meta-Agent | Agno (Python) | Same pattern as Nova agents |
| Auth | Clerk | Same as Nova, proven |
| DB | PostgreSQL | Platform data (tenants, billing) |
| Cache | Redis | Session store, rate limiting |
| Containers | Docker | Hermes instances |
| Reverse Proxy | Traefik | SSL, routing, per-tenant subdomains |
| CI/CD | GitHub Actions → GHCR → Watchtower | Same as Nova |
| Payments | Stripe | Standard SaaS billing |
| Monitoring | Sentry + UptimeRobot | Error tracking + uptime |

---

## 10. MVP Scope (First 4 Weeks)

### Week 1: Platform Foundation
- Nuxt landing page + signup
- Hono API (tenants CRUD, auth)
- PostgreSQL schema
- Docker Compose for platform services

### Week 2: Hermes Spawner
- Create/destroy Hermes containers via Docker API
- Volume management (create, mount, backup)
- Port allocation (dynamic port per tenant)
- Health check polling

### Week 3: Integration & Config
- OAuth flow for Google Workspace
- Notion API key input
- Config writer (model, skills, personality)
- Dashboard showing instance status

### Week 4: Meta-Agent + Polish
- Agno meta-agent with Docker management tools
- Auto-restart on failure
- Basic billing (Stripe checkout)
- Deploy to production

---

## 11. Open Questions

1. **Custom domains**: Should each tenant get `{slug}.martes.app` or use their own domain?
2. **Model API keys**: Do we provide a shared OpenRouter key (and bill per token), or does each tenant bring their own?
3. **Hermes updates**: When NousResearch releases a new version, do we auto-update all tenants or let them choose?
4. **Data export**: How does a tenant export their Hermes data (sessions, memories, skills) if they leave?
5. **Abuse prevention**: How do we prevent tenants from using Hermes for spam/abuse via the messaging gateways?
