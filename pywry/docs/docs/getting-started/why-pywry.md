# Why PyWry

PyWry is a rendering engine for building lightweight, cross-platform interfaces using web technologies (HTML, CSS, JavaScript) with Python. It is open source, Apache-licensed, and free for both commercial and personal use. In this document, we'll explain why companies and developers choose PyWry.

We can split up the benefits of PyWry into two questions: First, why should you use web technologies to build your Python interfaces? Then, why should you choose PyWry as the framework to do so?

## Why choose web technologies

Modern applications are powered by web technologies - HTML, CSS, JavaScript, and WebAssembly. They are the dominant way to build user interfaces — both for consumer applications and mission-critical business tools. This is true for apps that run in a browser **and** for desktop applications that aren't accessed from a browser.

Most application framework SDKs make you choose between native or web-based. PyWry provides a unified Python API that services both. It runs directly inside any Python IDE, making it fast and easy to develop reusable components and layouts that are Pydantic objects.

PyWry is a full-stack rendering solution for Python that allows you to declaratively build interactive elements that automatically wire frontend <-> backend communication. No JavaScript required.

### Versatility

Web technologies are versatile. Your PyWry interface can include anything a web page can, or any custom HTML/CSS/JS you need. It bundles AgGrid and Plotly in the distributed wheel with pre-wired events and sensible defaults that allow you to render tables and charts with minimal effort - without any CDN delivery or other external libraries.


### Reliability

Web rendering engines are among the most battle-tested software in the world. The OS webviews that PyWry uses (WebView2 on Windows, WebKit on macOS/Linux) ship with billions of devices and are maintained by Microsoft and Apple respectively.

### Interoperability

PyWry interfaces are built with standard web APIs. That means you can use any JavaScript library, any CSS framework, and any HTML pattern. If it works in a browser, it works in PyWry.

### Ubiquity

Web developers are everywhere. If your team needs to customize the frontend, they can use skills they already have. No proprietary widget toolkit to learn.


## Why choose PyWry

There are many ways to render web content from Python — Electron-based apps, Dash, Streamlit, NiceGUI, Gradio, Flet, Jupyter widgets, or plain FastAPI servers. So why should you choose PyWry?

### The "Goldilocks" Framework

Python developers often find themselves choosing between uncomfortable extremes:
- **Native GUI Toolkits (PyQt/Tkinter)**: Steep learning curves, custom styling systems, and they don't look modern without massive effort.
- **Web-to-Desktop (Electron)**: Forces Python developers into the JavaScript/Node.js ecosystem and ships with hundreds of megabytes of Chromium bloat.
- **Data Dashboards (Streamlit/Gradio)**: Excellent for rapid deployment in a browser, but highly opinionated, difficult to deeply customize, and hard to package as a true desktop executable.

PyWry targets the sweet spot: **Write your logic in Python, build your UI with modern web technologies, and deploy it anywhere**—including as a native, lightweight executable.

### The Jupyter → Web → Desktop Pipeline

PyWry's most potent feature is its **"Build Once, Render Anywhere"** pipeline. Most frameworks support Web + Desktop, but PyWry is uniquely optimized for data science and full-stack environments.

You can instantly render a Plotly chart or AgGrid table directly inside a **Jupyter Notebook** cell. When you're ready to share your work, you use the exact same code to deploy a browser-based FastAPI application. When you want to hand an internal tool to a business user, you use `pywry[freeze]` to compile that *same code* into a standalone `.exe` or `.app`—dropping the notebook or server entirely.

### Unrestricted Web Technologies

Unlike frameworks like Flet (which draws its own UI using the Flutter canvas), PyWry uses standard HTML, CSS, and JS rendered inside a local OS webview. This means you aren't restricted to a custom widget ecosystem. If you want to use Tailwind CSS, arbitrary JS libraries, or your company's internal React design system, PyWry acts as an invisible bridge.

### Lightweight Native Windows

PyWry uses the **OS-native webview** (WebView2, WebKit) instead of bundling a full browser engine. A PyWry app adds a few megabytes of overhead. An Electron app ships 150 MB+ of Chromium, and can't be used as a web application. Dash, Streamlit, and Panel require a running web server; they don't create native OS windows.

### One API, three targets

Write your interface once. PyWry automatically renders it in the right place:

| Environment | Rendering Path |
|---|---|
| Desktop terminal | Native OS window via PyTauri |
| Jupyter / VS Code / Colab | anywidget or inline IFrame |
| Headless / SSH / Deploy | Browser tab via FastAPI + WebSocket |

You don't change your code. PyWry detects the environment and picks the right backend.

### Built for data workflows

PyWry isn't a general-purpose web framework. It's built specifically for Python data workflows:

- **Plotly charts** with pre-wired event callbacks (click, select, hover, zoom)
- **AG Grid tables** with automatic DataFrame conversion and grid events
- **Toolbar system** with 18 Pydantic input components across 7 layout positions
- **Two-way events** between Python and JavaScript, with no boilerplate

The Toolbar system lets you build nested structures that wrap around your main content. You can easily add headers, footers, collapsible sidebars, marquees, and overlays - with no custom HTML or JS.

### Fast startup

Native windows open in under a second. There's no server to spin up, no browser to launch, no bundle to compile. For notebook widgets, rendering is near-instant through anywidget.

### Production-ready

PyWry isn't just for prototyping and single-user applications:

- **Deploy Mode** with Redis backend for horizontal scaling and RBAC
- **OAuth2** authentication system for both native and deploy modes
- **Token authentication** and CSRF protection out of the box
- **CSP headers** and security presets for production environments
- **TOML-based configuration** with layered precedence (defaults → project → user → env vars)

### Cross-platform

PyWry runs on Windows, macOS, and Linux. The same code produces native windows on all three platforms, notebook widgets in any Jupyter environment, and browser-based interfaces anywhere Python runs.

### Mature foundation

PyWry is built on [Tauri](https://tauri.app/) via [PyTauri](https://github.com/pytauri/pytauri) — a mature Rust framework used by thousands of production applications. The webview layer, event system, and window management are battle-tested Rust code, not Python wrappers around fragile subprocess calls. 


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
