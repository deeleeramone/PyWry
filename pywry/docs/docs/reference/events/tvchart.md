# TradingView Events (tvchart:*)

The `tvchart:*` namespace handles all communication between the Python `TVChartStateMixin` and the TradingView Lightweight Charts frontend. This includes chart lifecycle, data flow, the full datafeed protocol, drawing tools, layout persistence, and toolbar actions.

!!! note "Availability"
    TradingView events are active when content includes a `TVChartConfig`. The chart frontend is initialized by `tvchart:create` and destroyed by `tvchart:destroy`.

## Chart Lifecycle

| Event | Direction | Payload | Description |
|-------|-----------|---------|-------------|
| `tvchart:create` | Python→JS | `containerId`, `chartId`, + full chart config | Create/initialize a chart instance in a DOM container |
| `tvchart:destroy` | Python→JS | `chartId` | Destroy a chart instance and clean up resources |

## Data & Series

| Event | Direction | Payload | Description |
|-------|-----------|---------|-------------|
| `tvchart:update` | Python→JS | `{bars, volume?, chartId?, seriesId?, fitContent}` | Replace all data on a series |
| `tvchart:stream` | Python→JS | `{bar, volume?, chartId?, seriesId?}` | Stream a single real-time bar update |
| `tvchart:data-request` | JS→Python | `{chartId, seriesId, symbol, symbolInfo?, interval, resolution, periodParams, compareMode?, session?, timezone?}` | Request bars (interval change, compare, symbol switch) |
| `tvchart:data-response` | Python→JS | `{chartId, seriesId, bars, interval, fitContent}` | Respond with bars; triggers chart recreate on interval change |
| `tvchart:add-series` | Python→JS | `{seriesId, bars, seriesType, seriesOptions, chartId?, symbol?, symbolInfo?, compareMode?, volume?}` | Add an overlay/indicator series |
| `tvchart:remove-series` | JS→Python | `{chartId, seriesId}` | Remove a series (legend/compare panel remove button) |
| `tvchart:add-markers` | Python→JS | `{markers, seriesId?, chartId?}` | Add buy/sell signal markers to a series |
| `tvchart:add-price-line` | Python→JS | `{price, color, lineWidth, title, seriesId?, chartId?}` | Add a horizontal price line |

## Chart Options & State

| Event | Direction | Payload | Description |
|-------|-----------|---------|-------------|
| `tvchart:apply-options` | Python→JS | `{chartOptions?, seriesOptions?, seriesId?, chartId?}` | Apply runtime options to chart or series |
| `tvchart:time-scale` | Python→JS | `{fitContent?, scrollTo?, visibleRange?, chartId?}` | Control time scale (fit, scroll, set visible range) |
| `tvchart:request-state` | Python→JS | `{chartId?, context?}` | Request current chart state export |
| `tvchart:state-response` | JS→Python | `{chartId, ...series info, viewport, context?, error?}` | Exported chart state response |

## User Interaction (JS → Python)

| Event | Direction | Payload | Description |
|-------|-----------|---------|-------------|
| `tvchart:crosshair-move` | JS→Python | `{chartId, time, point, prices}` | Crosshair moved — time + prices at cursor |
| `tvchart:click` | JS→Python | `{chartId, time, point}` | Chart clicked — click coordinates |
| `tvchart:visible-range-change` | JS→Python | `{chartId, from, to}` | Visible logical range changed (pan/zoom) |

## Toolbar Actions

These events are fired by built-in toolbar buttons and handled by the chart frontend JavaScript.

| Event | Direction | Payload | Description |
|-------|-----------|---------|-------------|
| `tvchart:chart-type-change` | JS internal | `{value, chartId?, seriesId?}` | Change chart type (Candles, Line, Area, etc.) |
| `tvchart:interval-change` | JS internal | `{value, chartId?}` | Change data interval/timeframe |
| `tvchart:time-range` | Python→JS | `{value}` | Zoom to a time range preset (1D, 1W, 1M, 1Y) |
| `tvchart:time-range-picker` | Python→JS | — | Open date range picker dialog |
| `tvchart:toggle-dark-mode` | Python→JS | `{value}` (boolean) | Toggle dark/light theme |
| `tvchart:show-settings` | Python→JS | `{chartId?}` | Open chart settings modal |
| `tvchart:show-indicators` | Python→JS | `{chartId?}` | Open indicators panel |
| `tvchart:log-scale` | Python→JS | `{value}` (boolean) | Toggle logarithmic price scale |
| `tvchart:auto-scale` | Python→JS | `{value}` (boolean) | Toggle auto-scale price axis |
| `tvchart:screenshot` | Python→JS | `{chartId?}` | Take and open chart screenshot |
| `tvchart:undo` | Python→JS | — | Undo last chart action |
| `tvchart:redo` | Python→JS | — | Redo last undone action |
| `tvchart:compare` | Python→JS | `{chartId?}` | Open compare symbol panel |
| `tvchart:symbol-search` | Python→JS | `{chartId?}` | Open symbol search dialog |
| `tvchart:fullscreen` | Python→JS | — | Toggle fullscreen on chart wrapper |

## Drawing Tools

| Event | Direction | Payload | Description |
|-------|-----------|---------|-------------|
| `tvchart:tool-cursor` | Python→JS | — | Activate cursor (pointer) mode |
| `tvchart:tool-crosshair` | Python→JS | — | Activate crosshair mode |
| `tvchart:tool-magnet` | Python→JS | — | Toggle magnet mode |
| `tvchart:tool-eraser` | Python→JS | — | Remove all drawings |
| `tvchart:tool-visibility` | Python→JS | — | Toggle drawing layer visibility |
| `tvchart:tool-lock` | Python→JS | — | Toggle drawing interaction lock |
| `tvchart:drawing-added` | JS→Python | `{chartId, drawing}` | A drawing was added to the chart |
| `tvchart:drawing-deleted` | JS→Python | `{chartId, index}` | A drawing was deleted from the chart |

## Layout Persistence

| Event | Direction | Payload | Description |
|-------|-----------|---------|-------------|
| `tvchart:save-state` | Python→JS | — | Request full state export from all charts |
| `tvchart:save-layout` | Python→JS | `{chartId?, name?}` | Save current layout (annotations + indicators) |
| `tvchart:layout-response` | JS→Python | layout object (indicators, drawings, settings) | Exported layout data |
| `tvchart:open-layout` | Python→JS | `{chartId?}` | Open layout picker dialog |
| `tvchart:open-layout-request` | JS→Python | `{}` | Notification that the open-layout dialog was launched |

## Chart Storage (Server-Side Persistence)

| Event | Direction | Payload | Description |
|-------|-----------|---------|-------------|
| `tvchart:storage-set` | JS→Python | `{chartId, key, value}` | Persist a key-value pair |
| `tvchart:storage-remove` | JS→Python | `{chartId, key}` | Remove a persisted key |

## Datafeed Protocol

The datafeed protocol implements a request/response pattern for TradingView's data contract. Each request from JS includes a `requestId` that must be echoed in the response.

### Configuration (onReady)

| Event | Direction | Payload | Description |
|-------|-----------|---------|-------------|
| `tvchart:datafeed-config-request` | JS→Python | `{chartId, requestId}` | Request datafeed configuration |
| `tvchart:datafeed-config-response` | Python→JS | `{requestId, config, chartId?, error?}` | Supported resolutions, exchanges, etc. |

### Symbol Search

| Event | Direction | Payload | Description |
|-------|-----------|---------|-------------|
| `tvchart:datafeed-search-request` | JS→Python | `{chartId, requestId, query, exchange, symbolType, limit}` | Search for symbols |
| `tvchart:datafeed-search-response` | Python→JS | `{requestId, items, chartId?, query?, error?}` | Search results |

### Symbol Resolve

| Event | Direction | Payload | Description |
|-------|-----------|---------|-------------|
| `tvchart:datafeed-resolve-request` | JS→Python | `{chartId, requestId, symbol}` | Resolve full symbol metadata |
| `tvchart:datafeed-resolve-response` | Python→JS | `{requestId, symbolInfo, chartId?, error?}` | Resolved symbol info |

### Historical Bars

| Event | Direction | Payload | Description |
|-------|-----------|---------|-------------|
| `tvchart:datafeed-history-request` | JS→Python | `{chartId, requestId, symbol, resolution, from, to, firstDataRequest, countBack?}` | Request historical bars |
| `tvchart:datafeed-history-response` | Python→JS | `{requestId, bars, status, chartId?, noData?, nextTime?, error?}` | Historical bars response |

### Real-Time Subscriptions

| Event | Direction | Payload | Description |
|-------|-----------|---------|-------------|
| `tvchart:datafeed-subscribe` | JS→Python | `{chartId, listenerGuid, symbol, resolution}` | Subscribe to real-time bar updates |
| `tvchart:datafeed-unsubscribe` | JS→Python | `{listenerGuid, chartId?}` | Unsubscribe from real-time updates |
| `tvchart:datafeed-bar-update` | Python→JS | `{listenerGuid, bar, chartId?}` | Push a real-time bar to a subscriber |
| `tvchart:datafeed-reset-cache` | Python→JS | `{listenerGuid, chartId?}` | Signal subscriber to reset cached data |

### Marks

| Event | Direction | Payload | Description |
|-------|-----------|---------|-------------|
| `tvchart:datafeed-marks-request` | JS→Python | `{chartId, requestId, symbol, from, to, resolution}` | Request chart marks |
| `tvchart:datafeed-marks-response` | Python→JS | `{requestId, marks, chartId?, error?}` | Return marks |
| `tvchart:datafeed-timescale-marks-request` | JS→Python | `{chartId, requestId, symbol, from, to, resolution}` | Request timescale marks |
| `tvchart:datafeed-timescale-marks-response` | Python→JS | `{requestId, marks, chartId?, error?}` | Return timescale marks |

### Server Time

| Event | Direction | Payload | Description |
|-------|-----------|---------|-------------|
| `tvchart:datafeed-server-time-request` | JS→Python | `{chartId, requestId}` | Request server time |
| `tvchart:datafeed-server-time-response` | Python→JS | `{requestId, time, chartId?, error?}` | Server time (UNIX seconds) |
