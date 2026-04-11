"""TradingView chart toolbar factory.

Builds the standard TradingView-style toolbar set (header, drawing tools,
time-range presets, OHLC legend overlay) using the PyWry toolbar system.
"""

from __future__ import annotations

from typing import Any


# TradingView-style SVG icons (18x18, stroke-based, currentColor).
_VB = 'xmlns="http://www.w3.org/2000/svg" viewBox="0 0 18 18" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"'

_ICON_CROSSHAIR = (
    f'<svg {_VB}><line x1="9" y1="1" x2="9" y2="17"/><line x1="1" y1="9" x2="17" y2="9"/></svg>'
)
_ICON_CURSOR = f'<svg {_VB}><path d="M4 2l10 7-5 1-2 5z"/></svg>'
_ICON_TRENDLINE = f'<svg {_VB}><line x1="3" y1="15" x2="15" y2="3"/><circle cx="3" cy="15" r="1.5" fill="currentColor"/><circle cx="15" cy="3" r="1.5" fill="currentColor"/></svg>'
_ICON_HLINE = f'<svg {_VB}><line x1="1" y1="9" x2="17" y2="9"/><line x1="1" y1="9" x2="3" y2="7" stroke-width="1"/><line x1="1" y1="9" x2="3" y2="11" stroke-width="1"/><line x1="17" y1="9" x2="15" y2="7" stroke-width="1"/><line x1="17" y1="9" x2="15" y2="11" stroke-width="1"/></svg>'
_ICON_FIBONACCI = f'<svg {_VB}><line x1="1" y1="3" x2="17" y2="3" stroke-dasharray="2 2"/><line x1="1" y1="7.5" x2="17" y2="7.5" stroke-dasharray="2 2"/><line x1="1" y1="11" x2="17" y2="11" stroke-dasharray="2 2"/><line x1="1" y1="15" x2="17" y2="15" stroke-dasharray="2 2"/><text x="1" y="2.5" font-size="4" fill="currentColor" stroke="none">0</text><text x="1" y="16.5" font-size="4" fill="currentColor" stroke="none">1</text></svg>'
_ICON_GANN = f'<svg {_VB}><rect x="2" y="3" width="14" height="12" fill="none"/><line x1="2" y1="3" x2="16" y2="15"/><line x1="2" y1="9" x2="16" y2="9" stroke-dasharray="2 2"/><line x1="9" y1="3" x2="9" y2="15" stroke-dasharray="2 2"/></svg>'
_ICON_PROJECTION = f'<svg {_VB}><rect x="3" y="3" width="12" height="12" fill="none"/><line x1="3" y1="9" x2="15" y2="9" stroke-dasharray="2 2"/><line x1="9" y1="3" x2="15" y2="9" fill="none" stroke="currentColor"/></svg>'
_ICON_MEASURE = f'<svg {_VB}><rect x="2" y="4" width="14" height="10" rx="1"/><line x1="5" y1="14" x2="5" y2="11"/><line x1="9" y1="14" x2="9" y2="11"/><line x1="13" y1="14" x2="13" y2="11"/></svg>'
_ICON_ERASER = f'<svg {_VB}><path d="M15 5l-4-4-8 8 4 4 2 0 6-6z"/><line x1="8" y1="4" x2="14" y2="10" stroke-width="1"/><line x1="3" y1="15" x2="15" y2="15"/></svg>'
_ICON_CHANNEL = f'<svg {_VB}><line x1="2" y1="14" x2="14" y2="2"/><line x1="4" y1="16" x2="16" y2="4" stroke-dasharray="2 2"/></svg>'
_ICON_BRUSH = (
    f'<svg {_VB}><path d="M13 2l3 3-8 8-4 1 1-4z"/><line x1="10" y1="5" x2="13" y2="8"/></svg>'
)
_ICON_TEXT = f'<svg {_VB}><line x1="4" y1="4" x2="14" y2="4"/><line x1="9" y1="4" x2="9" y2="15"/><line x1="6" y1="15" x2="12" y2="15"/></svg>'
_ICON_RECT = f'<svg {_VB}><rect x="3" y="4" width="12" height="10" rx="1"/></svg>'
_ICON_MAGNET = f'<svg {_VB}><path d="M5 3v5a4 4 0 0 0 8 0V3"/><line x1="5" y1="3" x2="5" y2="6"/><line x1="13" y1="3" x2="13" y2="6"/><line x1="3" y1="3" x2="7" y2="3"/><line x1="11" y1="3" x2="15" y2="3"/></svg>'
_ICON_INDICATOR = f'<svg {_VB}><polyline points="1,13 5,7 9,10 13,4 17,8"/></svg>'
_ICON_SAVE = f'<svg {_VB}><path d="M3 3h9l3 3v9H3z"/><rect x="5" y="3" width="6" height="4"/><rect x="5" y="10" width="8" height="5"/></svg>'
_ICON_SETTINGS = f'<svg {_VB}><circle cx="9" cy="9" r="2.2"/><path d="M9 2.2l1 .2.5 1 .9.3.8-.6.9.5-.2 1 .7.7 1-.2.5.9-.6.8.3.9 1 .5.2 1-.9.5-.3.9.6.8-.5.9-1-.2-.7.7.2 1-.9.5-.8-.6-.9.3-.5 1-1 .2-1-.2-.5-1-.9-.3-.8.6-.9-.5.2-1-.7-.7-1 .2-.5-.9.6-.8-.3-.9-1-.5-.2-1 .9-.5.3-.9-.6-.8.5-.9 1 .2.7-.7-.2-1 .9-.5.8.6.9-.3.5-1z" fill="none"/></svg>'
_ICON_SCREENSHOT = f'<svg {_VB}><rect x="2" y="4" width="14" height="11" rx="1.5"/><circle cx="9" cy="9.5" r="2.5"/><circle cx="13" cy="6" r="0.8" fill="currentColor"/></svg>'
_ICON_FULLSCREEN = f'<svg {_VB}><polyline points="1,6 1,1 6,1"/><polyline points="12,1 17,1 17,6"/><polyline points="17,12 17,17 12,17"/><polyline points="6,17 1,17 1,12"/></svg>'
_ICON_UNDO = f'<svg {_VB}><path d="M4 7h7a4 4 0 0 1 0 8H8"/><polyline points="7,4 4,7 7,10"/></svg>'
_ICON_REDO = (
    f'<svg {_VB}><path d="M14 7H7a4 4 0 0 0 0 8h3"/><polyline points="11,4 14,7 11,10"/></svg>'
)
_ICON_COMPARE = f'<svg {_VB}><circle cx="9" cy="9" r="7.2"/><line x1="9" y1="5.2" x2="9" y2="12.8"/><line x1="5.2" y1="9" x2="12.8" y2="9"/></svg>'
_ICON_SEARCH = (
    f'<svg {_VB}><circle cx="7.5" cy="7.5" r="5"/><line x1="11.5" y1="11.5" x2="16" y2="16"/></svg>'
)
_ICON_CANDLESTICK = f'<svg {_VB}><line x1="5" y1="2" x2="5" y2="16"/><rect x="3" y="5" width="4" height="7" fill="currentColor" stroke="none" rx="0.5"/><line x1="13" y1="2" x2="13" y2="16"/><rect x="11" y="6" width="4" height="6" rx="0.5"/></svg>'
_ICON_LOCK = f'<svg {_VB}><rect x="4" y="8" width="10" height="8" rx="1.5"/><path d="M6 8V5.5a3 3 0 016 0V8"/></svg>'
_ICON_EYE = f'<svg {_VB}><path d="M1 9s3-5 8-5 8 5 8 5-3 5-8 5-8-5-8-5z"/><circle cx="9" cy="9" r="2.5"/></svg>'
_ICON_TRASH = f'<svg {_VB}><path d="M3 5h12M7 5V3.5A1.5 1.5 0 018.5 2h1A1.5 1.5 0 0111 3.5V5m-6 0l.8 10a1.5 1.5 0 001.5 1.4h3.4a1.5 1.5 0 001.5-1.4L13 5"/></svg>'
_ICON_DATE_RANGE = f'<svg {_VB}><rect x="2" y="3" width="14" height="12" rx="1.5"/><line x1="2" y1="6" x2="16" y2="6"/><line x1="6" y1="1.8" x2="6" y2="4.6"/><line x1="12" y1="1.8" x2="12" y2="4.6"/><path d="M6 10h6"/><polyline points="10,8 12,10 10,12"/></svg>'

# Small caret & folder for dropdown
_ICON_CARET = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 8" width="8" '
    'height="8" fill="none" stroke="currentColor" stroke-width="1.5" '
    'stroke-linecap="round" stroke-linejoin="round">'
    '<polyline points="1,3 4,6 7,3"/></svg>'
)
_ICON_FOLDER = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="14" '
    'height="14" fill="none" stroke="currentColor" stroke-width="1.2" '
    'stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M2 4h4l2 2h6v7H2z"/></svg>'
)


def _icon_btn(svg: str, component_id: str, event: str, tooltip: str = "") -> Any:
    """Build a Div that looks and acts like an icon button."""
    from ..toolbar import Div

    esc_tip = tooltip.replace("'", "\\'")
    html = (
        f'<div class="pywry-icon-btn" id="{component_id}" '
        f'data-event="{event}" data-component-id="{component_id}" '
        f'data-tooltip="{esc_tip}" '
        f'role="button" tabindex="0">'
        f"{svg}</div>"
    )
    return Div(
        component_id=f"wrap-{component_id}",
        content=html,
        event="tvchart:noop",
        class_name="pywry-icon-btn-wrap",
    )


def _tool_group_btn(
    svg: str,
    component_id: str,
    group: str,
    tooltip: str = "",
) -> Any:
    """Build a toolbar button that opens a tool-group flyout submenu."""
    from ..toolbar import Div

    esc_tip = tooltip.replace("'", "\\'")
    html = (
        f'<div class="pywry-icon-btn pywry-tool-group" id="{component_id}" '
        f'data-tool-group="{group}" data-component-id="{component_id}" '
        f'data-event="tvchart:noop" '
        f'data-tooltip="{esc_tip}" '
        f'role="button" tabindex="0">'
        f'<span class="pywry-tool-group-icon">{svg}</span>'
        f'<span class="pywry-tool-group-caret"></span>'
        f"</div>"
    )
    return Div(
        component_id=f"wrap-{component_id}",
        content=html,
        event="tvchart:noop",
        class_name="pywry-icon-btn-wrap",
    )


def _separator() -> Any:
    """Vertical or horizontal separator line between toolbar groups."""
    from ..toolbar import Div

    return Div(
        content='<div class="tv-separator"></div>',
        event="tvchart:noop",
        class_name="tv-separator-wrap",
    )


def _save_split_btn() -> Any:
    """Build a TradingView-style Save split button with dropdown menu."""
    from ..toolbar import Div

    html = (
        '<div class="tvchart-save-split" id="tvchart-save-split">'
        f'<div class="pywry-icon-btn tvchart-save-main" id="tvchart-save" '
        f'data-event="tvchart:save-layout" data-component-id="tvchart-save" '
        f'data-tooltip="Save layout" role="button" tabindex="0">'
        f'<span class="tvchart-save-label">Layout</span></div>'
        f'<div class="pywry-icon-btn tvchart-save-caret" id="tvchart-save-caret" '
        f'role="button" tabindex="0">{_ICON_CARET}</div>'
        '<div class="tvchart-save-menu" id="tvchart-save-menu">'
        f'<div class="tvchart-save-menu-item" data-action="save-layout" '
        f'data-component-id="tvchart-save-layout">'
        f'{_ICON_SAVE}<span class="tvchart-save-menu-text">Save layout</span>'
        '<span class="tvchart-save-shortcut">Ctrl+S</span></div>'
        f'<div class="tvchart-save-menu-item" data-action="make-copy" '
        f'data-component-id="tvchart-save-copy">'
        f'<span class="tvchart-save-menu-text">Make a copy\u2026</span></div>'
        f'<div class="tvchart-save-menu-item" data-action="rename-layout" '
        f'data-component-id="tvchart-rename-layout">'
        f'<span class="tvchart-save-menu-text">Rename\u2026</span></div>'
        '<div class="tvchart-save-menu-sep"></div>'
        f'<div class="tvchart-save-menu-item" data-action="open-layout" '
        f'data-component-id="tvchart-open-layout">'
        f'{_ICON_FOLDER}<span class="tvchart-save-menu-text">Open layout\u2026</span></div>'
        "</div></div>"
    )
    return Div(
        component_id="wrap-tvchart-save-split",
        content=html,
        event="tvchart:noop",
        class_name="pywry-icon-btn-wrap tvchart-save-split-wrap",
    )


def _chart_type_selector(selected: str = "Candles") -> Any:
    """Build a static chart-type menu anchored to the toolbar."""
    from ..toolbar import Div

    chart_types = [
        "Bars",
        "Candles",
        "Hollow candles",
        "HLC bars",
        "Line",
        "Line with markers",
        "Step line",
        "Area",
        "HLC area",
        "Baseline",
        "Columns",
        "High-low",
        "Heikin Ashi",
    ]
    menu_items = "".join(
        f'<div class="tvchart-chart-type-item{" selected" if chart_type == selected else ""}" '
        f'data-type="{chart_type}">{chart_type}</div>'
        for chart_type in chart_types
    )
    html = (
        '<div class="tvchart-menu-anchor tvchart-chart-type-anchor">'
        f'<div class="pywry-icon-btn tvchart-menu-trigger" id="tvchart-chart-type-icon" '
        f'data-event="tvchart:noop" data-component-id="tvchart-chart-type-icon" '
        f'data-tooltip="Chart Type" role="button" tabindex="0">{_ICON_CANDLESTICK}</div>'
        f'<div class="tvchart-chart-type-menu" id="tvchart-chart-type-menu">{menu_items}</div>'
        "</div>"
    )
    return Div(
        component_id="wrap-tvchart-chart-type",
        content=html,
        event="tvchart:noop",
        class_name="pywry-icon-btn-wrap tvchart-chart-type-wrap",
    )


# Canonical display labels for interval values.
_INTERVAL_LABELS: dict[str, str] = {
    "1m": "1m",
    "3m": "3m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "45m": "45m",
    "1h": "1H",
    "2h": "2H",
    "3h": "3H",
    "4h": "4H",
    "1d": "D",
    "1w": "W",
    "1M": "M",
    "3M": "3M",
    "6M": "6M",
    "12M": "12M",
}

_INTERVAL_DAYS: dict[str, float] = {
    "1m": 1 / 1440,
    "3m": 3 / 1440,
    "5m": 5 / 1440,
    "15m": 15 / 1440,
    "30m": 30 / 1440,
    "45m": 45 / 1440,
    "1h": 1 / 24,
    "2h": 2 / 24,
    "3h": 3 / 24,
    "4h": 4 / 24,
    "1d": 1,
    "1w": 7,
    "1M": 30,
    "3M": 91,
    "6M": 182,
    "12M": 365,
}

_TIME_RANGE_PRESET_DAYS: list[tuple[str, int]] = [
    ("all", 365 * 50),
    ("ytd", 365),
    ("20y", 365 * 20),
    ("10y", 365 * 10),
    ("5y", 365 * 5),
    ("3y", 365 * 3),
    ("1y", 365),
    ("6m", 182),
    ("3m", 91),
    ("1m", 30),
    ("5d", 5),
    ("1d", 1),
]


_INTERVAL_DISPLAY: dict[str, str] = {
    "1m": "1 minute",
    "3m": "3 minutes",
    "5m": "5 minutes",
    "15m": "15 minutes",
    "30m": "30 minutes",
    "45m": "45 minutes",
    "1h": "1 hour",
    "2h": "2 hours",
    "3h": "3 hours",
    "4h": "4 hours",
    "1d": "1 day",
    "1w": "1 week",
    "1M": "1 month",
    "3M": "3 months",
    "6M": "6 months",
    "12M": "12 months",
}

_TIME_RANGE_DISPLAY: dict[str, str] = {
    "all": "all",
    "ytd": "year to date",
    "1d": "1 day",
    "5d": "5 days",
    "1m": "1 month",
    "3m": "3 months",
    "6m": "6 months",
    "1y": "1 year",
    "3y": "3 years",
    "5y": "5 years",
    "10y": "10 years",
    "20y": "20 years",
}

_TIME_RANGE_INTERVAL_PREFERENCES: dict[str, list[str]] = {
    "all": [
        "1d",
        "1w",
        "1M",
        "3M",
        "6M",
        "12M",
        "4h",
        "2h",
        "1h",
        "45m",
        "30m",
        "15m",
        "5m",
        "3m",
        "1m",
    ],
    "ytd": ["1d", "4h", "2h", "1h", "1w", "1M", "3M", "6M", "12M"],
    "1d": [
        "1m",
        "3m",
        "5m",
        "15m",
        "30m",
        "45m",
        "1h",
        "2h",
        "3h",
        "4h",
        "1d",
        "1w",
        "1M",
        "3M",
        "6M",
        "12M",
    ],
    "5d": [
        "5m",
        "15m",
        "3m",
        "30m",
        "45m",
        "1h",
        "2h",
        "3h",
        "4h",
        "1d",
        "1w",
        "1M",
        "3M",
        "6M",
        "12M",
    ],
    "1m": ["30m", "15m", "45m", "1h", "5m", "3m", "2h", "4h", "1d", "1w", "1M", "3M", "6M", "12M"],
    "3m": ["1h", "45m", "2h", "30m", "4h", "15m", "1d", "1w", "1M", "3M", "6M", "12M"],
    "6m": ["2h", "4h", "1h", "1d", "1w", "1M", "3M", "6M", "12M"],
    "1y": ["1d", "4h", "1w", "1M", "3M", "6M", "12M"],
    "3y": ["1w", "1d", "1M", "3M", "6M", "12M"],
    "5y": ["1w", "1M", "3M", "6M", "12M"],
    "10y": ["1M", "1w", "3M", "6M", "12M"],
    "20y": ["3M", "1M", "6M", "12M"],
}


def _resolve_time_range_interval(preset: str, intervals: list[str] | None = None) -> str:
    """Choose the interval TradingView-style time-range presets should request."""
    available = intervals or ["1d"]
    for candidate in _TIME_RANGE_INTERVAL_PREFERENCES.get(preset, []):
        if candidate in available:
            return candidate
    # Fallback: large ranges → coarsest available, small ranges → finest
    span_days = dict(_TIME_RANGE_PRESET_DAYS).get(preset, 365)
    if span_days >= 30:
        return max(available, key=lambda interval: _INTERVAL_DAYS.get(interval, float("inf")))
    return min(available, key=lambda interval: _INTERVAL_DAYS.get(interval, float("inf")))


def _time_range_presets(intervals: list[str] | None = None) -> tuple[list[Any], str]:
    """Pick practical bottom time-range presets for the finest available interval."""
    from ..toolbar import Option

    available_intervals = intervals or ["1d"]
    finest_days = min(_INTERVAL_DAYS.get(interval, 1) for interval in available_intervals)

    if finest_days < 1:
        candidates = ["all", "10y", "5y", "1y", "ytd", "6m", "3m", "1m", "5d", "1d"]
    elif finest_days <= 1:
        candidates = ["all", "10y", "5y", "1y", "ytd", "6m", "3m", "1m"]
    elif finest_days <= 7:
        candidates = ["all", "10y", "5y", "3y", "1y", "ytd", "6m", "3m"]
    else:
        candidates = ["all", "20y", "10y", "5y", "3y", "1y", "ytd"]

    span_lookup = dict(_TIME_RANGE_PRESET_DAYS)

    preferred = [
        value
        for value in candidates
        if value in {"all", "ytd"} or (span_lookup[value] / finest_days) >= 8
    ]

    if len(preferred) < 3:
        preferred = [
            value
            for value in candidates
            if value in {"all", "ytd"} or (span_lookup[value] / finest_days) >= 3
        ]

    if not preferred:
        preferred = candidates[-3:]

    selected = next(
        (
            candidate
            for candidate in [
                "1y",
                "ytd",
                "5y",
                "3y",
                "6m",
                "10y",
                "20y",
                "3m",
                "1m",
                "5d",
                "1d",
                "all",
            ]
            if candidate in preferred
        ),
        preferred[min(len(preferred) - 1, len(preferred) // 2)],
    )
    label_map = {
        "all": "Max",
        "ytd": "YTD",
        "10y": "10y",
    }
    options = []
    for preset in preferred:
        target_interval = _resolve_time_range_interval(preset, available_intervals)
        options.append(
            Option(
                label=label_map.get(preset, preset),
                value=preset,
                description=_TIME_RANGE_DISPLAY.get(preset, preset).capitalize(),
                data_attrs={"target-interval": target_interval},
            )
        )
    return options, selected


def _interval_selector(
    intervals: list[str],
    selected: str | None = None,
) -> Any:
    """Compact interval dropdown matching TradingView top-bar style.

    Parameters
    ----------
    intervals
        List of interval codes the developer wants to expose.
        E.g. ``["1d", "1w", "1M"]``.
    selected
        Initially-active interval.  Falls back to ``intervals[0]``.
    """
    from ..toolbar import Div

    available_intervals = set(intervals or ["1d"])
    sel = (
        selected
        if selected and selected in available_intervals
        else (intervals[0] if intervals else "1d")
    )
    label = _INTERVAL_LABELS.get(sel, sel)

    categories = {
        "minutes": "MINUTES",
        "hours": "HOURS",
        "days": "DAYS",
    }
    ordered_intervals_by_category: dict[str, list[str]] = {
        "minutes": ["1m", "3m", "5m", "15m", "30m", "45m"],
        "hours": ["1h", "2h", "3h", "4h"],
        "days": ["1d", "1w", "1M", "3M", "6M", "12M"],
    }

    menu_parts: list[str] = []
    for category_key in ["minutes", "hours", "days"]:
        menu_parts.append(f'<div class="tvchart-interval-section">{categories[category_key]}</div>')
        for interval in ordered_intervals_by_category[category_key]:
            is_available = interval in available_intervals
            item_classes = ["tvchart-interval-item"]
            if interval == sel:
                item_classes.append("selected")
            if not is_available:
                item_classes.append("disabled")
            menu_parts.append(
                f'<div class="{" ".join(item_classes)}" '
                f'data-interval="{interval}">{_INTERVAL_DISPLAY.get(interval, interval)}</div>'
            )
    menu_html = "".join(menu_parts)
    html = (
        '<div class="tvchart-menu-anchor tv-interval-anchor">'
        f'<div class="tv-interval-btn" id="tvchart-interval-btn" data-selected="{sel}">'
        f'<span class="tv-interval-label" id="tvchart-interval-label">{label}</span>'
        f'<svg class="tv-interval-caret" viewBox="0 0 8 8" width="8" height="8" '
        f'fill="none" stroke="currentColor" stroke-width="1.5" '
        f'stroke-linecap="round" stroke-linejoin="round">'
        f'<polyline points="1,3 4,6 7,3"/></svg>'
        f"</div>"
        f'<div class="tvchart-interval-menu" id="tvchart-interval-menu">{menu_html}</div>'
        "</div>"
    )
    return Div(
        component_id="wrap-tvchart-interval-btn",
        content=html,
        event="tvchart:noop",
        class_name="pywry-icon-btn-wrap tv-interval-wrap",
    )


def build_tvchart_toolbars(
    intervals: list[str] | None = None,
    selected_interval: str | None = None,
    *,
    theme: str | None = None,
) -> list[Any]:
    """Build the default toolbar set for a TradingView chart.

    Parameters
    ----------
    intervals
        Data-frequency intervals the user can switch between.
        Only intervals that can actually be resolved from the
        underlying data (or that the developer explicitly wants)
        should be listed.  Pass ``None`` (default) to omit the
        interval selector entirely.
        Examples: ``["1d", "1w", "1M"]``, ``["1m", "5m", "1h", "1d"]``.
    selected_interval
        Which interval is initially active.  Falls back to the
        first entry in *intervals*.
    theme
        Active theme (``"dark"`` or ``"light"``).  Controls the
        initial state of the dark-mode toggle.  Defaults to
        ``"dark"`` when *None*.

    Returns
    -------
    list
        Four :class:`Toolbar` objects: header (top), drawing tools
        (left), time-range presets (bottom), and OHLC legend overlay
        (inside).
    """
    from ..toolbar import Div, TabGroup, Toggle, Toolbar

    time_range_options, time_range_selected = _time_range_presets(intervals)

    # -- Top header toolbar --------------------------------------------------
    header_items: list[Any] = [
        _icon_btn(
            _ICON_SEARCH,
            "tvchart-symbol-search",
            "tvchart:symbol-search",
            "Symbol Search",
        ),
        _separator(),
        _chart_type_selector(),
    ]
    if intervals:
        header_items += [
            _separator(),
            _interval_selector(intervals, selected_interval),
        ]
    header_items += [
        _separator(),
        _icon_btn(_ICON_COMPARE, "tvchart-compare", "tvchart:compare", "Compare"),
        _icon_btn(_ICON_INDICATOR, "tvchart-indicators", "tvchart:show-indicators", "Indicators"),
        _separator(),
        _icon_btn(_ICON_UNDO, "tvchart-undo", "tvchart:undo", "Undo"),
        _icon_btn(_ICON_REDO, "tvchart-redo", "tvchart:redo", "Redo"),
        _separator(),
        _save_split_btn(),
        _icon_btn(_ICON_SETTINGS, "tvchart-settings", "tvchart:show-settings", "Settings"),
        _icon_btn(_ICON_SCREENSHOT, "tvchart-screenshot", "tvchart:screenshot", "Screenshot"),
        _icon_btn(_ICON_FULLSCREEN, "tvchart-fullscreen", "tvchart:fullscreen", "Fullscreen"),
        Div(
            component_id="tvchart-header-spacer",
            content='<div class="tv-spacer"></div>',
            event="tvchart:noop",
            class_name="tv-spacer-wrap",
        ),
        Toggle(
            component_id="tvchart-dark-mode",
            label="dark",
            event="tvchart:toggle-dark-mode",
            value=str(theme).lower() != "light",
        ),
    ]
    header = Toolbar(
        position="top",
        class_name="tvchart-header",
        items=header_items,
    )

    # -- Left drawing-tool toolbar -------------------------------------------
    left = Toolbar(
        position="left",
        class_name="tvchart-left",
        items=[
            # --- Pointer (standalone) ---
            _icon_btn(_ICON_CURSOR, "tvchart-tool-cursor", "tvchart:tool-cursor", "Pointer"),
            _icon_btn(
                _ICON_CROSSHAIR, "tvchart-tool-crosshair", "tvchart:tool-crosshair", "Crosshair"
            ),
            _separator(),
            # --- Line tools (submenu) ---
            _tool_group_btn(_ICON_TRENDLINE, "tvchart-group-lines", "lines", "Line Tools"),
            # --- Channel tools (submenu) ---
            _tool_group_btn(_ICON_CHANNEL, "tvchart-group-channels", "channels", "Channel Tools"),
            _separator(),
            # --- Fibonacci (submenu) ---
            _tool_group_btn(_ICON_FIBONACCI, "tvchart-group-fib", "fib", "Fibonacci Tools"),
            # --- Gann (submenu) ---
            _tool_group_btn(_ICON_GANN, "tvchart-group-gann", "gann", "Gann Tools"),
            # --- Shapes (submenu) ---
            _tool_group_btn(_ICON_RECT, "tvchart-group-shapes", "shapes", "Shapes"),
            _separator(),
            # --- Annotations (submenu) ---
            _tool_group_btn(_ICON_BRUSH, "tvchart-group-annotations", "annotations", "Annotations"),
            # --- Projection (submenu) ---
            _tool_group_btn(
                _ICON_PROJECTION, "tvchart-group-projection", "projection", "Projection"
            ),
            # --- Measure (submenu) ---
            _tool_group_btn(_ICON_MEASURE, "tvchart-group-measure", "measure", "Measure"),
            _separator(),
            # --- Utilities (standalone) ---
            _icon_btn(_ICON_MAGNET, "tvchart-tool-magnet", "tvchart:tool-magnet", "Magnet Mode"),
            _icon_btn(
                _ICON_EYE,
                "tvchart-tool-visibility",
                "tvchart:tool-visibility",
                "Show/Hide Drawings",
            ),
            _icon_btn(_ICON_LOCK, "tvchart-tool-lock", "tvchart:tool-lock", "Lock Drawings"),
            _separator(),
            _icon_btn(
                _ICON_TRASH, "tvchart-tool-eraser", "tvchart:tool-eraser", "Remove All Drawings"
            ),
        ],
    )

    # -- Bottom time-range toolbar -------------------------------------------
    bottom = Toolbar(
        position="bottom",
        class_name="tvchart-bottom",
        items=[
            TabGroup(
                component_id="tvchart-time-range",
                event="tvchart:time-range",
                options=time_range_options,
                selected=time_range_selected,
                size="sm",
            ),
            _separator(),
            _icon_btn(
                _ICON_DATE_RANGE,
                "tvchart-date-range",
                "tvchart:time-range-picker",
                "Pick date range",
            ),
            Div(
                component_id="tvchart-bottom-spacer",
                content='<div class="tv-spacer"></div>',
                event="tvchart:noop",
                class_name="tv-spacer-wrap",
            ),
            Div(
                component_id="tvchart-exchange-clock",
                content='<span id="tvchart-exchange-clock" style="font-size:12px;color:var(--pywry-tvchart-text-muted);white-space:nowrap;padding:0 8px;"></span>',
                event="tvchart:noop",
                class_name="tv-exchange-clock-wrap",
            ),
            Div(
                component_id="tvchart-tz-wrap",
                content=(
                    '<button id="tvchart-tz-btn" class="tvchart-bottom-btn" '
                    'type="button" data-tooltip="Timezone" '
                    'onclick="_tvToggleTimezoneMenu()"'
                    '><span class="tvchart-bottom-btn-label">Exchange</span>'
                    '<svg class="tvchart-bottom-btn-caret" width="8" height="5" viewBox="0 0 8 5">'
                    '<path d="M0.5 0.5L4 4L7.5 0.5" stroke="currentColor" fill="none" stroke-width="1.2"/>'
                    "</svg></button>"
                ),
                event="tvchart:noop",
                class_name="tv-tz-btn-wrap",
            ),
            Div(
                component_id="tvchart-session-wrap",
                content=(
                    '<button id="tvchart-session-btn" class="tvchart-bottom-btn" '
                    'type="button" data-tooltip="Session" '
                    'onclick="_tvToggleSessionMenu()"'
                    ' style="display:none;"'
                    '><span class="tvchart-bottom-btn-label">ETH</span>'
                    '<svg class="tvchart-bottom-btn-caret" width="8" height="5" viewBox="0 0 8 5">'
                    '<path d="M0.5 0.5L4 4L7.5 0.5" stroke="currentColor" fill="none" stroke-width="1.2"/>'
                    "</svg></button>"
                ),
                event="tvchart:noop",
                class_name="tv-session-btn-wrap",
            ),
            Div(
                component_id="tvchart-pct-scale",
                content=(
                    '<button id="tvchart-pct-scale-btn" class="tvchart-scale-btn"'
                    ' type="button" data-tooltip="Toggle percentage scale"'
                    ' onclick="_tvTogglePctScale()"'
                    ">%</button>"
                ),
                event="tvchart:noop",
                class_name="tv-scale-btn-wrap",
            ),
            Div(
                component_id="tvchart-log-scale",
                content=(
                    '<button id="tvchart-log-scale-btn" class="tvchart-scale-btn"'
                    ' type="button" data-tooltip="Toggle log scale"'
                    ' onclick="_tvToggleLogScale()"'
                    ">log</button>"
                ),
                event="tvchart:noop",
                class_name="tv-scale-btn-wrap",
            ),
            Div(
                component_id="tvchart-auto-scale",
                content=(
                    '<button id="tvchart-auto-scale-btn" class="tvchart-scale-btn active"'
                    ' type="button" data-tooltip="Toggle auto scale"'
                    ' onclick="_tvToggleAutoScale()"'
                    ">auto</button>"
                ),
                event="tvchart:noop",
                class_name="tv-scale-btn-wrap",
            ),
        ],
    )

    # -- Inside overlay: OHLC legend -----------------------------------------
    legend_html = (
        '<div class="tvchart-legend-container" id="tvchart-legend-box">'
        '<div class="tvchart-legend-row tvchart-legend-row-main" id="tvchart-legend-main-row">'
        '<span class="tvchart-legend-title" id="tvchart-legend-title"></span>'
        '<span class="tvchart-legend-ohlc" id="tvchart-legend-ohlc"></span>'
        '<span class="tvchart-legend-row-actions" id="tvchart-legend-main-ctrl"></span>'
        "</div>"
        '<div class="tvchart-legend-series" id="tvchart-legend-series"></div>'
        '<div class="tvchart-legend-row tvchart-legend-row-volume" id="tvchart-legend-vol-row">'
        '<span class="tvchart-legend-vol" id="tvchart-legend-vol"></span>'
        '<span class="tvchart-legend-row-actions" id="tvchart-legend-vol-ctrl"></span>'
        "</div>"
        '<div class="tvchart-legend-indicators" id="tvchart-legend-indicators"></div>'
        '<button type="button" class="tvchart-legend-collapse-btn" id="tvchart-legend-collapse"'
        ' data-tooltip="Hide indicator legend" aria-label="Hide indicator legend" style="display:none">'
        '<svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor"'
        ' stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:block">'
        '<polyline points="4,6 8,10 12,6"/></svg></button>'
        "</div>"
    )
    inside = Toolbar(
        position="inside",
        class_name="tvchart-inside",
        items=[
            Div(
                component_id="tvchart-legend",
                content=legend_html,
                class_name="tvchart-legend-wrap",
                event="tvchart:noop",
            ),
        ],
    )

    return [header, left, bottom, inside]
