# Setup

## Installation

Install PyWry with MCP support:

```bash
pip install pywry[mcp]
```

This installs the `mcp` SDK along with PyWry. Requires Python 3.10+.

## Starting the Server

### From the CLI

Two entry points are available:

```bash
# Module entry point
python -m pywry.mcp

# PyWry CLI (adds --headless/--native flags)
pywry mcp
```

### CLI Options

| Flag | Default | Description |
|:---|:---|:---|
| `--transport` | `stdio` | Transport type: `stdio`, `sse`, or `streamable-http` |
| `--port PORT` | `8001` | Port for HTTP transports |
| `--host HOST` | `127.0.0.1` | Host for HTTP transports |
| `--sse [PORT]` | `8001` | Shorthand for `--transport sse` |
| `--streamable-http [PORT]` | `8001` | Shorthand for `--transport streamable-http` |
| `--headless` | off | Use browser widgets instead of native windows |
| `--native` | off | Force native windows (overrides config) |
| `--name NAME` | `pywry-widgets` | Server name advertised to clients |

```bash
# stdio (Claude Desktop)
python -m pywry.mcp

# SSE on port 9000
python -m pywry.mcp --sse 9000

# Headless + SSE
pywry mcp --headless --sse

# Streamable HTTP
python -m pywry.mcp --streamable-http
```

### Programmatic

```python
from pywry.mcp import run_server

run_server(
    transport="stdio",   # "stdio", "sse", or "streamable-http"
    port=8001,
    host="127.0.0.1",
    headless=False,
)
```

Or create the server instance directly:

```python
from pywry.mcp import create_server

mcp = create_server()  # FastMCP instance with all tools registered
mcp.run(transport="stdio")
```

## Client Configuration

### Claude Desktop

#### macOS

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

#### Windows

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

#### Linux

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

### Virtual Environment

Point to the venv Python directly:

=== "macOS / Linux"

    ```json
    {
      "mcpServers": {
        "pywry": {
          "command": "/path/to/venv/bin/python",
          "args": ["-m", "pywry.mcp"]
        }
      }
    }
    ```

=== "Windows"

    ```json
    {
      "mcpServers": {
        "pywry": {
          "command": "C:\\path\\to\\venv\\Scripts\\python.exe",
          "args": ["-m", "pywry.mcp"]
        }
      }
    }
    ```

### Conda Environment

```json
{
  "mcpServers": {
    "pywry": {
      "command": "conda",
      "args": ["run", "-n", "myenv", "python", "-m", "pywry.mcp"]
    }
  }
}
```

### Headless Mode

For remote servers, Docker, CI, or SSH — use headless mode so widgets render in the browser instead of native windows:

```json
{
  "mcpServers": {
    "pywry": {
      "command": "python",
      "args": ["-m", "pywry.mcp"],
      "env": {
        "PYWRY_MCP__HEADLESS": "true"
      }
    }
  }
}
```

Or via CLI flags:

```json
{
  "mcpServers": {
    "pywry": {
      "command": "pywry",
      "args": ["mcp", "--headless"]
    }
  }
}
```

### SSE Transport

For web-based MCP clients that connect over HTTP:

```json
{
  "mcpServers": {
    "pywry": {
      "command": "python",
      "args": ["-m", "pywry.mcp", "--sse", "8001"]
    }
  }
}
```

The SSE endpoint is available at `http://127.0.0.1:8001/sse` with messages at `/messages/`.

## Configuration

### MCPSettings

All MCP settings can be configured via environment variables (`PYWRY_MCP__` prefix), config file, or programmatically:

| Setting | Env Variable | Default | Description |
|:---|:---|:---|:---|
| `name` | `PYWRY_MCP__NAME` | `pywry-widgets` | Server name |
| `transport` | `PYWRY_MCP__TRANSPORT` | `stdio` | Transport type |
| `host` | `PYWRY_MCP__HOST` | `127.0.0.1` | HTTP host |
| `port` | `PYWRY_MCP__PORT` | `8001` | HTTP port |
| `headless` | `PYWRY_MCP__HEADLESS` | `false` | Browser widget mode |
| `max_widgets` | `PYWRY_MCP__MAX_WIDGETS` | `100` | Max concurrent widgets |
| `widget_ttl` | `PYWRY_MCP__WIDGET_TTL` | `0` | Auto-cleanup seconds (0 = disabled) |
| `event_buffer_size` | `PYWRY_MCP__EVENT_BUFFER_SIZE` | `1000` | Max events per widget buffer |
| `default_width` | `PYWRY_MCP__DEFAULT_WIDTH` | `800` | Default window width |
| `default_height` | `PYWRY_MCP__DEFAULT_HEIGHT` | `600` | Default window height |
| `debug` | `PYWRY_MCP__DEBUG` | `false` | Verbose logging |
| `log_tools` | `PYWRY_MCP__LOG_TOOLS` | `false` | Log tool calls |
| `log_level` | `PYWRY_MCP__LOG_LEVEL` | `INFO` | Log level |
| `skills_auto_load` | `PYWRY_MCP__SKILLS_AUTO_LOAD` | `true` | Auto-load skills on connect |
| `include_tags` | `PYWRY_MCP__INCLUDE_TAGS` | `[]` | Only expose tools with these tags |
| `exclude_tags` | `PYWRY_MCP__EXCLUDE_TAGS` | `[]` | Exclude tools with these tags |

### Config File

```toml
# pywry.toml
[mcp]
name = "my-widgets"
transport = "sse"
port = 9000
headless = true
max_widgets = 50
debug = true
```

### Environment Variables

```json
{
  "mcpServers": {
    "pywry": {
      "command": "python",
      "args": ["-m", "pywry.mcp"],
      "env": {
        "PYWRY_MCP__HEADLESS": "true",
        "PYWRY_MCP__MAX_WIDGETS": "50",
        "PYWRY_MCP__DEBUG": "true"
      }
    }
  }
}
```

## Verifying the Setup

1. Restart Claude Desktop after editing the config
2. Open a new conversation
3. Ask: *"What PyWry tools do you have available?"*
4. Claude should list 25 tools

You can also test manually:

```bash
# Check the server starts
python -m pywry.mcp --sse 8001 &

# Test with curl (SSE)
curl http://127.0.0.1:8001/sse
```

## Troubleshooting

### Server Not Starting

```bash
# Verify Python and pywry are accessible
python -c "import pywry.mcp; print('OK')"

# Check MCP is installed
python -c "import mcp; print(mcp.__version__)"
```

### Tools Not Available in Claude

1. Verify the config JSON is valid — use a JSON linter
2. Check the file path matches your OS (see above)
3. Restart Claude Desktop completely (quit + relaunch, not just close the window)
4. Check Claude Desktop logs for error messages

### Port Already in Use

```bash
# macOS/Linux
lsof -i :8001

# Windows
netstat -ano | findstr :8001
```

### Debug Mode

Run with debug logging to see what's happening:

```bash
PYWRY_MCP__DEBUG=true PYWRY_MCP__LOG_TOOLS=true python -m pywry.mcp
```

## Next Steps

- **[Tools Reference](tools.md)** — Every tool with parameters and examples
- **[Skills & Resources](skills.md)** — How the agent learns PyWry
- **[Examples](examples.md)** — Common workflows and patterns
