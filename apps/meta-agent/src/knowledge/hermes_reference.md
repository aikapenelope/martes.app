# Hermes Agent — Referencia Técnica para el Meta-Agente

> v0.14.0 "The Foundation Release" — mayo 2026
> Ref: https://hermes-agent.nousresearch.com/docs

## Qué es Hermes

Agente IA auto-mejorante. Cada tenant de martes.app es un container Hermes
**completo y sin restricciones**. El límite del plan no es funcional — es el
presupuesto de tokens (créditos de OpenRouter). El cliente tiene libertad total
sobre su agente.

## Imagen Docker

- Imagen pineada: `nousresearch/hermes-agent:0.14.0`
- Entrypoint: `/usr/bin/tini -g -- /opt/hermes/docker/entrypoint.sh`
- Comando: `gateway run`
- Puerto API: 8642 (cuando `API_SERVER_ENABLED=true`)

## Estructura del volumen (/opt/data dentro del container)

```
/opt/data/
├── config.yaml    ← configuración del agente (hot-reload en cada turno)
├── .env           ← API keys (permisos 600, hot-reload en cada turno)
├── SOUL.md        ← personalidad (hot-reload en cada turno)
├── state.db       ← SQLite: sesiones, historial, búsqueda FTS5
├── memories/      ← MEMORY.md + USER.md (auto-gestionados por Hermes)
├── skills/        ← skills instalados (auto-creados + hub)
├── wiki/          ← base de conocimiento del cliente
├── cron/          ← jobs programados
├── sessions/      ← historial de conversaciones
├── workspace/     ← directorio de trabajo del agente
└── home/          ← HOME para subprocesos (git, ssh, npm)
```

**Hot-reload crítico**: Hermes recarga `config.yaml`, `.env` y `SOUL.md` al
inicio de cada turno de conversación (gateway/run.py:16119). Cambiar estos
archivos en el volumen tiene efecto en el próximo mensaje SIN reiniciar.

## Variables de entorno en `.env` del tenant

| Variable | Obligatoria | Descripción |
|---|---|---|
| `OPENROUTER_API_KEY` | Sí | Key de OpenRouter con créditos del plan |
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
| `API_SERVER_ENABLED` | `true` | Habilita /health en :8642 para health checks |
| `API_SERVER_HOST` | `0.0.0.0` | Expone el API fuera del container |

## El paradigma de libertad del cliente

El cliente puede cambiar CUALQUIER cosa de su agente desde Telegram:

```
/model openai/gpt-4o          → cambia modelo, persiste en config.yaml
/model deepseek/deepseek-v4-flash → modelo más barato con 1M ctx
/skills browse                → explorar skills del hub
/skills install official/notion-overhaul → instalar skill de Notion
/cron add "0 9 * * *" "resumen diario"   → programar tarea
/memory                       → ver memoria persistente
/reset                        → nueva sesión (memoria preservada)
/handoff anthropic/claude-opus-4.6 → transferir sesión a otro modelo en vivo
```

El meta-agente puede hacer los mismos cambios desde afuera sin reiniciar:
- `update_tenant_model(tenant_code, model_id)` → edita config.yaml
- `update_tenant_soul(tenant_code, soul_content)` → edita SOUL.md
- `inject_credential(tenant_code, "openrouter_api_key", nueva_key)` → edita .env

## Errores comunes

| Error | Causa | Solución |
|---|---|---|
| Bot no responde | `TELEGRAM_ALLOWED_USERS` faltante | Agregar al .env, efecto inmediato |
| `Permission denied /opt/data` | UID/GID incorrecto | `chown 1000:1000 -R /var/lib/martes/tenants/{code}/` |
| `Token must contain a colon` | Bot token inválido | Verificar formato `123456789:ABCdef...` |
| `Connection refused :8642` | API server no habilitado | Verificar `API_SERVER_ENABLED=true` en docker run |
| 402 en LLM | Créditos agotados | `inject_credential` con nueva key de cliente o recargar créditos |

## Actualización de versión de Hermes

1. Backup del volumen: `backup_tenant(tenant_code)`
2. Cambiar `HERMES_IMAGE` en config.py del meta-agent → nuevo PR → deploy
3. Para el tenant específico: `stop_tenant()` → `restart_tenant()` o recrear container
4. Verificar health: `container_health(tenant_code)`
5. Si falla: `restore_tenant_from_backup()` + recrear con imagen anterior
