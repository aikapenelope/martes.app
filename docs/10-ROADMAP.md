# Roadmap — martes.app

> **Estado a**: 4 junio 2026  
> **Sistema**: Producción — 1 tenant activo (t001), t002 archivado/pendiente purge  
> **Stack**: Hetzner CX43 · Coolify · Agno AgentOS 2.6.8 · SeaweedFS 4.28 · Hermes v2026.5.16 · Metabase v0.61.2.6  
> **PRs abiertos**: #71 (investigación PocketBase), #72 (arquitectura PocketBase)  
> **Documentación PocketBase**: `docs/hermes-guia/07-POCKETBASE-CRM-INVESTIGACION.md` · `08-ARQUITECTURA-POCKETBASE-COMPLETA.md`

---

## ✅ Completado

### Sprints A, B, C, D, F (PRs #57–72)

Ver `CHANGELOG.md` para el detalle completo.

**Resumen de lo implementado:**
- Robustez del agente: Pydantic, name→code, EntityMemory
- Monitoreo automático: health-check, billing-check, alertas Telegram
- Herramientas de producción: get_server_capacity, diagnose_container_error, upgrade_tenant
- Backups y hardening: lifecycle SeaweedFS, healthcheck fix, restore fix
- Observabilidad: health_checks y error_logs se pueblan desde el código
- Billing SaaS: trial 30d, alertas escalonadas, auto-suspend
- Gaps operativos: gitleaks CI, docker-cleanup, stale resources
- Metabase v0.61.2.6 en compose (solo Tailscale)
- Platform key BYOK (TTL 2h, auth.json detection multi-proveedor)
- Documentación fundacional: 8 documentos en `docs/hermes-guia/`

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

## Sprint G — PocketBase CRM (próximo sprint mayor)

> **Investigación completada**: ver `docs/hermes-guia/07` y `08`.  
> **Decisión arquitectural**: una instancia PocketBase por tenant (recomendación oficial del maintainer ganigeorgiev). No se usa instancia compartida.

### Decisiones tomadas

**Subdominio**: `{slug}.martes.app` (ej: `acme.martes.app`)
- Mejor UX que `t001.app.martes.app` — memorable y representa la marca del cliente
- El slug se deriva del nombre del negocio (lowercase, guiones)
- Slugs reservados: `api`, `www`, `app`, `admin`, `metabase`
- Requiere wildcard cert `*.martes.app` en Traefik (una configuración, cubre todos)
- El slug se guarda en `instance_configs.extra_config: {"pb_slug": "acme"}`

**Traefik**: sin conflictos. Cada PocketBase usa `Host({slug}.martes.app)`. El meta-agente usa `Host(api.martes.app)`. Traefik descubre containers con `traefik.enable=true` automáticamente.

**Browser**: los clientes de martes.app NO necesitan browser local. Hermes usa `ddgs` (DuckDuckGo, sin API key, sin Chromium, +0MB RAM) para búsquedas. Para automatización web si alguien la pide: Browserbase o Browser Use cloud API (+0MB en container, pago por uso).

**Kanban/workers**: descartado para el perfil de PyME venezolana. No es necesario.

**Container restrictions**: los cambios mínimos necesarios son:
- `pids_limit`: 256 → **512** (Hermes spawna más procesos de lo esperado con skills activas)
- `tmpfs /tmp`: 100MB → **500MB** (pip installs de skills, archivos temporales)
- `mem_limit`: mantener **768MB** — con ddgs y sin browser es suficiente
- `cap_drop/cap_add`: mantener igual — no se necesita SYS_PTRACE para uso normal

**Web search sin browser** (confirmado del source code de Hermes):
```
web_search = ddgs (DuckDuckGo)  →  HTTP puro, sin Chromium, +0MB RAM, sin API key
web_extract = Firecrawl API     →  HTTP puro, +0MB RAM, necesita API key ($20/mes)
browser_tool                    →  solo si el cliente necesita formularios/SPAs
```

---

### G1 · Ajustes del container (rápido)

Cambiar en `create_tenant()` en `write_ops.py`:
```python
pids_limit=256       →  pids_limit=512
tmpfs={"/tmp": "size=100m"}  →  tmpfs={"/tmp": "size=500m"}
```

Tenants existentes: `update_tenant_resources()` no cubre pids/tmpfs. Se aplica en el próximo recreate o upgrade del container.

**Archivos**: `apps/meta-agent/src/tools/write_ops.py`

---

### G2 · PocketBase sidecar en `create_tenant()`

Cuando se crea un tenant, además del container `hermes-{code}`, se crea `pb-{code}`:

```python
# Después de crear hermes-{code}:
1. Crear /var/lib/martes/tenants/{code}/pb_data/      # vacío, PocketBase lo inicializa
2. Crear /var/lib/martes/tenants/{code}/pb_migrations/ # con schema CRM pre-definido
   └── 1_crm_schema.js     # 6 colecciones: contactos, conversaciones, productos, pedidos, pagos, calendario
   └── 2_hermes_token.js   # API token para Hermes
3. Lanzar container pb-{code}:
   - image: ghcr.io/pocketbase/pocketbase:latest
   - redes: tenant-{code}-net (para Hermes) + coolify (para Traefik)
   - volumen: pb_data/ → /pb_data
   - labels Traefik: Host({slug}.martes.app) → :8090
   - mem_limit: 128MB
4. Esperar health OK (curl /_/api/health)
5. Crear superadmin via CLI
6. Generar API token para Hermes → escribir POCKETBASE_TOKEN en .env del tenant
7. Reiniciar hermes-{code} para cargar la nueva var
```

**Archivos**: `apps/meta-agent/src/tools/write_ops.py` (create_tenant + nuevo deploy_pocketbase)

---

### G3 · `deploy_pocketbase_tenant()` — tool del meta-agente

Para tenants **existentes** (t001, etc.) que no tienen PocketBase todavía:

```python
def deploy_pocketbase_tenant(tenant_code: str, slug: str) -> str:
    """Despliega PocketBase para un tenant existente.
    Crea el container, copia migrations, configura Traefik, escribe token en .env.
    Requiere aprobación.
    """
```

**Archivos**: `write_ops.py`, `agents/operador.py`

---

### G4 · `install_skill_in_tenant()` — tool del meta-agente

El cliente Hermes no puede instalar skills (requiere reiniciar el gateway). El meta-agente sí puede:

```python
def install_skill_in_tenant(tenant_code: str, skill_name: str) -> str:
    """Instala una skill en el tenant sin que el cliente la instale directo.
    
    1. Descarga SKILL.md desde el hub oficial de Hermes (agentskills.io o GitHub)
    2. Copia a /var/lib/martes/tenants/{code}/skills/{skill}/SKILL.md
    3. Reinicia hermes-{code} para que cargue la skill
    4. Verifica que el bot responde normalmente
    
    Skills disponibles: airtable, notion, google-workspace, stocks, shopify,
                        solana, evm, crm-pocketbase (ver G5)
    Requiere aprobación.
    """
```

**Archivos**: `write_ops.py`, `agents/operador.py`

---

### G5 · Skill `crm-pocketbase` para Hermes

La skill que enseña a Hermes cómo usar su PocketBase como CRM:

```
/var/lib/martes/tenants/{code}/skills/crm-pocketbase/SKILL.md

Contenido:
- Cómo guardar cada conversación de WhatsApp/Telegram en la colección `conversaciones`
- Cómo crear un contacto nuevo cuando el cliente no existe
- Cómo registrar un pedido cuando el cliente confirma una compra
- Cómo actualizar el stock cuando se confirma entrega
- Cómo crear un evento en `calendario` cuando agenda una cita
- URL y token de PocketBase: http://pb-{code}:8090 + token del .env
```

Esta skill se instala automáticamente en G2 al crear el tenant. Para tenants existentes: `install_skill_in_tenant("t001", "crm-pocketbase")`.

**Archivos**: `infra/templates/skills/crm-pocketbase/SKILL.md` (nuevo template)

---

### G6 · `delete_tenant()` actualizado para PocketBase

Cuando se da de baja un tenant, también se elimina su PocketBase:

```python
# En delete_tenant(), después de eliminar hermes-{code}:
1. Parar y eliminar container pb-{code}
2. El volumen pb_data/ se elimina con el resto del volumen del tenant
   (o se conserva si keep_volume=True)
```

**Archivos**: `write_ops.py` (delete_tenant + stop_tenant)

---

### G7 · PWA mínima viable

> **Trabajo externo a este repo.** Tecnología: Next.js + PocketBase JS SDK.

```
Una única app Next.js en Vercel que sirve a todos los tenants.
Ruta de login: app.martes.app → detecta slug → conecta a {slug}.martes.app API

Vistas:
  / — Dashboard (inventario crítico, pedidos del día, conversaciones sin leer)
  /inventario — Tabla de productos con stock, búsqueda, edición inline
  /pedidos — Lista de pedidos con filtros por estado
  /contactos — CRM básico: lista de clientes, historial de conversaciones
  /calendario — Citas y entregas de la semana
  /config — Datos del negocio, métodos de pago, SOUL del agente

Auth: PocketBase built-in (email/OTP — sin Clerk)
Realtime: SSE subscriptions para pedidos e inventario en tiempo real
```

---

## Sprint H — Código pendiente de calidad

### Alta prioridad

**`inject_credential` con `openrouter_api_key`** — Cuando el admin inyecta la key propia del cliente, borrar inmediatamente el marker `.platform_key_expires`:

```python
# En inject_credential(), si credential_type == "openrouter_api_key":
marker_file = tenant_path / _PLATFORM_KEY_EXPIRES_FILE
marker_file.unlink(missing_ok=True)  # cleanup inmediato, no esperar 30min
```

**`martes_traces` y `martes_sessions` pruning** — Schedule semanal:
```sql
DELETE FROM martes_traces WHERE created_at < NOW() - INTERVAL '30 days';
DELETE FROM martes_sessions WHERE updated_at < NOW() - INTERVAL '90 days';
```

### Media prioridad

**`health_checks` pruning** — Schedule semanal para datos > 90 días.

**Billing agent conversacional** — Tercer agente del Team especializado en billing. Responde: *"¿quiénes vencen esta semana?"*, *"¿cuánto revenue este mes?"*. Solo lectura. ~50 líneas.

---

## Sprint E — Producto

### E1 · Primer cliente real (beta)

**Bloqueante**: C1 (backup→restore), G1 (container fixes), G2 (PocketBase deploy).

Flujo de onboarding con PocketBase incluido:
```
1. "crea tenant [nombre] [slug] token [bot_token] telegram_id [id]"
   → hermes-{code} + pb-{code} arrancados
   → paid_until = hoy + 30 días (trial)
   → {slug}.martes.app accesible

2. Cliente instala la PWA en su móvil (app.martes.app)
   → ve su inventario vacío, sus pedidos, su configuración

3. Admin configura el catálogo inicial vía Telegram o PocketBase admin UI:
   "agrega estos productos al catálogo de t001: [lista]"

4. Cliente configura su propia OpenRouter key
   → platform key expira automáticamente en 2h

5. billing-check corre diariamente
```

### E2 · upgrade_tenant() en producción

Cuando NousResearch publique la siguiente versión estable de Hermes.

---

## Descartado

**Hermes dashboard por tenant** — Demasiado complejo, expone API keys. Los clientes gestionan desde Telegram.

**Kanban/workers para PyMEs** — El perfil de uso no lo requiere. Browser local tampoco. ddgs cubre búsquedas sin overhead.

---

## Capacidad del servidor

| Tier | RAM/tenant | Tenants en CX43 | Precio |
|---|---|---|---|
| **Básico** (ddgs, sin browser) | 768MB Hermes + 128MB PocketBase | ~18 | $30/mes |
| **Pro** (browser cloud API) | 768MB Hermes + 128MB PocketBase | ~18 | $50/mes |
| **Heavy** (browser local) | 1.5GB Hermes + 128MB PocketBase | ~9 | $80/mes |

El browser local (Chromium headless) no se desplegará en los primeros clientes — ddgs cubre búsquedas, browser cloud (Browserbase API) cubre automatización si alguien lo necesita, sin cambiar el límite de RAM del container.

---

## Lecciones aprendidas

Ver `CHANGELOG.md` → Notas técnicas.

**Adiciones recientes (PocketBase sprint):**
1. PocketBase: una instancia por tenant es la arquitectura correcta (recomendación oficial del maintainer)
2. ddgs (DuckDuckGo) = búsqueda web gratuita sin browser, sin API key, +0MB RAM — suficiente para 80%+ de casos PyME
3. Browser local (Chromium) = +350-500MB RAM cuando activo — no necesario para el perfil de cliente actual
4. `{slug}.martes.app` mejor que `{code}.app.martes.app` — memorable, representa la marca del cliente
5. El meta-agente SÍ puede instalar skills/configurar tenants que el bot del cliente no puede — la infraestructura existe, faltan las tools Python
6. Agno schema `"ai"` aísla sus tablas de las tablas de negocio en `"public"` — Metabase solo debe ver `"public"`
