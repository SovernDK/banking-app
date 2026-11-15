from collections.abc import Iterator
from contextlib import contextmanager

from nicegui import ui


@contextmanager
def overview_band() -> Iterator[None]:
    with ui.column().classes("yiji-band w-full rounded-2xl p-6 gap-4"):
        yield
