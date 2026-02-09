# Deploy Mode

Deploy mode runs PyWry as a standalone web server for production use. It serves widgets over HTTP with WebSocket communication, and optionally uses Redis for distributed state across multiple workers.

For server and deploy configuration options, see the [Configuration Guide](configuration.md) and [Configuration Reference](../reference/config.md).

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

@app.get("/", response_class=HTMLResponse)
async def home():
    fig = px.bar(x=[1, 2, 3], y=[4, 5, 6])
    widget = show_plotly(fig, title="My Chart")
    html = await get_widget_html_async(widget.label)
    return HTMLResponse(html)

if __name__ == "__main__":
    deploy()
```

Run it:

```bash
python my_app.py
```

## Environment Variables

Deploy mode is configured primarily through environment variables. The most important ones:

```bash
# Server
export PYWRY_SERVER__HOST=0.0.0.0
export PYWRY_SERVER__PORT=8080
export PYWRY_SERVER__WORKERS=4

# State backend
export PYWRY_DEPLOY__STATE_BACKEND=redis
export PYWRY_DEPLOY__REDIS_URL=redis://localhost:6379/0
```

For the complete list, see the [Configuration Reference](../reference/config.md).

## Memory vs Redis Backend

### Memory (Default)

Single-process, in-memory state. Suitable for development and single-instance deployments.

```bash
python my_app.py
```

### Redis

Distributed state for multi-worker deployments. State persists across restarts and is shared across workers.

```bash
PYWRY_DEPLOY__STATE_BACKEND=redis \
PYWRY_DEPLOY__REDIS_URL=redis://localhost:6379/0 \
python my_app.py
```

## Full Example

See `examples/pywry_demo_deploy.py` for a complete example with:

- Multiple pages (Sales Dashboard, Inventory Manager)
- Toolbar components with callbacks
- Plotly charts with dynamic updates
- AG Grid with row selection
- Navigation between pages

```python
import os
os.environ.setdefault("PYWRY_SERVER__HOST", "0.0.0.0")
os.environ.setdefault("PYWRY_SERVER__PORT", "8080")

import pandas as pd
import plotly.express as px
from fastapi.responses import HTMLResponse
from pywry.inline import deploy, get_server_app, show_plotly, get_widget_html_async
from pywry.toolbar import Button, Option, Select, Toolbar

app = get_server_app()

# Create widget once at startup
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

def on_region_change(data, event_type, label):
    # Update chart based on region
    pass

def on_export(data, event_type, label):
    widget.emit("pywry:download", {
        "filename": "data.csv",
        "content": "q,value\nQ1,100\nQ2,150",
        "mimeType": "text/csv",
    })

widget = show_plotly(
    fig,
    title="Dashboard",
    toolbars=[toolbar],
    callbacks={
        "chart:region": on_region_change,
        "chart:export": on_export,
    },
)

@app.get("/", response_class=HTMLResponse)
async def home():
    html = await get_widget_html_async(widget.label)
    return HTMLResponse(html)

if __name__ == "__main__":
    from pywry.state import get_state_backend, get_worker_id, is_deploy_mode
    
    print(f"Deploy Mode: {is_deploy_mode()}")
    print(f"State Backend: {get_state_backend().value}")
    print(f"Worker ID: {get_worker_id()}")
    
    deploy()
```

## Key Functions

Deploy mode uses functions from `pywry.inline`:

- **`deploy()`** — Starts the uvicorn server using settings from configuration
- **`get_server_app()`** — Returns the FastAPI app instance (add your own routes to this)
- **`get_widget_html_async(label)`** — Retrieves rendered HTML for a widget by label
- **`show()` / `show_plotly()` / `show_dataframe()`** — Create widgets (in headless mode, returns handle without opening a browser)

For the complete API, see the [InlineWidget Reference](../reference/inline-widget.md).

## Configuration

Deploy settings can also be set in config files. See the [Configuration Guide](configuration.md) for details on TOML files, `pyproject.toml`, and the full settings hierarchy.

## Docker

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

```yaml
# docker-compose.yml
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

## Checking Deploy Mode

```python
from pywry.state import is_deploy_mode, get_state_backend, get_worker_id

print(f"Deploy Mode: {is_deploy_mode()}")
print(f"Backend: {get_state_backend().value}")  # "memory" or "redis"
print(f"Worker ID: {get_worker_id()}")
```
