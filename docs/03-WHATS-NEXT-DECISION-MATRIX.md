# Martes.app — Qué Sigue + Decisiones Pendientes

> **Status**: Checkpoint de planificación  
> **Date**: May 2026

---

## 1. Lo Que Ya Está Definido (No Requiere Más Decisiones)

| Tema | Decisión | Doc |
|------|----------|-----|
| Aislamiento de tenants | Container por tenant, volumen propio, bridge network | doc-02 |
| Base de datos interna de Hermes | SQLite (state.db) dentro del volumen — no tocamos | doc-02 |
| Base de datos de plataforma | PostgreSQL compartido (Agno + plataforma, ~200MB) | doc-02 |
| Browser | Por tier: sin browser / Firecrawl / Playwright | doc-01 |
| Tokens/LLM | BYOK en MVP, LiteLLM proxy en V2 | doc-01 |
| Version pinning | Sí, versión fija por tenant, update manual | doc-01 |
| Templates preconfigurados | 3 tiers: Trabajo ($15), Completo ($35), Autónomo ($75) | doc-01 |
| Meta-agente | Agno con PostgresDb, tools de Docker + DB | doc-00, doc-02 |
| Infra base | Hetzner CX43, Docker, Traefik | doc-00 |

---

## 2. Verificación: Docker Bridge NO Tiene Problemas con Hermes

Revisé el código fuente de Hermes:

| Componente | ¿Funciona en bridge mode? | Notas |
|-----------|--------------------------|-------|
| Gateway (Telegram, Discord, WhatsApp) | SI | Solo hace requests salientes a APIs externas |
| API Server (puerto 8642) | SI | Necesita `API_SERVER_HOST=0.0.0.0` para ser alcanzable |
| Dashboard (puerto 9119) | SI | Necesita `HERMES_DASHBOARD_HOST=0.0.0.0` |
| Cron jobs | SI | Solo ejecutan código dentro del container |
| Skills (Google, Notion, Airtable) | SI | Solo hacen HTTP requests salientes |
| Browser (Playwright) | SI | Navega internet, no necesita puertos entrantes |
| Docker backend (sandbox) | PARCIAL | Si el tenant quiere Docker-in-Docker, necesita socket mount |
| MCP servers | SI | Se conectan via stdio o HTTP saliente |

**El único caso problemático**: Si un tenant quiere usar el "Docker terminal backend" (Hermes crea un sub-container para ejecutar código). Esto requiere montar `/var/run/docker.sock` — lo cual es un riesgo de seguridad en multi-tenant.

**Solución**: No ofrecer Docker backend en el SaaS. Usar "local" backend (el código se ejecuta dentro del mismo container de Hermes, que ya está aislado). O usar Modal/Daytona como backend remoto para el tier Business.

---

## 3. La Decisión de Coolify

### Opción A: Sin Coolify (Docker Compose + Meta-Agente)

```
Meta-agente Agno gestiona containers directamente via Docker API:
- docker run / docker stop / docker rm
- docker network create
- docker logs
- Health check polling
```

**Pros:**
- 0MB de RAM extra (Coolify consume ~500MB-1GB)
- Control total programático
- Sin UI que pueda ser hackeada
- Más tenants por servidor

**Contras:**
- Sin UI visual para debugging manual
- Todo depende del meta-agente (si falla, no hay plan B)
- No hay log viewer bonito

### Opción B: Con Coolify (como UI de admin)

```
Coolify corre en el servidor como panel de admin:
- Visualizar containers
- Ver logs
- Restart manual si algo falla
- El meta-agente TAMBIÉN gestiona containers (Coolify es solo viewer)
```

**Pros:**
- UI para cuando necesitas intervenir manualmente
- Log viewer sin SSH
- Puedes ver el estado de todo de un vistazo

**Contras:**
- ~500MB-1GB de RAM (Coolify + su PostgreSQL + su Redis)
- Eso son 2-3 tenants menos por servidor
- Otro servicio que mantener/actualizar
- Superficie de ataque adicional (panel web público)

### Opción C: Coolify Solo en Dev/Staging, No en Producción

```
- Servidor de producción: solo Docker + meta-agente (máxima densidad)
- Servidor de staging/admin: Coolify para debugging y testing
```

**Pros:**
- Producción optimizada (máximos tenants)
- Tienes UI cuando la necesitas (en staging)
- Separación de concerns

**Contras:**
- Necesitas un segundo servidor (CX22, ~$4/mo)
- O usas Coolify solo en tu laptop via Tailscale

### Mi Recomendación: Opción A (Sin Coolify) + Portainer Ligero

**Portainer CE** (Community Edition) es una alternativa a Coolify que:
- Consume solo ~30-50MB de RAM (vs 500MB-1GB de Coolify)
- Es solo un viewer de Docker (no hace builds, no hace deploys)
- Te da: lista de containers, logs, restart, shell access
- Se accede via Tailscale (no público)

```yaml
portainer:
  image: portainer/portainer-ce:latest
  container_name: portainer
  restart: unless-stopped
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock
    - portainer_data:/data
  ports:
    - "127.0.0.1:9000:9000"  # Solo accesible via Tailscale
  deploy:
    resources:
      limits:
        memory: 64M
```

Esto te da una UI de emergencia sin sacrificar RAM significativa.

---

## 4. Lo Que Falta Definir Antes de Empezar a Codear

### 4.1 Decisiones de Producto

| Pregunta | Opciones | Impacto |
|----------|----------|---------|
| ¿Subdominios o paths? | `t001.martes.app` vs `martes.app/t001` | Routing de Traefik, SSL certs |
| ¿Cómo se registra el usuario? | Landing → Stripe → auto-provision | Flujo de onboarding |
| ¿Qué pasa si no paga? | Container se para vs se borra vs se congela | Retención de datos |
| ¿Puede el tenant hacer SSH a su container? | Sí (via web terminal) vs No | Seguridad, complejidad |
| ¿Ofrecemos custom SOUL.md? | Editor en dashboard vs solo templates | UX, diferenciación |
| ¿Telegram bot compartido o por tenant? | Un bot nuestro vs cada tenant crea el suyo | Onboarding friction |

### 4.2 Decisiones Técnicas

| Pregunta | Opciones | Impacto |
|----------|----------|---------|
| ¿Frontend framework? | Nuxt 3 vs Next.js vs solo landing estática | Velocidad de desarrollo |
| ¿Cómo se comunica el dashboard con el meta-agente? | API REST vs WebSocket vs cola de mensajes | Tiempo real vs simplicidad |
| ¿Dónde corre el meta-agente? | Mismo servidor vs separado | Resiliencia |
| ¿Cómo se escala a múltiples servidores? | DNS routing vs proxy central | Complejidad |
| ¿Backup offsite? | R2 vs Hetzner Object Storage vs S3 | Costo, velocidad |

### 4.3 Lo Que NO Necesitas Decidir Ahora

- Multi-servidor (resuelve cuando tengas 15+ tenants)
- Composio MCP (resuelve cuando un tenant lo pida)
- Custom domains por tenant (resuelve después del MVP)
- Mobile app (resuelve después de validar el producto)

---

## 5. Orden de Implementación Sugerido

### Fase 1: Infraestructura Base (1 semana)

```
1. docker-compose.prod.yml con:
   - PostgreSQL (plataforma + Agno)
   - Traefik (reverse proxy)
   - Meta-agente Agno (container)
   - Portainer (UI de emergencia)

2. Script de bootstrap (como novaincs)

3. Meta-agente con tools básicos:
   - create_tenant_container()
   - stop_tenant_container()
   - restart_tenant_container()
   - check_health()
   - list_containers()
```

### Fase 2: Plataforma Web (1-2 semanas)

```
4. Landing page (martes.app)
5. Stripe checkout → webhook → crear tenant
6. Dashboard mínimo:
   - Status del agente (running/stopped)
   - Conectar Telegram (input bot token)
   - Elegir template
   - Ver logs básicos
```

### Fase 3: Integraciones (1 semana)

```
7. OAuth flow para Google Workspace
8. Input de API key para Notion/Airtable
9. Cron jobs preconfigurados por template
10. SOUL.md editor básico
```

### Fase 4: Producción (1 semana)

```
11. Monitoring (health checks + alertas)
12. Backup automatizado
13. Documentación para usuarios
14. Beta launch (5-10 usuarios)
```

---

## 6. Resumen Ejecutivo

**¿Qué falta por definir?** Las decisiones de producto (sección 4.1). Las técnicas se resuelven durante la implementación.

**¿Coolify?** No. Usa Portainer CE (~50MB) como UI de emergencia. El meta-agente gestiona todo programáticamente.

**¿Docker bridge tiene problemas con Hermes?** No. Verificado en el código fuente. Solo necesitas `API_SERVER_HOST=0.0.0.0` y no ofrecer Docker-in-Docker backend.

**¿Estamos listos para empezar a codear?** Sí, si decides las preguntas de producto de la sección 4.1. La arquitectura técnica está completa.
