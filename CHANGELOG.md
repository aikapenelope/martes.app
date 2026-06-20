# CHANGELOG — martes.app

---

## [Sprint 9] — 4–5 junio 2026

### Schedules — fix crítico del startup handler (PR #82)

**Root cause confirmado**: `@app.on_event("startup")` (deprecado en FastAPI ≥0.99) ejecutaba llamadas HTTP a `localhost:7777` antes de que el servidor aceptara conexiones. `ConnectionRefused` era silenciado por `except Exception`. Solo `daily-backup-all` existía (creado el 24 mayo en el primer deploy). Los otros 4 schedules nunca se registraron en los 10 días siguientes.

**Fix**: patrón `lifespan=` documentado en https://docs.agno.com/agent-os/lifespan. `asyncio.create_task()` difiere la ejecución hasta que el servidor está listo. La función `_register_schedules_when_ready()` reintenta `GET /health` cada 5s (hasta 60s) antes de crear los schedules.

Schedules ahora funcionando en producción (confirmado via `ai.agno_schedules`):
- `daily-backup-all` · `health-check-all` · `billing-check` · `expire-platform-keys` · `docker-cleanup` · `prune-old-data`

También en PR #82:
- Nuevo endpoint `POST /maintenance/prune-old-data` — limpia `ai.martes_traces` (30d), `ai.martes_sessions` (90d), `public.health_checks` (90d). Schedule domingos 2AM UTC.
- `container_health()` y `check_all_health()`: nuevo estado `"starting"` para containers con < 60s de vida y `restart_count == 0` — evita falsos positivos inmediatamente después de `create_tenant()` o restart.

### Billing agent (PR #84)

Nuevo agente `Billing` en el Team (`apps/meta-agent/src/agents/billing.py`). Tercer especialista del coordinador, solo lectura.

4 tools en `read_ops.py`:
- `get_billing_summary()` — conteo por status, vencen en 7d, revenue mes actual, tenants en trial
- `get_expiring_tenants(days)` — tenants venciendo en N días con flag `overdue`
- `get_revenue_by_period(year, month)` — revenue con desglose por tenant
- `get_tenant_payment_history(tenant_code)` — historial completo de pagos

Ejemplos desde Telegram: *"¿quiénes vencen esta semana?"*, *"¿cuánto revenue llevo este mes?"*, *"¿qué pagos tiene t001?"*

### H1 — inject_credential soporta openrouter_api_key (PR #85)

- Añadido `openrouter_api_key` al `CredentialType Literal` y `_CREDENTIAL_FILE_MAP`
- Al inyectar `openrouter_api_key`, el marker `.platform_key_expires` se borra inmediatamente — sin esperar el ciclo de 30 min del scheduler BYOK

### H5 — 104 tests unitarios + CI (PR #86, #89)

**PR #86**: 74 tests en 4 archivos (tar filter, validación, BYOK, billing). Job `unit-tests` añadido al CI en paralelo con el build check.

**PR #89** (+30 tests):
- `test_backup_security.py`: path traversal en `_restore_filter()`, chmod 600 post-restore, consistencia `_RESTORE_STALE_FILES` vs `_BACKUP_EXCLUDE_NAMES`
- `test_inject_credential.py`: lógica de cleanup marker BYOK, formato .env
- `test_billing_edge_cases.py`: `paid_until=NULL`, `BILLING_AUTO_SUSPEND=False`, alertas en días exactos

**Bugfix descubierto por tests**: `gateway.lock` estaba en `_RESTORE_STALE_FILES` pero no en `_BACKUP_EXCLUDE_NAMES` — podía entrar en backups y bloquear el arranque de Hermes al restaurar.

### server_metrics + backup_log → Metabase (PR #87)

**Nuevas tablas en schema `public`** (migración 004):
- `server_metrics(disk_used_gb, disk_total_gb, disk_pct, checked_at)` — escrita por `health-check-all` cada 5 min
- `backup_log(tenant_code, filename, size_mb, storage, created_at)` — escrita por `backup_tenant()` en cada backup

**Metabase configurado completamente** (via API):
- Dashboard "martes.app — Plataforma" con **16 cards** como homepage
- 4 KPIs numéricos · tabla tenants + vencimientos · uptime · response time · health timeline · incidentes · revenue · disco histórico · schedules · historial de backups

### Bugfixes críticos (PR #90)

**Bug 1 — CRÍTICO — upgrade_tenant() columna incorrecta**:
`SET template = %s` intentaba escribir `"nousresearch/hermes-agent:v2026.6.1"` (38 chars) en `template VARCHAR(20)`. PostgreSQL lo rechazaba. Ningún upgrade había registrado la versión nueva en DB. Fix: `SET extra_config = extra_config || %s::jsonb` con `{"hermes_image": "..."}`.

**Bug 2 — inject_wiki_content() custom_pages nunca funcionaba**:
`"concepts" / pn` era `str / str` → `TypeError` silenciado por `except Exception: pass`. Las páginas wiki custom nunca se creaban. Fix: `Path("concepts") / pn`.

**Inconsistencia A — upgrade_tenant() con restricciones obsoletas**:
`_run_container()` dentro de `upgrade_tenant()` seguía con `cap_drop=ALL`, `pids_limit=256`, `tmpfs=100m`, `security_opt=no-new-privileges` — los mismos que PR #76 eliminó de `create_tenant()`. Un tenant upgradeado quedaba más restringido que uno nuevo. Eliminados.

**Inconsistencia B — check_all_health() sin estado 'starting'**:
`container_health()` correctamente devuelve `"starting"` para containers recién arrancados. `check_all_health()` (scheduler global) los clasificaba como `"unhealthy"` generando alertas falsas. Corregido con el mismo criterio.

**Inconsistencia C — commit() explícito**:
`backup_log` y `server_metrics` ahora tienen `conn.commit()` explícito, consistente con el resto del código.

### Principio verificado (todos los PRs de esta sesión)

El `.env` de arranque tiene exactamente **6 vars** y nada más. La única limitación del container es `mem_limit=768m`. Confirmado en las tres funciones que crean containers (`create_tenant`, `upgrade_tenant`, `recreate_tenant_container`). Hermes tiene capacidades completas de fábrica — `hermes skills install`, `hermes update`, `agent-browser install`, subagentes.

---

## [Sprint 8] — 4 junio 2026

### Paradigma plataforma vs agente (PR #74)

- **Nuevo paradigma documentado**: martes.app gestiona la plataforma. Hermes gestiona su funcionamiento interno. Regla absoluta: si Hermes tiene un comando nativo para algo, el cliente lo hace desde Telegram — nosotros no lo reimplementamos desde el backend. Ver `docs/hermes-guia/00-PARADIGMA-PLATAFORMA.md`
- **Fix home channel** — `TELEGRAM_HOME_CHANNEL={telegram_user_id}` y `TELEGRAM_HOME_CHANNEL_NAME={name}` escritos en `.env` al crear el tenant. Elimina el mensaje "📬 No home channel is set" que aparecía en cada primera conversación de sesión nueva. Fuente: `hermes/gateway/run.py:8530` — condición que dispara el aviso cuando `TELEGRAM_HOME_CHANNEL` no está en el entorno. En Telegram DMs, `chat_id == user_id` del destinatario.
- **AGENTS.md** actualizado con regla "Paradigma plataforma vs agente" — la prueba de fuego para toda decisión de implementación

### Hermes factory defaults — sin restricciones de container (PR #76)

Eliminadas todas las restricciones que impedían a Hermes operar con total libertad:
- `cap_drop=["ALL"]` → eliminado
- `cap_add=[NET_RAW, CHOWN, ...]` → eliminado (innecesario sin cap_drop)
- `pids_limit=256` → eliminado (bloqueaba npm, subagentes, skills con subprocess)
- `tmpfs={"/tmp": "size=100m"}` → eliminado (bloqueaba `agent-browser install`, pip installs)
- `security_opt=["no-new-privileges"]` → eliminado

**Único límite intencional que permanece**: `mem_limit=768m` (límite de la plataforma SaaS).

El cliente puede ahora desde Telegram: `hermes skills install X`, `agent-browser install`, `hermes update`, spawnar subagentes paralelos — exactamente como viene de fábrica en NousResearch.

Aplica también a `recreate_tenant_container()` para consistencia en rebuild y restore.

Ref: docker-compose.yml oficial de NousResearch — sin ninguna de estas restricciones.

### Investigación y decisiones arquitecturales (PRs #71–73, #75, #77–79)

**Investigación PocketBase** (documentada en `docs/hermes-guia/07` y `08`):
- Una instancia por tenant = recomendación oficial del maintainer ganigeorgiev (GitHub #738)
- MCP server `@mabeldata/pocketbase-mcp` identificado como opción correcta para comunicación Hermes↔PocketBase
- La posición oficial de PocketBase: "NOT recommended for production critical applications yet" (pre-v1.0.0)

**Investigación InsForge** (YC Spring 2026, OSS Apache-2.0):
- Plataforma backend diseñada específicamente para agentes de IA
- Multi-tenancy: NO nativa — "Running Multiple Projects" = múltiples Docker Compose stacks separados (~450-600MB por stack)
- MCP server built-in — el más maduro del ecosistema
- Descartado para martes.app: misma limitación que PocketBase pero 15-20x más RAM por instancia

**Investigación CRM ligero ("Memos para CRM")**:
- No existe en el ecosistema 2026
- CRMs existentes (EspoCRM, Twenty, Frappe, Monica) todos requieren stack completo (~400MB+)
- El único que cumple "como Memos" era PocketBase (pre-v1.0.0)

**Decisiones finales**:
- Sprint G completo (PocketBase + install_skill_in_tenant) → descartado
- `install_skill_in_tenant()` → obsoleto: con factory defaults, el cliente instala skills desde Telegram directamente (`hermes skills install X` + `/restart`)
- CRM → Sprint I cuando PocketBase alcance v1.0.0 (estimado Q4 2026–Q1 2027)
- Hermes factory defaults es la liberación completa del agente — la plataforma solo gestiona el arranque

### Documentación fundacional

Creados 8 documentos en `docs/hermes-guia/`:
- `00-PARADIGMA-PLATAFORMA.md` — la separación definitiva plataforma vs agente
- `01-CAPACIDADES-COMPLETAS.md` — Hermes v0.14.0: 22 plataformas, 200+ modelos, tools, skills
- `02-CONTEXTO-VENEZOLANO.md` — mercado digital venezolano 2026, WhatsApp 92%, pagos
- `03-MEJORES-PRACTICAS.md` — SOUL.md, modelos, skills, cron, seguridad
- `04-INTEGRACIONES-TOOLS.md` — Airtable, Google Workspace, stocks, Shopify, blockchain
- `05-PITCH-PYME.md` — propuesta de valor para PyMEs venezolanas
- `06-AGENTES-DERIVADOS-MULTIAGENTE.md` — arquitecturas multi-agente, Higgsfield AI
- `07-POCKETBASE-CRM-INVESTIGACION.md` — investigación completa PocketBase (referencia futura Sprint I)
- `08-ARQUITECTURA-POCKETBASE-COMPLETA.md` — diagrama Mermaid, análisis RAM, browser vs HTTP

---



### Infraestructura

- **Metabase v0.61.2.6** — Super Admin dashboard (PR #67)
  - Servicio añadido al compose: expuesto solo en Tailscale (`100.104.89.128:3000`)
  - Conectado a la red `default` del stack → alcanza `db:5432` directamente
  - H2 embebido para metadata interna (un admin personal — suficiente)
  - JAVA_OPTS=-Xmx768m — limita heap JVM para conservar RAM del servidor
  - Compatible con PostgreSQL 18 + pgvector (extensiones transparentes a Metabase)
  - Las tablas de Agno viven en schema `ai` (default de PostgresDb cuando db_schema=None)
  - Las tablas de negocio viven en schema `public` — Metabase debe configurarse para schema `public` únicamente
  - Ref: `agno/db/postgres/db.py` línea 99: `self.db_schema: str = db_schema if db_schema is not None else "ai"`

- **Gitleaks secret scanner en CI** (PR #66)
  - Job `secret-scan` corre ANTES del build check — bloquea si detecta credenciales hardcodeadas
  - `gitleaks-action@v2.3.9` con `fetch-depth: 0` (historial completo)
  - Detecta: bot tokens de Telegram, API keys de OpenRouter, y 100+ formatos de secrets

- **Eliminada red legacy `martes-tenants` del cloud-init** (PR #66)
  - La arquitectura actual usa redes aisladas por tenant (`tenant-tXXX-net`)
  - La red compartida era dead code de un diseño anterior
  - Solo aplica a nuevos servidores (ignoreChanges: userData)

### Meta-agente (Agno AgentOS)

- **Sprint A — Robustez del agente** (PR #57–58)
  - **A3 — Validación Pydantic en tools críticos**:
    - `inject_credential()`: `credential_type` tipado como `Literal[5 valores]` → Agno genera enum en el schema del tool
    - `register_payment()`: `method` como `Literal`, `amount > 0`, `months` entre 1 y 12
    - `create_tenant()`: validación de `bot_token` (regex oficial Telegram) y `telegram_user_id` (numérico)
  - **A1 — Resolución nombre→código**: ambos agentes llaman `get_all_tenants()` antes de operar cuando el admin menciona un tenant por nombre
  - **A2 — EntityMemory wire-up**: `LearningMachine` recibe `db=db` explícito; `create_tenant()` llama `entity_memory_store.create_entity()` al activar el tenant

- **Sprint B — Herramientas de producción** (PR #59)
  - **B0 — Monitoreo automático**: `/maintenance/health-check-all` (cada 5 min) + `/maintenance/billing-check` (9 AM UTC) + `_send_telegram_alert()` centralizado
  - Fix bug en startup handler: early return al encontrar primer schedule existente — corregido para iterar todos
  - **B1 — `get_server_capacity()`**: RAM, disco, RAM asignada a tenants, slots disponibles
  - **B2 — `diagnose_container_error()`**: OOMKill, API key, token, permisos, imagen, crash loop, exit 75 clasificados automáticamente
  - **B3 — `upgrade_tenant()`**: pull nueva imagen → backup → stop → recreate → health check (30s) → rollback automático si falla

- **Sprint C+D — Backups y hardening** (PR #60)
  - **C3 — Lifecycle rules SeaweedFS**: `ensure_bucket_lifecycle()` configura expiración de objetos a 30 días vía `PutBucketLifecycleConfiguration`. Safety net sobre `cleanup_old_backups()`
  - **D2 — Fix SeaweedFS healthcheck**: `curl -sf http://localhost:8888/dir/status` → `curl -sf http://localhost:8333/healthz` (bug de puerto: `/dir/status` está en el master :9333, no el filer :8888). `curl` SÍ está en la imagen

- **Fix health check localhost→127.0.0.1** (PR #61)
  - `container_health()` y `check_all_health()` usaban `localhost` que resuelve a `::1` en Docker con IPv6
  - Hermes `DEFAULT_HOST = "127.0.0.1"` (confirmado en `gateway/platforms/api_server.py`)
  - Eliminaba el falso positivo de "unhealthy" en todos los tenants

- **`recreate_tenant_container()`** (PR #61)
  - Nuevo tool para recrear el container después de `restore_tenant_from_backup()` cuando el container original fue eliminado con `delete_tenant()`
  - Lee recursos de `instance_configs` en DB, verifica volumen y `.env`, salud post-creación

- **Fix restore con caché de uv** (PR #61)
  - `filter="data"` en `extractall()` abortaba el restore al encontrar symlinks absolutos de la caché de uv
  - `_restore_filter()`: usa `tarfile.data_filter` pero captura `FilterError` → omite el symlink, continúa extrayendo
  - `_BACKUP_EXCLUDE_DIRS`: añadidos `.cache` y `archive-v0` para futuros backups

- **`purge_archived_tenant()` + skill COMANDOS** (PR #62)
  - Hard delete de la fila de un tenant archivado en DB (CASCADE elimina instance_configs, payments, health_checks)
  - Primer skill del meta-agente (`src/skills/comandos/SKILL.md`): glosario de todos los tools con parámetros, enums y flujos

- **Sprint D1 — Billing SaaS** (PR #63)
  - `create_tenant()` activa trial de 30 días desde el día 0: `paid_until = hoy + BILLING_TRIAL_DAYS`
  - `/maintenance/billing-check` refactorizado con ciclo completo de 4 estados: recordatorio (7d/3d antes), vence hoy (gracia), auto-suspend tras grace period
  - `stop_tenant()` automático cuando `paid_until + BILLING_GRACE_DAYS < hoy` si `BILLING_AUTO_SUSPEND=True`
  - 4 variables de entorno nuevas configurables en Coolify: `BILLING_TRIAL_DAYS`, `BILLING_GRACE_DAYS`, `BILLING_AUTO_SUSPEND`, `BILLING_ALERT_DAYS`
  - El admin reactiva con `register_payment()` + `restart_tenant()`

- **Sprint F2 — Recursos huérfanos + limpieza Docker** (PR #64)
  - `find_stale_resources()`: detecta tenants con `status='creating'` sin container, redes Docker huérfanas, directorios sin registro en DB
  - `/maintenance/docker-cleanup`: elimina imágenes `nousresearch/hermes-agent` no usadas por ningún container. Solo toca imágenes Hermes — no afecta Coolify, PostgreSQL, SeaweedFS
  - Schedule semanal `docker-cleanup`: domingos 4 AM UTC. Alerta Telegram si liberó espacio

- **Platform key expiry — BYOK bootstrapping** (PR #67, #68)
  - Al crear un tenant, `create_tenant()` escribe `.platform_key_expires` (ISO timestamp de now + TTL)
  - `expire_platform_key()`: detecta en dos niveles si el cliente configuró su propia auth:
    1. `OPENROUTER_API_KEY` en `.env` diferente de la platform key
    2. `auth.json` existe con contenido → cliente autenticó cualquier proveedor en Hermes (incluye Anthropic, Google, etc. — los 20+ del `PROVIDER_REGISTRY`)
  - Patrón BYOK validado contra: Hermes source, guías de producción de bitdoze.com, estándares de Augment Code Enterprise. El modelo "plataforma provisiona key inicial, cliente migra a la suya" es exactamente el estándar de la industria
  - Schedule `expire-platform-keys`: cada 30 minutos. No requiere restart del container — Hermes recarga `.env` en cada turno de conversación
  - `PLATFORM_KEY_TTL_HOURS=0` desactiva la expiración
  - `PLATFORM_KEY_TTL_HOURS=2` default
  - Ref: `hermes/gateway/run.py:_reload_runtime_env_preserving_config_authority()` — "per-turn code reloads ~/.hermes/.env to pick up rotated API keys"

- **Observabilidad — health_checks y error_logs** (PR #68)
  - `container_health()` y `check_all_health()`: INSERT en `health_checks` después de cada check → Metabase tiene historial de uptime, SLA, response_time
  - `diagnose_container_error()`: INSERT en `error_logs` cuando clasifica un error (OOMKill→critical, auth→error, exit_75→info)
  - `run_health_check()`: INSERT en `error_logs` cuando detecta tenants unhealthy (source='system')
  - Helpers: `_get_tenant_db_id()`, `_record_health_check()`, `_record_error_log()` — todos fallo silencioso

### Schedules automáticos (estado actual)

| Schedule | Cron | Qué hace |
|---|---|---|
| `daily-backup-all` | `0 3 * * *` | Backup todos los tenants activos |
| `health-check-all` | `*/5 * * * *` | Health + alerta Telegram si unhealthy o disco >80% |
| `billing-check` | `0 9 * * *` | Ciclo de billing: recordatorios + auto-suspend |
| `expire-platform-keys` | `*/30 * * * *` | Blanquea platform keys expiradas (BYOK) |
| `docker-cleanup` | `0 4 * * 0` | Limpia imágenes Hermes huérfanas |

### Lecciones técnicas nuevas

- **Agno `PostgresDb` usa schema `ai` por defecto** — todas las tablas operacionales de Agno (sessions, memories, traces, knowledge) viven en schema `ai`, no en `public`. Las tablas de negocio de martes.app están en `public`. Separación limpia sin configuración adicional. Metabase debe conectarse solo a schema `public` para ver únicamente datos de negocio
- **Hermes dashboard NO se expone externamente** — el dashboard (puerto 9119) fue investigado para exposición por tenant. Conclusión: demasiado complejo (segundo container por tenant, credenciales efímeras, CORS restrictivo) y demasiado riesgoso (expone API keys y config completa). Descartado
- **`tarfile.FilterError`** es la excepción base para todos los errores de seguridad del filtro en Python 3.12+. Capturarla permite restore robusto sin abortar por symlinks de herramientas de build como uv
- **Hermes `auth.json`** en `/opt/data/auth.json` (= `tenant_path/auth.json` en el host) indica que el cliente autenticó algún proveedor vía el sistema nativo de Hermes. Sirve como señal de "BYOK completado" independiente del proveedor elegido

---

## [Sprint 3] — 23–24 mayo 2026

### Infraestructura

- **Migración a build nativo de Coolify** (PR #44, #45)
  - El meta-agente ya no usa GHCR — Coolify construye la imagen directamente desde el repo
  - Fix crítico: `context: ..` → `context: .` en docker-compose.yml
    (Coolify pasa `--project-directory=<repo-root>`, las rutas relativas se resuelven desde la raíz)
  - Fix `../db/migrations` → `./db/migrations` por la misma causa

- **SeaweedFS 4.28** — Object storage S3-compatible para backups (PR #49)
  - Corre en el mismo stack de Coolify como servicio `seaweedfs`
  - Acceso solo por red Docker interna — no expuesto al host ni a internet
  - Bucket `martes-backups` creado automáticamente
  - Credenciales gestionadas vía env vars de Coolify (`SEAWEEDFS_ACCESS_KEY`, `SEAWEEDFS_SECRET_KEY`)

- **Migración DB 002** — modelo Hermes libre sin tiers (PR #47, aplicada manualmente)
  - `CHECK (plan IN ('basico'))` — un solo plan, constraint actualizado en producción
  - Eliminados registros con valores obsoletos (starter, growth, scale, equipo, pro)

- **SeaweedFS healthcheck** corregido: `/dir/status` → `/cluster/status` (PR #49)

### Meta-agente (Agno AgentOS)

- **Hermes image tag corregido** (PR #46): `0.14.0` → `v2026.5.16`
  - El tag `0.14.0` nunca existió en Docker Hub
  - Hermes usa esquema `vAÑO.MES.DIA` — `v2026.5.16` = Hermes v0.14.0

- **Seguridad `API_SERVER_HOST`** (PR #46): eliminado `API_SERVER_HOST=0.0.0.0`
  - Los health checks usan `docker exec` (localhost) — no necesitan red
  - Hermes docs: `API_SERVER_HOST=0.0.0.0` requiere `API_SERVER_KEY` obligatoriamente

- **curl reemplaza wget** en health checks (PR #48)
  - Hermes `v2026.5.16` no tiene `wget` en la imagen, solo `curl`
  - `container_health()` y `check_all_health()` actualizados

- **DockerTools de Agno eliminados** de Operador y Diagnosticador (PR #48)
  - AgnoDockerTools no filtran por label — veían y podían operar todos los containers del host,
    incluyendo Coolify, coolify-db, coolify-redis, etc.
  - Reemplazados por los tools custom ya filtrados por `martes.tenant`

- **Modelo Hermes libre** — eliminación completa del sistema de tiers (PR #47)
  - Removido parámetro `plan` de `create_tenant()` — hardcodeado a `"basico"` internamente
  - Eliminados templates `basico/`, `equipo/`, `pro/` — código muerto (solo se usa `default/`)
  - `tool_call_limit`: 5 → 10 en Operador (evita agotar budget en un fallo y delegar)
  - Knowledge base reescrita: sin referencias a tiers, flujos correctos documentados

- **Storage layer S3** con boto3 (PR #50)
  - Nuevo módulo `src/storage.py` — cliente boto3 para SeaweedFS
  - `backup_tenant()` → crea tar.gz + sube a SeaweedFS + borra local + cleanup (keep_last=7)
  - `restore_tenant_from_backup()` → descarga de SeaweedFS → extrae → limpia stale → permisos
  - `list_backups()` → lista desde SeaweedFS (fallback a disco local)
  - Añadido `boto3==1.43.14` + `httpx==0.28.1` a pyproject.toml

- **Backup automático diario** — scheduler Agno (PR #50, #52)
  - Endpoint `POST /maintenance/backup-all` — sin LLM, 0 tokens
  - Schedule `daily-backup-all`: cron `0 3 * * *` (3 AM UTC)
  - Startup handler registra el schedule en cada deploy (idempotente)
  - Fix: `agno[telegram,scheduler]` — `agno[telegram]` no incluye `croniter`
  - Fix: startup handler parseaba `resp.json()` como lista cuando en realidad es `{"data": [...]}`

- **Prácticas correctas de backup Hermes** (PR #51)
  - Excluye `gateway.pid`, `cron.pid`, `*.db-wal`, `*.db-shm` del tar.gz
    (Hermes documenta: WAL sidecars junto al .db producen "torn restore")
  - Post-restore: elimina automáticamente archivos estériles + chmod 600 a `.env`/`auth.json`/`state.db`

- **Telegram guardrail** (PR #54)
  - `TelegramAllowlistMiddleware` — capa HTTP dura, independiente del LLM
  - Descarta updates de usuarios no autorizados antes de que Agno los procese
  - Configuración: `TELEGRAM_ADMIN_IDS=<id>` en Coolify
  - Si vacío: sin guardrail (modo dev compatible)

- **delete_tenant() + update_tenant_resources()** (PR #55)
  - `delete_tenant(tenant_code, keep_volume=False)`:
    backup final → stop → remove container → remove network → rmtree volumen → DB archived
  - `update_tenant_resources(tenant_code, memory_mb, cpu_cores)`:
    usa `docker update` (cgroups en caliente, sin restart, efecto inmediato)
    Perfiles: 512/0.5 (ligero), 768/0.75 (estándar), 1024/1.0 (pesado), 2048/2.0 (intensivo)

- **AGENTS.md** actualizado con regla absoluta de no acceso directo al servidor (PR #53)

### Fixes y limpieza de código

- Dead code eliminado: segunda implementación de `create_tenant()` (117 líneas inalcanzables)
- Imports limpiados: `Any`, `approval`, `list_containers` sin usar
- Reorganización de imports en `write_ops.py` (isort)
- `readers=[MarkdownReader()]` → `readers={".md": MarkdownReader()}` (tipo correcto para Agno API)
- CI/CD: `cd.yml` convertido de "Build and Push" a "CI — Build check" (sin push a GHCR)

### Operaciones en producción

- **Primer tenant creado**: `t001` — Acme, Hermes conectado a Telegram, respondió en 11.8s
- **Segundo tenant creado y eliminado**: `t002` — prueba2, ciclo de vida completo verificado
- **Primer backup ejecutado**: `t001_20260524_041520.tar.gz` (10.87 MB) en SeaweedFS
- **Schedule registrado**: `daily-backup-all` en Agno scheduler — próxima ejecución 03:00 UTC
- **Migración SQL aplicada**: `002_single_plan.sql` en DB de producción

---

## [Sprint 2] — May 21–22, 2026

### Meta-agente v1 — Refactoring completo

- **Token-budget model** (PR #38): eliminados tiers basico/equipo/pro
  - Todos los tenants tienen Hermes completo — el límite es el presupuesto de tokens
  - `plan` en DB: solo metadata de billing, no determina capacidades técnicas

- **Patrones Agno correctos**:
  - Telegram Interface nativa de Agno en vez de bot custom
  - `@approval` reemplazado por HITL conversacional (el patrón API no funciona en Telegram)
  - `db=db` pasado al AgentOS para persistencia de sesiones

- **Knowledge base** (PR #40): `upsert=True` para que cambios en .md se reflejen al restart

- **Observability** (PR #41): OpenTelemetry tracing (`opentelemetry-api/sdk`, `openinference-instrumentation-agno`)

- **Routing Traefik** (PR #36): labels en compose para `api.martes.app` + red `coolify`

- **CI/CD** (PR #39): eliminado registry cache que causaba capas stale en GHCR

---

## [Sprint 1] — May 20–21, 2026

### Infraestructura inicial

- Hetzner CX43 desplegado con Pulumi (8 vCPU, 16GB RAM, 160GB NVMe, hel1)
- Coolify instalado via cloud-init
- SSH key ED25519 generada por Pulumi (secret en stack)
- Tailscale instalado — IP: `100.104.89.128`
- Firewall Hetzner: 22, 80, 443, 41641/udp, 6001, 6002
- Delete/rebuild protection activados en el servidor

### Meta-agente v0

- Stack inicial: PostgreSQL + meta-agent + Traefik
- Arquitectura: Diagnosticador + Operador + Team (coordinate mode)
- Telegram interface conectada al Team
- Knowledge base: hermes_reference.md + procedures.md
- Templates Hermes: default/ con config.yaml optimizado
- Schema DB: tenants, instance_configs, payments, health_checks, error_logs

---

## Notas técnicas para futuras implementaciones

### Coolify

- Siempre usa `--project-directory=<repo-root>` cuando el compose está en `infra/`
- Las variables en `${VAR:?}` deben estar marcadas como **buildtime AND runtime** en Coolify UI
- El GitHub App auto-deploy funciona para builds desde Dockerfile (no para imágenes externas)
- Exit code 255 en builds = container de build matado (disk/memory, no error de código)
- El `--no-cache` consume mucho más disco y puede matar el build container — preferir con caché

### Agno

- `agno[telegram,scheduler]` siempre — `agno[telegram]` no incluye `croniter`
- `GET /schedules` devuelve `{"data": [...], "meta": {...}}` — parsear `.get("data", [])`
- `EntityMemoryConfig(mode=LearningMode.AGENTIC, namespace="martes")` ya está configurado
  pero NO se popula automáticamente — requiere llamada explícita en `create_tenant()`
- El Team coordinator en modo HITL: el "sí" del admin puede no llegar al Operador
  si el Team lo redirige al Diagnosticador — ser explícito: "sí, confirmo la creación"
- `PostgresDb` usa schema `"ai"` por defecto (cuando `db_schema=None`) — Agno NO toca schema `public`
  Ref: `agno/db/postgres/db.py` línea 99: `self.db_schema: str = db_schema if db_schema is not None else "ai"`

### Hermes Docker

- Tag Docker Hub: `nousresearch/hermes-agent:vAÑO.MES.DIA` (no semver)
- `v2026.5.16` = Hermes v0.14.0 (último estable mayo 2026)
- No incluye `wget` — usar `curl -sf` en health checks
- `API_SERVER_ENABLED=true` sin `API_SERVER_HOST=0.0.0.0` → API en localhost (correcto)
- `restart: unless-stopped` + exit 75 = restart graceful del cliente vía `/restart`
- Nunca dos gateways sobre el mismo `/opt/data` simultáneamente
- `auth.json` en `/opt/data/auth.json` indica que el cliente autenticó algún proveedor via Hermes
- El dashboard (puerto 9119) NO debe exponerse — no tiene auth propia, expone API keys y config completa
- `PROVIDER_REGISTRY` en `hermes_cli/auth.py` mapea 20+ proveedores a sus env vars. Todos se cargan desde `.env` en cada turno

### SeaweedFS

- Image: `chrislusf/seaweedfs:4.28` (Apache 2.0, activo)
- MinIO community edition archivado en febrero 2026 — no usar
- `weed mini` = single-node todo-en-uno (master + volume + filer + S3)
- Puerto S3: 8333 | Master UI: 9333 | Filer: 8888
- `boto3` con `signature_version="s3v4"` + `region_name="us-east-1"` (ignorado por SeaweedFS)
- Backup NUNCA debe incluir `*.db-wal`, `*.db-shm` — torn restore con SQLite
- `/healthz` en :8333 (S3 API) es el endpoint correcto para healthcheck. `/dir/status` está en :9333 (master)
- `PutBucketLifecycleConfiguration` soportado — Expiration funciona, Transition no

### Docker SDK Python

- `container.update(mem_limit="1g", nano_cpus=int(1.0*1e9))` — cgroups en caliente, sin restart
- `container.remove(force=True)` — elimina aunque esté corriendo (equivalent a `docker rm -f`)
- `restart_policy={"Name": "unless-stopped"}` → `# type: ignore[arg-type]` (docker SDK typing bug)
- `log_config={"Type": "json-file", ...}` → `# type: ignore[arg-type]` (mismo)
- `Container.image` y `Image.id` son `Optional` en los stubs — siempre hacer guard antes de usar
