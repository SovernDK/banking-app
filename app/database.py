import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

# The daily sync and the running app may write at the same moment; wait rather than fail.
_BUSY_TIMEOUT_SECONDS = 10

_SCHEMA = """
CREATE TABLE IF NOT EXISTS payments (
    account_key TEXT NOT NULL,
    booked_on TEXT NOT NULL,
    name TEXT,
    payee TEXT,
    amount TEXT NOT NULL,
    currency TEXT NOT NULL,
    payment_method TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS payments_by_account_and_day ON payments (account_key, booked_on);

CREATE TABLE IF NOT EXISTS exchange_rates (
    day TEXT NOT NULL,
    currency TEXT NOT NULL,
    per_euro TEXT NOT NULL,
    PRIMARY KEY (day, currency)
);

CREATE TABLE IF NOT EXISTS exchange_rate_coverage (
    currency TEXT PRIMARY KEY,
    first_day TEXT NOT NULL,
    last_day TEXT NOT NULL,
    checked_at TEXT NOT NULL
);
"""


@contextmanager
def connect(path: Path) -> Iterator[sqlite3.Connection]:
    """A connection whose statements commit together when the block ends, or roll back."""
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=_BUSY_TIMEOUT_SECONDS)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.executescript(_SCHEMA)
        with connection:
            yield connection
    finally:
        connection.close()
