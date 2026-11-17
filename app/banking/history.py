import logging
from collections.abc import Iterable
from datetime import date
from pathlib import Path

from pydantic import ValidationError

from app.database import connect
from app.payments import Payment

logger = logging.getLogger(__name__)


class HistoryStore:
    """Every payment ever fetched, kept after the bank stops serving it."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def replace_from(self, account_key: str, date_from: date, payments: Iterable[Payment]) -> None:
        """Swaps the account's payments from `date_from` on for what the bank just served.

        Banks often send no stable transaction id, so a re-fetched window replaces the stored
        one instead of being matched payment by payment; payments before it stay untouched."""
        rows = [
            (
                account_key,
                payment.booked_on.isoformat(),
                payment.name,
                payment.payee,
                str(payment.amount),
                payment.currency,
                payment.payment_method.value,
            )
            for payment in payments
            if payment.booked_on >= date_from
        ]
        with connect(self._path) as connection:
            connection.execute(
                "DELETE FROM payments WHERE account_key = ? AND booked_on >= ?",
                (account_key, date_from.isoformat()),
            )
            connection.executemany(
                "INSERT INTO payments"
                " (account_key, booked_on, name, payee, amount, currency, payment_method)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                rows,
            )

    def payments(self) -> list[Payment]:
        """Newest first, so where two spellings of a name tie, the latest one labels both."""
        with connect(self._path) as connection:
            rows = connection.execute(
                "SELECT name, payee, amount, currency, booked_on, payment_method"
                " FROM payments ORDER BY booked_on DESC, rowid"
            ).fetchall()
        payments: list[Payment] = []
        for row in rows:
            try:
                payments.append(Payment.model_validate(dict(row)))
            except ValidationError:
                logger.warning("Skipping an unreadable stored payment in %s", self._path)
        return payments
