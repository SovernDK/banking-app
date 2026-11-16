from collections.abc import Callable
from datetime import date, timedelta

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.pages.dashboard_page import DashboardPage
from tests.fakes.enable_banking import debit

pytestmark = pytest.mark.e2e


def _days_ago(days: int) -> date:
    return date.today() - timedelta(days=days)


@pytest.fixture
def dashboard(page: Page, fake_bank: Callable[..., None]) -> DashboardPage:
    fake_bank(
        transactions=[
            debit("40", _days_ago(1), creditor="Biedronka"),
            debit("2", _days_ago(2), creditor="BIEDRONKA "),
            debit("100", _days_ago(3), family="CCRD", sub_family="CWDL"),
            debit("25", _days_ago(20), creditor="Landlord", family="ICDT"),
        ]
    )
    dashboard = DashboardPage(page)
    dashboard.open()
    dashboard.connect_bank()
    expect(dashboard.categories_legend).to_be_visible()
    return dashboard


def test_spending_is_split_by_payment_method(dashboard: DashboardPage) -> None:
    legend = dashboard.payment_methods_legend

    expect(dashboard.legend_entry(legend, "ATM withdrawal")).to_contain_text("100.00 EUR")
    expect(dashboard.legend_entry(legend, "Transfer")).to_contain_text("67.00 EUR")


def test_new_spending_is_uncategorised(dashboard: DashboardPage) -> None:
    legend = dashboard.categories_legend

    expect(dashboard.legend_entry(legend, "Uncategorised")).to_contain_text("167.00 EUR")


def test_breakdown_follows_the_period_filter(dashboard: DashboardPage) -> None:
    dashboard.select_period("Last week")

    expect(dashboard.legend_entry(dashboard.categories_legend, "Uncategorised")).to_contain_text(
        "142.00 EUR"
    )


def test_period_without_spending_shows_no_breakdown(
    page: Page, fake_bank: Callable[..., None]
) -> None:
    fake_bank(transactions=[debit("25", _days_ago(20), creditor="Landlord")])
    dashboard = DashboardPage(page)
    dashboard.open()
    dashboard.connect_bank()
    expect(dashboard.categories_legend).to_be_visible()

    dashboard.select_period("Last week")

    expect(dashboard.empty_state).to_have_text("No spending in this period.")
    expect(dashboard.payment_methods_legend).to_have_count(0)
    expect(dashboard.categories_legend).to_have_count(0)
