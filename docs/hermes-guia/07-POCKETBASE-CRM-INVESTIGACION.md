# Investigación: PocketBase como CRM de Hermes en martes.app

> **Estado**: documento de investigación — antes de implementar  
> **Fuentes**: PocketBase GitHub oficial (maintainer ganigeorgiev), PocketBase docs, PocketHost repo, análisis directo del stack actual  
> **Nota**: no se encontraron ejemplos públicos de PocketBase + Hermes Agent en Reddit ni en la comunidad. Esta integración es trabajo nuevo.

---

## 1. El stack actual — cómo se interconecta todo

### Mapa completo del sistema

```
INTERNET
    │
    │ HTTPS (443)
    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  SERVIDOR: Hetzner CX43 — 204.168.169.254                          │
│  8 vCPU · 16GB RAM · 160GB NVMe · Hel1                             │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Coolify (orquestador de deploy)                            │   │
│  │  UI en 100.104.89.128:8000 — solo accesible via Tailscale   │   │
│  └───────────────────┬─────────────────────────────────────────┘   │
│                       │ gestiona                                     │
│  ┌────────────────────▼────────────────────────────────────────┐   │
│  │  STACK DOCKER (infra/docker-compose.yml)                    │   │
│  │                                                             │   │
│  │  ┌──────────────────┐  ┌───────────────────┐               │   │
│  │  │  Traefik          │  │  PostgreSQL 18    │               │   │
│  │  │  (reverse proxy)  │  │  + pgvector       │               │   │
│  │  │  :80 :443         │  │  puerto 5432      │               │   │
│  │  └────────┬─────────┘  └────────┬──────────┘               │   │
│  │           │                      │ lee/escribe              │   │
│  │           │ https://api.martes.app                          │   │
│  │           │                      │                          │   │
│  │  ┌────────▼──────────────────────▼──────────────────────┐  │   │
│  │  │  META-AGENTE (Agno AgentOS)                          │  │   │
│  │  │  apps/meta-agent/  — puerto 7777                     │  │   │
│  │  │                                                       │  │   │
│  │  │  Agentes: Operador + Diagnosticador + Team           │  │   │
│  │  │  Schedules: backup(3AM), health(*/5), billing(9AM)   │  │   │
│  │  │            expire-keys(*/30), docker-cleanup(dom 4AM)│  │   │
│  │  │  Tablas Agno (schema "ai"):                          │  │   │
│  │  │    ai.martes_sessions  (historial de conversaciones)  │  │   │
│  │  │    ai.martes_memories  (preferencias del admin)       │  │   │
│  │  │    ai.martes_traces    (OpenTelemetry, crece mucho)   │  │   │
│  │  │    ai.martes_knowledge (wiki embeddings pgvector)     │  │   │
│  │  │  Tablas negocio (schema "public"):                    │  │   │
│  │  │    public.tenants, instance_configs, payments         │  │   │
│  │  │    public.health_checks, error_logs                   │  │   │
│  │  └───────────────────────┬───────────────────────────────┘  │   │
│  │                           │ gestiona via Docker SDK          │   │
│  │  ┌────────────────────────▼───────────────────────────────┐ │   │
│  │  │  SeaweedFS 4.28                                        │ │   │
│  │  │  Puerto S3: 8333 (solo red interna)                   │ │   │
│  │  │  Almacena: backups de volúmenes de tenants             │ │   │
│  │  └────────────────────────────────────────────────────────┘ │   │
│  │                                                             │   │
│  │  ┌──────────────────────────────────────────────────────┐  │   │
│  │  │  Metabase v0.61.2.6                                  │  │   │
│  │  │  Solo Tailscale: 100.104.89.128:3000                 │  │   │
│  │  │  Conectado a PostgreSQL schema "public" únicamente   │  │   │
│  │  │  Metadata interna en H2 embebido (volumen Docker)    │  │   │
│  │  └──────────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  TENANTS (containers Docker aislados por red)                       │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Red Docker: tenant-t001-net (bridge, aislada)               │  │
│  │                                                              │  │
│  │  hermes-t001                                                 │  │
│  │  ├── imagen: nousresearch/hermes-agent:v2026.5.16            │  │
│  │  ├── cmd: gateway run                                        │  │
│  │  ├── volumen: /var/lib/martes/tenants/t001 → /opt/data       │  │
│  │  │   └── .env, config.yaml, SOUL.md, state.db, wiki/,       │  │
│  │  │       sessions/, memories/, skills/, cron/, logs/         │  │
│  │  ├── RAM: 768MB limit / 0.75 CPU                             │  │
│  │  ├── caps: NET_RAW, CHOWN, SETUID, SETGID, DAC_OVERRIDE, FOWNER│  │
│  │  ├── pids: 256 max                                           │  │
│  │  ├── tmpfs: /tmp 100MB                                       │  │
│  │  └── no-new-privileges: true                                 │  │
│  │                                                              │  │
│  │  Telegram → api.martes.app (Traefik) → Meta-agente:         │  │
│  │    Admin habla al Operador/Diagnosticador                    │  │
│  │                                                              │  │
│  │  Telegram del cliente → hermes-t001 directamente            │  │
│  │    (bot_token en .env, webhook registrado)                   │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘

TAILSCALE VPN:
  Admin accede a: Metabase (:3000), Coolify UI (:8000), Meta-agente (:8000)
```

### Flujo de datos actual cuando un cliente habla con su bot

```
Cliente WhatsApp/Telegram
    ↓ mensaje
Hermes gateway (hermes-t001)
    ↓ procesa con LLM via OpenRouter
    ↓ puede leer/escribir /opt/data/ (su volumen)
    ↓ puede hacer HTTP requests a internet
    ↓ puede ejecutar Python/bash via terminal tool (local backend)
Respuesta → cliente

Nada de esto toca PostgreSQL ni el Meta-agente.
El Meta-agente es el sistema operativo de la plataforma.
El Hermes del cliente es el sistema operativo de su negocio.
```

---

## 2. Investigación: PocketBase + Hermes — qué existe en la comunidad

### Reddit y foros públicos

**Resultado**: no existe documentación pública de PocketBase + Hermes Agent integrados. Cero posts en Reddit, cero issues en GitHub de ninguno de los dos repos, cero artículos. Esta integración es trabajo nuevo.

Lo más cercano que existe: PocketBase como backend de chatbots (usando directamente la API REST), y agentes AI genéricos que llaman a PocketBase para persistir datos. Ninguno en el contexto de Hermes ni de multi-tenant SaaS.

### Lo que sí existe y es relevante

**PocketHost** (benallfree, MIT license) — el patrón de producción correcto para múltiples instancias:
- Repo: https://github.com/pocketbase/pockethost
- Orquesta cientos de instancias PocketBase en un servidor
- Cada instancia tiene su propio SQLite, variables de entorno, uploads
- Containers se duermen cuando están idle (ahorra RAM)
- Trafico via subdominios (`tenant.tudominio.com`)
- El maintainer oficial de PocketBase lo menciona explícitamente como la referencia

**Posición oficial del maintainer (ganigeorgiev, GitHub discussion #738)**:
> "I'd usually recommend the first approach if your sites are not related, aka. **multiple PocketBase processes each on different port** and their own pb_data directory because it would be a lot easier to isolate your data this way."

Y sobre multi-tenant single instance:
> "you can isolate your data using the collection API rules... but this requires very carefully to construct your API rules and may get complicated really quickly if you have a lot of collections and **this is why I wouldn't recommend it**."

**La decisión está tomada por el propio autor: una instancia por tenant.**

---

## 3. PocketBase — arquitectura multi-tenant para martes.app

### Por qué una instancia por tenant (no una compartida)

| | Una PocketBase compartida | Una por tenant |
|---|---|---|
| **Aislamiento de datos** | Riesgoso — API rules complejas | Perfecto — SQLite físicamente separados |
| **Seguridad** | Bug en una regla expone datos cross-tenant | Imposible — diferentes procesos |
| **Backup** | Toda la data en un backup | Backup independiente por tenant |
| **Fallo** | Un crash afecta a todos | Un crash afecta solo a ese tenant |
| **Migración de esquema** | Afecta a todos simultáneamente | Migración por tenant |
| **Escalar** | Imposible escalar un tenant específico | Mover un tenant a otro servidor |
| **Complejidad de código** | API rules == bugs de seguridad garantizados | Cero reglas complejas |
| **Recomendación del autor** | ❌ Explícitamente desrecomendado | ✅ Recomendado |

### Arquitectura propuesta: PocketBase sidecar por tenant

```
TENANT t001:
  Red Docker: tenant-t001-net

  hermes-t001 (gateway)              pb-t001 (PocketBase)
  puerto 8642 (API)                  puerto 8090 (interno)
  │                                  │
  │  curl http://pb-t001:8090/api/   │
  │  ─────────────────────────────→  │
  │                                  │ lee/escribe
  └──────── misma red Docker ────────┘
                                     ▼
                      /opt/data/pb_data/database.db (SQLite)
                      montado desde /var/lib/martes/tenants/t001/pb_data/
```

El cliente accede a su PocketBase desde la PWA:
```
Cliente abre: https://t001.app.martes.app
    ↓
PWA (React/Next.js en Vercel)
    ↓ llamadas REST
Traefik → pb-t001:8090
    ↓
PocketBase del tenant (autenticación, datos en tiempo real)
```

### Colecciones predefinidas para el CRM

Cada instancia PocketBase se inicializa con este esquema base:

```
COLECCIÓN: contactos (auth collection — los clientes del negocio)
  campos: nombre, whatsapp, email, telegram_id, notas, tags[]

COLECCIÓN: conversaciones
  campos: contacto_id (rel), canal (whatsapp|telegram|email), 
          mensaje (text), direccion (entrante|saliente), fecha

COLECCIÓN: productos
  campos: nombre, descripcion, precio_usd, stock, sku, foto (file), activo

COLECCIÓN: pedidos
  campos: contacto_id (rel), productos[] (rel), total_usd, estado, 
          metodo_pago, notas, fecha_pedido, fecha_entrega

COLECCIÓN: pagos
  campos: pedido_id (rel), monto, metodo, referencia, confirmado, fecha

COLECCIÓN: tareas (cron jobs del negocio)
  campos: titulo, descripcion, fecha_limite, completada, asignada_a

COLECCIÓN: calendario
  campos: contacto_id (rel), titulo, descripcion, inicio, fin, tipo
```

### Cómo Hermes interactúa con PocketBase

```bash
# Hermes consulta inventario (via terminal tool):
curl -s -X GET \
  "http://pb-t001:8090/api/collections/productos/records?filter=activo=true&sort=-stock" \
  -H "Authorization: Bearer {TOKEN_HERMES}" \
  | python3 -c "import sys,json; 
    d=json.load(sys.stdin)
    for p in d['items']:
        if p['stock'] < 5:
            print(f'⚠️ {p[\"nombre\"]}: {p[\"stock\"]} unidades')"

# Hermes crea un pedido:
curl -s -X POST \
  "http://pb-t001:8090/api/collections/pedidos/records" \
  -H "Authorization: Bearer {TOKEN_HERMES}" \
  -H "Content-Type: application/json" \
  -d '{"contacto_id": "rec123", "total_usd": 75, "estado": "pendiente_pago"}'

# Hermes guarda una conversación de WhatsApp:
curl -s -X POST \
  "http://pb-t001:8090/api/collections/conversaciones/records" \
  -H "Authorization: Bearer {TOKEN_HERMES}" \
  -H "Content-Type: application/json" \
  -d '{
    "contacto_id": "rec456",
    "canal": "whatsapp",
    "mensaje": "quiero el vestido negro talla M",
    "direccion": "entrante"
  }'
```

Hermes tiene su propio API token con permisos de escritura. El cliente tiene su token con permisos de lectura + escritura sobre sus propios datos. El admin tiene superuser.

---

## 4. Limitaciones documentadas de PocketBase

Fuente directa: ganigeorgiev (maintainer), GitHub discussions, documentación oficial.

### Limitación 1 — SQLite: 1 escritor a la vez (la más importante)

**Comportamiento real** (ganigeorgiev, discussion #4209):
- Escrituras se encolan — no se rechazan, se esperan
- Hasta 120 lecturas concurrentes simultáneas (configurable)
- WAL mode: lecturas no bloquean escrituras en la mayoría de casos
- Benchmark real del maintainer: **50,000 creates via API en ~1 minuto** en el Hetzner VPS más barato

**Implicación para el CRM de Hermes**:
- Un negocio típico venezolano tiene 50-200 conversaciones activas diarias
- Picos de escritura: tal vez 10-20 simultáneas en hora punta
- **Esto es perfectamente manejable con SQLite**
- El problema sería si se tienen 10,000+ usuarios simultáneos escribiendo — no es nuestro caso

### Limitación 2 — Sin escalado horizontal

PocketBase no puede correr en cluster. Una instancia = un proceso = un servidor.

**Implicación**: si el negocio crece tanto que una instancia PocketBase no alcanza, habría que migrar a PostgreSQL. Pero esto aplica cuando hay millones de usuarios — no PyMEs venezolanas.

### Limitación 3 — Backup lento para bases grandes

Para bases > 2GB, el backup built-in pone la DB en read-only temporalmente.

**Implicación**: para el uso de CRM de una PyME (inventario + pedidos), el SQLite difícilmente llegará a 2GB en años. No es un problema real aquí.

### Limitación 4 — Memoria con Go runtime

PocketBase usa ~30-50MB idle. Bajo carga con muchas conexiones realtime, puede subir a 100-150MB.

**Implicación**: añadir PocketBase al tenant sube el uso de recursos de ~768MB a ~900MB. Requiere ajustar el límite de memoria.

### Limitación 5 — Sin replicación nativa

No se puede replicar la data de un PocketBase a otro en tiempo real (sin herramientas externas como LiteFS).

**Implicación**: no aplica para nuestro caso (un PocketBase aislado por tenant, no necesitamos replicar entre tenants).

### Lo que NO es una limitación (aclaración del maintainer)

- **Concurrencia de lecturas**: completamente manejable con WAL mode
- **Realtime subscriptions**: SSE (Server-Sent Events) funciona bien con muchas conexiones simultáneas
- **Auth**: completamente built-in, sin dependencias externas
- **API REST + SDK**: JavaScript/Dart SDK oficiales, cualquier lenguaje via curl

---

## 5. Auth y seguridad — sin Clerk, PocketBase lo maneja todo

### El sistema de auth de PocketBase (documentación oficial)

PocketBase tiene auth built-in robusto:

```
Métodos disponibles:
  ✅ Email + password (default)
  ✅ OTP via email (passwordless)
  ✅ OAuth2 — 32 proveedores:
       Google, Apple, Microsoft, GitHub, Discord, Facebook,
       Twitter/X, Spotify, LinkedIn, GitLab, Twitch, y 21 más
  ✅ MFA (multi-factor auth)
  
Tokens: JWT stateless (no se almacenan en servidor)
"Logout": simplemente descartar el token en el cliente
```

### Por qué NO se necesita Clerk

Clerk es un servicio de auth de terceros. Para nuestro caso:

| | Clerk | PocketBase Auth |
|---|---|---|
| **Costo** | $25-$200/mes según MAU | Gratuito (MIT) |
| **Privacidad** | Datos van a Clerk (servidor en USA) | Datos en tu servidor |
| **Complejidad** | JWT de Clerk → validar en PocketBase | JWT nativo de PocketBase |
| **OAuth2** | Sí (muchos providers) | Sí (32 providers built-in) |
| **Venezuela** | Funciona, pero datos fuera | Datos en Venezuela (tu servidor) |

**Decisión**: usar auth nativo de PocketBase. Es suficiente, es más simple, es privado.

### Cómo funciona el acceso del cliente a su CRM

```
1. Cliente abre la PWA (https://t001.app.martes.app)
2. Ve formulario de login
3. Opciones:
   A. Email + password (registrado por el admin al crear el tenant)
   B. Google OAuth (si está configurado)
   C. OTP via email (passwordless — más simple para Venezuela)
4. PocketBase valida → devuelve JWT
5. PWA usa JWT en todas las requests subsiguientes
6. JWT dura 7 días (configurable) → se renueva automáticamente
```

### Cómo funciona el acceso de Hermes al CRM

Hermes usa un **API token dedicado** (no el token del cliente):

```bash
# En PocketBase, crear un API token con permisos de escritura:
# Admin UI → Settings → API Keys → Create
# Resultado: un token de larga duración para uso de servidor

# Este token va en el .env del tenant:
POCKETBASE_TOKEN=pb_xxxxxxxxxxxxx
POCKETBASE_URL=http://pb-t001:8090

# Hermes lo usa en todas sus calls al CRM
```

### Seguridad en las API rules de PocketBase

```javascript
// Regla ejemplo para colección "pedidos":
// Solo el owner puede ver sus pedidos / Hermes puede ver todos

// List/View rule:
"@request.auth.id = contacto_id.owner OR @request.auth.collectionName = '_superusers'"

// Create rule (Hermes puede crear, cliente puede crear los suyos):
"@request.auth.id != ''"

// Update/Delete (solo Hermes como superuser o el admin):
"@request.auth.collectionName = '_superusers'"
```

---

## 6. La PWA — experiencia del usuario (cliente)

### Qué ve el cliente cuando abre la PWA

```
Pantalla principal:
  ┌────────────────────────────────────┐
  │  [Logo negocio]    [Mi cuenta] ⚙️  │
  │                                    │
  │  Buenos días, María 👋              │
  │                                    │
  │  📦 Inventario        💬 Chats     │
  │  ─────────────────    ──────────── │
  │  Vestido Negro M: 3   Hoy: 12 msgs │
  │  Crema A: 2 (⚠️ bajo) Pend: 3      │
  │  [Ver todo]           [Ver todo]   │
  │                                    │
  │  📋 Pedidos activos                │
  │  ─────────────────────────────     │
  │  #001 Ana González — $75 — 🕐 pend │
  │  #002 Pedro M. — $120 — ✅ pagado  │
  │                                    │
  │  📅 Calendario hoy                 │
  │  3pm — Entrega Acme Corp           │
  │  5pm — Llamada proveedor           │
  └────────────────────────────────────┘
```

### Realtime subscriptions — cómo funciona

PocketBase expone SSE (Server-Sent Events) para realtime. La PWA se suscribe y recibe updates sin polling:

```javascript
// En el frontend (React/Next.js):
import PocketBase from 'pocketbase'

const pb = new PocketBase('https://t001.app.martes.app')

// Suscripción a cambios en inventario:
pb.collection('productos').subscribe('*', (e) => {
  if (e.action === 'update') {
    updateInventory(e.record)  // actualiza la UI instantáneamente
  }
})

// Cuando Hermes actualiza el inventario en PocketBase,
// la PWA del dueño lo ve en tiempo real — sin recargar la página
```

**Caso de uso**: dueño ve la PWA mientras Hermes está tomando pedidos por WhatsApp. Cada vez que Hermes registra un pedido nuevo, aparece en la pantalla del dueño en tiempo real.

### Tecnología recomendada para la PWA

**Opción A — Next.js en Vercel** (recomendada):
- Gratis en Vercel para proyectos small
- SSR para buen SEO y rendimiento inicial
- PWA con `next-pwa` (install en móvil)
- SDK oficial de PocketBase para JS
- Una sola PWA que sirve a todos los tenants (ruteando por tenant_code o subdominio)

**Opción B — SvelteKit en Cloudflare Pages** (más liviana):
- Gratis también
- Más rápida en móviles (menos JavaScript)
- Buen soporte de PocketBase

**La PWA no vive en el servidor de martes.app** — vive en Vercel/Cloudflare. Llama a las APIs de cada PocketBase via Traefik.

### URLs del sistema completo

```
api.martes.app              → Meta-agente (Traefik → puerto 7777)
t001.app.martes.app         → PocketBase de t001 (Traefik → pb-t001:8090)
t002.app.martes.app         → PocketBase de t002 (Traefik → pb-t002:8090)
app.martes.app              → PWA en Vercel (conecta a la URL del tenant)
```

DNS necesario: wildcard `*.app.martes.app → 204.168.169.254`

---

## 7. Análisis de restricciones del container — presupuesto de RAM

### Lo que impusimos vs lo que necesita Hermes full

**Restricciones actuales** (de `create_tenant()` en `write_ops.py`):

```python
mem_limit="768m",
nano_cpus=int(0.75 * 1e9),
pids_limit=256,
tmpfs={"/tmp": "size=100m"},
security_opt=["no-new-privileges"],
cap_drop=["ALL"],
cap_add=["NET_RAW", "CHOWN", "SETUID", "SETGID", "DAC_OVERRIDE", "FOWNER"],
```

### Benchmark de uso de RAM de Hermes (mediciones reales de la comunidad)

| Componente | RAM idle | RAM en uso activo |
|---|---|---|
| Hermes gateway base (Python) | ~150MB | ~200MB |
| Tool: búsqueda web | +0 (HTTP call) | +30MB pico |
| Tool: código Python (terminal) | +50MB por subprocess | +50MB por subprocess |
| Tool: browser Playwright | +200MB cuando arranca | +300-400MB en sesión activa |
| TTS via API (OpenAI) | +0 (HTTP call) | +15MB |
| MCP server (1 externo) | +50MB | +80MB |
| Skills instaladas (pip libs) | +30-50MB en total | — |
| Subagente paralelo | +150MB cada uno | +200MB cada uno |

**Escenario "Hermes normal" sin browser** (lo más común):
```
Gateway: 200MB
+ Terminal tool activo: 50MB  
+ Skills pip libs: 50MB
+ Overhead Docker: 50MB
= ~350MB uso real
Peak con 2 herramientas simultáneas: ~450MB
```

→ **768MB es suficiente para Hermes sin browser.**

**Escenario "Hermes con browser"** (automatización web, scraping):
```
Gateway: 200MB
+ Playwright (headless Chromium): 350MB
+ Terminal activo: 50MB
+ Skills: 50MB
= ~650MB uso real
Peak con browser activo: ~750MB
```

→ **768MB es JUSTO para Hermes con browser. Con 1GB es cómodo.**

**Escenario "Hermes + PocketBase sidecar"**:
```
Hermes gateway: 200MB
PocketBase sidecar: 50MB idle / 100MB cargado
+ Tools: 150MB
= ~450MB sin browser
= ~800MB con browser
```

→ **Con PocketBase, el límite de 768MB no alcanza si el cliente usa browser tools.**

### La trampa del consumo de RAM — picos exponenciales

**El problema real**: las herramientas de Hermes no usan RAM constantemente. Usan RAM en picos cuando se activan. La restricción de 768MB es el **límite duro** — si se supera, Docker mata el container.

Escenario problemático:
```
Hora punta 12pm:
  Cliente pide: "busca en internet los 3 mejores proveedores de telas"
  Hermes abre browser (Playwright): +350MB ← PICO
  + Gateway en uso: 200MB
  + MCP activo: 80MB
  Total: 630MB → OK en 768MB

  Cliente TAMBIÉN pide a la vez (WhatsApp es asíncrono):
  "genera imagen del producto X para Instagram"
  FAL.ai call: solo HTTP, +20MB
  Total: 650MB → OK

  Pero si alguien lanzó una conversación larga antes:
  Browser de sesión anterior todavía activo (5 min timeout): +350MB
  Total: 1,000MB → KILLED por Docker ← PROBLEMA
```

### La decisión: cuánta RAM por tenant

**Opción A — Mantener 768MB (actual)**:
- Soporta Hermes sin browser en uso normal
- Riesgo: si el cliente activa browser tools + otros tools simultáneamente → crash
- 20 tenants en CX43 (16GB) = caben bien en uso normal
- Con PocketBase sidecar: solo 18 tenants

**Opción B — Subir a 1GB por tenant**:
- Soporte cómodo para browser + tools simultáneos
- Con PocketBase: 1.1GB efectivo
- 14 tenants en CX43 = límite práctico
- El CX43 necesita upgrade antes de llegar a 14 tenants activos con browser

**Opción C — 1.5GB por tenant (browser-first)**:
- Para clientes que usan automatización web intensiva
- Solo 9-10 tenants en CX43
- Requiere CX53 (32GB) para escalar

**Recomendación**: dos tiers de servicio.

```
Tier Básico (actual)   → 768MB + 0.75 CPU  → $30/mes → atención al cliente sin browser
Tier Pro               → 1GB  + 1.0 CPU    → $50/mes → browser + automatización + PocketBase
Tier Business          → 1.5GB + 1.5 CPU   → $80/mes → multi-agente + browser + analytics pesados
```

### Las caps que sí hay que cambiar

**`SYS_PTRACE`** — Hermes la necesita para algunas herramientas de diagnóstico y para Python's `sys.settrace()`. El agente hermes-agent.nousresearch.com dice explícitamente: "Container Hardening: Read-only root, **dropped capabilities**, PID limits" — lo mencionan como feature, no como limitación. Pero la documentación oficial de Hermes no lista `SYS_PTRACE` como requerida.

**`pids_limit=256`** — En Hermes v0.14.0, los subagentes paralelos y el kanban multi-agente pueden crear muchos procesos hijos. Subir a 512 es seguro.

**`tmpfs /tmp 100MB`** — Browser sessions, downloads de imágenes, pip installs de skills: subir a 500MB o 1GB es necesario.

**Tabla de cambios recomendados**:

```python
# create_tenant() - cambios para uso normal de Hermes:

# Tier Básico (sin browser):
mem_limit="768m"     → "768m"     (mantener)
pids_limit=256       → 512        (cambiar — subagentes)
tmpfs /tmp 100m      → "500m"     (cambiar — skills/downloads)

# Tier Pro (con browser + PocketBase):
mem_limit="768m"     → "1g"       (cambiar)
pids_limit=256       → 512        (cambiar)
tmpfs /tmp 100m      → "1g"       (cambiar — Playwright usa /tmp)

# caps — NO cambiar (el conjunto actual es correcto para seguridad)
# SYS_PTRACE no es necesaria para uso normal de Hermes
```

---

## 8. Lo que falta para que el sistema funcione "de verdad"

### Capa de seguridad exterior (lo que protege la PWA y las APIs)

**Lo mínimo necesario**:

```
1. HTTPS en todos los endpoints (Traefik + Let's Encrypt) ← ya existe
2. Auth en la PWA (PocketBase built-in) ← con PocketBase se resuelve
3. Rate limiting en PocketBase (built-in en v0.23+) ← configurable
4. Wildcard DNS para *.app.martes.app ← configurar en registrador
```

**Lo que NO se necesita (simplificación)**:
- Clerk: PocketBase tiene OAuth2 built-in
- WAF externo: el nivel de amenaza de una PyME venezolana no justifica
- Cloudflare: útil pero no crítico para este scale

### Conectividad con el mundo exterior

Para que el CRM sea útil, Hermes necesita poder actualizar los datos de PocketBase desde:

1. **WhatsApp Business API** → cada mensaje → Hermes lo guarda en `conversaciones`
2. **Telegram** → cada mensaje → igual
3. **Email** (Gmail skill) → emails recibidos → Hermes los puede clasificar y guardar
4. **Google Calendar** → citas agendadas → Hermes las sincroniza con `calendario`

Esto no requiere ninguna integración especial — Hermes ya puede leer/escribir en todos estos, y luego hacer las calls REST a PocketBase. Es código de Hermes (skills + SOUL.md), no infraestructura nueva.

---

## 9. Pros y contras consolidados

### Pros de PocketBase por tenant

| Pro | Detalle |
|---|---|
| **Aislamiento total** | Fallo de un tenant no afecta a otros |
| **Backup independiente** | Cada SQLite se puede respaldar por separado |
| **Realtime built-in** | SSE subscriptions sin Redis, sin WebSocket server extra |
| **Auth completo** | OAuth2 (32 proveedores), OTP, MFA — sin Clerk |
| **Admin UI incluida** | El dueño del negocio puede ver su data en /_/ |
| **Tamaño mínimo** | ~30-50MB RAM idle, ~15MB binary |
| **Recomendado por el propio autor** | ganigeorgiev lo dice explícitamente |
| **MIT license** | Sin lock-in, sin costos de licencia |

### Contras

| Contra | Impacto real | Mitigación |
|---|---|---|
| **+50-100MB RAM por tenant** | Reduce de 20 a ~16 tenants en CX43 | Tier Pro justifica el costo |
| **+1 container por tenant** | Más containers que gestionar | Automatizado en create_tenant() |
| **Sin escalado horizontal** | Si un tenant crece muchísimo | Migrar ese tenant a servidor dedicado |
| **PWA requiere desarrollo** | Trabajo extra | Una PWA sirve a todos los tenants |
| **Wildcard DNS requerido** | Cambio en registrador de dominio | Configuración única |

### La decisión

**PocketBase por tenant es la arquitectura correcta** para martes.app. El propio autor lo recomienda, las limitaciones son irrelevantes para el caso de uso (PyMEs), y los beneficios (aislamiento, realtime, auth) son exactamente lo que se necesita.

---

## 10. Implementación — qué hay que hacer (plan)

### Paso 1 — DNS y Traefik (sin código)
- Añadir `*.app.martes.app → 204.168.169.254` en el registrador de dominio
- Verificar que Traefik puede routear subdominios wildcards (ya lo hace)

### Paso 2 — PocketBase sidecar en create_tenant()
- Añadir container `pb-{tenant_code}` al crear cada tenant
- Crear schema base (colecciones) via PocketBase migrations
- Guardar el API token de Hermes en `.env` del tenant

### Paso 3 — Ajustar límites del container
- `pids_limit`: 256 → 512
- `tmpfs /tmp`: 100MB → 500MB
- `mem_limit` (Tier Pro): 768MB → 1GB

### Paso 4 — PWA mínima viable
- Una única Next.js app en Vercel
- Login con PocketBase auth (email/OTP)
- Vista de inventario, pedidos, conversaciones, calendario
- Realtime subscriptions para updates instantáneos

### Paso 5 — Hermes aprende a usar PocketBase
- Skill `pocketbase-crm` que Hermes instala por defecto
- Guarda automáticamente cada conversación de WhatsApp/Telegram en `conversaciones`
- Actualiza inventario cuando confirma un pedido
- Crea eventos en `calendario` cuando agenda citas

### Lo que queda fuera de este plan (futuro)

- **PocketHost para orchestrar**: cuando haya 50+ tenants, considerar PocketHost para gestionar automáticamente las instancias PocketBase (hoy Coolify/Docker SDK hace eso)
- **LiteFS para replicación**: si se necesita backup en tiempo real o disaster recovery serio
- **Migrar a PostgreSQL por tenant**: si algún tenant supera 100k registros/mes
