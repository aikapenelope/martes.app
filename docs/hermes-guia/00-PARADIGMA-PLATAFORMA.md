# Paradigma de Plataforma — martes.app

> **Regla absoluta**: martes.app gestiona la **plataforma**. Hermes gestiona su propio **funcionamiento**.

---

## La separación de responsabilidades

```
CAPA DE PLATAFORMA (martes.app)        CAPA DEL AGENTE (Hermes)
────────────────────────────────        ────────────────────────
Crear y destruir containers             Responder mensajes
Billing y ciclo de vida del tenant      Gestionar su memoria
Backups y restauración                  Crear y usar skills
Monitoreo de salud del container        Configurar su modelo
Actualizar la imagen Docker             Gestionar sus crons
Configurar el .env de arranque          Configurar /sethome
Escalar recursos (RAM, CPU)             Modificar config.yaml
Gestionar la platform key inicial       Gestionar auth.json
```

**La prueba de fuego para cualquier decisión de implementación:**
> "¿Hermes tiene un comando nativo para esto?"
> Si sí → el cliente lo hace desde Telegram. Nosotros no lo tocamos.
> Si no → podría ser responsabilidad nuestra.

---

## Qué es nuestro y qué es de Hermes

### Archivos que son NUESTROS (los creamos al crear el tenant)

```
/opt/data/
  .env           ← nuestro: vars de arranque, leído por Hermes, no escrito por él
  config.yaml    ← nuestro: configuración inicial de la plataforma
  SOUL.md        ← nuestro: personalidad inicial del agente
  wiki/          ← nuestro: conocimiento inicial del negocio del cliente
  skills/        ← nuestro: skills pre-instaladas en el onboarding
```

Una vez entregados al cliente, Hermes puede modificar todos estos archivos desde conversación (el cliente le pide cambios y él los aplica). Eso es correcto y esperado.

### Archivos que son de HERMES (nunca los tocamos)

```
/opt/data/
  state.db        ← base de datos interna: sesiones, memoria, checksums
  sessions/       ← historial de conversaciones del cliente
  memories/       ← memorias del agente sobre el usuario y el negocio
  auth.json       ← credenciales OAuth configuradas por el cliente
  *.pid *.lock    ← archivos de proceso del gateway
  cron/           ← cron jobs configurados por el cliente
```

**Por qué importa**: si tocamos estos archivos podemos corromper el estado del agente. Hermes gestiona su consistencia interna — nosotros no sabemos qué relaciones mantiene entre esos datos.

---

## El .env — nuestra única interfaz de configuración de arranque

El `.env` es el único archivo que escribimos Y mantenemos durante el ciclo de vida. Hermes lo **lee** en cada turno de conversación pero nunca lo escribe. Contiene exactamente lo que necesita para arrancar:

```bash
# Lo que escribimos en create_tenant():

OPENROUTER_API_KEY=sk-or-...        # Platform key inicial (BYOK bootstrapping)
OPENROUTER_BASE_URL=https://...     # Endpoint de OpenRouter

TELEGRAM_BOT_TOKEN=123456:ABC...    # Token del bot de Telegram

TELEGRAM_ALLOWED_USERS=563825119   # Quién puede hablar con el bot (el cliente)
                                    # El cliente añade más usuarios con:
                                    # /config set telegram.allow_from [id1,id2]
                                    # en su conversación con Hermes

TELEGRAM_HOME_CHANNEL=563825119    # Dónde entregar cron results y notificaciones
                                    # Igual al user_id en DMs (chat_id == user_id)
                                    # El cliente también puede hacer /sethome

TELEGRAM_HOME_CHANNEL_NAME=Acme    # Nombre legible del canal

# Estas dos vars previenen el mensaje "📬 No home channel is set"
# que Hermes envía en la primera conversación de cada sesión nueva
# Ref: gateway/run.py línea 8530 — condición que dispara el aviso
```

Lo que NO ponemos en `.env` a propósito (lo gestiona el cliente desde Telegram):
```bash
# Hermes y el cliente configuran esto con /model, /config, auth.json:
# DEFAULT_MODEL          → /model en Telegram
# TELEGRAM_ALLOW_FROM    → /config set telegram.allow_from
# ANTHROPIC_API_KEY      → /auth en Telegram (guarda en auth.json)
# OPENAI_API_KEY         → /auth en Telegram (guarda en auth.json)
```

---

## Cómo funciona la platform key — el ciclo BYOK completo

Esta es la única danza compleja entre nuestra plataforma y Hermes.

### El problema que resuelve

El cliente nuevo no tiene OpenRouter API key. Necesita poder probar el bot inmediatamente. Nosotros pagamos por el uso inicial, luego el cliente migra a su propia key.

### El flujo completo

```
CREAR TENANT
    │
    ├─ create_tenant() escribe en .env:
    │    OPENROUTER_API_KEY=sk-or-PLATAFORMA  ← nuestra key
    │
    ├─ También escribe .platform_key_expires:
    │    "2026-06-04T12:00:00+00:00"          ← ahora + TTL_HOURS (default 2h)
    │
    └─ Hermes arranca y usa NUESTRA key para sus llamadas a OpenRouter


CADA 30 MINUTOS — scheduler expire-platform-keys
    │
    ├─ Para CADA tenant activo que tenga .platform_key_expires:
    │
    │  NIVEL 1: ¿Cambió la key en .env?
    │    └─ Si OPENROUTER_API_KEY en .env ≠ nuestra platform key
    │       → el cliente ya puso su propia key
    │       → borramos .platform_key_expires
    │       → status: "client_key_active"
    │
    │  NIVEL 2: ¿Existe auth.json con contenido?
    │    └─ Si /opt/data/auth.json tiene > 50 bytes
    │       → el cliente autenticó algún proveedor via Hermes
    │         (OpenRouter OAuth, Anthropic, Google, etc.)
    │       → borramos .platform_key_expires
    │       → status: "client_auth_active"
    │
    │  ¿Expiró el TTL?
    │    └─ Si datetime.now() > expires_at:
    │       → blanqueamos: OPENROUTER_API_KEY=  (línea vacía)
    │       → borramos .platform_key_expires
    │       → Hermes verá la key vacía en el próximo turno
    │       → Hermes caerá a auth.json (si el cliente lo configuró)
    │       → Si tampoco hay auth.json → el bot no funcionará hasta que
    │         el cliente configure su propia credencial
    │
    │  ¿Sigue vigente el TTL?
    │    └─ No hacer nada. Seguimos pagando por ese cliente.


HERMES POR SU LADO (transparente para nosotros)
    │
    ├─ Lee .env en cada turno via _reload_runtime_env_preserving_config_authority()
    ├─ OPENROUTER_API_KEY vacía → el LLM principal falla
    ├─ Hermes busca auth.json → si existe, usa esas credenciales
    └─ El cliente puede en cualquier momento:
         /auth → configura OAuth con cualquier proveedor
         /model → configura una key directa de cualquier proveedor
         → Hermes guarda en auth.json, nosotros no sabemos qué hay ahí
         → En el próximo ciclo de 30min, nuestro scheduler detecta auth.json
           y limpia el marker. La plataforma key ya no es necesaria.
```

### Variables de configuración del scheduler

```bash
# En Coolify (env vars del meta-agente):
PLATFORM_KEY_TTL_HOURS=2    # 0 = desactivar expiración (cliente premium, trial ilimitado)
```

---

## El onboarding — qué hace la plataforma vs qué hace el cliente

### Lo que nosotros hacemos (automatizado en create_tenant())

```
1. Crear volumen /var/lib/martes/tenants/{code}/
2. Copiar config.yaml con el modelo inicial
3. Escribir .env con las 6 vars de arranque
4. Escribir SOUL.md con la personalidad del negocio
5. Arrancar el container hermes-{code}
6. Verificar que está healthy (GET /health → 200 en 30s)
7. Escribir .platform_key_expires
8. Activar el tenant en DB con paid_until = hoy + 30 días (trial)
```

### Lo que el cliente hace (desde su Telegram, guiado por nosotros)

```
Primera conversación con el bot:
  → Hermes se presenta con /help disponible
  → Si el mensaje "📬 No home channel" aparece:
      El cliente escribe: /sethome
      (Aunque con el .env correcto ya no debería aparecer)

Cuando quiera configurar su propia key (opcional):
  → /auth  — OAuth con Google, Anthropic, OpenRouter, etc.
  → /model — selecciona modelo + pega API key

Si quiere añadir a un empleado o familiar al bot:
  → Le dice al bot: "quiero que también [nombre] pueda hablar contigo"
  → El bot le pregunta el ID de Telegram de esa persona
  → El bot actualiza config.yaml: telegram.allow_from: [id1, id2]
  → Hermes lo aplica en el próximo mensaje
```

---

## La regla de NO intervención post-onboarding

Una vez entregado el bot al cliente, **no tocamos nada** en su container salvo:

| Acción | Quién la hace | Cuándo |
|---|---|---|
| Upgrade de imagen Hermes | Admin via meta-agente | Nueva versión estable disponible |
| Backup del volumen | Scheduler automático | 3AM UTC diariamente |
| Health check | Scheduler automático | Cada 5 minutos |
| Billing check | Scheduler automático | 9AM UTC diariamente |
| Expire platform key | Scheduler automático | Cada 30 minutos |
| Escalar recursos (RAM/CPU) | Admin via meta-agente | El cliente solicita más capacidad |
| Restaurar backup | Admin via meta-agente | Corrupción o pérdida de datos |

**TODO lo demás** — skills, model, memory, crons, config, personalidad — lo gestiona Hermes o el cliente directamente desde Telegram.

---

## Por qué este paradigma protege las actualizaciones de Hermes

Hermes se actualiza con la misma cadencia que martes.app: cambia el tag Docker y el container se recrea. Si nosotros hubiéramos sobreescrito config files internos, una actualización podría:

- Romper el formato de `state.db` si cambia el schema
- Invalidar entradas en `sessions/` con formato nuevo
- Corromper `auth.json` si cambia el schema de auth
- Crear conflictos entre nuestra `SOUL.md` y cambios de formato

Como solo tocamos `.env` (que Hermes solo lee, nunca escribe), `config.yaml` (que entregamos una vez y el cliente puede modificar), y `SOUL.md` + `wiki/` + `skills/` (contenido que nosotros aportamos y Hermes puede ampliar), las actualizaciones son seguras.

El container se recrea con la nueva imagen, monta el mismo volumen, y Hermes arranca sin conflictos.
