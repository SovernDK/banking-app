import functools
from collections.abc import Awaitable, Callable
from datetime import date
from decimal import Decimal
from urllib.parse import urlencode

from nicegui import run, ui

from app import texts
from app.ai_categories.client import CategorisationUnavailableError
from app.ai_categories.service import AutoCategoriser, find_auto_categoriser
from app.banking.client import BankApiError, BankSessionExpiredError
from app.banking.errors import BankErrorCode
from app.banking.service import BankingService, NotConnectedError, find_banking_service
from app.categories import (
    CATEGORIES_FILENAME,
    CategoryBook,
    CategoryStore,
    DuplicateCategoryError,
    InvalidCategoryNameError,
)
from app.config import Settings, get_settings
from app.i18n import Language
from app.payments import Payment, counterparty_name, display_name
from app.rates.book import convert_payments
from app.rates.client import RatesUnavailableError
from app.spending import (
    Comparison,
    Period,
    Share,
    all_time_spending_by,
    daily_spending,
    main_currency,
    merge_spellings,
    spending_by,
    top_shares,
)
from app.spending_filter import UNCATEGORISED, SpendingFilter, counterparty_names
from app.ui.components import (
    CategoryEntry,
    CategoryOption,
    CounterpartyRow,
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


CHART_SLICE_LIMIT = 7


def _counterparty_slices(shares: list[Share[str]], language: Language) -> list[DonutSlice]:
    kept, rest = top_shares(shares, CHART_SLICE_LIMIT)
    slices = [
        DonutSlice(label=share.key, amount=share.amount, colour_slot=rank)
        for rank, share in enumerate(kept)
    ]
    if rest:
        slices.append(DonutSlice(label=texts.OTHER(language), amount=rest, hatched=True))
    return slices


def _category_slices(
    shares: list[Share[str | None]], book: CategoryBook, language: Language
) -> list[DonutSlice]:
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
        slices.append(DonutSlice(label=texts.OTHER(language), amount=rest, hatched=True))
    if uncategorised:
        slices.append(DonutSlice(label=texts.UNCATEGORISED(language), amount=uncategorised))
    return slices


def _currency_options(settings: Settings, payments: list[Payment]) -> list[str]:
    """The configured display currencies, then any other currency the payments came in."""
    others = sorted({payment.currency for payment in payments} - set(settings.display_currencies))
    return [*settings.display_currencies, *others]


def _spending_view(
    payments: list[Payment],
    currency: str,
    converted: bool,
    currencies: list[str],
    default_currency: str,
    today: date,
    initial: Period,
    initial_comparison: Comparison,
    counterparty_query: str | None,
    category_query: str | None,
    shell: PageShell,
    band: ui.column,
    store: CategoryStore,
    book: CategoryBook,
    auto_categoriser: AutoCategoriser | None,
) -> None:
    language = shell.language
    dark_mode = shell.dark_mode
    spending = {period: daily_spending(payments, currency, period, today) for period in Period}
    selected = initial
    comparison = initial_comparison

    def spends_in(period: Period) -> bool:
        return any(entry.amount for entry in spending[period])

    counterparties = counterparty_names(payments, currency)
    spending_filter = SpendingFilter.parse(counterparty_query, category_query, counterparties, book)

    def url(shown_currency: str) -> str:
        chosen_currency = {"currency": shown_currency} if shown_currency != default_currency else {}
        query = urlencode(
            {
                "period": selected.value,
                **spending_filter.query(),
                "compare": comparison.value,
                **chosen_currency,
            }
        )
        return f"/?{query}"

    def show_url() -> None:
        # Settings callbacks run inside dialogs that may already be gone; the band outlives them
        # and tells NiceGUI which browser to send the URL to.
        with band:
            ui.navigate.history.replace(url(currency))

    def overview_label() -> str:
        period = texts.PERIODS_IN_SENTENCE[selected](language)
        if spending_filter.category_id == UNCATEGORISED:
            return texts.SPENT_UNCATEGORISED(language, period=period)
        subject = spending_filter.subject(book)
        if subject:
            return texts.SPENT_ON(language, subject=subject, period=period)
        return texts.SPENT(language, period=period)

    spending_overview: SpendingOverview | None = None

    def show_overview() -> None:
        if spending_overview is None:
            return
        matching = [payment for payment in payments if spending_filter.matches(payment, book)]
        spending_overview.show(
            daily_spending(matching, currency, selected, today),
            daily_spending(matching, currency, selected, comparison.shift(today)),
            overview_label(),
            comparison,
        )

    @ui.refreshable
    def overview() -> None:
        nonlocal spending_overview
        spending_overview = SpendingOverview(
            currency, language, converted=converted, dark=bool(dark_mode.value)
        )
        show_overview()

    def category_options() -> list[CategoryOption]:
        return [
            *(
                CategoryOption(id=category.id, name=category.name, colour_slot=category.colour_slot)
                for category in book.categories
            ),
            CategoryOption(id=UNCATEGORISED, name=texts.UNCATEGORISED(language), colour_slot=None),
        ]

    def category_id_of(payment: Payment) -> str | None:
        category = book.category_of(counterparty_name(payment))
        return category.id if category else None

    def category_slices() -> list[DonutSlice]:
        shares = spending_by(payments, currency, selected, today, category_id_of)
        return _category_slices(shares, book, language)

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
        nonlocal spending_filter
        if category_donut is not None:
            category_donut.update(category_slices())
        settings.update(
            category_entries(), category_names(), assigned_category, book.is_ai_assigned
        )
        revalidated = SpendingFilter.parse(
            spending_filter.counterparty, spending_filter.category_id, counterparties, book
        )
        if revalidated != spending_filter:
            spending_filter = revalidated
            show_url()
        filters.update_categories(category_options(), spending_filter)
        show_overview()

    async def change_and_show(change: Callable[[CategoryBook], None]) -> None:
        nonlocal book

        def changed(fresh: CategoryBook) -> CategoryBook:
            change(fresh)
            return fresh

        book = await run.io_bound(store.update, changed)
        show_categories()

    async def change_category(counterparty: str, value: str | None) -> None:
        if value == assigned_category(counterparty):
            return

        def assign(fresh: CategoryBook) -> None:
            if value is None or fresh.get(value):
                category_id = value
            else:
                existing = fresh.find_by_name(value)
                category_id = existing.id if existing else fresh.create(value).id
            fresh.assign(counterparty, category_id)

        try:
            await change_and_show(assign)
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
        nonlocal book
        try:
            assigned = await run.io_bound(categoriser.run, payments)
        except CategorisationUnavailableError:
            ui.notify(texts.AI_UNAVAILABLE(language), type="negative")
        else:
            if assigned:
                ui.notify(texts.AI_CATEGORISED(language, assigned), type="positive")
            else:
                ui.notify(texts.AI_NOTHING_ASSIGNED(language))
        # A failure part way still keeps the batches answered before it.
        book = await run.io_bound(store.load)
        show_categories()

    settings = SettingsDialog(
        category_entries(),
        [
            CounterpartyRow(
                name=share.key,
                amount=share.amount,
                category_id=assigned_category(share.key),
                ai_assigned=book.is_ai_assigned(share.key),
            )
            for share in all_time_spending_by(payments, currency, counterparty_name)
            if share.key is not None
        ],
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
        if not spends_in(selected):
            return
        dark = bool(dark_mode.value)
        with ui.grid().classes("w-full grid-cols-1 md:grid-cols-2 gap-4"):
            with section(texts.COUNTERPARTIES(language), currency):
                counterparty_shares = merge_spellings(
                    spending_by(payments, currency, selected, today, display_name)
                )
                Donut(
                    _counterparty_slices(counterparty_shares, language),
                    currency,
                    legend_label=texts.COUNTERPARTIES(language),
                    dark=dark,
                    testid="counterparty-donut",
                )
            with section(texts.CATEGORIES(language), currency):
                category_donut = Donut(
                    category_slices(),
                    currency,
                    legend_label=texts.CATEGORIES(language),
                    dark=dark,
                    testid="categories",
                )

    def select(period: Period) -> None:
        nonlocal selected
        selected = period
        show_url()
        show_overview()
        breakdown.refresh()

    def compare(value: Comparison) -> None:
        nonlocal comparison
        comparison = value
        show_url()
        show_overview()

    def show_in(value: str) -> None:
        # Every amount on the page changes; the filter sits at the top, so a reload costs no
        # scroll position.
        ui.navigate.to(url(value))

    def choose(value: SpendingFilter) -> None:
        nonlocal spending_filter
        spending_filter = value
        show_url()
        show_overview()

    with band:
        with ui.row().classes("w-full items-center gap-4"):
            period_filter(initial, select, language)
            comparison_filter(comparison, compare, language)
            currency_filter(currencies, currency, show_in, language)
        filters = SpendingFilters(
            counterparties, category_options(), spending_filter, choose, language
        )
        overview()
    breakdown()

    def redraw() -> None:
        overview.refresh()
        breakdown.refresh()

    dark_mode.on_value_change(redraw)


async def _payments_or_connect(
    service: BankingService, language: Language
) -> tuple[list[Payment], bool]:
    """Brings the stored payments up to date when the bank allows; when it doesn't, says why and
    keeps showing what was stored before. Also tells whether the bank needs connecting."""
    needs_connection = False
    try:
        await run.io_bound(service.refresh)
    except NotConnectedError:
        needs_connection = True
    except BankSessionExpiredError:
        alert(texts.BANK_ERRORS[BankErrorCode.SESSION_EXPIRED](language))
        needs_connection = True
    except BankApiError:
        alert(texts.BANK_ERRORS[BankErrorCode.BANK_UNAVAILABLE](language))
    payments = await run.io_bound(service.payments)
    if needs_connection and not payments:
        empty_state(texts.NO_TRANSACTIONS(language))
    if needs_connection:
        primary_button(
            texts.CONNECT_BANK(language), _connector(service, language), testid="connect-bank"
        )
    else:
        ends_on = await run.io_bound(service.connection_ends_on)
        if ends_on is not None:
            reconnect_notice(
                ends_on,
                get_settings().reconnect_warning_days,
                language,
                service.today,
                _connector(service, language),
            )
    return payments, needs_connection


def register() -> None:
    @ui.page("/")
    async def dashboard_page(
        period: str | None = None,
        compare: str | None = None,
        currency: str | None = None,
        counterparty: str | None = None,
        category: str | None = None,
        bank_error: str | None = None,
    ) -> None:
        settings = get_settings()
        service = find_banking_service()
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
                if service is None:
                    alert(texts.BANK_ERRORS[BankErrorCode.NOT_CONFIGURED](language))
                    return
                if error:
                    alert(texts.BANK_ERRORS[error](language))
                payments, needs_connection = await _payments_or_connect(service, language)
                try:
                    await run.io_bound(service.refresh_rates, payments)
                except RatesUnavailableError:
                    alert(texts.RATES_UNAVAILABLE(language), testid="rates-error")
                rates = await run.io_bound(service.exchange_rates)
                default_currency = main_currency(payments, rates)
                if default_currency is None:
                    if not needs_connection:
                        empty_state(texts.NO_RECENT_SPENDING(language))
                    return
                currencies = _currency_options(settings, payments)
                shown_currency = currency if currency in currencies else default_currency
                converted, skipped = convert_payments(payments, shown_currency, rates)
                if skipped:
                    alert(
                        texts.NOT_CONVERTED(language, skipped, currency=shown_currency),
                        testid="rates-error",
                    )
                store = CategoryStore(
                    settings.data_dir / CATEGORIES_FILENAME, settings.starter_categories
                )
                book = await run.io_bound(store.load)
            _spending_view(
                converted,
                shown_currency,
                any(payment.currency != shown_currency for payment in payments),
                currencies,
                default_currency,
                service.today(),
                Period.parse(period),
                Comparison.parse(compare),
                counterparty,
                category,
                shell,
                band,
                store,
                book,
                find_auto_categoriser(),
            )
