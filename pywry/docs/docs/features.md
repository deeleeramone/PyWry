# Features

## Rendering Paths

One API, three output targets — PyWry automatically selects the right one:

| Environment | Path | Backend |
|-------------|------|---------|
| Desktop | [Native Window](getting-started/rendering-paths.md#native-window) | PyTauri + OS webview |
| Jupyter + anywidget | [Notebook Widget](getting-started/rendering-paths.md#notebook-widget) | anywidget comms |
| Jupyter (fallback) | [Inline IFrame](getting-started/rendering-paths.md#inline-iframe) | FastAPI server |
| Headless/SSH | [Browser Mode](guides/browser-mode.md) | FastAPI + browser |

## Core Capabilities

| Feature | Description |
|---------|-------------|
| **Native Windows** | OS webview (WebView2/WebKit) — a few MBs vs Electron's 150MB+ |
| **Jupyter Widgets** | anywidget with traitlet sync, IFrame fallback |
| **Browser Mode** | FastAPI + WebSocket, optional Redis for scaling |
| **[Toolbar System](components/toolbar/index.md)** | Declarative Pydantic components, 7 layout positions |
| **[Two-Way Events](guides/events.md)** | Python↔JS communication, pre-wired events for integration |
| **[TradingView Charts](integrations/tradingview/index.md)** | Advanced Lightweight Charts supporting static content, Datafeed, and UDF adapter.
| **[Plotly Charts](integrations/plotly/index.md)** | Pre-wired plot events, custom modebar buttons |
| **[AgGrid Tables](integrations/aggrid/index.md)** | Pandas→AgGrid conversion, grid events, editing |
| **Toast Notifications** | info, success, warning, error, confirm |
| **[Theming](components/theming.md)** | Light/dark modes, 60+ CSS variables |
| **Secrets** | Server-side storage, never rendered in HTML |
| **Security** | Token auth, CSP headers, production presets |
| **[Configuration](guides/configuration.md)** | TOML files, env vars, layered precedence |
| **[Hot Reload](guides/hot-reload.md)** | Live CSS/JS updates during development |
| **[Deploy Mode](guides/deploy-mode.md)** | Redis backend for horizontal scaling |
| **[Tauri Plugins](integrations/pytauri/tauri-plugins.md)** | 19 bundled plugins — clipboard, notifications, HTTP, and more |

## Platform Support

| Platform | Native Window | Notebook | Browser |
|----------|:---:|:---:|:---:|
| macOS | WebKit | anywidget/IFrame | FastAPI |
| Windows | WebView2 | anywidget/IFrame | FastAPI |
| Linux | WebKit2GTK | anywidget/IFrame | FastAPI |

## Configuration Precedence

Settings are merged in order (highest priority last):

1. Built-in defaults
2. `pyproject.toml` `[tool.pywry]`
3. `pywry.toml`
4. `~/.config/pywry/config.toml`
5. Environment variables `PYWRY_*`

See the [Configuration Guide](guides/configuration.md) for details.
