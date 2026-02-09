# SliderInput

A visual slider for selecting numeric values within a range.

<div class="component-preview">
  <span class="pywry-input-group pywry-input-inline">
    <span class="pywry-input-label">Volume:</span>
    <input type="range" class="pywry-input pywry-input-range" value="50" min="0" max="100" step="1">
    <span class="pywry-range-value">50</span>
  </span>
</div>

## Basic Usage

```python
from pywry import SliderInput

volume = SliderInput(
    label="Volume",
    event="audio:volume",
    value=50,
    min=0,
    max=100,
)
```

## With Step

```python
SliderInput(
    label="Brightness",
    event="display:brightness",
    value=75,
    min=0,
    max=100,
    step=5,  # Snaps to multiples of 5
)
```

## Show Value Display

```python
SliderInput(
    label="Opacity",
    event="style:opacity",
    value=100,
    min=0,
    max=100,
    show_value=True,  # Displays current value next to slider
)
```

## Common Patterns

### Real-time Updates

```python
from pywry import PyWry, Toolbar, SliderInput, Div

app = PyWry()

def on_zoom_change(data, event_type, label):
    zoom_level = data["value"]
    app.emit("pywry:set-content", {
        "selector": "#zoom-display",
        "html": f"Zoom: {zoom_level}%"
    }, label)

app.show(
    "<h1>Zoom Demo</h1><div id='zoom-display'>Zoom: 100%</div>",
    toolbars=[
        Toolbar(position="top", items=[
            SliderInput(label="Zoom", event="chart:zoom", value=100, min=50, max=200, step=10)
        ])
    ],
    callbacks={"chart:zoom": on_zoom_change},
)
```

### With Labels

```python
from pywry import PyWry, Toolbar, SliderInput, Div

app = PyWry()

def format_slider_label(data, event_type, label):
    value = data["value"]
    app.emit("pywry:set-content", {
        "selector": "#opacity-label",
        "html": f"{value}%"
    }, label)

app.show(
    "<h1>Opacity Control</h1>",
    toolbars=[
        Toolbar(position="top", items=[
            SliderInput(label="Opacity", event="style:opacity", value=100, min=0, max=100),
            Div(component_id="opacity-label", content="100%"),
        ])
    ],
    callbacks={"style:opacity": format_slider_label},
)
```

### Multiple Sliders

```python
rgb_toolbar = Toolbar(
    position="right",
    items=[
        SliderInput(label="R", event="color:r", value=128, min=0, max=255),
        SliderInput(label="G", event="color:g", value=128, min=0, max=255),
        SliderInput(label="B", event="color:b", value=128, min=0, max=255),
    ],
)
```

## Attributes

```
component_id : str | None
    Unique identifier for state tracking (auto-generated if not provided)
label : str | None
    Display label shown next to the slider
description : str | None
    Tooltip/hover text for accessibility and user guidance
event : str
    Event name emitted on value change (format: namespace:event-name)
style : str | None
    Optional inline CSS
disabled : bool
    Whether the slider is disabled (default: False)
value : float | int
    Current slider value (default: 50)
min : float | int
    Minimum value (default: 0)
max : float | int
    Maximum value (default: 100)
step : float | int
    Increment step size (default: 1)
show_value : bool
    Display current value next to the slider (default: True)
debounce : int
    Milliseconds to debounce input events (default: 50)
```

## Events

Emits the `event` name with payload:

```json
{"value": 75, "componentId": "slider-abc123"}
```

- `value` — current numeric value of the slider

## Slider vs NumberInput

| Component | Best For |
|-----------|----------|
| SliderInput | Visual selection, continuous ranges |
| NumberInput | Precise values, wide ranges |

## API Reference

For complete parameter documentation, see the [SliderInput API Reference](../reference/components/sliderinput.md).
