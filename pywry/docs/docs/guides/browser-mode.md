# Browser Mode

Browser mode runs PyWry as a web server, opening content in your default browser instead of native windows.

## When to Use

- **SSH/Remote access** — No GUI available
- **Cross-platform sharing** — Share via URL
- **Development** — Use browser DevTools

## Enable Browser Mode

### Programmatic

```python
from pywry import PyWry, WindowMode

app = PyWry(mode=WindowMode.BROWSER)
handle = app.show("<h1>Hello Browser!</h1>")

app.block()  # Keep server running
```

### Environment Variable

```bash
export PYWRY_WINDOW__MODE=browser
python my_app.py
```

## How It Works

1. PyWry starts a FastAPI server with WebSocket support
2. Content is served at `http://localhost:8765/widget/{label}`
3. Browser opens automatically
4. WebSocket maintains bidirectional communication

## Server Configuration

### pywry.toml

```toml
[server]
host = "127.0.0.1"
port = 8765
auto_start = true
```

### Environment Variables

```bash
export PYWRY_SERVER__HOST=0.0.0.0
export PYWRY_SERVER__PORT=8080
```

## Multiple Widgets

Each widget gets its own URL:

```python
from pywry import PyWry, WindowMode

app = PyWry(mode=WindowMode.BROWSER)

h1 = app.show("<h1>Widget 1</h1>", label="widget-1")
h2 = app.show("<h1>Widget 2</h1>", label="widget-2")

# URLs:
# http://localhost:8765/widget/widget-1
# http://localhost:8765/widget/widget-2

app.block()
```

## HTTPS Configuration

Enable HTTPS via configuration:

```toml
# pywry.toml
[server]
host = "0.0.0.0"
port = 443
ssl_certfile = "/path/to/cert.pem"
ssl_keyfile = "/path/to/key.pem"
```

Or environment variables:

```bash
export PYWRY_SERVER__SSL_CERTFILE=/path/to/cert.pem
export PYWRY_SERVER__SSL_KEYFILE=/path/to/key.pem
```

## WebSocket Security

Enable per-widget authentication tokens:

```toml
[server]
websocket_require_token = true
```

## Deploy Mode

For production deployments with multiple workers, see [Deploy Mode](deploy-mode.md).
