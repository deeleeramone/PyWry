# TabGroup

A tab bar for switching between sections or views.

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
tabs = TabGroup(
    event="section:tab",
    options=[
        Option(label="📊 Charts", value="charts"),
        Option(label="📝 Data", value="data"),
        Option(label="⚙️ Config", value="config"),
    ],
    selected="charts",
)

def on_section_change(data, event_type, label):
    active = data["value"]
    
    # Hide all sections, show active
    for section in ["charts", "data", "config"]:
        display = "block" if section == active else "none"
        widget.emit("pywry:set-style", {
            "selector": f"#section-{section}",
            "styles": {"display": display}
        })

# HTML structure
html = '''
<div id="section-charts">Charts content...</div>
<div id="section-data" style="display:none">Data content...</div>
<div id="section-config" style="display:none">Config content...</div>
'''
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
def on_tab_change(data, event_type, label):
    tab = data["value"]
    
    # Show loading state
    widget.emit("pywry:set-content", {
        "selector": "#content",
        "html": "<div class='loading'>Loading...</div>"
    })
    
    # Update content based on tab
    content_map = {
        "charts": "<div>Charts content here</div>",
        "data": "<div>Data content here</div>",
        "config": "<div>Config content here</div>",
    }
    
    widget.emit("pywry:set-content", {
        "selector": "#content",
        "html": content_map.get(tab, "")
    })
```

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
