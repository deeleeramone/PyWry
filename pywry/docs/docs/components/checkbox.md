# Checkbox

A checkable box for boolean selections, typically used in forms.

## Basic Usage

```python
from pywry import Checkbox

agree = Checkbox(
    label="I agree to the terms",
    event="form:agree",
    value=False,
)
```

## Common Patterns

### Form Agreement

```python
from pywry import Toolbar, Checkbox, Button

def on_agree_change(data, event_type, label):
    agreed = data["value"]
    
    # Enable/disable submit button based on agreement
    widget.emit("toolbar:set-value", {
        "componentId": "submit-btn",
        "disabled": not agreed
    })

form_toolbar = Toolbar(
    position="bottom",
    items=[
        Checkbox(
            label="I agree to the terms and conditions",
            event="form:agree",
        ),
        Button(
            component_id="submit-btn",
            label="Submit",
            event="form:submit",
            variant="primary",
            disabled=True,  # Initially disabled
        ),
    ],
)
```

### Multiple Checkboxes

```python
from pywry import Toolbar, Checkbox, Div

features_toolbar = Toolbar(
    position="right",
    items=[
        Div(content="<strong>Features</strong>"),
        Checkbox(label="Email notifications", event="pref:email", value=True),
        Checkbox(label="SMS notifications", event="pref:sms", value=False),
        Checkbox(label="Push notifications", event="pref:push", value=True),
    ],
)
```

### Select All Pattern

```python
from pywry import Toolbar, Checkbox

items = [{"id": 1, "name": "Item A"}, {"id": 2, "name": "Item B"}]

def on_select_all(data, event_type, label):
    select_all = data["value"]
    
    # Update all child checkboxes
    for item in items:
        widget.emit("toolbar:set-value", {
            "componentId": f"item-{item['id']}",
            "value": select_all
        })

toolbar = Toolbar(
    position="top",
    items=[
        Checkbox(label="Select All", event="items:select_all"),
        *[Checkbox(
            component_id=f"item-{item['id']}",
            label=item['name'],
            event=f"item:select:{item['id']}"
        ) for item in items],
    ],
)
```

## Checkbox vs Toggle

| Component | Visual | Use Case |
|-----------|--------|----------|
| Checkbox | Checkmark box | Forms, multiple selections, agreements |
| Toggle | Switch | Settings that apply immediately |

## API Reference

For complete parameter documentation, see the [Checkbox API Reference](../reference/components/checkbox.md).
