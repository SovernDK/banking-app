import secrets
from collections.abc import Callable
from datetime import date, datetime, timedelta
from functools import lru_cache

import httpx2

from app.bank_profiles import BankProfile, profile_for
from app.banking.client import (
    BankRequestRejectedError,
    BankSessionExpiredError,
    EnableBankingClient,
)
from app.banking.history import HistoryStore
from app.banking.models import Transaction
from app.banking.state import new_state, nonce_of
from app.banking.store import STORE_FILENAME, BankStore, StoredSession, StoredState
from app.config import MissingCredentialsError, Settings, get_settings
from app.database import DATABASE_FILENAME
from app.spending import LONGEST_PERIOD, history_start


class InvalidStateError(Exception):
    pass


class NotConnectedError(Exception):
    pass


def local_now() -> datetime:
    return datetime.now().astimezone()


class BankingService:
    def __init__(
        self,
        client: EnableBankingClient,
        store: BankStore,
        history: HistoryStore,
        profile: BankProfile,
        settings: Settings,
        now: Callable[[], datetime] = local_now,
    ) -> None:
        self._client = client
        self._store = store
        self._history = history
        self._profile = profile
        self._settings = settings
        self._now = now
        self._refresh_after = timedelta(minutes=settings.transactions_refresh_minutes)

    def today(self) -> date:
        return self._now().date()

    def connection_ends_on(self) -> date | None:
        """The local day the bank consent ends; None while no bank is connected."""
        session = self._store.load().session
        if session is None:
            return None
        return session.valid_until.astimezone(self._now().tzinfo).date()

    def _live_session(self, stored: StoredState) -> StoredSession:
        session = stored.session
        if session is None or session.valid_until <= self._now():
            raise NotConnectedError
        return session

    def connect_url(self) -> str:
        state, nonce = new_state(self._settings.port, self._settings.public_origin)
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
                account_keys={account.uid: account.key for account in session.accounts},
                own_iban_hashes={
                    iban_hash
                    for account in session.accounts
                    if account.account_id and (iban_hash := account.account_id.iban_hash())
                },
                valid_until=session.access.valid_until,
            )
        )
        self._store.save(stored)

    def refresh(self, *, force: bool = False) -> None:
        """Stores what the bank has booked since the last sync (less the overlap for late
        bookings), or everything it serves after a new connection. Without `force` it does
        nothing while the last sync is recent."""
        stored = self._store.load()
        session = self._live_session(stored)
        now = self._now()
        if not force and stored.synced_within(now, self._refresh_after):
            return
        if stored.synced_at is None:
            wanted_from = history_start(self.today())
        else:
            overlap = timedelta(days=self._settings.sync_overlap_days)
            wanted_from = stored.synced_at.date() - overlap
        try:
            for account_uid in session.account_uids:
                served_from, transactions = self._fetch(account_uid, wanted_from)
                payments = [
                    payment
                    for transaction in transactions
                    if not session.is_own_transfer(transaction)
                    and (payment := self._profile(transaction)) is not None
                ]
                self._history.replace_from(session.account_key(account_uid), served_from, payments)
        except BankSessionExpiredError:
            stored.replace_session(None)
            self._store.save(stored)
            raise
        stored.synced_at = now
        self._store.save(stored)

    def _fetch(self, account_uid: str, wanted_from: date) -> tuple[date, list[Transaction]]:
        """Transactions from `wanted_from`, or from as near it as the bank allows, and the day
        they start from. Banks cap how far back they go (often 90 days), so a refused range is
        retried shorter."""
        today = self.today()
        fallback_days = self._settings.transactions_fallback_history_days
        shorter = {
            history_start(today),
            today - timedelta(days=fallback_days - 1),
            today - timedelta(days=LONGEST_PERIOD.days - 1),
        }
        oldest_first = sorted({wanted_from, *(day for day in shorter if day > wanted_from)})
        for date_from in oldest_first[:-1]:
            try:
                return date_from, self._client.fetch_transactions(account_uid, date_from)
            except BankRequestRejectedError:
                continue
        return oldest_first[-1], self._client.fetch_transactions(account_uid, oldest_first[-1])


@lru_cache
def _build_banking_service() -> BankingService:
    settings = get_settings()
    app_id, key_path = settings.enable_banking_credentials()
    http = httpx2.Client(
        base_url=str(settings.enable_banking_api_url),
        timeout=settings.enable_banking_timeout_seconds,
    )
    client = EnableBankingClient(http=http, app_id=app_id, key_path=key_path)
    database = settings.data_dir / DATABASE_FILENAME
    return BankingService(
        client=client,
        store=BankStore(settings.data_dir / STORE_FILENAME),
        history=HistoryStore(database),
        profile=profile_for(
            settings.enable_banking_aspsp_name, settings.enable_banking_aspsp_country
        ),
        settings=settings,
    )


def find_banking_service() -> BankingService | None:
    try:
        return _build_banking_service()
    except MissingCredentialsError:
        return None
