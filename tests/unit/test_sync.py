from collections.abc import Callable

import pytest

from app.ai_categories.service import AutoCategoriser
from app.banking.history import HistoryStore
from app.banking.service import BankingService
from app.categories import CategoryStore
from app.refresh import Refresher
from app.sync import SyncResult, main, sync
from tests.fakes.enable_banking import FakeBankState, debit
from tests.fakes.exchange_rates import FakeRatesState
from tests.fakes.ollama import FakeOllamaState
from tests.unit.conftest import Clock

Connect = Callable[[BankingService], None]


@pytest.mark.parametrize(
    ("breakage", "expected"),
    [
        ({}, SyncResult.SYNCED),
        ({"session_expired": True}, SyncResult.NEEDS_RECONNECT),
        ({"failure_status": 503}, SyncResult.FAILED),
    ],
)
def test_exit_code_says_whether_the_bank_synced(
    refresher: Refresher,
    service: BankingService,
    connect: Connect,
    fake_bank: FakeBankState,
    breakage: dict[str, object],
    expected: SyncResult,
) -> None:
    connect(service)
    for field, value in breakage.items():
        setattr(fake_bank, field, value)

    assert sync(refresher) is expected


def test_sync_without_a_connection_asks_for_a_reconnect(
    refresher: Refresher,
) -> None:
    assert sync(refresher) is SyncResult.NEEDS_RECONNECT


def test_rates_outage_fails_the_sync(
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

    assert sync(refresher) is SyncResult.FAILED


def test_sync_lets_the_model_categorise_new_counterparties(
    refresher: Refresher,
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

    assert sync(refresher, auto_categoriser) is SyncResult.SYNCED

    category = category_store.load().category_of("Lidl")
    assert category is not None and category.name == "Groceries"


def test_model_outage_leaves_payments_uncategorised_but_the_sync_succeeds(
    history: HistoryStore,
    refresher: Refresher,
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

    assert sync(refresher, auto_categoriser) is SyncResult.SYNCED
    assert category_store.load().category_of("Lidl") is None
    assert len(history.payments()) == 1


def test_sync_without_bank_credentials_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.sync.find_refresher", lambda: None)

    assert main() == SyncResult.FAILED
