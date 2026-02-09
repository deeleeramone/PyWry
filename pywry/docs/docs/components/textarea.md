# TextArea

A multi-line text input for longer content like notes or descriptions.

<div class="component-preview col">
  <div class="pywry-input-group pywry-textarea-group">
    <span class="pywry-input-label">Notes:</span>
    <textarea class="pywry-input pywry-textarea" rows="3" cols="40" placeholder="Enter your notes here..." style="resize: both"></textarea>
  </div>
</div>

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
from pywry import PyWry, Toolbar, TextArea, Button

app = PyWry()

def on_apply_css(data, event_type, label):
    css = data.get("value", "")
    app.emit("pywry:inject-css", {"css": css}, label)
    app.emit("pywry:alert", {"message": "CSS applied!", "type": "success"}, label)

app.show(
    "<h1>CSS Editor Demo</h1><p class='styled'>Style this text!</p>",
    toolbars=[
        Toolbar(position="right", items=[
            TextArea(
                label="Custom CSS",
                event="style:custom_css",
                placeholder="/* Enter custom CSS */\n.styled { color: red; }",
                rows=10,
            ),
            Button(label="Apply", event="style:custom_css", variant="primary"),
        ])
    ],
    callbacks={"style:custom_css": on_apply_css},
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
from pywry import PyWry, Toolbar, TextArea, Div, Button

app = PyWry()
max_chars = 500

def on_text_change(data, event_type, label):
    text = data.get("value", "")
    char_count = len(text)
    color = "red" if char_count > max_chars else "inherit"
    app.emit("pywry:set-content", {
        "selector": "#char-count",
        "html": f'<span style="color:{color}">{char_count}/{max_chars}</span>'
    }, label)

def on_submit(data, event_type, label):
    app.emit("pywry:alert", {"message": "Message submitted!", "type": "success"}, label)

app.show(
    "<h1>Feedback Form</h1>",
    toolbars=[
        Toolbar(position="bottom", items=[
            TextArea(label="Message", event="msg:content", rows=4),
            Div(component_id="char-count", content="0/500"),
            Button(label="Submit", event="msg:submit", variant="primary"),
        ])
    ],
    callbacks={"msg:content": on_text_change, "msg:submit": on_submit},
)
```

## Attributes

```
component_id : str | None
    Unique identifier for state tracking (auto-generated if not provided)
label : str | None
    Display label shown above the textarea
description : str | None
    Tooltip/hover text for accessibility and user guidance
event : str
    Event name emitted on input change (format: namespace:event-name)
style : str | None
    Optional inline CSS
disabled : bool
    Whether the textarea is disabled (default: False)
value : str
    Initial text content (default: "")
placeholder : str
    Placeholder text shown when empty (default: "")
debounce : int
    Milliseconds to debounce input events (default: 300)
rows : int
    Initial number of visible text rows (default: 3, min: 1)
cols : int
    Initial number of visible columns (default: 40, min: 1)
resize : str
    CSS resize behavior: "both", "horizontal", "vertical", or "none" (default: "both")
min_height : str
    Minimum height CSS value, e.g. "50px" (default: "")
max_height : str
    Maximum height CSS value, e.g. "500px" (default: "")
min_width : str
    Minimum width CSS value, e.g. "100px" (default: "")
max_width : str
    Maximum width CSS value, e.g. "100%" (default: "")
```

## Events

Emits the `event` name with payload:

```json
{"value": "User-entered text...", "componentId": "textarea-abc123"}
```

- `value` — current text content of the textarea

## TextArea vs TextInput

| Component | Lines | Use Case |
|-----------|-------|----------|
| TextInput | Single | Names, emails, short values |
| TextArea | Multiple | Notes, descriptions, code |

## API Reference

For complete parameter documentation, see the [TextArea API Reference](../reference/components/textarea.md).
