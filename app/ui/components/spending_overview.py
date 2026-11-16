from decimal import Decimal
from typing import Any

from nicegui import ui

from app.spending import Comparison, DailySpending, change
from app.ui import format as fmt
from app.ui.components.chart import chart, hatch_decal
from app.ui.components.empty_state import empty_state
from app.ui.components.kpi_tile import KpiTile, Tone
from app.ui.components.section import section
from app.ui.palette import DARK, LIGHT, Palette

CURRENT_SERIES = "This period"


def _spending_option(currency: str, palette: Palette) -> dict[str, Any]:
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
            {**bar, "name": CURRENT_SERIES, "itemStyle": corners},
            {**bar, "name": "", "itemStyle": {**corners, "decal": hatch_decal(palette)}},
        ],
    }


def _delta(total: Decimal, previous: Decimal, currency: str, ago: str) -> tuple[str, Tone]:
    compared = f"vs {fmt.money(previous, currency)} {ago}"
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
    page."""

    def __init__(self, currency: str, *, dark: bool) -> None:
        self._currency = currency
        self._total = KpiTile(testid="total")
        with (
            section("Spending per day", currency) as self._title,
            ui.column().classes("w-full h-72 justify-center"),
        ):
            self._chart = chart(
                _spending_option(currency, DARK if dark else LIGHT),
                dark=dark,
                testid="spending-chart",
            )
            self._empty = empty_state("No spending in this period.")

    def show(
        self,
        days: list[DailySpending],
        compared_days: list[DailySpending],
        label: str,
        comparison: Comparison,
    ) -> None:
        total = sum((entry.amount for entry in days), Decimal(0))
        previous = sum((entry.amount for entry in compared_days), Decimal(0))
        delta, tone = _delta(total, previous, self._currency, comparison.ago)
        self._total.show(fmt.money(total, self._currency), label, delta, tone)
        self._title.set_text(f"Spending per day vs {comparison.ago}")
        current, compared = self._chart.options["series"]
        self._chart.options["xAxis"]["data"] = [fmt.date(entry.day) for entry in days]
        current["data"] = _amounts(days)
        compared["data"] = _amounts(compared_days)
        compared["name"] = comparison.ago.capitalize()
        self._chart.update()
        has_spending = total != 0 or previous != 0
        self._chart.set_visibility(has_spending)
        self._empty.set_visibility(not has_spending)
