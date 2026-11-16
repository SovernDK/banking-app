from collections.abc import Iterator
from contextlib import contextmanager

from nicegui import ui


@contextmanager
def section(title: str, subtitle: str | None = None) -> Iterator[ui.label]:
    with ui.card().props("flat bordered").classes("w-full rounded-xl p-4"):
        heading = (
            ui.label(title).classes("text-2xl font-normal").props('role="heading" aria-level="2"')
        )
        if subtitle:
            ui.label(subtitle).classes("text-xs text-muted")
        yield heading
