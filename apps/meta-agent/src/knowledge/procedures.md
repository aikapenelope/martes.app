# Procedimientos Operativos del Meta-Agente

## Crear Tenant Nuevo

### Prerequisitos
- Nombre del cliente
- Plan (basico/equipo/pro)
- Bot token de Telegram (del @BotFather del cliente)
- Email de contacto (opcional)

### Pasos (en orden estricto)

1. **Crear registro en DB**
   - Tool: `create_tenant_record(name, plan, email)`
   - Genera tenant_code automatico (t001, t002, ...)
   - Estado inicial: "creating"

2. **Escribir config en disco**
   - Tool: `write_tenant_config(tenant_code, plan, bot_token)`
   - Copia template del plan
   - Escribe .env con credenciales
   - Crea estructura de directorios
   - Aplica permisos (chown 1000:1000)

3. **Crear container Docker**
   - Tool: `create_tenant_container(tenant_code, plan, bot_token)`
   - Crea bridge network aislada
   - Lanza container con limites de recursos
   - Conecta a red de Traefik

4. **Verificar health**
   - Tool: `check_tenant_health(tenant_code)`
   - Esperar ~30 segundos para que arranque
   - Si falla: revisar logs con `get_tenant_logs(tenant_code)`

5. **Activar tenant**
   - Tool: `update_tenant_status(tenant_code, "active")`
   - Solo si health check paso

### Si algo falla
- Reportar el error al admin
- NO dejar el tenant en estado "creating" indefinidamente
- Si el container fallo: revisar logs, sugerir solucion
- Si fue error de config: corregir y reintentar

---

## Pausar Tenant (No Pago)

1. Confirmar con el admin (accion destructiva)
2. `stop_tenant_container(tenant_code)` — detiene container, preserva datos
3. `update_tenant_status(tenant_code, "paused")`
4. Reportar: "Container detenido. Datos preservados. Se puede reactivar."

---

## Reactivar Tenant

1. `restart_tenant_container(tenant_code)` — si el container existe pero esta parado
2. `check_tenant_health(tenant_code)` — verificar que arranco bien
3. `update_tenant_status(tenant_code, "active")`
4. Reportar: "Tenant reactivado y funcionando."

---

## Registrar Pago

1. `register_payment(tenant_code, amount, method, months=1, reference)`
2. Esto automaticamente:
   - Calcula period_start y period_end
   - Actualiza paid_until del tenant
   - Marca tenant como "active" si estaba pausado

---

## Conectar Integracion

### Google Workspace
1. Admin provee OAuth token (ya29.xxx...)
2. `inject_credential(tenant_code, "google_token", token_json)`
3. `restart_tenant_container(tenant_code)` — para que Hermes cargue el token
4. Reportar: "Google Workspace conectado."

### Notion / Airtable / GitHub / Linear
1. Admin provee API key
2. `inject_credential(tenant_code, "notion_key|airtable_key|github_token|linear_key", key)`
3. `restart_tenant_container(tenant_code)`
4. Reportar: "[Servicio] conectado."

---

## Health Check Global

1. `check_all_health()` — revisa todos los containers
2. Reportar resumen: X healthy, Y unhealthy, Z stopped
3. Para cada unhealthy: sugerir accion (restart, revisar logs)
4. Para cada stopped con status "active" en DB: alertar inconsistencia

---

## Troubleshooting

### Container no arranca
1. `get_tenant_logs(tenant_code, lines=100)`
2. Buscar errores comunes:
   - "Permission denied" → problema de permisos en volumen
   - "Token must contain a colon" → bot token invalido
   - "OOM" → necesita mas RAM (upgrade de plan)
   - "Address already in use" → container duplicado

### Container unhealthy
1. Verificar que esta corriendo: `check_tenant_health(tenant_code)`
2. Si esta corriendo pero unhealthy: API server puede no estar habilitado
3. Intentar restart: `restart_tenant_container(tenant_code)`
4. Si persiste: revisar logs

### Tenant no responde en Telegram
1. Verificar container esta running y healthy
2. Verificar bot token es correcto en .env
3. Verificar TELEGRAM_ALLOWED_USERS no bloquea al usuario
4. Restart del container para forzar reconexion

---

## Backup de Tenant

### Cuándo hacer backup
- Diariamente para todos los tenants activos (verificar con check_backup_status())
- Antes de operaciones destructivas (archivado, upgrade de imagen)
- Cuando un tenant no paga y se va a pausar (backup previo a pausa)

### Crear backup
1. Verificar que el tenant existe: `get_all_tenants()`
2. Crear backup: `backup_tenant(tenant_code)`
   - Genera: `/var/lib/martes/backups/{tenant_code}_{YYYYMMDD}_{HHMMSS}.tar.gz`
   - Incluye TODO el /opt/data: state.db, config.yaml, .env, SOUL.md, sessions/, memories/, wiki/, skills/, cron/
3. Verificar que el archivo se creó: `list_backups(tenant_code)`

### Restaurar backup
1. Listar backups disponibles: `list_backups(tenant_code)`
2. Si el container está corriendo, detenerlo primero: `stop_tenant(tenant_code)`
3. Restaurar: `restore_tenant_from_backup(tenant_code, "nombre_del_archivo.tar.gz")`
4. Reiniciar el container: `restart_tenant(tenant_code)` o crear nuevo container
5. Verificar health: `container_health(tenant_code)`

### Verificar estado de backups
- `check_backup_status()` — muestra todos los tenants y cuándo fue su último backup
- Status "ok" = backup en las últimas 26 horas
- Status "overdue" = más de 26 horas sin backup
- Status "never" = nunca se ha hecho backup

### Política de retención recomendada
- Plan básico: 7 días (7 backups)
- Plan equipo: 14 días
- Plan pro: 30 días
- Los backups más antiguos se eliminan manualmente por el admin

---

## Flujo No-Pago con Backup

```
Día 30: No paga
  1. backup_tenant(tenant_code)          ← backup antes de pausar
  2. stop_tenant(tenant_code)            ← detener container
  3. DB: status → "paused"               ← automático en stop_tenant()

Día 45: Sigue sin pagar
  1. backup_tenant(tenant_code)          ← backup antes de archivar (redundante pero seguro)
  2. Archivar volumen a almacenamiento   ← operación futura
  3. Eliminar directorio local del tenant

Si paga antes del día 90:
  1. restore_tenant_from_backup(tenant_code, último_backup)
  2. create_tenant() si el container ya no existe
  3. restart_tenant(tenant_code)
```
