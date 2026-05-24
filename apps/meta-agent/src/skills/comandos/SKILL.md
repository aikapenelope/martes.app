---
name: comandos
description: Glosario completo de todos los comandos disponibles en el meta-agente martes.app. Consulta esta skill cuando necesites recordar parámetros exactos, valores válidos o el flujo correcto de una operación.
---

# Comandos del meta-agente martes.app

> Referencia rápida de todos los tools disponibles. Cargada por Operador y Diagnosticador.

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
```

---

## Backup y restore (Operador — requieren confirmación)

### `backup_tenant` — Backup manual
```
Parámetros:
  tenant_code  str  — Código del tenant. Ej: t001

Crea tar.gz y lo sube a SeaweedFS → tenants/{code}/{code}_{timestamp}.tar.gz
Exclusiones: .cache/, archive-v0/, checkpoints/, __pycache__, *.db-wal, *.db-shm, *.pid
```

### `restore_tenant_from_backup` — Restaurar volumen
```
Parámetros:
  tenant_code      str  — Código del tenant. Ej: t001
  backup_filename  str  — Nombre exacto del archivo. Ej: t001_20260524_041520.tar.gz

IMPORTANTE: el container debe estar detenido o no existir antes de restaurar.
Descarga de SeaweedFS → extrae → limpia archivos estériles → fija permisos.
Después del restore: usa restart_tenant() o recreate_tenant_container().
```

### `recreate_tenant_container` — Recrear container tras restore
```
Parámetros:
  tenant_code  str  — Código del tenant. Ej: t002

Uso: después de restore_tenant_from_backup() cuando el container fue eliminado
     (por delete_tenant()). El volumen existe, el container no.

Prerequisitos:
  - Volumen /var/lib/martes/tenants/{code}/ debe existir
  - .env debe estar en el volumen
  - El container NO debe existir ya

Lee recursos de instance_configs en DB. Usa la imagen actual (HERMES_IMAGE).
```

### Flujo completo de restore tras delete_tenant:
```
1. lista los backups de tXXX
2. restaura tXXX desde tXXX_YYYYMMDD_HHMMSS.tar.gz
3. recrea el container de tXXX
4. health check de tXXX
```

---

## Upgrades y recursos (Operador — requieren confirmación)

### `upgrade_tenant` — Actualizar imagen Hermes
```
Parámetros:
  tenant_code  str  — Código del tenant. Ej: t001
  new_image    str  — Imagen completa con tag. Ej: nousresearch/hermes-agent:v2026.6.1

Flujo: pull nueva imagen → backup → stop → rm container → create con nueva imagen
       → health check (30s) → si falla: rollback automático a imagen anterior.

Tags disponibles: https://hub.docker.com/r/nousresearch/hermes-agent/tags
Formato de tags Hermes: vAÑO.MES.DIA (ej: v2026.5.16 = Hermes v0.14.0)
```

### `update_tenant_resources` — Cambiar RAM/CPU en caliente
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
```

### `update_tenant_model` — Cambiar modelo LLM
```
Parámetros:
  tenant_code  str  — Código del tenant. Ej: t001
  model_id     str  — ID del modelo en OpenRouter. Ej: deepseek/deepseek-v4-flash

Hermes recarga config.yaml en cada turno — efecto en el próximo mensaje.
No requiere aprobación.
```

### `update_tenant_soul` — Cambiar personalidad
```
Parámetros:
  tenant_code   str  — Código del tenant. Ej: t001
  soul_content  str  — Contenido completo del nuevo SOUL.md

Hermes carga SOUL.md en cada turno — efecto en el próximo mensaje.
No requiere aprobación.
```

---

## Credenciales y contenido (Operador — requieren confirmación)

### `inject_credential` — Inyectar credencial
```
Parámetros:
  tenant_code       str  — Código del tenant. Ej: t001
  credential_type   str  — Tipo de credencial (enum):
                           google_token  → google_token.json
                           notion_key    → NOTION_KEY en .env
                           airtable_key  → AIRTABLE_KEY en .env
                           github_token  → GITHUB_TOKEN en .env
                           linear_key    → LINEAR_KEY en .env
  credential_value  str  — Valor de la credencial

Requiere restart_tenant() para que Hermes cargue la nueva credencial.
```

### `inject_wiki_content` — Cargar wiki inicial
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

### `register_payment` — Registrar pago
```
Parámetros:
  tenant_code  str    — Código del tenant. Ej: t001
  amount       float  — Monto en USD. Debe ser > 0. Ej: 30.0
  method       str    — Método de pago (enum):
                        transferencia | stripe | crypto | efectivo | otro
  months       int    — Meses que cubre el pago. Entre 1 y 12. Default: 1
  reference    str    — Número de transacción (opcional)

Actualiza paid_until en DB: si ya tiene fecha futura, extiende desde ahí.
```

---

## Diagnóstico (Diagnosticador — solo lectura)

### `container_health` — Health check individual
```
Parámetros:
  tenant_code  str  — Código del tenant. Ej: t001

Curl al endpoint GET /health en 127.0.0.1:8642 dentro del container.
Devuelve: healthy | unhealthy | stopped | not_found + response_ms + details.
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
           | crash loop (restart > 3) | exit 75 (graceful restart normal)
Devuelve: probable_cause + suggested_solution + log_tail.
```

### `get_server_capacity` — Capacidad del servidor
```
Sin parámetros.

Devuelve:
  - RAM total, disponible, asignada a containers
  - Disco: total, libre, % de uso
  - Tenants corriendo / total
  - Slots adicionales disponibles a perfil 768 MB y 512 MB
```

### `list_backups` — Listar backups
```
Parámetros:
  tenant_code  str  — Código del tenant (vacío = todos los tenants)

Lista desde SeaweedFS (fallback a disco local). Ordenado: más reciente primero.
```

### `check_backup_status` — Estado de backups
```
Sin parámetros.

Muestra last_backup, hours_since_backup y status (ok | overdue | never)
para todos los tenants.
```

---

## Schedules automáticos

| Schedule | Cron | Endpoint | Qué hace |
|---|---|---|---|
| `daily-backup-all` | `0 3 * * *` (3 AM UTC) | POST /maintenance/backup-all | Backup de todos los tenants activos |
| `health-check-all` | `*/5 * * * *` (cada 5 min) | POST /maintenance/health-check-all | Health check + alerta Telegram si unhealthy o disco > 80% |
| `billing-check` | `0 9 * * *` (9 AM UTC) | POST /maintenance/billing-check | Alerta Telegram si paid_until vence en ≤ 5 días |

Para verificar que los schedules corrieron:
```
GET http://100.104.89.128:8000/schedules/{id}/runs
→ status: success | failed, triggered_at
```

---

## Resolución nombre → código

Cuando el admin mencione un tenant por nombre:
1. Llama `get_all_tenants()` para obtener la lista
2. Identifica el `tenant_code` (tXXX) que corresponde
3. Usa SIEMPRE el código en los tools, NUNCA el nombre
4. Confirma mostrando ambos: "Voy a hacer X a Acme (t001). ¿Confirmas?"
