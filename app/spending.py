import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from enum import StrEnum


class Period(StrEnum):
    LAST_WEEK = "week"
    LAST_MONTH = "month"

    @property
    def days(self) -> int:
        return _PERIOD_DAYS[self]

    def first_day(self, last_day: date) -> date:
        return last_day - timedelta(days=self.days - 1)

    @classmethod
    def parse(cls, value: str | None) -> "Period":
        try:
            return cls(value)
        except ValueError:
            return cls.LAST_MONTH


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
