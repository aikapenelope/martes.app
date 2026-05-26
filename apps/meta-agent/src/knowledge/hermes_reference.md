# Hermes Agent — Referencia Técnica para el Meta-Agente

> v0.14.0 (tag Docker Hub: `v2026.5.16`) — mayo 2026
> Ref: https://hermes-agent.nousresearch.com/docs

## Qué es Hermes

Agente IA auto-mejorante. Cada tenant de martes.app es un container Hermes
**completo y sin restricciones**. No existen tiers ni planes — todos los
tenants son idénticos técnicamente. El límite del cliente es solo el
presupuesto de tokens (créditos de OpenRouter).

## Imagen Docker

- Imagen pineada: `nousresearch/hermes-agent:v2026.5.16`
- Versioning: los tags de Hermes usan `vAÑO.MES.DIA` (no semver)
- Entrypoint: `/usr/bin/tini -g -- /opt/hermes/docker/entrypoint.sh`
- Comando: `gateway run`
- Puerto API: `8642` (cuando `API_SERVER_ENABLED=true`)

## Estructura del volumen (/opt/data dentro del container)

```
/opt/data/
├── config.yaml         ← configuración (hot-reload en cada turno)
├── .env                ← API keys (permisos 600, hot-reload en cada turno)
├── SOUL.md             ← personalidad (hot-reload en cada turno)
├── state.db            ← SQLite: sesiones, historial, búsqueda FTS5
├── gateway_state.json  ← estado del gateway (plataformas, sesiones activas)
├── channel_directory.json ← mapa de canales por plataforma
├── pairing/            ← datos de emparejamiento por plataforma
├── auth.json           ← credenciales OAuth (permisos 600)
├── memories/           ← MEMORY.md + USER.md (auto-gestionados)
├── skills/             ← skills instalados
├── wiki/               ← base de conocimiento del cliente
├── cron/               ← jobs programados (cron/jobs.json)
├── sessions/           ← historial de conversaciones
├── workspace/          ← directorio de trabajo del agente
├── logs/               ← agent.log + errors.log
└── home/               ← HOME para subprocesos (git, ssh, npm)
```

**Hot-reload crítico**: Hermes recarga `config.yaml`, `.env` y `SOUL.md` al
inicio de cada turno de conversación. Cambiar estos archivos en el volumen
tiene efecto en el próximo mensaje SIN reiniciar el container.

## Variables de entorno en `.env` del tenant

| Variable | Obligatoria | Descripción |
|---|---|---|
| `OPENROUTER_API_KEY` | Sí | Key de OpenRouter con créditos del cliente |
| `OPENROUTER_BASE_URL` | Sí | `https://openrouter.ai/api/v1` |
| `TELEGRAM_BOT_TOKEN` | Sí | Token del bot de @BotFather |
| `TELEGRAM_ALLOWED_USERS` | Sí | ID de Telegram del cliente. Sin esto: bot no responde |

**TELEGRAM_ALLOWED_USERS es crítico**: si no está seteado, el bot no responde
a nadie y logea un warning de seguridad. Siempre se escribe al crear el tenant.

## Variables de entorno del container Docker (no del .env)

Estas se pasan en `docker run`, no se leen desde el volumen:

| Variable | Valor | Por qué |
|---|---|---|
| `HERMES_UID` | `1000` | Remapeo de UID para permisos del volumen |
| `HERMES_GID` | `1000` | Remapeo de GID |
| `API_SERVER_ENABLED` | `true` | Habilita `/health` en `:8642` para health checks |

**Nota**: `API_SERVER_HOST` NO se configura. El API server escucha en
`127.0.0.1` dentro del container. Los health checks del meta-agente
usan `docker exec` para acceder al endpoint desde dentro, no por red.
Ref: https://hermes-agent.nousresearch.com/docs/user-guide/docker

## Backup — qué incluir y qué excluir

Fuente oficial: `hermes_cli/backup.py` del repo de Hermes.

### Archivos que NUNCA deben estar en un backup:

| Archivo/patrón | Por qué |
|---|---|
| `gateway.pid`, `cron.pid` | PIDs del proceso. Stale en cualquier restore. |
| `*.db-wal`, `*.db-shm`, `*.db-journal` | Sidecars WAL de SQLite. Si van en el backup junto al `.db`, producen un **torn restore** (BD inconsistente). Hermes los excluye explícitamente. |
| `checkpoints/` | Caches de sesión locales, no portables entre containers. |
| `backups/` | Para evitar backups anidados. |
| `*.pyc`, `*.pyo` | Bytecache, se regeneran. |

### Archivos que necesitan permisos 600 tras el restore:

`.env`, `auth.json`, `state.db`

### Archivos de estado críticos (mínimo viable para restore funcional):

`state.db`, `config.yaml`, `.env`, `auth.json`, `cron/jobs.json`,
`gateway_state.json`, `channel_directory.json`, `pairing/`

## Restore — flujo correcto

El entrypoint de Docker (`docker/entrypoint.sh`) solo copia los defaults
(`.env`, `config.yaml`, `SOUL.md`) si **no existen**. Esto significa que
al restaurar un backup y arrancar un container nuevo, el entrypoint
respeta los archivos restaurados y no los sobreescribe.

**Flujo completo de restore:**

```
1. stop_tenant(tenant_code)         → parar container (obligatorio)
2. list_backups(tenant_code)        → elegir backup de SeaweedFS
3. restore_tenant_from_backup(      → descarga SeaweedFS → extrae
     tenant_code, backup_filename)
     
   Interno (automático en restore_tenant_from_backup):
   a. Descarga el tar.gz de SeaweedFS a /tmp/
   b. Extrae sobre /var/lib/martes/tenants/{code}/
   c. LIMPIA archivos estériles:
      - gateway.pid, gateway.lock, cron.pid
      - *.db-wal, *.db-shm (sidecars WAL stale)
   d. Aplica chmod 600 a .env, auth.json, state.db
   e. chown 1000:1000 recursivo (usuario hermes)
   
4. restart_tenant(tenant_code)      → nuevo container, datos restaurados
5. container_health(tenant_code)    → verificar que arrancó
```

**Por qué limpiar después del restore:**
- `gateway.pid` stale puede confundir al gateway en el arranque
- `*.db-wal` stale junto al `.db` de la snapshot produce un estado SQLite
  inconsistente en el primer open — Hermes documenta esto explícitamente
  como "torn restore" en su código fuente

## Lo que el cliente puede hacer desde Telegram

```
/model openai/gpt-4o              → cambia modelo, persiste en config.yaml
/model deepseek/deepseek-v4-flash → modelo más barato con 1M ctx
/skills browse                    → explorar skills del hub
/skills install official/notion   → instalar skill
/cron add "0 9 * * *" "resumen"   → programar tarea
/memory                           → ver memoria persistente
/reset                            → nueva sesión (memoria preservada)
/restart                          → reinicia el gateway (exit 75 → Docker lo revive)
```

El meta-agente puede hacer los mismos cambios desde fuera sin reiniciar:
- `update_tenant_model(tenant_code, model_id)` → edita config.yaml
- `update_tenant_soul(tenant_code, soul_content)` → edita SOUL.md
- `inject_credential(tenant_code, "openrouter_api_key", nueva_key)` → edita .env

## Errores comunes

| Error | Causa | Solución |
|---|---|---|
| Bot no responde | `TELEGRAM_ALLOWED_USERS` faltante | `inject_credential(t, "telegram_allowed_users", id)` |
| `Permission denied /opt/data` | UID/GID incorrecto | `chown 1000:1000 -R /var/lib/martes/tenants/{code}/` |
| `Token must contain a colon` | Bot token inválido | Verificar formato `123456789:ABCdef...` |
| `Connection refused :8642` | API server no habilitado | Verificar `API_SERVER_ENABLED=true` en docker run |
| 402 en LLM | Créditos agotados | `inject_credential` con nueva key o recargar créditos |
| `No such image` | Imagen no descargada | `docker pull nousresearch/hermes-agent:v2026.5.16` |
| BD corrupta tras restore | WAL sidecars en backup | `restore_tenant_from_backup` los limpia automáticamente |

## Actualización de versión de Hermes

1. Backup del volumen: `backup_tenant(tenant_code)`
2. Cambiar `hermes_image` en `config.py` del meta-agente → nuevo PR → deploy
3. Para el tenant específico: `stop_tenant()` → recrear container con nueva imagen
4. Verificar health: `container_health(tenant_code)`
5. Si falla: `restore_tenant_from_backup()` + recrear con imagen anterior
