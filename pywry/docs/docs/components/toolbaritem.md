# ToolbarItem

The base class for all toolbar components. You typically won't use ToolbarItem directly—instead use specific components like Button, Select, or TextInput.

## Components

All toolbar components inherit from `ToolbarItem`:

| Category | Components |
|----------|-----------|
| **Actions** | [Button](button.md) |
| **Selection** | [Select](select.md), [MultiSelect](multiselect.md), [RadioGroup](radiogroup.md), [TabGroup](tabgroup.md) |
| **Text Input** | [TextInput](textinput.md), [TextArea](textarea.md), [SearchInput](searchinput.md), [SecretInput](secretinput.md) |
| **Numeric** | [NumberInput](numberinput.md), [DateInput](dateinput.md), [SliderInput](sliderinput.md), [RangeInput](rangeinput.md) |
| **Toggles** | [Toggle](toggle.md), [Checkbox](checkbox.md) |
| **Layout** | [Div](div.md), [Marquee](marquee.md) |

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
from pywry import PyWry, Toolbar, Button

app = PyWry()

def on_click(data, event_type, label):
    # Update the button dynamically
    app.emit("toolbar:set-value", {
        "componentId": "my-button",
        "label": "Clicked!",
        "disabled": True,
    }, label)

app.show(
    "<h1>Demo</h1>",
    toolbars=[
        Toolbar(position="top", items=[
            Button(
                component_id="my-button",  # ID required for dynamic updates
                label="Click Me",
                event="action:click",
            )
        ])
    ],
    callbacks={"action:click": on_click},
)
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
from pywry import PyWry, Toolbar, Button

app = PyWry()

def on_click(data, event_type, label):
    # Disable button after click
    app.emit("toolbar:set-value", {
        "componentId": "submit-btn",
        "disabled": True,
        "label": "Submitting...",
    }, label)

app.show(
    "<h1>Form</h1>",
    toolbars=[
        Toolbar(position="top", items=[
            Button(
                component_id="submit-btn",
                label="Submit",
                event="form:submit",
            )
        ])
    ],
    callbacks={"form:submit": on_click},
)
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
