# CHANGELOG — martes.app

## [Sprint 1] — May 20-21, 2026

### Infraestructura (Hetzner + Pulumi)

- **Servidor**: Hetzner CX43 desplegado con Pulumi (8 vCPU, 16GB RAM, 160GB NVMe, Helsinki)
  - IP: `204.168.169.254`
  - Ubuntu 24.04, Docker 29.x, fail2ban, ufw (22/80/443)
  - Destruido stack anterior `qyne-infra` (Dokploy + Coolify, obsoleto)
  - Repo clonado en `/opt/martes`, imagen Hermes pre-descargada

- **Volúmenes persistentes** en `/var/lib/martes/`:
  - `pg-data/` — PostgreSQL (64MB, persiste schemas y datos)
  - `meta-agent/` — LanceDB vectors + wiki del meta-agente
  - `tenants/` — Volúmenes de containers Hermes (vacío, sin tenants aún)
  - `backups/` — Directorio para backups

- **Tailscale** instalado y conectado a la red `aikapenelope-org`
  - IP Tailscale del servidor: `100.104.89.128`
  - AgentOS API accesible en `100.104.89.128:8000`

### Servicios Docker corriendo

| Container | Imagen | Estado | Puerto |
|-----------|--------|--------|--------|
| `martes-db` | agnohq/pgvector:18 | healthy | 5432 (interno) |
| `martes-traefik` | traefik:v2.11 | healthy | 80, 443 |
| `martes-portainer` | portainer/portainer-ce | running | deploy.martes.app |
| `martes-meta` | infra-meta-agent (build) | healthy | 7777 (interno) |
| `martes-deploy-hook` | infra-deploy-hook (build) | running | hook.martes.app |

**Nota**: Portainer solo sirve como visor. No tiene Stacks configurados.
Todo el stack se gestiona via `docker compose` directamente.

### DNS (Cloudflare — DNS Only, sin proxy)

| Record | Tipo | Destino |
|--------|------|---------|
| `@` | A | 204.168.169.254 |
| `www` | A | 204.168.169.254 |
| `*` | A | 204.168.169.254 |
| `deploy` | A | 204.168.169.254 |
| `hook` | A | 204.168.169.254 |
| `api` | A | 204.168.169.254 |

### SSL (Let's Encrypt via Traefik)

- `deploy.martes.app` → Portainer UI ✓
- `hook.martes.app` → Deploy webhook ✓
- Wildcards de tenants (`t001.martes.app`, etc.) — auto-generados cuando se creen

### Auto-deploy (GitHub Actions → hook.martes.app)

**Flujo**:
```
Push a main → GitHub Actions → POST https://hook.martes.app/deploy
    ↓ HMAC-SHA256 verification
    ↓ git pull origin main (HTTPS, repo público)
    ↓ docker compose up -d --build db meta-agent traefik portainer
    ↓ ~2-3 minutos
```

- Secret en GitHub: `DEPLOY_SECRET` (en repository secrets)
- Secret en servidor: `/opt/martes/infra/.env → DEPLOY_SECRET`
- Deploy-hook NO se reinicia a sí mismo (evita self-kill)
- Logs en: `/var/log/martes-deploy.log`

### Meta-agente Agno (Team + Knowledge)

**Arquitectura** (patrones Scout + Coda):
- `TeamMode.coordinate` — Diagnosticador + Operador + Skill Builder
- `DatabaseContextProvider` — SQL directo a tenants DB
- `WikiContextProvider` — Wiki persistente en `/var/lib/martes/meta-agent/wiki/`
- `LearningMachine` — entity memory, decision log, session context
- `Knowledge RAG` — LanceDB + OpenAI embeddings (3 docs indexados)
- `CompressionManager` — comprime outputs largos
- `@approval` decorator — Human in the Loop en TODA escritura

**Agentes**:
- `Diagnosticador` — read-only, 7 tools + DockerTools + ContextProviders
- `Operador` — write con approval, 6 tools + DockerTools
- `Skill Builder` — crea/gestiona skills para meta-agente y tenants

**8 Skills lazy-loaded**:
- `tenant-management`, `tenant-onboarding`, `hermes-config`
- `hermes-troubleshooting`, `backup-restore`, `network-security`
- `monitoring-alerts`, `integrations`

**Knowledge base** (3 docs en LanceDB):
- `hermes_reference.md` — imagen Docker, volumen, env vars, health
- `procedures.md` — flujos operativos paso a paso
- `config_reference.md` — referencia completa del config.yaml de Hermes

### Templates Hermes (3 tiers — producción)

| Setting | Básico ($30) | Equipo ($100) | Pro ($200) |
|---------|-------------|---------------|------------|
| Modelo | deepseek-chat | deepseek-chat | claude-3.5-haiku |
| Toolsets | 6 (sin terminal) | 8 (+vision) | completo sin terminal |
| restart_drain_timeout | 30s | 60s | 120s |
| busy_input_mode | queue | queue | steer |
| compression threshold | 0.30 | 0.40 | 0.50 |
| hard_stop | SI (3) | SI (4) | SI (5) |
| lazy_installs | false | false | true |

### Docker hardening (containers de tenants)

- `cap_drop: ALL` + `cap_add: CHOWN, SETUID, SETGID, DAC_OVERRIDE, FOWNER, NET_RAW`
- `security_opt: no-new-privileges`
- `pids_limit: 256`
- `tmpfs /tmp: 100MB`
- `log_config: max-size 50MB, 3 files`
- `dns: 1.1.1.1, 8.8.8.8`
- Permisos volumen: `chown 1000:1000` (UID de Hermes)

### Documentación creada (16 docs)

| Doc | Contenido |
|-----|-----------|
| 00-08 | Arquitectura, decisiones, investigación (pre-existentes) |
| 09 | Plan Sprint 2+ |
| 10 | Guía Knowledge y Skills |
| 11 | Deployment Guide Hermes v0.14.0 |
| 12 | Auditoría infra + spec Dashboard |
| 13 | Guía optimización Hermes (toolsets, costs) |
| 14 | Restart/Update guide (exit 75, drain) |
| 15 | Por qué los tenants no se auto-actualizan |
| 16 | Plan deploy via dominio |

---

## Estado actual — Grado de producción

### ✅ Listo para producción
- Servidor corriendo y estable (24h+)
- SSL automático en todos los subdominios
- Auto-deploy funcionando (push to main)
- Meta-agente corriendo y healthy
- PostgreSQL con datos persistentes
- Hardening de seguridad aplicado
- Documentación completa

### ⏳ Falta para primer cliente
1. **Token de Telegram** del meta-agente (`PENDIENTE` en .env)
2. **Primer tenant de prueba** — validar flujo end-to-end
3. **Scheduler jobs** — health check periódico (scheduler activo, sin jobs)

### 🔜 Sprint 2 (siguiente)
- `upgrade_tenant()` tool — cambiar imagen Hermes sin recrear datos
- Restart graceful via SIGUSR1 (en vez de SIGTERM)
- Backup automático a R2
- Health monitoring con alertas a Telegram
- Wiki templates por industria (SOUL.md personalizado)

---

## Pendientes técnicos conocidos

| Issue | Impacto | Fix |
|-------|---------|-----|
| Portainer sin Stacks configurados | Bajo — solo visor | Crear Stack cuando sea necesario |
| 2 volúmenes duplicados de Traefik/Portainer | Bajo — espacio | `docker volume prune` cuando conveniente |
| deploy-hook no se auto-actualiza | Bajo — manual | Cron o script separado para actualizarlo |
| Telegram token = PENDIENTE | **Blocker para usar** | Configurar con token real |
