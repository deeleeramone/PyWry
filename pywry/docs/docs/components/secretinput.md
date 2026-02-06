# SecretInput

A password-style input that masks characters with optional reveal toggle and copy button.

## Basic Usage

```python
from pywry import SecretInput

api_key = SecretInput(
    label="API Key",
    event="auth:api_key",
    placeholder="Enter API key",
)
```

## With Reveal Toggle

```python
SecretInput(
    label="Password",
    event="auth:password",
    reveal_toggle=True,  # Show/hide button
)
```

## With Copy Button

```python
SecretInput(
    label="Token",
    event="auth:token",
    value="sk-abc123xyz...",
    copy_button=True,  # Copy to clipboard button
)
```

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
            reveal_toggle=True,
        ),
        SecretInput(
            label="API Secret",
            event="config:api_secret",
            placeholder="Enter secret",
            reveal_toggle=True,
        ),
        Button(label="Save", event="config:save", variant="primary"),
    ],
)
```

### Token Display

For displaying generated tokens:

```python
import secrets

def on_generate_token(data, event_type, label):
    token = secrets.token_urlsafe(32)
    
    widget.emit("toolbar:set-value", {
        "componentId": "token-display",
        "value": token
    })

toolbar = Toolbar(
    position="top",
    items=[
        SecretInput(
            component_id="token-display",
            label="Token",
            event="token:value",
            copy_button=True,
            reveal_toggle=True,
        ),
        Button(label="Generate New", event="token:generate"),
    ],
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
            reveal_toggle=True,
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
