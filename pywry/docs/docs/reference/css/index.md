# CSS Reference

PyWry's styling system is driven by CSS custom properties (variables) with dark and light theme support. The CSS is organized across four source files, each covering a distinct feature area.

## Source Files

| File | Description | Page |
|:-----|:------------|:-----|
| `pywry.css` | Core layout, toolbar, buttons, inputs, controls, modal, scrollbars, utilities | [Core Stylesheet](core.md) |
| `chat.css` | Chat UI — messages, threads, tool calls, artifacts, syntax highlighting | [Chat Stylesheet](chat.md) |
| `toast.css` | Toast notifications — types, positions, blocking overlay | [Toast Stylesheet](toast.md) |
| `tvchart.css` | TradingView chart UI — header, legend, drawing tools, settings panels | [TradingView Stylesheet](tvchart.md) |

---

## CSS Variables

All component styles are driven by CSS custom properties. Override them to customize the entire look.

### Shared Variables (theme-independent)

```css
:root {
    /* Typography */
    --pywry-font-family: Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    --pywry-font-size: 14px;
    --pywry-font-weight-normal: 400;
    --pywry-font-weight-medium: 500;
    --pywry-font-mono: 'Cascadia Code', 'Fira Code', Consolas, monospace;

    /* Spacing & Radius */
    --pywry-radius: 4px;
    --pywry-radius-lg: 6px;
    --pywry-spacing-xs: 2px;
    --pywry-spacing-sm: 4px;
    --pywry-spacing-md: 6px;
    --pywry-spacing-lg: 8px;

    /* Widget Sizing */
    --pywry-widget-width: 100%;
    --pywry-widget-min-height: 200px;
    --pywry-widget-height: 500px;
    --pywry-grid-min-height: 200px;

    /* Transitions */
    --pywry-transition-fast: 0.1s ease;
    --pywry-transition-normal: 0.2s ease;

    /* Accent Colors */
    --pywry-accent: #0078d4;
    --pywry-accent-hover: #106ebe;
    --pywry-text-accent: rgb(51, 187, 255);
    --pywry-btn-neutral-bg: rgb(0, 136, 204);
    --pywry-btn-neutral-text: #ffffff;
    --pywry-btn-neutral-hover: rgb(0, 115, 173);

    /* Scrollbar */
    --pywry-scrollbar-size: 10px;
    --pywry-scrollbar-thumb: rgba(155, 155, 155, 0.5);
    --pywry-scrollbar-thumb-hover: rgba(175, 175, 175, 0.7);

    /* Marquee */
    --pywry-marquee-speed: 15s;

    /* Toast */
    --pywry-toast-bg: rgba(30, 30, 30, 0.95);
    --pywry-toast-color: #ffffff;
    --pywry-toast-accent: #0ea5e9;

    /* Modal */
    --pywry-modal-overlay-opacity: 0.5;
}
```

### Dark Theme

```css
:root, html.dark, .pywry-theme-dark {
    --pywry-bg-primary: #212124;
    --pywry-bg-secondary: rgba(21, 21, 24, 1);
    --pywry-bg-tertiary: rgba(31, 30, 35, 1);
    --pywry-bg-quartary: rgba(36, 36, 42, 1);
    --pywry-bg-hover: rgba(255, 255, 255, 0.08);
    --pywry-bg-overlay: rgba(30, 30, 30, 0.8);

    --pywry-text-primary: #ebebed;
    --pywry-text-secondary: #a0a0a0;
    --pywry-text-muted: #707070;

    --pywry-border-color: #333;
    --pywry-border-focus: #555;

    --pywry-tab-bg: #2a2a2e;
    --pywry-tab-active-bg: #3d3d42;
    --pywry-tab-hover-bg: #353538;

    --pywry-btn-primary-bg: #e2e2e2;
    --pywry-btn-primary-text: #151518;
    --pywry-btn-primary-hover: #cccccc;
    --pywry-btn-secondary-bg: #3d3d42;
    --pywry-btn-secondary-text: #ebebed;
    --pywry-btn-secondary-hover: #4a4a50;
    --pywry-btn-secondary-border: rgba(90, 90, 100, 0.5);
}
```

### Light Theme

```css
html.light, .pywry-theme-light {
    --pywry-bg-primary: #f5f5f5;
    --pywry-bg-secondary: #ffffff;
    --pywry-bg-hover: rgba(0, 0, 0, 0.06);
    --pywry-bg-overlay: rgba(255, 255, 255, 0.8);

    --pywry-text-primary: #000000;
    --pywry-text-secondary: #666666;
    --pywry-text-muted: #999999;

    --pywry-border-color: #ccc;
    --pywry-border-focus: #999;

    --pywry-tab-bg: #e8e8ec;
    --pywry-tab-active-bg: #ffffff;
    --pywry-tab-hover-bg: #f0f0f4;

    --pywry-btn-primary-bg: #2c2c32;
    --pywry-btn-primary-text: #ffffff;
    --pywry-btn-primary-hover: #1a1a1e;
    --pywry-btn-secondary-bg: #d0d0d8;
    --pywry-btn-secondary-text: #2c2c32;
    --pywry-btn-secondary-hover: #c0c0c8;
    --pywry-btn-secondary-border: rgba(180, 180, 190, 1);
}
```

### System Theme

When `mode="system"`, PyWry uses dark by default and applies light overrides via `@media (prefers-color-scheme: light)`.

---

## Custom CSS Injection

### From Python

```python
# Inject CSS at runtime
handle.emit("pywry:inject-css", {
    "id": "my-custom-styles",
    "css": """
        .my-class {
            color: var(--pywry-text-accent);
            background: var(--pywry-bg-secondary);
        }
    """
})

# Remove injected CSS
handle.emit("pywry:remove-css", {"id": "my-custom-styles"})
```

### From JavaScript

```javascript
window.pywry.injectCSS(".highlight { color: red; }", "my-highlights");
window.pywry.removeCSS("my-highlights");
```

### Inline Styles via Event

```python
# By element ID
handle.emit("pywry:set-style", {
    "id": "my-element",
    "styles": {"fontSize": "24px", "fontWeight": "bold"}
})

# By CSS selector
handle.emit("pywry:set-style", {
    "selector": ".my-class",
    "styles": {"display": "none"}
})
```

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

---

## Override Examples

### Widget Height

```python
app = PyWry(
    html="<h1>Tall Widget</h1>",
    head='<style>:root { --pywry-widget-height: 800px; }</style>',
)
```

### Custom Theme

```python
custom_css = """
<style>
    .pywry-theme-custom {
        --pywry-bg-primary: #1a1a2e;
        --pywry-bg-secondary: #16213e;
        --pywry-text-primary: #e94560;
        --pywry-accent: #0f3460;
    }
</style>
"""

app = PyWry(html=content, head=custom_css)
```

### Custom Button Styles

```python
def on_customize(data, event_type, label):
    app.emit("pywry:inject-css", {
        "id": "custom-buttons",
        "css": """
            .pywry-btn-primary {
                background: linear-gradient(135deg, #667eea, #764ba2);
                border: none;
            }
            .pywry-btn-primary:hover {
                background: linear-gradient(135deg, #764ba2, #667eea);
            }
        """
    }, label)
```

---

## Data Attributes

PyWry uses HTML data attributes for event wiring and component configuration:

| Attribute | Used On | Description |
|:----------|:--------|:------------|
| `data-event` | Buttons, inputs | Event name to emit (e.g., `"app:save"`) |
| `data-component-id` | All components, modals | Unique component identifier |
| `data-data` | Buttons | JSON payload passed with the event |
| `data-tooltip` | Toolbar items | Tooltip text shown on hover |
| `data-value` | Dropdown options | Option value |
| `data-selected` | Dropdown options | Marks the selected option |
| `data-pywry-chart` | Plotly containers | Chart/Plotly instance identifier |
| `data-close-escape` | Modals | `"true"` to close on Escape key |
| `data-close-overlay` | Modals | `"true"` to close on overlay click |
| `data-reset-on-close` | Modals | `"true"` to reset form fields on close |
| `data-on-close-event` | Modals | Event emitted when modal closes |
| `data-collapsible` | Toolbars | `"true"` for collapsible toolbar |
| `data-resizable` | Toolbars | `"true"` for resizable toolbar |
| `data-accept-types` | Chat input | Accepted file types for upload |
