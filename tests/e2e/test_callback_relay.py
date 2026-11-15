from collections.abc import Callable
from urllib.parse import urlencode, urlparse

import pytest
from playwright.sync_api import Page, expect

from app.config import PROJECT_ROOT
from tests.e2e.pages.dashboard_page import DashboardPage

pytestmark = pytest.mark.e2e

CALLBACK_PAGE = (PROJECT_ROOT / "site" / "callback.html").as_uri()


def test_hosted_callback_relays_bank_response_to_local_app(
    page: Page, base_url: str, fake_bank: Callable[..., None]
) -> None:
    port = urlparse(base_url).port
    query = urlencode({"code": "abc", "state": f"{port}.never-issued-nonce-123"})

    page.goto(f"{CALLBACK_PAGE}?{query}")

    expect(DashboardPage(page).error).to_contain_text("no longer valid")


@pytest.mark.parametrize("state", ["evil.example.com.abcdefghijklmnop", "0.abcdefghijklmnop", ""])
def test_hosted_callback_refuses_states_without_a_local_port(page: Page, state: str) -> None:
    page.goto(f"{CALLBACK_PAGE}?{urlencode({'code': 'abc', 'state': state})}")

    expect(page.get_by_role("status")).to_contain_text("not a valid Yiji bank callback")
    expect(page).to_have_url(f"{CALLBACK_PAGE}?{urlencode({'code': 'abc', 'state': state})}")
