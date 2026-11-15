import logging
from datetime import datetime, timedelta
from pathlib import Path

from pydantic import BaseModel, ValidationError

from app.banking.models import Transaction
from app.json_file import write_atomically

logger = logging.getLogger(__name__)

STORE_FILENAME = "bank.json"

# Bump whenever Transaction keeps more bank fields: rows cached by an older model lack them and
# would stay incomplete until the refresh window ran out.
TRANSACTIONS_CACHE_VERSION = 1


class StoredSession(BaseModel):
    account_uids: list[str]
    valid_until: datetime


class StoredState(BaseModel):
    pending_nonce: str | None = None
    session: StoredSession | None = None
    transactions: list[Transaction] = []
    fetched_at: datetime | None = None
    cache_version: int = 0

    def has_fresh_cache(self, now: datetime, max_age: timedelta) -> bool:
        return (
            self.fetched_at is not None
            and self.cache_version == TRANSACTIONS_CACHE_VERSION
            and now - self.fetched_at < max_age
        )

    def cache_transactions(self, transactions: list[Transaction], fetched_at: datetime) -> None:
        self.transactions = transactions
        self.fetched_at = fetched_at
        self.cache_version = TRANSACTIONS_CACHE_VERSION

    def replace_session(self, session: StoredSession | None) -> None:
        self.session = session
        self.transactions = []
        self.fetched_at = None


class BankStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> StoredState:
        try:
            return StoredState.model_validate_json(self._path.read_bytes())
        except FileNotFoundError:
            return StoredState()
        except ValidationError:
            logger.warning("Ignoring unreadable bank store at %s", self._path)
            return StoredState()

    def save(self, state: StoredState) -> None:
        write_atomically(self._path, state.model_dump_json())
