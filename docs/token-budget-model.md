# Modelo de Token Budget — El Enfoque Correcto para martes.app

> Decisión de arquitectura de producto.
> Fecha: mayo 2026
> Fuentes: https://openrouter.ai/docs/features/provisioning-api-keys · RELEASE_v0.14.0.md

---

## El problema con el enfoque actual de planes por features

El sistema actual restringe las capacidades de Hermes según el plan del cliente:

```
Básico  → toolsets limitados, sin skills, sin Discord, modelo más barato
Equipo  → más plataformas, skills activados, browser básico
Pro     → todo habilitado, Claude, browser completo
```

Esto es **contranatural al diseño de Hermes**. v0.14.0 ("The Foundation Release") está
construido explícitamente para ser un sistema abierto y auto-mejorante:

> *"The self-improving AI agent... creates skills from experience, improves them during use,
> nudges itself to persist knowledge, searches its own past conversations."*

Poner trabas artificiales sobre un sistema diseñado para crecer libremente genera:

1. **Conflictos de lazy-install**: v0.14.0 instala plataformas y herramientas bajo demanda.
   Si un cliente en Básico activa algo que su config "no debería tener", el sistema intenta
   instalarlo y puede fallar silenciosamente en un container sin salida a internet.

2. **Deuda de mantenimiento**: 3 templates distintos que divergen con cada versión de Hermes.
   Cada actualización (v0.15, v0.16...) hay que validar los 3 configs.

3. **Fricción del cliente**: el cliente percibe un sistema capado. No puede hacer lo que sabe
   que Hermes puede hacer. Genera soporte y frustración.

4. **Complejidad interna**: lógica de `create_tenant()` diferente por plan, diferentes
   validaciones, diferentes toolsets a gestionar.

5. **Falsa seguridad**: los toolsets limitan lo que el agente *intenta* hacer, no lo que
   *puede* hacer. Con skills instalados desde el hub, el cliente puede saltarse cualquier
   restricción de toolset.

---

## El enfoque correcto: libertad total + límite de tokens

### La idea central

```
Un tenant = una instancia Hermes completa y sin restricciones
El límite no está en lo que puede hacer, sino en cuántas llamadas al LLM puede hacer
```

Cada tenant tiene su propia API key de OpenRouter con un **presupuesto mensual en USD**.
Cuando el presupuesto se agota, el LLM no responde. El cliente compra más créditos
con martes.app. Agno (el Operador) los aumenta via la API de OpenRouter.

### Por qué funciona

**OpenRouter soporta exactamente esto.** La API de Provisioning Keys permite:
- Crear una sub-key por cliente con `limit` (techo de crédito en USD)
- `limit_reset: 'monthly'` → se reinicia automáticamente cada mes
- Monitorear `limit_remaining` y `usage_monthly` en tiempo real
- Aumentar el límite programáticamente cuando el cliente paga

Fuente: https://openrouter.ai/docs/features/provisioning-api-keys

---

## Los números (verificados con precios reales mayo 2026)

### Costo por turno de conversación

Un turno típico de un cliente SaaS de productividad:
- ~2,000 tokens input (contexto + memoria + sistema + mensaje)
- ~800 tokens output (respuesta del agente)

| Modelo | Costo/turno | Uso recomendado |
|---|---|---|
| `deepseek/deepseek-v4-flash` | **$0.000360** | Default para todos |
| `deepseek/deepseek-v4-pro` | $0.001566 | Tareas complejas |
| `anthropic/claude-3.5-haiku` | $0.004800 | Cuando el cliente quiere Claude |

Con DeepSeek V4 Flash, $1 USD = **2,777 turnos de conversación**.

### Estructura de planes por presupuesto mensual

| Plan | Precio | Budget LLM | Overhead | Margen | Turnos/mes | Turnos/día |
|---|---|---|---|---|---|---|
| Starter | $30 | $18 | $0.30 | $11.70 | ~50,000 | ~1,666 |
| Growth | $100 | $60 | $1.50 | $38.50 | ~166,666 | ~5,555 |
| Scale | $200 | $120 | $5.00 | $75.00 | ~333,333 | ~11,111 |
| Recarga | $10 | $6 | — | $4.00 | ~16,666 | — |

**Un usuario activo promedio hace 20-50 turnos/día.**
El plan Starter de $30 alcanza para ~33-83 días activos.
En un mes real de 30 días, el usuario tiene margen holgado a $30.

### El margen es sólido

```
Starter $30:  costo LLM máximo = $18  →  margen = $12 (39%)
Growth $100:  costo LLM máximo = $60  →  margen = $40 (40%)
Scale $200:   costo LLM máximo = $120 →  margen = $80 (40%)
```

Y esto asumiendo que el cliente **agota** todo su presupuesto mensual.
En la práctica, la mayoría no lo agota → el margen real es mayor.

---

## Arquitectura técnica

### Un solo template de Hermes para todos los planes

```yaml
# infra/templates/default/config.yaml — ÚNICO template
model:
  provider: openrouter
  default: deepseek/deepseek-v4-flash
  base_url: "https://openrouter.ai/api/v1"
  # min_coding_score: 0.7  # OpenRouter Pareto router (v0.14.0)

# Hermes completo — sin toolset restrictions
# El cliente activa lo que quiere en conversación

skills:
  creation_nudge_interval: 15    # auto-crea skills desde experiencia

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
  idle_minutes: 1440
  at_hour: 4

agent:
  max_turns: 60
  reasoning_effort: "medium"

display:
  tool_progress: all
  busy_input_mode: queue

# No platform_toolsets → Hermes usa el toolset completo por defecto
```

### Una sub-key de OpenRouter por tenant

```
martes.app OpenRouter account
│
├── MANAGEMENT KEY (en ESC: martes-infra/secrets → openrouter_mgmt_key)
│   └── Solo para administración. NO hace llamadas LLM.
│
└── SUB-KEYS (una por tenant, creadas via API)
    ├── t001: limit=$18, limit_reset=monthly, name="martes-t001-acme"
    ├── t002: limit=$60, limit_reset=monthly, name="martes-t002-techcorp"
    └── t003: limit=$18, limit_reset=monthly, name="martes-t003-startup"
```

Cada tenant usa **su propia sub-key** en el `.env`. Nunca la key maestra de martes.app.

### Ciclo de vida de la sub-key

```
CREAR TENANT:
  Operador llama provision_tenant_key(tenant_code, plan="starter")
  → POST /api/v1/keys {name: "martes-t001", limit: 18, limit_reset: "monthly"}
  → response: {key: "sk-or-v1-xxxx", hash: "abcd1234"}
  → Guardar key en .env del tenant
  → Guardar hash en DB para gestión futura

PAGO MENSUAL (automático, limit_reset):
  OpenRouter resetea limit_remaining automáticamente cada mes
  No se necesita intervención de Agno

RECARGA MANUAL (cliente compra más):
  Operador llama add_tenant_credits(tenant_code, amount_usd=10)
  → PATCH /api/v1/keys/{hash} {limit: limit_actual + 6}
  (los $10 del cliente se traducen en $6 de crédito en OR)

PAUSA POR NO PAGO:
  Operador llama disable_tenant_key(tenant_code)
  → PATCH /api/v1/keys/{hash} {disabled: true}
  → El siguiente mensaje del cliente → 401/402 → agente no responde

REACTIVACIÓN:
  Operador llama enable_tenant_key(tenant_code, new_limit_usd)
  → PATCH /api/v1/keys/{hash} {disabled: false, limit: new_limit}

MONITOREO (Diagnosticador):
  GET /api/v1/keys/{hash}
  → {limit_remaining: 4.23, usage_monthly: 13.77}
  → Si limit_remaining < 2: alerta al admin
```

---

## Lo que experimenta el cliente cuando se queda sin tokens

Cuando `limit_remaining = 0`, OpenRouter devuelve:

```json
HTTP 402 Payment Required
{
  "error": {
    "message": "You've exceeded your credit limit.",
    "code": 402
  }
}
```

Hermes recibe este error y responde al cliente en Telegram:

> *"Error: API key limit exceeded. Please contact your provider to add more credits."*

Este mensaje es el punto de conversión natural: el cliente va con el admin o con el portal
de martes.app para recargar. Sin fricción artificial, sin planes confusos.

**El cliente puede seguir accediendo a sus memorias, skills, wiki** — todo eso está en el
volumen local y no requiere LLM. Solo las conversaciones nuevas que llamen al LLM fallan.

---

## Lo que simplifica en el código

### Se elimina

```
infra/templates/basico/     ← ELIMINAR
infra/templates/equipo/     ← ELIMINAR
infra/templates/pro/        ← ELIMINAR
```

Reemplazado por:

```
infra/templates/default/    ← UN SOLO template para todos
  config.yaml
  SOUL.md
```

### `create_tenant()` simplificado

```python
# ANTES: lógica diferente por plan
defaults = {
    "basico": (["telegram"], "deepseek/deepseek-chat", 512, 0.5),
    "equipo": (["telegram", "discord"], "deepseek/deepseek-chat", 768, 0.75),
    "pro": (["telegram", "discord", "whatsapp"], "anthropic/claude-3.5-haiku", 1024, 1.0),
}
platforms, model, mem, cpu = defaults[plan]

# DESPUÉS: siempre igual, el plan solo define el presupuesto de tokens
budget_map = {"starter": 18.0, "growth": 60.0, "scale": 120.0}
monthly_budget = budget_map[plan]
tenant_key = provision_openrouter_key(tenant_code, monthly_budget)
# config.yaml: siempre el mismo template default
# recursos Docker: siempre igual (ej: 512MB RAM para todos)
```

### Recursos Docker uniformes

```yaml
# Todos los planes: mismos recursos
mem_limit: 768m
nano_cpus: 750_000_000  # 0.75 cores
pids_limit: 256
```

No hay razón para dar más RAM al plan Pro si el límite es el LLM, no la computación.
Si el cliente necesita más para tareas intensivas (browser, computer_use), se evalúa
caso por caso.

---

## Nuevos tools del Operador

Los tools de gestión de plan se simplifican a operaciones de crédito:

```python
# Nuevos tools (sin @approval — son operaciones de billing, no destructivas)
provision_tenant_key(tenant_code, monthly_budget_usd)
add_tenant_credits(tenant_code, amount_usd)
set_tenant_budget(tenant_code, new_monthly_budget_usd)
disable_tenant_key(tenant_code)
enable_tenant_key(tenant_code)

# Nuevo tool del Diagnosticador
check_tenant_token_usage(tenant_code)
# → {limit: 18.00, remaining: 4.23, used_this_month: 13.77, pct_used: 76.5}
```

El `inject_credential()` existente maneja la actualización del `.env` cuando la key cambia.

---

## Nuevo flujo de monitoreo automático

El Diagnosticador puede hacer un health check de créditos en el cron scheduler del meta-agente:

```python
# Cron diario: revisar créditos de todos los tenants
# "Avisa si algún tenant está al 80% o más de su presupuesto mensual"
check_tenant_token_usage(all=True)
→ [
    {"tenant": "t001", "pct_used": 76.5, "days_remaining_in_month": 8, "status": "warning"},
    {"tenant": "t002", "pct_used": 12.0, "days_remaining_in_month": 8, "status": "ok"},
  ]
```

El admin recibe alerta en Telegram antes de que el cliente se quede sin tokens. Puede
ofrecer recarga proactiva.

---

## Plan de migración

### Paso 1: Configuración de OpenRouter

1. Crear Management Key en https://openrouter.ai/settings/management-keys
2. Guardar en ESC: `pulumi env set aikapenelope-org/martes-infra/secrets openrouter_mgmt_key --secret`
3. Agregar `openrouter_mgmt_key` a `src/config.py` y al compose

### Paso 2: Nuevo template único

1. Crear `infra/templates/default/config.yaml` con el config completo
2. Crear `infra/templates/default/SOUL.md` con el template mínimo
3. Eliminar `basico/`, `equipo/`, `pro/`

### Paso 3: Tools de billing

1. Agregar `provision_tenant_key()` en `write_ops.py`
2. Agregar `add_tenant_credits()` en `write_ops.py`
3. Agregar `check_tenant_token_usage()` en `read_ops.py`
4. Actualizar `create_tenant()` para usar el nuevo flujo

### Paso 4: Schema de DB

```sql
-- Agregar columna a instance_configs
ALTER TABLE instance_configs
  ADD COLUMN openrouter_key_hash VARCHAR(64),
  ADD COLUMN monthly_budget_usd NUMERIC(10,2) DEFAULT 18.00;

-- El "plan" en tenants ahora es solo un nombre comercial,
-- no determina las capacidades técnicas del agente
```

### Paso 5: Fix de los gaps existentes (del doc hermes-ops-guide.md)

Los 4 gaps identificados previamente se resuelven aquí de paso:
- **Gap 1** (TELEGRAM_ALLOWED_USERS): se agrega al signature de `create_tenant()`
- **Gap 2** (modelo hardcodeado): se elimina, siempre deepseek-v4-flash
- **Gap 3** (SOUL.md faltante): hay un solo SOUL.md en el template default
- **Gap 4** (health check): se agrega wait loop con retry

---

## Resumen de beneficios

| Antes | Ahora |
|---|---|
| 3 templates distintos | 1 template único |
| Hermes capado por plan | Hermes completo para todos |
| Conflictos de lazy-install | Sin conflictos — todo está disponible |
| Lógica de plan en código | Plan = solo un número: el presupuesto USD |
| Actualizar Hermes → validar 3 configs | Actualizar Hermes → validar 1 config |
| El cliente ve un sistema limitado | El cliente ve el sistema completo |
| Upgrade de plan = nueva config | Upgrade de plan = agregar créditos |
| Upsell: "cambia de plan" | Upsell: "recarga tokens" (conversión más alta) |

---

## Referencias

- OpenRouter Provisioning API: https://openrouter.ai/docs/features/provisioning-api-keys
- Precios verificados mayo 2026: `deepseek/deepseek-v4-flash` $0.10/$0.20 por 1M tokens
- Hermes v0.14.0 lazy-install: RELEASE_v0.14.0.md (debloating wave)
- Hermes gateway circuit breaker: RELEASE_v0.14.0.md (per-platform circuit breaker)
