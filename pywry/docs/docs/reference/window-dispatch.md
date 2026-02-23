# pywry.window_dispatch

Low-level window property getters and method dispatchers for the PyTauri subprocess.

Dispatches window operations across eight categories: visibility, state,
property setters, size/position, appearance, cursor, behavior, and webview
methods.  Phase 2 added `start_dragging`, `set_skip_taskbar`, `set_icon`,
`set_badge_count`, and `set_overlay_icon` handlers.

---

::: pywry.window_dispatch.get_window_property
    options:
      show_root_heading: true
      heading_level: 2

::: pywry.window_dispatch.call_window_method
    options:
      show_root_heading: true
      heading_level: 2

---

## Dispatch Categories

All dispatchable methods are grouped into these sets (exported for testing):

| Category | Examples |
|:---|:---|
| `VISIBILITY_METHODS` | `show`, `hide`, `set_focus`, `set_visible`, `start_dragging` |
| `STATE_METHODS` | `minimize`, `maximize`, `unmaximize`, `toggle_maximize`, `set_fullscreen` |
| `PROPERTY_METHODS` | `set_title`, `set_decorations`, `set_resizable`, `set_always_on_top`, `set_skip_taskbar` |
| `SIZE_POSITION_METHODS` | `set_size`, `set_min_size`, `set_max_size`, `set_position`, `center` |
| `APPEARANCE_METHODS` | `set_shadow`, `set_effects`, `set_progress_bar`, `set_icon`, `set_badge_count`, `set_overlay_icon` |
| `CURSOR_METHODS` | `set_cursor_icon`, `set_cursor_position`, `set_cursor_visible`, `set_cursor_grab` |
| `BEHAVIOR_METHODS` | `set_ignore_cursor_events`, `set_content_protected`, `request_user_attention`, `set_title_bar_style` |
| `WEBVIEW_METHODS` | `navigate`, `eval`, `open_devtools`, `close_devtools`, `reload`, `zoom`, `print` |
