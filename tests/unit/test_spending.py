from datetime import date
from decimal import Decimal

import pytest

from app.spending import (
    Comparison,
    DailySpending,
    Period,
    Share,
    all_time_spending_by,
    change,
    daily_spending,
    history_start,
    main_currency,
    merge_spellings,
    spending_by,
    top_shares,
)
from tests.fakes.payments import payment

TODAY = date(2026, 11, 15)


@pytest.mark.parametrize(
    ("period", "expected_days"), [(Period.LAST_WEEK, 7), (Period.LAST_MONTH, 30)]
)
def test_window_is_zero_filled_and_ends_today(period: Period, expected_days: int) -> None:
    spending = daily_spending([], "EUR", period, TODAY)

    assert len(spending) == expected_days
    assert spending[-1] == DailySpending(day=TODAY, amount=Decimal(0))
    assert all(entry.amount == 0 for entry in spending)


def test_sums_debits_per_day() -> None:
    payments = [
        payment("10.50", TODAY),
        payment("4.50", TODAY),
        payment("7", date(2026, 11, 14)),
    ]

    spending = daily_spending(payments, "EUR", Period.LAST_WEEK, TODAY)

    assert spending[-1].amount == Decimal("15.00")
    assert spending[-2].amount == Decimal("7")


def test_includes_first_window_day_and_excludes_the_day_before() -> None:
    first_day = date(2026, 11, 9)
    payments = [
        payment("1", first_day),
        payment("99", date(2026, 11, 8)),
    ]

    spending = daily_spending(payments, "EUR", Period.LAST_WEEK, TODAY)

    assert spending[0] == DailySpending(day=first_day, amount=Decimal("1"))
    assert sum(entry.amount for entry in spending) == Decimal("1")


def test_period_parses_from_url_value_and_defaults_to_last_month() -> None:
    assert Period.parse("week") is Period.LAST_WEEK
    assert Period.parse("month") is Period.LAST_MONTH
    assert Period.parse("anything-else") is Period.LAST_MONTH
    assert Period.parse(None) is Period.LAST_MONTH


def test_spending_currency_is_the_one_with_the_largest_spending() -> None:
    payments = [
        payment("10", TODAY, currency="EUR"),
        payment("50", TODAY, currency="PLN"),
    ]

    assert main_currency(payments) == "PLN"
    assert main_currency([]) is None


def test_only_sums_payments_in_the_requested_currency() -> None:
    payments = [
        payment("10", TODAY, currency="EUR"),
        payment("50", TODAY, currency="PLN"),
    ]

    assert daily_spending(payments, "PLN", Period.LAST_WEEK, TODAY)[-1].amount == Decimal("50")


def test_spending_by_groups_the_period_spending_biggest_first() -> None:
    payments = [
        payment("4", TODAY),
        payment("3", TODAY),
        payment("30", TODAY),
        payment("12", TODAY, currency="PLN"),
        payment("40", date(2026, 10, 1)),
    ]

    shares = spending_by(
        payments,
        "EUR",
        Period.LAST_WEEK,
        TODAY,
        key=lambda paid: "big" if paid.amount > 5 else "small",
    )

    assert shares == [Share("big", Decimal("30")), Share("small", Decimal("7"))]


def test_all_time_spending_by_groups_every_payment_in_the_currency() -> None:
    payments = [
        payment("4", TODAY),
        payment("40", date(2025, 1, 1)),
        payment("12", TODAY, currency="PLN"),
    ]

    shares = all_time_spending_by(
        payments,
        "EUR",
        key=lambda paid: "big" if paid.amount > 5 else "small",
    )

    assert shares == [Share("big", Decimal("40")), Share("small", Decimal("4"))]


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


def test_merge_spellings_joins_names_differing_only_in_case_under_the_biggest_spelling() -> None:
    shares = [
        Share("Biedronka", Decimal("40")),
        Share("Netflix", Decimal("15")),
        Share("BIEDRONKA", Decimal("30")),
        Share("biedronka", Decimal("2")),
    ]

    assert merge_spellings(shares) == [
        Share("Biedronka", Decimal("72")),
        Share("Netflix", Decimal("15")),
    ]


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
