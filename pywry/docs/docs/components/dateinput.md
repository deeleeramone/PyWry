# DateInput

A date picker for selecting calendar dates.

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

## API Reference

For complete parameter documentation, see the [DateInput API Reference](../reference/components/dateinput.md).
