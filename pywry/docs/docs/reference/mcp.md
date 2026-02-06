# MCP Server

PyWry includes an MCP (Model Context Protocol) server that exposes widgets to AI agents. This enables LLMs to create and manipulate interactive visualizations.

## Quick Start

```bash
# Run with stdio transport (default for Claude Desktop)
python -m pywry.mcp

# Run with SSE transport on port 8001
python -m pywry.mcp --sse 8001

# Headless mode (inline widgets, no native windows)
python -m pywry.mcp --headless
```

## Installation

The MCP server requires the `mcp` package:

```bash
pip install pywry[mcp]
# or
pip install mcp
```

## Claude Desktop Configuration

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "pywry": {
      "command": "python",
      "args": ["-m", "pywry.mcp"],
      "env": {
        "PYWRY_HEADLESS": "0"
      }
    }
  }
}
```

For headless mode (inline widgets):

```json
{
  "mcpServers": {
    "pywry": {
      "command": "python",
      "args": ["-m", "pywry.mcp", "--headless"],
      "env": {
        "PYWRY_HEADLESS": "1"
      }
    }
  }
}
```

## API

### create_server()

Create and configure the MCP server.

```python
from pywry.mcp import create_server

server = create_server(name="pywry-widgets")
```

### run_server()

Run the MCP server.

```python
from pywry.mcp import run_server

run_server(
    transport="stdio",  # or "sse"
    port=8001,          # SSE port (ignored for stdio)
    host="127.0.0.1",   # SSE host
    name="pywry-widgets",
    headless=False,     # True for inline widgets
)
```

## Available Tools

The MCP server provides 25+ tools:

### Widget Creation

| Tool | Description |
|------|-------------|
| `create_widget` | Create HTML widget with toolbars |
| `show_plotly` | Create Plotly chart widget |
| `show_dataframe` | Create AG Grid table widget |
| `build_div` | Build a Div component HTML |
| `build_ticker_item` | Build ticker item for Marquee |

### Widget Manipulation

| Tool | Description |
|------|-------------|
| `set_content` | Update element text/HTML |
| `set_style` | Update element CSS styles |
| `show_toast` | Display toast notification |
| `update_theme` | Switch dark/light theme |
| `update_plotly` | Update Plotly figure |
| `send_event` | Send custom event to widget |

### State Management

| Tool | Description |
|------|-------------|
| `get_events` | Retrieve queued events |
| `request_grid_state` | Request AG Grid state |
| `restore_grid_state` | Restore AG Grid state |
| `request_toolbar_state` | Request toolbar values |

### Skills/Context

| Tool | Description |
|------|-------------|
| `get_skills` | Get context-appropriate guidance |

## Skills

The MCP server includes 8 skills/prompts for AI guidance:

| Skill | Description |
|-------|-------------|
| `component_reference` | Complete component documentation |
| `interactive_buttons` | Button callback patterns |
| `native` | Desktop window mode |
| `jupyter` | Notebook widget mode |
| `iframe` | Embedded widget mode |
| `deploy` | Production server mode |
| `data_visualization` | Charts and tables |
| `forms_and_inputs` | User input collection |

**Usage:**
```
get_skills(skill="component_reference")
```

## Resources

The server exposes documentation and source code:

| Resource | Description |
|----------|-------------|
| `pywry://docs/readme` | README documentation |
| `pywry://docs/components` | Component reference |
| `pywry://source/{module}` | Python source code |

## Tool Examples

### create_widget

```json
{
  "html": "<div id=\"counter\" style=\"font-size:48px;text-align:center\">0</div>",
  "title": "Counter",
  "height": 400,
  "toolbars": [{
    "position": "top",
    "items": [
      {"type": "button", "label": "+1", "event": "counter:increment", "variant": "primary"},
      {"type": "button", "label": "-1", "event": "counter:decrement", "variant": "neutral"},
      {"type": "button", "label": "Reset", "event": "counter:reset", "variant": "danger"}
    ]
  }]
}
```

### show_plotly

```json
{
  "figure_json": "{\"data\": [{\"type\": \"bar\", \"x\": [1,2,3], \"y\": [4,5,6]}], \"layout\": {}}",
  "title": "Bar Chart",
  "height": 500
}
```

### show_dataframe

```json
{
  "data_json": "[{\"name\": \"Alice\", \"age\": 30}, {\"name\": \"Bob\", \"age\": 25}]",
  "title": "People",
  "height": 400
}
```

### set_content

```json
{
  "widget_id": "abc123",
  "component_id": "counter",
  "text": "42"
}
```

### send_event

```json
{
  "widget_id": "abc123",
  "event_type": "grid:update-data",
  "data": {
    "data": [{"name": "New", "value": 100}],
    "strategy": "append"
  }
}
```

## Event Handling

The MCP server stores events from widgets for retrieval:

```python
# In tool handler
events = get_events(widget_id="abc123")
# Returns: [{"event_type": "button:click", "data": {...}}, ...]
```

## Complete Example

```python
from pywry.mcp import create_server, run_server
import json

# Custom server with additional setup
server = create_server(name="my-widgets")

# Run server
run_server(
    transport="sse",
    port=8001,
    headless=True,
)
```

## SSE Transport

For web-based MCP clients:

```bash
python -m pywry.mcp --sse 8001
```

Endpoints:
- `GET /sse` - SSE event stream
- `POST /messages` - Send messages

## Programmatic Usage

```python
from pywry.mcp.tools import get_tools
from pywry.mcp.handlers import handle_tool
from pywry.mcp.prompts import get_prompts, get_prompt_content
from pywry.mcp.resources import get_resources, read_resource

# Get all tools
tools = get_tools()

# Handle a tool call
events = {}
def make_callback(wid):
    return lambda data, event_type, label: events.setdefault(wid, []).append(data)

result = await handle_tool(
    name="create_widget",
    arguments={"html": "<h1>Hello</h1>", "title": "Test"},
    events=events,
    callback_factory=make_callback,
)

# Get prompts
prompts = get_prompts()
content = get_prompt_content("component_reference")

# Read resources
resources = get_resources()
readme = read_resource("pywry://docs/readme")
```
