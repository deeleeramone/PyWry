# Event Reference

Complete reference for all PyWry events, payloads, and the JavaScript bridge API.

## Event Format

All events follow the `namespace:event-name` pattern:

| Part | Rules | Examples |
|------|-------|----------|
| namespace | Starts with letter, alphanumeric | `app`, `plotly`, `grid`, `myapp` |
| event-name | Starts with letter, alphanumeric + hyphens | `click`, `row-select`, `update-data` |

**Reserved namespaces:** `pywry:*`, `plotly:*`, `grid:*`, `toolbar:*`, `auth:*`

---

## System Events (pywry:*)

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

## Plotly Events (plotly:*)

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

## AG Grid Events (grid:*)

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

## Toolbar Events (toolbar:*)

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

## Auth Events (auth:*)

The `auth:*` namespace is used by the built-in OAuth2 authentication system.
Events flow in both directions: the frontend can request login/logout, and the
backend notifies the frontend when auth state changes (e.g. after a token
refresh or successful logout).

!!! note "Availability"
    Auth events are only active when `PYWRY_DEPLOY__AUTH_ENABLED=true` and a
    valid `PYWRY_OAUTH2__*` configuration is present. In native mode the full
    flow is handled by `app.login()` / `app.logout()` — these events apply to
    the frontend integration via `window.pywry.auth`.

### Auth Requests (JS → Python)

| Event | Payload | Description |
|-------|---------|-------------|
| `auth:login-request` | `{}` | Frontend requests a login flow (calls `window.pywry.auth.login()`). In native mode the backend opens the provider's authorization URL; in deploy mode it redirects to `/auth/login`. |
| `auth:logout-request` | `{}` | Frontend requests logout (calls `window.pywry.auth.logout()`). The backend revokes tokens, destroys the session, and emits `auth:logout` back. |

### Auth Notifications (Python → JS)

| Event | Payload | Description |
|-------|---------|-------------|
| `auth:state-changed` | `{authenticated, user_id?, roles?, token_type?}` | Auth state changed (login succeeded or session expired). When `authenticated` is `false`, `window.__PYWRY_AUTH__` is cleared. |
| `auth:token-refresh` | `{token_type, expires_in?}` | Access token was refreshed in the background. Updates the current session without requiring re-login. |
| `auth:logout` | `{}` | Server-side logout completed. Clears `window.__PYWRY_AUTH__` and notifies registered `onAuthStateChange` handlers. |

**`auth:state-changed` payload detail:**

```python
{
    "authenticated": True,
    "user_id": "user@example.com",   # sub / id / email from userinfo
    "roles": ["viewer", "editor"],   # from session roles list
    "token_type": "Bearer"           # OAuth2 token type
}
```

When `authenticated` is `false` only the key itself is present:

```python
{"authenticated": False}
```

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

### The window.pywry Object

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

### Auth Globals (window.pywry.auth)

When `auth_enabled=True` the `auth-helpers.js` script is injected and the
`window.pywry.auth` namespace becomes available.

```javascript
// Check authentication state
window.pywry.auth.isAuthenticated()   // boolean

// Get the full auth state
window.pywry.auth.getState()
// Returns: { authenticated, user_id, roles, token_type }

// Trigger OAuth2 login flow (emits auth:login-request to Python)
window.pywry.auth.login()

// Trigger logout (emits auth:logout-request to Python)
window.pywry.auth.logout()

// React to auth state changes (from auth:state-changed / auth:logout events)
window.pywry.auth.onAuthStateChange(function(state) {
    if (state.authenticated) {
        console.log("Logged in as", state.user_id, "with roles", state.roles);
    } else {
        console.log("Logged out");
    }
});
```

**`window.__PYWRY_AUTH__`** is injected server-side for authenticated requests and
contains `{ user_id, roles, token_type }`. Use `window.pywry.auth.getState()`
rather than reading it directly — the helper normalizes the value and handles
the unauthenticated case.

### Tauri Access (Native Mode Only)

In native desktop mode, a subset of Tauri APIs and the PyTauri IPC bridge are available via `window.__TAURI__`. PyWry does **not** expose the full Tauri plugin ecosystem — only the APIs listed below are bundled and configured.

!!! warning "Do not use `window.__TAURI__.core.invoke()`"
    PyWry uses PyTauri for all JS → Python IPC. Call `window.__TAURI__.pytauri.pyInvoke()` instead of the standard Tauri `invoke()`. All registered [PyWry commands](#pytauri-commands) go through this path.

#### PyTauri Commands

All JS → Python communication uses `pyInvoke`:

```javascript
if (window.__TAURI__ && window.__TAURI__.pytauri) {
    // Send a custom event to Python
    window.__TAURI__.pytauri.pyInvoke('pywry_event', {
        label: window.__PYWRY_LABEL__ || 'main',
        event_type: 'app:my-action',
        data: { key: 'value' }
    });

    // Return a result to Python
    window.__TAURI__.pytauri.pyInvoke('pywry_result', {
        data: { answer: 42 },
        window_label: window.__PYWRY_LABEL__ || 'main'
    });
}
```

!!! tip "Prefer `window.pywry.emit()`"
    You rarely need to call `pyInvoke` directly. The `window.pywry.emit()` bridge wraps it for you and works across all rendering modes.

#### Available Tauri APIs

| API | Namespace | Used for |
|-----|-----------|----------|
| Event system | `window.__TAURI__.event` | Listening for Python → JS events (`listen`, `emit`) |
| Dialog | `window.__TAURI__.dialog` | Native save-file dialog (`save()`) |
| Filesystem | `window.__TAURI__.fs` | Writing files to disk (`writeTextFile()`) |
| PyTauri IPC | `window.__TAURI__.pytauri` | JS → Python calls (`pyInvoke()`) |

**Example — native save dialog:**

```javascript
if (window.__TAURI__ && window.__TAURI__.dialog && window.__TAURI__.fs) {
    const filePath = await window.__TAURI__.dialog.save({
        defaultPath: 'export.csv',
        title: 'Save File'
    });
    if (filePath) {
        await window.__TAURI__.fs.writeTextFile(filePath, csvContent);
    }
}
```

**Example — listening for Python events:**

```javascript
if (window.__TAURI__ && window.__TAURI__.event) {
    window.__TAURI__.event.listen('pywry:event', function(event) {
        // event.payload contains {type, data}
        console.log('Received:', event.payload.type, event.payload.data);
    });
}
```

!!! note "Tauri APIs are only available in native desktop mode"
    Check for `window.__TAURI__` before using any Tauri-specific API. In browser and notebook modes, only the `window.pywry` bridge is available — it abstracts the transport automatically.
