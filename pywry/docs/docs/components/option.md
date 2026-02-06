# Option

A label-value pair used in selection components like Select, MultiSelect, RadioGroup, and TabGroup.

## Basic Usage

```python
from pywry import Option

option = Option(
    label="Display Text",  # What the user sees
    value="internal_value", # What your code receives
)
```

## Usage with Components

### Select

```python
from pywry import Select, Option

Select(
    label="Theme",
    event="settings:theme",
    options=[
        Option(label="Light", value="light"),
        Option(label="Dark", value="dark"),
        Option(label="System", value="system"),
    ],
    selected="dark",
)
```

### MultiSelect

```python
from pywry import MultiSelect, Option

MultiSelect(
    label="Categories",
    event="filter:categories",
    options=[
        Option(label="Technology", value="tech"),
        Option(label="Finance", value="finance"),
        Option(label="Healthcare", value="health"),
    ],
    selected=["tech", "finance"],
)
```

### RadioGroup

```python
from pywry import RadioGroup, Option

RadioGroup(
    label="Chart Type",
    event="chart:type",
    options=[
        Option(label="Line", value="line"),
        Option(label="Bar", value="bar"),
        Option(label="Scatter", value="scatter"),
    ],
    selected="line",
)
```

### TabGroup

```python
from pywry import TabGroup, Option

TabGroup(
    event="nav:section",
    options=[
        Option(label="Overview", value="overview"),
        Option(label="Details", value="details"),
        Option(label="Settings", value="settings"),
    ],
    selected="overview",
)
```

## Building Options from Data

### From a List

```python
colors = ["Red", "Green", "Blue", "Yellow"]

options = [Option(label=c, value=c.lower()) for c in colors]
```

### From a Dictionary

```python
countries = {
    "us": "United States",
    "uk": "United Kingdom",
    "de": "Germany",
    "jp": "Japan",
}

options = [Option(label=name, value=code) for code, name in countries.items()]
```

### From Database Records

```python
users = fetch_users()  # Returns list of User objects

options = [
    Option(label=f"{user.name} ({user.email})", value=str(user.id))
    for user in users
]
```

## With Icons

```python
options = [
    Option(label="🌙 Dark", value="dark"),
    Option(label="☀️ Light", value="light"),
    Option(label="💻 System", value="system"),
]
```

## Label vs Value

- **label**: Human-readable text shown in the UI
- **value**: Machine-readable value sent to callbacks

```python
Option(label="United States", value="US")  # User sees "United States", code gets "US"
Option(label="Small (8oz)", value="small")  # Descriptive label, simple value
Option(label="$9.99/month", value="9.99")   # Formatted label, numeric value
```

## API Reference

For complete parameter documentation, see the [Option API Reference](../reference/components/option.md).
