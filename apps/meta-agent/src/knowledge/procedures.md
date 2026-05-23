# Procedimientos Operativos del Meta-Agente

> Paradigma: token-budget. Hermes completo para todos. Sin restricciones de features.
> El plan (starter/growth/scale) solo define el presupuesto mensual de tokens.

---

## Crear Tenant Nuevo

### Qué necesitas del admin
- Nombre del cliente o empresa
- Bot token de Telegram (el cliente lo crea en @BotFather)
- ID de Telegram del cliente (el cliente lo obtiene con @userinfobot)
- Modelo LLM inicial (opcional, default: `openai/gpt-4o-mini`)
- Plan comercial (opcional, default: `starter`)

### Cómo obtener el Telegram ID
El cliente manda un mensaje a @userinfobot o @getidsbot en Telegram.
Le responde con su user ID numérico (ej: `123456789`).

### Pasos (todo en un solo tool)

```
create_tenant(
    name="Acme Corp",
    bot_token="123456789:ABCdef...",
    telegram_user_id="987654321",
    model="openai/gpt-4o-mini",  # opcional
    plan="starter"                # opcional
)
```

Este tool hace todo en orden:
1. Crea registro en DB (`status='creating'`)
2. Crea volumen en disco (`/var/lib/martes/tenants/t001/`)
3. Copia template `default/config.yaml` con el modelo elegido
4. Escribe `.env` con API key de OpenRouter + bot token + `TELEGRAM_ALLOWED_USERS`
5. Copia `default/SOUL.md` con el nombre del cliente
6. Crea red Docker aislada
7. Lanza container Hermes completo
8. Actualiza DB a `status='active'`

### Si algo falla
- `steps_completed` en la respuesta indica hasta dónde llegó
- Verificar con `container_logs(tenant_code)` si el container arrancó
- Errores comunes: imagen no descargada, permisos del volumen

---

## Cambios en caliente (sin reiniciar el container)

Hermes recarga `config.yaml`, `.env` y `SOUL.md` en cada turno.
Estos cambios tienen efecto en el **próximo mensaje del cliente**:

### Cambiar modelo LLM
```
update_tenant_model("t001", "deepseek/deepseek-v4-flash")
```
Modelos disponibles en OpenRouter:
- `openai/gpt-4o-mini` — default, balanceado ($0.15/$0.60 por 1M)
- `openai/gpt-4o` — más potente
- `deepseek/deepseek-v4-flash` — muy barato, 1M ctx ($0.10/$0.20)
- `anthropic/claude-3.5-haiku` — buena calidad
- `anthropic/claude-opus-4.6` — premium

### Cambiar personalidad
```
update_tenant_soul("t001", "Soy el asistente de Acme Corp.\nEspecializado en...")
```

### Cambiar API key (cuando cliente trae su propia key)
```
inject_credential("t001", "openrouter_api_key", "sk-or-v1-xxxxx")
```

---

## Pausar Tenant (No Pago)

1. `backup_tenant(tenant_code)` — SIEMPRE backup antes de pausar
2. `stop_tenant(tenant_code)` — detiene container, preserva volumen
3. DB queda en `status='paused'` automáticamente

---

## Reactivar Tenant

1. `restart_tenant(tenant_code)` — si el container sigue existiendo
2. `container_health(tenant_code)` — verificar que arrancó
3. DB queda en `status='active'`

---

## Registrar Pago

```
register_payment("t001", amount=30, method="transferencia", months=1)
```
Calcula automáticamente `period_start`, `period_end`, actualiza `paid_until`,
y reactiva el tenant si estaba pausado.

---

## Conectar Integraciones del Cliente

El cliente puede hacerlo él mismo desde Telegram con `/skills install`.
El admin puede hacerlo con:

```
inject_credential("t001", "google_token", "ya29.xxx...")
inject_credential("t001", "notion_key", "secret_xxx")
inject_credential("t001", "github_token", "ghp_xxx")
```

Estas keys van al `.env` del tenant. Hermes las lee en el próximo turno.
Para Google: puede requerir `restart_tenant()` si necesita inicializar OAuth.

---

## Health Check Global

```
check_all_health()
```
→ X healthy, Y unhealthy, Z stopped
→ Para cada unhealthy: sugerir `container_logs()` y luego `restart_tenant()`

---

## Backup y Restore

### Crear backup
```
backup_tenant("t001")
```
Genera: `/var/lib/martes/backups/t001_20260523_123456.tar.gz`
Incluye: state.db, config.yaml, .env, SOUL.md, memories/, wiki/, skills/, cron/

### Listar backups
```
list_backups("t001")
```

### Verificar estado de todos los backups
```
check_backup_status()
```
- `ok`: backup en las últimas 26 horas
- `overdue`: más de 26 horas sin backup
- `never`: nunca se ha hecho backup

### Restaurar
1. `stop_tenant("t001")` — container debe estar detenido
2. `restore_tenant_from_backup("t001", "t001_20260523_123456.tar.gz")`
3. `restart_tenant("t001")`
4. `container_health("t001")`

---

## Flujo No-Pago

```
Cliente no paga en fecha límite:
  1. backup_tenant(tenant_code)
  2. stop_tenant(tenant_code)     → status='paused'

Si paga (antes de los 90 días):
  1. register_payment(tenant_code, ...)   → reactiva automáticamente
  2. restart_tenant(tenant_code)
  3. container_health(tenant_code)

Si no paga después de 90 días:
  1. backup_tenant(tenant_code)   → backup final
  2. stop_tenant(tenant_code)     → status='paused'
  (volumen queda en disco, se puede restaurar más tarde si paga)
```

---

## Troubleshooting

### Bot no responde al cliente
1. Verificar container running: `container_health(tenant_code)`
2. Si está parado: `restart_tenant(tenant_code)`
3. Si está running pero no responde: verificar `.env` tenga `TELEGRAM_ALLOWED_USERS`
   → `inject_credential(tenant_code, "telegram_allowed_users", "ID_DEL_CLIENTE")`

### Container no arranca
1. `container_logs(tenant_code, lines=50)` — ver errores
2. Errores comunes:
   - `Permission denied` → `chown 1000:1000 /var/lib/martes/tenants/{code}/`
   - `Token must contain a colon` → bot token inválido
   - `invalid_token` → revisar `OPENROUTER_API_KEY` en .env
   - `No such image` → imagen de Hermes no descargada en el VPS

### Cliente pide cambiar de modelo
```
update_tenant_model(tenant_code, "deepseek/deepseek-v4-flash")
```
Sin reinicio. Efecto en el próximo mensaje del cliente.
