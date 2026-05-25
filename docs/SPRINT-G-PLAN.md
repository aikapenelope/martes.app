# Sprint G — Plan de implementación PocketBase CRM

> **Estado**: plan aprobado, pendiente de implementación  
> **Prerequisito**: PR #74 mergeado en main  
> **Principio**: martes.app hace el deploy. Hermes hace el resto.  
> **Ref filosofía**: `docs/hermes-guia/00-PARADIGMA-PLATAFORMA.md`

---

## Resumen de lo que se construye

Cada tenant de martes.app tendrá, además de su container Hermes, un container PocketBase que actúa como su CRM privado. Hermes puede leer y escribir en él. El dueño del negocio puede acceder a sus datos via una PWA en `{slug}.martes.app`.

Lo que nosotros hacemos:
1. Arrancar el container PocketBase con el schema CRM pre-cargado
2. Conectarlo a la misma red que Hermes
3. Escribir el token de acceso en el `.env` del tenant
4. Enseñarle a Hermes cómo usarlo (via una skill)

Lo que Hermes y el cliente hacen solos:
- Usar el CRM desde conversaciones de Telegram/WhatsApp
- Personalizar las colecciones si quieren
- Acceder a la PWA con sus propias credenciales

---

## Pre-sprint — operacional (tú en el registrador de dominio)

```
Añadir registro DNS:
  Tipo: A  (o CNAME si usas Cloudflare proxy)
  Host: *.martes.app
  Valor: 204.168.169.254
  TTL: 3600

Esto cubre automáticamente todos los slugs de tenants:
  acme.martes.app → 204.168.169.254
  farmacia.martes.app → 204.168.169.254
  etc.
```

También verifica que Traefik (via Coolify) está configurado con certificados wildcard o con certresolver que soporte `*.martes.app`. El certresolver `letsencrypt` de Coolify soporta wildcard via DNS challenge.

---

## G1 — DB migration: campo `slug` en tenants

**Archivo**: `db/migrations/003_pocketbase_slug.sql` (nuevo)

```sql
-- Migración 003: slug de subdominio para PocketBase
-- El slug determina el subdominio del cliente: {slug}.martes.app
-- Se genera a partir del nombre del negocio: lowercased, guiones, sin caracteres especiales

ALTER TABLE tenants
    ADD COLUMN IF NOT EXISTS slug VARCHAR(63) UNIQUE;

COMMENT ON COLUMN tenants.slug IS
    'Subdominio del cliente en martes.app. Ej: "acme" → acme.martes.app';

-- Índice para lookup rápido por slug (Traefik + routing)
CREATE INDEX IF NOT EXISTS idx_tenants_slug ON tenants(slug) WHERE slug IS NOT NULL;

-- Slugs reservados por la plataforma (no pueden asignarse a tenants):
-- api, www, app, admin, metabase, mail, smtp, ftp, ns1, ns2
```

**Por qué**: necesitamos guardar el slug para que `delete_tenant()`, `stop_tenant()` y el Diagnosticador puedan saber qué subdominio tiene cada tenant sin recalcularlo.

---

## G2 — `create_tenant()`: slug + PocketBase sidecar + container fixes

**Archivo**: `apps/meta-agent/src/tools/write_ops.py`

### 2a — Ajustes del container Hermes (2 líneas)

```python
# ANTES:
pids_limit=256,
tmpfs={"/tmp": "size=100m"},

# DESPUÉS:
pids_limit=512,          # subagentes, tools paralelas, skills con subprocess
tmpfs={"/tmp": "size=500m"},  # pip installs de skills, downloads, archivos temporales
```

`mem_limit="768m"` y `nano_cpus=int(0.75 * 1e9)` **sin cambio**.

### 2b — Pydantic `TenantCreateInput`: añadir campo `slug`

```python
class TenantCreateInput(BaseModel):
    name: str          # Nombre del negocio: "Acme Corp"
    slug: str          # Subdominio: "acme" → acme.martes.app
    bot_token: str     # Token del bot de Telegram
    telegram_user_id: str
    model: str = "openai/gpt-4o-mini"
    email: str = ""
```

Validación del slug (añadir al modelo):
```python
@field_validator("slug")
@classmethod
def validate_slug(cls, v: str) -> str:
    import re
    _RESERVED = {"api", "www", "app", "admin", "metabase", "mail", "smtp"}
    v = v.lower().strip()
    if not re.match(r"^[a-z0-9][a-z0-9\-]{1,61}[a-z0-9]$", v):
        raise ValueError("Slug inválido. Solo letras, números y guiones. 3-63 caracteres.")
    if v in _RESERVED:
        raise ValueError(f"Slug '{v}' está reservado por la plataforma.")
    return v
```

### 2c — Guardar slug en DB

```python
# En la INSERT de create_tenant():
conn.execute(
    "INSERT INTO tenants (tenant_code, name, email, plan, status, slug) "
    "VALUES (%s, %s, %s, %s, 'creating', %s)",
    (tenant_code, input.name, input.email, _billing_plan, input.slug),
)
```

### 2d — Directorios PocketBase en el volumen

```python
# Después de crear los directorios del tenant:
pb_data = tp / "pb_data"
pb_data.mkdir(mode=0o750, exist_ok=True)
pb_migrations = tp / "pb_migrations"
pb_migrations.mkdir(mode=0o750, exist_ok=True)

# Copiar migration templates al volumen
templates_pb = Path(settings.templates_path) / "pocketbase" / "migrations"
for mig_file in sorted(templates_pb.glob("*.js")):
    shutil.copy2(mig_file, pb_migrations / mig_file.name)

_chown(tp)
```

### 2e — Lanzar container PocketBase (después de hermes-{code})

```python
# PocketBase sidecar — arranca después de hermes-{code}
# Conectado a DOS redes:
#   1. tenant-{code}-net: para que Hermes lo alcance (http://pb-{code}:8090)
#   2. coolify: para que Traefik lo exponga externamente ({slug}.martes.app)
pb_container = c.containers.run(
    image="ghcr.io/pocketbase/pocketbase:latest",
    name=f"pb-{tenant_code}",
    detach=True,
    restart_policy={"Name": "unless-stopped"},  # type: ignore[arg-type]
    network=net,  # tenant-{code}-net
    volumes={
        str(tp / "pb_data"): {"bind": "/pb_data", "mode": "rw"},
        str(tp / "pb_migrations"): {"bind": "/pb_migrations", "mode": "ro"},
    },
    command=[
        "serve",
        "--http=0.0.0.0:8090",
        "--dir=/pb_data",
        "--migrationsDir=/pb_migrations",
    ],
    mem_limit="128m",
    nano_cpus=int(0.25 * 1e9),
    labels={
        "martes.tenant": tenant_code,
        "martes.service": "pocketbase",
        # Traefik routing: {slug}.martes.app → pb-{code}:8090
        "traefik.enable": "true",
        "traefik.docker.network": "coolify",
        f"traefik.http.routers.pb-{tenant_code}-https.rule": f"Host(`{input.slug}.martes.app`)",
        f"traefik.http.routers.pb-{tenant_code}-https.entrypoints": "https",
        f"traefik.http.routers.pb-{tenant_code}-https.tls": "true",
        f"traefik.http.routers.pb-{tenant_code}-https.tls.certresolver": "letsencrypt",
        f"traefik.http.services.pb-{tenant_code}.loadbalancer.server.port": "8090",
        f"traefik.http.routers.pb-{tenant_code}-http.rule": f"Host(`{input.slug}.martes.app`)",
        f"traefik.http.routers.pb-{tenant_code}-http.entrypoints": "http",
        f"traefik.http.routers.pb-{tenant_code}-http.middlewares": "redirect-to-https@docker",
    },
)

# Conectar también a red coolify para Traefik
try:
    coolify_net = c.networks.get("coolify")
    coolify_net.connect(pb_container)
except Exception:
    pass  # Si no existe coolify net, Traefik no lo expone — no fatal
```

### 2f — Esperar health de PocketBase y obtener token

```python
# Esperar hasta 30s que PocketBase esté healthy
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

if not pb_healthy:
    steps.append("pb_container_unhealthy_but_continuing")
else:
    # Crear superadmin via CLI (--createDefaultAdmin crea admin@martes.app con password random)
    pb_admin_pass = secrets.token_urlsafe(24)
    c.containers.get(f"pb-{tenant_code}").exec_run([
        "/pb/pocketbase", "superuser", "create",
        f"admin-{tenant_code}@martes.app", pb_admin_pass
    ])

    # Crear API token para Hermes via REST API
    import urllib.request, urllib.parse
    auth_payload = json.dumps({
        "identity": f"admin-{tenant_code}@martes.app",
        "password": pb_admin_pass,
    }).encode()
    req = urllib.request.Request(
        "http://localhost:8090/api/admins/auth-with-password",  # ← esto no funciona
        # ↑ NOTA: se hace via docker exec + curl dentro del container
    )
    # ... ver nota implementación abajo

    steps.append("pb_configured")
```

**Nota de implementación — cómo obtener el token de PocketBase:**

PocketBase no expone el API al host directamente (está en la red del tenant, no el host). Se usa `docker exec` para correr `curl` dentro del container:

```python
# Autenticar y obtener token
auth_cmd = [
    "wget", "-qO-",
    "--post-data", json.dumps({
        "identity": f"admin-{tenant_code}@martes.app",
        "password": pb_admin_pass
    }),
    "--header", "Content-Type: application/json",
    "http://localhost:8090/api/collections/_superusers/auth-with-password"
]
result = c.containers.get(f"pb-{tenant_code}").exec_run(auth_cmd)
auth_data = json.loads(result.output.decode())
pb_token = auth_data.get("token", "")

# Crear API token permanente para Hermes
token_cmd = [...]  # POST /api/collections/_authTokens/records con el admin token
```

**Alternativa más simple**: usar el token de admin directamente en el `.env` del tenant. El token de admin expira (en PocketBase v0.23+ los admin tokens no expiran por default). Se recomienda generar un **API key** (`/api/collections/_superusers/api-keys`) que sí es permanente.

```python
# Guardar en .env del tenant:
env_lines_new = env_file.read_text() + f"\nPOCKETBASE_URL=http://pb-{tenant_code}:8090\nPOCKETBASE_TOKEN={pb_token}\n"
env_file.write_text(env_lines_new)
os.chmod(env_file, 0o600)

# Guardar slug en extra_config de instance_configs
conn.execute(
    "UPDATE instance_configs SET extra_config = extra_config || %s WHERE tenant_id = ("
    "  SELECT id FROM tenants WHERE tenant_code = %s"
    ")",
    (json.dumps({"pb_slug": input.slug}), tenant_code),
)
```

---

## G3 — Lifecycle tools: stop, restart, delete

**Archivo**: `apps/meta-agent/src/tools/write_ops.py`

### stop_tenant()
```python
# Añadir después de stop de hermes-{code}:
try:
    c.containers.get(f"pb-{tenant_code}").stop(timeout=10)
    steps.append("pb_stopped")
except NotFound:
    pass  # PocketBase no existía, no es error
```

### restart_tenant()
```python
# Añadir:
try:
    c.containers.get(f"pb-{tenant_code}").restart(timeout=10)
    steps.append("pb_restarted")
except NotFound:
    pass  # PocketBase no desplegado todavía, ok
```

### delete_tenant()
```python
# Añadir antes de rmtree del volumen:
try:
    pb = c.containers.get(f"pb-{tenant_code}")
    pb.stop(timeout=5)
    pb.remove(force=True)
    steps.append("pb_container_removed")
except NotFound:
    pass
```

---

## G4 — `deploy_pocketbase_tenant()` — para tenants existentes (t001)

**Archivo**: `apps/meta-agent/src/tools/write_ops.py` (nueva función, registrar en operador.py)

```python
@tool
def deploy_pocketbase_tenant(tenant_code: str, slug: str) -> str:
    """Despliega PocketBase CRM para un tenant que ya existe sin PocketBase.

    Usado para:
    - Tenants creados antes del Sprint G (ej: t001)
    - Casos donde el container de PocketBase fue eliminado accidentalmente

    Pasos:
    1. Verifica que hermes-{code} existe y está healthy
    2. Crea pb_data/ y pb_migrations/ en el volumen si no existen
    3. Copia las migration templates
    4. Arranca el container pb-{code} con las mismas specs que create_tenant()
    5. Configura Traefik labels para {slug}.martes.app
    6. Crea superadmin, genera token, escribe en .env
    7. Actualiza slug en DB (tenants.slug = slug)
    8. Reinicia hermes-{code} para cargar POCKETBASE_URL y POCKETBASE_TOKEN
    9. Instala skill crm-pocketbase en el volumen del tenant

    Requiere aprobación — crea un container nuevo.
    """
```

---

## G5 — Skill CRM template

**Archivo nuevo**: `infra/templates/skills/crm-pocketbase/SKILL.md`

```markdown
---
name: crm-pocketbase
description: CRM personal del negocio via PocketBase. Gestiona contactos,
  conversaciones, inventario, pedidos y calendario desde el chat.
version: 1.0.0
author: martes.app
---

# CRM Personal — martes.app

Tu CRM está en http://pb-{TENANT_CODE}:8090 (accesible dentro del container).
Tu API token está en POCKETBASE_TOKEN (cargado desde .env).

## Colecciones disponibles

- contactos — clientes del negocio
- conversaciones — historial de mensajes por canal
- productos — inventario con stock y precios
- pedidos — órdenes con estado y método de pago
- pagos — confirmaciones de pago con comprobante
- calendario — citas, entregas, recordatorios

## Cómo guardar una conversación

Cuando un cliente envía un mensaje por WhatsApp o Telegram, guárdalo:

```bash
curl -s -X POST "$POCKETBASE_URL/api/collections/conversaciones/records" \
  -H "Authorization: Bearer $POCKETBASE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "contacto": "[ID_DEL_CONTACTO o null si es nuevo]",
    "canal": "telegram",
    "mensaje": "[TEXTO]",
    "direccion": "entrante"
  }'
```

## Cómo registrar un pedido

```bash
curl -s -X POST "$POCKETBASE_URL/api/collections/pedidos/records" \
  -H "Authorization: Bearer $POCKETBASE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "contacto": "[ID]",
    "items": [{"nombre": "[PRODUCTO]", "qty": 1, "precio_usd": 75}],
    "total_usd": 75,
    "estado": "pendiente_pago",
    "metodo_pago": "pago_movil"
  }'
```

## Cuándo usar el CRM

- Siempre que un cliente haga una consulta → buscar si existe en contactos
- Cuando hay una venta → crear pedido en pedidos
- Cuando el cliente confirma el pago → actualizar estado del pedido
- Cuando queda poco stock → el dueño puede verlo en la PWA
```

**Cómo se instala**: `create_tenant()` copia automáticamente `infra/templates/skills/crm-pocketbase/` al volumen del tenant en `{tenant_path}/skills/crm-pocketbase/`. Hermes lo descubre al arrancar.

---

## G6 — Migration templates PocketBase

**Archivos nuevos**:
- `infra/templates/pocketbase/migrations/1_crm_schema.js`
- `infra/templates/pocketbase/migrations/2_hermes_token.js`

El schema completo de las 6 colecciones está documentado en `docs/hermes-guia/07-POCKETBASE-CRM-INVESTIGACION.md` sección 3.

---

## Orden de implementación recomendado

```
1. Mergear PR #74 (paradigma + home channel fix)
   → base limpia

2. Sprint G1 — DB migration 003
   → archivo SQL, sin código Python todavía
   → Se aplica en producción al redeploy del compose

3. Sprint G2a+b — create_tenant() fixes + slug
   → pids/tmpfs fixes
   → slug en Pydantic + DB

4. Sprint G3 — Templates PocketBase (migrations + skill)
   → archivos en infra/templates/

5. Sprint G4 — PocketBase sidecar en create_tenant()
   → el bloque grande de código

6. Sprint G5 — Lifecycle updates (stop/restart/delete)
   → 3 funciones actualizadas

7. Sprint G6 — deploy_pocketbase_tenant() para t001
   → tool del Operador + update operador.py

8. Operacional: DNS wildcard *.martes.app
   → Antes de cualquier prueba en producción

9. Preview + test en VPS con un tenant de prueba
   → No en t001 directamente
```

---

## Notas de implementación importantes

### PocketBase image tag
Usar tag fijo, no `latest`:
```python
image="ghcr.io/pocketbase/pocketbase:0.23.6"  # último estable junio 2026
```

### El token de PocketBase en `.env`
El `.env` tendrá dos vars nuevas:
```
POCKETBASE_URL=http://pb-t001:8090
POCKETBASE_TOKEN=pb_admin_token_xxx
```
Hermes las lee automáticamente en cada turno. La skill `crm-pocketbase` las usa en sus llamadas `curl`. El cliente no necesita saber que existen.

### Compatibilidad con tenants sin PocketBase
`stop_tenant()`, `restart_tenant()`, `delete_tenant()` — todos los bloques de PocketBase van en `try/except NotFound: pass`. Si el tenant fue creado antes del Sprint G, simplemente no hay container pb-{code} y las funciones siguen funcionando igual.

### No romper t001
t001 actualmente no tiene PocketBase. Seguirá funcionando igual hasta que el admin ejecute `deploy_pocketbase_tenant("t001", "acme")` explícitamente.
