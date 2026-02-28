# Forms and User Input

> Building interactive forms with validation and collecting user input.

## Available Input Components

| Type | Component | Use Case |
|------|-----------|----------|
| `text` | TextInput | Single-line text (names, emails) |
| `textarea` | TextareaInput | Multi-line text (comments, descriptions) |
| `number` | NumberInput | Numeric values with min/max/step |
| `date` | DateInput | Date selection |
| `search` | SearchInput | Search with debounce |
| `secret` | SecretInput | Passwords, API keys (value hidden) |
| `select` | Select | Single choice dropdown |
| `multiselect` | MultiSelect | Multiple choices |
| `radio` | RadioGroup | Visible single choice (small set) |
| `checkbox` | Checkbox | Boolean toggle |
| `toggle` | Toggle | On/off switch |
| `slider` | SliderInput | Single value in range |
| `range` | RangeInput | Two values (min/max range) |

## Basic Form Pattern

```python
create_widget(
    html='<div id="results">Fill out the form and click Submit</div>',
    toolbars=[{
        "position": "left",
        "items": [
            {"type": "text", "label": "Name", "event": "form:name", "placeholder": "Enter your name"},
            {"type": "text", "label": "Email", "event": "form:email", "placeholder": "email@example.com"},
            {"type": "number", "label": "Age", "event": "form:age", "min": 0, "max": 120, "value": 25},
            {"type": "select", "label": "Country", "event": "form:country",
             "options": [
                 {"label": "United States", "value": "us"},
                 {"label": "United Kingdom", "value": "uk"},
                 {"label": "Canada", "value": "ca"},
             ]},
            {"type": "button", "label": "Submit", "event": "form:submit", "variant": "primary"},
        ]
    }]
)
```

## Collecting Form Data

### From Events
```python
events = get_events(widget_id, clear=True)

# Collect latest values
form_data = {}
for e in events:
    if e["event_type"].startswith("form:"):
        field = e["event_type"].replace("form:", "")
        form_data[field] = e["data"].get("value")

# On submit
if "submit" in form_data:
    process_form(form_data)
```

### Tracking State
```python
# Keep running state across event polls
form_state = {}

while True:
    events = get_events(widget_id, clear=True)
    for e in events:
        if e["event_type"].startswith("form:"):
            field = e["event_type"].replace("form:", "")
            if field != "submit":
                form_state[field] = e["data"].get("value")
            else:
                # Submit with current state
                result = process_form(form_state)
                set_content(widget_id, component_id="results", text=result)
    time.sleep(0.1)
```

## Validation Patterns

### Show Error Toast
```python
def validate_form(data):
    if not data.get("name"):
        show_toast(widget_id, message="Name is required", type="error")
        return False
    if not data.get("email") or "@" not in data["email"]:
        show_toast(widget_id, message="Valid email is required", type="error")
        return False
    return True
```

### Highlight Invalid Fields
```python
def highlight_error(component_id):
    set_style(widget_id, component_id=component_id, styles={
        "borderColor": "var(--error-color)",
        "boxShadow": "0 0 0 2px rgba(239, 68, 68, 0.2)",
    })

def clear_error(component_id):
    set_style(widget_id, component_id=component_id, styles={
        "borderColor": "var(--border-color)",
        "boxShadow": "none",
    })
```

### Show Inline Errors
```python
# Create form with error placeholders
html = """
<div class="form-group">
    <div id="name-error" class="error-message" style="display: none; color: var(--error-color);"></div>
</div>
"""

# Show error
set_content(widget_id, component_id="name-error", text="Name is required")
set_style(widget_id, component_id="name-error", styles={"display": "block"})

# Clear error
set_style(widget_id, component_id="name-error", styles={"display": "none"})
```

## Input Component Details

### Text Input
```python
{"type": "text",
 "label": "Username",
 "event": "username",
 "placeholder": "Enter username",
 "value": "",  # Default value
}
# Event data: {"value": "entered_text"}
```

### Number Input
```python
{"type": "number",
 "label": "Quantity",
 "event": "quantity",
 "min": 1,
 "max": 100,
 "step": 1,
 "value": 10,
}
# Event data: {"value": 10}  # Always a number
```

### Select
```python
{"type": "select",
 "label": "Category",
 "event": "category",
 "options": [
     {"label": "Option A", "value": "a"},
     {"label": "Option B", "value": "b"},
     {"label": "Option C", "value": "c"},
 ],
 "value": "a",  # Default selection
}
# Event data: {"value": "a", "label": "Option A"}
```

### MultiSelect
```python
{"type": "multiselect",
 "label": "Tags",
 "event": "tags",
 "options": [
     {"label": "Important", "value": "important"},
     {"label": "Urgent", "value": "urgent"},
     {"label": "Review", "value": "review"},
 ],
 "value": ["important"],  # Default selections (array)
}
# Event data: {"value": ["important", "urgent"]}
```

### Radio Group
```python
{"type": "radio",
 "label": "Priority",
 "event": "priority",
 "options": [
     {"label": "Low", "value": "low"},
     {"label": "Medium", "value": "medium"},
     {"label": "High", "value": "high"},
 ],
 "value": "medium",
}
# Event data: {"value": "medium"}
```

### Toggle / Checkbox
```python
{"type": "toggle",  # or "checkbox"
 "label": "Enable notifications",
 "event": "notifications",
 "value": True,  # Default state
}
# Event data: {"value": true}  # Boolean
```

### Slider
```python
{"type": "slider",
 "label": "Volume",
 "event": "volume",
 "min": 0,
 "max": 100,
 "step": 5,
 "value": 50,
}
# Event data: {"value": 50}
```

### Range (Two Values)
```python
{"type": "range",
 "label": "Price Range",
 "event": "price_range",
 "min": 0,
 "max": 1000,
 "step": 10,
 "value": [100, 500],  # [min_value, max_value]
}
# Event data: {"value": [100, 500]}
```

### Date
```python
{"type": "date",
 "label": "Start Date",
 "event": "start_date",
 "value": "2024-01-01",  # ISO format
}
# Event data: {"value": "2024-01-15"}
```

### Search (with debounce)
```python
{"type": "search",
 "label": "Search",
 "event": "search",
 "placeholder": "Type to search...",
 "debounce": 300,  # ms delay before firing event
}
# Event data: {"value": "search query"}
```

## Secret Input (Passwords / API Keys)

```python
{"type": "secret",
 "label": "API Key",
 "event": "api_key",
 "placeholder": "Enter your API key",
}

# Events emitted:
# "api_key" - Value changed (value in event data, but NEVER rendered in HTML)
# "api_key:reveal" - User clicked reveal button
# "api_key:copy" - User clicked copy button
```

### Handling Secret Events
```python
events = get_events(widget_id, clear=True)
for e in events:
    if e["event_type"] == "api_key":
        # Store securely - never log or display
        api_key = e["data"]["value"]
        save_api_key_securely(api_key)
    elif e["event_type"] == "api_key:reveal":
        # User wants to see the key - show toast or handle appropriately
        show_toast(widget_id, message="Key revealed in input", type="info")
    elif e["event_type"] == "api_key:copy":
        show_toast(widget_id, message="API key copied to clipboard", type="success")
```

## Complete Form Example

```python
from pywry import PyWry
from pywry.toolbar import Div, Button, Toolbar

app = PyWry()

content = Div(
    content="""
        <div style="padding: 20px;">
            <h2>Registration Form</h2>
            <div id="message" style="margin: 16px 0; padding: 12px; display: none;"></div>
        </div>
    """,
    component_id="form-container",
)

widget = app.show(
    html=content.build_html(),
    height=500,
    toolbars=[
        Toolbar(
            position="left",
            items=[
                {"type": "text", "label": "Full Name", "event": "form:name"},
                {"type": "text", "label": "Email", "event": "form:email"},
                {"type": "secret", "label": "Password", "event": "form:password"},
                {"type": "select", "label": "Role", "event": "form:role", "options": [
                    {"label": "User", "value": "user"},
                    {"label": "Admin", "value": "admin"},
                ]},
                {"type": "toggle", "label": "Accept Terms", "event": "form:terms"},
                {"type": "button", "label": "Register", "event": "form:submit", "variant": "primary"},
            ]
        )
    ]
)

# Handle form
form_state = {}
while True:
    events = widget.get_events(clear=True)
    for e in events:
        if e["event_type"].startswith("form:"):
            field = e["event_type"].replace("form:", "")
            if field != "submit":
                form_state[field] = e["data"].get("value")
            else:
                # Validate
                if not form_state.get("name"):
                    widget.show_toast("Name is required", type="error")
                elif not form_state.get("terms"):
                    widget.show_toast("Please accept terms", type="error")
                else:
                    # Success
                    widget.set_content(
                        component_id="message",
                        html=f"<p style='color: var(--success-color);'>Welcome, {form_state['name']}!</p>"
                    )
                    widget.set_style(component_id="message", styles={"display": "block"})
    time.sleep(0.1)
```
