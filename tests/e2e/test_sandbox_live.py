"""Talks to the real Enable Banking sandbox with the credentials in .env. Opt in with
`uv run pytest -m sandbox`; never runs against the production app."""

import re
from typing import Any

import pytest
from playwright.sync_api import Page, expect

from app.config import MissingCredentialsError, Settings
from app.tls import write_localhost_certificate
from tests.e2e.conftest import AppServer, free_port
from tests.e2e.pages.dashboard_page import DashboardPage

pytestmark = pytest.mark.sandbox


@pytest.fixture(scope="module")
def browser_context_args(browser_context_args: dict[str, Any]) -> dict[str, Any]:
    return {**browser_context_args, "ignore_https_errors": True}


@pytest.fixture(scope="module")
def sandbox_url(serve_app: AppServer, tmp_path_factory: pytest.TempPathFactory) -> str:
    settings = Settings(enable_banking_environment="sandbox")
    try:
        settings.enable_banking_credentials()
    except MissingCredentialsError:
        pytest.skip("Enable Banking sandbox credentials are not configured in .env")
    data_dir = tmp_path_factory.mktemp("sandbox-data")
    env = {"YIJI_ENABLE_BANKING_ENVIRONMENT": "sandbox"}
    redirect = settings.active_redirect_url
    if settings.local_callback_path() is None or redirect.port is None:
        return serve_app(free_port(), data_dir, env)
    # The registered redirect URL points at this machine, so the app must run exactly there.
    tls_dir = tmp_path_factory.mktemp("tls")
    certificate, key = tls_dir / "localhost.crt", tls_dir / "localhost.key"
    write_localhost_certificate(certificate, key)
    tls = (certificate, key) if redirect.scheme == "https" else None
    return serve_app(redirect.port, data_dir, env, tls)


def test_connect_opens_enable_banking_authorization_for_mock_aspsp(
    page: Page, sandbox_url: str
) -> None:
    dashboard = DashboardPage(page)
    page.goto(sandbox_url)

    dashboard.connect_bank()

    expect(page).to_have_url(re.compile(r"^https://[^/]*enablebanking\.com/"))
