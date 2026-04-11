"""Settings for the Cluster Stats backend."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings for the Cluster Stats backend.

    Values are read from environment variables automatically.
    """

    app_name: str = "Cluster Stats API"
    debug: bool = False
    mimir_base_url: str = "http://mimir:8080"
    mimir_tenant_id: str = "anonymous"
    mimir_timeout_seconds: float = 10.0
    api_prefix: str = "/api"
    static_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parent / "static")

    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")
