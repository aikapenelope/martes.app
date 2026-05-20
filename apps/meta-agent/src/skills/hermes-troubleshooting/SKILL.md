---
name: hermes-troubleshooting
description: "Diagnostico y resolucion de problemas comunes en containers Hermes"
license: MIT
metadata:
  tags: [hermes, docker, troubleshooting, diagnostics]
  category: operations
---

# Troubleshooting de Hermes Agent

## Container no arranca (restart loop)

### Sintomas
- `docker ps` muestra status "Restarting"
- Logs muestran crash repetido

### Diagnostico
1. `docker logs hermes-{code} --tail 50`
2. Buscar el primer error (no los repetidos)

### Causas y soluciones

| Error en logs | Causa | Solucion |
|---------------|-------|----------|
| `Permission denied: /opt/data` | UID/GID incorrecto | `chown -R 1000:1000 /var/lib/martes/tenants/{code}/` |
| `Token must contain a colon` | Bot token invalido | Verificar formato `123456:ABC-DEF` en .env |
| `OPENROUTER_API_KEY not set` | .env vacio o mal formateado | Revisar /var/lib/martes/tenants/{code}/.env |
| `OOMKilled` | Excede memory limit | Subir plan o reducir toolset en config.yaml |
| `Address already in use` | Container duplicado | `docker rm -f hermes-{code}` y recrear |
| `sqlite3.OperationalError: database is locked` | Dos gateways en mismo volumen | Solo un container por volumen |
| `ModuleNotFoundError` | Imagen corrupta o version incorrecta | `docker pull nousresearch/hermes-agent:0.14.0` |

## Container corriendo pero no responde en Telegram

### Diagnostico
1. Verificar container running: `docker ps | grep hermes-{code}`
2. Verificar health: `docker exec hermes-{code} wget -q -O - http://localhost:8642/health`
3. Revisar logs de Telegram: `docker logs hermes-{code} 2>&1 | grep -i telegram`

### Causas
- Bot token expirado o revocado → crear nuevo con @BotFather
- `TELEGRAM_ALLOWED_USERS` bloquea al usuario → revisar .env
- Webhook vs polling conflict → restart container
- Rate limit de Telegram → esperar 5 min y reintentar

## Container unhealthy (health check falla)

### Diagnostico
1. `docker exec hermes-{code} wget -q -O - http://localhost:8642/health`
2. Si timeout: el proceso interno esta colgado
3. Si connection refused: API_SERVER_ENABLED no esta en true

### Soluciones
- Restart: `docker restart hermes-{code}`
- Si persiste: revisar logs por deadlock o memory pressure
- Verificar `API_SERVER_ENABLED=true` en environment del container

## Alto consumo de memoria

### Diagnostico
- `docker stats hermes-{code}` — ver MEM USAGE vs LIMIT
- Si >90% del limit: riesgo de OOM

### Causas
- Playwright/Chromium activo (plan pro): consume ~300MB extra
- Muchas sesiones activas simultaneas
- Wiki muy grande cargada en memoria

### Soluciones
- Reducir toolset (quitar browser si no se usa)
- Aumentar memory limit (upgrade plan)
- Restart para liberar sesiones acumuladas

## SQLite corrupto (state.db)

### Sintomas
- Errores `sqlite3.DatabaseError` en logs
- Agente pierde historial de conversaciones

### Solucion
1. Parar container
2. Backup del state.db corrupto: `cp state.db state.db.bak`
3. Intentar recovery: `sqlite3 state.db ".recover" | sqlite3 state_new.db`
4. Si falla: eliminar state.db (se recrea vacio, pierde historial)
5. Reiniciar container

## Errores de red (no puede llamar APIs)

### Sintomas
- `ConnectionError` o `TimeoutError` en logs
- Agente no puede buscar web ni llamar OpenRouter

### Diagnostico
- `docker exec hermes-{code} wget -q -O - https://openrouter.ai/api/v1/models`
- Si falla: problema de DNS o red

### Soluciones
- Verificar DNS: container debe tener `dns: ["1.1.1.1"]`
- Verificar que la bridge network tiene acceso a internet (internal: false)
- Verificar que no hay firewall bloqueando egress
