<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="pywry/pywry/frontend/assets/PyWry-dark.svg">
  <img src="pywry/pywry/frontend/assets/PyWry-light.svg" alt="PyWry" width="640">
</picture>

</div>

PyWry is a cross-platform rendering engine and desktop UI toolkit for Python. One API, three output targets:

- **Native window** — OS webview via [PyTauri](https://pypi.org/project/pytauri/). Not Qt, not Electron. Use unrestricted HTML/CSS/JS.
- **Jupyter widget** — anywidget + FastAPI + WebSocket, works in JupyterLab, VS Code, and Colab.
- **Browser tab** — FastAPI server with Redis state backend for horizontal scaling.

**Build Once, Render Anywhere:** Prototype interactive data apps in a Jupyter Notebook, easily deploy them as web apps, and seamlessly compile them into secure, lightweight standalone desktop executables via `pywry[freeze]`.

## Installation

Python 3.10–3.14, virtual environment recommended.

```bash
pip install pywry
```

Core extras:

| Extra | When to use |
|-------|-------------|
| `pip install 'pywry[notebook]'` | Jupyter / anywidget integration |
| `pip install 'pywry[auth]'` | OAuth2 and keyring-backed auth support |
| `pip install 'pywry[freeze]'` | PyInstaller hook for standalone executables |
| `pip install 'pywry[mcp]'` | Model Context Protocol server support |
| `pip install 'pywry[sqlite]'` | Encrypted SQLite state backend (SQLCipher) |
| `pip install 'pywry[all]'` | Everything above |

Chat provider extras:

| Extra | When to use |
|-------|-------------|
| `pip install 'pywry[openai]'` | `OpenAIProvider` (OpenAI SDK) |
| `pip install 'pywry[anthropic]'` | `AnthropicProvider` (Anthropic SDK) |
| `pip install 'pywry[magentic]'` | `MagenticProvider` (any magentic-supported LLM) |
| `pip install 'pywry[acp]'` | `StdioProvider` (Agent Client Protocol subprocess) |
| `pip install 'pywry[deepagent]'` | `DeepagentProvider` (LangChain Deep Agents — includes MCP adapters and ACP) |

The chat UI itself is included in the base package.  Provider extras only install the matching third-party SDK.

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

- **Toolbar components** — `Button`, `Select`, `MultiSelect`, `TextInput`, `SecretInput`, `SliderInput`, `RangeInput`, `Toggle`, `Checkbox`, `RadioGroup`, `TabGroup`, `Marquee`, `Modal`, and more.  All Pydantic models; position them around the content edges or inside the chart area.
- **Two-way events** — `app.emit()` and `app.on()` bridge Python and JavaScript in both directions.  Pre-wired Plotly and AgGrid events included.
- **Chat** — streaming chat widget with threads, slash commands, artifacts, and pluggable providers: `OpenAIProvider`, `AnthropicProvider`, `MagenticProvider`, `CallbackProvider`, `StdioProvider` (ACP subprocess), and `DeepagentProvider` (LangChain Deep Agents).
- **TradingView charts** — extended Lightweight Charts integration with a full drawing surface (trendlines, fib tools, text annotations, price notes, brushes), pluggable datafeed API, UDF adapter for external quote servers, streaming bar updates, compare overlays, compare-derivative indicators (Spread / Ratio / Sum / Product / Correlation), savable layouts, and a themeable settings panel.
- **Theming** — light / dark / system modes, themeable via `--pywry-*` CSS variables, hot reload during development.
- **Security** — token auth, CSP headers, `SecuritySettings.strict()` / `.permissive()` / `.localhost()` presets.  `SecretInput` stores values server-side, never in HTML.
- **State backends** — in-memory (default), Redis (multi-worker), or SQLite with SQLCipher encryption at rest.
- **Standalone executables** — PyInstaller hook ships with `pywry[freeze]`.  No `.spec` edits or `--hidden-import` flags required.
- **MCP server** — drive widgets, charts, and dashboards from any Model Context Protocol client (Claude Desktop, Claude Code, Cursor, etc.).

## MCP Server

```bash
pip install 'pywry[mcp]'
pywry mcp --transport stdio
```

Widget-creating MCP tools (`create_widget`, `show_plotly`, `show_dataframe`, `show_tvchart`, `create_chat_widget`) auto-return an **`AppArtifact`** in headless mode — a self-contained HTML snapshot delivered as an MCP `EmbeddedResource` (`mimeType: text/html`, `uri: pywry-app://<widget_id>/<revision>`). MCP clients that render HTML resources — Claude Desktop's artifact pane, mcp-ui-aware clients, PyWry's own chat widget — show the app inline. Each render bumps a per-widget revision counter; the latest revision keeps a live WebSocket bridge back to Python while older ones freeze at their last known state. Call `get_widget_app(widget_id)` to re-snapshot a widget after mutating it.

See the [MCP docs](https://deeleeramone.github.io/PyWry/mcp/) for Claude Desktop setup and tool reference.

## Claude Code Plugin

PyWry ships as a Claude Code plugin under [claude/plugins/pywry/](claude/plugins/pywry/) that bundles the MCP server, an orientation skill, slash commands (`/pywry:doctor`, `/pywry:scaffold`, `/pywry:examples`), a `pywry-builder` subagent, and a post‑edit `ruff format` hook.

```
/plugin marketplace add deeleeramone/PyWry --path claude/.claude-plugin/marketplace.json
/plugin install pywry@pywry
```

Prerequisite: `pip install 'pywry[dev]'` (or `pywry[all]`) in the Python interpreter that `python` resolves to — `[dev]` pulls in `fastmcp` plus `ruff` for the post‑edit format hook; `[all]` covers every runtime extra. Run `/pywry:doctor` after install to verify everything is wired correctly.

The plugin is also bundled into the `pywry` pip wheel (at `pywry/_claude_plugin/`) — see [claude/README.md](claude/README.md) for the PyPI-based install path and the mono-repo layout.

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
