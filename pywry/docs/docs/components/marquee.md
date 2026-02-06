# Marquee

A scrolling ticker display for continuous information streams like stock prices or news.

## Basic Usage

```python
from pywry import Marquee, TickerItem

ticker = Marquee(
    items=[
        TickerItem(symbol="AAPL", value="$185.32", change="+1.2%"),
        TickerItem(symbol="GOOGL", value="$141.80", change="-0.5%"),
        TickerItem(symbol="MSFT", value="$378.91", change="+0.8%"),
    ],
)
```

## Speed Control

```python
Marquee(
    items=[...],
    speed=50,  # Pixels per second (default: 50)
)
```

## Direction

```python
# Right to left (default)
Marquee(items=[...], direction="left")

# Left to right
Marquee(items=[...], direction="right")
```

## Common Patterns

### Stock Ticker

```python
stocks = [
    {"symbol": "AAPL", "price": 185.32, "change": 1.2},
    {"symbol": "GOOGL", "price": 141.80, "change": -0.5},
    {"symbol": "MSFT", "price": 378.91, "change": 0.8},
    {"symbol": "AMZN", "price": 178.25, "change": 2.1},
]

ticker = Marquee(
    component_id="stock-ticker",
    items=[
        TickerItem(
            symbol=s["symbol"],
            value=f"${s['price']:.2f}",
            change=f"{'+' if s['change'] > 0 else ''}{s['change']:.1f}%",
        )
        for s in stocks
    ],
)

toolbar = Toolbar(
    position="header",
    items=[ticker],
)
```

### Updating Ticker Dynamically

```python
def update_ticker_prices(widget, new_prices):
    """Update ticker with new price data."""
    widget.emit("toolbar:marquee-set-content", {
        "componentId": "stock-ticker",
        "items": [
            {
                "symbol": p["symbol"],
                "value": f"${p['price']:.2f}",
                "change": f"{'+' if p['change'] > 0 else ''}{p['change']:.1f}%",
            }
            for p in new_prices
        ]
    })
```

### News Ticker

```python
headlines = [
    "Breaking: Major tech earnings beat expectations",
    "Fed signals steady rates through Q2",
    "New AI regulations proposed in Congress",
]

news_ticker = Marquee(
    items=[
        TickerItem(symbol="📰", value=headline, change="")
        for headline in headlines
    ],
    speed=30,  # Slower for readability
)
```

### Metrics Dashboard

```python
metrics = Marquee(
    items=[
        TickerItem(symbol="Users", value="12,453", change="+5%"),
        TickerItem(symbol="Revenue", value="$1.2M", change="+12%"),
        TickerItem(symbol="Orders", value="834", change="+8%"),
        TickerItem(symbol="Uptime", value="99.9%", change=""),
    ],
)
```

## Styling

Customize appearance with CSS:

```css
.pywry-marquee {
    background: linear-gradient(to right, #1a1a2e, #16213e);
    padding: 8px 0;
}

.pywry-ticker-item {
    margin: 0 24px;
}

.pywry-ticker-symbol {
    font-weight: bold;
    color: #fff;
}

.pywry-ticker-change.positive {
    color: #00ff88;
}

.pywry-ticker-change.negative {
    color: #ff4444;
}
```

## API Reference

For complete parameter documentation, see the [Marquee API Reference](../reference/components/marquee.md).
