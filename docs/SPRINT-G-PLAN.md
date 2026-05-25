# Sprint G — Plan de implementación PocketBase CRM

> **Estado**: plan aprobado v2, pendiente de implementación  
> **Prerequisito**: PR #74 + PR #76 mergeados en main  
> **Principio**: martes.app hace el deploy. Hermes hace el resto.  
> **Ref filosofía**: `docs/hermes-guia/00-PARADIGMA-PLATAFORMA.md`

---

## Decisiones arquitecturales (definitivas)

### Lo que se descartó y por qué

**Imagen Docker custom (`martes-crm`)**: descartada. Acoplaba el ciclo de vida de React, PocketBase y Hermes en una sola imagen. Cualquier update de UI requería reconstruir la imagen y hacer upgrade en todos los containers activos. Frágil.

**Skill con instrucciones curl**: descartada para la comunicación operacional. El MCP server es la forma correcta — Hermes tiene herramientas nativas, TOML output (25% menos tokens), sin construir JSON manual.

### Lo que se usa

| Decisión | Solución | Fuente |
|---|---|---|
| Imagen PocketBase | `ghcr.io/muchobien/pocketbase:latest` (oficial) | github.com/muchobien/pocketbase-docker |
| Schema CRM inicial | JS migrations montadas desde host (`pb_migrations/` volumen ro) | pocketbase.io/docs/js-migrations |
| Superadmin | Env vars `PB_ADMIN_EMAIL` + `PB_ADMIN_PASSWORD` — imagen las maneja sola | muchobien/pocketbase feature |
| React SPA | Montada desde host en `/pb_public/` (compartida por todos los tenants, ro) | pocketbase.io/docs → sirve `/pb_public/` nativamente |
| Comunicación Hermes→PB | MCP server `pocketbase-mcp-server` en `config.yaml` del tenant | lobehub.com/mcp/feirelles-pocketbase-mcp |
| Backup PocketBase | API nativa `POST /api/backups` → SeaweedFS separado | pocketbase.io/docs/api-backups |
| Skill CRM | Contexto de negocio (cuándo usar qué colección) — NO infraestructura | paradigma martes.app |
| Repo separado | No necesario | — |

---

## Pre-sprint — operacional (admin en el registrador de dominio)

```
DNS wildcard: *.martes.app → 204.168.169.254
TTL: 3600
```

Una sola vez. Cubre acme.martes.app, farmacia.martes.app, etc.

También: preparar `/var/lib/martes/pb_public/` en el VPS con el primer build de la React SPA
(vacío al principio — PocketBase simplemente sirve la API hasta que se despliegue la UI).

---

## G1 — DB migration: campo `slug`

**Archivo**: `db/migrations/003_pocketbase_slug.sql` (nuevo)

```sql
ALTER TABLE tenants
    ADD COLUMN IF NOT EXISTS slug VARCHAR(63) UNIQUE;

COMMENT ON COLUMN tenants.slug IS
    'Subdominio del cliente en martes.app. Ej: "acme" → acme.martes.app';

CREATE INDEX IF NOT EXISTS idx_tenants_slug ON tenants(slug)
    WHERE slug IS NOT NULL;
```

Slugs reservados (validar en código): `api`, `www`, `app`, `admin`, `metabase`

---

## G2 — Pydantic `TenantCreateInput`: campo `slug`

**Archivo**: `apps/meta-agent/src/tools/write_ops.py`

```python
class TenantCreateInput(BaseModel):
    name: str
    slug: str           # "acme" → acme.martes.app
    bot_token: str
    telegram_user_id: str
    model: str = "openai/gpt-4o-mini"
    email: str = ""

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        import re
        _RESERVED = {"api", "www", "app", "admin", "metabase"}
        v = v.lower().strip()
        if not re.match(r"^[a-z0-9][a-z0-9\-]{1,61}[a-z0-9]$", v):
            raise ValueError("Slug: solo letras/números/guiones, 3-63 chars.")
        if v in _RESERVED:
            raise ValueError(f"'{v}' está reservado por la plataforma.")
        return v
```

Guardar en DB: `INSERT INTO tenants (..., slug) VALUES (..., input.slug)`

---

## G3 — Templates JS de migrations CRM

**Archivos nuevos** en `infra/templates/pocketbase/migrations/`:

```
1_crm_schema.js     ← 6 colecciones del CRM
2_api_rules.js      ← reglas de acceso (owner-only por defecto)
3_settings.js       ← configura app name y CORS para el slug del tenant
```

**Colecciones** (fuente: `docs/hermes-guia/07-POCKETBASE-CRM-INVESTIGACION.md` sección 3):

```javascript
// 1_crm_schema.js — syntax oficial: pocketbase.io/docs/js-collections
migrate((app) => {

  // contactos
  app.save(new Collection({
    type: "base", name: "contactos",
    fields: [
      { name: "nombre",       type: "text",     required: true },
      { name: "whatsapp",     type: "text" },
      { name: "telegram_id",  type: "text" },
      { name: "email",        type: "email" },
      { name: "notas",        type: "editor" },
      { name: "tags",         type: "json" },
      { name: "ultimo_contacto", type: "date" },
    ]
  }))

  // conversaciones
  const contactosCol = app.findCollectionByNameOrId("contactos")
  app.save(new Collection({
    type: "base", name: "conversaciones",
    fields: [
      { name: "contacto",   type: "relation",
        collectionId: contactosCol.id, maxSelect: 1 },
      { name: "canal",      type: "select",
        values: ["whatsapp","telegram","email","otro"], maxSelect: 1 },
      { name: "mensaje",    type: "text",   required: true },
      { name: "direccion",  type: "select",
        values: ["entrante","saliente"],    maxSelect: 1 },
      { name: "procesado",  type: "bool",   default: false },
    ]
  }))

  // productos
  app.save(new Collection({
    type: "base", name: "productos",
    fields: [
      { name: "nombre",       type: "text",    required: true },
      { name: "sku",          type: "text" },
      { name: "descripcion",  type: "editor" },
      { name: "stock",        type: "number",  default: 0 },
      { name: "precio_usd",   type: "number",  required: true },
      { name: "foto",         type: "file",    maxSelect: 3 },
      { name: "activo",       type: "bool",    default: true },
      { name: "variantes",    type: "json" },
    ]
  }))

  // pedidos
  const productosCol = app.findCollectionByNameOrId("productos")
  app.save(new Collection({
    type: "base", name: "pedidos",
    fields: [
      { name: "contacto",      type: "relation",
        collectionId: contactosCol.id, maxSelect: 1 },
      { name: "items",         type: "json" },
      { name: "total_usd",     type: "number",  required: true },
      { name: "estado",        type: "select",
        values: ["pendiente_pago","pagado","en_preparacion",
                 "enviado","entregado","cancelado"],
        maxSelect: 1 },
      { name: "metodo_pago",   type: "select",
        values: ["pago_movil","usdt","zelle","efectivo","otro"],
        maxSelect: 1 },
      { name: "referencia",    type: "text" },
      { name: "fecha_entrega", type: "date" },
      { name: "notas",         type: "text" },
    ]
  }))

  // pagos
  const pedidosCol = app.findCollectionByNameOrId("pedidos")
  app.save(new Collection({
    type: "base", name: "pagos",
    fields: [
      { name: "pedido",      type: "relation",
        collectionId: pedidosCol.id, maxSelect: 1 },
      { name: "monto_usd",   type: "number",  required: true },
      { name: "metodo",      type: "select",
        values: ["pago_movil","usdt","zelle","efectivo","otro"],
        maxSelect: 1 },
      { name: "referencia",  type: "text" },
      { name: "comprobante", type: "file",    maxSelect: 1 },
      { name: "confirmado",  type: "bool",    default: false },
    ]
  }))

  // calendario
  app.save(new Collection({
    type: "base", name: "calendario",
    fields: [
      { name: "titulo",       type: "text",    required: true },
      { name: "contacto",     type: "relation",
        collectionId: contactosCol.id, maxSelect: 1 },
      { name: "tipo",         type: "select",
        values: ["cita","entrega","llamada","recordatorio"],
        maxSelect: 1 },
      { name: "inicio",       type: "date",    required: true },
      { name: "fin",          type: "date" },
      { name: "descripcion",  type: "text" },
      { name: "completado",   type: "bool",    default: false },
    ]
  }))

}, (app) => {
  // downFunc — rollback si fuera necesario
  for (const name of ["calendario","pagos","pedidos","productos",
                       "conversaciones","contactos"]) {
    try {
      app.delete(app.findCollectionByNameOrId(name))
    } catch (_) {}
  }
})
```

```javascript
// 3_settings.js — nombre de la app y CORS
// TENANT_SLUG se reemplaza en create_tenant() antes de copiar el archivo
migrate((app) => {
  const settings = app.settings()
  settings.meta.appName = "{{TENANT_NAME}}"
  settings.meta.appURL = "https://{{TENANT_SLUG}}.martes.app"
  app.save(settings)
})
```

El placeholder `{{TENANT_SLUG}}` y `{{TENANT_NAME}}` se sustituyen con
`str.replace()` en `create_tenant()` antes de copiar el archivo al volumen.

---

## G4 — `create_tenant()`: PocketBase sidecar completo

**Archivo**: `apps/meta-agent/src/tools/write_ops.py`

### 4a — Directorios y migrations

```python
# Crear directorios del CRM
pb_data = tp / "pb_data"
pb_data.mkdir(mode=0o750, exist_ok=True)
pb_migrations_dir = tp / "pb_migrations"
pb_migrations_dir.mkdir(mode=0o750, exist_ok=True)

# Copiar migrations desde templates, sustituyendo placeholders
templates_pb = Path(settings.templates_path) / "pocketbase" / "migrations"
for mig_file in sorted(templates_pb.glob("*.js")):
    content = mig_file.read_text()
    content = content.replace("{{TENANT_SLUG}}", input.slug)
    content = content.replace("{{TENANT_NAME}}", input.name)
    (pb_migrations_dir / mig_file.name).write_text(content)

_chown(tp)
```

### 4b — Lanzar container PocketBase

```python
pb_admin_pass = secrets.token_urlsafe(24)

pb_container = c.containers.run(
    image=settings.pocketbase_crm_image,  # "ghcr.io/muchobien/pocketbase:latest"
    name=f"pb-{tenant_code}",
    detach=True,
    restart_policy={"Name": "unless-stopped"},  # type: ignore[arg-type]
    network=net,   # tenant-{code}-net
    environment={
        # muchobien/pocketbase feature: crea superadmin automáticamente en primer arranque
        # Ref: github.com/muchobien/pocketbase-docker — PB_ADMIN_EMAIL / PB_ADMIN_PASSWORD
        "PB_ADMIN_EMAIL":    f"admin-{tenant_code}@martes.app",
        "PB_ADMIN_PASSWORD": pb_admin_pass,
    },
    volumes={
        str(tp / "pb_data"):          {"bind": "/pb_data",      "mode": "rw"},
        str(tp / "pb_migrations"):    {"bind": "/pb_migrations", "mode": "ro"},
        # React SPA compartida por todos los tenants (read-only)
        # Vacía al principio — PocketBase sirve solo la API hasta que se despliegue la UI
        "/var/lib/martes/pb_public":  {"bind": "/pb_public",    "mode": "ro"},
    },
    mem_limit="128m",
    nano_cpus=int(0.25 * 1e9),
    labels={
        "martes.tenant":  tenant_code,
        "martes.service": "pocketbase",
        # Traefik: {slug}.martes.app → pb-{code}:8090
        "traefik.enable":  "true",
        "traefik.docker.network": "coolify",
        f"traefik.http.routers.pb-{tenant_code}-https.rule":
            f"Host(`{input.slug}.martes.app`)",
        f"traefik.http.routers.pb-{tenant_code}-https.entrypoints": "https",
        f"traefik.http.routers.pb-{tenant_code}-https.tls": "true",
        f"traefik.http.routers.pb-{tenant_code}-https.tls.certresolver":
            "letsencrypt",
        f"traefik.http.services.pb-{tenant_code}.loadbalancer.server.port":
            "8090",
        f"traefik.http.routers.pb-{tenant_code}-http.rule":
            f"Host(`{input.slug}.martes.app`)",
        f"traefik.http.routers.pb-{tenant_code}-http.entrypoints": "http",
        f"traefik.http.routers.pb-{tenant_code}-http.middlewares":
            "redirect-to-https@docker",
    },
)

# Conectar a red coolify para que Traefik lo vea
try:
    c.networks.get("coolify").connect(pb_container)
except Exception:
    pass  # Si no existe, Traefik no lo expone externamente — no fatal para el agente
```

### 4c — Esperar health y obtener token para Hermes

```python
# Esperar hasta 30s — PocketBase es muy rápido (< 2s típico)
pb_healthy = False
for _ in range(30):
    time.sleep(1)
    try:
        result = c.containers.get(f"pb-{tenant_code}").exec_run(
            ["wget", "-qO-", "http://localhost:8090/api/health"]
        )
        if result.exit_code == 0:
            pb_healthy = True
            break
    except Exception:
        continue

if pb_healthy:
    # Obtener token admin (permanente en v0.38+)
    # wget dentro del container porque pb-{code} no es accesible desde el meta-agente
    auth_result = c.containers.get(f"pb-{tenant_code}").exec_run([
        "wget", "-qO-",
        "--post-data",
        f'{{"identity":"admin-{tenant_code}@martes.app","password":"{pb_admin_pass}"}}',
        "--header", "Content-Type: application/json",
        "http://localhost:8090/api/collections/_superusers/auth-with-password",
    ])
    try:
        pb_token = json.loads(auth_result.output.decode()).get("token", "")
    except (json.JSONDecodeError, AttributeError):
        pb_token = ""

    # Escribir vars de PocketBase en .env del tenant (Hermes las carga en cada turno)
    env_content = env_file.read_text()
    env_file.write_text(
        env_content
        + f"\nPOCKETBASE_URL=http://pb-{tenant_code}:8090"
        + f"\nPOCKETBASE_TOKEN={pb_token}\n"
    )
    os.chmod(env_file, 0o600)

    # Guardar slug en instance_configs para referencia futura
    conn.execute(
        "UPDATE instance_configs "
        "SET extra_config = extra_config || %s "
        "WHERE tenant_id = (SELECT id FROM tenants WHERE tenant_code = %s)",
        (json.dumps({"pb_slug": input.slug, "pb_admin_email":
                     f"admin-{tenant_code}@martes.app"}),
         tenant_code),
    )
    steps.append("pb_configured")
else:
    steps.append("pb_unhealthy_token_pending")
```

### 4d — config.yaml del tenant incluye MCP

La template `infra/templates/default/config.yaml` incluirá el bloque MCP:

```yaml
# config.yaml del tenant — añadir sección mcp_servers
mcp_servers:
  crm:
    command: npx
    args: ["-y", "pocketbase-mcp-server@1.0.0"]
    env:
      POCKETBASE_URL: "{{POCKETBASE_URL}}"
    timeout: 30
    connect_timeout: 15
```

El placeholder `{{POCKETBASE_URL}}` se reemplaza en `create_tenant()` igual que los de migrations:
```python
config_content = (tmpl / "config.yaml").read_text()
config_content = config_content.replace(
    "{{POCKETBASE_URL}}", f"http://pb-{tenant_code}:8090"
)
(tp / "config.yaml").write_text(config_content)
```

### 4e — Skill CRM como contexto de negocio

La skill **no contiene instrucciones de infraestructura**. Solo contexto de negocio:

```markdown
# infra/templates/skills/crm-pocketbase/SKILL.md
---
name: crm-pocketbase
description: Guía para gestionar el CRM del negocio.
  Colecciones disponibles, cuándo usarlas y flujos clave.
version: 1.0.0
author: martes.app
---

# CRM del negocio — guía de uso

Tienes disponibles las herramientas del MCP `crm` para interactuar
con la base de datos del negocio.

## Colecciones

| Colección     | Para qué sirve                                      |
|---------------|-----------------------------------------------------|
| contactos     | Clientes del negocio (WhatsApp, Telegram, email)    |
| conversaciones| Historial de mensajes por canal                     |
| productos     | Inventario con stock y precios en USD               |
| pedidos       | Órdenes con estado y método de pago                 |
| pagos         | Confirmaciones de pago con comprobante              |
| calendario    | Citas, entregas y recordatorios                     |

## Flujos principales

### Cuando un cliente nuevo escribe
1. Buscar si existe en `contactos` por whatsapp/telegram_id
2. Si no existe: crear registro en `contactos`
3. Guardar el mensaje en `conversaciones` (canal, direccion: entrante)

### Cuando hay un pedido
1. Confirmar datos: productos, cantidades, método de pago
2. Crear en `pedidos` con estado "pendiente_pago"
3. Cuando el cliente confirme: crear en `pagos` + actualizar pedido a "pagado"
4. Actualizar `stock` en `productos`

### Seguimiento de inventario
Consultar `productos` con filter `activo=true` ordenado por stock ascendente
para detectar productos con poco stock.
```

---

## G5 — Lifecycle tools: stop, restart, delete

**Archivo**: `apps/meta-agent/src/tools/write_ops.py`

Todos los bloques van en `try/except NotFound: pass` para compatibilidad con
tenants sin PocketBase (creados antes del Sprint G):

```python
# stop_tenant() — después de stop hermes-{code}:
try:
    c.containers.get(f"pb-{tenant_code}").stop(timeout=10)
except NotFound:
    pass

# restart_tenant() — después de restart hermes-{code}:
try:
    c.containers.get(f"pb-{tenant_code}").restart(timeout=10)
except NotFound:
    pass

# delete_tenant() — antes de rmtree del volumen:
try:
    pb = c.containers.get(f"pb-{tenant_code}")
    pb.stop(timeout=5)
    pb.remove(force=True)
except NotFound:
    pass
```

---

## G6 — Backup separado de PocketBase

**Archivo**: `apps/meta-agent/src/tools/write_ops.py` (nueva función `backup_pocketbase_tenant`)

**Archivo**: `apps/meta-agent/src/main.py` (nuevo endpoint + schedule)

### La función

```python
@tool
def backup_pocketbase_tenant(tenant_code: str) -> str:
    """Crea backup del CRM PocketBase y lo sube a SeaweedFS.

    Usa la API nativa de backup de PocketBase (POST /api/backups)
    para crear un .zip consistente del SQLite.
    Ref: pocketbase.io/docs/api-backups

    Independiente del backup de Hermes — prefijo separado en SeaweedFS:
      pb-backups/{tenant_code}/pb_backup_{timestamp}.zip
    Mantiene los últimos 7 backups.
    """
```

Flujo:
```python
# 1. Autenticar como admin (igual que en create_tenant)
# 2. POST /api/backups → PocketBase crea el .zip en pb_data/backups/
# 3. GET /api/backups → obtener el nombre del archivo creado
# 4. Leer desde /var/lib/martes/tenants/{code}/pb_data/backups/{file}.zip
# 5. Upload a SeaweedFS: pb-backups/{tenant_code}/{file}.zip
# 6. Borrar local
# 7. Cleanup SeaweedFS: mantener últimos 7
```

### El schedule

```python
# En main.py — añadir junto a daily-backup-all:
"backup-pocketbase-all": {
    "cron": "30 3 * * *",   # 3:30 AM UTC — media hora después de Hermes
    "endpoint": "/maintenance/backup-pocketbase-all",
}
```

---

## G7 — `deploy_pocketbase_tenant()` para tenants existentes

**Archivo**: `apps/meta-agent/src/tools/write_ops.py` + `agents/operador.py`

Para t001 y tenants creados antes del Sprint G:

```
Admin → meta-agente: "despliega pocketbase para t001 con slug acme"
Operador ejecuta: deploy_pocketbase_tenant("t001", "acme")
```

Mismos pasos que G4 pero sin crear hermes-{code}.
Termina reiniciando hermes-{code} para que cargue las nuevas vars del .env
(`POCKETBASE_URL`, `POCKETBASE_TOKEN`) y el nuevo `config.yaml` con el MCP.

---

## G8 — React SPA (trabajo en frontend, fuera de este repo)

**Stack**: React + Vite + TypeScript + PocketBase JS SDK

**Estructura**:
```
src/
  lib/pocketbase.ts     → new PocketBase(window.location.origin)
  components/
    Dashboard.tsx       → inventario crítico, pedidos del día
    Contactos.tsx       → lista de clientes + historial de conversaciones
    Inventario.tsx      → productos con stock en tiempo real (SSE)
    Pedidos.tsx         → gestión de pedidos con estados
    Calendario.tsx      → citas y entregas de la semana
  App.tsx               → router, auth con PocketBase
```

**Por qué funciona sin configuración especial**:
```typescript
// lib/pocketbase.ts
// Si el cliente abre acme.martes.app, window.location.origin = https://acme.martes.app
// PocketBase está sirviendo en ese mismo origen → same-origin, sin CORS
const pb = new PocketBase(window.location.origin)
export default pb
```

**Deploy**: build de Vite genera `/dist/` → se sube a `/var/lib/martes/pb_public/` en el VPS.
Todos los containers `pb-{code}` ven la UI actualizada sin reiniciar.

```bash
# Para actualizar la UI en producción (admin en el servidor):
# 1. Hacer el build localmente
npm run build
# 2. Subir al VPS
rsync -av dist/ root@204.168.169.254:/var/lib/martes/pb_public/
# 3. Listo — todos los tenants ven la nueva UI inmediatamente
```

---

## Orden de implementación

```
0. Pre-sprint operacional
   ├── DNS wildcard *.martes.app → VPS
   └── mkdir -p /var/lib/martes/pb_public  (vacío al principio)

1. G1 — DB migration 003_pocketbase_slug.sql
   → atómico, sin tocar código Python

2. G2 — TenantCreateInput: campo slug + validación

3. G3 — Templates JS en infra/templates/pocketbase/migrations/
   → solo archivos .js + config.yaml actualizado con MCP placeholder

4. G4 — create_tenant(): PocketBase sidecar
   → el bloque más grande
   → validar contra tenant de prueba

5. G5 — Lifecycle: stop + restart + delete actualizados

6. G6 — backup_pocketbase_tenant() + schedule 3:30 AM

7. G7 — deploy_pocketbase_tenant() para tenants existentes (t001)

8. G8 — React SPA (trabajo externo, se sube a /var/lib/martes/pb_public/)
```

---

## Notas técnicas finales

**Image tag**: `ghcr.io/muchobien/pocketbase:latest` — pinear a tag específico en producción:
```python
# settings.py
pocketbase_crm_image: str = "ghcr.io/muchobien/pocketbase:v0.38.2"
```

**`/var/lib/martes/pb_public/` vacía al principio**: PocketBase sirve la API normalmente.
El admin UI sigue disponible en `{slug}.martes.app/_/`. La React SPA es un extra
que se despliega cuando esté lista, sin afectar el funcionamiento del CRM.

**Hermes y el MCP**: el MCP server (`npx pocketbase-mcp-server`) se lanza como
subprocess cuando Hermes arranca. Node.js está incluido en la imagen de Hermes.
Si `POCKETBASE_URL` no está configurada, el MCP falla silenciosamente y Hermes
continúa sin herramientas de CRM.

**Pinear versión del MCP**:
```yaml
# config.yaml template
mcp_servers:
  crm:
    command: npx
    args: ["-y", "pocketbase-mcp-server@1.0.0"]  # versión pinneada
```
