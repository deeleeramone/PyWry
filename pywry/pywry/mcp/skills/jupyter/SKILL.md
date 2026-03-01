# Jupyter Notebook Skill

This skill covers building PyWry widgets for Jupyter notebooks via MCP tools.

There are **two approaches** for displaying widgets in Jupyter:

| Approach | Best For | Requires |
|----------|----------|----------|
| **AnyWidget** (recommended) | Native Jupyter integration, bidirectional comms | `pip install 'pywry[notebook]'` |
| **IFrame** (fallback) | When anywidget unavailable | MCP server in headless mode |

---

## Approach 1: AnyWidget (Recommended)

AnyWidget provides native Jupyter widget integration with traitlet-based bidirectional communication. No iframe, no server - just native Jupyter widgets.

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Jupyter Notebook                                       │
│  ┌───────────────────────────────────────────────────┐  │
│  │  Cell [1]: # Code from MCP agent                  │  │
│  │            from pywry.widget import PyWryWidget   │  │
│  │            widget = PyWryWidget(                  │  │
│  │                content="<div>...</div>",          │  │
│  │                height="400px"                     │  │
│  │            )                                      │  │
│  │            widget  # Display in cell              │  │
│  ├───────────────────────────────────────────────────┤  │
│  │  Output: ┌─────────────────────────────────────┐  │  │
│  │          │  [Native Jupyter Widget]            │  │  │
│  │          │  Buttons, Charts, Tables, etc.      │  │  │
│  │          └─────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
         ▲
         │ Traitlet sync (bidirectional)
         ▼
┌─────────────────────────────────────────────────────────┐
│  Python Kernel                                          │
│  PyWryWidget instance with .on() event handlers         │
└─────────────────────────────────────────────────────────┘
```

### MCP Workflow for AnyWidget

When asked to create an interactive widget in Jupyter with anywidget installed:

1. **Use `build_div` to build HTML content**
2. **Provide Python code for the user to run**

The MCP agent **cannot** directly instantiate Python objects in the user's kernel. Instead, provide code the user can execute.

### Example: Parameter Tuning Widget

When user asks: "Create a widget to tune learning rate and model type"

**Step 1**: Build the HTML content using MCP tools:

```json
{
  "tool": "build_div",
  "arguments": {
    "component_id": "output",
    "content": "Adjust parameters below",
    "style": "padding: 1rem; min-height: 100px;"
  }
}
```

**Step 2**: Provide this Python code to the user:

```python
from pywry.widget import PyWryWidget
from pywry.toolbar import Toolbar, Slider, Select, Option, Button

# Build toolbar
toolbar = Toolbar(position="inside", items=[
    Slider(label="Learning Rate", event="lr", min=0.001, max=0.1, step=0.001, value=0.01),
    Select(label="Model", event="model", options=[
        Option(label="Linear", value="linear"),
        Option(label="Random Forest", value="rf")
    ]),
    Button(label="Train", event="train", variant="primary")
])

# Build HTML with toolbar
html = f'''
<div id="output" style="padding: 1rem; min-height: 100px;">
    Adjust parameters and click Train
</div>
{toolbar.render()}
'''

# Create and display widget
widget = PyWryWidget(content=html, height="350px")

# Handle events
def on_train(data, event_type, label):
    print(f"Training with: {data}")
    widget.emit("pywry:set-content", {"id": "output", "html": "<p>Training...</p>"})

widget.on("train", on_train)
widget  # Display in cell
```

### AnyWidget Classes

| Class | Use Case |
|-------|----------|
| `PyWryWidget` | General HTML/toolbar widgets |
| `PyWryPlotlyWidget` | Charts with Plotly.js bundled |
| `PyWryAgGridWidget` | Data tables with AG Grid bundled |

### PyWryPlotlyWidget Example

```python
from pywry.widget import PyWryPlotlyWidget

widget = PyWryPlotlyWidget(
    figure={"data": [{"x": [1,2,3], "y": [4,5,6], "type": "scatter"}]},
    height="450px"
)

# Handle plot click events
widget.on("plotly_click", lambda data, *_: print(f"Clicked: {data}"))
widget
```

### PyWryAgGridWidget Example

```python
from pywry.widget import PyWryAgGridWidget
import pandas as pd

df = pd.DataFrame({"A": [1, 2, 3], "B": ["x", "y", "z"]})

widget = PyWryAgGridWidget(
    data=df.to_dict("records"),
    columns=[{"field": "A"}, {"field": "B"}],
    height="400px"
)

# Handle row selection
widget.on("row_selected", lambda data, *_: print(f"Selected: {data}"))
widget
```

---

## Approach 2: IFrame (Fallback)

When anywidget is not installed, use the MCP server in headless mode to serve widgets via HTTP.

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Jupyter Notebook                                       │
│  ┌───────────────────────────────────────────────────┐  │
│  │  Cell [1]: from IPython.display import IFrame     │  │
│  │            IFrame("http://localhost:8765/widget/  │  │
│  │                   abc123", width="100%",          │  │
│  │                   height=400)                     │  │
│  ├───────────────────────────────────────────────────┤  │
│  │  Output: ┌─────────────────────────────────────┐  │  │
│  │          │  [Your Widget Rendered Here]        │  │  │
│  │          │  Buttons, Charts, Tables, etc.      │  │  │
│  │          └─────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
         ▲
         │ HTTP (iframe src)
         ▼
┌─────────────────────────────────────────────────────────┐
│  PyWry Widget Server (localhost:8765)                   │
│  Serves widget HTML at /widget/{widget_id}              │
└─────────────────────────────────────────────────────────┘
```

### MCP Tool Workflow (IFrame Mode)

#### Step 1: Create the Widget

Use `create_widget` to build your widget:

```json
{
  "tool": "create_widget",
  "arguments": {
    "title": "Parameter Tuner",
    "html": "<div id='output'>Adjust parameters below</div>",
    "height": 350,
    "toolbars": [{
      "position": "inside",
      "items": [
        {"type": "slider", "label": "Learning Rate", "event": "lr", "min": 0.001, "max": 0.1, "step": 0.001, "value": 0.01},
        {"type": "select", "label": "Model", "event": "model", "options": [
          {"label": "Linear", "value": "linear"},
          {"label": "Random Forest", "value": "rf"}
        ]}
      ]
    }]
  }
}
```

#### Step 2: Provide Display Code to User

The `create_widget` tool returns:
```json
{
  "widget_id": "abc123",
  "path": "/widget/abc123",
  "created": true
}
```

**IMPORTANT**: You must give the user Python code to display the widget. Include this in your response:

```python
from IPython.display import IFrame
IFrame("http://localhost:8765/widget/abc123", width="100%", height=350)
```

Replace `abc123` with the actual `widget_id` and `350` with the height you used.

#### Step 3: Poll for Events

Use `get_events` to check for user interactions:

```json
{
  "tool": "get_events",
  "arguments": {
    "widget_id": "abc123",
    "clear": true
  }
}
```

Events contain the user's selections:
```json
{
  "events": [
    {"event_type": "lr", "data": {"value": 0.05}},
    {"event_type": "model", "data": {"value": "rf"}}
  ]
}
```

#### Step 4: Update the Widget

Use `set_content` to update displayed results:

```json
{
  "tool": "set_content",
  "arguments": {
    "widget_id": "abc123",
    "component_id": "output",
    "html": "<p>Training with LR=0.05, Model=Random Forest...</p>"
  }
}
```

### Example Response (IFrame Mode)

When asked to create a widget in Jupyter without anywidget, your response should look like:

---

I've created a parameter tuning widget. Run this code in a cell to display it:

```python
from IPython.display import IFrame
IFrame("http://localhost:8765/widget/abc123", width="100%", height=350)
```

Use the sliders and dropdowns to adjust parameters. Let me know when you've made your selections and I'll process them.

---

---

## Best Practices (Both Approaches)

### Use `position: "inside"` for Toolbars

Place toolbars inside the widget to maximize vertical space in notebook cells:

```json
{
  "toolbars": [{
    "position": "inside",
    "items": [...]
  }]
}
```

### Keep Heights Modest

Notebook cells have limited vertical space. Use heights between 300-500px:

```json
{
  "height": 400
}
```

### Include Plotly for Charts

Set `include_plotly: true` when building data visualizations:

```json
{
  "tool": "create_widget",
  "arguments": {
    "html": "<div id='chart'></div>",
    "include_plotly": true,
    "height": 450
  }
}
```

Then use `show_plotly` or inject chart data via events.

### Include AG Grid for Tables

Set `include_aggrid: true` for data tables:

```json
{
  "tool": "create_widget",
  "arguments": {
    "html": "<div id='table'></div>",
    "include_aggrid": true,
    "height": 400
  }
}
```

## Data Science Patterns

### Parameter Exploration Widget

Create widgets that let users tune model parameters:

```json
{
  "tool": "create_widget",
  "arguments": {
    "title": "Hyperparameter Tuning",
    "html": "<div id='results'>Select parameters and click Train</div>",
    "height": 400,
    "toolbars": [{
      "position": "inside",
      "items": [
        {"type": "number", "label": "Epochs", "event": "epochs", "value": 100, "min": 1, "max": 1000},
        {"type": "slider", "label": "Dropout", "event": "dropout", "min": 0, "max": 0.5, "step": 0.05, "value": 0.2},
        {"type": "button", "label": "Train Model", "event": "train", "variant": "primary"}
      ]
    }]
  }
}
```

### Data Filter Widget

Create filtering interfaces for dataframes:

```json
{
  "tool": "create_widget",
  "arguments": {
    "title": "Data Explorer",
    "html": "<div id='preview'>Apply filters to see results</div>",
    "height": 450,
    "include_aggrid": true,
    "toolbars": [{
      "position": "inside",
      "items": [
        {"type": "multiselect", "label": "Columns", "event": "columns", "options": [
          {"label": "Date", "value": "date"},
          {"label": "Price", "value": "price"},
          {"label": "Volume", "value": "volume"}
        ]},
        {"type": "date", "label": "Start Date", "event": "start_date"},
        {"type": "date", "label": "End Date", "event": "end_date"},
        {"type": "button", "label": "Apply", "event": "apply", "variant": "primary"}
      ]
    }]
  }
}
```

### Live Dashboard

For real-time updates, create a widget and periodically update it:

```json
{
  "tool": "create_widget",
  "arguments": {
    "title": "Live Metrics",
    "html": "<div style='display:grid;grid-template-columns:1fr 1fr;gap:1rem;padding:1rem'><div id='metric1' style='padding:1rem;background:#1a1a2e;border-radius:8px'><h3>Accuracy</h3><p style='font-size:2rem'>--</p></div><div id='metric2' style='padding:1rem;background:#1a1a2e;border-radius:8px'><h3>Loss</h3><p style='font-size:2rem'>--</p></div></div>",
    "height": 200
  }
}
```

Update metrics with `set_content`:

```json
{
  "tool": "set_content",
  "arguments": {
    "widget_id": "abc123",
    "component_id": "metric1",
    "html": "<h3>Accuracy</h3><p style='font-size:2rem;color:#4ade80'>94.5%</p>"
  }
}
```

## Troubleshooting

### AnyWidget Issues

1. Ensure `pip install 'pywry[notebook]'` was run
2. Restart the kernel after installing
3. Check widget displays with just `widget` (not `print(widget)`)

### IFrame Issues

1. Ensure the MCP server is running with `PYWRY_HEADLESS=1`
2. Check the widget server is accessible at `http://localhost:8765`
3. Verify the `widget_id` in the IFrame URL matches

### Events Not Captured

1. Ensure toolbar items have `event` properties set
2. Use `get_events` with `clear: false` first to inspect without clearing
3. Check that the widget_id is correct

---

## Summary

### AnyWidget Approach (Recommended)
1. **Build components** using MCP tools (`build_div`, etc.)
2. **Provide Python code** for user to run in a cell
3. **User executes code** to create widget with `.on()` handlers
4. **Widget handles events** natively via traitlets

### IFrame Approach (Fallback)
1. **Create widget** with `create_widget` tool
2. **Give user the IFrame code** to run in a cell
3. **Poll events** with `get_events` when user interacts
4. **Update content** with `set_content` or `set_style`
5. **Repeat** steps 3-4 as needed
