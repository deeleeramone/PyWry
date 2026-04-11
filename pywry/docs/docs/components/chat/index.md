# Chat

PyWry includes a first-class chat UI that can run in native windows, notebook widgets, and browser-rendered deployments. The chat stack has two layers:

- `build_chat_html()` for low-level rendering of the chat shell.
- `ChatManager` for the production path: thread management, event wiring, streaming, stop-generation, slash commands, settings, and input requests.

If you are building an interactive assistant, use `ChatManager` unless you explicitly need to assemble the raw chat HTML yourself.

For the complete API surface, see the [Chat API](../../reference/chat.md), [ChatManager API](../../reference/chat-manager.md), and [Chat Providers API](../../integrations/chat/chat-providers.md).

## Minimal ChatManager Setup

```python
from pywry import Div, HtmlContent, PyWry, Toolbar
from pywry.chat_manager import ChatManager


def handler(messages, ctx):
    user_text = messages[-1]["text"]
    return f"You said: {user_text}"


app = PyWry(title="Chat Demo")
chat = ChatManager(
    handler=handler,
    welcome_message="Welcome to **PyWry Chat**.",
    system_prompt="You are a concise assistant.",
)

widget = app.show(
    HtmlContent(html="<h1>Assistant</h1><p>Ask something in the chat panel.</p>"),
    toolbars=[chat.toolbar(position="right")],
    callbacks=chat.callbacks(),
)

chat.bind(widget)
app.block()
```

`ChatManager` expects three pieces to be connected together:

1. `chat.toolbar()` to render the chat panel.
2. `chat.callbacks()` to wire the `chat:*` frontend events.
3. `chat.bind(widget)` after `app.show(...)` so the manager can emit updates back to the active widget.

## Handler Shapes

The handler passed to `ChatManager` is the core integration point. PyWry supports all of these forms:

- Sync function returning `str`
- Async function returning `str`
- Sync generator yielding `str` chunks
- Async generator yielding `str` chunks
- Sync or async generator yielding rich `ChatResponse` objects

### One-shot response

```python
def handler(messages, ctx):
    question = messages[-1]["text"]
    return f"Answering: {question}"
```

### Streaming response

```python
import time


def handler(messages, ctx):
    text = "Streaming responses work token by token in the chat UI."
    for word in text.split():
        if ctx.cancel_event.is_set():
            return
        yield word + " "
        time.sleep(0.03)
```

### Rich response objects

```python
from pywry import StatusResponse, ThinkingResponse, TodoItem, TodoUpdateResponse


def handler(messages, ctx):
    yield StatusResponse(text="Searching project files...")
    yield TodoUpdateResponse(
        items=[
            TodoItem(id=1, title="Analyze request", status="completed"),
            TodoItem(id=2, title="Generate answer", status="in-progress"),
        ]
    )
    yield ThinkingResponse(text="Comparing the available implementation paths...\n")
    yield "Here is the final answer."
```

## Conversation State

`ChatManager` handles thread state internally:

- Creates a default thread on startup
- Tracks active thread selection
- Supports thread create, switch, rename, and delete events
- Keeps message history per thread
- Exposes `active_thread_id`, `threads`, and `settings` as read-only views

Use `send_message()` when you need to push a programmatic assistant message into the active thread or a specific thread.

```python
chat.send_message("Background task completed.")
```

## Slash Commands

Slash commands appear in the command palette inside the chat input. Register custom commands with `SlashCommandDef` and optionally handle them through `on_slash_command`.

```python
from pywry import SlashCommandDef


def on_slash(command, args, thread_id):
    if command == "/time":
        chat.send_message("Current time: **12:34:56**", thread_id)


chat = ChatManager(
    handler=handler,
    slash_commands=[
        SlashCommandDef(name="/time", description="Show the current time"),
        SlashCommandDef(name="/clearcache", description="Clear cached results"),
    ],
    on_slash_command=on_slash,
)
```

PyWry also ships built-in commands at the lower-level `ChatConfig` layer, including `/clear`, `/export`, `/model`, and `/system`.

## Settings Menu

Use `SettingsItem` to populate the gear-menu dropdown. These values are stored by the manager and emitted back through `on_settings_change`.

```python
from pywry import SettingsItem


def on_settings_change(key, value):
    print(f"{key} changed to {value}")


chat = ChatManager(
    handler=handler,
    settings=[
        SettingsItem(
            id="model",
            label="Model",
            type="select",
            value="gpt-4o-mini",
            options=["gpt-4o-mini", "gpt-4.1", "claude-sonnet-4"],
        ),
        SettingsItem(
            id="temperature",
            label="Temperature",
            type="range",
            value=0.7,
            min=0,
            max=2,
            step=0.1,
        ),
    ],
    on_settings_change=on_settings_change,
)
```

## Cooperative Cancellation

The stop button triggers `chat:stop-generation`, and `ChatManager` exposes that to your handler through `ctx.cancel_event`.

Your handler should check `ctx.cancel_event.is_set()` while streaming so long generations terminate quickly and cleanly.

```python
def handler(messages, ctx):
    for chunk in very_long_generation():
        if ctx.cancel_event.is_set():
            return
        yield chunk
```

At the lower level, `GenerationHandle` tracks the active task and provides cancellation state for provider-backed streaming flows.

## Input Requests

Chat flows can pause and ask the user for confirmation or structured input by yielding `InputRequiredResponse`. The handler can then continue by calling `ctx.wait_for_input()`.

```python
from pywry import InputRequiredResponse


def handler(messages, ctx):
    yield "I need confirmation before I continue."
    yield InputRequiredResponse(
        prompt="Proceed with deployment?",
        input_type="buttons",
    )
    answer = ctx.wait_for_input()
    if not answer or answer.lower().startswith("n"):
        yield "Deployment cancelled."
        return
    yield "Deployment approved. Continuing now."
```

Supported flows include:

- Button confirmation dialogs
- Radio/select choices
- Free-text or filename input

See the chat demo example for a complete input-request flow.

## Context Mentions And File Attachments

`ChatManager` can expose extra context sources to the user:

- `enable_context=True` enables `@` mentions for registered live widget sources.
- `register_context_source(component_id, name)` makes a widget target selectable.
- `enable_file_attach=True` enables file uploads.
- `file_accept_types` is required when file attachment is enabled.
- `context_allowed_roots` restricts attachment reads to specific directories.

```python
chat = ChatManager(
    handler=handler,
    enable_context=True,
    enable_file_attach=True,
    file_accept_types=[".csv", ".json", ".xlsx"],
    context_allowed_roots=["./data", "./reports"],
)

chat.register_context_source("sales-grid", "Sales Data")
```

When attachments are present, `ChatManager.CONTEXT_TOOL` can be passed into an LLM tool schema so the model can request the full contents of an attached item on demand.

## Eager Versus Lazy Assets

The chat UI can render AG Grid and Plotly artifacts inline. You can choose between:

- Eager asset loading with `include_plotly=True` and `include_aggrid=True`
- Lazy asset injection when the first matching artifact is emitted

Eager loading is simpler for predictable assistant workflows. Lazy loading reduces initial page weight.

## Lower-Level HTML Assembly

If you need to embed the raw chat shell yourself, use `build_chat_html()`.

```python
from pywry import build_chat_html

html = build_chat_html(
    show_sidebar=True,
    show_settings=True,
    enable_context=True,
    enable_file_attach=True,
    file_accept_types=[".md", ".py", ".json"],
    container_id="assistant-chat",
)
```

This returns only the chat HTML structure. You are then responsible for wiring the matching frontend and backend event flow.

## Examples

- `pywry/examples/pywry_demo_chat.py` demonstrates `ChatManager`, slash commands, settings, todo updates, thinking output, and `InputRequiredResponse`.
- `pywry/examples/pywry_demo_chat_artifacts.py` demonstrates all supported artifact types.

## Next Steps

- [Chat Artifacts And Providers](../../integrations/chat/index.md)
- [Chat API](../../reference/chat.md)
- [ChatManager API](../../reference/chat-manager.md)
- [Chat Providers API](../../integrations/chat/chat-providers.md)
