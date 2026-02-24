<div align="center">

![PyWry](https://github.com/deeleeramone/PyWry/blob/82db0c977a8ec812bf8652c0be14bf62b66b66a1/pywry/pywry/frontend/assets/PyWry.png?raw=true)

</div>

PyWry is a cross-platform rendering engine and GUI toolkit for Python. One API, three output targets:

- **Native window** — OS webview via [PyTauri](https://pypi.org/project/pytauri/). Not Qt, not Electron.
- **Jupyter widget** — anywidget or FastAPI + WebSocket, works in JupyterLab and notebook environments.
- **Browser tab** — FastAPI server with Redis state backend for horizontal scaling and RBAC.

## Installation

Python 3.10–3.14, virtual environment recommended.

```bash
pip install pywry
```

| Extra | When to use |
|-------|-------------|
| `pip install 'pywry[notebook]'` | Jupyter / anywidget integration |
| `pip install 'pywry[mcp]'` | MCP server for AI agents |
| `pip install 'pywry[freeze]'` | PyInstaller hook for standalone executables |
| `pip install 'pywry[all]'` | Everything above |

**Linux only** — install system webview dependencies first:

```bash
sudo apt-get install libwebkit2gtk-4.1-dev libgtk-3-dev libglib2.0-dev \
    libxkbcommon-x11-0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
    libxcb-randr0 libxcb-render-util0 libxcb-xinerama0 libxcb-xfixes0 \
    libxcb-shape0 libgl1 libegl1
```

## Quick Start

```python
from pywry import PyWry

app = PyWry()
app.show("Hello World!")
app.block()
```

### Toolbar + callbacks

```python
from pywry import PyWry, Toolbar, Button

app = PyWry()

def on_click(data, event_type, label):
    app.emit("pywry:set-content", {"selector": "h1", "text": "Clicked!"}, label)

app.show(
    "<h1>Hello</h1>",
    toolbars=[Toolbar(position="top", items=[Button(label="Click me", event="app:click")])],
    callbacks={"app:click": on_click},
)
app.block()
```

### Pandas DataFrame → AgGrid

```python
from pywry import PyWry
import pandas as pd

app = PyWry()
df = pd.DataFrame({"name": ["Alice", "Bob", "Carol"], "age": [30, 25, 35]})

def on_select(data, event_type, label):
    names = ", ".join(row["name"] for row in data["rows"])
    app.emit("pywry:alert", {"message": f"Selected: {names}"}, label)

app.show_dataframe(df, callbacks={"grid:row-selected": on_select})
app.block()
```

### Plotly chart

```python
from pywry import PyWry
import plotly.express as px

app = PyWry(theme="light")
fig = px.scatter(px.data.iris(), x="sepal_width", y="sepal_length", color="species")
app.show_plotly(fig)
app.block()
```

## Features

- **18 toolbar components** — `Button`, `Select`, `MultiSelect`, `TextInput`, `SecretInput`, `SliderInput`, `RangeInput`, `Toggle`, `Checkbox`, `RadioGroup`, `TabGroup`, `Marquee`, `Modal`, and more. All Pydantic models, 7 layout positions.
- **Two-way events** — `app.emit()` and `app.on()` bridge Python and JavaScript in both directions. Pre-wired Plotly and AgGrid events included.
- **Theming** — light/dark modes, 60+ CSS variables, hot reload during development.
- **Security** — token auth, CSP headers, `SecuritySettings.strict()` / `.permissive()` / `.localhost()` presets. `SecretInput` stores values server-side, never in HTML.
- **Standalone executables** — PyInstaller hook ships with `pywry[freeze]`. No `.spec` edits or `--hidden-import` flags required.
- **MCP server** — 25 tools, 8 skills, 20+ resources for AI agent integration.

## MCP Server

```bash
pip install 'pywry[mcp]'
pywry mcp --transport stdio
```

See the [MCP docs](https://deeleeramone.github.io/PyWry/mcp/) for Claude Desktop setup and tool reference.

## Standalone Executables

```bash
pip install 'pywry[freeze]'
pyinstaller --windowed --name MyApp my_app.py
```

The output in `dist/MyApp/` is fully self-contained. Target machines need no Python installation — only the OS webview (WebView2 on Windows 10 1803+, WKWebView on macOS, libwebkit2gtk on Linux).

## Documentation

**[deeleeramone.github.io/PyWry](https://deeleeramone.github.io/PyWry/)**

- [Getting Started](https://deeleeramone.github.io/PyWry/getting-started/) — installation, quick start, rendering paths
- [Concepts](https://deeleeramone.github.io/PyWry/getting-started/) — events, configuration, state, hot reload, RBAC
- [Components](https://deeleeramone.github.io/PyWry/components/) — live previews for all toolbar components
- [API Reference](https://deeleeramone.github.io/PyWry/reference/) — auto-generated docs for every class and function
- [MCP Server](https://deeleeramone.github.io/PyWry/mcp/) — AI agent integration

## License

Apache 2.0 — see [LICENSE](LICENSE).
