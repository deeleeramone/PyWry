# DateInput

A date picker for selecting calendar dates.

<div class="component-preview">
  <span class="pywry-input-group pywry-input-inline">
    <span class="pywry-input-label">Date:</span>
    <input type="date" class="pywry-input pywry-input-date" value="2026-02-08">
  </span>
</div>

## Basic Usage

```python
from pywry import DateInput

date_picker = DateInput(
    label="Date",
    event="form:date",
)
```

## With Default Value

```python
from datetime import date

DateInput(
    label="Start Date",
    event="filter:start_date",
    value=date.today().isoformat(),  # "2026-02-03"
)
```

## Date Constraints

```python
DateInput(
    label="Delivery Date",
    event="order:delivery",
    min="2026-02-01",   # Earliest selectable date
    max="2026-12-31",   # Latest selectable date
)
```

## Date Range Toolbar

```python
from pywry import DateInput, Button, Toolbar

toolbar = Toolbar(
    position="top",
    items=[
        DateInput(
            component_id="start-date",
            label="From",
            event="filter:start",
        ),
        DateInput(
            component_id="end-date",
            label="To",
            event="filter:end",
        ),
        Button(label="Apply", event="filter:apply", variant="primary"),
    ],
)
```

## Attributes

```
component_id : str | None
    Unique identifier for state tracking (auto-generated if not provided)
label : str | None
    Display label shown next to the date picker
description : str | None
    Tooltip/hover text for accessibility and user guidance
event : str
    Event name emitted on date change (format: namespace:event-name)
style : str | None
    Optional inline CSS
disabled : bool
    Whether the date picker is disabled (default: False)
value : str
    Current date value in YYYY-MM-DD format (default: "")
min : str
    Earliest selectable date in YYYY-MM-DD format (default: "")
max : str
    Latest selectable date in YYYY-MM-DD format (default: "")
```

## Events

Emits the `event` name with payload:

```json
{"value": "2026-02-08", "componentId": "date-abc123"}
```

- `value` — selected date as a YYYY-MM-DD string

## API Reference

For complete parameter documentation, see the [DateInput API Reference](../reference/components/dateinput.md).
