# Select

Dropdown for single-choice selection.

<div class="component-preview">
  <div class="pywry-input-group pywry-input-inline">
    <span class="pywry-input-label">Theme:</span>
    <div class="pywry-dropdown" id="select-demo" data-event="theme:change">
      <div class="pywry-dropdown-selected">
        <span class="pywry-dropdown-text">Dark</span>
        <span class="pywry-dropdown-arrow"></span>
      </div>
      <div class="pywry-dropdown-menu">
        <div class="pywry-select-options">
          <div class="pywry-dropdown-option pywry-selected" data-value="dark">Dark</div>
          <div class="pywry-dropdown-option" data-value="light">Light</div>
          <div class="pywry-dropdown-option" data-value="auto">Auto</div>
        </div>
      </div>
    </div>
  </div>
</div>

### Searchable

<div class="component-preview">
  <div class="pywry-input-group pywry-input-inline">
    <span class="pywry-input-label">Country:</span>
    <div class="pywry-dropdown pywry-searchable" id="select-search-demo" data-event="form:country">
      <div class="pywry-dropdown-selected">
        <span class="pywry-dropdown-text">United States</span>
        <span class="pywry-dropdown-arrow"></span>
      </div>
      <div class="pywry-dropdown-menu">
        <div class="pywry-select-header">
          <div class="pywry-search-wrapper pywry-search-inline">
            <svg class="pywry-search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="10" cy="10" r="7"/><line x1="15" y1="15" x2="21" y2="21"/></svg>
            <input type="text" class="pywry-input pywry-search-input" placeholder="Search..." value="">
          </div>
        </div>
        <div class="pywry-select-options">
          <div class="pywry-dropdown-option pywry-selected" data-value="us">United States</div>
          <div class="pywry-dropdown-option" data-value="uk">United Kingdom</div>
          <div class="pywry-dropdown-option" data-value="ca">Canada</div>
          <div class="pywry-dropdown-option" data-value="de">Germany</div>
          <div class="pywry-dropdown-option" data-value="fr">France</div>
          <div class="pywry-dropdown-option" data-value="jp">Japan</div>
        </div>
      </div>
    </div>
  </div>
</div>

```python
Select(
    label="Country",
    event="form:country",
    options=[
        Option(label="United States", value="us"),
        Option(label="United Kingdom", value="uk"),
        Option(label="Canada", value="ca"),
        Option(label="Germany", value="de"),
        Option(label="France", value="fr"),
        Option(label="Japan", value="jp"),
    ],
    selected="us",
    searchable=True,
)
```

## Complete Example

```python
from pywry import PyWry, Toolbar, Select, Option

app = PyWry()

def on_theme(data, event_type, label):
    app.emit("pywry:update-theme", {"theme": data["value"]}, label)
    app.emit("pywry:alert", {"message": f"Theme: {data['value']}", "type": "info"}, label)

toolbar = Toolbar(
    position="top",
    items=[
        Select(
            label="Theme",
            event="settings:theme",
            options=[
                Option(label="Light", value="light"),
                Option(label="Dark", value="dark"),
            ],
            selected="dark",
        ),
    ],
)

app.show("<h1>Settings</h1>", toolbars=[toolbar], callbacks={"settings:theme": on_theme})
app.block()
```

## Dynamic Options

Update dropdown options based on another selection:

```python
from pywry import PyWry, Toolbar, Select, Option

app = PyWry()

categories = {
    "fruits": ["Apple", "Banana", "Orange"],
    "vegetables": ["Carrot", "Broccoli", "Spinach"],
}

def on_category(data, event_type, label):
    items = categories.get(data["value"], [])
    app.emit("toolbar:set-value", {
        "componentId": "item-select",
        "options": [{"label": i, "value": i.lower()} for i in items],
        "value": items[0].lower() if items else None,
    }, label)

def on_item(data, event_type, label):
    app.emit("pywry:alert", {"message": f"Selected: {data['value']}"}, label)

toolbar = Toolbar(
    position="top",
    items=[
        Select(
            label="Category",
            event="form:category",
            options=[Option(label="Fruits", value="fruits"), Option(label="Vegetables", value="vegetables")],
            selected="fruits",
        ),
        Select(
            component_id="item-select",
            label="Item",
            event="form:item",
            options=[Option(label="Apple", value="apple"), Option(label="Banana", value="banana"), Option(label="Orange", value="orange")],
            selected="apple",
        ),
    ],
)

app.show("<h1>Selection</h1>", toolbars=[toolbar], callbacks={"form:category": on_category, "form:item": on_item})
app.block()
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
selected : str
    Currently selected value (default: "")
searchable : bool
    Enable a search input to filter dropdown options (default: False)
```

## Events

Emits the `event` name with payload:

```json
{"value": "dark", "componentId": "select-abc123"}
```

- `value` — the `value` string of the selected option

## API Reference

For complete parameter documentation, see the [Select API Reference](../reference/components/select.md).
