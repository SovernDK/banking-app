from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest

from app.categories import CategoryBook
from app.payment_methods import PaymentMethod
from app.payments import Payment
from app.rates.book import ExchangeRates
from app.spending import Comparison, DailySpending, Period
from app.spending_view import (
    ALL,
    UNCATEGORISED,
    CounterpartyTotal,
    Slice,
    SliceKind,
    SpendingFilter,
    SpendingView,
    ViewQuery,
)
from tests.fakes.payments import payment

TODAY = date(2026, 11, 15)
LONG_AGO = date(2000, 1, 1)
# One rate per currency, valid for every day the tests book on.
RATES = ExchangeRates(
    {"PLN": [(LONG_AGO, Decimal("4"))], "JPY": [(LONG_AGO, Decimal("160"))]},
    timedelta(days=36500),
)
NO_RATES = ExchangeRates({}, timedelta(days=7))


def _view(
    payments: list[Payment],
    *,
    rates: ExchangeRates = RATES,
    book: CategoryBook | None = None,
    currency: str | None = None,
    display_currencies: tuple[str, ...] = ("EUR",),
    slice_limit: int = 7,
) -> SpendingView:
    return SpendingView(
        payments,
        rates,
        display_currencies=display_currencies,
        requested_currency=currency,
        book=book or CategoryBook(),
        today=TODAY,
        slice_limit=slice_limit,
    )


def _paid(amount: str = "10", day: date = TODAY, **fields: Any) -> Payment:
    return payment(amount, day, **fields)


def _total(view: SpendingView, query: ViewQuery | None = None) -> Decimal:
    days = view.overview(query or ViewQuery()).days
    return sum((entry.amount for entry in days), Decimal(0))


def _book_with_groceries() -> tuple[CategoryBook, str]:
    book = CategoryBook()
    groceries = book.create("Groceries")
    book.assign("Biedronka", groceries.id)
    return book, groceries.id


def test_needs_at_least_one_payment() -> None:
    with pytest.raises(ValueError):
        _view([])


def test_main_currency_is_the_one_with_the_most_spending_in_value() -> None:
    """5000 JPY is worth less than 100 EUR, though the number is bigger."""
    view = _view([_paid("100"), _paid("5000", currency="JPY")])

    assert view.default_currency == "EUR"
    assert view.currency == "EUR"


def test_without_any_rate_the_main_currency_has_the_most_payments() -> None:
    view = _view(
        [
            _paid("10", currency="PLN"),
            _paid("20", currency="PLN"),
            _paid("50000", currency="HUF"),
        ],
        rates=NO_RATES,
    )

    assert view.default_currency == "PLN"


def test_main_currency_compares_value_of_the_payments_with_a_rate_when_some_lack_one() -> None:
    """A payment with no rate must not decide the main currency, or it changes between visits."""
    view = _view(
        [
            _paid("400", currency="PLN"),
            _paid("1"),
            _paid("1"),
            _paid("50000", currency="HUF"),
        ],
    )

    assert view.default_currency == "PLN"


def test_offers_the_configured_currencies_then_the_rest_and_shows_a_requested_one() -> None:
    payments = [_paid("40", currency="PLN"), _paid("10", currency="JPY")]

    view = _view(payments, currency="EUR", display_currencies=("EUR", "USD"))

    assert view.currencies == ["EUR", "USD", "JPY", "PLN"]
    assert view.currency == "EUR"
    assert _view(payments, currency="XYZ").currency == view.default_currency == "PLN"


def test_converts_every_payment_into_the_shown_currency() -> None:
    view = _view([_paid("40", currency="PLN"), _paid("10")], currency="PLN")

    assert _total(view) == Decimal("80")
    assert [paid.currency for paid in view.payments] == ["PLN", "PLN"]


@pytest.mark.parametrize("period", list(Period))
def test_overview_days_are_zero_filled_and_end_today(period: Period) -> None:
    view = _view([_paid("1", TODAY - timedelta(days=60))])

    days = view.overview(ViewQuery(period=period)).days

    assert len(days) == period.days
    assert days[-1] == DailySpending(day=TODAY, amount=Decimal(0))
    assert all(entry.amount == 0 for entry in days)


def test_overview_sums_each_day_from_the_first_day_of_the_period() -> None:
    first_day = date(2026, 11, 9)
    view = _view(
        [
            _paid("10.50"),
            _paid("4.50"),
            _paid("1", first_day),
            _paid("99", first_day - timedelta(days=1)),
        ]
    )

    days = view.overview(ViewQuery(period=Period.LAST_WEEK)).days

    assert days[0] == DailySpending(day=first_day, amount=Decimal("1"))
    assert days[-1].amount == Decimal("15.00")
    assert sum(entry.amount for entry in days) == Decimal("16.00")


@pytest.mark.parametrize("comparison", list(Comparison))
def test_compared_days_are_the_same_days_shifted_back(comparison: Comparison) -> None:
    then = comparison.shift(TODAY)
    view = _view([_paid("7", then)])

    compared = view.overview(ViewQuery(Period.LAST_WEEK, comparison)).compared_days

    assert compared[-1] == DailySpending(day=then, amount=Decimal("7"))


def test_exchange_rate_note_counts_only_converted_spending_in_the_shown_days() -> None:
    view = _view(
        [
            _paid("80", currency="PLN"),
            _paid("10", TODAY - timedelta(days=10)),
            _paid("10", Comparison.YEAR.shift(TODAY)),
        ],
        currency="PLN",
    )

    assert not view.overview(ViewQuery(Period.LAST_WEEK)).exchanged
    assert view.overview(ViewQuery(Period.LAST_MONTH)).exchanged
    assert view.overview(ViewQuery(Period.LAST_WEEK, Comparison.YEAR)).exchanged


def test_left_out_counts_only_payments_without_a_rate_in_the_shown_days() -> None:
    view = _view(
        [
            _paid("30", currency="PLN"),
            _paid("10", TODAY - timedelta(days=10)),
            _paid("10", TODAY - timedelta(days=100)),
        ],
        rates=NO_RATES,
        currency="PLN",
    )

    assert view.overview(ViewQuery(Period.LAST_WEEK)).left_out == 0
    assert view.overview(ViewQuery(Period.LAST_MONTH)).left_out == 1


FILTERED = [
    _paid("1", payee="Netflix"),
    _paid("2", payee="NETFLIX"),
    _paid("4", payee="Biedronka"),
    _paid("8", method=PaymentMethod.ATM_WITHDRAWAL),
    _paid("16", name="Orlen"),
]


@pytest.mark.parametrize(
    ("spending_filter", "total"),
    [
        (ALL, "31"),
        (SpendingFilter(counterparty="netflix"), "3"),
        (SpendingFilter(counterparty="ATM withdrawal"), "8"),
        (SpendingFilter(counterparty="Spotify"), "0"),
        (SpendingFilter(category_id=UNCATEGORISED), "27"),
    ],
)
def test_filter_narrows_the_overview(spending_filter: SpendingFilter, total: str) -> None:
    book, _ = _book_with_groceries()
    view = _view(FILTERED, book=book)

    assert _total(view, ViewQuery(spending_filter=spending_filter)) == Decimal(total)


def test_category_filter_keeps_names_assigned_to_it_and_names_it() -> None:
    book, groceries = _book_with_groceries()
    view = _view(FILTERED, book=book)

    overview = view.overview(ViewQuery(spending_filter=SpendingFilter(category_id=groceries)))

    assert sum(entry.amount for entry in overview.days) == Decimal("4")
    assert overview.subject == "Groceries"
    assert not overview.uncategorised


@pytest.mark.parametrize(
    ("spending_filter", "subject", "uncategorised"),
    [
        (ALL, None, False),
        (SpendingFilter(counterparty="Orlen"), "Orlen", False),
        (SpendingFilter(category_id=UNCATEGORISED), None, True),
    ],
)
def test_overview_says_what_the_filter_narrows_to(
    spending_filter: SpendingFilter, subject: str | None, uncategorised: bool
) -> None:
    overview = _view(FILTERED).overview(ViewQuery(spending_filter=spending_filter))

    assert (overview.subject, overview.uncategorised) == (subject, uncategorised)


def test_filter_refuses_a_counterparty_and_a_category_at_once() -> None:
    with pytest.raises(ValueError):
        SpendingFilter(counterparty="Netflix", category_id=UNCATEGORISED)


def test_counterparties_cover_all_time_spending_merged_biggest_first() -> None:
    view = _view(
        [
            _paid("5", payee="Netflix"),
            _paid("5", payee="NETFLIX"),
            _paid("30", payee="Orlen"),
            _paid("3", method=PaymentMethod.ATM_WITHDRAWAL),
            _paid("99", date(2020, 1, 1), payee="Landlord"),
        ]
    )

    assert view.counterparties == ["Landlord", "Orlen", "Netflix", "ATM withdrawal"]


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ({}, ViewQuery()),
        (
            {"period": "week", "compare": "y2y"},
            ViewQuery(Period.LAST_WEEK, Comparison.YEAR),
        ),
        ({"period": "decade", "compare": "q2q"}, ViewQuery()),
        (
            {"counterparty": "orlen"},
            ViewQuery(spending_filter=SpendingFilter(counterparty="Orlen")),
        ),
        ({"counterparty": "Spotify"}, ViewQuery()),
        (
            {"category": UNCATEGORISED},
            ViewQuery(spending_filter=SpendingFilter(category_id=UNCATEGORISED)),
        ),
        ({"category": "no-such-id"}, ViewQuery()),
        ({"counterparty": "Orlen", "category": UNCATEGORISED}, ViewQuery()),
    ],
)
def test_parse_reads_url_values_keeping_only_a_known_counterparty_or_category(
    values: dict[str, str], expected: ViewQuery
) -> None:
    assert _view(FILTERED).parse(**values) == expected


def test_parse_accepts_a_known_category_id() -> None:
    book, groceries = _book_with_groceries()

    query = _view(FILTERED, book=book).parse(category=groceries)

    assert query.spending_filter == SpendingFilter(category_id=groceries)


@pytest.mark.parametrize(
    "query",
    [
        ViewQuery(),
        ViewQuery(Period.LAST_WEEK, Comparison.YEAR, SpendingFilter(counterparty="Orlen")),
        ViewQuery(spending_filter=SpendingFilter(category_id=UNCATEGORISED)),
    ],
)
def test_url_reads_back_as_the_same_query(query: ViewQuery) -> None:
    view = _view(FILTERED)

    url = view.url(query)

    assert url.startswith("/?")
    assert view.parse(**dict(pair.split("=") for pair in url[2:].split("&"))) == query


def test_url_names_the_currency_only_when_it_is_not_the_main_one() -> None:
    payments = [_paid("40", currency="PLN"), _paid("1")]
    query = ViewQuery(Period.LAST_WEEK)

    assert _view(payments).url(query) == "/?period=week&compare=m2m"
    assert _view(payments, currency="EUR").url(query) == "/?period=week&compare=m2m&currency=EUR"
    assert _view(payments).url(query, "USD") == "/?period=week&compare=m2m&currency=USD"


def test_checked_drops_a_category_filter_once_the_category_is_deleted() -> None:
    book, groceries = _book_with_groceries()
    view = _view(FILTERED, book=book)
    query = view.parse(category=groceries)
    book.delete(groceries)

    assert view.with_book(book).checked(query) == ViewQuery()
    assert view.checked(view.parse(counterparty="Orlen")) == view.parse(counterparty="Orlen")


def test_breakdown_is_empty_when_nothing_was_spent_in_the_period() -> None:
    view = _view([_paid("5", TODAY - timedelta(days=10))])

    assert view.breakdown(Period.LAST_WEEK) is None
    assert view.breakdown(Period.LAST_MONTH) is not None


def test_counterparty_slices_merge_spellings_and_fold_the_rest_into_other() -> None:
    view = _view(
        [
            _paid("30", payee="Biedronka"),
            _paid("20", payee="BIEDRONKA"),
            _paid("40", payee="Orlen"),
            _paid("30", payee="Netflix"),
            _paid("20", payee="Rent"),
            _paid("99", TODAY - timedelta(days=60), payee="Old"),
        ],
        slice_limit=3,
    )

    breakdown = view.breakdown(Period.LAST_MONTH)

    assert breakdown is not None
    assert breakdown.counterparties == [
        Slice(SliceKind.NAMED, Decimal("50"), name="Biedronka", colour_slot=0),
        Slice(SliceKind.NAMED, Decimal("40"), name="Orlen", colour_slot=1),
        Slice(SliceKind.OTHER, Decimal("50")),
    ]


def test_category_slices_keep_a_place_for_uncategorised_spending() -> None:
    book = CategoryBook()
    for counterparty, name in [("Biedronka", "Groceries"), ("Orlen", "Fuel"), ("Rent", "Home")]:
        book.assign_choice(counterparty, name)
    groceries = book.find_by_name("Groceries")
    assert groceries is not None
    view = _view(
        [
            _paid("50", payee="Biedronka"),
            _paid("40", payee="Orlen"),
            _paid("30", payee="Rent"),
            _paid("10", payee="Netflix"),
        ],
        book=book,
        slice_limit=3,
    )

    breakdown = view.breakdown(Period.LAST_MONTH)

    assert breakdown is not None
    assert breakdown.categories == [
        Slice(SliceKind.NAMED, Decimal("50"), name="Groceries", colour_slot=groceries.colour_slot),
        Slice(SliceKind.OTHER, Decimal("70")),
        Slice(SliceKind.UNCATEGORISED, Decimal("10")),
    ]


def test_spellings_of_a_name_are_one_counterparty_shown_by_its_most_used_spelling() -> None:
    """NETFLIX and Netflix showed as two settings rows sharing one category rule."""
    a_month_ago = TODAY - timedelta(days=40)
    view = _view(
        [
            _paid("20", payee="NETFLIX"),
            _paid("5", a_month_ago, payee="Netflix"),
            _paid("5", a_month_ago, payee=" netflix "),
            _paid("5", a_month_ago, payee="Netflix"),
        ]
    )

    breakdown = view.breakdown(Period.LAST_WEEK)

    assert view.counterparties == ["Netflix"]
    assert breakdown is not None
    assert [part.name for part in breakdown.counterparties] == ["Netflix"]
    assert view.counterparty_totals() == [CounterpartyTotal("Netflix", Decimal("35"), None)]
    assert view.parse(counterparty="NETFLIX").spending_filter.counterparty == "Netflix"


def test_counterparty_totals_cover_all_time_spending_with_categories() -> None:
    book, groceries = _book_with_groceries()
    fuel = book.create("Fuel")
    book.assign_suggested("Orlen", fuel.id)
    view = _view(
        [
            _paid("5", payee="Biedronka"),
            _paid("30", date(2020, 1, 1), name="Orlen"),
            _paid("3", method=PaymentMethod.ATM_WITHDRAWAL),
        ],
        book=book,
    )

    assert view.counterparty_totals() == [
        CounterpartyTotal("Orlen", Decimal("30"), fuel.id, ai_assigned=True),
        CounterpartyTotal("Biedronka", Decimal("5"), groceries),
    ]


def test_counterparty_totals_list_names_spent_on_only_without_a_rate_last_with_no_amount() -> None:
    view = _view([_paid("5", payee="Biedronka"), _paid("900", currency="HUF", payee="Orlen")])

    assert view.counterparty_totals() == [
        CounterpartyTotal("Biedronka", Decimal("5"), None),
        CounterpartyTotal("Orlen", None, None),
    ]
