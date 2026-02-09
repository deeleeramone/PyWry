# Checkbox

A checkable box for boolean selections, typically used in forms.

<div class="component-preview">
  <label class="pywry-checkbox">
    <input type="checkbox" class="pywry-checkbox-input" checked>
    <span class="pywry-checkbox-box"></span>
    <span class="pywry-checkbox-label">Checked</span>
  </label>
  <span class="preview-sep"></span>
  <label class="pywry-checkbox">
    <input type="checkbox" class="pywry-checkbox-input">
    <span class="pywry-checkbox-box"></span>
    <span class="pywry-checkbox-label">Unchecked</span>
  </label>
</div>

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
from pywry import PyWry, Toolbar, Checkbox, Button

app = PyWry()

def on_agree_change(data, event_type, label):
    agreed = data["value"]
    # Enable/disable submit button based on agreement
    app.emit("toolbar:set-value", {
        "componentId": "submit-btn",
        "disabled": not agreed
    }, label)

def on_submit(data, event_type, label):
    app.emit("pywry:alert", {"message": "Form submitted!", "type": "success"}, label)

app.show(
    "<h1>Sign Up</h1><p>Please agree to continue.</p>",
    toolbars=[
        Toolbar(position="bottom", items=[
            Checkbox(label="I agree to the terms and conditions", event="form:agree"),
            Button(
                component_id="submit-btn",
                label="Submit",
                event="form:submit",
                variant="primary",
                disabled=True,  # Initially disabled
            ),
        ])
    ],
    callbacks={
        "form:agree": on_agree_change,
        "form:submit": on_submit,
    },
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
from pywry import PyWry, Toolbar, Checkbox

app = PyWry()
items = [{"id": 1, "name": "Item A"}, {"id": 2, "name": "Item B"}, {"id": 3, "name": "Item C"}]

def on_select_all(data, event_type, label):
    select_all = data["value"]
    # Update all child checkboxes
    for item in items:
        app.emit("toolbar:set-value", {
            "componentId": f"item-{item['id']}",
            "value": select_all
        }, label)

def on_item_select(data, event_type, label):
    app.emit("pywry:alert", {
        "message": f"Item selected: {data.get('value')}",
        "type": "info"
    }, label)

app.show(
    "<h1>Select Items</h1>",
    toolbars=[
        Toolbar(position="top", items=[
            Checkbox(label="Select All", event="items:select_all"),
            *[Checkbox(
                component_id=f"item-{item['id']}",
                label=item['name'],
                event="item:select"
            ) for item in items],
        ])
    ],
    callbacks={
        "items:select_all": on_select_all,
        "item:select": on_item_select,
    },
)
```

## Attributes

```
component_id : str | None
    Unique identifier for state tracking (auto-generated if not provided)
label : str | None
    Display label shown next to the checkbox
description : str | None
    Tooltip/hover text for accessibility and user guidance
event : str
    Event name emitted on interaction (format: namespace:event-name)
style : str | None
    Optional inline CSS
disabled : bool
    Whether the checkbox is disabled (default: False)
value : bool
    Current checked state (default: False)
```

## Events

Emits the `event` name with payload:

```json
{"value": true, "componentId": "checkbox-abc123"}
```

- `value` — `true` when checked, `false` when unchecked

## Checkbox vs Toggle

| Component | Visual | Use Case |
|-----------|--------|----------|
| Checkbox | Checkmark box | Forms, multiple selections, agreements |
| Toggle | Switch | Settings that apply immediately |

## API Reference

For complete parameter documentation, see the [Checkbox API Reference](../reference/components/checkbox.md).
