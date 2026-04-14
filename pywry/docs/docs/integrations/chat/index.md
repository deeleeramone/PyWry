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

The provider maps LangGraph streaming events to ACP session updates:

- Text chunks from the LLM → `AgentMessageUpdate`
- Tool invocations (`read_file`, `write_file`, `execute`, etc.) → `ToolCallUpdate` with lifecycle tracking (pending → in_progress → completed/failed)
- The `write_todos` built-in tool → `PlanUpdate` with structured task entries
- `interrupt_on` tools → `PermissionRequestUpdate` for inline approval in the chat UI

Session persistence adapts to PyWry's state backend automatically. With `auto_checkpointer=True` (default), the provider creates a `MemorySaver` for desktop apps, a `RedisSaver` for deploy mode, or a `SqliteSaver` for local persistent storage — matching whatever backend the rest of PyWry is using.

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
