from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from enum import StrEnum

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


def daily_spending(
    transactions: list[Transaction], currency: str, period: Period, today: date
) -> list[DailySpending]:
    first_day = today - timedelta(days=period.days - 1)
    totals: dict[date, Decimal] = defaultdict(Decimal)
    for transaction in filter(_is_spending, transactions):
        spent_on = transaction.spent_on
        amount = transaction.transaction_amount
        if spent_on and first_day <= spent_on <= today and amount.currency == currency:
            # Banks differ on whether debit amounts are signed; the indicator carries the direction.
            totals[spent_on] += abs(amount.amount)
    return [
        DailySpending(day=day, amount=totals[day])
        for day in (first_day + timedelta(days=offset) for offset in range(period.days))
    ]
