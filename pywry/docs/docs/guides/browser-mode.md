# Browser Mode

Browser mode runs PyWry without native OS windows. Instead, it starts a local web server and opens your content in the system browser. All communication between Python and JavaScript happens over WebSocket.

## When to Use Browser Mode

| Scenario | Why browser mode helps |
|:---|:---|
| SSH / remote server | No display server available |
| Docker / CI containers | No GUI libraries installed |
| WSL | Native windows can't reach the Linux display |
| Cross-browser testing | Use browser DevTools directly |
| Sharing with others | Send a URL instead of installing an app |

## Enabling Browser Mode

### In Code

```python
from pywry import PyWry, WindowMode

app = PyWry(mode=WindowMode.BROWSER)
handle = app.show("<h1>Hello Browser!</h1>")
app.block()  # Keeps the server running
```

### Via Environment Variable

```bash
export PYWRY_WINDOW__MODE=browser
python my_app.py
```

### Via Config File

```toml
# pywry.toml
[window]
mode = "browser"
```

## How It Works

When you call `app.show()` in browser mode:

1. **Server starts** — A FastAPI + uvicorn server launches in a background daemon thread (once, on first `show()`)
2. **Widget registers** — The rendered HTML is stored in the server's widget registry, keyed by label
3. **Browser opens** — The system default browser navigates to `http://127.0.0.1:8765/widget/{label}`
4. **WebSocket connects** — The page's JavaScript bridge opens a WebSocket back to the server for bidirectional events
5. **Events flow** — `window.pywry.emit()` in the browser sends JSON over WebSocket to Python; `handle.emit()` in Python pushes JSON back

### Server Routes

| Route | Method | Description |
|:---|:---|:---|
| `/widget/{widget_id}` | GET | Serves the widget's HTML page |
| `/ws/{widget_id}` | WebSocket | Bidirectional event bridge |
| `/health` | GET | Health check (requires internal API token) |
| `/register_widget` | POST | Re-register a widget (kernel restart recovery) |
| `/disconnect/{widget_id}` | POST | Clean disconnect of a widget |

## Server Configuration

### Default Settings

| Setting | Default | Environment variable |
|:---|:---|:---|
| Host | `127.0.0.1` | `PYWRY_SERVER__HOST` |
| Port | `8765` | `PYWRY_SERVER__PORT` |
| Widget URL prefix | `/widget` | `PYWRY_SERVER__WIDGET_PREFIX` |
| Auto-start | `True` | `PYWRY_SERVER__AUTO_START` |

### Custom Host and Port

```python
import os

os.environ["PYWRY_SERVER__HOST"] = "0.0.0.0"  # Bind to all interfaces
os.environ["PYWRY_SERVER__PORT"] = "9000"

from pywry import PyWry, WindowMode

app = PyWry(mode=WindowMode.BROWSER)
handle = app.show("<h1>Available on the network</h1>")
app.block()
```

Or in a config file:

```toml
# pywry.toml
[server]
host = "0.0.0.0"
port = 9000
```

## Multiple Widgets

Each widget gets its own URL. The server can serve many widgets simultaneously:

```python
app = PyWry(mode=WindowMode.BROWSER)

h1 = app.show("<h1>Chart</h1>", label="chart")
h2 = app.show("<h1>Table</h1>", label="table")

# Two browser tabs open:
#   http://127.0.0.1:8765/widget/chart
#   http://127.0.0.1:8765/widget/table
print(h1.url)  # Full URL for the chart widget
print(h2.url)  # Full URL for the table widget

app.block()
```

## HTTPS

Enable TLS by providing certificate and key files:

### Via Config

```toml
# pywry.toml
[server]
host = "0.0.0.0"
port = 443
ssl_certfile = "/path/to/cert.pem"
ssl_keyfile = "/path/to/key.pem"
```

### Via Environment Variables

```bash
export PYWRY_SERVER__SSL_CERTFILE=/path/to/cert.pem
export PYWRY_SERVER__SSL_KEYFILE=/path/to/key.pem
```

When SSL is configured, widget URLs use `https://` and WebSocket connections use `wss://`.

## WebSocket Security

By default, each widget gets a unique token generated with `secrets.token_urlsafe(32)`. The browser sends this token via the `Sec-WebSocket-Protocol` header during the WebSocket handshake. Connections without a valid token are rejected.

```toml
# pywry.toml
[server]
websocket_require_token = true   # Default — enforce per-widget tokens
```

### Origin Validation

Restrict which origins can connect:

```toml
[server]
websocket_allowed_origins = ["https://myapp.example.com"]
```

An empty list (the default) allows connections from any origin.

### CORS

```toml
[server]
cors_origins = ["https://myapp.example.com"]  # Default: ["*"]
```

## Callbacks and Events

Callbacks work identically in browser mode — the WebSocket transport is transparent:

```python
app = PyWry(mode=WindowMode.BROWSER)

def on_click(data, event_type, label):
    handle.emit("app:response", {"message": "Button clicked!"})

handle = app.show(
    '<button onclick="window.pywry.emit(\'app:click\', {})">Click me</button>',
    callbacks={"app:click": on_click},
)
app.block()
```

## Blocking

`app.block()` in browser mode monitors WebSocket connections. It returns when all widgets have disconnected (i.e., every browser tab has been closed or navigated away):

```python
app.show(content)
app.block()  # Waits until all browser tabs close
# Code continues after disconnect
```

Press `Ctrl+C` to stop immediately — PyWry calls `app.destroy()` to shut down the server cleanly.

## Relationship to Deploy Mode

Browser mode runs the server in a **background thread** alongside your script. For **production** deployments where the server _is_ your application, use [Deploy Mode](deploy-mode.md) instead — it runs uvicorn in the foreground with multi-worker support, Redis state, and proper process management.
