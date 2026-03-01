# Styling and Theming

> Style widgets using CSS variables, theme colors, and dynamic style updates.

## Theme CSS Variables

PyWry provides CSS variables that adapt to dark/light themes. **Use these instead of hardcoded colors!**

### Text Colors
```css
var(--text-primary)      /* Main text - high contrast */
var(--text-secondary)    /* Muted text - medium contrast */
var(--text-muted)        /* Very subtle text - low contrast */
```

### Background Colors
```css
var(--bg-primary)        /* Main background (page/window) */
var(--bg-secondary)      /* Card/section background */
var(--bg-tertiary)       /* Nested elements, insets */
var(--bg-hover)          /* Hover states */
```

### Border Colors
```css
var(--border-color)      /* Standard borders */
var(--border-subtle)     /* Subtle dividers */
```

### Accent Colors
```css
var(--accent-color)      /* Primary accent (brand color) */
var(--accent-hover)      /* Accent hover state */
```

### Status Colors
```css
var(--success-color)     /* Green - positive, success */
var(--warning-color)     /* Orange/Yellow - caution */
var(--error-color)       /* Red - error, danger */
var(--info-color)        /* Blue - informational */
```

## Using Theme Variables

### In Div Component
```python
content = Div(
    content="Status: OK",
    component_id="status",
    style="color: var(--success-color); background: var(--bg-secondary); padding: 10px;",
)
```

### In HTML Content
```python
html = """
<div style="
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 16px;
">
    <h2 style="color: var(--text-primary); margin: 0;">Title</h2>
    <p style="color: var(--text-secondary);">Description</p>
</div>
"""
```

### Via inject_css
```python
inject_css(widget_id, css="""
    .custom-card {
        background: var(--bg-secondary);
        border-radius: 8px;
        padding: 16px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .custom-card .title {
        color: var(--text-primary);
        font-weight: 600;
    }
    .custom-card .subtitle {
        color: var(--text-muted);
        font-size: 0.875rem;
    }
""", id="custom-styles")
```

## Dynamic Style Updates

### Using set_style
```python
# Update styles on an element by component_id
set_style(widget_id, component_id="status", styles={
    "color": "var(--error-color)",
    "backgroundColor": "var(--bg-tertiary)",
    "borderLeft": "4px solid var(--error-color)",
})

# Update by selector
set_style(widget_id, selector=".price.up", styles={
    "color": "var(--success-color)",
})
set_style(widget_id, selector=".price.down", styles={
    "color": "var(--error-color)",
})
```

### Style Property Names
Both camelCase and kebab-case work:

```python
# camelCase (JavaScript style)
set_style(widget_id, component_id="box", styles={
    "backgroundColor": "red",
    "fontSize": "16px",
    "borderRadius": "8px",
})

# kebab-case (CSS style)
set_style(widget_id, component_id="box", styles={
    "background-color": "red",
    "font-size": "16px",
    "border-radius": "8px",
})
```

## Theme Switching

### Programmatic Switching
```python
# Switch to dark theme
update_theme(widget_id, theme="dark")

# Switch to light theme
update_theme(widget_id, theme="light")

# Follow OS preference (recommended)
update_theme(widget_id, theme="system")
```

### Theme Detection
```python
# Let the widget follow system preference
update_theme(widget_id, theme="system")

# The CSS variables automatically update when theme changes
# Your content adapts without code changes
```

## Injecting Custom CSS

### Adding Styles
```python
inject_css(widget_id, css="""
    /* Custom component styles */
    .my-button {
        background: var(--accent-color);
        color: white;
        border: none;
        padding: 8px 16px;
        border-radius: 4px;
        cursor: pointer;
        transition: background 0.2s;
    }
    .my-button:hover {
        background: var(--accent-hover);
    }

    /* Status indicators */
    .status-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 500;
    }
    .status-badge.success {
        background: var(--success-color);
        color: white;
    }
    .status-badge.error {
        background: var(--error-color);
        color: white;
    }
""", id="custom-styles")  # ID lets you remove/replace later
```

### Removing Styles
```python
# Remove previously injected styles
remove_css(widget_id, id="custom-styles")
```

### Replacing Styles
```python
# Inject with same ID replaces previous
inject_css(widget_id, css="...", id="custom-styles")  # Replaces previous
```

## Component Styling

### Button Variants
```python
Button(label="Primary", variant="primary")   # Accent color background
Button(label="Default", variant="default")   # Neutral background
Button(label="Ghost", variant="ghost")       # Transparent, border only
Button(label="Danger", variant="danger")     # Red/error color
```

### Div with Full CSS Control
```python
Div(
    content="Card content",
    component_id="my-card",
    style="padding: 20px; border-radius: 8px; background: var(--bg-secondary);",
    class_name="my-card",  # For CSS targeting
)
```

### Styling Built-in Components
```python
# Most components accept style and class_name
Select(
    label="Choose",
    options=[...],
    style="width: 200px;",
    class_name="compact-select",
)
```

## Responsive Patterns

### Media Queries
```python
inject_css(widget_id, css="""
    /* Mobile-first base styles */
    .dashboard {
        display: flex;
        flex-direction: column;
        gap: 16px;
    }

    /* Tablet and up */
    @media (min-width: 600px) {
        .dashboard {
            flex-direction: row;
        }
        .sidebar {
            width: 250px;
            flex-shrink: 0;
        }
        .main-content {
            flex-grow: 1;
        }
    }

    /* Desktop */
    @media (min-width: 1024px) {
        .sidebar {
            width: 300px;
        }
    }
""")
```

### Hide/Show Based on Screen Size
```python
inject_css(widget_id, css="""
    /* Hide sidebar on mobile */
    @media (max-width: 599px) {
        .sidebar {
            display: none;
        }
        .main-content {
            width: 100%;
        }
    }
""")
```

## Common Patterns

### Card Component
```python
inject_css(widget_id, css="""
    .card {
        background: var(--bg-secondary);
        border: 1px solid var(--border-color);
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 16px;
    }
    .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 12px;
    }
    .card-title {
        font-size: 1.125rem;
        font-weight: 600;
        color: var(--text-primary);
    }
    .card-body {
        color: var(--text-secondary);
    }
""")
```

### Status Indicators
```python
inject_css(widget_id, css="""
    .status-dot {
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        margin-right: 8px;
    }
    .status-dot.online { background: var(--success-color); }
    .status-dot.offline { background: var(--error-color); }
    .status-dot.pending { background: var(--warning-color); }
""")
```

### Price Styling
```python
inject_css(widget_id, css="""
    .price {
        font-family: monospace;
        font-weight: 500;
    }
    .price.up {
        color: var(--success-color);
    }
    .price.up::before {
        content: "▲ ";
    }
    .price.down {
        color: var(--error-color);
    }
    .price.down::before {
        content: "▼ ";
    }
""")
```
