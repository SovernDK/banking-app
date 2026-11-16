from collections import defaultdict
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Generic, TypeVar

from app.banking.models import Transaction


class Period(StrEnum):
    LAST_WEEK = "week"
    LAST_MONTH = "month"

    @property
    def days(self) -> int:
        return _PERIOD_DAYS[self]

    @property
    def label(self) -> str:
        return _PERIOD_LABELS[self]

    @classmethod
    def parse(cls, value: str | None) -> "Period":
        try:
            return cls(value)
        except ValueError:
            return cls.LAST_MONTH


Key = TypeVar("Key")

_PERIOD_DAYS = {Period.LAST_WEEK: 7, Period.LAST_MONTH: 30}
_PERIOD_LABELS = {Period.LAST_WEEK: "Last week", Period.LAST_MONTH: "Last month"}
LONGEST_PERIOD = max(Period, key=lambda period: period.days)


@dataclass(frozen=True)
class DailySpending:
    day: date
    amount: Decimal


def _is_spending(transaction: Transaction) -> bool:
    return transaction.credit_debit_indicator == "DBIT" and transaction.status not in {
        "CNCL",
        "RJCT",
    }


def main_currency(transactions: list[Transaction]) -> str | None:
    totals: dict[str, Decimal] = defaultdict(Decimal)
    for transaction in filter(_is_spending, transactions):
        amount = transaction.transaction_amount
        totals[amount.currency] += abs(amount.amount)
    return max(totals, key=totals.__getitem__, default=None)


@dataclass(frozen=True)
class Share(Generic[Key]):
    key: Key
    amount: Decimal


def _spending(
    transactions: list[Transaction], currency: str
) -> Iterator[tuple[Transaction, Decimal]]:
    for transaction in filter(_is_spending, transactions):
        amount = transaction.transaction_amount
        if amount.currency == currency:
            # Banks differ on whether debit amounts are signed; the indicator carries the direction.
            yield transaction, abs(amount.amount)


def _spending_in_period(
    transactions: list[Transaction], currency: str, period: Period, today: date
) -> Iterator[tuple[Transaction, date, Decimal]]:
    first_day = today - timedelta(days=period.days - 1)
    for transaction, amount in _spending(transactions, currency):
        spent_on = transaction.spent_on
        if spent_on and first_day <= spent_on <= today:
            yield transaction, spent_on, amount


def _shares(
    spending: Iterable[tuple[Transaction, Decimal]], key: Callable[[Transaction], Key]
) -> list[Share[Key]]:
    totals: dict[Key, Decimal] = defaultdict(Decimal)
    for transaction, amount in spending:
        totals[key(transaction)] += amount
    shares = [Share(key=group, amount=amount) for group, amount in totals.items()]
    return sorted(shares, key=lambda share: share.amount, reverse=True)


def daily_spending(
    transactions: list[Transaction], currency: str, period: Period, today: date
) -> list[DailySpending]:
    first_day = today - timedelta(days=period.days - 1)
    totals: dict[date, Decimal] = defaultdict(Decimal)
    for _, spent_on, amount in _spending_in_period(transactions, currency, period, today):
        totals[spent_on] += amount
    return [
        DailySpending(day=day, amount=totals[day])
        for day in (first_day + timedelta(days=offset) for offset in range(period.days))
    ]


def spending_by(
    transactions: list[Transaction],
    currency: str,
    period: Period,
    today: date,
    key: Callable[[Transaction], Key],
) -> list[Share[Key]]:
    """Spending per key, biggest first."""
    in_period = _spending_in_period(transactions, currency, period, today)
    return _shares(((transaction, amount) for transaction, _, amount in in_period), key)


def all_time_spending_by(
    transactions: list[Transaction], currency: str, key: Callable[[Transaction], Key]
) -> list[Share[Key]]:
    """Spending per key over every transaction, dated or not, biggest first."""
    return _shares(_spending(transactions, currency), key)


def top_shares(shares: list[Share[Key]], limit: int) -> tuple[list[Share[Key]], Decimal]:
    """At most `limit` slices: the biggest shares, plus the total of the rest when not all fit."""
    if len(shares) <= limit:
        return shares, Decimal(0)
    kept = shares[: limit - 1]
    return kept, sum((share.amount for share in shares[limit - 1 :]), Decimal(0))


def merge_spellings(shares: list[Share[str]]) -> list[Share[str]]:
    """Joins names that differ only in case, labelled by the spelling with the most spending."""
    spellings: dict[str, list[Share[str]]] = defaultdict(list)
    for share in shares:
        spellings[share.key.casefold()].append(share)
    merged = [
        Share(
            key=max(group, key=lambda share: share.amount).key,
            amount=sum((share.amount for share in group), Decimal(0)),
        )
        for group in spellings.values()
    ]
    return sorted(merged, key=lambda share: share.amount, reverse=True)
