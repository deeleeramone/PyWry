# SecretInput

A secure input for sensitive values like API keys, passwords, and tokens. Values are never rendered in the DOM — they're masked with bullet characters and managed through a secure edit/reveal/copy workflow.

The input is **read-only by default**. Users click the edit (pencil) button to enter edit mode, and can optionally reveal the masked value or copy it to clipboard. Both `show_toggle` and `show_copy` are enabled by default.

<div class="component-preview">
  <span class="pywry-input-group pywry-input-inline">
    <span class="pywry-input-label">API Key:</span>
    <span class="pywry-secret-wrapper">
      <input type="password" class="pywry-input pywry-input-secret" value="sk-abc123xyz" readonly placeholder="Enter API key..." autocomplete="off" spellcheck="false">
      <span class="pywry-secret-actions">
        <button type="button" class="pywry-secret-btn pywry-secret-edit" data-tooltip="Edit value"><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/></svg></button>
        <button type="button" class="pywry-secret-btn pywry-secret-copy" data-tooltip="Copy to clipboard"><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg></button>
        <button type="button" class="pywry-secret-btn pywry-secret-toggle" data-tooltip="Show value"><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg></button>
      </span>
    </span>
  </span>
</div>

Action buttons (left-to-right): Edit (pencil) enters edit mode, Copy (clipboard) copies value, Reveal (eye) toggles mask on/off.

### Edit Mode

Clicking the edit button switches the masked input to a resizable textarea with confirm/cancel buttons. Confirm sends the value; cancel restores the mask.

<div class="component-preview">
  <span class="pywry-input-group pywry-input-inline">
    <span class="pywry-input-label">API Key:</span>
    <span class="pywry-secret-wrapper">
      <textarea class="pywry-input pywry-secret-textarea" placeholder="Enter API key..." style="width: 180px; min-width: 180px; height: 28px; min-height: 28px;">sk-abc123xyz-new-value</textarea>
      <span class="pywry-secret-actions pywry-secret-edit-actions" style="opacity: 1; pointer-events: auto;">
        <button type="button" class="pywry-secret-btn pywry-secret-confirm" data-tooltip="Confirm (Ctrl+Enter)"><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg></button>
        <button type="button" class="pywry-secret-btn pywry-secret-cancel" data-tooltip="Cancel (Escape)"><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>
      </span>
    </span>
  </span>
</div>

## Basic Usage

```python
from pywry import SecretInput

api_key = SecretInput(
    label="API Key",
    event="auth:api_key",
    placeholder="Enter API key",
)
```

Both `show_toggle` and `show_copy` default to `True`, so a basic SecretInput already has all three action buttons (edit, copy, reveal).

## Disabling Action Buttons

```python
# Only the edit button — no reveal or copy
SecretInput(
    label="Password",
    event="auth:password",
    show_toggle=False,  # Hide the reveal/eye button
    show_copy=False,    # Hide the copy button
)
```

## With Custom Handler

For secrets stored in an external vault or environment variable:

```python
import os
from pywry import SecretInput

def resolve_api_key(value, *, component_id, event, label=None, **metadata):
    """Custom handler for API key storage.

    Parameters:
        value: None to get the secret, str to set the secret
        component_id: unique component ID
        event: the event string
        label: optional label text
    """
    if value is None:
        # Get mode - return the secret
        return os.environ.get("MY_API_KEY", "")
    # Set mode - store the secret
    os.environ["MY_API_KEY"] = value
    return value

SecretInput(
    label="API Key",
    event="config:api_key",
    handler=resolve_api_key,
    value_exists=bool(os.environ.get("MY_API_KEY")),
)
```

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `label` | `str` | `""` | Display label |
| `event` | `str` | `"toolbar:input"` | Event name emitted on interaction |
| `value` | `SecretStr` | `""` | The secret value (never rendered in DOM) |
| `placeholder` | `str` | `""` | Placeholder text shown when empty |
| `show_toggle` | `bool` | `True` | Show the eye reveal/hide button |
| `show_copy` | `bool` | `True` | Show the copy-to-clipboard button |
| `debounce` | `int` | `300` | Debounce delay in ms for input events |
| `handler` | `callable` | `None` | Custom secret storage handler |
| `value_exists` | `bool` | `None` | Flag indicating a value exists externally |
| `component_id` | `str` | auto | Unique ID for state tracking |
| `description` | `str` | `""` | Tooltip/hover text |
| `disabled` | `bool` | `False` | Disable interaction |
| `style` | `str` | `""` | Optional inline CSS |

## Events

Emits the `event` name with payload on edit (when user exits the textarea):

```json
{"value": "<base64-encoded-string>", "encoded": true, "componentId": "secret-abc123"}
```

- `value` — the new secret value, base64-encoded
- `encoded` — always `true` (value must be decoded on the Python side)

Additional events:

- **`{event}:copy`** — emitted when the copy button is clicked: `{"componentId": "secret-abc123"}`  
  The backend responds on `{event}:copy-response` with the decrypted value.
- **`{event}:reveal`** — emitted when the show/hide toggle is clicked: `{"componentId": "secret-abc123"}`  
  The backend responds on `{event}:reveal-response` with the decrypted value.

## Common Patterns

### API Configuration

```python
config_toolbar = Toolbar(
    position="top",
    items=[
        SecretInput(
            label="API Key",
            event="config:api_key",
            placeholder="sk-...",
        ),
        SecretInput(
            label="API Secret",
            event="config:api_secret",
            placeholder="Enter secret",
        ),
        Button(label="Save", event="config:save", variant="primary"),
    ],
)
```

### Token Display

For displaying generated tokens:

```python
import secrets
from pywry import PyWry, Toolbar, SecretInput, Button

app = PyWry()

def on_generate_token(data, event_type, label):
    token = secrets.token_urlsafe(32)
    app.emit("toolbar:set-value", {
        "componentId": "token-display",
        "value": token
    }, label)
    app.emit("pywry:alert", {"message": "New token generated!", "type": "success"}, label)

app.show(
    "<h1>Token Generator</h1>",
    toolbars=[
        Toolbar(position="top", items=[
            SecretInput(
                component_id="token-display",
                label="Token",
                event="token:value",
            ),
            Button(label="Generate New", event="token:generate"),
        ])
    ],
    callbacks={"token:generate": on_generate_token},
)
```

### Login Form

```python
login_modal = Modal(
    component_id="login-modal",
    title="Login",
    items=[
        TextInput(label="Username", event="login:username"),
        SecretInput(
            label="Password",
            event="login:password",
            show_copy=False,  # Don't need copy for password entry
        ),
        Button(label="Login", event="login:submit", variant="primary"),
    ],
)
```

## Security Notes

!!! warning "Client-Side Only"
    SecretInput masks display only. For true security:
    
    - Never log secret values
    - Use HTTPS in production
    - Store secrets server-side when possible
    - Consider environment variables for sensitive configs

## API Reference

For complete parameter documentation, see the [SecretInput API Reference](../reference/components/secretinput.md).
