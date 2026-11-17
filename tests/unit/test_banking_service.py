import json
import sqlite3
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from pydantic import HttpUrl

from app.banking.client import BankApiError, BankSessionExpiredError
from app.banking.service import BankingService, InvalidStateError, NotConnectedError
from app.banking.store import STORE_FILENAME, BankStore
from app.config import Settings
from app.payment_methods import PaymentMethod
from app.payments import Payment
from app.spending_filter import counterparty_names
from tests.fakes.enable_banking import FAKE_CODE, FakeBankState, debit
from tests.unit.conftest import Clock

Connect = Callable[[BankingService], None]


def _date_froms(fake_bank: FakeBankState) -> list[str]:
    return [
        request.query_params["date_from"]
        for request in fake_bank.requests
        if request.url.path.endswith("/transactions")
    ]


def _amounts(service: BankingService) -> list[Decimal]:
    return [payment.amount for payment in service.payments()]


def test_connect_state_carries_local_port_for_the_callback_relay(
    service: BankingService, fake_bank: FakeBankState
) -> None:
    service.connect_url()

    assert fake_bank.auth_bodies[-1]["state"].startswith("8123.")


def test_connect_state_carries_the_public_origin_when_yiji_runs_on_a_server(
    service: BankingService, fake_bank: FakeBankState, settings: Settings
) -> None:
    settings.public_url = HttpUrl("https://yiji.home.net")

    service.connect_url()

    assert fake_bank.auth_bodies[-1]["state"].startswith("aHR0cHM6Ly95aWppLmhvbWUubmV0.")


def test_completing_authorization_connects_and_survives_restart(
    service: BankingService, connect: Connect, store: BankStore
) -> None:
    connect(service)

    assert store.load().session is not None
    service.refresh()
    assert service.payments() == []


def test_rejects_callback_whose_state_was_not_issued_by_this_app(service: BankingService) -> None:
    service.connect_url()

    with pytest.raises(InvalidStateError):
        service.complete(FAKE_CODE, "8123.forged-nonce-value-000000")


def test_state_cannot_be_replayed(service: BankingService) -> None:
    state = parse_qs(urlparse(service.connect_url()).query)["state"][0]
    service.complete(FAKE_CODE, state)

    with pytest.raises(InvalidStateError):
        service.complete(FAKE_CODE, state)


def test_connection_ends_on_the_local_day_the_bank_consent_ends(
    service: BankingService, connect: Connect, fake_bank: FakeBankState
) -> None:
    assert service.connection_ends_on() is None
    fake_bank.session_valid_until = "2026-11-20T23:30:00-02:00"

    connect(service)

    assert service.connection_ends_on() == date(2026, 11, 21)


def test_refresh_requires_a_connection(service: BankingService) -> None:
    with pytest.raises(NotConnectedError):
        service.refresh()


def test_stores_booked_spending_only(
    service: BankingService, connect: Connect, fake_bank: FakeBankState, clock: Clock
) -> None:
    today = clock().date()
    fake_bank.transactions = [
        debit("10", today, creditor="Biedronka", remittance=["Card 1"], family="CCRD"),
        debit("20", today, status="PDNG"),
        debit("30", today, status="CNCL"),
        debit("2500", today, indicator="CRDT", creditor="Employer"),
    ]
    connect(service)

    service.refresh()

    assert service.payments() == [
        Payment(
            name="Card 1",
            payee="Biedronka",
            amount=Decimal("10"),
            currency="EUR",
            booked_on=today,
            payment_method=PaymentMethod.CARD_PAYMENT,
        )
    ]


def test_database_holds_no_bank_data_beyond_the_payment_fields(
    service: BankingService,
    connect: Connect,
    fake_bank: FakeBankState,
    clock: Clock,
    database: Path,
) -> None:
    fake_bank.transactions = [debit("10", clock().date(), creditor="Biedronka")]
    connect(service)

    service.refresh()

    with sqlite3.connect(database) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(payments)")}
    assert columns == {
        "account_key",
        "booked_on",
        "name",
        "payee",
        "amount",
        "currency",
        "payment_method",
    }


def test_bank_is_asked_again_only_after_the_refresh_window(
    service: BankingService, connect: Connect, fake_bank: FakeBankState, clock: Clock
) -> None:
    connect(service)
    fake_bank.transactions = [debit("5", date(2026, 11, 14))]
    service.refresh()

    fake_bank.transactions = [debit("5", date(2026, 11, 14)), debit("7", date(2026, 11, 15))]
    clock.current += timedelta(minutes=59)
    service.refresh()
    assert _amounts(service) == [Decimal("5")]

    clock.current += timedelta(minutes=2)
    service.refresh()
    assert _amounts(service) == [Decimal("7"), Decimal("5")]


def test_first_sync_fetches_history_for_the_longest_period_a_year_ago(
    service: BankingService, connect: Connect, fake_bank: FakeBankState
) -> None:
    connect(service)

    service.refresh()

    assert _date_froms(fake_bank) == ["2025-10-17"]


def test_later_syncs_fetch_from_the_last_sync_less_the_overlap(
    service: BankingService, connect: Connect, fake_bank: FakeBankState, clock: Clock
) -> None:
    connect(service)
    service.refresh()

    clock.current += timedelta(days=3)
    service.refresh(force=True)

    assert _date_froms(fake_bank)[-1] == "2026-11-08"


def test_payments_the_bank_stops_serving_stay_in_the_history(
    service: BankingService, connect: Connect, fake_bank: FakeBankState, clock: Clock
) -> None:
    fake_bank.transactions = [debit("80", date(2026, 6, 1)), debit("5", date(2026, 11, 14))]
    connect(service)
    service.refresh()

    clock.current += timedelta(days=200)
    fake_bank.history_from = "2027-03-01"
    fake_bank.transactions = [debit("9", date(2027, 6, 1))]
    service.refresh(force=True)

    assert _amounts(service) == [Decimal("9"), Decimal("5"), Decimal("80")]


def test_overlapping_syncs_do_not_duplicate_payments(
    service: BankingService, connect: Connect, fake_bank: FakeBankState, clock: Clock
) -> None:
    fake_bank.transactions = [debit("5", date(2026, 11, 14)), debit("5", date(2026, 11, 14))]
    connect(service)
    service.refresh()

    clock.current += timedelta(days=1)
    service.refresh(force=True)

    assert _amounts(service) == [Decimal("5"), Decimal("5")]


def test_a_payment_the_bank_drops_from_a_refetched_window_is_dropped(
    service: BankingService, connect: Connect, fake_bank: FakeBankState, clock: Clock
) -> None:
    fake_bank.transactions = [debit("5", date(2026, 11, 14)), debit("6", date(2026, 11, 15))]
    connect(service)
    service.refresh()

    fake_bank.transactions = [debit("5", date(2026, 11, 14))]
    service.refresh(force=True)

    assert _amounts(service) == [Decimal("5")]


def test_reconnecting_the_same_account_keeps_history_without_duplicates(
    service: BankingService, connect: Connect, fake_bank: FakeBankState
) -> None:
    fake_bank.transactions = [debit("5", date(2026, 11, 14))]
    connect(service)
    service.refresh()

    fake_bank.accounts = [
        {"uid": "uid-of-next-session", "identification_hash": "fake-account-hash"}
    ]
    connect(service)
    service.refresh()

    assert _amounts(service) == [Decimal("5")]


def test_each_account_keeps_its_own_payments(
    service: BankingService, connect: Connect, fake_bank: FakeBankState
) -> None:
    fake_bank.accounts = [{"uid": "current"}, {"uid": "savings"}]
    fake_bank.transactions = [debit("5", date(2026, 11, 14))]
    connect(service)

    service.refresh()

    assert _amounts(service) == [Decimal("5"), Decimal("5")]


def test_transfers_between_connected_accounts_are_not_spending(
    service: BankingService, connect: Connect, fake_bank: FakeBankState
) -> None:
    fake_bank.accounts = [
        {"uid": "current", "account_id": {"iban": "PL61109010140000071219812874"}},
        {"uid": "savings", "account_id": {"iban": "PL27114020040000300201355387"}},
    ]
    fake_bank.transactions = [
        debit("500", date(2026, 11, 14), creditor_iban="PL27 1140 2004 0000 3002 0135 5387"),
        debit("40", date(2026, 11, 14), creditor_iban="PL83101010230000261395100000"),
    ]
    connect(service)

    service.refresh()

    assert _amounts(service) == [Decimal("40"), Decimal("40")]


def test_bank_store_keeps_no_account_numbers(
    service: BankingService, connect: Connect, fake_bank: FakeBankState, tmp_path: Path
) -> None:
    iban = "PL61109010140000071219812874"
    fake_bank.accounts = [{"uid": "current", "account_id": {"iban": iban}}]
    connect(service)

    assert iban not in (tmp_path / STORE_FILENAME).read_text()


def test_store_written_before_payments_were_kept_syncs_the_full_history(
    service: BankingService,
    connect: Connect,
    fake_bank: FakeBankState,
    store: BankStore,
    clock: Clock,
    tmp_path: Path,
) -> None:
    """Older versions cached raw transactions in bank.json, marked with `fetched_at`."""
    connect(service)
    legacy = store.load().model_dump(mode="json", exclude={"synced_at"})
    legacy |= {"fetched_at": clock().isoformat(), "transactions": [], "cache_version": 2}
    (tmp_path / STORE_FILENAME).write_text(json.dumps(legacy))
    fake_bank.transactions = [debit("5", date(2026, 11, 14))]

    service.refresh()

    assert _amounts(service) == [Decimal("5")]


@pytest.mark.parametrize(
    ("history_from", "served_from"),
    [("2026-08-01", "2026-08-18"), ("2026-10-01", "2026-10-17")],
)
def test_bank_refusing_long_history_is_asked_for_shorter_ranges(
    service: BankingService,
    connect: Connect,
    fake_bank: FakeBankState,
    history_from: str,
    served_from: str,
) -> None:
    connect(service)
    fake_bank.history_from = history_from
    fake_bank.transactions = [debit("5", date(2026, 11, 14))]

    service.refresh()

    assert _amounts(service) == [Decimal("5")]
    assert _date_froms(fake_bank)[-1] == served_from


def test_expired_bank_session_disconnects_but_keeps_the_history(
    service: BankingService, connect: Connect, fake_bank: FakeBankState, clock: Clock
) -> None:
    fake_bank.transactions = [debit("5", date(2026, 11, 14))]
    connect(service)
    service.refresh()
    fake_bank.session_expired = True
    clock.current += timedelta(days=1)

    with pytest.raises(BankSessionExpiredError):
        service.refresh()
    with pytest.raises(NotConnectedError):
        service.refresh()
    assert _amounts(service) == [Decimal("5")]


def test_bank_refusal_that_is_not_about_the_session_keeps_the_connection(
    service: BankingService, connect: Connect, fake_bank: FakeBankState
) -> None:
    connect(service)
    fake_bank.failure_status = 401

    with pytest.raises(BankApiError) as raised:
        service.refresh()
    assert not isinstance(raised.value, BankSessionExpiredError)

    fake_bank.failure_status = None
    service.refresh()


def test_session_past_valid_until_is_not_connected(
    service: BankingService, connect: Connect, clock: Clock
) -> None:
    connect(service)

    clock.current = datetime(2100, 1, 1, tzinfo=UTC)

    with pytest.raises(NotConnectedError):
        service.refresh()


def test_corrupt_store_file_starts_disconnected(tmp_path: Path) -> None:
    path = tmp_path / STORE_FILENAME
    path.write_text("{not json")

    assert BankStore(path).load().session is None


def test_history_lists_the_newest_payments_first_so_their_spelling_names_ties(
    service: BankingService, connect: Connect, fake_bank: FakeBankState
) -> None:
    fake_bank.transactions = [
        debit("15", date(2026, 11, 1), creditor="NETFLIX"),
        debit("15", date(2026, 11, 14), creditor="Netflix"),
    ]
    connect(service)
    service.refresh()

    assert counterparty_names(service.payments(), "EUR") == ["Netflix"]
