from nicegui import ui


def chip(icon: str, text: str) -> None:
    with ui.row().classes("yiji-chip items-center gap-1 rounded-md px-2 py-1 text-xs"):
        ui.icon(icon).props('aria-hidden="true"')
        ui.label(text)
