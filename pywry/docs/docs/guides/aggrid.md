# AgGrid Tables

PyWry provides first-class support for AG Grid with automatic asset loading and event handling.

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

### ColDef Properties

| Property | Type | Description |
|----------|------|-------------|
| `field` | `str` | Column data field |
| `header_name` | `str` | Display header |
| `width` | `int` | Column width in pixels |
| `min_width` | `int` | Minimum column width |
| `max_width` | `int` | Maximum column width |
| `flex` | `int` | Flex sizing factor |
| `sortable` | `bool` | Enable sorting |
| `filter` | `bool \| str` | Enable filtering |
| `editable` | `bool` | Allow editing |
| `resizable` | `bool` | Allow resizing |
| `pinned` | `str` | Pin to `"left"` or `"right"` |
| `hide` | `bool` | Hide column |
| `value_formatter` | `str` | JS expression for formatting |
| `value_getter` | `str` | JS expression for value |
| `cell_renderer` | `str` | Custom cell renderer |
| `cell_class` | `str \| list` | CSS class for cells |
| `cell_style` | `dict` | Inline styles for cells |
| `cell_data_type` | `str` | Data type hint |

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

### GridOptions Properties

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `pagination` | `bool` | `None` | Enable pagination |
| `pagination_page_size` | `int` | `100` | Rows per page |
| `row_selection` | `dict \| bool` | `None` | Row selection config |
| `cell_selection` | `bool` | `True` | Enable cell selection |
| `animate_rows` | `bool` | `True` | Animate row changes |
| `single_click_edit` | `bool` | `None` | Edit on single click |
| `undo_redo_cell_editing` | `bool` | `True` | Enable undo/redo |
| `dom_layout` | `str` | `"normal"` | Layout mode |
| `default_col_def` | `dict` | `None` | Default column properties |

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

### Available Events

| Event | Trigger | Payload |
|-------|---------|---------|
| `grid:row-selected` | Row selection changes | `{ rows, gridId }` |
| `grid:cell-click` | Cell clicked | `{ rowIndex, colId, value, data, gridId }` |
| `grid:cell-double-click` | Cell double-clicked | `{ rowIndex, colId, value, data, gridId }` |
| `grid:cell-edit` | Cell edited | `{ rowId, colId, oldValue, newValue, gridId }` |
| `grid:filter-changed` | Filter applied | `{ filterModel, gridId }` |
| `grid:sort-changed` | Sort applied | `{ sortModel, gridId }` |

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

Add interactive controls above the grid:

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
