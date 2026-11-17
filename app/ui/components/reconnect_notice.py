from collections.abc import Awaitable, Callable
from datetime import date

from nicegui import ui

from app import texts
from app.i18n import Language
from app.ui.components.primary_button import primary_button


def ends_in_text(language: Language, days: int) -> str:
    if days == 0:
        return texts.CONNECTION_ENDS_TODAY(language)
    return texts.CONNECTION_ENDS_IN(language, days)


def reconnect_notice(
    ends_on: date,
    warning_days: int,
    language: Language,
    today: Callable[[], date],
    on_reconnect: Callable[[], Awaitable[None]],
) -> None:
    """Counts down the bank connection's last days in place, so an open dashboard stays right
    across midnight without a reload."""
    with (
        ui.row()
        .classes("yiji-alert w-full flex-wrap items-center justify-between gap-2 rounded-xl p-4")
        .props('role="status" data-testid="reconnect-notice"') as notice
    ):
        with ui.row().classes("min-w-0 flex-1 flex-nowrap items-center gap-2 text-sm"):
            ui.icon("warning").props('aria-hidden="true"')
            message = ui.label()
        primary_button(texts.RECONNECT_BANK(language), on_reconnect, testid="reconnect-bank")

    def update() -> None:
        days = (ends_on - today()).days
        notice.set_visibility(0 <= days <= warning_days)
        message.set_text(ends_in_text(language, max(days, 0)))

    update()
    ui.timer(3600, update)
