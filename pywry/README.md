<div align="center">

![PyWry](./pywry/frontend/assets/PyWry.png)

**Blazingly fast rendering library for native desktop windows, Jupyter widgets, and browser tabs.**

Full bidirectional Python ↔ JavaScript communication. Get started in minutes, not hours.

[![PyPI](https://img.shields.io/pypi/v/pywry?color=blue)](https://pypi.org/project/pywry/)
[![Python](https://img.shields.io/pypi/pyversions/pywry)](https://pypi.org/project/pywry/)
[![License](https://img.shields.io/github/license/deeleeramone/PyWry)](LICENSE)
[![Docs](https://img.shields.io/badge/docs-live-brightgreen)](https://deeleeramone.github.io/PyWry/)

</div>

---

PyWry is **not** a web dashboard framework. It is a **rendering engine** that targets three output paths from one unified API:

| Mode | Where It Runs | Backend |
|------|---------------|---------|
| `NEW_WINDOW` / `SINGLE_WINDOW` / `MULTI_WINDOW` | Native OS window | PyTauri (Tauri/Rust) subprocess using OS webview |
| `NOTEBOOK` | Jupyter / VS Code / Colab | anywidget or IFrame + FastAPI + WebSocket |
| `BROWSER` | System browser tab | FastAPI server + WebSocket + Redis |

Built on [PyTauri](https://pypi.org/project/pytauri/) (Rust's [Tauri](https://tauri.app/) framework), it uses the OS webview instead of bundling a browser engine — a few MBs versus Electron's 150MB+ overhead.

<details>
<summary><strong>Features at a Glance</strong></summary>

| Feature | What It Does |
|---------|--------------|
| **Native Windows** | Lightweight OS webview windows (not Electron) |
| **Jupyter Widgets** | Works in notebooks via anywidget with traitlet sync |
| **Browser Mode** | Deploy to web with FastAPI + WebSocket |
| **Toolbar System** | 18 declarative Pydantic components with 7 layout positions |
| **Two-Way Events** | Python ↔ JavaScript with pre-wired Plotly/AgGrid events |
| **Modals** | Overlay dialogs with toolbar components inside |
| **AgGrid Tables** | Pandas → AgGrid conversion with pre-wired grid events |
| **Plotly Charts** | Plotly rendering with custom modebar buttons and plot events |
| **Toast Notifications** | Built-in alert system with configurable positioning |
| **Theming & CSS** | Light/dark modes, 60+ CSS variables, hot reload |
| **Secrets Handling** | Server-side password storage, never rendered in HTML |
| **Security** | Token auth, CSP headers, production presets |
| **Configuration** | Layered TOML files, env vars, security presets |
| **Hot Reload** | Live CSS injection and JS updates during development |
| **Deploy Mode** | Redis state backend for horizontal scaling |
| **MCP Server** | AI agent integration via Model Context Protocol |

</details>

## Installation

Requires Python 3.10–3.14. Install in a virtual environment.

<details>
<summary><strong>Linux Prerequisites</strong></summary>

```bash
# Ubuntu/Debian
sudo apt-get install libwebkit2gtk-4.1-dev libgtk-3-dev libglib2.0-dev \
    libxkbcommon-x11-0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
    libxcb-randr0 libxcb-render-util0 libxcb-xinerama0 libxcb-xfixes0 \
    libxcb-shape0 libgl1 libegl1
```

</details>

```bash
pip install pywry
```

| Extra | Command | Description |
|-------|---------|-------------|
| **notebook** | `pip install 'pywry[notebook]'` | anywidget for Jupyter integration |
| **mcp** | `pip install 'pywry[mcp]'` | Model Context Protocol server for AI agents |
| **all** | `pip install 'pywry[all]'` | All optional dependencies |

> See [Installation Guide](https://deeleeramone.github.io/PyWry/getting-started/installation/) for full details.

---

## Quick Start

### Hello World

```python
from pywry import PyWry

app = PyWry()

app.show("Hello World!")

app.block()  # block the main thread until the window closes
```

### Interactive Toolbar

```python
from pywry import PyWry, Toolbar, Button

app = PyWry()

def on_click(data, event_type, label):
    app.emit("pywry:set-content", {"selector": "h1", "text": "Toolbar Works!"}, label)

toolbar = Toolbar(
    position="top",
    items=[Button(label="Update Text", event="app:click")]
)

handle = app.show(
    "<h1>Hello, World!</h1>",
    toolbars=[toolbar],
    callbacks={"app:click": on_click},
)
```

### DataFrame → AgGrid

```python
from pywry import PyWry
import pandas as pd

app = PyWry()

df = pd.DataFrame({"name": ["Alice", "Bob", "Carol"], "age": [30, 25, 35]})

def on_select(data, event_type, label):
    names = ", ".join(row["name"] for row in data["rows"])
    app.emit("pywry:alert", {"message": f"Selected: {names}" if names else "None selected"}, label)

handle = app.show_dataframe(df, callbacks={"grid:row-selected": on_select})
```

### Plotly Chart

```python
from pywry import PyWry, Toolbar, Button
import plotly.express as px

app = PyWry(theme="light")

fig = px.scatter(px.data.iris(), x="sepal_width", y="sepal_length", color="species")

handle = app.show_plotly(
    fig,
    toolbars=[Toolbar(position="top", items=[Button(label="Reset Zoom", event="app:reset")])],
    callbacks={"app:reset": lambda d, e, l: app.emit("plotly:reset-zoom", {}, l)},
)
```

> See [Quick Start Guide](https://deeleeramone.github.io/PyWry/getting-started/quickstart/) and [Examples](https://deeleeramone.github.io/PyWry/examples/) for more.

---

## Components

PyWry includes 18 declarative toolbar components, all Pydantic models with 7 layout positions (`header`, `footer`, `top`, `bottom`, `left`, `right`, `inside`):

| Component | Description |
|-----------|-------------|
| **Button** | Clickable button — primary, secondary, neutral, ghost, outline, danger, warning, icon |
| **Select** | Dropdown select with `Option` items |
| **MultiSelect** | Multi-select dropdown with checkboxes |
| **TextInput** | Text input with debounce support |
| **SecretInput** | Secure password input — values stored server-side, never in HTML |
| **TextArea** | Multi-line text area |
| **SearchInput** | Search input with debounce |
| **NumberInput** | Numeric input with min/max/step |
| **DateInput** | Date picker |
| **SliderInput** | Slider with optional value display |
| **RangeInput** | Dual-handle range slider |
| **Toggle** | Boolean toggle switch |
| **Checkbox** | Boolean checkbox |
| **RadioGroup** | Radio button group |
| **TabGroup** | Tab navigation |
| **Div** | Container element for content/HTML |
| **Marquee** | Scrolling ticker — scroll, alternate, slide, static |
| **Modal** | Overlay dialog supporting all toolbar components |

> See [Components Documentation](https://deeleeramone.github.io/PyWry/components/) for live previews, attributes, and usage examples.

---

## Documentation

Full documentation is available at **[deeleeramone.github.io/PyWry](https://deeleeramone.github.io/PyWry/)**.

| Section | Topics |
|---------|--------|
| [Getting Started](https://deeleeramone.github.io/PyWry/getting-started/) | Installation, Quick Start, Rendering Paths |
| [Concepts](https://deeleeramone.github.io/PyWry/getting-started/) | `app.show()`, HtmlContent, Events, Configuration, State & RBAC, Hot Reload |
| [UI](https://deeleeramone.github.io/PyWry/getting-started/) | Toolbar System, Modals, Toasts & Alerts, Theming & CSS |
| [Integrations](https://deeleeramone.github.io/PyWry/getting-started/) | Plotly Charts, AgGrid Tables |
| [Hosting](https://deeleeramone.github.io/PyWry/getting-started/) | Browser Mode, Deploy Mode |
| [Components](https://deeleeramone.github.io/PyWry/components/) | Live previews for all 18 toolbar components + Modal |
| [API Reference](https://deeleeramone.github.io/PyWry/reference/) | Auto-generated API docs for every class and function |
| [MCP Server](https://deeleeramone.github.io/PyWry/mcp/) | AI agent integration via Model Context Protocol |

---

## MCP Server

PyWry includes a built-in [Model Context Protocol](https://modelcontextprotocol.io/) server for AI agent integration — 25 tools, 8 skills, and 20+ resources.

```bash
pip install 'pywry[mcp]'
pywry mcp --transport stdio
```

> See [MCP Documentation](https://deeleeramone.github.io/PyWry/mcp/) for setup with Claude Desktop, tool reference, and examples.

---

## License

Apache 2.0 — see [LICENSE](LICENSE) for details.
