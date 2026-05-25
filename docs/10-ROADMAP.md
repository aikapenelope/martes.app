# Roadmap — martes.app

> **Estado a**: 4 junio 2026  
> **Sistema**: Producción — 1 tenant activo (t001), t002 archivado/pendiente purge  
> **Stack**: Hetzner CX43 · Coolify · Agno AgentOS 2.6.8 · SeaweedFS 4.28 · Hermes v2026.5.16 · Metabase v0.61.2.6  
> **PRs abiertos**: #76 (factory defaults), #80 (docs)

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

### Backups
- Diario 3AM a SeaweedFS, keep_last=7
- Lifecycle rules SeaweedFS 30 días
- Restore correcto (WAL, symlinks, permisos)

### Billing
- Trial 30d, alertas 7d/3d/día 0, auto-suspend
- `register_payment()`, BYOK platform key (TTL 2h, auth.json detection)

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
| **C2** | Verificar backup 3AM: `GET /schedules/{id}/runs` → triggered_at≈03:00 + status=success | 🟡 |
| **D1** | Test `register_payment()` real con t001 + verificar `paid_until` en DB | 🟡 |
| **Metabase** | Primer login → conectar `db:5432` solo schema `public` → dashboards de tenants + uptime | 🟡 |
| **Purge t002** | "purga el registro archivado de t002 de la base de datos" | 🟢 |

---

## Sprint H — Código pendiente

### H1 · `inject_credential` + `openrouter_api_key`

**Archivo**: `apps/meta-agent/src/tools/write_ops.py`

Dos cambios en el mismo PR:

```python
# 1. Añadir openrouter_api_key a CredentialType y _CREDENTIAL_FILE_MAP:
CredentialType = Literal[
    "google_token", "notion_key", "airtable_key",
    "github_token", "linear_key",
    "openrouter_api_key",   # ← añadir
]

_CREDENTIAL_FILE_MAP = {
    ...
    "openrouter_api_key": ".env",   # ← añadir
}

# 2. En inject_credential(), después de escribir la key:
if credential_type == "openrouter_api_key":
    # El cliente configuró su propia key → limpiar el marker de expiración
    # inmediatamente en lugar de esperar el ciclo de 30 minutos
    marker_file = tenant_path / _PLATFORM_KEY_EXPIRES_FILE
    marker_file.unlink(missing_ok=True)
```

**Por qué**: cuando el admin inyecta la key propia del cliente via `inject_credential()`, el scheduler de 30 minutos tarda en limpiar el marker. Con este cambio el cleanup es inmediato.

---

### H2 · Pruning de tablas

**Archivo**: `apps/meta-agent/src/main.py`

Nuevo endpoint + schedule semanal:

```python
@app.post("/maintenance/prune-old-data")
async def run_prune_old_data() -> JSONResponse:
    """Limpieza semanal de tablas que crecen indefinidamente."""
```

```sql
-- martes_traces: cada LLM call genera una traza — sin limpiar, millones/año
DELETE FROM ai.martes_traces WHERE created_at < NOW() - INTERVAL '30 days';

-- martes_sessions: sesiones inactivas más de 90 días
DELETE FROM ai.martes_sessions WHERE updated_at < NOW() - INTERVAL '90 days';

-- health_checks: 5 min × N tenants × 24h = cientos de filas/día
DELETE FROM public.health_checks WHERE checked_at < NOW() - INTERVAL '90 days';
```

Schedule: `prune-old-data` · cron `0 2 * * 0` (domingos 2AM, antes del backup)

---

### H3 · `TenantCreateInput` — Pydantic BaseModel

**Archivo**: `apps/meta-agent/src/tools/write_ops.py`

`create_tenant()` usa args posicionales con type hints inline. Sprint A definió convertirlo a `BaseModel` para que Agno genere el JSON schema correcto para el LLM (enum enforcement, validaciones declarativas).

```python
class TenantCreateInput(BaseModel):
    name: str = Field(..., description="Nombre del cliente o empresa. Ej: 'Acme Corp'")
    bot_token: str = Field(..., description="Token del bot de @BotFather. Formato: 123456:ABC...")
    telegram_user_id: str = Field(..., description="ID numérico de Telegram. Obtener con @userinfobot")
    model: str = Field(
        default="openai/gpt-4o-mini",
        description="Modelo LLM. Opciones: openai/gpt-4o-mini, deepseek/deepseek-v4-flash, anthropic/claude-3.5-haiku"
    )
    email: str = Field(default="", description="Email de contacto (opcional)")

def create_tenant(input: TenantCreateInput) -> str:
    # El cuerpo no cambia — solo acceder via input.name, input.bot_token, etc.
    # Las validaciones inline (regex bot_token, isdigit telegram_user_id) se mueven al modelo
```

**Por qué ahora y no antes**: la validación inline funciona, pero con BaseModel el schema del tool que recibe el LLM incluye `description` de cada campo y restricciones declarativas. El LLM comete menos errores al llamar el tool.

---

### H4 · Billing agent conversacional

**Archivo nuevo**: `apps/meta-agent/src/agents/billing.py`
**Archivo modificado**: `apps/meta-agent/src/team.py`

Tercer agente del Team, solo lectura. Responde consultas de billing desde Telegram sin necesidad de abrir Metabase:

```
Admin: "¿quiénes vencen esta semana?"
Billing: "3 tenants vencen en los próximos 7 días:
  • Acme Corp (t001) — vence en 3 días (7 junio)
  • Farmacia El Sol (t003) — vence en 5 días (9 junio)
  • Studio XYZ (t005) — vence en 7 días (11 junio)"

Admin: "¿cuánto revenue llevo este mes?"
Billing: "Junio 2026: $210 registrados (7 pagos)
  Pendientes de cobro esta semana: $90 (3 tenants)"
```

Herramientas: consultas SQL directas a `tenants` + `payments` via `psycopg`. Sin LLM en las consultas — solo formateo del resultado. ~60 líneas de código.

---

### H5 · Tests básicos

**Directorio nuevo**: `apps/meta-agent/tests/`

No hay ningún test. Un cambio en `write_ops.py` puede romper `create_tenant()` silenciosamente.

Tests mínimos necesarios:

```
tests/
  test_create_tenant_validation.py   — valida bot_token regex, telegram_user_id numérico
  test_billing_expiry.py             — lógica de billing_check: trial/grace/suspend
  test_expire_platform_key.py        — lógica BYOK: niveles 1 y 2 de detección
  test_backup_restore.py             — lógica del tar filter (exclusión WAL, symlinks)
```

Todos son unit tests puros — sin Docker, sin PostgreSQL. Mockean Docker SDK y psycopg. Ejecutan en CI en segundos.

```bash
# Añadir al cd.yml después del build check:
- name: Run tests
  run: |
    cd apps/meta-agent
    pip install -e ".[dev]"
    pytest tests/ -v
```

---

## Sprint F — Producto y landing

### F1 · Landing page `martes.app`

**El dominio raíz sirve nada actualmente.**

```
martes.app              → ❌ vacío
www.martes.app          → ❌ vacío
api.martes.app          → ✅ meta-agente
```

**Arquitectura recomendada**:
- Repo separado: `aikapenelope/martes-landing`
- Framework: Next.js (static export) o Astro
- Deploy: Vercel (free tier, CDN global)
- DNS: `martes.app CNAME cname.vercel-dns.com` (no afecta `api.martes.app`)

**Por qué antes de E1**: el primer cliente real va a buscar `martes.app`. Si está vacío, daña la credibilidad. Mínimo necesario: nombre, propuesta de valor, precio, cómo contactar.

**Contenido mínimo del landing**:
- Qué es: "Tu agente IA personal conectado a WhatsApp/Telegram"
- Precio: $30/mes
- Qué incluye: atención 24/7, integra Airtable/Google/Notion/más
- CTA: "Contactar al admin" (link a Telegram del dueño)

---

### F2 · Limpieza de docs históricos

Los siguientes documentos son del proceso inicial de diseño (inglés, desactualizados):

```
docs/00-ARCHITECTURE-PLAN.md       → archivar o eliminar
docs/01-DEEP-RESEARCH-FINDINGS.md  → archivar o eliminar
docs/02-DOCKER-INFRA-EXPLAINED.md  → archivar o eliminar
docs/03-WHATS-NEXT-DECISION-MATRIX.md → archivar o eliminar
docs/04-PRODUCT-DECISIONS-FINAL.md → archivar o eliminar
docs/05-MEMORY-WIKI-LLM-DECISIONS.md → archivar o eliminar
docs/06-ADDONS-COMPOSIO-MEMORY.md  → archivar o eliminar
docs/07-IMPLEMENTATION-START.md    → archivar o eliminar
docs/08-VALIDATION-AUDIT.md        → archivar o eliminar
docs/09-SPRINT2-PLAN.md            → archivar o eliminar
docs/14-HERMES-RESTART-UPDATE-GUIDE.md → evaluar si aún aplica
docs/15-HERMES-RESTART-WHY-AND-HOW.md  → evaluar si aún aplica
docs/16-DEPLOY-PLAN-DOMAIN.md          → evaluar si aún aplica
```

El `hermes-ops-guide.md` y `observability.md` y `token-budget-model.md` pueden mantenerse si siguen siendo precisos.

**Acción**: mover a `docs/archive/` o eliminar. Reducir el ruido para que `docs/hermes-guia/` sea la fuente de verdad.

---

## Sprint E — Producto

### E1 · Primer cliente real (beta)

**Bloqueantes**:
1. C1 (backup→restore end-to-end) — no deployar sin esto
2. F1 (landing page) — credibilidad básica
3. Metabase configurado — para monitorear al cliente

Flujo de onboarding:
```
1. "crea tenant [nombre] token [bot_token] telegram_id [id]"
   → hermes-{code} arrancado con capacidades completas de fábrica
   → paid_until = hoy + 30 días (trial)
   → TELEGRAM_HOME_CHANNEL configurado → sin "No home channel"

2. Cliente habla con su bot por Telegram
   → /help muestra capacidades
   → /model para elegir el LLM
   → /skills install [skill] para integrar herramientas
   → /auth para poner su propia API key

3. Plataforma key expira en 2h → cliente configura la suya
   (o el admin extiende con PLATFORM_KEY_TTL_HOURS=0 para trial más largo)

4. billing-check corre cada día a las 9AM UTC
```

### E2 · upgrade_tenant() en producción

Cuando NousResearch publique la siguiente versión estable de Hermes (estimado v2026.6.x o posterior):
1. Revisar release notes: cambios en `.env`, `config.yaml`, comportamientos nuevos
2. `upgrade_tenant("t_test", "nousresearch/hermes-agent:vNUEVO")` — tenant de prueba
3. Verificar health + mensaje de prueba en Telegram
4. Si ok: upgradear t001 y siguientes uno a uno

---

## Sprint I — CRM (futuro, cuando PocketBase v1.0.0)

La investigación completa está documentada en `docs/hermes-guia/07` y `08`.

**Prerequisitos para retomar**:
- PocketBase ≥ v1.0.0 (actualmente pre-v1.0.0, sus autores no lo recomiendan para producción)
- Ecosistema MCP estable (paquetes alpha → v1.x estable)
- Al menos 5 tenants activos que justifiquen el dashboard visual

**Arquitectura decidida** (cuando llegue el momento):
- Una instancia PocketBase por tenant (`pb-{code}` container sidecar)
- Schema CRM: contactos, conversaciones, productos, pedidos, pagos, calendario
- Comunicación Hermes→PocketBase: MCP server `@mabeldata/pocketbase-mcp`
- Backup separado via API nativa de PocketBase → SeaweedFS `pb-backups/`
- React SPA en `/pb_public/` (mismo container) o CDN externo
- Subdominio: `{slug}.martes.app`

---

## Descartado

**Hermes dashboard** — expone API keys. Los clientes configuran desde Telegram.

**CRM (ahora)** — ninguna solución ligera ("Memos para CRM") existe en el ecosistema 2026.
Investigación en `docs/hermes-guia/07` y `08`. Retomar como Sprint I cuando PocketBase v1.0.0.

**`install_skill_in_tenant()`** — obsoleto. Con factory defaults, el cliente instala skills
desde Telegram directamente: `hermes skills install X` + `/restart`.

**InsForge para CRM** — no es multi-tenant nativo. Una instancia = un proyecto Docker Compose.
~500MB RAM por instancia. Diseñado para developers, no para data layer de clientes SaaS.

---

## Capacidad del servidor

| Config | Tenants seguros en CX43 |
|---|---|
| 768MB / 0.75 CPU por tenant | ~20 tenants |
| Uso idle real (~200MB) | hasta ~60 teóricamente |
| **Práctica segura** | **20–25 tenants** |

Para escalar: upgrade a CX53 (32GB RAM, €45/mes) o segundo servidor dedicado a tenants.
