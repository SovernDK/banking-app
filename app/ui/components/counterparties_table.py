from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from decimal import Decimal

from nicegui import ui
from nicegui.events import ValueChangeEventArguments

from app.ui import format as fmt


@dataclass(frozen=True)
class CounterpartyRow:
    name: str
    amount: Decimal
    category_id: str | None


class CounterpartiesTable:
    """One category select per counterparty. `update` changes the selects in place instead of
    rebuilding the rows, so editing never moves the page."""

    def __init__(
        self,
        rows: list[CounterpartyRow],
        categories: dict[str, str],
        currency: str,
        on_change: Callable[[str, str | None], Awaitable[None]],
    ) -> None:
        """`on_change` gets a category id, a typed new category name, or None to uncategorise."""
        self._on_change = on_change
        self._selects: dict[str, ui.select] = {}
        with ui.element("ul").classes("w-full flex flex-col").props('data-testid="counterparties"'):
            for row in rows:
                with ui.element("li").classes(
                    "yiji-divider flex flex-wrap items-center gap-x-4 gap-y-1 py-2"
                ):
                    ui.label(row.name).classes("flex-1 min-w-40 text-sm")
                    ui.label(fmt.money(row.amount, currency)).classes("text-sm")
                    select = (
                        ui.select(
                            dict(categories),
                            value=row.category_id,
                            label="Category",
                            with_input=True,
                            new_value_mode="add-unique",
                            clearable=True,
                            on_change=lambda event, name=row.name: self._changed(event, name),
                        )
                        .classes("w-56")
                        .props("dense outlined")
                    )
                    # Names come from the bank, so they never go through the props parser.
                    select.props["aria-label"] = f"Category for {row.name}"
                    self._selects[row.name] = select

    async def _changed(self, event: ValueChangeEventArguments, name: str) -> None:
        # Quasar keeps the menu open after Enter adds a typed value; picking one closes it anyway.
        event.sender.run_method("hidePopup")
        await self._on_change(name, event.value)

    def update(self, categories: dict[str, str], category_of: Callable[[str], str | None]) -> None:
        for name, select in self._selects.items():
            select.set_options(dict(categories), value=category_of(name))
