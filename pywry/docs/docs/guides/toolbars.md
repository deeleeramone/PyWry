# Toolbar System

18 Pydantic components. No HTML/JS required.

## Example

```python
from pywry import PyWry, Toolbar, Button, Select, Option

app = PyWry()

def on_theme(data, event_type, label):
    theme = "plotly_dark" if data["value"] == "dark" else "plotly_white"
    app.emit("pywry:update-theme", {"theme": theme}, label)

def on_save(data, event_type, label):
    app.emit("pywry:alert", {"message": "Saved!", "type": "success"}, label)

toolbar = Toolbar(
    position="top",
    items=[
        Button(label="Save", event="app:save"),
        Select(
            label="Theme",
            event="app:theme",
            options=[Option(label="Light", value="light"), Option(label="Dark", value="dark")],
            selected="dark"
        ),
    ],
)

app.show("<h1>Hello</h1>", toolbars=[toolbar], callbacks={"app:save": on_save, "app:theme": on_theme})
```

## Positions

| Position | Layout |
|----------|--------|
| `top` | Horizontal at top |
| `bottom` | Horizontal at bottom |
| `left` | Vertical at left |
| `right` | Vertical at right |
| `header` | Above main content |
| `footer` | Below main content |
| `inside` | Inside content area |

Layout structure: `HEADER > LEFT | TOP > CONTENT + INSIDE > BOTTOM | RIGHT > FOOTER`

## Components

| Category | Components |
|----------|------------|
| Actions | Button |
| Selection | Select, MultiSelect, RadioGroup, TabGroup |
| Text | TextInput, TextArea, SearchInput, SecretInput |
| Numeric | NumberInput, DateInput, SliderInput, RangeInput |
| Boolean | Toggle, Checkbox |
| Layout | Div, Marquee, TickerItem |

## Event Payloads

| Component | Payload |
|-----------|---------|
| Button | `{componentId, ...data}` |
| Select | `{value, componentId}` |
| MultiSelect | `{values, componentId}` |
| TextInput | `{value, componentId}` |
| NumberInput | `{value, componentId}` |
| DateInput | `{value, componentId}` (YYYY-MM-DD) |
| SliderInput | `{value, componentId}` |
| RangeInput | `{start, end, componentId}` |
| Toggle | `{value, componentId}` (bool) |
| Checkbox | `{value, componentId}` (bool) |
| RadioGroup | `{value, componentId}` |
| TabGroup | `{value, componentId}` |

## Toolbar Events

| Event | Direction | Payload |
|-------|-----------|---------|
| `toolbar:collapse` | JS → Python | `{componentId, collapsed: true}` |
| `toolbar:expand` | JS → Python | `{componentId, collapsed: false}` |
| `toolbar:resize` | JS → Python | `{componentId, position, width, height}` |
| `toolbar:state-response` | JS → Python | `{toolbars, components, timestamp}` |
| `toolbar:request-state` | Python → JS | `{toolbarId?, componentId?}` |
| `toolbar:set-value` | Python → JS | `{componentId, value}` |
| `toolbar:set-values` | Python → JS | `{values: {id: value, ...}}` |

## State Management

### Query State

```python
def on_state(data, event_type, label):
    components = data.get("components", {})
    summary = ", ".join(f"{cid}: {s.get('value')}" for cid, s in components.items())
    app.emit("pywry:alert", {"message": f"State: {summary}"}, label)

handle = app.show("<h1>Hello</h1>", toolbars=[toolbar], callbacks={"toolbar:state-response": on_state})

# Request state
handle.emit("toolbar:request-state", {"toolbarId": "my-toolbar"})
```

Response:
```python
{
    "toolbars": {"toolbar-a1b2c3d4": {"position": "top", "components": ["button-x1y2z3"]}},
    "components": {"button-x1y2z3": {"type": "button", "value": None}},
    "timestamp": 1234567890
}
```

### Set Values

```python
def on_reset(data, event_type, label):
    # Set single value
    app.emit("toolbar:set-value", {"componentId": "theme-select", "value": "light"}, label)
    
    # Set multiple values at once
    app.emit("toolbar:set-values", {
        "values": {
            "theme-select": "light",
            "zoom-input": 100,
            "dark-toggle": False
        }
    }, label)

toolbar = Toolbar(
    position="top",
    items=[
        Select(event="app:theme", component_id="theme-select", options=["light", "dark"], selected="dark"),
        NumberInput(event="app:zoom", component_id="zoom-input", value=150, min=50, max=200),
        Toggle(event="app:dark", component_id="dark-toggle", value=True),
        Button(label="Reset", event="app:reset"),
    ]
)

app.show("<h1>Settings</h1>", toolbars=[toolbar], callbacks={"app:reset": on_reset})
```

### JavaScript Access

```javascript
// Get all toolbar state
const state = window.__PYWRY_TOOLBAR__.getState();

// Get specific toolbar
const state = window.__PYWRY_TOOLBAR__.getState("toolbar-a1b2c3d4");

// Get/set component value
const value = window.__PYWRY_TOOLBAR__.getValue("select-a1b2c3d4");
window.__PYWRY_TOOLBAR__.setValue("select-a1b2c3d4", "dark");
```

## Marquee Events

| Event | Direction | Payload |
|-------|-----------|---------|
| `toolbar:marquee-set-content` | Python → JS | `{id, text?, html?, speed?, paused?, separator?}` |
| `toolbar:marquee-set-item` | Python → JS | `{ticker, text?, html?, styles?, class_add?, class_remove?}` |

```python
# Update marquee text
handle.emit("toolbar:marquee-set-content", {
    "id": marquee.component_id,
    "text": "Breaking news!",
    "speed": 10
})

# Update individual ticker item
handle.emit("toolbar:marquee-set-item", {
    "ticker": "AAPL",
    "text": "AAPL $186.25",
    "styles": {"color": "#22c55e"}
})
```

## Import

```python
from pywry import (
    Toolbar, Button, Select, MultiSelect, RadioGroup, TabGroup, Option,
    TextInput, TextArea, SearchInput, SecretInput,
    NumberInput, DateInput, SliderInput, RangeInput,
    Toggle, Checkbox, Div, Marquee, TickerItem,
)
```

See [Components](../components/index.md) for full API reference.
