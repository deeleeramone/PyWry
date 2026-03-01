# Native Window Mode

> **CRITICAL**: This is a **native desktop application** using PyWry/WRY (Rust WebView).
> This is **NOT** a browser. This is **NOT** Jupyter. This is **NOT** an iframe.

## What Native Mode IS

You're creating widgets for a **native desktop window** powered by:
- **PyWry** (Python bindings)
- **WRY** (Rust WebView library)
- **Tauri** ecosystem (system-level access)

The widget runs in a **standalone system window** with:
- Native title bar, minimize, maximize, close buttons
- Direct OS integration (file dialogs, notifications, clipboard)
- No browser chrome, no URL bar, no tabs
- Full screen real estate for your content

## What Native Mode is NOT

❌ **NOT a web browser** - No DevTools (unless explicitly enabled), no extensions, no URL bar
❌ **NOT Jupyter** - No cell output area, no kernel, no notebook context
❌ **NOT an iframe** - No parent page, no sandboxing, no cross-origin restrictions

## Architecture

```
┌───────────────────────────────────────────────────────────┐
│                      Native Window                        │
│  ┌─────────────────────────────────────────────────────┐  │
│  │               Title Bar (OS-native)                 │  │
│  ├─────────────────────────────────────────────────────┤  │
│  │                                                     │  │
│  │                 WebView (WRY/Tauri)                 │  │
│  │                                                     │  │
│  │    ┌─────────────────────────────────────────┐      │  │
│  │    │          Your Widget Content            │      │  │
│  │    │      (HTML/CSS/JS via PyWry API)        │      │  │
│  │    └─────────────────────────────────────────┘      │  │
│  │                                                     │  │
│  └─────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────┘
              ↕ Python ↔ Rust ↔ OS integration
```

## Key Capabilities

### Window Control
- Resize, minimize, maximize, close via native controls
- Set window title dynamically
- Window always stays on top (optional)
- Multiple windows possible

### System Integration
- **Downloads**: `download` tool triggers native OS save dialog
- **Navigation**: `navigate` can open external URLs in system browser
- **Clipboard**: Full clipboard access
- **File System**: Can reference local files

### Persistent State
- Widget state persists until window is closed
- Events accumulate until `get_events(clear=True)`
- Long-running applications are the norm

## Best Practices

### 1. Layout - Use Full Viewport
```python
# You have the entire window - use it
content = Div(
    content="<h1>Dashboard</h1>",
    component_id="main",
    style="height: 100vh; width: 100vw; padding: 20px;",
)
```

### 2. Toolbars - Position Top/Bottom
```python
# Top toolbar for primary navigation
create_widget(
    html=content.build_html(),
    toolbars=[{
        "position": "top",
        "items": [
            {"type": "button", "label": "File", "event": "menu:file"},
            {"type": "button", "label": "Edit", "event": "menu:edit"},
            {"type": "button", "label": "View", "event": "menu:view"},
        ]
    }]
)
```

### 3. Theme - Respect System Preference
```python
# Let OS dark/light mode control the theme
update_theme(widget_id, theme="system")
```

### 4. Interactive Buttons - The Pattern

**CRITICAL**: Buttons work automatically when events follow `elementId:action` pattern.

```
# Counter widget - buttons update content automatically
create_widget(
    html='<div id="counter" style="font-size:48px;text-align:center">0</div>',
    toolbars=[{
        "position": "top",
        "items": [
            {"type": "button", "label": "+1", "event": "counter:increment"},
            {"type": "button", "label": "-1", "event": "counter:decrement"},
            {"type": "button", "label": "Reset", "event": "counter:reset"}
        ]
    }]
)
```

The magic: `event="counter:increment"` automatically:
1. Finds element with `id="counter"`
2. Increments its text content by 1
3. Updates the display

Supported actions:
- `increment` - add 1
- `decrement` - subtract 1
- `reset` - set to 0
- `toggle` - switch true/false

### 5. Window Events
```python
# Detect window close
events = get_events(widget_id, clear=True)
for e in events:
    if e["event_type"] == "pywry:disconnect":
        # User closed the window - cleanup
        cleanup_resources()
```

## Recommended Components

| Component | Why |
|-----------|-----|
| `TabGroup` | Multi-view navigation (like app tabs) |
| `SecretInput` | Secure API key storage |
| `Marquee` | Live data tickers (full width available) |
| `Plotly` | Full interactive charts (zoom, pan, export) |

## Code Example

```python
from pywry import PyWry
from pywry.toolbar import Button, Div, TabGroup, Toolbar

app = PyWry()

# Create main content area
content = Div(
    content="""
        <h1 style="margin: 0;">Financial Dashboard</h1>
        <p>Real-time market data</p>
    """,
    component_id="dashboard",
    style="padding: 24px; height: calc(100vh - 100px);",
)

# Create window with toolbars
widget = app.show(
    html=content.build_html(),
    title="Market Dashboard",
    height=800,
    toolbars=[
        Toolbar(
            position="top",
            items=[
                Button(label="Refresh", event="action:refresh", variant="primary"),
                Button(label="Settings", event="action:settings", variant="ghost"),
            ]
        )
    ]
)

# Event loop
while True:
    events = widget.get_events(clear=True)
    for e in events:
        if e["event_type"] == "pywry:disconnect":
            exit()
        elif e["event_type"] == "action:refresh":
            # Refresh data...
            pass
```

## Native-Specific Features

### File Downloads
```python
# Triggers native OS save dialog
download(widget_id,
         url="data:text/csv;base64,...",
         filename="export.csv")
```

### Open in System Browser
```python
# Opens URL in user's default browser (not the widget)
navigate(widget_id, url="https://example.com", external=True)
```

### Toast Notifications
```python
# Native-style toast (position matters less in native)
show_toast(widget_id, message="Saved!", type="success")
```
