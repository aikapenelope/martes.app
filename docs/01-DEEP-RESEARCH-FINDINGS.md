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

## 8. Decisiones Actualizadas

| Decisión | Antes | Ahora (post-investigación) |
|----------|-------|---------------------------|
| Browser | Incluido siempre | Por tier (Starter: sin browser, Pro: Firecrawl, Business: Playwright) |
| Capacidad | 10-12/servidor | 25-30 Starter, 12-15 Pro, 6-8 Business |
| Tokens | Modelo compartido | BYOK para Starter, incluido para Pro/Business |
| Dashboard Hermes | Para todos | Solo Pro/Business (Starter usa nuestro web UI) |
| Resource limits | No definidos | 512MB/0.5CPU (S), 1GB/1CPU (P), 2GB/1.5CPU (B) |
| Updates | Auto | Pinned por tenant, update manual |
| Load balancing | Tradicional | Determinístico (tenant → servidor fijo) |
