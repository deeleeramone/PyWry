# MultiSelect

A dropdown that allows selecting multiple options from a list.

<div class="component-preview">
  <div class="pywry-input-group pywry-input-inline">
    <span class="pywry-input-label">Categories:</span>
    <div class="pywry-dropdown pywry-multiselect" id="multiselect-demo" data-event="columns:filter">
      <div class="pywry-dropdown-selected">
        <span class="pywry-dropdown-text">Technology, Finance</span>
        <span class="pywry-dropdown-arrow"></span>
      </div>
      <div class="pywry-dropdown-menu pywry-multiselect-menu">
        <div class="pywry-multiselect-header">
          <div class="pywry-search-wrapper pywry-search-inline">
            <svg class="pywry-search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="10" cy="10" r="7"/><line x1="15" y1="15" x2="21" y2="21"/></svg>
            <input type="text" class="pywry-input pywry-search-input" placeholder="Search..." value="">
          </div>
          <div class="pywry-multiselect-actions">
            <button type="button" class="pywry-multiselect-action" data-action="all">All</button>
            <button type="button" class="pywry-multiselect-action" data-action="none">None</button>
          </div>
        </div>
        <div class="pywry-multiselect-options">
          <label class="pywry-multiselect-option pywry-selected" data-value="tech">
            <input type="checkbox" class="pywry-multiselect-checkbox" value="tech" checked>
            <span class="pywry-multiselect-label">Technology</span>
          </label>
          <label class="pywry-multiselect-option pywry-selected" data-value="finance">
            <input type="checkbox" class="pywry-multiselect-checkbox" value="finance" checked>
            <span class="pywry-multiselect-label">Finance</span>
          </label>
          <label class="pywry-multiselect-option" data-value="health">
            <input type="checkbox" class="pywry-multiselect-checkbox" value="health">
            <span class="pywry-multiselect-label">Healthcare</span>
          </label>
          <label class="pywry-multiselect-option" data-value="energy">
            <input type="checkbox" class="pywry-multiselect-checkbox" value="energy">
            <span class="pywry-multiselect-label">Energy</span>
          </label>
        </div>
      </div>
    </div>
  </div>
</div>

## Basic Usage

```python
from pywry import MultiSelect, Option

categories = MultiSelect(
    label="Categories",
    event="filter:categories",
    options=[
        Option(label="Technology", value="tech"),
        Option(label="Finance", value="finance"),
        Option(label="Healthcare", value="health"),
        Option(label="Energy", value="energy"),
    ],
    selected=["tech", "finance"],  # Default selections
)
```

## Selected Values

```python
from pywry import MultiSelect, Option

MultiSelect(
    label="Tags",
    event="item:tags",
    options=[
        Option(label="Tag 1", value="tag1"),
        Option(label="Tag 2", value="tag2"),
    ],
    selected=["tag1"],  # Pre-selected values
)
```

## Select All Pattern

```python
from pywry import PyWry, Toolbar, MultiSelect, Option

app = PyWry()
options = [
    Option(label="All", value="all"),
    Option(label="Technology", value="tech"),
    Option(label="Finance", value="finance"),
    Option(label="Healthcare", value="health"),
]

def on_multi_change(data, event_type, label):
    selected = data.get("values", [])
    if "all" in selected:
        # "All" is selected - select everything
        all_values = [opt.value for opt in options if opt.value != "all"]
        app.emit("toolbar:set-value", {
            "componentId": "category-select",
            "value": all_values
        }, label)
    elif not selected:
        # Nothing selected
        app.emit("pywry:alert", {"message": "No categories selected", "type": "info"}, label)

app.show(
    "<h1>Category Filter</h1>",
    toolbars=[
        Toolbar(position="top", items=[
            MultiSelect(
                component_id="category-select",
                label="Categories",
                event="filter:categories",
                options=options,
            )
        ])
    ],
    callbacks={"filter:categories": on_multi_change},
)
```

## Tag Selection

```python
from pywry import MultiSelect, Option

tags = MultiSelect(
    label="Tags",
    event="post:tags",
    options=[
        Option(label="📊 Data", value="data"),
        Option(label="📈 Charts", value="charts"),
        Option(label="🔧 Tools", value="tools"),
        Option(label="📚 Tutorial", value="tutorial"),
    ],
)
```

## Attributes

```
component_id : str | None
    Unique identifier for state tracking (auto-generated if not provided)
label : str | None
    Display label shown next to the dropdown
description : str | None
    Tooltip/hover text for accessibility and user guidance
event : str
    Event name emitted on selection change (format: namespace:event-name)
style : str | None
    Optional inline CSS
disabled : bool
    Whether the dropdown is disabled (default: False)
options : list[Option]
    List of Option(label, value) items
selected : list[str]
    Currently selected values (default: [])
```

## Events

Emits the `event` name with payload:

```json
{"values": ["tech", "finance"], "componentId": "multiselect-abc123"}
```

- `values` — list of all currently selected values

## MultiSelect vs Select

| Component | Selection | Use Case |
|-----------|-----------|----------|
| Select | Single | Mutually exclusive choices |
| MultiSelect | Multiple | Filters, tags, permissions |

## API Reference

For complete parameter documentation, see the [MultiSelect API Reference](../reference/components/multiselect.md).
