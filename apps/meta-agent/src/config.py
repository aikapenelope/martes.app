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

    model_config = {"env_prefix": "", "case_sensitive": False, "extra": "ignore"}


# Singleton de settings
settings = Settings()
