# RadioGroup

A group of radio buttons for mutually exclusive selection.

<div class="component-preview">
  <span class="pywry-input-group pywry-input-inline">
    <span class="pywry-input-label">Chart Type:</span>
    <div class="pywry-radio-group pywry-radio-horizontal">
      <label class="pywry-radio-option">
        <input type="radio" name="chart-demo" value="line" checked>
        <span class="pywry-radio-button"></span>
        <span class="pywry-radio-label">Line</span>
      </label>
      <label class="pywry-radio-option">
        <input type="radio" name="chart-demo" value="bar">
        <span class="pywry-radio-button"></span>
        <span class="pywry-radio-label">Bar</span>
      </label>
      <label class="pywry-radio-option">
        <input type="radio" name="chart-demo" value="scatter">
        <span class="pywry-radio-button"></span>
        <span class="pywry-radio-label">Scatter</span>
      </label>
    </div>
  </span>
</div>

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
from pywry import PyWry, Toolbar, RadioGroup, Option

app = PyWry()

def on_view_change(data, event_type, label):
    mode = data["value"]
    # Show/hide different content sections
    for view in ["grid", "list", "chart"]:
        display = "block" if view == mode else "none"
        app.emit("pywry:set-style", {
            "selector": f".view-{view}",
            "styles": {"display": display}
        }, label)

app.show(
    '''
    <div class="view-grid">Grid View Content</div>
    <div class="view-list" style="display:none">List View Content</div>
    <div class="view-chart" style="display:none">Chart View Content</div>
    ''',
    toolbars=[
        Toolbar(position="top", items=[
            RadioGroup(
                label="View",
                event="ui:view",
                options=[
                    Option(label="📊 Grid", value="grid"),
                    Option(label="📋 List", value="list"),
                    Option(label="📈 Chart", value="chart"),
                ],
                selected="grid",
            )
        ])
    ],
    callbacks={"ui:view": on_view_change},
)
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

## Attributes

```
component_id : str | None
    Unique identifier for state tracking (auto-generated if not provided)
label : str | None
    Display label shown next to the radio group
description : str | None
    Tooltip/hover text for accessibility and user guidance
event : str
    Event name emitted on selection change (format: namespace:event-name)
style : str | None
    Optional inline CSS
disabled : bool
    Whether the radio group is disabled (default: False)
options : list[Option]
    List of Option(label, value) items
selected : str
    Currently selected value (default: "")
direction : str
    Layout direction: "horizontal" or "vertical" (default: "horizontal")
```

## Events

Emits the `event` name with payload:

```json
{"value": "line", "componentId": "radio-abc123"}
```

- `value` — the `value` string of the selected option

## RadioGroup vs Select vs TabGroup

| Component | Visual | Best For |
|-----------|--------|----------|
| RadioGroup | Radio buttons | 3-5 options, always visible |
| Select | Dropdown | Many options, save space |
| TabGroup | Tab bar | Navigation, section switching |

## API Reference

For complete parameter documentation, see the [RadioGroup API Reference](../reference/components/radiogroup.md).
