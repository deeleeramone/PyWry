# Multi-Widget Pages

`show_plotly()` and `show_dataframe()` each render a single widget. To combine multiple widgets — charts, grids, forms, tickers — in one window, use `build_html()` to generate each piece and compose them with `Div`.

## The Pattern

1. **Generate HTML snippets** — `build_html()` on any component returns a self-contained HTML string.
2. **Compose with `Div`** — Nest `Div` objects to build your page tree. Style with CSS using `--pywry-*` theme variables.
3. **Show** — Pass combined HTML as `HtmlContent` to `app.show()` with `include_plotly` / `include_aggrid` flags as needed.

Every toolbar component (`Button`, `Select`, `Toggle`, `TextInput`, `Checkbox`, `RadioGroup`, `TabGroup`, `SliderInput`, `RangeInput`, `NumberInput`, `DateInput`, `SearchInput`, `SecretInput`, `TextArea`, `MultiSelect`, `Marquee`, `TickerItem`), plus `Toolbar`, `Modal`, and `Div` all expose `build_html()`. See the [Toolbar System](toolbars.md) and [Modals](modals.md) guides for their APIs.

---

## Widget Snippets

### Plotly

```python
import json
from pywry.templates import build_plotly_init_script

fig_dict = json.loads(fig.to_json())  # must be a plain dict, not a Figure
chart_html = build_plotly_init_script(figure=fig_dict, chart_id="my-chart")
```

Requires `include_plotly=True` on `app.show()`. Target later with `widget.emit("plotly:update-figure", {"figure": new_dict, "chartId": "my-chart"})`.

### AG Grid

```python
from pywry.grid import build_grid_config, build_grid_html

config = build_grid_config(df, grid_id="my-grid", row_selection=True)
grid_html = build_grid_html(config)
```

Requires `include_aggrid=True` on `app.show()`. Target later with `widget.emit("grid:update-data", {"data": rows, "gridId": "my-grid"})`.

Use unique `chart_id` / `grid_id` values when placing multiple charts or grids on the same page.

---

## Composing with `Div`

`Div` is the layout primitive. Use `content` for raw HTML (widget snippets, headings, text) and `children` for nested component objects. Both render in order: `content` first, then `children`.

```python
from pywry import Div, Button, Toggle

dashboard = Div(
    class_name="dashboard",
    children=[
        Div(class_name="kpi-row", children=[
            Div(class_name="kpi-card", content='<span class="label">Revenue</span><span class="value">$318K</span>'),
            Div(class_name="kpi-card", content='<span class="label">Users</span><span class="value">1,247</span>'),
        ]),
        Div(class_name="content-row", children=[
            Div(class_name="chart-panel", content=chart_html),
            Div(class_name="grid-panel", content=grid_html),
        ]),
        Div(class_name="controls", children=[
            Toggle(label="Live:", event="app:live", value=True),
            Button(label="Export", event="app:export", variant="secondary"),
        ]),
    ],
)

page_html = dashboard.build_html()
```

- `class_name` is added alongside the automatic `pywry-div` class — target it in CSS
- Nested `Div`s pass parent context via `data-parent-id` automatically

### Scripts

`Div` and `Toolbar` accept a `script` field (inline JS or file path). `build_html()` resolves it and emits a `<script>` tag inside the `<div>`:

```python
panel = Div(content="<p>Hello</p>", script="console.log('loaded');")
# → <div class="pywry-div" ...><p>Hello</p><script>console.log('loaded');</script></div>

panel = Div(content="<p>Chart</p>", script="static/chart_init.js")  # reads file
```

`collect_scripts()` is also available if you need raw script strings without HTML wrapping.

---

## Showing the Page

```python
from pywry import PyWry, HtmlContent

app = PyWry(title="Dashboard", width=1200, height=780)

content = HtmlContent(html=dashboard.build_html(), inline_css=css)

widget = app.show(
    content,
    include_plotly=True,
    include_aggrid=True,
    toolbars=[toolbar],    # optional positioned toolbar bars
    modals=[modal],        # optional modals
    callbacks={
        "plotly:click": on_chart_click,
        "grid:row-selected": on_row_selected,
        "app:export": on_export,
    },
)
```

- Components embedded directly in your HTML emit events via `window.pywry.emit()` without needing `toolbars=`
- Toolbars passed via `toolbars=` are auto-positioned (top, bottom, left, right)
- Modals passed via `modals=` are auto-injected with open/close wiring

### Sizing Tips

- Plotly: set `width: 100% !important; height: 100% !important` on `.pywry-plotly` and give its parent a flex layout
- AG Grid: needs a parent with defined height — `flex: 1` inside a flex column works
- Use `min-height: 0` on flex children that need to shrink below content size

---

## Cross-Widget Events

With everything in one page, wire interactions through callbacks — no JavaScript needed:

```python
# Grid selection → update chart
def on_row_selected(data, _event_type, _label):
    rows = data.get("rows", [])
    widget.emit("plotly:update-figure", {"figure": filtered_fig, "chartId": "my-chart"})

# Chart click → update detail panel
def on_chart_click(data, _event_type, _label):
    point = data.get("points", [{}])[0]
    widget.emit("pywry:set-content", {"id": "detail-panel", "html": f"<b>{point['x']}</b>"})

# Export CSV
def on_export(_data, _event_type, _label):
    widget.emit("pywry:download", {"content": df.to_csv(index=False), "filename": "data.csv", "mimeType": "text/csv"})
```

See the [Event System guide](events.md) for the full list of system events (`pywry:set-content`, `pywry:download`, `plotly:update-figure`, `grid:update-data`, etc.).

---

## Complete Example

See [`examples/pywry_demo_multi_widget.py`](https://github.com/deeleeramone/PyWry/blob/main/pywry/examples/pywry_demo_multi_widget.py) for a full working dashboard with KPI cards, Plotly chart, AG Grid, toolbar, cross-widget filtering, and CSV export.

---

## Related Guides

- [Toolbar System](toolbars.md) — all toolbar component types and their APIs
- [Modals](modals.md) — modal overlay components
- [Event System](events.md) — event registration and dispatch
- [Theming & CSS](theming.md) — `--pywry-*` variables and theme switching
- [HtmlContent](html-content.md) — CSS files, script files, inline CSS, JSON data
- [Content Assembly](content-assembly.md) — what PyWry injects into the document
