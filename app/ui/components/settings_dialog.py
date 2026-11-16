from collections.abc import Awaitable, Callable

from nicegui import ui

from app.ui.components.category_list import CategoryEntry, CategoryList
from app.ui.components.counterparties_table import CounterpartiesTable, CounterpartyRow
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
        counterparties: list[CounterpartyRow],
        category_names: dict[str, str],
        currency: str,
        on_rename: Callable[[str, str], Awaitable[None]],
        on_delete: Callable[[str], Awaitable[None]],
        on_assign: Callable[[str, str | None], Awaitable[None]],
    ) -> None:
        with (
            ui.dialog() as self._dialog,
            ui.card()
            .props('flat bordered data-testid="settings-dialog"')
            .classes("w-full max-w-2xl rounded-xl p-4 gap-4"),
        ):
            ui.label("Settings").classes("text-lg font-medium").props(
                'role="heading" aria-level="2"'
            )
            with _box("Categories", "settings-categories"), ui.column().classes("w-full"):
                self._categories = CategoryList(categories, on_rename, on_delete)
            with (
                _box("Counterparties", "settings-counterparties"),
                ui.column().classes("w-full gap-1"),
            ):
                ui.label("Pick a category for each name; it applies to all their payments").classes(
                    "text-xs text-muted"
                )
                self._counterparties = CounterpartiesTable(
                    counterparties, category_names, currency, on_assign
                )
            with ui.row().classes("w-full justify-end"):
                ghost_button("Done", self._dialog.close)

    def open(self) -> None:
        self._dialog.open()

    def update(
        self,
        categories: list[CategoryEntry],
        category_names: dict[str, str],
        category_of: Callable[[str], str | None],
    ) -> None:
        self._categories.update(categories)
        self._counterparties.update(category_names, category_of)


def settings_button(on_click: Callable[[], None]) -> ui.button:
    return ui.button(icon="settings", on_click=on_click).props(
        'flat round color=inherit aria-label="Settings" data-testid="settings"'
    )
