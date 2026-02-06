# TickerItem

An individual entry in a Marquee ticker, displaying a symbol, value, and optional change indicator.

## Basic Usage

```python
from pywry import TickerItem

item = TickerItem(
    symbol="AAPL",
    value="$185.32",
    change="+1.2%",
)
```

## Properties

| Property | Description | Example |
|----------|-------------|---------|
| `symbol` | Identifier/label | "AAPL", "BTC", "📈" |
| `value` | Current value | "$185.32", "12,453" |
| `change` | Change indicator | "+1.2%", "-5.3%", "" |

## Change Styling

The `change` value automatically styles based on prefix:

```python
# Positive (green styling)
TickerItem(symbol="AAPL", value="$185", change="+1.2%")

# Negative (red styling)
TickerItem(symbol="GOOGL", value="$141", change="-0.5%")

# Neutral (no color)
TickerItem(symbol="INFO", value="Status", change="")
```

## Common Patterns

### Stock Quote

```python
TickerItem(
    symbol="AAPL",
    value="$185.32",
    change="+2.15 (+1.17%)",
)
```

### Cryptocurrency

```python
TickerItem(
    symbol="BTC",
    value="$67,234",
    change="+3.2%",
)
```

### Metrics

```python
[
    TickerItem(symbol="Users", value="12,453", change="+5%"),
    TickerItem(symbol="Revenue", value="$1.2M", change="+12%"),
    TickerItem(symbol="CPU", value="45%", change=""),
    TickerItem(symbol="Memory", value="8.2GB", change=""),
]
```

### With Icons

```python
[
    TickerItem(symbol="📈", value="S&P 500", change="+0.8%"),
    TickerItem(symbol="💰", value="Gold", change="-0.3%"),
    TickerItem(symbol="⛽", value="Oil", change="+1.5%"),
]
```

## Building from Data

```python
prices = [
    {"symbol": "AAPL", "price": 185.32, "change_pct": 1.2},
    {"symbol": "GOOGL", "price": 141.80, "change_pct": -0.5},
]

items = [
    TickerItem(
        symbol=p["symbol"],
        value=f"${p['price']:.2f}",
        change=f"{'+' if p['change_pct'] >= 0 else ''}{p['change_pct']:.1f}%",
    )
    for p in prices
]

ticker = Marquee(items=items)
```

## Related Components

- [Marquee](marquee.md) - Container that displays scrolling TickerItems

## API Reference

For complete parameter documentation, see the [TickerItem API Reference](../reference/components/tickeritem.md).
