from collections.abc import Callable

from nicegui import ui


def toggle_filter(
    options: dict[str, str],
    value: str,
    on_change: Callable[[str], None],
    *,
    label: str,
    testid: str,
) -> ui.toggle:
    """Segmented buttons with exactly one always selected."""
    toggle = (
        ui.toggle(options, value=value, on_change=lambda event: on_change(event.value))
        .classes("yiji-toggle rounded-lg")
        .props(
            "unelevated no-caps toggle-color=yiji-ink toggle-text-color=yiji-inverse"
            f' data-testid="{testid}"'
        )
    )
    toggle.props["aria-label"] = label
    return toggle
