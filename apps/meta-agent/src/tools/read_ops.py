"""Read-only tools — el Diagnosticador los usa sin restriccion."""

import json
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import docker
import psycopg
from docker.errors import APIError, NotFound

from src.config import settings

_BACKUPS_DIR = Path("/var/lib/martes/backups")


def _docker() -> docker.DockerClient:
    return docker.from_env()


def _pg() -> str:
    url = settings.database_url
    return url.replace("+psycopg", "") if "+psycopg" in url else url


def list_containers() -> str:
    """Lista todos los containers de tenants Hermes."""
    try:
        cs = _docker().containers.list(all=True, filters={"label": "martes.tenant"})
        return json.dumps(
            {
                "count": len(cs),
                "tenants": [
                    {
                        "name": c.name,
                        "tenant": c.labels.get("martes.tenant"),
                        "plan": c.labels.get("martes.plan"),
                        "status": c.status,
                    }
                    for c in cs
                ],
            }
        )
    except APIError as e:
        return json.dumps({"error": str(e)})


def container_health(tenant_code: str) -> str:
    """Verifica health de un container via curl al puerto 8642.

    Hermes expone GET /health en :8642 cuando API_SERVER_ENABLED=true.
    Usamos curl (disponible en la imagen Hermes); wget no está disponible.
    Ref: https://hermes-agent.nousresearch.com/docs/user-guide/docker
    """
    try:
        c = _docker().containers.get(f"hermes-{tenant_code}")
        if c.status != "running":
            return json.dumps({"tenant": tenant_code, "status": "stopped"})
        start = time.time()
        result = c.exec_run("curl -sf http://localhost:8642/health")
        ms = int((time.time() - start) * 1000)
        exit_code: int = result.exit_code or 1
        output: bytes = result.output  # type: ignore[assignment]
        return json.dumps(
            {
                "tenant": tenant_code,
                "status": "healthy" if exit_code == 0 else "unhealthy",
                "response_ms": ms,
                "details": output.decode("utf-8", errors="replace")[:200],
            }
        )
    except NotFound:
        return json.dumps({"tenant": tenant_code, "status": "not_found"})
    except APIError as e:
        return json.dumps({"error": str(e)})


def container_logs(tenant_code: str, lines: int = 50) -> str:
    """Obtiene los ultimos logs de un container."""
    try:
        c = _docker().containers.get(f"hermes-{tenant_code}")
        raw: bytes = c.logs(tail=lines, timestamps=True)  # type: ignore[assignment]
        return json.dumps({"tenant": tenant_code, "logs": raw.decode("utf-8", errors="replace")})
    except NotFound:
        return json.dumps({"error": f"Container hermes-{tenant_code} no encontrado."})
    except APIError as e:
        return json.dumps({"error": str(e)})


def container_stats(tenant_code: str) -> str:
    """CPU y memoria de un container."""
    try:
        c = _docker().containers.get(f"hermes-{tenant_code}")
        if c.status != "running":
            return json.dumps({"tenant": tenant_code, "status": "stopped"})
        stats: dict[str, Any] = c.stats(stream=False)  # type: ignore[assignment]
        mem = stats["memory_stats"]
        mem_mb = round(mem.get("usage", 0) / (1024 * 1024), 1)
        mem_pct = round(mem.get("usage", 0) / max(mem.get("limit", 1), 1) * 100, 1)
        cpu = stats.get("cpu_stats", {})
        pcpu = stats.get("precpu_stats", {})
        cd = cpu.get("cpu_usage", {}).get("total_usage", 0) - pcpu.get("cpu_usage", {}).get(
            "total_usage", 0
        )
        sd = cpu.get("system_cpu_usage", 0) - pcpu.get("system_cpu_usage", 0)
        nc: int = cpu.get("online_cpus", 1)
        cpu_pct = round(cd / sd * nc * 100, 2) if sd > 0 else 0.0
        return json.dumps(
            {
                "tenant": tenant_code,
                "memory_mb": mem_mb,
                "memory_percent": mem_pct,
                "cpu_percent": cpu_pct,
            }
        )
    except (NotFound, APIError, KeyError) as e:
        return json.dumps({"error": str(e)})


def check_all_health() -> str:
    """Health check global de todos los tenants."""
    try:
        cs = _docker().containers.list(all=True, filters={"label": "martes.tenant"})
        healthy = unhealthy = stopped = 0
        results = []
        for c in cs:
            t = c.labels.get("martes.tenant", "?")
            if c.status != "running":
                results.append({"tenant": t, "status": "stopped"})
                stopped += 1
            else:
                try:
                    r = c.exec_run("curl -sf http://localhost:8642/health")
                    ec: int = r.exit_code or 1
                    if ec == 0:
                        results.append({"tenant": t, "status": "healthy"})
                        healthy += 1
                    else:
                        results.append({"tenant": t, "status": "unhealthy"})
                        unhealthy += 1
                except Exception:
                    results.append({"tenant": t, "status": "unhealthy"})
                    unhealthy += 1
        return json.dumps(
            {
                "total": len(results),
                "healthy": healthy,
                "unhealthy": unhealthy,
                "stopped": stopped,
                "tenants": results,
            }
        )
    except APIError as e:
        return json.dumps({"error": str(e)})


def list_backups(tenant_code: str = "") -> str:
    """Lista backups disponibles en SeaweedFS (o disco local como fallback).

    Si tenant_code se proporciona, filtra por ese tenant.
    Orden: más reciente primero.
    """
    from src import storage

    try:
        if storage.storage_available():
            # Listar desde SeaweedFS
            if tenant_code:
                backups = storage.list_tenant_backups(tenant_code)
                for b in backups:
                    b["tenant"] = tenant_code
            else:
                # Sin filtro: listar todos los tenants desde disco y agregar
                tenants_dir = Path(settings.tenants_base_path)
                backups = []
                if tenants_dir.exists():
                    for tp in sorted(tenants_dir.iterdir()):
                        if tp.is_dir():
                            for b in storage.list_tenant_backups(tp.name):
                                b["tenant"] = tp.name
                                backups.append(b)
                    backups.sort(key=lambda b: b["created_at"], reverse=True)
            return json.dumps({"count": len(backups), "source": "seaweedfs", "backups": backups})

        # Fallback: listar desde disco local
        _BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
        files = sorted(
            _BACKUPS_DIR.glob("*.tar.gz"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        if tenant_code:
            files = [f for f in files if f.name.startswith(f"{tenant_code}_")]
        backups = []
        for f in files:
            stat = f.stat()
            backups.append(
                {
                    "filename": f.name,
                    "tenant": f.name.split("_")[0] if "_" in f.name else "?",
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "created_at": datetime.fromtimestamp(
                        stat.st_mtime, tz=timezone.utc
                    ).isoformat(),
                }
            )
        return json.dumps({"count": len(backups), "source": "local", "backups": backups})
    except Exception as e:
        return json.dumps({"error": str(e)})


def check_backup_status() -> str:
    """Verifica el estado de backups de todos los tenants.

    Consulta SeaweedFS para saber cuándo fue el último backup de cada tenant.
    Fallback a disco local si SeaweedFS no está disponible.
    """
    from src import storage

    try:
        tenants_dir = Path(settings.tenants_base_path)
        if not tenants_dir.exists():
            return json.dumps({"error": "tenants directory not found"})

        results = []
        use_seaweedfs = storage.storage_available()

        for tenant_path in sorted(tenants_dir.iterdir()):
            if not tenant_path.is_dir():
                continue
            code = tenant_path.name
            last_backup: str | None = None
            hours_since: float | None = None
            backup_count = 0

            if use_seaweedfs:
                backups = storage.list_tenant_backups(code)  # más reciente primero
                backup_count = len(backups)
                if backups:
                    # list_tenant_backups siempre devuelve created_at como str
                    last_backup = backups[0]["created_at"]
                    last_dt = datetime.fromisoformat(last_backup)  # type: ignore[arg-type]
                    hours_since = round(
                        (datetime.now(tz=timezone.utc) - last_dt).total_seconds() / 3600, 1
                    )
            else:
                # Fallback a disco local
                local_backups = sorted(
                    _BACKUPS_DIR.glob(f"{code}_*.tar.gz"),
                    key=lambda f: f.stat().st_mtime,
                    reverse=True,
                )
                backup_count = len(local_backups)
                if local_backups:
                    mtime = local_backups[0].stat().st_mtime
                    last_backup = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
                    hours_since = round(
                        (datetime.now(tz=timezone.utc).timestamp() - mtime) / 3600, 1
                    )

            results.append(
                {
                    "tenant": code,
                    "last_backup": last_backup,
                    "hours_since_backup": hours_since,
                    "backup_count": backup_count,
                    "status": (
                        "ok"
                        if hours_since is not None and hours_since < 26
                        else "overdue"
                        if last_backup
                        else "never"
                    ),
                }
            )

        overdue = [r for r in results if r["status"] != "ok"]
        return json.dumps(
            {
                "total_tenants": len(results),
                "overdue": len(overdue),
                "source": "seaweedfs" if use_seaweedfs else "local",
                "tenants": results,
            }
        )
    except Exception as e:
        return json.dumps({"error": str(e)})


def diagnose_container_error(tenant_code: str) -> str:
    """Diagnóstico automático de un container que no arranca o está unhealthy.

    Combina docker inspect + tail de logs para clasificar la causa del error
    sin que el admin tenga que pedir cada pieza por separado.

    Devuelve causa probable y solución recomendada en un solo tool call.
    """
    try:
        c = _docker().containers.get(f"hermes-{tenant_code}")
        attrs = c.attrs

        state = attrs.get("State", {})
        host_cfg = attrs.get("HostConfig", {})
        exit_code: int = state.get("ExitCode", 0)
        oom_killed: bool = state.get("OOMKilled", False)
        restart_count: int = attrs.get("RestartCount", 0)
        status: str = state.get("Status", "unknown")
        error_msg: str = state.get("Error", "")
        image: str = attrs.get("Config", {}).get("Image", "?")
        mem_limit_mb = round(host_cfg.get("Memory", 0) / (1 << 20))

        # Últimas 50 líneas de logs para análisis
        raw: bytes = c.logs(tail=50, timestamps=False)  # type: ignore[assignment]
        log_tail = raw.decode("utf-8", errors="replace")

        # Clasificación del error — orden: OOM primero (más destructivo)
        cause = "desconocido"
        solution = "Revisa los logs completos con container_logs() para más detalle."

        if oom_killed:
            cause = f"OOM Kill — el container superó el límite de {mem_limit_mb} MB de RAM"
            solution = (
                f"Usa update_tenant_resources() para subir la RAM. "
                f"Perfil recomendado: 1024 MB / 1.0 CPU. "
                f"Comando: update_tenant_resources('{tenant_code}', memory_mb=1024, cpu_cores=1.0)"
            )
        elif exit_code == 1 and (
            "OPENROUTER_API_KEY" in log_tail or "openrouter" in log_tail.lower()
        ):
            cause = "API key de OpenRouter inválida, expirada o sin créditos"
            solution = (
                "Verifica que OPENROUTER_API_KEY en el .env del tenant es válida y tiene saldo. "
                "Usa inject_credential() para actualizarla si cambió."
            )
        elif exit_code == 1 and (
            "TELEGRAM_BOT_TOKEN" in log_tail
            or "telegram" in log_tail.lower()
            and "token" in log_tail.lower()
        ):
            cause = "Token de Telegram inválido o revocado"
            solution = (
                "Verifica el token con @BotFather en Telegram. "
                "Usa inject_credential() para actualizarlo."
            )
        elif "permission denied" in log_tail.lower() or "permissionerror" in log_tail.lower():
            cause = "Error de permisos en el volumen del tenant"
            solution = (
                f"El directorio /var/lib/martes/tenants/{tenant_code} "
                "necesita chown 1000:1000 recursivo. "
                "Esto puede indicar que el backup/restore no aplicó los permisos correctamente."
            )
        elif error_msg and (
            "no such image" in error_msg.lower() or "not found" in error_msg.lower()
        ):
            cause = f"Imagen Docker no encontrada: {image}"
            solution = (
                f"La imagen '{image}' no está disponible en el servidor. "
                "Verifica que HERMES_IMAGE apunta a un tag existente en Docker Hub. "
                "Ref: https://hub.docker.com/r/nousresearch/hermes-agent/tags"
            )
        elif restart_count > 3:
            cause = f"Crash loop — el container ha reiniciado {restart_count} veces"
            solution = (
                "Revisa los logs completos con container_logs(). "
                "Causas frecuentes: .env incorrecto, config.yaml inválido, "
                "o conflicto de gateway.pid stale tras un restore. "
                "Si hay gateway.pid/gateway.lock en el volumen, elimínalos y reinicia."
            )
        elif exit_code == 75:
            cause = "Exit 75 — restart graceful solicitado por Hermes (normal tras /restart)"
            solution = (
                "Esto es normal. El container debería reiniciarse automáticamente "
                "por restart_policy=unless-stopped. "
                "Si lleva más de 30s sin arrancar, usa restart_tenant()."
            )
        elif status == "created" and exit_code == 0:
            cause = "Container creado pero nunca arrancó"
            solution = "Usa restart_tenant() para iniciarlo."

        return json.dumps(
            {
                "tenant": tenant_code,
                "status": status,
                "image": image,
                "exit_code": exit_code,
                "oom_killed": oom_killed,
                "restart_count": restart_count,
                "memory_limit_mb": mem_limit_mb,
                "probable_cause": cause,
                "suggested_solution": solution,
                "log_tail": log_tail[-1500:],
            }
        )
    except NotFound:
        return json.dumps(
            {
                "tenant": tenant_code,
                "error": f"Container hermes-{tenant_code} no encontrado.",
                "suggestion": (
                    "El container no existe. Puede que fue eliminado. "
                    "Comprueba get_all_tenants() para ver el estado en DB."
                ),
            }
        )
    except APIError as e:
        return json.dumps({"error": str(e)})


def find_stale_resources() -> str:
    """Detecta recursos huérfanos en el sistema. Solo lectura — no borra nada.

    Busca tres tipos de inconsistencias:
    1. Tenants en DB con status='creating' sin container Docker
       (create_tenant() falló a mitad — el código queda bloqueado)
    2. Redes Docker 'tenant-tXXX-net' sin container asociado
       (crea_tenant parcial o delete_tenant incompleto)
    3. Directorios en /var/lib/martes/tenants/ sin registro en DB
       (datos huérfanos en disco)

    Devuelve el inventario de recursos huérfanos con sus detalles.
    Para limpiarlos: usa el Operador con los tools correspondientes.
    """
    stale: dict = {
        "db_creating": [],
        "orphan_networks": [],
        "orphan_dirs": [],
        "total": 0,
    }

    try:
        # 1. Tenants con status='creating' (create_tenant falló a mitad)
        with psycopg.connect(_pg()) as conn:
            rows = conn.execute(
                "SELECT tenant_code, name, created_at FROM tenants WHERE status = 'creating'"
            ).fetchall()
        stale["db_creating"] = [{"code": r[0], "name": r[1], "created_at": str(r[2])} for r in rows]

        # 2. Redes Docker tenant-tXXX-net sin container asociado
        c_client = _docker()
        tenant_container_names = {
            c.name for c in c_client.containers.list(all=True, filters={"label": "martes.tenant"})
        }
        tenant_nets = c_client.networks.list(filters={"name": "tenant-"})
        for net in tenant_nets:
            net_name: str = net.name or ""
            net_id: str = net.id or ""
            if not net_name.startswith("tenant-") or not net_name.endswith("-net"):
                continue
            # Derivar el tenant_code esperado: tenant-t001-net → t001
            parts = net_name.split("-")
            if len(parts) < 3:
                continue
            tenant_code = parts[1]
            expected_container = f"hermes-{tenant_code}"
            if expected_container not in tenant_container_names:
                stale["orphan_networks"].append(
                    {"network": net_name, "tenant_code": tenant_code, "id": net_id[:12]}
                )

        # 3. Directorios en tenants/ sin registro en DB
        tenants_dir = Path(settings.tenants_base_path)
        if tenants_dir.exists():
            with psycopg.connect(_pg()) as conn:
                known_codes = {
                    r[0] for r in conn.execute("SELECT tenant_code FROM tenants").fetchall()
                }
            for tenant_dir in sorted(tenants_dir.iterdir()):
                if not tenant_dir.is_dir():
                    continue
                if tenant_dir.name not in known_codes:
                    size_mb = round(
                        sum(f.stat().st_size for f in tenant_dir.rglob("*") if f.is_file())
                        / (1 << 20),
                        1,
                    )
                    stale["orphan_dirs"].append(
                        {"dir": tenant_dir.name, "path": str(tenant_dir), "size_mb": size_mb}
                    )

        stale["total"] = (
            len(stale["db_creating"]) + len(stale["orphan_networks"]) + len(stale["orphan_dirs"])
        )

        if stale["total"] == 0:
            stale["message"] = "Sin recursos huérfanos detectados."
        else:
            stale["message"] = (
                f"{stale['total']} recurso(s) huérfano(s) detectado(s). "
                "Solo lectura — usa el Operador para limpiarlos manualmente."
            )

        return json.dumps(stale)

    except Exception as e:
        return json.dumps({"error": str(e)})


def get_server_capacity() -> str:
    """Capacidad disponible del servidor: RAM, disco y slots de tenants libres.

    Combina /proc/meminfo, shutil.disk_usage y docker stats de los containers
    de tenants para calcular cuántos tenants adicionales caben.

    Perfiles de referencia:
    - Estándar: 768 MB / 0.75 CPU (por defecto al crear)
    - Ligero:   512 MB / 0.5 CPU
    """
    try:
        # RAM del host via /proc/meminfo
        meminfo = Path("/proc/meminfo").read_text()
        mem_total_kb = int(
            next(ln for ln in meminfo.splitlines() if ln.startswith("MemTotal")).split()[1]
        )
        mem_avail_kb = int(
            next(ln for ln in meminfo.splitlines() if ln.startswith("MemAvailable")).split()[1]
        )
        mem_total_mb = mem_total_kb // 1024
        mem_avail_mb = mem_avail_kb // 1024

        # Disco en /var/lib/martes
        disk = shutil.disk_usage("/var/lib/martes")
        disk_free_gb = round(disk.free / (1 << 30), 1)
        disk_total_gb = round(disk.total / (1 << 30), 1)
        disk_pct = round(disk.used / disk.total * 100, 1)

        # RAM asignada a containers de tenants (límite configurado, no uso real)
        cs = _docker().containers.list(filters={"label": "martes.tenant"})
        tenant_alloc_mb = sum(
            round(c.attrs.get("HostConfig", {}).get("Memory", 0) / (1 << 20))
            for c in cs
            if c.attrs.get("HostConfig", {}).get("Memory", 0) > 0
        )
        tenants_running = sum(1 for c in cs if c.status == "running")
        tenants_total = len(cs)

        # Slots disponibles — basado en RAM libre del sistema
        slots_standard = mem_avail_mb // 768  # perfil estándar 768 MB
        slots_light = mem_avail_mb // 512  # perfil ligero 512 MB

        return json.dumps(
            {
                "server": {
                    "ram_total_mb": mem_total_mb,
                    "ram_available_mb": mem_avail_mb,
                    "ram_allocated_to_tenants_mb": tenant_alloc_mb,
                },
                "disk": {
                    "total_gb": disk_total_gb,
                    "free_gb": disk_free_gb,
                    "used_pct": disk_pct,
                    "warning": disk_pct > 80,
                },
                "tenants": {
                    "running": tenants_running,
                    "total_containers": tenants_total,
                },
                "capacity": {
                    "additional_slots_768mb": slots_standard,
                    "additional_slots_512mb": slots_light,
                    "recommendation": (
                        f"Caben ~{slots_standard} tenants más al perfil estándar (768 MB). "
                        "Considera upgrade a CX53 si superas 20 tenants activos."
                    ),
                },
            }
        )
    except Exception as e:
        return json.dumps({"error": str(e)})


def get_all_tenants() -> str:
    """Lista todos los tenants de la base de datos."""
    try:
        with psycopg.connect(_pg()) as conn:
            rows = conn.execute("""
                SELECT t.tenant_code, t.name, t.plan, t.status, t.paid_until,
                       t.container_name, ic.platforms, ic.model
                FROM tenants t
                LEFT JOIN instance_configs ic ON ic.tenant_id = t.id
                ORDER BY t.tenant_code
            """).fetchall()
            from datetime import datetime, timezone

            now = datetime.now(tz=timezone.utc).date()
            tenants = []
            for r in rows:
                pu = r[4]
                tenants.append(
                    {
                        "code": r[0],
                        "name": r[1],
                        "plan": r[2],
                        "status": r[3],
                        "paid_until": pu.isoformat() if pu else None,
                        "days_remaining": (pu - now).days if pu else None,
                        "container": r[5],
                        "platforms": r[6],
                        "model": r[7],
                    }
                )
            return json.dumps({"count": len(tenants), "tenants": tenants})
    except psycopg.Error as e:
        return json.dumps({"error": str(e)})
