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


def _open_counterparties(dashboard: DashboardPage) -> None:
    dashboard.open_settings()
    dashboard.expand("Counterparties")


def _open_categories(dashboard: DashboardPage) -> None:
    dashboard.open_settings()
    dashboard.expand("Categories")


def test_categories_and_counterparties_live_only_in_settings(dashboard: DashboardPage) -> None:
    expect(dashboard.counterparties).to_be_hidden()
    expect(dashboard.page.get_by_text("Manage categories")).to_have_count(0)

    dashboard.open_settings()

    expect(dashboard.box_toggle("Expand", "Categories")).to_be_visible()
    expect(dashboard.box_toggle("Expand", "Counterparties")).to_be_visible()
    expect(dashboard.counterparties).to_be_hidden()
    expect(dashboard.categories_list).to_be_hidden()


def test_counterparties_box_lists_names_outside_the_selected_period(
    dashboard: DashboardPage,
) -> None:
    dashboard.select_period("Last week")

    _open_counterparties(dashboard)

    expect(dashboard.counterparties).to_contain_text("Biedronka")
    expect(dashboard.category_select("Landlord")).to_be_visible()


def test_assigning_a_category_covers_every_payment_to_that_name(dashboard: DashboardPage) -> None:
    _open_counterparties(dashboard)

    dashboard.assign_category("Biedronka", "Groceries")
    dashboard.close_settings()

    legend = dashboard.categories_legend
    expect(dashboard.legend_entry(legend, "Groceries")).to_contain_text("42.00 EUR")
    expect(dashboard.legend_entry(legend, "Uncategorised")).to_contain_text("125.00 EUR")


def test_typing_a_new_category_creates_it_and_lists_it_in_categories(
    dashboard: DashboardPage,
) -> None:
    _open_counterparties(dashboard)

    dashboard.create_category("Landlord", "Rent")

    expect(dashboard.page.get_by_role("listbox")).to_have_count(0)
    dashboard.expand("Categories")
    expect(dashboard.category_name_field("Rent")).to_have_value("Rent")
    dashboard.close_settings()
    expect(dashboard.legend_entry(dashboard.categories_legend, "Rent")).to_contain_text("25.00 EUR")


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
    dashboard.page.set_viewport_size({"width": 1280, "height": 500})
    dashboard.open_settings()
    dashboard.expand("Categories")
    dashboard.expand("Counterparties")
    dashboard.category_select("Landlord").scroll_into_view_if_needed()
    scrolled_to = dashboard.dialog_scroll_position()
    assert scrolled_to > 0

    edit(dashboard)

    expect(dashboard.legend_entry(dashboard.categories_legend, "Uncategorised")).to_contain_text(
        "142.00 EUR"
    )
    assert dashboard.dialog_scroll_position() == scrolled_to


def test_category_survives_a_reload(dashboard: DashboardPage) -> None:
    _open_counterparties(dashboard)
    dashboard.assign_category("Landlord", "Housing")
    expect(dashboard.legend_entry(dashboard.categories_legend, "Housing")).to_be_attached()

    dashboard.open()

    expect(dashboard.legend_entry(dashboard.categories_legend, "Housing")).to_contain_text(
        "25.00 EUR"
    )


def test_renamed_category_shows_its_new_name(dashboard: DashboardPage) -> None:
    _open_counterparties(dashboard)
    dashboard.assign_category("Landlord", "Housing")
    dashboard.expand("Categories")

    dashboard.rename_category("Housing", "Home")

    expect(dashboard.category_name_field("Home")).to_have_value("Home")
    dashboard.close_settings()
    expect(dashboard.legend_entry(dashboard.categories_legend, "Home")).to_contain_text("25.00 EUR")


def test_renaming_to_an_existing_name_is_refused_and_restored(dashboard: DashboardPage) -> None:
    _open_categories(dashboard)

    dashboard.rename_category("Housing", "Groceries")

    expect(dashboard.page.get_by_text("already exists")).to_be_visible()
    expect(dashboard.category_name_field("Housing")).to_have_value("Housing")


def test_deleting_a_used_category_warns_and_uncategorises_its_names(
    dashboard: DashboardPage,
) -> None:
    _open_counterparties(dashboard)
    dashboard.assign_category("Biedronka", "Groceries")
    dashboard.expand("Categories")

    dashboard.delete_category("Groceries")
    expect(dashboard.page.get_by_text("1 counterparty will become Uncategorised")).to_be_visible()
    dashboard.confirm_delete()

    expect(dashboard.category_name_field("Groceries")).to_have_count(0)
    expect(dashboard.category_select("Biedronka")).to_have_value("")
    dashboard.close_settings()
    legend = dashboard.categories_legend
    expect(dashboard.legend_entry(legend, "Groceries")).to_have_count(0)
    expect(dashboard.legend_entry(legend, "Uncategorised")).to_contain_text("167.00 EUR")
