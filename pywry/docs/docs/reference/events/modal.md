# Modal Events (modal:*)

The `modal:*` namespace controls modal dialog visibility. These events are **intercepted client-side** — they do not round-trip to Python.

## Modal Control (Python → JS or JS → JS)

| Event | Payload | Description |
|-------|---------|-------------|
| `modal:open:{id}` | `{}` | Open the modal with the given component ID. |
| `modal:close:{id}` | `{}` | Close the modal with the given component ID. |
| `modal:toggle:{id}` | `{}` | Toggle the modal open/closed. |

Send these via `handle.emit()` or use them as toolbar button events:

```python
# From Python
handle.emit("modal:open:settings-modal", {})

# As a toolbar button event (handled entirely client-side)
Button(label="⚙ Settings", event="modal:open:settings-modal")
```

## Modal Lifecycle (JS CustomEvents)

These are DOM `CustomEvent` objects dispatched on the document. Listen for them in custom JavaScript:

| Event | Detail | Description |
|-------|--------|-------------|
| `modal:opened` | `{modalId}` | Fired after a modal opens. Bubbles. |
| `modal:closed` | `{modalId, wasReset}` | Fired after a modal closes. `wasReset` indicates whether form fields were restored to initial values. |

```javascript
document.addEventListener("modal:opened", function(e) {
    console.log("Modal opened:", e.detail.modalId);
});
```
