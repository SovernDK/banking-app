from datetime import date
from decimal import Decimal

import pytest

from app.ui import format as fmt


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("1234.5"), "1,234.50 PLN"),
        (Decimal("-1234.5"), "-1,234.50 PLN"),
        (Decimal("0"), "0.00 PLN"),
    ],
)
def test_money_shows_two_decimals_grouped_thousands_and_currency(
    value: Decimal, expected: str
) -> None:
    assert fmt.money(value, "PLN") == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [(Decimal(40) / Decimal(3), "13.33"), (Decimal("1234.5"), "1234.50"), (Decimal(0), "0.00")],
)
def test_chart_amount_rounds_to_two_decimals_without_grouping(
    value: Decimal, expected: str
) -> None:
    assert fmt.chart_amount(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [(Decimal("0.125"), "+12.5%"), (Decimal("-0.05"), "-5.0%"), (Decimal("0"), "+0.0%")],
)
def test_pct_always_shows_sign(value: Decimal, expected: str) -> None:
    assert fmt.pct(value) == expected


def test_date_renders_iso_format() -> None:
    assert fmt.date(date(2026, 1, 31)) == "2026-01-31"
