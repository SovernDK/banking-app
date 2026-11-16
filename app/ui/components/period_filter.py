from collections.abc import Callable

from nicegui import ui

from app.spending import Comparison, Period
from app.ui.components.toggle_filter import toggle_filter


def period_filter(value: Period, on_change: Callable[[Period], None]) -> ui.toggle:
    return toggle_filter(
        {period.value: period.label for period in Period},
        value.value,
        lambda chosen: on_change(Period(chosen)),
        label="Period",
        testid="period-filter",
    )


def comparison_filter(value: Comparison, on_change: Callable[[Comparison], None]) -> ui.toggle:
    return toggle_filter(
        {comparison.value: comparison.label for comparison in Comparison},
        value.value,
        lambda chosen: on_change(Comparison(chosen)),
        label="Compare with",
        testid="comparison-filter",
    )
