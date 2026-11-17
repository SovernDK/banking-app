import calendar
from collections import defaultdict
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Generic, TypeVar

from app.payments import Payment


class Period(StrEnum):
    LAST_WEEK = "week"
    LAST_MONTH = "month"

    @property
    def days(self) -> int:
        return _PERIOD_DAYS[self]

    @classmethod
    def parse(cls, value: str | None) -> "Period":
        try:
            return cls(value)
        except ValueError:
            return cls.LAST_MONTH


Key = TypeVar("Key")

_PERIOD_DAYS = {Period.LAST_WEEK: 7, Period.LAST_MONTH: 30}
LONGEST_PERIOD = max(Period, key=lambda period: period.days)


def _months_back(day: date, months: int) -> date:
    month_index = day.year * 12 + day.month - 1 - months
    year, month = divmod(month_index, 12)
    last_day = calendar.monthrange(year, month + 1)[1]
    return date(year, month + 1, min(day.day, last_day))


class Comparison(StrEnum):
    """What the current period is compared with: the same days a month or a year earlier."""

    MONTH = "m2m"
    YEAR = "y2y"

    def shift(self, day: date) -> date:
        """The same day back in time; a day the target month lacks becomes its last day."""
        return _months_back(day, _COMPARISON_MONTHS[self])

    @classmethod
    def parse(cls, value: str | None) -> "Comparison":
        try:
            return cls(value)
        except ValueError:
            return cls.MONTH


_COMPARISON_MONTHS = {Comparison.MONTH: 1, Comparison.YEAR: 12}


def history_start(today: date) -> date:
    """The earliest day any period or its comparison can show."""
    earliest_end = min(comparison.shift(today) for comparison in Comparison)
    return earliest_end - timedelta(days=LONGEST_PERIOD.days - 1)


def change(current: Decimal, previous: Decimal) -> Decimal | None:
    """Relative change from `previous`; None when there was nothing to compare with."""
    if previous == 0:
        return None
    return (current - previous) / previous


@dataclass(frozen=True)
class DailySpending:
    day: date
    amount: Decimal


def main_currency(payments: list[Payment]) -> str | None:
    totals: dict[str, Decimal] = defaultdict(Decimal)
    for payment in payments:
        totals[payment.currency] += payment.amount
    return max(totals, key=totals.__getitem__, default=None)


@dataclass(frozen=True)
class Share(Generic[Key]):
    key: Key
    amount: Decimal


def _in_currency(payments: Iterable[Payment], currency: str) -> Iterator[Payment]:
    return (payment for payment in payments if payment.currency == currency)


def _in_period(
    payments: list[Payment], currency: str, period: Period, today: date
) -> Iterator[Payment]:
    first_day = today - timedelta(days=period.days - 1)
    for payment in _in_currency(payments, currency):
        if first_day <= payment.booked_on <= today:
            yield payment


def _shares(payments: Iterable[Payment], key: Callable[[Payment], Key]) -> list[Share[Key]]:
    totals: dict[Key, Decimal] = defaultdict(Decimal)
    for payment in payments:
        totals[key(payment)] += payment.amount
    shares = [Share(key=group, amount=amount) for group, amount in totals.items()]
    return sorted(shares, key=lambda share: share.amount, reverse=True)


def daily_spending(
    payments: list[Payment], currency: str, period: Period, today: date
) -> list[DailySpending]:
    first_day = today - timedelta(days=period.days - 1)
    totals: dict[date, Decimal] = defaultdict(Decimal)
    for payment in _in_period(payments, currency, period, today):
        totals[payment.booked_on] += payment.amount
    return [
        DailySpending(day=day, amount=totals[day])
        for day in (first_day + timedelta(days=offset) for offset in range(period.days))
    ]


def spending_by(
    payments: list[Payment],
    currency: str,
    period: Period,
    today: date,
    key: Callable[[Payment], Key],
) -> list[Share[Key]]:
    """Spending per key, biggest first."""
    return _shares(_in_period(payments, currency, period, today), key)


def all_time_spending_by(
    payments: list[Payment], currency: str, key: Callable[[Payment], Key]
) -> list[Share[Key]]:
    """Spending per key over every payment, biggest first."""
    return _shares(_in_currency(payments, currency), key)


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
