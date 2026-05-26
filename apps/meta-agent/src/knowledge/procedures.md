# Procedimientos Operativos del Meta-Agente

> Modelo Hermes libre: todos los tenants son técnicamente idénticos.
> Hermes completo para todos. Sin tiers, sin restricciones de features.
> La única diferencia entre clientes es el presupuesto de tokens (créditos OpenRouter).

---

## Crear Tenant Nuevo

### Qué necesitas del admin

- Nombre del cliente o empresa
- Bot token de Telegram (el cliente lo crea en @BotFather)
- ID de Telegram del cliente (el cliente lo obtiene con @userinfobot)
- Modelo LLM inicial (opcional, default: `openai/gpt-4o-mini`)

**NO hay plan, tier, ni ningún otro parámetro.** El sistema asigna los mismos
recursos a todos los tenants automáticamente.

### Cómo obtener el Telegram ID del cliente

El cliente envía un mensaje a @userinfobot en Telegram.
Le responde con su user ID numérico (ej: `123456789`).

### Pasos

```
create_tenant(
    name="Acme Corp",
    bot_token="123456789:ABCdef...",
    telegram_user_id="987654321",
    model="openai/gpt-4o-mini",  # opcional
)
```

Este tool hace todo en orden:
1. Crea registro en DB (`status='creating'`)
2. Crea volumen en disco (`/var/lib/martes/tenants/t001/`)
3. Copia template `default/config.yaml` con el modelo elegido
4. Escribe `.env` con API key de OpenRouter + bot token + `TELEGRAM_ALLOWED_USERS`
5. Copia `default/SOUL.md` con el nombre del cliente
6. Crea red Docker aislada (`tenant-t001-net`)
7. Lanza container `hermes-t001` con imagen `nousresearch/hermes-agent:v2026.5.16`
8. Actualiza DB a `status='active'`

### Después de crear: verificar

```
container_health("t001")
```

Hermes tarda ~30 segundos en arrancar. Si el primer health check falla,
esperar y reintentar. Una vez "healthy", el bot está operativo.

### Si algo falla

- `steps_completed` en la respuesta JSON indica hasta dónde llegó
- `container_logs("t001")` para ver errores de arranque
- Errores comunes: imagen no descargada aún, permisos del volumen

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

El cliente también puede cambiar su propio modelo desde Telegram con `/model`.

### Actualizar recursos (RAM / CPU) sin reiniciar

Modifica cgroups del container en caliente. Efecto inmediato, sin restart.

```
update_tenant_resources("t001", memory_mb=1024, cpu_cores=1.0)
```

| Perfil | RAM | CPU | Cuándo usar |
|---|---|---|---|
| Ligero | 512 MB | 0.5 | Tareas simples, conversación básica |
| Estándar | 768 MB | 0.75 | Default al crear — uso normal |
| Pesado | 1024 MB | 1.0 | Contexto largo, skills complejos |
| Intensivo | 2048 MB | 2.0 | Subagentes, code execution, tasks largas |

Límite mínimo seguro: 256 MB RAM, 0.1 CPU (por debajo puede causar OOM kills).

---

### Cambiar personalidad

```
update_tenant_soul("t001", "Soy el asistente de Acme Corp.\nEspecializado en...")
```

### Cambiar API key (cuando el cliente trae su propia key de OpenRouter)

```
inject_credential("t001", "openrouter_api_key", "sk-or-v1-xxxxx")
```

---

## Estado de credenciales de un tenant — cómo leer correctamente

**CRÍTICO**: antes de asumir que un tenant no tiene credenciales propias, verificar
el estado real. Un tenant PUEDE estar funcionando perfectamente aunque no hayas
inyectado una key desde aquí.

### Cómo funciona la prioridad de credenciales en Hermes

Hermes usa credenciales en este orden de prioridad (de mayor a menor):

```
1. auth.json en /opt/data/auth.json  ← MÁXIMA PRIORIDAD
   El cliente configuró su cuenta vía /auth en Telegram (OAuth con OpenRouter,
   Anthropic, Google, xAI, etc.). Si este archivo existe con >50 bytes,
   el bot funciona con esas credenciales INDEPENDIENTEMENTE de lo que haya en .env.

2. OPENROUTER_API_KEY en .env  ← segunda prioridad
   Puede ser: a) la platform key que pusimos al crear el tenant
              b) una key propia del cliente inyectada con inject_credential()

3. Nada → el bot muestra error de credencial al responder
```

### Cómo verificar el estado real antes de actuar

```
expire_platform_key("t001", dry_run=True)
```

Devuelve uno de estos estados:
- `"client_auth_active"` → auth.json existe con credenciales → **bot funciona, NO intervenir**
- `"client_key_active"` → .env tiene la key propia del cliente → **bot funciona, NO intervenir**
- `"not_expired"` → platform key activa, TTL no vencido → **bot funciona temporalmente**
- `"blanked"` → platform key fue borrada → **el cliente debe configurar su key**

### Señal práctica: si el container está "healthy", tiene credenciales

Si `container_health("t001")` devuelve `"healthy"`, el bot está respondiendo peticiones.
Hermes solo responde si tiene credenciales válidas. No asumir que falta una key
solo porque no la inyectamos nosotros.

### Por qué el bot puede parecer que "tiene dos conversaciones"

Esto ocurre por dos razones independientes:

**Causa 1 — Loop de herramienta fallida**: el cliente le pidió al bot que ejecutara
algo que usa el CLI de Hermes (ej: "actualízate", "instala skills"). El CLI de Hermes
(`hermes`) no está en el PATH de bash del container, entonces Hermes cae en un loop
reintentando con pip, apt, sudo — todos fallando. El bot parece responder cosas raras.
**Fix**: el cliente envía `/restart` a su bot. Mata la sesión activa. El container
no necesita reiniciarse.

**Causa 2 — Conflicto de polling de Telegram**: cuando el container se reinicia,
momentáneamente hay dos conexiones de getUpdates activas. Se resuelve solo en 10-30s.



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

## Eliminar Tenant (baja permanente)

`delete_tenant()` hace el ciclo completo de baja en un solo paso.
Siempre hace backup final a SeaweedFS antes de eliminar.

```
delete_tenant("t002")                    # borra volumen del disco también
delete_tenant("t002", keep_volume=True)  # preserva /var/lib/martes/tenants/t002/
```

**Flujo interno** (automático):
1. Backup final → SeaweedFS (`tenants/t002/t002_YYYYMMDD_HHMMSS.tar.gz`)
2. Stop del container si está corriendo
3. `container.remove(force=True)` — elimina el container de Docker
4. Elimina la red `tenant-t002-net`
5. `shutil.rmtree(/var/lib/martes/tenants/t002/)` si `keep_volume=False`
6. DB → `status='archived'`

**Los backups en SeaweedFS SIEMPRE se conservan** independientemente de `keep_volume`.
Si el cliente regresa, se puede restaurar con `restore_tenant_from_backup()` + `create_tenant()`.

**Cuándo usar `keep_volume=True`**:
- El cliente puede volver en los próximos 90 días
- Los datos locales son grandes y no están todos en SeaweedFS aún
- Preferir `keep_volume=False` cuando hay certeza de que no volverá (ahorra disco)

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
El admin puede hacerlo desde aquí con:

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
→ Para cada unhealthy: `container_logs()` → si sigue fallando: `restart_tenant()`

---

## Backup y Restore

Los backups se almacenan en SeaweedFS (object storage S3 interno al stack).
El backup diario automático corre a las 3 AM UTC via Agno scheduler.

### Crear backup manual

```
backup_tenant("t001")
```

Excluye automáticamente archivos estériles: `gateway.pid`, `cron.pid`,
`*.db-wal`, `*.db-shm` (según prácticas oficiales de Hermes).
Sube a SeaweedFS → `tenants/t001/t001_YYYYMMDD_HHMMSS.tar.gz`.
Retiene los últimos 7 backups, elimina los más antiguos.

### Listar backups de un tenant

```
list_backups("t001")
```

Responde con lista de backups en SeaweedFS, ordenados del más reciente al más antiguo.
Incluye: `filename`, `size_mb`, `created_at` (ISO 8601).

### Verificar estado de todos los backups

```
check_backup_status()
```

- `ok`: backup en las últimas 26 horas
- `overdue`: más de 26 horas sin backup
- `never`: nunca se ha hecho backup

### Restaurar — flujo completo y correcto

**IMPORTANTE**: el container DEBE estar detenido antes de restaurar.

```
1. stop_tenant("t001")
2. list_backups("t001")    → ver backups disponibles y elegir el correcto
3. restore_tenant_from_backup("t001", "t001_20260522_030000.tar.gz")

   La tool automáticamente:
   a. Descarga el backup de SeaweedFS a /tmp/
   b. Extrae sobre /var/lib/martes/tenants/t001/
   c. Elimina gateway.pid, gateway.lock, cron.pid (PIDs stale)
   d. Elimina *.db-wal, *.db-shm (sidecars WAL — producen BD corrupta si quedan)
   e. chmod 600 en .env, auth.json, state.db
   f. chown 1000:1000 recursivo

4. restart_tenant("t001")
5. container_health("t001")   → verificar que el gateway arrancó
```

**Por qué el container nuevo no sobreescribe los datos restaurados:**
El entrypoint de Hermes (`docker/entrypoint.sh`) solo crea `.env`,
`config.yaml` y `SOUL.md` si NO existen. Al restaurar, estos archivos
ya están del backup — el entrypoint los respeta sin tocarlos.

**Escenario de recuperación total (servidor perdido o nuevo deploy):**

```
1. Desplegar nuevo stack (Coolify + meta-agent + db)
2. Para cada tenant:
   a. create_tenant(name, bot_token, telegram_user_id)
      → crea DB + directorios + container nuevo (datos en blanco)
   b. stop_tenant(tenant_code)
      → parar el container antes de restaurar
   c. list_backups(tenant_code)
      → SeaweedFS tiene los backups del tenant anterior
   d. restore_tenant_from_backup(tenant_code, backup_filename)
      → restaura datos del backup sobre el directorio recién creado
   e. restart_tenant(tenant_code)
      → container arranca con datos restaurados
   f. container_health(tenant_code)
```

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

1. `container_health(tenant_code)` — verificar que está running
2. Si está parado: `restart_tenant(tenant_code)`
3. Si está running pero no responde: verificar que `.env` tiene `TELEGRAM_ALLOWED_USERS`
   → Si falta: `inject_credential(tenant_code, "telegram_allowed_users", "ID_DEL_CLIENTE")`
4. **ANTES de asumir que falta API key**: revisar sección "Estado de credenciales"
   → Si `container_health` da "healthy", el bot tiene credenciales. No inyectar key.
   → Ejecutar `expire_platform_key(tenant_code, dry_run=True)` para ver el estado real.

### Bot parece confundido o responde cosas extrañas (loop de herramienta)

El cliente intentó algo que requiere el CLI de Hermes internamente y Hermes cayó en un
loop de reintentos. **No reiniciar el container** — solo la sesión.

El cliente envía `/restart` a su bot desde Telegram. El gateway hace exit 75, Docker
lo levanta en segundos, sesión nueva sin el loop.

Si el admin quiere hacerlo desde aquí: `restart_tenant(tenant_code)` (reinicia el container)
funciona también pero es más brusco — el cliente tiene que esperar ~30s.

### Container no arranca

1. `container_logs(tenant_code, lines=50)` — ver errores
2. Errores comunes:
   - `Permission denied` → `chown 1000:1000 /var/lib/martes/tenants/{code}/`
   - `Token must contain a colon` → bot token inválido (revisar formato)
   - `invalid_token` → `OPENROUTER_API_KEY` incorrecta en `.env`
   - `No such image` → imagen Hermes no descargada: `docker pull nousresearch/hermes-agent:v2026.5.16`

### Cliente pide cambiar de modelo

```
update_tenant_model(tenant_code, "deepseek/deepseek-v4-flash")
```

Sin reinicio. Efecto en el próximo mensaje del cliente.
El cliente también puede cambiarlo él mismo con `/model` en Telegram.
