# Event Reference

Complete reference for all PyWry events, payloads, and the JavaScript bridge API.

## Event Format

All events follow the `namespace:event-name` pattern:

| Part | Rules | Examples |
|------|-------|----------|
| namespace | Starts with letter, alphanumeric | `app`, `plotly`, `grid`, `myapp` |
| event-name | Starts with letter, alphanumeric + hyphens | `click`, `row-select`, `update-data` |

**Reserved namespaces:** `pywry:*`, `plotly:*`, `grid:*`, `toolbar:*`

---

## System Events (`pywry:*`)

### Lifecycle Events (JS → Python)

| Event | Payload | Description |
|-------|---------|-------------|
| `pywry:ready` | `{}` | Window/widget initialized and ready |
| `pywry:result` | `any` | Data from `window.pywry.result(data)` |
| `pywry:message` | `any` | Data from `window.pywry.message(data)` |
| `pywry:content-request` | `{widget_type, window_label, reason}` | Window requests content |
| `pywry:disconnect` | `{}` | Widget disconnected (browser/inline mode) |
| `pywry:close` | `{label}` | Window close requested |

### Window Events (JS → Python)

| Event | Payload | Description |
|-------|---------|-------------|
| `window:closed` | `{label}` | Window was closed |
| `window:hidden` | `{label}` | Window was hidden |

### Content & Styling (Python → JS)

| Event | Payload | Description |
|-------|---------|-------------|
| `pywry:set-content` | `{id?, selector?, text?, html?}` | Update element text/HTML |
| `pywry:set-style` | `{id?, selector?, styles: {}}` | Update element CSS |
| `pywry:inject-css` | `{css, id?}` | Inject CSS (id for replacement) |
| `pywry:remove-css` | `{id}` | Remove injected CSS by id |
| `pywry:update-html` | `{html}` | Replace entire page content |
| `pywry:update-theme` | `{theme}` | Switch theme (`dark` or `light`) |

### Notifications & Actions (Python → JS)

| Event | Payload | Description |
|-------|---------|-------------|
| `pywry:alert` | `{message, type?, title?, duration?, position?, callback_event?}` | Toast notification |
| `pywry:download` | `{content, filename, mimeType?}` | Trigger file download |
| `pywry:navigate` | `{url}` | Navigate to URL |
| `pywry:refresh` | `{}` | Request content refresh |
| `pywry:cleanup` | `{}` | Cleanup resources (native mode) |

**Alert types:** `info`, `success`, `warning`, `error`, `confirm`

**Alert positions:** `top-right` (default), `top-left`, `bottom-right`, `bottom-left`

---

## Plotly Events (`plotly:*`)

### User Interactions (JS → Python)

| Event | Payload |
|-------|---------|
| `plotly:click` | `{chartId, widget_type, points, point_indices, curve_number, event}` |
| `plotly:hover` | `{chartId, widget_type, points, point_indices, curve_number}` |
| `plotly:unhover` | `{chartId}` |
| `plotly:selected` | `{chartId, widget_type, points, point_indices, range, lassoPoints}` |
| `plotly:deselect` | `{chartId}` |
| `plotly:relayout` | `{chartId, widget_type, relayout_data}` |
| `plotly:state-response` | `{chartId, layout, data}` |
| `plotly:export-response` | `{data: [{traceIndex, name, x, y, type}, ...]}` |

**Point structure:**

```python
{
    "curveNumber": 0,
    "pointNumber": 5,
    "pointIndex": 5,
    "x": 2.5,
    "y": 10.3,
    "z": None,
    "text": "label",
    "customdata": {...},
    "data": {...},
    "trace_name": "Series A"
}
```

### Chart Updates (Python → JS)

| Event | Payload |
|-------|---------|
| `plotly:update-figure` | `{figure, chartId?, config?, animate?}` |
| `plotly:update-layout` | `{layout, chartId?}` |
| `plotly:update-traces` | `{update, indices, chartId?}` |
| `plotly:replace` | `{figure, chartId?}` |
| `plotly:reset-zoom` | `{chartId?}` |
| `plotly:request-state` | `{chartId?}` |
| `plotly:export-data` | `{chartId?}` |

---

## AG Grid Events (`grid:*`)

### User Interactions (JS → Python)

| Event | Payload |
|-------|---------|
| `grid:row-selected` | `{gridId, widget_type, rows}` |
| `grid:cell-click` | `{gridId, widget_type, rowIndex, colId, value, data}` |
| `grid:cell-double-click` | `{gridId, widget_type, rowIndex, colId, value, data}` |
| `grid:cell-edit` | `{gridId, widget_type, rowIndex, rowId, colId, oldValue, newValue, data}` |
| `grid:filter-changed` | `{gridId, widget_type, filterModel}` |
| `grid:sort-changed` | `{gridId, widget_type, sortModel}` |
| `grid:data-truncated` | `{gridId, widget_type, displayedRows, truncatedRows, message}` |
| `grid:mode` | `{gridId, widget_type, mode, serverSide, totalRows, blockSize, message}` |
| `grid:request-page` | `{gridId, widget_type, startRow, endRow, sortModel, filterModel}` |
| `grid:state-response` | `{gridId, columnState, filterModel, sortModel, context?}` |
| `grid:export-csv` | `{gridId, data}` |

### Grid Updates (Python → JS)

| Event | Payload |
|-------|---------|
| `grid:update-data` | `{data, gridId?, strategy?}` |
| `grid:update-columns` | `{columnDefs, gridId?}` |
| `grid:update-cell` | `{rowId, colId, value, gridId?}` |
| `grid:update-grid` | `{data?, columnDefs?, restoreState?, gridId?}` |
| `grid:request-state` | `{gridId?, context?}` |
| `grid:restore-state` | `{state, gridId?}` |
| `grid:reset-state` | `{gridId?, hard?}` |
| `grid:update-theme` | `{theme, gridId?}` |
| `grid:page-response` | `{gridId, rows, totalRows, isLastPage, requestId}` |
| `grid:show-notification` | `{message, duration?, gridId?}` |

**Update strategies for `grid:update-data`:** `set` (default — replace all), `append`, `update`

---

## Toolbar Events (`toolbar:*`)

### User Interactions (JS → Python)

| Event | Payload |
|-------|---------|
| `toolbar:collapse` | `{componentId, collapsed: true}` |
| `toolbar:expand` | `{componentId, collapsed: false}` |
| `toolbar:resize` | `{componentId, position, width, height}` |
| `toolbar:state-response` | `{toolbars, components, timestamp, context?}` |

### State Management (Python → JS)

| Event | Payload |
|-------|---------|
| `toolbar:request-state` | `{toolbarId?, componentId?, context?}` |
| `toolbar:set-value` | `{componentId, value?, label?, disabled?, ...attrs}` |
| `toolbar:set-values` | `{values: {id: value, ...}, toolbarId?}` |

**Supported attributes for `toolbar:set-value`:**

| Attribute | Description |
|-----------|-------------|
| `value` | Component value |
| `label` / `text` | Text content |
| `disabled` | Enable/disable |
| `variant` | Button style (`primary`, `danger`, etc.) |
| `tooltip` / `description` | Hover text |
| `options` | Dropdown options |
| `style` | Inline CSS (string or object) |
| `className` | CSS classes (`{add: [...], remove: [...]}`) |
| `placeholder`, `min`, `max`, `step` | Input constraints |

### Marquee Events (Python → JS)

| Event | Payload |
|-------|---------|
| `toolbar:marquee-set-content` | `{id, text?, html?, speed?, paused?, separator?}` |
| `toolbar:marquee-set-item` | `{ticker, text?, html?, styles?, class_add?, class_remove?}` |

---

## Component Event Payloads

Every toolbar component emits its custom event with these payloads:

| Component | Payload |
|-----------|---------|
| Button | `{componentId, ...data}` |
| Select | `{value, componentId}` |
| MultiSelect | `{values, componentId}` |
| TextInput | `{value, componentId}` |
| TextArea | `{value, componentId}` |
| SearchInput | `{value, componentId}` |
| SecretInput | `{value, componentId}` |
| NumberInput | `{value, componentId}` |
| DateInput | `{value, componentId}` (YYYY-MM-DD format) |
| SliderInput | `{value, componentId}` |
| RangeInput | `{start, end, componentId}` |
| Toggle | `{value, componentId}` (boolean) |
| Checkbox | `{value, componentId}` (boolean) |
| RadioGroup | `{value, componentId}` |
| TabGroup | `{value, componentId}` |

---

## JavaScript API

### The `window.pywry` Object

Every PyWry window/widget exposes a global bridge object:

```javascript
window.pywry = {
    emit(event, data),      // Send event to Python
    on(event, handler),     // Listen for events from Python
    off(event, handler),    // Remove event listener
    result(data),           // Send result to Python (triggers pywry:result)
    message(data),          // Send message to Python (triggers pywry:message)
    label,                  // Current window/widget label
    config,                 // Widget configuration
    version,                // PyWry version string
};
```

### Sending Events to Python

```javascript
window.pywry.emit("app:save", { id: 123 });

window.pywry.emit("app:update", {
    selection: [1, 2, 3],
    timestamp: Date.now(),
    metadata: { source: "user" }
});
```

### Listening for Python Events

```javascript
// Register handler
window.pywry.on("app:data-ready", function(data) {
    console.log("Data:", data);
});

// Remove handler
window.pywry.off("app:update", handler);
```

### Chart, Grid, and Toolbar Globals

```javascript
// Plotly charts
window.__PYWRY_CHARTS__["chart-id"]       // DOM element

// AG Grid instances
window.__PYWRY_GRIDS__["grid-id"]         // {api, div}
window.__PYWRY_GRIDS__["grid-id"].api.getSelectedRows()

// Toolbar state
window.__PYWRY_TOOLBAR__.getState()                     // All toolbars
window.__PYWRY_TOOLBAR__.getState("toolbar-id")         // Specific toolbar
window.__PYWRY_TOOLBAR__.getValue("component-id")       // Get value
window.__PYWRY_TOOLBAR__.setValue("component-id", value) // Set value
```

### Tauri Access (Native Mode Only)

In native desktop mode, Tauri APIs are available:

```javascript
if (window.__TAURI__) {
    const { invoke } = window.__TAURI__.core;
    const result = await invoke("my_command", { arg: "value" });
}
```

**Available Tauri Plugins:**

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
