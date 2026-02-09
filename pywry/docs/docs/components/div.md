# Div

A container for displaying custom HTML content, labels, or status indicators.

<div class="component-preview">
  <div class="pywry-div" data-component-id="file-group">
    <strong style="color: var(--pywry-text-primary)">File:</strong>
  </div>
  <button class="pywry-btn pywry-toolbar-button pywry-btn-secondary" data-event="file:new">New</button>
  <button class="pywry-btn pywry-toolbar-button pywry-btn-neutral" data-event="file:save">Save</button>
  <span class="preview-sep"></span>
  <div class="pywry-div" data-component-id="view-group">
    <strong style="color: var(--pywry-text-primary)">View:</strong>
  </div>
  <button class="pywry-btn pywry-toolbar-button pywry-btn-outline" data-event="view:edit">Edit</button>
  <button class="pywry-btn pywry-toolbar-button pywry-btn-outline" data-event="view:preview">Preview</button>
</div>

## Basic Usage

```python
from pywry import Div

status = Div(
    content="Ready",
)
```

## With HTML

```python
Div(
    content='<span style="color: green">✓</span> Connected',
)
```

## With Component ID

For dynamic updates:

```python
from pywry import PyWry, Toolbar, Div, Button

app = PyWry()

def on_update(data, event_type, label):
    app.emit("pywry:set-content", {
        "selector": "#status-display",
        "html": "Status: Processing..."
    }, label)

app.show(
    "<h1>Dashboard</h1>",
    toolbars=[
        Toolbar(position="top", items=[
            Div(component_id="status-display", content="Status: Idle"),
            Button(label="Update", event="status:update"),
        ])
    ],
    callbacks={"status:update": on_update},
)
```

## Common Patterns

### Status Indicator

```python
from pywry import PyWry, Toolbar, Div, Button

app = PyWry()

def set_status(status: str, label: str):
    icons = {"connected": "●", "disconnected": "○", "error": "⚠"}
    colors = {"connected": "green", "disconnected": "gray", "error": "red"}
    app.emit("pywry:set-content", {
        "selector": "#status",
        "html": f'<span style="color:{colors[status]}">{icons[status]}</span> {status.title()}'
    }, label)

def on_connect(data, event_type, label):
    set_status("connected", label)

def on_disconnect(data, event_type, label):
    set_status("disconnected", label)

app.show(
    "<h1>Connection Manager</h1>",
    toolbars=[
        Toolbar(position="footer", items=[
            Div(component_id="status", content="○ Disconnected"),
        ]),
        Toolbar(position="top", items=[
            Button(label="Connect", event="conn:connect"),
            Button(label="Disconnect", event="conn:disconnect"),
        ]),
    ],
    callbacks={"conn:connect": on_connect, "conn:disconnect": on_disconnect},
)
```

### Spacer

```python
toolbar = Toolbar(
    position="top",
    items=[
        Button(label="File", event="menu:file"),
        Button(label="Edit", event="menu:edit"),
        Div(content=""),  # Spacer - pushes remaining items right
        Button(label="Help", event="menu:help"),
    ],
)
```

### Live Counter

```python
from pywry import PyWry, Toolbar, Div, Button

app = PyWry()
count = 0

def on_increment(data, event_type, label):
    global count
    count += 1
    app.emit("pywry:set-content", {
        "selector": "#counter",
        "html": f"Count: {count}"
    }, label)

app.show(
    "<h1>Counter Demo</h1>",
    toolbars=[
        Toolbar(position="top", items=[
            Div(component_id="counter", content="Count: 0"),
            Button(label="+1", event="counter:increment"),
        ])
    ],
    callbacks={"counter:increment": on_increment},
)
```

### Section Labels

```python
from pywry import Toolbar, Div, Button

toolbar = Toolbar(
    position="left",
    items=[
        Div(content="<strong>File</strong>"),
        Button(label="New", event="file:new"),
        Button(label="Save", event="file:save"),
        Div(content="<strong>View</strong>"),
        Button(label="Edit", event="view:edit"),
        Button(label="Preview", event="view:preview"),
    ],
)
```

## Attributes

```
component_id : str | None
    Unique identifier for state tracking and dynamic content updates (auto-generated if not provided)
label : str | None
    Display label (default: "")
description : str | None
    Tooltip/hover text for accessibility and user guidance
event : str
    Event name (default: "toolbar:input")
style : str | None
    Optional inline CSS
disabled : bool
    Whether the div is disabled (default: False)
content : str
    HTML content to render inside the div (default: "")
script : str | Path | None
    JS file path or inline script for this container (default: None)
class_name : str
    Custom CSS class added to the div alongside "pywry-div" (default: "")
children : list[ToolbarItem] | None
    Nested toolbar items rendered inside the div (default: None)
```

## Events

Div does not emit events automatically. Use it as a display container for labels, status indicators, or custom HTML. Content can be updated dynamically via:

```python
app.emit("pywry:set-content", {
    "selector": "#my-div-id",
    "html": "New content"
}, label)
```

## API Reference

For complete parameter documentation, see the [Div API Reference](../reference/components/div.md).
