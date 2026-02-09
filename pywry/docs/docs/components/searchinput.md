# SearchInput

A text input styled as a search box with a magnifying glass icon.

<div class="component-preview">
  <span class="pywry-input-group pywry-input-inline">
    <span class="pywry-input-label">Search:</span>
    <div class="pywry-search-wrapper">
      <svg class="pywry-search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="10" cy="10" r="7"/><line x1="15" y1="15" x2="21" y2="21"/></svg>
      <input type="text" class="pywry-input pywry-search-input" placeholder="Search items..." value="">
    </div>
  </span>
</div>

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
from pywry import PyWry, Toolbar, SearchInput

app = PyWry()

def on_search(data, event_type, label):
    query = data["value"].lower()
    # Filter AG Grid (requires AG Grid content)
    app.emit("grid:quick-filter", {"filter": query}, label)

app.show(
    "<h1>Data Table</h1>",
    toolbars=[
        Toolbar(position="top", items=[
            SearchInput(label="Filter", event="table:filter", placeholder="Filter rows...")
        ])
    ],
    callbacks={"table:filter": on_search},
)
```

### Search with Results Count

```python
from pywry import PyWry, Toolbar, SearchInput, Div

app = PyWry()

def on_search(data, event_type, label):
    query = data["value"]
    # Update results count display
    app.emit("pywry:set-content", {
        "selector": "#result-count",
        "html": f"Searching for: {query}" if query else "Enter search term"
    }, label)

app.show(
    "<h1>Search Demo</h1>",
    toolbars=[
        Toolbar(position="top", items=[
            SearchInput(label="Search", event="data:search"),
            Div(component_id="result-count", content="Enter search term"),
        ])
    ],
    callbacks={"data:search": on_search},
)
```

### Clear Button Pattern

```python
from pywry import PyWry, Toolbar, SearchInput, Button

app = PyWry()

def on_search(data, event_type, label):
    app.emit("pywry:alert", {"message": f"Searching: {data['value']}", "type": "info"}, label)

def on_clear(data, event_type, label):
    app.emit("toolbar:set-value", {
        "componentId": "search-box",
        "value": ""
    }, label)
    app.emit("pywry:alert", {"message": "Search cleared", "type": "info"}, label)

app.show(
    "<h1>Search with Clear</h1>",
    toolbars=[
        Toolbar(position="top", items=[
            SearchInput(component_id="search-box", label="Search", event="data:search"),
            Button(label="✕", event="search:clear", variant="neutral"),
        ])
    ],
    callbacks={"data:search": on_search, "search:clear": on_clear},
)
```

## Attributes

```
component_id : str | None
    Unique identifier for state tracking (auto-generated if not provided)
label : str | None
    Display label shown next to the search box
description : str | None
    Tooltip/hover text for accessibility and user guidance
event : str
    Event name emitted on input change (format: namespace:event-name)
style : str | None
    Optional inline CSS
disabled : bool
    Whether the input is disabled (default: False)
value : str
    Current search text value (default: "")
placeholder : str
    Placeholder text shown when empty (default: "Search...")
debounce : int
    Milliseconds to debounce input events (default: 300)
spellcheck : bool
    Enable browser spell checking (default: False)
autocomplete : str
    Browser autocomplete behavior (default: "off")
autocorrect : str
    Enable browser auto-correction: "on" or "off" (default: "off")
autocapitalize : str
    Control capitalization on mobile keyboards:
    "off", "none", "on", "sentences", "words", or "characters" (default: "off")
```

## Events

Emits the `event` name with payload:

```json
{"value": "search query", "componentId": "search-abc123"}
```

- `value` — current text content of the search input

## API Reference

For complete parameter documentation, see the [SearchInput API Reference](../reference/components/searchinput.md).
