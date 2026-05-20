# martes.app

SaaS de agentes Hermes gestionados por un meta-agente Agno. PYMEs pagan $30-200/mes y obtienen un agente IA conectado a sus herramientas de trabajo (Google, Notion, Airtable, GitHub), accesible via Telegram/Discord.

---

## Arquitectura

```
┌─────────────────────────────────────────────────────────────────────┐
│ Servidor (Hetzner CX43 — 8 vCPU, 16 GB RAM)                         │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ Infraestructura de Plataforma                                │    │
│  │                                                               │    │
│  │  ┌──────────┐  ┌──────────────┐  ┌──────────┐  ┌────────┐  │    │
│  │  │ Traefik  │  │ Meta-Agente  │  │PostgreSQL│  │Portainer│  │    │
│  │  │ :80/:443 │  │   (Agno)     │  │(pgvector)│  │  :9000  │  │    │
│  │  │          │  │   :8000*     │  │  :5432   │  │         │  │    │
│  │  └──────────┘  └──────────────┘  └──────────┘  └────────┘  │    │
│  │  * Puerto 8000 solo via Tailscale                            │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ Containers de Tenants (Hermes Agent v0.14.0)                 │    │
│  │                                                               │    │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────┐               │    │
│  │  │hermes-t001│  │hermes-t002│  │hermes-t003│  ...           │    │
│  │  │ Telegram  │  │ Discord   │  │ Telegram  │               │    │
│  │  │ Google WS │  │ GitHub    │  │ Notion    │               │    │
│  │  │ Notion    │  │ Linear    │  │ Airtable  │               │    │
│  │  │ ~400MB    │  │ ~700MB    │  │ ~400MB    │               │    │
│  │  └───────────┘  └───────────┘  └───────────┘               │    │
│  │  Cada uno en su propia bridge network (aislados)             │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Stack Técnico

| Componente | Tecnología | Versión |
|-----------|-----------|---------|
| Meta-agente | Agno AgentOS + Telegram Interface | v2.6.x |
| DB | `agnohq/pgvector:18` (PostgreSQL 18 + pgvector) | 18 |
| Tenants | `nousresearch/hermes-agent` | v0.14.0 (pinned) |
| Reverse proxy | Traefik | v3.4 |
| VPN admin | Tailscale | latest |
| Viewer emergencia | Portainer CE | latest |
| LLM | DeepSeek V4 via OpenRouter | — |

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

### Gestión via Telegram

```
Admin: "Lista todos los tenants"
Meta:  "3 tenants activos:
        • Empresa XYZ (equipo) — healthy, 15 días restantes
        • Dev Studio (pro) — healthy, 28 días restantes  
        • Freelancer Juan (básico) — healthy, 5 días restantes"

Admin: "Pausa Freelancer Juan, no pagó"
Meta:  "✓ Container hermes-t003 detenido. Datos preservados."

Admin: "Conecta Google Workspace a Empresa XYZ, token: ya29.xxx"
Meta:  "✓ google_token.json inyectado. Container reiniciado. Google activo."
```

---

## Tiers

| Tier | Precio | Plataformas | Skills | Modelo | RAM |
|------|--------|-------------|--------|--------|-----|
| **Básico** | $30/mo | 1 (Telegram) | Google WS, email, Notion, Airtable | DeepSeek V4 | ~400MB |
| **Equipo** | $100/mo | 2 (Telegram + Discord) | Todo oficina + wiki + OCR + vision | DeepSeek V4 | ~600MB |
| **Pro** | $200/mo | Todas | Todo + GitHub + Linear + browser + code | Claude Haiku | ~1GB |

**Capacidad por servidor**: ~24 tenants (mix típico) = ~$2,000/mo revenue en un servidor de $16/mo.

---

## Estructura del Proyecto

```
martes.app/
├── apps/
│   └── meta-agent/                 # Agno AgentOS (FastAPI + Telegram)
│       ├── src/
│       │   ├── main.py             # AgentOS entry point
│       │   ├── config.py           # PostgresDb, modelos, config
│       │   ├── agent.py            # Meta-agente (instrucciones + tools)
│       │   └── tools/
│       │       ├── docker_ops.py   # create/stop/restart/list containers
│       │       ├── tenant_config.py # write config/env/soul to volumes
│       │       ├── tenant_db.py    # CRUD tenants en PostgreSQL
│       │       ├── health.py       # poll health de todos los containers
│       │       └── backup.py       # tar.gz → R2
│       ├── Dockerfile
│       └── pyproject.toml
│
├── db/
│   └── migrations/
│       └── 001_initial.sql         # Schema: tenants, configs, payments, health, errors
│
├── infra/
│   ├── docker-compose.yml          # PostgreSQL + Traefik + meta-agente + Portainer
│   ├── bootstrap.sh                # Setup completo de VPS nuevo
│   └── templates/                  # Configs preconfigurados de Hermes
│       ├── basico/
│       │   ├── config.yaml         # Toolset mínimo, DeepSeek, 1 plataforma
│       │   ├── env.template        # Variables de entorno
│       │   └── SOUL.md             # Personalidad default
│       ├── equipo/
│       │   ├── config.yaml         # Toolset completo oficina, wiki, vision
│       │   ├── env.template
│       │   └── SOUL.md
│       └── pro/
│           ├── config.yaml         # Todo habilitado, browser, code execution
│           ├── env.template
│           └── SOUL.md
│
├── docs/                           # Planificación completa (8 documentos)
│
└── .github/
    └── workflows/
        └── cd.yml                  # Build meta-agent image → GHCR
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

## Hermes: Cómo Funciona Cada Tenant

Cada tenant es un container `nousresearch/hermes-agent:0.14.0` con:

**Almacenamiento** (volumen en `/var/lib/martes/tenants/{id}/`):
- `state.db` — SQLite con sesiones, historial, búsqueda FTS5
- `config.yaml` — configuración completa del agente
- `.env` — API keys (OpenRouter, bot token)
- `SOUL.md` — personalidad del agente
- `wiki/` — LLM Wiki (conocimiento acumulativo del equipo)
- `memories/` — memoria persistente por usuario
- `skills/` — skills instalados
- `cron/` — jobs programados

**Red**: Bridge network aislada (no ve otros tenants ni la DB de plataforma)

**Recursos**: Limitados por Docker (`--memory`, `--cpus`) según tier

**Actualización**: Version pinned. No auto-update. Admin decide cuándo actualizar.

---

## Seguridad

| Capa | Mecanismo |
|------|-----------|
| Aislamiento de tenants | Bridge network separada + volumen propio |
| Acceso al meta-agente | Solo via Telegram (bot privado del admin) |
| Puerto 8000 (API) | Solo accesible via Tailscale |
| Dashboard de tenants | Cloudflare Access (login por email) |
| Docker socket | Solo el meta-agente lo tiene (no los tenants) |
| Credenciales | En .env con permisos 600, nunca en código |
| Backups | Encriptados antes de subir a R2 |

---

## Flujo de No-Pago

```
Día 0:   Activo
Día 30:  No paga → Admin le escribe al meta-agente: "Pausa tenant X"
         → Container detenido, datos preservados
Día 45:  No paga → "Archiva tenant X"
         → Backup a R2, volumen local eliminado
Día 90:  No paga → Backup eliminado de R2
         → Datos perdidos permanentemente

Si paga después (antes de día 90):
         → "Reactiva tenant X"
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
- Config: una línea en `config.yaml` del tenant

### LLM Wiki (incluido en todos):
- Base de conocimiento en markdown
- El agente la construye y consulta automáticamente
- Meta-agente inyecta contenido inicial (info de empresa, equipo, procesos)

---

## Desarrollo

### Requisitos
- Python 3.12+
- Docker + Docker Compose
- Una API key de OpenRouter
- Un bot token de Telegram (para el meta-agente)

### Setup Local

```bash
git clone https://github.com/aikapenelope/martes.app.git
cd martes.app

# Configurar variables
cp infra/.env.example .env
# Editar .env con tus keys

# Levantar infra
docker compose -f infra/docker-compose.yml up -d

# Desarrollar meta-agente
cd apps/meta-agent
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python src/main.py
```

### Deploy a Producción

```bash
# Opción A: VPS nuevo manual
ssh root@<IP>
git clone https://github.com/aikapenelope/martes.app.git /opt/martes
cd /opt/martes && bash infra/bootstrap.sh

# Opción B: Pulumi (crea el VPS automáticamente)
cd pulumi/
pulumi up
```

---

## Documentación Completa

| Doc | Contenido |
|-----|-----------|
| [00-ARCHITECTURE-PLAN](docs/00-ARCHITECTURE-PLAN.md) | Visión general del SaaS |
| [01-DEEP-RESEARCH](docs/01-DEEP-RESEARCH-FINDINGS.md) | Browser, tokens, multi-tenant, costos |
| [02-DOCKER-INFRA](docs/02-DOCKER-INFRA-EXPLAINED.md) | Docker, redes, DB, patrones de producción |
| [03-DECISIONS](docs/03-WHATS-NEXT-DECISION-MATRIX.md) | Coolify (no), bridge (sí), orden de implementación |
| [04-PRODUCT](docs/04-PRODUCT-DECISIONS-FINAL.md) | Precio, templates, seguridad, no-pago |
| [05-MEMORY-WIKI](docs/05-MEMORY-WIKI-LLM-DECISIONS.md) | Wiki, memoria, LLM incluido |
| [06-ADDONS](docs/06-ADDONS-COMPOSIO-MEMORY.md) | Composio, Honcho, add-ons |
| [07-IMPLEMENTATION](docs/07-IMPLEMENTATION-START.md) | Sprints, estructura, flujo de pagos |
| [08-VALIDATION](docs/08-VALIDATION-AUDIT.md) | Auditoría pre-implementación, errores corregidos |
