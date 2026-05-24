"""Configuracion central del meta-agente martes.app."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Variables de entorno del meta-agente."""

    # Base de datos
    database_url: str = "postgresql+psycopg://martes:martes@localhost:5432/martes"

    # LLM via OpenRouter
    # deepseek/deepseek-v4-flash: 1M ctx, verificado disponible mayo 2026
    # Ref: https://openrouter.ai/deepseek/deepseek-v4-flash
    openrouter_api_key: str = ""
    default_model: str = "deepseek/deepseek-v4-flash"

    # Telegram
    telegram_token: str = ""

    # Guardrail: IDs de Telegram autorizados para hablar al meta-agente.
    # Formato: IDs numéricos separados por coma. Ej: "563825119,987654321"
    # Si está vacío, el bot responde a cualquier usuario (solo para desarrollo).
    # En producción SIEMPRE debe tener al menos el ID del admin.
    # El ID se obtiene hablándole a @userinfobot en Telegram.
    telegram_admin_ids: str = ""

    # Entorno
    app_env: str = "development"

    # Paths
    tenants_base_path: str = "/var/lib/martes/tenants"
    templates_path: str = "/app/infra/templates"

    # Docker
    # v2026.5.16 = Hermes Agent v0.14.0 (release tag en Docker Hub)
    # Los tags de Hermes usan vAÑO.MES.DIA, no semver.
    # Ref: https://github.com/NousResearch/hermes-agent/releases/tag/v2026.5.16
    hermes_image: str = "nousresearch/hermes-agent:v2026.5.16"

    # Object storage — SeaweedFS S3-compatible (corriendo en el mismo stack Docker)
    # El endpoint apunta al servicio 'seaweedfs' por Docker DNS interno.
    # Si storage_endpoint está vacío, los backups quedan solo en disco local (fallback).
    # Ref: https://github.com/seaweedfs/seaweedfs/wiki/Amazon-S3-API
    storage_endpoint: str = "http://seaweedfs:8333"
    storage_access_key: str = ""
    storage_secret_key: str = ""
    storage_bucket: str = "martes-backups"
    # Número de backups a retener por tenant. Los más antiguos se borran automáticamente.
    storage_keep_last: int = 7

    # ---------------------------------------------------------------------------
    # Billing — ciclo de vida de pagos (SaaS)
    #
    # billing_trial_days: días de trial gratis desde la creación del tenant.
    #   Al crear un tenant, paid_until = hoy + billing_trial_days.
    #   Esto inicia el reloj de billing desde el primer día.
    #
    # billing_grace_days: días de gracia DESPUÉS de que vence paid_until antes
    #   de suspender automáticamente. El tenant sigue activo durante la gracia.
    #   Si billing_auto_suspend=False, nunca se suspende automáticamente.
    #
    # billing_alert_days: días ANTES de vencimiento en que se envían alertas.
    #   Ej: [7, 3] → alerta a 7 días y a 3 días del vencimiento.
    #
    # billing_auto_suspend: si True, stop_tenant() automático cuando
    #   paid_until + grace_days < hoy. El admin reactiva con restart_tenant()
    #   después de register_payment().
    # ---------------------------------------------------------------------------
    billing_trial_days: int = 30
    billing_grace_days: int = 3
    billing_auto_suspend: bool = True
    billing_alert_days: str = "7,3"  # Lista separada por comas

    # ---------------------------------------------------------------------------
    # Platform key TTL — expiración automática de la key de plataforma en tenants
    #
    # Al crear un tenant, el meta-agente escribe OPENROUTER_API_KEY (la key de la
    # plataforma) en el .env del tenant para que el bot funcione desde el minuto 0.
    # El cliente debe configurar su propia key durante este período.
    #
    # Hermes recarga .env en CADA turno de conversación, no solo al arrancar:
    # Ref: hermes/gateway/run.py:_reload_runtime_env_preserving_config_authority()
    # Esto garantiza que blanquear la key toma efecto en el siguiente mensaje del
    # cliente SIN necesitar restart del container. Cero downtime.
    #
    # Si el cliente ya configuró su propia key en auth.json (via /model en Hermes),
    # el blankeo de .env no afecta su servicio — Hermes usa auth.json con prioridad.
    # Si no configuró su propia key, el siguiente mensaje retorna error de credencial.
    #
    # platform_key_ttl_hours=0 desactiva la expiración automática.
    # ---------------------------------------------------------------------------
    platform_key_ttl_hours: int = 2

    model_config = {"env_prefix": "", "case_sensitive": False, "extra": "ignore"}


# Singleton de settings
settings = Settings()
