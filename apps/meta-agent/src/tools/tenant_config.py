"""Tools para escribir configuracion de tenants en volumenes."""

import json
import os
import shutil
from pathlib import Path

from src.config import settings


def write_tenant_config(
    tenant_code: str,
    plan: str,
    bot_token: str,
    api_key: str | None = None,
    soul_name: str | None = None,
) -> str:
    """Escribe config.yaml, .env y SOUL.md en el volumen del tenant.

    Copia el template correspondiente al plan y personaliza con los datos del tenant.

    Args:
        tenant_code: Codigo del tenant (e.g. t001).
        plan: Plan del tenant (basico, equipo, pro).
        bot_token: Token del bot de Telegram del tenant.
        api_key: API key de OpenRouter (usa la del sistema si no se provee).
        soul_name: Nombre para personalizar SOUL.md (opcional).

    Returns:
        JSON con el resultado de la operacion.
    """
    tenant_path = Path(settings.tenants_base_path) / tenant_code
    template_path = Path(settings.templates_path) / plan

    try:
        # Crear directorio del tenant con subdirectorios
        tenant_path.mkdir(parents=True, exist_ok=True)
        for subdir in ["sessions", "memories", "skills", "cron", "logs", "wiki", "workspace"]:
            (tenant_path / subdir).mkdir(exist_ok=True)

        # Copiar config.yaml del template
        config_src = template_path / "config.yaml"
        if config_src.exists():
            shutil.copy2(config_src, tenant_path / "config.yaml")
        else:
            return json.dumps(
                {"success": False, "error": f"Template no encontrado: {template_path}"}
            )

        # Escribir .env con credenciales
        effective_api_key = api_key or settings.openrouter_api_key
        env_content = (
            f"# Generado automaticamente por martes.app meta-agente\n"
            f"OPENROUTER_API_KEY={effective_api_key}\n"
            f"TELEGRAM_BOT_TOKEN={bot_token}\n"
            f"OPENROUTER_BASE_URL=https://openrouter.ai/api/v1\n"
        )
        env_file = tenant_path / ".env"
        env_file.write_text(env_content)
        os.chmod(env_file, 0o600)

        # Copiar y personalizar SOUL.md
        soul_src = template_path / "SOUL.md"
        if soul_src.exists():
            soul_content = soul_src.read_text()
            if soul_name:
                soul_content = soul_content.replace("{{AGENT_NAME}}", soul_name)
            (tenant_path / "SOUL.md").write_text(soul_content)

        return json.dumps(
            {
                "success": True,
                "tenant_code": tenant_code,
                "path": str(tenant_path),
                "files_written": ["config.yaml", ".env", "SOUL.md"],
                "directories_created": [
                    "sessions",
                    "memories",
                    "skills",
                    "cron",
                    "logs",
                    "wiki",
                    "workspace",
                ],
            }
        )

    except OSError as e:
        return json.dumps({"success": False, "error": str(e)})


def inject_credential(
    tenant_code: str,
    credential_type: str,
    credential_value: str,
) -> str:
    """Inyecta una credencial (OAuth token, API key) en el volumen del tenant.

    Args:
        tenant_code: Codigo del tenant (e.g. t001).
        credential_type: Tipo de credencial (google_token, notion_key, etc.).
        credential_value: Valor de la credencial.

    Returns:
        JSON con el resultado.
    """
    tenant_path = Path(settings.tenants_base_path) / tenant_code

    if not tenant_path.exists():
        return json.dumps(
            {"success": False, "error": f"Tenant {tenant_code} no existe en disco."}
        )

    # Mapeo de tipo a archivo
    credential_files: dict[str, str] = {
        "google_token": "google_token.json",
        "google_client_secret": "google_client_secret.json",
        "notion_key": ".env",  # Se agrega al .env
        "airtable_key": ".env",
        "github_token": ".env",
        "linear_key": ".env",
    }

    target_file = credential_files.get(credential_type)
    if not target_file:
        return json.dumps(
            {
                "success": False,
                "error": f"Tipo de credencial desconocido: {credential_type}. "
                f"Tipos validos: {list(credential_files.keys())}",
            }
        )

    try:
        if target_file == ".env":
            # Agregar al .env existente
            env_file = tenant_path / ".env"
            env_key = credential_type.upper()
            existing = env_file.read_text() if env_file.exists() else ""
            # Reemplazar si ya existe, sino agregar
            lines = existing.splitlines()
            found = False
            for i, line in enumerate(lines):
                if line.startswith(f"{env_key}="):
                    lines[i] = f"{env_key}={credential_value}"
                    found = True
                    break
            if not found:
                lines.append(f"{env_key}={credential_value}")
            env_file.write_text("\n".join(lines) + "\n")
            os.chmod(env_file, 0o600)
        else:
            # Escribir archivo dedicado
            cred_file = tenant_path / target_file
            cred_file.write_text(credential_value)
            os.chmod(cred_file, 0o600)

        return json.dumps(
            {
                "success": True,
                "tenant_code": tenant_code,
                "credential_type": credential_type,
                "file": target_file,
                "message": f"Credencial {credential_type} inyectada en {tenant_code}.",
            }
        )

    except OSError as e:
        return json.dumps({"success": False, "error": str(e)})


def update_tenant_config(tenant_code: str, config_updates: str) -> str:
    """Actualiza campos especificos del config.yaml de un tenant.

    Args:
        tenant_code: Codigo del tenant.
        config_updates: JSON string con los campos a actualizar.

    Returns:
        JSON con el resultado.
    """
    tenant_path = Path(settings.tenants_base_path) / tenant_code
    config_file = tenant_path / "config.yaml"

    if not config_file.exists():
        return json.dumps(
            {"success": False, "error": f"config.yaml no existe para {tenant_code}."}
        )

    try:
        import yaml  # noqa: F401 - yaml might not be installed

        updates = json.loads(config_updates)
        existing = yaml.safe_load(config_file.read_text()) or {}
        existing.update(updates)
        config_file.write_text(yaml.dump(existing, default_flow_style=False))

        return json.dumps(
            {
                "success": True,
                "tenant_code": tenant_code,
                "updated_fields": list(updates.keys()),
            }
        )

    except json.JSONDecodeError as e:
        return json.dumps({"success": False, "error": f"JSON invalido: {e}"})
    except ImportError:
        return json.dumps({"success": False, "error": "PyYAML no instalado."})
    except OSError as e:
        return json.dumps({"success": False, "error": str(e)})
