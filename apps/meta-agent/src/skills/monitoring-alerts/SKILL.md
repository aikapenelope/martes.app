---
name: monitoring-alerts
description: "Monitoreo de salud, alertas proactivas, y deteccion de problemas"
license: MIT
metadata:
  tags: [monitoring, health, alerts, proactive, cron]
  category: operations
---

# Monitoreo y Alertas

## Health check global

Ejecutar periodicamente (cada 5 min via scheduler):
1. Listar todos los containers con label `martes.tenant`
2. Para cada uno running: verificar health endpoint
3. Para cada uno stopped: verificar si deberia estar running (status=active en DB)
4. Reportar inconsistencias

## Metricas a monitorear

### Por container:
- **Memory %**: >85% = warning, >95% = critical
- **CPU %**: >80% sostenido = warning
- **Restart count**: >3 en 1 hora = critical
- **Health response time**: >5s = warning, timeout = critical

### Por plataforma:
- **Disk usage**: >80% = warning, >90% = critical
- **PostgreSQL connections**: >40/50 = warning
- **Docker images**: limpiar imagenes sin usar (>5GB)

## Alertas por Telegram

Cuando se detecta un problema, notificar al admin via Telegram:

```
ALERTA: Container hermes-t003 unhealthy
- Status: running pero health check falla
- Ultima respuesta: timeout (>10s)
- Accion sugerida: restart_tenant("t003")
```

```
ALERTA: Tenant t005 sin pago
- Plan: equipo ($100/mo)
- Pagado hasta: 2026-05-15 (hace 5 dias)
- Accion sugerida: contactar cliente o pausar
```

```
ALERTA: Disco al 85%
- Uso: 136GB / 160GB
- Tenants: 18 activos
- Accion sugerida: limpiar backups antiguos o docker system prune
```

## Deteccion de problemas comunes

### Container en restart loop
- Sintoma: restart count incrementa cada 30s
- Causa probable: error en config o .env
- Accion: revisar logs, pausar container, notificar admin

### Tenant activo pero container stopped
- Sintoma: DB dice status=active pero container no existe
- Causa: crash sin restart, o alguien lo elimino manualmente
- Accion: recrear container con misma config

### Memoria creciente (memory leak)
- Sintoma: memory % sube constantemente sin bajar
- Causa: sesiones acumuladas, wiki grande, browser no cerrado
- Accion: restart programado (session_reset deberia manejarlo)

### Disco lleno
- Sintoma: containers no pueden escribir, errores de I/O
- Causa: logs sin rotacion, backups acumulados, state.db grande
- Accion: limpiar logs, rotar backups, docker system prune

## Scheduler de Agno (jobs periodicos)

El meta-agente tiene scheduler habilitado (poll cada 60s).
Se pueden crear jobs via la API de AgentOS:

```
POST /schedules
{
  "name": "health-check-global",
  "cron": "*/5 * * * *",
  "agent_id": "diagnosticador",
  "input": "Ejecuta un health check global y reporta problemas"
}
```
