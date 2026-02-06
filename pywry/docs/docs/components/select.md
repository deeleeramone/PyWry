# Select

A dropdown menu for single-choice selection from a list of options.

## Basic Usage

```python
from pywry import Select, Option

theme_select = Select(
    label="Theme",
    event="settings:theme",
    options=[
        Option(label="Light", value="light"),
        Option(label="Dark", value="dark"),
        Option(label="System", value="system"),
    ],
    selected="dark",  # Default selection
)
```

## Options

Options are defined using the `Option` model:

```python
Option(
    label="Display Text",  # What the user sees
    value="internal_value", # What your code receives
)
```

### Dynamic Options

Build options from data:

```python
countries = ["USA", "Canada", "UK", "Germany", "Japan"]

country_select = Select(
    label="Country",
    event="form:country",
    options=[Option(label=c, value=c.lower()) for c in countries],
)
```

## Placeholder

Show placeholder text when nothing is selected:

```python
Select(
    label="Select a file",
    event="file:select",
    options=[...],
    placeholder="Choose file...",  # Shown when no selection
)
```

## Disabled State

```python
Select(
    label="Mode",
    event="app:mode",
    options=[...],
    disabled=True,  # Cannot be changed
)
```

## Common Patterns

### Dependent Selects

Chain selects where one depends on another:

```python
categories = {
    "fruits": ["Apple", "Banana", "Orange"],
    "vegetables": ["Carrot", "Broccoli", "Spinach"],
}

def on_category_change(data, event_type, label):
    category = data["value"]
    items = categories.get(category, [])
    
    # Update the items select with new options
    widget.emit("toolbar:set-value", {
        "componentId": "item-select",
        "options": [{"label": i, "value": i.lower()} for i in items],
    })

category_select = Select(
    label="Category",
    event="form:category",
    options=[
        Option(label="Fruits", value="fruits"),
        Option(label="Vegetables", value="vegetables"),
    ],
)

item_select = Select(
    component_id="item-select",
    label="Item",
    event="form:item",
    options=[],  # Initially empty
    placeholder="Select category first",
)
```

### With Search/Filter

For large option lists, consider [SearchInput](searchinput.md) + dynamic filtering.

## API Reference

For complete parameter documentation, see the [Select API Reference](../reference/components/select.md).
