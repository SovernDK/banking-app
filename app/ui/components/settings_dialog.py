from collections.abc import Awaitable, Callable

from nicegui import ui

from app import texts
from app.i18n import Language
from app.spending_view import CounterpartyTotal
from app.ui.components.category_list import CategoryEntry, CategoryList
from app.ui.components.counterparties_table import CounterpartiesTable
from app.ui.components.ghost_button import ghost_button


def _box(title: str, testid: str) -> ui.expansion:
    box = (
        ui.expansion(title, value=False)
        .classes("yiji-box w-full shrink-0 rounded-xl overflow-hidden")
        .props("header-class=text-lg")
    )
    box.props["data-testid"] = testid
    return box


class SettingsDialog:
    """Categories and counterparties, each in a collapsible box; both start collapsed."""

    def __init__(
        self,
        categories: list[CategoryEntry],
        counterparties: list[CounterpartyTotal],
        category_names: dict[str, str],
        currency: str,
        on_rename: Callable[[str, str], Awaitable[None]],
        on_delete: Callable[[str], Awaitable[None]],
        on_assign: Callable[[str, str | None], Awaitable[None]],
        on_categorise_with_ai: Callable[[], Awaitable[None]] | None,
        language: Language,
    ) -> None:
        """Without `on_categorise_with_ai`, the dialog says how to turn AI categories on."""
        with (
            ui.dialog() as self._dialog,
            ui.card()
            .props('flat bordered data-testid="settings-dialog"')
            .classes("w-full max-w-2xl rounded-xl p-4 gap-4"),
        ):
            ui.label(texts.SETTINGS(language)).classes("text-lg font-medium").props(
                'role="heading" aria-level="2"'
            )
            with (
                _box(texts.CATEGORIES(language), "settings-categories"),
                ui.column().classes("w-full"),
            ):
                self._categories = CategoryList(categories, on_rename, on_delete, language)
            with (
                _box(texts.COUNTERPARTIES(language), "settings-counterparties"),
                ui.column().classes("w-full gap-1"),
            ):
                ui.label(texts.PICK_CATEGORY_HINT(language)).classes("text-xs text-muted")
                _ai_action(on_categorise_with_ai, language)
                self._counterparties = CounterpartiesTable(
                    counterparties, category_names, currency, on_assign, language
                )
            with ui.row().classes("w-full justify-end"):
                ghost_button(texts.DONE(language), self._dialog.close)

    def open(self) -> None:
        self._dialog.open()

    def update(
        self,
        categories: list[CategoryEntry],
        category_names: dict[str, str],
        category_of: Callable[[str], str | None],
        is_ai_assigned: Callable[[str], bool],
    ) -> None:
        self._categories.update(categories)
        self._counterparties.update(category_names, category_of, is_ai_assigned)


def _ai_action(on_click: Callable[[], Awaitable[None]] | None, language: Language) -> None:
    if on_click is None:
        ui.label(texts.AI_NOT_CONFIGURED(language)).classes("text-xs text-muted")
        return

    async def categorise() -> None:
        button.props("loading")
        try:
            await on_click()
        finally:
            button.props(remove="loading")

    button = ghost_button(
        texts.CATEGORISE_WITH_AI(language),
        categorise,
        icon="auto_awesome",
        testid="categorise-with-ai",
    )


def settings_button(on_click: Callable[[], None], language: Language) -> ui.button:
    button = ui.button(icon="settings", on_click=on_click).props(
        'flat round color=inherit data-testid="settings"'
    )
    button.props["aria-label"] = texts.SETTINGS(language)
    return button
