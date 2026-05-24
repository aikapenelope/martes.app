# Roadmap — martes.app

> **Estado a**: 27 mayo 2026  
> **Sistema actual**: Producción corriendo — 1 tenant activo (t001), 1 archivado (t002)  
> **Infraestructura**: Hetzner CX43 · Coolify · Agno AgentOS 2.6.8 · SeaweedFS 4.28 · Hermes v2026.5.16  
> **Base de investigación**: Agno 2.6.8 source, SeaweedFS 4.28 source, Hermes v0.14.0 source, Docker SDK 7.x docs

---

## Sprint A — Robustez del agente

### A3 · Pydantic en tools críticos ⚡ PRIMERO — ya hubo fallo en producción

**Problema**: El LLM puede pasar tipos incorrectos. Ya ocurrió con `plan="starter"` en
producción. Con tipos primitivos no hay contrato entre el LLM y el tool.

**Patrón oficial**: Agno convierte automáticamente un `BaseModel` como argumento de tool
a JSON schema con restricciones. Los `Field(description=...)` se propagan al schema que
recibe el LLM — no puede pasar valores fuera del enum.

Ref: https://docs.agno.com/tools/introduction — sección "Pydantic models in tool functions"

**Implementación** (`tools/write_ops.py`):

```python
from pydantic import BaseModel, Field
from typing import Literal

# Reemplaza los parámetros primitivos de create_tenant():
class TenantCreateInput(BaseModel):
    name: str = Field(..., description="Nombre del cliente o empresa. Ej: 'Acme Corp'")
    bot_token: str = Field(..., description="Token del bot Telegram de @BotFather. Formato: 123456:ABC...")
    telegram_user_id: str = Field(..., description="ID numérico de Telegram del cliente. Lo obtiene con @userinfobot")
    model: str = Field(
        default="openai/gpt-4o-mini",
        description="Modelo LLM inicial. Opciones: openai/gpt-4o-mini, deepseek/deepseek-v4-flash, anthropic/claude-3.5-haiku"
    )
    email: str = Field(default="", description="Email de contacto (opcional)")

# Para inject_credential():
class CredentialInput(BaseModel):
    tenant_code: str = Field(..., description="Código del tenant. Ej: t001")
    credential_type: Literal["google_token", "notion_key", "airtable_key", "github_token", "linear_key"] = Field(
        ..., description="Tipo de credencial a inyectar"
    )
    credential_value: str = Field(..., description="Valor de la credencial (secret)")

# Para register_payment():
class PaymentInput(BaseModel):
    tenant_code: str = Field(..., description="Código del tenant. Ej: t001")
    amount: float = Field(..., gt=0, description="Monto en USD. Ej: 30.0")
    method: Literal["transferencia", "stripe", "crypto", "efectivo", "otro"] = Field(
        ..., description="Método de pago"
    )
    months: int = Field(default=1, ge=1, le=12, description="Meses de servicio que cubre el pago")
    reference: str = Field(default="", description="Referencia o número de transacción (opcional)")
```

**Firma de función**: `def create_tenant(input: TenantCreateInput) -> str:`

El cuerpo del tool no cambia — solo se accede via `input.name`, `input.bot_token`, etc.

**Archivos**: `tools/write_ops.py`

**Verificación**: Pide al agente crear un tenant con `plan="starter"` → debe rechazar con
error de validación antes de ejecutar, no en el except del try/catch.

---

### A1 · Resolución nombre→código en Operador y Diagnosticador

**Problema**: El admin dice "backup de Acme" y el agente puede llamar
`backup_tenant("Acme")` en lugar de `backup_tenant("t001")`.

**Fix**: Añadir instrucción explícita en ambos agentes. No es código — es una instrucción
al LLM en el `instructions` list del agente.

**Archivos**: `agents/operador.py`, `agents/diagnosticador.py`

Añadir al bloque de instrucciones de ambos agentes:

```python
"## Resolución de nombre a código de tenant",
"Cuando el admin mencione un tenant por nombre (ej: 'backup de Acme', 'logs de XYZ'):",
"1. Llama get_all_tenants() para obtener la lista completa",
"2. Encuentra el tenant_code que corresponde al nombre mencionado",
"3. Usa SIEMPRE el tenant_code (tXXX) en las herramientas — nunca el nombre",
"4. Confirma con el admin: 'Voy a hacer X a Acme (t001). ¿Confirmas?'",
"Si el nombre no coincide con ningún tenant: muestra la lista y pide aclaración",
```

**Verificación**: Admin dice "¿cuándo fue el último backup de Acme?" → agente debe llamar
`get_all_tenants()` primero, luego `list_backups("t001")`, nunca `list_backups("Acme")`.

---

### A2 · EntityMemory — perfiles de tenants

**Problema**: El agente no recuerda quién es cada tenant entre sesiones. No tiene contexto
de "Acme Corp lleva 3 meses, usa deepseek".

**Root cause**: `EntityMemoryConfig(mode=LearningMode.AGENTIC, namespace="martes")` está
configurado en `shared.py`, pero `LearningMachine._create_entity_memory_store()` requiere
`self.db` (el `PostgresDb`) para inicializar el store. En el código actual `learning` se
crea sin `db` y este lo recibe implícitamente vía los agentes — pero los tools se ejecutan
fuera de ese contexto de inicialización.

Ref: agno==2.6.8 source — `learn/machine.py:_create_entity_memory_store()`:
```python
if config.db is None:
    config.db = self.db   # usa self.db si EntityMemoryConfig.db es None
```

**Fix en dos pasos**:

Paso 1 — en `shared.py`, asociar el `db` al `learning` explícitamente:
```python
learning = LearningMachine(
    model=FAST_MODEL,
    db=db,   # ← añadir este parámetro
    user_memory=UserMemoryConfig(mode=LearningMode.AGENTIC),
    entity_memory=EntityMemoryConfig(mode=LearningMode.AGENTIC, namespace="martes"),
    ...
)
```

Paso 2 — al final de `create_tenant()` exitoso, después de `steps.append("activated")`:
```python
# Registrar en EntityMemory para que el agente recuerde este tenant
from src.shared import learning
try:
    learning.entity_memory_store.create_entity(
        entity_id=tenant_code,
        entity_type="company",
        name=name,
        description=f"Tenant {tenant_code} en martes.app — agente Hermes personal",
        properties={
            "tenant_code": tenant_code,
            "model": model,
            "email": email or "no registrado",
            "hermes_version": settings.hermes_image.split(":")[-1],
        },
        namespace="martes",
    )
    steps.append("entity_memory_created")
except Exception:
    # No-fatal: la memoria falla silenciosamente
    steps.append("entity_memory_skipped")
```

Ref API: agno==2.6.8 source — `learn/stores/entity_memory.py`:
`create_entity(entity_id, entity_type, name, description, properties, namespace) -> bool`

**Archivos**: `shared.py`, `tools/write_ops.py`

**Verificación**: Después de crear un tenant, preguntarle al agente "¿quién es t001?" →
debe responder sin consultar la DB, solo desde EntityMemory.

---

## Sprint B — Visibilidad y alertas operativas

### B0 · Monitoreo automático + alerta Telegram ⚡ MOVIDO ARRIBA — bloquea escalar

**Problema**: Sin alertas automáticas, un container caído a las 3 AM no se detecta hasta
que el cliente se queja. `check_all_health()` existe pero no está schedulado.

**Solución en tres partes**:

**B0.1 — Endpoint de health check global** (`main.py`):

```python
@app.post("/maintenance/health-check-all")
async def run_health_check() -> JSONResponse:
    """Health check de todos los tenants. Sin LLM, 0 tokens.
    Llamado por el scheduler cada 5 minutos.
    """
    from src.tools.read_ops import check_all_health
    import json, httpx

    result = json.loads(check_all_health())
    unhealthy = [t for t in result["tenants"] if t["status"] != "healthy"]

    if unhealthy and settings.telegram_token and settings.telegram_admin_ids:
        tenant_list = ", ".join(f"{t['tenant']}({t['status']})" for t in unhealthy)
        msg = f"⚠️ martes.app — {len(unhealthy)} tenant(s) unhealthy: {tenant_list}"
        for admin_id in settings.telegram_admin_ids.split(","):
            admin_id = admin_id.strip()
            if admin_id:
                try:
                    async with httpx.AsyncClient(timeout=5) as client:
                        await client.post(
                            f"https://api.telegram.org/bot{settings.telegram_token}/sendMessage",
                            json={"chat_id": admin_id, "text": msg},
                        )
                except Exception:
                    pass  # No-fatal: alerta falla silenciosamente

    return JSONResponse(content=result, status_code=200 if not unhealthy else 207)
```

**B0.2 — Registrar schedule cada 5 minutos** (en `register_maintenance_schedules()`):

```python
# Añadir después del schedule de daily-backup-all:
health_schedule_name = "health-check-all"
if health_schedule_name not in existing:
    await client.post("/schedules", json={
        "name": health_schedule_name,
        "cron_expr": "*/5 * * * *",
        "endpoint": "/maintenance/health-check-all",
        "method": "POST",
        "timezone": "UTC",
        "max_retries": 0,   # no reintentar — si falla, el próximo ciclo lo cubre
    })
```

**B0.3 — Alerta de disco** (en el mismo endpoint, añadir):

```python
import shutil
disk = shutil.disk_usage("/var/lib/martes")
disk_pct = round(disk.used / disk.total * 100, 1)
if disk_pct > 80 and settings.telegram_token and settings.telegram_admin_ids:
    msg = f"⚠️ martes.app — Disco al {disk_pct}% ({disk.used // (1<<30)}GB / {disk.total // (1<<30)}GB)"
    # mismo bloque de envío Telegram que arriba
```

Ref Telegram Bot API: https://core.telegram.org/bots/api#sendmessage  
Ref Agno scheduler: https://docs.agno.com/examples/agent-os/scheduler/schedule-management

**Archivos**: `main.py`, `config.py` (verificar que `telegram_token` y `telegram_admin_ids` son accesibles)

**Verificación**: `POST http://100.104.89.128:8000/maintenance/health-check-all` →
debe devolver JSON con tenants. Pausar t001 manualmente → el siguiente ciclo de 5 min
debe llegar un mensaje Telegram al admin.

---

### B1 · `get_server_capacity()` — visibilidad del sistema

**Problema**: No sabemos cuánta RAM queda ni cuántos tenants más caben antes de llegar
al límite del servidor.

**Implementación** (`tools/read_ops.py`):

```python
def get_server_capacity() -> str:
    """Capacidad disponible del servidor: RAM, disco, conteo de tenants.

    Combina docker stats de todos los tenants con /proc/meminfo y df
    para calcular cuántos tenants adicionales caben con el perfil estándar.
    """
    import subprocess

    try:
        # RAM del host via /proc/meminfo
        meminfo = Path("/proc/meminfo").read_text()
        mem_total_kb = int(next(l for l in meminfo.splitlines() if "MemTotal" in l).split()[1])
        mem_avail_kb = int(next(l for l in meminfo.splitlines() if "MemAvailable" in l).split()[1])
        mem_total_mb = mem_total_kb // 1024
        mem_avail_mb = mem_avail_kb // 1024

        # Disco en /var/lib/martes
        disk = shutil.disk_usage("/var/lib/martes")
        disk_free_gb = round(disk.free / (1 << 30), 1)
        disk_total_gb = round(disk.total / (1 << 30), 1)
        disk_pct = round(disk.used / disk.total * 100, 1)

        # Tenants activos y su RAM asignada
        cs = _docker().containers.list(filters={"label": "martes.tenant"})
        tenant_ram_total_mb = sum(
            round(c.attrs.get("HostConfig", {}).get("Memory", 0) / (1 << 20))
            for c in cs
        )

        tenants_running = len([c for c in cs if c.status == "running"])
        tenants_total = len(cs)

        # Tenants adicionales que caben a perfil estándar (768MB)
        slots_standard = mem_avail_mb // 768
        slots_light = mem_avail_mb // 512

        return json.dumps({
            "server": {
                "ram_total_mb": mem_total_mb,
                "ram_available_mb": mem_avail_mb,
                "ram_used_by_tenants_mb": tenant_ram_total_mb,
            },
            "disk": {
                "total_gb": disk_total_gb,
                "free_gb": disk_free_gb,
                "used_pct": disk_pct,
            },
            "tenants": {
                "running": tenants_running,
                "total": tenants_total,
            },
            "capacity": {
                "additional_slots_768mb": slots_standard,
                "additional_slots_512mb": slots_light,
                "recommendation": (
                    f"Caben ~{slots_standard} tenants más al perfil estándar (768MB). "
                    f"Considera upgrade a CX53 si superas 20 tenants activos."
                ),
            },
        })
    except Exception as e:
        return json.dumps({"error": str(e)})
```

Añadir `import shutil` a los imports existentes.

**Archivos**: `tools/read_ops.py` (función), `agents/diagnosticador.py` (añadir al tools list)

**Verificación**: El Diagnosticador responde "¿cuántos tenants más caben?" con números
reales: RAM disponible, slots, %.

---

### B2 · `diagnose_container_error()` — debug automatizado

**Problema**: Cuando un container no arranca, el admin tiene que pedir logs manualmente
y correlacionar el error a mano.

**Implementación** (`tools/read_ops.py`):

```python
def diagnose_container_error(tenant_code: str) -> str:
    """Diagnóstico automatizado de un container que no arranca o está unhealthy.

    Combina docker inspect + tail de logs para clasificar el error sin
    necesidad de que el admin pida cada pieza por separado.
    """
    try:
        c = _docker().containers.get(f"hermes-{tenant_code}")
        attrs = c.attrs

        # Datos de inspect
        state = attrs.get("State", {})
        host_cfg = attrs.get("HostConfig", {})
        exit_code = state.get("ExitCode", 0)
        oom_killed = state.get("OOMKilled", False)
        restart_count = attrs.get("RestartCount", 0)
        status = state.get("Status", "unknown")
        error = state.get("Error", "")

        # Últimas 50 líneas de logs
        raw: bytes = c.logs(tail=50, timestamps=False)  # type: ignore[assignment]
        log_tail = raw.decode("utf-8", errors="replace")

        # Clasificación del error
        cause = "desconocido"
        solution = "Revisa los logs para más detalle"

        if oom_killed:
            mem_limit_mb = round(host_cfg.get("Memory", 0) / (1 << 20))
            cause = f"OOM Kill — el container superó el límite de {mem_limit_mb}MB de RAM"
            solution = "Usa update_tenant_resources() para subir la RAM. Perfil recomendado: 1024MB/1.0CPU"
        elif exit_code == 1 and "OPENROUTER_API_KEY" in log_tail:
            cause = "API key de OpenRouter inválida o expirada"
            solution = "Revisa que OPENROUTER_API_KEY en el .env del tenant es válida y tiene créditos"
        elif exit_code == 1 and "TELEGRAM_BOT_TOKEN" in log_tail:
            cause = "Token de Telegram inválido"
            solution = "Verifica el bot_token con @BotFather. Usa inject_credential() para actualizarlo"
        elif "permission denied" in log_tail.lower():
            cause = "Error de permisos en el volumen"
            solution = "El directorio /var/lib/martes/tenants/{tenant_code} necesita chown 1000:1000"
        elif "image" in error.lower() and "not found" in error.lower():
            cause = f"Imagen Docker no encontrada: {attrs.get('Config', {}).get('Image', '?')}"
            solution = "Ejecuta docker pull <imagen> en el servidor. Verifica HERMES_IMAGE en la configuración"
        elif restart_count > 3:
            cause = f"Crash loop — el container ha reiniciado {restart_count} veces"
            solution = "Revisa los logs detalladamente. Posiblemente un error de configuración en .env o config.yaml"

        return json.dumps({
            "tenant": tenant_code,
            "status": status,
            "exit_code": exit_code,
            "oom_killed": oom_killed,
            "restart_count": restart_count,
            "probable_cause": cause,
            "suggested_solution": solution,
            "log_tail": log_tail[-1000:],   # últimos 1000 chars de logs
        })
    except NotFound:
        return json.dumps({"tenant": tenant_code, "error": "Container no encontrado"})
    except APIError as e:
        return json.dumps({"error": str(e)})
```

**Archivos**: `tools/read_ops.py` (función), `agents/diagnosticador.py` (añadir al tools list)

**Verificación**: Detener un container con `docker stop hermes-t001` desde fuera (o esperar
un crash), luego preguntar al Diagnosticador "¿qué le pasa a t001?" → debe devolver causa
clasificada + solución, sin pasos manuales adicionales.

---

### B3 · `upgrade_tenant()` — actualizar Hermes sin perder datos

**La única operación de ciclo de vida pendiente.** Cuando NousResearch publique
Hermes v2026.6.x, necesitamos actualizar tenant a tenant sin perder datos.

**Flujo con rollback** (`tools/write_ops.py`):

```python
def upgrade_tenant(tenant_code: str, new_image: str) -> str:
    """Actualiza la imagen Hermes de un tenant con backup previo y rollback automático.

    Flujo:
    1. backup_tenant() — snapshot antes del upgrade
    2. Detener el container
    3. Eliminar el container (pero NO el volumen)
    4. Crear container nuevo con la misma config pero nueva imagen
    5. container_health() — verificar que arrancó
    6. Si falla: recrear container con imagen anterior (rollback automático)

    Requiere aprobación. No mezclar con upgrade masivo sin probar en t001 primero.
    Ref: https://docker-py.readthedocs.io/en/stable/containers.html#docker.models.containers.Container.remove
    """
    from src.tools.read_ops import container_health

    steps: list[str] = []
    old_image: str = ""
    c_client = _docker()

    try:
        # Capturar config actual del container antes de cualquier cambio
        try:
            old_container = c_client.containers.get(f"hermes-{tenant_code}")
            old_cfg = old_container.attrs
            old_image = old_cfg.get("Config", {}).get("Image", settings.hermes_image)
            host_cfg = old_cfg.get("HostConfig", {})
            old_mem = host_cfg.get("Memory", 768 * (1 << 20))
            old_nano_cpus = host_cfg.get("NanoCpus", int(0.75 * 1e9))
        except NotFound:
            return json.dumps({"error": f"Container hermes-{tenant_code} no encontrado."})

        if old_image == new_image:
            return json.dumps({"error": f"El tenant ya usa la imagen {new_image}. No hay upgrade."})

        # 1. Backup previo (obligatorio antes de cualquier cambio)
        backup_result = json.loads(backup_tenant(tenant_code))
        if not backup_result.get("success"):
            return json.dumps({
                "success": False,
                "error": f"Backup previo falló: {backup_result.get('error')}. Upgrade cancelado."
            })
        steps.append(f"backup_ok:{backup_result.get('backup_file')}")

        # 2. Detener y eliminar el container (el volumen se preserva)
        if old_container.status == "running":
            old_container.stop(timeout=30)
            steps.append("container_stopped")
        old_container.remove(force=True)
        steps.append("container_removed")

        # 3. Crear container nuevo con nueva imagen, misma config
        tenant_path = Path(settings.tenants_base_path) / tenant_code
        net = f"tenant-{tenant_code}-net"
        try:
            c_client.networks.get(net)
        except NotFound:
            c_client.networks.create(net, driver="bridge")

        with psycopg.connect(_pg()) as conn:
            row = conn.execute(
                "SELECT ic.memory_limit_mb, ic.cpu_limit FROM instance_configs ic "
                "JOIN tenants t ON t.id = ic.tenant_id WHERE t.tenant_code = %s",
                (tenant_code,)
            ).fetchone()
            mem_mb = row[0] if row else 768
            cpu = row[1] if row else 0.75

        c_client.containers.run(
            image=new_image,
            name=f"hermes-{tenant_code}",
            detach=True,
            restart_policy={"Name": "unless-stopped"},  # type: ignore[arg-type]
            network=net,
            volumes={str(tenant_path): {"bind": "/opt/data", "mode": "rw"}},
            environment={"HERMES_UID": "1000", "HERMES_GID": "1000", "API_SERVER_ENABLED": "true"},
            mem_limit=f"{mem_mb}m",
            memswap_limit=f"{mem_mb * 2}m",
            nano_cpus=int(cpu * 1e9),
            command=["gateway", "run"],
            security_opt=["no-new-privileges"],
            pids_limit=256,
            cap_drop=["ALL"],
            cap_add=["NET_RAW", "CHOWN", "SETUID", "SETGID", "DAC_OVERRIDE", "FOWNER"],
            dns=["1.1.1.1", "8.8.8.8"],
            tmpfs={"/tmp": "size=100m"},
            log_config={"Type": "json-file", "Config": {"max-size": "50m", "max-file": "3"}},  # type: ignore[arg-type]
            labels={"martes.tenant": tenant_code, "martes.plan": "basico"},
        )
        steps.append(f"container_created_with_{new_image}")

        # 4. Verificar health (esperar hasta 30s)
        import time
        for attempt in range(6):
            time.sleep(5)
            health = json.loads(container_health(tenant_code))
            if health.get("status") == "healthy":
                steps.append("health_ok")
                # Actualizar imagen en DB
                with psycopg.connect(_pg()) as conn:
                    conn.execute(
                        "UPDATE instance_configs ic SET template = %s "
                        "FROM tenants t WHERE t.id = ic.tenant_id AND t.tenant_code = %s",
                        (new_image, tenant_code)
                    )
                    conn.commit()
                return json.dumps({
                    "success": True, "tenant": tenant_code,
                    "old_image": old_image, "new_image": new_image,
                    "steps": steps,
                    "message": f"Upgrade de {old_image} → {new_image} completado. Tenant healthy.",
                })
        # 5. Rollback automático si no arranca en 30s
        steps.append("health_check_failed_rolling_back")
        try:
            c_client.containers.get(f"hermes-{tenant_code}").remove(force=True)
        except NotFound:
            pass
        c_client.containers.run(
            image=old_image,
            name=f"hermes-{tenant_code}",
            detach=True,
            restart_policy={"Name": "unless-stopped"},  # type: ignore[arg-type]
            network=net,
            volumes={str(tenant_path): {"bind": "/opt/data", "mode": "rw"}},
            environment={"HERMES_UID": "1000", "HERMES_GID": "1000", "API_SERVER_ENABLED": "true"},
            mem_limit=f"{mem_mb}m",
            memswap_limit=f"{mem_mb * 2}m",
            nano_cpus=int(cpu * 1e9),
            command=["gateway", "run"],
            security_opt=["no-new-privileges"],
            pids_limit=256,
            cap_drop=["ALL"],
            cap_add=["NET_RAW", "CHOWN", "SETUID", "SETGID", "DAC_OVERRIDE", "FOWNER"],
            dns=["1.1.1.1", "8.8.8.8"],
            tmpfs={"/tmp": "size=100m"},
            log_config={"Type": "json-file", "Config": {"max-size": "50m", "max-file": "3"}},  # type: ignore[arg-type]
            labels={"martes.tenant": tenant_code, "martes.plan": "basico"},
        )
        steps.append(f"rolled_back_to_{old_image}")
        return json.dumps({
            "success": False, "tenant": tenant_code,
            "error": f"El container con {new_image} no pasó health check en 30s. Rollback a {old_image} ejecutado.",
            "steps": steps,
        })

    except Exception as e:
        return json.dumps({"success": False, "error": str(e), "steps_completed": steps})
```

**Archivos**: `tools/write_ops.py`, `agents/operador.py` (añadir al tools list),
`knowledge/procedures.md` (documentar procedimiento de upgrade masivo)

**Procedimiento para upgrade masivo** (cuando hay múltiples tenants activos):
1. Probar `upgrade_tenant("t001", "nousresearch/hermes-agent:vNUEVO")` primero
2. Si ok: upgradar los demás de uno en uno
3. Si rollback: investigar el motivo antes de continuar

**Verificación**: `upgrade_tenant("t001", "nousresearch/hermes-agent:v2026.5.16")` →
mismo tag, debe detectar "ya usa esta imagen" y cancelar. Con un tag diferente:
backup → remove → create → health → ok.

---

## Sprint C — Backups y disaster recovery

> ⚠️ **C1 es bloqueante para E1** (primer cliente real). No se onboardea un cliente
> de pago sin haber probado el restore end-to-end al menos una vez.

### C1 · Test completo backup → restore → container funcionando

El flujo está implementado. Nunca se ha probado end-to-end. Ejecutar ANTES del primer
cliente real:

```
1. backup_tenant("t001")
   → Verificar: backup_file en SeaweedFS, size_mb > 0

2. stop_tenant("t001")
   → Verificar: container status = stopped

3. Borrar /var/lib/martes/tenants/t001/ manualmente (simular pérdida de datos)
   → Verificar: directorio ya no existe

4. restore_tenant_from_backup("t001", "t001_YYYYMMDD_HHMMSS.tar.gz")
   → Verificar: success=True, cleaned_stale listado

5. restart_tenant("t001")
   → Verificar: container status = running

6. container_health("t001")
   → Verificar: status=healthy, response_ms < 5000

7. Enviarle un mensaje al bot de t001 en Telegram
   → Verificar: responde correctamente, memoria intacta
```

**Si algún paso falla**: documentar el fallo exacto y corregir el código antes de
continuar con los sprints de producto.

---

### C2 · Verificar primer backup automático (3 AM UTC)

El schedule `daily-backup-all` está registrado. Verificar que se ejecutó:

```
# Via Agno scheduler API (desde el servidor via Tailscale):
GET http://100.104.89.128:8000/schedules
→ Encontrar el ID del schedule "daily-backup-all"

GET http://100.104.89.128:8000/schedules/{id}/runs
→ Verificar: status: "success", triggered_at: 03:00 UTC
```

O preguntarle al meta-agente: `"estado de backups"` → debe mostrar t001 con
`last_backup` de las 03:00 UTC y `hours_since_backup` < 26.

Ref: https://docs.agno.com/examples/agent-os/scheduler/schedule-management  
(endpoint `GET /schedules/{id}/runs` — campos: `attempt`, `status`, `triggered_at`)

---

### C3 · Lifecycle rules en SeaweedFS (30 días de retención)

**Ahora mismo**: la rotación es solo por código en `cleanup_old_backups(keep_last=7)`.
Si el código falla silenciosamente, los backups se acumulan indefinidamente.

**SeaweedFS sí soporta `PutBucketLifecycleConfiguration`** — confirmado en el
código fuente y en la wiki oficial.

Ref: https://github.com/seaweedfs/seaweedfs/wiki/Amazon-S3-API (sección Lifecycle)  
Ref: `seaweedfs/weed/s3api/s3api_bucket_lifecycle_config.go`

**Implementación** — añadir a `storage.py` como función de setup llamada una sola vez:

```python
def ensure_bucket_lifecycle(client: boto3.client, bucket: str, days: int = 30) -> bool:
    """Configura lifecycle rule en SeaweedFS para expirar objetos > N días.

    Idempotente — si la rule ya existe con los mismos días, no hace nada.
    Expiration days = capa de seguridad extra; cleanup_old_backups() sigue siendo
    la línea primaria (keep_last=7).

    Ref: https://github.com/seaweedfs/seaweedfs/wiki/Amazon-S3-API
    boto3 PutBucketLifecycleConfiguration:
    https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/put_bucket_lifecycle_configuration.html
    """
    try:
        client.put_bucket_lifecycle_configuration(
            Bucket=bucket,
            LifecycleConfiguration={
                "Rules": [{
                    "ID": "expire-old-backups",
                    "Status": "Enabled",
                    "Filter": {"Prefix": "tenants/"},
                    "Expiration": {"Days": days},
                }]
            },
        )
        return True
    except Exception:
        return False
```

Llamar una vez en el startup del `StorageClient` (en `storage.py:__init__` o en el
primer `storage_available()` exitoso).

---

## Sprint D — Seguridad y hardening

### D2 · SeaweedFS healthcheck — root cause encontrado ✅

**El bug**: el compose usa `curl -sf http://localhost:8888/dir/status`, pero el endpoint
`/dir/status` está registrado en el **master server** (puerto 9333), no en el filer
(puerto 8888).

Evidencia del código fuente de SeaweedFS 4.28:
```go
// weed/server/master_server.go — línea 200+:
r.HandleFunc("/dir/status", ms.proxyToLeader(...))  // Puerto 9333 (master)
// El filer en puerto 8888 NO tiene /dir/status
```

`curl` SÍ está disponible en el container — confirmado en el Dockerfile:
```dockerfile
# docker/Dockerfile.go_build — stage final:
RUN apk add --no-cache fuse curl su-exec libgcc libcrypto3 libssl3
```

**Fix recomendado** — usar el endpoint S3 `/healthz` (puerto 8333) porque es lo que
usamos en producción y está documentado en el código fuente:
```go
// weed/s3api/s3api_server.go:
apiRouter.Methods(http.MethodGet, http.MethodHead).Path("/healthz").HandlerFunc(s3a.StatusHandler)
```

**Cambio en `infra/docker-compose.yml`**:
```yaml
# ANTES (incorrecto — /dir/status está en :9333, no en :8888):
healthcheck:
  test: ["CMD-SHELL", "curl -sf http://localhost:8888/dir/status || exit 1"]

# DESPUÉS (correcto — /healthz en el S3 API port):
healthcheck:
  test: ["CMD-SHELL", "curl -sf http://localhost:8333/healthz || exit 1"]
```

**Archivos**: `infra/docker-compose.yml`

**Verificación**: Después del deploy, `docker inspect <seaweedfs-container> | jq '.[].State.Health'`
→ `Status: "healthy"`.

---

### D1 · `register_payment()` test real

**No probado**. Flujo completo:

```
1. Admin: "registra pago de Acme (t001) $30 transferencia"
2. Operador muestra parámetros y pide confirmación
3. Admin confirma
4. register_payment("t001", 30.0, "transferencia", 1)
5. Verificar en DB:
   SELECT paid_until, status FROM tenants WHERE tenant_code = 't001'
   → paid_until debe ser today + 30 days, status = 'active'
6. Verificar en tabla payments:
   SELECT * FROM payments WHERE tenant_id = (SELECT id FROM tenants WHERE tenant_code='t001')
   → registro con amount=30, method='transferencia', period_start y period_end correctos
```

Con A3 (Pydantic) implementado, también verificar que el agente rechaza:
- `amount = 0` → error de validación (gt=0)
- `method = "paypal"` → error de validación (Literal constraint)

---

### D3 · API_SERVER_KEY para tenants externos

**Actualmente**: API server en `127.0.0.1:8642` (correcto).  
**Futuro**: Si algún tenant necesita exponer el API externamente para Open WebUI u otro
cliente compatible con OpenAI API.

**Plan cuando sea necesario**:
```python
# 1. Generar key segura:
import secrets
api_key = secrets.token_hex(32)   # 64 chars hex

# 2. Inyectar en el tenant:
inject_credential(tenant_code, "api_server_key", api_key)
# Esto escribe API_SERVER_KEY en .env

# 3. Añadir API_SERVER_HOST en .env:
inject_credential(tenant_code, "api_server_host", "0.0.0.0")
# (extend inject_credential() para soportar "api_server_host" y "api_server_key")

# 4. Reiniciar:
restart_tenant(tenant_code)
```

Ref: https://hermes-agent.nousresearch.com/docs/user-guide/docker — sección API Server  
"API_SERVER_HOST=0.0.0.0 requires API_SERVER_KEY — both or neither"

**No urgente** hasta que haya un cliente que lo pida explícitamente.

---

## Sprint E — Producto / SaaS

### E1 · Primer cliente real (beta) — requiere C1 completado

Pre-requisitos antes de onboardear el primer cliente de pago:
1. ✅ C1 — test backup→restore completado sin errores
2. ✅ B0 — alertas automáticas activas (saber si el bot del cliente cae)
3. ✅ A3 — Pydantic en create_tenant (no más errores de tipo en el onboarding)

Flujo de onboarding:
```
1. Crear tenant:
   create_tenant(TenantCreateInput(
       name="NombreCliente",
       bot_token="TOKEN_DE_BOTFATHER",
       telegram_user_id="TELEGRAM_ID_CLIENTE",
       model="openai/gpt-4o-mini",
   ))

2. Verificar health:
   container_health("tXXX") → healthy

3. Registrar pago:
   register_payment("tXXX", 30.0, "transferencia", 1)

4. Opcional — cargar wiki inicial:
   inject_wiki_content("tXXX", "NombreEmpresa", "Descripción del negocio")

5. Verificar que el cliente puede hablar con su bot en Telegram
```

---

### E2 · upgrade_tenant() en producción

Cuando NousResearch publique la siguiente versión estable de Hermes:

1. Revisar release notes para breaking changes en `config.yaml` o `.env`
2. Probar `upgrade_tenant("t001", "nousresearch/hermes-agent:vNUEVO")` primero
3. Verificar que t001 sigue funcionando (health + mensaje de prueba en Telegram)
4. Si ok: upgradar el resto de tenants activos uno a uno
5. Si falla: el rollback automático de `upgrade_tenant()` restaura la imagen anterior

**Depende de**: B3 (`upgrade_tenant()` implementado)

---

### E3 · Monitoreo avanzado

**Movido a B0** (prioritario). Las funcionalidades básicas de alerta están en B0.

Extensiones futuras post B0:
- Alerta si `paid_until` de algún tenant cae en los próximos 3 días → ver F1
- Dashboard de métricas en Coolify (B1 + check_all_health ya dan los datos)
- Gráfico de uso de RAM por tenant a lo largo del tiempo (requiere persistir stats en DB)

---

## Sprint F — Gaps operativos

*Descubiertos en auditoría del sistema mayo 2026. No bloquean los sprints anteriores
pero son importantes para operar con más de 5 tenants activos.*

---

### F1 · Alertas de `paid_until` próximo a vencer

**Problema**: Si el admin está ocupado una semana, un tenant puede seguir activo con el
bot respondiendo sin ningún pago registrado. Sin alerta proactiva, esto pasa desapercibido.

**Implementación** — añadir al endpoint `/maintenance/health-check-all` (o crear uno
separado `/maintenance/billing-check`):

```python
@app.post("/maintenance/billing-check")
async def run_billing_check() -> JSONResponse:
    """Verifica paid_until de todos los tenants. Alerta si vence en <= 5 días."""
    from src.tools.read_ops import get_all_tenants
    from datetime import date

    tenants_data = json.loads(get_all_tenants())
    expiring_soon = []
    today = date.today()

    for t in tenants_data.get("tenants", []):
        if t["status"] != "active":
            continue
        days_remaining = t.get("days_remaining")
        if days_remaining is not None and days_remaining <= 5:
            expiring_soon.append({
                "tenant": t["code"],
                "name": t["name"],
                "days_remaining": days_remaining,
            })

    if expiring_soon and settings.telegram_token and settings.telegram_admin_ids:
        lines = [f"- {t['name']} ({t['tenant']}): {t['days_remaining']} días" for t in expiring_soon]
        msg = "💳 martes.app — Pagos próximos a vencer:\n" + "\n".join(lines)
        # mismo bloque de envío Telegram que B0

    return JSONResponse(content={"expiring_soon": expiring_soon}, status_code=200)
```

**Schedule**: cron `0 9 * * *` (9 AM UTC diario, cuando el admin está disponible).

**Archivos**: `main.py`, `register_maintenance_schedules()` en startup handler

---

### F2 · `cleanup_stale_resources()` — limpieza de recursos huérfanos

**Problema**: Si `create_tenant()` falla a mitad de ejecución puede quedar:
- Un registro en DB con `status='creating'` que nunca se activó
- Una red Docker `tenant-tXXX-net` sin container
- Un directorio parcial en `/var/lib/martes/tenants/tXXX/`

Con 1-2 tenants esto es manejable. Con 10+ puede confundir al agente.

**Implementación** (`tools/read_ops.py`):

```python
def find_stale_resources() -> str:
    """Detecta recursos huérfanos: DB records 'creating', redes sin container, directorios sin DB.

    Solo detecta — no borra. Reporta para que el admin decida.
    """
    stale = {"db_creating": [], "orphan_networks": [], "orphan_dirs": []}

    # 1. Tenants con status='creating' (fallo en create_tenant a mitad)
    with psycopg.connect(_pg()) as conn:
        rows = conn.execute(
            "SELECT tenant_code, name, created_at FROM tenants WHERE status = 'creating'"
        ).fetchall()
        stale["db_creating"] = [{"code": r[0], "name": r[1], "created_at": str(r[2])} for r in rows]

    # 2. Redes Docker tenant-tXXX-net sin container asociado
    nets = _docker().networks.list(filters={"name": "tenant-"})
    container_names = {c.name for c in _docker().containers.list(all=True)}
    for net in nets:
        tenant_code = net.name.replace("tenant-", "").replace("-net", "")
        if f"hermes-{tenant_code}" not in container_names:
            stale["orphan_networks"].append({"network": net.name, "tenant_code": tenant_code})

    # 3. Directorios en tenants/ sin registro en DB
    tenants_dir = Path(settings.tenants_base_path)
    if tenants_dir.exists():
        with psycopg.connect(_pg()) as conn:
            known = {r[0] for r in conn.execute("SELECT tenant_code FROM tenants").fetchall()}
        for d in tenants_dir.iterdir():
            if d.is_dir() and d.name not in known:
                size_mb = round(sum(f.stat().st_size for f in d.rglob("*") if f.is_file()) / (1 << 20), 1)
                stale["orphan_dirs"].append({"dir": d.name, "size_mb": size_mb})

    total = sum(len(v) for v in stale.values())
    return json.dumps({
        "total_stale": total,
        "stale": stale,
        "message": (
            f"Se encontraron {total} recursos huérfanos. "
            "Revisa cada uno antes de borrar. Para borrar: borra manualmente via Operador."
        ) if total else "Sin recursos huérfanos detectados.",
    })
```

**Archivos**: `tools/read_ops.py`, `agents/diagnosticador.py` (añadir al tools list)

---

### F3 · `rotate_api_key_all_tenants()` — rotación de OpenRouter key

**Problema**: La `OPENROUTER_API_KEY` se escribe en el `.env` de cada tenant al crear.
Si hay que rotarla (compromiso de seguridad, expiración), hay que actualizar todos los
tenants. Actualmente no hay tool para esto.

**Implementación** (`tools/write_ops.py`):

```python
def rotate_api_key_all_tenants(new_api_key: str, dry_run: bool = True) -> str:
    """Actualiza OPENROUTER_API_KEY en el .env de todos los tenants activos.

    dry_run=True (default): solo lista qué tenants se verían afectados, sin modificar.
    dry_run=False: actualiza los .env. Requiere restart_tenant() después para que Hermes
    cargue la nueva key.

    Requiere aprobación explícita — operación en batch sobre todos los tenants.
    Ref: Hermes carga .env en cada arranque del gateway.
    """
    tenants_dir = Path(settings.tenants_base_path)
    if not tenants_dir.exists():
        return json.dumps({"error": "tenants directory not found"})

    affected = []
    errors = []
    for tenant_path in sorted(tenants_dir.iterdir()):
        if not tenant_path.is_dir():
            continue
        env_file = tenant_path / ".env"
        if not env_file.exists():
            continue
        content = env_file.read_text()
        if "OPENROUTER_API_KEY=" in content:
            if not dry_run:
                lines = content.splitlines()
                new_lines = [
                    f"OPENROUTER_API_KEY={new_api_key}" if l.startswith("OPENROUTER_API_KEY=") else l
                    for l in lines
                ]
                try:
                    env_file.write_text("\n".join(new_lines) + "\n")
                    os.chmod(env_file, 0o600)
                    affected.append(tenant_path.name)
                except OSError as e:
                    errors.append({"tenant": tenant_path.name, "error": str(e)})
            else:
                affected.append(tenant_path.name)

    return json.dumps({
        "dry_run": dry_run,
        "tenants_affected": affected,
        "count": len(affected),
        "errors": errors,
        "next_step": (
            "Para aplicar: llama rotate_api_key_all_tenants(new_key, dry_run=False)"
            if dry_run else
            "Key actualizada. Haz restart_tenant() a cada tenant para que Hermes cargue la nueva key."
        ),
    })
```

**Archivos**: `tools/write_ops.py`, `agents/operador.py` (añadir al tools list con
instrucción de HITL obligatorio)

---

### F4 · Secret scanner en CI

**Problema**: El workflow de CI solo hace build check. Si alguien sube accidentalmente
un bot_token de Telegram, una OPENROUTER_API_KEY o un bot token en código, no hay
detección automática.

**Fix** — añadir `gitleaks` como step en `.github/workflows/cd.yml`:

```yaml
- name: Scan for secrets (gitleaks)
  uses: gitleaks/gitleaks-action@v2.3.9
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
  # Falla el build si encuentra secretos — antes de que llegue a Coolify
```

Ref: https://github.com/gitleaks/gitleaks-action  
Patrón confirmado: detects Telegram bot tokens (`\d{10}:[A-Za-z0-9_-]{35}`),
API keys con formato OpenRouter, etc.

**Archivo**: `.github/workflows/cd.yml`

**Consideración**: añadir `.gitleaks.toml` en raíz para allowlist de strings en tests
o docs que parezcan secrets pero no lo son.

---

### F5 · Red `martes-tenants` en cloud-init — verificar o eliminar

**El cloud-init crea** `docker network create martes-tenants || true`, pero ningún
servicio en el compose ni en el código usa esa red. Cada tenant tiene su propia red
`tenant-tXXX-net` creada por `create_tenant()`.

**Acción**: verificar en el servidor si la red existe y si tiene containers conectados:

```bash
docker network inspect martes-tenants 2>/dev/null | jq '.[].Containers'
```

Si está vacía: es un artefacto legacy. Remover del cloud-init en `pulumi/index.ts`
para no crear confusión en servidores futuros. La red existente en el servidor actual
no molesta.

**Nota**: el cloud-init tiene `ignoreChanges: ["userData"]` — este cambio solo afecta
a servidores creados con `pulumi up` en el futuro.

**Archivo**: `pulumi/index.ts`

---

## Capacidad del servidor (referencia)

| Configuración | Tenants |
|---|---|
| 768 MB / 0.75 CPU (estándar) | ~17 máximo (RAM teórica) |
| Uso real idle (~200 MB) | ~60 caben (no realista en práctica) |
| **Práctica segura** | **20–25 tenants** |

Para escalar más allá de 25 tenants activos: upgrade a CX53 (32GB, €45/mes) o añadir
un segundo servidor para tenants.

Con B1 (`get_server_capacity()`) implementado, el agente puede darte este cálculo en
tiempo real con los valores actuales del servidor.

---

## Lecciones aprendidas (actualizado mayo 2026)

1. **Coolify usa `--project-directory=<repo-root>`** — todas las rutas relativas en el
   compose se resuelven desde la raíz del repo, no desde `infra/`. Usar `context: .`
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

9. **SeaweedFS healthcheck: el bug es el puerto, no curl.** `curl` sí está instalado
   en `chrislusf/seaweedfs:4.28` (confirmado en Dockerfile). El problema era usar
   `:8888/dir/status` (filer) en lugar de `:8333/healthz` (S3 API) o `:9333/dir/status`
   (master). Ref: `seaweedfs/weed/s3api/s3api_server.go` y `master_server.go`.

10. **Agno EntityMemory requiere `db` en LearningMachine.** El `LearningMachine` debe
    crearse con `db=db` explícito en `shared.py` para que `entity_memory_store.create_entity()`
    funcione desde tools fuera del contexto de un agente.
    Ref: agno==2.6.8 `learn/machine.py:_create_entity_memory_store()`.

11. **Pydantic en tools de Agno es automático.** Un argumento tipado como `BaseModel`
    se convierte automáticamente al JSON schema del tool — los `Field(description=...)`
    llegan al LLM como restricciones en la definición del tool.
    Ref: https://docs.agno.com/tools/introduction

12. **SeaweedFS soporta lifecycle rules** vía S3 API `PutBucketLifecycleConfiguration`.
    Solo `Expiration` (borrar objetos) — `Transition` no está soportado.
    Ref: `seaweedfs/weed/s3api/s3api_bucket_lifecycle_config.go`
