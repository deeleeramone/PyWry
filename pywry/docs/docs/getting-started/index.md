# Getting Started

PyWry is a rendering engine — not a dashboard framework like Dash, Streamlit, or Panel. You give it content (HTML, a Plotly figure, a DataFrame), and it renders that content in a native window, a Jupyter widget, or a browser tab. One API, three output targets.

## How It Works

PyWry selects the rendering path automatically based on your environment:

| Mode | Where It Runs | Backend |
|------|---------------|---------|
| `NEW_WINDOW` / `SINGLE_WINDOW` / `MULTI_WINDOW` | Native OS window | PyTauri (Tauri/Rust) using OS webview |
| `NOTEBOOK` | Jupyter / VS Code / Colab | anywidget or IFrame + FastAPI + WebSocket |
| `BROWSER` | System browser tab | FastAPI server + WebSocket + Redis |

Running a script from your terminal? Native window. Inside a Jupyter notebook? Widget or IFrame. Set `mode=BROWSER`? Opens in the system browser. You don't change your code — PyWry detects the environment and picks the right path. See [Rendering Paths](rendering-paths.md) for details.

## Architecture

Built on [PyTauri](https://pypi.org/project/pytauri/) (which wraps Rust's [Tauri](https://tauri.app/) framework), PyWry uses the OS webview (WebView2 on Windows, WebKit on macOS/Linux) instead of bundling a full browser engine. This means a few MBs of overhead instead of Electron's 150 MB+.

Communication between Python and JavaScript is bidirectional. JavaScript in the webview can emit events that Python callbacks receive, and Python can push updates back to the webview. Plotly chart events and AG Grid events are pre-wired — you just register callbacks.

## Layout Structure

PyWry uses declarative Pydantic components that wrap content in a nested layout targeted with CSS selectors:

```
HEADER → LEFT | TOP → CONTENT + INSIDE → BOTTOM | RIGHT → FOOTER
```

Toolbars can be placed at any of 7 positions (`top`, `bottom`, `left`, `right`, `header`, `footer`, `inside`) and PyWry handles the flexbox layout automatically.

## Next Steps

<div class="grid cards" markdown>

-   :material-download:{ .lg .middle } **Installation**

    ---

    Install PyWry and platform-specific dependencies

    [:octicons-arrow-right-24: Installation](installation.md)

-   :material-rocket-launch:{ .lg .middle } **Quick Start**

    ---

    Step-by-step examples with HTML, DataFrames, Plotly, and toolbars

    [:octicons-arrow-right-24: Quick Start](quickstart.md)

-   :material-monitor:{ .lg .middle } **Rendering Paths**

    ---

    Native windows, notebook widgets, and browser mode explained

    [:octicons-arrow-right-24: Rendering Paths](rendering-paths.md)

-   :material-lightning-bolt:{ .lg .middle } **Event System**

    ---

    Two-way Python ↔ JavaScript communication

    [:octicons-arrow-right-24: Events](../guides/events.md)

</div>
