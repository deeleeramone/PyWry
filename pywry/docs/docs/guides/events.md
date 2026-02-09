# Event System

This guide explains how PyWry's bidirectional event system works and how to use it effectively. For the complete list of all events and their payloads, see the [Event Reference](../reference/events.md).

## How Events Work

PyWry uses namespaced events for all communication between Python and JavaScript. Every event follows the `namespace:event-name` format — for example, `plotly:click` or `app:save`.

There are two directions:

- **JS → Python**: User interactions in the browser trigger callbacks in your Python code
- **Python → JS**: Your Python code sends commands to update the UI

This means your Python code can react to clicks, selections, and form inputs — then respond by updating charts, changing styles, or showing notifications — all without writing any JavaScript.

## The Callback Signature

Every callback receives up to three arguments. You can use all three or just the ones you need:

```python
def my_callback(data: dict, event_type: str, label: str) -> None:
    """
    data       — Event payload from JavaScript (contents vary by event type)
    event_type — The event name that triggered this callback (e.g., "plotly:click")
    label      — The window/widget identifier (use to target responses)
    """
    pass

# Shorter forms are fine too
def on_click(data, event_type): pass
def on_click(data): pass
```

## Registering Callbacks

There are three ways to register handlers, depending on your workflow:

### 1. The `callbacks` dict (recommended for most cases)

Pass a mapping of event names to handler functions when creating a widget. This is the most common pattern and works across all rendering paths:

```python
from pywry import PyWry
import plotly.express as px

app = PyWry()
fig = px.scatter(x=[1, 2, 3], y=[1, 4, 9])

def on_click(data, event_type, label):
    point = data["points"][0]
    app.emit("pywry:alert", {"message": f"Clicked: ({point['x']}, {point['y']})"}, label)

app.show_plotly(fig, callbacks={"plotly:click": on_click})
```

### 2. Using `handle.on()` after creation

Register handlers on the returned handle. Useful when you need to add callbacks dynamically:

```python
handle = app.show_plotly(fig)
handle.on("plotly:click", on_click)
```

### 3. Using `app.on()` with a label (native mode only)

Pre-register callbacks before showing content. The label connects the callback to the window:

```python
app.on("plotly:click", on_click, label="my-chart")
app.show_plotly(fig, label="my-chart")
```

## Sending Events from Python

Send events from Python to update the UI. Two equivalent approaches:

```python
# Using the handle returned by show()
handle = app.show("<h1 id='msg'>Hello</h1>")
handle.emit("pywry:set-content", {"id": "msg", "text": "Updated!"})

# Using app.emit() with a label (useful inside callbacks)
def on_click(data, event_type, label):
    app.emit("pywry:set-content", {"id": "msg", "text": "Updated!"}, label)
```

Inside a callback, use `app.emit(..., label)` since the `label` parameter identifies which window to target.

## Common Patterns

### Update content in response to interaction

```python
from pywry import PyWry, Toolbar, Button

app = PyWry()

def on_click(data, event_type, label):
    app.emit("pywry:set-content", {"selector": "h1", "text": "Button was clicked!"}, label)

toolbar = Toolbar(position="top", items=[Button(label="Click Me", event="app:click")])

app.show(
    "<h1>Waiting for click...</h1>",
    toolbars=[toolbar],
    callbacks={"app:click": on_click},
)
```

### Show toast notifications

```python
def on_save(data, event_type, label):
    app.emit("pywry:alert", {
        "message": "File saved successfully!",
        "type": "success",       # info, success, warning, error, confirm
        "position": "top-right", # top-right, top-left, bottom-right, bottom-left
        "duration": 3000,        # milliseconds
    }, label)
```

### React to chart interactions

```python
def on_chart_click(data, event_type, label):
    point = data["points"][0]
    # Update the chart title with the clicked point
    app.emit("plotly:update-layout", {
        "layout": {"title": f"Clicked: ({point['x']:.2f}, {point['y']:.2f})"}
    }, label)

app.show_plotly(fig, callbacks={"plotly:click": on_chart_click})
```

### Forward events between windows

```python
from pywry import PyWry, WindowMode

app = PyWry(mode=WindowMode.MULTI_WINDOW)
windows = {}

def on_action(data, event_type, label):
    other = windows.get("sidebar")
    if other:
        other.emit("app:update", data)

windows["main"] = app.show(main_html, label="main", callbacks={"app:action": on_action})
windows["sidebar"] = app.show(sidebar_html, label="sidebar")
```

## Custom Event Naming

Use your own namespace for application events. Reserved namespaces (`pywry:*`, `plotly:*`, `grid:*`, `toolbar:*`) are for system events.

```python
# Good — custom namespace
callbacks = {
    "myapp:save": on_save,
    "myapp:export": on_export,
    "dashboard:filter-change": on_filter,
}

# Works, but less organized
callbacks = {
    "app:save": on_save,
    "app:export": on_export,
}
```

## Next Steps

- **[Event Reference](../reference/events.md)** — Complete list of all events and payloads
- **[JavaScript Bridge](javascript-bridge.md)** — Direct JS interaction with `window.pywry`
- **[Toolbar System](toolbars.md)** — Building interactive controls
