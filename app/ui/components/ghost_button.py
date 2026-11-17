from collections.abc import Awaitable, Callable

from nicegui import ui


def ghost_button(
    label: str,
    on_click: Callable[[], Awaitable[None] | None],
    *,
    icon: str | None = None,
    testid: str | None = None,
    icon_only_on_phones: bool = False,
) -> ui.button:
    if icon_only_on_phones and icon:
        button = ui.button(icon=icon, on_click=on_click)
        button.props["aria-label"] = label
        with button:
            ui.label(label).classes("ml-2 max-sm:hidden")
    else:
        button = ui.button(label, icon=icon, on_click=on_click)
    button.props("flat no-caps color=inherit")
    if testid:
        button.props["data-testid"] = testid
    return button
