"""Read-only tools — el Diagnosticador los usa sin restriccion."""

import json
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
        return json.dumps({
            "count": len(cs),
            "tenants": [{"name": c.name, "tenant": c.labels.get("martes.tenant"),
                         "plan": c.labels.get("martes.plan"), "status": c.status}
                        for c in cs]
        })
    except APIError as e:
        return json.dumps({"error": str(e)})


def container_health(tenant_code: str) -> str:
    """Verifica health de un container via wget al puerto 8642."""
    try:
        c = _docker().containers.get(f"hermes-{tenant_code}")
        if c.status != "running":
            return json.dumps({"tenant": tenant_code, "status": "stopped"})
        start = time.time()
        result = c.exec_run("wget -q -O - http://localhost:8642/health")
        ms = int((time.time() - start) * 1000)
        exit_code: int = result.exit_code or 1
        output: bytes = result.output  # type: ignore[assignment]
        return json.dumps({
            "tenant": tenant_code,
            "status": "healthy" if exit_code == 0 else "unhealthy",
            "response_ms": ms,
            "details": output.decode("utf-8", errors="replace")[:200],
        })
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
        cd = (cpu.get("cpu_usage", {}).get("total_usage", 0)
              - pcpu.get("cpu_usage", {}).get("total_usage", 0))
        sd = cpu.get("system_cpu_usage", 0) - pcpu.get("system_cpu_usage", 0)
        nc: int = cpu.get("online_cpus", 1)
        cpu_pct = round(cd / sd * nc * 100, 2) if sd > 0 else 0.0
        return json.dumps({"tenant": tenant_code, "memory_mb": mem_mb,
                           "memory_percent": mem_pct, "cpu_percent": cpu_pct})
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
                    r = c.exec_run("wget -q -O - http://localhost:8642/health")
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
        return json.dumps({"total": len(results), "healthy": healthy,
                           "unhealthy": unhealthy, "stopped": stopped, "tenants": results})
    except APIError as e:
        return json.dumps({"error": str(e)})


def list_backups(tenant_code: str = "") -> str:
    """Lista backups disponibles. Si se da tenant_code filtra por ese tenant.
    Backups en /var/lib/martes/backups/ — formato: {tenant_code}_{YYYYMMDD}_{HHMMSS}.tar.gz
    """
    try:
        _BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
        files = sorted(_BACKUPS_DIR.glob("*.tar.gz"), key=lambda f: f.stat().st_mtime, reverse=True)
        if tenant_code:
            files = [f for f in files if f.name.startswith(f"{tenant_code}_")]
        backups = []
        for f in files:
            stat = f.stat()
            backups.append({
                "filename": f.name,
                "tenant": f.name.split("_")[0] if "_" in f.name else "?",
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "created": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            })
        return json.dumps({"count": len(backups), "backups": backups})
    except OSError as e:
        return json.dumps({"error": str(e)})


def check_backup_status() -> str:
    """Verifica el estado de backups de todos los tenants.
    Muestra cuándo fue el último backup de cada tenant y si está al día.
    """
    try:
        tenants_dir = Path(settings.tenants_base_path)
        _BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
        results = []
        if not tenants_dir.exists():
            return json.dumps({"error": "tenants directory not found"})
        for tenant_path in sorted(tenants_dir.iterdir()):
            if not tenant_path.is_dir():
                continue
            code = tenant_path.name
            backups = sorted(
                _BACKUPS_DIR.glob(f"{code}_*.tar.gz"),
                key=lambda f: f.stat().st_mtime,
                reverse=True,
            )
            last_backup = None
            hours_since = None
            if backups:
                last_mtime = backups[0].stat().st_mtime
                last_backup = datetime.fromtimestamp(last_mtime, tz=timezone.utc).isoformat()
                hours_since = round((datetime.now(tz=timezone.utc).timestamp() - last_mtime) / 3600, 1)
            results.append({
                "tenant": code,
                "last_backup": last_backup,
                "hours_since_backup": hours_since,
                "backup_count": len(backups),
                "status": "ok" if hours_since and hours_since < 26 else "overdue" if last_backup else "never",
            })
        overdue = [r for r in results if r["status"] != "ok"]
        return json.dumps({
            "total_tenants": len(results),
            "overdue": len(overdue),
            "tenants": results,
        })
    except OSError as e:
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
                tenants.append({
                    "code": r[0], "name": r[1], "plan": r[2], "status": r[3],
                    "paid_until": pu.isoformat() if pu else None,
                    "days_remaining": (pu - now).days if pu else None,
                    "container": r[5], "platforms": r[6], "model": r[7],
                })
            return json.dumps({"count": len(tenants), "tenants": tenants})
    except psycopg.Error as e:
        return json.dumps({"error": str(e)})
