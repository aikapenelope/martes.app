# Martes.app — Deep Research Findings

> **Status**: Active Research  
> **Date**: May 20, 2026  
> **Sources**: Hermes docs, GitHub issues, community blogs, Reddit threads, Docker resource limits

---

## 1. Alternativas al Browser (Playwright/Chromium)

### El Problema

La imagen Docker de Hermes incluye Playwright + Chromium (~300MB de la imagen). Cuando el browser está activo, consume ~200-800MB de RAM adicional. Para un SaaS multi-tenant, esto es el mayor consumidor de recursos.

### Alternativas Investigadas

| Alternativa | RAM | Velocidad | Stealth | Estado en Hermes |
|-------------|-----|-----------|---------|-----------------|
| **Playwright/Chromium** (actual) | 200-800MB activo | ~500ms/page | CamoFox (built-in) | Default |
| **Obscura** (Rust headless) | ~30MB | ~85ms/page | Built-in stealth | Issue #15445 (propuesto, no implementado) |
| **Firecrawl** (API externa) | 0MB (remoto) | Variable | Cloud-managed | Plugin existente |
| **Browserbase** (cloud browser) | 0MB (remoto) | Variable | Premium stealth | Plugin existente |
| **LightPanda** | ~50MB | Rápido | Básico | Mencionado en issues |
| **Sin browser** (solo web tools) | 0MB | N/A | N/A | Configurable |

### Recomendación para el SaaS

**Estrategia por tier:**

| Tier | Browser Strategy | RAM Impact |
|------|-----------------|-----------|
| **Starter** | Sin browser. Solo web tools (Firecrawl API para scraping básico) | 0MB extra |
| **Pro** | Firecrawl API (cloud, sin RAM local) | 0MB extra |
| **Business** | Playwright local (full CamoFox) O Browserbase cloud | 200-800MB |

**Esto cambia la capacidad dramáticamente:**

- Sin browser (Starter/Pro): container idle ~150-300MB → **30-40 instancias por CX43**
- Con browser (Business): container activo ~800MB-1.2GB → **10-12 instancias**

### Cómo Desactivar el Browser

En `config.yaml` del tenant:
```yaml
tools:
  browser: false  # Desactiva todas las browser tools
web:
  provider: firecrawl  # Usa Firecrawl API para web access
```

O via toolset distributions (Hermes v0.13+):
```yaml
toolset_distributions:
  messaging:  # Para gateway (Telegram, Discord)
    exclude: [browser_navigate, browser_click, browser_snapshot, browser_vision]
```

---

## 2. Problemas Reales de Hermes en Multi-Instancia

### 2.1 Token Overhead (EL PROBLEMA #1)

**Hallazgo crítico** (de la comunidad):
- CLI: 6-8K tokens de overhead por request
- Gateway (Telegram/Discord): **15-20K tokens** por request (2-3x más)
- Un usuario reportó: "4 millones de tokens en 2 horas de uso ligero"
- "21K tokens solo preguntando por el clima"

**Causa**: Hermes carga tool definitions, system prompt, SOUL.md, skills activos, y AGENTS.md en cada request. En gateway mode, agrega metadata de la plataforma.

**Impacto en nuestro SaaS**: Si cada tenant usa 2-5M tokens/mes, y nosotros pagamos (modelo compartido), el costo es $0.60-$15/tenant/mes solo en tokens. Si el tenant trae su propia API key, no nos afecta.

**Mitigaciones que debemos implementar:**
1. Limitar skills activos por tier (menos skills = menos tokens de overhead)
2. Usar modelos con cache discount (DeepSeek V4: 90% descuento en cache hits)
3. Desactivar tools innecesarios por plataforma (toolset distributions)
4. No cargar AGENTS.md en producción (bug conocido, ya fixeado en versiones recientes)

### 2.2 Concurrencia y Archivos de Estado

**Advertencia oficial de Hermes:**
> "Never run two Hermes gateway containers against the same data directory simultaneously — session files and memory stores are not designed for concurrent write access."

**Impacto**: Cada tenant DEBE tener su propio volumen. No podemos compartir volúmenes entre instancias. Esto confirma que container-per-tenant es obligatorio, no opcional.

### 2.3 Dashboard Requiere Mismo PID Namespace

**Hallazgo**: El dashboard de Hermes necesita correr en el mismo container que el gateway (shared PID namespace). No se puede separar en otro container.

**Impacto**: Si ofrecemos dashboard por tenant, debe correr dentro del mismo container (puertos 8642 + 9119). Esto agrega ~50-100MB de RAM por tenant.

**Decisión**: Dashboard solo para tier Pro/Business. Starter usa solo nuestro dashboard web (martes.app).

### 2.4 Resource Limits Recomendados

Del docker-compose oficial de Hermes:
```yaml
deploy:
  resources:
    limits:
      memory: 4G
      cpus: "2.0"
```

**Esto es para un solo usuario con uso intensivo.** Para nuestro SaaS con uso moderado por tenant:
- Starter (sin browser, sin dashboard): `memory: 512M, cpus: 0.5`
- Pro (sin browser, con dashboard): `memory: 1G, cpus: 1.0`
- Business (con browser): `memory: 2G, cpus: 1.5`

### 2.5 Port Allocation

Cada instancia necesita puertos únicos:
- API server: 8642 (configurable)
- Dashboard: 9119 (configurable)

**Solución**: Asignar puertos dinámicamente por tenant:
- Tenant 1: 8700/9700
- Tenant 2: 8701/9701
- Tenant N: 8700+N / 9700+N

Traefik rutea por subdominio → puerto interno.

---

## 3. Manejo de Load Balancing

### Problema

Con 10-40 instancias por servidor, necesitamos:
1. Rutear requests al container correcto
2. Distribuir tenants entre múltiples servidores (cuando escalemos)
3. Health checks por instancia
4. Auto-restart en fallo

### Arquitectura de Routing

```
Internet
  │
  ▼
Cloudflare (DNS + CDN)
  │
  ▼
Traefik (reverse proxy en cada servidor)
  │
  ├── t001.martes.app → hermes-t001:8642
  ├── t002.martes.app → hermes-t002:8643
  ├── t003.martes.app → hermes-t003:8644
  └── ...
```

### Para Multi-Servidor (futuro)

```
Cloudflare DNS (weighted routing)
  │
  ├── server-1 (tenants 001-015)
  │   └── Traefik → hermes-t001...t015
  │
  ├── server-2 (tenants 016-030)
  │   └── Traefik → hermes-t016...t030
  │
  └── server-3 (tenants 031-045)
      └── Traefik → hermes-t031...t045
```

**No necesitamos un load balancer tradicional** porque cada tenant tiene un container fijo. El routing es determinístico (tenant → servidor → container). Solo necesitamos saber en qué servidor está cada tenant (tabla en la DB de la plataforma).

### Health Checks

El meta-agente (Agno) hace polling a `/health` de cada instancia:
```
GET http://hermes-t001:8642/health
GET http://hermes-t001:8642/health/detailed  # Status rico
```

Si falla 3 veces consecutivas → restart automático.

---

## 4. Costos Reales por Tenant (Investigación de Mercado)

### Hosting (nuestro costo)

| Tier | RAM/tenant | Tenants/CX43 | Costo/tenant |
|------|-----------|--------------|--------------|
| Starter | 512MB | ~25 | $0.64/mo |
| Pro | 1GB | ~12 | $1.33/mo |
| Business | 2GB | ~6 | $2.67/mo |

### LLM Tokens (costo del tenant o nuestro)

| Modelo | Input/1M | Output/1M | Costo mensual típico |
|--------|----------|-----------|---------------------|
| DeepSeek V4 | $0.30 | $0.50 | $2-5/mo |
| Claude Haiku 4.5 | $1.00 | $5.00 | $5-15/mo |
| GPT-4.1 | $2.00 | $8.00 | $10-30/mo |
| Claude Sonnet 4.6 | $3.00 | $15.00 | $15-50/mo |

### Modelo de Negocio Recomendado

**Opción A: Tenant trae su API key** (BYOK)
- Nosotros cobramos solo por hosting + plataforma
- Margen: 90%+ (solo pagamos infra)
- Riesgo: usuario ve el costo real de tokens y se asusta

**Opción B: API key compartida (nosotros pagamos tokens)**
- Cobramos un precio fijo que incluye X tokens/mes
- Margen: 50-70% (dependiendo del uso)
- Riesgo: heavy users nos cuestan más de lo que pagan

**Opción C: Híbrido (recomendado)**
- Starter: BYOK obligatorio (traen su OpenRouter key)
- Pro: Incluimos X tokens/mes con DeepSeek V4 (barato), BYOK opcional
- Business: Incluimos tokens premium, BYOK opcional para modelos custom

---

## 5. Cosas que Faltan por Configurar

### 5.1 Seguridad Multi-Tenant

| Item | Estado | Prioridad |
|------|--------|-----------|
| Aislamiento de red entre containers | Pendiente | CRITICO |
| Rate limiting por tenant (API server) | Pendiente | CRITICO |
| Disk quota por volumen | Pendiente | ALTO |
| CPU/RAM limits por container | Pendiente | ALTO |
| Logs separados por tenant | Pendiente | ALTO |
| Backup por tenant (no global) | Pendiente | MEDIO |
| Audit log de acciones del meta-agente | Pendiente | MEDIO |

### 5.2 Operaciones

| Item | Estado | Prioridad |
|------|--------|-----------|
| Auto-scaling (agregar servidores) | Pendiente | MEDIO |
| Migración de tenant entre servidores | Pendiente | MEDIO |
| Hermes version pinning por tenant | Pendiente | BAJO |
| Rollback de config por tenant | Pendiente | BAJO |
| Métricas de uso por tenant (tokens, requests) | Pendiente | ALTO |

### 5.3 Onboarding

| Item | Estado | Prioridad |
|------|--------|-----------|
| Setup wizard web (reemplaza CLI setup) | Pendiente | CRITICO |
| OAuth flow para Google/Notion en web | Pendiente | CRITICO |
| Telegram bot token input + verificación | Pendiente | ALTO |
| Discord bot setup guiado | Pendiente | ALTO |
| Modelo/provider selector visual | Pendiente | ALTO |
| SOUL.md editor (personalidad) | Pendiente | MEDIO |

---

## 6. Problemas Potenciales y Mitigaciones

### 6.1 "Noisy Neighbor" (un tenant consume todo)

**Problema**: Un tenant con cron jobs pesados o browser automation intensiva puede saturar CPU/RAM del servidor.

**Mitigación**:
- Docker resource limits estrictos (`--memory`, `--cpus`)
- OOM killer mata el container del tenant, no del servidor
- Meta-agente detecta containers que exceden limits repetidamente → notifica + throttle

### 6.2 Token Explosion

**Problema**: Un tenant con muchos skills activos + gateway + cron puede consumir millones de tokens sin darse cuenta.

**Mitigación**:
- Dashboard muestra uso de tokens en tiempo real
- Alertas cuando se acerca al límite del plan
- Hard cap: si excede 2x el límite, se pausa el cron y se notifica
- Toolset distributions: limitar tools por plataforma

### 6.3 Hermes Updates Rompen Cosas

**Problema**: NousResearch publica updates frecuentes. Un update puede romper skills o configs existentes.

**Mitigación**:
- NO auto-update tenants. Pinear versión por tenant.
- Testear nuevas versiones en un "canary tenant" interno primero
- Ofrecer "update" como acción manual en el dashboard
- Mantener 2-3 versiones de la imagen disponibles para rollback

### 6.4 Abuso de Gateway (Spam)

**Problema**: Un tenant usa el gateway de WhatsApp/Telegram para enviar spam masivo.

**Mitigación**:
- Rate limiting en mensajes salientes por tenant
- Monitoreo de patrones de spam (muchos mensajes a diferentes números)
- ToS explícitos: abuso = suspensión inmediata
- Las plataformas (Telegram, WhatsApp) ya tienen sus propios rate limits

### 6.5 Datos Sensibles en Volúmenes

**Problema**: Los volúmenes contienen API keys, OAuth tokens, conversaciones privadas.

**Mitigación**:
- Volúmenes en disco encriptado (LUKS)
- Permisos 700 en directorios de tenant
- Backup encriptado (GPG antes de subir a R2)
- Borrado seguro al cancelar cuenta (shred + rm)

---

## 7. Competencia Directa

| Competidor | Modelo | Precio | Diferencia con nosotros |
|-----------|--------|--------|------------------------|
| **Petronella** (managed Hermes) | Consultoría | $5K-$40K | Nosotros: self-service, $15-75/mo |
| **OpenClaw Cloud** | SaaS (fork antiguo) | Free-$20/mo | Nosotros: Hermes actual (no fork) |
| **FlyHermes** | Hosting simple | Variable | Nosotros: meta-agente + OAuth proxy |
| **Remote OpenClaw** | Guías/hosting | Variable | Nosotros: plataforma completa |

**Nuestro diferenciador**: 
1. Self-service (no consultoría)
2. Meta-agente que mantiene las instancias
3. OAuth proxy (conectar Google/Notion sin CLI)
4. Dashboard web (no solo CLI/Telegram)
5. Pricing accesible ($15-75/mo vs $5K+)

---

---

## 8. Hermes NO es Pesado — Tú Construyes Sobre Él

### Aclaración Importante

Hermes no es un monolito pesado que instalas completo. Es un **runtime ligero** donde tú decides qué activar:

- **Base** (gateway idle): ~150-200MB RAM — solo el loop de conversación + conexión a plataforma
- **+ Skills activos**: +50-100MB (depende de cuántos)
- **+ Browser (Playwright)**: +200-800MB (solo cuando se usa activamente)
- **+ Dashboard**: +50-100MB
- **+ Cron jobs corriendo**: +50-200MB (depende de la complejidad)

La imagen Docker incluye TODO (Playwright, Node.js, Python, etc.) pero **solo consume RAM lo que está activo**. Un tenant con solo Telegram + Google Workspace + 3 cron jobs usa ~300-400MB.

### Presets Preconfigurados (Producto)

Podemos ofrecer "templates" de Hermes preconfigurados:

#### Template: "Asistente de Trabajo" ($15/mo)
```yaml
# config.yaml preconfigurado
platforms: [telegram]  # O discord
skills:
  - google-workspace   # Gmail, Calendar, Drive, Sheets
  - airtable           # Base de datos
  - notion             # Notas y wikis
tools:
  browser: false       # Sin browser (ahorra RAM)
  web_search: true     # Búsqueda web básica
  terminal: false      # Sin acceso a terminal
  file: false          # Sin manipulación de archivos
cron:
  - "Daily briefing at 8am: summarize unread emails and today's calendar"
  - "Weekly report: Airtable status summary every Monday 9am"
  - "Auto-archive: move emails older than 30 days to archive every Sunday"
model: deepseek-v4     # Barato, con cache discount
```

**RAM estimada**: ~300MB idle, ~400MB activo
**Tokens**: ~500K-1M/mes (bajo, sin browser)
**Costo nuestro**: ~$0.50/mo infra + $0-2/mo tokens (BYOK o DeepSeek)

#### Template: "Asistente Completo" ($35/mo)
```yaml
platforms: [telegram, discord]
skills:
  - google-workspace
  - airtable
  - notion
  - github-code-review
  - ocr-and-documents
tools:
  browser: firecrawl   # Web scraping via API (sin RAM local)
  web_search: true
  terminal: true       # Puede ejecutar código
  file: true
  vision: true         # Analiza imágenes
cron:
  - "Daily briefing at 8am"
  - "Monitor GitHub PRs every 2 hours"
  - "Weekly analytics report"
  - "Daily expense tracker from email receipts"
model: claude-haiku    # Mejor razonamiento
dashboard: true        # Dashboard web incluido
```

**RAM estimada**: ~500-700MB
**Tokens**: ~2-5M/mes
**Costo nuestro**: ~$1.50/mo infra + $5-15/mo tokens

#### Template: "Agente Autónomo" ($75/mo)
```yaml
platforms: [telegram, discord, whatsapp, api]
skills:
  - google-workspace
  - airtable
  - notion
  - github-pr-workflow
  - linear
  - ocr-and-documents
  - research (arxiv, web)
tools:
  browser: playwright  # Browser completo (CamoFox)
  web_search: true
  terminal: true
  file: true
  vision: true
  delegate: true       # Puede crear sub-agentes
  code_execution: true
cron:
  - "Daily briefing at 8am"
  - "Monitor all platforms every 30 min"
  - "Weekly deep research report"
  - "Auto-respond to routine emails"
  - "Nightly backup of Notion workspace"
model: claude-sonnet   # Máximo razonamiento
dashboard: true
memory: unlimited
```

**RAM estimada**: ~1-2GB (con browser activo)
**Tokens**: ~5-15M/mes
**Costo nuestro**: ~$2.50/mo infra + $15-50/mo tokens

---

## 9. Aislamiento de Red — Cómo Funciona

### El Problema Original

Hermes usa `network_mode: host` en su docker-compose oficial. Esto significa que el container comparte la red del servidor directamente — puede ver todos los puertos, todos los otros containers, todo.

**Para un SaaS multi-tenant esto es INACEPTABLE.** Un tenant podría acceder a la base de datos de otro, o al API server de otro tenant.

### La Solución: Bridge Networks Aisladas

```
┌─────────────────────────────────────────────────────┐
│ Servidor                                             │
│                                                      │
│  ┌─────────────────────────────────────────────┐    │
│  │ Red "platform" (solo infra + API)            │    │
│  │  Traefik ←→ Platform API ←→ PostgreSQL      │    │
│  └─────────────────────────────────────────────┘    │
│                                                      │
│  ┌──────────────┐  ┌──────────────┐                 │
│  │ Red "t001"   │  │ Red "t002"   │  (aisladas)    │
│  │              │  │              │                  │
│  │ hermes-t001  │  │ hermes-t002  │                 │
│  │ (solo ve     │  │ (solo ve     │                 │
│  │  su propia   │  │  su propia   │                 │
│  │  red + salida│  │  red + salida│                 │
│  │  a internet) │  │  a internet) │                 │
│  └──────────────┘  └──────────────┘                 │
└─────────────────────────────────────────────────────┘
```

**Implementación:**

```bash
# Crear red aislada por tenant
docker network create --internal=false tenant-t001

# Lanzar container en su red aislada
docker run -d \
  --name hermes-t001 \
  --network tenant-t001 \
  --memory 512m \
  --cpus 0.5 \
  -v /var/lib/martes/tenants/t001:/opt/data \
  nousresearch/hermes-agent gateway run
```

**Qué logra esto:**
- Tenant t001 NO puede ver a tenant t002 (redes separadas)
- Tenant t001 NO puede acceder a PostgreSQL de la plataforma (red diferente)
- Tenant t001 SÍ puede acceder a internet (para APIs, LLM, etc.)
- Traefik SÍ puede rutear tráfico al tenant (se conecta a ambas redes)

**NO necesita IP propia cada container.** Docker asigna IPs internas automáticamente (172.x.x.x). Traefik rutea por nombre de container, no por IP.

### Alternativa Más Simple (si no hay riesgo real)

Si todos los tenants son BYOK y no comparten infraestructura sensible, el aislamiento de red es **nice-to-have, no crítico**. Lo crítico es:
1. Volúmenes separados (ya lo tenemos)
2. Resource limits (memory/CPU)
3. No `network_mode: host` (usar bridge default)

Con bridge default, los containers pueden verse entre sí por nombre, pero no pueden acceder a puertos que no están expuestos. Si PostgreSQL solo expone en `127.0.0.1:5432` (no en la red Docker), los tenants no pueden accederlo.

---

## 10. Métricas de Uso — No Son Necesarias Si Es BYOK

### Si el tenant trae su propia API key (BYOK):

- **No necesitamos medir tokens** — el tenant ve su consumo directamente en OpenRouter/Anthropic/etc.
- **No necesitamos billing por uso** — cobramos flat fee por el hosting
- **Lo que sí medimos**: uptime del container, health checks, disk usage

### Si nosotros proveemos la IA (modelo compartido):

Necesitamos un **proxy de API** entre Hermes y el LLM provider que:
1. Intercepta cada request al LLM
2. Cuenta tokens (input + output)
3. Asocia al tenant
4. Aplica rate limits por plan

**Implementación**: Un proxy ligero (LiteLLM o similar) que corre como servicio compartido:

```
Hermes-t001 → LiteLLM Proxy → OpenRouter → LLM
                  ↓
            Registra: tenant=t001, tokens_in=5000, tokens_out=1200
```

**LiteLLM** ya hace esto out-of-the-box:
- Proxy OpenAI-compatible
- Tracking por API key (una key por tenant)
- Rate limiting
- Fallback entre providers
- Dashboard de uso

### Recomendación

**MVP**: Solo BYOK. No necesitas métricas de tokens. Cobra flat fee.
**V2**: Agrega LiteLLM proxy para ofrecer "tokens incluidos" en Pro/Business.

---

## 11. Version Pinning — Sí, Es Lo Mejor

### Por Qué

Hermes publica releases frecuentes (v0.14.0 actual, ~2 releases/mes). Cada release puede:
- Cambiar formato de config.yaml
- Deprecar skills
- Romper plugins
- Cambiar comportamiento de tools

Si auto-updateamos todos los tenants, un release roto afecta a TODOS.

### Cómo Implementarlo

```bash
# Cada tenant tiene su versión pinned
docker run -d \
  --name hermes-t001 \
  nousresearch/hermes-agent:0.14.0  # Versión fija, no :latest
```

**Flujo de updates:**
1. NousResearch publica v0.15.0
2. Nosotros la testeamos en un tenant interno ("canary")
3. Si funciona bien → la marcamos como "stable" en nuestra plataforma
4. Los tenants ven "Update available" en su dashboard
5. El tenant decide cuándo actualizar (click en "Update")
6. El meta-agente hace: stop container → pull nueva imagen → start container

**Rollback**: Si el tenant reporta problemas post-update, el meta-agente puede revertir a la versión anterior (la imagen anterior sigue en cache).

### Versiones que Mantenemos

| Tag | Propósito |
|-----|-----------|
| `0.14.0` | Versión actual estable |
| `0.13.0` | Versión anterior (rollback) |
| `latest` | NUNCA usar en producción |
| `canary` | Para testing interno |

---

## 12. Decisiones Actualizadas (Final)

| Decisión | Resolución Final |
|----------|-----------------|
| Browser | Por template: "Trabajo" sin browser, "Completo" con Firecrawl, "Autónomo" con Playwright |
| Capacidad | ~30-40 "Trabajo", ~15-20 "Completo", ~8-10 "Autónomo" por CX43 |
| Tokens | BYOK obligatorio en MVP. LiteLLM proxy en V2 para "tokens incluidos" |
| Métricas | No necesarias si BYOK. Solo health/uptime. LiteLLM en V2. |
| Aislamiento de red | Bridge networks separadas por tenant (no host mode) |
| Version pinning | Sí. Versión fija por tenant. Update manual via dashboard. |
| Presets | 3 templates preconfigurados (Trabajo $15, Completo $35, Autónomo $75) |
| Cron jobs | Preelaborados por template + custom del tenant |
| Dashboard Hermes | Solo en "Completo" y "Autónomo" |
| Skills | Preinstalados por template, tenant puede agregar más |
