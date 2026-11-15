from collections.abc import Iterator
from contextlib import contextmanager

from nicegui import ui

from app.ui.palette import DARK, LIGHT, Palette


def _theme_variables(palette: Palette) -> str:
    return (
        f"--yiji-ink: {palette.ink}; --yiji-inverse-text: {palette.inverse_text};"
        f" --yiji-text: {palette.text}; --yiji-muted: {palette.muted};"
        f" --yiji-band: {palette.band}; --yiji-page: {palette.page};"
        f" --yiji-card: {palette.card}; --yiji-card-muted: {palette.card_muted};"
        f" --yiji-border: {palette.border};"
        f" --q-primary: {palette.ink}; --q-positive: {palette.gain};"
        f" --q-negative: {palette.loss}; --q-warning: {palette.warning};"
    )


THEME_CSS = f"""
body {{ {_theme_variables(LIGHT)} }}
body.body--dark {{ {_theme_variables(DARK)} }}
body {{
    background-color: var(--yiji-page);
    color: var(--yiji-text);
    font-family: Inter, system-ui, sans-serif;
    font-variant-numeric: tabular-nums;
}}
.yiji-top-bar {{
    background-color: var(--yiji-page);
    color: var(--yiji-text);
    border-bottom: 1px solid var(--yiji-border);
}}
.yiji-band {{ background-color: var(--yiji-band); }}
.q-card {{
    background-color: var(--yiji-card);
    border-color: var(--yiji-border);
}}
.text-muted {{ color: var(--yiji-muted); }}
"""


@contextmanager
def page_shell(title: str) -> Iterator[None]:
    ui.colors(primary=LIGHT.ink, positive=LIGHT.gain, negative=LIGHT.loss, warning=LIGHT.warning)
    ui.add_css(THEME_CSS)
    dark_mode = ui.dark_mode()
    with ui.header().classes("yiji-top-bar items-center justify-between px-6 py-3"):
        ui.label(title).classes("text-lg font-semibold")
        ui.button(icon="dark_mode", on_click=dark_mode.toggle).props(
            'flat round color=inherit aria-label="Toggle dark mode"'
        )
    with ui.column().classes("w-full max-w-6xl mx-auto p-4 gap-4"):
        yield
