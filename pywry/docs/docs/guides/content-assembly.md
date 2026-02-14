# Content Assembly

When you call `app.show()`, PyWry doesn't just render your HTML. It assembles a complete document from multiple components — base styles, the JavaScript bridge, your custom CSS and scripts, toolbar layouts, library code, and your content. This page explains exactly what gets built and in what order.

## The Assembly Pipeline

Here's what happens when `app.show(content)` is called in native window mode (the most complete path):

1. Normalize content → HtmlContent
2. Build WindowConfig (title, dimensions, theme, libraries)
3. Resolve window label
4. **Build all HTML components**
    - CSP meta tag
    - Base styles — pywry.css + toast.css
    - Global CSS from AssetSettings
    - Custom CSS — inline_css + css_files
    - Library scripts — Plotly.js / AG Grid
    - JSON data injection
    - Init script — bridge, theme, events
    - Global + custom scripts
    - Toolbar layout wrapping
    - Modal HTML + scripts
5. Detect complete doc vs. fragment
6. Assemble final HTML document
7. Send to rendering path (native / notebook / browser)

## What Goes Into `<head>`

The `<head>` section is built from these components, injected in this exact order:

### 1. Content Security Policy

A `<meta>` CSP tag that controls which resources the page can load. Built from your `SecuritySettings`:

```html
<meta http-equiv="Content-Security-Policy"
      content="default-src 'self' 'unsafe-inline' 'unsafe-eval'; ...">
```

### 2. Base Styles

PyWry's built-in CSS:

- **`pywry.css`** — Layout system, container styles, theme variables, scrollbar styling, the `.pywry-container` wrapper, and toolbar/modal base layout
- **`toast.css`** — Toast notification positioning and animations
- **Custom theme CSS** — If `ThemeSettings.css_file` is set, that file is appended

```html
<style>/* pywry.css — layout, theme vars, containers */</style>
<style>/* toast.css — notifications */</style>
<style>/* optional: your theme.css override */</style>
```

### 3. Global CSS

CSS files specified in `AssetSettings.css_files` (from your `pywry.toml` or `pyproject.toml`). These apply to every window, not just one:

```toml
# pywry.toml
[asset]
css_files = ["styles/global.css", "styles/brand.css"]
```

```html
<style id="hash-abc123">/* global.css */</style>
<style id="hash-def456">/* brand.css */</style>
```

Each `<style>` tag gets a hash-based `id` so the hot reload system can target it precisely.

### 4. Custom CSS (from HtmlContent)

Your per-window CSS, in this order:

1. `HtmlContent.inline_css` → `<style id="pywry-inline-css">...</style>`
2. Each file in `HtmlContent.css_files` → `<style id="hash-xxx">...</style>`

### 5. Library Scripts

If `include_plotly=True` or `include_aggrid=True`, the full library JavaScript is included:

- **Plotly**: `plotly.min.js` + `plotly-defaults.js` (configures default templates, themes)
- **AG Grid**: `ag-grid-community.min.js` + `ag-grid-defaults.js` (base grid setup) + AG Grid CSS

These are bundled assets loaded from disk — not CDN URLs — so they work offline.

### 6. JSON Data

If `HtmlContent.json_data` is set, it's serialized and injected:

```html
<script>window.json_data = {"users": [{"name": "Alice"}, {"name": "Bob"}]};</script>
```

Uses a custom encoder that handles numpy arrays, datetime objects, and other Python types.

### 7. Initialization Script

This is the largest single injection — the core JavaScript bridge built by `build_init_script()`:

```html
<script>
    window.__PYWRY_LABEL__ = 'my-window';  // Window identity

    // PyWry Bridge (window.pywry)
    //   .emit(), .on(), .off(), .result(), .dispatch(), ._trigger()

    // System Event Handlers
    //   pywry:inject-css, pywry:remove-css, pywry:set-style,
    //   pywry:set-content, pywry:download, pywry:refresh, pywry:navigate

    // Toast Notification System
    //   window.pywry.toast(), alert types, positioning, animations

    // Tooltip Manager
    //   data-tooltip attribute handling

    // Theme Manager
    //   pywry:update-theme handler, CSS class toggling

    // Event Bridge
    //   Tauri IPC listeners (native) or WebSocket handlers (browser)
    //   Routes events between Python and JS

    // Toolbar Bridge
    //   Connects toolbar component events to window.pywry.emit()

    // Cleanup Handler
    //   SecretInput cleanup, page unload handling

    // Hot Reload (when enabled)
    //   WebSocket file watcher, CSS injection, page refresh
</script>
```

### 8. Toolbar Script

If toolbars are present, the toolbar component JavaScript is included. This handles rendering toolbar items (buttons, inputs, selects, etc.) and wiring their change/click events to `window.pywry.emit()`.

### 9. Modal Scripts

If modals are present, the modal system JavaScript is included — open/close/toggle logic, backdrop handling, and event wiring.

### 10. Global Scripts

JavaScript files from `AssetSettings.script_files` — global scripts that apply to every window.

### 11. Custom Scripts

Each file in `HtmlContent.script_files` is injected as a `<script>` tag.

### 12. Custom Init

`HtmlContent.init_script` runs last — it's the final `<script>` tag in the document. By the time it executes, everything else is available: `window.pywry`, `window.json_data`, all CSS applied, all libraries loaded.

## What Goes Into `<body>`

### Content Wrapping

Your HTML content is placed inside a container div:

```html
<body>
    <div class="pywry-container">
        <!-- your HTML here -->
    </div>
</body>
```

### Toolbar Layout

When toolbars are present, `wrap_content_with_toolbars()` wraps your content in a flexbox layout structure:

<div style="font-family: monospace; text-align: center; max-width: 520px; margin: 1.5em auto;">
  <div style="background: #2d3748; color: #e2e8f0; padding: 10px; border: 1px solid #4a5568;">HEADER <span style="opacity:.5">— full width</span></div>
  <div style="display: flex; border-left: 1px solid #4a5568; border-right: 1px solid #4a5568;">
    <div style="background: #374151; color: #e2e8f0; padding: 20px 12px; border-right: 1px solid #4a5568; writing-mode: vertical-rl; text-orientation: mixed;">LEFT</div>
    <div style="flex: 1;">
      <div style="background: #1e3a5f; color: #93c5fd; padding: 8px; border-bottom: 1px solid #3b82f6;">TOP toolbar</div>
      <div style="background: #134e4a; color: #5eead4; padding: 18px 8px; border-bottom: 1px solid #14b8a6;">YOUR CONTENT + INSIDE toolbar</div>
      <div style="background: #1e3a5f; color: #93c5fd; padding: 8px;">BOTTOM toolbar</div>
    </div>
    <div style="background: #374151; color: #e2e8f0; padding: 20px 12px; border-left: 1px solid #4a5568; writing-mode: vertical-rl; text-orientation: mixed;">RIGHT</div>
  </div>
  <div style="background: #2d3748; color: #e2e8f0; padding: 10px; border: 1px solid #4a5568;">FOOTER <span style="opacity:.5">— full width</span></div>
</div>

The actual HTML structure:

```html
<div class="pywry-layout">
    <div class="pywry-header"><!-- header toolbars --></div>
    <div class="pywry-body">
        <div class="pywry-left"><!-- left toolbars --></div>
        <div class="pywry-center">
            <div class="pywry-top"><!-- top toolbars --></div>
            <div class="pywry-content">
                <div class="pywry-scroll-container">
                    <!-- YOUR HTML CONTENT -->
                    <div class="pywry-inside"><!-- inside toolbars --></div>
                </div>
            </div>
            <div class="pywry-bottom"><!-- bottom toolbars --></div>
        </div>
        <div class="pywry-right"><!-- right toolbars --></div>
    </div>
    <div class="pywry-footer"><!-- footer toolbars --></div>
</div>
<div class="pywry-toast-container pywry-toast-container--top-right"></div>
```

Even without toolbars, your content is wrapped in the `pywry-content` → `pywry-scroll-container` structure, plus the toast container.

### Modal Injection

Modal HTML is injected before `</body>`. Each modal is a hidden overlay that can be opened with `modal:open:<id>` events:

```html
    <!-- modal overlays, hidden by default -->
    <div class="pywry-modal-overlay" id="modal-settings" style="display:none">
        <div class="pywry-modal">
            <div class="pywry-modal-header">Settings</div>
            <div class="pywry-modal-body"><!-- modal items --></div>
        </div>
    </div>
</body>
```

## Fragment vs. Complete Document

PyWry detects which type of HTML you provided:

**Fragment** (no `<!DOCTYPE` or `<html>` tag):

```python
HtmlContent(html="<h1>Hello</h1>")
```

PyWry builds the entire document around it — `<!DOCTYPE html>`, `<html>` with theme class, `<head>` with all injections, `<body>` with `.pywry-container` wrapping.

**Complete document** (starts with `<!DOCTYPE` or `<html>`):

```python
HtmlContent(html="<!DOCTYPE html><html><head>...</head><body>...</body></html>")
```

PyWry injects all assets before the `</head>` tag and adds the theme class to the `<html>` tag. Your document structure is preserved. Modals are injected before `</body>`.

## Theme Integration

The `<html>` tag always gets a theme class:

- `pywry-theme-dark` — dark mode (default)
- `pywry-theme-light` — light mode

This class is used by pywry.css to set CSS custom properties (colors, backgrounds, borders). The theme manager JavaScript handles runtime toggling via the `pywry:update-theme` event.

Additionally, PyWry auto-corrects AG Grid and Plotly themes to match the window theme:

- `ag-theme-alpine` → `ag-theme-alpine-dark` when dark mode
- `template: 'plotly_white'` → `template: 'plotly_dark'` when dark mode

## Asset Loading

The `AssetLoader` resolves all file paths and caches file contents:

```
AssetLoader
    ├─ base_dir: Path (defaults to cwd)
    ├─ load_css(path) → reads file, caches content, generates hash ID
    ├─ load_script(path) → reads file, caches content
    └─ get_asset_id(path) → deterministic ID for hot reload targeting
```

Paths in `css_files` and `script_files` are resolved relative to `base_dir`. If `AssetSettings.path` is set in your config, that becomes the base directory for global assets.

## The Complete Picture

Putting it all together, here's a concrete example. Given:

```python
from pywry import PyWry, HtmlContent, Toolbar, Button

app = PyWry()

content = HtmlContent(
    html="<div id='output'>Ready</div>",
    css_files=["styles/app.css"],
    inline_css="#output { font-size: 1.2em; }",
    json_data={"version": "2.0"},
    init_script="document.getElementById('output').textContent = 'v' + window.json_data.version;",
)

toolbar = Toolbar(position="top", items=[
    Button(label="Run", event="app:run"),
])

app.show(content, title="My App", toolbars=[toolbar])
```

PyWry assembles:

```html
<!DOCTYPE html>
<html lang="en" class="pywry-native pywry-theme-dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Content-Security-Policy" content="...">
    <title>My App</title>

    <!-- 1. Base styles -->
    <style>/* pywry.css */</style>
    <style>/* toast.css */</style>

    <!-- 2. Global CSS (from config) -->
    <!-- (none in this example) -->

    <!-- 3. Custom CSS -->
    <style id="pywry-inline-css">#output { font-size: 1.2em; }</style>
    <style id="css-a1b2c3">/* styles/app.css content */</style>

    <!-- 4. Libraries (none - no Plotly/AG Grid) -->

    <!-- 5. JSON data -->
    <script>window.json_data = {"version": "2.0"};</script>

    <!-- 6. Init script (bridge, events, theme, toolbars) -->
    <script>
        window.__PYWRY_LABEL__ = 'pywry-abc12345';
        // ... PyWry bridge, system events, theme manager, event bridge ...
    </script>

    <!-- 7. Toolbar component script -->
    <script>/* toolbar rendering + event wiring */</script>

    <!-- 8. Custom init (runs last) -->
    <script>document.getElementById('output').textContent = 'v' + window.json_data.version;</script>
</head>
<body>
    <!-- Toolbar layout wrapping -->
    <div class="pywry-layout">
        <div class="pywry-body">
            <div class="pywry-center">
                <div class="pywry-top">
                    <!-- Top toolbar with Run button -->
                    <div class="pywry-toolbar pywry-toolbar--top">
                        <button class="pywry-btn" data-event="app:run">Run</button>
                    </div>
                </div>
                <div class="pywry-content">
                    <div class="pywry-scroll-container">
                        <div id="output">Ready</div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    <div class="pywry-toast-container pywry-toast-container--top-right"></div>
</body>
</html>
```

This exact same assembly runs for all rendering paths — native, notebook, and browser. The only difference is the transport layer used to deliver it.

## Next Steps

- **[app.show()](app-show.md)** — The full `show()` method and its parameters
- **[HtmlContent](html-content.md)** — Controlling CSS, JS, and data injection
- **[Event System](events.md)** — How the JavaScript bridge communicates with Python
- **[Configuration](configuration.md)** — Global settings, asset paths, and security
