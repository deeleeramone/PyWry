# Button

Button clicks trigger an event to be sent from the frontend, to the Python handler function defined in the callbacks parameter of `app.show`.

Button click events will emit the instance's `componentId`, and any custom data assigned on initialization.

Multiple buttons can be assigned to the same event handler.

## Import

```python
from pywry import Button
```

## Variants

Buttons support typical styles via the `variant` parameter:

```python
["primary", "secondary", "neutral", "outline", "ghost", "danger", "warning", "icon"]
```

<img width="500" height="40" alt="Button Variants - Dark" src="https://github.com/user-attachments/assets/ded61da3-e06a-40fd-b07a-55a7671bae4b" />
<img width="500" height="40" alt="Button Variants - Light" src="https://github.com/user-attachments/assets/d746890b-ffc7-486d-85c5-a34b29960c98" />

## Sizes

Button sizes can be defined by presets, or can be overriden by supplying the `style` initialization parameter.

<img width="300" height="60" alt="Button Sizes" src="https://github.com/user-attachments/assets/e2f8ce04-c38e-4655-8ba5-5ff846094f60" />

## Icons

Add icons using emoji or Unicode characters:

```python
Button(label="💾 Save", event="file:save")
Button(label="📤 Export", event="file:export")
Button(label="🗑️ Delete", event="item:delete", variant="danger")
```

## Attributes

```
component_id: str | None
    Unique identifier for state tracking (auto-generated if not provided)
label: str | None
    Display label
description: str | None
    Tooltip/hover text for accessibility and user guidance
event: str
    Event name emitted on interaction (format: namespace:event-name)
style: str | None
    Optional inline CSS
disabled: bool | None
    Whether the item is disabled. Set to False 
variant : str
    Button style variant.
      - "primary" (theme-aware)
      - "secondary" (subtle)
      - "neutral" (blue)
      - "ghost" (transparent)
      - "outline" (bordered)
      - "danger" (red)
      - "warning" (orange)
      - "icon" (ghost style, square aspect ratio)
size : str or None
    Button size variant. Options: None (default), "xs", "sm", "lg", "xl".
data : dict
    Additional data payload to include with the event.
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
