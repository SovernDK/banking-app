from collections.abc import Awaitable, Callable

from nicegui import ui
from nicegui.events import ValueChangeEventArguments

from app import texts
from app.i18n import Language
from app.spending_view import CounterpartyTotal
from app.ui import format as fmt


class CounterpartiesTable:
    """One category select per counterparty. `update` changes the selects in place instead of
    rebuilding the rows, so editing never moves the page."""

    def __init__(
        self,
        rows: list[CounterpartyTotal],
        categories: dict[str, str],
        currency: str,
        on_change: Callable[[str, str | None], Awaitable[None]],
        language: Language,
    ) -> None:
        """`on_change` gets a category id, a typed new category name, or None to uncategorise."""
        self._on_change = on_change
        self._selects: dict[str, ui.select] = {}
        self._ai_badges: dict[str, ui.element] = {}
        with ui.element("ul").classes("w-full flex flex-col").props('data-testid="counterparties"'):
            for row in rows:
                with ui.element("li").classes(
                    "yiji-divider flex flex-wrap items-center gap-x-4 gap-y-1 py-2"
                ):
                    ui.label(row.name).classes("flex-1 min-w-40 text-sm")
                    amount = (
                        texts.NO_RATE(language)
                        if row.amount is None
                        else fmt.money(row.amount, currency)
                    )
                    ui.label(amount).classes("text-sm")
                    self._ai_badges[row.name] = _ai_badge(row.ai_assigned, language)
                    select = (
                        ui.select(
                            dict(categories),
                            value=row.category_id,
                            label=texts.CATEGORY(language),
                            with_input=True,
                            new_value_mode="add-unique",
                            clearable=True,
                            on_change=lambda event, name=row.name: self._changed(event, name),
                        )
                        .classes("w-56")
                        .props("dense outlined")
                    )
                    # Names come from the bank, so they never go through the props parser.
                    select.props["aria-label"] = texts.CATEGORY_FOR(language, name=row.name)
                    self._selects[row.name] = select

    async def _changed(self, event: ValueChangeEventArguments, name: str) -> None:
        # Quasar keeps the menu open after Enter adds a typed value; picking one closes it anyway.
        event.sender.run_method("hidePopup")
        await self._on_change(name, event.value)

    def update(
        self,
        categories: dict[str, str],
        category_of: Callable[[str], str | None],
        is_ai_assigned: Callable[[str], bool],
    ) -> None:
        for name, select in self._selects.items():
            select.set_options(dict(categories), value=category_of(name))
            self._ai_badges[name].set_visibility(is_ai_assigned(name))


def _ai_badge(visible: bool, language: Language) -> ui.element:
    with ui.element("span").classes("yiji-chip rounded-md px-2 py-0.5 text-xs") as badge:
        ui.label(texts.AI_ASSIGNED_BADGE(language)).props('aria-hidden="true"')
        ui.label(texts.AI_ASSIGNED(language)).classes("sr-only")
    badge.props["data-testid"] = "ai-badge"
    badge.tooltip(texts.AI_ASSIGNED(language))
    badge.set_visibility(visible)
    return badge
