# Menu Events (menu:*)

The `menu:*` namespace handles native OS menu item clicks from window menus, app menus, and tray menus.

!!! note "Availability"
    Menu events are only available in native desktop mode.

## Menu Interactions (Native → Python)

| Event | Payload | Description |
|-------|---------|-------------|
| `menu:click` | `{item_id, source?}` | A native menu item was clicked. `source` is `"tray"` for tray menu items, absent for window/app menus. |

Menu item handlers are typically registered via `MenuProxy` or `TrayProxy.from_config()` rather than listened for directly.
