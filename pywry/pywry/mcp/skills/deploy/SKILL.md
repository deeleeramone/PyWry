# Production Deploy Mode

> **CRITICAL**: This mode is for **production servers** serving multiple concurrent users.
> Widgets are stateless. State lives externally. Scale horizontally.

## What Deploy Mode IS

You're creating widgets for a **production SSE server** with:
- Multiple concurrent users/sessions
- Stateless widget creation
- Horizontal scaling support
- Persistent widget URLs

## Architecture

```
                         ┌─────────────────┐
                         │  Load Balancer  │
                         └────────┬────────┘
                                  │
         ┌────────────────────────┼────────────────────────┐
         │                        │                        │
         ▼                        ▼                        ▼
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│  PyWry Server   │      │  PyWry Server   │      │  PyWry Server   │
│    (SSE #1)     │      │    (SSE #2)     │      │    (SSE #3)     │
└─────────────────┘      └─────────────────┘      └─────────────────┘
         │                        │                        │
         └────────────────────────┼────────────────────────┘
                                  │
                                  ▼
                      ┌───────────────────────┐
                      │   Shared State Store  │
                      │   (Redis / Database)  │
                      └───────────────────────┘
```

## Key Principles

### Widgets Are Stateless
- Widget instances don't persist server state
- Store state externally (Redis, database, etc.)
- Any server can handle any widget update

### Session Management
- Each user gets a unique widget_id
- Map widget_id to user session externally
- Implement timeouts and cleanup

### Horizontal Scaling
- Servers behind load balancer
- SSE connections are per-server (sticky sessions may help)
- Widget operations are idempotent

## Best Practices

### 1. Widget IDs - Use Meaningful IDs
```python
# Include user/session info in widget_id
widget_id = f"user_{user_id}_dashboard"

# Or use session-scoped IDs
widget_id = f"session_{session_id}_chart"

# This makes debugging and monitoring easier
```

### 2. State - Store Externally
```python
# BAD: State in widget
widget_state = {"threshold": 0.5}  # Lost on server restart

# GOOD: State in external store
redis.set(f"widget:{widget_id}:state", json.dumps({"threshold": 0.5}))

# On event:
state = json.loads(redis.get(f"widget:{widget_id}:state"))
```

### 3. Cleanup - Destroy Widgets
```python
# Implement session timeouts
def cleanup_expired_sessions():
    for widget_id in list_widgets():
        if is_expired(widget_id):
            destroy_widget(widget_id)
            redis.delete(f"widget:{widget_id}:*")

# Call on disconnect
events = get_events(widget_id, clear=True)
for e in events:
    if e["event_type"] == "pywry:disconnect":
        destroy_widget(widget_id)
```

### 4. Theme - User Choice
```python
# Don't force dark/light - let users choose
# Store preference in user settings
user_prefs = get_user_preferences(user_id)
update_theme(widget_id, theme=user_prefs.get("theme", "system"))
```

## Recommended Components

| Component | Why |
|-----------|-----|
| `Div` | Server-rendered content |
| `Button` | Explicit user actions (trackable) |
| `RadioGroup`/`TabGroup` | View switching (state trackable) |
| `AG Grid` | Large datasets (`show_dataframe`) |

## Multi-User Considerations

### No Cross-Talk
```python
# Events are per-widget
# User A's events don't appear in User B's widget
events_a = get_events(widget_id_a, clear=True)  # Only user A's events
events_b = get_events(widget_id_b, clear=True)  # Only user B's events
```

### Session Monitoring
```python
# Monitor active sessions
active_widgets = list_widgets()
print(f"Active sessions: {len(active_widgets)}")

# Check specific widget
if widget_id in active_widgets:
    # Widget still active
    pass
```

### Broadcast Updates
```python
# Send updates to multiple widgets
for widget_id in get_widgets_by_room("market-updates"):
    send_event(widget_id, event_type="price:update", data=new_prices)
```

## Scaling Patterns

### Sticky Sessions (Simple)
```nginx
# nginx.conf
upstream pywry_servers {
    ip_hash;  # Same client → same server
    server pywry1:8001;
    server pywry2:8001;
    server pywry3:8001;
}
```

### Redis Pub/Sub (Advanced)
```python
# Publish updates to all servers
redis.publish("widget:updates", json.dumps({
    "widget_id": widget_id,
    "event_type": "data:refresh",
    "data": new_data
}))

# Servers subscribe and forward
def handle_redis_message(message):
    data = json.loads(message)
    send_event(data["widget_id"], data["event_type"], data["data"])
```

## Code Example

```python
import asyncio
import json
from pywry import PyWry
from pywry.toolbar import Div, Button, Toolbar
from redis import Redis

app = PyWry()
redis = Redis()

def create_user_dashboard(user_id: str, session_id: str):
    """Create a dashboard widget for a user session."""
    widget_id = f"user_{user_id}_{session_id}"

    # Load user state from Redis
    state = json.loads(redis.get(f"state:{widget_id}") or "{}")

    content = Div(
        content=f"""
            <div id="dashboard">
                <h1>Welcome, User {user_id}</h1>
                <div id="data-area">Loading...</div>
            </div>
        """,
        component_id="main",
    )

    widget = app.show(
        html=content.build_html(),
        height=600,
        toolbars=[
            Toolbar(
                position="top",
                items=[
                    Button(label="Refresh", event="refresh", variant="primary"),
                    Button(label="Export", event="export"),
                    Button(label="Logout", event="logout", variant="danger"),
                ]
            )
        ]
    )

    # Track session
    redis.setex(f"session:{widget_id}", 3600, user_id)  # 1 hour TTL

    return widget

async def handle_session(widget_id: str):
    """Handle events for a user session."""
    while True:
        events = get_events(widget_id, clear=True)

        for e in events:
            if e["event_type"] == "pywry:disconnect":
                # Cleanup
                destroy_widget(widget_id)
                redis.delete(f"session:{widget_id}")
                redis.delete(f"state:{widget_id}")
                return

            elif e["event_type"] == "refresh":
                data = fetch_user_data(widget_id)
                set_content(widget_id, component_id="data-area", html=render_data(data))

            elif e["event_type"] == "logout":
                destroy_widget(widget_id)
                return

        await asyncio.sleep(0.1)
```

## Production Checklist

- [ ] Widget IDs include user/session info
- [ ] State stored in external store (Redis/DB)
- [ ] Session timeouts implemented
- [ ] `destroy_widget` called on disconnect
- [ ] Error handling for all operations
- [ ] Logging for debugging
- [ ] Metrics for monitoring (active sessions, events/sec)
- [ ] Load balancer configured
- [ ] Health check endpoint available
