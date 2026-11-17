from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from nicegui import app, ui
from nicegui.events import ValueChangeEventArguments

from app import texts
from app.i18n import Language
from app.ui.palette import DARK, FONT_FAMILY, LIGHT, Palette


def _theme_variables(palette: Palette) -> str:
    return (
        f"--yiji-ink: {palette.ink}; --yiji-inverse-text: {palette.inverse_text};"
        f" --yiji-text: {palette.text}; --yiji-muted: {palette.muted};"
        f" --yiji-band: {palette.band}; --yiji-page: {palette.page};"
        f" --yiji-card: {palette.card}; --yiji-card-muted: {palette.card_muted};"
        f" --yiji-border: {palette.border}; --yiji-other-category: {palette.other_category};"
        + "".join(
            f" --yiji-category-{slot}: {colour};" for slot, colour in enumerate(palette.categories)
        )
        # Quasar writes its brand colours inline on <body> at startup; only !important lets
        # these theme values, and so their dark-mode versions, win over that inline style.
        + f" --q-primary: {palette.ink} !important; --q-positive: {palette.gain} !important;"
        f" --q-negative: {palette.loss} !important; --q-warning: {palette.warning} !important;"
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
.yiji-language .q-field__native, .yiji-language .q-field__append {{ color: var(--yiji-text); }}
.yiji-chip {{ border: 1px solid var(--yiji-border); }}
.yiji-box {{ border: 1px solid var(--yiji-border); }}
.yiji-divider {{ border-bottom: 1px solid var(--yiji-border); }}
.yiji-alert {{ background-color: var(--yiji-card-muted); }}
.yiji-alert .q-icon {{ color: var(--q-warning); }}
"""


@dataclass(frozen=True)
class PageShell:
    dark_mode: ui.dark_mode
    language: Language
    actions: ui.row
    """Header slot between the language picker and the dark-mode toggle, for buttons a page adds
    once its data loads."""


def _viewer_language(default: Language) -> Language:
    return Language.parse(app.storage.user.get("language")) or default


def _choose_language(event: ValueChangeEventArguments) -> None:
    language = Language.parse(event.value)
    if language is None:
        return
    app.storage.user["language"] = language.value
    # Every text is built in the viewer's language as the page is made, so the page is made
    # again; its URL keeps the chosen filters.
    ui.navigate.reload()


def _language_picker(language: Language) -> ui.select:
    picker = (
        ui.select(
            {option.value: option.label for option in Language},
            value=language.value,
            on_change=_choose_language,
        )
        .classes("yiji-language")
        .props('dense borderless options-dense data-testid="language"')
    )
    picker.props["aria-label"] = texts.LANGUAGE(language)
    return picker


@contextmanager
def page_shell(title: str, default_language: Language) -> Iterator[PageShell]:
    """The viewer's language is kept per browser and falls back to `default_language`."""
    ui.add_css(THEME_CSS)
    language = _viewer_language(default_language)
    ui.query("html").props(f"lang={language.value}")
    dark_mode = ui.dark_mode()
    with ui.header().classes("yiji-top-bar items-center justify-between px-6 py-3"):
        ui.label(title).classes("text-lg font-semibold")
        with ui.row().classes("items-center gap-1"):
            _language_picker(language)
            actions = ui.row().classes("items-center gap-1")
            toggle = ui.button(icon="dark_mode", on_click=dark_mode.toggle).props(
                "flat round color=inherit"
            )
            toggle.props["aria-label"] = texts.TOGGLE_DARK_MODE(language)
    with ui.column().classes("w-full max-w-6xl mx-auto p-4 gap-4"):
        yield PageShell(dark_mode=dark_mode, language=language, actions=actions)
