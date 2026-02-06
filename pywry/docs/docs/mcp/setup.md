# MCP Server Setup

Complete guide to setting up the PyWry MCP server.

## Prerequisites

- Python 3.10+
- PyWry installed
- MCP package (`pip install mcp`)
- Claude Desktop (for Claude integration) or another MCP-compatible client

## Installation

Install PyWry with MCP support:

```bash
pip install pywry[mcp]
# or
pip install pywry mcp
```

## Starting the Server

### CLI

```bash
# stdio transport (default, for Claude Desktop)
python -m pywry.mcp

# SSE transport on custom port
python -m pywry.mcp --sse 8001

# Headless mode (inline widgets, no native windows)
python -m pywry.mcp --headless
```

### Programmatic

```python
from pywry.mcp import run_server

run_server(
    transport="stdio",  # or "sse"
    port=8001,          # SSE port
    headless=False,     # True for inline widgets
)
```

## Claude Desktop Configuration

### macOS

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

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

### Windows

Edit `%APPDATA%\Claude\claude_desktop_config.json`:

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

### Linux

Edit `~/.config/claude/claude_desktop_config.json`:

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

## Using a Virtual Environment

If PyWry is installed in a virtual environment:

### macOS/Linux

```json
{
  "mcpServers": {
    "pywry": {
      "command": "/path/to/venv/bin/python",
      "args": ["-m", "pywry", "mcp"]
    }
  }
}
```

### Windows

```json
{
  "mcpServers": {
    "pywry": {
      "command": "C:\\path\\to\\venv\\Scripts\\python.exe",
      "args": ["-m", "pywry", "mcp"]
    }
  }
}
```

## Environment Variables

Pass environment variables for configuration:

```json
{
  "mcpServers": {
    "pywry": {
      "command": "python",
      "args": ["-m", "pywry", "mcp"],
      "env": {
        "PYWRY_RENDERING_PATH": "browser",
        "PYWRY_SERVER__PORT": "8080"
      }
    }
  }
}
```

## Verifying the Setup

1. Restart Claude Desktop after editing the config
2. Open a new conversation
3. Ask Claude: "What PyWry tools do you have available?"
4. Claude should list the available MCP tools

## Troubleshooting

### Server Not Starting

Check Python is in PATH:

```bash
which python
python --version
```

### Tools Not Available

1. Verify config file syntax is valid JSON
2. Check file path is correct for your OS
3. Restart Claude Desktop completely

### Connection Errors

Ensure no other process is using the same port:

```bash
lsof -i :8766  # macOS/Linux
netstat -ano | findstr :8766  # Windows
```

### View Server Logs

Run manually to see errors:

```bash
python -m pywry mcp --verbose
```

## Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `--transport` | `stdio` | Transport type: `stdio` or `sse` |
| `--port` | `8001` | Port for SSE transport |
| `--sse [PORT]` | `8001` | Shorthand for `--transport sse --port N` |

## Security Considerations

The MCP server runs locally and only accepts connections from localhost by default. For production use:

1. Use authentication tokens
2. Restrict network access
3. Run in a sandboxed environment

## Next Steps

- **[Capabilities](capabilities.md)** — Available tools and resources
- **[Examples](examples.md)** — Usage examples
