from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="YIJI_", env_file=".env", extra="ignore")

    app_title: str = "Yiji"
    storage_secret: str = "change-me"
    host: str = "127.0.0.1"
    port: int = Field(default=8100, ge=1, le=65535)
    reload: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
