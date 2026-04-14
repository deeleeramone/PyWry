# Why PyWry

PyWry is an open-source rendering engine for building cross-platform interfaces using Python. It solves a specific problem: **how to build modern data applications in Python without being forced into an opinionated web framework or a heavy native GUI toolkit.**

PyWry renders standard HTML, CSS, and JavaScript inside OS-native webviews (WebView2 on Windows, WebKit on macOS/Linux) via [PyTauri](https://pytauri.github.io/pytauri/). Your team can use web skills they already have — no proprietary widget toolkit to learn. If it works in a browser, it works in PyWry.

## Write Once, Render Anywhere

PyWry's defining feature is that the same code renders in three environments without modification:

| Environment | Transport | How It Renders |
|---|---|---|
| Desktop terminal | PyTauri subprocess | Native OS webview window |
| Jupyter / VS Code / Colab | Anywidget traitlets | Notebook cell widget (no server) |
| Headless / SSH / Deploy | FastAPI + WebSocket | Browser tab via IFrame |

A Plotly chart, an AG Grid table, a TradingView financial chart, or a full chat interface — all render identically across these three paths. The same `on()`/`emit()` event protocol works in every environment, so components you build are portable by default.

This pipeline is designed for data teams: prototype in a Jupyter notebook, share as a browser-based FastAPI application, and package as a standalone desktop executable with `pywry[freeze]` — all from the same Python code.

## Built-In Integrations

PyWry ships with production-ready integrations that implement industry-standard interfaces where they exist, so your code stays portable and your skills transfer.

### Plotly Charts

Interactive charts with automatic dark/light theming, pre-wired click/hover/selection/zoom events, programmatic updates, custom mode bar buttons that fire Python callbacks, and per-theme template overrides. Accepts standard Plotly `Figure` objects and figure dicts — the same data format used across the Plotly ecosystem.

### AG Grid Tables

Sortable, filterable, editable data tables with automatic DataFrame conversion, cell editing callbacks, row selection events, and pagination. Configures through standard AG Grid `ColDef` and `GridOptions` structures — the same column definitions and grid options documented in the [AG Grid docs](https://www.ag-grid.com/javascript-data-grid/) work directly in PyWry.

### TradingView Financial Charts

Full [TradingView Lightweight Charts](https://tradingview.github.io/lightweight-charts/) integration supporting three data modes:

- **Static** — pass a DataFrame or list of OHLCV dicts for one-shot rendering
- **Datafeed** — implement the `DatafeedProvider` interface for async on-demand bar loading, symbol resolution, and real-time subscriptions (follows TradingView's [Datafeed API](https://www.tradingview.com/charting-library-docs/latest/connecting_data/Datafeed-API/) contract)
- **UDF** — `UDFAdapter` wraps any `DatafeedProvider` as a [Universal Data Feed](https://www.tradingview.com/charting-library-docs/latest/connecting_data/UDF/) HTTP endpoint compatible with TradingView's server-side data protocol

Also includes drawing tools, technical indicators, persistent chart layouts (file or Redis storage), and session/timezone management.

### AI Chat (ACP)

The chat system implements the [Agent Client Protocol (ACP)](https://agentclientprotocol.com) — an open standard for AI agent communication using JSON-RPC 2.0. This means:

- **Provider interface** follows ACP's session lifecycle: `initialize` → `new_session` → `prompt` → `cancel`
- **Session updates** use ACP's typed notification system: `agent_message`, `tool_call`, `plan`, `available_commands`, `config_option`, `current_mode`
- **Content blocks** use ACP's content model: `text`, `image`, `audio`, `resource`, `resource_link`
- **StdioProvider** connects to any ACP-compatible agent (Claude Code, Gemini CLI) over stdio JSON-RPC without writing adapter code

Built-in providers for OpenAI, Anthropic, Magentic (100+ backends), [Deep Agents](https://docs.langchain.com/oss/python/deepagents/overview) (LangChain's agent harness with filesystem tools, planning, and subagents), and user-supplied callables adapt their respective APIs to the ACP session interface. Rich inline artifacts (code, markdown, tables, Plotly charts, TradingView charts, images, JSON trees) render directly in the chat transcript.

### MCP Server

A [Model Context Protocol](https://modelcontextprotocol.io/) server built on [FastMCP](https://github.com/jlowin/fastmcp) with 25+ tools that lets AI coding agents create and control PyWry widgets, send chat messages, manage chart data, and build interactive dashboards programmatically. MCP is the standard protocol used by Claude Code, Cursor, Windsurf, and other AI coding tools for tool integration.

### Toolbar System

18 declarative Pydantic input components (buttons, selects, toggles, sliders, text inputs, date pickers, search bars, secret inputs, radio groups, tab groups, marquees, and more) across 7 layout positions, all with automatic event wiring.

## Lightweight Native Windows

PyWry uses the OS-native webview via PyTauri instead of bundling a full browser engine like Electron. Apps add only a few megabytes of overhead and open in under a second. The PyTauri subprocess provides access to 19 Tauri plugins for native OS capabilities — clipboard, file dialogs, notifications, global shortcuts, system tray icons, and more.

## Unified Event Protocol

All three rendering transports implement the same bidirectional event protocol:

- **Python → JavaScript**: `widget.emit("app:update", {"count": 42})` updates the UI
- **JavaScript → Python**: `pywry.emit("app:click", {x: 100})` fires a Python callback

This means every component — whether it's a Plotly chart, an AG Grid table, a TradingView chart, a chat panel, or a custom HTML element — uses the same `on()`/`emit()` pattern. Build a component once and it works in native windows, notebooks, and browser tabs.

## Production Ready

PyWry scales from a single-user notebook to multi-user deployments:

- **Three state backends**: in-memory (ephemeral), SQLite with encryption at rest (local persistent), and Redis (multi-worker distributed) — the same interfaces, queries, and RBAC work on all three
- **SQLite audit trail**: tool call traces, generated artifacts, token usage stats, resource references, and skill activations persisted to an encrypted local database
- **Deploy Mode** with a Redis backend for horizontal scaling across multiple Uvicorn workers
- **OAuth2 authentication** with pluggable providers (Google, GitHub, Microsoft, generic OIDC) for both native and deploy modes
- **Role-based access control** with viewer/editor/admin roles enforced across all ACP chat operations, file system access, and terminal control
- **Security built-in**: per-widget token authentication, origin validation, CSP headers, secret input values never rendered in HTML, and SQLite databases encrypted at rest via SQLCipher

## Cross Platform

PyWry runs on Windows, macOS, and Linux. The same code produces native windows on all three platforms, notebook widgets in any Jupyter environment, and browser-based interfaces anywhere Python runs. The PyTauri binary ships as a vendored wheel — no Rust toolchain or system dependencies required.

## Why Not Something Else

| Alternative | What PyWry Adds |
|---|---|
| **Electron** | 150MB+ runtime, requires Node.js. PyWry uses the OS webview — a few MB, pure Python. |
| **Dash / Streamlit / Gradio** | Browser-only, opinionated layouts, no desktop executables. PyWry renders in notebooks, browsers, and native windows from one codebase. |
| **NiceGUI** | Server + browser required for native rendering. PyWry renders directly in the OS webview with no server for desktop mode. |
| **Flet** | Flutter canvas rendering — cannot use standard web libraries (Plotly, AG Grid, TradingView). PyWry renders any HTML/CSS/JS. |
| **PyQt / Tkinter** | Proprietary widget toolkits with custom layout engines. PyWry uses standard web technologies. |
| **Plain FastAPI** | No native windows, no notebook rendering, no event system, no component library. PyWry provides all of these. |

None of these alternatives offer the combination of native desktop rendering, Jupyter notebook widgets, browser deployment, integrated AI chat with ACP protocol support, TradingView financial charting, and MCP agent tooling — all from one Python API with one event protocol.

## Next Steps

- [**Installation**](installation.md) — Install PyWry and platform dependencies
- [**Quick Start**](quickstart.md) — Build your first interface in 5 minutes
- [**Rendering Paths**](rendering-paths.md) — Understand the three output targets
