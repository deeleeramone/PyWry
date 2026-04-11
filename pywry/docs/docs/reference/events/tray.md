# Tray Events (tray:*)

The `tray:*` namespace handles system tray icon interactions. Events are dispatched on the synthetic label `__tray__{tray_id}`.

!!! note "Availability"
    Tray events are only available in native desktop mode. Requires a `TrayIconConfig` or `TrayProxy` setup.

## Icon Interactions (Native → Python)

| Event | Payload | Description |
|-------|---------|-------------|
| `tray:click` | `{tray_id, button, button_state, position?}` | Single click on the tray icon. |
| `tray:double-click` | `{tray_id, button, position?}` | Double-click on the tray icon. |
| `tray:right-click` | `{tray_id, position?}` | Right-click on the tray icon. |
| `tray:enter` | `{tray_id, position?}` | Cursor enters tray icon area. |
| `tray:leave` | `{tray_id, position?}` | Cursor leaves tray icon area. |
| `tray:move` | `{tray_id, position?}` | Cursor moves over tray icon area. |

**`button` values:** `"Left"`, `"Right"`, `"Middle"`

**`button_state` values:** `"Up"`, `"Down"`

**Position structure (when present):**

```python
{"x": float, "y": float}
```
