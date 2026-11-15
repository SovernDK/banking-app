import secrets
from collections.abc import Callable
from datetime import date, datetime, timedelta
from functools import lru_cache

import httpx2

from app.banking.client import BankSessionExpiredError, EnableBankingClient
from app.banking.models import Transaction
from app.banking.state import new_state, nonce_of
from app.banking.store import STORE_FILENAME, BankStore, StoredSession, StoredState
from app.config import MissingCredentialsError, Settings, get_settings
from app.spending import LONGEST_PERIOD


class InvalidStateError(Exception):
    pass


class NotConnectedError(Exception):
    pass


def _local_now() -> datetime:
    return datetime.now().astimezone()


class BankingService:
    def __init__(
        self,
        client: EnableBankingClient,
        store: BankStore,
        settings: Settings,
        now: Callable[[], datetime] = _local_now,
    ) -> None:
        self._client = client
        self._store = store
        self._settings = settings
        self._now = now

    def today(self) -> date:
        return self._now().date()

    def _live_session(self, stored: StoredState) -> StoredSession:
        session = stored.session
        if session is None or session.valid_until <= self._now():
            raise NotConnectedError
        return session

    def connect_url(self) -> str:
        state, nonce = new_state(self._settings.port)
        stored = self._store.load()
        stored.pending_nonce = nonce
        self._store.save(stored)
        return self._client.start_authorization(
            aspsp_name=self._settings.enable_banking_aspsp_name,
            aspsp_country=self._settings.enable_banking_aspsp_country,
            redirect_url=str(self._settings.active_redirect_url),
            state=state,
            valid_until=self._now() + timedelta(days=self._settings.enable_banking_consent_days),
        )

    def complete(self, code: str, state: str) -> None:
        stored = self._store.load()
        nonce = nonce_of(state)
        if not stored.pending_nonce or not secrets.compare_digest(nonce, stored.pending_nonce):
            raise InvalidStateError
        stored.pending_nonce = None
        self._store.save(stored)
        session = self._client.create_session(code)
        stored.replace_session(
            StoredSession(
                account_uids=[account.uid for account in session.accounts],
                valid_until=session.access.valid_until,
            )
        )
        self._store.save(stored)

    def transactions(self) -> list[Transaction]:
        stored = self._store.load()
        session = self._live_session(stored)
        refresh_after = timedelta(minutes=self._settings.transactions_refresh_minutes)
        if stored.has_fresh_cache(self._now(), refresh_after):
            return stored.transactions
        date_from = self.today() - timedelta(days=LONGEST_PERIOD.days - 1)
        try:
            transactions = [
                transaction
                for account_uid in session.account_uids
                for transaction in self._client.fetch_transactions(account_uid, date_from)
            ]
        except BankSessionExpiredError:
            stored.replace_session(None)
            self._store.save(stored)
            raise
        stored.cache_transactions(transactions, self._now())
        self._store.save(stored)
        return transactions


@lru_cache
def _build_banking_service() -> BankingService:
    settings = get_settings()
    app_id, key_path = settings.enable_banking_credentials()
    http = httpx2.Client(
        base_url=str(settings.enable_banking_api_url),
        timeout=settings.enable_banking_timeout_seconds,
    )
    client = EnableBankingClient(http=http, app_id=app_id, key_path=key_path)
    return BankingService(
        client=client, store=BankStore(settings.data_dir / STORE_FILENAME), settings=settings
    )


def find_banking_service() -> BankingService | None:
    try:
        return _build_banking_service()
    except MissingCredentialsError:
        return None
