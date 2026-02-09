# TabGroup

A tab bar for switching between sections or views.

<div class="component-preview">
  <div class="pywry-tab-group" data-event="nav:tab">
    <button type="button" class="pywry-tab pywry-tab-active" data-value="overview">Overview</button>
    <button type="button" class="pywry-tab" data-value="details">Details</button>
    <button type="button" class="pywry-tab" data-value="settings">Settings</button>
  </div>
</div>

## Basic Usage

```python
from pywry import TabGroup, Option

tabs = TabGroup(
    event="nav:tab",
    options=[
        Option(label="Overview", value="overview"),
        Option(label="Details", value="details"),
        Option(label="Settings", value="settings"),
    ],
    selected="overview",
)
```

## Common Patterns

### Section Switching

```python
from pywry import PyWry, Toolbar, TabGroup, Option

app = PyWry()

def on_section_change(data, event_type, label):
    active = data["value"]
    # Hide all sections, show active
    for section in ["charts", "data", "config"]:
        display = "block" if section == active else "none"
        app.emit("pywry:set-style", {
            "selector": f"#section-{section}",
            "styles": {"display": display}
        }, label)

app.show(
    '''
    <div id="section-charts">Charts content...</div>
    <div id="section-data" style="display:none">Data content...</div>
    <div id="section-config" style="display:none">Config content...</div>
    ''',
    toolbars=[
        Toolbar(position="top", items=[
            TabGroup(
                event="section:tab",
                options=[
                    Option(label="📊 Charts", value="charts"),
                    Option(label="📝 Data", value="data"),
                    Option(label="⚙️ Config", value="config"),
                ],
                selected="charts",
            )
        ])
    ],
    callbacks={"section:tab": on_section_change},
)
```

### Dashboard Navigation

```python
dashboard_tabs = TabGroup(
    event="dashboard:nav",
    options=[
        Option(label="Home", value="home"),
        Option(label="Analytics", value="analytics"),
        Option(label="Reports", value="reports"),
        Option(label="Users", value="users"),
    ],
    selected="home",
)

toolbar = Toolbar(
    position="header",
    items=[dashboard_tabs],
)
```

### With Content Loading

```python
from pywry import PyWry, Toolbar, TabGroup, Option

app = PyWry()

content_map = {
    "charts": "<div><h2>Charts</h2><p>Charts content here</p></div>",
    "data": "<div><h2>Data</h2><p>Data content here</p></div>",
    "config": "<div><h2>Config</h2><p>Config content here</p></div>",
}

def on_tab_change(data, event_type, label):
    tab = data["value"]
    app.emit("pywry:set-content", {
        "selector": "#content",
        "html": content_map.get(tab, "")
    }, label)

app.show(
    '<div id="content"><h2>Charts</h2><p>Charts content here</p></div>',
    toolbars=[
        Toolbar(position="top", items=[
            TabGroup(
                event="content:tab",
                options=[
                    Option(label="Charts", value="charts"),
                    Option(label="Data", value="data"),
                    Option(label="Config", value="config"),
                ],
                selected="charts",
            )
        ])
    ],
    callbacks={"content:tab": on_tab_change},
)
```

## Attributes

```
component_id : str | None
    Unique identifier for state tracking (auto-generated if not provided)
label : str | None
    Display label (rarely used for tabs, but available)
description : str | None
    Tooltip/hover text for accessibility and user guidance
event : str
    Event name emitted on tab change (format: namespace:event-name)
style : str | None
    Optional inline CSS
disabled : bool
    Whether the tab group is disabled (default: False)
options : list[Option]
    List of Option(label, value) items defining the tabs
selected : str
    Currently selected tab value (default: "")
size : str
    Tab size: "sm", "md", or "lg" (default: "md")
```

## Events

Emits the `event` name with payload:

```json
{"value": "overview", "componentId": "tab-abc123"}
```

- `value` — the `value` string of the selected tab

## TabGroup vs RadioGroup

| Component | Visual | Use Case |
|-----------|--------|----------|
| TabGroup | Tab bar | Page/section navigation |
| RadioGroup | Radio buttons | Data options, settings |

```python
# TabGroup: Navigation
TabGroup(event="nav:page", options=[...])  # Switch pages

# RadioGroup: Options
RadioGroup(label="Chart Type", event="chart:type", options=[...])  # Change chart
```

## API Reference

For complete parameter documentation, see the [TabGroup API Reference](../reference/components/tabgroup.md).
