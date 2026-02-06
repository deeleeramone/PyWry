# Toggle

An on/off switch for boolean settings.

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
from pywry import Toggle

def on_advanced_toggle(data, event_type, label):
    show_advanced = data["value"]
    
    # Show/hide advanced options
    widget.emit("pywry:set-style", {
        "selector": ".advanced-options",
        "styles": {"display": "block" if show_advanced else "none"}
    })

advanced_toggle = Toggle(
    label="Advanced Options",
    event="ui:advanced",
    value=False,
)
```

## Theme Toggle

```python
from pywry import Toggle

def on_theme_toggle(data, event_type, label):
    is_dark = data["value"]
    
    # Update theme
    widget.emit("pywry:update-theme", {
        "theme": "plotly_dark" if is_dark else "plotly_white"
    })
    
    # Update Plotly charts
    widget.emit("plotly:update-layout", {
        "layout": {"template": "plotly_dark" if is_dark else "plotly_white"}
    })

theme_toggle = Toggle(
    label="🌙 Dark Mode",
    event="theme:toggle",
    value=True,
)
```

## Toggle vs Checkbox

| Component | Visual | Use Case |
|-----------|--------|----------|
| Toggle | Switch slider | Settings, preferences |
| Checkbox | Checkmark box | Form fields, agreements |

## API Reference

For complete parameter documentation, see the [Toggle API Reference](../reference/components/toggle.md).
