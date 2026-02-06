# NumberInput

A numeric input field with optional min/max constraints and step increments.

## Basic Usage

```python
from pywry import NumberInput

quantity = NumberInput(
    label="Quantity",
    event="order:quantity",
    value=1,
    min=1,
    max=100,
)
```

## With Step

```python
NumberInput(
    label="Price",
    event="item:price",
    value=9.99,
    min=0,
    step=0.01,  # Decimal increments
)
```

## Constraints

| Parameter | Description |
|-----------|-------------|
| `min` | Minimum allowed value |
| `max` | Maximum allowed value |
| `step` | Increment/decrement step |

```python
# Integer 1-10
NumberInput(label="Rating", event="review:rating", min=1, max=10, step=1)

# Percentage 0-100%
NumberInput(label="Opacity", event="style:opacity", min=0, max=100, step=5)

# Decimal values
NumberInput(label="Weight (kg)", event="item:weight", min=0, step=0.1)
```

## Common Patterns

### Calculated Fields

```python
# Store current values
current_dimensions = {"width": 10, "height": 10}

def on_width_change(data, event_type, label):
    current_dimensions["width"] = data["value"]
    area = current_dimensions["width"] * current_dimensions["height"]
    
    widget.emit("pywry:set-content", {
        "selector": "#area-display",
        "html": f"Area: {area} sq units"
    })

def on_height_change(data, event_type, label):
    current_dimensions["height"] = data["value"]
    area = current_dimensions["width"] * current_dimensions["height"]
    
    widget.emit("pywry:set-content", {
        "selector": "#area-display",
        "html": f"Area: {area} sq units"
    })

toolbar = Toolbar(
    position="top",
    items=[
        NumberInput(
            component_id="width-input",
            label="Width",
            event="calc:width",
            value=10,
            min=1,
        ),
        NumberInput(
            component_id="height-input",
            label="Height",
            event="calc:height",
            value=10,
            min=1,
        ),
        Div(component_id="area-display", content="Area: 100 sq units"),
    ],
)
```

## Related Components

- [SliderInput](sliderinput.md) - Visual slider for numeric selection
- [RangeInput](rangeinput.md) - Min-max range selection

## API Reference

For complete parameter documentation, see the [NumberInput API Reference](../reference/components/numberinput.md).
