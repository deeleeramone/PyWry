# Toggle

An on/off switch for boolean settings.

<div class="component-preview">
  <span class="pywry-input-group pywry-input-inline">
    <span class="pywry-input-label">Dark Mode:</span>
    <label class="pywry-toggle">
      <input type="checkbox" class="pywry-toggle-input" checked>
      <span class="pywry-toggle-slider"></span>
    </label>
  </span>
  <span class="preview-sep"></span>
  <span class="pywry-input-group pywry-input-inline">
    <span class="pywry-input-label">Sound:</span>
    <label class="pywry-toggle">
      <input type="checkbox" class="pywry-toggle-input">
      <span class="pywry-toggle-slider"></span>
    </label>
  </span>
</div>

## Basic Usage

```python
from pywry import Toggle

dark_mode = Toggle(
    label="Dark Mode",
    event="settings:dark_mode",
    value=True,  # Initially on
)
```

## Feature Toggles

```python
from pywry import Toolbar, Toggle

settings_toolbar = Toolbar(
    position="right",
    items=[
        Toggle(label="Auto-refresh", event="settings:autorefresh", value=True),
        Toggle(label="Notifications", event="settings:notifications", value=True),
        Toggle(label="Sound", event="settings:sound", value=False),
    ],
)
```

## Show/Hide UI Sections

```python
from pywry import PyWry, Toolbar, Toggle

app = PyWry()

def on_advanced_toggle(data, event_type, label):
    show_advanced = data["value"]
    app.emit("pywry:set-style", {
        "selector": ".advanced-options",
        "styles": {"display": "block" if show_advanced else "none"}
    }, label)

app.show(
    '''
    <h1>Settings</h1>
    <p>Basic options are always visible.</p>
    <div class="advanced-options" style="display:none">
        <p>Advanced options are hidden by default.</p>
    </div>
    ''',
    toolbars=[
        Toolbar(position="top", items=[
            Toggle(label="Advanced Options", event="ui:advanced", value=False)
        ])
    ],
    callbacks={"ui:advanced": on_advanced_toggle},
)
```

## Theme Toggle

```python
from pywry import PyWry, Toolbar, Toggle

app = PyWry()

def on_theme_toggle(data, event_type, label):
    is_dark = data["value"]
    theme = "dark" if is_dark else "light"
    app.emit("pywry:update-theme", {"theme": theme}, label)
    app.emit("pywry:alert", {
        "message": f"Theme changed to {theme}",
        "type": "info"
    }, label)

app.show(
    "<h1>Theme Demo</h1><p>Toggle to switch themes.</p>",
    toolbars=[
        Toolbar(position="top", items=[
            Toggle(label="🌙 Dark Mode", event="theme:toggle", value=True)
        ])
    ],
    callbacks={"theme:toggle": on_theme_toggle},
)
```

## Attributes

```
component_id : str | None
    Unique identifier for state tracking (auto-generated if not provided)
label : str | None
    Display label shown next to the toggle
description : str | None
    Tooltip/hover text for accessibility and user guidance
event : str
    Event name emitted on interaction (format: namespace:event-name)
style : str | None
    Optional inline CSS
disabled : bool
    Whether the toggle is disabled (default: False)
value : bool
    Current toggle state (default: False)
```

## Events

Emits the `event` name with payload:

```json
{"value": true, "componentId": "toggle-abc123"}
```

- `value` — `true` when toggled on, `false` when toggled off

## Toggle vs Checkbox

| Component | Visual | Use Case |
|-----------|--------|----------|
| Toggle | Switch slider | Settings, preferences |
| Checkbox | Checkmark box | Form fields, agreements |

## API Reference

For complete parameter documentation, see the [Toggle API Reference](../reference/components/toggle.md).
