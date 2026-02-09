# Configuration

PyWry uses a layered configuration system — settings can come from built-in defaults, TOML files, or environment variables, all merged with a clear priority order. This guide explains how to configure your application. For the full settings API, see the [Configuration Reference](../reference/config.md).

## Configuration Sources

Settings are merged in this order (highest priority last):

1. **Built-in defaults**
2. **pyproject.toml** — `[tool.pywry]` section
3. **Project config** — `./pywry.toml`
4. **User config** — `~/.config/pywry/config.toml` (Linux/macOS) or `%APPDATA%\pywry\config.toml` (Windows)
5. **Environment variables** — `PYWRY_*` prefix

## Configuration File (pywry.toml)

Create a `pywry.toml` file in your project root:

```toml
[theme]
# css_file = "/path/to/custom.css"

[window]
title = "My Application"
width = 1280
height = 720
center = true
resizable = true
devtools = false
on_window_close = "hide"  # "hide" or "close"

[timeout]
startup = 10.0
response = 5.0
create_window = 5.0
set_content = 5.0
shutdown = 2.0

[hot_reload]
enabled = true
debounce_ms = 100
css_reload = "inject"
preserve_scroll = true
watch_directories = ["./src", "./styles"]

[csp]
default_src = "'self' 'unsafe-inline' 'unsafe-eval' data: blob:"
connect_src = "'self' http://*:* https://*:* ws://*:* wss://*:*"
script_src = "'self' 'unsafe-inline' 'unsafe-eval'"
style_src = "'self' 'unsafe-inline'"
img_src = "'self' http://*:* https://*:* data: blob:"
font_src = "'self' data:"

[asset]
plotly_version = "3.3.1"
aggrid_version = "35.0.0"

[log]
level = "WARNING"
format = "%(name)s - %(levelname)s - %(message)s"

[server]
host = "127.0.0.1"
port = 8765
auto_start = true
websocket_require_token = true

[deploy]
state_backend = "memory"  # or "redis"
redis_url = "redis://localhost:6379/0"
```

## pyproject.toml

Add configuration to your existing `pyproject.toml`:

```toml
[tool.pywry]
[tool.pywry.window]
title = "My App"
width = 1280

[tool.pywry.log]
level = "DEBUG"
```

## Environment Variables

Override any setting with `PYWRY_{SECTION}__{KEY}`:

```bash
export PYWRY_WINDOW__TITLE="Production App"
export PYWRY_WINDOW__WIDTH=1920
export PYWRY_HOT_RELOAD__ENABLED=true
export PYWRY_LOG__LEVEL=DEBUG
```

## Configuration Sections

| Section | Env Prefix | Description |
|---------|------------|-------------|
| `csp` | `PYWRY_CSP__` | Content Security Policy directives |
| `theme` | `PYWRY_THEME__` | Custom CSS file path |
| `timeout` | `PYWRY_TIMEOUT__` | Timeout values in seconds |
| `asset` | `PYWRY_ASSET__` | Library versions and asset paths |
| `log` | `PYWRY_LOG__` | Log level and format |
| `window` | `PYWRY_WINDOW__` | Default window properties |
| `hot_reload` | `PYWRY_HOT_RELOAD__` | Hot reload behavior |
| `server` | `PYWRY_SERVER__` | Inline server settings |
| `deploy` | `PYWRY_DEPLOY__` | Deploy mode settings |

## Programmatic Configuration

Pass settings directly to PyWry:

```python
from pywry import PyWry, PyWrySettings, WindowSettings

settings = PyWrySettings(
    window=WindowSettings(
        title="My App",
        width=1920,
        height=1080,
    )
)

pywry = PyWry(settings=settings)
```

## Security Presets

PyWry provides CSP factory methods for common scenarios:

```python
from pywry import SecuritySettings

# Permissive - allows unsafe-inline/eval (default, good for development)
permissive = SecuritySettings.permissive()

# Strict - removes unsafe-eval, restricts to self and specific CDNs
strict = SecuritySettings.strict()

# Localhost - allows only localhost connections
localhost = SecuritySettings.localhost()

# Localhost with specific ports
localhost_ports = SecuritySettings.localhost(ports=[8000, 8080])
```

## Window Settings

Window properties can be set in config or passed directly to `show()`:

```python
handle = app.show(
    "<h1>Hello</h1>",
    title="My Application",
    width=1280,
    height=720,
)
```

For the full list of window settings, see [`WindowSettings`](../reference/config.md).

## Server Settings

Server settings control the FastAPI backend used in browser and inline modes.

For the full list of server settings, see [`ServerSettings`](../reference/config.md).

## CLI Commands

PyWry provides CLI commands for configuration management:

```bash
# Show current configuration
pywry config --show

# Export as TOML
pywry config --toml

# Export as environment variables
pywry config --env

# Show configuration sources
pywry config --sources

# Initialize pywry.toml
pywry init
```

## Next Steps

- **[Configuration Reference](../reference/config.md)** — Complete `PyWrySettings` API
- **[Deploy Mode](deploy-mode.md)** — Production server configuration
- **[Browser Mode](browser-mode.md)** — Server settings for browser mode
