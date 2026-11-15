from datetime import date as date_type
from decimal import Decimal


def money(value: Decimal, currency: str) -> str:
    return f"{value:,.2f} {currency}"


def pct(value: Decimal) -> str:
    return f"{value * 100:+.1f}%"


def date(value: date_type) -> str:
    return value.isoformat()
