# Plotly Charts

PyWry provides first-class support for Plotly.js charts with automatic asset loading and event handling.

## Basic Usage

```python
import plotly.express as px
from pywry import PyWry

app = PyWry()

fig = px.scatter(
    x=[1, 2, 3, 4, 5],
    y=[1, 4, 9, 16, 25],
    title="Quadratic Function"
)

handle = app.show_plotly(fig)
```

## Plotly Configuration

Use `PlotlyConfig` to customize chart behavior:

```python
from pywry import PlotlyConfig

config = PlotlyConfig(
    responsive=True,
    scroll_zoom=True,
    display_mode_bar=True,  # True, False, or "hover"
    mode_bar_buttons_to_remove=["lasso2d", "select2d"],
)

handle = app.show_plotly(fig, config=config)
```

### PlotlyConfig Properties

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `responsive` | `bool` | `True` | Auto-resize with container |
| `static_plot` | `bool` | `False` | Disable interactivity |
| `scroll_zoom` | `bool` | `False` | Enable scroll wheel zoom |
| `display_mode_bar` | `bool \| str` | `"hover"` | Show mode bar |
| `display_logo` | `bool` | `False` | Show Plotly logo |
| `double_click` | `str` | `"reset+autosize"` | Double-click behavior |
| `editable` | `bool` | `False` | Allow editing titles/legends |
| `mode_bar_buttons_to_remove` | `list` | `None` | Hide specific buttons |
| `mode_bar_buttons_to_add` | `list` | `None` | Add custom buttons |

## Custom Mode Bar Buttons

Add custom buttons to the chart toolbar:

```python
from pywry import PlotlyConfig, ModeBarButton, SvgIcon

config = PlotlyConfig(
    mode_bar_buttons_to_add=[
        ModeBarButton(
            name="custom",
            title="Custom Action",
            icon=SvgIcon(path="M10 10 L90 90", width=100, height=100),
            click="function(gd) { window.pywry.emit('app:custom', {}); }"
        )
    ],
)
```

## Chart Events

Plotly charts emit events for user interactions:

```python
def on_click(data, event_type, label):
    point = data["points"][0]
    x, y = point["x"], point["y"]
    app.emit("pywry:alert", {"message": f"Clicked: ({x}, {y})"}, label)

def on_hover(data, event_type, label):
    point = data["points"][0]
    app.emit("pywry:set-content", {
        "id": "status",
        "text": f"Hovering: {point['x']}, {point['y']}"
    }, label)

def on_select(data, event_type, label):
    points = data.get("points", [])
    app.emit("pywry:alert", {"message": f"Selected {len(points)} points"}, label)

handle = app.show_plotly(
    fig,
    callbacks={
        "plotly:click": on_click,
        "plotly:hover": on_hover,
        "plotly:selected": on_select,
    },
)
```

### Available Events

| Event | Trigger | Payload |
|-------|---------|---------|
| `plotly:click` | Point clicked | `{ points, point_indices, chartId }` |
| `plotly:hover` | Point hovered | `{ points, point_indices, chartId }` |
| `plotly:unhover` | Mouse leaves point | `{ chartId }` |
| `plotly:selected` | Box/lasso selection | `{ points, range, chartId }` |
| `plotly:deselect` | Selection cleared | `{ chartId }` |
| `plotly:relayout` | Zoom/pan/resize | `{ relayout_data, chartId }` |

## Updating Charts

### Update Layout

```python
handle.emit("plotly:update-layout", {
    "layout": {
        "title": "Updated Title",
        "showlegend": False,
    }
})
```

### Update Traces

```python
handle.emit("plotly:update-traces", {
    "update": {"marker.color": "red"},
    "traceIndices": [0],
})
```

### Reset Zoom

```python
handle.emit("plotly:reset-zoom", {})
```

## With Toolbars

Add interactive controls:

```python
from pywry import Toolbar, Button, Select, Option

toolbar = Toolbar(
    position="top",
    items=[
        Select(
            event="chart:dataset",
            label="Dataset",
            options=[
                Option(label="Dataset A", value="a"),
                Option(label="Dataset B", value="b"),
            ],
            selected="a",
        ),
        Button(event="chart:reset", label="Reset Zoom"),
    ],
)

def on_dataset_change(data, event_type, label):
    dataset = data.get("value")
    # Load new data and update chart

def on_reset(data, event_type, label):
    handle.emit("plotly:reset-zoom", {})

handle = app.show_plotly(
    fig,
    toolbars=[toolbar],
    callbacks={
        "chart:dataset": on_dataset_change,
        "chart:reset": on_reset,
    },
)
```

## Multiple Charts

Display multiple charts using HTML layout:

```python
import plotly.express as px
from pywry import PyWry

app = PyWry()

fig1 = px.line(x=[1, 2, 3], y=[1, 2, 3], title="Linear")
fig2 = px.scatter(x=[1, 2, 3], y=[1, 4, 9], title="Quadratic")

html = f"""
<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; padding: 20px;">
    <div id="chart1"></div>
    <div id="chart2"></div>
</div>
<script>
    Plotly.newPlot('chart1', {fig1.to_json()});
    Plotly.newPlot('chart2', {fig2.to_json()});
</script>
"""

app.show(html, include_plotly=True)
```

## Theming

Charts automatically adapt to PyWry's theme:

```python
from pywry import PyWry, ThemeMode

app = PyWry(theme=ThemeMode.LIGHT)  # or ThemeMode.DARK

fig = px.scatter(x=[1, 2, 3], y=[1, 4, 9])
app.show_plotly(fig)  # Uses appropriate Plotly template
```

To change theme dynamically:

```python
handle.emit("pywry:update-theme", {"theme": "light"})
```
