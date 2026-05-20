# Martes.app — Inicio de Implementación

> **Status**: En desarrollo  
> **Date**: May 2026

---

## Tiers de Precio (Final)

| Tier | Precio | Audiencia | Plataformas | Skills | Crons | Modelo | Browser | Dashboard |
|------|--------|-----------|-------------|--------|-------|--------|---------|-----------|
| **Básico** | $30/mo | Freelancer/persona sola | 1 | Google WS, email, Notion | 3 | DeepSeek V4 | No | No |
| **Equipo** | $100/mo | PYME hasta 10 personas | 2 | Todos oficina + wiki + OCR | 10 | DeepSeek V4 | Firecrawl | Sí |
| **Pro** | $200/mo | Dev teams / power users | Todas | Todos + GitHub + Linear + code | Ilimitados | Claude Haiku | Playwright | Sí |

---

## Flujo de Pagos: Stripe → PostgreSQL → Meta-Agente

```
Stripe Checkout → Webhook → API → PostgreSQL → Meta-Agente → Container creado
```

### Detalle:

1. **Usuario contacta por WhatsApp** → le mandamos link de Stripe Checkout
2. **Stripe procesa pago** → envía webhook `checkout.session.completed`
3. **Nuestro endpoint** (`/api/webhooks/stripe`) verifica firma y escribe en DB:
   - `INSERT INTO tenants` (nuevo cliente)
   - `INSERT INTO billing_events` (pago registrado)
   - `INSERT INTO pending_actions` (acción: crear instancia)
4. **Meta-agente** (polling cada 30s) lee `pending_actions`:
   - Crea volumen + config + container
   - Marca acción como completada
   - Actualiza tenant status → 'active'
5. **Notificamos al usuario** (WhatsApp): "Tu agente está listo"

### Eventos de Stripe que manejamos:

| Evento | Acción |
|--------|--------|
| `checkout.session.completed` | Crear tenant + instancia |
| `invoice.paid` | Registrar pago, reactivar si estaba pausado |
| `invoice.payment_failed` | Registrar fallo, enviar aviso |
| `customer.subscription.deleted` | Pausar instancia, iniciar countdown de backup |
| `customer.subscription.updated` | Upgrade/downgrade de plan |

---

## Estructura del Proyecto

```
martes.app/
├── apps/
│   ├── meta-agent/                 ← Agno meta-agente
│   │   ├── src/
│   │   │   ├── __init__.py
│   │   │   ├── main.py            ← AgentOS entry point
│   │   │   ├── config.py          ← DB, modelos, config
│   │   │   ├── agent.py           ← Definición del meta-agente
│   │   │   └── tools/
│   │   │       ├── __init__.py
│   │   │       ├── docker_ops.py  ← create/stop/restart containers
│   │   │       ├── tenant_config.py ← write config/env/soul to volumes
│   │   │       ├── billing.py     ← check payments, process actions
│   │   │       ├── health.py      ← poll health, detect issues
│   │   │       └── backup.py      ← tar.gz volumes, upload to R2
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   │
│   └── api/                        ← API mínima (webhooks + health)
│       ├── src/
│       │   ├── index.ts
│       │   ├── webhooks/
│       │   │   └── stripe.ts      ← Recibe webhooks de Stripe
│       │   └── health.ts
│       ├── Dockerfile
│       └── package.json
│
├── db/
│   └── migrations/
│       └── 001_initial_schema.sql  ← Schema de arriba
│
├── infra/
│   ├── docker-compose.yml          ← Todo el stack
│   ├── bootstrap.sh                ← Setup de VPS
│   └── templates/                  ← Configs preconfigurados
│       ├── basico/
│       │   ├── config.yaml
│       │   ├── env.template
│       │   └── SOUL.md
│       ├── equipo/
│       │   ├── config.yaml
│       │   ├── env.template
│       │   └── SOUL.md
│       └── pro/
│           ├── config.yaml
│           ├── env.template
│           └── SOUL.md
│
├── scripts/
│   ├── create-tenant.sh            ← Manual (para testing)
│   ├── stop-tenant.sh
│   └── backup-tenant.sh
│
├── docs/                           ← Planificación (ya hecha)
│   ├── 00-ARCHITECTURE-PLAN.md
│   ├── 01-DEEP-RESEARCH-FINDINGS.md
│   ├── 02-DOCKER-INFRA-EXPLAINED.md
│   ├── 03-WHATS-NEXT-DECISION-MATRIX.md
│   ├── 04-PRODUCT-DECISIONS-FINAL.md
│   ├── 05-MEMORY-WIKI-LLM-DECISIONS.md
│   ├── 06-ADDONS-COMPOSIO-MEMORY.md
│   └── 07-IMPLEMENTATION-START.md
│
├── .github/
│   └── workflows/
│       └── cd.yml                  ← Build meta-agent + API images
│
└── docker-compose.yml → infra/docker-compose.yml (symlink)
```

---

## Orden de Implementación

### Sprint 1 (esta semana): Infra + Meta-Agente

1. `docker-compose.yml` (PostgreSQL + Traefik + meta-agente + Portainer)
2. Schema SQL (migrations/001)
3. Meta-agente Agno con tools básicos:
   - `create_tenant_container()`
   - `stop_tenant_container()`
   - `check_health()`
   - `process_pending_actions()`
4. Templates de Hermes (config.yaml para cada tier)
5. Script `create-tenant.sh` para testing manual

### Sprint 2: API + Stripe

6. API mínima (Hono): webhook de Stripe + health check
7. Integración Stripe → DB → pending_actions
8. Meta-agente procesa acciones automáticamente
9. Flujo completo: pago → container creado

### Sprint 3: Onboarding + Polish

10. Guía de setup de Telegram bot para el tenant
11. Wiki injection (meta-agente escribe contenido inicial)
12. Health monitoring + auto-restart
13. Backup automatizado

### Sprint 4: Producción

14. Deploy en VPS (Hetzner CX43)
15. DNS + Cloudflare
16. Primer tenant real (beta)
17. Monitoring (Sentry + UptimeRobot)
