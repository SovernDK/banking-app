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
def dashboard(
    page: Page, fake_bank: Callable[..., None], fake_ollama: Callable[..., None]
) -> DashboardPage:
    fake_bank(
        transactions=[
            debit("40", _days_ago(1), creditor="Biedronka"),
            debit("12", _days_ago(2), creditor="ŻABKA POLSKA", remittance=["Zakup BLIK"]),
            debit("25", _days_ago(3), creditor="Jan Kowalski"),
        ]
    )
    dashboard = DashboardPage(page)
    dashboard.open()
    dashboard.connect_bank()
    expect(dashboard.categories_legend).to_be_visible()
    dashboard.open_settings()
    dashboard.expand("Counterparties")
    return dashboard


def test_ai_fills_in_categories_the_user_can_then_correct(
    dashboard: DashboardPage, fake_ollama: Callable[..., None]
) -> None:
    fake_ollama(categories={"Biedronka": "Groceries", "ŻABKA POLSKA": "Groceries"})

    dashboard.categorise_with_ai()

    expect(
        dashboard.page.get_by_text("AI assigned categories to 2 counterparties.")
    ).to_be_visible()
    expect(dashboard.category_select("Biedronka")).to_have_value("Groceries")
    expect(dashboard.ai_badge("Biedronka")).to_be_visible()
    expect(dashboard.ai_badge("Jan Kowalski")).to_be_hidden()
    expect(dashboard.legend_entry(dashboard.categories_legend, "Groceries")).to_contain_text(
        "52.00 EUR"
    )

    dashboard.assign_category("ŻABKA POLSKA", "Eating out")

    expect(dashboard.ai_badge("ŻABKA POLSKA")).to_be_hidden()
    expect(dashboard.ai_badge("Biedronka")).to_be_visible()


def test_ai_leaves_categories_the_user_chose(
    dashboard: DashboardPage, fake_ollama: Callable[..., None]
) -> None:
    dashboard.assign_category("Biedronka", "Shopping")
    fake_ollama(categories={"Biedronka": "Groceries"})

    dashboard.categorise_with_ai()

    expect(dashboard.page.get_by_text("AI found nothing it could assign.")).to_be_visible()
    expect(dashboard.category_select("Biedronka")).to_have_value("Shopping")
    expect(dashboard.ai_badge("Biedronka")).to_be_hidden()


def test_ai_outage_is_explained_and_changes_nothing(
    dashboard: DashboardPage, fake_ollama: Callable[..., None]
) -> None:
    fake_ollama(failure_status=503)

    dashboard.categorise_with_ai()

    expect(dashboard.page.get_by_text("AI is unavailable right now.")).to_be_visible()
    expect(dashboard.ai_badge("Biedronka")).to_be_hidden()
    expect(dashboard.legend_entry(dashboard.categories_legend, "Uncategorised")).to_contain_text(
        "77.00 EUR"
    )
