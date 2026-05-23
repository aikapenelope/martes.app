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
    hermes_image: str = "nousresearch/hermes-agent:0.14.0"

    model_config = {"env_prefix": "", "case_sensitive": False, "extra": "ignore"}


# Singleton de settings
settings = Settings()
