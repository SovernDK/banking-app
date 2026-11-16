from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from nicegui import ui

from app.ui.palette import DARK, FONT_FAMILY, LIGHT, Palette


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
    font-family: {FONT_FAMILY};
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
.bg-yiji-ink {{ background-color: var(--yiji-ink); }}
.text-yiji-inverse {{ color: var(--yiji-inverse-text); }}
.yiji-toggle {{ border: 1px solid var(--yiji-muted); }}
.yiji-chip {{ border: 1px solid var(--yiji-border); }}
.yiji-box {{ border: 1px solid var(--yiji-border); }}
.yiji-divider {{ border-bottom: 1px solid var(--yiji-border); }}
.yiji-alert {{ background-color: var(--yiji-card-muted); }}
.yiji-alert .q-icon {{ color: var(--q-warning); }}
"""


@dataclass(frozen=True)
class PageShell:
    dark_mode: ui.dark_mode
    actions: ui.row
    """Header slot left of the dark-mode toggle, for buttons a page adds once its data loads."""


@contextmanager
def page_shell(title: str) -> Iterator[PageShell]:
    ui.colors(primary=LIGHT.ink, positive=LIGHT.gain, negative=LIGHT.loss, warning=LIGHT.warning)
    ui.add_css(THEME_CSS)
    dark_mode = ui.dark_mode()
    with ui.header().classes("yiji-top-bar items-center justify-between px-6 py-3"):
        ui.label(title).classes("text-lg font-semibold")
        with ui.row().classes("items-center gap-1"):
            actions = ui.row().classes("items-center gap-1")
            ui.button(icon="dark_mode", on_click=dark_mode.toggle).props(
                'flat round color=inherit aria-label="Toggle dark mode"'
            )
    with ui.column().classes("w-full max-w-6xl mx-auto p-4 gap-4"):
        yield PageShell(dark_mode=dark_mode, actions=actions)
