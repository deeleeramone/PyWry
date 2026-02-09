# TextInput

A single-line text input field for capturing short text values.

<div class="component-preview">
  <span class="pywry-input-group pywry-input-inline">
    <span class="pywry-input-label">Name:</span>
    <input type="text" class="pywry-input pywry-input-text" value="John Doe" placeholder="Enter your name">
  </span>
</div>

## Basic Usage

```python
from pywry import TextInput

name_input = TextInput(
    label="Name",
    event="form:name",
    placeholder="Enter your name",
)
```

## With Default Value

```python
from pywry import TextInput

TextInput(
    label="Title",
    event="form:title",
    value="Untitled Document",  # Pre-filled value
)
```

## Validation Pattern

```python
from pywry import PyWry, Toolbar, TextInput, Button

app = PyWry()

def on_email_change(data, event_type, label):
    email = data["value"]
    is_valid = "@" in email and "." in email
    if not is_valid and email:  # Don't warn on empty
        app.emit("pywry:alert", {"message": "Please enter a valid email", "type": "warning"}, label)

def on_submit(data, event_type, label):
    app.emit("pywry:alert", {"message": "Form submitted!", "type": "success"}, label)

app.show(
    "<h1>Contact Form</h1>",
    toolbars=[
        Toolbar(position="top", items=[
            TextInput(label="Email", event="form:email", placeholder="user@example.com"),
            Button(label="Submit", event="form:submit", variant="primary"),
        ])
    ],
    callbacks={"form:email": on_email_change, "form:submit": on_submit},
)
```

## Form Fields

```python
from pywry import Toolbar, TextInput, Button

form_fields = Toolbar(
    position="top",
    items=[
        TextInput(label="First Name", event="form:first_name"),
        TextInput(label="Last Name", event="form:last_name"),
        TextInput(label="Email", event="form:email"),
        Button(label="Submit", event="form:submit", variant="primary"),
    ],
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
    Event name emitted on input change (format: namespace:event-name)
style : str | None
    Optional inline CSS
disabled : bool
    Whether the input is disabled (default: False)
value : str
    Current text value (default: "")
placeholder : str
    Placeholder text shown when empty (default: "")
debounce : int
    Milliseconds to debounce input events (default: 300)
```

## Events

Emits the `event` name with payload:

```json
{"value": "John Doe", "componentId": "text-abc123"}
```

- `value` — current text content of the input

## Related Components

- [TextArea](textarea.md) - Multi-line text input
- [SearchInput](searchinput.md) - Text input with search icon
- [SecretInput](secretinput.md) - Password/sensitive text input

## API Reference

For complete parameter documentation, see the [TextInput API Reference](../reference/components/textinput.md).
