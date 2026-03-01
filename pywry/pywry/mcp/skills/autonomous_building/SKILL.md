---
description: Autonomous PyWry application building using LLM sampling, elicitation, and progress reporting.
---

# Autonomous Application Building

This skill teaches agents how to use PyWry MCP's agentic tools to autonomously design, build,
and export complete widget applications from a plain-English description.

## When to Use These Tools

Use the agentic tools when you need to:

- Build a complete PyWry app from a description **without manual step-by-step tool calls**
- Deliver a **full Python project** (main.py, requirements.txt, README.md, widgets/)
- Interactively **gather requirements** from the user before generating code
- Show **real-time progress** to the user during long build operations

---

## Available Agentic Tools

### `plan_widget` — AI-Planned Widget Spec

Sends the description to the LLM via sampling and returns a validated `WidgetPlan` JSON object.
Use this to **inspect the plan before committing** to building.

```python
# Returns a WidgetPlan JSON (no widget is created yet)
result = await client.call_tool("plan_widget", {
    "description": "A crypto price dashboard with symbol selector and refresh button"
})
plan = json.loads(result[0].text)
# plan contains: title, html_content, toolbars, callbacks, width, height, ...
```

### `build_app` — End-to-End Autonomous Builder

The primary tool for autonomous app building. One call:
1. Samples a `WidgetPlan` from the description
2. Registers the widget in the session
3. Returns `widget_id` **and complete runnable Python code**

```python
result = await client.call_tool("build_app", {
    "description": "Task tracker with add/remove buttons and completion percentage",
    "open_window": False  # set True to open a native window immediately
})
data = json.loads(result[0].text)
widget_id  = data["widget_id"]
python_code = data["python_code"]  # paste into a .py and run directly
```

The returned `python_code` is a fully self-contained Python script requiring only `pywry`.

### `export_project` — Complete Python Project Package

Takes one or more `widget_id`s and generates a full project tree:

```
my_app/
    main.py            ← entry-point
    requirements.txt   ← dependencies
    README.md          ← quickstart docs
    widgets/
        <widget_id>.py ← one file per widget
```

```python
result = await client.call_tool("export_project", {
    "widget_ids": ["abc123", "def456"],
    "project_name": "my_dashboard",
    "output_dir": "",          # leave empty to get file contents as JSON
    # "output_dir": "/tmp"     # set to write files to disk
})
data = json.loads(result[0].text)
files = data["files"]  # {relative_path: file_content}
```

### `scaffold_app` — Interactive Multi-Turn Builder

Uses `ctx.elicit()` to ask the user questions before generating the plan:
- App title and description
- Display mode (native / inline)
- Optional libraries (Plotly, AG-Grid)
- Toolbar position

```python
result = await client.call_tool("scaffold_app", {})
# MCP client will prompt the user for each field
data = json.loads(result[0].text)
plan = data["widget_plan"]
```

---

## Recommended Workflow

### Quick build (autonomous)

```python
# 1. Build the app
build = await client.call_tool("build_app", {
    "description": "Your plain-English description here"
})
data = json.loads(build[0].text)

# 2. Save the code
Path("my_widget.py").write_text(data["python_code"])

# 3. Or package as a full project
project = await client.call_tool("export_project", {
    "widget_ids": [data["widget_id"]],
    "project_name": "my_app",
    "output_dir": "./output"  # writes files to disk
})
```

### Inspect-then-build

```python
# 1. Plan first
plan_result = await client.call_tool("plan_widget", {
    "description": "..."
})
plan = json.loads(plan_result[0].text)

# 2. Review and tweak the JSON plan manually
# 3. Then build using the reviewed description
```

### Interactive (with user input)

```python
# Let the user guide the design
scaffold = await client.call_tool("scaffold_app", {})
data = json.loads(scaffold[0].text)

# Build from the collected spec
build = await client.call_tool("build_app", {
    "description": data["collected"]["description"]
})
```

---

## Progress Reporting

All agentic tools emit `report_progress` events.
Clients that display a progress bar will show real-time status:
`Planning… → Generating code… → Writing files… → Done`

---

## Combining With Other Tools

After `build_app` you can continue refining using the standard tools:

```python
# Read the skill resource for styling tips
content = await client.read_resource("skill://styling/SKILL.md")

# Update a component dynamically
await client.call_tool("set-content", {
    "widget_id": widget_id,
    "component_id": "main-content",
    "content": "<p>Updated!</p>"
})

# Check events emitted by toolbar buttons
await client.call_tool("get-events", {"widget_id": widget_id})
```

---

## Tips for Good Results

- **Specificity beats brevity**: "A real-time stock ticker with 5 company buttons and a price display area"
  produces better plans than "a finance app".
- **Mention coloring / layout**: "left sidebar with dark theme", "top toolbar with primary variant buttons".
- **Describe interactivity**: "clicking a country updates the chart below" triggers better callback planning.
- **Large widgets**: Request `include_plotly=True` or `include_aggrid=True` in your description if you need
  charts or tables.
