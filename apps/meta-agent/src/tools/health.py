"""Tool para verificar el estado de salud de containers de tenants."""

import json
import time
from typing import Any

import docker
from docker.errors import APIError, NotFound


def _get_client() -> docker.DockerClient:
    """Obtiene el cliente Docker."""
    return docker.from_env()


def check_all_health() -> str:
    """Verifica el estado de salud de todos los containers de tenants.

    Revisa cada container con label martes.tenant y reporta su estado.

    Returns:
        JSON con el resumen de salud de todos los tenants.
    """
    client = _get_client()

    try:
        containers = client.containers.list(
            all=True, filters={"label": "martes.tenant"}
        )

        results: list[dict[str, Any]] = []
        healthy_count = 0
        unhealthy_count = 0
        stopped_count = 0

        for container in containers:
            tenant_code = container.labels.get("martes.tenant", "unknown")
            plan = container.labels.get("martes.plan", "unknown")

            if container.status != "running":
                results.append(
                    {
                        "tenant_code": tenant_code,
                        "plan": plan,
                        "status": "stopped",
                        "container_status": container.status,
                    }
                )
                stopped_count += 1
                continue

            # Verificar health del container
            health_status = _check_container_health(container)
            results.append(
                {
                    "tenant_code": tenant_code,
                    "plan": plan,
                    "status": health_status["status"],
                    "response_ms": health_status.get("response_ms"),
                    "details": health_status.get("details", ""),
                }
            )

            if health_status["status"] == "healthy":
                healthy_count += 1
            else:
                unhealthy_count += 1

        summary = {
            "success": True,
            "total": len(results),
            "healthy": healthy_count,
            "unhealthy": unhealthy_count,
            "stopped": stopped_count,
            "tenants": results,
        }

        return json.dumps(summary)

    except APIError as e:
        return json.dumps({"success": False, "error": str(e)})


def check_tenant_health(tenant_code: str) -> str:
    """Verifica el estado de salud de un tenant especifico.

    Args:
        tenant_code: Codigo del tenant (e.g. t001).

    Returns:
        JSON con el estado de salud del tenant.
    """
    client = _get_client()
    container_name = f"hermes-{tenant_code}"

    try:
        container = client.containers.get(container_name)

        if container.status != "running":
            return json.dumps(
                {
                    "success": True,
                    "tenant_code": tenant_code,
                    "status": "stopped",
                    "container_status": container.status,
                    "message": f"Container {container_name} no esta corriendo.",
                }
            )

        health = _check_container_health(container)

        return json.dumps(
            {
                "success": True,
                "tenant_code": tenant_code,
                "status": health["status"],
                "response_ms": health.get("response_ms"),
                "details": health.get("details", ""),
                "container_name": container_name,
            }
        )

    except NotFound:
        return json.dumps(
            {
                "success": True,
                "tenant_code": tenant_code,
                "status": "not_found",
                "message": f"Container {container_name} no existe.",
            }
        )
    except APIError as e:
        return json.dumps({"success": False, "error": str(e)})


def get_tenant_logs(tenant_code: str, lines: int = 50) -> str:
    """Obtiene los ultimos logs de un container de tenant.

    Args:
        tenant_code: Codigo del tenant.
        lines: Numero de lineas a obtener (default 50).

    Returns:
        JSON con los logs del container.
    """
    client = _get_client()
    container_name = f"hermes-{tenant_code}"

    try:
        container = client.containers.get(container_name)
        logs = container.logs(tail=lines, timestamps=True).decode("utf-8", errors="replace")

        return json.dumps(
            {
                "success": True,
                "tenant_code": tenant_code,
                "container_name": container_name,
                "lines": lines,
                "logs": logs,
            }
        )

    except NotFound:
        return json.dumps(
            {"success": False, "error": f"Container {container_name} no encontrado."}
        )
    except APIError as e:
        return json.dumps({"success": False, "error": str(e)})


def get_tenant_stats(tenant_code: str) -> str:
    """Obtiene estadisticas de uso de recursos de un container.

    Args:
        tenant_code: Codigo del tenant.

    Returns:
        JSON con CPU, memoria, y red del container.
    """
    client = _get_client()
    container_name = f"hermes-{tenant_code}"

    try:
        container = client.containers.get(container_name)

        if container.status != "running":
            return json.dumps(
                {
                    "success": True,
                    "tenant_code": tenant_code,
                    "status": "stopped",
                    "message": "Container no esta corriendo, no hay stats.",
                }
            )

        stats: dict[str, Any] = container.stats(stream=False)  # type: ignore[assignment]

        # Calcular uso de memoria
        mem_usage: int = stats["memory_stats"].get("usage", 0)
        mem_limit: int = stats["memory_stats"].get("limit", 1)
        mem_percent = (mem_usage / mem_limit) * 100 if mem_limit > 0 else 0.0

        # Calcular uso de CPU
        cpu_delta = (
            stats["cpu_stats"]["cpu_usage"]["total_usage"]
            - stats["precpu_stats"]["cpu_usage"]["total_usage"]
        )
        system_delta = (
            stats["cpu_stats"].get("system_cpu_usage", 0)
            - stats["precpu_stats"].get("system_cpu_usage", 0)
        )
        num_cpus: int = stats["cpu_stats"].get("online_cpus", 1)
        cpu_percent = (
            (cpu_delta / system_delta) * num_cpus * 100 if system_delta > 0 else 0
        )

        return json.dumps(
            {
                "success": True,
                "tenant_code": tenant_code,
                "memory_mb": round(mem_usage / (1024 * 1024), 1),
                "memory_limit_mb": round(mem_limit / (1024 * 1024), 1),
                "memory_percent": round(mem_percent, 1),
                "cpu_percent": round(cpu_percent, 2),
                "status": "running",
            }
        )

    except NotFound:
        return json.dumps(
            {"success": False, "error": f"Container {container_name} no encontrado."}
        )
    except (APIError, KeyError) as e:
        return json.dumps({"success": False, "error": str(e)})


def _check_container_health(container: Any) -> dict[str, Any]:
    """Verifica la salud de un container ejecutando un exec dentro.

    Intenta hacer curl al health endpoint interno de Hermes (puerto 8642).

    Args:
        container: Objeto container de Docker.

    Returns:
        Dict con status y detalles.
    """
    try:
        start = time.time()
        # Hermes expone health en puerto 8642
        exit_code, output = container.exec_run(
            "wget -q -O - http://localhost:8642/health",
            timeout=10,
        )
        elapsed_ms = int((time.time() - start) * 1000)

        if exit_code == 0:
            return {
                "status": "healthy",
                "response_ms": elapsed_ms,
                "details": output.decode("utf-8", errors="replace")[:200],
            }
        else:
            return {
                "status": "unhealthy",
                "response_ms": elapsed_ms,
                "details": f"Health check failed (exit {exit_code})",
            }

    except Exception as e:
        return {
            "status": "unhealthy",
            "details": f"Error ejecutando health check: {e}",
        }
