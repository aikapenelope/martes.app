# Hermes Tenants — Arquitectura, Configuración y Capacidad

> Documento de referencia para operar tenants Hermes en martes.app.
> Fuente: repositorio oficial https://github.com/nousresearch/hermes-agent (v0.14.0, mayo 2026)

---

## 1. Qué es Hermes v0.14.0

Hermes es un agente IA auto-mejorante construido por Nous Research. En la versión 0.14.0
("The Foundation Release") se convirtió en un paquete PyPI (`pip install hermes-agent`)
con soporte nativo para 22 plataformas de mensajería, lazy-install de dependencias pesadas,
y ~19 segundos menos de cold start.

Cada tenant de martes.app es **un container Hermes aislado**, con su propio volumen de datos,
su propio bot de Telegram, y su propio contexto de memoria y skills.

---

## 2. Arquitectura del container

### Estructura de la imagen

```
/opt/hermes/          ← código fuente de Hermes (read-only en runtime)
  .venv/              ← Python venv con dependencias
  skills/             ← skills bundled de fábrica (sync'd al arranque)
  docker/
    entrypoint.sh     ← bootstrap: uid remap + chown + seed de defaults
    SOUL.md           ← personalidad por defecto (vacía, para personalizar)

/opt/data/            ← VOLUME: datos del tenant (montado desde el host)
  config.yaml         ← configuración del agente (creada desde template al primer boot)
  .env                ← API keys (permisos 600, creada desde .env.example)
  SOUL.md             ← personalidad del agente (creada desde docker/SOUL.md)
  state.db            ← SQLite: sesiones, historial FTS5, mensajes
  memories/
    MEMORY.md         ← notas del agente (auto-gestionadas, bounded)
    USER.md           ← perfil del usuario (auto-gestionado, bounded)
  sessions/           ← historial JSON de conversaciones
  skills/             ← skills creados por el agente (y skills instalados)
  wiki/               ← LLM Wiki: base de conocimiento editable
  cron/               ← jobs programados (jobs.json + outputs)
  logs/               ← logs del gateway
  workspace/          ← directorio de trabajo del agente
  home/               ← HOME para subprocesos (git, ssh, npm)
  auth.json           ← OAuth credentials (si usa Nous Portal)
  .install_method     ← "docker" (escrito por entrypoint)
```

### Proceso de arranque (`entrypoint.sh`)

1. **UID remap**: si `HERMES_UID` difiere del UID interno (10000), hace `usermod` + `chown -R`
2. **Permisos**: `chown hermes:hermes` sobre `config.yaml` y `.venv`
3. **Bootstrap de defaults** (solo si no existen en el volumen):
   - `.env` ← copia de `.env.example`
   - `config.yaml` ← copia de `cli-config.yaml.example`
   - `SOUL.md` ← copia de `docker/SOUL.md`
4. **`auth.json`**: si `HERMES_AUTH_JSON_BOOTSTRAP` está seteado y no existe el archivo, lo crea (one-shot)
5. **Sync de skills bundled**: `python3 tools/skills_sync.py` (preserva ediciones del usuario)
6. **Dashboard** (opcional): si `HERMES_DASHBOARD=1`, arranca en background
7. **Exec final**: `exec hermes gateway run`

**Consecuencia para martes.app**: Los archivos `config.yaml`, `.env`, y `SOUL.md` deben estar
pre-escritos en el volumen **antes** del primer arranque, porque el entrypoint los crea desde
defaults solo si no existen. El Operador los escribe via `write_tenant_config()` antes de
crear el container.

---

## 3. Variables de entorno críticas

| Variable | Requerida | Descripción |
|---|---|---|
| `HERMES_UID` | Sí | UID del host que posee el volumen (evita problemas de permisos) |
| `HERMES_GID` | Sí | GID del host |
| `OPENROUTER_API_KEY` | Sí | LLM via OpenRouter (o usar `.env` del volumen) |
| `TELEGRAM_BOT_TOKEN` | Sí* | Token del bot de Telegram (*si usa Telegram) |
| `TELEGRAM_ALLOWED_USERS` | No | IDs de usuarios permitidos (comma-separated) |
| `API_SERVER_ENABLED` | No | `true` para habilitar API OpenAI-compatible en :8642 |
| `API_SERVER_HOST` | No | `0.0.0.0` para exponer la API fuera del container |
| `API_SERVER_KEY` | No | Auth key para el API server |
| `HERMES_DASHBOARD` | No | `1` para habilitar dashboard web en :9119 |
| `HERMES_AUTH_JSON_BOOTSTRAP` | No | JSON de OAuth para seed en primer boot (one-shot) |

**Nota de seguridad**: `API_SERVER_KEY` y `HERMES_DASHBOARD` exponen interfaces. No activar
en producción sin auth. El meta-agente (martes.app) accede a Hermes via Docker SDK, no via API.

---

## 4. Configuración del agente (`config.yaml`)

El `config.yaml` es la fuente de verdad para el comportamiento del agente. Se carga en cada
arranque. Los cambios no requieren reconstruir la imagen, solo reiniciar el container.

### Secciones relevantes para martes.app

```yaml
# Modelo LLM
model:
  provider: openrouter
  default: deepseek/deepseek-v4-flash   # 1M ctx, mayo 2026
  base_url: "https://openrouter.ai/api/v1"

# Toolsets por plataforma
# Los toolsets controlan qué herramientas tiene disponibles el agente
platform_toolsets:
  telegram: [web, memory, todo, cronjob, clarify]

# Skills auto-creation
skills:
  creation_nudge_interval: 15  # Cada 15 tool calls, nudge a crear skill. 0=desactivado

# Compresión de contexto
compression:
  enabled: true
  threshold: 0.40    # Comprimir cuando el contexto esté al 40%
  target_ratio: 0.20 # Comprimir hasta el 20%
  protect_last_n: 15 # Proteger los últimos N mensajes de la compresión

# Memoria persistente (bounded, auto-gestionada)
memory:
  memory_enabled: true
  user_profile_enabled: true
  memory_char_limit: 2200    # ~800 tokens
  user_char_limit: 1375      # ~500 tokens
  nudge_interval: 10         # Nudge cada 10 turns a actualizar memoria

# Reset de sesión
session_reset:
  mode: both           # "both" | "idle" | "daily" | "none"
  idle_minutes: 1440   # 24h de inactividad → nueva sesión
  at_hour: 4           # Reset diario a las 4 AM

# Comportamiento del agente
agent:
  max_turns: 50
  reasoning_effort: "medium"  # "low" | "medium" | "high"
  restart_drain_timeout: 60   # Segundos para completar el turno antes de reiniciar
```

### Toolsets disponibles en v0.14.0

Definidos en `toolsets.py`. Los principales para martes.app:

| Toolset | Herramientas incluidas | Uso recomendado |
|---|---|---|
| `web` | web_search, web_extract | Básico para todos los planes |
| `memory` | memory_save, memory_load, user_update | Todos los planes |
| `todo` | todo_create, todo_list, todo_complete | Productividad |
| `cronjob` | schedule, list_schedules, cancel_schedule | Automatizaciones |
| `clarify` | clarify (botones nativos en Telegram/Discord) | Todos los planes |
| `vision` | vision_analyze (con modelos vision-capable) | Equipo, Pro |
| `skills` | skills instalar, crear, listar | Equipo, Pro |
| `browser` | browser_navigate, browser_extract | Pro |
| `file` | read_file, write_file, patch | Pro (con sandbox) |
| `terminal` | bash, python | Pro (con sandbox) |
| `hermes-telegram` | Toolset completo para Telegram | Pro (todo incluido) |
| `hermes-discord` | Toolset completo para Discord | Pro (todo incluido) |
| `hermes-whatsapp` | Toolset completo para WhatsApp | Pro (todo incluido) |

---

## 5. Lo que controla Agno vs lo que controla Hermes

```
┌─────────────────────────────────────────────────────────────────┐
│  AGNO (meta-agente martes.app)                                  │
│                                                                 │
│  ● Ciclo de vida del container (create/stop/restart)            │
│  ● Provisión del config.yaml desde templates                    │
│  ● Inyección de credenciales al .env del tenant                 │
│  ● Monitoreo de health (Docker SDK → /health endpoint)          │
│  ● Backups del volumen (tar.gz de /var/lib/martes/tenants/{id}) │
│  ● Registro en base de datos (tenants, payments)                │
│  ● Routing de mensajes admin → Diagnosticador o Operador        │
│  ● Límites de recursos por plan (RAM, CPU, PIDs via Docker)     │
└───────────────────┬─────────────────────────────────────────────┘
                    │ Docker API (socket)
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│  HERMES (container por tenant)                                  │
│                                                                 │
│  ● Comportamiento del agente (toolsets, skills, memoria)        │
│  ● Conexión a plataformas (Telegram, Discord, WhatsApp...)      │
│  ● Gestión de sesiones y contexto                               │
│  ● Auto-creación de skills desde experiencia                    │
│  ● Compresión de contexto y session reset                       │
│  ● Modelo LLM (OpenRouter, proveedor configurable)              │
│  ● Wiki del cliente (base de conocimiento editable)             │
│  ● Cron jobs del agente                                         │
│  ● Memoria persistente (MEMORY.md + USER.md)                    │
└─────────────────────────────────────────────────────────────────┘
```

**Regla general**: Agno controla el *container*, Hermes controla el *agente dentro del container*.

---

## 6. Templates de martes.app

Los templates definen la configuración inicial de cada plan. Se copian a
`/var/lib/martes/tenants/{code}/config.yaml` al crear el tenant.

### Plan Básico ($30/mo)

```yaml
model:
  provider: openrouter
  default: deepseek/deepseek-v4-flash   # actualizar desde deepseek-chat
  base_url: "https://openrouter.ai/api/v1"

platform_toolsets:
  telegram: [web, memory, todo, cronjob, clarify]

agent:
  max_turns: 30
  reasoning_effort: "low"
```

Recursos Docker: `RAM=512MB, CPU=0.5 cores, PIDs=256`
Plataformas: 1 (Telegram)
Skills: desactivado (`creation_nudge_interval: 0`)

### Plan Equipo ($100/mo)

```yaml
model:
  provider: openrouter
  default: deepseek/deepseek-v4-flash   # actualizar
  base_url: "https://openrouter.ai/api/v1"

platform_toolsets:
  telegram: [web, memory, todo, cronjob, clarify, vision, skills]
  discord: [web, memory, todo, cronjob, clarify, vision, skills]

agent:
  max_turns: 50
  reasoning_effort: "medium"
```

Recursos Docker: `RAM=768MB, CPU=0.75 cores, PIDs=256`
Plataformas: 2 (Telegram + Discord)

### Plan Pro ($200/mo)

```yaml
model:
  provider: openrouter
  default: anthropic/claude-3.5-haiku
  base_url: "https://openrouter.ai/api/v1"

platform_toolsets:
  telegram: [hermes-telegram]
  discord: [hermes-discord]
  whatsapp: [hermes-whatsapp]

browser:
  provider: playwright
  inactivity_timeout: 120

agent:
  max_turns: 60
  reasoning_effort: "medium"
```

Recursos Docker: `RAM=1024MB, CPU=1.0 core, PIDs=256`
Plataformas: 3 (Telegram + Discord + WhatsApp)
Browser automation: Playwright habilitado

---

## 7. Capacidad del servidor (Hetzner CX43)

**Specs**: 8 vCPU, 16 GB RAM, 40 GB disco, Ubuntu 24.04

### Presupuesto de memoria

| Componente | RAM |
|---|---|
| Sistema operativo | ~800 MB |
| Coolify + Traefik + agentes Coolify | ~600 MB |
| PostgreSQL (martes.app) | ~256 MB |
| Meta-agente (AgentOS) | ~512 MB |
| **Disponible para tenants** | **~14 GB** |

### Tenants por plan

| Plan | RAM/tenant | Tenants posibles |
|---|---|---|
| Básico (512 MB) | 512 MB | ~27 |
| Equipo (768 MB) | 768 MB | ~18 |
| Pro (1024 MB) | 1024 MB | ~14 |

### Estimación realista (mix de planes)

Un mix típico en producción temprana (mayoría básico):
- 15 tenants básico: 7.7 GB
- 3 tenants equipo: 2.3 GB
- 1 tenant pro: 1.0 GB
- **Total**: ~11 GB → cómodo en el CX43

**Límite práctico**: ~20 tenants simultáneos en CX43 con mix saludable. A partir de 20
conviene mover a CX53 (32 GB RAM).

### CPU

Los contenedores Hermes son ligeros en CPU en reposo. El pico ocurre durante un turno activo
(llamada al LLM API + tool calls). Con limits de 0.5-1.0 core por tenant y uso promedio bajo,
el CX43 maneja 20-25 tenants sin contención de CPU.

### Disco

Cada tenant ocupa aprox. 50-200 MB en disco según conversaciones y skills acumulados.
Con 40 GB y 20 tenants: ~4 GB para tenants, resto para sistema y backups locales.

---

## 8. Flujo de creación de un tenant (Operador)

```
1. create_tenant(name, plan, bot_token)
   └── Genera tenant_code (t001, t002, ...)
   └── Crea registro en DB: status="creating"
   └── Copia template de config.yaml del plan
   └── Escribe .env con: OPENROUTER_API_KEY, TELEGRAM_BOT_TOKEN
   └── Escribe SOUL.md (puede ser default o personalizado)
   └── chown 1000:1000 del volumen
   └── Crea bridge network aislada
   └── docker run con límites del plan
   └── Espera health check (/health en :8642)
   └── Si ok: status="active"
   └── Si falla: reporta error al admin

2. Hermes arranca (entrypoint.sh):
   └── Detecta UID/GID → remap si necesario
   └── Detecta config.yaml ya existe → NO sobreescribe
   └── Sync skills bundled
   └── exec hermes gateway run
   └── Telegram: inicia polling o webhook según config
```

---

## 9. Comandos clave del gateway (enviados vía Telegram al tenant)

Una vez activo, el cliente interactúa directamente con el bot de Telegram de su tenant.
Comandos útiles para el admin (debug remoto):

```
/model [provider:model]    — cambiar modelo en caliente, sin reiniciar
/personality [nombre]      — cambiar SOUL.md en caliente
/skills                    — ver skills instalados
/reset o /new              — nueva sesión (preserva memoria)
/compress                  — comprimir contexto manualmente
/usage                     — tokens consumidos en sesión actual
/sessions                  — explorar sesiones anteriores
/handoff                   — transferir sesión a otro modelo en vivo
/subgoal                   — agregar criterio a un objetivo activo
/stop                      — interrumpir tarea en curso
```

---

## 10. Pendientes en los templates

Los templates actuales usan `deepseek/deepseek-chat` (v3). Con PR #32 se actualizó el
meta-agente a `deepseek/deepseek-v4-flash`. Los templates de los tenants también deben
actualizarse para consistencia:

- `infra/templates/basico/config.yaml`: `default: deepseek/deepseek-chat` → `deepseek/deepseek-v4-flash`
- `infra/templates/equipo/config.yaml`: mismo cambio
- `infra/templates/pro/config.yaml`: ya usa `anthropic/claude-3.5-haiku` (correcto para Pro)

Este cambio aplica solo a **tenants nuevos**. Los tenants existentes mantienen su modelo
hasta que el admin lo cambie via `/model` o actualizando su `config.yaml`.

---

## 11. Referencias

- Repo oficial: https://github.com/nousresearch/hermes-agent
- Docs: https://hermes-agent.nousresearch.com/docs/
- Release v0.14.0: `/workspace/hermes-agent/RELEASE_v0.14.0.md`
- Entrypoint: `docker/entrypoint.sh`
- Config reference: `cli-config.yaml.example`
- Toolsets: `toolsets.py`
