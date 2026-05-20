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

## Flujo de Pagos: Manual via Telegram al Meta-Agente

```
Admin (tú) escribe al meta-agente por Telegram → Meta-agente crea todo
```

**No hay Stripe. No hay checkout automatizado.** El cobro es manual (transferencia, Zelle, Pago Móvil, lo que sea). Cuando el cliente paga, tú le dices al meta-agente que cree la instancia.

### Flujo Real:

1. **Cliente te contacta por WhatsApp** → acuerdan plan y precio
2. **Cliente paga** (transferencia, Zelle, Pago Móvil, crypto, lo que sea)
3. **Tú confirmas el pago** y le escribes al meta-agente por Telegram:

```
Tú: "Crea un tenant nuevo:
  - Nombre: Empresa XYZ
  - Email: contacto@xyz.com
  - Plan: equipo
  - Plataforma: telegram
  - Bot token: 123456:ABC..."

Meta-agente: "Creando instancia para Empresa XYZ (plan equipo)...
  ✓ Volumen creado
  ✓ Config escrita (template equipo)
  ✓ Container hermes-t004 iniciado
  ✓ Health check OK
  
  Listo. El agente está activo en Telegram."
```

4. **Tú le dices al cliente**: "Tu agente está listo, escríbele a @xyz_bot"

### Para Pausar/Reactivar:

```
Tú: "Pausa el tenant Empresa XYZ, no pagó este mes"
Meta-agente: "Pausando hermes-t004...
  ✓ Container detenido
  ✓ Tenant marcado como 'paused'
  Datos preservados. Se puede reactivar cuando pague."

Tú: "Reactiva Empresa XYZ, ya pagó"
Meta-agente: "Reactivando hermes-t004...
  ✓ Container iniciado
  ✓ Health check OK
  ✓ Tenant marcado como 'active'"
```

### Para Conectar Integraciones:

```
Tú: "Conecta Google Workspace al tenant Empresa XYZ. 
     El token OAuth es: ya29.xxx..."
Meta-agente: "Inyectando credenciales de Google en hermes-t004...
  ✓ google_token.json escrito
  ✓ Container reiniciado
  Google Workspace activo para Empresa XYZ."
```

### Ventajas de Este Enfoque:

- **Sin infraestructura de pagos** (no Stripe, no webhooks, no checkout pages)
- **Flexible** (aceptas cualquier método de pago)
- **El meta-agente es tu interfaz** (todo se hace hablándole por Telegram)
- **Puedes automatizar después** (agregar Stripe cuando tengas 50+ tenants)
- **Menos código** (no necesitas API de webhooks en el MVP)

---

## Estructura del Proyecto

```
martes.app/
├── apps/
│   └── meta-agent/                 ← Agno meta-agente (ES TODO EL BACKEND)
│       ├── src/
│       │   ├── __init__.py
│       │   ├── main.py            ← AgentOS entry point (FastAPI + Telegram gateway)
│       │   ├── config.py          ← DB, modelos, config
│       │   ├── agent.py           ← Definición del meta-agente
│       │   └── tools/
│       │       ├── __init__.py
│       │       ├── docker_ops.py  ← create/stop/restart containers
│       │       ├── tenant_config.py ← write config/env/soul to volumes
│       │       ├── tenant_db.py   ← CRUD tenants en PostgreSQL
│       │       ├── health.py      ← poll health, detect issues
│       │       └── backup.py      ← tar.gz volumes, upload to R2
│       ├── Dockerfile
│       └── pyproject.toml
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
2. Schema SQL (tenants, configs, payments, health, errors)
3. Meta-agente Agno con tools:
   - `create_tenant()` — crea volumen + config + container
   - `stop_tenant()` — para container
   - `restart_tenant()` — reinicia container
   - `list_tenants()` — muestra todos los tenants y su estado
   - `register_payment()` — marca que un tenant pagó
   - `check_health()` — verifica estado de todos los containers
4. Templates de Hermes (config.yaml para cada tier)
5. Conectar meta-agente a Telegram (tú le hablas, él ejecuta)

### Sprint 2: Integraciones + Wiki

6. Tool para inyectar OAuth tokens (Google, Notion)
7. Tool para inyectar wiki content inicial
8. Tool para conectar Composio MCP
9. Health monitoring automático (cron cada 5 min)
10. Auto-restart en fallo

### Sprint 3: Backup + Producción

11. Backup automatizado (tar.gz → R2)
12. Tool para pausar/reactivar con backup
13. Deploy en VPS (Hetzner CX43)
14. DNS + Cloudflare + Cloudflare Access
15. Primer tenant real (beta)

### Sprint 4: Polish

16. Monitoring (Sentry + UptimeRobot)
17. Documentación para tenants (cómo usar su agente)
18. Onboarding guiado (el meta-agente te guía por Telegram)
