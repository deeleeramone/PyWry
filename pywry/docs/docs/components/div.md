# Div

A container for displaying custom HTML content, labels, or status indicators.

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
Div(
    component_id="status-display",
    content="Status: Idle",
)

# Later, update the content
widget.emit("pywry:set-content", {
    "selector": "#status-display",
    "html": "Status: Processing..."
})
```

## Common Patterns

### Status Indicator

```python
def update_status(status: str):
    icons = {
        "connected": '●',
        "disconnected": '○',
        "error": '⚠',
    }
    colors = {
        "connected": "green",
        "disconnected": "gray",
        "error": "red",
    }
    
    widget.emit("pywry:set-content", {
        "selector": "#status",
        "html": f'<span style="color:{colors[status]}">{icons[status]}</span> {status.title()}'
    })

toolbar = Toolbar(
    position="footer",
    items=[
        Div(component_id="status", content="○ Disconnected"),
    ],
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
count = 0

def on_increment(data, event_type, label):
    global count
    count += 1
    widget.emit("pywry:set-content", {
        "selector": "#counter",
        "html": f"Count: {count}"
    })

toolbar = Toolbar(
    position="top",
    items=[
        Div(component_id="counter", content="Count: 0"),
        Button(label="+1", event="counter:increment"),
    ],
)
```

### Section Labels

```python
from pywry import Toolbar, Div, Button

toolbar = Toolbar(
    position="left",
    items=[
        Div(content="<strong>Navigation</strong>"),
        Button(label="Home", event="nav:home"),
        Button(label="Settings", event="nav:settings"),
        Div(content="<strong>Actions</strong>"),
        Button(label="Export", event="action:export"),
        Button(label="Share", event="action:share"),
    ],
)
```

## API Reference

For complete parameter documentation, see the [Div API Reference](../reference/components/div.md).
