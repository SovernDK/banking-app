from collections.abc import Callable

from nicegui import ui

from app import texts
from app.i18n import Language
from app.spending import Comparison, Period
from app.ui.components.toggle_filter import toggle_filter


def period_filter(
    value: Period, on_change: Callable[[Period], None], language: Language
) -> ui.toggle:
    return toggle_filter(
        {period.value: texts.PERIODS[period](language) for period in Period},
        value.value,
        lambda chosen: on_change(Period(chosen)),
        label=texts.PERIOD(language),
        testid="period-filter",
    )


def comparison_filter(
    value: Comparison, on_change: Callable[[Comparison], None], language: Language
) -> ui.toggle:
    return toggle_filter(
        {comparison.value: texts.COMPARISONS[comparison](language) for comparison in Comparison},
        value.value,
        lambda chosen: on_change(Comparison(chosen)),
        label=texts.COMPARE_WITH(language),
        testid="comparison-filter",
    )


def currency_filter(
    currencies: list[str], value: str, on_change: Callable[[str], None], language: Language
) -> ui.toggle:
    return toggle_filter(
        {currency: currency for currency in currencies},
        value,
        on_change,
        label=texts.CURRENCY(language),
        testid="currency-filter",
    )
