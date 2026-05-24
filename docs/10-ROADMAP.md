# Roadmap — martes.app

> **Estado a**: 24 mayo 2026  
> **Sistema actual**: Producción corriendo — 2 tenants (t001 active, t002 archived)  
> **Infraestructura**: Hetzner CX43 · Coolify · Agno AgentOS · SeaweedFS · Hermes v2026.5.16

---

## PRs pendientes de merge (inmediato)

Estos están listos — solo falta mergear y Coolify redespliega automáticamente.

| PR | Título | Impacto |
|---|---|---|
| #53 | AGENTS.md — regla absoluta de no acceso directo al servidor | Documentación de seguridad |
| #54 | Telegram guardrail — meta-agente solo responde al admin | **Seguridad crítica** |
| #55 | delete_tenant + update_tenant_resources | Ciclo de vida completo |

**Orden de merge**: #53 → #54 → #55 (son independientes, cualquier orden funciona)

---

## Sprint A — Robustez del agente (próximo)

### A1 · Resolución nombre → código en el Operador
**Problema**: cuando el admin dice "backup de Acme", el agente puede intentar
`backup_tenant("Acme")` en vez de `backup_tenant("t001")`. No hay instrucción
explícita de hacer el lookup primero.

**Fix**: añadir a las instrucciones del Operador y Diagnosticador:
```
Cuando el admin mencione un tenant por nombre (ej: "backup de Acme"):
1. Llama get_all_tenants() para obtener el tenant_code correcto
2. Muestra siempre NOMBRE + código en confirmaciones:
   "Voy a hacer backup de Acme (t001). ¿Confirmas?"
```

**Archivos**: `agents/operador.py`, `agents/diagnosticador.py`

---

### A2 · EntityMemory — perfiles de tenants

**Problema**: el agente no recuerda quién es cada tenant entre sesiones. No tiene
contexto de "Acme Corp lleva 3 meses, paga $30/mes, usa deepseek".

**Solución** (documentada en Agno docs — `EntityMemoryConfig`):
Ya tenemos `entity_memory=EntityMemoryConfig(mode=LearningMode.AGENTIC, namespace="martes")`
en `shared.py`. El agente tiene las herramientas, pero `create_tenant()` no las llama.

**Fix**: después del INSERT en DB en `create_tenant()`, crear automáticamente la entidad:
```python
# Al final de create_tenant() exitoso:
# Llamar create_entity(entity_id=f"{tenant_code}_{slug(name)}", entity_type="company",
#                      name=name, properties={tenant_code, bot_token_masked, ...})
```

Esto permite que cuando el admin diga "quién es t002", el agente lo sepa sin
consultar la DB.

**Ref**: https://docs.agno.com/learning/stores/entity-memory

---

### A3 · Pydantic en tools críticos

**Problema**: el LLM puede pasar tipos incorrectos o valores inválidos.
Ya ocurrió con `plan="starter"` (fallo en producción).

**Tools a actualizar**:
- `create_tenant()` → `TenantInput(BaseModel)` con descripciones por campo
- `inject_credential()` → `credential_type: Literal["google_token","notion_key",...]`
- `register_payment()` → `amount: float`, `method: Literal[...]`

**Impacto**: el LLM recibe un JSON schema con restricciones — no puede pasar valores
arbitrarios donde hay enumerados.

**Archivos**: `tools/write_ops.py`

---

## Sprint B — Herramientas de producción

### B1 · `upgrade_tenant()` — actualizar Hermes sin perder datos

**La única operación de ciclo de vida que falta**. Cuando NousResearch publique
Hermes v2026.6.x, necesitamos actualizarlo tenant a tenant sin perder datos.

**Flujo**:
1. `backup_tenant(tenant_code)` — snapshot antes de upgrade
2. `stop_tenant(tenant_code)` — parar
3. `docker pull nousresearch/hermes-agent:{nueva_version}` — bajar imagen
4. `docker rm hermes-{tenant_code}` — eliminar container viejo
5. Recrear container con nueva imagen (mismos parámetros)
6. `container_health(tenant_code)` — verificar
7. Si falla: `restore_tenant_from_backup()` + recrear con imagen anterior

**Archivos**: `tools/write_ops.py`, `agents/operador.py`, `knowledge/procedures.md`

---

### B2 · `get_server_capacity()` — visibilidad del sistema

**Problema**: no sabemos cuánta RAM queda disponible ni cuántos tenants más caben.

**Tool**:
```python
def get_server_capacity() -> str:
    # docker stats de todos los tenants (uso real)
    # /proc/meminfo (RAM libre en el host)
    # disk usage de /var/lib/martes/
    # Calcular: tenants que caben a 768MB, 512MB
```

**Archivos**: `tools/read_ops.py`, `agents/diagnosticador.py`

---

### B3 · `diagnose_container_error()` — debug automatizado

**Problema**: cuando un container no arranca, el admin tiene que pedir logs manualmente.

**Tool**: recibe `tenant_code`, hace:
1. `docker inspect` → OOMKilled, ExitCode, RestartCount
2. `docker logs --tail=50` → últimas líneas
3. Clasifica el error: imagen no encontrada, permiso denegado, OOM, token inválido, etc.
4. Devuelve causa probable + solución recomendada

**Archivos**: `tools/read_ops.py`, `agents/diagnosticador.py`

---

## Sprint C — Backups y disaster recovery

### C1 · Test completo backup → restore → container funcionando

**Pendiente de ejecutar** (el flujo está implementado, no probado end-to-end):

```
1. backup_tenant("t001")           → backup en SeaweedFS
2. stop_tenant("t001")             → parar
3. Borrar /var/lib/martes/tenants/t001/ manualmente (simular pérdida)
4. restore_tenant_from_backup(     → descarga SeaweedFS → extrae → limpia stale
     "t001", "t001_YYYYMMDD.tar.gz")
5. restart_tenant("t001")          → nuevo container
6. container_health("t001")        → verify healthy
7. Hablarle al bot de t001         → verify responde
```

---

### C2 · Verificar primer backup automático (3 AM UTC)

El schedule `daily-backup-all` está registrado en Agno. Verificar que el próximo día
a las 03:00 UTC se ejecutó correctamente:

```
GET http://100.104.89.128:8000/schedules/{id}/runs
→ status: success, timestamp: 03:00 UTC
```

O preguntarle al meta-agente: `"estado de backups"` → debe mostrar t001 con
`last_backup` de las 3 AM.

---

### C3 · Rotación automática en SeaweedFS (lifecycle rules)

**Ahora mismo**: la rotación es por código en `cleanup_old_backups(keep_last=7)`.

**Mejora**: añadir lifecycle rule en SeaweedFS para eliminar objetos con
más de 30 días automáticamente — capa extra de protección sin depender del código.

---

## Sprint D — Seguridad y hardening

### D1 · `register_payment()` test real

**No probado**. Flujo: admin dice "registra pago de Acme $30 transferencia" →
Operador ejecuta `register_payment("t001", 30, "transferencia", 1)` →
`paid_until` se actualiza en DB.

Verificar que el campo `paid_until` se calcula correctamente.

---

### D2 · SeaweedFS healthcheck — fix cosmético

El container SeaweedFS siempre aparece como "unhealthy" en Docker aunque funcione.
El endpoint `curl -sf http://localhost:9333/cluster/status` devuelve 200 cuando
se ejecuta manualmente, pero el CMD-SHELL del healthcheck falla.

**Investigar**: si `curl` está disponible dentro del container de SeaweedFS
o si el problema es el usuario con el que corre el healthcheck.

---

### D3 · API_SERVER_KEY para tenants que exponen el API

**Actualmente**: el API server de Hermes escucha en `127.0.0.1:8642` (correcto).
Si en el futuro algún tenant necesita exponer el API externamente (para integrar
con Open WebUI u otro cliente), necesitará `API_SERVER_HOST=0.0.0.0` + `API_SERVER_KEY`.

**Plan**: `inject_credential(tenant_code, "api_server_key", openssl_rand_hex_32)`
+ `restart_tenant()`. No urgente hasta que haya necesidad.

---

## Sprint E — Producto / SaaS

### E1 · Primer cliente real (beta)

Una vez que t001 esté probado completamente:
1. Decidir precio y método de pago del primer cliente beta
2. Crear tenant real con nombre, email y bot_token del cliente
3. `register_payment()` con monto y método
4. Cargar wiki inicial con `inject_wiki_content()` si el cliente proporciona info
5. Verificar que el bot responde al cliente

---

### E2 · upgrade_tenant() en producción

Cuando NousResearch publique la siguiente versión estable de Hermes:
1. Implementar `upgrade_tenant()` (Sprint B1)
2. Probar con t001 (backup → upgrade → verify)
3. Si ok, actualizar todos los tenants activos

---

### E3 · Monitoreo y alertas

**Actualmente**: health checks manuales. Falta:
- `check_all_health()` corriendo cada 5 min via Agno scheduler
- Si un tenant está unhealthy > 3 checks seguidos → Telegram al admin
- Alerta si disco > 80% de uso

---

## Capacidad del servidor (referencia)

| Configuración | Tenants |
|---|---|
| 768 MB / 0.75 CPU (estándar) | ~17 máximo |
| Uso real idle (~200 MB) | ~60 caben |
| **Práctica segura** | **20-25 tenants** |

Para escalar más allá de 25 tenants activos: upgrade a CX53 (32GB, €45/mes) o
añadir un segundo servidor para tenants.

---

## Lecciones aprendidas (mayo 2026)

1. **Coolify usa `--project-directory=<repo-root>`** — todas las rutas relativas en
   el compose se resuelven desde la raíz del repo, no desde `infra/`. Usar `context: .`
   no `context: ..` en builds.

2. **Nunca acceder al servidor vía SSH para operaciones de escritura** sin aprobación
   explícita. Los `docker restart` fuera de Coolify desincronizaron su estado interno.

3. **MinIO fue archivado** (feb 2026). SeaweedFS (Apache 2.0, activo) es la alternativa
   de producción para object storage S3-compatible auto-hospedado.

4. **El tag de Hermes es `vAÑO.MES.DIA`** — `0.14.0` es el nombre interno, `v2026.5.16`
   es el tag real en Docker Hub.

5. **`agno[scheduler]`** requiere `croniter` que no incluye `agno[telegram]`. Siempre
   usar `agno[telegram,scheduler]` como extra.

6. **Backup de SQLite**: nunca incluir `*.db-wal`, `*.db-shm` junto al `.db` — produce
   torn restore. Hermes lo documenta explícitamente en su código fuente.

7. **`docker update`** permite cambiar RAM y CPU de un container corriendo sin restart.
   No necesita recreación — modifica cgroups en caliente.

8. **API Agno `/schedules`** devuelve `{"data": [...], "meta": {...}}` no un array plano.
   El startup handler debe parsear `.get("data", [])`.
