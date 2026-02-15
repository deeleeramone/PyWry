# Deploy Mode

Deploy mode turns PyWry into a standalone web application server. Instead of running alongside a script, the server _is_ the application — uvicorn runs in the foreground, you mount your own FastAPI routes, and widgets are served to any browser.

For development and local use, see [Browser Mode](browser-mode.md). Deploy mode is for production.

## When to Use Deploy Mode

| Scenario | Why deploy mode fits |
|:---|:---|
| Multi-user web app | Serve dashboards to many browsers at once |
| Multi-worker scaling | Run multiple uvicorn workers behind a load balancer |
| Shared state | Use Redis so all workers see the same widgets |
| Production hosting | Docker, Kubernetes, systemd, cloud platforms |
| Custom API routes | Add your own FastAPI endpoints alongside widgets |

## Quick Start

```python
# my_app.py
import os

os.environ.setdefault("PYWRY_SERVER__HOST", "0.0.0.0")
os.environ.setdefault("PYWRY_SERVER__PORT", "8080")

import plotly.express as px
from fastapi.responses import HTMLResponse
from pywry.inline import deploy, get_server_app, show_plotly, get_widget_html_async

app = get_server_app()

fig = px.bar(x=["Q1", "Q2", "Q3", "Q4"], y=[100, 150, 130, 180])
widget = show_plotly(fig, title="Quarterly Revenue")


@app.get("/", response_class=HTMLResponse)
async def home():
    html = await get_widget_html_async(widget.label)
    return HTMLResponse(html)


if __name__ == "__main__":
    deploy()
```

```bash
python my_app.py
# Server starts on http://0.0.0.0:8080
```

## Key Functions

Deploy mode uses four functions from `pywry.inline`:

### get_server_app()

```python
from pywry.inline import get_server_app

app = get_server_app()
```

Returns the configured **FastAPI** application instance. Add your own routes, middleware, and exception handlers to this app before calling `deploy()`. Internally, this sets `PYWRY_HEADLESS=1` and configures the widget state backend from settings.

### deploy()

```python
from pywry.inline import deploy

deploy()
```

Starts the uvicorn server in the **foreground** (blocking). Reads all configuration from `PyWrySettings` — host, port, workers, SSL, log level, etc. Also starts a background thread to process callbacks.

### show() / show_plotly() / show_dataframe()

These work the same as in browser mode, but in deploy mode they register widgets without opening a browser tab:

```python
from pywry.inline import show, show_plotly, show_dataframe

# Register widgets — no browser opens
widget = show("<h1>Dashboard</h1>", label="dashboard")
chart = show_plotly(fig, title="Revenue")
table = show_dataframe(df, title="Inventory")
```

### get_widget_html_async()

```python
html = await get_widget_html_async(widget.label)
```

Retrieves the rendered HTML for a widget by label. Use this in your FastAPI route handlers to serve widget content. There's also a synchronous version, `get_widget_html()`, for non-async contexts.

## Configuration

Deploy mode is configured through environment variables (prefix `PYWRY_SERVER__` for server settings, `PYWRY_DEPLOY__` for deploy-specific settings) or config files.

### Server Settings

| Setting | Default | Environment variable | Description |
|:---|:---|:---|:---|
| Host | `127.0.0.1` | `PYWRY_SERVER__HOST` | Bind address |
| Port | `8765` | `PYWRY_SERVER__PORT` | Server port |
| Workers | `1` | `PYWRY_SERVER__WORKERS` | Uvicorn worker processes |
| Log level | `info` | `PYWRY_SERVER__LOG_LEVEL` | `debug`, `info`, `warning`, `error` |
| Access log | `True` | `PYWRY_SERVER__ACCESS_LOG` | Enable access logging |
| Auto-reload | `False` | `PYWRY_SERVER__RELOAD` | Auto-reload on code changes (dev only) |
| Keep-alive | `5` | `PYWRY_SERVER__TIMEOUT_KEEP_ALIVE` | Keep-alive timeout (seconds) |
| Graceful shutdown | `None` | `PYWRY_SERVER__TIMEOUT_GRACEFUL_SHUTDOWN` | Shutdown timeout |
| Max connections | `None` | `PYWRY_SERVER__LIMIT_CONCURRENCY` | Connection limit |
| Max requests | `None` | `PYWRY_SERVER__LIMIT_MAX_REQUESTS` | Requests before worker restart |
| Backlog | `2048` | `PYWRY_SERVER__BACKLOG` | Socket backlog |
| CORS origins | `["*"]` | `PYWRY_SERVER__CORS_ORIGINS` | Allowed CORS origins |
| Widget prefix | `/widget` | `PYWRY_SERVER__WIDGET_PREFIX` | URL path prefix for widgets |

### SSL Settings

| Setting | Default | Environment variable |
|:---|:---|:---|
| Certificate | `None` | `PYWRY_SERVER__SSL_CERTFILE` |
| Private key | `None` | `PYWRY_SERVER__SSL_KEYFILE` |
| Key password | `None` | `PYWRY_SERVER__SSL_KEYFILE_PASSWORD` |
| CA bundle | `None` | `PYWRY_SERVER__SSL_CA_CERTS` |

### Deploy Settings

| Setting | Default | Environment variable | Description |
|:---|:---|:---|:---|
| State backend | `memory` | `PYWRY_DEPLOY__STATE_BACKEND` | `memory` or `redis` |
| Redis URL | `redis://localhost:6379/0` | `PYWRY_DEPLOY__REDIS_URL` | Redis connection string |
| Redis prefix | `pywry` | `PYWRY_DEPLOY__REDIS_PREFIX` | Key namespace in Redis |
| Redis pool size | `10` | `PYWRY_DEPLOY__REDIS_POOL_SIZE` | Connection pool size (1–100) |
| Widget TTL | `86400` (24h) | `PYWRY_DEPLOY__WIDGET_TTL` | Widget auto-expiry in seconds |
| Connection TTL | `300` (5min) | `PYWRY_DEPLOY__CONNECTION_TTL` | Connection routing TTL |
| Session TTL | `86400` (24h) | `PYWRY_DEPLOY__SESSION_TTL` | User session TTL |
| Worker ID | auto-generated | `PYWRY_DEPLOY__WORKER_ID` | Unique worker identifier |
| Auth enabled | `False` | `PYWRY_DEPLOY__AUTH_ENABLED` | Enable session auth |

## State Backends

### Memory (Default)

All widget state lives in the process's memory. Works for single-worker deployments and development.

```bash
python my_app.py
```

- Fast, no dependencies
- State is lost on restart
- Not shared across workers

### Redis

Widget state is stored in Redis. Required for multi-worker deployments.

```bash
PYWRY_DEPLOY__STATE_BACKEND=redis \
PYWRY_DEPLOY__REDIS_URL=redis://localhost:6379/0 \
python my_app.py
```

- State persists across restarts
- Shared across all workers
- Requires a running Redis instance
- Keys are auto-expired based on `WIDGET_TTL`

Redis key structure: `{prefix}:widget:{widget_id}` (hash), `{prefix}:widgets:active` (set of active IDs).

## Detecting Deploy Mode

```python
from pywry.state import is_deploy_mode, get_state_backend, get_worker_id

print(f"Deploy mode: {is_deploy_mode()}")
print(f"Backend: {get_state_backend().value}")  # "memory" or "redis"
print(f"Worker: {get_worker_id()}")
```

Deploy mode is active when any of these are true:

- `PYWRY_DEPLOY_MODE=1` or `true`
- `PYWRY_DEPLOY__STATE_BACKEND=redis`
- `PYWRY_HEADLESS=1` with a state backend configured

## Full Example

A dashboard with a toolbar, Plotly chart, and callback-driven interactions:

```python
import os

os.environ.setdefault("PYWRY_SERVER__HOST", "0.0.0.0")
os.environ.setdefault("PYWRY_SERVER__PORT", "8080")

import plotly.express as px
from fastapi.responses import HTMLResponse
from pywry.inline import deploy, get_server_app, show_plotly, get_widget_html_async
from pywry.toolbar import Button, Option, Select, Toolbar

app = get_server_app()

toolbar = Toolbar(
    position="top",
    items=[
        Select(
            event="chart:region",
            label="Region",
            options=[
                Option(label="All", value="all"),
                Option(label="North", value="north"),
                Option(label="South", value="south"),
            ],
            selected="all",
        ),
        Button(event="chart:export", label="Export CSV"),
    ],
)

fig = px.bar(x=["Q1", "Q2", "Q3", "Q4"], y=[100, 150, 130, 180])


def on_region(data, event_type, label):
    # Filter and update chart based on selected region
    pass


def on_export(data, event_type, label):
    widget.emit("pywry:download", {
        "filename": "data.csv",
        "content": "quarter,value\nQ1,100\nQ2,150\nQ3,130\nQ4,180",
        "mimeType": "text/csv",
    })


widget = show_plotly(
    fig,
    title="Sales Dashboard",
    toolbars=[toolbar],
    callbacks={
        "chart:region": on_region,
        "chart:export": on_export,
    },
)


@app.get("/", response_class=HTMLResponse)
async def home():
    html = await get_widget_html_async(widget.label)
    return HTMLResponse(html)


if __name__ == "__main__":
    deploy()
```

## Docker

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

ENV PYWRY_SERVER__HOST=0.0.0.0
ENV PYWRY_SERVER__PORT=8080

CMD ["python", "my_app.py"]
```

### docker-compose with Redis

```yaml
version: "3.8"

services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  app:
    build: .
    ports:
      - "8080:8080"
    environment:
      - PYWRY_SERVER__HOST=0.0.0.0
      - PYWRY_SERVER__PORT=8080
      - PYWRY_DEPLOY__STATE_BACKEND=redis
      - PYWRY_DEPLOY__REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis
```

## Multi-Worker Deployment

With Redis as the state backend, you can run multiple workers:

```bash
PYWRY_SERVER__WORKERS=4 \
PYWRY_DEPLOY__STATE_BACKEND=redis \
PYWRY_DEPLOY__REDIS_URL=redis://localhost:6379/0 \
python my_app.py
```

Each worker gets an auto-generated worker ID. Widget ownership is tracked so events route to the correct worker. Connection heartbeats (TTL-based) handle worker failures.
