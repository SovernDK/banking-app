from datetime import date
from decimal import Decimal
from typing import Any

from nicegui import run, ui

from app.banking.client import BankApiError, BankSessionExpiredError
from app.banking.errors import BankErrorCode
from app.banking.models import Transaction
from app.banking.service import BankingService, NotConnectedError, find_banking_service
from app.config import get_settings
from app.spending import DailySpending, Period, daily_spending, main_currency
from app.ui import format as fmt
from app.ui.components import (
    alert,
    chart,
    chip,
    empty_state,
    kpi_tile,
    overview_band,
    page_shell,
    period_filter,
    primary_button,
    section,
)


def _error_from(code: str | None) -> BankErrorCode | None:
    try:
        return BankErrorCode(code)
    except ValueError:
        return None


def _connect_button(service: BankingService) -> None:
    async def connect() -> None:
        try:
            url = await run.io_bound(service.connect_url)
        except BankApiError:
            ui.notify(BankErrorCode.BANK_UNAVAILABLE.message, type="negative")
            return
        ui.navigate.to(url)

    primary_button("Connect bank", connect, testid="connect-bank")


def _spending_option(days: list[DailySpending], currency: str) -> dict[str, Any]:
    return {
        "xAxis": {"type": "category", "data": [fmt.date(entry.day) for entry in days]},
        "yAxis": {"type": "value"},
        "tooltip": {"trigger": "axis", "formatter": f"{{b}}<br/>{{c}} {currency}"},
        "series": [
            {
                "name": "Spending",
                "type": "bar",
                "data": [float(entry.amount) for entry in days],
                "itemStyle": {"borderRadius": [4, 4, 0, 0]},
            }
        ],
    }


def _spending_view(
    transactions: list[Transaction], today: date, initial: Period, dark_mode: ui.dark_mode
) -> None:
    currency = main_currency(transactions)
    if currency is None:
        empty_state("No spending in the last month.")
        return
    spending = {period: daily_spending(transactions, currency, period, today) for period in Period}

    @ui.refreshable
    def content(period: Period) -> None:
        days = spending[period]
        total = sum((entry.amount for entry in days), Decimal(0))
        kpi_tile(f"Spent, {period.label.lower()}", fmt.money(total, currency), testid="total")
        with section("Spending per day", currency):
            if total == 0:
                empty_state("No spending in this period.")
            else:
                chart(
                    _spending_option(days, currency),
                    dark=bool(dark_mode.value),
                    testid="spending-chart",
                )

    def select(period: Period) -> None:
        ui.navigate.history.replace(f"/?period={period}")
        content.refresh(period)

    period_filter(initial, select)
    content(initial)
    dark_mode.on_value_change(lambda: content.refresh())


def register() -> None:
    @ui.page("/")
    async def dashboard_page(period: str | None = None, bank_error: str | None = None) -> None:
        settings = get_settings()
        service = find_banking_service()
        error = _error_from(bank_error)
        with page_shell(settings.app_title) as dark_mode, overview_band():
            with ui.row().classes("w-full items-center justify-between gap-4"):
                ui.label("Overview").classes("text-2xl font-normal").props(
                    'role="heading" aria-level="1"'
                )
                if settings.enable_banking_environment == "sandbox":
                    chip("science", "Sandbox")
            if service is None:
                alert(BankErrorCode.NOT_CONFIGURED.message)
                return
            if error:
                alert(error.message)
            try:
                transactions = await run.io_bound(service.transactions)
            except NotConnectedError:
                empty_state("No transactions yet. Connect a bank account to see your history.")
                _connect_button(service)
                return
            except BankSessionExpiredError:
                alert(BankErrorCode.SESSION_EXPIRED.message)
                _connect_button(service)
                return
            except BankApiError:
                alert(BankErrorCode.BANK_UNAVAILABLE.message)
                return
            _spending_view(transactions, service.today(), Period.parse(period), dark_mode)
