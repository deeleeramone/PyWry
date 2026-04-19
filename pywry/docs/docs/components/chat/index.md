# Chat

PyWry ships a complete chat UI component that works in native desktop windows, Jupyter notebooks, and browser tabs. It handles the entire conversation lifecycle — rendering messages, streaming responses token-by-token, managing multiple conversation threads, and displaying rich content like code blocks, charts, and data tables inline.

The chat system is built on the **Agent Client Protocol (ACP)**, an open standard that defines how AI coding agents communicate with client applications. You do not need to know anything about ACP to use PyWry chat — the protocol details are handled internally. What it means in practice is that the same chat component can talk to any ACP-compatible agent (like Claude Code or Gemini CLI) as easily as it talks to the OpenAI or Anthropic APIs.

## Architecture Overview

The chat system has two layers:

1. **`ChatManager`** — the high-level orchestrator that most developers should use. It handles thread management, event wiring, streaming, cancellation, slash commands, settings menus, and all the plumbing between your AI backend and the chat UI.

2. **`build_chat_html()`** — the low-level HTML builder that produces the raw chat DOM structure. Use this only if you are assembling a completely custom chat experience and want to handle all events yourself.

## How It Works

When a user types a message in the chat input and presses send:

1. The frontend emits a `chat:user-message` event with the text.
2. `ChatManager` receives the event, stores the message in the thread history, and starts a background thread.
3. The background thread calls your **handler function** (or **provider**) with the conversation history.
4. Your handler returns or yields response chunks — plain strings for text, or typed objects for rich content.
5. `ChatManager` dispatches each chunk to the frontend as it arrives, which renders it in real time.
6. When the handler finishes, the assistant message is finalized and stored in thread history.

The user can click **Stop** at any time to cancel generation. Your handler receives this signal through `ctx.cancel_event`.

## Getting Started

### Install

```bash
pip install pywry
```

For AI provider support, install the optional extras:

```bash
pip install 'pywry[openai]'      # OpenAI
pip install 'pywry[anthropic]'   # Anthropic
pip install 'pywry[magentic]'    # Magentic (100+ providers)
pip install 'pywry[acp]'         # External ACP agents
pip install 'pywry[all]'         # Everything
```

### Minimal Example

This creates a chat window with a simple echo handler:

```python
from pywry import HtmlContent, PyWry
from pywry.chat.manager import ChatManager


def handler(messages, ctx):
    """Called every time the user sends a message.

    Parameters
    ----------
    messages : list[dict]
        The full conversation history for the active thread.
        Each dict has 'role' ('user' or 'assistant') and 'text'.
    ctx : ChatContext
        Context object with thread_id, settings, cancel_event, etc.

    Returns or yields
    -----------------
    str or SessionUpdate objects — see below.
    """
    user_text = messages[-1]["text"]
    return f"You said: {user_text}"


app = PyWry(title="Chat Demo")
chat = ChatManager(
    handler=handler,
    welcome_message="Hello! Type a message to get started.",
)

widget = app.show(
    HtmlContent(html="<h1>My App</h1>"),
    toolbars=[chat.toolbar(position="right")],
    callbacks=chat.callbacks(),
)

chat.bind(widget)
app.block()
```

Three things must be wired together:

1. **`chat.toolbar()`** — returns a collapsible sidebar panel containing the chat UI. Pass it to `app.show(toolbars=[...])`.
2. **`chat.callbacks()`** — returns a dict mapping `chat:*` event names to handler methods. Pass it to `app.show(callbacks=...)`.
3. **`chat.bind(widget)`** — tells the manager which widget to send events back to. Call this after `app.show()` returns.

## Writing Handlers

The handler function is where your AI logic lives. It receives the conversation history and a context object, and produces the assistant's response.

### Return a String

The simplest handler returns a complete string. The entire response appears at once.

```python
def handler(messages, ctx):
    return "Here is my answer."
```

### Yield Strings (Streaming)

For a streaming experience where text appears word-by-word, yield string chunks from a generator:

```python
import time


def handler(messages, ctx):
    words = "This streams one word at a time.".split()
    for word in words:
        if ctx.cancel_event.is_set():
            return  # User clicked Stop
        yield word + " "
        time.sleep(0.05)
```

Always check `ctx.cancel_event.is_set()` between chunks. This is how the Stop button works — it sets the event, and your handler should exit promptly.

### Yield Rich Objects

Beyond plain text, handlers can yield typed objects that render as structured UI elements:

```python
from pywry.chat.updates import PlanUpdate, StatusUpdate, ThinkingUpdate
from pywry.chat.session import PlanEntry


def handler(messages, ctx):
    # Show a transient status message (disappears when next content arrives)
    yield StatusUpdate(text="Searching documentation...")

    # Show collapsible thinking/reasoning (not stored in history)
    yield ThinkingUpdate(text="Evaluating three possible approaches...\n")

    # Show a task plan with progress tracking
    yield PlanUpdate(entries=[
        PlanEntry(content="Search docs", priority="high", status="completed"),
        PlanEntry(content="Synthesize answer", priority="high", status="in_progress"),
    ])

    # Stream the actual answer
    yield "Based on the documentation, the answer is..."
```

These objects are called **session updates** and follow the ACP specification. The available types are:

| Type | What It Does |
|------|-------------|
| `StatusUpdate` | Shows a transient inline status (e.g. "Searching...") |
| `ThinkingUpdate` | Shows collapsible reasoning text (not saved to history) |
| `PlanUpdate` | Shows a task list with priority and status for each entry |
| `ToolCallUpdate` | Shows a tool invocation with name, kind, and lifecycle status |
| `CitationUpdate` | Shows a source reference link |
| `ArtifactUpdate` | Shows a rich content block (code, chart, table — see Artifacts below) |
| `PermissionRequestUpdate` | Shows an inline approval card for tool execution |
| `CommandsUpdate` | Dynamically registers slash commands |
| `ConfigOptionUpdate` | Pushes settings options from the agent |
| `ModeUpdate` | Switches the agent's operational mode |

You can mix these freely with plain text strings in any order.

### Async Handlers

All handler shapes work as `async` functions or async generators too:

```python
async def handler(messages, ctx):
    async for chunk in my_async_llm_stream(messages):
        if ctx.cancel_event.is_set():
            return
        yield chunk
```

## Using a Provider Instead of a Handler

If you want to connect to an actual LLM API, you can pass a **provider** instead of writing a handler function. Providers implement the ACP session interface and handle message formatting, streaming, and cancellation internally.

```python
from pywry.chat.manager import ChatManager
from pywry.chat.providers.openai import OpenAIProvider

provider = OpenAIProvider(api_key="sk-...")
chat = ChatManager(
    provider=provider,
    system_prompt="You are a helpful coding assistant.",
)
```

Available providers:

| Provider | Backend | Install |
|----------|---------|---------|
| `OpenAIProvider` | OpenAI API | `pip install 'pywry[openai]'` |
| `AnthropicProvider` | Anthropic API | `pip install 'pywry[anthropic]'` |
| `MagenticProvider` | Any magentic-supported LLM | `pip install 'pywry[magentic]'` |
| `CallbackProvider` | Your own Python callable | (included) |
| `StdioProvider` | External ACP agent via subprocess | `pip install 'pywry[acp]'` |
| `DeepagentProvider` | LangChain Deep Agents (planning, MCP tools, skills) | `pip install 'pywry[deepagent]'` |

See [Chat Providers](../../integrations/chat/chat-providers.md) for the reference API of each provider.

The `StdioProvider` is special — it spawns an external program (like `claude` or `gemini`) as a subprocess and communicates over stdin/stdout using JSON-RPC. This means you can connect PyWry's chat UI to any ACP-compatible agent without writing any adapter code.

See [Chat Artifacts And Providers](../../integrations/chat/index.md) for detailed provider documentation.

## Conversation Threads

`ChatManager` supports multiple conversation threads. The UI includes a thread picker dropdown in the header bar where users can create, switch between, rename, and delete threads.

Each thread has its own independent message history. The manager tracks:

- The active thread ID
- Thread titles
- Per-thread message lists

You can access these programmatically:

```python
chat.active_thread_id       # Currently selected thread
chat.threads                # Dict of thread_id → message list
chat.settings               # Current settings values
chat.send_message("Hi!")    # Inject a message into the active thread
```

## Slash Commands

Slash commands appear in a palette when the user types `/` in the input bar. Register them at construction time:

```python
from pywry.chat.models import ACPCommand


chat = ChatManager(
    handler=handler,
    slash_commands=[
        ACPCommand(name="/time", description="Show the current time"),
        ACPCommand(name="/clear", description="Clear the conversation"),
    ],
    on_slash_command=my_slash_handler,
)


def my_slash_handler(command, args, thread_id):
    if command == "/time":
        import time
        chat.send_message(f"It is {time.strftime('%H:%M:%S')}", thread_id)
```

The `/clear` command is always available by default — it clears the current thread's history.

## Settings Menu

The gear icon in the chat header opens a settings dropdown. Populate it with `SettingsItem` entries:

```python
from pywry.chat.manager import SettingsItem


def on_settings_change(key, value):
    if key == "model":
        chat.send_message(f"Switched to **{value}**")
    elif key == "temp":
        chat.send_message(f"Temperature set to **{value}**")


chat = ChatManager(
    handler=handler,
    settings=[
        SettingsItem(id="model", label="Model", type="select",
                     value="gpt-4", options=["gpt-4", "gpt-4o", "claude-sonnet"]),
        SettingsItem(id="temp", label="Temperature", type="range",
                     value=0.7, min=0, max=2, step=0.1),
        SettingsItem(id="stream", label="Streaming", type="toggle", value=True),
    ],
    on_settings_change=on_settings_change,
)
```

Setting values are available in your handler via `ctx.settings`:

```python
def handler(messages, ctx):
    model = ctx.settings.get("model", "gpt-4")
    temp = ctx.settings.get("temp", 0.7)
    # Use these to configure your LLM call
```

## File Attachments And Context Mentions

The chat input supports two ways to include extra context:

**File attachments** — users drag-and-drop or click the paperclip button to attach files:

```python
chat = ChatManager(
    handler=handler,
    enable_file_attach=True,
    file_accept_types=[".csv", ".json", ".py"],  # Required
)
```

**Widget mentions** — users type `@` to reference live dashboard components:

```python
chat = ChatManager(
    handler=handler,
    enable_context=True,
)
chat.register_context_source("sales-grid", "Sales Data")
```

When attachments are present, your handler receives them in `ctx.attachments`:

```python
def handler(messages, ctx):
    if ctx.attachments:
        yield StatusUpdate(text=f"Processing {len(ctx.attachments)} attachments...")
        for att in ctx.attachments:
            content = ctx.get_attachment(att.name)
            yield f"**{att.name}** ({att.type}): {len(content)} chars\n\n"
    yield "Here is my analysis of the attached data."
```

## Artifacts

Artifacts are rich content blocks that render inline in the chat transcript. Unlike streamed text, they appear as standalone visual elements — code editors, charts, tables, etc.

To emit an artifact, yield it from your handler wrapped in an `ArtifactUpdate`, or yield it directly (the manager auto-wraps `_ArtifactBase` subclasses):

```python
from pywry.chat.artifacts import CodeArtifact, PlotlyArtifact, TableArtifact, TradingViewArtifact

# Code with syntax highlighting
yield CodeArtifact(
    title="fibonacci.py",
    language="python",
    content="def fib(n):\n    if n <= 1:\n        return n\n    return fib(n - 1) + fib(n - 2)",
)

# Interactive Plotly chart
yield PlotlyArtifact(title="Revenue", figure={"data": [{"type": "bar", "x": [1,2], "y": [3,4]}]})

# AG Grid table
yield TableArtifact(title="Users", data=[{"name": "Alice", "age": 30}])

# TradingView financial chart
from pywry.chat.artifacts import TradingViewSeries
yield TradingViewArtifact(
    title="AAPL",
    series=[TradingViewSeries(type="candlestick", data=[
        {"time": "2024-01-02", "open": 185, "high": 186, "low": 184, "close": 185.5},
    ])],
)
```

Available artifact types: `CodeArtifact`, `MarkdownArtifact`, `HtmlArtifact`, `TableArtifact`, `PlotlyArtifact`, `ImageArtifact`, `JsonArtifact`, `TradingViewArtifact`.

The frontend libraries for `TableArtifact` (AG Grid), `PlotlyArtifact` (Plotly.js), and `TradingViewArtifact` (lightweight-charts) are loaded automatically the first time an artifact of that type is emitted. You can also preload them by passing `include_plotly=True` or `include_aggrid=True` to the `ChatManager` constructor.

## Notebook Mode

When running inside a Jupyter notebook with `anywidget` installed (`pip install 'pywry[notebook]'`), the chat automatically renders as a native notebook widget — no HTTP server, no IFrame. The `PyWryChatWidget` bundles the chat JavaScript in its ESM module and loads artifact libraries (Plotly, AG Grid, TradingView) through traitlet synchronization when needed.

This happens automatically. The same code works in native windows, notebooks, and browser deployments with no changes.

## RBAC

When PyWry's authentication system is enabled (deploy mode), all chat operations are gated by role-based access control:

- **Viewers** can read but cannot send messages
- **Editors** can send messages and interact normally
- **Admins** can additionally approve file write operations from ACP agents

See [Chat Artifacts And Providers](../../integrations/chat/index.md) for the full RBAC permission mapping.

## Examples

Working examples in the `examples/` directory:

- **`pywry_demo_chat.py`** — ChatManager with slash commands, settings, plan updates, thinking output, and streaming
- **`pywry_demo_chat_artifacts.py`** — all artifact types including TradingView charts
- **`pywry_demo_chat_magentic.py`** — magentic provider integration with tool calls

## Next Steps

- [Chat Artifacts And Providers](../../integrations/chat/index.md) — detailed artifact and provider documentation
- [Chat Providers API](../../integrations/chat/chat-providers.md) — API reference for all providers
