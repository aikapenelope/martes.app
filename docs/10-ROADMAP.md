# Roadmap — martes.app

> **Estado a**: 4 junio 2026  
> **Sistema**: Producción — 1 tenant activo (t001), t002 archivado/pendiente purge  
> **Stack**: Hetzner CX43 · Coolify · Agno AgentOS 2.6.8 · SeaweedFS 4.28 · Hermes v2026.5.16 · Metabase v0.61.2.6  
> **PRs abiertos**: #76 (Hermes factory defaults), #78 (Sprint G cleanup)

---

## ✅ Completado — Plataforma base

### Ciclo de vida de tenants
- `create_tenant()` completo: .env (6 vars), config.yaml, SOUL.md, container, DB, trial, platform key BYOK
- `stop_tenant()`, `restart_tenant()`, `delete_tenant()`, `recreate_tenant_container()`
- `upgrade_tenant()` con rollback automático
- `purge_archived_tenant()`
- `update_tenant_resources()` — escalar RAM/CPU en caliente
- `update_tenant_model()`, `update_tenant_soul()`, `inject_credential()`, `inject_wiki_content()`

### Observabilidad y operaciones
- Health checks automáticos cada 5 min con alertas Telegram
- `diagnose_container_error()` — clasificación automática de fallos
- `health_checks` y `error_logs` se pueblan desde el código → Metabase
- `find_stale_resources()`, `docker-cleanup` semanal

### Backups
- Backup diario 3AM a SeaweedFS, keep_last=7
- Lifecycle rules SeaweedFS (expiración 30 días)
- Restore con manejo correcto de WAL y symlinks

### Billing
- Trial 30 días desde create_tenant()
- Alertas escalonadas 7d/3d/día 0
- Auto-suspend configurable
- `register_payment()`, `expire_platform_key()` BYOK

### Seguridad y paradigma
- `TelegramAllowlistMiddleware` — guardrail duro para el meta-agente
- `TELEGRAM_HOME_CHANNEL` en .env — elimina el mensaje "No home channel"
- Paradigma plataforma vs agente documentado — Hermes gestiona su funcionamiento
- **PR #76**: Hermes factory defaults — eliminadas todas las restricciones de container.  
  Solo queda `mem_limit=768m`. Sin cap_drop, sin pids_limit, sin tmpfs, sin security_opt.  
  Hermes tiene capacidades completas: `hermes skills install`, `hermes update`,  
  browser, subagentes — todo desde la conversación del cliente, sin intervención del admin.

### Infra
- Gitleaks CI, Metabase v0.61.2.6, Agno AgentOS 2.6.8

---

## Operacional pendiente

| Item | Qué hacer | Prioridad |
|---|---|---|
| **C1** | Test backup→restore end-to-end en t001 | 🔴 Antes de E1 |
| **C2** | Verificar schedule 3AM: `GET /schedules/{id}/runs` | 🟡 |
| **D1** | Test `register_payment()` real con t001 | 🟡 |
| **Metabase setup** | Login → conectar DB (schema `public` only) → dashboards | 🟡 |
| **Purge t002** | "purga el registro archivado de t002 de la base de datos" | 🟢 |

---

## Pendiente de código (Sprint H)

### Alta prioridad

**`inject_credential` con `openrouter_api_key`** — borrar `.platform_key_expires` inmediatamente:
```python
# En inject_credential(), si credential_type == "openrouter_api_key":
marker_file = tenant_path / _PLATFORM_KEY_EXPIRES_FILE
marker_file.unlink(missing_ok=True)
```

**Pruning de tablas** — schedule semanal para evitar crecimiento indefinido:
```sql
DELETE FROM martes_traces   WHERE created_at < NOW() - INTERVAL '30 days';
DELETE FROM martes_sessions WHERE updated_at < NOW() - INTERVAL '90 days';
DELETE FROM health_checks   WHERE checked_at < NOW() - INTERVAL '90 days';
```

### Media prioridad

**Billing agent conversacional** — tercer agente del Team, solo lectura, ~50 líneas.  
Responde desde Telegram: *"¿quiénes vencen esta semana?"*, *"¿cuánto revenue este mes?"*

---

## Sprint E — Producto

### E1 · Primer cliente real (beta)

**Bloqueante**: completar C1 (backup→restore end-to-end).

Flujo de onboarding:
```
1. "crea tenant [nombre] token [bot_token] telegram_id [id]"
   → hermes-{code} arrancado con capacidades completas de fábrica
   → paid_until = hoy + 30 días (trial)
   → TELEGRAM_HOME_CHANNEL configurado → sin mensaje "No home channel"

2. Cliente habla con su bot por Telegram
   → puede usar /help, /model, /skills, /auth, etc. — control total

3. El cliente puede instalar skills directamente:
   "instala la skill de airtable" → Hermes lo hace solo, sin intervención del admin

4. Cliente configura su propia API key → platform key expira en 2h automáticamente

5. billing-check corre diariamente
```

### E2 · upgrade_tenant() en producción

Cuando NousResearch publique la siguiente versión estable de Hermes.

---

## Descartado

**Hermes dashboard** — expone API keys. Los clientes configuran desde Telegram.

**CRM** — ninguna solución ligera tipo "Memos para CRM" existe en el ecosistema 2026.
Investigación completa en `docs/hermes-guia/07` y `08` (referencia para Sprint I).
Se retoma como **Sprint I** cuando PocketBase alcance v1.0.0 (estimado Q4 2026–Q1 2027).

**`install_skill_in_tenant()`** — obsoleto. Con factory defaults (PR #76), el cliente
instala skills directamente desde Telegram: `hermes skills install X` + `/restart`.

## Capacidad del servidor

| Config | Tenants seguros en CX43 |
|---|---|
| 768MB / 0.75 CPU por tenant | ~20 |
| Para escalar | Upgrade a CX53 (32GB, €45/mes) |
