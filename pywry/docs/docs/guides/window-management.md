# Window Management

PyWry supports multiple window modes for different use cases.

## Window Modes

### NEW_WINDOW (Default)

Each `show()` call creates a new window:

```python
from pywry import PyWry, WindowMode

app = PyWry(mode=WindowMode.NEW_WINDOW)

handle1 = app.show("<h1>Window 1</h1>", label="win1")
handle2 = app.show("<h1>Window 2</h1>", label="win2")
# Two separate windows open
```

### SINGLE_WINDOW

All content appears in the same window:

```python
from pywry import PyWry, WindowMode

app = PyWry(mode=WindowMode.SINGLE_WINDOW)

app.show("<h1>First Content</h1>")
app.show("<h1>Second Content</h1>")  # Replaces first
```

### MULTI_WINDOW

Create named windows that can be reused:

```python
from pywry import PyWry, WindowMode

app = PyWry(mode=WindowMode.MULTI_WINDOW)

app.show("<h1>Main</h1>", label="main")
app.show("<h1>Settings</h1>", label="settings")

# Update existing window by reusing label
app.show("<h1>Updated Main</h1>", label="main")
```

### BROWSER

Opens content in system browser instead of native window:

```python
from pywry import PyWry, WindowMode

app = PyWry(mode=WindowMode.BROWSER)

handle = app.show("<h1>Hello Browser!</h1>")
# Opens in default browser at http://localhost:8765/widget/{label}
```

### NOTEBOOK

For Jupyter notebook inline rendering (auto-detected):

```python
from pywry import PyWry, WindowMode

app = PyWry(mode=WindowMode.NOTEBOOK)

# Displays inline in notebook cell
app.show_plotly(fig)
```

## Window Labels

Every window/widget has a label for identification:

```python
# Explicit label
handle = app.show(content, label="my-window")

# Auto-generated label (UUID)
handle = app.show(content)

# Access label
label = handle.label  # "my-window" or auto-generated UUID
```

## Window Properties

Pass window properties directly to `show()`:

```python
handle = app.show(
    "<h1>Hello</h1>",
    title="My Application",
    width=1280,
    height=720,
)
```

### Available Properties

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `title` | `str` | `"PyWry"` | Window title |
| `width` | `int` | `800` | Window width in pixels |
| `height` | `int` | `600` | Window height in pixels |
| `label` | `str` | auto-generated | Unique identifier |

## Updating Content

```python
# Update entire content
handle.emit("pywry:update-html", {"html": "<h1>New Content</h1>"})

# Update specific element by ID
handle.emit("pywry:set-content", {"id": "title", "text": "Updated!"})

# Update by CSS selector
handle.emit("pywry:set-content", {"selector": "h1", "text": "Updated!"})
```

## Closing Windows

```python
# Close from Python
handle.close()

# Minimize/maximize
handle.minimize()
handle.maximize()
```

## Window Events

```python
def on_close(data, event_type, label):
    # Window closing - cleanup logic here
    pass

handle = app.show(
    content,
    callbacks={
        "pywry:close": on_close,
    },
)
```

## Multiple Windows Communication

Windows communicate through Python callbacks:

```python
windows = {}

def on_action(data, event_type, label):
    # Forward to another window
    other = windows.get("other")
    if other:
        other.emit("app:update", data)

windows["main"] = app.show(
    content1,
    label="main",
    callbacks={"app:action": on_action}
)
windows["other"] = app.show(content2, label="other")
```

## Blocking

Block the main thread until windows close:

```python
# Block indefinitely
app.block()

# Block with timeout (seconds)
app.block(timeout=60.0)
```
