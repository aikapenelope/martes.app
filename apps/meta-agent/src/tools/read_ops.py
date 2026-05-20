"""Tools de solo lectura — el Diagnosticador los usa sin restriccion.

Ninguno de estos tools modifica estado. Solo observan, consultan, y reportan.
"""

import json
from typing import Any

import docker
import psycopg
from docker.errors import APIError, NotFound

from src.config import settings


def _get_docker() -> docker.DockerClient:
    """Obtiene cliente Docker."""
    return docker.from_env()


def _get_conn_str() -> str:
    """Connection string para psycopg."""
    url = settings.database_url
    if "+psycopg" in url:
        url = url.replace("+psycopg", "")
    return url


# ---------------------------------------------------------------------------
# Docker read operations
# ---------------------------------------------------------------------------


def list_containers() -> str:
    """Lista todos los containers de tenants Hermes y su estado actual."""
    client = _get_docker()
    try:
        containers = client.containers.list(all=True, filters={"label": "martes.tenant"})
        tenants = []
        for c in containers:
            tenants.append({
                "name": c.name,
                "tenant": c.labels.get("martes.tenant", "?"),
                "plan": c.labels.get("martes.plan", "?"),
                "status": c.status,
            })
        return json.dumps({"count": len(tenants), "tenants": tenants})
    except APIError as e:
        return json.dumps({"error": str(e)})


def container_health(tenant_code: str) -> str:
    """Verifica health de un container especifico via wget al puerto 8642."""
    client = _get_docker()
    name = f"hermes-{tenant_code}"
    try:
        container = client.containers.get(name)
        if container.status != "running":
            return json.dumps({"tenant": tenant_code, "status": "stopped"})

        import time

        start = time.time()
        result = container.exec_run("wget -q -O - http://localhost:8642/health")
        exit_code: int = result.exit_code or 1
        output: bytes = result.output  # type: ignore[assignment]
        ms = int((time.time() - start) * 1000)

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
    """Obtiene los ultimos logs de un container de tenant."""
    client = _get_docker()
    name = f"hermes-{tenant_code}"
    try:
        container = client.containers.get(name)
        raw_logs: bytes = container.logs(tail=lines, timestamps=True)  # type: ignore[assignment]
        logs = raw_logs.decode("utf-8", errors="replace")
        return json.dumps({"tenant": tenant_code, "lines": lines, "logs": logs})
    except NotFound:
        return json.dumps({"error": f"Container {name} no encontrado."})
    except APIError as e:
        return json.dumps({"error": str(e)})


def container_stats(tenant_code: str) -> str:
    """Obtiene uso de CPU y memoria de un container."""
    client = _get_docker()
    name = f"hermes-{tenant_code}"
    try:
        container = client.containers.get(name)
        if container.status != "running":
            return json.dumps({"tenant": tenant_code, "status": "stopped"})

        stats: dict[str, Any] = container.stats(stream=False)  # type: ignore[assignment]
        mem_usage: int = stats["memory_stats"].get("usage", 0)
        mem_limit: int = stats["memory_stats"].get("limit", 1)
        mem_pct = (mem_usage / mem_limit) * 100 if mem_limit > 0 else 0.0

        cpu_delta = (
            stats["cpu_stats"]["cpu_usage"]["total_usage"]
            - stats["precpu_stats"]["cpu_usage"]["total_usage"]
        )
        sys_delta = (
            stats["cpu_stats"].get("system_cpu_usage", 0)
            - stats["precpu_stats"].get("system_cpu_usage", 0)
        )
        cpus: int = stats["cpu_stats"].get("online_cpus", 1)
        cpu_pct = (cpu_delta / sys_delta) * cpus * 100 if sys_delta > 0 else 0.0

        return json.dumps({
            "tenant": tenant_code,
            "memory_mb": round(mem_usage / (1024 * 1024), 1),
            "memory_percent": round(mem_pct, 1),
            "cpu_percent": round(cpu_pct, 2),
        })
    except NotFound:
        return json.dumps({"error": f"Container {name} no encontrado."})
    except (APIError, KeyError) as e:
        return json.dumps({"error": str(e)})


def check_all_health() -> str:
    """Health check global: revisa todos los containers de tenants."""
    client = _get_docker()
    try:
        containers = client.containers.list(all=True, filters={"label": "martes.tenant"})
        results = []
        healthy = unhealthy = stopped = 0
        for c in containers:
            tenant = c.labels.get("martes.tenant", "?")
            if c.status != "running":
                results.append({"tenant": tenant, "status": "stopped"})
                stopped += 1
            else:
                # Quick check: is the container responsive?
                try:
                    exit_code, _ = c.exec_run(
                        "wget -q -O - http://localhost:8642/health"
                    )
                    if exit_code == 0:
                        results.append({"tenant": tenant, "status": "healthy"})
                        healthy += 1
                    else:
                        results.append({"tenant": tenant, "status": "unhealthy"})
                        unhealthy += 1
                except Exception:
                    results.append({"tenant": tenant, "status": "unhealthy"})
                    unhealthy += 1

        return json.dumps({
            "total": len(results),
            "healthy": healthy,
            "unhealthy": unhealthy,
            "stopped": stopped,
            "tenants": results,
        })
    except APIError as e:
        return json.dumps({"error": str(e)})


# ---------------------------------------------------------------------------
# Database read operations
# ---------------------------------------------------------------------------


def get_all_tenants() -> str:
    """Lista todos los tenants registrados en la base de datos con su estado."""
    try:
        with psycopg.connect(_get_conn_str()) as conn:
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
            for row in rows:
                paid_until = row[4]
                days_left = (paid_until - now).days if paid_until else None
                tenants.append({
                    "code": row[0],
                    "name": row[1],
                    "plan": row[2],
                    "status": row[3],
                    "paid_until": paid_until.isoformat() if paid_until else None,
                    "days_remaining": days_left,
                    "container": row[5],
                    "platforms": row[6],
                    "model": row[7],
                })
            return json.dumps({"count": len(tenants), "tenants": tenants})
    except psycopg.Error as e:
        return json.dumps({"error": str(e)})


def get_tenant_detail(tenant_code: str) -> str:
    """Obtiene informacion detallada de un tenant especifico."""
    try:
        with psycopg.connect(_get_conn_str()) as conn:
            row = conn.execute(
                """
                SELECT t.*, ic.template, ic.platforms, ic.skills, ic.model,
                       ic.memory_limit_mb, ic.cpu_limit
                FROM tenants t
                LEFT JOIN instance_configs ic ON ic.tenant_id = t.id
                WHERE t.tenant_code = %s
                """,
                (tenant_code,),
            ).fetchone()

            if row is None:
                return json.dumps({"error": f"Tenant {tenant_code} no encontrado."})

            return json.dumps({
                "tenant_code": row[1],
                "name": row[2],
                "email": row[3],
                "plan": row[4],
                "status": row[5],
                "container_name": row[6],
                "paid_until": row[8].isoformat() if row[8] else None,
            })
    except psycopg.Error as e:
        return json.dumps({"error": str(e)})
