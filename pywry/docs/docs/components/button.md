# Button

Buttons trigger actions when clicked. They're the primary way users interact with your toolbar.

## Basic Usage

```python
from pywry import Button

save_btn = Button(
    label="Save",
    event="file:save",
)
```

## Variants

Buttons support different visual styles via the `variant` parameter:

```python
Button(label="Primary", event="action:primary", variant="primary")    # Blue, prominent
Button(label="Success", event="action:success", variant="success")    # Green
Button(label="Warning", event="action:warning", variant="warning")    # Yellow/Orange
Button(label="Danger", event="action:danger", variant="danger")       # Red
Button(label="Neutral", event="action:neutral", variant="neutral")    # Gray
```

| Variant | Color | Use Case |
|---------|-------|----------|
| `primary` | Blue | Main actions (Save, Submit) |
| `success` | Green | Positive actions (Confirm, Apply) |
| `warning` | Yellow | Cautionary actions (Override) |
| `danger` | Red | Destructive actions (Delete, Remove) |
| `neutral` | Gray | Secondary actions (Cancel, Close) |

## Icons

Add icons using emoji or Unicode characters:

```python
Button(label="💾 Save", event="file:save")
Button(label="📤 Export", event="file:export")
Button(label="🗑️ Delete", event="item:delete", variant="danger")
```

## Disabled State

Disable buttons that shouldn't be clickable:

```python
Button(
    label="Save",
    event="file:save",
    disabled=True,  # Grayed out and unclickable
)
```

## Handling Clicks

Connect button clicks to Python callbacks:

```python
from pywry import PyWry, Toolbar, Button

def on_save(data, event_type, label):
    """Handle save button click."""
    # data contains {"clicked": True} for buttons
    # Perform your save operation here
    app.emit("pywry:alert", {"message": "Saved!", "type": "success"}, label)

app = PyWry()
app.show(
    "<h1>Document</h1>",
    toolbars=[Toolbar(position="top", items=[Button(label="Save", event="file:save")])],
    callbacks={"file:save": on_save}
)
```

## Common Patterns

### Confirmation Dialog

```python
from pywry import Button

def show_confirm(data, event_type, label):
    """Show a confirmation dialog before destructive action."""
    app.emit("pywry:alert", {
        "message": "Are you sure you want to delete?",
        "type": "confirm",
        "callback_event": "delete:confirmed",
    }, label)

def on_delete_confirmed(data, event_type, label):
    """Handle confirmation response."""
    if data.get("confirmed"):
        # Perform delete and show success
        app.emit("pywry:alert", {"message": "Deleted!", "type": "success"}, label)

delete_btn = Button(
    label="🗑️ Delete",
    event="action:delete",
    variant="danger",
)

# Register callbacks
callbacks = {
    "action:delete": show_confirm,
    "delete:confirmed": on_delete_confirmed,
}
```

### Toggle State Buttons

```python
from pywry import Button

current_state = {"playing": False}

def on_toggle(data, event_type, label):
    is_playing = not current_state["playing"]
    current_state["playing"] = is_playing
    # Update button label dynamically
    widget.emit("toolbar:set-value", {
        "componentId": "play-btn",
        "label": "⏸️ Pause" if is_playing else "▶️ Play"
    })

play_btn = Button(
    component_id="play-btn",  # Required for dynamic updates
    label="▶️ Play",
    event="media:toggle",
)
```

### Button Groups

```python
from pywry import Toolbar, Button, Div

toolbar = Toolbar(
    position="top",
    items=[
        Button(label="Undo", event="edit:undo"),
        Button(label="Redo", event="edit:redo"),
        Div(content=""),  # Spacer
        Button(label="Save", event="file:save", variant="primary"),
    ],
)
```

## API Reference

For complete parameter documentation, see the [Button API Reference](../reference/components/button.md).
