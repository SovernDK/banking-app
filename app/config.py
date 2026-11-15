from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="YIJI_",
        env_file=PROJECT_ROOT / ".env",
        env_ignore_empty=True,
        extra="ignore",
    )

    app_title: str = "Yiji"
    storage_secret: str = "change-me"
    host: str = "127.0.0.1"
    port: int = Field(default=8100, ge=1, le=65535)
    reload: bool = False

    enable_banking_app_id: str | None = Field(
        default=None, min_length=1, validation_alias="ENABLE_BANKING_APP_ID"
    )
    enable_banking_key_path: Path | None = Field(
        default=None, validation_alias="ENABLE_BANKING_KEY_PATH"
    )
    enable_banking_sandbox_id: str | None = Field(
        default=None, min_length=1, validation_alias="ENABLE_BANKING_SANDBOX_ID"
    )
    enable_banking_sandbox_key_path: Path | None = Field(
        default=None, validation_alias="ENABLE_BANKING_SANDBOX_KEY_PATH"
    )

    @field_validator("enable_banking_key_path", "enable_banking_sandbox_key_path")
    @classmethod
    def _resolve_key_path(cls, key_path: Path | None) -> Path | None:
        if key_path is None:
            return None
        resolved = key_path if key_path.is_absolute() else PROJECT_ROOT / key_path
        if not resolved.is_file():
            raise ValueError(f"key file not found: {resolved}")
        return resolved


@lru_cache
def get_settings() -> Settings:
    return Settings()
