"""Settings for the Hello API."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings for the Hello API.

    Values are read from environment variables automatically.
    """

    app_name: str = "Hello API"
    debug: bool = False

    model_config = SettingsConfigDict(case_sensitive=False)
