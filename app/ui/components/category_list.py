from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from nicegui import ui

from app import texts
from app.i18n import Language
from app.ui.components.ghost_button import ghost_button
from app.ui.components.primary_button import primary_button


@dataclass(frozen=True)
class CategoryEntry:
    id: str
    name: str
    usage: int


def _delete_warning(entry: CategoryEntry, language: Language) -> str:
    if entry.usage == 0:
        return texts.CONFIRM_DELETE(language, name=entry.name)
    return texts.CONFIRM_DELETE_IN_USE(language, entry.usage, name=entry.name)


@dataclass
class _Row:
    entry: CategoryEntry
    container: ui.row
    field: ui.input
    delete: ui.button


class CategoryList:
    """A name field and delete button per category. `update` adds, renames and removes rows in
    place instead of rebuilding the list, so editing never moves the page."""

    def __init__(
        self,
        entries: list[CategoryEntry],
        on_rename: Callable[[str, str], Awaitable[None]],
        on_delete: Callable[[str], Awaitable[None]],
        language: Language,
    ) -> None:
        self._language = language
        self._on_rename = on_rename
        self._on_delete = on_delete
        self._rows: dict[str, _Row] = {}
        with ui.column().classes("w-full gap-2").props('data-testid="categories-list"') as column:
            self._column = column
        self.update(entries)

    def update(self, entries: list[CategoryEntry]) -> None:
        current = {entry.id for entry in entries}
        for category_id in [known for known in self._rows if known not in current]:
            self._column.remove(self._rows.pop(category_id).container)
        for entry in entries:
            row = self._rows.get(entry.id)
            if row is None:
                self._rows[entry.id] = self._add_row(entry)
            else:
                row.entry = entry
                row.field.set_value(entry.name)
                self._label(row)

    def _add_row(self, entry: CategoryEntry) -> _Row:
        with self._column, ui.row().classes("w-full items-center gap-2 no-wrap") as container:
            field = (
                ui.input(value=entry.name).classes("flex-1").props("dense outlined maxlength=40")
            )
            delete = ui.button(
                icon="delete", on_click=lambda: self._confirm_delete(row.entry)
            ).props("flat round color=inherit")
        row = _Row(entry=entry, container=container, field=field, delete=delete)
        field.on("blur", lambda: self._rename(row))
        field.on("keydown.enter", lambda: self._rename(row))
        self._label(row)
        return row

    def _label(self, row: _Row) -> None:
        # Names are user input, so they never go through the props parser.
        row.field.props["aria-label"] = texts.CATEGORY_NAME_OF(self._language, name=row.entry.name)
        row.delete.props["aria-label"] = texts.DELETE_NAMED(self._language, name=row.entry.name)
        row.field.update()
        row.delete.update()

    async def _rename(self, row: _Row) -> None:
        if row.field.value != row.entry.name:
            await self._on_rename(row.entry.id, row.field.value)

    async def _confirm_delete(self, entry: CategoryEntry) -> None:
        with ui.dialog() as confirm, ui.card().props("flat bordered").classes("rounded-xl p-4"):
            ui.label(_delete_warning(entry, self._language)).classes("text-sm")
            with ui.row().classes("w-full justify-end gap-2"):
                ghost_button(texts.CANCEL(self._language), lambda: confirm.submit(False))
                primary_button(
                    texts.DELETE(self._language),
                    lambda: confirm.submit(True),
                    testid="confirm-delete",
                )
        if await confirm:
            await self._on_delete(entry.id)
        confirm.delete()
