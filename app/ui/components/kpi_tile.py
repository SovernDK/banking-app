from typing import Literal

from nicegui import ui

Tone = Literal["gain", "loss", "muted"]
_TONE_CLASSES: dict[Tone, str] = {
    "gain": "text-positive",
    "loss": "text-negative",
    "muted": "text-muted",
}


class KpiTile:
    """Big number over a muted label and a delta line; `show` changes them in place."""

    def __init__(self, *, testid: str) -> None:
        with ui.column().classes("gap-1"):
            self._value = (
                ui.label().classes("text-4xl font-normal").props(f'data-testid="{testid}"')
            )
            self._label = (
                ui.label().classes("text-xs text-muted").props(f'data-testid="{testid}-label"')
            )
            self._delta = ui.label().classes("text-xs").props(f'data-testid="{testid}-delta"')

    def show(self, value: str, label: str, delta: str, tone: Tone) -> None:
        self._value.set_text(value)
        self._label.set_text(label)
        self._delta.set_text(delta)
        self._delta.classes(replace=f"text-xs {_TONE_CLASSES[tone]}")
