import re
from collections.abc import Callable
from datetime import date

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.pages.dashboard_page import DashboardPage
from tests.fakes.enable_banking import debit

pytestmark = pytest.mark.e2e


def test_new_user_sees_empty_state_prompting_bank_connection(
    page: Page, fake_bank: Callable[..., None]
) -> None:
    dashboard = DashboardPage(page)
    dashboard.open()

    expect(dashboard.empty_state).to_contain_text("Connect a bank account")
    expect(dashboard.connect_button).to_be_visible()
    expect(dashboard.settings_button).to_have_count(0)


def test_dark_mode_toggle_switches_theme(page: Page, fake_bank: Callable[..., None]) -> None:
    dashboard = DashboardPage(page)
    dashboard.open()

    dashboard.dark_mode_toggle.click()

    expect(page.locator("body")).to_have_class(re.compile(r"body--dark"))


def _switch_currency(dashboard: DashboardPage) -> None:
    dashboard.select_currency("PLN")
    expect(dashboard.page).to_have_url(re.compile(r"currency=PLN"))


@pytest.mark.parametrize(
    "change",
    [
        lambda dashboard: dashboard.select_period("Last week"),
        lambda dashboard: dashboard.select_comparison("Y2Y"),
        _switch_currency,
        lambda dashboard: dashboard.filter_by_counterparty("Shop"),
        lambda dashboard: dashboard.page.reload(),
    ],
    ids=["period", "comparison", "currency", "counterparty", "reload"],
)
def test_dark_mode_stays_on_through_filter_changes_and_reloads(
    page: Page, fake_bank: Callable[..., None], change: Callable[[DashboardPage], None]
) -> None:
    fake_bank(transactions=[debit("12.50", date.today(), creditor="Shop")])
    dashboard = DashboardPage(page)
    dashboard.open()
    dashboard.connect_bank()
    expect(dashboard.spending_chart).to_be_visible()
    dashboard.dark_mode_toggle.click()
    expect(page.locator("body")).to_have_class(re.compile(r"body--dark"))

    change(dashboard)

    expect(dashboard.total).to_be_visible()
    expect(page.locator("body")).to_have_class(re.compile(r"body--dark"))
