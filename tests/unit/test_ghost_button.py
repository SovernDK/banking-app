import pytest

from app.ui.components.ghost_button import ghost_button


def _noop() -> None:
    pass


def test_icon_only_button_keeps_its_label_as_the_accessible_name() -> None:
    button = ghost_button("Clear filters", _noop, icon="filter_alt_off", icon_only_on_phones=True)

    assert button.props["aria-label"] == "Clear filters"


def test_labelled_button_is_named_by_its_visible_label_alone() -> None:
    button = ghost_button("Cancel", _noop, icon="close")

    assert "aria-label" not in button.props


@pytest.mark.parametrize("icon", [None, ""])
def test_icon_only_button_without_an_icon_is_rejected(icon: str | None) -> None:
    with pytest.raises(ValueError, match="needs an icon"):
        ghost_button("Clear filters", _noop, icon=icon, icon_only_on_phones=True)
