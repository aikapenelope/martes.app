# Martes.app — Docker e Infraestructura Explicada

> **Status**: Referencia técnica  
> **Date**: May 2026  
> **Audiencia**: Para entender exactamente cómo funciona Docker, la red, y la base de datos en este sistema.

---

## 1. Cómo Funciona Hermes Internamente (Sin Misterio)

### La "Base de Datos" de Hermes

Hermes **NO usa PostgreSQL ni Redis**. Usa **SQLite** — un archivo `.db` que vive dentro del volumen del container:

```
/opt/data/                    ← Volumen montado desde el host
├── state.db                  ← SQLite: sesiones, historial, búsqueda FTS5
├── .env                      ← API keys (texto plano, permisos 600)
├── config.yaml               ← Configuración del agente
├── SOUL.md                   ← Personalidad del agente
├── sessions/                 ← Historial de conversaciones (JSON)
├── memories/                 ← Memoria persistente (archivos)
├── skills/                   ← Skills instalados (carpetas con SKILL.md)
├── cron/                     ← Jobs programados (jobs.json + outputs)
├── logs/                     ← Logs del runtime
├── google_token.json         ← OAuth token de Google (si conectado)
├── google_client_secret.json ← OAuth client credentials
└── workspace/                ← Directorio de trabajo del agente
```

**SQLite con WAL mode** (Write-Ahead Logging):
- Permite múltiples lectores simultáneos + un escritor
- El archivo `state.db` contiene: sesiones, mensajes, metadata, búsqueda full-text
- No necesita un servidor de base de datos separado
- Es por esto que Hermes dice "nunca corras dos gateways contra el mismo directorio" — SQLite no soporta escritores concurrentes desde procesos diferentes

**Esto es lo que recomienda Nous Research (los creadores)**. No hay PostgreSQL en la arquitectura de Hermes. Es deliberado: SQLite es más simple, no tiene dependencias externas, y para un solo usuario es más que suficiente.

### Qué Significa Esto Para Nuestro SaaS

Cada tenant tiene su propio archivo `state.db` dentro de su propio volumen. No hay base de datos compartida entre tenants. El aislamiento es **físico** (archivos separados en disco), no lógico (como RLS en PostgreSQL).

La única base de datos PostgreSQL que necesitamos es para **nuestra plataforma** (tenants, billing, configs) — no para Hermes.

---

## 2. Docker Explicado Para Este Proyecto

### Qué es un Container

Un container es un proceso aislado que corre en el servidor. Tiene su propio filesystem, su propia red, sus propios procesos. Pero comparte el kernel del servidor (no es una VM completa).

```
┌─────────────────────────────────────────────┐
│ Servidor (Ubuntu 24.04, 16 GB RAM)          │
│                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │Container │  │Container │  │Container │  │
│  │hermes-01 │  │hermes-02 │  │hermes-03 │  │
│  │          │  │          │  │          │  │
│  │ Python   │  │ Python   │  │ Python   │  │
│  │ Node.js  │  │ Node.js  │  │ Node.js  │  │
│  │ SQLite   │  │ SQLite   │  │ SQLite   │  │
│  │ (300MB)  │  │ (300MB)  │  │ (300MB)  │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  │
│       │              │              │         │
│  /var/lib/martes/ /var/lib/martes/ /var/lib/ │
│  tenants/t001/   tenants/t002/   tenants/   │
│                                    t003/     │
│                                              │
│  Kernel Linux (compartido)                   │
└─────────────────────────────────────────────┘
```

Cada container:
- Tiene su propio filesystem (la imagen de Hermes: Python, Node.js, Playwright)
- Tiene su propio volumen montado (los datos del tenant: state.db, config, skills)
- Tiene su propia red virtual
- Tiene límites de RAM y CPU asignados
- NO puede ver los archivos de otros containers
- NO puede ver los procesos de otros containers

### Qué es una Bridge Network

Una "bridge network" es una red virtual que Docker crea dentro del servidor. Es como un switch virtual al que conectas containers.

```
Internet
    │
    ▼
┌─────────────────────────────────────────────────────┐
│ Servidor                                             │
│                                                      │
│  eth0 (IP pública: 204.168.169.254)                 │
│    │                                                 │
│    ▼                                                 │
│  ┌─────────────────────────────────────────────┐    │
│  │ Bridge "platform-net" (172.20.0.0/24)       │    │
│  │                                              │    │
│  │  Traefik ──── Platform API ──── PostgreSQL  │    │
│  │  172.20.0.2   172.20.0.3       172.20.0.4   │    │
│  └─────────────────────────────────────────────┘    │
│                                                      │
│  ┌───────────────────┐  ┌───────────────────┐       │
│  │ Bridge "tenant-01" │  │ Bridge "tenant-02" │      │
│  │ (172.21.0.0/24)   │  │ (172.22.0.0/24)   │      │
│  │                    │  │                    │      │
│  │  hermes-t001       │  │  hermes-t002       │      │
│  │  172.21.0.2        │  │  172.22.0.2        │      │
│  └───────────────────┘  └───────────────────┘       │
│                                                      │
│  Cada bridge es una red separada.                    │
│  172.21.x.x NO puede hablar con 172.22.x.x          │
│  172.21.x.x NO puede hablar con 172.20.x.x          │
│  Pero TODOS pueden salir a internet (NAT)            │
└─────────────────────────────────────────────────────┘
```

**En español simple:**
- Cada tenant está en su propia "LAN virtual"
- No puede ver a otros tenants (como si estuvieran en edificios diferentes)
- Sí puede acceder a internet (para llamar a OpenRouter, Google API, etc.)
- Traefik (el proxy) se conecta a TODAS las redes para poder rutear tráfico

**NO necesita IP pública por container.** Las IPs son internas (172.x.x.x), asignadas automáticamente por Docker. El mundo exterior solo ve la IP del servidor. Traefik decide a qué container enviar cada request basándose en el dominio.

### Cómo Llega el Tráfico al Container Correcto

```
Usuario escribe en Telegram
    │
    ▼
Telegram servers envían webhook a:
    https://t001.martes.app/webhook/telegram
    │
    ▼
Cloudflare (DNS) → IP del servidor (204.168.169.254)
    │
    ▼
Traefik (puerto 443) lee el dominio "t001.martes.app"
    │
    ▼
Regla: t001.martes.app → container hermes-t001, puerto 8642
    │
    ▼
hermes-t001 recibe el webhook, procesa el mensaje
    │
    ▼
hermes-t001 llama a OpenRouter (sale a internet via NAT)
    │
    ▼
hermes-t001 responde via Telegram API
```

---

## 3. Patrón de Producción (Lo Que Recomienda Nous Research)

### Del Docker Compose Oficial de Hermes

```yaml
services:
  gateway:
    image: nousresearch/hermes-agent
    container_name: hermes
    restart: unless-stopped
    network_mode: host          # ← ESTO es para un solo usuario
    volumes:
      - ~/.hermes:/opt/data     # ← Un solo volumen
    command: ["gateway", "run"]
```

**Nous Research recomienda `network_mode: host` para un solo usuario** porque es más simple (no hay NAT, no hay port mapping). Pero para multi-tenant esto NO sirve.

### Lo Que Nosotros Hacemos (Multi-Tenant)

```yaml
# POR CADA TENANT (generado dinámicamente por el meta-agente)
services:
  hermes-t001:
    image: nousresearch/hermes-agent:0.14.0   # Versión pinned
    container_name: hermes-t001
    restart: unless-stopped
    networks:
      - tenant-t001-net                        # Red aislada
      - traefik-net                            # Para que Traefik lo alcance
    volumes:
      - /var/lib/martes/tenants/t001:/opt/data # Volumen propio
    environment:
      - HERMES_UID=1001
      - HERMES_GID=1001
      - API_SERVER_ENABLED=true
      - API_SERVER_HOST=0.0.0.0
      - API_SERVER_KEY=${T001_API_KEY}
      - HERMES_DASHBOARD=1
    deploy:
      resources:
        limits:
          memory: 512M                         # Límite de RAM
          cpus: "0.5"                          # Límite de CPU
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.t001.rule=Host(`t001.martes.app`)"
      - "traefik.http.routers.t001.tls.certresolver=letsencrypt"
      - "traefik.http.services.t001.loadbalancer.server.port=8642"

networks:
  tenant-t001-net:
    driver: bridge
    internal: false   # Permite salida a internet
  traefik-net:
    external: true    # Red compartida con Traefik
```

### Diferencias con el Patrón Oficial

| Aspecto | Oficial (1 usuario) | Nuestro (multi-tenant) |
|---------|---------------------|------------------------|
| Network | `host` (comparte red del servidor) | Bridge aislada por tenant |
| Volumen | `~/.hermes` (home del usuario) | `/var/lib/martes/tenants/{id}` |
| Nombre | `hermes` (fijo) | `hermes-{tenant_id}` (único) |
| Puertos | 8642 directo | Via Traefik (sin exponer puertos) |
| Recursos | Sin límites | memory + cpus limitados |
| Versión | `:latest` | `:0.14.0` (pinned) |
| Dashboard | Opcional | Según plan |

---

## 4. La Base de Datos: PostgreSQL Compartido (Agno + Plataforma)

### Decisión Final

Un **solo PostgreSQL ligero** (~150-200MB RAM) que sirve para dos cosas:

1. **Meta-agente Agno**: sesiones, memoria, traces, learning (via `PostgresDb` nativo de Agno)
2. **Plataforma**: tenants, billing, configs, error logs, audit trail

```
┌─────────────────────────────────────────────────────────────────┐
│ PostgreSQL (pg-platform, ~150-200MB RAM)                         │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Schema "public" (plataforma)                             │    │
│  │                                                           │    │
│  │  tenants          → Quién es cada cliente                │    │
│  │  instance_configs → Qué template/skills/model tiene      │    │
│  │  integrations     → OAuth tokens por tenant              │    │
│  │  billing_events   → Pagos, cancelaciones, upgrades       │    │
│  │  error_logs       → Errores de containers por tenant     │    │
│  │  health_history   → Historial de health checks           │    │
│  │  actions_log      → Qué hizo el meta-agente y cuándo    │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Tablas de Agno (auto-creadas por PostgresDb)             │    │
│  │                                                           │    │
│  │  agno_sessions    → Sesiones del meta-agente             │    │
│  │  agno_memories    → Lo que el meta-agente recuerda       │    │
│  │  agno_traces      → Logs de cada acción (audit trail)    │    │
│  │  agno_learnings   → Patrones aprendidos                  │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ SQLite (DENTRO de cada container Hermes, por tenant)              │
│                                                                   │
│  state.db         → Sesiones del tenant, mensajes, búsqueda    │
│  (kanban.db)      → Si usa kanban multi-agente                  │
│                                                                   │
│  NO es accesible desde fuera del container                       │
│  Se respalda cuando respaldas el volumen completo                │
└─────────────────────────────────────────────────────────────────┘
```

### Por Qué PostgreSQL y No SQLite Para la Plataforma

Agno se integra **nativamente** con PostgreSQL via `agno.db.postgres.PostgresDb`. Es su base de datos principal para:
- Sesiones (historial de conversaciones del meta-agente)
- Memoria persistente (lo que aprende sobre los tenants)
- Traces (log completo de cada acción — audit trail automático)
- Learning (patrones que mejoran con el tiempo)

Si ya necesitamos PostgreSQL para Agno, usamos la misma instancia para la plataforma. No tiene sentido tener SQLite + PostgreSQL cuando uno solo hace todo.

### Qué Puede Hacer el Meta-Agente con Acceso a la DB

```python
# El meta-agente Agno tiene acceso directo a PostgreSQL
# Puede hacer queries como tools:

@tool()
async def check_tenant_billing(tenant_id: str) -> str:
    """Verifica si un tenant tiene su suscripción activa."""
    result = await db.execute(
        "SELECT status, plan FROM tenants WHERE id = $1", tenant_id
    )
    return json.dumps(result)

@tool()
async def log_container_error(tenant_id: str, error: str) -> str:
    """Registra un error de container para análisis posterior."""
    await db.execute(
        "INSERT INTO error_logs (tenant_id, error, timestamp) VALUES ($1, $2, now())",
        tenant_id, error
    )
    return "Error logged"

@tool()
async def get_unhealthy_tenants() -> str:
    """Lista tenants con containers en estado unhealthy."""
    result = await db.execute(
        "SELECT id, name, last_health_check FROM tenants WHERE status = 'unhealthy'"
    )
    return json.dumps(result)
```

### Configuración Mínima

```yaml
pg-platform:
  image: postgres:16-alpine
  container_name: pg-platform
  restart: unless-stopped
  environment:
    POSTGRES_USER: martes
    POSTGRES_PASSWORD: ${PG_PASSWORD}
    POSTGRES_DB: martes
  volumes:
    - /var/lib/martes/pg-data:/var/lib/postgresql/data
  command:
    - "postgres"
    - "-c"
    - "shared_buffers=128MB"
    - "-c"
    - "max_connections=30"
    - "-c"
    - "log_min_duration_statement=1000"
  deploy:
    resources:
      limits:
        memory: 256M   # Suficiente para <1000 tenants
  networks:
    - platform-net
```

**RAM real**: ~150-200MB con `shared_buffers=128MB` y 30 conexiones.
Esto es 1 tenant menos de RAM, pero a cambio tienes audit trail, error tracking, y billing verification automáticos via el meta-agente.

### Resumen de Bases de Datos

| DB | Dónde | Para qué | RAM |
|----|-------|----------|-----|
| PostgreSQL (pg-platform) | Container separado en el servidor | Plataforma + Agno meta-agente | ~200MB |
| SQLite (state.db) | Dentro de cada container Hermes | Datos del agente del tenant | 0MB extra (incluido en Hermes) |

---

## 5. Cómo Se Crea un Tenant (Flujo Completo)

```
1. Usuario se registra en martes.app
   → Se crea registro en PostgreSQL (tabla tenants)

2. Usuario elige template ("Asistente de Trabajo")
   → Se crea registro en instance_configs

3. Meta-agente (Agno) recibe la orden de crear instancia:

   a) Crear directorio de datos:
      mkdir -p /var/lib/martes/tenants/t001

   b) Escribir .env con las API keys del tenant:
      echo "OPENROUTER_API_KEY=sk-..." > /var/lib/martes/tenants/t001/.env

   c) Escribir config.yaml con el template elegido:
      cp templates/trabajo/config.yaml /var/lib/martes/tenants/t001/

   d) Copiar skills preconfigurados:
      cp -r templates/trabajo/skills/ /var/lib/martes/tenants/t001/skills/

   e) Escribir SOUL.md (personalidad):
      cp templates/trabajo/SOUL.md /var/lib/martes/tenants/t001/

   f) Crear red Docker aislada:
      docker network create tenant-t001-net

   g) Lanzar container:
      docker run -d \
        --name hermes-t001 \
        --network tenant-t001-net \
        --network traefik-net \
        --memory 512m --cpus 0.5 \
        -v /var/lib/martes/tenants/t001:/opt/data \
        nousresearch/hermes-agent:0.14.0 \
        gateway run

   h) Esperar health check:
      curl http://hermes-t001:8642/health
      → {"status": "ok"}

   i) Configurar Traefik (label o dynamic config):
      t001.martes.app → hermes-t001:8642

4. Tenant recibe notificación: "Tu agente está listo"
   → Puede conectar Telegram, configurar cron, etc.
```

---

## 6. Backup y Recuperación

### Qué Respaldar

```bash
# Todo el estado de un tenant es UN directorio:
/var/lib/martes/tenants/t001/

# Backup = comprimir ese directorio
tar czf backup-t001-$(date +%Y%m%d).tar.gz /var/lib/martes/tenants/t001/

# Restore = descomprimir + recrear container
tar xzf backup-t001-20260520.tar.gz -C /
docker run -d --name hermes-t001 ... (mismo comando de arriba)
```

**SQLite se respalda correctamente con tar** porque:
- El container está parado durante el backup (o usamos `sqlite3 .backup`)
- WAL mode asegura consistencia si el container está corriendo (pero mejor pararlo)

### Backup Automatizado

```bash
# Cron job: backup diario de todos los tenants
0 4 * * * for dir in /var/lib/martes/tenants/*/; do
  tenant=$(basename "$dir")
  tar czf /var/lib/martes/backups/${tenant}-$(date +%Y%m%d).tar.gz "$dir"
done
```

---

## 7. Resumen: Qué Hay Dentro vs Fuera del Container

| Componente | Dentro del Container | Fuera (en el servidor) |
|-----------|---------------------|----------------------|
| Python runtime | Si | No |
| Node.js | Si | No |
| Playwright/Chromium | Si | No |
| SQLite (state.db) | Si (en volumen) | Accesible via volumen |
| Skills | Si (en volumen) | Accesible via volumen |
| Config/API keys | Si (en volumen) | Accesible via volumen |
| PostgreSQL (plataforma) | No | Si (container separado) |
| Traefik | No | Si (container separado) |
| Meta-agente (Agno) | No | Si (container separado) |
| Docker daemon | No | Si (en el host) |

**El volumen es el puente**: vive en el disco del servidor (`/var/lib/martes/tenants/t001/`) pero se monta dentro del container como `/opt/data`. Ambos ven los mismos archivos.
