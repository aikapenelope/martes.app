# Hermes Agent — Referencia Tecnica para el Meta-Agente

## Que es Hermes

Hermes es un agente IA que corre como container Docker. Cada tenant tiene su propio container
con su propio volumen de datos. No comparten nada entre si.

## Imagen Docker

- Imagen: `nousresearch/hermes-agent:0.14.0`
- Base: Debian 13 + Python 3.13 + Node.js + Playwright
- Entrypoint: `/usr/bin/tini -g -- /opt/hermes/docker/entrypoint.sh`
- Comando: `gateway run`
- Puerto interno: 8642 (API server)
- Dashboard: puerto 9119 (opcional, habilitado con HERMES_DASHBOARD=1)

## Estructura del volumen (/opt/data dentro del container)

```
/opt/data/
├── state.db              ← SQLite: sesiones, historial, busqueda FTS5
├── config.yaml           ← Configuracion completa del agente
├── .env                  ← API keys (permisos 600)
├── SOUL.md               ← Personalidad del agente
├── auth.json             ← OAuth credentials (si usa Nous Portal)
├── sessions/             ← Historial de conversaciones (JSON)
├── memories/             ← MEMORY.md + USER.md (persistente)
├── skills/               ← Skills instalados (carpetas con SKILL.md)
├── cron/                 ← Jobs programados (jobs.json + outputs)
├── logs/                 ← Logs del runtime
├── wiki/                 ← LLM Wiki (knowledge base en markdown)
├── workspace/            ← Directorio de trabajo del agente
└── home/                 ← HOME para subprocesos (git, ssh, npm)
```

## Variables de entorno criticas

| Variable | Requerida | Descripcion |
|----------|-----------|-------------|
| HERMES_UID | Si | UID del usuario hermes dentro del container (default 1000) |
| HERMES_GID | Si | GID del grupo hermes (default 1000) |
| OPENROUTER_API_KEY | Si | Key para el LLM via OpenRouter |
| TELEGRAM_BOT_TOKEN | Si* | Token del bot de Telegram (*si usa Telegram) |
| TELEGRAM_ALLOWED_USERS | No | IDs de usuarios permitidos (comma-separated) |
| API_SERVER_ENABLED | No | Habilita API OpenAI-compatible en :8642 |
| API_SERVER_HOST | No | Host del API server (0.0.0.0 para exponer) |
| API_SERVER_KEY | No | Key de autenticacion para el API server |
| HERMES_DASHBOARD | No | 1 para habilitar dashboard web en :9119 |
| HERMES_DASHBOARD_HOST | No | Host del dashboard (default 0.0.0.0) |

## Networking

- Cada tenant tiene su propia bridge network aislada
- Tambien se conecta a la red de Traefik para recibir webhooks
- Puede salir a internet (NAT) para llamar APIs externas
- NO puede ver otros tenants ni la red de plataforma

## Limites de recursos por plan

| Plan | RAM | CPU | PIDs |
|------|-----|-----|------|
| basico | 512MB | 0.5 cores | 256 |
| equipo | 768MB | 0.75 cores | 256 |
| pro | 1024MB | 1.0 cores | 256 |

## Health check

El API server expone `/health` en puerto 8642 cuando `API_SERVER_ENABLED=true`.
Respuesta esperada: `{"status": "ok"}`

## Comandos del container

```bash
# Iniciar gateway (modo normal)
gateway run

# Ver estado
hermes status

# Dashboard (si habilitado)
hermes dashboard --host 0.0.0.0 --no-open
```

## Actualizacion de version

1. Parar container actual
2. Backup del volumen (tar.gz)
3. Crear nuevo container con nueva imagen
4. Verificar health
5. Si falla: restaurar backup, recrear con imagen anterior

## Errores comunes

| Error | Causa | Solucion |
|-------|-------|----------|
| Permission denied en /opt/data | UID/GID incorrecto | chown 1000:1000 del volumen |
| SQLite locked | Dos procesos escribiendo | Solo un gateway por volumen |
| OOM killed | Excede memory limit | Subir plan o reducir toolset |
| Token must contain a colon | Bot token invalido | Verificar formato 123456:ABC |
| Connection refused :8642 | API server no habilitado | Setear API_SERVER_ENABLED=true |
