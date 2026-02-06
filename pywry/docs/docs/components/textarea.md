# TextArea

A multi-line text input for longer content like notes or descriptions.

## Basic Usage

```python
from pywry import TextArea

notes = TextArea(
    label="Notes",
    event="form:notes",
    placeholder="Enter your notes here...",
    rows=4,  # Height in rows
)
```

## With Default Value

```python
from pywry import TextArea

TextArea(
    label="Description",
    event="item:description",
    value="Default description text\nwith multiple lines",
    rows=6,
)
```

## Custom CSS Editor

```python
from pywry import TextArea

def on_css_change(data, event_type, label):
    css = data["value"]
    # Inject custom CSS into the page
    widget.emit("pywry:inject-css", {"css": css})

css_editor = TextArea(
    label="Custom CSS",
    event="style:custom_css",
    placeholder="/* Enter custom CSS */",
    rows=10,
)
```

## Feedback Form

```python
from pywry import Toolbar, TextArea, Button

feedback_toolbar = Toolbar(
    position="bottom",
    items=[
        TextArea(
            label="Feedback",
            event="feedback:message",
            placeholder="Share your thoughts...",
            rows=3,
        ),
        Button(label="Submit", event="feedback:submit", variant="primary"),
    ],
)
```

## Character Count

```python
from pywry import Toolbar, TextArea, Div

def on_text_change(data, event_type, label):
    text = data["value"]
    char_count = len(text)
    max_chars = 500
    
    widget.emit("pywry:set-content", {
        "selector": "#char-count",
        "html": f"{char_count}/{max_chars}"
    })
    
    if char_count > max_chars:
        widget.emit("pywry:alert", {
            "message": "Character limit exceeded",
            "type": "warning"
        })

toolbar = Toolbar(
    position="bottom",
    items=[
        TextArea(label="Message", event="msg:content", rows=4),
        Div(component_id="char-count", content="0/500"),
    ],
)
```

## TextArea vs TextInput

| Component | Lines | Use Case |
|-----------|-------|----------|
| TextInput | Single | Names, emails, short values |
| TextArea | Multiple | Notes, descriptions, code |

## API Reference

For complete parameter documentation, see the [TextArea API Reference](../reference/components/textarea.md).
