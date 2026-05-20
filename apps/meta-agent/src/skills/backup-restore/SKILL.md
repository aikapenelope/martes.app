---
name: backup-restore
description: "Procedimientos de backup y restauracion de tenants Hermes"
license: MIT
metadata:
  tags: [backup, restore, disaster-recovery, volumes]
  category: operations
---

# Backup y Restauracion de Tenants

## Que se respalda

Todo el estado de un tenant es UN directorio:
```
/var/lib/martes/tenants/{code}/
├── state.db       ← Historial, sesiones (SQLite)
├── config.yaml    ← Configuracion
├── .env           ← Credenciales
├── SOUL.md        ← Personalidad
├── sessions/      ← Conversaciones
├── memories/      ← Memoria persistente
├── skills/        ← Skills instalados
├── cron/          ← Jobs programados
├── wiki/          ← Knowledge base del tenant
└── workspace/     ← Archivos de trabajo
```

## Backup manual de un tenant

```bash
# 1. Pausar container (evita escrituras durante backup)
docker pause hermes-{code}

# 2. Comprimir volumen
tar czf /var/lib/martes/backups/{code}-$(date +%Y%m%d-%H%M).tar.gz \
  /var/lib/martes/tenants/{code}/

# 3. Reanudar container
docker unpause hermes-{code}
```

Tiempo estimado: <5 segundos para un tenant tipico (~50MB).

## Restaurar un tenant desde backup

```bash
# 1. Parar y eliminar container actual (si existe)
docker stop hermes-{code} && docker rm hermes-{code}

# 2. Restaurar volumen
tar xzf /var/lib/martes/backups/{code}-YYYYMMDD-HHMM.tar.gz -C /

# 3. Verificar permisos
chown -R 1000:1000 /var/lib/martes/tenants/{code}/

# 4. Recrear container (usar create_tenant del Operador)
# O manualmente con los mismos parametros del docker run original
```

## Backup de la base de datos de plataforma

```bash
# PostgreSQL dump
docker exec martes-db pg_dump -U martes martes | gzip > \
  /var/lib/martes/backups/db-$(date +%Y%m%d).sql.gz
```

## Backup automatizado (cron del host)

```bash
# /etc/cron.d/martes-backup
0 3 * * * root /opt/martes/scripts/backup-all.sh
```

Script `backup-all.sh`:
```bash
#!/bin/bash
BACKUP_DIR=/var/lib/martes/backups
DATE=$(date +%Y%m%d)

# Backup DB
docker exec martes-db pg_dump -U martes martes | gzip > $BACKUP_DIR/db-$DATE.sql.gz

# Backup cada tenant
for dir in /var/lib/martes/tenants/*/; do
  code=$(basename "$dir")
  docker pause hermes-$code 2>/dev/null
  tar czf $BACKUP_DIR/$code-$DATE.tar.gz "$dir"
  docker unpause hermes-$code 2>/dev/null
done

# Limpiar backups >7 dias
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete
find $BACKUP_DIR -name "*.sql.gz" -mtime +7 -delete
```

## Flujo de no-pago con backup

| Dia | Accion | Comando |
|-----|--------|---------|
| 0 | Activo | — |
| 30 | No paga → Pausar | `stop_tenant(code)` |
| 45 | No paga → Archivar | Backup + `remove_tenant(code)` |
| 90 | No paga → Eliminar backup | `rm backup` |

Si paga antes del dia 90: restaurar desde backup.
