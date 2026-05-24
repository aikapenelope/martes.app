# CHANGELOG — martes.app

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
  pero NO se popula automáticamente — requiere llamada explícita en create_tenant()
- El Team coordinator en modo HITL: el "sí" del admin puede no llegar al Operador
  si el Team lo redirige al Diagnosticador — ser explícito: "sí, confirmo la creación"

### Hermes Docker

- Tag Docker Hub: `nousresearch/hermes-agent:vAÑO.MES.DIA` (no semver)
- `v2026.5.16` = Hermes v0.14.0 (último estable mayo 2026)
- No incluye `wget` — usar `curl -sf` en health checks
- `API_SERVER_ENABLED=true` sin `API_SERVER_HOST=0.0.0.0` → API en localhost (correcto)
- `restart: unless-stopped` + exit 75 = restart graceful del cliente vía `/restart`
- Nunca dos gateways sobre el mismo `/opt/data` simultáneamente

### SeaweedFS

- Image: `chrislusf/seaweedfs:4.28` (Apache 2.0, activo)
- MinIO community edition archivado en febrero 2026 — no usar
- `weed mini` = single-node todo-en-uno (master + volume + filer + S3)
- Puerto S3: 8333 | Master UI: 9333 | Filer: 8888
- `boto3` con `signature_version="s3v4"` + `region_name="us-east-1"` (ignorado por SeaweedFS)
- Backup NUNCA debe incluir `*.db-wal`, `*.db-shm` — torn restore con SQLite

### Docker SDK Python

- `container.update(mem_limit="1g", nano_cpus=int(1.0*1e9))` — cgroups en caliente, sin restart
- `container.remove(force=True)` — elimina aunque esté corriendo (equivalent a `docker rm -f`)
- `restart_policy={"Name": "unless-stopped"}` → `# type: ignore[arg-type]` (docker SDK typing bug)
- `log_config={"Type": "json-file", ...}` → `# type: ignore[arg-type]` (mismo)
