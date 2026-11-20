from pathlib import Path
from typing import Literal

from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from pydantic import Field, HttpUrl, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.categories import CategoryName
from app.i18n import Language
from app.payments import CurrencyCode

PROJECT_ROOT = Path(__file__).resolve().parent.parent

EnableBankingEnvironment = Literal["sandbox", "production"]
Thinking = Literal["off", "low", "medium", "high"]


LOOPBACK_HOSTS = {"localhost", "127.0.0.1"}


class MissingCredentialsError(ValueError):
    pass


class LocalCallbackError(ValueError):
    pass


def load_rsa_private_key(path: Path) -> RSAPrivateKey:
    """Enable Banking signs requests with RS256, so only an unencrypted RSA key will do."""
    problem = f"expected an unencrypted RSA private key in PEM format: {path}"
    try:
        key = load_pem_private_key(path.read_bytes(), password=None)
    except (ValueError, TypeError, UnsupportedAlgorithm) as error:
        raise ValueError(problem) from error
    if not isinstance(key, RSAPrivateKey):
        raise ValueError(problem)
    return key


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="YIJI_",
        env_file=PROJECT_ROOT / ".env",
        env_ignore_empty=True,
        extra="ignore",
    )

    app_title: str = "Yiji"
    default_language: Language = Field(
        default=Language.EN, description="Shown until the viewer picks a language."
    )
    storage_secret: str = "change-me"
    host: str = "127.0.0.1"
    port: int = Field(default=8100, ge=1, le=65535)
    reload: bool = False
    ssl_certfile: Path | None = None
    ssl_keyfile: Path | None = None
    data_dir: Path = PROJECT_ROOT / ".yiji"
    backup_dir: Path = PROJECT_ROOT / ".yiji-backups"
    backup_keep: int = Field(default=14, ge=1, description="Daily backups kept; older are deleted.")
    public_url: HttpUrl | None = Field(
        default=None,
        description="Where Yiji is reached when it runs on a server; the bank callback goes there.",
    )

    enable_banking_environment: EnableBankingEnvironment = "sandbox"
    enable_banking_api_url: HttpUrl = HttpUrl("https://api.enablebanking.com")
    enable_banking_redirect_url: HttpUrl = HttpUrl(
        "https://sovernDK.github.io/yiji-site/callback.html"
    )
    enable_banking_sandbox_redirect_url: HttpUrl = HttpUrl("https://localhost:8100/callback")
    enable_banking_aspsp_name: str = Field(default="Mock ASPSP", min_length=1, max_length=200)
    enable_banking_aspsp_country: str = Field(default="FI", pattern=r"^[A-Z]{2}$")
    enable_banking_consent_days: int = Field(default=90, ge=1, le=180)
    reconnect_warning_days: int = Field(
        default=7,
        ge=1,
        le=180,
        description="Days before the bank connection ends to offer renewal.",
    )
    enable_banking_timeout_seconds: float = Field(default=30, gt=0)
    transactions_refresh_minutes: int = Field(
        default=720,
        ge=1,
        description="PSD2 banks allow about 4 unattended fetches a day; the daily sync uses one.",
    )
    sync_overlap_days: int = Field(
        default=7,
        ge=1,
        le=90,
        description="Days before the last fetch fetched again, for payments the bank books late.",
    )
    transactions_fallback_history_days: int = Field(
        default=90,
        ge=30,
        description="History asked for when the bank refuses a year; PSD2 banks often cap at 90.",
    )
    exchange_rates_api_url: HttpUrl = HttpUrl("https://api.frankfurter.dev/v1")
    exchange_rates_timeout_seconds: float = Field(default=30, gt=0)
    exchange_rate_lookback_days: int = Field(
        default=7,
        ge=1,
        le=31,
        description="How far back a rate may come from; none is published on weekends or holidays.",
    )
    display_currencies: list[CurrencyCode] = Field(
        default=["PLN", "EUR", "USD", "JPY"], min_length=1
    )
    starter_categories: list[CategoryName] = [
        "Groceries",
        "Eating out",
        "Transport",
        "Housing",
        "Shopping",
        "Health",
        "Entertainment",
    ]
    ollama_api_url: HttpUrl = HttpUrl("https://ollama.com")
    ai_category_model: str = Field(
        default="gpt-oss:120b",
        min_length=1,
        max_length=200,
        description="Ollama model that picks categories; it must read Polish payment names.",
    )
    ai_category_thinking: Thinking = Field(
        default="low",
        description="Reasoning effort; picking a category is simple, so little thinking is needed."
        " Use off for models that cannot think.",
    )
    ai_category_timeout_seconds: float = Field(default=120, gt=0)
    ai_category_batch_size: int = Field(
        default=50, ge=1, le=200, description="Counterparties sent to the model per request."
    )
    ai_category_examples: int = Field(
        default=100,
        ge=0,
        le=500,
        description="Categories the user chose, shown to the model as examples to follow.",
    )
    ai_category_titles_per_name: int = Field(
        default=3, ge=0, le=10, description="Payment titles sent with each counterparty name."
    )

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

    ollama_api_key: SecretStr | None = Field(
        default=None,
        min_length=1,
        validation_alias="OLLAMA_API_KEY",
        description="Ollama Cloud key; without one, categories are only assigned by hand.",
    )

    @field_validator("public_url")
    @classmethod
    def _require_bare_https_origin(cls, url: HttpUrl | None) -> HttpUrl | None:
        # The hosted relay forwards to <origin>/api/bank/callback and accepts nothing else.
        if url is not None and (
            url.scheme != "https" or url.path not in (None, "", "/") or url.query
        ):
            raise ValueError("expected a bare https origin such as https://yiji.example.net")
        return url

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

    @field_validator("enable_banking_key_path", "enable_banking_sandbox_key_path")
    @classmethod
    def _require_rsa_key(cls, path: Path | None) -> Path | None:
        if path is not None:
            load_rsa_private_key(path)
        return path

    @property
    def public_origin(self) -> str | None:
        if self.public_url is None:
            return None
        port = f":{self.public_url.port}" if self.public_url.port != 443 else ""
        return f"https://{self.public_url.host}{port}"

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
