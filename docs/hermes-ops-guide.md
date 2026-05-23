# Hermes Ops Guide — Creación y Mantenimiento de Agentes desde Agno

> Guía de producción para operar tenants Hermes desde el meta-agente martes.app.
> Fuentes: https://hermes-agent.nousresearch.com/docs + repo oficial v0.14.0

---

## 1. Modelo mental: lo que controla Agno desde afuera

Agno (el meta-agente de martes.app) opera como un **orchestrador externo** de containers Hermes.
No modifica el código de Hermes. Interactúa con él de tres maneras:

```
Agno (meta-agente)
│
├── Docker SDK          → crear / parar / reiniciar containers
├── Sistema de archivos → leer/escribir en el volumen /opt/data del tenant
│     ├── config.yaml   → comportamiento del agente (toolsets, modelo, limits)
│     ├── .env          → credenciales (API keys, bot tokens)
│     ├── SOUL.md       → identidad y personalidad
│     └── wiki/         → base de conocimiento del cliente
└── API REST            → /health en :8642 (cuando API_SERVER_ENABLED=true)
```

**Hermes v0.14.0 recarga `config.yaml`, `.env` y `SOUL.md` en cada turno de conversación.**
Esto significa que Agno puede cambiar el comportamiento de un agente activo **sin reiniciar el container**,
simplemente editando los archivos en el volumen.

Fuente: `gateway/run.py:16119`
```python
# Re-read .env and config for fresh credentials (gateway is long-lived,
# keys may change without restart).
_reload_runtime_env_preserving_config_authority()
```

---

## 2. Anatomía del volumen — qué debe existir ANTES del primer boot

El `entrypoint.sh` de Hermes aplica esta lógica al arrancar:

```
Si .env NO existe       → copia .env.example (vacío, sin credenciales)
Si config.yaml NO existe → copia cli-config.yaml.example (defaults genéricos)
Si SOUL.md NO existe    → copia docker/SOUL.md (vacío)
```

**Consecuencia crítica**: si el container arranca sin los archivos del tenant pre-escritos,
usa defaults que NO incluyen las credenciales del cliente. El agente arrancará pero
no tendrá su bot de Telegram configurado ni acceso al LLM correcto.

### Archivos OBLIGATORIOS antes del primer `docker run`

```
/var/lib/martes/tenants/{tenant_code}/
├── .env              ← credenciales (permisos 600)
├── config.yaml       ← configuración del agente
└── SOUL.md           ← identidad básica (puede ser 3 líneas)
```

Los directorios (`sessions/`, `memories/`, `skills/`, etc.) los crea el entrypoint
automáticamente si no existen — no hay que pre-crearlos.

---

## 3. El `.env` del tenant — variables críticas

Fuente: https://hermes-agent.nousresearch.com/docs/reference/environment-variables

### Obligatorias para producción

```bash
# LLM provider
OPENROUTER_API_KEY=sk-or-v1-xxxxx

# Telegram gateway
TELEGRAM_BOT_TOKEN=123456789:ABCdef...
TELEGRAM_ALLOWED_USERS=12345678          # ← CRÍTICO: sin esto, NADIE puede hablar al bot

# OpenRouter base URL (explícito para evitar defaults incorrectos)
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
```

### Por qué `TELEGRAM_ALLOWED_USERS` es crítico

La documentación oficial dice:

> *"By default, the gateway denies all users who are not in an allowlist or paired via DM."*

Sin `TELEGRAM_ALLOWED_USERS`, el bot NO responde a nadie y logea un warning de seguridad.
El ID de Telegram del cliente **debe estar en este archivo al momento de creación**.

Si el cliente no conoce su Telegram ID al momento de contratar, usar la alternativa de DM
pairing: el bot envía un código de 8 caracteres que el admin aprueba con el Operador.

### Opcionales pero recomendadas para producción

```bash
# Limitar intentos fallidos y timeouts
HERMES_API_TIMEOUT=600            # timeout por llamada al LLM (default: 1800s)
HERMES_AGENT_TIMEOUT=900          # inactividad máxima en el gateway (default: 900s)

# Para plan equipo/pro: Discord
DISCORD_BOT_TOKEN=Bot.xxxxx
DISCORD_ALLOWED_USERS=123456789012345678

# Para plan pro: WhatsApp (a través del gateway de WhatsApp)
# Configurar separadamente via hermes gateway setup
```

### Credenciales del cliente vs. de martes.app

| Plan | `OPENROUTER_API_KEY` | Modelo | Quién paga el LLM |
|---|---|---|---|
| Básico | Key de martes.app | deepseek/deepseek-v4-flash | martes.app |
| Equipo | Key de martes.app | deepseek/deepseek-v4-flash | martes.app |
| Pro | Key del cliente (o martes.app) | anthropic/claude-3.5-haiku | Configurable |

Para Pro donde el cliente quiere usar su propia key: usar `inject_credential()` después de
crear el tenant, pasando `"openrouter_api_key"` como tipo de credencial.

---

## 4. El `config.yaml` del tenant — estructura por plan

Fuente: https://hermes-agent.nousresearch.com/docs/user-guide/configuration

### Plan Básico

```yaml
model:
  provider: openrouter
  default: deepseek/deepseek-v4-flash   # 1M ctx, mayo 2026
  base_url: "https://openrouter.ai/api/v1"

# Toolsets: solo lo que el plan incluye
# Los toolsets controlan qué herramientas tiene disponibles el agente en cada plataforma
platform_toolsets:
  telegram: [web, memory, todo, cronjob, clarify]

skills:
  creation_nudge_interval: 0   # desactivado en básico

compression:
  enabled: true
  threshold: 0.30              # comprimir pronto para ahorrar tokens
  target_ratio: 0.20
  protect_last_n: 10

memory:
  memory_enabled: true
  user_profile_enabled: true
  memory_char_limit: 1500
  user_char_limit: 1000
  nudge_interval: 15

session_reset:
  mode: both
  idle_minutes: 720            # 12h — básico tiene sesiones más cortas
  at_hour: 4

agent:
  max_turns: 30
  reasoning_effort: "low"
  restart_drain_timeout: 30

display:
  tool_progress: new
  busy_input_mode: queue       # guardar mensajes mientras el agente trabaja
```

### Plan Equipo

```yaml
model:
  provider: openrouter
  default: deepseek/deepseek-v4-flash
  base_url: "https://openrouter.ai/api/v1"

platform_toolsets:
  telegram: [web, memory, todo, cronjob, clarify, vision, skills]
  discord: [web, memory, todo, cronjob, clarify, vision, skills]

skills:
  creation_nudge_interval: 15  # el agente crea skills automáticamente

compression:
  enabled: true
  threshold: 0.40
  target_ratio: 0.20
  protect_last_n: 15

memory:
  memory_enabled: true
  user_profile_enabled: true
  memory_char_limit: 2200
  user_char_limit: 1375
  nudge_interval: 10

session_reset:
  mode: both
  idle_minutes: 1440           # 24h
  at_hour: 4

agent:
  max_turns: 50
  reasoning_effort: "medium"
  restart_drain_timeout: 60

browser:
  provider: firecrawl          # web scraping para investigación
  inactivity_timeout: 60

display:
  tool_progress: all
  busy_input_mode: queue
```

### Plan Pro

```yaml
model:
  provider: openrouter
  default: anthropic/claude-3.5-haiku
  base_url: "https://openrouter.ai/api/v1"

platform_toolsets:
  telegram: [hermes-telegram]   # toolset completo para Telegram
  discord: [hermes-discord]
  whatsapp: [hermes-whatsapp]

skills:
  creation_nudge_interval: 10
  external_dirs:
    - /opt/data/custom-skills    # skills propios del cliente

compression:
  enabled: true
  threshold: 0.50
  target_ratio: 0.20
  protect_last_n: 20

memory:
  memory_enabled: true
  user_profile_enabled: true
  memory_char_limit: 2200
  user_char_limit: 1375
  nudge_interval: 10

session_reset:
  mode: both
  idle_minutes: 1440
  at_hour: 4

agent:
  max_turns: 60
  reasoning_effort: "medium"
  restart_drain_timeout: 120

browser:
  provider: playwright          # automatización de navegador completa
  inactivity_timeout: 120

display:
  tool_progress: all
  busy_input_mode: steer        # redirigir sin interrumpir (Pro tiene tareas largas)
```

---

## 5. El `SOUL.md` — identidad del agente

El `SOUL.md` define la personalidad y comportamiento del agente. Se carga **fresco en cada turno**.
Si está vacío, el agente responde como "Hermes genérico" sin identidad específica.

### Template mínimo para creación (Tier 0)

```markdown
Soy el asistente de IA de {{COMPANY_NAME}}.
Trabajo en el sector {{SECTOR}}.
Respondo en español, de forma concisa y profesional.
```

El `create_tenant()` reemplaza `{{AGENT_NAME}}` automáticamente. Agno debe
extender este template antes de crear el container.

### Template post-onboarding (Tier 1, después de primera conversación)

```markdown
Soy {{agent_name}}, el asistente de {{company_name}}.

## Contexto
- Empresa: {{company_name}}
- Sector: {{sector}}
- Usuarios: {{who_uses_it}}
- Mi especialidad: {{what_i_do}}

## Cómo trabajo
- Respondo en español, tono {{tone}}
- Soy directo y práctico
- Para tareas complejas, confirmo antes de ejecutar

## Lo que puedo hacer
{{capabilities_list}}
```

Agno actualiza el `SOUL.md` con `update_tenant_soul()` después del onboarding.
El cambio tiene efecto en el **próximo mensaje del usuario**, sin reiniciar.

---

## 6. Flujo completo de creación de un tenant

### Fase 0: Pre-provisioning (Operador ejecuta, requiere aprobación)

```
Admin (Telegram) → "Crea tenant Acme Corp plan basico token 123:ABC telegram_id 9876"
                                         ↓
                              Operador.create_tenant()
                                         ↓
   ┌─────────────────────────────────────────────────────────────┐
   │ 1. DB: INSERT tenants (status='creating')                   │
   │ 2. DB: INSERT instance_configs (plataformas, modelo, límites)│
   │ 3. Disco: mkdir /var/lib/martes/tenants/t001/               │
   │ 4. Disco: cp template/basico/config.yaml → t001/config.yaml │
   │ 5. Disco: write t001/.env (OPENROUTER_KEY + BOT_TOKEN +     │
   │           TELEGRAM_ALLOWED_USERS={telegram_id})             │
   │ 6. Disco: write t001/SOUL.md (template mínimo)              │
   │ 7. Disco: chown 1000:1000 -R t001/                          │
   │ 8. Docker: create network tenant-t001-net                   │
   │ 9. Docker: run hermes container (límites del plan)          │
   │ 10. Health check: GET :8642/health (timeout 60s)            │
   │ 11. DB: UPDATE tenants SET status='active'                  │
   └─────────────────────────────────────────────────────────────┘
                                         ↓
   Respuesta al admin: "Tenant t001 activo. Bot: @acmecorp_bot"
```

### Fase 1: Onboarding (primera conversación del cliente con su bot)

El cliente manda su primer mensaje al bot. El agente responde con el mensaje de bienvenida
del template. Luego el admin (o un flujo automático) ejecuta:

```
Admin → "Haz onboarding del tenant t001: empresa=Acme, sector=retail,
          usuario=María directora, necesita=reportes diarios y recordatorios"
                                         ↓
         Operador.inject_wiki_content(tenant_code="t001",
                                      company_name="Acme Corp",
                                      company_description="Retail B2C online",
                                      ...)
         Operador.update_tenant_soul(tenant_code="t001",
                                     soul_content="Soy el asistente de Acme...")
```

Ambas operaciones sin reinicio. El próximo mensaje del cliente ya tiene el contexto.

### Fase 2: Crecimiento orgánico (sin intervención de Agno)

A partir de aquí, Hermes gestiona solo:

| Qué | Quién lo hace | Cómo |
|---|---|---|
| Memoria del usuario | Hermes automático | Cada 15 turns: nudge a actualizar MEMORY.md |
| Skills de procedimientos | Hermes automático | Después de tareas complejas (nudge_interval) |
| Cron jobs | El cliente en conversación | "/cron add daily 9am..." |
| Wiki | El cliente o el admin | Conversación o inject_wiki_content() |

---

## 7. Operaciones de mantenimiento desde Agno

### Cambios sin reinicio (hot-reload)

| Operación | Tool | Efecto |
|---|---|---|
| Cambiar modelo | `update_tenant_model(t001, "deepseek/deepseek-v4-pro")` | Próximo mensaje |
| Actualizar personalidad | `update_tenant_soul(t001, nuevo_soul)` | Próximo mensaje |
| Inyectar credential | `inject_credential(t001, "openrouter_api_key", nueva_key)` | Próximo mensaje |
| Agregar wiki | `inject_wiki_content(t001, ...)` | Próximo mensaje |

### Operaciones que requieren reinicio

| Operación | Cuándo |
|---|---|
| Cambiar `platform_toolsets` | Los toolsets se cargan al arrancar el gateway |
| Cambiar `memory.memory_char_limit` | Afecta la inicialización del memory manager |
| Cambiar `terminal.backend` | Backend de terminal se inicializa una vez |
| Actualizar imagen de Hermes | Cambio de versión |

Para estas: `stop_tenant()` → editar archivos → `restart_tenant()`.

### Upgrade de plan

```
Admin → "Sube el tenant t001 a plan equipo"
                    ↓
1. update_tenant_model(t001, "deepseek/deepseek-v4-flash")   # ya es v4-flash, ok
2. Editar t001/config.yaml: platform_toolsets, memory_char_limit, etc.
3. DB: UPDATE tenants SET plan='equipo' WHERE tenant_code='t001'
4. DB: UPDATE instance_configs SET memory_limit_mb=768, cpu_limit=0.75
5. stop_tenant(t001)
6. Docker: update container resource limits (mem, cpu)
7. restart_tenant(t001)
```

**Nota**: Los recursos del container (RAM, CPU) solo se actualizan recreando el container.
No hay hot-reload para límites de Docker.

### Pausa por no pago

```
1. backup_tenant(t001)          ← backup antes de pausar (SIEMPRE)
2. stop_tenant(t001)            ← detiene el container, preserva datos
3. DB: status='paused'          ← automático en stop_tenant()
```

Si paga:
```
1. restart_tenant(t001)         ← si el container aún existe
   — o —
   create_tenant(...) con los mismos datos  ← si el container fue eliminado
2. DB: status='active'
```

---

## 8. Seguridad — modelo de Hermes en producción

Hermes implementa defensa en profundidad de 7 capas (según docs):

### Capa de autorización (crítica para producción)

```
Orden de evaluación:
1. Per-platform allow-all → NUNCA activar en producción
2. DM pairing approved list
3. TELEGRAM_ALLOWED_USERS (comma-separated IDs)
4. GATEWAY_ALLOWED_USERS (cross-platform)
5. Global allow-all → NUNCA activar en producción
6. Default: DENY todo
```

**Sin `TELEGRAM_ALLOWED_USERS` correctamente seteado, el bot no responde a nadie.**

### Isolación de containers

Cada tenant corre con:
```
--cap-drop ALL
--security-opt no-new-privileges
--pids-limit 256
--tmpfs /tmp:size=100m
```

Los caps re-agregados (mínimos):
```
NET_RAW, CHOWN, SETUID, SETGID, DAC_OVERRIDE, FOWNER
```
Esto permite que el entrypoint remapee el UID del usuario y gestione permisos del volumen.

### Aprobación de comandos

Para plan básico: `approvals.mode: manual` (el cliente aprueba comandos peligrosos).
Para plan pro: se puede configurar `approvals.mode: smart` (LLM evalúa el riesgo automáticamente).

**La lista negra permanente de Hermes** (no overrideable con ningún modo):
- `rm -rf /` y variantes
- Fork bombs
- Comandos de borrado catastrófico

---

## 9. Configuración progresiva vs. entrega completa

### Por qué NO entregar todo configurado desde el día 1

Hermes v0.14.0 ("The Foundation Release") está diseñado para crecer con el uso:

```
Al crear el tenant:
  config.yaml  ✓  (toolsets, modelo, límites de recursos)
  .env         ✓  (API keys, bot token, TELEGRAM_ALLOWED_USERS)
  SOUL.md      ✓  (3 líneas mínimas: empresa, sector, idioma)

Lo que NO pre-configurar:
  wiki/        ✗  → el cliente lo construye en conversación o onboarding
  memories/    ✗  → Hermes lo construye solo (auto-gestionado)
  skills/      ✗  → Hermes los crea desde experiencia (auto-generados)
  cron/        ✗  → el cliente los define en conversación
```

**La wiki, la memoria y los skills son el "cerebro" del agente.** Pre-configurarlos sin
conocer al cliente genera un agente que "sabe" cosas incorrectas. Es mejor que crezcan
orgánicamente.

### El flujo de 3 tiers recomendado

```
TIER 0 — Al crear (Operador, automatizado):
  → config.yaml + .env + SOUL.md mínimo
  → Container arranca
  → El agente PUEDE responder mensajes básicos

TIER 1 — Onboarding (primera semana, admin lo orquesta):
  → inject_wiki_content() con info del negocio
  → update_tenant_soul() con personalidad completa
  → El agente CONOCE al cliente y su negocio

TIER 2 — Crecimiento orgánico (continuo, sin intervención):
  → Hermes crea skills desde tareas repetidas
  → Hermes actualiza MEMORY.md y USER.md automáticamente
  → El cliente define cron jobs en conversación
  → El agente MEJORA con cada sesión

TIER 3 — Configuración avanzada (bajo demanda, admin):
  → update_tenant_model() para cambiar modelo
  → inject_credential() para key propia del cliente
  → restart_tenant() para cambios que requieren reinicio
```

---

## 10. Gaps actuales en la implementación

Los siguientes problemas están identificados en el código actual y deben corregirse
antes de crear el primer tenant de producción:

### Gap 1: `TELEGRAM_ALLOWED_USERS` no se escribe en `.env`

**Archivo**: `apps/meta-agent/src/tools/write_ops.py`, función `create_tenant()`

```python
# ACTUAL (línea 96-100) — falta TELEGRAM_ALLOWED_USERS
env_file.write_text(
    f"OPENROUTER_API_KEY={settings.openrouter_api_key}\n"
    f"TELEGRAM_BOT_TOKEN={bot_token}\n"
    f"OPENROUTER_BASE_URL=https://openrouter.ai/api/v1\n"
)
```

```python
# CORRECTO — agregar telegram_user_id al signature y al .env
env_file.write_text(
    f"OPENROUTER_API_KEY={settings.openrouter_api_key}\n"
    f"TELEGRAM_BOT_TOKEN={bot_token}\n"
    f"TELEGRAM_ALLOWED_USERS={telegram_user_id}\n"
    f"OPENROUTER_BASE_URL=https://openrouter.ai/api/v1\n"
)
```

### Gap 2: Modelo hardcodeado en DB en lugar de leerlo del template

```python
# ACTUAL (línea 70-74) — modelo hardcodeado, no sincronizado con templates
defaults = {
    "basico": (["telegram"], "deepseek/deepseek-chat", 512, 0.5),
    ...
}
```

```python
# CORRECTO — leer del config.yaml del template
import yaml
template_config = yaml.safe_load((Path(settings.templates_path) / plan / "config.yaml").read_text())
model = template_config.get("model", {}).get("default", "deepseek/deepseek-v4-flash")
```

### Gap 3: No existe `SOUL.md` en los templates

Los templates en `infra/templates/{basico,equipo,pro}/` no tienen `SOUL.md`.
El código en `create_tenant()` ya copia el SOUL.md si existe, pero el archivo no está creado.
Hay que crear un `SOUL.md` template mínimo en cada plan.

### Gap 4: Health check no espera el tiempo correcto

Hermes demora ~15-30 segundos en inicializar el gateway. El `create_tenant()` actual activa
el tenant inmediatamente sin esperar el health check. Hay que agregar un wait loop
con retry antes de marcar como `active`.

---

## 11. Variables de entorno del container Docker (pasadas vía docker run)

Estas van en el `environment` del `docker.containers.run()`, NO en el `.env` del volumen:

| Variable | Valor | Por qué |
|---|---|---|
| `HERMES_UID` | `1000` | Remapeo de UID para permisos del volumen |
| `HERMES_GID` | `1000` | Remapeo de GID |
| `API_SERVER_ENABLED` | `true` | Habilita /health en :8642 para health checks |
| `API_SERVER_HOST` | `0.0.0.0` | Expone el API server fuera del container |
| `HERMES_DASHBOARD` | `1` (equipo/pro) | Dashboard web en :9119 |

**Diferencia importante**: las variables del container se pasan en `docker run` y son fijas.
Las variables del agente (API keys, bot tokens) van en `.env` del volumen y se recargan en caliente.

---

## 12. Comandos de referencia — Hermes desde Telegram (admin)

Una vez creado el tenant, el admin puede enviar estos comandos al bot del cliente
para configuración y debugging:

```
/model deepseek/deepseek-v4-flash     ← cambiar modelo (persiste en config.yaml)
/model anthropic/claude-opus-4.6      ← upgrade de modelo
/skills                                ← ver skills instalados
/skills install official/productivity/notion   ← instalar skill del hub
/cron add "0 9 * * *" "Resumen diario de tareas pendientes"
/memory                                ← ver estado de memoria
/usage                                 ← tokens consumidos en sesión actual
/compress                              ← comprimir contexto manualmente
/reset                                 ← nueva sesión (preserva memoria)
/handoff anthropic/claude-opus-4.6    ← transferir sesión a otro modelo en vivo
/personality [nombre]                  ← cambiar perfil de personalidad
```

---

## 13. Referencias

| Recurso | URL |
|---|---|
| Docs oficiales | https://hermes-agent.nousresearch.com/docs |
| Config reference | https://hermes-agent.nousresearch.com/docs/user-guide/configuration |
| Env vars reference | https://hermes-agent.nousresearch.com/docs/reference/environment-variables |
| Messaging gateway | https://hermes-agent.nousresearch.com/docs/user-guide/messaging |
| Security | https://hermes-agent.nousresearch.com/docs/user-guide/security |
| Skills system | https://hermes-agent.nousresearch.com/docs/user-guide/features/skills |
| Memory | https://hermes-agent.nousresearch.com/docs/user-guide/features/memory |
| Cron | https://hermes-agent.nousresearch.com/docs/user-guide/features/cron |
| Repo oficial | https://github.com/nousresearch/hermes-agent |
