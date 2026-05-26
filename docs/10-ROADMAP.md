# Roadmap — martes.app

> **Estado a**: 4 junio 2026  
> **Sistema**: Producción — 1 tenant activo (t001), 2 archivados (t002, t003)  
> **Stack**: Hetzner CX43 · Coolify · Agno AgentOS 2.6.8 · SeaweedFS 4.28 · Hermes v2026.5.16 · Metabase v0.61.2.6  
> **PRs abiertos**: #83 (roadmap v7 docs — mergear)  
> **Regla**: todo cambio va por PR → merge → Coolify auto-deploy. Sin SSH directo.

---

## ✅ Completado — Plataforma base

### Ciclo de vida de tenants
- `create_tenant()`: .env (6 vars inc. home channel), config.yaml, SOUL.md, container, DB, trial 30d, BYOK
- `stop_tenant()`, `restart_tenant()`, `delete_tenant()`, `recreate_tenant_container()`
- `upgrade_tenant()` con rollback automático · `purge_archived_tenant()`
- `update_tenant_resources()`, `update_tenant_model()`, `update_tenant_soul()`
- `inject_credential()` — soporta `openrouter_api_key` con cleanup BYOK inmediato (PR #85)
- `inject_wiki_content()`, `register_payment()`

### Observabilidad
- Health checks cada 5 min + alertas Telegram
- `diagnose_container_error()` — clasificación automática
- `health_checks` + `error_logs` + `server_metrics` + `backup_log` → Metabase
- `find_stale_resources()`, `docker-cleanup` semanal
- Estado `"starting"` para containers recién levantados (falsos positivos eliminados, PR #82)

### Backups
- Diario 3AM a SeaweedFS, keep_last=7
- Backup log en `public.backup_log` → historial por tenant en Metabase (PR #87)
- Restore correcto (WAL, symlinks, permisos)

### Billing
- Trial 30d, alertas 7d/3d/día 0, auto-suspend
- `register_payment()`, BYOK platform key (TTL 2h, auth.json detection)

### Schedules (todos funcionando — confirmado en producción, PR #82)
| Schedule | Cron | Función |
|---|---|---|
| `daily-backup-all` | `0 3 * * *` | Backup todos los tenants → SeaweedFS + backup_log |
| `health-check-all` | `*/5 * * * *` | Health + alertas + escribe en health_checks y server_metrics |
| `billing-check` | `0 9 * * *` | Alertas vencimiento + auto-suspend |
| `expire-platform-keys` | `*/30 * * * *` | BYOK: blanquea platform keys expiradas |
| `docker-cleanup` | `0 4 * * 0` | Limpia imágenes Hermes huérfanas |
| `prune-old-data` | `0 2 * * 0` | Limpia traces/sessions/health_checks (H2) |

### Agentes del meta-agente
- **Diagnosticador** — solo lectura: health, logs, stats, DB
- **Operador** — escritura con HITL: ciclo de vida tenants
- **Billing** — solo lectura: revenue, vencimientos, historial de pagos (PR #84)

### Tests y CI
- 74 unit tests (tar filter, validación, BYOK, billing) — todos pasan (PR #86)
- Job `unit-tests` en CI paralelo al build check

### Metabase (configurado completamente)
- DB conectada (schema `public`)
- Dashboard "martes.app — Plataforma" como homepage
- **16 cards** en 8 secciones:
  - 4 KPIs numéricos (tenants activos, uptime, incidentes críticos, revenue mes)
  - Tenants con vencimiento · Vencen esta semana
  - Uptime 24h · Response time
  - Health timeline 6h
  - Incidentes sin resolver · Revenue mensual
  - Disco actual (%) · Disco histórico 7 días
  - Schedules — últimas ejecuciones · Último backup por tenant
  - Historial de backups completo

### Paradigma y seguridad
- Paradigma plataforma vs agente documentado → `docs/hermes-guia/00-PARADIGMA-PLATAFORMA.md`
- Factory defaults: sin cap_drop, pids_limit, tmpfs, security_opt. Solo `mem_limit=768m`
- `TelegramAllowlistMiddleware` — guardrail duro del meta-agente

---

## Operacional pendiente

| Item | Qué hacer | Prioridad |
|---|---|---|
| **C1** | Test backup→restore end-to-end en t001 | 🔴 Bloqueante para E1 |
| **D1** | Test `register_payment()` real con t001 | 🟡 |
| **Purge t002+t003** | "purga los registros archivados de t002 y t003" | 🟢 |

---

## Sprint H — Código pendiente

### H3 · `TenantCreateInput` — Pydantic BaseModel

Ahora que existen tests (H5), es seguro hacer este refactor.

**Archivo**: `apps/meta-agent/src/tools/write_ops.py`

```python
class TenantCreateInput(BaseModel):
    name: str = Field(..., description="Nombre del cliente. Ej: 'Acme Corp'")
    bot_token: str = Field(..., description="Token @BotFather. Formato: 123456:ABC... (35 chars)")
    telegram_user_id: str = Field(..., description="ID numérico. Obtener con @userinfobot")
    model: str = Field(default="openai/gpt-4o-mini",
        description="Modelo LLM. Opciones: openai/gpt-4o-mini, deepseek/deepseek-v4-flash, anthropic/claude-3.5-haiku")
    email: str = Field(default="", description="Email de contacto (opcional)")

def create_tenant(input: TenantCreateInput) -> str:
    # Los @field_validator reemplazan las validaciones inline actuales
```

Mover validaciones de bot_token (regex) y telegram_user_id (isdigit) a `@field_validator`.

---

## Sprint F — Producto y landing

### F1 · Landing page `martes.app`

El dominio raíz sirve nada. Bloqueante para E1 — el primer cliente buscará `martes.app`.

- **Repo**: `aikapenelope/martes-landing` (crear)
- **Framework**: Next.js static export o Astro
- **Deploy**: Vercel free tier → `martes.app CNAME cname.vercel-dns.com`
- **Contenido mínimo**: nombre, propuesta de valor, precio ($30/mes), CTA a Telegram

### F2 · Limpieza de docs históricos

13 documentos en inglés del proceso inicial (`docs/00` – `docs/09`, `docs/14`–`docs/16`) → mover a `docs/archive/` o eliminar.

---

## Sprint E — Producto

### E1 · Primer cliente real

**Bloqueantes**: C1 (backup→restore) + F1 (landing page)

Flujo cuando esté listo:
```
1. "crea tenant [nombre] token [bot] telegram_id [id]"
2. Cliente recibe su bot con capacidades completas de fábrica
3. billing-check corre diariamente — alerta a 7d y 3d del vencimiento
```

### E2 · upgrade_tenant() en producción

Cuando NousResearch publique nueva versión estable de Hermes.

---

## Sprint I — CRM (futuro, cuando PocketBase v1.0.0)

Arquitectura completa en `docs/hermes-guia/07` y `08`.  
Retomar cuando PocketBase ≥ v1.0.0 y ecosistema MCP estable (Q4 2026–Q1 2027).

---

## Descartado

- **Hermes dashboard** — expone API keys. Los clientes configuran desde Telegram.
- **CRM ahora** — PocketBase pre-v1.0.0. Sprint I futuro.
- **`install_skill_in_tenant()`** — obsoleto con factory defaults.
- **InsForge para CRM** — no multi-tenant nativo, ~500MB RAM/instancia.

---

## Capacidad del servidor

| Config | Tenants seguros |
|---|---|
| 768MB / 0.75 CPU por tenant | ~20 en CX43 |
| Para escalar | Upgrade a CX53 (32GB, €45/mes) |
