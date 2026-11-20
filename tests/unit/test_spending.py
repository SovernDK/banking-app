from datetime import date
from decimal import Decimal

import pytest

from app.spending import Comparison, Period, change, history_start

TODAY = date(2026, 11, 15)


def test_period_parses_from_url_value_and_defaults_to_last_month() -> None:
    assert Period.parse("week") is Period.LAST_WEEK
    assert Period.parse("month") is Period.LAST_MONTH
    assert Period.parse("anything-else") is Period.LAST_MONTH
    assert Period.parse(None) is Period.LAST_MONTH


@pytest.mark.parametrize(
    ("comparison", "day", "expected"),
    [
        (Comparison.MONTH, date(2026, 11, 15), date(2026, 10, 15)),
        (Comparison.MONTH, date(2026, 3, 31), date(2026, 2, 28)),
        (Comparison.MONTH, date(2028, 3, 31), date(2028, 2, 29)),
        (Comparison.MONTH, date(2026, 1, 10), date(2025, 12, 10)),
        (Comparison.YEAR, date(2026, 11, 15), date(2025, 11, 15)),
        (Comparison.YEAR, date(2028, 2, 29), date(2027, 2, 28)),
    ],
)
def test_comparison_shifts_a_day_back_clamping_to_the_month_end(
    comparison: Comparison, day: date, expected: date
) -> None:
    assert comparison.shift(day) == expected


def test_comparison_parses_from_url_value_and_defaults_to_month_to_month() -> None:
    assert Comparison.parse("y2y") is Comparison.YEAR
    assert Comparison.parse("m2m") is Comparison.MONTH
    assert Comparison.parse(None) is Comparison.MONTH
    assert Comparison.parse("q2q") is Comparison.MONTH


def test_history_reaches_back_to_the_longest_period_a_year_ago() -> None:
    assert history_start(TODAY) == date(2025, 10, 17)


@pytest.mark.parametrize(
    ("current", "previous", "expected"),
    [("112", "100", Decimal("0.12")), ("50", "100", Decimal("-0.5")), ("10", "0", None)],
)
def test_change_is_the_share_of_the_previous_amount(
    current: str, previous: str, expected: Decimal | None
) -> None:
    assert change(Decimal(current), Decimal(previous)) == expected
