# Plotly

PyWry integrates [Plotly.js](https://plotly.com/javascript/) to render interactive charts — scatter plots, bar charts, line graphs, heatmaps, 3D surfaces, and every other Plotly chart type. The integration handles figure serialization, event bridging, theme synchronization, and programmatic updates automatically.

Plotly.js runs entirely in the browser. PyWry's role is to serialize your Python Plotly figure into JSON, inject the Plotly library into the page, wire up events so clicks, hovers, and selections flow back to Python, and keep the chart's template in sync with PyWry's dark/light mode.

## How It Works

1. You pass a Plotly `Figure` (or figure dict) to `show_plotly()` or `PlotlyArtifact`
2. PyWry converts the figure to a JSON dict via `fig.to_json()` (or uses it directly if already a dict)
3. The Plotly.js library (~1MB gzipped) is injected into the page
4. `plotly-defaults.js` registers event listeners on the chart element that call `pywry.emit()` when the user clicks, hovers, selects, or zooms
5. Your Python callbacks receive these events through the same `on()`/`emit()` protocol used by all PyWry components

Charts render in all three environments — native windows, notebooks (anywidget or IFrame), and browser tabs — using the same code.

## Displaying a Chart

### From a Plotly Figure

```python
import plotly.express as px
from pywry import PyWry

app = PyWry()

df = px.data.gapminder().query("year == 2007")
fig = px.scatter(
    df,
    x="gdpPercap",
    y="lifeExp",
    size="pop",
    color="continent",
    hover_name="country",
    log_x=True,
    title="GDP vs Life Expectancy (2007)",
)

handle = app.show_plotly(fig)
```

### From a Figure Dict

```python
figure = {
    "data": [
        {"type": "bar", "x": ["Q1", "Q2", "Q3", "Q4"], "y": [120, 180, 150, 210], "name": "Revenue"},
        {"type": "bar", "x": ["Q1", "Q2", "Q3", "Q4"], "y": [80, 90, 110, 130], "name": "Costs"},
    ],
    "layout": {
        "barmode": "group",
        "title": {"text": "Quarterly Financials"},
    },
}

handle = app.show_plotly(figure)
```

### Inside a Chat Response

```python
from pywry.chat.artifacts import PlotlyArtifact

def handler(messages, ctx):
    yield PlotlyArtifact(
        title="Revenue Trend",
        figure=fig.to_dict(),
        height="360px",
    )
```

The Plotly library is loaded lazily in chat — it's only injected when the first `PlotlyArtifact` is emitted.

## Chart Configuration

`PlotlyConfig` controls chart behavior — responsiveness, mode bar, scroll zoom, and custom toolbar buttons:

```python
from pywry import PlotlyConfig

config = PlotlyConfig(
    responsive=True,
    scroll_zoom=True,
    display_mode_bar="hover",
    mode_bar_buttons_to_remove=["lasso2d", "select2d", "toImage"],
)

handle = app.show_plotly(fig, config=config)
```

Key `PlotlyConfig` fields:

| Field | Type | Default | Effect |
|-------|------|---------|--------|
| `responsive` | `bool` | `True` | Chart resizes with container |
| `scroll_zoom` | `bool` | `True` | Mouse wheel zooms chart |
| `display_mode_bar` | `bool` or `str` | `True` | Mode bar visibility (`True`, `False`, `"hover"`) |
| `display_logo` | `bool` | `False` | Show Plotly logo in mode bar |
| `mode_bar_buttons_to_remove` | `list[str]` | `[]` | Remove standard buttons by name |
| `mode_bar_buttons_to_add` | `list[ModeBarButton]` | `[]` | Add custom buttons |
| `template_dark` | `dict` | `None` | Custom template overrides for dark mode |
| `template_light` | `dict` | `None` | Custom template overrides for light mode |

For the complete API, see [`PlotlyConfig`](plotly-config.md).

### Custom Mode Bar Buttons

Add buttons that fire events back to Python:

```python
from pywry import PlotlyConfig, ModeBarButton, SvgIcon

config = PlotlyConfig(
    mode_bar_buttons_to_add=[
        ModeBarButton(
            name="export-csv",
            title="Export Data as CSV",
            icon=SvgIcon(
                path="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z",
                width=24,
                height=24,
            ),
            event="chart:export-csv",
        ),
    ],
)

def on_export_csv(data, event_type, label):
    handle.emit("pywry:download", {
        "filename": "chart_data.csv",
        "content": df.to_csv(index=False),
        "mimeType": "text/csv",
    })

handle = app.show_plotly(fig, config=config, callbacks={"chart:export-csv": on_export_csv})
```

When `event` is set on a `ModeBarButton`, clicking the button calls `pywry.emit(event, {})` instead of requiring a raw JavaScript click handler.

## Chart Events

Plotly interactions produce events that your Python callbacks receive:

```python
def on_click(data, event_type, label):
    point = data["points"][0]
    country = point.get("hovertext", point.get("text", ""))
    x_val = point["x"]
    y_val = point["y"]
    app.emit("pywry:set-content", {
        "id": "detail",
        "html": f"<b>{country}</b><br/>GDP: ${x_val:,.0f}<br/>Life Exp: {y_val:.1f}",
    }, label)

def on_selection(data, event_type, label):
    selected = data.get("points", [])
    countries = [p.get("hovertext", "") for p in selected]
    filtered_df = df[df["country"].isin(countries)]
    handle.emit("pywry:set-content", {
        "id": "count",
        "text": f"{len(selected)} countries selected",
    })

def on_relayout(data, event_type, label):
    zoom_range = data.get("xaxis.range", [])
    if zoom_range:
        min_gdp, max_gdp = zoom_range
        # React to zoom changes

handle = app.show_plotly(
    fig,
    callbacks={
        "plotly:click": on_click,
        "plotly:selected": on_selection,
        "plotly:relayout": on_relayout,
    },
)
```

Available Plotly events:

| Event | Payload Fields | When It Fires |
|-------|---------------|---------------|
| `plotly:click` | `points` (list of clicked point dicts) | User clicks a data point |
| `plotly:hover` | `points` (list of hovered point dicts) | Mouse enters a data point |
| `plotly:unhover` | `points` | Mouse leaves a data point |
| `plotly:selected` | `points` (list of selected point dicts) | User completes a box/lasso selection |
| `plotly:deselect` | `{}` | User clears selection |
| `plotly:relayout` | Layout changes (axis ranges, etc.) | User zooms, pans, or resizes |
| `plotly:restyle` | Trace style changes | Trace visibility or style changes |

Each point dict in the `points` array contains `x`, `y`, `curveNumber`, `pointNumber`, `pointIndex`, and any custom `hovertext` or `text` fields from your traces.

For complete payload structures, see the [Event Reference](../../reference/events/plotly.md).

## Updating Charts

After the chart is displayed, update it from Python without re-rendering the entire page:

### Replace the Entire Figure

```python
new_fig = px.scatter(updated_df, x="gdpPercap", y="lifeExp")
handle.emit("plotly:update-figure", {"figure": new_fig.to_dict()})
```

This calls `Plotly.react()` under the hood — it diffs the old and new figures and applies only the changes, preserving zoom state when possible.

### Update Layout Only

```python
handle.emit("plotly:update-layout", {
    "layout": {
        "title": {"text": "Updated Title"},
        "xaxis": {"type": "log"},
        "showlegend": False,
    }
})
```

This calls `Plotly.relayout()` — it only touches layout properties, leaving trace data untouched.

### Update Trace Styles

```python
handle.emit("plotly:update-traces", {
    "update": {"marker.color": "red", "marker.size": 12},
    "traceIndices": [0],
})
```

### Reset Zoom

```python
handle.emit("plotly:reset-zoom", {})
```

## Theming

Charts automatically adapt to PyWry's dark/light mode. PyWry applies the built-in `plotly_dark` or `plotly_white` template based on the active theme.

To switch dynamically:

```python
handle.emit("pywry:update-theme", {"theme": "light"})
```

The chart re-renders with the appropriate Plotly template.

### Custom Per-Theme Templates

Override specific layout properties while keeping automatic theme switching:

```python
config = PlotlyConfig(
    template_dark={
        "layout": {
            "paper_bgcolor": "#1a1a2e",
            "plot_bgcolor": "#16213e",
            "font": {"color": "#e0e0e0"},
            "colorway": ["#89b4fa", "#a6e3a1", "#f9e2af", "#f38ba8"],
        }
    },
    template_light={
        "layout": {
            "paper_bgcolor": "#ffffff",
            "plot_bgcolor": "#f8f9fa",
            "font": {"color": "#222222"},
            "colorway": ["#1971c2", "#2f9e44", "#e8590c", "#c2255c"],
        }
    },
)

handle = app.show_plotly(fig, config=config)
```

Your overrides are deep-merged on top of the built-in base template. Values you set take precedence; everything else is inherited. Both templates are stored on the chart and automatically selected when the theme toggles.

Set only one side (e.g. `template_dark` alone) and the other theme uses the unmodified base.

## Embedding in Multi-Widget Pages

To place a chart alongside other components, generate the chart HTML directly:

```python
import json
from pywry.templates import build_plotly_init_script

chart_html = build_plotly_init_script(
    figure=json.loads(fig.to_json()),
    chart_id="revenue-chart",
)
```

Then compose with `Div` and pass `include_plotly=True` to `app.show()`. The `chart_id` lets you target the specific chart when multiple charts share a page:

```python
handle.emit("plotly:update-figure", {"figure": new_fig_dict, "chartId": "revenue-chart"})
```

See [Multi-Widget Composition](../../guides/multi-widget.md) for the full pattern.

## With Toolbars

```python
from pywry import Toolbar, Button, Select, Option

toolbar = Toolbar(
    position="top",
    items=[
        Select(
            event="chart:metric",
            label="Metric",
            options=[
                Option(label="GDP per Capita", value="gdpPercap"),
                Option(label="Population", value="pop"),
                Option(label="Life Expectancy", value="lifeExp"),
            ],
            selected="gdpPercap",
        ),
        Button(event="chart:reset", label="Reset Zoom"),
    ],
)

def on_metric_change(data, event_type, label):
    metric = data["value"]
    new_fig = px.scatter(df, x=metric, y="lifeExp", color="continent")
    handle.emit("plotly:update-figure", {"figure": new_fig.to_dict()})

def on_reset(data, event_type, label):
    handle.emit("plotly:reset-zoom", {})

handle = app.show_plotly(
    fig,
    toolbars=[toolbar],
    callbacks={
        "chart:metric": on_metric_change,
        "chart:reset": on_reset,
    },
)
```

## Next Steps

- **[`PlotlyConfig` Reference](plotly-config.md)** — All configuration options
- **[Event Reference](../../reference/events/plotly.md)** — Plotly event payloads
- **[Multi-Widget Composition](../../guides/multi-widget.md)** — Embedding charts in dashboards
- **[Theming & CSS](../../components/theming.md)** — Visual customization
