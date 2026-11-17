import logging
from datetime import datetime, timedelta
from pathlib import Path

from pydantic import BaseModel, ValidationError

from app.json_file import write_atomically

logger = logging.getLogger(__name__)

STORE_FILENAME = "bank.json"


class StoredSession(BaseModel):
    account_uids: list[str]
    account_keys: dict[str, str] = {}
    """Account uid to the key its payments are stored under; uids change with every session."""
    valid_until: datetime

    def account_key(self, account_uid: str) -> str:
        return self.account_keys.get(account_uid, account_uid)


class StoredState(BaseModel):
    pending_nonce: str | None = None
    session: StoredSession | None = None
    synced_at: datetime | None = None

    def synced_within(self, now: datetime, max_age: timedelta) -> bool:
        return self.synced_at is not None and now - self.synced_at < max_age

    def replace_session(self, session: StoredSession | None) -> None:
        """A new connection may reach further back than the last sync, so it fetches it all."""
        self.session = session
        self.synced_at = None


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
