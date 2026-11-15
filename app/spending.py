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
        return 7 if self is Period.LAST_WEEK else 30

    @property
    def label(self) -> str:
        return "Last week" if self is Period.LAST_WEEK else "Last month"

    @classmethod
    def parse(cls, value: str | None) -> "Period":
        try:
            return cls(value)
        except ValueError:
            return cls.LAST_MONTH


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
