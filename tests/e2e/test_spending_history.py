from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from app.banking.store import BankStore
from app.modules import DataFiles
from tests.e2e.pages.dashboard_page import DashboardPage
from tests.fakes.enable_banking import debit

pytestmark = pytest.mark.e2e


def _end_bank_consent(data_dir: Path) -> None:
    store = BankStore(DataFiles.under(data_dir).bank)
    state = store.load()
    assert state.session is not None
    state.session.valid_until = datetime(2000, 1, 1, tzinfo=UTC)
    store.save(state)


def test_stored_spending_stays_on_the_dashboard_after_the_bank_connection_ends(
    page: Page, fake_bank: Callable[..., None], app_data_dir: Path
) -> None:
    fake_bank(transactions=[debit("12.50", date.today())])
    dashboard = DashboardPage(page)
    dashboard.open()
    dashboard.connect_bank()
    expect(dashboard.total).to_have_text("12.50 EUR")

    _end_bank_consent(app_data_dir)
    dashboard.open()

    expect(dashboard.total).to_have_text("12.50 EUR")
    expect(dashboard.connect_button).to_be_visible()
    expect(dashboard.page.get_by_text("Connect a bank account")).to_have_count(0)


def test_pending_payments_wait_until_the_bank_books_them(
    page: Page, fake_bank: Callable[..., None]
) -> None:
    fake_bank(
        transactions=[
            debit("12.50", date.today()),
            debit("99", date.today(), status="PDNG"),
        ]
    )
    dashboard = DashboardPage(page)
    dashboard.open()

    dashboard.connect_bank()

    expect(dashboard.total).to_have_text("12.50 EUR")
