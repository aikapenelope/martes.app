# Roadmap — martes.app

> **Estado a**: junio 2026 (post-Sprint 9)
> **Sistema**: Producción — 1 tenant activo (t001), 2 archivados (t002, t003)
> **Stack**: Hetzner CX43 (16 GB) · Coolify · Agno AgentOS 2.6.8 · SeaweedFS 4.28 · Hermes v2026.5.16 · Metabase v0.61.2.6
> **Tests**: 172 unit tests — todos pasan
> **PRs abiertos**: ninguno
> **Regla**: todo cambio va por PR → merge → Coolify auto-deploy. Sin SSH directo.

---

## Evaluación honesta: ¿Qué tan lista está la plataforma?

**90% lista para primer cliente real.**

El código de backend está completo, probado y sin bugs conocidos. Lo que falta no es
código nuevo — es validación operacional y una puerta de entrada al producto.

### Qué está completamente listo

- Ciclo de vida completo de tenants (crear, pausar, reactivar, eliminar, upgradear)
- Backups automáticos diarios + restore funcional en código
- Billing con trial, alertas, auto-suspend y pagos manuales
- BYOK: platform key TTL 2h con detección de key propia del cliente
- 6 schedules de mantenimiento corriendo en producción
- 3 agentes especializados con instrucciones completas y knowledge base correcta
- 172 tests unitarios, CI verde en cada PR
- Metabase con 16 cards de observabilidad
- Todos los gaps de la auditoría cerrados (Sprint 9, PRs #96–103)

### Qué falta para los 2 puntos restantes

| Bloqueante | Naturaleza | Esfuerzo |
|---|---|---|
| **C1** — Test backup→restore en producción | Operacional (30 min) | 🔴 Inmediato |
| **F1** — Landing page `martes.app` | Frontend (1 día) | 🔴 Inmediato |

Sin C1, si un cliente tiene un problema y necesitas restaurar sus datos, no sabes si
funciona. Sin F1, cualquier cliente que busque el dominio ve una página en blanco.

---

## ✅ Completado — Plataforma base (Sprints 1–8)

### Ciclo de vida de tenants

- `create_tenant()`: .env (6 vars inc. home channel), config.yaml, SOUL.md,
  container, DB, trial 30d, BYOK platform key
- `stop_tenant()`, `restart_tenant()`, `delete_tenant()`, `recreate_tenant_container()`
- `upgrade_tenant()` con backup previo y rollback automático
- `purge_archived_tenant()`
- `update_tenant_resources()` — hot-update de cgroups (persiste en DB desde PR #97)
- `update_tenant_model()`, `update_tenant_soul()`
- `inject_credential()` — soporta 9 tipos:
  `google_token`, `notion_key`, `airtable_key`, `github_token`, `linear_key`,
  `openrouter_api_key`, `telegram_bot_token`, `telegram_allowed_users`,
  `telegram_home_channel`
- `inject_wiki_content()`, `register_payment()`

### Observabilidad

- Health checks cada 5 min + alertas Telegram
- Alerta RAM cuando disponible < 20% (PR #99)
- `diagnose_container_error()` — clasificación automática de causa
- `get_tenant_config()` — modelo activo, plataformas, skills, cron jobs (PR #98)
- `get_tenant_env_keys()` — claves del .env sin valores (PR #98)
- `health_checks` + `error_logs` + `server_metrics` + `backup_log` → Metabase
- `find_stale_resources()`, `docker-cleanup` semanal
- Estado `"starting"` para containers recién levantados

### Backups

- Diario 3AM a SeaweedFS, keep\_last=7, lifecycle rule 30 días
- Backup log → historial por tenant en Metabase
- Restore correcto: WAL sidecars, symlinks absolutos, permisos 600, chown 1000:1000

### Billing

- Trial 30d, alertas 7d/3d/día 0, auto-suspend
- `register_payment()` con cálculo de extensión desde paid\_until
- BYOK: platform key TTL 2h + detección por auth.json + cleanup inmediato en inject

### Schedules (todos en producción)

| Schedule | Cron | Función |
|---|---|---|
| `daily-backup-all` | `0 3 * * *` | Backup todos los tenants activos |
| `health-check-all` | `*/5 * * * *` | Health + alertas + server\_metrics + alerta RAM |
| `billing-check` | `0 9 * * *` | Alertas vencimiento + auto-suspend |
| `expire-platform-keys` | `*/30 * * * *` | BYOK: blanquea platform keys expiradas |
| `docker-cleanup` | `0 4 * * 0` | Limpia imágenes Hermes huérfanas |
| `prune-old-data` | `0 2 * * 0` | Purge traces/sessions/health\_checks |

### Agentes del meta-agente

- **Diagnosticador** — solo lectura: health, logs, stats, DB, config de volumen
  Diagnostica 'bot no responde', loops de herramienta, estado de credenciales
- **Operador** — escritura HITL: ciclo de vida completo, 15 tool calls, 9 tipos de credencial
- **Billing** — solo lectura: revenue, vencimientos, historial de pagos

### Tests y CI

- **172 unit tests** — todos pasan en < 2s
- 12 archivos de tests: backup/restore, security, billing, BYOK, validación,
  healthcheck, inject\_credential, update\_resources, herramientas diagnóstico
- Job `unit-tests` en CI paralelo al build check (gitleaks → build + tests)

### Metabase

- 16 cards en 8 secciones (KPIs, uptime, incidentes, revenue, disco, RAM, backups)
- Solo accesible por Tailscale — nunca expuesto a internet

### Paradigma y seguridad

- Paradigma plataforma vs agente documentado y operativo
- Factory defaults: sin cap\_drop, sin pids\_limit, sin tmpfs. Solo `mem_limit=768m`
- `TelegramAllowlistMiddleware` — guardrail duro del meta-agente
- Gitleaks en CI — detecta secrets en commits antes del deploy

---

## ✅ Completado — Sprint 9 (PRs #89–103, junio 2026)

### Correcciones de bugs (todos cerrados)

- **gateway.lock** añadido a `_BACKUP_EXCLUDE_NAMES` (PR #89)
- **`upgrade_tenant()`**: columna incorrecta `template` → `extra_config` JSONB (PR #90)
- **`inject_wiki_content()`**: `"concepts" / pn` TypeError → `Path("concepts") / pn` (PR #90)
- **`check_all_health()`**: estado "starting" añadido (PR #90)
- **`_run_container()`**: caps/pids/tmpfs eliminados — consistente con `create_tenant()` (PR #90)
- **`exit_code or 1`**: health check NUNCA podía reportar "healthy" — crítico (PR #94)
- **`truly_unhealthy`**: "starting" excluido de alertas Telegram (PR #94)
- **RAM de CX43**: 16 GB, no 32 GB, en tests y docs (PR #103)

### Gaps de operación cerrados

- **`inject_credential()`**: `telegram_bot_token`, `telegram_allowed_users`,
  `telegram_home_channel` — admin puede resolver problemas de acceso sin SSH (PR #96)
- **`update_tenant_resources()`**: persiste en `instance_configs` DB — los ajustes
  no se pierden al recrear el container (PR #97)
- **`get_tenant_config()`** + **`get_tenant_env_keys()`**: Diagnosticador puede
  inspeccionar el volumen sin SSH (PR #98)
- **Alerta RAM < 20%**: detecta servidor al límite antes de OOM kills (PR #99)

### Agentes y knowledge

- Instrucciones de Diagnosticador, Operador y Team mejoradas (PR #100)
- `hermes_reference.md`: factory defaults, exit 75, TELEGRAM\_HOME\_CHANNEL,
  CLI path, prioridad de credenciales (PR #101)
- `procedures.md`: error `inject_credential(telegram_allowed_users)` corregido,
  upgrade procedure actualizado (PR #101)
- `SOUL.md` template: voz propia para pymes latinoamericanas (PR #102)
- Auditoría completa documentada en `docs/11-AUDITORIA-PLATAFORMA-GAPS.md` (PR #95)

---

## 🔴 Bloqueantes para E1 — primer cliente real

### C1 · Test backup → restore en producción (30 min)

El flujo está implementado y el código es correcto, pero **nunca se ha ejecutado
de punta a punta en el servidor real con t001**.

```
# Desde el meta-agente en Telegram:
1. "backup t001"                           → backup_tenant("t001")
2. "para t001"                             → stop_tenant("t001")
3. "restaura t001 desde [backup_filename]" → restore_tenant_from_backup(...)
4. "reinicia t001"                         → restart_tenant("t001")
5. "health t001"                           → container_health("t001") → healthy?
6. Verificar con el cliente que el bot funciona
```

Sin este test, no sabes si la recuperación de datos funciona en producción.
Es el riesgo operativo más grande del sistema.

### F1 · Landing page `martes.app`

El dominio raíz sirve nada. Si un cliente potencial busca el dominio, no hay producto.

- **Repo**: `aikapenelope/martes-landing` (crear)
- **Framework**: Next.js static export o Astro (1 página)
- **Deploy**: Vercel free tier → `martes.app CNAME cname.vercel-dns.com`
- **Contenido mínimo**: nombre + propuesta de valor + precio ($30/mes) + botón
  "Habla con el admin" que abra Telegram con el admin

---

## 🟡 Pendiente — no bloqueante

### D1 · Test `register_payment()` real con t001

Ejecutar un pago real con t001 para confirmar que el ciclo completo funciona:
`register_payment()` → extensión de `paid_until` → billing-check no alerta → confirmado.

### H3 · `TenantCreateInput` Pydantic BaseModel

Mover las validaciones inline de `create_tenant()` a un `BaseModel` con
`@field_validator`. Ahora que existen tests (172), es seguro hacer este refactor.
No bloquea nada — es deuda técnica menor.

### Purge t002 + t003

Limpiar los registros archivados:
```
purge_archived_tenant("t002")
purge_archived_tenant("t003")
```

### F2 · Limpieza de docs históricos

13 documentos en inglés del proceso inicial (`docs/00` – `docs/09`, `docs/14`–`docs/16`)
→ mover a `docs/archive/` o eliminar. No afecta operación.

---

## 🔵 Futuro — cuando se necesite

### E2 · upgrade_tenant() en producción

El código ya funciona (bug del PR #90 corregido). Ejecutar cuando NousResearch
publique una versión estable nueva de Hermes.
**Probar siempre en un tenant de test antes de escalar a todos los clientes.**

### Escalar a >20 tenants (CX53)

CX43 tiene 16 GB RAM. Con 768 MB por tenant: ~18-20 tenants seguros.
El health check ahora alerta RAM < 20% — hay señal antes de que sea un problema.

| Config | RAM | Tenants seguros |
|---|---|---|
| CX43 actual | 16 GB | ~18-20 |
| CX53 (upgrade) | 32 GB | ~35-40 |

Criterio de migración: cuando el health check alerte RAM < 20% de forma continua.

### Sprint I — CRM (cuando PocketBase ≥ v1.0.0)

Arquitectura documentada en `docs/hermes-guia/07` y `08`.
Retomar en Q4 2026–Q1 2027 cuando PocketBase alcance v1.0.0 y MCP sea estable.

---

## Descartado (definitivo)

- **Hermes dashboard** — expone API keys. Clientes configuran desde Telegram.
- **`install_skill_in_tenant()`** — obsoleto. Factory defaults permiten que el
  cliente instale skills con `/skills install` desde Telegram directamente.
- **InsForge para CRM** — no multi-tenant nativo, ~500MB RAM/instancia.
- **CRM ahora** — PocketBase pre-v1.0.0. Sprint I futuro.
- **Stripe** — mercado venezolano opera con transferencia/pago móvil.

---

## Flujo completo cuando todo esté listo

```
Cliente encuentra martes.app          → F1 (landing page)
Escribe al admin por Telegram
Admin crea el tenant (30s)            → create_tenant() ya funciona
Cliente recibe su bot con todo listo  → SOUL.md, config.yaml, plataforma key
Cliente configura su API key propia   → /auth en Telegram (BYOK)
Admin registra el pago                → register_payment() ya funciona
Sistema monitorea solo                → 6 schedules corriendo
```

Los únicos pasos manuales son: crear el tenant y registrar el pago.
Todo lo demás es automático.
