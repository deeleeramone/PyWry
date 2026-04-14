# Anywidget Transport

PyWry's event system uses a unified protocol — `on()`, `emit()`, `update()`, `display()` — that works identically across native windows, IFrame+WebSocket, and anywidget. This page explains how that protocol is implemented over the anywidget transport, so you can build reusable components or introduce new integrations that work seamlessly in all three environments.

For the IFrame+WebSocket transport, see [IFrame + WebSocket Transport](../inline-widget/index.md).

## The Unified Protocol

Every PyWry widget — regardless of rendering path — implements `BaseWidget`:

```python
class BaseWidget(Protocol):
    def on(self, event_type: str, callback: Callable[[dict, str, str], Any]) -> BaseWidget: ...
    def emit(self, event_type: str, data: dict[str, Any]) -> None: ...
    def update(self, html: str) -> None: ...
    def display(self) -> None: ...
```

A reusable component only calls these four methods. It never knows whether it's running in a native window, a notebook widget, or a browser tab. The transport handles everything else.

## How Anywidget Implements the Protocol

In anywidget mode, `PyWryWidget` extends `anywidget.AnyWidget` and implements `BaseWidget` by mapping each method to traitlet synchronization:

| BaseWidget Method | Anywidget Implementation |
|-------------------|--------------------------|
| `emit(type, data)` | Serialize `{type, data, ts}` to JSON → set `_py_event` traitlet → `send_state()` |
| `on(type, callback)` | Store callback in `_handlers[type]` dict → `_handle_js_event` observer dispatches |
| `update(html)` | Set `content` traitlet → JS `model.on('change:content')` re-renders |
| `display()` | Call `IPython.display.display(self)` |

### Traitlets

Six traitlets carry all state between Python and JavaScript:

| Traitlet | Direction | Purpose |
|----------|-----------|---------|
| `content` | Python → JS | HTML markup to render |
| `theme` | Bidirectional | `"dark"` or `"light"` |
| `width` | Python → JS | CSS width |
| `height` | Python → JS | CSS height |
| `_js_event` | JS → Python | Serialized event from browser |
| `_py_event` | Python → JS | Serialized event from Python |

### Event Wire Format

Both `_js_event` and `_py_event` carry JSON strings:

```json
{"type": "namespace:event-name", "data": {"key": "value"}, "ts": "unique-id"}
```

The `ts` field ensures every event is a unique traitlet value. Jupyter only syncs on change — identical consecutive events would be dropped without unique timestamps.

### JS → Python Path

```
pywry.emit("form:submit", {name: "x"})
  → JSON.stringify({type: "form:submit", data: {name: "x"}, ts: Date.now()})
  → model.set("_js_event", json_string)
  → model.save_changes()
  → Jupyter kernel syncs traitlet
  → Python observer _handle_js_event fires
  → json.loads(change["new"])
  → callback(data, "form:submit", widget_label)
```

### Python → JS Path

```
widget.emit("pywry:set-content", {"id": "status", "text": "Done"})
  → json.dumps({"type": ..., "data": ..., "ts": uuid.hex})
  → self._py_event = json_string
  → self.send_state("_py_event")
  → Jupyter kernel syncs traitlet
  → JS model.on("change:_py_event") fires
  → JSON.parse(model.get("_py_event"))
  → pywry._fire(type, data)
  → registered on() listeners execute
```

## The ESM Render Function

The widget frontend is an ESM module with a `render({model, el})` function. This function must:

1. Create a `.pywry-widget` container div inside `el`
2. Render `model.get("content")` as innerHTML
3. Create a local `pywry` bridge object with `emit()`, `on()`, and `_fire()`
4. Also set `window.pywry` for HTML `onclick` handlers to access
5. Listen for `change:_py_event` and dispatch to `pywry._fire()`
6. Listen for `change:content` and re-render
7. Listen for `change:theme` and update CSS classes

The `pywry` bridge in the ESM implements the JavaScript side of the protocol:

```javascript
const pywry = {
    _handlers: {},
    emit: function(type, data) {
        // Write to _js_event traitlet → triggers Python observer
        model.set('_js_event', JSON.stringify({type, data: data || {}, ts: Date.now()}));
        model.save_changes();
        // Also dispatch locally so JS listeners fire immediately
        this._fire(type, data || {});
    },
    on: function(type, callback) {
        if (!this._handlers[type]) this._handlers[type] = [];
        this._handlers[type].push(callback);
    },
    _fire: function(type, data) {
        (this._handlers[type] || []).forEach(function(h) { h(data); });
    }
};
```

## Building a Reusable Component

A reusable component is a Python class that takes a `BaseWidget` and registers event handlers. Because it only calls `on()` and `emit()`, it works on all three rendering paths without modification.

### Python Side: State Mixin Pattern

PyWry's built-in components (`GridStateMixin`, `PlotlyStateMixin`, `ChatStateMixin`, `ToolbarStateMixin`) all follow the same pattern — they inherit from `EmittingWidget` and call `self.emit()`:

```python
from pywry.state_mixins import EmittingWidget


class CounterMixin(EmittingWidget):
    """Adds a counter widget that syncs between Python and JavaScript."""

    def increment(self, amount: int = 1):
        self.emit("counter:increment", {"amount": amount})

    def reset(self):
        self.emit("counter:reset", {})

    def set_value(self, value: int):
        self.emit("counter:set", {"value": value})
```

Any widget class that mixes this in and provides `emit()` gets counter functionality:

```python
class MyWidget(PyWryWidget, CounterMixin):
    pass

widget = MyWidget(content=counter_html)
widget.increment(5)   # Works in notebooks (anywidget traitlets)
widget.reset()        # Works in browser (WebSocket)
                      # Works in native windows (Tauri IPC)
```

### JavaScript Side: Event Handlers

The JavaScript side registers listeners through `pywry.on()` — this works identically in all rendering paths because every transport creates the same `pywry` bridge object:

```javascript
// This code works in ESM (anywidget), ws-bridge.js (IFrame), and bridge.js (native)
pywry.on('counter:increment', function(data) {
    var el = document.getElementById('counter-value');
    var current = parseInt(el.textContent) || 0;
    el.textContent = current + data.amount;
});

pywry.on('counter:reset', function() {
    document.getElementById('counter-value').textContent = '0';
});

pywry.on('counter:set', function(data) {
    document.getElementById('counter-value').textContent = data.value;
});

// User clicks emit events back to Python — same pywry.emit() everywhere
document.getElementById('inc-btn').onclick = function() {
    pywry.emit('counter:clicked', {action: 'increment'});
};
```

### Wiring It Together

To use the component with `ChatManager`, `app.show()`, or any other entry point:

```python
from pywry import HtmlContent, PyWry

app = PyWry()

counter_html = """
<div style="text-align:center; padding:20px">
    <h1 id="counter-value">0</h1>
    <button onclick="pywry.emit('counter:clicked', {action:'increment'})">+1</button>
    <button onclick="pywry.emit('counter:clicked', {action:'reset'})">Reset</button>
</div>
<script>
pywry.on('counter:increment', function(d) {
    var el = document.getElementById('counter-value');
    el.textContent = parseInt(el.textContent || 0) + d.amount;
});
pywry.on('counter:reset', function() {
    document.getElementById('counter-value').textContent = '0';
});
</script>
"""

def on_counter_click(data, event_type, label):
    if data["action"] == "increment":
        app.emit("counter:increment", {"amount": 1}, label)
    elif data["action"] == "reset":
        app.emit("counter:reset", {}, label)

widget = app.show(
    HtmlContent(html=counter_html),
    callbacks={"counter:clicked": on_counter_click},
)
```

This works in native windows, notebooks with anywidget, notebooks with IFrame fallback, and browser mode — the same HTML, the same callbacks, the same `pywry.emit()`/`pywry.on()` contract.

## Specialized Widget Subclasses

When a component needs its own bundled JavaScript library (like Plotly, AG Grid, or TradingView), it defines a widget subclass with a custom `_esm`:

| Subclass | Mixin | Bundled Library | Extra Traitlets |
|----------|-------|-----------------|-----------------|
| `PyWryWidget` | `EmittingWidget` | Base bridge only | — |
| `PyWryPlotlyWidget` | `PlotlyStateMixin` | Plotly.js | `figure_json`, `chart_id` |
| `PyWryAgGridWidget` | `GridStateMixin` | AG Grid | `grid_config`, `grid_id`, `aggrid_theme` |
| `PyWryChatWidget` | `ChatStateMixin` | Chat handlers | `_asset_js`, `_asset_css` |
| `PyWryTVChartWidget` | `TVChartStateMixin` | Lightweight-charts | `chart_config`, `chart_id` |

Each subclass overrides `_esm` with an ESM module that includes both the library code and the domain-specific event handlers. The extra traitlets carry domain state (chart data, grid config, etc.) alongside the standard `content`/`theme`/`_js_event`/`_py_event` protocol.

### Lazy Asset Loading

`PyWryChatWidget` uses two additional traitlets — `_asset_js` and `_asset_css` — for on-demand library loading. When `ChatManager` first encounters a `PlotlyArtifact`, it pushes the Plotly library source through `_asset_js`:

```python
# ChatManager detects anywidget and uses trait instead of HTTP
self._widget.set_trait("_asset_js", plotly_source_code)
```

The ESM listens for the trait change and injects the code:

```javascript
model.on("change:_asset_js", function() {
    var js = model.get("_asset_js");
    if (js) {
        var script = document.createElement("script");
        script.textContent = js;
        document.head.appendChild(script);
    }
});
```

This replaces the `chat:load-assets` HTTP-based injection used in the IFrame transport, keeping the protocol uniform while adapting to the transport's capabilities.

## Transport Comparison

| Aspect | Anywidget | IFrame+WebSocket | Native Window |
|--------|-----------|------------------|---------------|
| `pywry.emit()` | Traitlet `_js_event` | WebSocket send | Tauri IPC `pyInvoke` |
| `pywry.on()` | Local handler dict | Local handler dict | Local handler dict |
| Python `emit()` | Traitlet `_py_event` | Async queue → WS send | Tauri event emit |
| Python `on()` | Traitlet observer | Callback dict lookup | Callback dict lookup |
| Asset loading | Bundled in `_esm` or `_asset_js` trait | HTTP `<script>` injection | Bundled in page HTML |
| Server required | No | Yes (FastAPI) | No (subprocess IPC) |
| Multiple widgets | Each is an independent anywidget | Shared server, per-widget WS | Each is a window |

The Python-facing API (`on`, `emit`, `update`, `display`) and the JavaScript-facing API (`pywry.emit`, `pywry.on`, `pywry._fire`) are identical in every column. A component built against these interfaces works everywhere.
