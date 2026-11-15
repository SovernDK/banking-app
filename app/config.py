from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, HttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent

EnableBankingEnvironment = Literal["sandbox", "production"]


LOOPBACK_HOSTS = {"localhost", "127.0.0.1"}


class MissingCredentialsError(ValueError):
    pass


class LocalCallbackError(ValueError):
    pass


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
    ssl_certfile: Path | None = None
    ssl_keyfile: Path | None = None
    data_dir: Path = PROJECT_ROOT / ".yiji"

    enable_banking_environment: EnableBankingEnvironment = "sandbox"
    enable_banking_api_url: HttpUrl = HttpUrl("https://api.enablebanking.com")
    enable_banking_redirect_url: HttpUrl = HttpUrl(
        "https://sovernDK.github.io/yiji-site/callback.html"
    )
    enable_banking_sandbox_redirect_url: HttpUrl = HttpUrl("https://localhost:8100/callback")
    enable_banking_aspsp_name: str = Field(default="Mock ASPSP", min_length=1, max_length=200)
    enable_banking_aspsp_country: str = Field(default="FI", pattern=r"^[A-Z]{2}$")
    enable_banking_consent_days: int = Field(default=90, ge=1, le=180)
    enable_banking_timeout_seconds: float = Field(default=30, gt=0)
    transactions_refresh_minutes: int = Field(default=360, ge=1)

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

    @field_validator(
        "enable_banking_key_path", "enable_banking_sandbox_key_path", "ssl_certfile", "ssl_keyfile"
    )
    @classmethod
    def _resolve_project_file(cls, path: Path | None) -> Path | None:
        if path is None:
            return None
        resolved = path if path.is_absolute() else PROJECT_ROOT / path
        if not resolved.is_file():
            raise ValueError(f"file not found: {resolved}")
        return resolved

    @property
    def active_redirect_url(self) -> HttpUrl:
        if self.enable_banking_environment == "sandbox":
            return self.enable_banking_sandbox_redirect_url
        return self.enable_banking_redirect_url

    def local_callback_path(self) -> str | None:
        """Path to serve the bank callback on when the redirect URL points at this machine."""
        redirect = self.active_redirect_url
        if redirect.host not in LOOPBACK_HOSTS:
            return None
        return redirect.path or "/"

    def check_local_callback(self) -> None:
        redirect = self.active_redirect_url
        if redirect.host not in LOOPBACK_HOSTS:
            return
        if redirect.port != self.port:
            raise LocalCallbackError(
                f"The redirect URL {redirect} is served by this app: set YIJI_PORT={redirect.port}."
            )
        if redirect.scheme == "https" and (self.ssl_certfile is None or self.ssl_keyfile is None):
            raise LocalCallbackError(
                f"The redirect URL {redirect} needs HTTPS: run `uv run python -m app.tls` and set"
                " YIJI_SSL_CERTFILE and YIJI_SSL_KEYFILE."
            )

    def enable_banking_credentials(self) -> tuple[str, Path]:
        if self.enable_banking_environment == "sandbox":
            app_id, key_path = self.enable_banking_sandbox_id, self.enable_banking_sandbox_key_path
        else:
            app_id, key_path = self.enable_banking_app_id, self.enable_banking_key_path
        if app_id is None or key_path is None:
            raise MissingCredentialsError(
                f"Enable Banking {self.enable_banking_environment} app id or key path is not set"
            )
        return app_id, key_path


@lru_cache
def get_settings() -> Settings:
    return Settings()
