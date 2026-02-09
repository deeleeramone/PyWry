# Toolbar

The container that holds and organizes UI components. Toolbars can be positioned around your content.

## Basic Usage

```python
from pywry import PyWry, Toolbar, Button, Select, Option

app = PyWry()

toolbar = Toolbar(
    position="top",
    items=[
        Button(label="Save", event="file:save"),
        Select(
            label="Theme",
            event="settings:theme",
            options=[
                Option(label="Light", value="light"),
                Option(label="Dark", value="dark"),
            ],
        ),
    ],
)

app.show("<h1>My App</h1>", toolbars=[toolbar])
```

## Positions

Toolbars can be placed in 7 different positions:

```python
Toolbar(position="top", items=[...])      # Horizontal, above content
Toolbar(position="bottom", items=[...])   # Horizontal, below content
Toolbar(position="left", items=[...])     # Vertical, left side
Toolbar(position="right", items=[...])    # Vertical, right side
Toolbar(position="header", items=[...])   # Fixed at very top
Toolbar(position="footer", items=[...])   # Fixed at very bottom
Toolbar(position="inside", items=[...])   # Overlays content
```

### Layout Hierarchy

<div class="layout-diagram">
  <div class="ld-header">HEADER</div>
  <div class="ld-body">
    <div class="ld-left">LEFT</div>
    <div class="ld-center">
      <div class="ld-top">TOP</div>
      <div class="ld-content">
        CONTENT
        <div class="ld-inside">INSIDE</div>
      </div>
      <div class="ld-bottom">BOTTOM</div>
    </div>
    <div class="ld-right">RIGHT</div>
  </div>
  <div class="ld-footer">FOOTER</div>
</div>

## Multiple Toolbars

Use multiple toolbars for complex layouts:

```python
from pywry import PyWry, Toolbar, Button, Div

app = PyWry()

app.show(
    "<h1>Dashboard</h1>",
    toolbars=[
        Toolbar(
            position="header",
            items=[Button(label="☰ Menu", event="nav:menu")],
        ),
        Toolbar(
            position="top",
            items=[
                Button(label="Save", event="file:save"),
                Button(label="Export", event="file:export"),
            ],
        ),
        Toolbar(
            position="left",
            items=[
                Button(label="📊 Charts", event="view:charts"),
                Button(label="📋 Tables", event="view:tables"),
            ],
        ),
        Toolbar(
            position="footer",
            items=[Div(content="Status: Ready")],
        ),
    ],
)
```

## Component Mix

Combine different components in a toolbar:

```python
toolbar = Toolbar(
    position="top",
    items=[
        # Actions
        Button(label="💾 Save", event="file:save", variant="primary"),
        
        # Selection
        Select(
            label="View",
            event="view:mode",
            options=[
                Option(label="Grid", value="grid"),
                Option(label="List", value="list"),
            ],
        ),
        
        # Input
        SearchInput(
            label="Search",
            event="data:search",
            placeholder="Search items...",
        ),
        
        # Display
        Div(content="<span class='status'>●</span> Connected"),
        
        # Toggle
        Toggle(label="Auto-refresh", event="settings:autorefresh"),
    ],
)
```

## Vertical Toolbars

Left and right toolbars render components vertically:

```python
side_nav = Toolbar(
    position="left",
    items=[
        Button(label="🏠", event="nav:home"),      # Icon buttons work well
        Button(label="📊", event="nav:analytics"),
        Button(label="⚙️", event="nav:settings"),
    ],
)
```

## Styling

Toolbars automatically inherit theme styles. For custom styling, use CSS:

```css
/* In your custom CSS */
.pywry-toolbar-top {
    background: linear-gradient(to right, #667eea, #764ba2);
}

.pywry-toolbar-left {
    border-right: 2px solid var(--pywry-border-color);
}
```

## API Reference

For complete parameter documentation, see the [Toolbar API Reference](../reference/components/toolbar.md).
