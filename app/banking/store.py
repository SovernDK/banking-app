import logging
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ValidationError

from app.banking.models import Transaction

logger = logging.getLogger(__name__)


class StoredSession(BaseModel):
    session_id: str
    account_uids: list[str]
    valid_until: datetime


class StoredState(BaseModel):
    pending_nonce: str | None = None
    session: StoredSession | None = None
    transactions: list[Transaction] = []
    fetched_at: datetime | None = None


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
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(".tmp")
        temporary.write_text(state.model_dump_json())
        temporary.replace(self._path)
