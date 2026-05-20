"""Tools de Docker para gestionar containers de tenants Hermes."""

import json
from typing import Any

import docker
from docker.errors import APIError, NotFound

from src.config import settings

# Cliente Docker (se conecta via socket montado)
_client: docker.DockerClient | None = None


def _get_client() -> docker.DockerClient:
    """Obtiene o crea el cliente Docker."""
    global _client
    if _client is None:
        _client = docker.from_env()
    return _client


def create_tenant_container(
    tenant_code: str,
    plan: str,
    bot_token: str,
    api_key: str | None = None,
) -> str:
    """Crea un container Hermes para un tenant nuevo.

    Args:
        tenant_code: Codigo del tenant (e.g. t001).
        plan: Plan del tenant (basico, equipo, pro).
        bot_token: Token del bot de Telegram del tenant.
        api_key: API key de OpenRouter (usa la del sistema si no se provee).

    Returns:
        JSON con el resultado de la operacion.
    """
    client = _get_client()
    container_name = f"hermes-{tenant_code}"
    network_name = f"tenant-{tenant_code}-net"
    volume_path = f"{settings.tenants_base_path}/{tenant_code}"

    # Limites de recursos segun plan
    plan_resources: dict[str, dict[str, Any]] = {
        "basico": {"memory_mb": 512, "cpus": 0.5},
        "equipo": {"memory_mb": 768, "cpus": 0.75},
        "pro": {"memory_mb": 1024, "cpus": 1.0},
    }
    resource_limits = plan_resources.get(plan, plan_resources["basico"])

    try:
        # Crear red aislada para el tenant
        try:
            client.networks.get(network_name)
        except NotFound:
            client.networks.create(network_name, driver="bridge")

        # Crear container
        run_kwargs: dict[str, Any] = {
            "image": settings.hermes_image,
            "name": container_name,
            "detach": True,
            "restart_policy": {"Name": "unless-stopped"},
            "volumes": {volume_path: {"bind": "/opt/data", "mode": "rw"}},
            "environment": {
                "HERMES_UID": "1000",
                "HERMES_GID": "1000",
                "API_SERVER_ENABLED": "true",
                "API_SERVER_HOST": "0.0.0.0",
                "HERMES_DASHBOARD": "1" if plan in ("equipo", "pro") else "0",
            },
            "mem_limit": f"{resource_limits['memory_mb']}m",
            "nano_cpus": int(float(resource_limits["cpus"]) * 1e9),
            "command": ["gateway", "run"],
            "labels": {
                "martes.tenant": tenant_code,
                "martes.plan": plan,
                "traefik.enable": "true",
                f"traefik.http.routers.{tenant_code}.rule": (
                    f"Host(`{tenant_code}.martes.app`)"
                ),
                f"traefik.http.routers.{tenant_code}.tls.certresolver": "letsencrypt",
                f"traefik.http.services.{tenant_code}.loadbalancer.server.port": "8642",
            },
        }
        container = client.containers.run(**run_kwargs)

        # Conectar a la red del tenant y a la red de Traefik
        tenant_net = client.networks.get(network_name)
        tenant_net.connect(container)

        # Conectar a la red de traefik si existe
        try:
            traefik_net = client.networks.get("martes-tenants")
            traefik_net.connect(container)
        except NotFound:
            pass  # Se conectara cuando Traefik este corriendo

        return json.dumps(
            {
                "success": True,
                "container_name": container_name,
                "container_id": container.id[:12],
                "network": network_name,
                "status": "running",
            }
        )

    except APIError as e:
        return json.dumps({"success": False, "error": str(e)})


def stop_tenant_container(tenant_code: str) -> str:
    """Detiene el container de un tenant (preserva datos).

    Args:
        tenant_code: Codigo del tenant (e.g. t001).

    Returns:
        JSON con el resultado.
    """
    client = _get_client()
    container_name = f"hermes-{tenant_code}"

    try:
        container = client.containers.get(container_name)
        container.stop(timeout=30)
        return json.dumps(
            {
                "success": True,
                "container_name": container_name,
                "status": "stopped",
                "message": f"Container {container_name} detenido. Datos preservados.",
            }
        )
    except NotFound:
        return json.dumps(
            {"success": False, "error": f"Container {container_name} no encontrado."}
        )
    except APIError as e:
        return json.dumps({"success": False, "error": str(e)})


def restart_tenant_container(tenant_code: str) -> str:
    """Reinicia el container de un tenant.

    Args:
        tenant_code: Codigo del tenant (e.g. t001).

    Returns:
        JSON con el resultado.
    """
    client = _get_client()
    container_name = f"hermes-{tenant_code}"

    try:
        container = client.containers.get(container_name)
        container.restart(timeout=30)
        return json.dumps(
            {
                "success": True,
                "container_name": container_name,
                "status": "running",
                "message": f"Container {container_name} reiniciado.",
            }
        )
    except NotFound:
        return json.dumps(
            {"success": False, "error": f"Container {container_name} no encontrado."}
        )
    except APIError as e:
        return json.dumps({"success": False, "error": str(e)})


def list_tenant_containers() -> str:
    """Lista todos los containers de tenants Hermes y su estado.

    Returns:
        JSON con la lista de containers.
    """
    client = _get_client()

    try:
        # Buscar todos los containers con label martes.tenant
        containers = client.containers.list(
            all=True, filters={"label": "martes.tenant"}
        )

        tenants = []
        for c in containers:
            tenants.append(
                {
                    "container_name": c.name,
                    "tenant_code": c.labels.get("martes.tenant", "unknown"),
                    "plan": c.labels.get("martes.plan", "unknown"),
                    "status": c.status,
                    "created": c.attrs.get("Created", ""),
                }
            )

        return json.dumps(
            {"success": True, "count": len(tenants), "tenants": tenants}
        )

    except APIError as e:
        return json.dumps({"success": False, "error": str(e)})


def remove_tenant_container(tenant_code: str) -> str:
    """Elimina completamente un container y su red (para archivado).

    Args:
        tenant_code: Codigo del tenant (e.g. t001).

    Returns:
        JSON con el resultado.
    """
    client = _get_client()
    container_name = f"hermes-{tenant_code}"
    network_name = f"tenant-{tenant_code}-net"

    try:
        # Detener y eliminar container
        try:
            container = client.containers.get(container_name)
            container.stop(timeout=10)
            container.remove()
        except NotFound:
            pass

        # Eliminar red
        try:
            network = client.networks.get(network_name)
            network.remove()
        except NotFound:
            pass

        return json.dumps(
            {
                "success": True,
                "message": f"Container {container_name} y red {network_name} eliminados.",
            }
        )

    except APIError as e:
        return json.dumps({"success": False, "error": str(e)})
