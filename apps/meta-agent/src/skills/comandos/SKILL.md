---
name: comandos
description: Glosario completo de todos los comandos disponibles en el meta-agente martes.app. Consulta esta skill cuando necesites recordar parámetros exactos, valores válidos o el flujo correcto de una operación. Incluye Operador, Diagnosticador y Billing.
---

# Comandos del meta-agente martes.app

> Referencia rápida de todos los tools disponibles.
> Agentes que la usan: **Operador**, **Diagnosticador**, **Billing**.

---

## Ciclo de vida de tenants (Operador — requieren confirmación)

### `create_tenant` — Crear tenant nuevo
```
Parámetros:
  name              str  — Nombre del cliente o empresa. Ej: "Acme Corp"
  bot_token         str  — Token de @BotFather. Formato: 123456789:ABCDefgh... (8-12 dígitos : 35 chars)
  telegram_user_id  str  — ID numérico de Telegram del cliente (lo obtiene con @userinfobot)
  model             str  — Modelo LLM inicial (default: openai/gpt-4o-mini)
  email             str  — Email de contacto (opcional)

Modelos válidos:
  openai/gpt-4o-mini          (default — balance precio/calidad)
  openai/gpt-4o               (más potente, más caro)
  deepseek/deepseek-v4-flash  (1M tokens contexto, muy barato)
  anthropic/claude-3.5-haiku  (buena calidad, precio medio)
  anthropic/claude-opus-4-6   (premium)

Crea: registro en DB + directorio + .env + config.yaml + container Docker.
Trial automático: paid_until = hoy + 30 días.
```

### `stop_tenant` — Detener container
```
Parámetros:
  tenant_code  str  — Código del tenant. Ej: t001

Preserva todos los datos. Container queda en estado "exited".
Para volver a activarlo: restart_tenant().
```

### `restart_tenant` — Reiniciar container
```
Parámetros:
  tenant_code  str  — Código del tenant. Ej: t001

Reinicia un container existente (running o stopped).
```

### `delete_tenant` — Baja permanente
```
Parámetros:
  tenant_code  str   — Código del tenant. Ej: t001
  keep_volume  bool  — True: preserva datos en disco. False (default): borra todo.

Flujo automático:
  1. backup_tenant()        — backup de seguridad en SeaweedFS
  2. stop container
  3. docker rm container
  4. rmtree volumen (si keep_volume=False)
  5. DB: status = 'archived'

Los backups en SeaweedFS se conservan siempre, independientemente de keep_volume.
```

### `purge_archived_tenant` — Eliminar registro de DB
```
Parámetros:
  tenant_code     str   — Código del tenant archivado. Ej: t002
  delete_backups  bool  — True: elimina también backups en SeaweedFS. Default: False.

Solo funciona sobre tenants con status='archived'.
Elimina la fila de la tabla tenants (CASCADE borra instance_configs, payments, health_checks).
Si delete_backups=False, los backups permanecen en SeaweedFS hasta que expire la lifecycle rule (30 días).
OPERACIÓN IRREVERSIBLE — confirmar con el admin antes de ejecutar.
```

---

## Backup y restore (Operador — requieren confirmación)

### `backup_tenant` — Backup manual
```
Parámetros:
  tenant_code  str  — Código del tenant. Ej: t001

Crea tar.gz y lo sube a SeaweedFS → tenants/{code}/{code}_{timestamp}.tar.gz
Exclusiones: .cache/, archive-v0/, checkpoints/, __pycache__, *.db-wal, *.db-shm, *.pid, *.lock
Retiene los últimos 7 backups, elimina los más antiguos automáticamente.
```

### `restore_tenant_from_backup` — Restaurar volumen
```
Parámetros:
  tenant_code      str  — Código del tenant. Ej: t001
  backup_filename  str  — Nombre exacto del archivo. Ej: t001_20260524_041520.tar.gz

IMPORTANTE: el container DEBE estar detenido antes de restaurar.
Flujo automático:
  1. Descarga de SeaweedFS a /tmp/
  2. Extrae sobre /var/lib/martes/tenants/{code}/
  3. Limpia archivos estériles: gateway.pid, gateway.lock, cron.pid, *.db-wal, *.db-shm
  4. chmod 600 en .env, auth.json, state.db
  5. chown 1000:1000 recursivo

Después del restore: usa restart_tenant() o recreate_tenant_container().
```

### `recreate_tenant_container` — Recrear container tras restore
```
Parámetros:
  tenant_code  str  — Código del tenant. Ej: t002

Uso: después de restore_tenant_from_backup() cuando el container fue eliminado
     (por delete_tenant()). El volumen existe, el container no.

Prerrequisitos:
  - Volumen /var/lib/martes/tenants/{code}/ debe existir
  - .env debe estar en el volumen
  - El container NO debe existir ya

Lee recursos de instance_configs en DB. Usa la imagen actual (HERMES_IMAGE).
```

### Flujo completo de restore tras delete_tenant:
```
1. stop_tenant(tenant_code)
2. list_backups(tenant_code)                          → ver backups disponibles
3. restore_tenant_from_backup(tenant_code, filename)  → restaurar
4. restart_tenant(tenant_code)                        → si container existía
   — o —
   recreate_tenant_container(tenant_code)             → si container fue eliminado
5. container_health(tenant_code)                      → verificar
```

---

## Upgrades y recursos (Operador — requieren confirmación / sin aprobación)

### `upgrade_tenant` — Actualizar imagen Hermes  *(requiere confirmación)*
```
Parámetros:
  tenant_code  str  — Código del tenant. Ej: t001
  new_image    str  — Imagen completa con tag. Ej: nousresearch/hermes-agent:v2026.6.1

Flujo: pull nueva imagen → backup → stop → rm container → create con nueva imagen
       → health check 30s (6 intentos × 5s) → si falla: rollback automático.

Tags disponibles: https://hub.docker.com/r/nousresearch/hermes-agent/tags
Formato de tags Hermes: vAÑO.MES.DIA (ej: v2026.5.16 = Hermes v0.14.0)
Probar siempre en un tenant de test antes de upgradear clientes reales.
```

### `update_tenant_resources` — Cambiar RAM/CPU en caliente  *(sin aprobación)*
```
Parámetros:
  tenant_code  str    — Código del tenant. Ej: t001
  memory_mb    int    — RAM en MB. Mínimo: 256. (opcional)
  cpu_cores    float  — Núcleos CPU. Mínimo: 0.1. (opcional)

Perfiles de referencia:
  Ligero:    512 MB / 0.5 CPU   — tareas simples
  Estándar:  768 MB / 0.75 CPU  — default al crear
  Pesado:   1024 MB / 1.0 CPU   — tareas largas, contexto grande
  Intensivo: 2048 MB / 2.0 CPU  — subagentes, code execution

Usa docker update (cgroups en caliente) — sin restart, sin recrear container.
Persiste en instance_configs en DB — los nuevos valores se respetan si el container se recrea.
```

### `update_tenant_model` — Cambiar modelo LLM  *(sin aprobación)*
```
Parámetros:
  tenant_code  str  — Código del tenant. Ej: t001
  model_id     str  — ID del modelo en OpenRouter. Ej: deepseek/deepseek-v4-flash

Hermes recarga config.yaml en cada turno — efecto en el próximo mensaje del cliente.
El cliente también puede cambiarlo él mismo con /model desde Telegram.
```

### `update_tenant_soul` — Cambiar personalidad  *(sin aprobación)*
```
Parámetros:
  tenant_code   str  — Código del tenant. Ej: t001
  soul_content  str  — Contenido completo del nuevo SOUL.md

Hermes carga SOUL.md en cada turno — efecto en el próximo mensaje.
```

---

## Credenciales y contenido (Operador — requieren confirmación)

### `inject_credential` — Inyectar credencial en el .env del tenant
```
Parámetros:
  tenant_code       str  — Código del tenant. Ej: t001
  credential_type   str  — Tipo de credencial (enum):
                           openrouter_api_key    → OPENROUTER_API_KEY en .env (key propia del cliente)
                           telegram_bot_token    → TELEGRAM_BOT_TOKEN en .env (si el token fue revocado)
                           telegram_allowed_users → TELEGRAM_ALLOWED_USERS en .env (IDs autorizados)
                           telegram_home_channel  → TELEGRAM_HOME_CHANNEL en .env (canal de notificaciones)
                           google_token          → google_token.json (integración Google)
                           notion_key            → NOTION_KEY en .env
                           airtable_key          → AIRTABLE_KEY en .env
                           github_token          → GITHUB_TOKEN en .env
                           linear_key            → LINEAR_KEY en .env
  credential_value  str  — Valor de la credencial

IMPORTANTE: Hermes recarga .env en CADA TURNO de conversación.
El cambio toma efecto en el próximo mensaje del cliente — SIN restart del container.
Excepción: google_token puede requerir restart_tenant() para inicializar OAuth.

Al inyectar openrouter_api_key: limpia el marker .platform_key_expires inmediatamente
(el cliente ya tiene su propia key — el scheduler BYOK no necesita esperar 30 min).
```

### `inject_wiki_content` — Cargar wiki inicial  *(requiere confirmación)*
```
Parámetros:
  tenant_code          str  — Código del tenant
  company_name         str  — Nombre de la empresa
  company_description  str  — Descripción del negocio
  team_members         str  — Miembros del equipo (opcional)
  tools_used           str  — Herramientas que usan (opcional)
  active_projects      str  — Proyectos activos (opcional)
  custom_pages         str  — Páginas adicionales en JSON (opcional)

Pre-carga la LLM Wiki de Hermes con información de la empresa.
```

### `expire_platform_key` — Estado/expiración de la platform key  *(sin aprobación / dry_run por default)*
```
Parámetros:
  tenant_code  str   — Código del tenant. Ej: t001
  dry_run      bool  — True (default): solo reporta. False: aplica el blankeo.

Estados posibles en la respuesta:
  client_auth_active  → auth.json con credenciales propias → NO actuar
  client_key_active   → .env tiene key propia del cliente → NO actuar
  not_expired         → platform key activa, TTL no vencido → NO actuar
  no_expiry_marker    → TTL desactivado o tenant antiguo
  expired             → platform key vencida (dry_run=True: reporta, no actúa)
  expired_and_blanked → key blanqueada (solo cuando dry_run=False)

Usar con dry_run=True para diagnosticar estado BYOK antes de decidir.
```

### `register_payment` — Registrar pago  *(requiere confirmación)*
```
Parámetros:
  tenant_code  str    — Código del tenant. Ej: t001
  amount       float  — Monto en USD. Debe ser > 0. Ej: 30.0
  method       str    — Método de pago (enum):
                        transferencia | stripe | crypto | efectivo | otro
  months       int    — Meses que cubre el pago. Entre 1 y 12. Default: 1
  reference    str    — Número de transacción (opcional)

Extiende paid_until: si ya tiene fecha futura, extiende desde ahí.
Si el tenant estaba pausado por mora: lo reactiva automáticamente (status → active).
```

---

## Diagnóstico (Diagnosticador — solo lectura)

### `container_health` — Health check individual
```
Parámetros:
  tenant_code  str  — Código del tenant. Ej: t001

Curl al endpoint GET /health en 127.0.0.1:8642 dentro del container.
Estados posibles: healthy | unhealthy | stopped | not_found | starting
  starting: container recién creado (< 60s, 0 reinicios) — esperar, no es un error.
Devuelve: status + response_ms + details.
```

### `check_all_health` — Health check global
```
Sin parámetros.

Health check de todos los tenants en un solo call.
Devuelve: total, healthy, unhealthy, stopped, starting + lista detallada.
Usado por el scheduler health-check-all cada 5 minutos.
```

### `container_logs` — Logs del container
```
Parámetros:
  tenant_code  str  — Código del tenant
  lines        int  — Número de líneas. Default: 50
```

### `container_stats` — CPU y RAM en tiempo real
```
Parámetros:
  tenant_code  str  — Código del tenant

Devuelve: memory_mb, memory_percent, cpu_percent (snapshot puntual).
```

### `diagnose_container_error` — Diagnóstico automático
```
Parámetros:
  tenant_code  str  — Código del tenant que no arranca o está unhealthy

Combina docker inspect + logs en un solo call.
Clasifica: OOMKill | API key inválida | token Telegram | permisos | imagen no encontrada
           | crash loop (restart > 3) | exit 75 (graceful restart — es normal)
Devuelve: probable_cause + suggested_solution + log_tail.
```

### `get_tenant_config` — Configuración activa del tenant
```
Parámetros:
  tenant_code  str  — Código del tenant. Ej: t001

Lee directamente desde el volumen (no desde la DB).
Devuelve:
  config.yaml  → modelo activo, memory_enabled, session_reset_mode, max_turns
  gateway_state.json → plataformas activas, versión del gateway
  skills/      → lista de skills instalados + count
  cron/jobs.json → número de cron jobs activos

Útil cuando el cliente dice "cambié el modelo pero sigue usando el viejo" —
config.yaml puede diferir de instance_configs si el cliente usó /model desde Telegram.
No requiere que el container esté corriendo.
```

### `get_tenant_env_keys` — Claves del .env (sin valores)
```
Parámetros:
  tenant_code  str  — Código del tenant. Ej: t001

NUNCA devuelve valores — solo nombres de claves + bool 'set' (True/False).
Devuelve también:
  summary.has_openrouter_key   → OPENROUTER_API_KEY seteada y no vacía
  summary.has_telegram_token   → TELEGRAM_BOT_TOKEN seteado
  summary.has_allowed_users    → TELEGRAM_ALLOWED_USERS seteado
  summary.has_home_channel     → TELEGRAM_HOME_CHANNEL presente

Usar antes de inject_credential() para confirmar qué falta.
Si has_openrouter_key=False y el container está unhealthy → esa es la causa.
```

### `get_all_tenants` — Lista completa de tenants
```
Sin parámetros.

Devuelve: tenant_code, name, plan, status, paid_until, days_remaining,
          container_name, platforms, model.
Usar para resolver nombre → código antes de cualquier operación.
```

### `list_containers` — Lista de containers Docker
```
Sin parámetros.

Lista todos los containers con label martes.tenant (activos e inactivos).
Muestra: name, tenant_code, plan, status.
```

### `find_stale_resources` — Detectar recursos huérfanos
```
Sin parámetros.

Detecta tres tipos de inconsistencias:
  db_creating    → tenants con status='creating' sin container (create_tenant falló a mitad)
  orphan_networks → redes Docker tenant-tXXX-net sin container asociado
  orphan_dirs    → directorios en tenants/ sin registro en DB

Solo lectura — reporta. Para limpiarlos: usar el Operador.
```

### `get_server_capacity` — Capacidad del servidor
```
Sin parámetros.

Devuelve:
  - RAM total, disponible, asignada a containers de tenants
  - Disco: total, libre, % de uso en /var/lib/martes
  - Tenants corriendo / total containers
  - Slots adicionales disponibles (perfil 768 MB y 512 MB)
```

### `list_backups` — Listar backups disponibles
```
Parámetros:
  tenant_code  str  — Código del tenant (vacío = todos los tenants)

Lista desde SeaweedFS (fallback a disco local si SeaweedFS no disponible).
Orden: más reciente primero.
Devuelve: filename, size_mb, created_at (ISO 8601).
```

### `check_backup_status` — Estado de backups de todos los tenants
```
Sin parámetros.

Para cada tenant devuelve: last_backup, hours_since_backup y status:
  ok      → backup en las últimas 26 horas
  overdue → más de 26 horas sin backup
  never   → nunca se ha hecho backup
```

---

## Billing (Billing — solo lectura)

### `get_billing_summary` — Resumen ejecutivo de billing
```
Sin parámetros.

Devuelve:
  - Conteo de tenants por status (active, paused, archived)
  - Tenants que vencen en los próximos 7 días
  - Revenue del mes actual (suma de payments)
  - Cuántos están en trial (activos sin ningún pago registrado)

Usar para: "¿cómo está el billing?", "¿cuántos activos tenemos?"
```

### `get_expiring_tenants` — Tenants que vencen próximamente
```
Parámetros:
  days  int  — Ventana de búsqueda en días. Default: 7. Usar 30 para vista mensual.

Lista tenants activos y pausados con paid_until <= hoy + days.
Incluye tenants ya vencidos (days_remaining < 0).
Devuelve: code, name, status, paid_until, days_remaining, overdue.

Usar para: "¿quiénes vencen esta semana?", "¿quiénes están en mora?"
```

### `get_revenue_by_period` — Revenue de un período
```
Parámetros:
  year   int  — Año. Ej: 2026
  month  int  — Mes 1-12 (opcional — si no se pasa: año completo)

Devuelve: total_usd, payments_count, desglose por tenant.

Usar para: "¿cuánto hemos cobrado este mes?", "¿cuánto en 2026?"
```

### `get_tenant_payment_history` — Historial de pagos de un tenant
```
Parámetros:
  tenant_code  str  — Código del tenant. Ej: t001

Devuelve: estado actual del tenant + lista de todos sus pagos con
  amount, method, reference, period_start, period_end, registered_at, notes.

Usar para: "¿cuándo pagó t001?", "¿qué pagos tiene registrados Acme?"
```

---

## Schedules automáticos (6 schedules activos en producción)

| Schedule | Cron | Qué hace |
|---|---|---|
| `daily-backup-all` | `0 3 * * *` (3 AM UTC) | Backup de todos los tenants activos → SeaweedFS + backup_log |
| `health-check-all` | `*/5 * * * *` (cada 5 min) | Health check + alerta Telegram si unhealthy/stopped, disco > 80% o RAM < 20% |
| `billing-check` | `0 9 * * *` (9 AM UTC) | Alertas a 7d y 3d antes del vencimiento + alerta día 0 + auto-suspend tras grace_days |
| `expire-platform-keys` | `*/30 * * * *` (cada 30 min) | BYOK: blanquea platform keys expiradas en .env de tenants |
| `docker-cleanup` | `0 4 * * 0` (domingos 4 AM) | Elimina imágenes Docker de Hermes que ya no están en uso |
| `prune-old-data` | `0 2 * * 0` (domingos 2 AM) | Purge de traces (>30d), sessions (>90d), health_checks (>90d) |

---

## Resolución nombre → código

Cuando el admin mencione un tenant por nombre:
1. Llama `get_all_tenants()` para obtener la lista
2. Identifica el `tenant_code` (tXXX) que corresponde
3. Usa SIEMPRE el código en los tools, NUNCA el nombre
4. Confirma mostrando ambos: "Voy a hacer X a Acme (t001). ¿Confirmas?"

---

## Referencia rápida de qué agente hace qué

| Qué quieres hacer | Agente | Aprobación |
|---|---|---|
| Ver estado de un tenant | Diagnosticador | No |
| Ver logs, stats, diagnóstico | Diagnosticador | No |
| Ver backups disponibles | Diagnosticador | No |
| Ver configuración activa (modelo, plataformas) | Diagnosticador | No |
| Ver claves del .env | Diagnosticador | No |
| Ver capacidad del servidor | Diagnosticador | No |
| Crear / parar / reiniciar tenant | Operador | Sí |
| Backup / restore / upgrade | Operador | Sí |
| Inyectar credenciales | Operador | Sí |
| Registrar pago | Operador | Sí |
| Cambiar modelo / soul / recursos | Operador | No |
| Estado de billing, revenue | Billing | No |
| Vencimientos, historial de pagos | Billing | No |
