# AG Grid Tables

PyWry provides first-class AG Grid support — pass a Pandas DataFrame to `show_dataframe()` and get sortable, filterable, editable data tables with pre-wired events.

For the complete column and grid configuration API, see the [Grid Reference](../reference/grid.md). For all grid events and payloads, see the [Event Reference](../reference/events.md#ag-grid-events-grid).

## Basic Usage

```python
import pandas as pd
from pywry import PyWry

app = PyWry()

df = pd.DataFrame({
    "Name": ["Alice", "Bob", "Charlie"],
    "Age": [25, 30, 35],
    "City": ["NYC", "LA", "Chicago"],
})

# Display the grid
handle = app.show_dataframe(df)
```

## Column Configuration

Use `ColDef` for detailed column configuration:

```python
from pywry.grid import ColDef

columns = [
    ColDef(field="name", header_name="Full Name", sortable=True, filter=True),
    ColDef(field="age", header_name="Age", width=100, cell_data_type="number"),
    ColDef(field="salary", value_formatter="'$' + value.toLocaleString()"),
    ColDef(field="active", editable=True, cell_renderer="agCheckboxCellRenderer"),
]

handle = app.show_dataframe(df, column_defs=columns)
```

For the full list of `ColDef` properties, see the [Grid Reference](../reference/grid.md).

## Grid Options

Use `GridOptions` for global grid configuration:

```python
from pywry.grid import GridOptions, RowSelection

options = GridOptions(
    pagination=True,
    pagination_page_size=25,
    row_selection={"mode": "multiRow", "enableClickSelection": True},
    animate_rows=True,
)

handle = app.show_dataframe(df, grid_options=options)
```

For the full list of `GridOptions` properties, see the [Grid Reference](../reference/grid.md).

## Grid Events

AgGrid emits events for user interactions:

```python
def on_row_selected(data, event_type, label):
    rows = data.get("rows", [])
    app.emit("pywry:alert", {"message": f"Selected {len(rows)} rows"}, label)

def on_cell_click(data, event_type, label):
    app.emit("pywry:set-content", {
        "id": "status",
        "text": f"{data['colId']} = {data['value']}"
    }, label)

def on_cell_edit(data, event_type, label):
    app.emit("pywry:alert", {
        "message": f"Edited {data['colId']}: {data['oldValue']} → {data['newValue']}"
    }, label)

handle = app.show_dataframe(
    df,
    callbacks={
        "grid:row-selected": on_row_selected,
        "grid:cell-click": on_cell_click,
        "grid:cell-edit": on_cell_edit,
    },
)
```

For the complete list of grid events and payload structures, see the [Event Reference](../reference/events.md#ag-grid-events-grid).

## Updating Grid Data

### Replace All Data

```python
new_df = pd.DataFrame({...})
handle.emit("grid:update-data", {"data": new_df.to_dict("records")})
```

## Themes

Available AG Grid themes:

```python
handle = app.show_dataframe(df, aggrid_theme="alpine")  # default
handle = app.show_dataframe(df, aggrid_theme="balham")
handle = app.show_dataframe(df, aggrid_theme="material")
```

Themes automatically adapt to PyWry's light/dark mode.

## With Toolbars

```python
from pywry import Toolbar, Button, TextInput

toolbar = Toolbar(
    position="top",
    items=[
        TextInput(event="grid:search", label="Search", placeholder="Filter..."),
        Button(event="grid:export", label="Export CSV"),
    ],
)

def on_search(data, event_type, label):
    query = data.get("value", "")
    # Filter logic here

def on_export(data, event_type, label):
    handle.emit("pywry:download", {
        "filename": "data.csv",
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

- **[Grid Reference](../reference/grid.md)** — Full `ColDef`, `GridOptions` API
- **[Event Reference](../reference/events.md#ag-grid-events-grid)** — All grid event payloads
- **[Toolbar System](toolbars.md)** — Building interactive controls
- **[Theming & CSS](theming.md)** — Styling the grid
