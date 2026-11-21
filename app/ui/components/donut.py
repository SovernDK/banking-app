from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from nicegui import ui

from app.ui import format as fmt
from app.ui.components.chart import chart, hatch_decal
from app.ui.palette import DARK, LIGHT, Palette


@dataclass(frozen=True)
class DonutSlice:
    """`colour_slot` indexes the category colours; None draws the neutral grey."""

    label: str
    amount: Decimal
    colour_slot: int | None = None
    hatched: bool = False


def _colour(entry: DonutSlice, palette: Palette) -> str:
    if entry.colour_slot is None:
        return palette.other_category
    return palette.categories[entry.colour_slot % len(palette.categories)]


def _swatch_style(entry: DonutSlice, palette: Palette) -> str:
    colour = _colour(entry, palette)
    if not entry.hatched:
        return f"background-color: {colour}"
    return f"background: repeating-linear-gradient(-45deg, {colour} 0 3px, {palette.card} 3px 5px)"


def _slice_data(slices: list[DonutSlice], palette: Palette) -> list[dict[str, Any]]:
    return [
        {
            "name": entry.label,
            "value": fmt.chart_amount(entry.amount),
            "itemStyle": {
                "color": _colour(entry, palette),
                **({"decal": hatch_decal(palette)} if entry.hatched else {}),
            },
        }
        for entry in slices
    ]


def donut_option(slices: list[DonutSlice], currency: str, palette: Palette) -> dict[str, Any]:
    return {
        "tooltip": {"trigger": "item", "formatter": f"{{b}}<br/>{{c}} {currency} ({{d}}%)"},
        "series": [
            {
                "type": "pie",
                "radius": ["55%", "85%"],
                "label": {"show": False},
                "itemStyle": {"borderColor": palette.card, "borderWidth": 2},
                "data": _slice_data(slices, palette),
            }
        ],
    }


class Donut:
    """Donut chart with a text legend; `update` redraws it in place, so the page never jumps."""

    def __init__(
        self,
        slices: list[DonutSlice],
        currency: str,
        *,
        legend_label: str,
        dark: bool,
        testid: str,
    ) -> None:
        self._currency = currency
        self._palette = DARK if dark else LIGHT
        with ui.column().classes("w-full gap-4").props(f'data-testid="{testid}"'):
            self._chart = chart(
                donut_option(slices, currency, self._palette), dark=dark, testid=f"{testid}-chart"
            )
            self._legend = ui.element("ul").classes("w-full flex flex-col gap-1")
        self._legend.props["aria-label"] = legend_label
        self._fill_legend(slices)

    def update(self, slices: list[DonutSlice]) -> None:
        self._chart.options["series"][0]["data"] = _slice_data(slices, self._palette)
        self._chart.update()
        self._legend.clear()
        self._fill_legend(slices)

    def _fill_legend(self, slices: list[DonutSlice]) -> None:
        with self._legend:
            for entry in slices:
                with ui.element("li").classes("flex items-center gap-2 text-sm"):
                    ui.element("span").classes("inline-block w-3 h-3 rounded-sm").style(
                        _swatch_style(entry, self._palette)
                    )
                    ui.label(entry.label).classes("flex-1")
                    ui.label(fmt.money(entry.amount, self._currency))
