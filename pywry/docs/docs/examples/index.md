# Examples

## Hello World

```python
from pywry import PyWry

app = PyWry()
app.show("<h1>Hello, World!</h1>")
app.block()
```

## Interactive Chart

```python
import plotly.express as px
from pywry import PyWry

app = PyWry()
fig = px.scatter(x=[1, 2, 3, 4, 5], y=[1, 4, 9, 16, 25], title="Quadratic")

def on_click(data, event_type, label):
    point = data["points"][0]
    app.emit("pywry:set-content", {
        "id": "chart-title",
        "text": f"Clicked: ({point['x']}, {point['y']})"
    }, label)

app.show_plotly(fig, callbacks={"plotly:click": on_click})
app.block()
```

## Data Table

```python
import pandas as pd
from pywry import PyWry

app = PyWry()

df = pd.DataFrame({
    "Name": ["Alice", "Bob", "Charlie", "Diana"],
    "Age": [25, 30, 35, 28],
    "Department": ["Engineering", "Marketing", "Sales", "Engineering"],
})

handle = app.show_dataframe(df)
app.block()
```

---

## Dashboard Examples

### Sales Dashboard

```python
import plotly.graph_objects as go
from pywry import PyWry, Toolbar, Select, Button, Option

app = PyWry()

# Sample data
months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
sales = [45000, 52000, 49000, 61000, 58000, 72000]
targets = [50000, 50000, 55000, 55000, 60000, 60000]

# Create figure
fig = go.Figure()
fig.add_trace(go.Scatter(x=months, y=sales, mode="lines+markers", name="Actual"))
fig.add_trace(go.Scatter(x=months, y=targets, mode="lines", name="Target", line=dict(dash="dash")))
fig.update_layout(title="Sales Performance", yaxis_title="Sales ($)")

# Toolbar - use event parameter, not id
toolbar = Toolbar(
    position="top",
    items=[
        Select(
            event="view:period",  # Use event, not id
            label="Period",
            options=[
                Option(label="H1 2024", value="h1"),
                Option(label="H2 2024", value="h2"),
                Option(label="Full Year", value="full"),
            ],
            selected="h1",  # Use selected, not value
        ),
        Button(event="export:csv", label="Export"),  # Use event, not id
    ],
)

def on_period_change(data, event_type, label):
    period = data["value"]
    handle.emit("pywry:alert", {"message": f"Loading {period} data..."})

def on_export(data, event_type, label):
    handle.emit("pywry:download", {
        "content": "Month,Sales,Target\n" + "\n".join(
            f"{m},{s},{t}" for m, s, t in zip(months, sales, targets)
        ),
        "filename": "sales_data.csv",
    })

# Use toolbars (list), not toolbar (singular)
handle = app.show_plotly(
    fig,
    toolbars=[toolbar],
    callbacks={
        "view:period": on_period_change,  # Match the event name
        "export:csv": on_export,
    },
)

app.block()
```

---

### Multi-Panel Dashboard

```python
import plotly.express as px
from pywry import PyWry

app = PyWry()

# Create multiple figures
fig1 = px.line(x=["Jan", "Feb", "Mar"], y=[100, 150, 130], title="Revenue")
fig2 = px.bar(x=["A", "B", "C"], y=[30, 45, 25], title="By Category")
fig3 = px.pie(values=[45, 30, 25], names=["Product", "Service", "Other"], title="Revenue Mix")

# Build HTML with Plotly charts
html = f"""
<div style="display: grid; grid-template-columns: 2fr 1fr; grid-template-rows: 1fr 1fr; gap: 16px; padding: 16px; height: 100vh; box-sizing: border-box;">
    <div id="chart1" style="grid-row: span 2;"></div>
    <div id="chart2"></div>
    <div id="chart3"></div>
</div>
<script>
    Plotly.newPlot('chart1', {fig1.to_json()});
    Plotly.newPlot('chart2', {fig2.to_json()});
    Plotly.newPlot('chart3', {fig3.to_json()});
</script>
"""

# Use include_plotly=True to load Plotly.js
app.show(html, include_plotly=True)
app.block()
```

---

## Form Examples

### Data Entry Form

```python
from pywry import (
    PyWry, Toolbar, TextInput, Select, NumberInput, 
    DateInput, Toggle, Button, Option
)

app = PyWry()

# Use event parameter for all components, not id
toolbar = Toolbar(
    position="left",
    items=[
        TextInput(event="form:name", label="Name", placeholder="Full name"),
        TextInput(event="form:email", label="Email", placeholder="email@example.com"),
        Select(
            event="form:department",
            label="Department",
            options=[
                Option(label="Engineering", value="eng"),
                Option(label="Marketing", value="mkt"),
                Option(label="Sales", value="sales"),
            ],
        ),
        NumberInput(event="form:salary", label="Salary", min=0, step=1000),
        DateInput(event="form:start_date", label="Start Date"),
        Toggle(event="form:remote", label="Remote"),
        Button(event="form:submit", label="Submit", variant="primary"),
    ],
)

form_data = {}

def on_field_change(data, event_type, label):
    field = event_type.replace("form:", "")
    form_data[field] = data.get("value")
    handle.emit("pywry:set-content", {"id": "status", "text": f"Updated {field}"})

def on_submit(data, event_type, label):
    handle.emit("pywry:alert", {
        "message": "Form submitted successfully!",
        "type": "success"
    })

# Use toolbars (list)
handle = app.show(
    '<h1>Employee Registration</h1><p id="status"></p>',
    toolbars=[toolbar],
    callbacks={
        "form:name": on_field_change,
        "form:email": on_field_change,
        "form:department": on_field_change,
        "form:salary": on_field_change,
        "form:start_date": on_field_change,
        "form:remote": on_field_change,
        "form:submit": on_submit,
    },
)

app.block()
```

---

## Integration Examples

### Chart + Grid Linked

```python
import plotly.express as px
import pandas as pd
from pywry import PyWry

app = PyWry()

df = pd.DataFrame({
    "Category": ["A", "B", "C", "D"],
    "Value": [100, 200, 150, 300],
    "Growth": [5, 12, -3, 8],
})

# Show chart
fig = px.bar(df, x="Category", y="Value", title="Category Performance")

def on_chart_click(data, event_type, label):
    point = data["points"][0]
    category = point["x"]
    chart.emit("pywry:alert", {"message": f"Selected category: {category}"})

chart = app.show_plotly(fig, label="chart", callbacks={"plotly:click": on_chart_click})

# Show grid
grid = app.show_dataframe(df, label="grid")

app.block()
```

---

### Real-Time Updates

```python
import time
import random
import threading
from pywry import PyWry

app = PyWry()

html = """
<div style="padding: 20px; text-align: center;">
    <h1 id="value" style="font-size: 72px; font-family: monospace;">0</h1>
    <p id="status" style="color: #666;">Updating...</p>
</div>
"""

handle = app.show(html)

def update_loop():
    while True:
        value = random.randint(0, 100)
        handle.emit("pywry:set-content", {"id": "value", "text": str(value)})
        
        color = "#10b981" if value > 50 else "#ef4444"
        handle.emit("pywry:set-style", {
            "id": "value",
            "styles": {"color": color}
        })
        
        time.sleep(1)

thread = threading.Thread(target=update_loop, daemon=True)
thread.start()

app.block()
```

---

## Browser Mode Examples

### Web Dashboard

```python
from pywry import PyWry, WindowMode
import plotly.express as px

app = PyWry(mode=WindowMode.BROWSER)

fig = px.scatter(x=[1, 2, 3], y=[1, 4, 9])
handle = app.show_plotly(fig)

# Access the URL: handle.url

app.block()
```

---

## Notebook Examples

### Jupyter Widget

```python
# In a Jupyter notebook
from pywry import PyWry, WindowMode
import plotly.express as px

app = PyWry(mode=WindowMode.NOTEBOOK)

fig = px.scatter(x=[1, 2, 3, 4, 5], y=[1, 4, 9, 16, 25])

# Displays inline in the notebook
app.show_plotly(fig)
```

---

## More Examples

Check out the example notebooks in the repository:

- `examples/pywry_demo_plotly.ipynb` — Plotly chart examples
- `examples/pywry_demo_aggrid.ipynb` — AG Grid examples
- `examples/pywry_demo_toolbar.ipynb` — Toolbar component examples
- `examples/pywry_demo_rendering.ipynb` — Rendering mode examples
- `examples/pywry_demo_deploy.py` — Deploy mode example
