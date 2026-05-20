# Hermes Agent v0.14.0 — Guia de Deployment para martes.app

> **Version**: 0.14.0 (May 2026)
> **Imagen**: `nousresearch/hermes-agent:0.14.0`
> **Modo**: Container por tenant, gateway mode

---

## Instalacion: Que cambio en v0.14.0

### Antes (v0.13 y anteriores)
- Habia que clonar el repo completo
- `pip install` bajaba TODOS los backends (Slack, Matrix, image gen, TTS...)
- Cold-start de ~19 segundos
- Todo cargado en memoria desde el inicio

### Ahora (v0.14.0)
- `pip install hermes-agent` desde PyPI (o Docker image oficial)
- **Lazy-deps**: backends se instalan la primera vez que se usan
- Cold-start <2 segundos
- Solo se carga lo que el config.yaml pide

### Implicacion para SaaS multi-tenant
- NO necesitas preinstalar todo en la imagen
- La imagen oficial `nousresearch/hermes-agent:0.14.0` ya tiene todo
- El `config.yaml` controla que se activa
- `security.allow_lazy_installs: false` bloquea que el agente instale cosas nuevas

---

## Modos de ejecucion Docker

### Modo 1: Hermes dentro del container (NUESTRO MODO)

```
Host (VPS)
└── Docker
    └── hermes-{tenant_code}
        ├── /opt/data (volumen montado)
        └── gateway run (proceso principal)
```

- Hermes + runtime viven dentro del container
- Estado en volumen montado (`/var/lib/martes/tenants/{code}:/opt/data`)
- Aislamiento completo entre tenants
- Restart policy: `unless-stopped`

### Modo 2: Docker como sandbox de terminal (SOLO PLAN PRO)

```
Host (VPS)
└── Docker
    └── hermes-{tenant_code}
        ├── /opt/data (volumen)
        └── gateway run
            └── Spawns → sandbox containers para terminal commands
```

- El agente Hermes crea containers efimeros para ejecutar codigo
- Configurado via `terminal.backend: "docker"` en config.yaml
- Requiere Docker-in-Docker o socket forwarding
- Solo para plan Pro (los otros no tienen terminal)

---

## Configuracion por archivos

### Estructura del volumen de un tenant

```
/var/lib/martes/tenants/{code}/
├── config.yaml          ← Comportamiento completo del agente
├── .env                 ← Secretos (API keys, bot tokens)
├── SOUL.md              ← Personalidad/identidad del agente
├── auth.json            ← OAuth credentials (si usa Nous Portal)
├── state.db             ← SQLite: sesiones, historial, FTS5
├── memories/
│   ├── MEMORY.md        ← Notas del agente (auto-gestionado)
│   └── USER.md          ← Perfil del usuario (auto-gestionado)
├── skills/              ← Skills creados o instalados
├── cron/                ← Jobs programados
│   └── jobs.json
├── sessions/            ← Historial de conversaciones
├── logs/                ← Logs (auto-rotados, secrets redactados)
├── wiki/                ← LLM Wiki (knowledge acumulativo)
└── workspace/           ← Directorio de trabajo
```

### config.yaml — Secciones principales

| Seccion | Que controla | Critico para SaaS? |
|---------|-------------|-------------------|
| `model` | LLM provider, modelo, base_url | SI |
| `platform_toolsets` | Que herramientas tiene por plataforma | SI |
| `security` | allow_lazy_installs | SI |
| `terminal` | Backend de ejecucion | SI (Pro) |
| `streaming` | Respuestas en tiempo real | SI |
| `compression` | Manejo de contexto largo | SI |
| `memory` | Memoria persistente | SI |
| `session_reset` | Cuando limpiar contexto | SI |
| `tool_loop_guardrails` | Proteccion contra loops | SI |
| `agent` | max_turns, reasoning_effort | SI |
| `skills` | Nudge interval | Opcional |
| `stt` | Transcripcion de voz | Opcional |
| `browser` | Timeout de inactividad | Solo Pro |
| `code_execution` | Timeout, max tool calls | Solo Pro |
| `delegation` | Subagentes | Solo Pro |
| `display` | Tool progress, cleanup | Opcional |
| `prompt_caching` | Cache TTL (Claude) | Solo Pro |
| `mcp_servers` | Integraciones MCP | Bajo demanda |

### .env — Solo secretos

```bash
# Obligatorio
OPENROUTER_API_KEY=sk-or-v1-xxx

# Plataforma principal
TELEGRAM_BOT_TOKEN=123456:ABC-DEF
TELEGRAM_ALLOWED_USERS=user_id_1,user_id_2

# Opcionales (segun integraciones)
DISCORD_BOT_TOKEN=xxx
WHATSAPP_TOKEN=xxx
GITHUB_TOKEN=ghp_xxx
NOTION_API_KEY=ntn_xxx
FIRECRAWL_API_KEY=xxx
FAL_KEY=xxx
```

### SOUL.md — Personalidad

El SOUL.md es el "slot #1" del system prompt. Define quien es el agente.
Hermes lo lee al inicio de cada sesion.

```markdown
# Nombre del Agente

Eres un asistente de [rol]. Tu objetivo es [objetivo].

## Personalidad
- Conciso y directo
- Responde en el idioma del usuario

## Capacidades
- [lista de lo que puede hacer]

## Reglas
- [restricciones]
```

---

## Crear un tenant nuevo (flujo tecnico)

### 1. Preparar volumen
```bash
TENANT=t001
mkdir -p /var/lib/martes/tenants/$TENANT/{sessions,memories,skills,cron,logs,wiki,workspace}
```

### 2. Copiar template
```bash
PLAN=basico  # basico | equipo | pro
cp /opt/martes/infra/templates/$PLAN/config.yaml /var/lib/martes/tenants/$TENANT/
cp /opt/martes/infra/templates/$PLAN/SOUL.md /var/lib/martes/tenants/$TENANT/
```

### 3. Escribir .env
```bash
cat > /var/lib/martes/tenants/$TENANT/.env << EOF
OPENROUTER_API_KEY=sk-or-v1-xxx
TELEGRAM_BOT_TOKEN=123456:ABC
TELEGRAM_ALLOWED_USERS=
EOF
chmod 600 /var/lib/martes/tenants/$TENANT/.env
```

### 4. Fijar permisos
```bash
chown -R 1000:1000 /var/lib/martes/tenants/$TENANT/
```

### 5. Crear container
```bash
docker run -d \
  --name hermes-$TENANT \
  --restart unless-stopped \
  --memory 512m \
  --cpus 0.5 \
  --pids-limit 256 \
  --security-opt no-new-privileges \
  --cap-drop ALL \
  --cap-add NET_RAW \
  --dns 1.1.1.1 --dns 8.8.8.8 \
  --tmpfs /tmp:size=100m \
  --log-opt max-size=50m --log-opt max-file=3 \
  -v /var/lib/martes/tenants/$TENANT:/opt/data \
  -e HERMES_UID=1000 \
  -e HERMES_GID=1000 \
  -e API_SERVER_ENABLED=true \
  -e API_SERVER_HOST=0.0.0.0 \
  -l martes.tenant=$TENANT \
  -l martes.plan=$PLAN \
  -l traefik.enable=true \
  -l "traefik.http.routers.$TENANT.rule=Host(\`$TENANT.martes.app\`)" \
  -l "traefik.http.routers.$TENANT.tls.certresolver=letsencrypt" \
  -l "traefik.http.services.$TENANT.loadbalancer.server.port=8642" \
  nousresearch/hermes-agent:0.14.0 \
  gateway run
```

### 6. Conectar a redes
```bash
docker network create tenant-$TENANT-net 2>/dev/null
docker network connect tenant-$TENANT-net hermes-$TENANT
docker network connect martes-tenants hermes-$TENANT
```

### 7. Verificar health
```bash
sleep 30
docker exec hermes-$TENANT wget -q -O - http://localhost:8642/health
# Esperado: {"status": "ok"}
```

---

## Actualizar version de Hermes

### Proceso seguro (zero-downtime por tenant)

```bash
TENANT=t001

# 1. Pull nueva imagen
docker pull nousresearch/hermes-agent:0.15.0

# 2. Backup del volumen
docker pause hermes-$TENANT
tar czf /var/lib/martes/backups/$TENANT-pre-upgrade.tar.gz \
  /var/lib/martes/tenants/$TENANT/
docker unpause hermes-$TENANT

# 3. Parar container actual
docker stop hermes-$TENANT
docker rm hermes-$TENANT

# 4. Crear con nueva imagen (mismos parametros)
docker run -d --name hermes-$TENANT ... nousresearch/hermes-agent:0.15.0 gateway run

# 5. Verificar
docker exec hermes-$TENANT wget -q -O - http://localhost:8642/health

# 6. Si falla: rollback
docker stop hermes-$TENANT && docker rm hermes-$TENANT
tar xzf /var/lib/martes/backups/$TENANT-pre-upgrade.tar.gz -C /
# Recrear con imagen anterior
```

---

## Diferencias entre tiers (resumen tecnico)

| Config | Basico ($30) | Equipo ($100) | Pro ($200) |
|--------|-------------|---------------|------------|
| **Modelo** | deepseek-chat | deepseek-chat | claude-3.5-haiku |
| **Plataformas** | Telegram | Telegram + Discord | Todas |
| **Toolsets** | web, memory, todo, cronjob, clarify, session_search | + vision, skills | hermes-telegram (todo) |
| **Terminal** | NO | NO | Docker sandbox |
| **Browser** | NO | Firecrawl (scraping) | Playwright (full) |
| **Code execution** | NO | NO | SI (60s timeout) |
| **Delegation** | NO | NO | SI (1 nivel) |
| **RAM** | 512MB | 768MB | 1024MB |
| **CPU** | 0.5 cores | 0.75 cores | 1.0 core |
| **max_turns** | 30 | 50 | 60 |
| **reasoning** | low | medium | medium |
| **compression** | 0.30 (agresiva) | 0.40 | 0.50 |
| **prompt_caching** | No (DeepSeek) | No (DeepSeek) | 1h (Claude) |
| **lazy_installs** | Bloqueado | Bloqueado | Permitido |
| **hard_stop** | SI (3 fallos) | SI (4 fallos) | SI (5 fallos) |
| **STT model** | base | base | small |

---

## Troubleshooting de deployment

### Container no arranca
```bash
docker logs hermes-$TENANT --tail 30
```

| Error | Causa | Fix |
|-------|-------|-----|
| Permission denied /opt/data | UID incorrecto | `chown -R 1000:1000 /var/lib/martes/tenants/$TENANT/` |
| Token must contain a colon | Bot token invalido | Verificar .env |
| OOMKilled | Excede memory limit | Subir plan |
| database is locked | Dos gateways en mismo volumen | Solo 1 container por tenant |

### Container healthy pero bot no responde
1. Verificar token: `docker exec hermes-$TENANT cat /opt/data/.env | grep TELEGRAM`
2. Verificar allowed users: si esta vacio, acepta todos
3. Restart: `docker restart hermes-$TENANT`
4. Logs de Telegram: `docker logs hermes-$TENANT 2>&1 | grep -i telegram`

### Alto consumo de tokens
1. Verificar compression threshold (bajar a 0.30)
2. Reducir toolsets (menos tools = menos tokens por request)
3. Bajar max_turns
4. Activar hard_stop en guardrails
