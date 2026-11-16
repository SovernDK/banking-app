import re
from collections.abc import Callable
from datetime import date, timedelta

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.pages.dashboard_page import DashboardPage
from tests.fakes.enable_banking import debit

pytestmark = pytest.mark.e2e

EVERYTHING_LAST_MONTH = "1,022.00 EUR"


def _days_ago(days: int) -> date:
    return date.today() - timedelta(days=days)


@pytest.fixture
def dashboard(
    page: Page,
    fake_bank: Callable[..., None],
    seed_categories: Callable[[dict[str, list[str]]], None],
) -> DashboardPage:
    fake_bank(
        transactions=[
            debit("15", _days_ago(1), creditor="Netflix"),
            debit("15", _days_ago(15), creditor="NETFLIX"),
            debit("40", _days_ago(2), creditor="Biedronka"),
            debit("2", _days_ago(9), creditor="BIEDRONKA "),
            debit("100", _days_ago(3), family="CCRD", sub_family="CWDL"),
            debit("850", _days_ago(20), creditor="Landlord", family="ICDT"),
        ]
    )
    seed_categories({"Groceries": ["Biedronka"], "Fun": []})
    dashboard = DashboardPage(page)
    dashboard.open()
    dashboard.connect_bank()
    expect(dashboard.total).to_have_text(EVERYTHING_LAST_MONTH)
    return dashboard


def test_counterparty_filter_shows_only_its_spending(dashboard: DashboardPage) -> None:
    dashboard.filter_by_counterparty("Netflix")

    expect(dashboard.total).to_have_text("30.00 EUR")
    expect(dashboard.total_label).to_have_text("Spent on Netflix, last month")
    expect(dashboard.page).to_have_url(re.compile(r"counterparty=Netflix"))


def test_counterparty_search_matches_any_part_of_the_name(dashboard: DashboardPage) -> None:
    dashboard.search_counterparties("FLIX")

    expect(dashboard.filter_options).to_have_text(["Netflix"])


@pytest.mark.parametrize(
    ("category", "total", "label"),
    [
        ("Groceries", "42.00 EUR", "Spent on Groceries, last month"),
        ("Uncategorised", "980.00 EUR", "Spent on uncategorised, last month"),
    ],
)
def test_category_filter_shows_only_its_spending(
    dashboard: DashboardPage, category: str, total: str, label: str
) -> None:
    dashboard.filter_by_category(category)

    expect(dashboard.total).to_have_text(total)
    expect(dashboard.total_label).to_have_text(label)


def test_category_options_include_unused_categories_and_uncategorised(
    dashboard: DashboardPage,
) -> None:
    dashboard.category_filter.click()

    expect(dashboard.filter_options).to_have_text(["All", "Groceries", "Fun", "Uncategorised"])


def test_choosing_a_category_resets_the_counterparty_filter(dashboard: DashboardPage) -> None:
    dashboard.filter_by_counterparty("Netflix")

    dashboard.filter_by_category("Groceries")

    expect(dashboard.total).to_have_text("42.00 EUR")
    expect(dashboard.counterparty_filter).to_have_value("All")
    expect(dashboard.page).not_to_have_url(re.compile(r"counterparty="))


def test_clear_filters_shows_all_spending_again(dashboard: DashboardPage) -> None:
    expect(dashboard.clear_filters_button).to_be_disabled()
    dashboard.filter_by_category("Groceries")

    dashboard.clear_filters()

    expect(dashboard.total).to_have_text(EVERYTHING_LAST_MONTH)
    expect(dashboard.total_label).to_have_text("Spent, last month")
    expect(dashboard.category_filter).to_have_value("All")
    expect(dashboard.clear_filters_button).to_be_disabled()
    expect(dashboard.page).to_have_url(re.compile(r"/\?period=month$"))


def test_filter_survives_a_period_change_and_can_leave_it_empty(
    dashboard: DashboardPage,
) -> None:
    dashboard.filter_by_counterparty("Landlord")

    dashboard.select_period("Last week")

    expect(dashboard.empty_state).to_have_text("No spending in this period.")
    expect(dashboard.total).to_have_text("0.00 EUR")
    expect(dashboard.counterparty_filter).to_have_value("Landlord")
    expect(dashboard.page).to_have_url(re.compile(r"period=week&counterparty=Landlord"))


def test_filter_is_restored_from_url_ignoring_case(dashboard: DashboardPage) -> None:
    dashboard.open("?period=month&counterparty=netflix")

    expect(dashboard.total).to_have_text("30.00 EUR")
    expect(dashboard.counterparty_filter).to_have_value("Netflix")


@pytest.mark.parametrize(
    "query",
    ["?counterparty=Netflix&category=uncategorised", "?counterparty=Spotify", "?category=nope"],
)
def test_conflicting_or_unknown_filters_in_url_show_all_spending(
    dashboard: DashboardPage, query: str
) -> None:
    dashboard.open(query)

    expect(dashboard.total).to_have_text(EVERYTHING_LAST_MONTH)
    expect(dashboard.clear_filters_button).to_be_disabled()


def test_assigning_a_category_updates_the_filtered_spending(dashboard: DashboardPage) -> None:
    dashboard.filter_by_category("Groceries")
    dashboard.open_settings()
    dashboard.expand("Counterparties")

    dashboard.assign_category("Netflix", "Groceries")

    expect(dashboard.total).to_have_text("72.00 EUR")


def test_deleting_the_filtered_category_resets_the_filter(dashboard: DashboardPage) -> None:
    dashboard.filter_by_category("Groceries")
    dashboard.open_settings()
    dashboard.expand("Categories")

    dashboard.delete_category("Groceries")
    dashboard.confirm_delete()
    dashboard.close_settings()

    expect(dashboard.total).to_have_text(EVERYTHING_LAST_MONTH)
    expect(dashboard.category_filter).to_have_value("All")
    expect(dashboard.page).not_to_have_url(re.compile(r"category="))


def test_category_edit_under_a_category_filter_keeps_the_page_scroll(
    dashboard: DashboardPage,
) -> None:
    dashboard.filter_by_category("Groceries")
    dashboard.categories_legend.scroll_into_view_if_needed()
    scrolled_to = dashboard.scroll_position()
    assert scrolled_to > 0
    dashboard.open_settings()
    dashboard.expand("Counterparties")

    dashboard.assign_category("Netflix", "Groceries")
    expect(dashboard.total).to_have_text("72.00 EUR")
    dashboard.close_settings()

    assert dashboard.scroll_position() == scrolled_to
