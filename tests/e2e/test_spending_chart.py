from collections.abc import Callable
from datetime import date, timedelta

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.pages.dashboard_page import DashboardPage

pytestmark = pytest.mark.e2e


def _debit(amount: str, days_ago: int) -> dict[str, object]:
    return {
        "transaction_amount": {"amount": amount, "currency": "EUR"},
        "credit_debit_indicator": "DBIT",
        "booking_date": (date.today() - timedelta(days=days_ago)).isoformat(),
    }


@pytest.fixture
def connected_dashboard(page: Page, fake_bank: Callable[..., None]) -> DashboardPage:
    fake_bank(transactions=[_debit("10", days_ago=0), _debit("100", days_ago=20)])
    dashboard = DashboardPage(page)
    dashboard.open()
    dashboard.connect_bank()
    expect(dashboard.spending_chart).to_be_visible()
    return dashboard


def test_switching_period_updates_spending(connected_dashboard: DashboardPage) -> None:
    expect(connected_dashboard.total).to_have_text("110.00 EUR")

    connected_dashboard.select_period("Last week")

    expect(connected_dashboard.total).to_have_text("10.00 EUR")
    expect(connected_dashboard.page).to_have_url("/?period=week", ignore_case=True)


def test_period_is_restored_from_url(connected_dashboard: DashboardPage) -> None:
    connected_dashboard.open("?period=week")

    expect(connected_dashboard.total).to_have_text("10.00 EUR")


def test_period_without_spending_shows_empty_state(
    page: Page, fake_bank: Callable[..., None]
) -> None:
    fake_bank(transactions=[_debit("100", days_ago=20)])
    dashboard = DashboardPage(page)
    dashboard.open()

    dashboard.connect_bank()
    dashboard.select_period("Last week")

    expect(dashboard.empty_state).to_contain_text("No spending in this period")
    expect(dashboard.spending_chart).to_have_count(0)
