# CSS Reference

PyWry provides a comprehensive CSS system with theme support, CSS variables, and utility classes.

## Theme Classes

Apply to root element or widget container:

| Class | Description |
|-------|-------------|
| `.pywry-theme-dark` | Dark theme (default) |
| `.pywry-theme-light` | Light theme |
| `.pywry-theme-system` | Follow OS preference |

```html
<div class="pywry-widget pywry-theme-dark">
  <!-- Dark themed content -->
</div>
```

## CSS Variables

### Typography

```css
:root {
    --pywry-font-family: Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    --pywry-font-size: 14px;
    --pywry-font-weight-normal: 400;
    --pywry-font-weight-medium: 500;
}
```

### Spacing & Layout

```css
:root {
    --pywry-radius: 4px;
    --pywry-radius-lg: 6px;
    --pywry-spacing-xs: 2px;
    --pywry-spacing-sm: 4px;
    --pywry-spacing-md: 6px;
    --pywry-spacing-lg: 8px;
}
```

### Widget Sizing

```css
:root {
    --pywry-widget-width: 100%;
    --pywry-widget-min-height: 200px;
    --pywry-widget-height: 500px;
    --pywry-grid-min-height: 200px;
}
```

### Transitions

```css
:root {
    --pywry-transition-fast: 0.1s ease;
    --pywry-transition-normal: 0.2s ease;
}
```

### Accent Colors (Shared)

```css
:root {
    --pywry-accent: #0078d4;
    --pywry-accent-hover: #106ebe;
    --pywry-text-accent: rgb(51, 187, 255);
    --pywry-btn-neutral-bg: rgb(0, 136, 204);
    --pywry-btn-neutral-text: #ffffff;
    --pywry-btn-neutral-hover: rgb(0, 115, 173);
}
```

### Dark Theme Colors

```css
.pywry-theme-dark {
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
    
    /* Tab Group */
    --pywry-tab-bg: #2a2a2e;
    --pywry-tab-active-bg: #3d3d42;
    --pywry-tab-hover-bg: #353538;
    
    /* Buttons */
    --pywry-btn-primary-bg: #e2e2e2;
    --pywry-btn-primary-text: #151518;
    --pywry-btn-primary-hover: #cccccc;
    --pywry-btn-secondary-bg: #3d3d42;
    --pywry-btn-secondary-text: #ebebed;
    --pywry-btn-secondary-hover: #4a4a50;
    --pywry-btn-secondary-border: rgba(90, 90, 100, 0.5);
}
```

### Light Theme Colors

```css
.pywry-theme-light {
    --pywry-bg-primary: #f5f5f5;
    --pywry-bg-secondary: #ffffff;
    --pywry-bg-hover: rgba(0, 0, 0, 0.06);
    --pywry-bg-overlay: rgba(255, 255, 255, 0.8);
    --pywry-text-primary: #000000;
    --pywry-text-secondary: #666666;
    --pywry-text-muted: #999999;
    --pywry-border-color: #ccc;
    --pywry-border-focus: #999;
    
    /* Tab Group */
    --pywry-tab-bg: #e8e8ec;
    --pywry-tab-active-bg: #ffffff;
    --pywry-tab-hover-bg: #f0f0f4;
    
    /* Buttons */
    --pywry-btn-primary-bg: #2c2c32;
    --pywry-btn-primary-text: #ffffff;
    --pywry-btn-primary-hover: #1a1a1e;
    --pywry-btn-secondary-bg: #d0d0d8;
    --pywry-btn-secondary-text: #2c2c32;
    --pywry-btn-secondary-hover: #c0c0c8;
    --pywry-btn-secondary-border: rgba(180, 180, 190, 1);
}
```

## Layout Classes

### Container

```css
.pywry-widget {
    /* Main widget container */
    width: var(--pywry-widget-width);
    min-height: var(--pywry-widget-min-height);
    height: var(--pywry-widget-height);
    display: flex;
    flex-direction: column;
}

.pywry-container {
    /* Content container */
    flex: 1 1 0%;
    min-height: 0;
    display: flex;
    flex-direction: column;
}
```

### Toolbar Positions

```css
.pywry-toolbar { /* Base toolbar */ }
.pywry-toolbar-top { /* Top position */ }
.pywry-toolbar-bottom { /* Bottom position */ }
.pywry-toolbar-left { /* Left sidebar */ }
.pywry-toolbar-right { /* Right sidebar */ }
.pywry-toolbar-header { /* Header with bottom border */ }
.pywry-toolbar-footer { /* Footer with top border */ }
.pywry-toolbar-inside { /* Floating overlay */ }
```

### Toolbar Content

```css
.pywry-toolbar-content {
    /* Flex container for toolbar items */
    display: flex;
    flex-wrap: wrap;
    gap: var(--pywry-spacing-md);
    align-items: center;
}
```

## Component Classes

### Buttons

```css
.pywry-btn { /* Base button */ }
.pywry-btn-primary { /* Primary style */ }
.pywry-btn-secondary { /* Secondary style */ }
.pywry-btn-neutral { /* Blue neutral style */ }
.pywry-btn-danger { /* Red danger style */ }
.pywry-btn-success { /* Green success style */ }
.pywry-btn-sm { /* Small size */ }
.pywry-btn-md { /* Medium size (default) */ }
.pywry-btn-lg { /* Large size */ }
```

### Inputs

```css
.pywry-input { /* Base input */ }
.pywry-input-group { /* Label + input wrapper */ }
.pywry-input-label { /* Input label */ }
.pywry-select { /* Select dropdown */ }
.pywry-textarea { /* Textarea */ }
.pywry-input-secret { /* Password input */ }
```

### Toggle & Checkbox

```css
.pywry-toggle { /* Toggle switch */ }
.pywry-toggle-track { /* Toggle track */ }
.pywry-toggle-thumb { /* Toggle thumb */ }
.pywry-checkbox { /* Checkbox wrapper */ }
.pywry-checkbox-input { /* Checkbox input */ }
.pywry-checkbox-label { /* Checkbox label */ }
```

### Tabs

```css
.pywry-tab-group { /* Tab container */ }
.pywry-tab { /* Individual tab */ }
.pywry-tab.active { /* Active tab */ }
```

### Slider

```css
.pywry-slider { /* Slider wrapper */ }
.pywry-slider-input { /* Range input */ }
.pywry-slider-value { /* Value display */ }
```

### Marquee

```css
.pywry-marquee { /* Scrolling container */ }
.pywry-marquee-track { /* Animated track */ }
.pywry-marquee-content { /* Content wrapper */ }
.pywry-marquee-left { /* Scroll left */ }
.pywry-marquee-right { /* Scroll right */ }
.pywry-marquee-up { /* Scroll up */ }
.pywry-marquee-down { /* Scroll down */ }
.pywry-marquee-static { /* No animation */ }
.pywry-marquee-pause { /* Pause on hover */ }
.pywry-ticker-item { /* Ticker item */ }
```

### Divs

```css
.pywry-div { /* Div component */ }
```

## State Classes

```css
.pywry-disabled { /* Disabled state */ }
.pywry-collapsed { /* Collapsed toolbar */ }
.pywry-loading { /* Loading state */ }
```

## Scrollbar Classes

Custom scrollbars for native windows:

```css
.pywry-scroll-wrapper { /* Scroll container wrapper */ }
.pywry-scroll-container { /* Scrollable content */ }
.pywry-scrollbar-track-v { /* Vertical scrollbar track */ }
.pywry-scrollbar-track-h { /* Horizontal scrollbar track */ }
.pywry-scrollbar-thumb-v { /* Vertical scrollbar thumb */ }
.pywry-scrollbar-thumb-h { /* Horizontal scrollbar thumb */ }
```

## Native Window Classes

Applied to `<html>` element in Tauri windows:

```css
html.pywry-native { /* Native window context */ }
html.dark { /* Dark mode on html */ }
html.light { /* Light mode on html */ }
```

## Custom CSS Injection

Inject CSS at runtime via Python:

```python
widget.emit("pywry:inject-css", {
    "id": "my-custom-styles",
    "css": """
        .my-class {
            color: var(--pywry-text-accent);
            background: var(--pywry-bg-secondary);
        }
    """
})
```

Remove injected CSS:

```python
widget.emit("pywry:remove-css", {"id": "my-custom-styles"})
```

## Inline Styles

Set inline styles via Python:

```python
widget.emit("pywry:set-style", {
    "id": "my-element",
    "styles": {
        "fontSize": "24px",
        "fontWeight": "bold",
        "color": "red"
    }
})
```

Or by selector:

```python
widget.emit("pywry:set-style", {
    "selector": ".my-class",
    "styles": {"display": "none"}
})
```

## Override Examples

### Custom Widget Height

```python
from pywry import PyWry

app = PyWry(
    html="<h1>Tall Widget</h1>",
    head="""
    <style>
        :root {
            --pywry-widget-height: 800px;
        }
    </style>
    """
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
widget.emit("pywry:inject-css", {
    "id": "custom-buttons",
    "css": """
        .pywry-btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border: none;
        }
        .pywry-btn-primary:hover {
            background: linear-gradient(135deg, #764ba2 0%, #667eea 100%);
        }
    """
})
```

## AG Grid Theme Integration

PyWry automatically syncs AG Grid themes:

```css
/* Dark mode */
.ag-theme-quartz-dark { /* Applied automatically */ }

/* Light mode */
.ag-theme-quartz { /* Applied automatically */ }
```

Update theme via event:

```python
widget.emit("pywry:update-theme", {"theme": "ag-theme-quartz"})
```
