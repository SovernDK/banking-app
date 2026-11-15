from collections.abc import Awaitable, Callable

from nicegui import ui


def primary_button(
    label: str, on_click: Callable[[], Awaitable[None] | None], *, testid: str
) -> ui.button:
    return (
        ui.button(label, on_click=on_click)
        .classes("rounded-lg px-4")
        .props(f'unelevated no-caps color=yiji-ink text-color=yiji-inverse data-testid="{testid}"')
    )
