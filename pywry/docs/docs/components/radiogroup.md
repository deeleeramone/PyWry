# RadioGroup

A group of radio buttons for mutually exclusive selection.

## Basic Usage

```python
from pywry import RadioGroup, Option

chart_type = RadioGroup(
    label="Chart Type",
    event="chart:type",
    options=[
        Option(label="Line", value="line"),
        Option(label="Bar", value="bar"),
        Option(label="Scatter", value="scatter"),
    ],
    selected="line",
)
```

## Horizontal vs Vertical

By default, radio buttons are arranged based on toolbar position:

- **Horizontal toolbars** (top/bottom): Radio buttons in a row
- **Vertical toolbars** (left/right): Radio buttons stacked

## Common Patterns

### View Mode Selector

```python
view_mode = RadioGroup(
    label="View",
    event="ui:view",
    options=[
        Option(label="📊 Grid", value="grid"),
        Option(label="📋 List", value="list"),
        Option(label="📈 Chart", value="chart"),
    ],
    selected="grid",
)

def on_view_change(data, event_type, label):
    mode = data["value"]
    # Show/hide different content sections
    for view in ["grid", "list", "chart"]:
        display = "block" if view == mode else "none"
        widget.emit("pywry:set-style", {
            "selector": f".view-{view}",
            "styles": {"display": display}
        })
```

### Data Source Selector

```python
data_source = RadioGroup(
    label="Source",
    event="data:source",
    options=[
        Option(label="Live", value="live"),
        Option(label="Historical", value="historical"),
        Option(label="Simulated", value="simulated"),
    ],
    selected="live",
)
```

### Period Selector

```python
period = RadioGroup(
    label="Period",
    event="chart:period",
    options=[
        Option(label="1D", value="1d"),
        Option(label="1W", value="1w"),
        Option(label="1M", value="1m"),
        Option(label="1Y", value="1y"),
        Option(label="All", value="all"),
    ],
    selected="1m",
)
```

## RadioGroup vs Select vs TabGroup

| Component | Visual | Best For |
|-----------|--------|----------|
| RadioGroup | Radio buttons | 3-5 options, always visible |
| Select | Dropdown | Many options, save space |
| TabGroup | Tab bar | Navigation, section switching |

## API Reference

For complete parameter documentation, see the [RadioGroup API Reference](../reference/components/radiogroup.md).
