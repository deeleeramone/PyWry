# Event System

Bidirectional Python ↔ JavaScript communication via namespaced events.

## Event Format

All events follow: `namespace:event-name`

| Part | Rules | Examples |
|------|-------|----------|
| namespace | Starts with letter, alphanumeric | `app`, `plotly`, `grid`, `myapp` |
| event-name | Starts with letter, alphanumeric + hyphens | `click`, `row-select`, `update_data` |

**Reserved namespaces:** `pywry:*`, `plotly:*`, `grid:*`, `toolbar:*`

## Handler Signature

```python
def handler(data: dict, event_type: str, label: str) -> None:
    """
    data: Event payload from JavaScript
    event_type: Event name (e.g., "plotly:click")
    label: Window/widget identifier
    """
    pass

# Shorter forms
def handler(data, event_type): pass
def handler(data): pass
```

## Registering Handlers

```python
# Option 1: callbacks dict (works everywhere)
app.show_plotly(fig, callbacks={"plotly:click": on_click})

# Option 2: app.on() (native mode only)
app.on("plotly:click", on_click, label="my-chart")
app.show_plotly(fig, label="my-chart")

# Option 3: widget.on() (all modes)
handle = app.show_plotly(fig)
handle.on("plotly:click", on_click)
```

## Sending Events

```python
# From Python to JavaScript
handle.emit("pywry:set-content", {"id": "msg", "text": "Updated!"})
app.emit("pywry:alert", {"message": "Hello"}, handle.label)
```

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

### Utility Events (Python → JS)

| Event | Payload | Description |
|-------|---------|-------------|
| `pywry:set-content` | `{id?, selector?, text?, html?}` | Update element text/HTML |
| `pywry:set-style` | `{id?, selector?, styles: {}}` | Update element CSS |
| `pywry:inject-css` | `{css, id?}` | Inject CSS (id for replacement) |
| `pywry:remove-css` | `{id}` | Remove injected CSS by id |
| `pywry:update-html` | `{html}` | Replace entire content |
| `pywry:update-theme` | `{theme}` | Switch theme (`plotly_dark`, `plotly_white`) |
| `pywry:alert` | `{message, type?, title?, duration?, position?, callback_event?}` | Toast notification |
| `pywry:download` | `{content, filename, mimeType?}` | Trigger file download |
| `pywry:navigate` | `{url}` | Navigate to URL |
| `pywry:refresh` | `{}` | Request content refresh |
| `pywry:cleanup` | `{}` | Cleanup resources (native mode) |

**Alert types:** `info`, `success`, `warning`, `error`, `confirm`

**Alert positions:** `top-right`, `top-left`, `bottom-right`, `bottom-left`

---

## Plotly Events (`plotly:*`)

### User Interactions (JS → Python)

| Event | Payload |
|-------|---------|
| `plotly:click` | `{chartId, widget_type, points, point_indices, curve_number, event}` |
| `plotly:hover` | `{chartId, widget_type, points, point_indices, curve_number}` |
| `plotly:selected` | `{chartId, widget_type, points, point_indices, range, lassoPoints}` |
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
| `plotly:reset-zoom` | `{chartId?}` |
| `plotly:request-state` | `{chartId?}` |
| `plotly:export-data` | `{chartId?}` |

---

## AgGrid Events (`grid:*`)

### User Interactions (JS → Python)

| Event | Payload |
|-------|---------|
| `grid:row-selected` | `{gridId, widget_type, rows}` |
| `grid:cell-click` | `{gridId, widget_type, rowIndex, colId, value, data}` |
| `grid:cell-edit` | `{gridId, widget_type, rowIndex, rowId, colId, oldValue, newValue, data}` |
| `grid:filter-changed` | `{gridId, widget_type, filterModel}` |
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

**Update strategies:** `set` (default, replace all), `append`, `update`

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
| `toolbar:set-value` | `{componentId, value, toolbarId?}` |
| `toolbar:set-values` | `{values: {id: value, ...}, toolbarId?}` |

### Marquee Events (Python → JS)

| Event | Payload |
|-------|---------|
| `toolbar:marquee-set-content` | `{id, text?, html?, speed?, paused?, separator?}` |
| `toolbar:marquee-set-item` | `{ticker, text?, html?, styles?, class_add?, class_remove?}` |

---

## Component Event Payloads

All toolbar components emit custom events with these payloads:

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
| DateInput | `{value, componentId}` (YYYY-MM-DD) |
| SliderInput | `{value, componentId}` |
| RangeInput | `{start, end, componentId}` |
| Toggle | `{value, componentId}` (bool) |
| Checkbox | `{value, componentId}` (bool) |
| RadioGroup | `{value, componentId}` |
| TabGroup | `{value, componentId}` |

---

## JavaScript API

### Sending Events to Python

```javascript
// Simple event
window.pywry.emit("app:save", { id: 123 });

// With complex data
window.pywry.emit("app:update", {
    selection: [1, 2, 3],
    timestamp: Date.now()
});

// Return result to Python
window.pywry.result({ computed: 42 });

// Send message to Python
window.pywry.message({ status: "processing" });
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

### Chart/Grid Access

```javascript
// Plotly charts
window.__PYWRY_CHARTS__["chart-id"]  // DOM element

// AG Grid instances
window.__PYWRY_GRIDS__["grid-id"]    // {api, div}
window.__PYWRY_GRIDS__["grid-id"].api.getSelectedRows()

// Toolbar state
window.__PYWRY_TOOLBAR__.getState()
window.__PYWRY_TOOLBAR__.getState("toolbar-id")
window.__PYWRY_TOOLBAR__.getValue("component-id")
window.__PYWRY_TOOLBAR__.setValue("component-id", value)
```

---

## Example

```python
from pywry import PyWry, Toolbar, Button, Select
import plotly.express as px

app = PyWry()
fig = px.scatter(px.data.iris(), x="sepal_width", y="sepal_length", color="species")

def on_click(data, event_type, label):
    point = data["points"][0]
    app.emit("plotly:update-layout", {
        "layout": {"title": f"Clicked: ({point['x']:.2f}, {point['y']:.2f})"}
    }, label)

def on_reset(data, event_type, label):
    app.emit("plotly:reset-zoom", {}, label)

def on_theme(data, event_type, label):
    theme = "plotly_dark" if data["value"] == "dark" else "plotly_white"
    app.emit("pywry:update-theme", {"theme": theme}, label)

toolbar = Toolbar(
    position="top",
    items=[
        Button(label="Reset Zoom", event="app:reset"),
        Select(label="Theme", event="app:theme", options=["light", "dark"], selected="dark"),
    ]
)

app.show_plotly(
    fig,
    toolbars=[toolbar],
    callbacks={
        "plotly:click": on_click,
        "app:reset": on_reset,
        "app:theme": on_theme,
    },
)
```
