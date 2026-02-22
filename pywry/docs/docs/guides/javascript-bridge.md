# JavaScript Bridge

Every PyWry window — native or browser-based — injects a `window.pywry` JavaScript object that connects the page's DOM to your Python code. This is how custom JavaScript sends events to Python and receives data back.

## The window.pywry Object

The bridge is available globally in every widget. It provides four methods:

| Method | Signature | What it does |
|:---|:---|:---|
| `emit(event, data)` | `(string, object?)` | Send an event from JavaScript to Python |
| `on(event, callback)` | `(string, function)` | Listen for events sent from Python |
| `off(event, callback?)` | `(string, function?)` | Remove a listener (all listeners for that event if no callback) |
| `label` | `string` | The current window/widget label (read-only) |

### Sending Events to Python

```javascript
// Simple event
window.pywry.emit("app:save", { id: 123 });

// With complex data
window.pywry.emit("app:update", {
    selection: [1, 2, 3],
    timestamp: Date.now(),
    metadata: { source: "user" },
});
```

Event names must follow a `namespace:event-name` pattern. The bridge validates this format and rejects bare names.

In Python, register a callback for the event:

```python
def on_save(data, event_type, label):
    print(f"Saving ID {data['id']} from window {label}")

handle = app.show(html, callbacks={"app:save": on_save})
```

### Listening for Python Events

```javascript
// Register a handler for data arriving from Python
window.pywry.on("app:data-ready", function (data) {
    renderChart(data.values);
});
```

From Python, send data to the browser:

```python
handle.emit("app:data-ready", {"values": [10, 20, 30, 40, 50]})
```

### Removing Listeners

```javascript
// Remove a specific handler
const handler = (data) => console.log(data);
window.pywry.on("app:update", handler);
window.pywry.off("app:update", handler);

// Remove ALL handlers for an event
window.pywry.off("app:update");
```

## Two Bridge Implementations

The `window.pywry` API is the same in both modes, but the transport layer differs:

| Mode | Transport | How it works |
|:---|:---|:---|
| **Native** (desktop) | PyTauri IPC | `emit()` calls `window.__TAURI__.pytauri.pyInvoke()`, which routes directly to a Rust→Python handler |
| **Browser / Notebook** | WebSocket | `emit()` sends JSON `{type, data, widgetId, ts}` over a WebSocket connection to the FastAPI server |

You don't need to think about this difference — write the same JavaScript for both modes. The bridge abstracts the transport.

## Built-in System Events

PyWry pre-registers handlers for several `pywry:*` events. You can trigger these from Python via `handle.emit()` or from JavaScript via `window.pywry.emit()`:

| Event | Payload | Effect |
|:---|:---|:---|
| `pywry:update-html` | `{html}` | Replaces the `#app` container's innerHTML |
| `pywry:set-content` | `{id?, selector?, html?, text?}` | Updates a specific element's content |
| `pywry:set-style` | `{id?, selector?, styles}` | Sets inline CSS styles on elements |
| `pywry:inject-css` | `{css, id}` | Injects or updates a `<style>` element |
| `pywry:remove-css` | `{id}` | Removes a `<style>` element by ID |
| `pywry:navigate` | `{url}` | Navigates to a URL (`window.location.href`) |
| `pywry:download` | `{filename, content, mimeType}` | Triggers a file download (Tauri save dialog in native; blob in browser) |
| `pywry:refresh` | — | Reloads the page |
| `pywry:alert` | `{message, type?}` | Shows a toast notification (or browser `alert()` as fallback) |

### Example: Updating Content from Python

```python
# Replace entire page content
handle.emit("pywry:update-html", {"html": "<h1>New Dashboard</h1>"})

# Update just one element by ID
handle.emit("pywry:set-content", {"id": "status", "text": "Connected"})

# Update by CSS selector, with HTML
handle.emit("pywry:set-content", {"selector": ".results", "html": "<b>42 items</b>"})
```

### Example: Injecting CSS from Python

```python
handle.emit("pywry:inject-css", {
    "id": "custom-theme",
    "css": ":root { --bg-primary: #1a1a2e; --text-primary: #e0e0e0; }",
})

# Later, remove it
handle.emit("pywry:remove-css", {"id": "custom-theme"})
```

## Complete Example

A text input in JavaScript that sends data to Python, which responds with a greeting:

### Python

```python
from pywry import PyWry

app = PyWry()

html = """
<div style="padding: 20px;">
    <input type="text" id="name" placeholder="Enter your name">
    <button onclick="submitName()">Submit</button>
    <p id="response">Waiting...</p>
</div>

<script>
function submitName() {
    const name = document.getElementById("name").value;
    window.pywry.emit("app:submit-name", { name: name });
}

window.pywry.on("app:greeting", function(data) {
    document.getElementById("response").innerText = data.message;
});
</script>
"""

def on_submit(data, event_type, label):
    name = data["name"]
    handle.emit("app:greeting", {"message": f"Hello, {name}!"})

handle = app.show(html, callbacks={"app:submit-name": on_submit})
app.block()
```

The flow:

1. User types a name and clicks Submit
2. `submitName()` calls `window.pywry.emit("app:submit-name", ...)`
3. Python callback `on_submit` fires with the data
4. Python sends back a greeting via `handle.emit("app:greeting", ...)`
5. The JavaScript handler updates the DOM

## Interacting with Plotly Charts

Plotly charts expose their own event system. To bridge Plotly events to Python:

```javascript
const plotDiv = document.getElementById("plotly-chart");

plotDiv.on("plotly_click", function (data) {
    const point = data.points[0];
    window.pywry.emit("app:point-clicked", {
        x: point.x,
        y: point.y,
        trace: point.curveNumber,
    });
});
```

!!! tip "Built-in Plotly Events"
    When you use `app.show_plotly()`, PyWry automatically wires `plotly_click`, `plotly_selected`, and `plotly_hover` events to the `plotly:click`, `plotly:selected`, and `plotly:hover` event names. You don't need to write this JavaScript yourself for the standard events — just register Python callbacks for `plotly:click`, etc.

## Interacting with AG Grid

Access the AG Grid API when using `app.show_dataframe()`:

```javascript
const gridOptions = window.agGridInstance;

// Get selected rows and send to Python
const selected = gridOptions.api.getSelectedRows();
window.pywry.emit("app:selection", { rows: selected });

// Apply a quick filter
gridOptions.api.setQuickFilter("search text");
```

## Tauri APIs (Native Mode Only)

In native desktop mode, a subset of Tauri APIs are available via `window.__TAURI__`. PyWry bundles the **dialog** and **filesystem** plugins along with the **PyTauri IPC bridge** and the core **event system** — it does *not* expose the full Tauri plugin ecosystem.

!!! warning "PyWry uses `pytauri.pyInvoke()`, not `core.invoke()`"
    All JS → Python calls go through `window.__TAURI__.pytauri.pyInvoke()`. Do not use `window.__TAURI__.core.invoke()` — it won't reach PyWry's command handlers.

```javascript
// Check if running in native mode
if (window.__TAURI__) {
    // Native save dialog + write file
    const filePath = await window.__TAURI__.dialog.save({
        defaultPath: "export.csv",
        title: "Save File",
    });

    if (filePath) {
        await window.__TAURI__.fs.writeTextFile(filePath, csvContent);
        window.pywry.emit("app:file-saved", { path: filePath });
    }
}
```

| API | Namespace | What's available |
|-----|-----------|-----------------|
| Event system | `window.__TAURI__.event` | `listen()`, `emit()` — Python ↔ JS event delivery |
| Dialog | `window.__TAURI__.dialog` | `save()` — native save-file dialog |
| Filesystem | `window.__TAURI__.fs` | `writeTextFile()` — write files to disk |
| PyTauri IPC | `window.__TAURI__.pytauri` | `pyInvoke()` — JS → Python command calls |

!!! note "Tauri APIs are not available in browser or notebook mode"
    Check for `window.__TAURI__` before using any Tauri-specific API. In browser/notebook mode, only the `window.pywry` bridge is available.

## Best Practices

### Use Namespaced Event Names

```javascript
// Good — clear namespace
window.pywry.emit("myapp:save-document", data);

// Bad — bare name, will be rejected by the bridge
window.pywry.emit("save", data);
```

### Guard Against Missing Bridge

The bridge may not be ready immediately on page load. Use a safe wrapper:

```javascript
function safeEmit(event, data) {
    if (window.pywry && typeof window.pywry.emit === "function") {
        window.pywry.emit(event, data);
    } else {
        console.warn("PyWry bridge not available");
    }
}
```

### Clean Up Listeners

Prevent memory leaks by removing handlers when you're done:

```javascript
const handlers = [];

function addHandler(event, fn) {
    window.pywry.on(event, fn);
    handlers.push({ event, fn });
}

function cleanup() {
    handlers.forEach(({ event, fn }) => window.pywry.off(event, fn));
    handlers.length = 0;
}
```

### Debounce Frequent Events

For events that fire rapidly (e.g., typing, dragging), debounce before emitting:

```javascript
function debounce(fn, delay) {
    let timeout;
    return function (...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => fn.apply(this, args), delay);
    };
}

const debouncedSearch = debounce((query) => {
    window.pywry.emit("app:search", { query });
}, 300);
```
