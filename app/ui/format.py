from datetime import date as date_type
from decimal import Decimal


def money(value: Decimal, currency: str) -> str:
    return f"{value:,.2f} {currency}"


def chart_amount(value: Decimal) -> str:
    """Two decimals without grouping: ECharts reads it as a number and shows it as given."""
    return f"{value:.2f}"


def pct(value: Decimal) -> str:
    return f"{value * 100:+.1f}%"


def date(value: date_type) -> str:
    return value.isoformat()
