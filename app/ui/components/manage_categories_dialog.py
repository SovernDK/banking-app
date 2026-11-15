from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from nicegui import ui

from app.ui.components.ghost_button import ghost_button
from app.ui.components.primary_button import primary_button


@dataclass(frozen=True)
class CategoryEntry:
    id: str
    name: str
    usage: int


def _delete_warning(entry: CategoryEntry) -> str:
    if entry.usage == 0:
        return f"Delete {entry.name}?"
    names = "counterparty" if entry.usage == 1 else "counterparties"
    return f"Delete {entry.name}? {entry.usage} {names} will become Uncategorised."


def manage_categories_dialog(
    categories: Callable[[], list[CategoryEntry]],
    on_rename: Callable[[str, str], Awaitable[None]],
    on_delete: Callable[[str], Awaitable[None]],
) -> Callable[[], None]:
    """Builds the dialog and returns the function that opens it with the current categories."""

    async def confirm_delete(entry: CategoryEntry) -> None:
        with ui.dialog() as confirm, ui.card().props("flat bordered").classes("rounded-xl p-4"):
            ui.label(_delete_warning(entry)).classes("text-sm")
            with ui.row().classes("w-full justify-end gap-2"):
                ghost_button("Cancel", lambda: confirm.submit(False))
                primary_button("Delete", lambda: confirm.submit(True), testid="confirm-delete")
        if await confirm:
            await on_delete(entry.id)
            content.refresh()
        confirm.delete()

    async def rename(entry: CategoryEntry, name: str) -> None:
        if name != entry.name:
            await on_rename(entry.id, name)
            content.refresh()

    @ui.refreshable
    def content() -> None:
        for entry in categories():
            with ui.row().classes("w-full items-center gap-2 no-wrap"):
                field = (
                    ui.input(value=entry.name)
                    .classes("flex-1")
                    .props("dense outlined maxlength=40")
                )
                field.props["aria-label"] = f"Name of {entry.name}"
                field.on("blur", lambda _, entry=entry, field=field: rename(entry, field.value))
                field.on(
                    "keydown.enter", lambda _, entry=entry, field=field: rename(entry, field.value)
                )
                delete = ui.button(
                    icon="delete", on_click=lambda _, entry=entry: confirm_delete(entry)
                ).props("flat round color=inherit")
                delete.props["aria-label"] = f"Delete {entry.name}"

    with (
        ui.dialog() as dialog,
        ui.card().props("flat bordered").classes("w-full max-w-md rounded-xl p-4 gap-4"),
    ):
        ui.label("Categories").classes("text-lg font-medium").props('role="heading" aria-level="2"')
        with ui.column().classes("w-full gap-2"):
            content()
        with ui.row().classes("w-full justify-end"):
            ghost_button("Done", dialog.close)

    def open_dialog() -> None:
        content.refresh()
        dialog.open()

    return open_dialog
