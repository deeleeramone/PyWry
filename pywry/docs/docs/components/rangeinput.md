# RangeInput

A dual-handle slider for selecting a range with minimum and maximum values.

## Basic Usage

```python
from pywry import RangeInput

price_range = RangeInput(
    label="Price",
    event="filter:price",
    min=0,
    max=1000,
    value_min=100,   # Left handle
    value_max=500,   # Right handle
)
```

## With Step

```python
RangeInput(
    label="Year Range",
    event="filter:years",
    min=1990,
    max=2026,
    value_min=2000,
    value_max=2026,
    step=1,
)
```

## Common Patterns

### Data Filtering

```python
def on_range_filter(data, event_type, label):
    min_val = data["min"]
    max_val = data["max"]
    
    # Filter and update visualization
    filtered = df[(df['value'] >= min_val) & (df['value'] <= max_val)]
    
    widget.emit("plotly:update-traces", {
        "update": {"x": [filtered['x'].tolist()], "y": [filtered['y'].tolist()]},
        "indices": [0]
    })

RangeInput(
    label="Value Range",
    event="data:range",
    min=0,
    max=100,
    value_min=25,
    value_max=75,
)
```

### Time Window

```python
RangeInput(
    label="Time (hours)",
    event="filter:time",
    min=0,
    max=24,
    value_min=9,    # 9 AM
    value_max=17,   # 5 PM
    step=1,
)
```

### With Display Labels

```python
def format_range(data, event_type, label):
    widget.emit("pywry:set-content", {
        "selector": "#range-display",
        "html": f"${data['min']:,} - ${data['max']:,}"
    })

toolbar = Toolbar(
    position="top",
    items=[
        RangeInput(
            label="Budget",
            event="filter:budget",
            min=0,
            max=10000,
            value_min=1000,
            value_max=5000,
            step=100,
        ),
        Div(component_id="range-display", content="$1,000 - $5,000"),
    ],
)
```

## API Reference

For complete parameter documentation, see the [RangeInput API Reference](../reference/components/rangeinput.md).
