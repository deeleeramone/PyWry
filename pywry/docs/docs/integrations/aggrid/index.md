# AG Grid

PyWry integrates [AG Grid](https://www.ag-grid.com/) — a high-performance JavaScript data grid — to render interactive tables with sorting, filtering, column resizing, row selection, cell editing, and pagination. The integration handles all data serialization, event bridging, and theme synchronization automatically.

AG Grid runs entirely in the browser. PyWry's role is to serialize your Python data (DataFrames, dicts, lists) into AG Grid's JSON format, inject the AG Grid library into the page, wire up events so user interactions flow back to Python, and keep the grid's theme in sync with PyWry's dark/light mode.

## How It Works

1. You pass a DataFrame (or list of dicts) to `show_dataframe()` or `TableArtifact`
2. PyWry calls `normalize_data()` which converts the data to `{rowData, columns, columnTypes}` — the format AG Grid expects
3. The AG Grid JavaScript library (~200KB gzipped) is injected into the page
4. `aggrid-defaults.js` registers event listeners on the grid instance that call `pywry.emit()` when the user clicks, selects, or edits cells
5. Your Python callbacks receive these events through the same `on()`/`emit()` protocol used by all PyWry components

The grid renders in all three environments — native windows, notebooks (anywidget or IFrame), and browser tabs — using the same code.

## Displaying a Grid

### From a DataFrame

```python
import pandas as pd
from pywry import PyWry

app = PyWry()

df = pd.DataFrame({
    "Symbol": ["AAPL", "MSFT", "GOOGL", "AMZN"],
    "Price": [189.84, 425.22, 176.49, 185.07],
    "Change": [1.23, -0.45, 0.89, -2.10],
    "Volume": [52_340_000, 18_920_000, 21_150_000, 45_670_000],
})

handle = app.show_dataframe(df)
```

### From a List of Dicts

```python
data = [
    {"name": "Alice", "role": "Engineer", "level": 3},
    {"name": "Bob", "role": "Designer", "level": 2},
]

handle = app.show_dataframe(data)
```

### Inside a Chat Response

```python
from pywry.chat.artifacts import TableArtifact

def handler(messages, ctx):
    yield TableArtifact(
        title="Portfolio",
        data=portfolio_df,
        height="320px",
    )
```

The AG Grid library is loaded lazily — it's only injected when the first grid is rendered.

## Data Normalization

`normalize_data()` accepts several input formats and converts them all to AG Grid's expected structure:

| Input | Example | Result |
|-------|---------|--------|
| pandas DataFrame | `pd.DataFrame({"a": [1, 2]})` | Columns from DataFrame columns, types auto-detected |
| List of dicts | `[{"a": 1}, {"a": 2}]` | Columns from dict keys, types inferred from values |
| Dict of lists | `{"a": [1, 2], "b": [3, 4]}` | Columns from dict keys |
| Single dict | `{"a": 1, "b": 2}` | Rendered as a two-column key/value table |

The normalizer also detects column types (`number`, `text`, `date`, `boolean`) and applies appropriate formatting defaults.

## Column Configuration

`ColDef` controls how individual columns render and behave:

```python
from pywry.grid import ColDef

columns = [
    ColDef(
        field="symbol",
        header_name="Ticker",
        sortable=True,
        filter=True,
        pinned="left",
        width=100,
    ),
    ColDef(
        field="price",
        header_name="Price",
        cell_data_type="number",
        value_formatter="'$' + value.toFixed(2)",
    ),
    ColDef(
        field="change",
        header_name="Change",
        cell_data_type="number",
        cell_style={"color": "params.value >= 0 ? '#a6e3a1' : '#f38ba8'"},
    ),
    ColDef(
        field="volume",
        header_name="Volume",
        value_formatter="value.toLocaleString()",
    ),
    ColDef(
        field="active",
        header_name="Active",
        editable=True,
        cell_renderer="agCheckboxCellRenderer",
    ),
]

handle = app.show_dataframe(df, column_defs=columns)
```

Key `ColDef` fields:

| Field | Type | Effect |
|-------|------|--------|
| `field` | `str` | Column key in the data |
| `header_name` | `str` | Display name in the header |
| `sortable` | `bool` | Allow clicking header to sort |
| `filter` | `bool` or `str` | Enable column filter (`True` for auto, or `"agTextColumnFilter"`, `"agNumberColumnFilter"`, etc.) |
| `editable` | `bool` | Allow inline cell editing |
| `width` | `int` | Fixed column width in pixels |
| `pinned` | `str` | Pin column to `"left"` or `"right"` |
| `cell_data_type` | `str` | `"number"`, `"text"`, `"date"`, `"boolean"` |
| `value_formatter` | `str` | JavaScript expression for display formatting |
| `cell_style` | `dict` | Conditional CSS styles |
| `cell_renderer` | `str` | AG Grid cell renderer component name |

For the complete list, see the [Grid Reference](grid.md).

## Grid Options

`GridOptions` controls grid-level behavior:

```python
from pywry.grid import GridOptions

options = GridOptions(
    pagination=True,
    pagination_page_size=25,
    row_selection={"mode": "multiRow", "enableClickSelection": True},
    animate_rows=True,
    suppress_column_virtualisation=True,
)

handle = app.show_dataframe(df, grid_options=options)
```

Key `GridOptions` fields:

| Field | Type | Effect |
|-------|------|--------|
| `pagination` | `bool` | Enable pagination |
| `pagination_page_size` | `int` | Rows per page |
| `row_selection` | `dict` | Selection mode configuration |
| `animate_rows` | `bool` | Animate row additions/removals |
| `default_col_def` | `dict` | Default properties for all columns |
| `suppress_column_virtualisation` | `bool` | Render all columns (not just visible ones) |

## Grid Events

AG Grid interactions produce events that your Python callbacks receive through the standard `on()`/`emit()` protocol:

```python
def on_row_selected(data, event_type, label):
    selected_rows = data.get("rows", [])
    symbols = [r["Symbol"] for r in selected_rows]
    app.emit("pywry:set-content", {
        "id": "selection",
        "text": f"Selected: {', '.join(symbols)}",
    }, label)

def on_cell_click(data, event_type, label):
    col = data["colId"]
    value = data["value"]
    row_index = data["rowIndex"]
    app.emit("pywry:set-content", {
        "id": "detail",
        "text": f"Row {row_index}: {col} = {value}",
    }, label)

def on_cell_edit(data, event_type, label):
    col = data["colId"]
    old_val = data["oldValue"]
    new_val = data["newValue"]
    row_data = data["data"]
    save_edit_to_database(row_data, col, new_val)

handle = app.show_dataframe(
    df,
    callbacks={
        "grid:row-selected": on_row_selected,
        "grid:cell-click": on_cell_click,
        "grid:cell-edit": on_cell_edit,
    },
)
```

Available grid events:

| Event | Payload Fields | When It Fires |
|-------|---------------|---------------|
| `grid:cell-click` | `colId`, `value`, `rowIndex`, `data` | User clicks a cell |
| `grid:cell-double-click` | `colId`, `value`, `rowIndex`, `data` | User double-clicks a cell |
| `grid:cell-edit` | `colId`, `oldValue`, `newValue`, `data` | User finishes editing a cell |
| `grid:row-selected` | `rows` (list of selected row dicts) | Row selection changes |
| `grid:sort-changed` | `columns` (list of sort state dicts) | User changes sort order |
| `grid:filter-changed` | `filterModel` (AG Grid filter model dict) | User changes column filters |

For complete payload structures, see the [Event Reference](../../reference/events/grid.md).

## Updating Grid Data

After the grid is displayed, update its data from Python:

```python
new_data = fetch_latest_prices()
handle.emit("grid:update-data", {"data": new_data})
```

The grid re-renders with the new data while preserving sort, filter, and selection state.

## Themes

AG Grid themes match PyWry's dark/light mode automatically:

```python
handle = app.show_dataframe(df, aggrid_theme="alpine")    # default
handle = app.show_dataframe(df, aggrid_theme="balham")
handle = app.show_dataframe(df, aggrid_theme="quartz")
handle = app.show_dataframe(df, aggrid_theme="material")
```

When the user switches PyWry's theme (via `pywry:update-theme`), the grid's CSS class is updated automatically — `ag-theme-alpine-dark` ↔ `ag-theme-alpine`.

## Embedding in Multi-Widget Pages

To place a grid alongside other components (charts, toolbars, etc.), generate the grid HTML directly:

```python
from pywry.grid import build_grid_config, build_grid_html

config = build_grid_config(df, grid_id="portfolio-grid", row_selection=True)
grid_html = build_grid_html(config)
```

Then compose it with `Div` and other components. The `grid_id` parameter lets you target the specific grid with events when multiple grids share a page. See [Multi-Widget Composition](../../guides/multi-widget.md) for the full pattern.

## With Toolbars

```python
from pywry import Toolbar, Button, TextInput

toolbar = Toolbar(
    position="top",
    items=[
        TextInput(event="grid:search", label="Search", placeholder="Filter rows..."),
        Button(event="grid:export", label="Export CSV"),
    ],
)

def on_search(data, event_type, label):
    query = data.get("value", "").lower()
    filtered = df[df.apply(lambda r: query in str(r.values).lower(), axis=1)]
    handle.emit("grid:update-data", {"data": filtered.to_dict("records")})

def on_export(data, event_type, label):
    handle.emit("pywry:download", {
        "filename": "portfolio.csv",
        "content": df.to_csv(index=False),
        "mimeType": "text/csv",
    })

handle = app.show_dataframe(
    df,
    toolbars=[toolbar],
    callbacks={
        "grid:search": on_search,
        "grid:export": on_export,
    },
)
```

## Next Steps

- **[Grid Reference](grid.md)** — Complete `ColDef`, `ColGroupDef`, `DefaultColDef`, `GridOptions` API
- **[Event Reference](../../reference/events/grid.md)** — All grid event payloads
- **[Multi-Widget Composition](../../guides/multi-widget.md)** — Embedding grids in dashboards
- **[Theming & CSS](../../components/theming.md)** — Styling and theme variables
