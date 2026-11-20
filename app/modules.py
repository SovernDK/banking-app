"""Builds every module once from the settings; the app, the daily sync and the backup each start
here. It is also the one place that knows how the data directory is laid out."""

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import httpx2

from app.ai_categories.service import AutoCategoriser, build_auto_categoriser
from app.bank_profiles import profile_for
from app.banking.client import EnableBankingClient
from app.banking.history import HistoryStore
from app.banking.service import BankingService
from app.banking.store import BankStore
from app.categories import CategoryStore
from app.config import MissingCredentialsError, Settings
from app.rates.book import RateBook
from app.rates.client import ExchangeRateClient
from app.refresh import Refresher


@dataclass(frozen=True)
class DataFiles:
    """What Yiji stores: the bank connection, the categories, and the database holding the
    spending history and exchange rates."""

    bank: Path
    categories: Path
    database: Path

    @classmethod
    def under(cls, data_dir: Path) -> "DataFiles":
        return cls(
            bank=data_dir / "bank.json",
            categories=data_dir / "categories.json",
            database=data_dir / "yiji.sqlite3",
        )


@dataclass(frozen=True)
class Modules:
    """`bank` and `refresher` are None until Enable Banking credentials are configured, and
    `auto_categoriser` until an Ollama key is."""

    settings: Settings
    files: DataFiles
    bank: BankingService | None
    refresher: Refresher | None
    category_store: CategoryStore
    auto_categoriser: AutoCategoriser | None


def build_modules(settings: Settings) -> Modules:
    files = DataFiles.under(settings.data_dir)
    history = HistoryStore(files.database)
    category_store = CategoryStore(files.categories, settings.starter_categories)
    bank = _build_bank(settings, files, history)
    refresher = None
    if bank is not None:
        rates_http = httpx2.Client(
            base_url=str(settings.exchange_rates_api_url),
            timeout=settings.exchange_rates_timeout_seconds,
        )
        refresher = Refresher(
            bank,
            history,
            RateBook(
                files.database,
                ExchangeRateClient(rates_http),
                settings.exchange_rate_lookback_days,
            ),
            display_currencies=settings.display_currencies,
            max_age=timedelta(minutes=settings.transactions_refresh_minutes),
        )
    return Modules(
        settings=settings,
        files=files,
        bank=bank,
        refresher=refresher,
        category_store=category_store,
        auto_categoriser=build_auto_categoriser(settings, category_store),
    )


def _build_bank(
    settings: Settings, files: DataFiles, history: HistoryStore
) -> BankingService | None:
    try:
        app_id, key_path = settings.enable_banking_credentials()
    except MissingCredentialsError:
        return None
    http = httpx2.Client(
        base_url=str(settings.enable_banking_api_url),
        timeout=settings.enable_banking_timeout_seconds,
    )
    return BankingService(
        client=EnableBankingClient(http=http, app_id=app_id, key_path=key_path),
        store=BankStore(files.bank),
        history=history,
        profile=profile_for(
            settings.enable_banking_aspsp_name, settings.enable_banking_aspsp_country
        ),
        settings=settings,
    )
