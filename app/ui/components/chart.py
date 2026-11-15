from typing import Any

from nicegui import ui

from app.ui.palette import DARK, FONT_FAMILY, LIGHT


def chart(option: dict[str, Any], *, dark: bool, testid: str) -> ui.echart:
    palette = DARK if dark else LIGHT
    axis = {
        "axisLine": {"show": False},
        "axisTick": {"show": False},
        "axisLabel": {"color": palette.muted},
        "splitLine": {"lineStyle": {"color": palette.border}},
    }
    tooltip = {
        "backgroundColor": palette.card,
        "borderColor": palette.border,
        "textStyle": {"color": palette.text, "fontFamily": FONT_FAMILY},
    }
    themed = {
        "aria": {"enabled": True},
        "backgroundColor": "transparent",
        "color": [palette.ink],
        "textStyle": {"fontFamily": FONT_FAMILY, "color": palette.muted},
        "grid": {"left": 8, "right": 8, "top": 16, "bottom": 8, "containLabel": True},
        **option,
        "tooltip": {**tooltip, **option.get("tooltip", {})},
    }
    for name in ("xAxis", "yAxis"):
        if name in option:
            themed[name] = {**axis, **option[name]}
    return ui.echart(themed).classes("w-full h-72").props(f'data-testid="{testid}"')
