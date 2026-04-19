# Tools Reference

The MCP server exposes **38 tools** organized into eight groups.
Every description, parameter name, type, and default below comes directly from the tool schemas in the source code.

!!! warning "Mandatory first step"
    Call `get_skills` with `skill="component_reference"` **before** creating any widget.
    The component reference is the authoritative source for event signatures,
    system events, and JSON schemas for all 18 toolbar component types.

---

## Discovery

### get_skills

Get context-appropriate skills and guidance for creating widgets.

The `component_reference` skill is **mandatory** — it contains the only correct event signatures and system events. Without it, the agent will not know the correct payloads for `grid:update-data`, `plotly:update-figure`, `toolbar:set-value`, etc.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `skill` | `string` | No | Skill to retrieve. If omitted, returns the full list with descriptions. |

**Skill IDs:** `component_reference`, `interactive_buttons`, `native`, `jupyter`, `iframe`, `deploy`, `css_selectors`, `styling`, `data_visualization`, `forms_and_inputs`, `modals`, `chat`, `autonomous_building`

**System events available via `component_reference`:**

| Event | Payload | Purpose |
|:---|:---|:---|
| `grid:update-data` | `{"data": [...], "strategy": "set|append|update"}` | Replace, append, or merge grid rows |
| `grid:request-state` | `{}` | Request grid state (response via `grid:state-response`) |
| `grid:restore-state` | `{"state": {...}}` | Restore a saved grid state |
| `grid:reset-state` | `{"hard": true|false}` | Soft reset (keeps columns) or hard reset |
| `plotly:update-figure` | `{"data": [...], "layout": {...}}` | Replace chart data and layout |
| `plotly:request-state` | `{}` | Request chart state |
| `pywry:set-content` | `{"id": "...", "text": "..."}` or `{"id": "...", "html": "..."}` | Update a DOM element |
| `pywry:update-theme` | `{"theme": "dark|light|system"}` | Switch theme |
| `toolbar:set-value` | `{"componentId": "...", "value": "..."}` | Set a toolbar component's value |
| `toolbar:request-state` | `{}` | Request all toolbar values (response via `toolbar:state-response`) |

---

## Widget Creation

### create_widget

Create an interactive native window with HTML content and Pydantic toolbar components.

| Parameter | Type | Required | Default | Description |
|:---|:---|:---|:---|:---|
| `html` | `string` | **Yes** | — | HTML content. Use `id` attributes or `Div` components for dynamic content. |
| `title` | `string` | No | `"PyWry Widget"` | Window title |
| `height` | `integer` | No | `500` | Window height in pixels |
| `include_plotly` | `boolean` | No | `false` | Include Plotly.js |
| `include_aggrid` | `boolean` | No | `false` | Include AG Grid |
| `toolbars` | `array` | No | — | Toolbar definitions (see schema below) |
| `callbacks` | `object` | No | — | Map of event names → callback actions that run on the Python backend |

**Returns (native):** `{"widget_id": "...", "mode": "native", "created": true}`
**Returns (headless):** `{"widget_id": "...", "path": "/widget/...", "export_uri": "pywry://export/...", "created": true}`

#### How events work

Toolbar components fire events when users interact with them. Every component's `event` attribute names the event (e.g. `"app:save"`, `"filter:region"`). When the user clicks a button or changes a select, the event travels from the browser back to the Python backend:

```
Browser click → toolbar-handlers.js reads data-event
  → WebSocket / anywidget traitlet sync → Python backend
  → widget.on() handlers fire → callback(data, event_type, label)
```

Events are registered on the widget via `widget.on(event_name, callback)`. Every toolbar item's event is automatically registered so the MCP server can capture interactions and surface them through `get_events`.

#### Callbacks — wiring events to backend actions

The `callbacks` parameter lets you wire events directly to Python-side actions that execute on the backend when the event fires. Each entry maps an event name to an action config:

| Property | Type | Description |
|:---|:---|:---|
| `action` | `string` | One of `increment`, `decrement`, `set`, `toggle`, `emit` |
| `target` | `string` | `component_id` of the DOM element to update after the action |
| `state_key` | `string` | Key in a per-widget state dict on the backend (default: `"value"`) |
| `value` | `any` | Value to use for the `set` action |
| `emit_event` | `string` | Event to emit to the browser (for the `emit` action) |
| `emit_data` | `object` | Payload to emit with the event |

When a callback fires:

1. The action modifies the widget's backend state dict (e.g. `state["value"] += 1` for `increment`).
2. If `target` is set, the server emits `pywry:set-content` with `{"id": target, "text": str(new_value)}` to push the updated value to the browser immediately.
3. The `emit` action skips the state update and instead emits a custom event to the browser via `widget.emit()`.

This means the callback runs real Python code on the backend and pushes results to the browser — there is no client-side magic.

#### Events without callbacks → get_events

Toolbar events that are **not** covered by an explicit `callbacks` entry are still captured by the MCP server and queued. The agent reads them with [`get_events`](#get_events) and decides what to do (update a chart, change data, show a toast, etc.).

#### Toolbar schema

```json
{
  "position": "top",        // top | bottom | left | right | inside
  "items": [
    {
      "type": "button",     // any of the 18 component types
      "label": "Save",
      "event": "app:save",  // namespace:action (avoid pywry/plotly/grid namespaces)
      "variant": "primary", // primary | neutral | danger | success
      "size": "md"          // sm | md | lg
    }
  ]
}
```

#### Component types and their event payloads

| Type | Event payload | Key properties |
|:---|:---|:---|
| `button` | `{componentId, ...data}` | `label`, `event`, `variant` |
| `select` | `{value, componentId}` | `event`, `options`, `selected` |
| `multiselect` | `{values: [], componentId}` | `event`, `options` |
| `toggle` | `{value: boolean, componentId}` | `event`, `label` |
| `checkbox` | `{value: boolean, componentId}` | `event`, `label` |
| `radio` | `{value, componentId}` | `event`, `options` |
| `tabs` | `{value, componentId}` | `event`, `options` |
| `text` | `{value, componentId}` | `event`, `placeholder` |
| `textarea` | `{value, componentId}` | `event`, `rows` |
| `search` | `{value, componentId}` | `event`, `debounce` |
| `number` | `{value: number, componentId}` | `event`, `min`, `max`, `step` |
| `date` | `{value: "YYYY-MM-DD", componentId}` | `event` |
| `slider` | `{value: number, componentId}` | `event`, `min`, `max`, `step`, `show_value` |
| `range` | `{start, end, componentId}` | `event`, `min`, `max` |
| `secret` | `{value: base64, encoded: true, componentId}` | `event`, `show_toggle`, `show_copy` |
| `div` | *(no events)* | `content`, `component_id`, `style` |
| `marquee` | `{value, componentId}` *(if clickable)* | `text`, `speed`, `behavior`, `ticker_items` |

**Options format** (select, multiselect, radio, tabs):

```json
"options": [{"label": "Dark", "value": "dark"}, {"label": "Light", "value": "light"}]
```

---

### show_plotly

Create a Plotly chart widget. Pass figure JSON from `fig.to_json()`.

| Parameter | Type | Required | Default | Description |
|:---|:---|:---|:---|:---|
| `figure_json` | `string` | **Yes** | — | Plotly figure as a JSON string |
| `title` | `string` | No | `"Plotly Chart"` | Window title |
| `height` | `integer` | No | `500` | Window height |

**Returns:** `{"widget_id": "...", "path": "...", "created": true}`

To update later, use `update_plotly` or `send_event` with event `plotly:update-figure` and data `{"data": [...], "layout": {...}}`.

---

### show_dataframe

Create an AG Grid table widget from JSON data.

| Parameter | Type | Required | Default | Description |
|:---|:---|:---|:---|:---|
| `data_json` | `string` | **Yes** | — | Data as JSON array of row objects |
| `title` | `string` | No | `"Data Table"` | Window title |
| `height` | `integer` | No | `500` | Window height |

**Returns:** `{"widget_id": "...", "path": "...", "created": true}`

To update later, use `send_event` with event `grid:update-data` and data `{"data": [...], "strategy": "set"}`. Strategies: `set` (replace all rows), `append` (add rows), `update` (merge by row ID).

---

### show_tvchart

Create a TradingView Lightweight Charts widget from JSON data.

| Parameter | Type | Required | Default | Description |
|:---|:---|:---|:---|:---|
| `data_json` | `string` | **Yes** | — | Chart data as JSON array of OHLCV objects |
| `title` | `string` | No | `"Chart"` | Window title |
| `height` | `integer` | No | `500` | Window height |
| `chart_options` | `string` | No | `null` | Chart-level options as JSON string |
| `series_options` | `string` | No | `null` | Series-level options as JSON string |

**Returns:** `{"widget_id": "...", "path": "...", "created": true}`

On creation the widget is wired to capture `tvchart:click`,
`tvchart:crosshair-move`, `tvchart:visible-range-change`,
`tvchart:drawing-added`, `tvchart:drawing-deleted`,
`tvchart:open-layout-request`, `tvchart:interval-change`, and
`tvchart:chart-type-change` into the MCP events dict — retrieve them
later with `get_events`.

---

## TVChart Manipulation

Every action the TradingView chart supports — data updates, indicators,
chart type, symbol, interval, drawing tools, layout persistence — is
exposed as a dedicated `tvchart_*` tool.  All tools take the owning
`widget_id` plus an optional `chart_id` for widgets hosting multiple
charts.

### Data and series

#### tvchart_update_series

Replace the bar data for a chart series.  Emits `tvchart:update`.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | |
| `bars` | `array` | **Yes** | OHLCV bar dicts (time in epoch seconds) |
| `volume` | `array` | No | Optional separate volume series |
| `series_id` | `string` | No | Target series (defaults to the main series) |
| `chart_id` | `string` | No | |
| `fit_content` | `boolean` | No | Default `true` |

#### tvchart_update_bar

Stream a single real-time bar update.  Emits `tvchart:stream`.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | |
| `bar` | `object` | **Yes** | Bar dict with time/open/high/low/close/volume |
| `series_id` | `string` | No | |
| `chart_id` | `string` | No | |

#### tvchart_add_series

Add a pre-computed overlay series.  Emits `tvchart:add-series`.  Use
`tvchart_add_indicator` instead when the JS indicator engine can
compute the values for you.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | |
| `series_id` | `string` | **Yes** | Unique id for later removal |
| `bars` | `array` | **Yes** | Series data (shape depends on series_type) |
| `series_type` | `string` | No | `Line` / `Area` / `Histogram` / `Baseline` / `Candlestick` / `Bar` |
| `series_options` | `object` | No | Color, lineWidth, priceScaleId, … |
| `chart_id` | `string` | No | |

#### tvchart_remove_series

Remove a series or overlay by id.  Emits `tvchart:remove-series`.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | |
| `series_id` | `string` | **Yes** | |
| `chart_id` | `string` | No | |

#### tvchart_add_markers

Add buy/sell or event markers at specific bars.  Emits `tvchart:add-markers`.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | |
| `markers` | `array` | **Yes** | `[{time, position, color, shape, text}]` |
| `series_id` | `string` | No | |
| `chart_id` | `string` | No | |

#### tvchart_add_price_line

Draw a horizontal price line.  Emits `tvchart:add-price-line`.

| Parameter | Type | Required | Default | Description |
|:---|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | — | |
| `price` | `number` | **Yes** | — | |
| `color` | `string` | No | `#2196F3` | |
| `line_width` | `integer` | No | `1` | |
| `title` | `string` | No | `""` | |
| `series_id` | `string` | No | — | |
| `chart_id` | `string` | No | — | |

#### tvchart_apply_options

Patch chart-level or series-level options.  Emits `tvchart:apply-options`.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | |
| `chart_options` | `object` | No | Chart-level patches (layout, grid, crosshair, timeScale) |
| `series_options` | `object` | No | Series-level patches |
| `series_id` | `string` | No | Target series when patching series options |
| `chart_id` | `string` | No | |

### Built-in indicators

The JS indicator engine computes these natively from the chart's bar
data, manages the legend and subplot panes, and supports undo/redo.

#### tvchart_add_indicator

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | |
| `name` | `string` | **Yes** | `SMA`, `EMA`, `WMA`, `SMA (50)`, `SMA (200)`, `EMA (12)`, `EMA (26)`, `Moving Average`, `RSI`, `Momentum`, `Bollinger Bands`, `ATR`, `VWAP`, `Volume SMA`, `Average Price`, `Median Price`, `Weighted Close`, `Percent Change`, `Correlation`, `Spread`, `Ratio`, `Sum`, `Product` |
| `period` | `integer` | No | Lookback period (0 uses the indicator default) |
| `color` | `string` | No | Hex colour (empty = auto-assign) |
| `source` | `string` | No | OHLC source: `close` / `open` / `high` / `low` / `hl2` / `hlc3` / `ohlc4` |
| `method` | `string` | No | For Moving Average: `SMA` / `EMA` / `WMA` |
| `multiplier` | `number` | No | Bollinger Bands multiplier |
| `ma_type` | `string` | No | Bollinger Bands MA type |
| `offset` | `integer` | No | Bar offset for indicator shifting |
| `chart_id` | `string` | No | |

**Compare-derivative indicators** (`Spread`, `Ratio`, `Sum`, `Product`,
`Correlation`) require a second series to compute against.  Add the
secondary ticker first via `tvchart_compare(widget_id, query=...)`,
then call `tvchart_add_indicator` with the derivative name — the
chart picks up the most recent compare series as the secondary.
`list_indicators` / `request_state` resolve the secondary back to its
ticker in `secondarySymbol` so agents can describe the indicator as
e.g. `Spread(AAPL, MSFT)` instead of `Spread(compare-msft)`.

#### tvchart_remove_indicator

Remove by series id.  Grouped indicators (e.g. the three Bollinger
bands) are removed together.  Emits `tvchart:remove-indicator`.

| Parameter | Type | Required |
|:---|:---|:---|
| `widget_id` | `string` | **Yes** |
| `series_id` | `string` | **Yes** |
| `chart_id` | `string` | No |

#### tvchart_list_indicators

Synchronously round-trips `tvchart:list-indicators` /
`tvchart:list-indicators-response` and returns the indicator inventory.

| Parameter | Type | Required | Default | Description |
|:---|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | — | |
| `chart_id` | `string` | No | — | |
| `timeout` | `number` | No | `5.0` | Response wait, seconds |

Each indicator entry in the result contains:

- `seriesId` — stable id used by `tvchart_remove_indicator`
- `name` — human-facing label, e.g. `"Spread"`
- `type` — machine key, e.g. `"spread"`
- `period`, `color`, `group`
- `sourceSeriesId` — the primary input series id (usually `"main"`)
- `secondarySeriesId` — the secondary compare series id for binary
  indicators (`null` otherwise)
- `secondarySymbol` — the ticker the secondary series holds
  (`"MSFT"`), resolved back from the compare map; `null` when the
  indicator is single-series
- `primarySource`, `secondarySource` — OHLC source selectors per leg
- `isSubplot` — true when the indicator lives in its own pane below
  the main chart

**Returns:** `{"widget_id": "...", "indicators": [...], "chartId": "..."}`

#### tvchart_show_indicators

Open the indicator picker panel UI.  Emits `tvchart:show-indicators`.

### Symbol / interval / view

#### tvchart_symbol_search

Open the symbol search dialog and (optionally) auto-change the main
ticker.  Emits `tvchart:symbol-search`.  When `query` is set the
datafeed search runs with that query and — if `auto_select` (default
`true`) — the exact-ticker match (or the first result otherwise) is
selected when results arrive.  The handler then polls
`tvchart:request-state` until the chart's reported `symbol` matches
the target (up to ~3s) and returns the real post-change state.

| Parameter | Type | Required | Default | Description |
|:---|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | — | |
| `query` | `string` | No | — | Pre-fill the search box and run the search |
| `auto_select` | `boolean` | No | `true` | Auto-pick when results arrive (only applies if `query` is set) |
| `symbol_type` | `string` | No | — | Security class filter — datafeed values such as `equity`, `etf`, `index`, `mutualfund`, `future`, `cryptocurrency`, `currency`.  Narrows the search so e.g. `SPY` finds the ETF rather than `SPYM`.  Case-insensitive. |
| `exchange` | `string` | No | — | Exchange filter — datafeed-provided value.  Case-insensitive. |
| `chart_id` | `string` | No | — | |

Result fields (when `query` + `auto_select`):

- `widget_id`, `event_sent`, `event_type` — standard emit confirmation
- `symbol` — the confirmed main symbol after the change
- `state` — the full `tvchart:request-state` snapshot
- `note` — present only if the change didn't land within the timeout

#### tvchart_compare

Add a ticker as a compare-series overlay on the chart.  Emits
`tvchart:compare`.  When `query` is set the compare panel searches and
— if `auto_add` (default `true`) — commits the matching ticker as a
compare series.  The handler polls chart state until the new ticker
appears in `state.compareSymbols` and returns the confirmed state.
Omit `query` to just open the panel for the user.

| Parameter | Type | Required | Default | Description |
|:---|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | — | |
| `query` | `string` | No | — | Ticker / name to search and auto-add |
| `auto_add` | `boolean` | No | `true` | Auto-commit the matching result when the search responds |
| `symbol_type` | `string` | No | — | Security class filter — datafeed values such as `equity`, `etf`, `index`, `mutualfund`, `future`, `cryptocurrency`, `currency`.  Narrows the search so e.g. `SPY` finds the ETF rather than `SPYM`.  Case-insensitive. |
| `exchange` | `string` | No | — | Exchange filter — datafeed-provided value.  Case-insensitive. |
| `chart_id` | `string` | No | — | |

Result fields (when `query` + `auto_add`):

- `widget_id`, `event_sent`, `event_type` — standard emit confirmation
- `compareSymbols` — the `{seriesId: ticker}` map from state after the
  add (user-facing compares only; indicator-source compares are
  excluded)
- `state` — the full `tvchart:request-state` snapshot
- `note` — present only if the compare didn't land within the timeout

Compare series added via this tool are the *input* for compare-
derivative indicators (`Spread`, `Ratio`, `Sum`, `Product`,
`Correlation`).  After the compare lands, call
`tvchart_add_indicator` to layer the derivative on top.

#### tvchart_change_interval

Change the chart timeframe.  Emits `tvchart:interval-change` and polls
state until the chart reports the new interval.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | |
| `value` | `string` | **Yes** | `1m` … `12M` |
| `chart_id` | `string` | No | |

Result fields:

- `widget_id`, `event_sent`, `event_type` — standard emit confirmation
- `interval` — the confirmed interval after the change
- `state` — the full `tvchart:request-state` snapshot
- `note` — present only if the change didn't land within the timeout

#### tvchart_set_visible_range

Set the chart's visible time range.  Emits `tvchart:time-scale` with
`{visibleRange: {from, to}}`.  Times are epoch seconds.

| Parameter | Type | Required |
|:---|:---|:---|
| `widget_id` | `string` | **Yes** |
| `from_time` | `integer` | **Yes** |
| `to_time` | `integer` | **Yes** |
| `chart_id` | `string` | No |

#### tvchart_fit_content

Fit all bars to the visible area.  Emits `tvchart:time-scale` with
`{fitContent: true}`.

#### tvchart_time_range

Zoom to a preset range.  Emits `tvchart:time-range`.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | |
| `value` | `string` | **Yes** | `1D`, `1W`, `1M`, `3M`, `6M`, `1Y`, `5Y`, `YTD`, … |
| `chart_id` | `string` | No | |

#### tvchart_time_range_picker

Open the date-range picker dialog.  Emits `tvchart:time-range-picker`.

#### tvchart_log_scale

Toggle logarithmic price scale.  Emits `tvchart:log-scale`.

| Parameter | Type | Required |
|:---|:---|:---|
| `widget_id` | `string` | **Yes** |
| `value` | `boolean` | **Yes** |
| `chart_id` | `string` | No |

#### tvchart_auto_scale

Toggle auto-scale on the price axis.  Emits `tvchart:auto-scale`.

| Parameter | Type | Required |
|:---|:---|:---|
| `widget_id` | `string` | **Yes** |
| `value` | `boolean` | **Yes** |
| `chart_id` | `string` | No |

### Chart type

#### tvchart_chart_type

Change the main series chart style.  Emits `tvchart:chart-type-change`.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | |
| `value` | `string` | **Yes** | `Candles`, `Hollow Candles`, `Heikin Ashi`, `Bars`, `Line`, `Area`, `Baseline`, `Histogram` |
| `series_id` | `string` | No | |
| `chart_id` | `string` | No | |

### Drawing tools

#### tvchart_drawing_tool

Activate a drawing mode or toggle drawing-layer state.  Emits one of
`tvchart:tool-cursor`, `tvchart:tool-crosshair`, `tvchart:tool-magnet`,
`tvchart:tool-eraser`, `tvchart:tool-visibility`, `tvchart:tool-lock`.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | |
| `mode` | `string` | **Yes** | `cursor`, `crosshair`, `magnet`, `eraser`, `visibility`, `lock` |
| `chart_id` | `string` | No | |

#### tvchart_undo / tvchart_redo

Undo/redo the last chart action.  Emits `tvchart:undo` / `tvchart:redo`.

### Chart chrome

#### tvchart_show_settings

Open the chart settings modal.  Emits `tvchart:show-settings`.

#### tvchart_toggle_dark_mode

Toggle the chart's dark/light theme.  Emits `tvchart:toggle-dark-mode`.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | |
| `value` | `boolean` | **Yes** | `true` = dark, `false` = light |
| `chart_id` | `string` | No | |

#### tvchart_screenshot

Take a chart screenshot.  Emits `tvchart:screenshot`.

#### tvchart_fullscreen

Toggle chart fullscreen.  Emits `tvchart:fullscreen`.

### Layout and state

#### tvchart_save_layout

Save the current chart layout (indicators + drawings).  Emits `tvchart:save-layout`.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | |
| `name` | `string` | No | Display name for the saved layout |
| `chart_id` | `string` | No | |

#### tvchart_open_layout

Open the layout picker dialog.  Emits `tvchart:open-layout`.

#### tvchart_save_state

Trigger a full state export from every chart in the widget.  The
exported state is delivered back via the `tvchart:layout-response`
event — retrieve it with `get_events`.  Emits `tvchart:save-state`.

#### tvchart_request_state

Synchronously read a single chart's state.  Round-trips
`tvchart:request-state` / `tvchart:state-response` and returns the
decoded state.  This is the authoritative source for what's on the
chart — agents reporting symbol / interval / compares / indicators
must quote values from this tool, never recall or fabricate.

| Parameter | Type | Required | Default | Description |
|:---|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | — | |
| `chart_id` | `string` | No | — | |
| `timeout` | `number` | No | `5.0` | Response wait, seconds |

**Returns:** `{"widget_id": "...", "state": {...}}` where `state`
contains:

- `chartId` — id of the chart pane within the widget
- `theme` — `"dark"` or `"light"`
- `symbol` — active main ticker (empty string if not yet resolved)
- `interval` — active timeframe (e.g. `"1D"`, `"1W"`)
- `chartType` — display style (`"Candles"`, `"Line"`, `"Heikin Ashi"`,
  `"Bars"`, `"Area"`)
- `compareSymbols` — `{seriesId: ticker}` map of **user-facing**
  compare overlays.  Indicator-input compares are NOT in this map.
- `indicatorSourceSymbols` — `{seriesId: ticker}` map of compares
  that drive binary indicators (hidden from the Compare panel).
  Exposed for agents that need to reason about where an indicator's
  secondary data comes from.
- `series` — `{seriesId: {type}}` summary of every series on the
  chart (main + compares + indicator subplots)
- `visibleRange` — `{from, to}` in unix seconds (null if unavailable)
- `visibleLogicalRange` — `{from, to}` in fractional bar indices
- `rawData` — last-known bars for the main series (may be null)
- `drawings` — array of user drawings (trendlines, rectangles, etc.)
- `indicators` — array matching the `tvchart_list_indicators`
  format, including `secondarySeriesId` / `secondarySymbol` for
  compare-derivative indicators

---

### build_div

Build a `Div` component's HTML string. Use `component_id` so the element can be targeted later with `set_content` or `set_style`.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `content` | `string` | **Yes** | Text or HTML content |
| `component_id` | `string` | No | ID attribute — required for `set_content`/`set_style` targeting |
| `style` | `string` | No | Inline CSS |
| `class_name` | `string` | No | CSS class |

**Returns:** `{"html": "<div id=\"counter\" style=\"...\">0</div>"}`

Use the returned `html` in `create_widget`'s `html` parameter.

---

### build_ticker_item

Build a `TickerItem` HTML span for use inside a Marquee. The `data-ticker` attribute lets `update_ticker_item` target it later.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `ticker` | `string` | **Yes** | Unique ID for targeting updates (e.g. `AAPL`, `BTC`) |
| `text` | `string` | No | Display text |
| `html` | `string` | No | HTML content (overrides `text`) |
| `class_name` | `string` | No | CSS classes |
| `style` | `string` | No | Inline CSS |

**Returns:** `{"html": "<span data-ticker=\"AAPL\" ...>...</span>", "ticker": "AAPL", "update_event": "toolbar:marquee-set-item"}`

---

## Widget Manipulation

All manipulation tools require a `widget_id` returned by a prior creation call.
Each tool emits a specific **system event** to the widget's frontend via WebSocket.

### set_content

Update an element's text or HTML by its `component_id`. Emits `pywry:set-content`.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | Target widget |
| `component_id` | `string` | **Yes** | Element ID to update |
| `text` | `string` | No | Plain text (sets `textContent`) |
| `html` | `string` | No | HTML string (sets `innerHTML`, overrides `text`) |

**Emits:** `pywry:set-content` → `{"id": "<component_id>", "text": "..."}` or `{"id": "<component_id>", "html": "..."}`

---

### set_style

Update CSS styles on an element. Emits `pywry:set-style`. Use camelCase property names.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | Target widget |
| `component_id` | `string` | **Yes** | Element ID to update |
| `styles` | `object` | **Yes** | CSS property → value pairs (camelCase keys) |

**Emits:** `pywry:set-style` → `{"id": "<component_id>", "styles": {"fontSize": "24px", "color": "red"}}`

---

### show_toast

Display a toast notification. Emits `pywry:alert`.

| Parameter | Type | Required | Default | Description |
|:---|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | — | Target widget |
| `message` | `string` | **Yes** | — | Notification text |
| `type` | `string` | No | `"info"` | `info`, `success`, `warning`, or `error` |
| `duration` | `integer` | No | `3000` | Auto-dismiss time in milliseconds |

**Emits:** `pywry:alert` → `{"message": "...", "type": "info", "duration": 3000}`

---

### update_theme

Switch a widget's color theme. Plotly charts and AG Grid auto-sync. Emits `pywry:update-theme`.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | Target widget |
| `theme` | `string` | **Yes** | `dark`, `light`, or `system` |

**Emits:** `pywry:update-theme` → `{"theme": "dark"}`

---

### inject_css

Inject CSS rules into a widget. Creates or updates a `<style>` element identified by `style_id`. Emits `pywry:inject-css`.

| Parameter | Type | Required | Default | Description |
|:---|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | — | Target widget |
| `css` | `string` | **Yes** | — | CSS rules to inject |
| `style_id` | `string` | No | `"pywry-injected-style"` | Unique ID for the `<style>` element |

**Emits:** `pywry:inject-css` → `{"css": "...", "id": "pywry-injected-style"}`

---

### remove_css

Remove a previously injected `<style>` element. Emits `pywry:remove-css`.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | Target widget |
| `style_id` | `string` | **Yes** | ID used when injecting |

**Emits:** `pywry:remove-css` → `{"id": "..."}`

---

### navigate

Client-side redirect inside a widget. Emits `pywry:navigate`.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | Target widget |
| `url` | `string` | **Yes** | URL to navigate to |

**Emits:** `pywry:navigate` → `{"url": "https://..."}`

---

### download

Trigger a file download in the browser. Emits `pywry:download`.

| Parameter | Type | Required | Default | Description |
|:---|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | — | Target widget |
| `content` | `string` | **Yes** | — | File content |
| `filename` | `string` | **Yes** | — | Suggested filename |
| `mime_type` | `string` | No | `"application/octet-stream"` | MIME type |

**Emits:** `pywry:download` → `{"content": "...", "filename": "...", "mimeType": "text/csv"}`

---

### update_plotly

Update a Plotly chart in an existing widget.

| Parameter | Type | Required | Default | Description |
|:---|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | — | Target widget |
| `figure_json` | `string` | **Yes** | — | New Plotly figure JSON |
| `layout_only` | `boolean` | No | `false` | If `true`, only update layout (not data traces) |

**Emits:**

- `layout_only=false` → `plotly:update-figure` → `{"data": [...], "layout": {...}}`
- `layout_only=true` → `plotly:update-layout` → `{"layout": {...}}`

---

### update_marquee

Update a Marquee component's content, speed, or play state.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | Target widget |
| `component_id` | `string` | **Yes** | Marquee component ID |
| `text` | `string` | No | New text content |
| `html` | `string` | No | New HTML content |
| `speed` | `number` | No | Animation speed in seconds |
| `paused` | `boolean` | No | Pause/resume |
| `ticker_update` | `object` | No | Update a single ticker item (has `ticker`, `text`, `html`, `styles`, `class_add`, `class_remove`) |

**Emits:**

- With `ticker_update` → `toolbar:marquee-set-item` → ticker update payload
- Without `ticker_update` → `toolbar:marquee-set-content` → `{"id": "...", ...}`

---

### update_ticker_item

Update a single ticker item inside a Marquee by its `ticker` ID. Uses `TickerItem.update_payload()` internally. Updates **all** elements matching the ticker (marquee content is duplicated for seamless scrolling).

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | Target widget |
| `ticker` | `string` | **Yes** | Ticker ID (e.g. `AAPL`, `BTC`) |
| `text` | `string` | No | New text |
| `html` | `string` | No | New HTML |
| `styles` | `object` | No | CSS property → value pairs |
| `class_add` | `string` or `array` | No | CSS class(es) to add |
| `class_remove` | `string` or `array` | No | CSS class(es) to remove |

**Emits:** `toolbar:marquee-set-item` → generated by `TickerItem.update_payload()`

---

## Widget Management

### list_widgets

List all active widgets.

**Parameters:** None

**Returns:**

```json
{"widgets": [{"widget_id": "w-abc123", "path": "/widget/w-abc123"}], "count": 1}
```

---

### get_events

Read queued user-interaction events from a widget. Every toolbar component event is registered via `widget.on()` on the backend, and the MCP server captures each firing into a per-widget buffer. Events that have explicit `callbacks` still fire their backend action **and** get queued here — events without callbacks are only queued.

| Parameter | Type | Required | Default | Description |
|:---|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | — | Target widget |
| `clear` | `boolean` | No | `false` | Clear the event buffer after reading |

**Returns:**

```json
{
  "widget_id": "w-abc123",
  "events": [
    {"event_type": "app:save", "data": {"componentId": "save-btn"}, "label": "app:save"},
    {"event_type": "app:region", "data": {"value": "north", "componentId": "region-select"}, "label": "app:region"}
  ]
}
```

Events include `event_type`, `data` (the component's event payload), and `label`.

---

### destroy_widget

Destroy a widget and clean up all associated resources (event buffers, callbacks, state, inline-mode registrations).

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | Widget to destroy |

---

## send_event

The low-level escape hatch. Send **any** event type to a widget's frontend. This is the same mechanism all the manipulation tools use internally — `set_content` emits `pywry:set-content`, `show_toast` emits `pywry:alert`, etc.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | Target widget |
| `event_type` | `string` | **Yes** | Event name |
| `data` | `object` | **Yes** | Event payload |

All three parameters are **required**.

### AG Grid events

| Event | Payload | Effect |
|:---|:---|:---|
| `grid:update-data` | `{"data": [...rows], "strategy": "set"}` | Replace all rows |
| `grid:update-data` | `{"data": [...rows], "strategy": "append"}` | Append rows |
| `grid:update-data` | `{"data": [...rows], "strategy": "update"}` | Update existing rows |
| `grid:update-columns` | `{"columnDefs": [...]}` | Replace column definitions |
| `grid:update-cell` | `{"rowId": "row-1", "colId": "price", "value": 99.50}` | Update a single cell |
| `grid:request-state` | `{}` | Request grid state (response via `grid:state-response`) |
| `grid:restore-state` | `{"state": {...savedState}}` | Restore a previously saved state |
| `grid:reset-state` | `{"hard": false}` | Soft reset (keeps columns) |
| `grid:reset-state` | `{"hard": true}` | Hard reset (full reset) |

### Plotly events

| Event | Payload | Effect |
|:---|:---|:---|
| `plotly:update-figure` | `{"data": [...], "layout": {...}, "config": {...}}` | Replace data + layout |
| `plotly:update-layout` | `{"layout": {...}}` | Update layout only |
| `plotly:reset-zoom` | `{}` | Reset chart zoom |
| `plotly:request-state` | `{}` | Request state (response via `plotly:state-response`) |
| `plotly:export-data` | `{}` | Export data (response via `plotly:export-response`) |

### Toolbar events

| Event | Payload | Effect |
|:---|:---|:---|
| `toolbar:set-value` | `{"componentId": "my-select", "value": "option2"}` | Set one component's value |
| `toolbar:set-values` | `{"values": {"id1": "v1", "id2": true}}` | Set multiple values at once |
| `toolbar:request-state` | `{}` | Request all values (response via `toolbar:state-response`) |

### DOM events

| Event | Payload | Effect |
|:---|:---|:---|
| `pywry:set-content` | `{"id": "elementId", "text": "..."}` | Set element `textContent` |
| `pywry:set-content` | `{"id": "elementId", "html": "..."}` | Set element `innerHTML` |
| `pywry:set-style` | `{"id": "elementId", "styles": {"color": "red", "fontSize": "18px"}}` | Update CSS styles |
| `pywry:update-theme` | `{"theme": "dark|light|system"}` | Switch theme |
| `pywry:alert` | `{"message": "...", "type": "info|success|warning|error"}` | Show toast |
| `pywry:navigate` | `{"url": "https://..."}` | Client-side redirect |
| `pywry:download` | `{"content": "...", "filename": "...", "mimeType": "text/plain"}` | Trigger file download |

### Marquee events

| Event | Payload | Effect |
|:---|:---|:---|
| `toolbar:marquee-set-item` | `{"ticker": "AAPL", "text": "AAPL $185", "styles": {"color": "green"}}` | Update one ticker item |
| `toolbar:marquee-set-content` | `{"id": "...", "text": "..."}` | Replace marquee content |

---

## Chat

Tools for creating and managing conversational chat widgets with LLM integration, threading, and slash commands.

### create_chat_widget

Create a chat widget with LLM-powered conversation capabilities.

| Parameter | Type | Required | Default | Description |
|:---|:---|:---|:---|:---|
| `title` | `string` | No | `"Chat"` | Window title |
| `height` | `integer` | No | `600` | Window height |
| `system_prompt` | `string` | No | `null` | System prompt for the LLM |
| `model` | `string` | No | `null` | Model name (provider-specific) |
| `temperature` | `number` | No | `null` | Sampling temperature |
| `max_tokens` | `integer` | No | `null` | Maximum response tokens |
| `streaming` | `boolean` | No | `true` | Enable streaming responses |
| `persist` | `boolean` | No | `false` | Persist chat history |
| `provider` | `string` | No | `null` | LLM provider name |
| `show_sidebar` | `boolean` | No | `true` | Show thread sidebar |
| `slash_commands` | `array` | No | `null` | Slash command definitions |
| `toolbars` | `array` | No | `null` | Toolbar component definitions |

**Returns:** `{"widget_id": "...", "path": "...", "created": true}`

---

### chat_send_message

Send a message to a chat widget.

| Parameter | Type | Required | Default | Description |
|:---|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | — | Target chat widget |
| `text` | `string` | **Yes** | — | Message text |
| `thread_id` | `string` | No | `null` | Target thread (uses active thread if omitted) |

---

### chat_stop_generation

Stop the current LLM generation in a chat widget.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | Target chat widget |
| `thread_id` | `string` | No | Target thread (uses active thread if omitted) |

---

### chat_manage_thread

Create, switch, delete, rename, or list threads in a chat widget.

| Parameter | Type | Required | Default | Description |
|:---|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | — | Target chat widget |
| `action` | `string` | **Yes** | — | One of `create`, `switch`, `delete`, `rename`, `list` |
| `thread_id` | `string` | No | `null` | Thread to target (required for `switch`, `delete`, `rename`) |
| `title` | `string` | No | `null` | Thread title (for `create` or `rename`) |

---

### chat_register_command

Register a slash command in a chat widget.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | Target chat widget |
| `name` | `string` | **Yes** | Command name (without leading `/`) |
| `description` | `string` | No | Command description shown in autocomplete |

---

### chat_get_history

Retrieve message history from a chat widget.

| Parameter | Type | Required | Default | Description |
|:---|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | — | Target chat widget |
| `thread_id` | `string` | No | `null` | Thread to get history for (uses active thread if omitted) |
| `limit` | `integer` | No | `50` | Maximum messages to return |
| `before_id` | `string` | No | `null` | Return messages before this message ID (pagination) |

---

### chat_update_settings

Update LLM settings for a chat widget.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | Target chat widget |
| `model` | `string` | No | Model name |
| `temperature` | `number` | No | Sampling temperature |
| `max_tokens` | `integer` | No | Maximum response tokens |
| `system_prompt` | `string` | No | System prompt |
| `streaming` | `boolean` | No | Enable/disable streaming |

---

### chat_set_typing

Set or clear the typing indicator in a chat widget.

| Parameter | Type | Required | Default | Description |
|:---|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | — | Target chat widget |
| `typing` | `boolean` | No | `true` | Whether to show the typing indicator |
| `thread_id` | `string` | No | `null` | Target thread (uses active thread if omitted) |

---

## Resources & Export

### get_component_docs

Retrieve documentation for a toolbar component type, including properties and usage examples.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `component` | `string` | **Yes** | Component type |

**Available:** `button`, `select`, `multiselect`, `toggle`, `checkbox`, `radio`, `tabs`, `text`, `textarea`, `search`, `number`, `date`, `slider`, `range`, `div`, `secret`, `marquee`, `ticker_item`

---

### get_component_source

Get the Python source code for a component class via `inspect.getsource()`.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `component` | `string` | **Yes** | Component type (also accepts `toolbar` and `option`) |

---

### export_widget

Export an active widget as standalone Python code that recreates it without MCP.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | Widget to export |

**Returns:** `{"widget_id": "...", "code": "...", "language": "python", "note": "..."}`

---

### list_resources

List all available MCP resources with their URIs.

**Parameters:** None

**Returns:** Resource URIs for:

- `pywry://component/{name}` — Component documentation
- `pywry://source/{name}` — Component source code
- `pywry://export/{widget_id}` — Widget export
- `pywry://docs/events` — Built-in events reference
- `pywry://docs/quickstart` — Quick start guide

---

## Autonomous Building

LLM-powered tools that use MCP sampling and elicitation to generate complete widget applications from plain-English descriptions. These tools require a sampling-capable client (Claude, etc.).

### plan_widget

Generate a complete `WidgetPlan` from a plain-English description using LLM sampling.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `description` | `string` | **Yes** | Plain-English description of the widget to build |

**Returns:** JSON-serialised `WidgetPlan` including `title`, `description`, `html_content`, `toolbars`, and `callbacks`.

```json title="Example"
{"description": "A stock price ticker with buy/sell buttons and a P&L counter"}
```

---

### build_app

End-to-end pipeline: plan → register → export. Produces a running widget and its Python source in one call.

| Parameter | Type | Required | Default | Description |
|:---|:---|:---|:---|:---|
| `description` | `string` | **Yes** | — | Plain-English app description |
| `open_window` | `boolean` | No | `false` | Open the widget window immediately after creation |

**Returns:**

```json
{
  "widget_id": "abc123",
  "title": "Stock Ticker",
  "python_code": "# Complete runnable script...",
  "files": {"main.py": "...", "requirements.txt": "..."}
}
```

---

### export_project

Package one or more existing widgets into a complete, runnable project directory.

| Parameter | Type | Required | Default | Description |
|:---|:---|:---|:---|:---|
| `widget_ids` | `array[string]` | **Yes** | — | IDs of widgets to include |
| `project_name` | `string` | No | `"pywry_project"` | Output directory / project name |
| `output_dir` | `string` | No | `null` | Write files to this path. Omit to return file contents as JSON. |

**Returns (in-memory):**

```json
{"project_name": "my_app", "files": {"main.py": "...", "requirements.txt": "...", "README.md": "...", "widgets/abc123.py": "..."}}
```

**Returns (written to disk):**

```json
{"project_name": "my_app", "output_dir": "/path/to/my_app", "files_written": ["main.py", "requirements.txt", "README.md", "widgets/abc123.py"]}
```

---

### scaffold_app

Interactive multi-turn app builder. Elicits requirements from the user step-by-step (title, description, display mode, libraries, toolbar placement), then delegates to `plan_widget`.

**Parameters:** None — requirements are gathered interactively via MCP elicitation.

**Returns:** JSON-serialised `WidgetPlan` (same as `plan_widget`) plus a `next_steps` hint.

!!! tip "When to use scaffold_app vs build_app"
    - Use `build_app` when you already have a clear description.
    - Use `scaffold_app` when you want to guide the user through requirements gathering before committing to a design.

---

## Error Handling

All tool calls return JSON. On error the response includes an `error` key:

```json
{"error": "Traceback (most recent call last):\n  ..."}
```

The agent can use the traceback to diagnose and retry.
