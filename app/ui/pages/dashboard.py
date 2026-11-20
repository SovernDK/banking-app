import functools
from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import date

from nicegui import run, ui

from app import texts
from app.ai_categories.client import CategorisationUnavailableError
from app.ai_categories.service import AutoCategoriser
from app.banking.client import BankApiError
from app.banking.errors import BankErrorCode
from app.banking.service import BankingService
from app.categories import (
    CategoryBook,
    CategoryStore,
    DuplicateCategoryError,
    InvalidCategoryNameError,
)
from app.i18n import Language
from app.modules import Modules
from app.refresh import BankStatus, Refreshed
from app.spending import Comparison, Period
from app.spending_view import (
    UNCATEGORISED,
    Overview,
    Slice,
    SliceKind,
    SpendingFilter,
    SpendingView,
    ViewQuery,
)
from app.ui.components import (
    Alert,
    CategoryEntry,
    CategoryOption,
    Donut,
    DonutSlice,
    PageShell,
    SettingsDialog,
    SpendingFilters,
    SpendingOverview,
    alert,
    chip,
    comparison_filter,
    currency_filter,
    empty_state,
    overview_band,
    page_shell,
    period_filter,
    primary_button,
    reconnect_notice,
    section,
    settings_button,
)
from app.ui.palette import LIGHT


def _error_from(code: str | None) -> BankErrorCode | None:
    try:
        return BankErrorCode(code)
    except ValueError:
        return None


def _connector(service: BankingService, language: Language) -> Callable[[], Awaitable[None]]:
    async def connect() -> None:
        try:
            url = await run.io_bound(service.connect_url)
        except BankApiError:
            ui.notify(texts.BANK_ERRORS[BankErrorCode.BANK_UNAVAILABLE](language), type="negative")
            return
        ui.navigate.to(url)

    return connect


def _donut_slices(slices: list[Slice], language: Language) -> list[DonutSlice]:
    labels = {
        SliceKind.OTHER: texts.OTHER(language),
        SliceKind.UNCATEGORISED: texts.UNCATEGORISED(language),
    }
    return [
        DonutSlice(
            label=part.name if part.name is not None else labels[part.kind],
            amount=part.amount,
            colour_slot=part.colour_slot,
            hatched=part.kind is SliceKind.OTHER,
        )
        for part in slices
    ]


def _overview_label(overview: Overview, period: Period, language: Language) -> str:
    in_sentence = texts.PERIODS_IN_SENTENCE[period](language)
    if overview.uncategorised:
        return texts.SPENT_UNCATEGORISED(language, period=in_sentence)
    if overview.subject:
        return texts.SPENT_ON(language, subject=overview.subject, period=in_sentence)
    return texts.SPENT(language, period=in_sentence)


def _spending_view(
    view: SpendingView,
    query: ViewQuery,
    shell: PageShell,
    band: ui.column,
    store: CategoryStore,
    auto_categoriser: AutoCategoriser | None,
) -> None:
    language = shell.language
    dark_mode = shell.dark_mode
    currency = view.currency

    def show_url() -> None:
        # Settings callbacks run inside dialogs that may already be gone; the band outlives them
        # and tells NiceGUI which browser to send the URL to.
        with band:
            ui.navigate.history.replace(view.url(query))

    spending_overview: SpendingOverview | None = None

    def show_overview() -> None:
        overview = view.overview(query)
        left_out_notice.show(
            texts.NOT_CONVERTED(language, overview.left_out, currency=currency)
            if overview.left_out
            else None
        )
        if spending_overview is None:
            return
        spending_overview.show(
            overview.days,
            overview.compared_days,
            _overview_label(overview, query.period, language),
            query.comparison,
            exchanged=overview.exchanged,
        )

    @ui.refreshable
    def overview() -> None:
        nonlocal spending_overview
        spending_overview = SpendingOverview(currency, language, dark=bool(dark_mode.value))

    def category_options() -> list[CategoryOption]:
        return [
            *(
                CategoryOption(id=category.id, name=category.name, colour_slot=category.colour_slot)
                for category in view.book.categories
            ),
            CategoryOption(id=UNCATEGORISED, name=texts.UNCATEGORISED(language), colour_slot=None),
        ]

    def assigned_category(counterparty: str) -> str | None:
        category = view.book.category_of(counterparty)
        return category.id if category else None

    def category_entries() -> list[CategoryEntry]:
        return [
            CategoryEntry(id=category.id, name=category.name, usage=view.book.usage(category.id))
            for category in view.book.categories
        ]

    def category_names() -> dict[str, str]:
        return {category.id: category.name for category in view.book.categories}

    category_donut: Donut | None = None

    def show_categories() -> None:
        nonlocal query
        if category_donut is not None:
            category_donut.update(_donut_slices(view.category_slices(query.period), language))
        settings.update(
            category_entries(), category_names(), assigned_category, view.book.is_ai_assigned
        )
        checked = view.checked(query)
        if checked != query:
            query = checked
            show_url()
        filters.update_categories(category_options(), query.spending_filter)
        show_overview()

    async def change_and_show(change: Callable[[CategoryBook], None]) -> None:
        nonlocal view

        def changed(fresh: CategoryBook) -> CategoryBook:
            change(fresh)
            return fresh

        view = view.with_book(await run.io_bound(store.update, changed))
        show_categories()

    async def change_category(counterparty: str, value: str | None) -> None:
        if value == assigned_category(counterparty):
            return

        try:
            await change_and_show(lambda fresh: fresh.assign_choice(counterparty, value))
        except InvalidCategoryNameError:
            ui.notify(texts.CATEGORY_NAME_LENGTH(language), type="negative")
            show_categories()

    async def rename_category(category_id: str, name: str) -> None:
        try:
            await change_and_show(lambda fresh: fresh.rename(category_id, name))
        except InvalidCategoryNameError:
            ui.notify(texts.CATEGORY_NAME_LENGTH(language), type="negative")
            show_categories()
            return
        except DuplicateCategoryError as error:
            ui.notify(texts.CATEGORY_EXISTS(language, name=error.name), type="negative")
            show_categories()

    async def delete_category(category_id: str) -> None:
        await change_and_show(lambda fresh: fresh.delete(category_id))

    async def categorise_with_ai(categoriser: AutoCategoriser) -> None:
        nonlocal view
        try:
            # Every stored payment, as the daily sync sends, not only those with a rate.
            assigned = await run.io_bound(categoriser.run, view.stored_payments)
        except CategorisationUnavailableError:
            ui.notify(texts.AI_UNAVAILABLE(language), type="negative")
        else:
            if assigned:
                ui.notify(texts.AI_CATEGORISED(language, assigned), type="positive")
            else:
                ui.notify(texts.AI_NOTHING_ASSIGNED(language))
        # A failure part way still keeps the batches answered before it.
        view = view.with_book(await run.io_bound(store.load))
        show_categories()

    settings = SettingsDialog(
        category_entries(),
        view.counterparty_totals(),
        category_names(),
        currency,
        rename_category,
        delete_category,
        change_category,
        None
        if auto_categoriser is None
        else functools.partial(categorise_with_ai, auto_categoriser),
        language,
    )
    with shell.actions:
        settings_button(settings.open, language)

    @ui.refreshable
    def breakdown() -> None:
        nonlocal category_donut
        category_donut = None
        shown = view.breakdown(query.period)
        if shown is None:
            return
        dark = bool(dark_mode.value)
        with ui.grid().classes("w-full grid-cols-1 md:grid-cols-2 gap-4"):
            with section(texts.COUNTERPARTIES(language), currency):
                Donut(
                    _donut_slices(shown.counterparties, language),
                    currency,
                    legend_label=texts.COUNTERPARTIES(language),
                    dark=dark,
                    testid="counterparty-donut",
                )
            with section(texts.CATEGORIES(language), currency):
                category_donut = Donut(
                    _donut_slices(shown.categories, language),
                    currency,
                    legend_label=texts.CATEGORIES(language),
                    dark=dark,
                    testid="categories",
                )

    def select(period: Period) -> None:
        nonlocal query
        query = replace(query, period=period)
        show_url()
        show_overview()
        breakdown.refresh()

    def compare(comparison: Comparison) -> None:
        nonlocal query
        query = replace(query, comparison=comparison)
        show_url()
        show_overview()

    def show_in(chosen_currency: str) -> None:
        # Every amount on the page changes; the filter sits at the top, so a reload costs no
        # scroll position.
        ui.navigate.to(view.url(query, chosen_currency))

    def choose(spending_filter: SpendingFilter) -> None:
        nonlocal query
        query = replace(query, spending_filter=spending_filter)
        show_url()
        show_overview()

    with band:
        with ui.row().classes("w-full items-center gap-4"):
            period_filter(query.period, select, language)
            comparison_filter(query.comparison, compare, language)
            currency_filter(view.currencies, currency, show_in, language)
        filters = SpendingFilters(
            view.counterparties, category_options(), query.spending_filter, choose, language
        )
        overview()
        # Below the chart, so the notice coming and going on an edit never pushes the chart.
        left_out_notice = Alert(testid="rates-error")
        show_overview()
    breakdown()

    async def redraw() -> None:
        # Not awaited, the refresh runs later and `show_overview` would fill the old chart.
        await overview.refresh()
        show_overview()
        breakdown.refresh()

    dark_mode.on_value_change(redraw)


def _show_connection(
    refreshed: Refreshed,
    connection_ends_on: date | None,
    service: BankingService,
    warning_days: int,
    language: Language,
) -> None:
    """Says why the bank could not be asked and offers to connect it, or counts down to the end
    of the connection."""
    if refreshed.bank is BankStatus.SESSION_EXPIRED:
        alert(texts.BANK_ERRORS[BankErrorCode.SESSION_EXPIRED](language))
    elif refreshed.bank is BankStatus.BANK_UNAVAILABLE:
        alert(texts.BANK_ERRORS[BankErrorCode.BANK_UNAVAILABLE](language))
    if refreshed.needs_connection and not refreshed.payments:
        empty_state(texts.NO_TRANSACTIONS(language))
    if refreshed.needs_connection:
        primary_button(
            texts.CONNECT_BANK(language), _connector(service, language), testid="connect-bank"
        )
    elif connection_ends_on is not None:
        reconnect_notice(
            connection_ends_on,
            warning_days,
            language,
            service.today,
            _connector(service, language),
        )


def register(modules: Modules) -> None:
    @ui.page("/")
    async def dashboard_page(
        period: str | None = None,
        compare: str | None = None,
        currency: str | None = None,
        counterparty: str | None = None,
        category: str | None = None,
        bank_error: str | None = None,
    ) -> None:
        settings = modules.settings
        bank = modules.bank
        error = _error_from(bank_error)
        with page_shell(settings.app_title, settings.default_language) as shell:
            language = shell.language
            with overview_band() as band:
                with ui.row().classes("w-full items-center justify-between gap-4"):
                    ui.label(texts.OVERVIEW(language)).classes("text-2xl font-normal").props(
                        'role="heading" aria-level="1"'
                    )
                    if settings.enable_banking_environment == "sandbox":
                        chip("science", texts.SANDBOX(language))
                if bank is None:
                    alert(texts.BANK_ERRORS[BankErrorCode.NOT_CONFIGURED](language))
                    return
                service = bank.service
                if error:
                    alert(texts.BANK_ERRORS[error](language))
                refreshed = await run.io_bound(bank.refresher.refresh)
                _show_connection(
                    refreshed,
                    await run.io_bound(service.connection_ends_on),
                    service,
                    settings.reconnect_warning_days,
                    language,
                )
                if not refreshed.payments:
                    if not refreshed.needs_connection:
                        empty_state(texts.NO_RECENT_SPENDING(language))
                    return
                if refreshed.rates_error is not None:
                    alert(texts.RATES_UNAVAILABLE(language), testid="rates-error")
                store = modules.category_store
                view = SpendingView(
                    refreshed.payments,
                    refreshed.rates,
                    display_currencies=settings.display_currencies,
                    requested_currency=currency,
                    book=await run.io_bound(store.load),
                    today=service.today(),
                    slice_limit=len(LIGHT.categories),
                )
            query = view.parse(
                period=period, compare=compare, counterparty=counterparty, category=category
            )
            _spending_view(view, query, shell, band, store, modules.auto_categoriser)
