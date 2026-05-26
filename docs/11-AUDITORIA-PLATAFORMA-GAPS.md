# Auditoría de plataforma — gaps, mejoras y estado

> Generado: junio 2026  
> Basado en revisión completa del código, docs oficiales de Agno/Hermes y estado actual de producción.

---

## 1. Cómo funciona el sistema

### Arquitectura en tres capas

```
┌─────────────────────────────────────────────────────┐
│ CAPA 1 — INFRAESTRUCTURA (Pulumi + Hetzner)         │
│  CX43 · Ubuntu · UFW · fail2ban · Docker · Tailscale │
│  Gestionado por: pulumi/index.ts                     │
└────────────────────────┬────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────┐
│ CAPA 2 — PLATAFORMA (Coolify + Docker Compose)       │
│  meta-agent (Agno AgentOS)  ← gestiona todo          │
│  db (PostgreSQL + pgvector)                          │
│  seaweedfs (object storage S3)                       │
│  metabase (dashboard interno)                        │
│  hermes-t001, hermes-t002... (containers de tenants) │
│  Gestionado por: infra/docker-compose.yml            │
└────────────────────────┬────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────┐
│ CAPA 3 — AGENTE (Agno AgentOS + Telegram)            │
│  Team coordinator → Diagnosticador + Operador        │
│                   + Billing                          │
│  6 maintenance schedules                             │
│  Gestionado por: apps/meta-agent/                    │
└─────────────────────────────────────────────────────┘
```

### Modelo de negocio

Cada cliente paga $30/mes y recibe un container **Hermes completo**:
- Bot de Telegram con IA conversacional (cualquier modelo de OpenRouter)
- Memoria persistente, skills, cron jobs, wiki de empresa
- Sin restricciones de features — el límite es su presupuesto de tokens
- El admin gestiona TODO desde un solo bot de Telegram (el meta-agente)

### Flujo de un cliente nuevo

```
Admin en Telegram → "crea tenant Acme, token 123:ABC, id 456"
  → Operador confirma parámetros
  → Admin dice "sí"
  → create_tenant() ejecuta:
     1. DB: INSERT tenant (status='creating')
     2. Volumen: /var/lib/martes/tenants/t001/ con .env + config.yaml + SOUL.md
     3. Docker: run hermes-t001 con imagen nousresearch/hermes-agent:v2026.5.16
     4. DB: status='active', paid_until=hoy+30d
  → container_health() verifica en ~30s
  → El cliente ya puede hablar con su bot de Telegram
```

### Automatizaciones en producción (6 schedules)

| Schedule | Cuándo | Qué hace |
|---|---|---|
| `daily-backup-all` | 3 AM UTC | Backup de todos los tenants activos → SeaweedFS |
| `health-check-all` | Cada 5 min | Health + alertas Telegram + server_metrics |
| `billing-check` | 9 AM UTC | Alertas vencimiento (7d, 3d, hoy) + auto-suspend |
| `expire-platform-keys` | Cada 30 min | BYOK: blanquea platform keys vencidas |
| `docker-cleanup` | Domingo 4 AM | Limpia imágenes Hermes huérfanas |
| `prune-old-data` | Domingo 2 AM | Purge traces/sessions/health_checks > 30/90 días |

---

## 2. Estado actual en producción

**Sistema funcional.** 1 tenant activo (t001), 2 archivados (t002, t003).  
Todos los schedules confirmados corriendo. 6 schedules activos. Metabase con 16 cards.

### Lo que funciona hoy

- Ciclo de vida completo de tenants (create/stop/restart/delete/upgrade)
- Backups diarios automáticos + restore funcional
- Billing: trial 30d, alertas, auto-suspend, register_payment
- BYOK: platform key TTL 2h + detección de key propia del cliente (auth.json)
- Health checks cada 5 min con alertas Telegram
- 104 tests unitarios, CI en GitHub Actions
- Metabase: dashboard con KPIs, uptime, revenue, backups, disco

### Tests de producción que aún no se han hecho

| Test | Prioridad | Bloqueante para |
|---|---|---|
| Backup → restore end-to-end en t001 (C1) | 🔴 Crítico | Primer cliente real |
| `register_payment()` real con t001 (D1) | 🟡 Alto | Ciclo de billing real |
| `upgrade_tenant()` con imagen nueva (E2) | 🟡 Alto | Mantenimiento futuro |
| Purge de t002 y t003 de la DB | 🟢 Bajo | Limpieza |

---

## 3. Gaps para ser un producto real

### 3.1 Sin landing page — bloqueante para E1

`martes.app` no sirve nada hoy. Un cliente potencial que busque el dominio no ve nada.

**Lo que falta:**
- Repo `aikapenelope/martes-landing` (crear)
- Framework: Next.js static export o Astro
- Deploy: Vercel (gratis) → `martes.app CNAME cname.vercel-dns.com`
- Contenido mínimo: nombre, propuesta, precio ($30/mes), CTA a Telegram del admin

### 3.2 Sin flujo de onboarding del cliente

El admin hace todo manualmente via Telegram. Para 5-10 clientes es manejable.  
Para más de 10 empieza a ser un cuello de botella.

**Lo que falta:**
- Página o bot de onboarding que recoja: nombre, bot_token, telegram_user_id
- O un formulario web que llame a la API del meta-agente para crear el tenant

### 3.3 Sin cobro automatizado

Los pagos son manuales (`register_payment()` desde Telegram). Funciona para Venezuela  
(transferencia, pago móvil) pero no escala.

**Futuro:** integrar Stripe o MercadoPago. En el horizonte, no bloqueante hoy.

### 3.4 `inject_credential()` no cubre todas las vars de .env

El procedimiento documenta `inject_credential(t, "telegram_allowed_users", "id")` pero  
`telegram_allowed_users` NO está en `_CREDENTIAL_FILE_MAP` ni en `CredentialType`.  
Lo mismo con `TELEGRAM_BOT_TOKEN` y `TELEGRAM_HOME_CHANNEL`.

**Impacto práctico:**
- Si el cliente cambia su Telegram ID → el admin no puede actualizar `TELEGRAM_ALLOWED_USERS`
- Si el bot_token es revocado → el admin no puede reemplazarlo desde el Operador
- Si el cliente no configuró home_channel → el admin no puede añadirlo

**Fix necesario:** añadir a `_CREDENTIAL_FILE_MAP`:
```python
"telegram_allowed_users": ".env",
"telegram_bot_token": ".env",
"telegram_home_channel": ".env",
```
Y añadirlos a `CredentialType`. El campo `key = credential_type.upper()` ya haría el mapeo correcto.

### 3.5 Sin herramienta para ver el .env actual de un tenant

El Diagnosticador no tiene forma de leer el estado actual del `.env` de un tenant.  
Para diagnosticar si `TELEGRAM_ALLOWED_USERS` está bien configurado hay que adivinar.

**Propuesta:** `get_tenant_env_keys(tenant_code)` — devuelve las CLAVES del .env (sin valores)  
para diagnóstico. Los valores nunca se devuelven (seguridad).

### 3.6 Sin herramienta para verificar modelo y plataformas activas de un tenant

No hay forma rápida de saber qué modelo está usando realmente un tenant  
(config.yaml puede diferir de lo que el cliente cambió con `/model`).

**Propuesta:** `get_tenant_config(tenant_code)` — lee config.yaml y gateway_state.json,  
devuelve: modelo actual, plataformas activas, skills instalados, cron jobs.

### 3.7 Race condition en generación de tenant_code

```python
row = conn.execute("SELECT tenant_code FROM tenants ORDER BY tenant_code DESC LIMIT 1").fetchone()
n = int(row[0][1:]) if row else 0
tenant_code = f"t{n + 1:03d}"
```

Dos `create_tenant()` simultáneos generan el mismo código. La UNIQUE constraint  
lo detecta y lanza error, pero el mensaje de error es confuso para el LLM.

**Fix (H3 ya lo cubre parcialmente):** SEQUENCE de PostgreSQL o retry con backoff.

---

## 4. Configuración de agentes — qué mejorar

### 4.1 Diagnosticador

**Gaps en herramientas:**

| Herramienta faltante | Para qué |
|---|---|
| `get_tenant_config(tenant_code)` | Leer config.yaml + gateway_state.json sin abrir shell |
| `get_tenant_env_keys(tenant_code)` | Saber qué vars están seteadas (sin valores) |
| `get_tenant_skills(tenant_code)` | Listar skills instalados en el tenant |
| `get_tenant_cron_jobs(tenant_code)` | Listar cron jobs activos del tenant |

**Gaps en instrucciones:**

El Diagnosticador sabe diagnosticar contenedores y DB, pero no sabe:
- Interpretar el comportamiento del loop de herramienta de Hermes (CLI no está en PATH)
- Distinguir entre "container healthy pero bot no responde" y "bot respondiendo con error"
- Leer `logs/agent.log` del volumen (existe en `/var/lib/martes/tenants/t001/logs/`)

**Mejora propuesta:**
```python
# Añadir a las instrucciones del Diagnosticador:
"Si el bot responde pero dice cosas raras o está en loop:",
"→ Pedir al cliente que envíe /restart a su bot (no restart_tenant)",
"→ El exit 75 que genera /restart es normal — Docker lo revive solo",
"",
"Si 'healthy' pero el cliente dice que el bot no responde:",
"→ Primero expire_platform_key(dry_run=True) para ver estado de credenciales",
"→ Si client_key_active o client_auth_active: el bot TIENE credenciales, no inyectar",
"→ Revisar container_logs() buscando 'TELEGRAM_ALLOWED_USERS'",
```

### 4.2 Operador

**Gaps:**
- `tool_call_limit=10`: en un flujo de diagnose → backup → restore → restart → verify son exactamente 5 calls. Si algo falla a mitad y hay que diagnosticar, se puede agotar.
- Las instrucciones de HITL listan herramientas que requieren confirmación, pero no dicen qué hacer cuando el admin confirma a medias ("hazlo para t001 y t002")

**Mejora propuesta:**
```python
tool_call_limit=15,  # era 10 — restaurar necesita 5+ calls

# Añadir a instrucciones:
"Si el admin confirma múltiples tenants a la vez ('hazlo para t001, t002, t003'):",
"→ Procesar uno por uno, confirmar resultado de cada uno antes de continuar",
"→ No procesar el siguiente si el anterior falló",
```

**Herramienta faltante:** `get_all_tenants()` no incluye el modelo LLM actual  
(solo el de instance_configs, que puede no coincidir con lo que el cliente cambió via `/model`).

### 4.3 Billing

**Estado:** bien implementado. Solo lectura, 4 tools, instrucciones claras.

**Mejora menor:** añadir a las instrucciones el contexto de que los pagos son manuales  
en Venezuela (transferencia, pago móvil) — el agente no debe sugerir "activar Stripe".

**Gap técnico:** `get_expiring_tenants()` incluye tenants con `paid_until <= hoy + N días`  
pero también muestra tenants ya vencidos. Si hay 10 tenants vencidos hace meses (archivados),  
contamina la respuesta. Añadir filtro `status='active'` solo (ya está, pero también tiene 'paused').

### 4.4 Team coordinator

**Gap principal:** las instrucciones son básicas (7 líneas). Para un equipo de 3 agentes  
especializados, el coordinator necesita más contexto sobre cuándo delegar vs. responder:

```python
# Añadir al Team:
"## Ambigüedades comunes:",
"'¿cuánto revenue tenemos?' → Billing (get_billing_summary)",
"'¿está funcionando t001?' → Diagnosticador (container_health + expire_platform_key)",
"'el cliente no puede usar su bot' → Diagnosticador primero, Operador si hay que actuar",
"'registra pago de t001' → Operador (register_payment — requiere confirmación)",
"",
"## Si el admin pregunta en inglés: responder en inglés también.",
"## Si hay ambigüedad entre diagnóstico y acción: Diagnosticador primero.",
```

---

## 5. Knowledge base — qué actualizar

### 5.1 hermes_reference.md — desactualizada en 3 puntos

**a) Factory defaults (desde PR #76/fde7a01)**

El conocimiento dice "sin restricciones" pero no explica el alcance completo.  
Con los factory defaults actuales (sin cap_drop, sin pids_limit, sin tmpfs):

```markdown
## Capacidades con factory defaults (sin restricciones)

Con la configuración actual (solo mem_limit=768m, sin cap_drop ni pids_limit):

- pip install / apt install: funciona dentro del container
- hermes update: puede actualizarse a sí mismo (exit 75 → Docker revive)
- Browser automation (Playwright, Selenium): funciona si el cliente lo pide
- Subagentes paralelos: funciona
- Code execution: funciona (workspace/ disponible)
- npm / git / ssh: funciona (home/ disponible como HOME)

IMPORTANTE: hermes CLI no está en PATH de bash subprocesses.
Path real: /opt/hermes/.venv/bin/hermes
Si un cliente pide al bot que "se instale algo" y el bot cae en loop,
es porque está intentando llamar 'hermes' en bash y falla.
Fix: el cliente envía /restart a su bot. No necesita restart del container.
```

**b) `/restart` y exit code 75**

No está documentado en hermes_reference.md.  
Hermes tiene el comando `/restart` en Telegram que hace:
1. El gateway llama `hermes gateway restart` internamente
2. El proceso sale con exit code 75
3. Docker detecta el exit y reinicia el container (restart_policy=unless-stopped)
4. El container vuelve en ~10s con sesión nueva
5. El cliente puede continuar conversando

Diferencia con `restart_tenant()` del meta-agente:
- `/restart` (cliente): mata solo la sesión activa, container se reinicia limpio en 10s
- `restart_tenant()` (admin): Docker restart, más brusco, ~30s de downtime

**c) `TELEGRAM_HOME_CHANNEL` — documentación incompleta**

Está en el .env inicial pero no se explica qué hace ni cuándo importa.

```markdown
## TELEGRAM_HOME_CHANNEL

Destino por defecto de notificaciones automáticas de Hermes:
- Resultados de cron jobs
- Resúmenes programados
- Alertas internas del agente

En un DM de Telegram: chat_id == user_id del destinatario.
Si no está configurado: Hermes muestra "📬 No home channel is set" en cada
primera conversación de la sesión. No es un error fatal, pero es ruido.

Al crear tenant: se configura automáticamente con el telegram_user_id del cliente.
Si el cliente quiere recibir notificaciones en otro chat: /sethome en Telegram.
```

### 5.2 procedures.md — 2 errores y 3 gaps

**Error 1 — inject_credential con TELEGRAM_ALLOWED_USERS no funciona:**
```markdown
# INCORRECTO (línea 364 actual):
inject_credential(tenant_code, "telegram_allowed_users", "ID_DEL_CLIENTE")

# Esto devuelve error: "Tipo desconocido: telegram_allowed_users"
# telegram_allowed_users NO está en CredentialType.

# HASTA que se añada al código, el workaround es:
# No hay workaround en este momento — es un gap del sistema.
```

**Error 2 — Upgrade procedure desactualizado:**

La sección de actualización de versión de Hermes dice "Cambiar hermes_image en config.py".  
Desde PR #90 la imagen queda en `extra_config.hermes_image` en instance_configs,  
no en config.py. Y existe `upgrade_tenant()` tool — la guía debería usarla.

**Gap 1 — Sin procedimiento para bot_token revocado:**

Si @BotFather revoca el token (el cliente lo hizo accidentalmente), no hay  
procedimiento documentado. El fix sería inject_credential con el nuevo token,  
pero ese tipo tampoco existe en CredentialType. Gap doble.

**Gap 2 — Sin procedimiento para recuperación total del servidor:**

Si el VPS se destruye, `procedures.md` documenta el flujo de "crear tenants de cero + restore".  
Pero falta: ¿cómo re-crear el stack completo? ¿Dónde están los secrets de Coolify?  
Referencia: el cloud-init de Pulumi crea el servidor limpio. Los secrets están en  
Coolify UI y en el stack de Pulumi. Falta un runbook de "disaster recovery".

**Gap 3 — Ningún procedimiento de capacidad:**

¿Cuándo migrar a CX53? El roadmap lo menciona pero no hay alerta automática  
cuando el servidor se acerca a su límite de ~20 tenants. El health check  
alerta si disco > 80% pero no alerta si RAM asignada > 80%.

### 5.3 SOUL.md template — demasiado genérico

El template actual es un asistente personal genérico. Para el mercado venezolano  
y pymes latinoamericanas, podría ser más específico y atractivo.

**Propuesta de mejora:**
```markdown
# {{AGENT_NAME}}

Soy el asistente inteligente de {{AGENT_NAME}}.
Fui configurado para entender el negocio de mi empresa y ayudar de forma práctica.

## Mi personalidad

- Conciso y directo — no doy respuestas largas innecesarias
- Proactivo — si veo algo que mejorar, lo sugiero
- Respondo en el idioma de mi usuario
- Adapto mi tono al contexto: formal para clientes, directo con el equipo

## Lo que puedo hacer por {{AGENT_NAME}}

- Investigar, resumir y redactar
- Gestionar tareas y recordatorios
- Automatizaciones programadas (reportes diarios, seguimiento)
- Memoria persistente — recuerdo lo que me cuentas entre conversaciones
- Conectar con herramientas: Google, Notion, GitHub, Airtable y más
- Crear skills especializados para procesos repetitivos del negocio

## Mis reglas

- No invento información — si no sé, lo digo
- Protejo la privacidad de {{AGENT_NAME}} y sus clientes
- En Telegram: respuestas cortas y al punto (máx 2-3 párrafos)
```

---

## 6. Mejoras técnicas adicionales

### 6.1 Alertas RAM — falta en health check

El scheduler `health-check-all` alerta disco > 80% pero **no alerta RAM**.  
Si el servidor está al 90% de RAM asignada, no hay señal.

**Propuesta:** en `run_health_check()`, añadir:
```python
# Verificar RAM del servidor
mem_avail_pct = mem_avail_mb / mem_total_mb * 100
if mem_avail_pct < 20:
    alerts.append(f"⚠️ RAM crítica: solo {round(mem_avail_pct)}% disponible ({mem_avail_mb}MB)")
```

### 6.2 `check_all_health()` no escala bien

Con 20+ tenants, el loop de `exec_run("curl ...")` es síncrono.  
20 tenants × ~500ms por curl = ~10 segundos por ciclo. El scheduler tiene timeout.

**Propuesta a futuro (no urgente hoy):** `asyncio.gather()` para los curls en paralelo.  
Con 5 tenants actuales, no es problema.

### 6.3 Sin métricas de tokens por tenant

No se sabe cuántos tokens gasta cada tenant. Para hacer pricing justo  
y detectar abusos es útil. OpenRouter tiene una API de usage que se podría consultar.

### 6.4 Tenant code genera t001, t002... — no reutiliza

Si se archiva t003 y se crea uno nuevo, genera t004 (el siguiente).  
Los códigos archivados no se reutilizan. El código actual es un contador, no un gap-filler.  
Para 20-50 tenants no es un problema, pero sí para cientos.

### 6.5 `instance_configs.memory_limit_mb` y `cpu_limit` no se actualizan al hacer `update_tenant_resources()`

`update_tenant_resources()` modifica los cgroups del container en caliente  
pero NO actualiza `instance_configs` en DB. Si el container se recrea  
(por upgrade, restore, etc.), los nuevos límites NO se aplican — vuelve a 768MB/0.75CPU.

**Fix:** añadir UPDATE a instance_configs en `update_tenant_resources()`.

---

## 7. Prioridades consolidadas

### Antes del primer cliente real (bloqueantes)

| # | Qué | Archivo |
|---|---|---|
| 1 | Test backup→restore end-to-end en t001 | Operacional |
| 2 | Landing page `martes.app` | Nuevo repo `martes-landing` |
| 3 | Añadir TELEGRAM_ALLOWED_USERS/BOT_TOKEN/HOME_CHANNEL a `inject_credential()` | `write_ops.py` |

### Mejoras de agentes (calidad operativa)

| # | Qué | Archivo |
|---|---|---|
| 4 | Actualizar `hermes_reference.md` con factory defaults, exit 75, TELEGRAM_HOME_CHANNEL | `knowledge/hermes_reference.md` |
| 5 | Corregir procedimiento `inject_credential(telegram_allowed_users, ...)` en procedures.md | `knowledge/procedures.md` |
| 6 | Añadir `get_tenant_config()` tool al Diagnosticador | `read_ops.py` + `diagnosticador.py` |
| 7 | `tool_call_limit=15` en el Operador | `operador.py` |
| 8 | Actualizar SOUL.md template | `infra/templates/default/SOUL.md` |
| 9 | Alerta RAM en `run_health_check()` | `main.py` |

### Técnico (deuda)

| # | Qué | Archivo |
|---|---|---|
| 10 | `update_tenant_resources()` debe actualizar instance_configs en DB | `write_ops.py` |
| 11 | H3: TenantCreateInput Pydantic BaseModel | `write_ops.py` |
| 12 | Runbook de disaster recovery | `docs/` |
| 13 | Sprint I: CRM (cuando PocketBase ≥ v1.0.0) | Futuro Q4 2026 |

---

## 8. Lo que NO hace falta hoy

- **Hermes dashboard** — expone API keys. Correcto descartarlo.
- **Multi-servidor** — CX43 aguanta 20 tenants. Escalar cuando se necesite.
- **install_skill_in_tenant()** — obsoleto. Los factory defaults permiten que el cliente  
  lo haga desde Telegram con `/skills install`. Correcto descartarlo.
- **CRM ahora** — PocketBase está en beta. Correcto aplazarlo.
- **Stripe** — El mercado venezolano opera con transferencia/pago móvil. Correcto no implementarlo ahora.
