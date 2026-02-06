# InlineWidget

The `InlineWidget` class powers browser-based rendering in PyWry. It runs a FastAPI server and serves widgets via IFrame, enabling Jupyter notebooks, browser tabs, and multi-user deployments.

## Import

```python
from pywry.inline import InlineWidget
```

Or use the helper functions:

```python
from pywry.inline import show, show_plotly, show_dataframe
```

## Class Signature

```python
class InlineWidget(GridStateMixin, PlotlyStateMixin, ToolbarStateMixin):
    def __init__(
        self,
        widget_id: str,
        html: str,
        width: str = "100%",
        height: str = "500px",
        callbacks: dict[str, Callable] | None = None,
    ) -> None: ...
```

## Properties

| Property | Type | Description |
|----------|------|-------------|
| `widget_id` | `str` | Unique identifier for this widget |
| `label` | `str` | Alias for `widget_id` (protocol consistency) |
| `url` | `str` | Full URL to access the widget |
| `output` | `Output` | IPython Output widget for callback messages |

## Core Methods

### emit()

Send an event from Python to JavaScript.

```python
def emit(self, event_type: str, data: dict[str, Any]) -> None: ...
```

**Example:**
```python
widget.emit("pywry:alert", {"message": "Updated!", "type": "success"})
widget.emit("pywry:set-content", {"id": "counter", "text": "42"})
```

### on()

Register a callback for events from JavaScript.

```python
def on(
    self, event_type: str, 
    callback: Callable[[dict[str, Any], str, str], Any]
) -> InlineWidget: ...
```

**Example:**
```python
def handle_click(data, event_type, widget_id):
    widget.emit("pywry:set-content", {"id": "status", "text": f"Clicked: {data}"})

widget.on("button:click", handle_click)
```

### alert()

Show a toast notification.

```python
def alert(
    self,
    message: str,
    alert_type: str = "info",  # info, success, warning, error, confirm
    title: str | None = None,
    duration: int | None = None,
    callback_event: str | None = None,
    position: str = "top-right",
) -> None: ...
```

**Example:**
```python
widget.alert("Operation complete", alert_type="success")
widget.alert("Are you sure?", alert_type="confirm", callback_event="confirm:result")
```

### update() / update_html()

Update the widget's HTML content.

```python
def update(self, html: str) -> None: ...
def update_html(self, html: str) -> None: ...  # alias
```

### open_in_browser()

Open the widget in a new browser tab.

```python
widget.open_in_browser()
```

### display()

Display in Jupyter with IFrame and Output widget.

```python
widget.display()
```

## Plotly Methods

Inherited from `PlotlyStateMixin`:

### update_figure()

Update a Plotly chart without page reload.

```python
def update_figure(
    self,
    figure: Figure | dict[str, Any],
    chart_id: str | None = None,
    animate: bool = False,
    config: dict[str, Any] | None = None,
) -> None: ...
```

**Example:**
```python
import plotly.express as px
new_fig = px.line(updated_data, x="date", y="value")
widget.update_figure(new_fig)
```

## Grid Methods

Inherited from `GridStateMixin`:

### update_data()

Update grid rows.

```python
def update_data(
    self,
    data: list[dict[str, Any]],
    grid_id: str | None = None,
    strategy: str = "set",  # set, append, update
) -> None: ...
```

### update_cell()

Update a single cell.

```python
def update_cell(
    self,
    row_id: str | int,
    col_id: str,
    value: Any,
    grid_id: str | None = None,
) -> None: ...
```

### update_columns()

Update column definitions.

```python
def update_columns(
    self,
    column_defs: list[dict[str, Any]],
    grid_id: str | None = None,
) -> None: ...
```

### update_grid()

Update data, columns, and/or restore state in one call.

```python
def update_grid(
    self,
    data: list[dict[str, Any]] | None = None,
    columns: list[dict[str, Any]] | None = None,
    restore_state: dict[str, Any] | None = None,
    grid_id: str | None = None,
) -> None: ...
```

### request_grid_state()

Request grid state (triggers `grid:state-response` callback).

```python
def request_grid_state(
    self, context: dict[str, Any] | None = None, 
    grid_id: str | None = None
) -> None: ...
```

### restore_state()

Restore a previously saved grid state.

```python
def restore_state(self, state: dict[str, Any], grid_id: str | None = None) -> None: ...
```

### reset_state()

Reset grid to default state.

```python
def reset_state(self, grid_id: str | None = None, hard: bool = False) -> None: ...
```

## Toolbar Methods

Inherited from `ToolbarStateMixin`:

### request_toolbar_state()

Request toolbar component values.

```python
def request_toolbar_state(
    self, toolbar_id: str | None = None, 
    context: dict[str, Any] | None = None
) -> None: ...
```

## Helper Functions

### show()

Create an InlineWidget from HTML.

```python
from pywry.inline import show

widget = show(
    "<h1>Hello World</h1>",
    width="100%",
    height="400px",
    callbacks={"click": my_handler},
)
```

### show_plotly()

Create an InlineWidget with a Plotly chart.

```python
from pywry.inline import show_plotly
import plotly.express as px

fig = px.bar(df, x="category", y="value")
widget = show_plotly(fig, title="Sales Chart", height=500)
```

### show_dataframe()

Create an InlineWidget with an AG Grid table.

```python
from pywry.inline import show_dataframe

widget = show_dataframe(df, title="Data Table", height=600)
```

## Server Functions

### block()

Block until all widgets disconnect (for scripts).

```python
from pywry.inline import block

widget = show("<h1>Hello</h1>")
widget.open_in_browser()
block()  # Wait until browser tab closed
```

### deploy()

Run as production server.

```python
from pywry.inline import deploy, get_server_app

app = get_server_app()

@app.get("/chart")
def chart():
    return HTMLResponse(get_widget_html("my-chart"))

deploy()
```

### get_widget_html()

Get widget HTML by ID.

```python
from pywry.inline import get_widget_html

html = get_widget_html(widget.label)
```

### get_widget_url()

Get widget URL with configured prefix.

```python
from pywry.inline import get_widget_url

url = get_widget_url(widget.label)  # "/widget/abc123"
```

### stop_server()

Stop the FastAPI server.

```python
from pywry.inline import stop_server

stop_server(timeout=5.0)
```

## Complete Example

```python
from pywry.inline import show_plotly
from pywry.toolbar import Toolbar, Button, Select, Option
import plotly.express as px

# Create figure
df = px.data.gapminder().query("year == 2007")
fig = px.scatter(df, x="gdpPercap", y="lifeExp", color="continent")

# Create with toolbar
toolbar = Toolbar(
    position="top",
    items=[
        Select(
            label="Continent",
            event="filter:continent",
            options=[Option(label="All", value="all")] + 
                    [Option(label=c, value=c) for c in df["continent"].unique()],
        ),
        Button(label="Reset", event="chart:reset", variant="neutral"),
    ],
)

widget = show_plotly(fig, title="GDP vs Life Expectancy", toolbars=[toolbar])

def on_filter(data, event_type, widget_id):
    continent = data.get("value", "all")
    if continent == "all":
        filtered = df
    else:
        filtered = df[df["continent"] == continent]
    new_fig = px.scatter(filtered, x="gdpPercap", y="lifeExp", color="continent")
    widget.update_figure(new_fig)

widget.on("filter:continent", on_filter)
```
