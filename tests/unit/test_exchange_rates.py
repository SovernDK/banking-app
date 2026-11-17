from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.banking.service import BankingService
from app.payments import Payment
from app.rates.book import convert_payments
from app.rates.client import RatesUnavailableError
from tests.fakes.exchange_rates import FakeRatesState, daily
from tests.fakes.payments import payment
from tests.unit.conftest import Clock

FRIDAY = date(2026, 11, 13)
SUNDAY = date(2026, 11, 15)


def _in(currency: str, service: BankingService, *payments: Payment) -> list[Decimal]:
    converted, _ = convert_payments(payments, currency, service.exchange_rates())
    return [paid.amount for paid in converted]


def _ranges(fake_rates: FakeRatesState) -> list[str]:
    return [request.url.path.lstrip("/") for request in fake_rates.requests]


def test_payment_is_converted_at_the_rate_of_its_booking_day(
    service: BankingService, fake_rates: FakeRatesState
) -> None:
    fake_rates.rates = {"2026-11-12": {"PLN": "4.00"}, "2026-11-13": {"PLN": "5.00"}}
    paid = payment("40", date(2026, 11, 12), currency="PLN")

    service.refresh_rates([paid])

    assert _in("EUR", service, paid) == [Decimal("10")]


def test_weekend_payment_uses_the_rate_published_the_friday_before(
    service: BankingService, fake_rates: FakeRatesState
) -> None:
    fake_rates.rates = {FRIDAY.isoformat(): {"PLN": "4.00"}}
    paid = payment("40", SUNDAY, currency="PLN")

    service.refresh_rates([paid])

    assert _in("EUR", service, paid) == [Decimal("10")]


def test_converts_between_two_currencies_through_the_euro(
    service: BankingService, fake_rates: FakeRatesState
) -> None:
    fake_rates.rates = {FRIDAY.isoformat(): {"PLN": "4.00", "JPY": "160"}}
    paid = payment("40", FRIDAY, currency="PLN")

    service.refresh_rates([paid])

    assert _in("JPY", service, paid) == [Decimal("1600")]


def test_payment_in_the_chosen_currency_needs_no_rate(service: BankingService) -> None:
    assert _in("PLN", service, payment("40", FRIDAY, currency="PLN")) == [Decimal("40")]


def test_payment_without_a_rate_near_its_day_is_left_out_and_counted(
    service: BankingService, fake_rates: FakeRatesState
) -> None:
    fake_rates.rates = {"2026-10-01": {"PLN": "4.00"}}
    stale, euro = payment("40", FRIDAY, currency="PLN"), payment("3", FRIDAY)
    service.refresh_rates([stale, euro])

    converted, skipped = convert_payments([stale, euro], "EUR", service.exchange_rates())

    assert [paid.amount for paid in converted] == [Decimal("3")]
    assert skipped == 1


def test_asks_for_the_payment_and_display_currencies_from_before_the_first_payment(
    service: BankingService, fake_rates: FakeRatesState
) -> None:
    service.refresh_rates([payment("5", FRIDAY, currency="GBP"), payment("5", SUNDAY)])

    request = fake_rates.requests[-1]
    assert request.url.path == "/2026-11-06..2026-11-15"
    assert request.query_params["symbols"] == "GBP,JPY,PLN,USD"


def test_days_already_fetched_are_not_fetched_again(
    service: BankingService, fake_rates: FakeRatesState, clock: Clock
) -> None:
    fake_rates.rates = daily(date(2026, 11, 1), SUNDAY, PLN="4.00", JPY="160", USD="1.1")
    service.refresh_rates([payment("5", FRIDAY)])
    service.refresh_rates([payment("5", FRIDAY)])

    clock.current += timedelta(hours=2)
    service.refresh_rates([payment("5", FRIDAY)])

    assert _ranges(fake_rates) == ["2026-11-06..2026-11-15", "2026-11-15..2026-11-15"]


def test_an_earlier_payment_fetches_only_the_days_before_those_already_stored(
    service: BankingService, fake_rates: FakeRatesState
) -> None:
    service.refresh_rates([payment("5", FRIDAY)])

    service.refresh_rates([payment("5", date(2026, 10, 20)), payment("5", FRIDAY)])

    assert _ranges(fake_rates)[-1] == "2026-10-13..2026-11-05"


def test_rates_outage_is_reported_and_retried_next_time(
    service: BankingService, fake_rates: FakeRatesState
) -> None:
    fake_rates.failure_status = 503

    with pytest.raises(RatesUnavailableError):
        service.refresh_rates([payment("5", FRIDAY)])

    fake_rates.failure_status = None
    fake_rates.rates = {FRIDAY.isoformat(): {"PLN": "4.00"}}
    service.refresh_rates([payment("5", FRIDAY)])
    assert _in("PLN", service, payment("1", FRIDAY)) == [Decimal("4.00")]


def test_rates_that_are_not_positive_are_refused(
    service: BankingService, fake_rates: FakeRatesState
) -> None:
    fake_rates.rates = {FRIDAY.isoformat(): {"PLN": "0"}}

    with pytest.raises(RatesUnavailableError):
        service.refresh_rates([payment("5", FRIDAY)])


def test_without_payments_no_rates_are_fetched(
    service: BankingService, fake_rates: FakeRatesState
) -> None:
    service.refresh_rates([])

    assert fake_rates.requests == []
