from collections.abc import Awaitable, Callable

from nicegui import ui


def ghost_button(
    label: str,
    on_click: Callable[[], Awaitable[None] | None],
    *,
    icon: str | None = None,
    testid: str | None = None,
) -> ui.button:
    button = ui.button(label, icon=icon, on_click=on_click).props("flat no-caps color=inherit")
    if testid:
        button.props["data-testid"] = testid
    return button
