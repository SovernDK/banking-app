from pathlib import Path

import pytest
from pydantic import ValidationError

from app import config
from app.config import PROJECT_ROOT, Settings


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
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, variable: str
) -> None:
    key_file = tmp_path / "pkeys" / "key.pem"
    key_file.parent.mkdir()
    key_file.touch()
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    monkeypatch.chdir(tmp_path.parent)
    monkeypatch.setenv(variable, "pkeys/key.pem")

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    field = variable.lower()
    assert getattr(settings, field) == key_file


def test_keeps_absolute_key_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    key_file = tmp_path / "key.pem"
    key_file.touch()
    monkeypatch.setenv("ENABLE_BANKING_KEY_PATH", str(key_file))

    assert Settings(_env_file=None).enable_banking_key_path == key_file  # type: ignore[call-arg]


@pytest.mark.parametrize("missing_path", ["pkeys/does-not-exist.pem", "pkeys"])
def test_rejects_key_path_that_is_not_an_existing_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, missing_path: str
) -> None:
    (tmp_path / "pkeys").mkdir()
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    monkeypatch.setenv("ENABLE_BANKING_KEY_PATH", missing_path)

    with pytest.raises(ValidationError, match="key file not found"):
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
