from collections.abc import Callable
from datetime import date

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.pages.dashboard_page import DashboardPage
from tests.fakes.enable_banking import debit

pytestmark = pytest.mark.e2e


def test_connecting_bank_shows_spending_chart(page: Page, fake_bank: Callable[..., None]) -> None:
    fake_bank(transactions=[debit("12.50", date.today())])
    dashboard = DashboardPage(page)
    dashboard.open()

    dashboard.connect_bank()

    expect(dashboard.spending_chart).to_be_visible()
    expect(dashboard.total).to_have_text("12.50 EUR")
    expect(dashboard.connect_button).to_have_count(0)


def test_bank_denying_access_shows_error_and_offers_reconnect(
    page: Page, fake_bank: Callable[..., None]
) -> None:
    fake_bank(deny_access=True)
    dashboard = DashboardPage(page)
    dashboard.open()

    dashboard.connect_bank()

    expect(dashboard.error).to_contain_text("did not grant access")
    expect(dashboard.connect_button).to_be_visible()


def test_bank_outage_on_connect_keeps_user_on_dashboard(
    page: Page, fake_bank: Callable[..., None]
) -> None:
    fake_bank(failure_status=503)
    dashboard = DashboardPage(page)
    dashboard.open()

    dashboard.connect_bank()

    expect(page.get_by_text("bank service is unavailable")).to_be_visible()
    expect(dashboard.connect_button).to_be_visible()


def test_expired_bank_session_asks_to_reconnect(page: Page, fake_bank: Callable[..., None]) -> None:
    fake_bank(session_expired=True)
    dashboard = DashboardPage(page)
    dashboard.open()

    dashboard.connect_bank()

    expect(dashboard.error).to_contain_text("connection has expired")
    expect(dashboard.connect_button).to_be_visible()
