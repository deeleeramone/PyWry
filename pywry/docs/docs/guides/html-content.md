# HtmlContent

`HtmlContent` is the Pydantic model that describes what to render and what assets to include. While `app.show()` accepts a plain HTML string, passing an `HtmlContent` object gives you control over CSS files, JavaScript files, inline styles, JSON data injection, initialization scripts, and hot reload watching.

## Basic Usage

```python
from pywry import HtmlContent

# Minimal — just HTML
content = HtmlContent(html="<h1>Hello</h1>")

# With assets
content = HtmlContent(
    html="<div id='app'></div>",
    css_files=["styles/app.css"],
    script_files=["scripts/app.js"],
    inline_css="body { background: #1a1a2e; }",
    json_data={"users": [{"name": "Alice"}, {"name": "Bob"}]},
    init_script="console.log('App initialized');",
    watch=True,
)

app.show(content)
```

## Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `html` | `str` | *(required)* | The HTML content to render — a fragment or a complete document |
| `css_files` | `list[Path | str]` | `None` | Paths to CSS files to inject as `<style>` tags |
| `script_files` | `list[Path | str]` | `None` | Paths to JavaScript files to inject as `<script>` tags |
| `inline_css` | `str` | `None` | Raw CSS string injected as a `<style>` tag |
| `json_data` | `dict` | `None` | Data injected as `window.json_data` in the page |
| `init_script` | `str` | `None` | JavaScript code executed after all other scripts load |
| `watch` | `bool` | `False` | Enable hot reload watching for `css_files` and `script_files` |

## HTML: Fragment vs. Complete Document

PyWry handles both HTML fragments and complete documents.

**Fragment** — PyWry wraps it in a full `<!DOCTYPE html>` document with `<head>`, `<body>`, and all injected assets:

```python
content = HtmlContent(html="<h1>Hello</h1>")
# PyWry generates:
# <!DOCTYPE html>
# <html lang="en" class="pywry-native pywry-theme-dark">
# <head>
#     ... CSP, base styles, your CSS, JS bridge, scripts ...
# </head>
# <body>
#     <div class="pywry-container">
#         <h1>Hello</h1>
#     </div>
# </body>
# </html>
```

**Complete document** — If your HTML starts with `<!DOCTYPE` or `<html`, PyWry injects assets into your existing `<head>` tag instead of wrapping:

```python
content = HtmlContent(html="""<!DOCTYPE html>
<html>
<head><title>My App</title></head>
<body>
    <div id="root"></div>
</body>
</html>""")
# PyWry injects its CSS, JS bridge, and your assets before </head>
# Your structure is preserved
```

The detection is simple: if `html.strip()` starts with `<!doctype` or `<html` (case-insensitive), it's treated as a complete document.

## CSS Files

`css_files` accepts a list of file paths (strings or `Path` objects). Each file is read at build time and injected as an inline `<style>` tag with a hash-based ID for efficient hot reload tracking.

```python
content = HtmlContent(
    html="<div class='card'>Content</div>",
    css_files=[
        "styles/layout.css",
        "styles/theme.css",
        Path("components/card.css"),
    ],
)
```

Paths are resolved relative to the `AssetLoader` base directory (defaults to the current working directory). Absolute paths work too.

The order matters — files are injected in the order listed, so later files can override earlier ones.

## Script Files

`script_files` works the same way as `css_files` but for JavaScript. Each file is read and injected as a `<script>` tag.

```python
content = HtmlContent(
    html="<div id='chart'></div>",
    script_files=[
        "scripts/utils.js",
        "scripts/chart.js",
    ],
)
```

Scripts are injected after PyWry's core bridge scripts (so `window.pywry` is available) but before `init_script`.

## Inline CSS

`inline_css` is a raw CSS string injected as a `<style id="pywry-inline-css">` tag. Useful for quick overrides without creating a file:

```python
content = HtmlContent(
    html="<h1>Dashboard</h1>",
    inline_css="""
        body { background: #0f172a; color: #e2e8f0; }
        h1 { color: #38bdf8; font-size: 2rem; }
    """,
)
```

Inline CSS is injected before `css_files`, so file-based styles take precedence.

## JSON Data

`json_data` injects a dictionary as `window.json_data` in the page. This is the cleanest way to pass structured data from Python to JavaScript without embedding it in HTML attributes or template strings.

```python
import pandas as pd

df = pd.DataFrame({"name": ["Alice", "Bob"], "score": [95, 87]})

content = HtmlContent(
    html="<div id='table'></div>",
    json_data={"rows": df.to_dict("records"), "title": "Scores"},
    init_script="""
        const data = window.json_data;
        document.getElementById('table').innerHTML =
            '<h2>' + data.title + '</h2>' +
            '<pre>' + JSON.stringify(data.rows, null, 2) + '</pre>';
    """,
)
```

PyWry uses a custom JSON encoder that handles numpy arrays, numpy scalars, `datetime` objects, and other common Python types automatically.

## Init Script

`init_script` is raw JavaScript code that runs **after** all other scripts have loaded. Use it for initialization logic that depends on your CSS files, script files, or JSON data being available.

```python
content = HtmlContent(
    html="<canvas id='canvas'></canvas>",
    script_files=["scripts/drawing.js"],
    json_data={"points": [[10, 20], [30, 40], [50, 60]]},
    init_script="""
        // drawing.js and window.json_data are both available here
        const canvas = document.getElementById('canvas');
        drawPoints(canvas, window.json_data.points);
    """,
)
```

The execution order is:

1. Base PyWry styles (`pywry.css`, `toast.css`)
2. Global CSS (from `AssetSettings`)
3. Inline CSS + CSS files (from `HtmlContent`)
4. Library scripts (Plotly.js, AG Grid if enabled)
5. JSON data injection (`window.json_data = ...`)
6. PyWry bridge + system scripts (`window.pywry`, event bridge, theme manager)
7. Global scripts (from `AssetSettings`)
8. Custom script files (from `HtmlContent`)
9. **`init_script`** ← runs last

## Hot Reload with watch

When `watch=True`, PyWry monitors the files listed in `css_files` and `script_files` for changes. When a file is modified:

- **CSS changes**: The updated CSS is injected into the page via `pywry:inject-css`, replacing the existing `<style>` tag by ID. No page reload.
- **JS changes**: The page is fully refreshed (JavaScript can't be hot-swapped safely).

```python
content = HtmlContent(
    html="<div class='dashboard'>...</div>",
    css_files=["styles/dashboard.css"],
    script_files=["scripts/dashboard.js"],
    watch=True,
)
app.show(content)
# Now edit dashboard.css → changes appear instantly
# Edit dashboard.js → page reloads
```

You can also override `watch` at the `app.show()` level:

```python
# HtmlContent has watch=False, but we enable it at show time
app.show(content, watch=True)
```

See the [Hot Reload guide](hot-reload.md) for the full implementation details.

## Passing HtmlContent vs. Strings

You can always pass a string to `app.show()` — PyWry wraps it in an `HtmlContent(html=...)` internally:

```python
# These are equivalent:
app.show("<h1>Hello</h1>")
app.show(HtmlContent(html="<h1>Hello</h1>"))
```

Use `HtmlContent` when you need any of: CSS files, script files, inline CSS, JSON data, init script, or hot reload. Use plain strings for quick prototyping.

## Combining with Toolbars

`HtmlContent` handles the *content* and its assets. Toolbars and modals are separate concerns, passed to `app.show()`:

```python
from pywry import Toolbar, Button

content = HtmlContent(
    html="<div id='output'>Ready</div>",
    css_files=["styles/app.css"],
    json_data={"version": "1.0"},
)

toolbar = Toolbar(position="top", items=[
    Button(label="Run", event="app:run"),
])

app.show(content, toolbars=[toolbar], callbacks={"app:run": on_run})
```

The toolbar HTML wraps `HtmlContent.html` at build time. See [Content Assembly](content-assembly.md) for how all the pieces come together.

## Next Steps

- **[Content Assembly](content-assembly.md)** — How PyWry builds the final HTML document
- **[app.show()](app-show.md)** — The full `show()` method reference
- **[Hot Reload](hot-reload.md)** — Live CSS/JS updates during development
- **[Theming & CSS](theming.md)** — Theme system and CSS variables
