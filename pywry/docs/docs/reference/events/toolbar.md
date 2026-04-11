# Toolbar Events (toolbar:*)

All interactive toolbar components emit a **user-defined event name** (the `event` parameter)
when the user interacts with them. The event name must follow the `namespace:event-name`
pattern (e.g. `file:save`, `settings:theme`).

!!! warning "Reserved Prefixes"
    Do not use `pywry:*`, `plotly:*`, `grid:*`, `modal:*`, `tvchart:*`, or `chat:*` as
    event prefixes — these are reserved for system events.

---

## Component Events (JS → Python)

These events fire when the user interacts with a toolbar component.
The event name is whatever you set in the component's `event` parameter.

### Button

Emitted on click.

```python
# Event name: the `event` parameter value
{
    "componentId": "btn-abc123",  # auto-generated or user-set component_id
    # ...any keys from the `data` parameter are merged in
}
```

If the button was created with `data={"format": "csv"}`, the payload becomes:

```python
{"componentId": "btn-abc123", "format": "csv"}
```

### Select

Emitted when the user picks an option from the dropdown.

```python
{
    "value": "dark",           # string — the selected Option.value
    "componentId": "select-xyz"
}
```

### MultiSelect

Emitted when any checkbox changes inside the multi-select dropdown.

```python
{
    "values": ["opt1", "opt3"],  # list[str] — all currently checked Option.values
    "componentId": "multi-xyz"
}
```

### RadioGroup

Emitted when the user clicks a radio option.

```python
{
    "value": "bar",            # string — the selected Option.value
    "componentId": "radio-xyz"
}
```

### TabGroup

Emitted when the user clicks a tab.

```python
{
    "value": "1d",                    # string — the selected Option.value
    "componentId": "tabs-xyz",
    "targetInterval": "1D",           # string — from Option.data_attrs (or "")
    "tooltip": "1 Day"                # string — from Option.description (or "")
}
```

### TextInput

Emitted on input (debounced, default 300 ms).

```python
{
    "value": "search query",   # string — current input text
    "componentId": "text-xyz"
}
```

### TextArea

Emitted on input (debounced, default 300 ms).

```python
{
    "value": "multi-line text",  # string — current textarea content
    "componentId": "area-xyz"
}
```

### SearchInput

Emitted on input (debounced, default 300 ms). Disables spellcheck and autocomplete.

```python
{
    "value": "AAPL",           # string — current search text
    "componentId": "search-xyz"
}
```

### SecretInput

SecretInput uses a **3-event architecture** for security — values are base64-encoded
in transit and never exposed via state getters.

**Value update** — emitted on blur or ++ctrl+enter++:

```python
# Event: {event}
{
    "value": "c2VjcmV0MTIz",  # string — base64-encoded value
    "encoded": True,           # always true
    "componentId": "secret-xyz"
}
```

**Reveal request** — emitted when the user clicks the eye icon:

```python
# Event: {event}:reveal
{"componentId": "secret-xyz"}
```

Your Python callback should respond by emitting `{event}:reveal-response`:

```python
# Event: {event}:reveal-response  (Python → JS)
{
    "componentId": "secret-xyz",
    "value": "c2VjcmV0MTIz",  # base64-encoded value to display
    "encoded": True
}
```

**Copy request** — emitted when the user clicks the copy icon:

```python
# Event: {event}:copy
{"componentId": "secret-xyz"}
```

Your Python callback should respond by emitting `{event}:copy-response`:

```python
# Event: {event}:copy-response  (Python → JS)
{
    "componentId": "secret-xyz",
    "value": "c2VjcmV0MTIz",  # base64-encoded value to copy to clipboard
    "encoded": True
}
```

### NumberInput

Emitted on input (debounced). Has custom spinner buttons.

```python
{
    "value": 42.5,             # number — parsed float
    "componentId": "num-xyz"
}
```

### DateInput

Emitted on change (native date picker).

```python
{
    "value": "2025-03-15",     # string — ISO date (YYYY-MM-DD)
    "componentId": "date-xyz"
}
```

### SliderInput

Emitted on input (debounced, 50 ms).

```python
{
    "value": 75.0,             # number — parsed float
    "componentId": "slider-xyz"
}
```

### RangeInput

Emitted on input (debounced). Enforces start ≤ end.

```python
{
    "start": 20.0,             # number — start handle value
    "end": 80.0,               # number — end handle value
    "componentId": "range-xyz"
}
```

### Toggle

Emitted on toggle.

```python
{
    "value": True,             # boolean — current checked state
    "componentId": "toggle-xyz"
}
```

### Checkbox

Emitted on check/uncheck.

```python
{
    "value": True,             # boolean — current checked state
    "componentId": "cb-xyz"
}
```

### Marquee

Emitted on click (only when `event` is set, making it clickable).

```python
{
    "value": "Breaking news…", # string — the data-text attribute
    "componentId": "marquee-xyz"
}
```

---

## Toolbar Structure Events (JS → Python)

These system events use fixed names (not user-defined).

| Event | Payload | Trigger |
|-------|---------|---------|
| `toolbar:collapse` | `{componentId, collapsed: true}` | User clicks collapse toggle |
| `toolbar:expand` | `{componentId, collapsed: false}` | User clicks expand toggle |
| `toolbar:resize` | `{componentId, position, width, height}` | User drags resize handle |
| `toolbar:state-response` | See below | Response to `toolbar:request-state` |

### toolbar:state-response

Emitted by the frontend in response to `toolbar:request-state`.

**Full state response** (when no `componentId` is specified):

```python
{
    "toolbars": {
        "toolbar-abc": {
            "position": "top",           # toolbar position
            "components": ["btn-1", "select-2"]  # component IDs in this toolbar
        }
    },
    "components": {
        "btn-1": {"type": "button", "value": {"disabled": False}},
        "select-2": {"type": "select", "value": "dark"},
        "multi-3": {"type": "multiselect", "value": ["opt1", "opt3"]},
        "text-4": {"type": "text", "value": "hello"},
        "num-5": {"type": "number", "value": 42},
        "date-6": {"type": "date", "value": "2025-03-15"},
        "range-7": {"type": "range", "value": 75.0},
        "secret-8": {"type": "secret", "value": {"has_value": True}}
    },
    "timestamp": 1712345678901,
    "context": "optional-context"        # echoed from request
}
```

**Single component response** (when `componentId` is specified):

```python
{
    "componentId": "select-2",
    "value": "dark",
    "context": "optional-context"
}
```

!!! note "Security"
    SecretInput values are **never** included in state responses. The state returns
    `{"has_value": true}` instead of the actual value.

---

## State Management (Python → JS)

### toolbar:request-state

Request current toolbar state from the frontend.

```python
# Request all toolbar state
app.emit("toolbar:request-state", {})

# Request specific toolbar
app.emit("toolbar:request-state", {"toolbarId": "toolbar-abc"})

# Request single component value
app.emit("toolbar:request-state", {"componentId": "select-2", "context": "my-ctx"})
```

| Field | Type | Description |
|-------|------|-------------|
| `toolbarId` | `str?` | Restrict to a specific toolbar |
| `componentId` | `str?` | Request a single component's value |
| `context` | `str?` | Echoed back in the response |

### toolbar:set-value

Set a single component's value and/or attributes.

```python
app.emit("toolbar:set-value", {
    "componentId": "select-2",
    "value": "light",
    "disabled": False,
    "label": "Theme",
})
```

| Attribute | Type | Applies To | Description |
|-----------|------|------------|-------------|
| `componentId` | `str` | All | **Required.** Target component ID |
| `value` | `any` | All | New value (type depends on component) |
| `label` / `text` | `str` | All | Update display text/label |
| `html` / `innerHTML` | `str` | Button, Div | Set inner HTML content |
| `disabled` | `bool` | All | Enable/disable the component |
| `variant` | `str` | Button | Style: `primary`, `secondary`, `neutral`, `ghost`, `outline`, `danger`, `warning`, `icon` |
| `size` | `str` | Button, TabGroup | Size: `xs`, `sm`, `lg`, `xl` |
| `tooltip` / `description` | `str` | All | Hover text |
| `data` | `dict` | Button | Custom event data payload |
| `event` | `str` | All | Change the emitted event name |
| `options` | `list[dict]` | Select | Replace dropdown options `[{value, label}, ...]` |
| `style` | `str \| dict` | All | Inline CSS (string or `{property: value}` dict) |
| `className` / `class` | `str \| dict` | All | CSS classes (string to add, or `{add: [...], remove: [...]}`) |
| `placeholder` | `str` | Text inputs | Input placeholder text |
| `min` | `number` | NumberInput, SliderInput, RangeInput | Minimum value |
| `max` | `number` | NumberInput, SliderInput, RangeInput | Maximum value |
| `step` | `number` | NumberInput, SliderInput, RangeInput | Step increment |
| `checked` | `bool` | Toggle, Checkbox | Set checked state |
| `selected` | `str` | RadioGroup, TabGroup | Set the active option by value |
| `start` | `number` | RangeInput | Set start handle |
| `end` | `number` | RangeInput | Set end handle |
| `values` | `list` | MultiSelect | Set checked values |

!!! warning "Security"
    `toolbar:set-value` **cannot** set SecretInput values. Attempting to do so is silently
    blocked. Use the SecretInput event handler pattern instead.

### toolbar:set-values

Set multiple component values at once.

```python
app.emit("toolbar:set-values", {
    "values": {
        "select-2": "dark",
        "slider-5": 80,
        "toggle-7": True
    }
})
```

| Field | Type | Description |
|-------|------|-------------|
| `values` | `dict[str, any]` | Map of `componentId → value` |

---

## Marquee Events (Python → JS)

### toolbar:marquee-set-content

Update all content in a marquee.

```python
app.emit("toolbar:marquee-set-content", {
    "id": "marquee-xyz",
    "html": "<b>Breaking:</b> New release available",
    "speed": 10,
    "paused": False,
})
```

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | **Required.** Marquee component ID |
| `text` | `str?` | Plain text content (HTML-escaped) |
| `html` | `str?` | HTML content (use `text` or `html`, not both) |
| `separator` | `str?` | Separator between repeated content |
| `speed` | `number?` | Animation duration in seconds |
| `paused` | `bool?` | Pause/resume scrolling |

### toolbar:marquee-set-item

Update individual ticker items within a marquee.

```python
app.emit("toolbar:marquee-set-item", {
    "ticker": "AAPL",
    "html": "<span class='up'>AAPL 195.20 +1.5%</span>",
    "styles": {"color": "green"},
    "class_add": ["flash"],
})
```

| Field | Type | Description |
|-------|------|-------------|
| `ticker` | `str?` | Match elements with `data-ticker` attribute |
| `selector` | `str?` | Alternative CSS selector (use `ticker` or `selector`) |
| `text` | `str?` | Plain text content |
| `html` | `str?` | HTML content |
| `styles` | `dict?` | Inline styles to apply `{property: value}` |
| `class_add` | `str \| list?` | CSS class(es) to add |
| `class_remove` | `str \| list?` | CSS class(es) to remove |
