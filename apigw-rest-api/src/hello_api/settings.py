"""Settings for the Hello API."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings for the Hello API.

    Values are read from environment variables automatically.
    """

    app_name: str = "Hello API"
    debug: bool = False

    otel_enabled: bool = True
    otel_service_name: str = "hello-api"
    otel_exporter_otlp_endpoint: str | None = None

    model_config = SettingsConfigDict(case_sensitive=False)
