# Martes.app — Decisiones de Producto (Final)

> **Status**: Aprobado — listo para implementar  
> **Date**: May 2026

---

## 1. Modelo de Negocio

### Cliente Objetivo

PYMEs con equipos de hasta 10 personas que quieren un agente IA conectado a sus herramientas de trabajo (Google, Notion, Airtable, GitHub, email).

### Precio

**$75-100/mes por equipo** (no por persona).

Un solo container de Hermes sirve a todo el equipo:
- El agente responde en un grupo de Telegram/Discord donde están todos
- Hermes distingue quién habla (por user_id) y mantiene memoria por persona
- Historial compartido en el canal del equipo

### Cobro

- WhatsApp (contacto inicial, onboarding)
- Stripe Checkout (pago recurrente)

---

## 2. UI del Tenant: Dashboard de Hermes via Subdominio

### Cómo Funciona

Cada tenant tiene un subdominio: `{empresa}.martes.app`

Ese subdominio apunta al Dashboard de Hermes (puerto 9119 del container del tenant). El dashboard muestra:
- Historial de conversaciones
- Estado del agente (running, skills activos)
- Cron jobs configurados
- Memoria del agente
- Configuración

### Seguridad: Cloudflare Access

El dashboard de Hermes NO tiene autenticación propia. Usamos **Cloudflare Access** (gratis hasta 50 usuarios) como capa de seguridad:

```
Miembro del equipo → empresa.martes.app → Cloudflare Access (login email) → Dashboard
```

- El tenant nos da los emails de su equipo (hasta 10)
- Cloudflare envía un código al email para verificar
- Sin contraseñas que gestionar
- SSL + DDoS protection incluido
- Si alguien no autorizado intenta acceder → bloqueado por Cloudflare

### Configuración por Tenant

```
DNS: empresa.martes.app → A record → IP del servidor
Cloudflare Access: policy "empresa" → allow emails: [user1@empresa.com, user2@empresa.com, ...]
Traefik: empresa.martes.app → hermes-{tenant_id}:9119
```

### Sin Workspace (TUI Web)

El Workspace de Hermes (terminal interactiva en browser) consume ~100-200MB extra y requiere un container separado. No lo ofrecemos. El Dashboard básico es suficiente para PYMEs.

---

## 3. Templates Preconfigurados

### Template: "Oficina" (default, $75/mo)

Para equipos que usan Google Workspace + Notion/Airtable.

**Skills incluidos:**
| Skill | Función | Setup del tenant |
|-------|---------|-----------------|
| google-workspace | Gmail, Calendar, Drive, Sheets, Docs | OAuth (nosotros gestionamos) |
| notion | Páginas, bases de datos, búsqueda | API key (tenant la pega) |
| airtable | CRUD de registros, filtros, upserts | API key (tenant la pega) |
| himalaya | Email IMAP/SMTP directo | Credenciales de email |
| ocr-and-documents | Leer PDFs, imágenes con texto | Ninguno |

**Cron jobs preconfigurados:**
1. "Resumen diario a las 8am: emails sin leer + calendario de hoy"
2. "Reporte semanal: actividad en Notion/Airtable cada lunes 9am"
3. "Auto-archivar emails de más de 30 días cada domingo"

**Tools activos:** web_search, memory, todo, clarify, cronjob, vision
**Plataforma:** Telegram O Discord (1)
**Browser:** No (usa web_search para búsquedas)
**RAM estimada:** ~300-400MB

---

### Template: "Desarrollo" ($100/mo)

Para equipos de desarrollo que usan GitHub + Linear + Google.

**Skills incluidos:**
| Skill | Función | Setup |
|-------|---------|-------|
| google-workspace | Email, Calendar | OAuth |
| github-pr-workflow | PRs, branches, commits, merge | GitHub token |
| github-code-review | Review de PRs, comentarios inline | GitHub token |
| github-issues | Crear, triagear, asignar issues | GitHub token |
| linear | Issues, proyectos, sprints | API key |
| notion | Documentación, wikis | API key |
| ocr-and-documents | Leer PDFs, screenshots | Ninguno |
| test-driven-development | TDD workflow | Ninguno |
| systematic-debugging | Debugging estructurado | Ninguno |

**Cron jobs preconfigurados:**
1. "Revisar PRs abiertos cada 2 horas, notificar conflictos"
2. "Resumen diario: issues asignados + PRs pendientes"
3. "Reporte semanal: commits, PRs merged, issues cerrados"
4. "Monitorear CI failures y notificar"

**Tools activos:** web_search, terminal, file, memory, todo, skills, code_execution, delegate
**Plataformas:** Telegram + Discord (2)
**Browser:** Firecrawl (API, sin RAM local)
**Dashboard:** Incluido
**RAM estimada:** ~500-700MB

---

### Template: "Custom" ($100/mo)

Para equipos con necesidades específicas. Se configura a medida.

**Skills:** Los que el equipo necesite (de los 50+ disponibles en Hermes)
**Cron jobs:** Custom, definidos con el equipo
**Plataformas:** Las que necesiten
**Browser:** Según necesidad
**Dashboard:** Incluido

---

## 4. Flujo de No-Pago

```
Día 0:  Suscripción activa, container corriendo
Día 30: Stripe intenta cobrar → falla
Día 31: Stripe reintenta → falla
Día 33: Stripe marca como "past_due"
        → Webhook llega a nuestro servidor
        → Meta-agente para el container (docker stop)
        → Tenant recibe mensaje: "Tu agente está pausado. Actualiza tu pago."
        → Dashboard muestra "Pausado — actualiza tu método de pago"

Día 45: Si no paga en 15 días:
        → Meta-agente hace backup del volumen (tar.gz → R2)
        → Elimina el volumen local (libera espacio)
        → Tenant recibe: "Tu agente fue archivado. Puedes reactivarlo pagando."

Si paga después:
        → Stripe webhook "invoice.paid"
        → Meta-agente descarga backup de R2
        → Descomprime volumen
        → Crea nuevo container
        → Todo restaurado (conversaciones, memoria, skills, cron)
        → Tenant recibe: "Tu agente está de vuelta."

Día 90: Si no paga en 90 días:
        → Backup se elimina de R2
        → Datos perdidos permanentemente
        → Tenant notificado antes (día 80): "Última oportunidad"
```

### Por Qué Funciona

Hermes almacena TODO en `/opt/data`:
- `state.db` (sesiones, historial)
- `memories/` (memoria persistente)
- `skills/` (skills instalados)
- `cron/jobs.json` (cron jobs)
- `config.yaml` (configuración)
- `.env` (API keys)
- `SOUL.md` (personalidad)

Un `tar.gz` de ese directorio es un backup completo. Restaurar = descomprimir + crear container. El tenant no pierde nada.

---

## 5. Capacidad Final por Servidor

| Template | RAM/tenant | Tenants/CX43 (16GB) | Revenue |
|----------|-----------|---------------------|---------|
| Oficina | ~400MB | ~30 | $2,250/mo |
| Desarrollo | ~700MB | ~18 | $1,800/mo |
| Custom | ~700MB | ~18 | $1,800/mo |
| Mix típico (70% Oficina, 30% Dev) | ~500MB avg | ~24 | $2,000/mo |

**Costo del servidor**: ~$16/mo
**Margen**: 99%+ (sin contar tokens, que son BYOK)

---

## 6. Stack Final

| Componente | Tecnología |
|-----------|-----------|
| Landing/Dashboard de gestión | Nuxt 3 en `app.martes.app` |
| Pagos | Stripe (webhook → meta-agente) |
| Onboarding | WhatsApp (manual) + dashboard web |
| Containers de tenants | `nousresearch/hermes-agent:0.14.0` |
| Meta-agente | Agno (Python) con PostgresDb |
| DB plataforma | PostgreSQL 16 Alpine (~200MB) |
| Reverse proxy | Traefik v3 |
| SSL + seguridad dashboard | Cloudflare Access (gratis) |
| Viewer de emergencia | Portainer CE (~50MB) |
| Backup | tar.gz → Cloudflare R2 |
| Monitoring | Health check polling + Sentry |

---

## 7. Siguiente Paso: Codear

La planificación está completa. Empezamos con:

1. **docker-compose.prod.yml** (PostgreSQL + Traefik + Portainer + meta-agente)
2. **Meta-agente** con tools: create/stop/restart container, check billing, backup
3. **Script de provisioning** de un tenant (crear volumen, config, container)
4. **Landing page** + Stripe checkout
5. **Dashboard** mínimo (status + conectar Telegram)
