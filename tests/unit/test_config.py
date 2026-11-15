from collections.abc import Callable
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from cryptography.hazmat.primitives.asymmetric.types import PrivateKeyTypes
from cryptography.hazmat.primitives.serialization import (
    BestAvailableEncryption,
    Encoding,
    KeySerializationEncryption,
    NoEncryption,
    PrivateFormat,
)
from pydantic import ValidationError

from app import config
from app.config import PROJECT_ROOT, LocalCallbackError, MissingCredentialsError, Settings
from app.tls import write_private_key


def test_port_defaults_to_8100(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("YIJI_PORT", raising=False)

    assert Settings(_env_file=None).port == 8100  # type: ignore[call-arg]


def test_port_is_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YIJI_PORT", "9000")

    assert Settings(_env_file=None).port == 9000  # type: ignore[call-arg]


@pytest.mark.parametrize("invalid_port", ["0", "65536", "-1", "abc"])
def test_rejects_out_of_range_or_non_numeric_port(
    monkeypatch: pytest.MonkeyPatch, invalid_port: str
) -> None:
    monkeypatch.setenv("YIJI_PORT", invalid_port)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_env_file_is_read_from_project_root_regardless_of_working_directory() -> None:
    assert (PROJECT_ROOT / "pyproject.toml").is_file()
    assert Settings.model_config.get("env_file") == PROJECT_ROOT / ".env"


def test_reads_enable_banking_ids_from_unprefixed_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENABLE_BANKING_APP_ID", "app-123")
    monkeypatch.setenv("ENABLE_BANKING_SANDBOX_ID", "sandbox-456")

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.enable_banking_app_id == "app-123"
    assert settings.enable_banking_sandbox_id == "sandbox-456"


@pytest.mark.parametrize("variable", ["ENABLE_BANKING_KEY_PATH", "ENABLE_BANKING_SANDBOX_KEY_PATH"])
def test_resolves_relative_key_path_against_project_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, private_key: RSAPrivateKey, variable: str
) -> None:
    key_file = tmp_path / "pkeys" / "key.pem"
    write_private_key(private_key, key_file)
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    monkeypatch.chdir(tmp_path.parent)
    monkeypatch.setenv(variable, "pkeys/key.pem")

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    field = variable.lower()
    assert getattr(settings, field) == key_file


def test_keeps_absolute_key_path(monkeypatch: pytest.MonkeyPatch, key_file: Path) -> None:
    monkeypatch.setenv("ENABLE_BANKING_KEY_PATH", str(key_file))

    assert Settings(_env_file=None).enable_banking_key_path == key_file  # type: ignore[call-arg]


@pytest.mark.parametrize("missing_path", ["pkeys/does-not-exist.pem", "pkeys"])
def test_rejects_key_path_that_is_not_an_existing_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, missing_path: str
) -> None:
    (tmp_path / "pkeys").mkdir()
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    monkeypatch.setenv("ENABLE_BANKING_KEY_PATH", missing_path)

    with pytest.raises(ValidationError, match="file not found"):
        Settings(_env_file=None)  # type: ignore[call-arg]


def _pem(key: PrivateKeyTypes, encryption: KeySerializationEncryption) -> bytes:
    return key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, encryption)


@pytest.mark.parametrize(
    "key_contents",
    [
        pytest.param(lambda rsa_key: b"not a key\n", id="not-pem"),
        pytest.param(
            lambda rsa_key: _pem(ec.generate_private_key(ec.SECP256R1()), NoEncryption()),
            id="ec-key",
        ),
        pytest.param(
            lambda rsa_key: _pem(rsa_key, BestAvailableEncryption(b"secret")), id="encrypted"
        ),
    ],
)
@pytest.mark.parametrize("variable", ["ENABLE_BANKING_KEY_PATH", "ENABLE_BANKING_SANDBOX_KEY_PATH"])
def test_rejects_key_file_that_is_not_an_unencrypted_rsa_private_key(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    private_key: RSAPrivateKey,
    key_contents: Callable[[RSAPrivateKey], bytes],
    variable: str,
) -> None:
    """A bad key used to pass startup and then fail every page load with a 500."""
    bad_key = tmp_path / "key.pem"
    bad_key.write_bytes(key_contents(private_key))
    monkeypatch.setenv(variable, str(bad_key))

    with pytest.raises(ValidationError, match="unencrypted RSA private key"):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_treats_empty_enable_banking_values_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable in (
        "ENABLE_BANKING_APP_ID",
        "ENABLE_BANKING_KEY_PATH",
        "ENABLE_BANKING_SANDBOX_ID",
        "ENABLE_BANKING_SANDBOX_KEY_PATH",
    ):
        monkeypatch.setenv(variable, "")

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.enable_banking_app_id is None
    assert settings.enable_banking_key_path is None
    assert settings.enable_banking_sandbox_id is None
    assert settings.enable_banking_sandbox_key_path is None


def test_environment_defaults_to_sandbox(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("YIJI_ENABLE_BANKING_ENVIRONMENT", raising=False)

    assert Settings(_env_file=None).enable_banking_environment == "sandbox"  # type: ignore[call-arg]


@pytest.mark.parametrize(
    ("environment", "expected_app_id"), [("sandbox", "sandbox-456"), ("production", "app-123")]
)
def test_credentials_follow_selected_environment(
    monkeypatch: pytest.MonkeyPatch, key_file: Path, environment: str, expected_app_id: str
) -> None:
    monkeypatch.setenv("YIJI_ENABLE_BANKING_ENVIRONMENT", environment)
    monkeypatch.setenv("ENABLE_BANKING_APP_ID", "app-123")
    monkeypatch.setenv("ENABLE_BANKING_KEY_PATH", str(key_file))
    monkeypatch.setenv("ENABLE_BANKING_SANDBOX_ID", "sandbox-456")
    monkeypatch.setenv("ENABLE_BANKING_SANDBOX_KEY_PATH", str(key_file))

    credentials = Settings(_env_file=None).enable_banking_credentials()  # type: ignore[call-arg]

    assert credentials == (expected_app_id, key_file)


def test_missing_credentials_for_selected_environment_raise_clear_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("YIJI_ENABLE_BANKING_ENVIRONMENT", "production")
    monkeypatch.delenv("ENABLE_BANKING_APP_ID", raising=False)
    monkeypatch.delenv("ENABLE_BANKING_KEY_PATH", raising=False)

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    with pytest.raises(MissingCredentialsError, match="production"):
        settings.enable_banking_credentials()


@pytest.mark.parametrize(
    ("variable", "invalid_value"),
    [
        ("YIJI_ENABLE_BANKING_ENVIRONMENT", "staging"),
        ("YIJI_ENABLE_BANKING_ASPSP_COUNTRY", "fin"),
        ("YIJI_ENABLE_BANKING_CONSENT_DAYS", "181"),
        ("YIJI_ENABLE_BANKING_API_URL", "not a url"),
    ],
)
def test_rejects_invalid_enable_banking_settings(
    monkeypatch: pytest.MonkeyPatch, variable: str, invalid_value: str
) -> None:
    monkeypatch.setenv(variable, invalid_value)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


@pytest.mark.parametrize(
    ("environment", "expected"),
    [
        ("sandbox", "https://localhost:8100/callback"),
        ("production", "https://sovernDK.github.io/yiji-site/callback.html"),
    ],
)
def test_redirect_url_follows_selected_environment(
    monkeypatch: pytest.MonkeyPatch, environment: str, expected: str
) -> None:
    monkeypatch.setenv("YIJI_ENABLE_BANKING_ENVIRONMENT", environment)

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert str(settings.active_redirect_url).lower() == expected.lower()


@pytest.mark.parametrize(
    ("redirect_url", "expected_path"),
    [
        ("https://localhost:8080/callback", "/callback"),
        ("http://127.0.0.1:8100/bank/return", "/bank/return"),
        ("https://sovernDK.github.io/yiji-site/callback.html", None),
    ],
)
def test_local_callback_path_is_set_only_for_loopback_redirects(
    redirect_url: str, expected_path: str | None
) -> None:
    settings = Settings(_env_file=None, enable_banking_sandbox_redirect_url=redirect_url)  # type: ignore[call-arg]

    assert settings.local_callback_path() == expected_path


def test_local_https_callback_requires_matching_port_and_certificate(tmp_path: Path) -> None:
    certificate = tmp_path / "localhost.crt"
    key = tmp_path / "localhost.key"
    certificate.touch()
    key.touch()

    wrong_port = Settings(_env_file=None, port=9000)  # type: ignore[call-arg]
    without_tls = Settings(_env_file=None, port=8100)  # type: ignore[call-arg]
    ready = Settings(_env_file=None, port=8100, ssl_certfile=certificate, ssl_keyfile=key)  # type: ignore[call-arg]

    with pytest.raises(LocalCallbackError, match="YIJI_PORT=8100"):
        wrong_port.check_local_callback()
    with pytest.raises(LocalCallbackError, match="YIJI_SSL_CERTFILE"):
        without_tls.check_local_callback()
    ready.check_local_callback()


def test_hosted_redirect_needs_no_local_server_setup() -> None:
    settings = Settings(_env_file=None, enable_banking_environment="production", port=8100)  # type: ignore[call-arg]

    settings.check_local_callback()
