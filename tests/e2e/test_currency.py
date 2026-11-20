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
    """Connects a bank that spent 40 PLN and 10 EUR today unless the transactions are given,
    with 4 PLN to the euro unless the rates are given."""

    def open_with(
        query: str = "", transactions: list[dict[str, object]] | None = None, **rates: object
    ) -> DashboardPage:
        fake_bank(
            transactions=transactions or [debit("40", TODAY, currency="PLN"), debit("10", TODAY)]
        )
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
    """With no PLN rate only the euros can be valued, so they set the main currency."""
    dashboard = open_dashboard(rates={})

    expect(dashboard.total).to_have_text("10.00 EUR")
    expect(dashboard.rates_warning).to_contain_text("1 payment is left out")


def test_left_out_warning_counts_only_payments_in_the_shown_days(
    open_dashboard: Callable[..., DashboardPage],
) -> None:
    """A payment left out ten days ago is no reason to warn about the last week."""
    dashboard = open_dashboard(
        "?period=week",
        transactions=[
            debit("30", TODAY, currency="PLN"),
            debit("50", TODAY, currency="PLN"),
            debit("10", TODAY - timedelta(days=10)),
        ],
        rates=daily(TODAY - timedelta(days=3), TODAY, PLN="4"),
    )

    expect(dashboard.total).to_have_text("80.00 PLN")
    expect(dashboard.rates_warning).to_be_hidden()

    dashboard.select_period("Last month")

    expect(dashboard.rates_warning).to_contain_text("1 payment is left out")


def test_left_out_warning_shown_by_a_category_edit_keeps_the_page_scroll(
    open_dashboard: Callable[..., DashboardPage],
    seed_categories: Callable[[dict[str, list[str]]], None],
) -> None:
    seed_categories({"Groceries": ["Biedronka"]})
    dashboard = open_dashboard(
        transactions=[
            debit("10", TODAY, creditor="Biedronka"),
            debit("90", TODAY, creditor="Orlen", currency="HUF"),
        ],
        rates={},
    )
    dashboard.filter_by_category("Groceries")
    expect(dashboard.rates_warning).to_be_hidden()
    dashboard.categories_legend.scroll_into_view_if_needed()
    scrolled_to = dashboard.scroll_position()
    assert scrolled_to > 0
    dashboard.open_settings()
    dashboard.expand("Counterparties")

    dashboard.assign_category("Orlen", "Groceries")
    expect(dashboard.rates_warning).to_contain_text("1 payment is left out")
    dashboard.close_settings()

    assert dashboard.scroll_position() == scrolled_to


def test_rates_outage_warns_and_still_shows_spending(
    open_dashboard: Callable[..., DashboardPage],
) -> None:
    dashboard = open_dashboard(failure_status=503)

    expect(dashboard.total).to_have_text("10.00 EUR")
    expect(dashboard.rates_warning.first).to_contain_text("could not be updated")


def test_converted_totals_note_that_the_comparison_includes_exchange_rate_changes(
    open_dashboard: Callable[..., DashboardPage],
) -> None:
    dashboard = open_dashboard()

    expect(dashboard.total_note).to_have_text(
        "Converted at each day's rate, so the comparison includes exchange-rate changes."
    )


def test_exchange_rate_note_shows_only_when_the_shown_days_include_converted_spending(
    open_dashboard: Callable[..., DashboardPage],
) -> None:
    """A payment converted ten days ago does not touch the last week or its comparison."""
    dashboard = open_dashboard(
        "?period=week",
        transactions=[
            debit("80", TODAY, currency="PLN"),
            debit("10", TODAY - timedelta(days=10)),
        ],
        rates=daily(TODAY - timedelta(days=20), TODAY, PLN="4"),
    )

    expect(dashboard.total).to_have_text("80.00 PLN")
    expect(dashboard.total_note).to_be_hidden()

    dashboard.select_period("Last month")

    expect(dashboard.total).to_have_text("120.00 PLN")
    expect(dashboard.total_note).to_be_visible()


def test_totals_in_their_own_currency_carry_no_exchange_rate_note(
    open_dashboard: Callable[..., DashboardPage],
) -> None:
    dashboard = open_dashboard(transactions=[debit("40", TODAY, currency="PLN")])

    expect(dashboard.total).to_have_text("40.00 PLN")
    expect(dashboard.total_note).to_be_hidden()

    dashboard.select_currency("EUR")

    expect(dashboard.total).to_have_text("10.00 EUR")
    expect(dashboard.total_note).to_be_visible()
