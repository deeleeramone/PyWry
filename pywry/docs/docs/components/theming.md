# Theming & CSS

PyWry ships with dark and light themes and automatic OS detection. All styles are driven by CSS custom properties — override them to customize the look. For complete variable definitions and class references, see the [CSS Reference](../reference/css/index.md).

---

## Setting the Theme

The `PyWry` constructor accepts a `theme` parameter. The default is `"dark"`.

```python
from pywry import PyWry

app = PyWry(theme="dark")    # always dark
app = PyWry(theme="light")   # always light
app = PyWry(theme="system")  # follow OS preference
```

The config file default for `mode` is `"system"`:

```toml
# pywry.toml
[theme]
mode = "dark"
```

Or via environment variable:

```bash
export PYWRY_THEME__MODE=dark
```

### Switching at Runtime

From Python (using the handle returned by `show()` or `show_plotly()`):

```python
handle.emit("pywry:update-theme", {"theme": "dark"})
handle.emit("pywry:update-theme", {"theme": "light"})
```

From JavaScript inside the window:

```javascript
window.pywry.emit("pywry:update-theme", { theme: "dark" });
window.pywry.emit("pywry:update-theme", { theme: "light" });
```

The handler checks whether the `theme` value contains `"dark"` — any string containing `"dark"` activates dark mode, anything else activates light mode.

When the theme switches, PyWry automatically:

- Updates `<html>` classes — adds `dark` + `pywry-theme-dark`, or `light` + `pywry-theme-light`
- Also updates `.pywry-widget` and `.pywry-container` elements with the matching theme class
- Switches Plotly figures between `plotly_dark` and `plotly_white` templates (deep-merged with any user overrides)
- Swaps AG Grid theme classes (adds/removes `-dark` suffix on the grid element)
- Fires `pywry:theme-update` with `{ mode: resolvedMode, original: mode }` so your code can react

---

## Overriding CSS Variables

All styles are driven by CSS custom properties. Override them to change the look without touching component internals.

### Theme-independent overrides

Variables set on `:root` apply regardless of theme. These are the actual variables defined in `pywry.css`:

```css
:root {
    --pywry-accent: #6366f1;           /* default: #0078d4 */
    --pywry-accent-hover: #4f46e5;     /* default: #106ebe */
    --pywry-radius: 8px;               /* default: 4px */
    --pywry-font-size: 15px;           /* default: 14px */
    --pywry-font-family: 'Your Font', sans-serif;
}
```

### Per-theme overrides

The dark theme is defined on `:root, html.dark, .pywry-theme-dark`. The light theme is defined on `html.light, .pywry-theme-light`. Target these selectors to set different values:

```css
.pywry-theme-dark {
    --pywry-bg-primary: #0f172a;       /* default: #212124 */
    --pywry-bg-secondary: #1e293b;     /* default: rgba(21, 21, 24, 1) */
    --pywry-text-primary: #f8fafc;     /* default: #ebebed */
    --pywry-border-color: #334155;     /* default: #333 */
}

.pywry-theme-light {
    --pywry-bg-primary: #ffffff;       /* default: #f5f5f5 */
    --pywry-bg-secondary: #f3f4f6;    /* default: #ffffff */
    --pywry-text-primary: #111827;     /* default: #000000 */
    --pywry-border-color: #e5e7eb;    /* default: #ccc */
}
```

The most commonly overridden variable groups:

| Group | Key variables | Reference |
|:------|:-------------|:----------|
| Colors & backgrounds | `--pywry-bg-primary`, `--pywry-bg-secondary`, `--pywry-accent` | [Core CSS](../reference/css/core.md) |
| Typography | `--pywry-font-family`, `--pywry-font-size` | [Core CSS](../reference/css/core.md) |
| Spacing & radius | `--pywry-radius`, `--pywry-spacing-xs` / `sm` / `md` / `lg` | [Core CSS](../reference/css/core.md) |
| Buttons | `--pywry-btn-primary-bg` / `text` / `hover`, `--pywry-btn-secondary-*` | [Core CSS](../reference/css/core.md) |
| Toast notifications | `--pywry-toast-bg`, `--pywry-toast-color`, `--pywry-toast-accent` | [Toast CSS](../reference/css/toast.md) |
| TradingView charts | `--pywry-tvchart-bg`, `--pywry-tvchart-text`, `--pywry-tvchart-up` / `down` | [TradingView CSS](../reference/css/tvchart.md) |

Chat CSS uses the core `--pywry-*` variables (bg, text, border, font) — there are no separate chat-specific CSS variables.

For the complete list of every variable with default values, see the [CSS Reference](../reference/css/index.md).

---

## Loading Custom CSS

There are three layers for loading CSS, each targeting a different scope.

### 1. Global CSS (applies to every window)

```toml
# pywry.toml
[theme]
css_file = "styles/brand.css"        # single theme override file

[asset]
css_files = ["styles/global.css"]    # additional global stylesheets
```

The `css_file` under `[theme]` is loaded after the base `pywry.css`, `toast.css`, and `chat.css`. The `css_files` under `[asset]` are loaded after the theme CSS file.

### 2. Per-content CSS (applies to one `HtmlContent`)

```python
from pywry import HtmlContent

content = HtmlContent(
    html="<div id='app'></div>",
    css_files=["styles/page.css"],
    inline_css="body { font-size: 16px; }",
)
```

`css_files` loads external files into `<style>` tags. `inline_css` injects a raw `<style id="pywry-inline-css">` block.

### 3. Runtime injection (add/remove CSS dynamically)

From Python (using the handle returned by `show()`):

```python
# Inject — creates or updates a <style> element with the given ID
handle.emit("pywry:inject-css", {
    "css": ".highlight { background: yellow; }",
    "id": "my-highlights",
})

# Remove — deletes the <style> element by ID
handle.emit("pywry:remove-css", {"id": "my-highlights"})
```

From JavaScript inside the window:

```javascript
window.pywry.injectCSS(".highlight { color: red; }", "my-highlights");
window.pywry.removeCSS("my-highlights");
```

### Injection order in the generated document

The `<head>` of the generated HTML is assembled in this order:

1. CSP meta tag
2. Base styles — `pywry.css`, `toast.css`, `chat.css`, then `[theme] css_file` if set
3. Global CSS — `[asset] css_files`
4. Per-content CSS — `HtmlContent.css_files` and `inline_css`
5. Library scripts — Plotly.js, AG Grid JS/CSS, TradingView JS/CSS
6. Init script, toolbar script, modal script, global scripts, custom scripts

Your custom CSS loads before the library scripts, so library-injected styles may override yours. Use higher specificity or `!important` if needed.

---

## Targeting Components

Toolbar components use these CSS classes (from `pywry.css`):

```css
.pywry-btn             { /* all buttons */ }
.pywry-select          { /* native <select> element */ }
.pywry-input           { /* base input styling (text, number, date) */ }
.pywry-toggle          { /* toggle switch container */ }
.pywry-toggle-slider   { /* toggle switch track */ }
.pywry-toolbar         { /* toolbar container */ }
.pywry-toolbar-content { /* inner content wrapper */ }
.pywry-modal-overlay   { /* modal backdrop */ }
.pywry-modal-container { /* modal dialog box */ }
```

Target a specific component by its `component_id` (rendered as the element's `id`):

```css
#theme-select { min-width: 160px; }
#submit-btn:hover { transform: translateY(-1px); }
```

Button variants use modifier classes on `.pywry-btn`:

```css
.pywry-btn                  { /* primary (default) */ }
.pywry-btn.pywry-btn-secondary { /* subtle background */ }
.pywry-btn.pywry-btn-neutral   { /* blue accent */ }
.pywry-btn.pywry-btn-ghost     { /* transparent */ }
.pywry-btn.pywry-btn-outline   { /* border only */ }
.pywry-btn.pywry-btn-danger    { /* red */ }
.pywry-btn.pywry-btn-warning   { /* orange */ }
.pywry-btn.pywry-btn-icon      { /* square, icon-only */ }
```

Button sizes: `.pywry-btn-xs`, `.pywry-btn-sm`, `.pywry-btn-lg`, `.pywry-btn-xl`.

For the full list of CSS classes, see the [Core Stylesheet reference](../reference/css/core.md).

---

## Plotly Theming

PyWry automatically switches Plotly between `plotly_dark` and `plotly_white` templates when the theme changes. To customize chart colors per theme while keeping automatic switching, use `template_dark` and `template_light` on `PlotlyConfig`:

```python
from pywry import PlotlyConfig

config = PlotlyConfig(
    template_dark={
        "layout": {
            "paper_bgcolor": "#1a1a2e",
            "plot_bgcolor": "#16213e",
            "font": {"color": "#e0e0e0"},
        }
    },
    template_light={
        "layout": {
            "paper_bgcolor": "#ffffff",
            "plot_bgcolor": "#f0f0f0",
            "font": {"color": "#222222"},
        }
    },
)

app.show_plotly(fig, config=config)
```

Overrides are **deep-merged** on top of the built-in base template — your values always win, anything unset is inherited.

For transparent charts that inherit the window background:

```python
fig.update_layout(paper_bgcolor="transparent", plot_bgcolor="transparent")
```

## AG Grid Theming

AG Grid theme classes are swapped automatically when the PyWry theme changes. The base theme is set via the `aggrid_theme` parameter on `show_grid()`:

```python
app.show_grid(
    data=df,
    aggrid_theme="alpine",  # "quartz", "alpine", "balham", or "material"
)
```

In dark mode, PyWry renders the grid as `ag-theme-alpine-dark`. In light mode, `ag-theme-alpine`. When the theme switches at runtime, the `-dark` suffix is added or removed automatically.

---

## Full Example

A complete custom theme file overriding colors, layout, and component styles:

```css
/* custom-theme.css */

/* Shared overrides (theme-independent) */
:root {
    --pywry-accent: #6366f1;
    --pywry-accent-hover: #4f46e5;
    --pywry-radius: 8px;
}

/* Dark overrides */
.pywry-theme-dark {
    --pywry-bg-primary: #0f172a;
    --pywry-bg-secondary: #1e293b;
    --pywry-text-primary: #f8fafc;
    --pywry-border-color: #334155;
}

/* Light overrides */
.pywry-theme-light {
    --pywry-bg-primary: #ffffff;
    --pywry-bg-secondary: #f3f4f6;
    --pywry-text-primary: #111827;
    --pywry-border-color: #e5e7eb;
}

/* Component tweaks */
.pywry-toolbar { padding: 12px 16px; gap: 12px; }
.pywry-btn:focus-visible { outline: 2px solid var(--pywry-accent); outline-offset: 2px; }
.pywry-input:focus { border-color: var(--pywry-accent); box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2); }
```

Load it globally or per-content:

=== "Global (pywry.toml)"

    ```toml
    [theme]
    css_file = "custom-theme.css"
    ```

=== "Per-content"

    ```python
    app.show(HtmlContent(html="<h1>Styled</h1>", css_files=["custom-theme.css"]))
    ```

---

## Reference

For complete variable definitions, default values, and class selectors:

- **[CSS Reference](../reference/css/index.md)** — All variables with dark/light defaults
- **[Core Stylesheet](../reference/css/core.md)** — Layout, toolbar, buttons, inputs, modal, scrollbars
- **[Chat Stylesheet](../reference/css/chat.md)** — Chat messages, threads, artifacts
- **[Toast Stylesheet](../reference/css/toast.md)** — Notification types and positioning
- **[TradingView Stylesheet](../reference/css/tvchart.md)** — Chart header, legend, drawing tools
