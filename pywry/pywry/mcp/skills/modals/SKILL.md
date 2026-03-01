# Modals - MANDATORY PATTERN

> **STOP. READ THIS ENTIRE FILE BEFORE CREATING MODALS.**

## Overview

Modals are reusable overlay dialogs that can contain any content - forms, confirmations, information panels, or custom HTML. They follow the same pattern as toolbars, passed to `.show-*` functions.

## The ONLY Correct Way to Create Modals

Copy this EXACTLY. Do not deviate.

```python
from pywry import Modal, show_plotly

fig = go.Figure(...)

widget = show_plotly(
    fig,
    modals=[
        Modal(
            component_id="settings-modal",
            title="Settings",
            items=["<p>Configure your preferences here.</p>"],
            size="medium",
        )
    ],
    toolbars=[{
        "position": "top",
        "items": [
            {"type": "button", "label": "Open Settings", "event": "modal:open:settings-modal"}
        ]
    }]
)
```

**THAT'S IT.** Button click opens the modal automatically.

---

## Modal Schema

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `component_id` | `str` | **YES** | - | Unique identifier for the modal |
| `title` | `str` | no | `""` | Modal header title |
| `items` | `list[str]` | no | `[]` | HTML content strings |
| `size` | `str` | no | `"medium"` | `"small"`, `"medium"`, `"large"`, `"fullscreen"` |
| `width` | `str` | no | `None` | Custom width (e.g., `"600px"`, `"80%"`) |
| `max_height` | `str` | no | `None` | Custom max-height (e.g., `"400px"`) |
| `overlay_opacity` | `float` | no | `0.5` | Backdrop opacity (0.0-1.0) |
| `close_on_escape` | `bool` | no | `True` | Close when Escape key pressed |
| `close_on_overlay_click` | `bool` | no | `True` | Close when clicking outside modal |
| `reset_on_close` | `bool` | no | `True` | Reset form inputs when closed |
| `on_close_event` | `str` | no | `None` | Event to emit when modal closes |
| `open_on_load` | `bool` | no | `False` | Open modal immediately on page load |
| `style` | `str` | no | `""` | Additional CSS for this modal |
| `script` | `str` | no | `""` | Additional JavaScript for this modal |
| `class_name` | `str` | no | `""` | Additional CSS classes |

---

## Size Presets

| Size | Width | Use Case |
|------|-------|----------|
| `small` | 320px | Confirmations, alerts |
| `medium` | 500px | Forms, settings (default) |
| `large` | 720px | Complex forms, tables |
| `fullscreen` | 95vw / 95vh | Data grids, large content |

---

## Modal Events

These are the ONLY events that work with modals:

### Opening and Closing

| Event Type | Description |
|------------|-------------|
| `modal:open:<component_id>` | Opens the modal |
| `modal:close:<component_id>` | Closes the modal |
| `modal:toggle:<component_id>` | Toggles open/closed state |

### Example: Button to Open Modal

```python
toolbars=[{
    "position": "top",
    "items": [
        {"type": "button", "label": "Settings", "event": "modal:open:settings-modal"}
    ]
}]
```

### Example: Button Inside Modal to Close

```python
Modal(
    component_id="confirm-modal",
    title="Confirm Action",
    items=[
        "<p>Are you sure?</p>",
        '<button onclick="window.pywry.modal.close(\'confirm-modal\')">Cancel</button>',
        '<button onclick="doAction()">Confirm</button>',
    ]
)
```

---

## Built-in Close Behaviors

1. **X Button**: Every modal has a close button in the top-right corner
2. **Escape Key**: Press Escape to close (unless `close_on_escape=False`)
3. **Overlay Click**: Click outside modal to close (unless `close_on_overlay_click=False`)

---

## reset_on_close Behavior

When `reset_on_close=True` (default):
- All `<input>`, `<textarea>`, `<select>` elements are reset to their initial values
- Form state is cleared when modal closes
- Next open shows fresh form

When `reset_on_close=False`:
- Form values persist between opens
- User can resume where they left off

---

## JavaScript API

Access modal functions via `window.pywry.modal`:

```javascript
// Open a modal
window.pywry.modal.open('my-modal');

// Close a modal  
window.pywry.modal.close('my-modal');

// Toggle a modal
window.pywry.modal.toggle('my-modal');

// Check if modal is open
const isOpen = window.pywry.modal.isOpen('my-modal');
```

---

## Complete Examples

### 1. Settings Modal with Form

```python
from pywry import Modal, show_plotly

widget = show_plotly(
    fig,
    modals=[
        Modal(
            component_id="settings",
            title="Chart Settings",
            items=[
                '<form id="settings-form">',
                '  <label>Title: <input type="text" name="title" value="My Chart"></label>',
                '  <label>Theme: <select name="theme">',
                '    <option value="dark">Dark</option>',
                '    <option value="light">Light</option>',
                '  </select></label>',
                '  <button type="button" onclick="applySettings()">Apply</button>',
                '</form>',
            ],
            size="medium",
            reset_on_close=False,  # Keep form values
        )
    ],
    toolbars=[{
        "position": "top",
        "items": [
            {"type": "button", "label": "⚙️ Settings", "event": "modal:open:settings"}
        ]
    }]
)
```

### 2. Confirmation Dialog

```python
Modal(
    component_id="delete-confirm",
    title="Delete Item",
    items=[
        '<p>Are you sure you want to delete this item?</p>',
        '<p style="color: var(--pywry-text-danger);">This action cannot be undone.</p>',
        '<div class="pywry-modal-footer">',
        '  <button onclick="window.pywry.modal.close(\'delete-confirm\')">Cancel</button>',
        '  <button onclick="confirmDelete()" class="danger">Delete</button>',
        '</div>',
    ],
    size="small",
    close_on_overlay_click=False,  # Force user to click a button
)
```

### 3. Modal with Custom Styling

```python
Modal(
    component_id="custom-modal",
    title="Styled Modal",
    items=["<p>Custom styled content</p>"],
    style="""
        #custom-modal .pywry-modal-container {
            border: 2px solid var(--pywry-accent);
            border-radius: 16px;
        }
        #custom-modal .pywry-modal-header {
            background: linear-gradient(90deg, var(--pywry-accent), var(--pywry-bg-secondary));
        }
    """,
)
```

### 4. Modal with Custom JavaScript

```python
Modal(
    component_id="data-modal",
    title="Data Preview",
    items=['<div id="data-preview"></div>'],
    script="""
        // Populate data when modal opens
        document.getElementById('data-modal').addEventListener('modal:opened', () => {
            fetch('/api/data')
                .then(r => r.json())
                .then(data => {
                    document.getElementById('data-preview').textContent = JSON.stringify(data, null, 2);
                });
        });
    """,
)
```

---

## CSS Selectors for Styling

Target modal elements with these selectors:

| Selector | Element |
|----------|---------|
| `#<component_id>` | The modal overlay |
| `#<component_id> .pywry-modal-container` | The modal box |
| `#<component_id> .pywry-modal-header` | Header with title and close button |
| `#<component_id> .pywry-modal-title` | Title text |
| `#<component_id> .pywry-modal-close` | X close button |
| `#<component_id> .pywry-modal-body` | Content area |
| `#<component_id> .pywry-modal-footer` | Footer area (if you add one) |

---

## Theme Awareness

Modals automatically inherit the current theme:

- `.pywry-theme-dark` → Dark background, light text
- `.pywry-theme-light` → Light background, dark text
- `.pywry-theme-system` → Follows OS preference

Use CSS variables for consistent theming:

```css
.pywry-modal-container {
    background: var(--pywry-bg-secondary);
    color: var(--pywry-text-primary);
    border: 1px solid var(--pywry-border);
}
```

---

## Common Mistakes

❌ Wrong: `event: "open-modal"` (missing modal: prefix and component_id)
❌ Wrong: `event: "modal:open"` (missing component_id)
❌ Wrong: Using `onclick` without `window.pywry.modal.` prefix

✅ Correct: `event: "modal:open:my-modal"` 
✅ Correct: `onclick="window.pywry.modal.close('my-modal')"`

---

## Dict Syntax (Alternative to Modal Class)

You can also use dict syntax if preferred:

```python
modals=[
    {
        "component_id": "info-modal",
        "title": "Information",
        "items": ["<p>Some info here</p>"],
        "size": "small",
    }
]
```

---

## Integration with Toolbars

Modals and toolbars work together seamlessly:

```python
show_dataframe(
    df,
    toolbars=[{
        "position": "top",
        "items": [
            {"type": "button", "label": "Export", "event": "grid:export-csv"},
            {"type": "button", "label": "Filter", "event": "modal:open:filter-modal"},
            {"type": "button", "label": "Help", "event": "modal:open:help-modal"},
        ]
    }],
    modals=[
        Modal(component_id="filter-modal", title="Filters", items=["..."]),
        Modal(component_id="help-modal", title="Help", items=["..."]),
    ]
)
```
