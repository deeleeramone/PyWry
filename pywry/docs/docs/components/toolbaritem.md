# ToolbarItem

The base class for all toolbar components. You typically won't use ToolbarItem directly—instead use specific components like Button, Select, or TextInput.

## Component Hierarchy

```
ToolbarItem (base)
├── Button
├── Select
├── MultiSelect
├── RadioGroup
├── TabGroup
├── TextInput
├── TextArea
├── SearchInput
├── SecretInput
├── NumberInput
├── DateInput
├── SliderInput
├── RangeInput
├── Toggle
├── Checkbox
├── Div
└── Marquee
```

## Common Properties

All toolbar items inherit these properties:

| Property | Type | Description |
|----------|------|-------------|
| `component_id` | str | Unique identifier for dynamic updates |
| `type` | str | Component type (auto-set) |
| `disabled` | bool | Whether the component is disabled |

## Component ID

The `component_id` is essential for dynamic updates:

```python
from pywry import Button

# Without ID - cannot update dynamically
Button(label="Click", event="action:click")

# With ID - can update later
Button(
    component_id="my-button",
    label="Click",
    event="action:click",
)

# Later, update the button
widget.emit("toolbar:set-value", {
    "componentId": "my-button",
    "label": "Clicked!",
    "disabled": True,
})
```

## Type System

Each component has a `type` that's automatically set:

```python
Button(...)       # type="button"
Select(...)       # type="select"
TextInput(...)    # type="text"
Toggle(...)       # type="toggle"
```

This type is used internally for rendering and serialization.

## Disabled State

All components can be disabled:

```python
# Initially disabled
Button(label="Submit", event="form:submit", disabled=True)

# Disable dynamically
widget.emit("toolbar:set-value", {
    "componentId": "submit-btn",
    "disabled": True,
})

# Enable dynamically
widget.emit("toolbar:set-value", {
    "componentId": "submit-btn",
    "disabled": False,
})
```

## Creating Custom Components

For advanced use cases, you can extend ToolbarItem:

```python
from pywry.toolbar import ToolbarItem

class CustomProgress(ToolbarItem):
    """A custom progress bar component."""
    
    type: str = "progress"  # Custom type
    value: int = 0
    max: int = 100
    
    def build_html(self) -> str:
        percentage = (self.value / self.max) * 100
        return f'''
        <div class="custom-progress" data-component-id="{self.component_id}">
            <div class="progress-bar" style="width: {percentage}%"></div>
            <span>{self.value}/{self.max}</span>
        </div>
        '''
```

## API Reference

For complete parameter documentation, see the [ToolbarItem API Reference](../reference/components/toolbaritem.md).
