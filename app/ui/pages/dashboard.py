from datetime import date
from decimal import Decimal
from typing import Any

from nicegui import run, ui

from app.bank_profiles import BankProfile, profile_for
from app.banking.client import BankApiError, BankSessionExpiredError
from app.banking.errors import BankErrorCode
from app.banking.models import Transaction
from app.banking.service import BankingService, NotConnectedError, find_banking_service
from app.categories import (
    CATEGORIES_FILENAME,
    CategoryBook,
    CategoryStore,
    DuplicateCategoryError,
    InvalidCategoryNameError,
    counterparty_name,
)
from app.config import get_settings
from app.payment_methods import PaymentMethod
from app.spending import (
    DailySpending,
    Period,
    Share,
    all_time_spending_by,
    daily_spending,
    main_currency,
    spending_by,
    top_shares,
)
from app.ui import format as fmt
from app.ui.components import (
    CategoryEntry,
    CounterpartyRow,
    Donut,
    DonutSlice,
    PageShell,
    SettingsDialog,
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
    settings_button,
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


CHART_SLICE_LIMIT = 7


def _payment_method_slices(shares: list[Share[PaymentMethod]]) -> list[DonutSlice]:
    order = list(PaymentMethod)
    return [
        DonutSlice(
            label=share.key,
            amount=share.amount,
            colour_slot=None if share.key is PaymentMethod.OTHER else order.index(share.key),
            hatched=share.key is PaymentMethod.OTHER,
        )
        for share in shares
    ]


def _category_slices(shares: list[Share[str | None]], book: CategoryBook) -> list[DonutSlice]:
    categorised = [
        Share(key=category, amount=share.amount)
        for share in shares
        if share.key and (category := book.get(share.key))
    ]
    uncategorised = sum((share.amount for share in shares if share.key is None), Decimal(0))
    limit = CHART_SLICE_LIMIT - 1 if uncategorised else CHART_SLICE_LIMIT
    kept, rest = top_shares(categorised, limit)
    slices = [
        DonutSlice(label=share.key.name, amount=share.amount, colour_slot=share.key.colour_slot)
        for share in kept
    ]
    if rest:
        slices.append(DonutSlice(label="Other", amount=rest, hatched=True))
    if uncategorised:
        slices.append(DonutSlice(label="Uncategorised", amount=uncategorised))
    return slices


def _spending_view(
    transactions: list[Transaction],
    today: date,
    initial: Period,
    shell: PageShell,
    band: ui.column,
    profile: BankProfile,
    store: CategoryStore,
    book: CategoryBook,
) -> None:
    currency = main_currency(transactions)
    if currency is None:
        with band:
            empty_state("No spending in the last month.")
        return
    dark_mode = shell.dark_mode
    spending = {period: daily_spending(transactions, currency, period, today) for period in Period}
    selected = initial

    def spends_in(period: Period) -> bool:
        return any(entry.amount for entry in spending[period])

    @ui.refreshable
    def overview(period: Period) -> None:
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

    def category_id_of(transaction: Transaction) -> str | None:
        category = book.category_of(counterparty_name(transaction))
        return category.id if category else None

    def category_slices() -> list[DonutSlice]:
        shares = spending_by(transactions, currency, selected, today, category_id_of)
        return _category_slices(shares, book)

    def assigned_category(counterparty: str) -> str | None:
        category = book.category_of(counterparty)
        return category.id if category else None

    def category_entries() -> list[CategoryEntry]:
        return [
            CategoryEntry(id=category.id, name=category.name, usage=book.usage(category.id))
            for category in book.categories
        ]

    def category_names() -> dict[str, str]:
        return {category.id: category.name for category in book.categories}

    category_donut: Donut | None = None

    def show_categories() -> None:
        if category_donut is not None:
            category_donut.update(category_slices())
        settings.update(category_entries(), category_names(), assigned_category)

    async def save_and_show() -> None:
        await run.io_bound(store.save, book)
        show_categories()

    async def change_category(counterparty: str, value: str | None) -> None:
        if value == assigned_category(counterparty):
            return
        try:
            if value is None or book.get(value):
                category_id = value
            else:
                existing = book.find_by_name(value)
                category_id = existing.id if existing else book.create(value).id
        except InvalidCategoryNameError as error:
            ui.notify(str(error), type="negative")
            show_categories()
            return
        book.assign(counterparty, category_id)
        await save_and_show()

    async def rename_category(category_id: str, name: str) -> None:
        try:
            book.rename(category_id, name)
        except (InvalidCategoryNameError, DuplicateCategoryError) as error:
            ui.notify(str(error), type="negative")
            show_categories()
            return
        await save_and_show()

    async def delete_category(category_id: str) -> None:
        book.delete(category_id)
        await save_and_show()

    settings = SettingsDialog(
        category_entries(),
        [
            CounterpartyRow(
                name=share.key, amount=share.amount, category_id=assigned_category(share.key)
            )
            for share in all_time_spending_by(transactions, currency, counterparty_name)
            if share.key is not None
        ],
        category_names(),
        currency,
        rename_category,
        delete_category,
        change_category,
    )
    with shell.actions:
        settings_button(settings.open)

    @ui.refreshable
    def breakdown() -> None:
        nonlocal category_donut
        category_donut = None
        if not spends_in(selected):
            return
        dark = bool(dark_mode.value)
        with ui.grid().classes("w-full grid-cols-1 md:grid-cols-2 gap-4"):
            with section("Payment methods", currency):
                profile_shares = spending_by(transactions, currency, selected, today, profile)
                Donut(
                    _payment_method_slices(profile_shares),
                    currency,
                    legend_label="Payment methods",
                    dark=dark,
                    testid="payment-methods",
                )
            with section("Categories", currency):
                category_donut = Donut(
                    category_slices(),
                    currency,
                    legend_label="Categories",
                    dark=dark,
                    testid="categories",
                )

    def select(period: Period) -> None:
        nonlocal selected
        selected = period
        ui.navigate.history.replace(f"/?period={period}")
        overview.refresh(period)
        breakdown.refresh()

    with band:
        period_filter(initial, select)
        overview(initial)
    breakdown()

    def redraw() -> None:
        overview.refresh()
        breakdown.refresh()

    dark_mode.on_value_change(redraw)


def register() -> None:
    @ui.page("/")
    async def dashboard_page(period: str | None = None, bank_error: str | None = None) -> None:
        settings = get_settings()
        service = find_banking_service()
        error = _error_from(bank_error)
        with page_shell(settings.app_title) as shell:
            with overview_band() as band:
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
                store = CategoryStore(
                    settings.data_dir / CATEGORIES_FILENAME, settings.starter_categories
                )
                book = await run.io_bound(store.load)
                profile = profile_for(
                    settings.enable_banking_aspsp_name, settings.enable_banking_aspsp_country
                )
            _spending_view(
                transactions,
                service.today(),
                Period.parse(period),
                shell,
                band,
                profile,
                store,
                book,
            )
