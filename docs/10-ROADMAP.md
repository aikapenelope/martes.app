# Roadmap — martes.app

> **Estado a**: 5 junio 2026  
> **Sistema**: Producción — 1 tenant activo (t001), 2 archivados (t002, t003 — purge pendiente)  
> **Stack**: Hetzner CX43 · Coolify · Agno AgentOS 2.6.8 · SeaweedFS 4.28 · Hermes v2026.5.16 · Metabase v0.61.2.6  
> **PRs abiertos**: ninguno  
> **Regla**: todo cambio por PR → merge → Coolify auto-deploy. Sin SSH directo al VPS.

---

## ✅ Completado — Plataforma base

### Ciclo de vida de tenants
- `create_tenant()`: .env (6 vars exactas), config.yaml, SOUL.md, container, DB, trial 30d, BYOK
- `stop_tenant()`, `restart_tenant()`, `delete_tenant()`, `recreate_tenant_container()`
- `upgrade_tenant()` — rollback automático, versión guardada en `extra_config` JSONB (PR #90)
- `purge_archived_tenant()` — hard delete en DB con CASCADE
- `update_tenant_resources()` · `update_tenant_model()` · `update_tenant_soul()`
- `inject_credential()` — soporta `openrouter_api_key` con cleanup BYOK inmediato (PR #85)
- `inject_wiki_content()` — custom_pages funciona correctamente (PR #90)

### Observabilidad y operaciones
- Health checks cada 5 min + alertas Telegram
- Estado `"starting"` en `container_health()` y `check_all_health()` — sin falsos positivos (PR #82, #90)
- `diagnose_container_error()` — clasificación automática de fallos
- `health_checks` · `error_logs` · `server_metrics` · `backup_log` → Metabase
- `find_stale_resources()` · `docker-cleanup` semanal

### Backups
- Diario 3AM a SeaweedFS, keep_last=7
- Registro en `backup_log` → historial por tenant (PR #87)
- Restore correcto (WAL, symlinks, permisos)

### Billing
- Trial 30d · alertas 7d/3d/día 0 · auto-suspend
- `register_payment()` · BYOK platform key (TTL 2h, auth.json detection)
- **Billing agent** — tercer agente del Team, solo lectura (PR #84)
  - `get_billing_summary()`, `get_expiring_tenants()`, `get_revenue_by_period()`, `get_tenant_payment_history()`

### Schedules (6, todos funcionando — confirmado en producción)
| Schedule | Cron | Función |
|---|---|---|
| `daily-backup-all` | `0 3 * * *` | Backup → SeaweedFS + `backup_log` |
| `health-check-all` | `*/5 * * * *` | Health + alertas + `health_checks` + `server_metrics` |
| `billing-check` | `0 9 * * *` | Alertas vencimiento + auto-suspend |
| `expire-platform-keys` | `*/30 * * * *` | BYOK: blanquea platform keys expiradas |
| `docker-cleanup` | `0 4 * * 0` | Limpia imágenes Hermes huérfanas |
| `prune-old-data` | `0 2 * * 0` | Limpia traces/sessions/health_checks |

### Tests y CI (104 tests, todos pasan)
- `test_backup_restore.py` · `test_backup_security.py` — tar filter + path traversal + chmod 600
- `test_billing_logic.py` · `test_billing_edge_cases.py` — cálculos de fechas, NULL, auto-suspend
- `test_byok_logic.py` · `test_inject_credential.py` — BYOK niveles 1/2, cleanup marker
- `test_validation.py` — regex bot_token, telegram_user_id
- Job `unit-tests` en CI en paralelo con el build check

### Metabase (configurado)
- DB conectada (schema `public`)
- Dashboard "martes.app — Plataforma" como homepage con 16 cards
- 4 KPIs · tenants/vencimientos · uptime · response time · health timeline · incidentes · revenue · disco · schedules · backups

### Paradigma y restricciones del container
- **Solo 6 vars en `.env`**: OPENROUTER_API_KEY · OPENROUTER_BASE_URL · TELEGRAM_BOT_TOKEN · TELEGRAM_ALLOWED_USERS · TELEGRAM_HOME_CHANNEL · TELEGRAM_HOME_CHANNEL_NAME
- **Única restricción**: `mem_limit=768m` — aplicada uniformemente en `create_tenant()`, `upgrade_tenant()`, `recreate_tenant_container()`
- Sin cap_drop · sin pids_limit · sin tmpfs · sin security_opt
- Hermes tiene capacidades completas: `/skills install`, `hermes update`, `agent-browser install`, subagentes

---

## Operacional pendiente

| Item | Qué hacer | Prioridad |
|---|---|---|
| **C1** | Test backup→restore end-to-end en t001 | 🔴 Bloqueante para E1 |
| **D1** | Test `register_payment()` real con t001 | 🟡 |
| **Purge t002+t003** | "purga el registro archivado de t002" · "purga el registro archivado de t003" | 🟢 Un comando cada uno |

---

## Sprint H — Código pendiente

### H3 · `TenantCreateInput` — Pydantic BaseModel

**Ahora seguro** — existen 104 tests que detectarán regresiones.

```python
class TenantCreateInput(BaseModel):
    name: str = Field(..., description="Nombre del cliente. Ej: 'Acme Corp'")
    bot_token: str = Field(..., description="Token @BotFather. 123456:ABC... (35 chars)")
    telegram_user_id: str = Field(..., description="ID numérico. Obtener con @userinfobot")
    model: str = Field(default="openai/gpt-4o-mini", description="Modelo LLM inicial")
    email: str = Field(default="", description="Email de contacto (opcional)")
    # Los @field_validator reemplazan las validaciones inline actuales
```

---

## Sprint F — Producto y landing

### F1 · Landing page `martes.app`

`martes.app` (dominio raíz) sirve nada. **Bloqueante para E1.**

- Repo: `aikapenelope/martes-landing`
- Framework: Next.js static export o Astro
- Deploy: Vercel → `martes.app CNAME cname.vercel-dns.com`
- Contenido mínimo: propuesta de valor, $30/mes, CTA a Telegram del admin

### F2 · Limpieza de docs históricos

13 docs en inglés del proceso inicial (`docs/00`–`docs/09`, `docs/14`–`docs/16`) → `docs/archive/` o eliminar.

---

## Sprint E — Producto

### E1 · Primer cliente real

**Bloqueantes**: C1 (backup→restore) + F1 (landing page)

```
1. "crea tenant [nombre] token [bot] telegram_id [id]"
2. Cliente recibe bot con capacidades completas de fábrica
3. billing-check corre diariamente
```

### E2 · upgrade_tenant() en producción

Cuando NousResearch publique nueva versión estable de Hermes.
La versión nueva queda registrada en `extra_config.hermes_image` (corregido en PR #90).

---

## Sprint I — CRM (futuro, cuando PocketBase v1.0.0)

Arquitectura completa documentada en `docs/hermes-guia/07` y `08`.
Retomar cuando PocketBase ≥ v1.0.0 y ecosistema MCP estable (Q4 2026–Q1 2027).

---

## Descartado

- **Hermes dashboard** — expone API keys. Los clientes configuran desde Telegram.
- **CRM ahora** — PocketBase pre-v1.0.0. Sprint I futuro.
- **`install_skill_in_tenant()`** — obsoleto con factory defaults.
- **InsForge para CRM** — no multi-tenant nativo, ~500MB RAM/instancia.
- **PR #83** — roadmap v7, superseded por PR #88 y #90. Cerrado.

---

## Capacidad del servidor

| Config | Tenants seguros |
|---|---|
| 768MB / 0.75 CPU por tenant | ~20 en CX43 |
| Para escalar | Upgrade a CX53 (32GB, €45/mes) |
