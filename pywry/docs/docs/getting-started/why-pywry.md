# Why PyWry

PyWry is an open-source rendering engine for building lightweight, cross-platform interfaces using Python. It solves a specific problem: **how to build beautiful, modern data applications in Python without being forced into an opinionated web framework or a heavy native GUI toolkit.**

PyWry renders standard HTML, CSS, and JavaScript inside battle-tested OS webviews (WebView2 on Windows, WebKit on macOS/Linux). Your team can use web skills they already have — no proprietary widget toolkit to learn. If it works in a browser, it works in PyWry.

There are many ways to render web content from Python — Electron, Dash, Streamlit, NiceGUI, Gradio, Flet, or plain FastAPI. So why choose PyWry?

### The "Goldilocks" Framework

Python developers often find themselves choosing between uncomfortable extremes:

- **Native GUI Toolkits (PyQt/Tkinter)**: Steep learning curves, custom styling systems, and they don't look modern without massive effort.
- **Web-to-Desktop (Electron)**: Forces Python developers into the JavaScript/Node.js ecosystem and ships with hundreds of megabytes of Chromium bloat.
- **Data Dashboards (Streamlit/Gradio)**: Excellent for rapid deployment in a browser, but highly opinionated, difficult to deeply customize, and hard to package as a true desktop executable.

PyWry targets the sweet spot: **Write your logic in Python, build your UI with modern web technologies, and deploy it anywhere**—including as a native, lightweight executable.

### The Jupyter → Web → Desktop Pipeline

PyWry's most potent feature is its **"Build Once, Render Anywhere"** pipeline. Most frameworks support Web + Desktop, but PyWry is uniquely optimized for data science and full-stack environments.

You can instantly render a Plotly chart or AgGrid table directly inside a **Jupyter Notebook** cell. When you're ready to share your work, you use the exact same code to deploy a browser-based FastAPI application. When you want to hand an internal tool to a business user, you use `pywry[freeze]` to compile that *same code* into a standalone `.exe` or `.app`—dropping the notebook or server entirely.

### Lightweight Native Windows

PyWry uses the **OS-native webview** (WebView2, WebKit) via [PyTauri](https://github.com/pytauri/pytauri) instead of bundling a full browser engine like Electron. This results in apps that add only a few megabytes of overhead and open in under a second. There's no server to spin up and no browser to launch.

### One API, three targets

Write your interface once. PyWry automatically renders it in the right place without changing your code:

| Environment | Rendering Path |
|---|---|
| Desktop terminal | Native OS window via PyTauri |
| Jupyter / VS Code / Colab | anywidget or inline IFrame |
| Headless / SSH / Deploy | Browser tab via FastAPI + WebSocket |


### Built for data workflows

PyWry comes with built-in integrations tailored for data workflows:

- **Plotly charts** with pre-wired event callbacks (click, select, hover, zoom).
- **AG Grid tables** with automatic DataFrame conversion and grid events.
- **Toolbar system** with 18 declarative Pydantic input components across 7 layout positions to easily add headers, sidebars, and overlays.
- **Two-way events** between Python and JavaScript, with no boilerplate.


### Production-ready

PyWry scales from prototyping to multi-user deployments:

- **Deploy Mode** with an optional Redis backend for horizontal scaling.
- **OAuth2** authentication system for both native and deploy modes with enterprise RBAC.
- **Security built-in**: Token authentication, CSRF protection, and CSP headers out of the box.

### Cross-platform

PyWry runs on Windows, macOS, and Linux. The same code produces native windows on all three platforms, notebook widgets in any Jupyter environment, and browser-based interfaces anywhere Python runs.


## Why not something else

| Alternative | Trade-off |
|---|---|
| **NiceGUI** | Server + browser required natively; highly capable but lacks the single-codebase Jupyter → Desktop executable pipeline of PyWry. |
| **Electron** | 150 MB+ runtime per app, requires Node.js/JavaScript context, difficult integration for native Python execution. |
| **Dash / Streamlit / Gradio** | Opinionated UIs, browser-only deployment, not easily packagable into offline standalone executables. |
| **Flet (Flutter/Python)** | Cannot use standard web libraries (React, Tailwind, AG Grid) as it relies entirely on Flutter's custom canvas rendering. |
| **PyQt / Tkinter / wxPython** | Proprietary widget toolkits, requires learning custom desktop layout engines, lacks web interactivity features. |
| **Plain FastAPI + HTML** | No native OS windows, no notebook support, requires manual WebSocket and event wiring. |

PyWry sits in a unique position: native-quality lightweight desktop rendering, interactive Jupyter notebook support, and browser deployment, all from one Python API.

## Next steps

Ready to try it?

- [**Installation**](installation.md) — Install PyWry and platform dependencies
- [**Quick Start**](quickstart.md) — Build your first interface in 5 minutes
- [**Rendering Paths**](rendering-paths.md) — Understand the three output targets
