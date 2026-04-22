# Chat Component - Reference Guide

> **Read this before creating chat widgets.**

## Overview

The chat component provides a full-featured conversational UI with:
- Message rendering with inline markdown
- Streaming responses with token-by-token display
- Stop-generation (cancel in-flight LLM responses)
- Thread management (create, switch, delete)
- Slash command palette (type `/` to see commands)
- Settings panel (model, temperature, system prompt)
- LLM provider adapters (OpenAI, Anthropic, custom callback)

## Quick Start

### Via MCP Tool

```json
{
  "name": "create_chat_widget",
  "arguments": {
    "title": "AI Assistant",
    "model": "gpt-4",
    "system_prompt": "You are a helpful assistant.",
    "streaming": true,
    "provider": "openai"
  }
}
```

### Via Python

```python
from pywry import App
from pywry.chat import ChatConfig, ChatWidgetConfig

app = App()
config = ChatWidgetConfig(
    title="AI Chat",
    height=600,
    chat=ChatConfig(
        system_prompt="You are helpful.",
        model="gpt-4",
        streaming=True,
        provider="openai",
    ),
)
# Widget creation handled by MCP or directly via app.show()
```

---

## MCP Tools

### create_chat_widget
Creates a chat widget. Returns `{widget_id, thread_id}`.

| Parameter       | Type    | Default  | Description                    |
|----------------|---------|----------|--------------------------------|
| title          | string  | "Chat"   | Window title                   |
| height         | integer | 600      | Window height                  |
| system_prompt  | string  | ""       | System prompt for LLM          |
| model          | string  | "gpt-4"  | Model name                     |
| temperature    | number  | 0.7      | Sampling temperature (0-2)     |
| max_tokens     | integer | 4096     | Max tokens per response        |
| streaming      | boolean | true     | Enable streaming               |
| persist        | boolean | false    | Persist threads in ChatStore   |
| provider       | string  | —        | "openai", "anthropic", "callback" |
| show_sidebar   | boolean | true     | Show thread sidebar            |
| slash_commands  | array   | —        | Custom slash commands           |

### chat_send_message
Send a user message. Returns `{message_id, thread_id, sent}`.

### chat_stop_generation
Stop an in-flight generation. Idempotent. Returns partial content.

### chat_manage_thread
Thread CRUD: create, switch, delete, rename, list.

### chat_register_command
Register a slash command at runtime.

### chat_get_history
Paginated conversation history with cursor (`before_id`).

### chat_update_settings
Update model, temperature, system prompt, etc.

### chat_set_typing
Show/hide the typing indicator.

---

## Event Contract

### Incoming Events (Python → Frontend)

| Event                      | Payload                                    |
|---------------------------|--------------------------------------------|
| `chat:assistant-message`   | `{messageId, text, threadId}`              |
| `chat:stream-chunk`        | `{chunk, messageId, threadId, done}`       |
| `chat:typing-indicator`    | `{typing, threadId}`                       |
| `chat:switch-thread`       | `{threadId}`                               |
| `chat:update-thread-list`  | `{threads: [{thread_id, title}]}`          |
| `chat:clear`               | `{}`                                       |
| `chat:register-command`    | `{name, description}`                      |
| `chat:update-settings`     | `{model, temperature, system_prompt}`      |
| `chat:state-response`      | `{messages, threads, settings, activeThreadId}` |
| `chat:generation-stopped`  | `{messageId, threadId, partialContent}`    |

### Outgoing Events (Frontend → Python)

| Event                    | Payload                                     |
|--------------------------|---------------------------------------------|
| `chat:user-message`      | `{text, threadId, timestamp}`               |
| `chat:slash-command`      | `{command, args, threadId}`                 |
| `chat:thread-create`      | `{title}`                                   |
| `chat:thread-switch`      | `{threadId}`                                |
| `chat:thread-delete`      | `{threadId}`                                |
| `chat:settings-change`    | `{key, value}`                              |
| `chat:request-history`    | `{threadId, limit}`                         |
| `chat:stop-generation`    | `{threadId, messageId}`                     |
| `chat:request-state`      | `{}`                                        |

---

## Stop-Generation Mechanics

1. User clicks Stop button → frontend immediately re-enables UI
2. `chat:stop-generation` sent to backend
3. Backend sets `cancel_event` on `GenerationHandle`
4. LLM provider checks `cancel_event.is_set()` between chunks
5. Provider raises `GenerationCancelledError` → partial content saved
6. Backend emits `chat:generation-stopped` with partial content
7. Frontend marks message as "(stopped)"

The UI **never waits** for backend confirmation — recovery is instant.

---

## Default Slash Commands

| Command    | Description                |
|-----------|----------------------------|
| `/clear`   | Clear conversation         |
| `/export`  | Export chat history         |
| `/model`   | Switch model               |
| `/system`  | Change system prompt        |

Register custom commands via `chat_register_command` tool or
`ChatConfig.slash_commands` list.

---

## LLM Providers

### OpenAI
```json
{"provider": "openai"}
```
Requires `openai` package and `OPENAI_API_KEY` environment variable.

### Anthropic
```json
{"provider": "anthropic"}
```
Requires `anthropic` package and `ANTHROPIC_API_KEY` environment variable.

### Custom Callback
```python
from pywry.chat.providers.callback import CallbackProvider

provider = CallbackProvider(
    prompt_fn=my_prompt,   # (session_id, content_blocks, cancel_event) → AsyncIterator[SessionUpdate]
)
```

---

## Safety Constants

| Constant                  | Value    | Purpose                          |
|--------------------------|----------|----------------------------------|
| MAX_RENDERED_MESSAGES    | 200      | DOM cap for performance          |
| MAX_CONTENT_LENGTH       | 100,000  | Per-message content limit        |
| MAX_MESSAGES_PER_THREAD  | 1,000    | Eviction threshold               |
| STREAM_TIMEOUT_SECONDS   | 30       | Max silence before timeout       |
| SEND_COOLDOWN_MS         | 1,000    | Input rate limit                 |
| GENERATION_HANDLE_TTL    | 300      | Auto-expire stale handles        |
