# TradingView Charts

PyWry provides a full TradingView Lightweight Charts integration — show OHLCV candlestick charts with built-in toolbars, drawing tools, indicators, theming, layout persistence, and an optional datafeed protocol for dynamic symbol search and real-time streaming.

For the complete configuration API, see the [TVChartConfig reference](tvchart-config.md). For all events and payloads, see the [TradingView events reference](../../reference/events/tvchart.md).

## Basic Usage

Pass OHLCV data (DataFrame or list of dicts) to `show_tvchart()`:

```python
import pandas as pd
from pywry import PyWry

app = PyWry()

df = pd.DataFrame({
    "date": pd.date_range("2024-01-01", periods=100),
    "open": [100 + i * 0.5 for i in range(100)],
    "high": [102 + i * 0.5 for i in range(100)],
    "low": [99 + i * 0.5 for i in range(100)],
    "close": [101 + i * 0.5 for i in range(100)],
    "volume": [1000 + i * 10 for i in range(100)],
})

handle = app.show_tvchart(df, title="My Chart")
```

Column names are auto-detected — any of `date`/`time`/`timestamp` for time, and standard `open`/`high`/`low`/`close`/`volume` names work.

## Chart & Series Options

Customize chart appearance with `chart_options` and `series_options`:

```python
handle = app.show_tvchart(
    df,
    chart_options={
        "layout": {"background": {"color": "#1a1a2e"}},
        "crosshair": {"mode": 0},  # CrosshairMode.NORMAL
        "timeScale": {"timeVisible": True},
    },
    series_options={
        "upColor": "#26a69a",
        "downColor": "#ef5350",
        "wickUpColor": "#26a69a",
        "wickDownColor": "#ef5350",
    },
)
```

Or use the Pydantic models for type-safe configuration:

```python
from pywry.tvchart import TVChartConfig, CrosshairConfig, CrosshairMode

config = TVChartConfig(
    crosshair=CrosshairConfig(mode=CrosshairMode.NORMAL),
)

handle = app.show_tvchart(
    df,
    chart_options=config.to_chart_options(),
    series_options=config.to_series_options(),
)
```

## Events

Listen for chart interactions:

```python
def on_click(data):
    print(f"Clicked at time={data['time']}")

def on_crosshair(data):
    print(f"Crosshair at {data['prices']}")

handle = app.show_tvchart(
    df,
    callbacks={
        "tvchart:click": on_click,
        "tvchart:crosshair-move": on_crosshair,
    },
)
```

## Real-Time Updates

Stream bar updates to a live chart:

```python
handle = app.show_tvchart(df)

# Replace all data
handle.update_series(new_df)

# Stream a single bar tick
handle.update_bar({
    "time": 1704153600,
    "open": 150.0,
    "high": 152.5,
    "low": 149.0,
    "close": 151.5,
    "volume": 5000,
})
```

## Indicators

Add overlay indicator series:

```python
# Add a simple moving average
sma_data = [{"time": bar["time"], "value": bar["close"]} for bar in bars]

handle.add_indicator(
    sma_data,
    series_id="sma-20",
    series_type="Line",
    series_options={"color": "#2196F3", "lineWidth": 2},
)

# Remove it later
handle.remove_indicator("sma-20")
```

## Markers & Price Lines

```python
# Add buy/sell markers
handle.add_marker([
    {"time": 1704153600, "position": "belowBar", "color": "#26a69a",
     "shape": "arrowUp", "text": "BUY"},
    {"time": 1704240000, "position": "aboveBar", "color": "#ef5350",
     "shape": "arrowDown", "text": "SELL"},
])

# Add a horizontal price line
handle.add_price_line(150.0, color="#FF9800", title="Target")
```

## Datafeed Protocol

For dynamic symbol search, resolution switching, and server-driven data loading, use the datafeed protocol. This replaces static data with a request/response flow where the frontend asks Python for data.

### Custom DatafeedProvider

Implement the `DatafeedProvider` ABC to connect any data source:

```python
from pywry.tvchart.datafeed import DatafeedProvider

class MyDatafeed(DatafeedProvider):
    async def get_config(self):
        return {
            "supported_resolutions": ["1", "5", "60", "D"],
            "exchanges": [{"value": "", "name": "All", "desc": ""}],
        }

    async def search_symbols(self, query, symbol_type="", exchange="", limit=30):
        # Return list of {symbol, full_name, description, exchange, type}
        return [{"symbol": "AAPL", "full_name": "Apple Inc",
                 "description": "Apple Inc", "exchange": "NASDAQ", "type": "stock"}]

    async def resolve_symbol(self, symbol):
        return {
            "name": symbol,
            "full_name": symbol,
            "description": f"{symbol} stock",
            "type": "stock",
            "session": "0930-1600",
            "exchange": "NASDAQ",
            "timezone": "America/New_York",
            "format": "price",
            "pricescale": 100,
            "minmov": 1,
            "has_intraday": True,
            "supported_resolutions": ["1", "5", "60", "D"],
        }

    async def get_bars(self, symbol, resolution, from_ts, to_ts, countback=None):
        bars = await fetch_bars_from_your_api(symbol, resolution, from_ts, to_ts)
        return {"bars": bars, "status": "ok", "no_data": len(bars) == 0}

feed = MyDatafeed()
handle = app.show_tvchart(provider=feed, symbol="AAPL", resolution="D")
```

The `DatafeedProvider` has optional methods for marks, timescale marks, server time, and real-time subscriptions. Override only what your data source supports and set the corresponding feature-flag properties. See the [DatafeedProvider API reference](tvchart-datafeed.md).

### UDF Adapter

For servers that implement the [TradingView UDF protocol](https://www.tradingview.com/charting-library-docs/latest/connecting_data/UDF/), use `UDFAdapter`:

```python
from pywry.tvchart.udf import UDFAdapter

udf = UDFAdapter(
    "https://demo-feed-data.tradingview.com",
    poll_interval=60,  # poll /history every 60s for real-time updates
)
udf.connect(app, symbol="AAPL", resolution="D")
```

`UDFAdapter` auto-discovers server capabilities via `/config` and wires all datafeed events automatically. See the [UDFAdapter API reference](tvchart-udf.md).

## Toolbars

Charts include built-in toolbars for interval selection, chart type, drawing tools, indicators, and more. You can also add custom toolbars:

```python
from pywry.toolbar import Toolbar, Button, Select, Option

custom_toolbar = Toolbar(
    id="chart-controls",
    position="top",
    items=[
        Select(
            id="symbol-select",
            label="Symbol",
            event="app:symbol-change",
            options=[
                Option(label="AAPL", value="AAPL"),
                Option(label="GOOGL", value="GOOGL"),
                Option(label="MSFT", value="MSFT"),
            ],
        ),
        Button(id="refresh-btn", label="↻ Refresh", event="app:refresh"),
    ],
)

handle = app.show_tvchart(df, toolbars=[custom_toolbar])
```

## Layout Persistence

Charts support saving and loading layouts (drawings, indicators, settings). The built-in save/load toolbar buttons wire to a `ChartStore` backend:

- **MemoryChartStore** — in-memory (default, lost on restart)
- **FileChartStore** — JSON files on disk
- **RedisChartStore** — Redis for multi-worker deploy mode

```python
handle = app.show_tvchart(
    df,
    storage={"backend": "file", "path": "./chart_layouts"},
)
```

## Drawing Tools

Built-in drawing tools are available in the toolbar:

- **Trend Line** — click two points to draw a line
- **Horizontal Line** — click to place a horizontal level
- **Vertical Line** — click to place a vertical marker
- **Rectangle** — click two corners
- **Parallel Channel** — three-point channel

Drawing events (`tvchart:drawing-added`, `tvchart:drawing-deleted`) are emitted to Python for persistence or analysis.

## Theming

Charts automatically follow the PyWry theme (dark/light). Toggle at runtime:

```python
handle.emit("tvchart:toggle-dark-mode", {"value": True})
```

Or set it at creation:

```python
from pywry import ThemeMode

app = PyWry(theme=ThemeMode.DARK)
handle = app.show_tvchart(df)
```

## API Reference

| Module | Description |
|--------|-------------|
| [TVChartConfig](tvchart-config.md) | Configuration models (enums, chart options, templates, themes) |
| [Models](tvchart-models.md) | Datafeed request/response protocol models |
| [DatafeedProvider](tvchart-datafeed.md) | Abstract base class for data sources |
| [UDFAdapter](tvchart-udf.md) | UDF HTTP server adapter |
| [TVChartStateMixin](tvchart-mixin.md) | Python ↔ JS bridge methods |
| [Events](../../reference/events/tvchart.md) | All 52 tvchart:* events |
