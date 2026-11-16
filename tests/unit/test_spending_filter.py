from datetime import date
from typing import Any

import pytest

from app.bank_profiles import generic
from app.banking.models import Transaction
from app.categories import CategoryBook
from app.spending_filter import ALL, UNCATEGORISED, SpendingFilter, counterparty_names
from tests.fakes.enable_banking import debit

DAY = date(2026, 11, 15)


def _debit(amount: str = "10", **fields: Any) -> Transaction:
    return Transaction.model_validate(debit(amount, DAY, **fields))


def _book_with_groceries() -> tuple[CategoryBook, str]:
    book = CategoryBook()
    groceries = book.create("Groceries")
    book.assign("Biedronka", groceries.id)
    return book, groceries.id


def _matching(spending_filter: SpendingFilter, book: CategoryBook | None = None) -> list[int]:
    book = book or _book_with_groceries()[0]
    return [
        index
        for index, transaction in enumerate(TRANSACTIONS)
        if spending_filter.matches(transaction, generic.payment_method, book)
    ]


TRANSACTIONS = [
    _debit(creditor="Netflix"),
    _debit(creditor="NETFLIX "),
    _debit(creditor="Biedronka"),
    _debit(family="CCRD", sub_family="CWDL"),
    _debit(creditor="Orlen"),
]


def test_all_matches_every_transaction() -> None:
    assert _matching(ALL) == [0, 1, 2, 3, 4]


@pytest.mark.parametrize(
    ("counterparty", "expected"),
    [("netflix", [0, 1]), ("ATM withdrawal", [3]), ("Spotify", [])],
)
def test_counterparty_filter_matches_its_name_ignoring_case(
    counterparty: str, expected: list[int]
) -> None:
    assert _matching(SpendingFilter(counterparty=counterparty)) == expected


def test_category_filter_matches_names_assigned_to_it() -> None:
    book, groceries = _book_with_groceries()

    assert _matching(SpendingFilter(category_id=groceries), book) == [2]


def test_uncategorised_filter_matches_unassigned_and_nameless_spending() -> None:
    assert _matching(SpendingFilter(category_id=UNCATEGORISED)) == [0, 1, 3, 4]


def test_filter_refuses_a_counterparty_and_a_category_at_once() -> None:
    with pytest.raises(ValueError):
        SpendingFilter(counterparty="Netflix", category_id=UNCATEGORISED)


def test_counterparty_names_cover_all_time_spending_merged_biggest_first() -> None:
    transactions = [
        _debit("5", creditor="Netflix"),
        _debit("5", creditor="NETFLIX"),
        _debit("30", creditor="Orlen"),
        _debit("3", family="CCRD", sub_family="CWDL"),
        Transaction.model_validate(debit("99", date(2020, 1, 1), creditor="Landlord")),
    ]

    assert counterparty_names(transactions, "EUR", generic.payment_method) == [
        "Landlord",
        "Orlen",
        "Netflix",
        "ATM withdrawal",
    ]


@pytest.mark.parametrize(
    ("counterparty", "category", "expected"),
    [
        (None, None, ALL),
        ("orlen", None, SpendingFilter(counterparty="Orlen")),
        ("Spotify", None, ALL),
        (None, UNCATEGORISED, SpendingFilter(category_id=UNCATEGORISED)),
        (None, "no-such-id", ALL),
        ("Orlen", UNCATEGORISED, ALL),
    ],
)
def test_parse_accepts_only_one_known_counterparty_or_category(
    counterparty: str | None, category: str | None, expected: SpendingFilter
) -> None:
    book, _ = _book_with_groceries()

    assert SpendingFilter.parse(counterparty, category, ["Orlen", "Netflix"], book) == expected


def test_parse_accepts_a_known_category_id() -> None:
    book, groceries = _book_with_groceries()

    assert SpendingFilter.parse(None, groceries, [], book) == SpendingFilter(category_id=groceries)


def test_subject_names_what_the_filter_shows() -> None:
    book, groceries = _book_with_groceries()

    assert ALL.subject(book) is None
    assert SpendingFilter(counterparty="Orlen").subject(book) == "Orlen"
    assert SpendingFilter(category_id=groceries).subject(book) == "Groceries"
    assert SpendingFilter(category_id=UNCATEGORISED).subject(book) == "uncategorised"


@pytest.mark.parametrize(
    ("spending_filter", "expected"),
    [
        (ALL, {}),
        (SpendingFilter(counterparty="Orlen"), {"counterparty": "Orlen"}),
        (SpendingFilter(category_id=UNCATEGORISED), {"category": UNCATEGORISED}),
    ],
)
def test_query_holds_the_one_active_filter(
    spending_filter: SpendingFilter, expected: dict[str, str]
) -> None:
    assert spending_filter.query() == expected
