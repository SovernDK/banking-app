from datetime import date
from decimal import Decimal

import pytest

from app.banking.models import Transaction
from app.spending import (
    DailySpending,
    Period,
    Share,
    daily_spending,
    main_currency,
    spending_by,
    top_shares,
)

TODAY = date(2026, 11, 15)


def _transaction(
    amount: str,
    *,
    indicator: str = "DBIT",
    status: str = "BOOK",
    currency: str = "EUR",
    **dates: date,
) -> Transaction:
    return Transaction.model_validate(
        {
            "transaction_amount": {"amount": amount, "currency": currency},
            "credit_debit_indicator": indicator,
            "status": status,
            **dates,
        }
    )


@pytest.mark.parametrize(
    ("period", "expected_days"), [(Period.LAST_WEEK, 7), (Period.LAST_MONTH, 30)]
)
def test_window_is_zero_filled_and_ends_today(period: Period, expected_days: int) -> None:
    spending = daily_spending([], "EUR", period, TODAY)

    assert len(spending) == expected_days
    assert spending[-1] == DailySpending(day=TODAY, amount=Decimal(0))
    assert all(entry.amount == 0 for entry in spending)


def test_sums_debits_per_day() -> None:
    transactions = [
        _transaction("10.50", booking_date=TODAY),
        _transaction("4.50", booking_date=TODAY),
        _transaction("7", booking_date=date(2026, 11, 14)),
    ]

    spending = daily_spending(transactions, "EUR", Period.LAST_WEEK, TODAY)

    assert spending[-1].amount == Decimal("15.00")
    assert spending[-2].amount == Decimal("7")


def test_ignores_income_and_cancelled_or_rejected_payments() -> None:
    transactions = [
        _transaction("100", indicator="CRDT", booking_date=TODAY),
        _transaction("20", status="RJCT", booking_date=TODAY),
        _transaction("30", status="CNCL", booking_date=TODAY),
        _transaction("5", status="PDNG", transaction_date=TODAY),
    ]

    assert daily_spending(transactions, "EUR", Period.LAST_WEEK, TODAY)[-1].amount == Decimal("5")


def test_counts_absolute_value_of_negative_debit_amounts() -> None:
    transactions = [_transaction("-12", booking_date=TODAY)]

    assert daily_spending(transactions, "EUR", Period.LAST_WEEK, TODAY)[-1].amount == Decimal("12")


def test_includes_first_window_day_and_excludes_the_day_before() -> None:
    first_day = date(2026, 11, 9)
    transactions = [
        _transaction("1", booking_date=first_day),
        _transaction("99", booking_date=date(2026, 11, 8)),
    ]

    spending = daily_spending(transactions, "EUR", Period.LAST_WEEK, TODAY)

    assert spending[0] == DailySpending(day=first_day, amount=Decimal("1"))
    assert sum(entry.amount for entry in spending) == Decimal("1")


def test_falls_back_to_value_date_then_transaction_date() -> None:
    transactions = [
        _transaction("2", value_date=TODAY),
        _transaction("3", transaction_date=TODAY),
        _transaction("50"),
    ]

    assert daily_spending(transactions, "EUR", Period.LAST_WEEK, TODAY)[-1].amount == Decimal("5")


def test_period_parses_from_url_value_and_defaults_to_last_month() -> None:
    assert Period.parse("week") is Period.LAST_WEEK
    assert Period.parse("month") is Period.LAST_MONTH
    assert Period.parse("anything-else") is Period.LAST_MONTH
    assert Period.parse(None) is Period.LAST_MONTH


def test_spending_currency_is_the_one_with_the_largest_spending() -> None:
    transactions = [
        _transaction("10", currency="EUR", booking_date=TODAY),
        _transaction("50", currency="PLN", booking_date=TODAY),
        _transaction("100", indicator="CRDT", currency="USD", booking_date=TODAY),
    ]

    assert main_currency(transactions) == "PLN"
    assert main_currency([]) is None


def test_only_sums_transactions_in_the_requested_currency() -> None:
    transactions = [
        _transaction("10", currency="EUR", booking_date=TODAY),
        _transaction("50", currency="PLN", booking_date=TODAY),
    ]

    assert daily_spending(transactions, "PLN", Period.LAST_WEEK, TODAY)[-1].amount == Decimal("50")


def test_spending_by_groups_the_period_spending_biggest_first() -> None:
    transactions = [
        _transaction("4", booking_date=TODAY),
        _transaction("3", booking_date=TODAY),
        _transaction("30", booking_date=TODAY),
        _transaction("20", status="RJCT", booking_date=TODAY),
        _transaction("12", currency="PLN", booking_date=TODAY),
        _transaction("40", booking_date=date(2026, 10, 1)),
    ]

    shares = spending_by(
        transactions,
        "EUR",
        Period.LAST_WEEK,
        TODAY,
        key=lambda transaction: "big" if transaction.transaction_amount.amount > 5 else "small",
    )

    assert shares == [Share("big", Decimal("30")), Share("small", Decimal("7"))]


@pytest.mark.parametrize(
    ("amounts", "limit", "kept", "rest"),
    [
        ([5, 4, 3], 3, [5, 4, 3], 0),
        ([5, 4, 3, 2, 1], 3, [5, 4], 6),
        ([], 3, [], 0),
    ],
)
def test_top_shares_folds_what_does_not_fit_into_one_rest_total(
    amounts: list[int], limit: int, kept: list[int], rest: int
) -> None:
    shares = [Share(index, Decimal(amount)) for index, amount in enumerate(amounts)]

    top, other = top_shares(shares, limit)

    assert [share.amount for share in top] == kept
    assert other == rest
