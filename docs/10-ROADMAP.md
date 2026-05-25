# Roadmap — martes.app

> **Estado a**: 4 junio 2026  
> **Sistema**: Producción — 1 tenant activo (t001), t002 archivado/pendiente purge  
> **Stack**: Hetzner CX43 · Coolify · Agno AgentOS 2.6.8 · SeaweedFS 4.28 · Hermes v2026.5.16 · Metabase v0.61.2.6  
> **PRs abiertos**: #76 (Hermes factory defaults)

---

## ✅ Completado

### Sprints A–F + Paradigma (PRs #57–76)

Ver `CHANGELOG.md` para el detalle completo.

**Resumen:**
- Robustez: Pydantic, name→code, EntityMemory
- Monitoreo: health-check, billing-check, alertas Telegram
- Producción: get_server_capacity, diagnose_container_error, upgrade_tenant
- Backups: lifecycle SeaweedFS, healthcheck fix, restore fix
- Observabilidad: health_checks y error_logs se pueblan desde el código
- Billing SaaS: trial 30d, alertas escalonadas, auto-suspend
- Gaps operativos: gitleaks CI, docker-cleanup, stale resources
- Metabase v0.61.2.6 en compose (solo Tailscale)
- Platform key BYOK (TTL 2h, auth.json detection multi-proveedor)
- **Paradigma plataforma vs agente** — documentado en `docs/hermes-guia/00-PARADIGMA-PLATAFORMA.md`
- **Home channel** — `TELEGRAM_HOME_CHANNEL` en `.env` desde create_tenant()
- **Hermes factory defaults** — eliminadas todas las restricciones de container (cap_drop, pids_limit, tmpfs, security_opt). Solo queda `mem_limit=768m`

---

## Operacional pendiente

| Item | Qué hacer | Prioridad |
|---|---|---|
| **C1** | Test backup→restore end-to-end en t001 | 🔴 Antes de E1 |
| **C2** | Verificar schedule 3AM: `GET /schedules/{id}/runs` | 🟡 |
| **D1** | Test `register_payment()` real con t001 | 🟡 |
| **Metabase setup** | Login → conectar DB (schema `public` only) → dashboards | 🟡 |
| **Purge t002** | "purga el registro archivado de t002 de la base de datos" | 🟢 Cosmético |

---

## Sprint G — `install_skill_in_tenant()`

> **Plan**: `docs/SPRINT-G-PLAN.md`

**Un solo item**: el meta-agente puede instalar skills en los tenants de Hermes.

El cliente no puede instalar skills directamente — `hermes skills install X` requiere
detener y reiniciar el gateway. El meta-agente sí puede: copia los archivos al volumen
y hace el restart.

```
Admin → meta-agente: "instala la skill de airtable en t001"
Operador ejecuta: install_skill_in_tenant("t001", "airtable")
→ descarga SKILL.md desde repo oficial de Hermes (GitHub)
→ copia a /var/lib/martes/tenants/t001/skills/airtable/
→ reinicia hermes-t001 (exit 75 → Docker lo levanta en segundos)
→ verifica health OK
```

**Archivos**: `apps/meta-agent/src/tools/write_ops.py` + `agents/operador.py`

---

## Sprint H — Código pendiente de calidad

### Alta prioridad

**`inject_credential` con `openrouter_api_key`** — borrar `.platform_key_expires` inmediatamente al inyectar la key propia del cliente:
```python
marker_file = tenant_path / _PLATFORM_KEY_EXPIRES_FILE
marker_file.unlink(missing_ok=True)
```

**`martes_traces` y `martes_sessions` pruning** — schedule semanal:
```sql
DELETE FROM martes_traces WHERE created_at < NOW() - INTERVAL '30 days';
DELETE FROM martes_sessions WHERE updated_at < NOW() - INTERVAL '90 days';
```

### Media prioridad

**`health_checks` pruning** — schedule semanal, datos > 90 días.

**Billing agent conversacional** — tercer agente del Team para consultas de billing desde Telegram. Solo lectura. ~50 líneas.

---

## Sprint E — Producto

### E1 · Primer cliente real (beta)

**Bloqueante**: C1 (backup→restore) y Sprint G (`install_skill_in_tenant`).

Flujo de onboarding:
```
1. "crea tenant [nombre] token [bot_token] telegram_id [id]"
   → hermes-{code} arrancado con todas las capacidades de fábrica
   → paid_until = hoy + 30 días (trial)

2. Cliente abre Telegram, habla con su bot
   → Hermes se presenta, explica /help

3. Admin puede instalar skills si el cliente las necesita:
   "instala la skill de airtable en t001"

4. Cliente configura su propia OpenRouter key
   → platform key expira automáticamente en 2h

5. billing-check corre diariamente
```

### E2 · upgrade_tenant() en producción

Cuando NousResearch publique la siguiente versión estable de Hermes.

---

## Descartado

**Hermes dashboard por tenant** — expone API keys. Los clientes gestionan desde Telegram.

**Kanban/workers para PyMEs** — no necesario para el perfil de cliente actual.

**Sprint G original (PocketBase CRM)** — descartado hasta que PocketBase alcance v1.0.0.
PocketBase dice explícitamente en su documentación: "NOT recommended for production critical
applications yet". Los MCP servers disponibles son alpha/v1.0.0. Se retoma como **Sprint I**
cuando el ecosistema madure (estimado Q4 2026).
La investigación completa está en `docs/hermes-guia/07` y `08` como referencia futura.
El CRM en la fase actual se implementa via SQLite directamente en el volumen de Hermes.

---

## Capacidad del servidor

| Configuración | Tenants seguros |
|---|---|
| 768MB / 0.75 CPU sin restricciones extra | ~20 tenants en CX43 |
| Uso idle real (~200MB) | ~60 caben teóricamente |
| **Límite práctico** | **20–25 tenants** |

Para escalar: upgrade a CX53 (32GB, €45/mes).

---

## Lecciones aprendidas recientes

1. **Paradigma plataforma vs agente**: martes.app gestiona solo la plataforma. Hermes gestiona su funcionamiento. `docs/hermes-guia/00-PARADIGMA-PLATAFORMA.md`
2. **Hermes factory defaults**: sin cap_drop, sin pids_limit, sin tmpfs — Docker defaults son correctos. El único límite intencional es `mem_limit=768m`
3. **ddgs**: búsqueda web gratuita, sin browser, sin API key, +0MB RAM — cubre 80%+ de casos
4. **PocketBase pre-v1.0.0**: no recomendado para producción según su propia documentación. Retomar en Sprint I
5. **MCP servers**: ecosystem madurando, no usar paquetes alpha en producción SaaS
