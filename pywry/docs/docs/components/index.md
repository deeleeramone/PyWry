# UI Components

PyWry provides 18 Pydantic-based UI components for building interactive toolbars and modals. All components are type-safe, fully customizable, and emit events that integrate with Python callbacks.

## Component Categories

### Action Components

Create clickable buttons and trigger actions.

| Component | Description | Use Case |
|-----------|-------------|----------|
| [Button](button.md) | Clickable action trigger | Save, submit, navigate |

### Selection Components

Let users choose from predefined options.

| Component | Description | Use Case |
|-----------|-------------|----------|
| [Select](select.md) | Single-choice dropdown | Theme picker, data source |
| [MultiSelect](multiselect.md) | Multiple-choice dropdown | Filter categories, tags |
| [RadioGroup](radiogroup.md) | Exclusive radio buttons | Chart type, view mode |
| [TabGroup](tabgroup.md) | Tab-style navigation | Switch between sections |

### Text Input Components

Capture text input from users.

| Component | Description | Use Case |
|-----------|-------------|----------|
| [TextInput](textinput.md) | Single-line text | Search, names, labels |
| [TextArea](textarea.md) | Multi-line text | Notes, descriptions |
| [SearchInput](searchinput.md) | Text with search icon | Search boxes |
| [SecretInput](secretinput.md) | Password field with reveal | API keys, passwords |

### Numeric & Date Components

Handle numbers and dates with validation.

| Component | Description | Use Case |
|-----------|-------------|----------|
| [NumberInput](numberinput.md) | Numeric input with limits | Quantities, prices |
| [DateInput](dateinput.md) | Date picker | Date ranges, scheduling |
| [SliderInput](sliderinput.md) | Sliding value selector | Volume, opacity |
| [RangeInput](rangeinput.md) | Min-max range selector | Price range, date range |

### Boolean Components

Simple on/off toggles.

| Component | Description | Use Case |
|-----------|-------------|----------|
| [Toggle](toggle.md) | On/off switch | Enable features |
| [Checkbox](checkbox.md) | Checkable option | Agree to terms |

### Layout Components

Organize and display content.

| Component | Description | Use Case |
|-----------|-------------|----------|
| [Div](div.md) | Container for custom content | Labels, status, icons |
| [Marquee](marquee.md) | Scrolling ticker display | Stock prices, news |
| [TickerItem](tickeritem.md) | Individual ticker entry | Stock symbol, metric |

### Container Components

Hold and organize other components.

| Component | Description | Use Case |
|-----------|-------------|----------|
| [Toolbar](toolbar.md) | Component container | Group related controls |

## Quick Import

```python
from pywry import (
    # Actions
    Button,
    # Selection
    Select, MultiSelect, RadioGroup, TabGroup, Option,
    # Text Input
    TextInput, TextArea, SearchInput, SecretInput,
    # Numeric & Date
    NumberInput, DateInput, SliderInput, RangeInput,
    # Boolean
    Toggle, Checkbox,
    # Layout
    Div, Marquee, TickerItem,
    # Container
    Toolbar,
)
```

## Common Patterns

### Event Naming

All interactive components emit events via the `event` parameter:

```python
Button(label="Save", event="file:save")
Select(label="Theme", event="settings:theme", options=[...])
```

Use namespaced events like `category:action` for organization:

- `file:save`, `file:export`, `file:import`
- `chart:zoom`, `chart:reset`, `chart:download`
- `settings:theme`, `settings:locale`

!!! warning "Reserved Prefixes"
    Avoid these reserved event prefixes:
    
    - `pywry:*` - Internal system events
    - `plotly:*` - Plotly chart events
    - `grid:*` - AG Grid events
    - `modal:*` - Modal control events

### Callbacks

Connect events to Python functions:

```python
from pywry import PyWry, Toolbar, Button

def handle_save(data, event_type, label):
    """Handle save button click."""
    # data contains component-specific information
    app.emit("pywry:alert", {"message": "Saved!", "type": "success"}, label)

app = PyWry()
toolbar = Toolbar(position="top", items=[Button(label="Save", event="file:save")])

app.show(
    "<h1>Editor</h1>",
    toolbars=[toolbar],
    callbacks={"file:save": handle_save}
)
```

### Component State

Components can have initial values that update dynamically:

```python
from pywry import PyWry, Toolbar, SliderInput, Button

app = PyWry()

def on_max_volume(data, event_type, label):
    app.emit("toolbar:set-value", {
        "componentId": "volume-slider",
        "value": 100
    }, label)
    app.emit("pywry:alert", {"message": "Volume set to max!", "type": "info"}, label)

app.show(
    "<h1>Audio Controls</h1>",
    toolbars=[
        Toolbar(position="top", items=[
            SliderInput(
                component_id="volume-slider",
                label="Volume",
                event="audio:volume",
                value=50,
                min=0,
                max=100,
            ),
            Button(label="Max Volume", event="audio:max", variant="primary"),
        ])
    ],
    callbacks={"audio:max": on_max_volume},
)
```

## Next Steps

- [Toolbar System Guide](../guides/toolbars.md) - Learn how to compose components
- [Event System Guide](../guides/events.md) - Deep dive into event handling
- [Theming Guide](../guides/theming.md) - Customize component appearance
