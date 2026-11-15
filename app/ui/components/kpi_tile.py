from nicegui import ui


def kpi_tile(label: str, value: str, *, testid: str) -> None:
    with ui.column().classes("gap-1"):
        ui.label(value).classes("text-4xl font-normal").props(f'data-testid="{testid}"')
        ui.label(label).classes("text-xs text-muted")
