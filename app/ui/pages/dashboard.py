from datetime import date
from decimal import Decimal
from urllib.parse import urlencode

from nicegui import run, ui

from app import texts
from app.bank_profiles import BankProfile, profile_for, transaction_name
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
from app.i18n import Language
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
    empty_state,
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


def _connect_button(service: BankingService, language: Language) -> None:
    async def connect() -> None:
        try:
            url = await run.io_bound(service.connect_url)
        except BankApiError:
            ui.notify(texts.BANK_ERRORS[BankErrorCode.BANK_UNAVAILABLE](language), type="negative")
            return
        ui.navigate.to(url)

    primary_button(texts.CONNECT_BANK(language), connect, testid="connect-bank")


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


def _spending_view(
    transactions: list[Transaction],
    today: date,
    initial: Period,
    initial_comparison: Comparison,
    counterparty_query: str | None,
    category_query: str | None,
    shell: PageShell,
    band: ui.column,
    profile: BankProfile,
    store: CategoryStore,
    book: CategoryBook,
) -> None:
    currency = main_currency(transactions)
    language = shell.language
    if currency is None:
        with band:
            empty_state(texts.NO_RECENT_SPENDING(language))
        return
    dark_mode = shell.dark_mode
    spending = {period: daily_spending(transactions, currency, period, today) for period in Period}
    selected = initial
    comparison = initial_comparison

    def spends_in(period: Period) -> bool:
        return any(entry.amount for entry in spending[period])

    counterparties = counterparty_names(transactions, currency, profile)
    spending_filter = SpendingFilter.parse(counterparty_query, category_query, counterparties, book)

    def show_url() -> None:
        query = urlencode(
            {"period": selected.value, **spending_filter.query(), "compare": comparison.value}
        )
        # Settings callbacks run inside dialogs that may already be gone; the band outlives them
        # and tells NiceGUI which browser to send the URL to.
        with band:
            ui.navigate.history.replace(f"/?{query}")

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
        matching = [
            transaction
            for transaction in transactions
            if spending_filter.matches(transaction, profile, book)
        ]
        spending_overview.show(
            daily_spending(matching, currency, selected, today),
            daily_spending(matching, currency, selected, comparison.shift(today)),
            overview_label(),
            comparison,
        )

    @ui.refreshable
    def overview() -> None:
        nonlocal spending_overview
        spending_overview = SpendingOverview(currency, language, dark=bool(dark_mode.value))
        show_overview()

    def category_options() -> list[CategoryOption]:
        return [
            *(
                CategoryOption(id=category.id, name=category.name, colour_slot=category.colour_slot)
                for category in book.categories
            ),
            CategoryOption(id=UNCATEGORISED, name=texts.UNCATEGORISED(language), colour_slot=None),
        ]

    def category_id_of(transaction: Transaction) -> str | None:
        category = book.category_of(counterparty_name(transaction))
        return category.id if category else None

    def category_slices() -> list[DonutSlice]:
        shares = spending_by(transactions, currency, selected, today, category_id_of)
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
        settings.update(category_entries(), category_names(), assigned_category)
        revalidated = SpendingFilter.parse(
            spending_filter.counterparty, spending_filter.category_id, counterparties, book
        )
        if revalidated != spending_filter:
            spending_filter = revalidated
            show_url()
        filters.update_categories(category_options(), spending_filter)
        show_overview()

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
        except InvalidCategoryNameError:
            ui.notify(texts.CATEGORY_NAME_LENGTH(language), type="negative")
            show_categories()
            return
        book.assign(counterparty, category_id)
        await save_and_show()

    async def rename_category(category_id: str, name: str) -> None:
        try:
            book.rename(category_id, name)
        except InvalidCategoryNameError:
            ui.notify(texts.CATEGORY_NAME_LENGTH(language), type="negative")
            show_categories()
            return
        except DuplicateCategoryError as error:
            ui.notify(texts.CATEGORY_EXISTS(language, name=error.name), type="negative")
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
                    spending_by(
                        transactions,
                        currency,
                        selected,
                        today,
                        lambda transaction: transaction_name(transaction, profile),
                    )
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

    def choose(value: SpendingFilter) -> None:
        nonlocal spending_filter
        spending_filter = value
        show_url()
        show_overview()

    with band:
        with ui.row().classes("w-full items-center gap-4"):
            period_filter(initial, select, language)
            comparison_filter(comparison, compare, language)
            filters = SpendingFilters(
                counterparties, category_options(), spending_filter, choose, language
            )
        overview()
    breakdown()

    def redraw() -> None:
        overview.refresh()
        breakdown.refresh()

    dark_mode.on_value_change(redraw)


def register() -> None:
    @ui.page("/")
    async def dashboard_page(
        period: str | None = None,
        compare: str | None = None,
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
                try:
                    transactions = await run.io_bound(service.transactions)
                except NotConnectedError:
                    empty_state(texts.NO_TRANSACTIONS(language))
                    _connect_button(service, language)
                    return
                except BankSessionExpiredError:
                    alert(texts.BANK_ERRORS[BankErrorCode.SESSION_EXPIRED](language))
                    _connect_button(service, language)
                    return
                except BankApiError:
                    alert(texts.BANK_ERRORS[BankErrorCode.BANK_UNAVAILABLE](language))
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
                Comparison.parse(compare),
                counterparty,
                category,
                shell,
                band,
                profile,
                store,
                book,
            )
