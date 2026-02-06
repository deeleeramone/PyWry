# SearchInput

A text input styled as a search box with a magnifying glass icon.

## Basic Usage

```python
from pywry import SearchInput

search = SearchInput(
    label="Search",
    event="data:search",
    placeholder="Search items...",
)
```

## Common Patterns

### Filter Table Data

```python
def on_search(data, event_type, label):
    query = data["value"].lower()
    
    # Filter AG Grid
    widget.emit("grid:quick-filter", {
        "filter": query
    })

toolbar = Toolbar(
    position="top",
    items=[
        SearchInput(
            label="Filter",
            event="table:filter",
            placeholder="Filter rows...",
        ),
    ],
)
```

### Search with Results Count

```python
def on_search(data, event_type, label):
    query = data["value"]
    
    # Update results count display
    widget.emit("pywry:set-content", {
        "selector": "#result-count",
        "html": f"Searching for: {query}"
    })

toolbar = Toolbar(
    position="top",
    items=[
        SearchInput(label="Search", event="data:search"),
        Div(component_id="result-count", content="0 results"),
    ],
)
```

### Clear Button Pattern

```python
def on_clear(data, event_type, label):
    widget.emit("toolbar:set-value", {
        "componentId": "search-box",
        "value": ""
    })
    
    # Clear the grid filter
    widget.emit("grid:quick-filter", {"filter": ""})

toolbar = Toolbar(
    position="top",
    items=[
        SearchInput(
            component_id="search-box",
            label="Search",
            event="data:search",
        ),
        Button(label="✕", event="search:clear", variant="neutral"),
    ],
)
```

## API Reference

For complete parameter documentation, see the [SearchInput API Reference](../reference/components/searchinput.md).
