# Martes.app — Auditoría de Validación Pre-Implementación

> **Status**: Revisión final antes de codear  
> **Date**: May 2026  
> **Fuentes**: Docs oficiales de Agno, repo de Hermes, GitHub issues, blogs de la comunidad

---

## 1. Errores Que Estamos Cometiendo (Corregidos)

### Error 1: PostgreSQL 16 en vez de 18

**Lo que teníamos**: `postgres:16-alpine`
**Lo correcto**: `agnohq/pgvector:18`

Agno recomienda su propia imagen `agnohq/pgvector:18` que incluye PostgreSQL 18 + pgvector preinstalado. Esto es necesario para knowledge embeddings si en el futuro queremos que el meta-agente use RAG.

**Fix**: Usar `agnohq/pgvector:18` en el docker-compose.

### Error 2: No teníamos JWT auth para producción

**Lo que teníamos**: Meta-agente sin auth
**Lo correcto**: AgentOS en producción requiere `RUNTIME_ENV=prd` + `JWT_VERIFICATION_KEY`

De los docs de Agno:
> "RUNTIME_ENV=prd enables JWT auth. JWT_VERIFICATION_KEY set."

Para nuestro caso (meta-agente solo accesible via Telegram, no expuesto a internet), podemos usar `RUNTIME_ENV=dev` y no exponer el puerto 8000. Pero si en el futuro exponemos la API, necesitamos JWT.

**Fix**: No exponer puerto 8000 del meta-agente. Solo Telegram interface.

### Error 3: Token overhead de Hermes no mitigado

**Hallazgo crítico** (GitHub issue #4379): Hermes consume **13,900 tokens fijos** por cada request (73% del total). Esto es:
- 8,759 tokens en tool definitions (31 tools)
- 5,176 tokens en system prompt (SOUL.md + skills catalog)

**Para nuestro SaaS esto significa**: Si un tenant tiene 100 mensajes/día × 14K tokens overhead = 1.4M tokens/día solo en overhead. Con DeepSeek V4 ($0.30/M) = $0.42/día = **$12.60/mes solo en overhead** por tenant.

**Fix obligatorio en nuestros templates**:
1. **Reducir tools por plataforma**: Messaging no necesita browser tools (-1,258 tokens)
2. **Lazy skills loading**: No inyectar catálogo de skills en system prompt (-2,200 tokens)
3. **Compression threshold más agresivo**: `threshold: 0.30` en vez de `0.50`
4. **Toolset mínimo por tier**: Básico = 10 tools, Equipo = 15, Pro = 25

**Overhead estimado después del fix**:
- Básico: ~6K tokens/request (vs 14K original) = $5/mes
- Equipo: ~8K tokens/request = $7/mes
- Pro: ~12K tokens/request = $10/mes

### Error 4: No teníamos Telegram Interface de Agno

**Lo que teníamos**: "El meta-agente se conecta a Telegram" (vago)
**Lo correcto**: Agno tiene una **Telegram Interface nativa** en AgentOS

```python
from agno.os import AgentOS
from agno.os.interfaces.telegram import Telegram

agent_os = AgentOS(
    agents=[meta_agent],
    interfaces=[Telegram(agent=meta_agent)],
    db=db,
    tracing=True,
)
```

Esto monta automáticamente un webhook de Telegram en el AgentOS. El meta-agente recibe mensajes directamente sin configuración extra.

**Fix**: Usar `agno.os.interfaces.telegram.Telegram` en vez de implementar un bot custom.

### Error 5: No consideramos `agnohq/pgvector` para knowledge

**Lo que teníamos**: "No necesitamos embeddings"
**Corrección**: Es cierto que no los necesitamos AHORA, pero usar `agnohq/pgvector:18` nos deja la puerta abierta sin costo extra. La imagen pesa lo mismo que `postgres:18-alpine` + pgvector.

---

## 2. Lo Que Estamos Haciendo Bien (Validado)

| Decisión | Validación |
|----------|-----------|
| Container por tenant | Confirmado: Hermes dice "never run two gateways against same data dir" |
| Docker socket para meta-agente | Patrón estándar (Portainer, Watchtower, Traefik) |
| PostgreSQL compartido (Agno + plataforma) | Agno docs: "PostgreSQL — Sessions, memory, knowledge, traces" |
| Bridge network por tenant | Hermes funciona en bridge mode (verificado en código fuente) |
| Version pinning | Correcto: Hermes publica releases frecuentes que pueden romper cosas |
| BYOK para LLM | Correcto: evita costos impredecibles |
| LLM Wiki para todos | Correcto: no usa embeddings, solo markdown + grep |
| Composio via MCP | Correcto: Hermes soporta MCP nativamente en config.yaml |
| Sin Coolify | Correcto: ahorra 500MB-1GB de RAM |

---

## 3. Lo Que Agno Nos Da Gratis (Que No Estábamos Usando)

| Feature | Qué es | Cómo nos ayuda |
|---------|--------|----------------|
| **Telegram Interface** | Bot de Telegram nativo en AgentOS | Meta-agente accesible via Telegram sin código extra |
| **Tracing** | Log de cada acción del agente | Audit trail automático de todo lo que hace el meta-agente |
| **Scheduler** | Cron jobs nativos de Agno | Health checks periódicos sin cron externo |
| **Background hooks** | Ejecutar código después de cada run | Auto-save de estado después de cada acción |
| **Health endpoint** | `/health` automático | Monitoring del meta-agente sin código extra |
| **Session isolation** | Sesiones separadas por user_id | Si múltiples admins hablan al meta-agente, no se mezclan |

---

## 4. Configuración Correcta de Templates (Post-Audit)

### Template Básico — Toolset Mínimo

```yaml
# config.yaml para tier Básico ($30/mo)
# Optimizado para mínimo token overhead

model:
  provider: openrouter
  default: deepseek/deepseek-chat
  base_url: "https://openrouter.ai/api/v1"

# CRITICAL: toolset reducido para messaging (ahorra ~4K tokens/request)
platform_toolsets:
  telegram: [web, memory, todo, cronjob, clarify]
  # NO incluye: browser, terminal, file, code_execution, delegate, vision

skills:
  creation_nudge_interval: 0  # Desactivar nudge de skills (ahorra tokens)

compression:
  enabled: true
  threshold: 0.30    # Más agresivo que default (0.50)
  target_ratio: 0.20
  protect_last_n: 10  # Menos que default (20) — ahorra contexto

memory:
  memory_enabled: true
  user_profile_enabled: true
  memory_char_limit: 1500   # Más pequeño que default (2200)
  user_char_limit: 1000
  nudge_interval: 15        # Menos frecuente

session_reset:
  mode: both
  idle_minutes: 720   # 12 horas (vs 24h default)
  at_hour: 4

agent:
  max_turns: 30       # Menos que default (60)
  reasoning_effort: "low"  # Ahorra tokens
```

### Template Equipo — Balance

```yaml
model:
  provider: openrouter
  default: deepseek/deepseek-chat
  base_url: "https://openrouter.ai/api/v1"

platform_toolsets:
  telegram: [web, memory, todo, cronjob, clarify, vision, skills]
  discord: [web, memory, todo, cronjob, clarify, vision, skills]

skills:
  creation_nudge_interval: 15

compression:
  enabled: true
  threshold: 0.40
  target_ratio: 0.20
  protect_last_n: 15

memory:
  memory_enabled: true
  user_profile_enabled: true
  memory_char_limit: 2200
  user_char_limit: 1375
  nudge_interval: 10

session_reset:
  mode: both
  idle_minutes: 1440
  at_hour: 4

agent:
  max_turns: 50
  reasoning_effort: "medium"
```

### Template Pro — Completo

```yaml
model:
  provider: openrouter
  default: anthropic/claude-3.5-haiku
  base_url: "https://openrouter.ai/api/v1"

platform_toolsets:
  telegram: [hermes-telegram]   # Todo incluido
  discord: [hermes-discord]
  whatsapp: [hermes-whatsapp]

skills:
  creation_nudge_interval: 10

compression:
  enabled: true
  threshold: 0.50
  target_ratio: 0.20
  protect_last_n: 20

memory:
  memory_enabled: true
  user_profile_enabled: true
  memory_char_limit: 2200
  user_char_limit: 1375
  nudge_interval: 10

session_reset:
  mode: both
  idle_minutes: 1440
  at_hour: 4

agent:
  max_turns: 60
  reasoning_effort: "medium"

browser:
  inactivity_timeout: 120
```

---

## 5. Docker Compose Correcto (Post-Audit)

```yaml
services:
  # PostgreSQL con pgvector (imagen oficial de Agno)
  db:
    image: agnohq/pgvector:18    # ← Correcto (no postgres:16-alpine)
    container_name: martes-db
    restart: unless-stopped
    environment:
      POSTGRES_USER: martes
      POSTGRES_PASSWORD: ${PG_PASSWORD}
      POSTGRES_DB: martes
    volumes:
      - /var/lib/martes/pg-data:/var/lib/postgresql/data
    networks:
      - platform-net
    deploy:
      resources:
        limits:
          memory: 256M

  # Meta-agente (Agno AgentOS con Telegram Interface)
  meta-agent:
    build: ./apps/meta-agent
    container_name: martes-meta
    restart: unless-stopped
    environment:
      AGNO_DB_URL: postgresql+psycopg://martes:${PG_PASSWORD}@db:5432/martes
      OPENROUTER_API_KEY: ${OPENROUTER_API_KEY}
      TELEGRAM_TOKEN: ${META_AGENT_TELEGRAM_TOKEN}
      RUNTIME_ENV: dev   # No JWT (no expuesto a internet)
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - /var/lib/martes/tenants:/var/lib/martes/tenants
    depends_on:
      db: { condition: service_healthy }
    networks:
      - platform-net
    deploy:
      resources:
        limits:
          memory: 512M

  # Traefik (reverse proxy para dashboards de tenants)
  traefik:
    image: traefik:v3.4
    container_name: martes-traefik
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    command:
      - "--providers.docker=true"
      - "--providers.docker.exposedbydefault=false"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.websecure.address=:443"
      - "--entrypoints.web.http.redirections.entrypoint.to=websecure"
      - "--certificatesresolvers.letsencrypt.acme.httpchallenge.entrypoint=web"
      - "--certificatesresolvers.letsencrypt.acme.email=${ACME_EMAIL}"
      - "--certificatesresolvers.letsencrypt.acme.storage=/letsencrypt/acme.json"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - traefik_certs:/letsencrypt
    networks:
      - platform-net
      - tenant-net
    deploy:
      resources:
        limits:
          memory: 128M

  # Portainer (UI de emergencia, solo via Tailscale)
  portainer:
    image: portainer/portainer-ce:latest
    container_name: martes-portainer
    restart: unless-stopped
    ports:
      - "127.0.0.1:9000:9000"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - portainer_data:/data
    deploy:
      resources:
        limits:
          memory: 64M

volumes:
  traefik_certs:
  portainer_data:

networks:
  platform-net:
    name: martes-platform
  tenant-net:
    name: martes-tenants
```

---

## 6. Cosas Que Podemos Agregar (No Errores, Mejoras)

| Feature | Esfuerzo | Impacto | Cuándo |
|---------|----------|---------|--------|
| **Usage footer** en mensajes de Hermes (tokens/costo) | Bajo | Transparencia para el tenant | Sprint 2 |
| **Auto-compression tuning** por el meta-agente | Medio | Reduce costos automáticamente | Sprint 3 |
| **Backup a R2 automático** via scheduler de Agno | Bajo | Disaster recovery | Sprint 3 |
| **Health dashboard** (meta-agente reporta status por Telegram) | Bajo | Visibilidad | Sprint 2 |
| **Multi-admin** (varios admins hablan al meta-agente) | Bajo | Agno ya soporta session isolation | Sprint 4 |
| **Webhook de Telegram** para el meta-agente (vs polling) | Medio | Respuesta más rápida | Sprint 2 |

---

## 7. Checklist de Producción (De los Docs de Agno)

| Item | Estado | Notas |
|------|--------|-------|
| PostgreSQL con volumen persistente | Pendiente | `/var/lib/martes/pg-data` |
| HTTPS terminado en reverse proxy | Pendiente | Traefik + Let's Encrypt |
| Health check en `/health` | Gratis | AgentOS lo expone automáticamente |
| Tracing activado (`tracing=True`) | Pendiente | Para debugging |
| Al menos una interface conectada | Pendiente | Telegram Interface |
| Pre-hooks para PII si hay input no confiable | No aplica | Solo el admin habla al meta-agente |
| `requires_confirmation=True` en tools irreversibles | Pendiente | Para `stop_tenant`, `delete_backup` |

---

## 8. Resumen: Estamos Listos Para Codear

**Errores corregidos:**
1. PostgreSQL → `agnohq/pgvector:18`
2. Telegram → usar Agno Telegram Interface nativa
3. Token overhead → templates con toolsets reducidos + compression agresiva
4. Auth → no exponer puerto 8000, solo Telegram

**Lo que no cambia:**
- Container por tenant ✓
- Docker socket ✓
- Bridge networks ✓
- BYOK ✓
- LLM Wiki ✓
- Sin Coolify ✓

**Infraestructura final validada. Lista para implementar.**

---

## 9. Correcciones Post-Revisión (Admin Feedback)

### Puerto 8000: Expuesto via Tailscale (no cerrado)

El puerto 8000 del meta-agente se expone pero SOLO accesible via Tailscale:
- Para debugging desde tu computadora
- Para ver traces y sesiones
- Para acceder al API del AgentOS directamente
- Firewall bloquea acceso desde internet público

### Token Overhead: No recortar agresivamente

DeepSeek V4 tiene 90% descuento en cache hits. El system prompt + tools se cachean automáticamente. El costo real con cache:
- Sin cache: $0.0042/request
- Con cache: $0.00042/request (10x más barato)

**Decisión**: Mantener toolsets completos para mejor experiencia. El cache absorbe el overhead. No degradar la experiencia del usuario por ahorrar fracciones de centavo.

### Telegram Interface de Agno: Features completas

La interface nativa incluye:
- Streaming (token-by-token, edita mensaje en tiempo real)
- User memory (recuerda cada admin entre sesiones)
- PostgresDb (sesiones + traces en la misma DB)
- Scheduler (cron jobs nativos para health checks)
- Background hooks (tareas largas sin bloquear Telegram)
- requires_confirmation (pide confirmación antes de acciones destructivas)
- Webhook automático en producción (polling en dev)

### Webhook vs Polling

- **Desarrollo** (`APP_ENV=development`): Agno usa polling (no necesita dominio)
- **Producción** (`APP_ENV=production`): Agno usa webhook (necesita HTTPS público)

Para producción del meta-agente: el webhook de Telegram llega via Traefik al puerto 8000 del container. Traefik maneja HTTPS.
