from collections.abc import Callable
from datetime import date

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.pages.dashboard_page import DashboardPage
from tests.fakes.enable_banking import debit

pytestmark = pytest.mark.e2e


@pytest.fixture
def connected_dashboard(page: Page, fake_bank: Callable[..., None]) -> DashboardPage:
    fake_bank(transactions=[debit("10", date.today())])
    dashboard = DashboardPage(page)
    dashboard.open()
    dashboard.connect_bank()
    expect(dashboard.spending_chart).to_be_visible()
    return dashboard


def test_dashboard_is_in_english_by_default(page: Page, fake_bank: Callable[..., None]) -> None:
    dashboard = DashboardPage(page)
    dashboard.open()

    expect(dashboard.language_picker).to_have_value("EN")
    expect(page.get_by_role("heading", name="Overview")).to_be_visible()
    expect(page.locator("html")).to_have_attribute("lang", "en")


def test_choosing_polish_translates_the_dashboard(connected_dashboard: DashboardPage) -> None:
    connected_dashboard.choose_language("PL")

    page = connected_dashboard.page
    expect(page.get_by_role("heading", name="Przegląd")).to_be_visible()
    expect(connected_dashboard.total_label).to_have_text("Wydano, ostatni miesiąc")
    expect(page.get_by_role("button", name="Ustawienia")).to_be_visible()
    expect(page.locator("html")).to_have_attribute("lang", "pl")


def test_chosen_language_is_remembered_on_the_next_visit(
    connected_dashboard: DashboardPage,
) -> None:
    connected_dashboard.choose_language("JP")
    expect(connected_dashboard.page.get_by_role("heading", name="概要")).to_be_visible()

    connected_dashboard.open()

    expect(connected_dashboard.language_picker).to_have_value("JP")
    expect(connected_dashboard.total_label).to_have_text("支出、過去1か月")


def test_switching_language_keeps_the_chosen_filters(connected_dashboard: DashboardPage) -> None:
    connected_dashboard.select_period("Last week")

    connected_dashboard.choose_language("JP")

    expect(connected_dashboard.total_label).to_have_text("支出、過去1週間")
    expect(connected_dashboard.page).to_have_url("/?period=week&compare=m2m")
