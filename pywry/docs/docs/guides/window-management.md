# Window Modes

Every `app.show()` call needs to decide _where_ the content appears — a new OS window, the same window, a browser tab, or an inline notebook cell. PyWry uses five **window modes** to control this behavior.

## The Five Modes

| Mode | Enum value | What happens on each `show()` |
|:---|:---|:---|
| **New Window** | `WindowMode.NEW_WINDOW` | Opens a fresh native OS window every time |
| **Single Window** | `WindowMode.SINGLE_WINDOW` | Replaces content in one reusable window |
| **Multi Window** | `WindowMode.MULTI_WINDOW` | Opens or updates windows by label |
| **Browser** | `WindowMode.BROWSER` | Starts a local web server, opens system browser |
| **Notebook** | `WindowMode.NOTEBOOK` | Renders inline in a Jupyter notebook cell |

### Setting the Mode

```python
from pywry import PyWry, WindowMode

# At construction
app = PyWry(mode=WindowMode.SINGLE_WINDOW)

# Or via environment variable (before import)
# PYWRY_WINDOW__MODE=single_window
```

PyWry auto-detects Notebook mode when running inside Jupyter. For all other environments the default is `NEW_WINDOW`.

---

## NEW_WINDOW

Each `show()` call creates an independent native window. This is the default for scripts and CLI usage.

```python
app = PyWry(mode=WindowMode.NEW_WINDOW)

handle1 = app.show("<h1>Window 1</h1>", label="win1")
handle2 = app.show("<h1>Window 2</h1>", label="win2")
# Two separate OS windows appear
```

Use this when the user needs to see multiple pieces of content side-by-side, each with its own lifecycle.

## SINGLE_WINDOW

All content renders in the same window. Calling `show()` again replaces whatever was there before.

```python
app = PyWry(mode=WindowMode.SINGLE_WINDOW)

app.show("<h1>Loading...</h1>")
# ... fetch data ...
app.show("<h1>Dashboard</h1>")  # Replaces "Loading..."
```

Use this for a single-page-app experience where there's only ever one viewport.

## MULTI_WINDOW

Like `NEW_WINDOW`, but labels let you reuse existing windows. If a window with the given label already exists, its content is replaced instead of opening a new one.

```python
app = PyWry(mode=WindowMode.MULTI_WINDOW)

app.show("<h1>Main</h1>", label="main")
app.show("<h1>Settings</h1>", label="settings")

# Later — update the main window without opening a third one
app.show("<h1>Updated Main</h1>", label="main")
```

Use this for multi-panel applications where each panel has a stable identity.

## BROWSER

No native window is created. PyWry starts a FastAPI server in a background thread and opens the system browser to the widget URL. Communication happens over WebSocket.

```python
app = PyWry(mode=WindowMode.BROWSER)

handle = app.show("<h1>Hello Browser!</h1>")
# Browser opens http://127.0.0.1:8765/widget/{label}
```

Use this for SSH sessions, remote servers, Docker containers, or any environment without a display server. See [Browser Mode](../guides/browser-mode.md) for full details.

## NOTEBOOK

Content renders inline in a Jupyter notebook cell. PyWry uses **anywidget** for bidirectional traitlet sync when available, falling back to an IFrame + WebSocket bridge.

```python
# Usually auto-detected — no need to set explicitly
app = PyWry()  # detects Jupyter automatically

app.show_plotly(fig)  # Renders inline in the cell output
```

---

## Labels

Every window or widget has a **label** — a unique string identifier. You can set it explicitly or let PyWry generate a UUID.

```python
# Explicit label
handle = app.show(content, label="dashboard")

# Auto-generated (UUID)
handle = app.show(content)
print(handle.label)  # e.g., "a3f1c2d4-..."
```

Labels are used to:

- Target a specific window for content updates (`MULTI_WINDOW` mode)
- Identify the source window in event callbacks (`label` parameter)
- Construct widget URLs in browser mode (`/widget/{label}`)
- Route `handle.emit()` calls to the correct window

## Window Properties

Native windows accept layout properties through `show()`:

```python
handle = app.show(
    "<h1>My App</h1>",
    title="My Application",
    width=1280,
    height=720,
)
```

### WindowConfig Defaults

| Property | Type | Default | Description |
|:---|:---|:---|:---|
| `title` | `str` | `"PyWry"` | Window title bar text |
| `width` | `int` | `1280` | Window width in pixels |
| `height` | `int` | `720` | Window height in pixels |
| `min_width` | `int` | `400` | Minimum resize width |
| `min_height` | `int` | `300` | Minimum resize height |
| `theme` | `ThemeMode` | `DARK` | `LIGHT`, `DARK`, or `SYSTEM` |
| `center` | `bool` | `True` | Center window on screen |
| `resizable` | `bool` | `True` | Allow window resizing |
| `decorations` | `bool` | `True` | Show title bar and borders |
| `always_on_top` | `bool` | `False` | Keep above other windows |
| `devtools` | `bool` | `False` | Open browser DevTools on launch |

## The Window Handle

`app.show()` returns a handle object. In native mode this is a `WindowProxy` — a full-featured wrapper around the OS window. In browser/notebook mode it's an `InlineWidget` with a subset of the same interface.

### Common Methods (all modes)

| Method | Description |
|:---|:---|
| `handle.emit(event, data)` | Send an event from Python to the window's JavaScript |
| `handle.on(event, callback)` | Register a Python callback for events from the window |
| `handle.label` | The window/widget label |

### Native-only Methods (WindowProxy)

The `WindowProxy` exposes the full set of OS window operations:

**Window state:**

| Method | Description |
|:---|:---|
| `show()` / `hide()` | Toggle visibility |
| `close()` / `destroy()` | Close the window |
| `maximize()` / `unmaximize()` | Maximize or restore |
| `minimize()` / `unminimize()` | Minimize or restore |
| `center()` | Center on screen |
| `set_focus()` | Bring to front |
| `set_fullscreen(bool)` | Enter/exit fullscreen |
| `set_always_on_top(bool)` | Pin above other windows |

**Window properties:**

| Method | Description |
|:---|:---|
| `set_title(str)` | Change title bar text |
| `set_size(PhysicalSize)` | Resize window |
| `set_position(PhysicalPosition)` | Move window |
| `set_decorations(bool)` | Toggle title bar |
| `set_resizable(bool)` | Toggle resizing |
| `set_theme(ThemeMode)` | Change theme |

**Read-only properties:**

```python
handle.title            # Current title
handle.inner_size       # Content area size (PhysicalSize)
handle.outer_size       # Window frame size
handle.inner_position   # Content position on screen
handle.is_fullscreen    # bool
handle.is_maximized     # bool
handle.is_focused       # bool
handle.is_visible       # bool
handle.current_monitor  # Monitor info (name, size, position, scale)
```

**JavaScript execution:**

```python
# Fire-and-forget
handle.eval("document.title = 'Hello'")

# With return value (blocks up to timeout)
result = handle.eval_with_result("document.querySelectorAll('li').length", timeout=5.0)
```

## Updating Content

All modes support updating widget content through events:

```python
# Replace the entire page
handle.emit("pywry:update-html", {"html": "<h1>New Content</h1>"})

# Update a specific element by ID
handle.emit("pywry:set-content", {"id": "title", "text": "Updated!"})

# Update by CSS selector
handle.emit("pywry:set-content", {"selector": ".status", "html": "<b>Online</b>"})
```

## Multi-Window Communication

Windows are isolated — they don't share DOM or JavaScript state. Communication routes through Python callbacks:

```python
windows = {}

def on_action(data, event_type, label):
    # Forward data from "main" to "sidebar"
    sidebar = windows.get("sidebar")
    if sidebar:
        sidebar.emit("app:update", data)

windows["main"] = app.show(
    main_html,
    label="main",
    callbacks={"app:action": on_action},
)
windows["sidebar"] = app.show(sidebar_html, label="sidebar")
```

## Blocking

Scripts exit when the main thread ends. `app.block()` keeps the process alive until all windows close (or the user presses Ctrl+C):

```python
app.show("<h1>Hello</h1>")
app.block()  # Waits here until the window is closed
```

How blocking works depends on the mode:

- **Native modes** — polls `get_labels()` every 100ms until no windows remain
- **Browser mode** — monitors WebSocket disconnections; blocks until all widgets disconnect
- Both catch `KeyboardInterrupt` and call `app.destroy()` to clean up

```python
# Block until a specific window closes
app.block(label="main")
```
