# SliderInput

A visual slider for selecting numeric values within a range.

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
def on_zoom_change(data, event_type, label):
    zoom_level = data["value"]
    
    # Update chart zoom in real-time
    widget.emit("plotly:update-layout", {
        "layout": {
            "xaxis.range": [0, 100 / zoom_level],
            "yaxis.range": [0, 100 / zoom_level],
        }
    })

SliderInput(
    label="Zoom",
    event="chart:zoom",
    value=100,
    min=50,
    max=200,
    step=10,
)
```

### With Labels

```python
# Show percentage label
def format_slider_label(data, event_type, label):
    value = data["value"]
    widget.emit("pywry:set-content", {
        "selector": "#opacity-label",
        "html": f"{value}%"
    })

toolbar = Toolbar(
    position="top",
    items=[
        SliderInput(
            label="Opacity",
            event="style:opacity",
            value=100,
            min=0,
            max=100,
        ),
        Div(component_id="opacity-label", content="100%"),
    ],
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

## Slider vs NumberInput

| Component | Best For |
|-----------|----------|
| SliderInput | Visual selection, continuous ranges |
| NumberInput | Precise values, wide ranges |

## API Reference

For complete parameter documentation, see the [SliderInput API Reference](../reference/components/sliderinput.md).
