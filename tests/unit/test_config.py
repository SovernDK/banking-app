import pytest
from pydantic import ValidationError

from app.config import Settings


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
