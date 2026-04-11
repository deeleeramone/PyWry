# Anywidget & Widget Protocol

PyWry supports three rendering paths — native desktop windows, anywidget-based Jupyter widgets, and IFrame + FastAPI server. All three implement the same `BaseWidget` protocol, so your application code works identically regardless of environment.

For the protocol and widget API reference, see [`BaseWidget`](../reference/widget-protocol.md), [`PyWryWidget`](../reference/widget.md), and [`InlineWidget`](../reference/inline-widget.md).

## Rendering Path Auto-Detection

`PyWry.show()` automatically selects the best rendering path:

```
Script / Terminal  ──→  Native OS window (PyTauri subprocess)
Notebook + anywidget ──→  PyWryWidget (traitlet sync, no server)
Notebook + Plotly/Grid ──→  InlineWidget (FastAPI + IFrame)
Notebook without anywidget ──→  InlineWidget (FastAPI fallback)
Browser / SSH / headless ──→  InlineWidget (opens system browser)
```

No configuration needed — the right path is chosen at `show()` time.

## The BaseWidget Protocol

Every rendering backend implements this protocol:

```python
from pywry.widget_protocol import BaseWidget

def use_widget(widget: BaseWidget):
    # Register a JS → Python event handler
    widget.on("app:click", lambda data, event_type, label: print(data))

    # Send a Python → JS event
    widget.emit("app:update", {"key": "value"})

    # Replace the widget HTML
    widget.update("<h1>New Content</h1>")

    # Show the widget in the current context
    widget.display()
```

| Method | Description |
|--------|-------------|
| `on(event_type, callback)` | Register callback for JS → Python events. Callback receives `(data, event_type, label)`. Returns self for chaining. |
| `emit(event_type, data)` | Send Python → JS event with a JSON-serializable payload. |
| `update(html)` | Replace the widget's HTML content. |
| `display()` | Show the widget (native window, notebook cell, or browser tab). |

## Level 1: PyWryWidget (anywidget)

The best notebook experience. Uses anywidget's traitlet sync — no server needed, instant bidirectional communication through the Jupyter kernel.

**Requirements:** `pip install anywidget traitlets`

```python
from pywry import PyWry

app = PyWry()
widget = app.show("<h1>Hello from anywidget!</h1>")

# Events work identically
widget.on("app:ready", lambda d, e, l: print("Widget ready"))
widget.emit("app:update", {"count": 42})
```

**How it works:**

1. Python creates a `PyWryWidget` (extends `anywidget.AnyWidget`)
2. An ESM module is bundled as the widget frontend
3. Traitlets (`content`, `theme`, `_js_event`, `_py_event`) sync bidirectionally via Jupyter comms
4. `widget.emit()` → sets `_py_event` traitlet → JS receives change → dispatches to JS listeners
5. JS `pywry.emit()` → sets `_js_event` traitlet → Python `_handle_js_event()` → dispatches to callbacks

**When it's used:** Notebook environment + anywidget installed + no Plotly/AG Grid/TradingView content.

## Level 2: InlineWidget (IFrame + FastAPI)

Used for Plotly, AG Grid, and TradingView content in notebooks, or when anywidget isn't installed. Starts a local FastAPI server and renders via an IFrame.

**Requirements:** `pip install fastapi uvicorn`

```python
from pywry import PyWry

app = PyWry()

# Plotly/Grid/TradingView automatically use InlineWidget
handle = app.show_plotly(fig)
handle = app.show_dataframe(df)
handle = app.show_tvchart(ohlcv_data)
```

**How it works:**

1. A singleton FastAPI server starts in a background thread (one per kernel)
2. Each widget gets a URL (`/widget/{widget_id}`) and a WebSocket (`/ws/{widget_id}`)
3. An IFrame in the notebook cell points to the widget URL
4. `widget.emit()` → enqueues event → WebSocket send loop pushes to browser
5. JS `pywry.emit()` → sends over WebSocket → FastAPI handler dispatches to Python callbacks

**Multiple widgets share one server** — efficient for dashboards with many components.

**Browser-only mode:**

```python
widget = app.show("<h1>Dashboard</h1>")
widget.open_in_browser()  # Opens system browser instead of notebook
```

## Level 3: NativeWindowHandle (Desktop)

Used in scripts and terminals. The PyTauri subprocess manages native OS webview windows.

```python
from pywry import PyWry

app = PyWry(title="My App", width=800, height=600)
handle = app.show("<h1>Native Window</h1>")

# Same API as notebook widgets
handle.on("app:click", lambda d, e, l: print("Clicked!", d))
handle.emit("app:update", {"status": "ready"})

# Additional native-only features
handle.close()
handle.hide()
handle.eval_js("document.title = 'Updated'")
print(handle.label)  # Window label
```

**How it works:** JSON-over-stdin/stdout IPC to the PyTauri Rust subprocess. The subprocess manages the OS webview (WKWebView on macOS, WebView2 on Windows, WebKitGTK on Linux).

## Writing Portable Code

Since all three backends share the `BaseWidget` protocol, write code against the protocol:

```python
def setup_dashboard(widget):
    """Works with any widget type."""
    widget.on("app:ready", lambda d, e, l: print("Ready in", l))
    widget.on("app:click", handle_click)
    widget.emit("app:config", {"theme": "dark"})

# Works everywhere
handle = app.show(my_html)
setup_dashboard(handle)
```

## Fallback Behavior

If `anywidget` is not installed, `PyWryWidget` becomes a stub that shows an error message with install instructions. The `InlineWidget` fallback handles all notebook rendering in that case.

| Scenario | Widget Used | Fallback |
|----------|-------------|----------|
| Notebook + anywidget + simple HTML | `PyWryWidget` | — |
| Notebook + anywidget + Plotly | `InlineWidget` | — |
| Notebook, no anywidget | `InlineWidget` | IFrame server |
| Desktop script | `NativeWindowHandle` | — |
| SSH / headless | `InlineWidget` | Opens browser |
