# JavaScript Bridge

PyWry exposes a JavaScript API through `window.pywry` for direct browser-side interaction.

## The window.pywry Object

Every PyWry window has access to a global `window.pywry` object:

```javascript
window.pywry = {
    emit(event, data),      // Send event to Python
    on(event, handler),     // Listen for events from Python
    off(event, handler),    // Remove event listener
    label,                  // Current window/widget label
    config,                 // Widget configuration
    version,                // PyWry version string
};
```

## Sending Events to Python

```javascript
// Simple event
window.pywry.emit("app:save", { id: 123 });

// With complex data
window.pywry.emit("app:update", {
    selection: [1, 2, 3],
    timestamp: Date.now(),
    metadata: { source: "user" }
});
```

In Python:

```python
def on_save(data, event_type, label):
    app.emit("pywry:alert", {"message": f"Saving ID: {data['id']}", "type": "info"}, label)

handle = app.show(html, callbacks={"app:save": on_save})
```

## Listening for Python Events

```javascript
// Register handler
window.pywry.on("app:data-ready", function(data) {
    console.log("Data received:", data);
    renderChart(data.values);
});

// Remove handler
const handler = (data) => console.log(data);
window.pywry.on("app:update", handler);
window.pywry.off("app:update", handler);
```

From Python:

```python
handle.emit("app:data-ready", {"values": [1, 2, 3, 4, 5]})
```

## Complete Example

### Python Side

```python
from pywry import PyWry

app = PyWry()

html = """
<div style="padding: 20px;">
    <input type="text" id="name" placeholder="Enter name">
    <button onclick="sendName()">Submit</button>
    <p id="response">Waiting...</p>
</div>

<script>
function sendName() {
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

## Using with Plotly

Access Plotly charts directly:

```javascript
// Get the Plotly div
const plotDiv = document.getElementById("plotly-chart");

// React to Plotly events
plotDiv.on("plotly_click", function(data) {
    const point = data.points[0];
    window.pywry.emit("app:point-clicked", {
        x: point.x,
        y: point.y,
        trace: point.curveNumber
    });
});

// Update chart programmatically
Plotly.relayout(plotDiv, { title: "Updated Title" });
```

## Using with AG Grid

Access the grid API:

```javascript
// Get grid instance
const gridOptions = window.agGridInstance;

// Get selected rows
const selected = gridOptions.api.getSelectedRows();
window.pywry.emit("app:selection", { rows: selected });

// Update data
gridOptions.api.setRowData(newData);

// Apply filter
gridOptions.api.setQuickFilter("search text");
```

## Tauri Access (Native Mode Only)

In native desktop mode, you can access Tauri APIs:

```javascript
// Check if running in Tauri
if (window.__TAURI__) {
    const { invoke } = window.__TAURI__.core;
    
    // Call Rust commands
    const result = await invoke("my_command", { arg: "value" });
    
    // File dialogs
    const { open } = window.__TAURI__.dialog;
    const selected = await open({ multiple: false });
    
    // Filesystem
    const { readTextFile } = window.__TAURI__.fs;
    const content = await readTextFile(selected);
}
```

### Available Tauri Plugins

| Plugin | Namespace | Description |
|--------|-----------|-------------|
| Shell | `window.__TAURI__.shell` | Execute commands |
| Dialog | `window.__TAURI__.dialog` | File dialogs |
| Filesystem | `window.__TAURI__.fs` | File operations |
| Clipboard | `window.__TAURI__.clipboard` | Copy/paste |
| Notification | `window.__TAURI__.notification` | System notifications |
| OS | `window.__TAURI__.os` | OS information |
| Path | `window.__TAURI__.path` | Path utilities |
| Process | `window.__TAURI__.process` | Process control |
| HTTP | `window.__TAURI__.http` | HTTP client |
| WebSocket | `window.__TAURI__.websocket` | WebSocket client |
| Updater | `window.__TAURI__.updater` | App updates |

### Example: File Dialog

```javascript
async function selectFile() {
    if (!window.__TAURI__) {
        console.log("Not in Tauri mode");
        return;
    }
    
    const { open } = window.__TAURI__.dialog;
    const { readTextFile } = window.__TAURI__.fs;
    
    const path = await open({
        multiple: false,
        filters: [{ name: "CSV", extensions: ["csv"] }]
    });
    
    if (path) {
        const content = await readTextFile(path);
        window.pywry.emit("app:file-loaded", {
            path: path,
            content: content
        });
    }
}
```

## Detecting Runtime Mode

```javascript
// Check if running in native Tauri
const isNative = !!window.__TAURI__;

// Check if running in browser mode
const isBrowser = !window.__TAURI__;

// Get current label
const label = window.pywry.label;
```

## Error Handling

```javascript
try {
    window.pywry.emit("app:action", data);
} catch (error) {
    console.error("Failed to emit event:", error);
}

window.pywry.on("app:error", function(data) {
    alert("Error: " + data.message);
});
```

## Best Practices

### 1. Use Namespaced Events

```javascript
// Good
window.pywry.emit("myapp:save-document", data);

// Bad
window.pywry.emit("save", data);
```

### 2. Handle Missing pywry Object

```javascript
function safeEmit(event, data) {
    if (window.pywry && typeof window.pywry.emit === "function") {
        window.pywry.emit(event, data);
    } else {
        console.warn("PyWry not available");
    }
}
```

### 3. Clean Up Event Listeners

```javascript
const handlers = [];

function addHandler(event, fn) {
    window.pywry.on(event, fn);
    handlers.push({ event, fn });
}

function cleanup() {
    handlers.forEach(({ event, fn }) => {
        window.pywry.off(event, fn);
    });
}
```

### 4. Debounce Frequent Events

```javascript
function debounce(fn, delay) {
    let timeoutId;
    return function(...args) {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => fn.apply(this, args), delay);
    };
}

const debouncedSearch = debounce((query) => {
    window.pywry.emit("app:search", { query });
}, 300);
```

## Next Steps

- **[Event System](events.md)** — Python event handling
- **[Window Management](window-management.md)** — Multiple windows
- **[PyWry API Reference](../reference/pywry.md)** — Full API reference
