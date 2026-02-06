# Theming & CSS

PyWry provides flexible theming options for customizing the look of your applications.

## CSS Variables

PyWry exposes CSS custom properties for easy theming:

```css
:root {
    /* Backgrounds */
    --pywry-bg-primary: #ffffff;
    --pywry-bg-secondary: #f8fafc;
    --pywry-bg-tertiary: #f1f5f9;
    
    /* Text */
    --pywry-text-primary: #0f172a;
    --pywry-text-secondary: #475569;
    --pywry-text-muted: #94a3b8;
    
    /* Borders */
    --pywry-border-color: #e2e8f0;
    --pywry-border-radius: 6px;
    
    /* Accents */
    --pywry-accent: #3b82f6;
    --pywry-accent-hover: #2563eb;
    --pywry-accent-text: #ffffff;
    
    /* Toolbar */
    --toolbar-bg: #1e293b;
    --toolbar-border: #374151;
    --toolbar-text: #f8fafc;
    --toolbar-input-bg: #334155;
    --toolbar-input-border: #475569;
    --toolbar-button-bg: #3b82f6;
    --toolbar-button-hover: #2563eb;
}
```

## Theme Classes

PyWry automatically applies theme classes to the body:

| Class | Applied When |
|-------|--------------|
| `.pywry-theme-light` | Light theme active |
| `.pywry-theme-dark` | Dark theme active |
| `.pywry-theme-system` | Following system preference |

## Switching Themes

### From Python

```python
handle.emit("pywry:update-theme", {"theme": "dark"})
```

### From JavaScript

```javascript
window.pywry.emit("pywry:update-theme", { theme: "light" });
```

## Dark Theme Overrides

```css
.pywry-theme-dark {
    --pywry-bg-primary: #0f172a;
    --pywry-bg-secondary: #1e293b;
    --pywry-bg-tertiary: #334155;
    
    --pywry-text-primary: #f8fafc;
    --pywry-text-secondary: #cbd5e1;
    --pywry-text-muted: #64748b;
    
    --pywry-border-color: #334155;
}
```

## Custom CSS Files

### Via HtmlContent

```python
from pywry import HtmlContent

content = HtmlContent(
    html="<div id='app'></div>",
    css_files=["styles/main.css", "styles/theme.css"],
)
```

### Via Configuration

```toml
# pywry.toml
[theme]
css_file = "styles/custom.css"
```

## CSS Injection

Inject CSS dynamically at runtime:

```python
# Inject CSS
handle.emit("pywry:inject-css", {
    "css": """
        .highlight {
            background: yellow;
            padding: 2px 4px;
        }
    """,
    "id": "custom-highlights",
})

# Remove injected CSS
handle.emit("pywry:remove-css", {"id": "custom-highlights"})
```

## Toolbar Styling

### Component-Specific Classes

Each toolbar component has a predictable class name:

```css
/* Button styling */
.pywry-button {
    padding: 8px 16px;
    border-radius: 6px;
}

/* Select styling */
.pywry-select {
    min-width: 120px;
}

/* Toggle styling */
.pywry-toggle-track {
    width: 48px;
    height: 24px;
}
```

### Target by ID

```css
/* Style specific component by ID */
#toolbar-export {
    background-color: #10b981;
}

#toolbar-export:hover {
    background-color: #059669;
}
```

## Plotly Theming

PyWry's `PlotlyConfig` controls Plotly.js behavior (modebar, interactivity). For visual theming, set properties on the figure's layout:

```python
from pywry import PyWry, PlotlyConfig
import plotly.graph_objects as go

app = PyWry()

# Create figure with layout styling
fig = go.Figure(
    data=[go.Bar(x=["A", "B", "C"], y=[1, 2, 3])],
    layout={
        "template": "plotly_dark",  # Built-in theme
        "paper_bgcolor": "transparent",
        "plot_bgcolor": "transparent",
        "margin": {"t": 40, "r": 20, "b": 40, "l": 60},
    }
)

# PlotlyConfig controls modebar behavior, not visual styling
config = PlotlyConfig(
    display_mode_bar="hover",  # Show modebar on hover
    display_logo=False,  # Hide Plotly logo
    responsive=True,
    scroll_zoom=True,
)

handle = app.show_plotly(fig, config=config)
```

## AgGrid Theming

AgGrid supports multiple built-in themes:

```python
from pywry import GridOptions

options = GridOptions(
    theme="ag-theme-alpine-dark",  # Dark theme
    # or "ag-theme-alpine", "ag-theme-balham", "ag-theme-quartz"
)
```

## Responsive Design

Use media queries for responsive layouts:

```css
/* Mobile */
@media (max-width: 768px) {
    .pywry-toolbar {
        flex-wrap: wrap;
    }
    
    .pywry-button {
        flex: 1 1 100%;
    }
}

/* Large screens */
@media (min-width: 1200px) {
    .pywry-container {
        max-width: 1140px;
        margin: 0 auto;
    }
}
```

## Animation

Add smooth transitions:

```css
:root {
    --pywry-transition: 0.2s ease-in-out;
}

.pywry-button {
    transition: background-color var(--pywry-transition),
                transform var(--pywry-transition);
}

.pywry-button:hover {
    transform: translateY(-1px);
}

.pywry-button:active {
    transform: translateY(0);
}
```

## Font Configuration

```css
:root {
    --pywry-font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    --pywry-font-size-sm: 12px;
    --pywry-font-size-base: 14px;
    --pywry-font-size-lg: 16px;
    --pywry-font-weight-normal: 400;
    --pywry-font-weight-medium: 500;
    --pywry-font-weight-bold: 600;
}
```

## Complete Theme Example

```css
/* custom-theme.css */

/* Light theme */
:root {
    --pywry-bg-primary: #ffffff;
    --pywry-bg-secondary: #f3f4f6;
    --pywry-text-primary: #111827;
    --pywry-text-secondary: #4b5563;
    --pywry-accent: #6366f1;
    --pywry-accent-hover: #4f46e5;
    --pywry-border-color: #e5e7eb;
    --pywry-border-radius: 8px;
    --pywry-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

/* Dark theme */
.pywry-theme-dark {
    --pywry-bg-primary: #111827;
    --pywry-bg-secondary: #1f2937;
    --pywry-text-primary: #f9fafb;
    --pywry-text-secondary: #d1d5db;
    --pywry-accent: #818cf8;
    --pywry-accent-hover: #a5b4fc;
    --pywry-border-color: #374151;
    --pywry-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
}

/* Toolbar customization */
.pywry-toolbar {
    background: var(--pywry-bg-secondary);
    border-bottom: 1px solid var(--pywry-border-color);
    padding: 12px 16px;
    gap: 12px;
}

/* Button styling */
.pywry-button {
    background: var(--pywry-accent);
    color: white;
    border: none;
    padding: 8px 16px;
    border-radius: var(--pywry-border-radius);
    font-weight: 500;
    cursor: pointer;
    transition: background-color 0.15s;
}

.pywry-button:hover {
    background: var(--pywry-accent-hover);
}

/* Input styling */
.pywry-input {
    background: var(--pywry-bg-primary);
    color: var(--pywry-text-primary);
    border: 1px solid var(--pywry-border-color);
    border-radius: var(--pywry-border-radius);
    padding: 8px 12px;
}

.pywry-input:focus {
    outline: none;
    border-color: var(--pywry-accent);
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2);
}
```

## Next Steps

- **[Hot Reload](hot-reload.md)** — Live CSS updates
- **[Toolbar System](toolbars.md)** — Component styling
- **[Toolbar Components](../components/index.md)** — Complete toolbar API
