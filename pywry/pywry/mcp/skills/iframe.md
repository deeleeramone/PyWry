# iFrame Embed Mode

> **CRITICAL**: This mode is for widgets **embedded as iframes in external web pages**.
> This is **NOT** a native window. This is **NOT** Jupyter. The widget is sandboxed.

## What iFrame Mode IS

You're creating widgets to be **embedded as iframes** in external pages:
- Widget served at a URL: `http://host:port/widget/{widget_id}`
- Embedded via `<iframe src="...">` in parent page
- Sandboxed execution - isolated from parent
- Cross-origin restrictions apply

## What iFrame Mode is NOT

❌ **NOT a native window** - No OS integration, no native dialogs
❌ **NOT Jupyter** - No kernel, no notebook context
❌ **NOT the main page** - You're embedded, constrained by parent

## Architecture

```
┌───────────────────────────────────────────────────────────────────┐
│                   Parent Web Page (any origin)                    │
│                                                                   │
│   <iframe src="http://pywry-server:port/widget/abc123"            │
│           width="100%" height="500">                              │
│     ┌───────────────────────────────────────────────────────┐     │
│     │              PyWry Widget (sandboxed)                 │     │
│     │                                                       │     │
│     │    ┌───────────────────────────────────────────┐      │     │
│     │    │        Your Content (HTML/CSS/JS)         │      │     │
│     │    └───────────────────────────────────────────┘      │     │
│     │                                                       │     │
│     │    [Toolbars, Charts, Forms, etc.]                    │     │
│     │                                                       │     │
│     └───────────────────────────────────────────────────────┘     │
│   </iframe>                                                       │
│                                                                   │
│   Other page content...                                           │
└───────────────────────────────────────────────────────────────────┘
                   ↕ postMessage for communication
```

## Key Constraints

### Fixed Dimensions
- Width and height determined by parent's `<iframe>` tag
- Widget cannot resize itself
- Design for specific dimensions or be responsive

### Sandboxed Execution
- Cannot access parent DOM
- Cannot read parent cookies/storage
- Limited access to some browser APIs
- Navigation stays within iframe (unless allowed)

### Cross-Origin Restrictions
- Widget origin ≠ parent origin (usually)
- Communication via `postMessage` only
- Some features require `allow` attributes

## Best Practices

### 1. Sizing - Design for Fixed Dimensions
```python
# The parent controls your size
# <iframe src="..." width="600" height="400">

# Design content to fit
content = Div(
    content="...",
    style="width: 100%; height: 100%; overflow: auto;",
)
```

### 2. Toolbars - Keep Minimal
```python
# Screen real estate is precious
create_widget(
    html=content.build_html(),
    toolbars=[{
        "position": "top",
        "items": [
            # Compact: icons only or short labels
            {"type": "button", "label": "⟳", "event": "refresh"},
            {"type": "toggle", "label": "Auto", "event": "auto-update"},
        ]
    }]
)
```

### 3. Navigation - Stays in Frame
```python
# By default, navigation stays within iframe
navigate(widget_id, url="/other-view")  # Still in iframe

# External links may be blocked by parent
# Use with caution:
navigate(widget_id, url="https://external.com", external=True)
```

### 4. Downloads - May Require Gesture
```python
# Some browsers block downloads from iframes
# Ensure download is triggered by user action
# (button click, not automatic)
```

## Security Considerations

### Sandboxing Protects Both Sides
- Widget can't access parent page data
- Parent can't directly access widget DOM
- Use this for untrusted contexts

### Secret Handling
```python
# Never expose secrets in URL or logs
# Use SecretInput handler - value stays server-side
create_widget(
    toolbars=[{
        "items": [
            {"type": "secret", "label": "API Key", "event": "api-key"},
        ]
    }]
)
```

### Token-Based Access
```python
# Consider adding tokens to widget URLs for access control
# http://host:port/widget/{widget_id}?token={access_token}
```

## Recommended Components

| Component | Why |
|-----------|-----|
| `Button` | Compact action triggers |
| `Toggle` | On/off states (saves space) |
| `Select` | Dropdowns (vertical space efficient) |
| `Plotly` | Self-contained interactive charts |

## Communication with Parent

### Widget → Parent (via events)
```python
# Widget emits events that parent can receive
# Parent listens for postMessage events
#
# Parent page JavaScript:
# window.addEventListener('message', (e) => {
#     if (e.data.type === 'pywry:event') {
#         console.log(e.data.event_type, e.data.data);
#     }
# });
```

### Parent → Widget (via send_event)
```python
# Server can send events to widget
send_event(widget_id, event_type="parent:message", data={"action": "refresh"})
```

## Embedding Pattern

### Basic Embed
```html
<iframe
  src="http://pywry-server:8001/widget/my-chart"
  width="100%"
  height="500"
  frameborder="0"
  loading="lazy">
</iframe>
```

### With Permissions
```html
<iframe
  src="http://pywry-server:8001/widget/my-chart"
  width="100%"
  height="500"
  frameborder="0"
  allow="clipboard-write; downloads"
  sandbox="allow-scripts allow-same-origin">
</iframe>
```

## Code Example

```python
from pywry import PyWry
from pywry.toolbar import Div, Button, Toggle, Toolbar

app = PyWry()

# Compact content for iframe embedding
content = Div(
    content="""
        <div style="padding: 12px;">
            <div id="status" style="margin-bottom: 12px;">Ready</div>
            <div id="chart" style="height: 350px;"></div>
        </div>
    """,
    component_id="embed-widget",
)

# Create embeddable widget
widget = app.show(
    html=content.build_html(),
    height=450,
    toolbars=[
        Toolbar(
            position="top",
            items=[
                Button(label="⟳ Refresh", event="refresh"),
                Toggle(label="Live", event="live-mode", value=False),
            ]
        )
    ]
)

# Widget is now available at:
# http://localhost:port/widget/{widget.id}
print(f"Embed URL: {widget.url}")

# Handle events server-side
while True:
    events = widget.get_events(clear=True)
    for e in events:
        if e["event_type"] == "refresh":
            new_data = fetch_data()
            widget.set_content(component_id="chart", html=render_chart(new_data))
        elif e["event_type"] == "live-mode":
            if e["data"]["value"]:
                start_live_updates()
            else:
                stop_live_updates()
```

## iFrame-Specific Features

### Responsive Design
```python
# Widget should adapt to container size
inject_css(widget_id, css="""
    @media (max-width: 400px) {
        .toolbar { flex-direction: column; }
        .chart { height: 200px; }
    }
""")
```

### Loading States
```python
# Parent may show iframe slowly - show loading state
content = Div(
    content="<div class='loading'>Loading...</div>",
    component_id="content",
)
# Then update when data is ready
```
