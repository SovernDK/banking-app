from collections.abc import Callable
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.ai_categories.service import AutoCategoriser
from app.banking.service import BankingService
from app.categories import CategoryStore
from app.sync import SyncResult, main, sync
from tests.fakes.enable_banking import FakeBankState, debit
from tests.fakes.exchange_rates import FakeRatesState
from tests.fakes.ollama import FakeOllamaState
from tests.unit.conftest import Clock

Connect = Callable[[BankingService], None]


def test_daily_sync_stores_new_payments_even_within_the_refresh_window(
    service: BankingService, connect: Connect, fake_bank: FakeBankState, clock: Clock
) -> None:
    connect(service)
    service.refresh()
    fake_bank.transactions = [debit("7", clock().date())]
    clock.current += timedelta(minutes=1)

    assert sync(service) is SyncResult.SYNCED
    assert [payment.amount for payment in service.payments()] == [Decimal("7")]


def test_sync_after_missed_days_catches_up_from_the_last_sync(
    service: BankingService, connect: Connect, fake_bank: FakeBankState, clock: Clock
) -> None:
    connect(service)
    sync(service)
    clock.current += timedelta(days=4)
    fake_bank.transactions = [debit("3", date(2026, 11, 16)), debit("4", date(2026, 11, 19))]

    sync(service)

    assert fake_bank.requests[-1].query_params["date_from"] == "2026-11-08"
    assert [payment.amount for payment in service.payments()] == [Decimal("4"), Decimal("3")]


def test_sync_also_fetches_the_exchange_rates(
    service: BankingService,
    connect: Connect,
    fake_bank: FakeBankState,
    fake_rates: FakeRatesState,
    clock: Clock,
) -> None:
    fake_bank.transactions = [debit("7", clock().date(), currency="PLN")]
    connect(service)

    sync(service)

    assert fake_rates.requests[-1].query_params["symbols"] == "JPY,PLN,USD"


def test_sync_without_a_connection_asks_for_a_reconnect(service: BankingService) -> None:
    assert sync(service) is SyncResult.NEEDS_RECONNECT


def test_sync_with_an_expired_session_asks_for_a_reconnect(
    service: BankingService, connect: Connect, fake_bank: FakeBankState
) -> None:
    connect(service)
    fake_bank.session_expired = True

    assert sync(service) is SyncResult.NEEDS_RECONNECT


def test_bank_outage_fails_the_sync(
    service: BankingService, connect: Connect, fake_bank: FakeBankState
) -> None:
    connect(service)
    fake_bank.failure_status = 503

    assert sync(service) is SyncResult.FAILED


def test_rates_outage_fails_the_sync_but_keeps_the_payments(
    service: BankingService,
    connect: Connect,
    fake_bank: FakeBankState,
    fake_rates: FakeRatesState,
    clock: Clock,
) -> None:
    fake_bank.transactions = [debit("7", clock().date())]
    fake_rates.failure_status = 503
    connect(service)

    assert sync(service) is SyncResult.FAILED
    assert len(service.payments()) == 1


def test_sync_lets_the_model_categorise_new_counterparties(
    service: BankingService,
    connect: Connect,
    fake_bank: FakeBankState,
    fake_ollama: FakeOllamaState,
    auto_categoriser: AutoCategoriser,
    category_store: CategoryStore,
    clock: Clock,
) -> None:
    fake_bank.transactions = [debit("7", clock().date(), creditor="Lidl")]
    fake_ollama.categories = {"Lidl": "Groceries"}
    connect(service)

    assert sync(service, auto_categoriser) is SyncResult.SYNCED

    category = category_store.load().category_of("Lidl")
    assert category is not None and category.name == "Groceries"


def test_model_outage_leaves_payments_uncategorised_but_the_sync_succeeds(
    service: BankingService,
    connect: Connect,
    fake_bank: FakeBankState,
    fake_ollama: FakeOllamaState,
    auto_categoriser: AutoCategoriser,
    category_store: CategoryStore,
    clock: Clock,
) -> None:
    fake_bank.transactions = [debit("7", clock().date(), creditor="Lidl")]
    fake_ollama.failure_status = 503
    connect(service)

    assert sync(service, auto_categoriser) is SyncResult.SYNCED
    assert category_store.load().category_of("Lidl") is None
    assert len(service.payments()) == 1


def test_sync_without_bank_credentials_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.sync.find_banking_service", lambda: None)

    assert main() == SyncResult.FAILED
