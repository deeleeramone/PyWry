# Quick Start

This guide walks you through PyWry's core functionality with practical examples. Each example builds on concepts introduced earlier.

## Prerequisites

Make sure you have PyWry installed:

```bash
pip install pywry
```

For Plotly examples, also install Plotly:

```bash
pip install plotly
```

---

## 1. Hello World

The simplest PyWry application:

```python
from pywry import PyWry

app = PyWry()

app.show("Hello World!")

app.block()  # Keep the window open until user closes it
```

**What's happening:**

1. `PyWry()` creates an application instance
2. `app.show()` opens a native window with your content (can be plain text, HTML, or an `HtmlContent` object)
3. `app.block()` pauses your script until the window is closed

!!! tip "When to use `block()`"
    Use `app.block()` at the end of scripts to keep the window alive. In notebooks or servers, you typically don't need it.

---

## 2. Display HTML Content

PyWry renders HTML, not just text:

```python
from pywry import PyWry

app = PyWry()

html = """
<div style="padding: 20px; text-align: center;">
    <h1 id="greeting">Welcome to PyWry</h1>
    <p>This is rendered HTML with styling.</p>
    <button onclick="window.pywry.emit('app:button-click', {clicked: true})">
        Click me!
    </button>
</div>
"""

app.show(html, title="My First Window", width=600, height=400)
app.block()
```

**Key points:**

- Pass any valid HTML string to `app.show()`
- Use `title`, `width`, `height` to customize the window
- JavaScript can call `window.pywry.emit()` to send events to Python

---

## 3. Handle Events with Callbacks

The real power of PyWry is bidirectional communication. Python can respond to JavaScript events:

```python
from pywry import PyWry

app = PyWry()

def on_button_click(data, event_type, label):
    """Called when the button is clicked."""
    print(f"Button clicked! Data: {data}")
    # Update the page content
    app.emit("pywry:set-content", {"id": "greeting", "text": "Button was clicked!"}, label)

html = """
<div style="padding: 20px; text-align: center;">
    <h1 id="greeting">Click the button below</h1>
    <button onclick="window.pywry.emit('app:button-click', {time: Date.now()})">
        Click me!
    </button>
</div>
"""

app.show(
    html,
    callbacks={"app:button-click": on_button_click},
)
app.block()
```

**How callbacks work:**

1. JavaScript calls `window.pywry.emit('app:button-click', {...})` when the button is clicked
2. PyWry routes this to your Python callback registered in `callbacks={"app:button-click": on_button_click}`
3. Your callback receives three arguments:
   - `data`: The payload from JavaScript (the second argument to `emit`)
   - `event_type`: The event name (`"app:button-click"`)
   - `label`: The window/widget identifier (for targeting responses)
4. Your callback can send events back using `app.emit()` or `handle.emit()`

---

## 4. Use Toolbar Components

Instead of writing HTML buttons, use PyWry's declarative toolbar components:

```python
from pywry import PyWry, Toolbar, Button

app = PyWry()

def on_click(data, event_type, label):
    """Update the heading when button is clicked."""
    app.emit("pywry:set-content", {"selector": "h1", "text": "Toolbar Works!"}, label)

toolbar = Toolbar(
    position="top",
    items=[
        Button(label="Update Text", event="app:click"),
        Button(label="Show Alert", event="app:alert", variant="secondary"),
    ]
)

def on_alert(data, event_type, label):
    """Show a toast notification."""
    app.emit("pywry:alert", {"message": "Hello from Python!"}, label)

app.show(
    "<h1>Hello, World!</h1>",
    toolbars=[toolbar],
    callbacks={
        "app:click": on_click,
        "app:alert": on_alert,
    },
)
app.block()
```

**Toolbar concepts:**

- `Toolbar(position="top", items=[...])` creates a toolbar at one of 7 positions: `top`, `bottom`, `left`, `right`, `header`, `footer`, `inside`
- `Button(label="...", event="...")` creates a button that emits the specified event when clicked
- The `event` name follows the `namespace:event-name` pattern (e.g., `app:click`, `view:reset`)
- `variant` controls the button style: `primary`, `secondary`, `neutral`, `ghost`, `outline`, `danger`, `warning`, `icon`

---

## 5. Display a Pandas DataFrame with AgGrid

PyWry includes first-class support for displaying DataFrames using AG Grid:

```python
from pywry import PyWry
import pandas as pd

app = PyWry()

df = pd.DataFrame({
    "name": ["Alice", "Bob", "Carol", "David"],
    "age": [30, 25, 35, 28],
    "department": ["Engineering", "Marketing", "Engineering", "Sales"],
})

def on_row_selected(data, event_type, label):
    """Called when rows are selected in the grid."""
    rows = data.get("rows", [])
    if rows:
        names = ", ".join(row["name"] for row in rows)
        app.emit("pywry:alert", {"message": f"Selected: {names}"}, label)

handle = app.show_dataframe(
    df,
    title="Employee Data",
    callbacks={"grid:row-selected": on_row_selected},
)
app.block()
```

**Grid features:**

- `show_dataframe()` automatically converts your DataFrame to an AG Grid
- Pre-wired events like `grid:row-selected`, `grid:cell-clicked`, `grid:cell-value-changed` are ready to use
- Click rows to select them; your callback receives the selected row data
- Use `grid_options` parameter for advanced AG Grid configuration

---

## 6. Display a Plotly Chart

PyWry integrates seamlessly with Plotly for interactive charts:

```python
from pywry import PyWry, Toolbar, Button
import plotly.express as px

app = PyWry(theme="light")

# Create a Plotly figure
fig = px.scatter(
    px.data.iris(),
    x="sepal_width",
    y="sepal_length",
    color="species",
    title="Iris Dataset"
)

def on_chart_click(data, event_type, label):
    """Called when a point on the chart is clicked."""
    point = data["points"][0]
    new_title = f"Clicked: ({point['x']:.2f}, {point['y']:.2f}) - {point.get('marker.color', 'N/A')}"
    app.emit("plotly:update-layout", {"layout": {"title": new_title}}, label)

def on_reset(data, event_type, label):
    """Reset the chart zoom level."""
    app.emit("plotly:reset-zoom", {}, label)

toolbar = Toolbar(
    position="top",
    items=[Button(label="Reset Zoom", event="app:reset")]
)

handle = app.show_plotly(
    fig,
    toolbars=[toolbar],
    callbacks={
        "plotly:click": on_chart_click,
        "app:reset": on_reset,
    },
)
app.block()
```

**Plotly features:**

- `show_plotly()` renders any Plotly figure with full interactivity
- Pre-wired events: `plotly:click`, `plotly:hover`, `plotly:select`, `plotly:double-click`
- Use `plotly:update-layout` to dynamically update chart properties
- Use `plotly:reset-zoom` to reset the view
- Combine with toolbars for Dash-like dashboards

---

## 7. Combine Everything

Here's a more complete example combining a chart with interactive controls:

```python
from pywry import PyWry, Toolbar, Button, Select, Option
import plotly.express as px

app = PyWry(theme="light")

# Load sample data
df = px.data.gapminder()

def create_chart(year):
    """Create a chart for the given year."""
    filtered = df[df["year"] == year]
    return px.scatter(
        filtered,
        x="gdpPercap",
        y="lifeExp",
        size="pop",
        color="continent",
        hover_name="country",
        log_x=True,
        title=f"Life Expectancy vs GDP ({year})",
    )

def on_year_change(data, event_type, label):
    """Update chart when year selection changes."""
    year = int(data["value"])
    fig = create_chart(year)
    # Update the entire chart
    app.emit("plotly:replace", {"figure": fig.to_dict()}, label)

# Create year selector
years = sorted(df["year"].unique())
toolbar = Toolbar(
    position="top",
    items=[
        Select(
            label="Year:",
            event="app:year-change",
            options=[Option(label=str(y), value=str(y)) for y in years],
            selected=str(years[-1]),
        ),
    ]
)

# Initial chart
fig = create_chart(years[-1])

handle = app.show_plotly(
    fig,
    toolbars=[toolbar],
    callbacks={"app:year-change": on_year_change},
    width=1000,
    height=600,
)
app.block()
```

---

## The Callback Signature

Every callback function receives three arguments:

```python
def my_callback(data: dict, event_type: str, label: str) -> None:
    """
    Parameters
    ----------
    data : dict
        The event payload from JavaScript. Contents depend on the event type.
        For example, `grid:row-selected` includes `{"rows": [...]}`.
    
    event_type : str
        The event name that triggered this callback (e.g., "app:click").
    
    label : str
        The unique identifier of the window/widget that sent the event.
        Use this to target responses back to the correct window.
    """
    pass
```

---

## Sending Events to JavaScript

There are two ways to send events from Python to JavaScript:

### Using the handle/widget returned by `show_*()`

```python
handle = app.show("<h1>Hello</h1>")
handle.emit("pywry:set-content", {"selector": "h1", "text": "Updated!"})
```

### Using `app.emit()` with a label

```python
handle = app.show("<h1>Hello</h1>")
app.emit("pywry:set-content", {"selector": "h1", "text": "Updated!"}, handle.label)
```

Both approaches work identically. Inside a callback, you typically use `app.emit(..., label)` since you receive the `label` as a parameter.

---

## Common Built-in Events

PyWry includes many pre-registered events you can use immediately:

| Event | Direction | Description |
|-------|-----------|-------------|
| `pywry:set-content` | Python → JS | Update element text/HTML by selector or id |
| `pywry:alert` | Python → JS | Show a toast notification |
| `pywry:set-style` | Python → JS | Update element CSS styles |
| `pywry:inject-css` | Python → JS | Add custom CSS to the page |
| `plotly:click` | JS → Python | Plotly chart point clicked |
| `plotly:update-layout` | Python → JS | Update Plotly chart layout |
| `grid:row-selected` | JS → Python | AG Grid rows selected |
| `grid:update-data` | Python → JS | Update AG Grid data |

See the [Event System](../guides/events.md) guide for the complete list.

---

## Next Steps

You now understand the basics of PyWry. Continue with:

- [Rendering Paths](rendering-paths.md) — Learn about native windows, notebook widgets, and browser mode
- [Event System](../guides/events.md) — Complete event reference
- [Toolbar System](../guides/toolbars.md) — All 18 toolbar components
- [Configuration](../guides/configuration.md) — TOML files, environment variables, security presets
