from collections.abc import Awaitable, Callable

from nicegui import ui

# Quasar's `.block` label and `.on-left` icon margin are unlayered (the label `!important`), so
# only an important Tailwind utility, which sits in a layer, can override them.
_LABEL_HIDDEN_ON_PHONES = "max-sm:[&_.q-icon~.block]:hidden! max-sm:[&_.on-left]:mr-0!"


def ghost_button(
    label: str,
    on_click: Callable[[], Awaitable[None] | None],
    *,
    icon: str | None = None,
    testid: str | None = None,
    icon_only_on_phones: bool = False,
) -> ui.button:
    button = ui.button(label, icon=icon, on_click=on_click).props("flat no-caps color=inherit")
    if icon_only_on_phones:
        if not icon:
            raise ValueError("An icon-only button needs an icon to show on phones.")
        button.classes(_LABEL_HIDDEN_ON_PHONES)
        # The hidden label leaves only the icon's ligature text to name the button.
        button.props["aria-label"] = label
    if testid:
        button.props["data-testid"] = testid
    return button
