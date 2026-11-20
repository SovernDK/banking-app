from datetime import date, timedelta
from decimal import Decimal

from app.banking.history import HistoryStore
from app.payments import Payment
from app.rates.book import ExchangeRates, convert_payments
from app.refresh import Refresher
from tests.fakes.exchange_rates import FakeRatesState, daily
from tests.fakes.payments import payment
from tests.unit.conftest import Clock

FRIDAY = date(2026, 11, 13)
SUNDAY = date(2026, 11, 15)


def _store(history: HistoryStore, *payments: Payment) -> None:
    history.replace_from("account", date(2000, 1, 1), payments)


def _rates(history: HistoryStore, refresher: Refresher, *payments: Payment) -> ExchangeRates:
    """The rates after a refresh with `payments` stored."""
    _store(history, *payments)
    return refresher.refresh().rates


def _in(currency: str, rates: ExchangeRates, *payments: Payment) -> list[Decimal]:
    return [paid.amount for paid in convert_payments(payments, currency, rates).payments]


def _ranges(fake_rates: FakeRatesState) -> list[str]:
    return [request.url.path.lstrip("/") for request in fake_rates.requests]


def test_payment_is_converted_at_the_rate_of_its_booking_day(
    history: HistoryStore, refresher: Refresher, fake_rates: FakeRatesState
) -> None:
    fake_rates.rates = {"2026-11-12": {"PLN": "4.00"}, "2026-11-13": {"PLN": "5.00"}}
    paid = payment("40", date(2026, 11, 12), currency="PLN")

    rates = _rates(history, refresher, paid)

    assert _in("EUR", rates, paid) == [Decimal("10")]


def test_weekend_payment_uses_the_rate_published_the_friday_before(
    history: HistoryStore, refresher: Refresher, fake_rates: FakeRatesState
) -> None:
    fake_rates.rates = {FRIDAY.isoformat(): {"PLN": "4.00"}}
    paid = payment("40", SUNDAY, currency="PLN")

    rates = _rates(history, refresher, paid)

    assert _in("EUR", rates, paid) == [Decimal("10")]


def test_converts_between_two_currencies_through_the_euro(
    history: HistoryStore, refresher: Refresher, fake_rates: FakeRatesState
) -> None:
    fake_rates.rates = {FRIDAY.isoformat(): {"PLN": "4.00", "JPY": "160"}}
    paid = payment("40", FRIDAY, currency="PLN")

    rates = _rates(history, refresher, paid)

    assert _in("JPY", rates, paid) == [Decimal("1600")]


def test_payment_in_the_chosen_currency_needs_no_rate(
    history: HistoryStore, refresher: Refresher
) -> None:
    rates = _rates(history, refresher)

    assert _in("PLN", rates, payment("40", FRIDAY, currency="PLN")) == [Decimal("40")]


def test_payment_without_a_rate_near_its_day_is_left_out_and_counted(
    history: HistoryStore, refresher: Refresher, fake_rates: FakeRatesState
) -> None:
    fake_rates.rates = {"2026-10-01": {"PLN": "4.00"}}
    stale, euro = payment("40", FRIDAY, currency="PLN"), payment("3", FRIDAY)
    rates = _rates(history, refresher, stale, euro)

    conversion = convert_payments([stale, euro], "EUR", rates)

    assert [paid.amount for paid in conversion.payments] == [Decimal("3")]
    assert conversion.left_out == [stale]


def test_conversion_tells_which_payments_came_from_another_currency(
    history: HistoryStore, refresher: Refresher, fake_rates: FakeRatesState
) -> None:
    fake_rates.rates = {FRIDAY.isoformat(): {"PLN": "4.00"}}
    zloty, euro = payment("40", FRIDAY, currency="PLN"), payment("3", FRIDAY)
    rates = _rates(history, refresher, zloty, euro)

    conversion = convert_payments([zloty, euro], "EUR", rates)

    assert [paid.amount for paid in conversion.exchanged] == [Decimal("10")]


def test_asks_for_the_payment_and_display_currencies_from_before_the_first_payment(
    history: HistoryStore, refresher: Refresher, fake_rates: FakeRatesState
) -> None:
    _rates(history, refresher, payment("5", FRIDAY, currency="GBP"), payment("5", SUNDAY))

    request = fake_rates.requests[-1]
    assert request.url.path == "/2026-11-06..2026-11-15"
    assert request.query_params["symbols"] == "GBP,JPY,PLN,USD"


def test_days_already_fetched_are_not_fetched_again(
    history: HistoryStore, refresher: Refresher, fake_rates: FakeRatesState, clock: Clock
) -> None:
    fake_rates.rates = daily(date(2026, 11, 1), SUNDAY, PLN="4.00", JPY="160", USD="1.1")
    _store(history, payment("5", FRIDAY))
    refresher.refresh()
    refresher.refresh()

    clock.current += timedelta(hours=2)
    refresher.refresh()

    assert _ranges(fake_rates) == ["2026-11-06..2026-11-15", "2026-11-15..2026-11-15"]


def test_an_earlier_payment_fetches_only_the_days_before_those_already_stored(
    history: HistoryStore, refresher: Refresher, fake_rates: FakeRatesState
) -> None:
    _rates(history, refresher, payment("5", FRIDAY))

    _rates(history, refresher, payment("5", date(2026, 10, 20)), payment("5", FRIDAY))

    assert _ranges(fake_rates)[-1] == "2026-10-13..2026-11-05"


def test_rates_outage_is_reported_and_retried_next_time(
    history: HistoryStore, refresher: Refresher, fake_rates: FakeRatesState
) -> None:
    _store(history, payment("5", FRIDAY))
    fake_rates.failure_status = 503

    assert refresher.refresh().rates_error

    fake_rates.failure_status = None
    fake_rates.rates = {FRIDAY.isoformat(): {"PLN": "4.00"}}
    refreshed = refresher.refresh()
    assert refreshed.rates_error is None
    assert _in("PLN", refreshed.rates, payment("1", FRIDAY)) == [Decimal("4.00")]


def test_rates_that_are_not_positive_are_refused(
    history: HistoryStore, refresher: Refresher, fake_rates: FakeRatesState
) -> None:
    fake_rates.rates = {FRIDAY.isoformat(): {"PLN": "0"}}

    assert refresher.refresh().rates_error is None
    _store(history, payment("5", FRIDAY))
    assert refresher.refresh().rates_error


def test_without_payments_no_rates_are_fetched(
    refresher: Refresher, fake_rates: FakeRatesState
) -> None:
    refresher.refresh()

    assert fake_rates.requests == []
