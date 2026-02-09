# RangeInput

A dual-handle slider for selecting a range with minimum and maximum values.

<div class="component-preview">
  <span class="pywry-input-group pywry-input-inline">
    <span class="pywry-input-label">Price:</span>
    <span class="pywry-range-group">
      <span class="pywry-range-value pywry-range-start-value">$200</span>
      <div class="pywry-range-track">
        <div class="pywry-range-track-bg"></div>
        <div class="pywry-range-track-fill" style="left: 20%; width: 50%;"></div>
        <input type="range" data-range="start" value="200" min="0" max="1000" step="10">
        <input type="range" data-range="end" value="700" min="0" max="1000" step="10">
      </div>
      <span class="pywry-range-value pywry-range-end-value">$700</span>
    </span>
  </span>
</div>

## Basic Usage

```python
from pywry import RangeInput

price_range = RangeInput(
    label="Price",
    event="filter:price",
    min=0,
    max=1000,
    start=100,   # Left handle
    end=500,     # Right handle
)
```

## With Step

```python
RangeInput(
    label="Year Range",
    event="filter:years",
    min=1990,
    max=2026,
    start=2000,
    end=2026,
    step=1,
)
```

## Common Patterns

### Data Filtering

```python
from pywry import PyWry, Toolbar, RangeInput, Div

app = PyWry()

def on_range_filter(data, event_type, label):
    start = data["start"]
    end = data["end"]
    # Update display with selected range
    app.emit("pywry:set-content", {
        "selector": "#filter-info",
        "html": f"Filtering values between {start} and {end}"
    }, label)

app.show(
    "<h1>Data Filter</h1><div id='filter-info'>Select a range</div>",
    toolbars=[
        Toolbar(position="top", items=[
            RangeInput(
                label="Value Range",
                event="data:range",
                min=0,
                max=100,
                start=25,
                end=75,
            )
        ])
    ],
    callbacks={"data:range": on_range_filter},
)
```

### Time Window

```python
RangeInput(
    label="Time (hours)",
    event="filter:time",
    min=0,
    max=24,
    start=9,    # 9 AM
    end=17,     # 5 PM
    step=1,
)
```

### With Display Labels

```python
from pywry import PyWry, Toolbar, RangeInput, Div

app = PyWry()

def format_range(data, event_type, label):
    app.emit("pywry:set-content", {
        "selector": "#range-display",
        "html": f"${data['start']:,} - ${data['end']:,}"
    }, label)

app.show(
    "<h1>Budget Selector</h1>",
    toolbars=[
        Toolbar(position="top", items=[
            RangeInput(
                label="Budget",
                event="filter:budget",
                min=0,
                max=10000,
                start=1000,
                end=5000,
                step=100,
            ),
            Div(component_id="range-display", content="$1,000 - $5,000"),
        ])
    ],
    callbacks={"filter:budget": format_range},
)
```

## Attributes

```
component_id : str | None
    Unique identifier for state tracking (auto-generated if not provided)
label : str | None
    Display label shown next to the range slider
description : str | None
    Tooltip/hover text for accessibility and user guidance
event : str
    Event name emitted on range change (format: namespace:event-name)
style : str | None
    Optional inline CSS
disabled : bool
    Whether the range slider is disabled (default: False)
start : float | int
    Start (left handle) of selected range (default: 0)
end : float | int
    End (right handle) of selected range (default: 100)
min : float | int
    Minimum value of the track (default: 0)
max : float | int
    Maximum value of the track (default: 100)
step : float | int
    Increment step size (default: 1)
show_value : bool
    Display range values next to the slider (default: True)
debounce : int
    Milliseconds to debounce input events (default: 50)
```

## Events

Emits the `event` name with payload:

```json
{"start": 100, "end": 500, "componentId": "range-abc123"}
```

- `start` — current value of the left handle
- `end` — current value of the right handle

## API Reference

For complete parameter documentation, see the [RangeInput API Reference](../reference/components/rangeinput.md).
