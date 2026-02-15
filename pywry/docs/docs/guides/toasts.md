# Toasts & Alerts

Toasts are non-blocking notifications that appear in a corner of the window and auto-dismiss. PyWry includes five toast types — info, success, warning, error, and confirm — with a Python helper method and full event-based control.

## Sending a Toast

The simplest way is the `alert()` method, available on any widget handle:

```python
from pywry import PyWry

app = PyWry()
handle = app.show("<h1>Dashboard</h1>")

# Basic toast
handle.alert("File saved successfully")

# With type and title
handle.alert("Export complete", alert_type="success", title="Done")

# Warning with longer duration
handle.alert("API rate limit approaching", alert_type="warning", duration=8000)

# Error
handle.alert("Connection failed", alert_type="error", title="Network Error")
```

### Toast Types

| Type | Color | Auto-dismiss | Use case |
|:---|:---|:---|:---|
| `info` | Blue accent | Yes | General notifications |
| `success` | Green | Yes | Completed actions |
| `warning` | Orange/amber | Yes | Caution notices |
| `error` | Red | Yes | Failures, problems |
| `confirm` | Blue + overlay | No | Requires user response |

## Alert Parameters

The `alert()` method accepts these parameters:

| Parameter | Type | Default | Description |
|:---|:---|:---|:---|
| `message` | `str` | (required) | Toast body text |
| `alert_type` | `str` | `"info"` | One of `info`, `success`, `warning`, `error`, `confirm` |
| `title` | `str | None` | `None` | Optional header text |
| `duration` | `int` | `5000` | Auto-dismiss time in milliseconds |
| `callback_event` | `str | None` | `None` | Event emitted when confirm toast is acknowledged |
| `position` | `str` | `"top-right"` | Corner position |

### Positions

| Value | Placement |
|:---|:---|
| `"top-right"` | Top-right corner (default) |
| `"top-left"` | Top-left corner |
| `"bottom-right"` | Bottom-right corner |
| `"bottom-left"` | Bottom-left corner |

## Using Events Directly

You can also send toasts via the event system, which gives you the same control without the helper method:

```python
# From Python
handle.emit("pywry:alert", {
    "message": "Data refreshed",
    "type": "success",
    "title": "Updated",
    "duration": 3000,
})
```

```javascript
// From JavaScript
window.pywry.emit("pywry:alert", {
    message: "Item deleted",
    type: "warning",
});
```

## Confirm Toasts

Confirm toasts are different — they don't auto-dismiss and they block interaction with a backdrop overlay. The user must click **Confirm** or **Cancel**:

```python
def on_confirm(data, event_type, label):
    if data.get("confirmed"):
        # User clicked Confirm
        delete_item(data.get("item_id"))
        app.alert("Deleted", alert_type="success")
    else:
        # User clicked Cancel
        app.alert("Cancelled", alert_type="info")

handle = app.show(
    content,
    callbacks={"app:delete-confirm": on_confirm},
)

# Show confirmation
handle.alert(
    "Are you sure you want to delete this item?",
    alert_type="confirm",
    title="Confirm Deletion",
    callback_event="app:delete-confirm",
)
```

When the user responds:

- **Confirm** → emits `callback_event` with `{"confirmed": true}`
- **Cancel** → emits `callback_event` with `{"confirmed": false}`

## Toasts from Callbacks

A common pattern is showing feedback after an action:

```python
def on_save(data, event_type, label):
    try:
        save_data(data)
        app.alert("Changes saved", alert_type="success", title="Saved")
    except Exception as e:
        app.alert(str(e), alert_type="error", title="Save Failed")

def on_export(data, event_type, label):
    app.alert("Preparing export...", alert_type="info")
    result = export_csv(data)
    app.alert(f"Exported {result['rows']} rows", alert_type="success")
```

## Styling

Toast styles are controlled by CSS variables. Override them for custom appearance:

```css
:root {
    --pywry-toast-bg: #1e293b;
    --pywry-toast-color: #f1f5f9;
    --pywry-toast-accent: #3b82f6;
}

.pywry-theme-light {
    --pywry-toast-bg: #ffffff;
    --pywry-toast-color: #1e293b;
}
```

The toast container is always present in the DOM (injected by the toolbar layout system) even if no toolbars are defined.

## Next Steps

- **[Modals](modals.md)** — Blocking dialogs with form components
- **[Toolbar System](toolbars.md)** — Interactive components that trigger toasts
- **[Event System](events.md)** — How `pywry:alert` events are dispatched
- **[Theming & CSS](theming.md)** — Customize toast appearance
