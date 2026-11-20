from collections.abc import Callable
from datetime import date, timedelta
from decimal import Decimal

from app.banking.history import HistoryStore
from app.banking.service import BankingService
from app.refresh import BankStatus, Refresher
from tests.fakes.enable_banking import FakeBankState, debit
from tests.fakes.exchange_rates import FakeRatesState, daily
from tests.unit.conftest import Clock

Connect = Callable[[BankingService], None]


def _amounts(history: HistoryStore) -> list[Decimal]:
    return [payment.amount for payment in history.payments()]


def test_refresh_stores_new_payments_and_the_rates_they_need(
    refresher: Refresher,
    service: BankingService,
    connect: Connect,
    fake_bank: FakeBankState,
    fake_rates: FakeRatesState,
    clock: Clock,
) -> None:
    today = clock().date()
    fake_bank.transactions = [debit("40", today, currency="PLN")]
    fake_rates.rates = daily(today - timedelta(days=3), today, PLN="4")
    connect(service)

    refreshed = refresher.refresh()

    assert refreshed.bank is BankStatus.UPDATED
    assert [payment.amount for payment in refreshed.payments] == [Decimal("40")]
    assert refreshed.rates.convert(Decimal("40"), "PLN", "EUR", today) == Decimal("10")
    assert refreshed.rates_error is None
    assert refreshed.bank_error is None
    assert not refreshed.needs_connection


def test_bank_is_asked_again_only_after_the_refresh_window_unless_forced(
    refresher: Refresher,
    service: BankingService,
    connect: Connect,
    fake_bank: FakeBankState,
    clock: Clock,
) -> None:
    connect(service)
    refresher.refresh()
    fake_bank.transactions = [debit("7", clock().date())]
    clock.current += timedelta(minutes=1)

    assert refresher.refresh().payments == []
    assert [payment.amount for payment in refresher.refresh(force=True).payments] == [Decimal("7")]


def test_refresh_after_missed_days_catches_up_from_the_last_one(
    history: HistoryStore,
    refresher: Refresher,
    service: BankingService,
    connect: Connect,
    fake_bank: FakeBankState,
    clock: Clock,
) -> None:
    connect(service)
    refresher.refresh(force=True)
    clock.current += timedelta(days=4)
    fake_bank.transactions = [debit("3", date(2026, 11, 16)), debit("4", date(2026, 11, 19))]

    refresher.refresh(force=True)

    assert fake_bank.requests[-1].query_params["date_from"] == "2026-11-08"
    assert _amounts(history) == [Decimal("4"), Decimal("3")]


def test_without_a_connection_nothing_is_fetched(
    refresher: Refresher,
) -> None:
    refreshed = refresher.refresh()

    assert refreshed.bank is BankStatus.NOT_CONNECTED
    assert refreshed.needs_connection
    assert refreshed.payments == []


def test_expired_session_is_reported_and_forgotten(
    refresher: Refresher, service: BankingService, connect: Connect, fake_bank: FakeBankState
) -> None:
    connect(service)
    fake_bank.session_expired = True

    refreshed = refresher.refresh()

    assert refreshed.bank is BankStatus.SESSION_EXPIRED
    assert refreshed.needs_connection
    assert refresher.refresh().bank is BankStatus.NOT_CONNECTED


def test_bank_outage_keeps_the_stored_payments_and_the_connection(
    refresher: Refresher,
    service: BankingService,
    connect: Connect,
    fake_bank: FakeBankState,
    clock: Clock,
) -> None:
    fake_bank.transactions = [debit("7", clock().date())]
    connect(service)
    refresher.refresh()
    fake_bank.failure_status = 503

    refreshed = refresher.refresh(force=True)

    assert refreshed.bank is BankStatus.BANK_UNAVAILABLE
    assert refreshed.bank_error
    assert [payment.amount for payment in refreshed.payments] == [Decimal("7")]
    assert not refreshed.needs_connection


def test_rates_outage_is_reported_and_keeps_the_payments(
    refresher: Refresher,
    service: BankingService,
    connect: Connect,
    fake_bank: FakeBankState,
    fake_rates: FakeRatesState,
    clock: Clock,
) -> None:
    fake_bank.transactions = [debit("7", clock().date(), currency="PLN")]
    fake_rates.failure_status = 503
    connect(service)

    refreshed = refresher.refresh()

    assert refreshed.bank is BankStatus.UPDATED
    assert refreshed.rates_error
    assert len(refreshed.payments) == 1
