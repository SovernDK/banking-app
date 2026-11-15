from collections.abc import Callable

from nicegui import ui

from app.spending import Period


def period_filter(value: Period, on_change: Callable[[Period], None]) -> ui.toggle:
    return (
        ui.toggle(
            {period.value: period.label for period in Period},
            value=value.value,
            on_change=lambda event: on_change(Period(event.value)),
        )
        .classes("yiji-toggle rounded-lg")
        .props(
            "unelevated no-caps toggle-color=yiji-ink toggle-text-color=yiji-inverse"
            ' aria-label="Period" data-testid="period-filter"'
        )
    )
