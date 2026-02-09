# Marquee

A scrolling ticker display for continuous information streams like stock prices or news.

<div class="component-preview col">
  <div class="pywry-marquee pywry-marquee-left pywry-marquee-scroll pywry-marquee-horizontal pywry-marquee-pause" style="--pywry-marquee-speed: 20s; --pywry-marquee-gap: 50px">
    <div class="pywry-marquee-track">
      <span class="pywry-marquee-content">
        <span class="pywry-ticker-item stock-up" data-ticker="AAPL">AAPL $185.32 +1.2%</span>
        <span class="pywry-ticker-item stock-down" data-ticker="GOOGL">GOOGL $141.80 -0.5%</span>
        <span class="pywry-ticker-item stock-up" data-ticker="MSFT">MSFT $378.91 +0.8%</span>
        <span class="pywry-ticker-item stock-up" data-ticker="AMZN">AMZN $178.25 +2.1%</span>
      </span>
      <span class="pywry-marquee-content" aria-hidden="true">
        <span class="pywry-ticker-item stock-up" data-ticker="AAPL">AAPL $185.32 +1.2%</span>
        <span class="pywry-ticker-item stock-down" data-ticker="GOOGL">GOOGL $141.80 -0.5%</span>
        <span class="pywry-ticker-item stock-up" data-ticker="MSFT">MSFT $378.91 +0.8%</span>
        <span class="pywry-ticker-item stock-up" data-ticker="AMZN">AMZN $178.25 +2.1%</span>
      </span>
    </div>
  </div>
</div>

## Basic Usage

```python
from pywry import Marquee, TickerItem

items = [
    TickerItem(ticker="AAPL", text="AAPL $185.32 +1.2%", class_name="stock-up"),
    TickerItem(ticker="GOOGL", text="GOOGL $141.80 -0.5%", class_name="stock-down"),
    TickerItem(ticker="MSFT", text="MSFT $378.91 +0.8%", class_name="stock-up"),
]

ticker = Marquee(
    text=" ".join(item.build_html() for item in items),
)
```

## Speed Control

```python
Marquee(
    items=[...],
    speed=20,  # Seconds per scroll cycle — lower is faster (default: 15.0)
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

items = [
    TickerItem(
        ticker=s["symbol"],
        text=f"{s['symbol']} ${s['price']:.2f} {'+'if s['change'] > 0 else ''}{s['change']:.1f}%",
        class_name="stock-up" if s["change"] > 0 else "stock-down",
    )
    for s in stocks
]

ticker = Marquee(
    component_id="stock-ticker",
    text=" ".join(item.build_html() for item in items),
)

toolbar = Toolbar(
    position="header",
    items=[ticker],
)
```

### Updating Ticker Dynamically

```python
from pywry import PyWry, Toolbar, Marquee, TickerItem, Button

app = PyWry()

def on_refresh_prices(data, event_type, label):
    # Simulate updated prices
    new_prices = [
        {"symbol": "AAPL", "price": 186.50, "change": 1.8},
        {"symbol": "GOOGL", "price": 142.20, "change": -0.2},
        {"symbol": "MSFT", "price": 380.00, "change": 1.1},
    ]
    new_items = [
        TickerItem(
            ticker=p["symbol"],
            text=f"{p['symbol']} ${p['price']:.2f} {'+'if p['change'] > 0 else ''}{p['change']:.1f}%",
            class_name="stock-up" if p["change"] > 0 else "stock-down",
        )
        for p in new_prices
    ]
    app.emit("toolbar:marquee-set-content", {
        "id": "stock-ticker",
        "text": " ".join(item.build_html() for item in new_items),
    }, label)
    app.emit("pywry:alert", {"message": "Prices refreshed!", "type": "success"}, label)

app.show(
    "<h1>Stock Dashboard</h1>",
    toolbars=[
        Toolbar(position="header", items=[
            Marquee(
                component_id="stock-ticker",
                text=" ".join(
                    TickerItem(ticker=s, text=f"{s} --").build_html()
                    for s in ["AAPL", "GOOGL", "MSFT"]
                ),
            )
        ]),
        Toolbar(position="top", items=[
            Button(label="Refresh Prices", event="prices:refresh", variant="primary")
        ]),
    ],
    callbacks={"prices:refresh": on_refresh_prices},
)
```

### News Ticker

```python
headlines = [
    "Breaking: Major tech earnings beat expectations",
    "Fed signals steady rates through Q2",
    "New AI regulations proposed in Congress",
]

news_items = [
    TickerItem(ticker=f"news-{i}", text=f"📰 {headline}")
    for i, headline in enumerate(headlines)
]

news_ticker = Marquee(
    text=" • ".join(item.build_html() for item in news_items),
    speed=30,  # Slower for readability
)
```

### Metrics Dashboard

```python
metric_items = [
    TickerItem(ticker="users", text="Users: 12,453 +5%", class_name="stock-up"),
    TickerItem(ticker="revenue", text="Revenue: $1.2M +12%", class_name="stock-up"),
    TickerItem(ticker="orders", text="Orders: 834 +8%", class_name="stock-up"),
    TickerItem(ticker="uptime", text="Uptime: 99.9%"),
]

metrics = Marquee(
    text=" ".join(item.build_html() for item in metric_items),
)
```

## Attributes

```
component_id : str | None
    Unique identifier for state tracking and dynamic updates (auto-generated if not provided)
label : str | None
    Display label (rarely used for marquees)
description : str | None
    Tooltip/hover text for accessibility and user guidance
event : str
    Event name emitted on click when clickable=True (format: namespace:event-name)
style : str | None
    Optional inline CSS
disabled : bool
    Whether the marquee is disabled (default: False)
text : str
    Text or HTML content to scroll (default: "")
speed : float
    Duration in seconds for one scroll cycle — lower is faster (default: 15.0, range: 1.0–300.0)
direction : str
    Scroll direction: "left", "right", "up", or "down" (default: "left")
behavior : str
    Animation behavior: "scroll", "alternate", "slide", or "static" (default: "scroll")
pause_on_hover : bool
    Pause animation when mouse hovers (default: True)
gap : int
    Gap in pixels between repeated content (default: 50, range: 0–500)
clickable : bool
    Whether clicking the marquee emits an event (default: False)
separator : str
    Optional separator between repeated content, e.g. " • " (default: "")
items : list[str] | None
    List of content items for static behavior with auto-cycling (default: None)
children : list[ToolbarItem] | None
    Nested toolbar items to scroll (alternative to text) (default: None)
```

## Events

When `clickable=True`, emits the `event` name with payload:

```json
{"value": "AAPL $185.32 +1.2%", "componentId": "marquee-abc123"}
```

- `value` — text content of the clicked item

**Dynamic update event:** Use `toolbar:marquee-set-content` to update items at runtime (see Updating Ticker Dynamically example above).

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
