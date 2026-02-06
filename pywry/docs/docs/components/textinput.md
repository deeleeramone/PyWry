# TextInput

A single-line text input field for capturing short text values.

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
from pywry import TextInput

def on_email_change(data, event_type, label):
    email = data["value"]
    is_valid = "@" in email and "." in email
    
    if not is_valid:
        widget.emit("pywry:alert", {
            "message": "Please enter a valid email",
            "type": "warning"
        })

email_input = TextInput(
    label="Email",
    event="form:email",
    placeholder="user@example.com",
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

## Related Components

- [TextArea](textarea.md) - Multi-line text input
- [SearchInput](searchinput.md) - Text input with search icon
- [SecretInput](secretinput.md) - Password/sensitive text input

## API Reference

For complete parameter documentation, see the [TextInput API Reference](../reference/components/textinput.md).
