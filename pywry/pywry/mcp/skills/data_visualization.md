# Data Visualization

> Best practices for creating charts, tables, and live data displays.

## Plotly Charts

### Creating a Chart
```python
import plotly.express as px

# Create figure
df = pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]})
fig = px.line(df, x="x", y="y", title="My Chart")

# Show as widget
show_plotly(figure_json=fig.to_json(), title="Line Chart")
```

### Updating a Chart
```python
# Full update
new_fig = px.bar(df, x="category", y="value")
update_plotly(widget_id, figure_json=new_fig.to_json())

# Layout-only update (faster - doesn't re-render data)
layout_update = {"title": {"text": "Updated Title"}}
update_plotly(widget_id, figure_json=json.dumps({"layout": layout_update}), layout_only=True)
```

### Theme Consistency
```python
# Use Plotly templates that match widget theme

# For dark theme
fig.update_layout(template="plotly_dark")

# For light theme
fig.update_layout(template="plotly_white")

# Or detect and set dynamically
# (check widget theme, set template accordingly)
```

### Chart Sizing
```python
# Let chart fill container
fig.update_layout(
    autosize=True,
    margin=dict(l=40, r=40, t=50, b=40),
)

# Or set explicit size
fig.update_layout(
    width=600,
    height=400,
)
```

## AG Grid Tables

### Creating a Table
```python
import json

# Data as list of dicts
data = [
    {"name": "Alice", "age": 30, "city": "NYC"},
    {"name": "Bob", "age": 25, "city": "LA"},
]

# Show as AG Grid widget
show_dataframe(data_json=json.dumps(data), title="Users")
```

### Theme Consistency
```python
# AG Grid themes
# - ag-theme-quartz-dark (dark mode)
# - ag-theme-quartz (light mode)
# Widget auto-applies based on current theme
```

### Large Datasets
```python
# AG Grid handles large datasets efficiently via virtualization
# Pagination is built-in

data = [{"id": i, "value": random.random()} for i in range(10000)]
show_dataframe(data_json=json.dumps(data), title="Large Dataset")
# Grid virtualizes - only visible rows are rendered
```

## Marquee for Live Data

### Building Ticker Items
```python
# Build individual ticker items
items = [
    build_ticker_item(ticker="AAPL", text="AAPL $185.50"),
    build_ticker_item(ticker="GOOGL", text="GOOGL $142.20"),
    build_ticker_item(ticker="MSFT", text="MSFT $378.90"),
]
```

### Creating Marquee
```python
create_widget(
    html="<div id='content'>Dashboard Content</div>",
    toolbars=[{
        "position": "top",
        "items": [{
            "type": "marquee",
            "ticker_items": [
                {"ticker": "AAPL", "text": "AAPL $185.50"},
                {"ticker": "GOOGL", "text": "GOOGL $142.20"},
            ],
            "speed": 50,  # pixels per second
            "direction": "left",  # left or right
        }]
    }]
)
```

### Updating Individual Tickers
```python
# Update one ticker without affecting others
update_ticker_item(
    widget_id,
    ticker="AAPL",
    text="AAPL $186.25 ▲",
    styles={"color": "#22c55e"}  # Green for up
)

update_ticker_item(
    widget_id,
    ticker="GOOGL",
    text="GOOGL $141.50 ▼",
    styles={"color": "#ef4444"}  # Red for down
)
```

### Updating All Tickers
```python
# Replace all ticker items
update_marquee(widget_id, ticker_items=[
    {"ticker": "AAPL", "text": "AAPL $186.25", "styles": {"color": "#22c55e"}},
    {"ticker": "GOOGL", "text": "GOOGL $141.50", "styles": {"color": "#ef4444"}},
    {"ticker": "NEW", "text": "NEW $100.00"},  # Add new ticker
])
```

## Live Data Patterns

### Pattern 1: Polling
```python
import time

widget = create_widget(html=initial_html, toolbars=[...])

while True:
    # Fetch new data
    data = fetch_latest_data()

    # Update chart
    fig = create_chart(data)
    update_plotly(widget.id, figure_json=fig.to_json())

    # Update tickers
    for ticker, price in data["prices"].items():
        update_ticker_item(widget.id, ticker=ticker, text=f"{ticker} ${price:.2f}")

    time.sleep(5)  # Poll every 5 seconds
```

### Pattern 2: Event-Driven
```python
widget = create_widget(html=initial_html, toolbars=[
    {
        "position": "top",
        "items": [
            {"type": "button", "label": "Refresh", "event": "refresh"},
            {"type": "select", "label": "Timeframe", "event": "timeframe",
             "options": [
                 {"label": "1D", "value": "1d"},
                 {"label": "1W", "value": "1w"},
                 {"label": "1M", "value": "1m"},
             ]},
        ]
    }
])

while True:
    events = get_events(widget.id, clear=True)
    for e in events:
        if e["event_type"] == "refresh":
            data = fetch_data()
            update_chart(widget.id, data)
        elif e["event_type"] == "timeframe":
            timeframe = e["data"]["value"]
            data = fetch_data(timeframe=timeframe)
            update_chart(widget.id, data)
    time.sleep(0.1)
```

### Pattern 3: Streaming via Marquee
```python
# Marquee is ideal for streaming price data
# - Continuous scrolling
- Individual ticker updates
- Visual indication of changes

def stream_prices():
    while True:
        for ticker, price, change in get_price_updates():
            color = "#22c55e" if change >= 0 else "#ef4444"
            arrow = "▲" if change >= 0 else "▼"
            update_ticker_item(
                widget_id,
                ticker=ticker,
                text=f"{ticker} ${price:.2f} {arrow}",
                styles={"color": color}
            )
        time.sleep(0.1)  # High-frequency updates OK for ticker
```

## Dashboard Layout

### Multi-Chart Layout
```python
content = Div(
    content="""
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; padding: 16px;">
            <div id="chart1" style="height: 300px;"></div>
            <div id="chart2" style="height: 300px;"></div>
            <div id="chart3" style="height: 300px;"></div>
            <div id="chart4" style="height: 300px;"></div>
        </div>
    """,
    component_id="dashboard",
)

widget = create_widget(html=content.build_html(), height=700)

# Embed Plotly charts in each div
# (Use Plotly.js directly for embedded charts, or use separate widgets)
```

### Chart + Table Layout
```python
content = Div(
    content="""
        <div style="display: flex; height: 100%; padding: 16px; gap: 16px;">
            <div id="chart" style="flex: 2;"></div>
            <div id="table" style="flex: 1; overflow: auto;"></div>
        </div>
    """,
    component_id="layout",
)
```

## Performance Tips

### For Charts
- Use `layout_only=True` when only changing titles, axes, annotations
- Reduce data points for line charts (downsample)
- Use WebGL for large scatter plots (`fig = px.scatter(..., render_mode='webgl')`)

### For Tables
- AG Grid virtualizes automatically - send all data
- Use server-side pagination for very large datasets (100k+ rows)
- Avoid complex cell renderers for large tables

### For Marquee
- Keep ticker count reasonable (10-20 items)
- Update only changed tickers, not all
- Use reasonable update frequency (not faster than visual perception ~100ms)
