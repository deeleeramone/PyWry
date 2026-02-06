# MCP Server

Model Context Protocol server for AI agent integration. Expose PyWry widgets to LLMs like Claude.

## Quick Start

```bash
# Run with stdio transport (default)
python -m pywry.mcp

# Run with SSE transport
python -m pywry.mcp --sse 8001

# Headless mode (inline widgets)
python -m pywry.mcp --headless
```

## Claude Desktop Config

```json
{
  "mcpServers": {
    "pywry": {
      "command": "python",
      "args": ["-m", "pywry.mcp"]
    }
  }
}
```

For headless mode (browser widgets instead of native):

```json
{
  "mcpServers": {
    "pywry": {
      "command": "python",
      "args": ["-m", "pywry.mcp", "--headless"]
    }
  }
}
```

## Ask Claude

Now you can ask Claude to create visualizations:

> "Create a scatter plot of sales data with x=month and y=revenue"

Claude will use the MCP tools to generate and display the chart.

## Available Tools

| Tool | Description |
|------|-------------|
| `get_skills` | Get component reference and guidance |
| `create_widget` | Create HTML widget with toolbars |
| `show_plotly` | Create Plotly chart widgets |
| `show_dataframe` | Create AG Grid table widgets |
| `set_content` | Update element text/HTML |
| `set_style` | Update element CSS styles |
| `show_toast` | Display toast notification |
| `update_theme` | Switch dark/light theme |
| `update_plotly` | Update Plotly figure |
| `send_event` | Send custom event to widget |
| `get_events` | Retrieve queued events |

See [Capabilities](capabilities.md) for full tool reference.

## Architecture

```
┌─────────────────────┐     MCP Protocol     ┌─────────────────────┐
│   Claude Desktop    │◄───────────────────►│   PyWry MCP Server   │
│   or AI Agent       │                      │                      │
└─────────────────────┘                      └─────────────────────┘
                                                       │
                                                       ▼
                                             ┌─────────────────────┐
                                             │    PyWry Widgets    │
                                             │  (Windows/Browser)  │
                                             └─────────────────────┘
```

## Next Steps

- **[Setup Guide](setup.md)** — Detailed installation instructions
- **[Capabilities](capabilities.md)** — Full tool reference
- **[Examples](examples.md)** — Common use cases
- **[API Reference](../reference/mcp.md)** — Programmatic usage
