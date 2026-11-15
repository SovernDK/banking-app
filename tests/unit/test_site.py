"""The hosted pages in site/ are static copies of app values; these tests keep them in step."""

import re

import pytest

from app.api.bank import CALLBACK_PATH
from app.banking.state import STATE_PATTERN
from app.config import PROJECT_ROOT
from app.ui.palette import DARK, LIGHT, Palette

SITE = PROJECT_ROOT / "site"


def test_callback_page_uses_app_state_pattern_and_callback_path() -> None:
    page = (SITE / "callback.html").read_text()

    assert f"/{STATE_PATTERN}/" in page
    assert CALLBACK_PATH in page


@pytest.mark.parametrize(("block", "palette"), [(0, LIGHT), (1, DARK)])
def test_site_colours_match_app_palette(block: int, palette: Palette) -> None:
    css = (SITE / "style.css").read_text().split("@media (prefers-color-scheme: dark)")[block]
    tokens = dict(re.findall(r"--([\w-]+):\s*(#[0-9A-Fa-f]{6})", css))

    assert tokens
    for name, value in tokens.items():
        assert getattr(palette, name.replace("-", "_")).upper() == value.upper(), name
