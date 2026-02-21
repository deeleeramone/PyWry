# State, Redis & RBAC

PyWry includes a pluggable state management system with built-in authentication and role-based access control. In development you get a zero-config in-memory backend. In production you switch to Redis — no code changes required.

## Architecture at a Glance

The state layer is made of four pluggable stores and a callback registry:

| Store | Responsibility |
|:---|:---|
| **WidgetStore** | Widget HTML, tokens, and metadata |
| **EventBus** | Cross-worker event pub/sub |
| **ConnectionRouter** | WebSocket connection → worker mapping |
| **SessionStore** | User sessions, roles, and permissions |
| **CallbackRegistry** | Python callback dispatch (always local) |

Each store has two implementations — `Memory*` for single-process use and `Redis*` for multi-worker deployments. A factory layer auto-selects the right one based on configuration.

## State Backends

### In-Memory (default)

Works out of the box with no external dependencies. All state lives in Python dicts protected by `asyncio.Lock`. Suitable for local development, notebooks, and single-process servers.

```python
from pywry.state import get_widget_store, get_session_store

store = get_widget_store()       # MemoryWidgetStore
sessions = get_session_store()   # MemorySessionStore
```

### Redis (production)

Enables horizontal scaling across multiple workers/processes. Widgets registered by one worker are visible to all others. Events published on one worker are received by subscribers on every worker.

Activate it with environment variables — no code changes:

```bash
export PYWRY_DEPLOY__STATE_BACKEND=redis
export PYWRY_DEPLOY__REDIS_URL=redis://localhost:6379/0
```

Or in Python:

```python
import os
os.environ["PYWRY_DEPLOY__STATE_BACKEND"] = "redis"
os.environ["PYWRY_DEPLOY__REDIS_URL"] = "redis://redis:6379/0"
```

The same `get_widget_store()` call now returns a `RedisWidgetStore`.

## Configuration

All settings are controlled via `DeploySettings` and read from environment variables with the `PYWRY_DEPLOY__` prefix:

| Variable | Default | Description |
|:---|:---|:---|
| `STATE_BACKEND` | `memory` | `memory` or `redis` |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `REDIS_PREFIX` | `pywry` | Key namespace prefix |
| `REDIS_POOL_SIZE` | `10` | Connection pool size (1–100) |
| `WIDGET_TTL` | `86400` | Widget expiry in seconds (24h) |
| `CONNECTION_TTL` | `300` | WebSocket connection expiry (5min) |
| `SESSION_TTL` | `86400` | User session expiry (24h) |
| `WORKER_ID` | auto | Worker identifier (auto-generated if unset) |
| `AUTH_ENABLED` | `false` | Enable authentication middleware |
| `AUTH_SESSION_COOKIE` | `pywry_session` | Cookie name for session ID |
| `AUTH_HEADER` | `Authorization` | Header name for bearer tokens |
| `DEFAULT_ROLES` | `viewer` | Roles assigned to new sessions |
| `ADMIN_USERS` | (empty) | User IDs with automatic admin role |

!!! tip "Namespace isolation"
    Multiple PyWry applications can share one Redis instance by using different `REDIS_PREFIX` values.

## Redis Key Layout

All keys are namespaced under the configured prefix:

```
{prefix}:widget:{widget_id}               # Widget data (hash)
{prefix}:widgets:active                   # Active widget IDs (set)
{prefix}:channel:{channel}                # Pub/Sub channel
{prefix}:conn:{widget_id}                 # Connection routing (hash)
{prefix}:worker:{worker_id}:connections   # Worker's widget IDs (set)
{prefix}:session:{session_id}             # Session data (hash)
{prefix}:user:{user_id}:sessions          # User's session IDs (set)
{prefix}:role_permissions                 # Role → permissions (hash)
```

Every key type has an automatic TTL — widgets expire after 24 hours, connections after 5 minutes (refreshed by heartbeat), and sessions after 24 hours. All values are configurable.

## Widget Lifecycle in State

When you call `app.show()`, the state system tracks the widget through its full lifecycle:

1. **Register** — `ServerStateManager.register_widget(widget_id, html, token)` stores the rendered HTML and an HMAC-signed access token
2. **Connect** — When a browser opens the widget WebSocket, `register_connection(widget_id, websocket)` records which worker owns the connection
3. **Route callbacks** — JS events are dispatched to the local `CallbackRegistry` first. If the callback lives on a different worker, the `EventBus` routes the event to the owner
4. **Update** — `update_widget_html()` pushes new content without re-registering
5. **Cleanup** — `remove_widget()` deletes state and unregisters connections. TTL handles leaked widgets automatically

### Cross-Worker Event Routing

Python callbacks are functions — they can't be serialized to Redis. So PyWry keeps callbacks local and routes events across workers:

```
Browser → WebSocket → Worker A
                        ↓
                   Callback found locally? → Execute
                        ↓ (no)
                   EventBus.publish(event)
                        ↓
                   Worker B (owns the callback) → Execute
```

This is transparent to your code. You register callbacks normally and PyWry handles the routing.

## The ServerStateManager

`ServerStateManager` is the high-level API that the server uses internally. It provides a **dual-mode interface** — same methods work in local mode (in-memory dicts) and deploy mode (Redis stores):

```python
from pywry.state.server import get_server_state

state = get_server_state()  # Singleton

# Widget operations
await state.register_widget(widget_id, html, token)
html = await state.get_widget_html(widget_id)
await state.update_widget_html(widget_id, new_html)
widgets = await state.list_widgets()

# Connection tracking
await state.register_connection(widget_id, websocket)
await state.unregister_connection(widget_id)

# Callbacks
await state.register_callback(widget_id, "grid:cell-clicked", handler)
success, result = await state.invoke_callback(widget_id, "grid:cell-clicked", data)

# Cross-worker events
await state.broadcast_event(widget_id, "update", data)
await state.send_to_widget(widget_id, "refresh", data)

# Sessions
session_id = await state.create_session(user_id="user-123", roles=["editor"])
session = await state.get_session(session_id)
```

## Calling Async APIs from Sync Code

All state APIs are async. If you need to call them from synchronous code (e.g., a callback), use the `run_async` helper:

```python
from pywry.state.sync_helpers import run_async

# From sync code:
html = run_async(state.get_widget_html("my-widget"), timeout=5.0)
```

!!! warning
    Don't call `run_async` from inside the server's own async event loop — it will deadlock. It's designed for external sync callers.

---

## RBAC — Role-Based Access Control

PyWry's RBAC system controls who can access which widgets and what they can do. It's off by default and activates when you set `AUTH_ENABLED=true`.

### Roles and Permissions

Roles are flat (no inheritance). A user's effective permissions are the **union** of all their assigned roles:

| Role | Permissions |
|:---|:---|
| **admin** | `read`, `write`, `admin`, `delete`, `manage_users` |
| **editor** | `read`, `write` |
| **viewer** | `read` |
| **anonymous** | (none) |

You can define custom roles with the `SessionStore`:

```python
sessions = get_session_store()

# In-memory backend (sync):
sessions.set_role_permissions("analyst", {"read", "write", "export"})

# Redis backend (async):
await sessions.set_role_permissions("analyst", {"read", "write", "export"})
```

### Permission Types

Permissions are checked against a **resource type** and **resource ID**:

```python
# Does this session have "read" access to widget "chart-1"?
allowed = await sessions.check_permission(
    session_id=sid,
    resource_type="widget",
    resource_id="chart-1",
    permission="read",
)
```

Resource types: `widget`, `session`, `user`, `system`.

Permission checking follows two layers:

1. **Role-based** — Does any of the user's roles grant this permission?
2. **Resource-specific** — Does the session's metadata contain explicit per-resource grants?

Resource-specific permissions are stored in session metadata:

```python
session = await sessions.create_session(
    session_id="sess-abc",
    user_id="user-123",
    roles=["viewer"],  # Can read anything
    metadata={
        "permissions": {
            "widget:dashboard-1": ["read", "write"],  # Extra write on this widget
        }
    },
)
```

### Sessions

Sessions track authenticated users, their roles, and expiry:

```python
from pywry.state import get_session_store

sessions = get_session_store()

# Create
session = await sessions.create_session(
    session_id="sess-abc",
    user_id="user-123",
    roles=["editor"],
    ttl=3600,  # 1 hour
)

# Validate
is_valid = await sessions.validate_session("sess-abc")

# Refresh (extend TTL)
await sessions.refresh_session("sess-abc", extend_ttl=3600)

# List all sessions for a user
user_sessions = await sessions.list_user_sessions("user-123")
```

### Tokens

PyWry provides two token types, both using HMAC-SHA256 signatures:

**Session tokens** — Long-lived, identify a user:

```python
from pywry.state.auth import generate_session_token, validate_session_token

token = generate_session_token("user-123", secret="my-secret", expires_at=time.time() + 86400)
is_valid, user_id, error = validate_session_token(token, secret="my-secret")
```

**Widget tokens** — Short-lived (5 minutes), authorize access to a specific widget:

```python
from pywry.state.auth import generate_widget_token, validate_widget_token

token = generate_widget_token("widget-abc", secret="my-secret", ttl=300)
is_valid, _, error = validate_widget_token(token, "widget-abc", secret="my-secret")
```

### Authentication Middleware

`AuthMiddleware` is an ASGI middleware that extracts session information from every request and makes it available to handlers:

```python
from pywry.state.auth import AuthMiddleware, AuthConfig

config = AuthConfig(
    enabled=True,
    session_cookie="pywry_session",
    token_secret="my-secret-key",
    require_auth_for_widgets=True,
)

app = AuthMiddleware(app, session_store=sessions, config=config)
```

The middleware checks three sources in order:

1. **Cookie** — `pywry_session` (configurable)
2. **Authorization header** — `Bearer <token>`
3. **Query parameter** — `?session=<id>` (for WebSocket upgrades)

The resolved `UserSession` (or `None`) is placed on the ASGI scope:

```python
# In a request handler:
session = request.scope.get("session")
if session and has_permission(session, "write"):
    # Allow action
    ...
```

### Helper Functions

```python
from pywry.state.auth import has_permission, is_admin, check_widget_permission

# Check role-based permission (sync, from session object)
if has_permission(session, "write"):
    ...

# Check admin status
if is_admin(session):
    ...

# Check widget-specific permission (async, uses session store)
allowed = await check_widget_permission(session, "widget-1", "read", session_store)
```

## Putting It All Together

A typical deploy mode setup:

```bash
# Environment
export PYWRY_DEPLOY__STATE_BACKEND=redis
export PYWRY_DEPLOY__REDIS_URL=redis://redis:6379/0
export PYWRY_DEPLOY__AUTH_ENABLED=true
export PYWRY_DEPLOY__ADMIN_USERS=admin-001
export PYWRY_DEPLOY__DEFAULT_ROLES=viewer
```

```python
from pywry import PyWry
from pywry.state.server import get_server_state
from pywry.state.auth import has_permission

app = PyWry()
state = get_server_state()

# Create a session for an authenticated user
session_id = await state.create_session(
    user_id="user-456",
    roles=["editor"],
)

# Show a widget — state is persisted in Redis
app.show("<h1>Dashboard</h1>", title="Dashboard")

# In a callback, check permissions before mutating
async def on_delete(data):
    session = await state.get_session(data.get("session_id"))
    if session and has_permission(session, "delete"):
        # proceed with deletion
        ...
    else:
        app.emit("pywry:toast", {
            "message": "Permission denied",
            "type": "error",
        })
```

## Testing

For unit tests, use `fakeredis` to avoid needing a real Redis server:

```python
import fakeredis.aioredis

fake_redis = fakeredis.aioredis.FakeRedis()
store = RedisWidgetStore(redis_url="", redis_client=fake_redis)
```

All Redis store constructors accept a `redis_client` parameter for dependency injection.

## Next Steps

- **[OAuth2 Authentication](oauth2.md)** — Add Google, GitHub, Microsoft, or custom OIDC login flows
- **[Deploy Mode](deploy-mode.md)** — Running PyWry behind a production server
- **[Configuration](configuration.md)** — Full settings reference
- **[Event System](events.md)** — How events flow across rendering paths
- **[API Reference: State](../reference/state.md)** — Full state API docs
- **[API Reference: OAuth2](../reference/auth.md)** — Full OAuth2 API docs
