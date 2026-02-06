# Hot Reload

Hot reload enables live updates during development without restarting your application.

## Enable Hot Reload

### Via Constructor

```python
from pywry import PyWry

app = PyWry(hot_reload=True)
```

### At Runtime

```python
app.enable_hot_reload()
app.disable_hot_reload()
```

### Via Configuration

```toml
# pywry.toml
[hot_reload]
enabled = true
```

## Behavior

| File Type | Behavior |
|-----------|----------|
| **CSS** | Injected without page reload |
| **JS/HTML** | Full page refresh with scroll preservation |

## Watch Files

Use the `watch` parameter to enable file watching:

### With HtmlContent

```python
from pywry import PyWry, HtmlContent

app = PyWry(hot_reload=True)

content = HtmlContent(
    html="<div id='app'></div>",
    css_files=["styles/main.css", "styles/theme.css"],
    script_files=["js/app.js"],
    watch=True,
)

app.show(content)
```

### With show()

```python
app.show("<h1>Hello</h1>", watch=True)
```

When `watch=True`, editing `main.css` will inject new styles instantly without refreshing the page.

## Manual CSS Reload

```python
# Reload CSS for all windows
app.refresh_css()

# Reload CSS for specific window
app.refresh_css(label="main-window")
```

## Configuration Options

```toml
[hot_reload]
enabled = true
debounce_ms = 100        # Wait before reloading (milliseconds)
css_reload = "inject"    # "inject" or "refresh"
preserve_scroll = true   # Keep scroll position on JS refresh
watch_directories = ["./src", "./styles"]
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `enabled` | `false` | Enable hot reload |
| `debounce_ms` | `100` | Debounce delay before reloading |
| `css_reload` | `"inject"` | `"inject"` for inline update, `"refresh"` for page reload |
| `preserve_scroll` | `true` | Maintain scroll position on JS refresh |
| `watch_directories` | `[]` | Additional directories to watch |

## How It Works

1. PyWry uses `watchdog` to monitor files for changes
2. When a file changes, it determines the file type
3. CSS files are injected directly into the page
4. JS/HTML changes trigger a full refresh with scroll preservation

## Best Practices

### Development Workflow

```python
from pywry import PyWry, HtmlContent

app = PyWry(hot_reload=True)

# Use external CSS files for easy editing
content = HtmlContent(
    html="<div id='app'></div>",
    css_files=["styles/main.css"],
    watch=True,
)

handle = app.show(content)

# Edit main.css and see changes immediately!
app.block()
```

### Disable in Production

```python
import os

app = PyWry(hot_reload=os.getenv("ENV") == "development")
```

Or via environment variable:

```bash
export PYWRY_HOT_RELOAD__ENABLED=false
```

## Troubleshooting

### Changes Not Detected

1. Ensure `watch=True` is set
2. Check that file paths are correct
3. Verify the file is in a watched directory

### CSS Not Updating

1. Check for CSS syntax errors
2. Ensure `css_reload = "inject"` is set
3. Try `app.refresh_css()` manually

### Page Keeps Refreshing

1. Increase `debounce_ms` to reduce sensitivity
2. Check for infinite loops in your code
3. Ensure you're not modifying watched files in callbacks

## Next Steps

- **[Configuration](configuration.md)** — Full configuration reference
- **[Theming & CSS](theming.md)** — Styling your application
