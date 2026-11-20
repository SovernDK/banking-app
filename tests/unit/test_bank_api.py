import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.bank import CALLBACK_PATH, Complete, create_router
from app.banking.service import InvalidStateError


class RecordingService:
    def __init__(self, *, accept: bool = True) -> None:
        self.accept = accept
        self.completed: list[tuple[str, str]] = []

    def complete(self, code: str, state: str) -> None:
        if not self.accept:
            raise InvalidStateError
        self.completed.append((code, state))


STATE = "8100.abcdefghijklmnop"


def _client(complete: Complete | None, local_callback_path: str | None = None) -> TestClient:
    app = FastAPI()
    app.include_router(create_router(complete, local_callback_path))
    return TestClient(app, follow_redirects=False)


@pytest.fixture
def recording_service() -> RecordingService:
    return RecordingService()


@pytest.fixture
def client(recording_service: RecordingService) -> TestClient:
    return _client(recording_service.complete)


def test_successful_callback_completes_connection_and_returns_to_dashboard(
    client: TestClient, recording_service: RecordingService
) -> None:
    response = client.get(CALLBACK_PATH, params={"code": "abc", "state": STATE})

    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert recording_service.completed == [("abc", STATE)]


@pytest.mark.parametrize(
    ("params", "expected_error"),
    [
        ({"error": "access_denied", "state": STATE}, "access_denied"),
        ({"code": "abc", "state": "<script>"}, "invalid_callback"),
        ({"state": STATE}, "invalid_callback"),
        ({}, "invalid_callback"),
    ],
)
def test_failed_callback_redirects_with_safe_error_code(
    client: TestClient,
    recording_service: RecordingService,
    params: dict[str, str],
    expected_error: str,
) -> None:
    response = client.get(CALLBACK_PATH, params=params)

    assert response.status_code == 303
    assert response.headers["location"] == f"/?bank_error={expected_error}"
    assert recording_service.completed == []


def test_callback_with_unknown_state_is_rejected(
    client: TestClient, recording_service: RecordingService
) -> None:
    recording_service.accept = False

    response = client.get(CALLBACK_PATH, params={"code": "abc", "state": STATE})

    assert response.headers["location"] == "/?bank_error=invalid_state"


def test_callback_without_configured_credentials_reports_not_configured() -> None:
    response = _client(None).get(CALLBACK_PATH, params={"code": "abc", "state": STATE})

    assert response.headers["location"] == "/?bank_error=not_configured"


def test_callback_is_also_served_on_local_redirect_path(
    recording_service: RecordingService,
) -> None:
    response = _client(recording_service.complete, "/callback").get(
        "/callback", params={"code": "abc", "state": STATE}
    )

    assert response.headers["location"] == "/"
    assert recording_service.completed == [("abc", STATE)]
