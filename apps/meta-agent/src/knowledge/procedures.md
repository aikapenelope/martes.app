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
