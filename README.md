# martes.app

SaaS de agentes Hermes gestionados por un meta-agente Agno. PYMEs pagan $30-200/mes y obtienen un agente IA conectado a sus herramientas de trabajo (Google, Notion, Airtable, GitHub), accesible via Telegram/Discord.

---

## Arquitectura

```
┌─────────────────────────────────────────────────────────────────────┐
│ Servidor (Hetzner CX43 — 8 vCPU, 16 GB RAM)                        │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ Coolify (orquestador + reverse proxy + SSL)                   │   │
│  │                                                                │   │
│  │  ┌──────────────────────┐  ┌──────────────────────────────┐  │   │
│  │  │   Meta-Agente (Agno) │  │ PostgreSQL (agnohq/pgvector)  │  │   │
│  │  │   api.martes.app     │  │   :5432 (interno)            │  │   │
│  │  │   :7777 (interno)    │  └──────────────────────────────┘  │   │
│  │  │   :8001 Tailscale    │                                     │   │
│  │  └──────────────────────┘                                     │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ Containers de Tenants (Hermes Agent v0.14.0)                  │   │
│  │                                                                │   │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────┐                │   │
│  │  │hermes-t001│  │hermes-t002│  │hermes-t003│  ...           │   │
│  │  │ Telegram  │  │ Discord   │  │ Telegram  │                │   │
│  │  │ ~400MB    │  │ ~700MB    │  │ ~400MB    │                │   │
│  │  └───────────┘  └───────────┘  └───────────┘                │   │
│  │  Cada uno en su propia bridge network (aislados)              │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Stack Técnico

| Componente      | Tecnología                                     | Versión   |
|-----------------|------------------------------------------------|-----------|
| Meta-agente     | Agno AgentOS + Telegram Interface              | v2.6.x    |
| DB              | `agnohq/pgvector:18` (PostgreSQL 18 + pgvector)| 18        |
| Tenants         | `nousresearch/hermes-agent`                    | v0.14.0   |
| Orquestador     | Coolify (reverse proxy + SSL + deployments)    | latest    |
| VPN admin       | Tailscale                                      | latest    |
| LLM             | DeepSeek V4 via OpenRouter                     | —         |
| Infraestructura | Hetzner Cloud via Pulumi (TypeScript)          | —         |

---

## Cómo Funciona

### Flujo de Operación

```
1. Cliente paga (transferencia, Zelle, crypto — manual)
2. Admin escribe al meta-agente por Telegram:
   "Crea tenant Empresa XYZ, plan equipo, bot token 123:ABC"
3. Meta-agente ejecuta:
   - Crea volumen /var/lib/martes/tenants/t001/
   - Escribe config.yaml (template según plan)
   - Escribe .env (OpenRouter key, bot token)
   - Escribe SOUL.md (personalidad)
   - Crea bridge network aislada
   - docker run nousresearch/hermes-agent:0.14.0
   - Verifica health check
   - Registra en PostgreSQL
4. Admin le dice al cliente: "Tu agente está listo, escríbele a @xyz_bot"
```

### Flujo de Deploy Automático

```
git push → main
    └── GitHub Actions
          ├── Build imagen ghcr.io/aikapenelope/martes-meta-agent:latest
          └── GET COOLIFY_WEBHOOK_URL
                └── Coolify
                      ├── git pull infra/docker-compose.yml
                      ├── docker pull ghcr.io/.../martes-meta-agent:latest
                      └── docker compose up -d meta-agent
```

### Gestión via Telegram

```
Admin: "Lista todos los tenants"
Meta:  "3 tenants activos:
        • Empresa XYZ (equipo) — healthy, 15 días restantes
        • Dev Studio (pro) — healthy, 28 días restantes
        • Freelancer Juan (básico) — healthy, 5 días restantes"

Admin: "Pausa Freelancer Juan, no pagó"
Meta:  "Container hermes-t003 detenido. Datos preservados."

Admin: "Conecta Google Workspace a Empresa XYZ, token: ya29.xxx"
Meta:  "google_token.json inyectado. Container reiniciado. Google activo."
```

---

## Tiers

| Tier       | Precio  | Plataformas              | Skills                              | Modelo       | RAM   |
|------------|---------|--------------------------|-------------------------------------|--------------|-------|
| **Básico** | $30/mo  | 1 (Telegram)             | Google WS, email, Notion, Airtable  | DeepSeek V4  | ~400MB|
| **Equipo** | $100/mo | 2 (Telegram + Discord)   | Todo oficina + wiki + OCR + vision  | DeepSeek V4  | ~600MB|
| **Pro**    | $200/mo | Todas                    | Todo + GitHub + Linear + code       | Claude Haiku | ~1GB  |

**Capacidad por servidor**: ~24 tenants (mix típico) = ~$2,000/mo revenue en un servidor de $16/mo.

---

## Estructura del Proyecto

```
martes.app/
├── apps/
│   └── meta-agent/                 # Agno AgentOS (FastAPI + Telegram)
│       ├── src/
│       │   ├── main.py             # AgentOS entry point
│       │   ├── team.py             # Team(coordinate) Diagnosticador + Operador
│       │   ├── shared.py           # DB, Models, Learning, Skills
│       │   └── agents/
│       │       ├── diagnosticador.py  # Read-only agent
│       │       └── operador.py        # Write agent con @approval
│       ├── Dockerfile
│       └── pyproject.toml
│
├── db/
│   └── migrations/
│       └── 001_initial.sql         # Schema: tenants, configs, payments, health, errors
│
├── infra/
│   ├── docker-compose.yml          # Solo servicios de app: PostgreSQL + meta-agente
│   ├── .env.example                # Variables requeridas
│   └── templates/                  # Configs preconfigurados de Hermes por tier
│       ├── basico/
│       ├── equipo/
│       └── pro/
│
├── pulumi/                         # Infraestructura Hetzner (TypeScript)
│   ├── index.ts                    # Servidor CX43 + SSH + Firewall + cloud-init
│   └── Pulumi.dev.yaml
│
└── .github/
    └── workflows/
        └── cd.yml                  # Build GHCR + trigger Coolify webhook
```

---

## Base de Datos (PostgreSQL Compartida)

Una sola instancia `agnohq/pgvector:18` (~200MB RAM) para:

**Tablas de plataforma:**
- `tenants` — clientes (nombre, plan, status, container_name, paid_until)
- `instance_configs` — qué tiene cada tenant (template, skills, platforms, model)
- `payments` — registro manual de pagos (monto, método, referencia, período)
- `health_checks` — historial de health checks por tenant
- `error_logs` — errores para diagnóstico

**Tablas de Agno (auto-creadas):**
- `agno_sessions` — sesiones del meta-agente
- `agno_memories` — lo que el meta-agente recuerda
- `agno_traces` — log de cada acción (audit trail automático)

---

## Seguridad

| Capa                    | Mecanismo                                              |
|-------------------------|--------------------------------------------------------|
| Aislamiento de tenants  | Bridge network separada + volumen propio               |
| Acceso al meta-agente   | Solo via Telegram (bot privado del admin)              |
| AgentOS API (:8001)     | Solo accesible via Tailscale                           |
| Coolify UI (:8000)      | Solo accesible via Tailscale (UFW + firewall Hetzner)  |
| Docker socket           | Solo el meta-agente lo tiene (no los tenants)          |
| Credenciales            | En Coolify env vars, nunca en código                   |
| Backups                 | Encriptados antes de subir a R2                        |

---

## Flujo de No-Pago

```
Día 0:   Activo
Día 30:  No paga → Admin: "Pausa tenant X" → Container detenido, datos preservados
Día 45:  No paga → Admin: "Archiva tenant X" → Backup a R2, volumen local eliminado
Día 90:  No paga → Backup eliminado de R2 → Datos perdidos permanentemente

Si paga antes del día 90:
         → Admin: "Reactiva tenant X"
         → Descarga backup de R2, crea container, todo restaurado
```

---

## Integraciones

### Nativas de Hermes (via skills):
- Google Workspace (Gmail, Calendar, Drive, Sheets, Docs) — OAuth
- Notion — API key
- Airtable — API key
- Linear — API key
- GitHub (PRs, issues, code review) — token
- Email IMAP/SMTP (Himalaya) — credenciales

### Via Composio MCP (add-on):
- 1000+ apps (Slack, HubSpot, Salesforce, Trello, Jira, etc.)
- OAuth gestionado por Composio

---

## Desarrollo Local

### Requisitos
- Python 3.12+
- Docker + Docker Compose
- API key de OpenRouter
- Bot token de Telegram

### Setup

```bash
git clone https://github.com/aikapenelope/martes.app.git
cd martes.app

# Configurar variables
cp infra/.env.example infra/.env
# Editar infra/.env con tus keys (APP_ENV=development para polling local)

# Levantar infra local
docker network create martes-tenants  # red de tenants (external en el compose)
docker compose -f infra/docker-compose.yml up -d

# Desarrollar meta-agente
cd apps/meta-agent
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python src/main.py
```

---

## Provisionar un VPS Nuevo (Pulumi)

```bash
cd pulumi/

# Configurar (primera vez)
pulumi stack select dev

# Opcional: auto-join Tailscale en el boot
pulumi config set --secret martes-infra:tailscaleAuthKey <tskey-...>

# Crear servidor en Hetzner
pulumi up
```

El servidor arranca con Docker + Tailscale + Coolify pre-instalados via cloud-init.

### Setup inicial de Coolify (una sola vez tras el boot)

1. Conectar via Tailscale y abrir `http://<tailscale-ip>:8000`
2. Crear cuenta admin
3. **Servers** → Add Server → localhost (via SSH local)
4. **New Project** → New Resource → Docker Compose → Git repository
   - URL: `https://github.com/aikapenelope/martes.app`
   - Compose path: `infra/docker-compose.yml`
   - Branch: `main`
5. Configurar dominio `api.martes.app` en el servicio `meta-agent`
6. **Registries** → Add → Custom (`ghcr.io`) + GitHub PAT con `read:packages`
7. **Environment Variables** → agregar `PG_PASSWORD`, `OPENROUTER_API_KEY`, `META_AGENT_TELEGRAM_TOKEN`
8. Deploy → copiar el **Webhook URL** del servicio
9. En GitHub repo → **Settings → Secrets** → agregar `COOLIFY_WEBHOOK_URL` con el valor copiado
10. Registrar webhook de Telegram:
    ```bash
    curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://api.martes.app/telegram/webhook"
    ```

---

## Documentación

| Doc | Contenido |
|-----|-----------|
| [00-ARCHITECTURE-PLAN](docs/00-ARCHITECTURE-PLAN.md) | Visión general del SaaS |
| [01-DEEP-RESEARCH](docs/01-DEEP-RESEARCH-FINDINGS.md) | Browser, tokens, multi-tenant, costos |
| [02-DOCKER-INFRA](docs/02-DOCKER-INFRA-EXPLAINED.md) | Docker, redes, DB, patrones de producción |
| [04-PRODUCT](docs/04-PRODUCT-DECISIONS-FINAL.md) | Precio, templates, seguridad, no-pago |
| [05-MEMORY-WIKI](docs/05-MEMORY-WIKI-LLM-DECISIONS.md) | Wiki, memoria, LLM incluido |
| [06-ADDONS](docs/06-ADDONS-COMPOSIO-MEMORY.md) | Composio, Honcho, add-ons |
