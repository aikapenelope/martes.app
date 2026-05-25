# Roadmap — martes.app

> **Estado a**: 4 junio 2026  
> **Sistema**: Producción — 1 tenant activo (t001), t002 archivado/pendiente purge  
> **Stack**: Hetzner CX43 · Coolify · Agno AgentOS 2.6.8 · SeaweedFS 4.28 · Hermes v2026.5.16 · Metabase v0.61.2.6  
> **PRs abiertos**: ninguno

---

## ✅ Completado — Plataforma base

### Ciclo de vida de tenants
- `create_tenant()`: .env (6 vars), config.yaml, SOUL.md, container, DB, trial 30d, platform key BYOK
- `stop_tenant()`, `restart_tenant()`, `delete_tenant()`, `recreate_tenant_container()`
- `upgrade_tenant()` con rollback automático
- `purge_archived_tenant()`
- `update_tenant_resources()` — RAM/CPU en caliente
- `update_tenant_model()`, `update_tenant_soul()`, `inject_credential()`, `inject_wiki_content()`

### Observabilidad
- Health checks cada 5 min + alertas Telegram
- `diagnose_container_error()` — clasificación automática
- `health_checks` + `error_logs` se pueblan → Metabase
- `find_stale_resources()`, `docker-cleanup` semanal
- `container_health()`: estado `"starting"` para containers < 60s — evita falsos positivos (PR #82)

### Backups
- Diario 3AM a SeaweedFS, keep_last=7
- Lifecycle rules SeaweedFS 30 días
- Restore correcto (WAL, symlinks, permisos)

### Billing
- Trial 30d, alertas 7d/3d/día 0, auto-suspend
- `register_payment()`, BYOK platform key (TTL 2h, auth.json detection)

### Schedules (PR #82 — ahora funcionan todos)
El bug del `@app.on_event("startup")` está corregido. Todos los schedules se registran automáticamente en cada deploy usando el patrón `lifespan=` de Agno (ref: docs.agno.com/agent-os/lifespan).

| Schedule | Cron | Función |
|---|---|---|
| `daily-backup-all` | `0 3 * * *` | Backup todos los tenants activos |
| `health-check-all` | `*/5 * * * *` | Health + alerta si unhealthy o disco >80% |
| `billing-check` | `0 9 * * *` | Alertas vencimiento + auto-suspend |
| `expire-platform-keys` | `*/30 * * * *` | BYOK: blanquea platform keys expiradas |
| `docker-cleanup` | `0 4 * * 0` | Limpia imágenes Hermes huérfanas |
| `prune-old-data` | `0 2 * * 0` | Limpia traces/sessions/health_checks (H2) |

### Pruning de tablas (H2 — PR #82)
- `POST /maintenance/prune-old-data` — endpoint nuevo
- Retenciones: `martes_traces` 30d · `martes_sessions` 90d · `health_checks` 90d
- Schedule domingos 2AM UTC (antes del backup de las 3AM)

### Seguridad y paradigma
- `TelegramAllowlistMiddleware` — guardrail duro del meta-agente
- `TELEGRAM_HOME_CHANNEL` en .env — sin mensaje "No home channel"
- Paradigma plataforma vs agente → `docs/hermes-guia/00-PARADIGMA-PLATAFORMA.md`
- **Factory defaults** (PR #76): eliminadas cap_drop, pids_limit, tmpfs, security_opt.
  Solo queda `mem_limit=768m`. Hermes tiene capacidades completas de fábrica.

### Infra
- Gitleaks CI, Metabase v0.61.2.6, Agno AgentOS 2.6.8
- SeaweedFS 4.28, PostgreSQL 18 + pgvector

---

## Operacional pendiente

| Item | Qué hacer | Prioridad |
|---|---|---|
| **C1** | Test backup→restore completo: backup t001 → stop → borrar volumen → restore → recreate → health → mensaje Telegram | 🔴 Antes de E1 |
| **C2** | Verificar que los 5 schedules nuevos quedaron registrados: `GET /schedules` debe devolver 6 items | 🔴 Inmediato — después del próximo deploy |
| **D1** | Test `register_payment()` real con t001 + verificar `paid_until` en DB | 🟡 |
| **Metabase** | Primer login → conectar `db:5432` solo schema `public` → dashboards de tenants + uptime | 🟡 |
| **Purge t002** | "purga el registro archivado de t002 de la base de datos" | 🟢 |

---

## Sprint H — Código pendiente

### H1 · `inject_credential` + `openrouter_api_key`

**Archivo**: `apps/meta-agent/src/tools/write_ops.py`

```python
# 1. Añadir openrouter_api_key a CredentialType y _CREDENTIAL_FILE_MAP:
CredentialType = Literal[
    "google_token", "notion_key", "airtable_key",
    "github_token", "linear_key",
    "openrouter_api_key",   # ← añadir
]
_CREDENTIAL_FILE_MAP["openrouter_api_key"] = ".env"

# 2. En inject_credential(), después de escribir la key:
if credential_type == "openrouter_api_key":
    marker_file = tenant_path / _PLATFORM_KEY_EXPIRES_FILE
    marker_file.unlink(missing_ok=True)   # cleanup inmediato, no esperar 30min
```

---

### H3 · `TenantCreateInput` — Pydantic BaseModel

**Archivo**: `apps/meta-agent/src/tools/write_ops.py`

```python
class TenantCreateInput(BaseModel):
    name: str = Field(..., description="Nombre del cliente. Ej: 'Acme Corp'")
    bot_token: str = Field(..., description="Token del bot de @BotFather. Formato: 123456:ABC...")
    telegram_user_id: str = Field(..., description="ID numérico. Obtener con @userinfobot")
    model: str = Field(default="openai/gpt-4o-mini",
        description="Modelo LLM. Opciones: openai/gpt-4o-mini, deepseek/deepseek-v4-flash, anthropic/claude-3.5-haiku")
    email: str = Field(default="", description="Email de contacto (opcional)")

def create_tenant(input: TenantCreateInput) -> str:
    # Validaciones inline se mueven al modelo con @field_validator
```

Mejora el schema del tool que recibe el LLM — descriptions, validaciones declarativas.

---

### H4 · Billing agent conversacional

**Archivo nuevo**: `apps/meta-agent/src/agents/billing.py`  
**Archivo modificado**: `apps/meta-agent/src/team.py`

Tercer agente del Team, solo lectura, ~60 líneas.

```
Admin: "¿quiénes vencen esta semana?"
Billing: "3 tenants vencen en los próximos 7 días: ..."

Admin: "¿cuánto revenue llevo este mes?"
Billing: "Junio 2026: $210 registrados (7 pagos)"
```

---

### H5 · Tests básicos

**Directorio nuevo**: `apps/meta-agent/tests/`

```
test_create_tenant_validation.py  — regex bot_token, isdigit telegram_user_id
test_billing_expiry.py            — billing_check: trial/grace/suspend
test_expire_platform_key.py       — BYOK: niveles 1 y 2 de detección
test_backup_restore.py            — tar filter: exclusión WAL, symlinks
```

Unit tests puros — sin Docker, sin PostgreSQL. Añadir al CI en `cd.yml`.

---

## Sprint F — Producto y landing

### F1 · Landing page `martes.app`

`martes.app` (dominio raíz) sirve nada actualmente.

- Repo separado: `aikapenelope/martes-landing`
- Framework: Next.js static export o Astro
- Deploy: Vercel (free tier, CDN global)
- DNS: `martes.app CNAME cname.vercel-dns.com` (no afecta `api.martes.app`)
- **Bloqueante para E1**: el primer cliente real va a buscar `martes.app`

Contenido mínimo: nombre, propuesta de valor, precio ($30/mes), CTA a Telegram del dueño.

---

### F2 · Limpieza de docs históricos

13 documentos en inglés del proceso inicial de diseño (docs/00–16) → mover a `docs/archive/` o eliminar. `docs/hermes-guia/` es la fuente de verdad.

---

## Sprint E — Producto

### E1 · Primer cliente real (beta)

**Bloqueantes**:
1. **C1** — test backup→restore (no deployar sin esto)
2. **F1** — landing page (credibilidad básica)
3. **Metabase** — configurado para monitorear

### E2 · upgrade_tenant() en producción

Cuando NousResearch publique la siguiente versión estable de Hermes.

---

## Sprint I — CRM (futuro, cuando PocketBase v1.0.0)

Arquitectura completa documentada en `docs/hermes-guia/07` y `08`.  
Retomar cuando PocketBase ≥ v1.0.0 y ecosistema MCP estable (estimado Q4 2026–Q1 2027).

---

## Descartado

**Hermes dashboard** — expone API keys. Los clientes configuran desde Telegram.

**CRM ahora** — ninguna solución ligera existe en 2026. Sprint I cuando PocketBase v1.0.0.

**`install_skill_in_tenant()`** — obsoleto. Con factory defaults el cliente instala desde Telegram.

**InsForge para CRM** — no multi-tenant nativo, ~500MB RAM/instancia.

---

## Capacidad del servidor

| Config | Tenants seguros en CX43 |
|---|---|
| 768MB / 0.75 CPU por tenant | ~20 tenants |
| **Práctica segura** | **20–25 tenants** |

Para escalar: upgrade a CX53 (32GB, €45/mes).
