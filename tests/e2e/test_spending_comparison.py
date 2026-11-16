import re
from collections.abc import Callable
from datetime import date, timedelta

import pytest
from playwright.sync_api import Page, expect

from app.spending import Comparison
from tests.e2e.pages.dashboard_page import DashboardPage
from tests.fakes.enable_banking import debit

pytestmark = pytest.mark.e2e

TODAY = date.today()


@pytest.fixture
def open_dashboard(page: Page, fake_bank: Callable[..., None]) -> Callable[..., DashboardPage]:
    def open_with(query: str = "?period=week", **bank: object) -> DashboardPage:
        fake_bank(
            transactions=[
                debit("100", TODAY, creditor="Netflix"),
                debit("10", TODAY, creditor="Orlen"),
                debit("50", Comparison.MONTH.shift(TODAY), creditor="Netflix"),
                debit("50", Comparison.MONTH.shift(TODAY), creditor="Orlen"),
                debit("220", Comparison.YEAR.shift(TODAY), creditor="Netflix"),
            ],
            **bank,
        )
        dashboard = DashboardPage(page)
        dashboard.open(query)
        dashboard.connect_bank()
        expect(dashboard.total).to_be_visible()
        dashboard.open(query)
        expect(dashboard.total).to_have_text("110.00 EUR")
        return dashboard

    return open_with


def test_compares_with_the_same_days_a_month_ago_by_default(
    open_dashboard: Callable[..., DashboardPage],
) -> None:
    dashboard = open_dashboard()

    expect(dashboard.total_delta).to_have_text("▲ +10.0% vs 100.00 EUR a month ago")
    expect(dashboard.total_delta).to_have_class(re.compile(r"text-negative"))
    expect(dashboard.spending_heading).to_have_text("Spending per day vs a month ago")


def test_y2y_compares_with_the_same_days_a_year_ago(
    open_dashboard: Callable[..., DashboardPage],
) -> None:
    dashboard = open_dashboard()

    dashboard.select_comparison("Y2Y")

    expect(dashboard.total_delta).to_have_text("▼ -50.0% vs 220.00 EUR a year ago")
    expect(dashboard.total_delta).to_have_class(re.compile(r"text-positive"))
    expect(dashboard.spending_heading).to_have_text("Spending per day vs a year ago")
    expect(dashboard.page).to_have_url(re.compile(r"compare=y2y"))


def test_comparison_is_restored_from_url(open_dashboard: Callable[..., DashboardPage]) -> None:
    dashboard = open_dashboard("?period=week&compare=y2y")

    expect(dashboard.total_delta).to_contain_text("a year ago")


def test_counterparty_filter_also_narrows_the_comparison(
    open_dashboard: Callable[..., DashboardPage],
) -> None:
    dashboard = open_dashboard()

    dashboard.filter_by_counterparty("Orlen")

    expect(dashboard.total_delta).to_have_text("▼ -80.0% vs 50.00 EUR a month ago")


def test_days_the_bank_has_no_history_for_count_as_no_spending(
    open_dashboard: Callable[..., DashboardPage],
) -> None:
    dashboard = open_dashboard(history_from=(TODAY - timedelta(days=29)).isoformat())

    dashboard.select_comparison("Y2Y")

    expect(dashboard.total_delta).to_have_text("vs 0.00 EUR a year ago")
    expect(dashboard.total_delta).to_have_class(re.compile(r"text-muted"))
