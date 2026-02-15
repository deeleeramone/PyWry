# Theming & CSS

PyWry uses CSS custom properties for theming. It ships with dark and light themes, supports automatic system detection, and lets you override everything with custom CSS.

## Theme Modes

Three modes are available:

| Mode | Behavior |
|:---|:---|
| `system` | Follows the OS dark/light preference (default) |
| `dark` | Always dark |
| `light` | Always light |

Set the mode in configuration:

```toml
# pywry.toml
[theme]
mode = "dark"
```

Or via environment variable:

```bash
export PYWRY_THEME__MODE=dark
```

Or in Python:

```python
from pywry import PyWry
app = PyWry(theme="dark")
```

## Theme Classes

PyWry applies theme classes to the `<html>` element that you can target in CSS:

| Class | When applied |
|:---|:---|
| `.pywry-theme-dark` + `html.dark` | Dark mode active |
| `.pywry-theme-light` + `html.light` | Light mode active |
| `.pywry-theme-system` | Following OS preference |

## Switching at Runtime

### From Python

```python
handle.emit("pywry:update-theme", {"theme": "dark"})
handle.emit("pywry:update-theme", {"theme": "light"})
handle.emit("pywry:update-theme", {"theme": "system"})
```

### From JavaScript

```javascript
window.pywry.emit("pywry:update-theme", { theme: "light" });
```

When the theme changes, PyWry:

1. Updates `html` classes and `dataset.themeMode`
2. Switches Plotly figures to the matching template (`plotly_dark` / `plotly_white`)
3. Swaps AG Grid theme classes (adds/removes `-dark` suffix)
4. Fires a `pywry:theme-update` event so your code can react

## CSS Variables

All component styles are driven by CSS custom properties. Override them to customize the entire look.

### Layout & Typography (theme-independent)

```css
:root {
    --pywry-font-family: /* system font stack */;
    --pywry-font-size: 14px;
    --pywry-font-weight-normal: 400;
    --pywry-font-weight-medium: 500;

    --pywry-radius: 4px;
    --pywry-radius-lg: 6px;

    --pywry-spacing-xs: 2px;
    --pywry-spacing-sm: 4px;
    --pywry-spacing-md: 6px;
    --pywry-spacing-lg: 8px;

    --pywry-transition-fast: 0.1s;
    --pywry-transition-normal: 0.2s;

    --pywry-accent: #0078d4;
    --pywry-accent-hover: #106ebe;
    --pywry-text-accent: rgb(51, 187, 255);
}
```

### Dark Theme

These are the defaults applied in dark mode:

```css
:root, html.dark, .pywry-theme-dark {
    --pywry-bg-primary: #212124;
    --pywry-bg-secondary: rgba(21, 21, 24, 1);
    --pywry-bg-tertiary: /* slightly lighter */;
    --pywry-bg-hover: /* hover state */;
    --pywry-bg-overlay: /* modal/overlay backdrop */;

    --pywry-text-primary: #ebebed;
    --pywry-text-secondary: #a0a0a0;
    --pywry-text-muted: #707070;

    --pywry-border-color: #333;
    --pywry-border-focus: #555;

    --pywry-btn-primary-bg: #e2e2e2;
    --pywry-btn-primary-text: #151518;
    --pywry-btn-primary-hover: /* lighter */;

    --pywry-btn-secondary-bg: /* secondary bg */;
    --pywry-btn-secondary-text: /* secondary text */;
    --pywry-btn-secondary-border: /* secondary border */;

    --pywry-tab-bg: /* tab background */;
    --pywry-tab-active-bg: /* active tab */;
    --pywry-tab-hover-bg: /* hovered tab */;

    --pywry-toast-bg: /* toast background */;
    --pywry-toast-color: /* toast text */;
    --pywry-toast-accent: /* toast accent */;

    --pywry-scrollbar-thumb: /* scrollbar color */;
    --pywry-scrollbar-thumb-hover: /* scrollbar hover */;
}
```

### Light Theme

```css
html.light, .pywry-theme-light {
    --pywry-bg-primary: #f5f5f5;
    --pywry-bg-secondary: #ffffff;
    --pywry-bg-hover: /* light hover */;
    --pywry-bg-overlay: /* light overlay */;

    --pywry-text-primary: #000000;
    --pywry-text-secondary: #666666;
    --pywry-text-muted: #999999;

    --pywry-border-color: #ccc;
    --pywry-border-focus: #999;

    /* All button, tab, input, toast variables
       are overridden for light backgrounds */
}
```

### System Theme

When `mode="system"`, PyWry uses dark by default and applies light overrides via `@media (prefers-color-scheme: light)`.

## Custom CSS Files

### Via HtmlContent

```python
from pywry import HtmlContent

content = HtmlContent(
    html="<div id='app'></div>",
    inline_css="body { font-size: 16px; }",
    css_files=["styles/main.css", "styles/theme.css"],
)
```

### Via Configuration

```toml
# pywry.toml
[theme]
css_file = "styles/custom.css"

[asset]
css_files = ["extra1.css", "extra2.css"]
```

### Runtime Injection

Inject or remove CSS dynamically:

```python
# Inject
handle.emit("pywry:inject-css", {
    "css": ".highlight { background: yellow; padding: 2px 4px; }",
    "id": "my-highlights",
})

# Remove
handle.emit("pywry:remove-css", {"id": "my-highlights"})
```

From JavaScript:

```javascript
window.pywry.injectCSS(".highlight { color: red; }", "my-highlights");
window.pywry.removeCSS("my-highlights");
```

## Component Styling

Every toolbar component has a predictable CSS class:

| Component | Class |
|:---|:---|
| Button | `.pywry-button` |
| Select | `.pywry-select` |
| Toggle | `.pywry-toggle-track` |
| TextInput | `.pywry-input` |
| Toolbar container | `.pywry-toolbar` |
| Modal | `.pywry-modal` |

Target specific components by their `component_id`:

```css
#theme-select { min-width: 160px; }
#submit-btn:hover { transform: translateY(-1px); }
```

## Plotly Theming

PyWry automatically switches Plotly figures between `plotly_dark` and `plotly_white` templates when the theme changes. For custom Plotly styling, set layout properties on the figure:

```python
import plotly.graph_objects as go

fig = go.Figure(
    data=[go.Bar(x=["A", "B", "C"], y=[1, 2, 3])],
    layout={
        "paper_bgcolor": "transparent",
        "plot_bgcolor": "transparent",
        "margin": {"t": 40, "r": 20, "b": 40, "l": 60},
    },
)

app.show_plotly(fig)
```

## AG Grid Theming

AG Grid theme classes are swapped automatically when the PyWry theme changes. Available themes:

```python
from pywry import GridOptions

options = GridOptions(
    theme="ag-theme-alpine-dark",
    # "ag-theme-alpine", "ag-theme-balham", "ag-theme-quartz"
)
```

## Complete Custom Theme Example

```css
/* custom-theme.css */

/* Override variables for both themes */
:root {
    --pywry-accent: #6366f1;
    --pywry-accent-hover: #4f46e5;
    --pywry-radius: 8px;
}

.pywry-theme-dark {
    --pywry-bg-primary: #0f172a;
    --pywry-bg-secondary: #1e293b;
    --pywry-text-primary: #f8fafc;
    --pywry-border-color: #334155;
}

.pywry-theme-light {
    --pywry-bg-primary: #ffffff;
    --pywry-bg-secondary: #f3f4f6;
    --pywry-text-primary: #111827;
    --pywry-border-color: #e5e7eb;
}

/* Toolbar customization */
.pywry-toolbar {
    padding: 12px 16px;
    gap: 12px;
}

/* Button focus ring */
.pywry-button:focus-visible {
    outline: 2px solid var(--pywry-accent);
    outline-offset: 2px;
}

/* Input focus styling */
.pywry-input:focus {
    border-color: var(--pywry-accent);
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2);
}
```

Apply it:

```python
app.show(
    HtmlContent(html="<h1>Styled</h1>", css_files=["custom-theme.css"]),
)
```

## Next Steps

- **[Toolbar System](toolbars.md)** — Building interactive controls
- **[Modals](modals.md)** — Popup dialogs with components
- **[Toasts & Alerts](toasts.md)** — Notification styling
- **[Hot Reload](hot-reload.md)** — Live CSS updates during development
