# Chat Events (chat:*)

The `chat:*` namespace handles all communication between the Python `ChatManager` and the chat frontend. Events flow in both directions: user messages travel JS → Python, while assistant responses, artifacts, and state updates travel Python → JS.

!!! note "Availability"
    Chat events are only active when content is rendered via `app.show_chat()` or the `ChatManager` component. They require the chat frontend assets.

## User Messages (JS → Python)

| Event | Payload | Description |
|-------|---------|-------------|
| `chat:user-message` | `{text, threadId, timestamp, attachments?}` | User sends a message. Triggers handler execution and response streaming. |
| `chat:stop-generation` | `{threadId, messageId}` | User clicks stop button to cancel in-progress generation. Sets cooperative cancel event. |
| `chat:slash-command` | `{command, args, threadId}` | User submits a `/command` from the input bar (e.g., `/clear`, `/export`). |
| `chat:input-response` | `{text, requestId, threadId}` | User responds to an `PermissionRequestUpdate` prompt mid-stream. |
| `chat:request-state` | `{}` | Frontend requests full state snapshot on initialization. |
| `chat:request-history` | `{threadId, limit}` | Frontend requests message history for a thread. |

**`chat:user-message` attachment structure:**

```python
{
    "type": "file" | "widget",
    "name": str,
    "path": str,             # Desktop only (filesystem path)
    "content": str,          # Browser/inline (file content)
    "widgetId": str,         # For widget attachments
    "componentId": str
}
```

## Thread Management (JS → Python)

| Event | Payload | Description |
|-------|---------|-------------|
| `chat:thread-create` | `{title}` | Create a new conversation thread. |
| `chat:thread-switch` | `{threadId}` | Switch active thread and replay its message history. |
| `chat:thread-delete` | `{threadId}` | Delete a thread and switch to the next available one. |
| `chat:thread-rename` | `{threadId, title}` | Rename a thread. |

## Settings & Todos (JS → Python)

| Event | Payload | Description |
|-------|---------|-------------|
| `chat:settings-change` | `{key, value}` | User changed a settings menu item (e.g., temperature slider, model select). |
| `chat:todo-clear` | `{}` | User dismissed the todo list above the input bar. |

## Assistant Responses (Python → JS)

| Event | Payload | Description |
|-------|---------|-------------|
| `chat:assistant-message` | `{messageId, text, threadId, role?, stopped?}` | Complete (non-streamed) assistant message. Also used to replay history on thread switch. |
| `chat:stream-chunk` | `{messageId, chunk, done, stopped?}` | Incremental text chunk during streaming. Flushed every 30 ms or 300 characters. |
| `chat:typing-indicator` | `{typing, threadId?}` | Show or hide the typing indicator before/after streaming. |
| `chat:generation-stopped` | `{messageId, partialContent}` | Generation was cancelled or stopped by the user or system. |

## Reasoning & Status (Python → JS)

| Event | Payload | Description |
|-------|---------|-------------|
| `chat:thinking-chunk` | `{messageId, text, threadId}` | Incremental reasoning/thinking text (rendered in a collapsible block). |
| `chat:thinking-done` | `{messageId, threadId}` | Thinking stream complete — collapses the thinking block and shows character count. |
| `chat:status-update` | `{messageId, text, threadId}` | Transient status message (e.g., "Searching..."). Shown inline, not stored in history. |

## Tool Use (Python → JS)

| Event | Payload | Description |
|-------|---------|-------------|
| `chat:tool-call` | `{messageId, toolId, name, arguments, threadId}` | Announces a tool invocation. Rendered as a collapsible `<details>` element. |
| `chat:tool-result` | `{messageId, toolId, result, isError, threadId}` | Result of a tool invocation. Appended inside the corresponding tool-call block. |

## Interactive Input (Python → JS)

| Event | Payload | Description |
|-------|---------|-------------|
| `chat:input-required` | `{messageId, threadId, requestId, prompt, placeholder, inputType, options?}` | Pause streaming to request user input mid-conversation. |

Handler pattern for permission requests:

```python
from pywry.chat.updates import PermissionRequestUpdate
from pywry.chat.session import PermissionOption

def my_handler(messages, ctx):
    yield PermissionRequestUpdate(
        toolCallId="call_1",
        title="Execute deployment script",
        options=[
            PermissionOption(id="allow_once", label="Allow"),
            PermissionOption(id="reject_once", label="Reject"),
        ],
    )
```

## Rich Content (Python → JS)

| Event | Payload | Description |
|-------|---------|-------------|
| `chat:artifact` | `{messageId, artifactType, title, threadId, ...}` | Rich content artifact (code, chart, table, image, etc.). |
| `chat:citation` | `{messageId, url, title, snippet, threadId}` | Source citation/reference link. |
| `chat:todo-update` | `{items}` | Push a todo list above the input bar. Not stored in history. |

**Artifact types and type-specific fields:**

| `artifactType` | Additional Fields |
|----------------|------------------|
| `code` | `content`, `language` |
| `markdown` | `content` |
| `html` | `content` |
| `table` | `rowData`, `columns`, `columnTypes`, `columnDefs?`, `gridOptions?`, `height` |
| `plotly` | `figure`, `height` |
| `image` | `url`, `alt` |
| `json` | `data` |

**Todo item structure:**

```python
{
    "id": int | str,
    "title": str,
    "status": "not-started" | "in-progress" | "completed"
}
```

## State & Configuration (Python → JS)

| Event | Payload | Description |
|-------|---------|-------------|
| `chat:state-response` | `{threads, activeThreadId, messages, settingsItems, contextSources}` | Full state snapshot in response to `chat:request-state`. |
| `chat:clear` | `{threadId?}` | Clear all messages from the chat display. |
| `chat:update-thread-list` | `{threads}` | Refresh the sidebar thread list after create/delete/rename. |
| `chat:switch-thread` | `{threadId}` | Tell the frontend to switch the active thread. |
| `chat:load-assets` | `{scripts, styles}` | Lazy-inject AG Grid or Plotly libraries on first artifact of that type. |
| `chat:register-command` | `{name, description}` | Register a slash command in the input autocomplete palette. |
| `chat:register-settings-item` | `{id, label, type, value, options?, min?, max?, step?}` | Register a settings menu item in the gear dropdown. |
| `chat:context-sources` | `{sources}` | List of dashboard components available as @-mentionable context sources. |
| `chat:update-settings` | `{key: value, ...}` | Push updated settings values to the frontend menu. |

**Settings item types:** `action`, `toggle`, `select`, `range`, `separator`
