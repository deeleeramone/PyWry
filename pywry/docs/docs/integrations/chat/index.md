# Chat Artifacts And Providers

This page explains two advanced features of the PyWry chat system: **artifacts** (rich content blocks rendered inline in the chat) and **providers** (adapters that connect the chat UI to different AI backends). Read the [Chat Guide](../../components/chat/index.md) first if you haven't — it covers the basics of `ChatManager`, handlers, and streaming.

## What Are Artifacts?

When your chat handler yields plain text, it appears as a normal message bubble. But sometimes you need to show structured content — a syntax-highlighted code block, an interactive chart, a data table, or a JSON tree. These are called **artifacts**.

Artifacts render as collapsible panels inside the chat transcript. Each one has a header with a title and a toggle to expand/collapse the content. They are not stored in conversation history — they exist only in the current rendering.

### How To Emit Artifacts

Yield an artifact object from your handler:

```python
from pywry.chat.artifacts import CodeArtifact


def handler(messages, ctx):
    yield "Here is the code you asked for:"
    yield CodeArtifact(
        title="fibonacci.py",
        language="python",
        content="""def fib(n):
    if n <= 1:
        return n
    return fib(n - 1) + fib(n - 2)""",
    )
    yield "This uses simple recursion."
```

Artifacts can appear anywhere in the response stream — before text, after text, or between text chunks. The chat UI renders them in order.

### All Artifact Types

#### CodeArtifact

Syntax-highlighted code with language detection.

```python
from pywry.chat.artifacts import CodeArtifact

yield CodeArtifact(title="query.sql", language="sql", content="SELECT * FROM users;")
```

**Fields:**

- `title` — displayed in the artifact header
- `language` — language hint for syntax highlighting (e.g. `"python"`, `"javascript"`, `"sql"`)
- `content` — the source code string

#### MarkdownArtifact

Rendered Markdown content.

```python
from pywry.chat.artifacts import MarkdownArtifact

yield MarkdownArtifact(
    title="Release Notes",
    content="# v2.0\n\n- New chat system\n- ACP support\n- TradingView charts",
)
```

#### HtmlArtifact

Raw HTML in a sandboxed container. Use this for custom visualizations or embedded content.

```python
from pywry.chat.artifacts import HtmlArtifact

yield HtmlArtifact(
    title="Status Card",
    content='<div style="padding:16px;background:#1e1e2e;border-radius:8px"><b>All systems operational</b></div>',
)
```

#### TableArtifact

An interactive data table powered by AG Grid. Supports sorting, filtering, and column resizing. Accepts the same data formats as `pywry.grid.normalize_data()` — a list of dicts, a dict of lists, or a pandas DataFrame.

```python
from pywry.chat.artifacts import TableArtifact

yield TableArtifact(
    title="Portfolio Positions",
    data=[
        {"symbol": "AAPL", "qty": 120, "price": 189.84, "value": 22780.80},
        {"symbol": "MSFT", "qty": 80, "price": 425.22, "value": 34017.60},
        {"symbol": "GOOGL", "qty": 50, "price": 176.49, "value": 8824.50},
    ],
    height="280px",
)
```

**Fields:**

- `data` — rows as list of dicts, or a pandas DataFrame
- `height` — CSS height for the grid container (default `"400px"`)
- `column_defs` — optional AG Grid column definitions for fine-grained control
- `grid_options` — optional AG Grid configuration overrides

The AG Grid JavaScript library (~200KB gzipped) is loaded automatically the first time a `TableArtifact` is emitted. If you want to avoid the first-render delay, pass `include_aggrid=True` to `ChatManager`.

#### PlotlyArtifact

An interactive Plotly.js chart. Accepts any standard Plotly figure dict with `data`, `layout`, and optionally `config`.

```python
from pywry.chat.artifacts import PlotlyArtifact

yield PlotlyArtifact(
    title="Revenue Trend",
    figure={
        "data": [
            {"type": "scatter", "x": ["Jan", "Feb", "Mar"], "y": [100, 150, 200], "name": "Revenue"},
            {"type": "scatter", "x": ["Jan", "Feb", "Mar"], "y": [80, 90, 110], "name": "Costs"},
        ],
        "layout": {"title": {"text": "Q1 Financials"}},
    },
    height="360px",
)
```

The Plotly.js library (~1MB gzipped) is loaded automatically on first use. Preload with `include_plotly=True`.

#### ImageArtifact

Displays an image from a URL or a base64 data URI. The URL is validated to block `javascript:` schemes.

```python
from pywry.chat.artifacts import ImageArtifact

yield ImageArtifact(
    title="Architecture Diagram",
    url="https://example.com/architecture.png",
    alt="System architecture showing three microservices",
)
```

#### JsonArtifact

A collapsible JSON tree viewer with syntax highlighting.

```python
from pywry.chat.artifacts import JsonArtifact

yield JsonArtifact(
    title="API Response",
    data={"status": 200, "results": [{"id": 1, "name": "Widget A"}, {"id": 2, "name": "Widget B"}]},
)
```

#### TradingViewArtifact

An interactive financial chart powered by TradingView's lightweight-charts library. Supports candlestick, line, area, bar, baseline, and histogram series. Multiple series can be overlaid on a single chart, and you can add markers for buy/sell signals.

```python
from pywry.chat.artifacts import TradingViewArtifact, TradingViewSeries

yield TradingViewArtifact(
    title="AAPL Daily Chart",
    series=[
        # Candlestick series for OHLC price data
        TradingViewSeries(
            type="candlestick",
            data=[
                {"time": "2024-01-02", "open": 185.5, "high": 186.1, "low": 184.0, "close": 185.6},
                {"time": "2024-01-03", "open": 185.6, "high": 187.0, "low": 183.7, "close": 184.3},
                {"time": "2024-01-04", "open": 184.3, "high": 185.8, "low": 183.0, "close": 185.2},
            ],
        ),
        # Moving average as a line overlay
        TradingViewSeries(
            type="line",
            data=[
                {"time": "2024-01-02", "value": 185.0},
                {"time": "2024-01-03", "value": 184.9},
                {"time": "2024-01-04", "value": 184.8},
            ],
            options={"color": "#f9e2af", "lineWidth": 1},
        ),
        # Volume as a histogram at the bottom
        TradingViewSeries(
            type="histogram",
            data=[
                {"time": "2024-01-02", "value": 5200000, "color": "#a6e3a1"},
                {"time": "2024-01-03", "value": 4800000, "color": "#f38ba8"},
                {"time": "2024-01-04", "value": 6100000, "color": "#a6e3a1"},
            ],
        ),
    ],
    options={
        "timeScale": {"timeVisible": True},
        "rightPriceScale": {"borderColor": "#45475a"},
    },
    height="500px",
)
```

**`TradingViewSeries` fields:**

- `type` — one of `"candlestick"`, `"line"`, `"area"`, `"bar"`, `"baseline"`, `"histogram"`
- `data` — list of data points. Candlestick: `{time, open, high, low, close}`. Others: `{time, value}`.
- `options` — series-level configuration (colors, line width, price format, etc.)
- `markers` — optional list of marker objects for buy/sell signals and annotations

**`TradingViewArtifact` fields:**

- `title` — displayed in the artifact header
- `series` — list of `TradingViewSeries` to overlay on the chart
- `options` — chart-level options passed to `LightweightCharts.createChart()` (layout, grid, crosshair, timeScale, etc.)
- `height` — CSS height for the chart container (default `"400px"`)

The chart automatically applies a dark theme matching PyWry's default dark UI. The lightweight-charts library (~50KB gzipped) is loaded on first use.

!!! note "TradingView Widget vs TradingView Artifact"
    PyWry also has a full `PyWryTVChartWidget` for standalone TradingView charts with persistent layouts, real-time data streaming, drawing tools, and indicators. The `TradingViewArtifact` is a lighter version designed for inline rendering within chat conversations. Use the widget for dedicated charting screens; use the artifact when an AI assistant needs to show financial data in a chat response.

## Asset Loading

Artifacts that need frontend libraries (AG Grid, Plotly, lightweight-charts) load them automatically the first time that artifact type appears. This is called **lazy loading**.

If you know your handler will definitely produce charts or tables, you can **eagerly load** the libraries at startup to avoid the first-render delay:

```python
chat = ChatManager(
    handler=handler,
    include_plotly=True,    # Preload Plotly.js
    include_aggrid=True,    # Preload AG Grid
)
```

### How Lazy Loading Works

In **native window and browser modes**, lazy loading works by emitting a `chat:load-assets` event that injects `<script>` and `<style>` tags into the page via HTTP.

In **Jupyter notebook mode** (anywidget), there is no HTTP server. Instead, the `ChatManager` detects that it is bound to a `PyWryChatWidget` and pushes the JavaScript/CSS through traitlet synchronization — the `_asset_js` and `_asset_css` traits on the widget. The frontend ESM listens for trait changes and injects the assets into the document. This happens transparently; you do not need to change any code.

## Providers

A **provider** is a Python class that connects `ChatManager` to an AI backend. Instead of writing a handler function that calls an LLM API, you instantiate a provider and pass it to `ChatManager`. The provider handles message formatting, API calls, streaming, and cancellation.

All providers implement the same interface — four methods that follow the ACP session lifecycle:

1. **`initialize(capabilities)`** — called once when the chat starts. The provider and client exchange what features they support (e.g., image input, file system access).
2. **`new_session(cwd)`** — creates a new conversation. Returns a session ID.
3. **`prompt(session_id, content_blocks, cancel_event)`** — processes a user message. This is an async generator that yields `SessionUpdate` objects (text chunks, tool calls, plan updates, etc.) as the response streams in.
4. **`cancel(session_id)`** — aborts an ongoing response.

You do not call these methods yourself. `ChatManager` calls them automatically when the user sends messages, switches threads, or clicks Stop.

### OpenAIProvider

Connects to the OpenAI API using the `openai` Python package.

```bash
pip install 'pywry[openai]'
```

```python
from pywry.chat.manager import ChatManager
from pywry.chat.providers.openai import OpenAIProvider

provider = OpenAIProvider(api_key="sk-...")
chat = ChatManager(provider=provider, system_prompt="You are helpful.")
```

The provider converts PyWry's `ContentBlock` messages into OpenAI's message format, calls the chat completions API with streaming enabled, and yields `AgentMessageUpdate` for each text chunk. It supports cooperative cancellation.

### AnthropicProvider

Connects to the Anthropic API using the `anthropic` Python package.

```bash
pip install 'pywry[anthropic]'
```

```python
from pywry.chat.manager import ChatManager
from pywry.chat.providers.anthropic import AnthropicProvider

provider = AnthropicProvider(api_key="sk-ant-...")
chat = ChatManager(provider=provider, system_prompt="You are helpful.")
```

Works the same way as the OpenAI provider but uses Anthropic's message streaming API.

### MagenticProvider

Connects to any LLM backend that [magentic](https://magentic.dev) supports — OpenAI, Anthropic, LiteLLM (100+ providers), Mistral, Ollama, Azure, and any OpenAI-compatible API.

```bash
pip install 'pywry[magentic]'
```

```python
from pywry.chat.manager import ChatManager
from pywry.chat.providers.magentic import MagenticProvider

# Pass a model name string (creates an OpenAI-backed model)
provider = MagenticProvider("gpt-4o-mini", api_key="sk-...")

# Or pass a preconfigured magentic ChatModel instance
from magentic import OpenaiChatModel
model = OpenaiChatModel("gpt-4o", base_url="http://localhost:11434/v1/")
provider = MagenticProvider(model)

chat = ChatManager(provider=provider)
```

### CallbackProvider

The lightest option — wraps a Python callable as a provider. Use this when you already have your own AI logic and just want it behind the provider interface.

```python
from pywry.chat.providers.callback import CallbackProvider
from pywry.chat.updates import AgentMessageUpdate


def my_prompt(session_id, content_blocks, cancel_event):
    """Your custom AI logic goes here.

    Parameters
    ----------
    session_id : str
        The active conversation session.
    content_blocks : list[ContentBlock]
        The user's message as ACP content blocks.
    cancel_event : asyncio.Event | None
        Set when the user clicks Stop.

    Yields
    ------
    SessionUpdate
        Response chunks to stream back to the UI.
    """
    # Extract text from content blocks
    from pywry.chat.models import TextPart
    user_text = "".join(p.text for p in content_blocks if isinstance(p, TextPart))

    # Your logic here
    for word in f"You said: {user_text}".split():
        yield AgentMessageUpdate(text=word + " ")


provider = CallbackProvider(prompt_fn=my_prompt)
```

### StdioProvider

Connects to an external ACP-compatible agent that runs as a subprocess and communicates over stdin/stdout using JSON-RPC 2.0. This is how you connect PyWry's chat UI to tools like Claude Code or Gemini CLI.

```bash
pip install 'pywry[acp]'
```

```python
from pywry.chat.manager import ChatManager
from pywry.chat.providers.stdio import StdioProvider

provider = StdioProvider(
    command="claude",
    args=["--agent"],
    env={"ANTHROPIC_API_KEY": "sk-ant-..."},
)
chat = ChatManager(provider=provider)
```

The stdio provider:

- Spawns the agent as a subprocess
- Sends `initialize` and `session/new` on startup
- Forwards user messages as `session/prompt` requests
- Parses `session/update` notifications from stdout and yields them as `SessionUpdate` objects
- Handles `session/request_permission` callbacks from the agent (renders as inline approval cards in the chat)
- Sends `session/cancel` when the user clicks Stop
- Cleans up the subprocess on shutdown

### DeepAgentProvider

Connects to [LangChain Deep Agents](https://docs.langchain.com/oss/python/deepagents/overview) — a full agent harness built on LangGraph with built-in filesystem tools, task planning, subagent delegation, and human-in-the-loop approval.

```bash
pip install 'pywry[deepagent]'
```

The `deepagent` extra pulls in both `deepagents>=0.1.0` and
`langchain-mcp-adapters>=0.1.0`.  The MCP adapters package is what
bridges any MCP server's tools into LangChain tools the agent can call.

```python
from deepagents import create_deep_agent
from pywry.chat.manager import ChatManager
from pywry.chat.providers.deepagent import DeepagentProvider

agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    tools=[my_search_tool],
    system_prompt="You are a research assistant.",
)

provider = DeepagentProvider(agent)
chat = ChatManager(provider=provider)
```

You can also pass parameters directly and let the provider build the agent:

```python
provider = DeepagentProvider(
    model="openai:gpt-4o",
    tools=[my_search_tool],
    system_prompt="You are a research assistant.",
    subagents=[{"name": "researcher", "description": "Deep research", "tools": [tavily_search]}],
)
```

#### Constructor parameters

| Parameter | Type | Default | Notes |
|-----------|------|---------|-------|
| `agent` | `CompiledGraph \| None` | `None` | Pre-built agent.  When `None` the provider builds one itself using the rest of the parameters. |
| `model` | `str` | `"anthropic:claude-sonnet-4-6"` | Any model string `create_deep_agent()` accepts (`"openai:gpt-4o"`, `"nvidia:meta/llama-3.3-70b-instruct"`, etc.). |
| `tools` | `list` | `None` | LangChain-compatible tool callables.  Merged with any MCP-served tools before the agent is built. |
| `mcp_servers` | `dict[str, dict]` | `None` | MCP servers the agent should connect to.  See the section below. |
| `system_prompt` | `str` | `""` | Appended to PyWry's base prompt before being passed to `create_deep_agent`. |
| `checkpointer` | LangGraph saver | `None` | Explicit checkpointer.  Auto-created when `auto_checkpointer=True`. |
| `store` | LangGraph store | `None` | Explicit memory store.  Auto-created when `auto_store=True`. |
| `memory`, `interrupt_on`, `backend`, `subagents`, `middleware` | — | `None` | Forwarded to `create_deep_agent()` when provided. |
| `skills` | `list[str] \| None` | `None` | File paths to Deep Agents skill markdown.  The PyWry MCP package ships seventeen of these under `pywry.mcp.skills` — point at the ones relevant to your agent.  See below. |
| `auto_checkpointer` | `bool` | `True` | Creates a checkpointer matching PyWry's state backend (Memory/Redis/SQLite) on first agent build. |
| `auto_store` | `bool` | `True` | Creates an `InMemoryStore` on first agent build when no explicit store is given. |
| `recursion_limit` | `int` | `50` | LangGraph recursion limit per prompt turn.  Every tool call costs 2–3 graph steps, so the default (LangGraph's own is 25) leaves headroom for multi-tool turns without hiding pathological loops. |

#### Connecting to MCP servers

`mcp_servers` takes a dict in the `langchain_mcp_adapters.client.MultiServerMCPClient` format — one entry per server, keyed by a short name:

```python
provider = DeepagentProvider(
    model="openai:gpt-4o",
    system_prompt="You are a chart analyst.",
    mcp_servers={
        # Remote HTTP transport
        "pywry": {
            "transport": "streamable_http",
            "url": "http://127.0.0.1:8765/mcp",
        },
        # Local stdio subprocess
        "fs": {
            "transport": "stdio",
            "command": "uvx",
            "args": ["mcp-server-filesystem", "/tmp"],
        },
    },
)
```

On first `_build_agent()` the provider calls `MultiServerMCPClient.get_tools()`,
converts every MCP tool into a LangChain tool, and merges the result
with `self._tools` before handing the combined list to
`create_deep_agent(tools=...)`.  The agent then sees local `@tool`
callables and MCP-served tools in a single unified list.

Pass `mcp_servers=None` (the default) to skip the MCP bridge entirely —
the adapters package is only imported when at least one server is
configured.

ACP clients can also add servers at session start by passing
`mcp_servers=[...]` to `new_session()`; the provider converts those
entries into the `MultiServerMCPClient` format, merges them into its
existing map, and rebuilds the agent on the next prompt turn.

#### In-process PyWry MCP server

To run PyWry's own MCP server alongside the app and have the Deep Agent
drive the same widgets the user sees, start it in a daemon thread and
point the provider at it:

```python
import socket, threading, sys
import pywry.mcp.state as mcp_state
from pywry.mcp.server import create_server

def start_pywry_mcp_server(app, chart_widget_id):
    """Start PyWry's FastMCP server in-process with shared app state."""
    mcp_state._app = app
    mcp_state.register_widget(chart_widget_id, app)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    mcp = create_server()
    threading.Thread(
        target=lambda: mcp.run(transport="streamable-http",
                               host="127.0.0.1", port=port),
        daemon=True,
    ).start()
    return f"http://127.0.0.1:{port}/mcp"

url = start_pywry_mcp_server(app, chart_widget_id="chart")
provider = DeepagentProvider(
    model="openai:gpt-4o",
    mcp_servers={"pywry": {"transport": "streamable_http", "url": url}},
)
```

The in-process server operates on the same `pywry.mcp.state._app`
singleton the running app uses, so `send_event`, `update_marquee`,
`update_plotly`, and all other MCP tools act on the live widget.

#### Loading PyWry skill files

PyWry ships seventeen agent-facing skill markdown files under
`pywry.mcp.skills`.  Pass the ones relevant to your agent's task
surface as `skills=` — Deep Agents exposes each file as on-demand
reference the agent can pull in when needed.

```python
import pathlib
from pywry.mcp import skills as _skills_pkg

skills_root = pathlib.Path(_skills_pkg.__file__).parent

provider = DeepagentProvider(
    model="nvidia:meta/llama-3.3-70b-instruct",
    mcp_servers={"pywry": {"transport": "streamable_http", "url": url}},
    skills=[
        str(skills_root / "tvchart" / "SKILL.md"),
        str(skills_root / "chat_agent" / "SKILL.md"),
        str(skills_root / "events" / "SKILL.md"),
    ],
)
```

The skills most useful for a running-widget agent (as opposed to the
widget-builder agents `pywry build_app` uses) are:

| Skill | When to include |
|-------|-----------------|
| `tvchart` | Any agent driving a `tvchart` widget — documents every typed tvchart MCP tool, the state shape, and compare-derivative indicator flow |
| `chat_agent` | Every DeepagentProvider-backed agent — explains `@<name>` context attachments, tool-result cards, edit/resend flow, reply style |
| `events` | Agents that use `send_event` / `get_events` or need to reason about request/response correlation |
| `component_reference` | Only when the agent needs to CREATE widgets (not relevant for agents that just operate on an existing one) |
| `authentication` | Agents that gate actions on OAuth / RBAC state |

See `pywry.mcp.skills.SKILL_METADATA` for the full inventory, and
[`docs/mcp/skills.md`](../../mcp/skills.md) for the full skill
reference table.

#### ACP session updates

The provider maps LangGraph streaming events to ACP session updates:

- Text chunks from the LLM → `AgentMessageUpdate`
- Tool invocations (`read_file`, `write_file`, `execute`, MCP tools, etc.) → `ToolCallUpdate` with lifecycle tracking (`in_progress` → `completed`/`failed`).  Completed updates carry the serialized tool output in `content`.
- The `write_todos` built-in tool → `PlanUpdate` with structured task entries
- `interrupt_on` tools → `PermissionRequestUpdate` for inline approval in the chat UI

#### Session persistence

Persistence adapts to PyWry's state backend automatically. With
`auto_checkpointer=True` (the default), the provider creates a
`MemorySaver` for desktop apps, a `RedisSaver` for deploy mode, or a
`SqliteSaver` for local persistent storage — matching whatever backend
the rest of PyWry is using.  The auto-creation runs the first time
`_build_agent()` is called so callers that bypass the async
`initialize()` still get conversation-history persistence across turns.

Each chat UI thread maps to its own LangGraph `thread_id`, so prior
turns in the same conversation are automatically visible to the agent
on every new message.

#### Edit / resend truncation

When the user hits **Edit** or **Resend** on a prior message, the chat
manager calls `provider.truncate_session(session_id, kept_messages)`
before re-running generation.  `DeepagentProvider` implements this by
deleting the thread state from the checkpointer (via `delete_thread()`
on newer LangGraph saver APIs, falling back to dict-level cleanup) or
— if deletion isn't supported — remapping the session to a fresh
`thread_id` so the next prompt runs against an empty graph state.

### Provider Factory

If you want to select a provider by name at runtime (e.g., from a config file):

```python
from pywry.chat import get_provider

provider = get_provider("openai", api_key="sk-...")
# Supported names: "openai", "anthropic", "callback", "magentic", "stdio", "deepagent"
```

## RBAC Integration

When PyWry's authentication system is enabled (deploy mode with `auth_enabled=True`), all chat operations are gated by role-based access control. The permission mapping is defined in `pywry.chat.permissions`:

| ACP Operation | Required Permission | Who Can Do It |
|---------------|-------------------|--------------|
| Send a message (`session/prompt`) | `write` | Editors, Admins |
| Cancel generation (`session/cancel`) | `write` | Editors, Admins |
| Change settings (`session/set_config_option`) | `write` | Editors, Admins |
| Switch mode (`session/set_mode`) | `write` | Editors, Admins |
| Approve tool execution (`session/request_permission`) | `write` | Editors, Admins |
| Read a file (`fs/read_text_file`) | `read` | Viewers, Editors, Admins |
| Write a file (`fs/write_text_file`) | `admin` | Admins only |
| Create/kill terminal (`terminal/*`) | `admin` | Admins only |

The default roles are:

- **`viewer`** — read-only access. Can see the chat but cannot send messages.
- **`editor`** — read/write access. Can chat normally.
- **`admin`** — full access. Can additionally approve file writes and terminal access from ACP agents.

If authentication is not enabled, all operations are permitted for all users.

## Examples

- **`examples/pywry_demo_chat_artifacts.py`** — demonstrates all artifact types (code, markdown, HTML, table, plotly, image, JSON, TradingView)
- **`examples/pywry_demo_chat.py`** — demonstrates ChatManager with streaming, plan updates, thinking output, and slash commands
- **`examples/pywry_demo_chat_magentic.py`** — demonstrates magentic provider with tool call traces

## Next Steps

- [Chat Guide](../../components/chat/index.md) — basics of ChatManager and handlers
- [Chat Providers API](chat-providers.md) — API reference for all provider classes
