"""MCP tool definitions for PyWry v2.0.0.

This module provides all tool schemas and the get_tools function
for the MCP server.
"""

from mcp.types import Tool

from .docs import COMPONENT_DOCS
from .skills import list_skills


# =============================================================================
# Component Types
# =============================================================================

COMPONENT_TYPES = [
    "button",
    "select",
    "multiselect",
    "toggle",
    "checkbox",
    "radio",
    "tabs",
    "text",
    "textarea",
    "search",
    "number",
    "date",
    "slider",
    "range",
    "div",
    "secret",
    "marquee",
]

# =============================================================================
# Tool Schemas
# =============================================================================

TOOLBAR_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "type": {
            "type": "string",
            "enum": COMPONENT_TYPES,
            "description": "Component type",
        },
        "label": {"type": "string", "description": "Label text"},
        "event": {"type": "string", "description": "Event name to emit on interaction"},
        "value": {"description": "Current value (type depends on component)"},
        "options": {
            "type": "array",
            "description": "Options for select/multiselect/radio/tabs",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "value": {"type": "string"},
                },
            },
        },
        "selected": {"description": "Selected value(s)"},
        "placeholder": {"type": "string"},
        "disabled": {"type": "boolean", "default": False},
        "variant": {
            "type": "string",
            "enum": ["primary", "neutral", "danger", "success"],
        },
        "size": {"type": "string", "enum": ["sm", "md", "lg"]},
        "min": {"type": "number"},
        "max": {"type": "number"},
        "step": {"type": "number"},
        "rows": {"type": "integer", "description": "Rows for textarea"},
        "debounce": {"type": "integer", "description": "Debounce ms for search/inputs"},
        "show_value": {"type": "boolean", "description": "Show value for slider/range"},
        "direction": {
            "type": "string",
            "enum": ["horizontal", "vertical", "left", "right", "up", "down"],
        },
        "content": {"type": "string", "description": "HTML content for div"},
        "component_id": {
            "type": "string",
            "description": "ID for div (for set_content)",
        },
        "style": {"type": "string", "description": "Inline CSS styles"},
        "class_name": {"type": "string", "description": "CSS class name"},
        "data": {"type": "object", "description": "Extra data to include in events"},
        # RangeInput properties
        "start": {"type": "number", "description": "Start value for range slider"},
        "end": {"type": "number", "description": "End value for range slider"},
        # SecretInput properties
        "show_toggle": {
            "type": "boolean",
            "description": "Show visibility toggle for secret",
        },
        "show_copy": {"type": "boolean", "description": "Show copy button for secret"},
        # Marquee properties
        "text": {"type": "string", "description": "Scrolling text for marquee"},
        "speed": {"type": "number", "description": "Animation speed in seconds"},
        "behavior": {
            "type": "string",
            "enum": ["scroll", "alternate", "slide", "static"],
        },
        "pause_on_hover": {
            "type": "boolean",
            "description": "Pause on hover for marquee",
        },
        "gap": {
            "type": "integer",
            "description": "Gap between repeated content for marquee",
        },
        "clickable": {"type": "boolean", "description": "Whether marquee is clickable"},
        "separator": {
            "type": "string",
            "description": "Separator between repeated content",
        },
        "ticker_items": {
            "type": "array",
            "description": "Ticker items for marquee (auto-builds HTML)",
            "items": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Unique ID for updates",
                    },
                    "text": {"type": "string"},
                    "html": {"type": "string"},
                    "class_name": {"type": "string"},
                    "style": {"type": "string"},
                },
            },
        },
    },
    "required": ["type"],
}

TOOLBAR_SCHEMA = {
    "type": "object",
    "properties": {
        "position": {
            "type": "string",
            "enum": ["top", "bottom", "left", "right", "inside"],
            "default": "top",
        },
        "items": {
            "type": "array",
            "items": TOOLBAR_ITEM_SCHEMA,
        },
        "class_name": {"type": "string"},
    },
}


def get_tools() -> list[Tool]:
    """Return all MCP tools with complete schemas.

    Returns
    -------
    list[Tool]
        List of all available MCP tools.

    """
    return [
        # =====================================================================
        # Skills / Context Discovery
        # =====================================================================
        Tool(
            name="get_skills",
            description="""Get context-appropriate skills and guidance for creating widgets.

⚠️ **MANDATORY FIRST STEP**: Call this with skill="component_reference" BEFORE creating ANY widget.
The component_reference contains the ONLY correct event signatures and system events.

**System Events for Updates (from component_reference):**
- `grid:update-data` with `{"data": [...], "strategy": "set|append|update"}`
- `grid:request-state` / `grid:restore-state` / `grid:reset-state` for state persistence
- `plotly:update-figure` with `{"data": [...], "layout": {...}}`
- `plotly:request-state` for chart state persistence
- `pywry:set-content` with `{"id": "...", "text": "..."}` or `{"id": "...", "html": "..."}`
- `pywry:update-theme` with `{"theme": "dark|light|system"}`
- `toolbar:set-value` / `toolbar:request-state` for toolbar component state

Available skills:
- **component_reference** (MANDATORY): Complete reference for ALL 18 component types, system events, and exact event signatures
- **interactive_buttons**: How to make buttons work automatically with auto-wired callbacks
- native: Desktop window with full control
- jupyter: Inline widgets in notebook cells
- iframe: Embedded in external web pages
- deploy: Production multi-user server
- data_visualization: Charts, tables, live data
- forms_and_inputs: User input collection

Call without arguments to list all skills, or specify a skill name.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "skill": {
                        "type": "string",
                        "description": "Specific skill to retrieve (optional)",
                        "enum": [s["id"] for s in list_skills()],
                    },
                },
            },
        ),
        # =====================================================================
        # Widget Creation
        # =====================================================================
        Tool(
            name="create_widget",
            description="""Create an interactive native window with HTML content and Pydantic toolbar components.

⚠️ **CALL get_skills(skill="component_reference") FIRST** for complete documentation.

**MANDATORY SYNTAX** - Use EXACTLY this structure:

```json
{
  "html": "<div id=\"counter\" style=\"font-size:48px;text-align:center;padding:50px\">0</div>",
  "title": "Counter",
  "height": 400,
  "toolbars": [{
    "position": "top",
    "items": [
      {"type": "button", "label": "+1", "event": "counter:increment", "variant": "primary"},
      {"type": "button", "label": "-1", "event": "counter:decrement", "variant": "neutral"},
      {"type": "button", "label": "Reset", "event": "counter:reset", "variant": "danger"}
    ]
  }]
}
```

**BUTTON EVENTS AUTO-WIRE** when following pattern `elementId:action`:
- `counter:increment` → adds 1 to element with id="counter"
- `counter:decrement` → subtracts 1
- `counter:reset` → sets to 0
- `status:toggle` → toggles true/false

**ALL COMPONENT TYPES AND EVENT SIGNATURES**:

| Type | Event Payload | Required Props |
|------|--------------|----------------|
| button | `{componentId, ...data}` | label, event |
| select | `{value, componentId}` | event, options |
| multiselect | `{values: [], componentId}` | event, options |
| toggle | `{value: boolean, componentId}` | event |
| checkbox | `{value: boolean, componentId}` | event, label |
| radio | `{value, componentId}` | event, options |
| tabs | `{value, componentId}` | event, options |
| text | `{value, componentId}` | event |
| textarea | `{value, componentId}` | event |
| search | `{value, componentId}` | event |
| number | `{value: number, componentId}` | event |
| date | `{value: "YYYY-MM-DD", componentId}` | event |
| slider | `{value: number, componentId}` | event |
| range | `{start, end, componentId}` | event |
| secret | `{value: base64, encoded: true, componentId}` | event |
| div | NO EVENTS | content |
| marquee | `{value, componentId}` (if clickable) | text |

**EVENT FORMAT RULES**:
- MUST be `namespace:action` format (e.g., `form:submit`, `view:change`)
- Reserved namespaces (DO NOT USE): `pywry`, `plotly`, `grid`

**OPTIONS FORMAT** (for select/multiselect/radio/tabs):
```json
"options": [{"label": "Dark", "value": "dark"}, {"label": "Light", "value": "light"}]
```

**TOOLBAR POSITIONS**: top, bottom, left, right, header, footer, inside""",
            inputSchema={
                "type": "object",
                "properties": {
                    "html": {
                        "type": "string",
                        "description": "HTML content. Use Div component for dynamic content.",
                    },
                    "title": {"type": "string", "default": "PyWry Widget"},
                    "height": {"type": "integer", "default": 500},
                    "include_plotly": {"type": "boolean", "default": False},
                    "include_aggrid": {"type": "boolean", "default": False},
                    "toolbars": {
                        "type": "array",
                        "description": "Toolbars with components",
                        "items": TOOLBAR_SCHEMA,
                    },
                    "callbacks": {
                        "type": "object",
                        "description": "Map of event names to callback actions",
                        "additionalProperties": {
                            "type": "object",
                            "properties": {
                                "action": {
                                    "type": "string",
                                    "enum": [
                                        "increment",
                                        "decrement",
                                        "set",
                                        "toggle",
                                        "emit",
                                    ],
                                    "description": "Action type",
                                },
                                "target": {
                                    "type": "string",
                                    "description": "component_id to update",
                                },
                                "state_key": {
                                    "type": "string",
                                    "description": "Key in widget state to track",
                                },
                                "value": {
                                    "description": "Value for set action",
                                },
                                "emit_event": {
                                    "type": "string",
                                    "description": "Event to emit (for emit action)",
                                },
                                "emit_data": {
                                    "type": "object",
                                    "description": "Data to emit with event",
                                },
                            },
                        },
                    },
                },
                "required": ["html"],
            },
        ),
        Tool(
            name="build_div",
            description="""Build a Div component HTML string. Use component_id to update later.

**MANDATORY SYNTAX**:
```json
{"content": "0", "component_id": "counter", "style": "font-size:48px;text-align:center"}
```

Returns: `{"html": "<div id=\"counter\" style=\"...\">0</div>"}`

Use the returned html in create_widget's html parameter.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Text or HTML content",
                    },
                    "component_id": {
                        "type": "string",
                        "description": "ID for updates via set_content",
                    },
                    "style": {"type": "string", "description": "Inline CSS styles"},
                    "class_name": {"type": "string", "description": "CSS class name"},
                },
                "required": ["content"],
            },
        ),
        Tool(
            name="build_ticker_item",
            description="""Build a TickerItem for Marquee. Can be updated dynamically via update_ticker_item.

**MANDATORY SYNTAX**:
```json
{"ticker": "AAPL", "text": "AAPL: $150.00", "style": "color: green"}
```

Returns HTML span with data-ticker attribute for targeting updates.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Unique ID for targeting updates (e.g., 'AAPL', 'BTC')",
                    },
                    "text": {"type": "string", "description": "Display text"},
                    "html": {
                        "type": "string",
                        "description": "HTML content (overrides text)",
                    },
                    "class_name": {"type": "string", "description": "CSS classes"},
                    "style": {"type": "string", "description": "Inline CSS styles"},
                },
                "required": ["ticker"],
            },
        ),
        Tool(
            name="show_plotly",
            description="""Create a Plotly chart widget. Pass figure JSON from fig.to_json().

**To update the chart later**, use `send_event` with:
- event_type: `plotly:update-figure`
- data: `{"data": [...], "layout": {...}}`

Or use `update_plotly` tool with new figure_json.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "figure_json": {
                        "type": "string",
                        "description": "Plotly figure as JSON",
                    },
                    "title": {"type": "string", "default": "Plotly Chart"},
                    "height": {"type": "integer", "default": 500},
                },
                "required": ["figure_json"],
            },
        ),
        Tool(
            name="show_dataframe",
            description="""Create an AG Grid table widget from JSON data.

**To update the grid data later**, use `send_event` with:
- event_type: `grid:update-data`
- data: `{"data": [...new rows...], "strategy": "set"}`

Strategy options: "set" (replace all), "append" (add rows), "update" (update existing)""",
            inputSchema={
                "type": "object",
                "properties": {
                    "data_json": {
                        "type": "string",
                        "description": "Data as JSON array of objects",
                    },
                    "title": {"type": "string", "default": "Data Table"},
                    "height": {"type": "integer", "default": 500},
                },
                "required": ["data_json"],
            },
        ),
        Tool(
            name="show_tvchart",
            description="""Create a TradingView Lightweight Chart widget from OHLCV data.

Data must be a JSON array of objects with time, open, high, low, close,
and optional volume fields. Time should be Unix epoch seconds.

**To update the chart later**, use `send_event` with:
- event_type: `tvchart:update`
- data: `{"bars": [...], "chartId": "..."}`""",
            inputSchema={
                "type": "object",
                "properties": {
                    "data_json": {
                        "type": "string",
                        "description": "OHLCV data as JSON array of objects",
                    },
                    "title": {"type": "string", "default": "Chart"},
                    "height": {"type": "integer", "default": 500},
                    "chart_options": {
                        "type": "object",
                        "description": "Chart-level options (layout, grid, crosshair)",
                    },
                    "series_options": {
                        "type": "object",
                        "description": "Series-specific options (colors, etc.)",
                    },
                },
                "required": ["data_json"],
            },
        ),
        # =====================================================================
        # TVChart — first-class tools for every chart operation.  Every tool
        # accepts the owning ``widget_id`` plus an optional ``chart_id`` for
        # multi-chart widgets (defaults to the first chart).
        # =====================================================================
        Tool(
            name="tvchart_update_series",
            description="""Replace the bar data for a chart series.

Emits ``tvchart:update`` with ``{bars, volume?, fitContent?, chartId?, seriesId?}``.
Time values are Unix epoch seconds.  Use ``series_id`` to target a specific
series (defaults to the main OHLCV series).""",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "bars": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Bar objects with time/open/high/low/close/volume fields",
                    },
                    "volume": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Optional separate volume points {time,value,color?}",
                    },
                    "series_id": {"type": "string"},
                    "chart_id": {"type": "string"},
                    "fit_content": {"type": "boolean", "default": True},
                },
                "required": ["widget_id", "bars"],
            },
        ),
        Tool(
            name="tvchart_update_bar",
            description="""Stream a single real-time bar update.

Emits ``tvchart:stream`` with the merged bar payload.  If the bar's time
matches the most recent bar the chart updates that bar; otherwise a new
bar is appended.  Volume colour is auto-derived from open/close unless
provided.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "bar": {
                        "type": "object",
                        "description": "Bar dict with time/open/high/low/close/volume",
                    },
                    "series_id": {"type": "string"},
                    "chart_id": {"type": "string"},
                },
                "required": ["widget_id", "bar"],
            },
        ),
        Tool(
            name="tvchart_add_series",
            description="""Add a pre-computed overlay series to the chart.

Emits ``tvchart:add-series``.  Use this for any series whose values you
already computed in Python (custom indicators, compare symbols, forecasts,
etc.).  For the built-in indicator engine (SMA/EMA/RSI/BB/…) use
``tvchart_add_indicator`` instead.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "series_id": {"type": "string"},
                    "bars": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Series data points — shape depends on series_type",
                    },
                    "series_type": {
                        "type": "string",
                        "enum": ["Line", "Area", "Histogram", "Baseline", "Candlestick", "Bar"],
                        "default": "Line",
                    },
                    "series_options": {"type": "object"},
                    "chart_id": {"type": "string"},
                },
                "required": ["widget_id", "series_id", "bars"],
            },
        ),
        Tool(
            name="tvchart_remove_series",
            description="""Remove a series or overlay by id.

Emits ``tvchart:remove-series``.  Works for any series added via
``tvchart_add_series`` or ``tvchart_add_indicator``.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "series_id": {"type": "string"},
                    "chart_id": {"type": "string"},
                },
                "required": ["widget_id", "series_id"],
            },
        ),
        Tool(
            name="tvchart_add_markers",
            description="""Add buy/sell or event markers at specific bars.

Emits ``tvchart:add-markers``.  Each marker is ``{time, position, color,
shape, text}`` where ``position`` is ``"aboveBar"`` or ``"belowBar"`` and
``shape`` is one of ``"arrowUp"``, ``"arrowDown"``, ``"circle"``, etc.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "markers": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "List of marker dicts",
                    },
                    "series_id": {"type": "string"},
                    "chart_id": {"type": "string"},
                },
                "required": ["widget_id", "markers"],
            },
        ),
        Tool(
            name="tvchart_add_price_line",
            description="""Draw a horizontal price line (support/resistance/target).

Emits ``tvchart:add-price-line``.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "price": {"type": "number"},
                    "color": {"type": "string", "default": "#2196F3"},
                    "line_width": {"type": "integer", "default": 1},
                    "title": {"type": "string", "default": ""},
                    "series_id": {"type": "string"},
                    "chart_id": {"type": "string"},
                },
                "required": ["widget_id", "price"],
            },
        ),
        Tool(
            name="tvchart_apply_options",
            description="""Apply chart-level or series-level option patches.

Emits ``tvchart:apply-options``.  ``chart_options`` patches the chart
(layout/grid/crosshair/timeScale); ``series_options`` patches the
specified series (colour, lineWidth, priceScaleId, etc.).""",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "chart_options": {"type": "object"},
                    "series_options": {"type": "object"},
                    "series_id": {"type": "string"},
                    "chart_id": {"type": "string"},
                },
                "required": ["widget_id"],
            },
        ),
        Tool(
            name="tvchart_add_indicator",
            description="""Add a built-in technical indicator to the chart.

Emits ``tvchart:add-indicator``.  The indicator is computed natively by
the charting engine from the current bar data.  Supports legend,
undo/redo, and subplot panes automatically.

Valid ``name`` values:
- Moving averages: ``SMA``, ``EMA``, ``WMA``, ``SMA (50)``, ``SMA (200)``,
  ``EMA (12)``, ``EMA (26)``, ``Moving Average``
- Momentum: ``RSI``, ``Momentum``
- Volatility: ``Bollinger Bands``, ``ATR``
- Volume: ``VWAP``, ``Volume SMA``
- Lightweight Examples: ``Average Price``, ``Median Price``, ``Weighted Close``,
  ``Percent Change``, ``Correlation``, ``Spread``, ``Ratio``, ``Sum``, ``Product``""",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "name": {"type": "string"},
                    "period": {
                        "type": "integer",
                        "description": "Lookback period (0 uses the indicator default)",
                    },
                    "color": {"type": "string", "description": "Hex colour (empty = auto-assign)"},
                    "source": {
                        "type": "string",
                        "description": "OHLC source: close/open/high/low/hl2/hlc3/ohlc4",
                    },
                    "method": {
                        "type": "string",
                        "description": "For Moving Average: SMA/EMA/WMA",
                    },
                    "multiplier": {"type": "number", "description": "Bollinger Bands multiplier"},
                    "ma_type": {"type": "string", "description": "Bollinger Bands MA type"},
                    "offset": {
                        "type": "integer",
                        "description": "Bar offset for indicator shifting",
                    },
                    "chart_id": {"type": "string"},
                },
                "required": ["widget_id", "name"],
            },
        ),
        Tool(
            name="tvchart_remove_indicator",
            description="""Remove a built-in indicator by series id.

Emits ``tvchart:remove-indicator``.  Grouped indicators (e.g. the three
Bollinger bands) are removed together, and subplot panes are cleaned up
automatically.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "series_id": {"type": "string"},
                    "chart_id": {"type": "string"},
                },
                "required": ["widget_id", "series_id"],
            },
        ),
        Tool(
            name="tvchart_list_indicators",
            description="""Return the list of active built-in indicators.

Synchronously round-trips ``tvchart:list-indicators`` →
``tvchart:list-indicators-response`` and returns the decoded response
(``{indicators: [{seriesId, name, type, period, color, group}]}``).""",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "chart_id": {"type": "string"},
                    "timeout": {"type": "number", "default": 5.0},
                },
                "required": ["widget_id"],
            },
        ),
        Tool(
            name="tvchart_show_indicators",
            description="Open the indicator picker panel.  Emits ``tvchart:show-indicators``.",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "chart_id": {"type": "string"},
                },
                "required": ["widget_id"],
            },
        ),
        Tool(
            name="tvchart_symbol_search",
            description="""Open the symbol search dialog, optionally pre-filling it.

Emits ``tvchart:symbol-search``.  When ``query`` is set the datafeed
search runs with that query and — if ``auto_select`` (default true) —
the exact-ticker match (or the first result otherwise) is selected as
soon as results arrive.  ``symbol_type`` and ``exchange`` narrow the
datafeed search to a specific security class or venue — e.g.
``symbol_type="etf"`` ensures ``SPY`` resolves to the SPDR ETF rather
than a near-prefix match like ``SPYM``.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "query": {"type": "string"},
                    "auto_select": {"type": "boolean", "default": True},
                    "symbol_type": {
                        "type": "string",
                        "description": (
                            "Security class filter (datafeed-provided values — "
                            "typically one of 'equity', 'etf', 'index', "
                            "'mutualfund', 'future', 'cryptocurrency', "
                            "'currency').  Case-insensitive."
                        ),
                    },
                    "exchange": {
                        "type": "string",
                        "description": "Exchange filter (datafeed-provided values).  Case-insensitive.",
                    },
                    "chart_id": {"type": "string"},
                },
                "required": ["widget_id"],
            },
        ),
        Tool(
            name="tvchart_compare",
            description="""Add a symbol as an overlay compare series on the chart.

Emits ``tvchart:compare``.  When ``query`` is set the compare panel
runs a datafeed search and — if ``auto_add`` (default true) — adds the
exact-ticker match (or the first result otherwise) to the chart.  The
tool polls chart state until the new compare series appears in
``state.compareSymbols`` and returns the confirmed state; if the match
doesn't commit in time, the result includes a ``note``.  Omit
``query`` to just open the panel for the user.  ``symbol_type`` and
``exchange`` narrow the datafeed search — e.g. ``symbol_type="etf"``
routes ``SPY`` to the SPDR ETF rather than a near-prefix match.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "query": {
                        "type": "string",
                        "description": "Ticker / name to search and auto-add as a compare series.",
                    },
                    "auto_add": {
                        "type": "boolean",
                        "default": True,
                        "description": "If true, auto-commit the matching result.  If false, just open the dialog.",
                    },
                    "symbol_type": {
                        "type": "string",
                        "description": (
                            "Security class filter (datafeed-provided values — "
                            "typically one of 'equity', 'etf', 'index', "
                            "'mutualfund', 'future', 'cryptocurrency', "
                            "'currency').  Case-insensitive."
                        ),
                    },
                    "exchange": {
                        "type": "string",
                        "description": "Exchange filter (datafeed-provided values).  Case-insensitive.",
                    },
                    "chart_id": {"type": "string"},
                },
                "required": ["widget_id"],
            },
        ),
        Tool(
            name="tvchart_change_interval",
            description="""Change the chart timeframe / bar interval.

Emits ``tvchart:interval-change``.  Valid intervals match the chart's
``supported_resolutions``.  Typical values: ``1m 3m 5m 15m 30m 45m 1h
2h 3h 4h 1d 1w 1M 3M 6M 12M``.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "value": {"type": "string", "description": "Interval (e.g. '5m', '1d')"},
                    "chart_id": {"type": "string"},
                },
                "required": ["widget_id", "value"],
            },
        ),
        Tool(
            name="tvchart_set_visible_range",
            description="""Set the chart's visible time range.

Emits ``tvchart:time-scale`` with ``{visibleRange: {from, to}}``.  Times
are Unix epoch seconds.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "from_time": {"type": "integer"},
                    "to_time": {"type": "integer"},
                    "chart_id": {"type": "string"},
                },
                "required": ["widget_id", "from_time", "to_time"],
            },
        ),
        Tool(
            name="tvchart_fit_content",
            description="Fit all bars to the visible area.  Emits ``tvchart:time-scale`` with ``{fitContent: true}``.",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "chart_id": {"type": "string"},
                },
                "required": ["widget_id"],
            },
        ),
        Tool(
            name="tvchart_time_range",
            description="""Zoom to a preset time range.

Emits ``tvchart:time-range``.  Typical values: ``1D 1W 1M 3M 6M 1Y 5Y YTD``.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "value": {"type": "string"},
                    "chart_id": {"type": "string"},
                },
                "required": ["widget_id", "value"],
            },
        ),
        Tool(
            name="tvchart_time_range_picker",
            description="Open the date-range picker dialog.  Emits ``tvchart:time-range-picker``.",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "chart_id": {"type": "string"},
                },
                "required": ["widget_id"],
            },
        ),
        Tool(
            name="tvchart_log_scale",
            description="Toggle the logarithmic price scale.  Emits ``tvchart:log-scale``.",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "value": {"type": "boolean"},
                    "chart_id": {"type": "string"},
                },
                "required": ["widget_id", "value"],
            },
        ),
        Tool(
            name="tvchart_auto_scale",
            description="Toggle auto-scale on the price axis.  Emits ``tvchart:auto-scale``.",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "value": {"type": "boolean"},
                    "chart_id": {"type": "string"},
                },
                "required": ["widget_id", "value"],
            },
        ),
        Tool(
            name="tvchart_chart_type",
            description="""Change the main series chart type.

Emits ``tvchart:chart-type-change``.  Valid values: ``Candles``,
``Hollow Candles``, ``Heikin Ashi``, ``Bars``, ``Line``, ``Area``,
``Baseline``, ``Histogram``.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "value": {"type": "string"},
                    "series_id": {"type": "string"},
                    "chart_id": {"type": "string"},
                },
                "required": ["widget_id", "value"],
            },
        ),
        Tool(
            name="tvchart_drawing_tool",
            description="""Activate a drawing tool or toggle drawing-layer state.

Emits one of ``tvchart:tool-cursor``, ``tvchart:tool-crosshair``,
``tvchart:tool-magnet``, ``tvchart:tool-eraser``,
``tvchart:tool-visibility``, ``tvchart:tool-lock`` depending on ``mode``.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "mode": {
                        "type": "string",
                        "enum": ["cursor", "crosshair", "magnet", "eraser", "visibility", "lock"],
                    },
                    "chart_id": {"type": "string"},
                },
                "required": ["widget_id", "mode"],
            },
        ),
        Tool(
            name="tvchart_undo",
            description="Undo the last chart action.  Emits ``tvchart:undo``.",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "chart_id": {"type": "string"},
                },
                "required": ["widget_id"],
            },
        ),
        Tool(
            name="tvchart_redo",
            description="Redo the last undone chart action.  Emits ``tvchart:redo``.",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "chart_id": {"type": "string"},
                },
                "required": ["widget_id"],
            },
        ),
        Tool(
            name="tvchart_show_settings",
            description="Open the chart settings modal.  Emits ``tvchart:show-settings``.",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "chart_id": {"type": "string"},
                },
                "required": ["widget_id"],
            },
        ),
        Tool(
            name="tvchart_toggle_dark_mode",
            description="Toggle the chart's dark/light theme.  Emits ``tvchart:toggle-dark-mode``.",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "value": {"type": "boolean", "description": "true = dark, false = light"},
                    "chart_id": {"type": "string"},
                },
                "required": ["widget_id", "value"],
            },
        ),
        Tool(
            name="tvchart_screenshot",
            description="Take a screenshot of the chart.  Emits ``tvchart:screenshot``.",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "chart_id": {"type": "string"},
                },
                "required": ["widget_id"],
            },
        ),
        Tool(
            name="tvchart_fullscreen",
            description="Toggle chart fullscreen mode.  Emits ``tvchart:fullscreen``.",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "chart_id": {"type": "string"},
                },
                "required": ["widget_id"],
            },
        ),
        Tool(
            name="tvchart_save_layout",
            description="""Save the current chart layout (indicators + drawings).

Emits ``tvchart:save-layout``.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "name": {"type": "string"},
                    "chart_id": {"type": "string"},
                },
                "required": ["widget_id"],
            },
        ),
        Tool(
            name="tvchart_open_layout",
            description="Open the layout picker dialog.  Emits ``tvchart:open-layout``.",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "chart_id": {"type": "string"},
                },
                "required": ["widget_id"],
            },
        ),
        Tool(
            name="tvchart_save_state",
            description="""Request a full state export from every chart in the widget.

Emits ``tvchart:save-state``.  Use ``tvchart_request_state`` for a
synchronous single-chart snapshot.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                },
                "required": ["widget_id"],
            },
        ),
        Tool(
            name="tvchart_request_state",
            description="""Read a single chart's full state synchronously.

Round-trips ``tvchart:request-state`` → ``tvchart:state-response`` and
returns the decoded state object (``{chartId, theme, series,
visibleRange, rawData, drawings, indicators}``).""",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "chart_id": {"type": "string"},
                    "timeout": {"type": "number", "default": 5.0},
                },
                "required": ["widget_id"],
            },
        ),
        # =====================================================================
        # Widget Manipulation
        # =====================================================================
        Tool(
            name="set_content",
            description="""Update element text/HTML by component_id.

Uses pywry:set-content event. The element must have a component_id set
(e.g., via Div component or id attribute in HTML).""",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "component_id": {
                        "type": "string",
                        "description": "Element ID to update",
                    },
                    "text": {"type": "string", "description": "New text content"},
                    "html": {
                        "type": "string",
                        "description": "New HTML content (overrides text)",
                    },
                },
                "required": ["widget_id", "component_id"],
            },
        ),
        Tool(
            name="set_style",
            description="""Update element CSS styles by component_id.

Uses pywry:set-style event. Pass styles as camelCase properties.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "component_id": {
                        "type": "string",
                        "description": "Element ID to update",
                    },
                    "styles": {
                        "type": "object",
                        "description": "CSS styles as {property: value}",
                        "additionalProperties": {"type": "string"},
                    },
                },
                "required": ["widget_id", "component_id", "styles"],
            },
        ),
        Tool(
            name="show_toast",
            description="Display a toast notification in the widget.",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "message": {"type": "string"},
                    "type": {
                        "type": "string",
                        "enum": ["info", "success", "warning", "error"],
                        "default": "info",
                    },
                    "duration": {"type": "integer", "default": 3000},
                },
                "required": ["widget_id", "message"],
            },
        ),
        Tool(
            name="update_theme",
            description="Switch widget theme to dark/light/system.",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "theme": {
                        "type": "string",
                        "enum": ["dark", "light", "system"],
                    },
                },
                "required": ["widget_id", "theme"],
            },
        ),
        Tool(
            name="inject_css",
            description="""Inject CSS styles into a widget.

Creates or updates a <style> element with the given CSS.
Use a unique style_id to update the same styles later.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "css": {"type": "string", "description": "CSS rules to inject"},
                    "style_id": {
                        "type": "string",
                        "description": "Unique ID for the style element (for updates)",
                        "default": "pywry-injected-style",
                    },
                },
                "required": ["widget_id", "css"],
            },
        ),
        Tool(
            name="remove_css",
            description="Remove previously injected CSS by style_id.",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "style_id": {
                        "type": "string",
                        "description": "ID of style element to remove",
                    },
                },
                "required": ["widget_id", "style_id"],
            },
        ),
        Tool(
            name="navigate",
            description="Navigate the widget to a new URL (client-side redirect).",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "url": {"type": "string", "description": "URL to navigate to"},
                },
                "required": ["widget_id", "url"],
            },
        ),
        Tool(
            name="download",
            description="Trigger a file download in the browser.",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "content": {"type": "string", "description": "File content"},
                    "filename": {"type": "string", "description": "Download filename"},
                    "mime_type": {
                        "type": "string",
                        "description": "MIME type (e.g., text/csv, application/json)",
                        "default": "application/octet-stream",
                    },
                },
                "required": ["widget_id", "content", "filename"],
            },
        ),
        Tool(
            name="update_plotly",
            description="Update an existing Plotly chart with new data/layout.",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "figure_json": {
                        "type": "string",
                        "description": "New figure JSON from fig.to_json()",
                    },
                    "layout_only": {
                        "type": "boolean",
                        "description": "If true, only update layout (not data)",
                        "default": False,
                    },
                },
                "required": ["widget_id", "figure_json"],
            },
        ),
        Tool(
            name="update_marquee",
            description="""Update marquee content, speed, or state.

Can update text, individual ticker items, speed, or pause/resume animation.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "component_id": {
                        "type": "string",
                        "description": "Marquee component ID",
                    },
                    "text": {"type": "string", "description": "New text content"},
                    "html": {"type": "string", "description": "New HTML content"},
                    "speed": {
                        "type": "number",
                        "description": "New animation speed in seconds",
                    },
                    "paused": {
                        "type": "boolean",
                        "description": "Pause/resume animation",
                    },
                    "ticker_update": {
                        "type": "object",
                        "description": "Update a single ticker item",
                        "properties": {
                            "ticker": {
                                "type": "string",
                                "description": "Ticker ID to update",
                            },
                            "text": {"type": "string"},
                            "html": {"type": "string"},
                            "styles": {"type": "object"},
                            "class_add": {"type": "string"},
                            "class_remove": {"type": "string"},
                        },
                    },
                },
                "required": ["widget_id", "component_id"],
            },
        ),
        Tool(
            name="update_ticker_item",
            description="""Update a single ticker item in a Marquee by its ticker ID.

Uses TickerItem.update_payload() pattern to generate the event.
Updates ALL elements matching the ticker (handles duplicated marquee content).""",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "ticker": {
                        "type": "string",
                        "description": "Ticker ID to update (e.g., 'AAPL', 'BTC')",
                    },
                    "text": {"type": "string", "description": "New text content"},
                    "html": {"type": "string", "description": "New HTML content"},
                    "styles": {
                        "type": "object",
                        "description": "CSS styles to apply (e.g., {color: 'green'})",
                        "additionalProperties": {"type": "string"},
                    },
                    "class_add": {
                        "description": "CSS class(es) to add",
                        "oneOf": [
                            {"type": "string"},
                            {"type": "array", "items": {"type": "string"}},
                        ],
                    },
                    "class_remove": {
                        "description": "CSS class(es) to remove",
                        "oneOf": [
                            {"type": "string"},
                            {"type": "array", "items": {"type": "string"}},
                        ],
                    },
                },
                "required": ["widget_id", "ticker"],
            },
        ),
        # =====================================================================
        # Widget Management
        # =====================================================================
        Tool(
            name="list_widgets",
            description="List all active widgets with their URLs.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_events",
            description="""Get events from a widget (button clicks, input changes, etc.).

Events include: event_type, data, and label. Use clear=true to clear after reading.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "clear": {"type": "boolean", "default": False},
                },
                "required": ["widget_id"],
            },
        ),
        Tool(
            name="destroy_widget",
            description="Destroy a widget and clean up resources.",
            inputSchema={
                "type": "object",
                "properties": {"widget_id": {"type": "string"}},
                "required": ["widget_id"],
            },
        ),
        Tool(
            name="send_event",
            description="""Send a custom event to a widget.

**AG Grid Data Updates (CRITICAL - use these exact formats):**
- grid:update-data: {"data": [...rows...], "strategy": "set"} - Replace all data
- grid:update-data: {"data": [...rows...], "strategy": "append"} - Append rows
- grid:update-data: {"data": [...rows...], "strategy": "update"} - Update existing
- grid:update-columns: {"columnDefs": [...]} - Update columns
- grid:update-cell: {"rowId": "row-1", "colId": "price", "value": 99.50} - Update cell

**AG Grid State Persistence:**
- grid:request-state: {} - Request state (response via grid:state-response)
- grid:restore-state: {"state": {...savedState...}} - Restore saved state
- grid:reset-state: {"hard": false} - Soft reset (keeps columns)
- grid:reset-state: {"hard": true} - Hard reset (full reset)

**Plotly Chart Updates:**
- plotly:update-figure: {"data": [...], "layout": {...}, "config": {...}}
- plotly:update-layout: {"layout": {...}}
- plotly:reset-zoom: {} - Reset chart zoom

**Plotly State Persistence:**
- plotly:request-state: {} - Request state (response via plotly:state-response)
- plotly:export-data: {} - Export data (response via plotly:export-response)

**Toolbar Component State (Get/Set Values):**
- toolbar:set-value: {"componentId": "my-select", "value": "option2"} - Set one
- toolbar:set-values: {"values": {"id1": "v1", "id2": true}} - Set multiple
- toolbar:request-state: {} - Request all values (response via toolbar:state-response)

**DOM Content Updates:**
- pywry:set-content: {"id": "elementId", "text": "..."} or {"id": "elementId", "html": "..."}
- pywry:set-style: {"id": "elementId", "styles": {"color": "red", "fontSize": "18px"}}

**Theme Updates:**
- pywry:update-theme: {"theme": "dark"} or {"theme": "light"} or {"theme": "system"}

**Other Events:**
- pywry:alert: {"message": "...", "type": "info|success|warning|error"}
- pywry:navigate: {"url": "https://..."}
- pywry:download: {"content": "...", "filename": "file.txt", "mimeType": "text/plain"}
- toolbar:marquee-set-item: {"ticker": "AAPL", "text": "AAPL $185", "styles": {"color": "green"}}""",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "event_type": {"type": "string"},
                    "data": {"type": "object"},
                },
                "required": ["widget_id", "event_type", "data"],
            },
        ),
        # =====================================================================
        # Resources / Export
        # =====================================================================
        Tool(
            name="get_component_docs",
            description="""Get documentation for a PyWry component.

Returns detailed documentation including properties and usage examples.
Available components: button, select, multiselect, toggle, checkbox, radio,
tabs, text, textarea, search, number, date, slider, range, div, secret,
marquee, ticker_item.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "component": {
                        "type": "string",
                        "description": "Component name",
                        "enum": list(COMPONENT_DOCS.keys()),
                    },
                },
                "required": ["component"],
            },
        ),
        Tool(
            name="get_component_source",
            description="""Get source code for a PyWry component class.

Returns the Python source code for implementing the component.
Useful for understanding implementation details or extending components.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "component": {
                        "type": "string",
                        "description": "Component name",
                        "enum": [*list(COMPONENT_DOCS.keys()), "toolbar", "option"],
                    },
                },
                "required": ["component"],
            },
        ),
        Tool(
            name="export_widget",
            description="""Export a created widget as Python code.

Generates standalone Python code that recreates the widget without MCP.
Use this to save your work or share widget implementations.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {
                        "type": "string",
                        "description": "ID of the widget to export",
                    },
                },
                "required": ["widget_id"],
            },
        ),
        Tool(
            name="list_resources",
            description="""List all available resources.

Returns URIs for:
- Component documentation (pywry://component/{name})
- Component source code (pywry://source/{name})
- Widget exports (pywry://export/{widget_id})
- Built-in events reference (pywry://docs/events)
- Quick start guide (pywry://docs/quickstart)""",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_widget_app",
            description="""Return the widget as a full AppArtifact snapshot.

Renders *widget_id* as self-contained HTML (CSS + JS + data inlined)
and returns it as an ``AppArtifact`` with a bumped revision counter.
MCP clients that render ``text/html`` embedded resources (Claude
Desktop artifact pane, mcp-ui clients, PyWry's own chat widget) show
the app inline. Older revisions of the same widget in chat history
freeze at their last known state because their WebSocket bridge is
rejected server-side on revision mismatch.

Widget-creating tools (``create_widget``, ``show_plotly``,
``show_dataframe``, ``show_tvchart``, ``create_chat_widget``)
auto-return an ``AppArtifact`` already; call this explicitly only to
re-snapshot an existing widget after it has been mutated.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {
                        "type": "string",
                        "description": "ID of the widget to snapshot",
                    },
                    "title": {
                        "type": "string",
                        "description": "Optional artifact title",
                        "default": "",
                    },
                    "height": {
                        "type": "string",
                        "description": "CSS height for the iframe (e.g. '600px')",
                        "default": "600px",
                    },
                },
                "required": ["widget_id"],
            },
        ),
        # =====================================================================
        # Chat
        # =====================================================================
        Tool(
            name="create_chat_widget",
            description="""Create a chat widget with conversational UI.

Returns a widget with message area, input bar, optional thread sidebar,
slash commands, and settings panel. Supports streaming responses and
stop-generation.

**Example**:
```json
{
  "title": "AI Chat",
  "system_prompt": "You are a helpful assistant.",
  "model": "gpt-4",
  "streaming": true,
  "provider": "openai",
  "show_sidebar": true
}
```""",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "default": "Chat"},
                    "height": {"type": "integer", "default": 600},
                    "system_prompt": {
                        "type": "string",
                        "description": "System prompt for the LLM",
                    },
                    "model": {
                        "type": "string",
                        "default": "gpt-4",
                        "description": "Model name for the provider",
                    },
                    "temperature": {
                        "type": "number",
                        "default": 0.7,
                        "minimum": 0,
                        "maximum": 2,
                    },
                    "max_tokens": {
                        "type": "integer",
                        "default": 4096,
                        "description": "Max tokens per response",
                    },
                    "streaming": {
                        "type": "boolean",
                        "default": True,
                        "description": "Enable streaming responses",
                    },
                    "persist": {
                        "type": "boolean",
                        "default": False,
                        "description": "Persist threads in ChatStore",
                    },
                    "provider": {
                        "type": "string",
                        "enum": ["openai", "anthropic", "callback"],
                        "description": "LLM provider name",
                    },
                    "show_sidebar": {
                        "type": "boolean",
                        "default": True,
                        "description": "Show thread sidebar",
                    },
                    "slash_commands": {
                        "type": "array",
                        "description": "Custom slash commands",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "description": {"type": "string"},
                            },
                            "required": ["name"],
                        },
                    },
                    "toolbars": {
                        "type": "array",
                        "description": "Additional toolbars around the chat area",
                        "items": TOOLBAR_SCHEMA,
                    },
                },
            },
        ),
        Tool(
            name="chat_send_message",
            description="""Send a user message to a chat widget and get the assistant response.

The message is appended to the thread history and the configured LLM
provider is invoked. If streaming is enabled, chunks are emitted as
progress notifications.

To stop a running generation, use `chat_stop_generation`.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "text": {
                        "type": "string",
                        "description": "User message text",
                    },
                    "thread_id": {
                        "type": "string",
                        "description": "Thread ID (uses active thread if omitted)",
                    },
                },
                "required": ["widget_id", "text"],
            },
        ),
        Tool(
            name="chat_stop_generation",
            description="""Stop an in-flight LLM generation.

Sets the cancel event on the active GenerationHandle, causing the
provider to stop producing tokens. Returns the partial content generated
so far. Idempotent — safe to call multiple times.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "thread_id": {
                        "type": "string",
                        "description": "Thread to stop generation in",
                    },
                },
                "required": ["widget_id"],
            },
        ),
        Tool(
            name="chat_manage_thread",
            description="""Create, switch, delete, or rename a chat thread.

Actions:
- `create`: Create a new thread (returns thread_id)
- `switch`: Switch to an existing thread (loads history)
- `delete`: Delete a thread and its messages
- `rename`: Rename a thread
- `list`: List all threads for the widget""",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "action": {
                        "type": "string",
                        "enum": ["create", "switch", "delete", "rename", "list"],
                    },
                    "thread_id": {
                        "type": "string",
                        "description": "Thread ID (required for switch/delete/rename)",
                    },
                    "title": {
                        "type": "string",
                        "description": "Thread title (for create/rename)",
                    },
                },
                "required": ["widget_id", "action"],
            },
        ),
        Tool(
            name="chat_register_command",
            description="""Register a slash command in a chat widget at runtime.

The command name is auto-prefixed with `/` if missing.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "name": {
                        "type": "string",
                        "description": "Command name (e.g., 'help' or '/help')",
                    },
                    "description": {
                        "type": "string",
                        "description": "Description shown in command palette",
                    },
                },
                "required": ["widget_id", "name"],
            },
        ),
        Tool(
            name="chat_get_history",
            description="""Retrieve conversation history for a thread.

Supports cursor-based pagination via `before_id`.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "thread_id": {
                        "type": "string",
                        "description": "Thread ID (uses active thread if omitted)",
                    },
                    "limit": {
                        "type": "integer",
                        "default": 50,
                        "description": "Max messages to return",
                    },
                    "before_id": {
                        "type": "string",
                        "description": "Cursor: return messages before this ID",
                    },
                },
                "required": ["widget_id"],
            },
        ),
        Tool(
            name="chat_update_settings",
            description="""Update chat settings for a widget (model, temperature, system prompt, etc.).

Changes are applied immediately and pushed to the frontend.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "model": {"type": "string"},
                    "temperature": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 2,
                    },
                    "max_tokens": {"type": "integer"},
                    "system_prompt": {"type": "string"},
                    "streaming": {"type": "boolean"},
                },
                "required": ["widget_id"],
            },
        ),
        Tool(
            name="chat_set_typing",
            description="Show or hide the typing indicator in a chat widget.",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "typing": {
                        "type": "boolean",
                        "default": True,
                        "description": "Whether to show the typing indicator",
                    },
                    "thread_id": {"type": "string"},
                },
                "required": ["widget_id"],
            },
        ),
    ]
