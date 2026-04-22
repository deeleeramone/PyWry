---
description: Drive a live TradingView Lightweight Charts widget end-to-end via PyWry MCP tools — symbol, interval, indicators, markers, price lines, layouts, state.
---

# TradingView Chart — Agent Reference

> **Use this when an agent needs to read or mutate a live `tvchart`
> widget.**  Every action is an MCP tool call on the PyWry FastMCP
> server — there are no local helpers, no side channels, no custom
> tools.  Pick the typed tool that matches the user's intent, pass the
> required arguments, and quote the tool's return values in your
> reply.

## Every tool takes `widget_id`

`widget_id` identifies which chart to operate on.  On a single-chart
server the framework auto-resolves it from the registry; on a
multi-chart server you must pass it explicitly.  Read the value from
the user's `@<name>` attachment (the chat prepends `--- Attached:
<name> ---\nwidget_id: <id>`) or call `list_widgets()` to enumerate.

## Reading chart state — always via `tvchart_request_state`

Never report symbol / interval / indicators / bars / last close from
memory.  Call the tool, quote the return.

```
tvchart_request_state(widget_id)
  → {
      "widget_id": "chart",
      "state": {
        "symbol": "AAPL",
        "interval": "1D",
        "series": [{ "seriesId": "main", "bars": [...], ... }],
        "indicators": [...],
        "visibleRange": { "from": ..., "to": ... },
        "chartType": "Candles",
        ...
      }
    }
```

When the user asks "what's on the chart", "what's the current price",
"what indicators are applied", call this and quote from `state`.

## Mutating tools — all confirm the change

Every mutation returns the real post-change state.  The model never has
to guess whether the change took effect.  If the mutation didn't land
within the settle window, the tool includes a `note` field — relay
it to the user.

### Symbol change

```
tvchart_symbol_search(widget_id, query, auto_select=True,
                      symbol_type=None, exchange=None)
  → { "widget_id": "chart", "symbol": "MSFT", "state": {...} }
```

Use this to switch the ticker.  `auto_select=True` commits the
selection; `auto_select=False` just opens the search dialog for the
user.  The tool polls chart state until the symbol actually changes
to the target (up to ~6s) so the return reflects reality.

Pass `symbol_type` to narrow the datafeed search to a specific
security class — values come from the datafeed, typically `equity`,
`etf`, `index`, `mutualfund`, `future`, `cryptocurrency`, `currency`.
Use it whenever the user's query is ambiguous: `SPY` with
`symbol_type="etf"` resolves to the SPDR S&P 500 ETF instead of
picking a near-prefix equity like `SPYM`.  `exchange` narrows to a
specific venue the same way.  Both are case-insensitive; unknown
values are silently dropped rather than erroring.

### Interval / timeframe

```
tvchart_change_interval(widget_id, value)
  → { "widget_id": "chart", "interval": "1W", "state": {...} }
```

Valid values: `1m 3m 5m 15m 30m 45m 1h 2h 3h 4h 1d 1w 1M 3M 6M 12M`.
Tool confirms the change via state polling.

### Indicators

```
tvchart_add_indicator(widget_id, name, period=..., color=..., ...)
tvchart_remove_indicator(widget_id, series_id)
tvchart_list_indicators(widget_id)
```

Supported names: `SMA`, `EMA`, `WMA`, `RSI`, `ATR`, `VWAP`,
`Bollinger Bands`, plus the rest of the built-in library.  `period`
defaults to a sensible value per indicator; override when the user
asks.

#### Compare-derivative indicators

`Spread`, `Ratio`, `Sum`, `Product`, `Correlation` require a
**secondary series** — a second ticker to spread/ratio/etc. against
the main series.  The flow is two steps:

1. Call `tvchart_compare(widget_id, query="<ticker>")` to add the
   secondary ticker as a compare series and confirm it landed in
   `state.compareSymbols`.
2. Call `tvchart_add_indicator(widget_id, name="Spread", ...)`.  The
   chart picks up the most recent compare series as the secondary
   automatically; pass `source` / `method` / `multiplier` to tune.

State reporting for these indicators:

- `state.indicators[i].type` is `"spread"` / `"ratio"` / etc.
- `state.indicators[i].secondarySeriesId` — the compare seriesId.
- `state.indicators[i].secondarySymbol` — the ticker it resolves to
  (this is what the user actually cares about when you describe the
  indicator).
- `state.indicatorSourceSymbols` — the compare-series map restricted
  to indicator inputs; these are NOT user-facing compares (they're
  hidden from the Compare panel).  Don't conflate with
  `state.compareSymbols` when listing "what's compared on the chart".

If the user asks "what's on the chart" for a chart with a Spread
against MSFT, quote it as `Spread(AAPL, MSFT)` using the indicator's
`secondarySymbol`, not the raw seriesId.

### Chart type / rendering

```
tvchart_chart_type(widget_id, value)
  # value ∈ { "Candles", "Line", "Heikin Ashi", "Bars", "Area" }

tvchart_log_scale(widget_id, value)    # true / false
tvchart_auto_scale(widget_id, value)
```

### Visible range / zoom

```
tvchart_set_visible_range(widget_id, from_time, to_time)
  # times are Unix seconds

tvchart_fit_content(widget_id)
tvchart_time_range(widget_id, value)    # "1D", "5D", "1M", "6M", "YTD", "1Y", "5Y", "All"
tvchart_time_range_picker(widget_id)    # opens custom picker UI
```

### Markers and price lines

```
tvchart_add_markers(widget_id, markers)
  # markers = [{ time, position, color, shape, text }, ...]
  # position: "aboveBar" | "belowBar" | "inBar"
  # shape: "arrowUp" | "arrowDown" | "circle" | "square"

tvchart_add_price_line(widget_id, price, title="", color="#2196F3", line_width=1)
```

Use markers for signals / events on specific bars.  Use price lines
for support / resistance / targets (horizontal lines across the whole
chart).

### Drawing tools

```
tvchart_drawing_tool(widget_id, tool)
  # tool ∈ { "trendline", "horizontal", "rectangle", "brush", "eraser", "cursor", ... }
```

### History and layout

```
tvchart_undo(widget_id)
tvchart_redo(widget_id)
tvchart_save_layout(widget_id, name)
tvchart_open_layout(widget_id, name)
tvchart_save_state(widget_id)
```

### Misc UI

```
tvchart_show_indicators(widget_id)    # open indicator panel
tvchart_show_settings(widget_id)
tvchart_screenshot(widget_id)
tvchart_fullscreen(widget_id)
tvchart_toggle_dark_mode(widget_id)
```

### Adding a compare overlay

```
tvchart_compare(widget_id, query, auto_add=True,
                symbol_type=None, exchange=None)
  → { "widget_id": "chart", "compareSymbols": { "compare-spy": "SPY" },
      "state": {...} }
```

`query` is the ticker to add.  Pass `symbol_type` to disambiguate:
`SPY` without it may resolve to `SPYM` (a near-prefix equity);
`symbol_type="etf"` routes it to the SPDR ETF.  `exchange` narrows
to a specific venue.  Both are case-insensitive and silently
dropped when the datafeed doesn't know the value.

The tool polls `state.compareSymbols` for up to ~10s (compares
require a full datafeed round-trip) before reporting a `note`.
Calling `tvchart_compare(widget_id)` with no `query` just opens
the dialog for the user — no state confirmation.

## Series and bar updates (non-datafeed mode)

Use these only when the chart is NOT in datafeed mode (the datafeed
manages its own streams).  In datafeed mode, new symbol / interval
data is fetched automatically via `tvchart:data-request` — don't try
to push bars yourself.

```
tvchart_update_series(widget_id, series_id, bars, volume=None)
tvchart_update_bar(widget_id, series_id, bar)       # live tick
tvchart_add_series(widget_id, series_id, bars, series_type="Line", series_options={...})
tvchart_remove_series(widget_id, series_id)
tvchart_apply_options(widget_id, chart_options=..., series_id=..., series_options=...)
```

## Last-resort escape hatch

If no typed tool exists for a specific event, use:

```
send_event(widget_id, event_type, data)
```

Event types are namespaced `tvchart:<event-name>`.  This is a raw
passthrough — prefer the typed tools above in every other case.

## Don'ts

- Do NOT fabricate chart state, bars, or timestamps.  Call the tool.
- Do NOT emit "Updated Chart State" or "Chart Update Response"
  pseudo-JSON blocks in replies — only quote real tool returns.
- Do NOT guess a `widget_id` — read it from the attachment or call
  `list_widgets()`.
- Do NOT call `send_event` when a typed tool already exists for the
  event.
