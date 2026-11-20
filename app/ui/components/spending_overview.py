from decimal import Decimal
from typing import Any

from nicegui import ui

from app import texts
from app.i18n import Language
from app.spending import Comparison, DailySpending, change
from app.ui import format as fmt
from app.ui.components.chart import chart, hatch_decal
from app.ui.components.empty_state import empty_state
from app.ui.components.kpi_tile import KpiTile, Tone
from app.ui.components.section import section
from app.ui.palette import DARK, LIGHT, Palette


def _spending_option(currency: str, palette: Palette, language: Language) -> dict[str, Any]:
    bar = {"type": "bar", "data": [], "barGap": "10%"}
    corners = {"borderRadius": [4, 4, 0, 0], "color": palette.ink}
    return {
        "xAxis": {"type": "category", "data": []},
        "yAxis": {"type": "value"},
        "tooltip": {
            "trigger": "axis",
            "formatter": f"{{b}}<br/>{{a0}}: {{c0}} {currency}<br/>{{a1}}: {{c1}} {currency}",
        },
        "series": [
            {**bar, "name": texts.THIS_PERIOD(language), "itemStyle": corners},
            {**bar, "name": "", "itemStyle": {**corners, "decal": hatch_decal(palette)}},
        ],
    }


def _delta(
    total: Decimal, previous: Decimal, currency: str, comparison: Comparison, language: Language
) -> tuple[str, Tone]:
    compared = texts.COMPARED_TOTAL(
        language,
        amount=fmt.money(previous, currency),
        ago=texts.COMPARISONS_AGO[comparison](language),
    )
    ratio = change(total, previous)
    if ratio is None or ratio == 0:
        return (compared if ratio is None else f"{fmt.pct(ratio)} {compared}"), "muted"
    # Spending more is the bad direction, so a rise reads as a loss.
    if ratio > 0:
        return f"▲ {fmt.pct(ratio)} {compared}", "loss"
    return f"▼ {fmt.pct(ratio)} {compared}", "gain"


def _amounts(days: list[DailySpending]) -> list[float]:
    return [float(entry.amount) for entry in days]


class SpendingOverview:
    """Period total and spending-per-day bars beside the compared days (hatched). `show` redraws
    them in place, and the chart box keeps its height when empty, so a redraw never moves the
    page. `converted` says some amounts came from another currency at their own day's rate."""

    def __init__(self, currency: str, language: Language, *, converted: bool, dark: bool) -> None:
        self._currency = currency
        self._language = language
        self._total = KpiTile(
            testid="total",
            note=texts.CONVERTED_COMPARISON(language) if converted else None,
        )
        with (
            section(texts.SPENDING_PER_DAY(language), currency) as self._title,
            ui.column().classes("w-full h-72 justify-center"),
        ):
            self._chart = chart(
                _spending_option(currency, DARK if dark else LIGHT, language),
                dark=dark,
                testid="spending-chart",
            )
            self._empty = empty_state(texts.NO_SPENDING_IN_PERIOD(language))

    def show(
        self,
        days: list[DailySpending],
        compared_days: list[DailySpending],
        label: str,
        comparison: Comparison,
    ) -> None:
        total = sum((entry.amount for entry in days), Decimal(0))
        previous = sum((entry.amount for entry in compared_days), Decimal(0))
        delta, tone = _delta(total, previous, self._currency, comparison, self._language)
        self._total.show(fmt.money(total, self._currency), label, delta, tone)
        ago = texts.COMPARISONS_AGO[comparison](self._language)
        self._title.set_text(texts.SPENDING_PER_DAY_VS(self._language, ago=ago))
        current, compared = self._chart.options["series"]
        self._chart.options["xAxis"]["data"] = [fmt.date(entry.day) for entry in days]
        current["data"] = _amounts(days)
        compared["data"] = _amounts(compared_days)
        compared["name"] = texts.COMPARED_SERIES[comparison](self._language)
        self._chart.update()
        has_spending = total != 0 or previous != 0
        self._chart.set_visibility(has_spending)
        self._empty.set_visibility(not has_spending)
