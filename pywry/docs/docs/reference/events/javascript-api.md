# JavaScript API

## The window.pywry Object

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

## Sending Events to Python

```javascript
window.pywry.emit("app:save", { id: 123 });

window.pywry.emit("app:update", {
    selection: [1, 2, 3],
    timestamp: Date.now(),
    metadata: { source: "user" }
});
```

## Listening for Python Events

```javascript
// Register handler
window.pywry.on("app:data-ready", function(data) {
    console.log("Data:", data);
});

// Remove handler
window.pywry.off("app:update", handler);
```

## Chart, Grid, and Toolbar Globals

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

## Auth Globals (window.pywry.auth)

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

## Tauri Access (Native Mode Only)

In native desktop mode, a subset of Tauri APIs and the PyTauri IPC bridge are available via `window.__TAURI__`. PyWry does **not** expose the full Tauri plugin ecosystem — only the APIs listed below are bundled and configured.

!!! warning "Do not use `window.__TAURI__.core.invoke()`"
    PyWry uses PyTauri for all JS → Python IPC. Call `window.__TAURI__.pytauri.pyInvoke()` instead of the standard Tauri `invoke()`. All registered PyWry commands go through this path.

### PyTauri Commands

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

### Available Tauri APIs

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
