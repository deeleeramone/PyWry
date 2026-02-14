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

## How Events Are Constructed and Executed

To understand what actually happens when you call `app.emit()` or when JavaScript fires an event, let's trace the full lifecycle using the **`pywry:download`** event as a concrete example. This event triggers a file download — it's a good illustration because it shows the complete Python → JS path, the payload structure, and how the same event is handled differently depending on the rendering mode.

### The Python side: constructing the event

When you call `app.emit()`, every rendering path starts the same way — Python builds a JSON payload with three fields:

```python
# Python: trigger a file download
app.emit("pywry:download", {
    "content": "Name,Value\nAlpha,1\nBeta,2",
    "filename": "export.csv",
    "mimeType": "text/csv;charset=utf-8",
}, label="my-window")
```

The payload that Python hands off is always:

```json
{
  "type": "pywry:download",
  "data": {
    "content": "Name,Value\nAlpha,1\nBeta,2",
    "filename": "export.csv",
    "mimeType": "text/csv;charset=utf-8"
  }
}
```

What happens next depends on how the widget is rendered.

### Path 1: Native window (PyTauri)

In native mode, `app.emit()` resolves the target window label and calls through the window manager to `runtime.emit_event()`:

```
app.emit(event_type, data, label)
  → app.send_event(event_type, data, label)
    → WindowMode.send_event(label, event_type, data)
      → runtime.emit_event(label, event_type, data)
```

`runtime.emit_event()` serializes the event as a **JSON command** and writes it to the **stdin pipe** of the PyTauri subprocess:

```json
{
  "action": "emit",
  "label": "my-window",
  "event": "pywry:download",
  "payload": {
    "content": "Name,Value\nAlpha,1\nBeta,2",
    "filename": "export.csv",
    "mimeType": "text/csv;charset=utf-8"
  }
}
```

The Rust/Tauri side reads this from stdin, parses it, and uses the **Tauri event system** (`emit_to`) to deliver the payload to the webview identified by `label`.

On the JavaScript side, the event is received by a `window.__TAURI__.event.listen()` handler registered during page initialization:

```javascript
// scripts.py — Tauri event listener (registered automatically)
window.__TAURI__.event.listen('pywry:download', function(event) {
    var data = event.payload;
    if (!data.content || !data.filename) {
        console.error('[PyWry] Download requires content and filename');
        return;
    }
    // Native mode: use Tauri's save dialog + filesystem API
    window.__TAURI__.dialog.save({
        defaultPath: data.filename,
        title: 'Save File'
    }).then(function(filePath) {
        if (filePath) {
            window.__TAURI__.fs.writeTextFile(filePath, data.content);
        }
    });
});
```

In native mode, the user sees an **OS-native save dialog** and the file is written directly to disk using Tauri's filesystem API — no browser involved.

### Path 2: Notebook widget (anywidget)

In notebook mode, `emit()` serializes the event as a JSON string and writes it to a **traitlet** (`_py_event`), which anywidget syncs to the frontend via the Jupyter comms protocol:

```python
# widget.py — PyWryWidget.emit()
def emit(self, event_type: str, data: dict) -> None:
    event = json.dumps({"type": event_type, "data": data or {}, "ts": uuid.uuid4().hex})
    self._py_event = event
    self.send_state("_py_event")  # Force sync to frontend
```

On the JavaScript side, the anywidget model fires a `change:_py_event` event. The handler parses the JSON, checks the event type, and executes the download inline:

```javascript
// widget.py — anywidget JS (registered automatically)
model.on('change:_py_event', () => {
    const event = JSON.parse(model.get('_py_event') || '{}');
    if (event.type === 'pywry:download' && event.data.content && event.data.filename) {
        // Browser fallback: create a Blob and trigger download via <a> click
        const mimeType = event.data.mimeType || 'application/octet-stream';
        const blob = new Blob([event.data.content], { type: mimeType });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = event.data.filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }
});
```

Since notebooks run inside a browser, there's no native save dialog — instead, the browser's built-in download mechanism creates the file.

### Path 3: IFrame / Browser mode (WebSocket)

In IFrame and browser mode, `emit()` sends the event as a JSON message over a **WebSocket** connection:

```python
# The server sends to the connected WebSocket for this widget
await websocket.send_json({"type": "pywry:download", "data": payload})
```

JavaScript receives the message on the WebSocket `onmessage` handler, which dispatches it through `window.pywry._fire()`. The `pywry:download` handler registered via `window.pywry.on()` picks it up and uses the same Blob/anchor technique as the notebook path:

```javascript
// scripts.py — system event handler (registered automatically)
window.pywry.on('pywry:download', function(data) {
    if (!data.content || !data.filename) return;
    // Browser fallback: Blob + invisible <a> click
    var mimeType = data.mimeType || 'application/octet-stream';
    var blob = new Blob([data.content], { type: mimeType });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = data.filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
});
```

### Summary: same event, three transport layers

| | Native Window | Notebook Widget | IFrame / Browser |
|---|---|---|---|
| **Transport** | stdin pipe → Tauri event system | traitlet sync via Jupyter comms | WebSocket JSON message |
| **JS receives via** | `__TAURI__.event.listen()` | `model.on('change:_py_event')` | `WebSocket.onmessage` → `pywry._fire()` |
| **Download mechanism** | OS save dialog + `fs.writeTextFile` | `Blob` + `<a>` click | `Blob` + `<a>` click |

The key insight: **your Python code is identical regardless of rendering path.** You always call `app.emit("pywry:download", {...})`. PyWry selects the transport automatically, and the JavaScript handlers adapt to the capabilities of the environment (native filesystem API vs. browser download).

### The JS → Python direction

The reverse direction works the same way in mirror. When JavaScript calls `window.pywry.emit()`:

- **Native**: Calls `__TAURI__.pytauri.pyInvoke('pywry_event', payload)` — Tauri IPC to the Rust subprocess, which forwards to Python callbacks
- **Notebook**: Calls `model.set('_js_event', ...)` — traitlet change synced via Jupyter comms, observed by Python `_on_js_event` handler
- **IFrame/Browser**: Calls `socket.send(JSON.stringify(msg))` — WebSocket message received by the FastAPI server, dispatched to Python callbacks

The payload structure is consistent:

```javascript
// What JS sends (all paths)
{
    "type": "plotly:click",            // namespaced event name
    "data": { "points": [...] },       // event-specific payload
    "label": "my-window"               // window/widget identifier
}
```

## Next Steps

- **[Event Reference](../reference/events.md)** — Complete list of all events and payloads
- **[JavaScript Bridge](javascript-bridge.md)** — Direct JS interaction with `window.pywry`
- **[Toolbar System](toolbars.md)** — Building interactive controls
