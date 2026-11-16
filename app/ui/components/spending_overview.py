from decimal import Decimal
from typing import Any

from nicegui import ui

from app.spending import DailySpending
from app.ui import format as fmt
from app.ui.components.chart import chart
from app.ui.components.empty_state import empty_state
from app.ui.components.kpi_tile import KpiTile
from app.ui.components.section import section


def _spending_option(days: list[DailySpending], currency: str) -> dict[str, Any]:
    return {
        "xAxis": {"type": "category", "data": [fmt.date(entry.day) for entry in days]},
        "yAxis": {"type": "value"},
        "tooltip": {"trigger": "axis", "formatter": f"{{b}}<br/>{{c}} {currency}"},
        "series": [
            {
                "name": "Spending",
                "type": "bar",
                "data": [float(entry.amount) for entry in days],
                "itemStyle": {"borderRadius": [4, 4, 0, 0]},
            }
        ],
    }


class SpendingOverview:
    """Period total and spending-per-day bars. `show` redraws them in place, and the chart box
    keeps its height when empty, so a redraw never moves the page."""

    def __init__(self, currency: str, *, dark: bool) -> None:
        self._currency = currency
        self._total = KpiTile(testid="total")
        with (
            section("Spending per day", currency),
            ui.column().classes("w-full h-72 justify-center"),
        ):
            self._chart = chart(_spending_option([], currency), dark=dark, testid="spending-chart")
            self._empty = empty_state("No spending in this period.")

    def show(self, days: list[DailySpending], label: str) -> None:
        total = sum((entry.amount for entry in days), Decimal(0))
        self._total.show(fmt.money(total, self._currency), label)
        option = _spending_option(days, self._currency)
        self._chart.options["xAxis"]["data"] = option["xAxis"]["data"]
        self._chart.options["series"][0]["data"] = option["series"][0]["data"]
        self._chart.update()
        self._chart.set_visibility(total != 0)
        self._empty.set_visibility(total == 0)
