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
    expect(dashboard.counterparties).to_be_visible()
    return dashboard


def test_spending_is_split_by_payment_method(dashboard: DashboardPage) -> None:
    legend = dashboard.payment_methods_legend

    expect(dashboard.legend_entry(legend, "ATM withdrawal")).to_contain_text("100.00 EUR")
    expect(dashboard.legend_entry(legend, "Transfer")).to_contain_text("67.00 EUR")


def test_new_spending_is_uncategorised(dashboard: DashboardPage) -> None:
    legend = dashboard.categories_legend

    expect(dashboard.legend_entry(legend, "Uncategorised")).to_contain_text("167.00 EUR")


def test_assigning_a_category_covers_every_payment_to_that_name(dashboard: DashboardPage) -> None:
    dashboard.assign_category("Biedronka", "Groceries")

    legend = dashboard.categories_legend
    expect(dashboard.legend_entry(legend, "Groceries")).to_contain_text("42.00 EUR")
    expect(dashboard.legend_entry(legend, "Uncategorised")).to_contain_text("125.00 EUR")


@pytest.mark.parametrize(
    "edit",
    [
        lambda dashboard: dashboard.assign_category("Landlord", "Housing"),
        lambda dashboard: dashboard.create_category("Landlord", "Rent"),
    ],
    ids=["assign", "create"],
)
def test_editing_a_category_keeps_the_scroll_position(
    dashboard: DashboardPage, edit: Callable[[DashboardPage], None]
) -> None:
    dashboard.page.set_viewport_size({"width": 1280, "height": 600})
    dashboard.category_select("Landlord").scroll_into_view_if_needed()
    scrolled_to = dashboard.scroll_position()
    assert scrolled_to > 0

    edit(dashboard)

    expect(dashboard.legend_entry(dashboard.categories_legend, "Uncategorised")).to_contain_text(
        "142.00 EUR"
    )
    assert dashboard.scroll_position() == scrolled_to


def test_typing_a_new_category_creates_and_assigns_it(dashboard: DashboardPage) -> None:
    dashboard.create_category("Landlord", "Rent")

    expect(dashboard.legend_entry(dashboard.categories_legend, "Rent")).to_contain_text("25.00 EUR")
    expect(dashboard.page.get_by_role("listbox")).to_have_count(0)


def test_category_survives_a_reload(dashboard: DashboardPage) -> None:
    dashboard.assign_category("Landlord", "Housing")
    expect(dashboard.legend_entry(dashboard.categories_legend, "Housing")).to_be_visible()

    dashboard.open()

    expect(dashboard.legend_entry(dashboard.categories_legend, "Housing")).to_contain_text(
        "25.00 EUR"
    )


def test_renamed_category_shows_its_new_name(dashboard: DashboardPage) -> None:
    dashboard.assign_category("Landlord", "Housing")
    dashboard.open_manage_categories()

    dashboard.rename_category("Housing", "Home")

    expect(dashboard.legend_entry(dashboard.categories_legend, "Home")).to_contain_text("25.00 EUR")


def test_deleting_a_used_category_warns_and_uncategorises_its_names(
    dashboard: DashboardPage,
) -> None:
    dashboard.assign_category("Biedronka", "Groceries")
    dashboard.open_manage_categories()

    dashboard.delete_category("Groceries")
    expect(dashboard.page.get_by_text("1 counterparty will become Uncategorised")).to_be_visible()
    dashboard.confirm_delete()

    legend = dashboard.categories_legend
    expect(dashboard.legend_entry(legend, "Groceries")).to_have_count(0)
    expect(dashboard.legend_entry(legend, "Uncategorised")).to_contain_text("167.00 EUR")


def test_breakdown_follows_the_period_filter(dashboard: DashboardPage) -> None:
    dashboard.select_period("Last week")

    expect(dashboard.legend_entry(dashboard.categories_legend, "Uncategorised")).to_contain_text(
        "142.00 EUR"
    )
    expect(dashboard.category_select("Landlord")).to_have_count(0)


def test_period_without_spending_shows_no_breakdown(
    page: Page, fake_bank: Callable[..., None]
) -> None:
    fake_bank(transactions=[debit("25", _days_ago(20), creditor="Landlord")])
    dashboard = DashboardPage(page)
    dashboard.open()
    dashboard.connect_bank()
    expect(dashboard.counterparties).to_be_visible()

    dashboard.select_period("Last week")

    expect(dashboard.empty_state).to_have_text("No spending in this period.")
    expect(dashboard.payment_methods_legend).to_have_count(0)
    expect(dashboard.counterparties).to_have_count(0)
