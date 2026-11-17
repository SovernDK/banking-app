import re
from collections.abc import Callable
from datetime import date, timedelta

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.pages.dashboard_page import DashboardPage
from tests.fakes.enable_banking import debit
from tests.fakes.exchange_rates import daily

pytestmark = pytest.mark.e2e

TODAY = date.today()


@pytest.fixture
def open_dashboard(
    page: Page, fake_bank: Callable[..., None], fake_rates: Callable[..., None]
) -> Callable[..., DashboardPage]:
    """Connects a bank that spent 40 PLN and 10 EUR today, with 4 PLN to the euro unless the
    rates are given."""

    def open_with(query: str = "", **rates: object) -> DashboardPage:
        fake_bank(transactions=[debit("40", TODAY, currency="PLN"), debit("10", TODAY)])
        fake_rates(**(rates or {"rates": daily(TODAY - timedelta(days=10), TODAY, PLN="4")}))
        dashboard = DashboardPage(page)
        dashboard.open()
        dashboard.connect_bank()
        expect(dashboard.spending_chart).to_be_visible()
        if query:
            dashboard.open(query)
        return dashboard

    return open_with


def test_spending_is_shown_in_the_main_currency_with_the_rest_converted(
    open_dashboard: Callable[..., DashboardPage],
) -> None:
    dashboard = open_dashboard()

    expect(dashboard.total).to_have_text("80.00 PLN")
    expect(dashboard.currency_filter.get_by_role("button", name="PLN")).to_have_attribute(
        "aria-pressed", "true"
    )


def test_choosing_a_currency_converts_every_amount_and_keeps_it_in_the_url(
    open_dashboard: Callable[..., DashboardPage],
) -> None:
    dashboard = open_dashboard()

    dashboard.select_currency("EUR")

    expect(dashboard.total).to_have_text("20.00 EUR")
    expect(dashboard.page).to_have_url(re.compile(r"currency=EUR"))
    dashboard.page.reload()
    expect(dashboard.total).to_have_text("20.00 EUR")


def test_unknown_currency_in_the_url_falls_back_to_the_main_currency(
    open_dashboard: Callable[..., DashboardPage],
) -> None:
    dashboard = open_dashboard("?currency=XYZ")

    expect(dashboard.total).to_have_text("80.00 PLN")


def test_payments_without_a_rate_are_left_out_with_a_warning(
    open_dashboard: Callable[..., DashboardPage],
) -> None:
    dashboard = open_dashboard(rates={})

    expect(dashboard.total).to_have_text("40.00 PLN")
    expect(dashboard.rates_warning).to_contain_text("1 payment is left out")


def test_rates_outage_warns_and_still_shows_spending(
    open_dashboard: Callable[..., DashboardPage],
) -> None:
    dashboard = open_dashboard(failure_status=503)

    expect(dashboard.total).to_have_text("40.00 PLN")
    expect(dashboard.rates_warning.first).to_contain_text("could not be updated")
