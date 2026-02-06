# MultiSelect

A dropdown that allows selecting multiple options from a list.

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

## Placeholder

```python
from pywry import MultiSelect, Option

MultiSelect(
    label="Tags",
    event="item:tags",
    options=[
        Option(label="Tag 1", value="tag1"),
        Option(label="Tag 2", value="tag2"),
    ],
    placeholder="Select tags...",  # Shown when nothing selected
)
```

## Select All Pattern

```python
from pywry import MultiSelect, Option

options = [
    Option(label="All", value="all"),
    Option(label="Technology", value="tech"),
    Option(label="Finance", value="finance"),
    Option(label="Healthcare", value="health"),
]

def on_multi_change(data, event_type, label):
    if "all" in data.get("added", []):
        # "All" was just selected - select everything
        all_values = [opt.value for opt in options if opt.value != "all"]
        widget.emit("toolbar:set-value", {
            "componentId": "category-select",
            "value": all_values
        })
    elif "all" in data.get("removed", []):
        # "All" was deselected - clear all
        widget.emit("toolbar:set-value", {
            "componentId": "category-select",
            "value": []
        })
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

## MultiSelect vs Select

| Component | Selection | Use Case |
|-----------|-----------|----------|
| Select | Single | Mutually exclusive choices |
| MultiSelect | Multiple | Filters, tags, permissions |

## API Reference

For complete parameter documentation, see the [MultiSelect API Reference](../reference/components/multiselect.md).
