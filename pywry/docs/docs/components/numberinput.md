# NumberInput

A numeric input field with optional min/max constraints and step increments.

<div class="component-preview">
  <span class="pywry-input-group pywry-input-inline">
    <span class="pywry-input-label">Quantity:</span>
    <span class="pywry-number-wrapper">
      <input type="number" class="pywry-input pywry-input-number" value="42" min="1" max="100" step="1">
      <span class="pywry-number-spinner">
        <button type="button" tabindex="-1">&#9650;</button>
        <button type="button" tabindex="-1">&#9660;</button>
      </span>
    </span>
  </span>
</div>

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

Use `min`, `max`, and `step` to control allowed values:

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
from pywry import PyWry, Toolbar, NumberInput, Div

app = PyWry()
current_dimensions = {"width": 10, "height": 10}

def update_area(label):
    area = current_dimensions["width"] * current_dimensions["height"]
    app.emit("pywry:set-content", {
        "selector": "#area-display",
        "html": f"Area: {area} sq units"
    }, label)

def on_width_change(data, event_type, label):
    current_dimensions["width"] = data["value"]
    update_area(label)

def on_height_change(data, event_type, label):
    current_dimensions["height"] = data["value"]
    update_area(label)

app.show(
    "<h1>Area Calculator</h1>",
    toolbars=[
        Toolbar(position="top", items=[
            NumberInput(component_id="width-input", label="Width", event="calc:width", value=10, min=1),
            NumberInput(component_id="height-input", label="Height", event="calc:height", value=10, min=1),
            Div(component_id="area-display", content="Area: 100 sq units"),
        ])
    ],
    callbacks={"calc:width": on_width_change, "calc:height": on_height_change},
)
```

## Attributes

```
component_id : str | None
    Unique identifier for state tracking (auto-generated if not provided)
label : str | None
    Display label shown next to the input
description : str | None
    Tooltip/hover text for accessibility and user guidance
event : str
    Event name emitted on value change (format: namespace:event-name)
style : str | None
    Optional inline CSS
disabled : bool
    Whether the input is disabled (default: False)
value : float | int | None
    Current numeric value (default: None)
min : float | int | None
    Minimum allowed value (default: None)
max : float | int | None
    Maximum allowed value (default: None)
step : float | int | None
    Increment step size for spinner buttons (default: None)
```

## Events

Emits the `event` name with payload:

```json
{"value": 42, "componentId": "number-abc123"}
```

- `value` — current numeric value

## Related Components

- [SliderInput](sliderinput.md) - Visual slider for numeric selection
- [RangeInput](rangeinput.md) - Min-max range selection

## API Reference

For complete parameter documentation, see the [NumberInput API Reference](../reference/components/numberinput.md).
