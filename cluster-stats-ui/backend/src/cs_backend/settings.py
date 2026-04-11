"""Settings for the Cluster Stats backend."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings for the Cluster Stats backend.

    Values are read from environment variables automatically.
    """

    app_name: str = "Cluster Stats API"
    debug: bool = False
    mimir_base_url: str = "http://localhost:9090"

    model_config = SettingsConfigDict(case_sensitive=False)
