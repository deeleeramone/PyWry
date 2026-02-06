# Getting Started

PyWry is a blazingly fast rendering library for generating and managing native desktop windows, iFrames, and Jupyter widgets — with full bidirectional Python ↔ JavaScript communication. Get started in minutes, not hours.

## What is PyWry?

Unlike dashboard frameworks (Dash, Streamlit, Panel), PyWry is a **rendering engine** that targets three output paths from one unified API:

| Mode | Where It Runs | Backend |
|------|---------------|---------|
| `NEW_WINDOW` / `SINGLE_WINDOW` / `MULTI_WINDOW` | Native OS window | PyTauri (Tauri/Rust) using OS webview |
| `NOTEBOOK` | Jupyter / VS Code / Colab | anywidget or IFrame + FastAPI + WebSocket |
| `BROWSER` | System browser tab | FastAPI server + WebSocket + Redis |

Built on [PyTauri](https://pypi.org/project/pytauri/) (which uses Rust's [Tauri](https://tauri.app/) framework), it leverages the OS webview instead of bundling a browser engine — a few MBs versus Electron's 150MB+ overhead.

## Key Features

| Feature | What It Does |
|---------|--------------|
| **Native Windows** | Lightweight OS webview windows (not Electron) |
| **Jupyter Widgets** | Works in notebooks with anywidget |
| **Browser Mode** | Deploy to web with FastAPI + WebSocket |
| **Toolbar System** | 18 declarative Pydantic components with 7 layout positions |
| **Two-Way Events** | Python ↔ JavaScript communication with pre-wired Plotly/AgGrid events |
| **AgGrid Tables** | Best-in-class Pandas → AgGrid conversion with pre-wired events |
| **Plotly Charts** | Plotly rendering with pre-wired events for Dash-like functionality |
| **Toast Notifications** | Built-in alert system with positioning |
| **Theming & CSS** | Light/dark modes, 60+ CSS variables, dynamic styling via events |
| **Hot Reload** | Live CSS/JS updates during development |
| **Deploy Mode** | Redis backend for horizontal scaling |

## Layout Structure

PyWry uses declarative Pydantic components that automatically wrap content in a nested structure that can be targeted with CSS selectors:

```
HEADER → LEFT | TOP → CONTENT + INSIDE → BOTTOM | RIGHT → FOOTER
```

This means you can add toolbars at any of 7 positions (`top`, `bottom`, `left`, `right`, `header`, `footer`, `inside`) and PyWry handles the flexbox layout automatically.

## Hello World

```python
from pywry import PyWry

app = PyWry()

app.show("Hello World!")

app.block()  # Block the main thread until the window closes
```

This opens a native OS window with your content. The `block()` method keeps your script running until the user closes the window.

## Interactive Example

Here's a more complete example showing interactivity:

```python
from pywry import PyWry, Toolbar, Button

app = PyWry()

def on_click(data, event_type, label):
    """Callback that runs when button is clicked."""
    app.emit("pywry:set-content", {"selector": "h1", "text": "It works!"}, label)

toolbar = Toolbar(
    position="top",
    items=[Button(label="Click Me", event="app:click")]
)

handle = app.show(
    "<h1>Hello, World!</h1>",
    toolbars=[toolbar],
    callbacks={"app:click": on_click},
)

app.block()
```

**What's happening here:**

1. We create a `PyWry` instance
2. Define a callback function that will update the page content
3. Create a `Toolbar` with a `Button` that emits an `app:click` event
4. Call `app.show()` with our HTML, toolbar, and callback mapping
5. When the button is clicked, the `on_click` function runs and updates the `<h1>` text

## Automatic Environment Detection

PyWry automatically selects the appropriate rendering path based on your environment:

| Environment | What Happens |
|-------------|--------------|
| **Desktop (script/terminal)** | Opens a native OS window using PyTauri |
| **Jupyter/VS Code with anywidget** | Renders inline using anywidget communication |
| **Jupyter/VS Code without anywidget** | Renders inline using IFrame + FastAPI server |
| **Headless/SSH/Server** | Opens in system browser with FastAPI server |

You don't need to change your code — PyWry figures it out.

## Next Steps

<div class="grid cards" markdown>

-   :material-download:{ .lg .middle } **Installation**

    ---

    Install PyWry and platform-specific dependencies

    [:octicons-arrow-right-24: Installation](installation.md)

-   :material-rocket-launch:{ .lg .middle } **Quick Start**

    ---

    Step-by-step examples with DataFrames, Plotly, and toolbars

    [:octicons-arrow-right-24: Quick Start](quickstart.md)

-   :material-monitor:{ .lg .middle } **Rendering Paths**

    ---

    Understand native windows, notebook widgets, and browser mode

    [:octicons-arrow-right-24: Rendering Paths](rendering-paths.md)

-   :material-lightning-bolt:{ .lg .middle } **Event System**

    ---

    Two-way Python ↔ JavaScript communication

    [:octicons-arrow-right-24: Events](../guides/events.md)

</div>
