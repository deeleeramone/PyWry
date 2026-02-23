# pywry

Main PyWry application class and top-level functions.

---

## PyWry Class

::: pywry.app.PyWry
    options:
      show_root_heading: true
      heading_level: 2

---

## Inline Rendering Functions

These functions provide quick one-liner display for Plotly figures and DataFrames.

::: pywry.inline.show_plotly
    options:
      show_root_heading: true
      heading_level: 2

::: pywry.inline.show_dataframe
    options:
      show_root_heading: true
      heading_level: 2

::: pywry.inline.block
    options:
      show_root_heading: true
      heading_level: 2

---

## Menu & Tray

App-level convenience methods for native menus and tray icons.
See the [Native Menus](../guides/menus.md) and [System Tray](../guides/tray.md) guides.

The following methods are on the `PyWry` class (documented above via autodoc):

- `create_menu(menu_id, items)` → `MenuProxy`
- `create_tray(tray_id, ...)` → `TrayProxy`
- `remove_tray(tray_id)` — remove a tracked tray icon
- `set_initialization_script(js)` — set default init script for new windows
- `default_config` property — mutable `WindowConfig` with builder defaults

---

## Window Lifecycle

::: pywry.window_manager.get_lifecycle
    options:
      show_root_heading: true
      heading_level: 2
