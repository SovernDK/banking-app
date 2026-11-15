from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from app.banking.client import BankApiError, BankSessionExpiredError, EnableBankingClient
from app.banking.service import BankingService, InvalidStateError, NotConnectedError
from app.banking.store import STORE_FILENAME, BankStore
from app.config import Settings
from tests.fakes.enable_banking import FAKE_CODE, FakeBankState, debit


class Clock:
    def __init__(self) -> None:
        self.current = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.current


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def store(tmp_path: Path) -> BankStore:
    return BankStore(tmp_path / STORE_FILENAME)


@pytest.fixture
def service(bank_client: EnableBankingClient, store: BankStore, clock: Clock) -> BankingService:
    settings = Settings(_env_file=None, port=8123, transactions_refresh_minutes=60)  # type: ignore[call-arg]
    return BankingService(client=bank_client, store=store, settings=settings, now=clock)


def _state_of(connect_url: str) -> str:
    return parse_qs(urlparse(connect_url).query)["state"][0]


def _connect(service: BankingService) -> None:
    service.complete(FAKE_CODE, _state_of(service.connect_url()))


def test_connect_state_carries_local_port_for_the_callback_relay(
    service: BankingService, fake_bank: FakeBankState
) -> None:
    service.connect_url()

    assert fake_bank.auth_bodies[-1]["state"].startswith("8123.")


def test_completing_authorization_connects_and_survives_restart(
    service: BankingService, bank_client: EnableBankingClient, store: BankStore, clock: Clock
) -> None:
    _connect(service)

    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    restarted = BankingService(client=bank_client, store=store, settings=settings, now=clock)
    assert restarted.transactions() == []


def test_rejects_callback_whose_state_was_not_issued_by_this_app(service: BankingService) -> None:
    service.connect_url()

    with pytest.raises(InvalidStateError):
        service.complete(FAKE_CODE, "8123.forged-nonce-value-000000")


def test_state_cannot_be_replayed(service: BankingService) -> None:
    state = _state_of(service.connect_url())
    service.complete(FAKE_CODE, state)

    with pytest.raises(InvalidStateError):
        service.complete(FAKE_CODE, state)


def test_transactions_require_a_connection(service: BankingService) -> None:
    with pytest.raises(NotConnectedError):
        service.transactions()


def test_transactions_are_cached_within_refresh_window(
    service: BankingService, fake_bank: FakeBankState, clock: Clock
) -> None:
    _connect(service)
    fake_bank.transactions = [debit("5", date(2026, 11, 14))]
    assert len(service.transactions()) == 1

    fake_bank.transactions = [debit("5", date(2026, 11, 14)), debit("5", date(2026, 11, 15))]
    clock.current += timedelta(minutes=59)
    assert len(service.transactions()) == 1

    clock.current += timedelta(minutes=2)
    assert len(service.transactions()) == 2


def test_fetches_the_longest_filter_period(
    service: BankingService, fake_bank: FakeBankState
) -> None:
    _connect(service)

    service.transactions()

    assert fake_bank.requests[-1].query_params["date_from"] == "2026-10-17"


def test_expired_bank_session_disconnects(
    service: BankingService, fake_bank: FakeBankState
) -> None:
    _connect(service)
    fake_bank.session_expired = True

    with pytest.raises(BankSessionExpiredError):
        service.transactions()
    with pytest.raises(NotConnectedError):
        service.transactions()


def test_bank_refusal_that_is_not_about_the_session_keeps_the_connection(
    service: BankingService, fake_bank: FakeBankState
) -> None:
    _connect(service)
    fake_bank.failure_status = 401

    with pytest.raises(BankApiError) as raised:
        service.transactions()
    assert not isinstance(raised.value, BankSessionExpiredError)

    fake_bank.failure_status = None
    assert service.transactions() == []


def test_session_past_valid_until_is_not_connected(service: BankingService, clock: Clock) -> None:
    _connect(service)

    clock.current = datetime(2100, 1, 1, tzinfo=UTC)

    with pytest.raises(NotConnectedError):
        service.transactions()


def test_corrupt_store_file_starts_disconnected(tmp_path: Path) -> None:
    path = tmp_path / STORE_FILENAME
    path.write_text("{not json")

    assert BankStore(path).load().session is None
