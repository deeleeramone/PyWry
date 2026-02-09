---
title: PyWry
hide:
  - toc
---

# PyWry

A rendering library for native desktop windows, Jupyter widgets, and browser tabs — with bidirectional Python-JavaScript communication.

Not a dashboard framework. A rendering engine that targets native OS windows, Jupyter notebooks, and browser tabs from one unified API. Built on [PyTauri](https://pypi.org/project/pytauri/) (Rust/Tauri), it uses the OS webview instead of bundling a browser — a few MBs versus Electron's 150 MB+.

![Modal Demo](assets/modal_demo.gif)

## Install

```bash
pip install pywry
```

## Hello World

```python
from pywry import PyWry, Toolbar, Button

app = PyWry()

def on_click(data, event_type, label):
    app.emit("pywry:set-content", {"selector": "h1", "text": "Clicked!"}, label)

toolbar = Toolbar(position="top", items=[Button(label="Update Text", event="app:click")])

app.show(
    "<h1>Hello, World!</h1>",
    toolbars=[toolbar],
    callbacks={"app:click": on_click},
)
app.block()
```

<div class="grid cards" markdown>

-   :material-monitor:{ .lg .middle } **Native Desktop Windows**

    ---

    OS webview via PyTauri — lightweight, fast, no bundled browser

-   :material-notebook:{ .lg .middle } **Jupyter Notebooks**

    ---

    anywidget with traitlet sync, IFrame fallback for any kernel

-   :material-web:{ .lg .middle } **Browser Mode**

    ---

    FastAPI + WebSocket server, optional Redis for horizontal scaling

-   :material-view-dashboard:{ .lg .middle } **18 Toolbar Components**

    ---

    Buttons, selects, toggles, sliders, date pickers — all declarative Pydantic models

-   :material-swap-horizontal:{ .lg .middle } **Two-Way Events**

    ---

    Python ↔ JS communication with pre-wired Plotly and AG Grid support

-   :material-palette:{ .lg .middle } **Theming & Hot Reload**

    ---

    Light/dark modes, 60+ CSS variables, live CSS/JS updates during development

</div>

## Documentation

<div class="nav-cards">
  <a href="getting-started/" class="nav-card">
    <h4>Getting Started</h4>
    <p>What PyWry is and how it works</p>
  </a>
  <a href="getting-started/installation/" class="nav-card">
    <h4>Installation</h4>
    <p>Install and setup</p>
  </a>
  <a href="getting-started/quickstart/" class="nav-card">
    <h4>Quick Start</h4>
    <p>First window in 5 minutes</p>
  </a>
  <a href="guides/events/" class="nav-card">
    <h4>Event System</h4>
    <p>Python-JS communication</p>
  </a>
  <a href="guides/toolbars/" class="nav-card">
    <h4>Toolbar System</h4>
    <p>18 declarative components</p>
  </a>
  <a href="reference/" class="nav-card">
    <h4>API Reference</h4>
    <p>Full API docs</p>
  </a>
</div>
