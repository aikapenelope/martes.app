# martes.app

Plataforma SaaS multi-tenant venezolana: cada cliente recibe su propia instancia de **Hermes AI agent** (NousResearch), gestionada y mantenida por un meta-agente Agno AgentOS. El admin opera todo desde Telegram.

---

## Qué hace esta plataforma

**martes.app gestiona la plataforma. Hermes gestiona su propio funcionamiento.**

El meta-agente despliega, monitorea, respalda y mantiene los containers de Hermes. El cliente configura su agente directamente desde Telegram usando los comandos nativos de Hermes (`/model`, `/skills`, `/auth`, `/sethome`, etc.).

```
Admin vía Telegram → Meta-agente → Crea / Monitorea / Mantiene containers Hermes
Cliente vía Telegram → Hermes → Responde, aprende, se configura solo
```

---

## Stack

| Componente | Tecnología | Versión |
|---|---|---|
| Servidor | Hetzner CX43 · 8 vCPU · 16GB RAM · hel1 | — |
| Orquestador | Coolify + Traefik | — |
| Meta-agente | Agno AgentOS + Telegram | 2.6.8 |
| Base de datos | PostgreSQL 18 + pgvector | agnohq/pgvector:18 |
| Tenants | Hermes Agent (NousResearch) | v2026.5.16 (= v0.14.0) |
| Object storage | SeaweedFS | 4.28 |
| Observabilidad | Metabase | v0.61.2.6 |
| Infraestructura | Hetzner Cloud via Pulumi (TypeScript) | — |
| VPN admin | Tailscale | — |

---

## Arquitectura

```
INTERNET
    │ HTTPS
    ▼
Traefik (Coolify)
    ├── api.martes.app → Meta-agente :7777
    └── (futuro) {slug}.martes.app → containers por tenant

Servidor Hetzner CX43
    ├── Stack Docker (infra/docker-compose.yml)
    │     ├── meta-agent     (Agno AgentOS)
    │     ├── db             (PostgreSQL 18 + pgvector)
    │     ├── seaweedfs      (backups S3)
    │     └── metabase       (admin dashboard — solo Tailscale)
    │
    └── Containers de tenants (gestionados por Docker SDK)
          ├── hermes-t001    (red aislada tenant-t001-net)
          ├── hermes-t002    (red aislada tenant-t002-net)
          └── ...
```

Cada tenant Hermes corre en:
- Imagen: `nousresearch/hermes-agent:v2026.5.16`
- Red Docker aislada propia
- Volumen dedicado en `/var/lib/martes/tenants/{code}/`
- RAM: `768MB` límite (único límite intencional)
- Sin restricciones de capabilities, pids, tmpfs — factory defaults de Docker

---

## Cómo funciona — operación diaria

### Crear un tenant

```
Admin → Telegram meta-agente:
"crea tenant Acme Corp token 123456:ABC telegram_id 563825119"

Meta-agente:
  1. Crea registro en DB (tenants + instance_configs)
  2. Crea volumen /var/lib/martes/tenants/t001/
  3. Escribe .env (TELEGRAM_BOT_TOKEN, OPENROUTER_API_KEY, TELEGRAM_HOME_CHANNEL, etc.)
  4. Copia config.yaml + SOUL.md desde infra/templates/default/
  5. Arranca container hermes-t001
  6. Verifica health (GET /health → 200 en 30s)
  7. Activa trial de 30 días en DB
  8. Confirma: "Tenant t001 creado. Bot listo en @acme_bot"
```

### El cliente usa su bot

El cliente habla con `@acme_bot` en Telegram. Hermes tiene capacidades completas:
- `/model deepseek/deepseek-v4-flash` — cambiar el modelo LLM
- `/skills install airtable` — instalar skills desde el hub oficial
- `/auth` — configurar su propia API key de cualquier proveedor
- `/sethome` — configurar el canal de notificaciones
- `hermes update` — actualizar Hermes a la última versión
- Búsqueda web (ddgs), browser automation, subagentes, cron jobs, TTS, etc.

### Mantenimiento automático

| Schedule | Cron | Función |
|---|---|---|
| `daily-backup-all` | 3:00 AM UTC | Backup de todos los tenants activos a SeaweedFS |
| `health-check-all` | cada 5 min | Health check + alerta Telegram si hay problemas |
| `billing-check` | 9:00 AM UTC | Alertas de vencimiento + auto-suspend |
| `expire-platform-keys` | cada 30 min | BYOK: blanquea platform key cuando expira |
| `docker-cleanup` | Dom 4:00 AM | Limpia imágenes Hermes huérfanas |

---

## Billing BYOK

Al crear un tenant, se escribe la platform key de OpenRouter en el `.env` del tenant. El agente funciona desde el minuto 0. El cliente tiene 2 horas (configurable) para configurar su propia key con `/auth` o `/model`. Cuando lo hace, nuestra key se blanquea automáticamente. Si no lo hace, el agente deja de funcionar hasta que configure sus credenciales.

---

## Base de datos

### Schema `public` — tablas de negocio

| Tabla | Contenido |
|---|---|
| `tenants` | Clientes (nombre, código, estado, paid_until) |
| `instance_configs` | Config técnica por tenant (modelo, resources, extra_config) |
| `payments` | Registro de pagos (monto, método, referencia) |
| `health_checks` | Historial de health checks (status, response_ms) |
| `error_logs` | Errores de containers (severity, source, resolved) |

### Schema `ai` — tablas de Agno (auto-gestionadas)

`martes_sessions`, `martes_memories`, `martes_traces`, `martes_knowledge`

---

## Estructura del repositorio

```
martes.app/
├── apps/
│   └── meta-agent/               # Agno AgentOS
│       ├── src/
│       │   ├── main.py           # AgentOS entry + maintenance endpoints + schedules
│       │   ├── team.py           # Team(coordinate): Diagnosticador + Operador
│       │   ├── shared.py         # DB, Models, Learning, Skills
│       │   ├── config.py         # Settings (pydantic_settings)
│       │   ├── storage.py        # Cliente SeaweedFS S3
│       │   └── agents/
│       │       ├── operador.py   # Agente de escritura (HITL)
│       │       └── diagnosticador.py  # Agente de lectura
│       │   └── tools/
│       │       ├── write_ops.py  # create/stop/restart/delete/backup/restore/upgrade...
│       │       └── read_ops.py   # health/logs/stats/backups/capacity...
│       ├── Dockerfile
│       └── pyproject.toml
│
├── db/
│   └── migrations/
│       ├── 001_initial_schema.sql
│       └── 002_single_plan.sql
│
├── infra/
│   ├── docker-compose.yml        # Stack principal: db + meta-agent + seaweedfs + metabase
│   ├── .env.example
│   └── templates/
│       └── default/
│           └── config.yaml       # Template Hermes para todos los tenants
│
├── pulumi/                       # Hetzner CX43 + SSH + Firewall + cloud-init
│
├── docs/
│   ├── hermes-guia/              # Documentación del producto y capacidades de Hermes
│   ├── 10-ROADMAP.md             # Estado actual y próximos sprints
│   └── SPRINT-G-PLAN.md          # Sprint G (descartado/referencia)
│
├── CHANGELOG.md
└── AGENTS.md                     # Reglas para Neo (este agente)
```

---

## CI/CD

```
git push → main
    └── GitHub Actions (.github/workflows/cd.yml)
          ├── Secret scan (gitleaks) — bloquea si detecta credenciales
          └── Build check (Docker build) — verifica que compila
                │
                └── Coolify (auto-deploy via GitHub App)
                      ├── Detecta el push
                      ├── Construye la imagen en el servidor
                      └── Redespliega meta-agent automáticamente
```

El deploy a producción es automático en cada push a `main`. No se sube imagen a ningún registry — Coolify construye directamente en el servidor.

---

## Desarrollo local

```bash
git clone https://github.com/aikapenelope/martes.app.git
cd martes.app

# Levantar infra local
cp infra/.env.example infra/.env
# Editar infra/.env (APP_ENV=development activa polling de Telegram)
docker compose -f infra/docker-compose.yml up -d

# Meta-agente
cd apps/meta-agent
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m src.main

# Validar código
pyright src/
ruff check src/
```

---

## Provisionar servidor nuevo (Pulumi)

```bash
cd pulumi/
pulumi stack select dev
pulumi config set --secret martes-infra:tailscaleAuthKey <tskey-...>  # opcional
pulumi up
```

El VPS arranca con Docker + Tailscale + Coolify pre-instalados via cloud-init.

---

## Documentación

| Doc | Contenido |
|---|---|
| `docs/hermes-guia/00-PARADIGMA-PLATAFORMA.md` | La separación plataforma vs agente |
| `docs/hermes-guia/01-CAPACIDADES-COMPLETAS.md` | Hermes v0.14.0: capacidades completas |
| `docs/hermes-guia/02-CONTEXTO-VENEZOLANO.md` | Mercado venezolano + oportunidad |
| `docs/hermes-guia/03-MEJORES-PRACTICAS.md` | SOUL.md, modelos, skills, cron |
| `docs/hermes-guia/04-INTEGRACIONES-TOOLS.md` | Airtable, Google WS, stocks, Shopify |
| `docs/hermes-guia/05-PITCH-PYME.md` | Propuesta de valor para PyMEs |
| `docs/10-ROADMAP.md` | Estado actual y próximos sprints |
| `CHANGELOG.md` | Historial de cambios por sprint |
| `AGENTS.md` | Reglas de comportamiento de Neo |
