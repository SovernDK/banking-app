import re
from collections.abc import Callable

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.pages.dashboard_page import DashboardPage

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
