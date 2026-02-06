# Rendering Paths

| Environment | Path | Return Type |
|-------------|------|-------------|
| Desktop/terminal | Native Window | `NativeWindowHandle` |
| Jupyter + anywidget | Notebook Widget | `PyWryWidget` |
| Jupyter (fallback) | Inline IFrame | `InlineWidget` |
| Headless/SSH | Browser Mode | `InlineWidget` |

## Native Window

```python
from pywry import PyWry, WindowMode

app = PyWry(
    mode=WindowMode.SINGLE_WINDOW,  # or NEW_WINDOW, MULTI_WINDOW
    theme="dark",
    width=1280,
    height=720,
)

handle = app.show("<h1 id='greeting'>Hello</h1>")
handle.emit("pywry:set-content", {"id": "greeting", "text": "Updated!"})
```

| Mode | Behavior |
|------|----------|
| `NEW_WINDOW` | New window each `show()` |
| `SINGLE_WINDOW` | Reuse one window |
| `MULTI_WINDOW` | Multiple labeled windows |

## Notebook Widget

```python
from pywry import PyWry
import plotly.express as px

app = PyWry()  # Auto-detects notebook
fig = px.scatter(px.data.iris(), x="sepal_width", y="sepal_length")

widget = app.show_plotly(fig, callbacks={"plotly:click": handler})
widget.emit("pywry:update-theme", {"theme": "plotly_white"})
```

Requires: `pip install 'pywry[notebook]'`

## Inline IFrame

Fallback when anywidget unavailable. Uses FastAPI server.

```python
from pywry.inline import show_plotly

widget = show_plotly(fig, callbacks={"plotly:click": handler})
```

## Browser Mode

For headless/SSH environments:

```python
from pywry import PyWry, WindowMode

app = PyWry(mode=WindowMode.BROWSER)
widget = app.show("<h1>Hello</h1>")
app.block()  # Keep server running
```

Opens in system browser with FastAPI backend.

## Common API

All return types implement `BaseWidget` protocol:

| Method | Description |
|--------|-------------|
| `emit(event, data)` | Send event to JS |
| `on(event, callback)` | Register callback |
| `update(html)` | Update content |
| `label` | Widget/window identifier |
