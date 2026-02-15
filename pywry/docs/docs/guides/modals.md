# Modals

Modals are popup dialogs that overlay the content area. They reuse the same component system as toolbars — any `ToolbarItem` works inside a modal — but add overlay behavior, sizing, keyboard handling, and open/close control.

## Creating a Modal

A `Modal` takes a list of toolbar items and is passed alongside your content:

```python
from pywry import PyWry, Modal, Button, TextInput, Select, Option

app = PyWry()

modal = Modal(
    component_id="settings-modal",
    title="Settings",
    items=[
        Select(
            label="Language",
            event="settings:language",
            options=[Option(label="Python"), Option(label="JavaScript"), Option(label="Rust")],
            selected="Python",
        ),
        TextInput(label="API Key", event="settings:api-key", placeholder="Enter key..."),
        Button(label="Save", event="settings:save", variant="primary"),
        Button(label="Cancel", event="settings:cancel", variant="ghost"),
    ],
)

app.show(
    "<h1>Dashboard</h1>",
    modals=[modal],
    callbacks={
        "settings:save": on_save,
        "settings:cancel": lambda d, e, l: app.emit("modal:close:settings-modal", {}, l),
    },
)
```

The modal is hidden by default. It renders as an overlay div with a backdrop, and its HTML is injected after the main content.

## Modal Properties

| Property | Type | Default | Description |
|:---|:---|:---|:---|
| `component_id` | `str` | auto | Unique identifier — used in open/close commands |
| `title` | `str` | `"Modal"` | Header text |
| `items` | `list[ToolbarItem]` | `[]` | Components inside the modal body |
| `size` | `"sm" | "md" | "lg" | "xl" | "full"` | `"md"` | Preset width |
| `width` | `str | None` | `None` | Custom width (overrides `size`) |
| `max_height` | `str` | `"80vh"` | Maximum height before scrolling |
| `overlay_opacity` | `float` | `0.5` | Backdrop darkness (0.0–1.0) |
| `close_on_escape` | `bool` | `True` | ESC key closes the modal |
| `close_on_overlay_click` | `bool` | `True` | Clicking outside closes the modal |
| `reset_on_close` | `bool` | `True` | Reset all inputs when closed |
| `on_close_event` | `str | None` | `None` | Event emitted when modal closes |
| `open_on_load` | `bool` | `False` | Open immediately on page load |
| `style` | `str` | `""` | Inline CSS on the modal container |
| `script` | `str | Path | None` | `None` | JavaScript to inject with the modal |
| `class_name` | `str` | `""` | Extra CSS class on the modal container |

### Size Presets

| Size | Width |
|:---|:---|
| `sm` | Small — compact dialogs, confirmations |
| `md` | Medium — forms, settings panels |
| `lg` | Large — data views, multi-column layouts |
| `xl` | Extra large — dashboards, wide content |
| `full` | Full viewport width |

## Opening and Closing

### From Python

```python
# Open
handle.emit("modal:open:settings-modal", {})

# Close
handle.emit("modal:close:settings-modal", {})

# Toggle
handle.emit("modal:toggle:settings-modal", {})
```

The event name format is `modal:{action}:{component_id}`. These events are intercepted client-side by the modal handler — they don't round-trip to the server.

### From JavaScript

```javascript
// Direct API
pywry.modal.open("settings-modal");
pywry.modal.close("settings-modal");
pywry.modal.toggle("settings-modal");

// Or via events (equivalent)
window.pywry.emit("modal:open:settings-modal", {});
```

### From a Toolbar Button

A common pattern is a toolbar button that opens a modal:

```python
toolbar = Toolbar(
    position="header",
    items=[Button(label="⚙ Settings", event="modal:open:settings-modal")],
)

modal = Modal(component_id="settings-modal", title="Settings", items=[...])

app.show(content, toolbars=[toolbar], modals=[modal])
```

Because the event matches `modal:open:*`, it's handled directly by the frontend — no Python callback needed.

## Close Events

When `on_close_event` is set, PyWry emits that event every time the modal closes (via ESC, overlay click, or programmatic close):

```python
modal = Modal(
    component_id="confirm-modal",
    title="Confirm Action",
    on_close_event="app:confirm-dismissed",
    items=[
        Button(label="Confirm", event="app:confirm-yes", variant="primary"),
        Button(label="Cancel", event="modal:close:confirm-modal", variant="ghost"),
    ],
)

def on_dismissed(data, event_type, label):
    print("User dismissed the confirmation dialog")

app.show(content, modals=[modal], callbacks={"app:confirm-dismissed": on_dismissed})
```

## Reset on Close

When `reset_on_close=True` (the default), all input components inside the modal are reset to their initial values when the modal is closed. This prevents stale form state when reopening.

Set `reset_on_close=False` if you want inputs to preserve their values between open/close cycles:

```python
modal = Modal(
    component_id="filter-modal",
    title="Filters",
    reset_on_close=False,  # Keep selections when reopened
    items=[
        Select(event="filter:status", options=["Active", "Archived", "All"], selected="Active"),
        Toggle(label="Include drafts", event="filter:drafts", value=False),
    ],
)
```

## Open on Load

Set `open_on_load=True` for modals that should appear immediately — useful for welcome screens, terms acceptance, or first-run configuration:

```python
modal = Modal(
    component_id="welcome",
    title="Welcome to the Dashboard",
    open_on_load=True,
    close_on_escape=False,
    close_on_overlay_click=False,
    items=[
        Button(label="Get Started", event="modal:close:welcome", variant="primary"),
    ],
)
```

## Custom Scripts

The `script` parameter lets you inject JavaScript that runs when the modal is loaded. This is useful for custom form validation, dynamic behavior, or third-party integrations:

```python
modal = Modal(
    component_id="my-modal",
    title="Custom Form",
    items=[
        TextInput(component_id="email", event="form:email", placeholder="Email"),
        Button(label="Submit", event="form:submit", variant="primary"),
    ],
    script="""
    document.getElementById('email').addEventListener('input', function(e) {
        const btn = document.querySelector('[data-event="form:submit"]');
        btn.disabled = !e.target.value.includes('@');
    });
    """,
)
```

## Multiple Modals

You can define multiple modals and open them independently:

```python
app.show(
    content,
    modals=[
        Modal(component_id="settings", title="Settings", items=[...]),
        Modal(component_id="export", title="Export Data", items=[...]),
        Modal(component_id="help", title="Help", size="lg", items=[...]),
    ],
    toolbars=[
        Toolbar(position="header", items=[
            Button(label="⚙", event="modal:open:settings", variant="icon"),
            Button(label="↓", event="modal:open:export", variant="icon"),
            Button(label="?", event="modal:open:help", variant="icon"),
        ]),
    ],
)
```

Only one modal can be visible at a time — opening a new one implicitly closes any currently open modal.

## Styling

Target modals with CSS using the component ID or the `.pywry-modal` class:

```css
/* All modals */
.pywry-modal {
    border-radius: 12px;
}

/* Specific modal */
#settings-modal .pywry-modal-body {
    padding: 24px;
}

/* Modal overlay */
.pywry-modal-overlay {
    backdrop-filter: blur(4px);
}
```

## Next Steps

- **[Toolbar System](toolbars.md)** — Components available inside modals
- **[Toasts & Alerts](toasts.md)** — Non-blocking notifications
- **[Theming & CSS](theming.md)** — Customize modal appearance
- **[Components](../components/index.md)** — Full component API reference
