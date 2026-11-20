from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.ai_categories.client import OllamaCategoriser
from app.ai_categories.service import AutoCategoriser
from app.bank_profiles import generic
from app.banking.client import EnableBankingClient
from app.banking.history import HistoryStore
from app.banking.service import BankingService
from app.banking.store import STORE_FILENAME, BankStore
from app.categories import CATEGORIES_FILENAME, CategoryStore
from app.config import Settings
from app.database import DATABASE_FILENAME
from app.rates.book import RateBook
from app.rates.client import ExchangeRateClient
from app.tls import generate_private_key, write_private_key
from tests.fakes.enable_banking import FAKE_CODE, FakeBankState, create_fake_enable_banking
from tests.fakes.exchange_rates import FakeRatesState, create_fake_exchange_rates
from tests.fakes.ollama import FakeOllamaState, create_fake_ollama

TEST_APP_ID = "test-app-id"


@pytest.fixture(scope="session")
def private_key() -> RSAPrivateKey:
    return generate_private_key()


@pytest.fixture
def key_file(tmp_path: Path, private_key: RSAPrivateKey) -> Path:
    path = tmp_path / "key.pem"
    write_private_key(private_key, path)
    return path


@pytest.fixture
def fake_enable_banking() -> FastAPI:
    return create_fake_enable_banking()


@pytest.fixture
def fake_bank(fake_enable_banking: FastAPI) -> FakeBankState:
    return fake_enable_banking.state.bank


@pytest.fixture
def bank_client(fake_enable_banking: FastAPI, key_file: Path) -> EnableBankingClient:
    return EnableBankingClient(
        http=TestClient(fake_enable_banking), app_id=TEST_APP_ID, key_path=key_file
    )


@pytest.fixture
def fake_exchange_rates() -> FastAPI:
    return create_fake_exchange_rates()


@pytest.fixture
def fake_rates(fake_exchange_rates: FastAPI) -> FakeRatesState:
    return fake_exchange_rates.state.rates


@pytest.fixture
def rate_client(fake_exchange_rates: FastAPI) -> ExchangeRateClient:
    return ExchangeRateClient(TestClient(fake_exchange_rates))


@pytest.fixture
def fake_ollama_app() -> FastAPI:
    return create_fake_ollama()


@pytest.fixture
def fake_ollama(fake_ollama_app: FastAPI) -> FakeOllamaState:
    return fake_ollama_app.state.ollama


@pytest.fixture
def category_store(tmp_path: Path, settings: Settings) -> CategoryStore:
    return CategoryStore(tmp_path / CATEGORIES_FILENAME, settings.starter_categories)


@pytest.fixture
def auto_categoriser(
    fake_ollama_app: FastAPI, category_store: CategoryStore, settings: Settings
) -> AutoCategoriser:
    return AutoCategoriser(
        OllamaCategoriser(
            TestClient(fake_ollama_app, headers={"Authorization": "Bearer test-key"}),
            settings.ai_category_model,
            settings.ai_category_thinking,
        ),
        category_store,
        batch_size=2,
        max_examples=settings.ai_category_examples,
        titles_per_name=2,
    )


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
def database(tmp_path: Path) -> Path:
    return tmp_path / DATABASE_FILENAME


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, port=8123, transactions_refresh_minutes=60)  # type: ignore[call-arg]


@pytest.fixture
def service(
    bank_client: EnableBankingClient,
    rate_client: ExchangeRateClient,
    store: BankStore,
    database: Path,
    clock: Clock,
    settings: Settings,
) -> BankingService:
    return BankingService(
        client=bank_client,
        store=store,
        history=HistoryStore(database),
        rate_book=RateBook(database, rate_client, settings.exchange_rate_lookback_days),
        profile=generic.to_payment,
        settings=settings,
        now=clock,
    )


@pytest.fixture
def connect() -> Callable[[BankingService], None]:
    """Completes a bank connection the way the bank's redirect back to Yiji does."""

    def complete(service: BankingService) -> None:
        state = parse_qs(urlparse(service.connect_url()).query)["state"][0]
        service.complete(FAKE_CODE, state)

    return complete
