import re

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.pages.dashboard_page import DashboardPage

pytestmark = pytest.mark.e2e


def test_new_user_sees_empty_state_prompting_bank_connection(page: Page) -> None:
    dashboard = DashboardPage(page)
    dashboard.open()

    expect(dashboard.empty_state).to_contain_text("Connect a bank account")


def test_dark_mode_toggle_switches_theme(page: Page) -> None:
    dashboard = DashboardPage(page)
    dashboard.open()

    dashboard.dark_mode_toggle.click()

    expect(page.locator("body")).to_have_class(re.compile(r"body--dark"))
