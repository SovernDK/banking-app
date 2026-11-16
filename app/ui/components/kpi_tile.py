from nicegui import ui


class KpiTile:
    """Big number over a muted label; `show` changes both in place."""

    def __init__(self, *, testid: str) -> None:
        with ui.column().classes("gap-1"):
            self._value = (
                ui.label().classes("text-4xl font-normal").props(f'data-testid="{testid}"')
            )
            self._label = (
                ui.label().classes("text-xs text-muted").props(f'data-testid="{testid}-label"')
            )

    def show(self, value: str, label: str) -> None:
        self._value.set_text(value)
        self._label.set_text(label)
