# Interactive Buttons - MANDATORY PATTERN

> **STOP. READ THIS ENTIRE FILE BEFORE CREATING ANY WIDGET.**

## The ONLY Correct Way to Create Buttons

Copy this EXACTLY. Do not deviate.

```json
{
  "html": "<div id=\"counter\" style=\"font-size:48px;text-align:center;padding:50px\">0</div>",
  "title": "Counter",
  "height": 400,
  "toolbars": [{
    "position": "top",
    "items": [
      {"type": "button", "label": "+1", "event": "counter:increment", "variant": "primary"},
      {"type": "button", "label": "-1", "event": "counter:decrement", "variant": "neutral"},
      {"type": "button", "label": "Reset", "event": "counter:reset", "variant": "danger"}
    ]
  }]
}
```

**THAT'S IT.** No callbacks needed. Buttons work automatically.

## How It Works

The event name `counter:increment` is parsed as:
- `counter` → the HTML element id to update
- `increment` → the action to perform

When you click "+1", PyWry:
1. Finds the element with `id="counter"`
2. Parses its current text as a number
3. Adds 1 to it
4. Updates the display

## Supported Actions

| Event Pattern | What It Does |
|--------------|--------------|
| `myId:increment` | Adds 1 to element's text |
| `myId:decrement` | Subtracts 1 from element's text |
| `myId:reset` | Sets element's text to 0 |
| `myId:toggle` | Toggles between true/false |

## More Examples

### Status Toggle

```python
create_widget(
    html='<div id="status" style="font-size:24px;text-align:center">false</div>',
    toolbars=[{
        "position": "top",
        "items": [
            {"type": "button", "label": "Toggle Status", "event": "status:toggle"}
        ]
    }]
)
```

### Score Tracker

```python
create_widget(
    html='''
        <div style="display:flex;justify-content:space-around;padding:20px">
            <div>Home: <span id="home" style="font-size:48px">0</span></div>
            <div>Away: <span id="away" style="font-size:48px">0</span></div>
        </div>
    ''',
    toolbars=[{
        "position": "top",
        "items": [
            {"type": "button", "label": "Home +1", "event": "home:increment"},
            {"type": "button", "label": "Away +1", "event": "away:increment"},
            {"type": "button", "label": "Reset All", "event": "home:reset"},
        ]
    }]
)
```

## Rules

1. **Element id must exist** - The HTML must have an element with the matching id
2. **Event format is `id:action`** - Colon separates the target from the action
3. **Actions are lowercase** - `increment`, `decrement`, `reset`, `toggle`
4. **Initial value matters** - For increment/decrement, start with a number like "0"

## Common Mistakes

❌ Wrong: `event: "increment"` (no target id)
❌ Wrong: `event: "counter-increment"` (hyphen instead of colon)
❌ Wrong: HTML has `id="Counter"` but event is `counter:increment` (case mismatch)

✅ Correct: `event: "counter:increment"` with `id="counter"` in HTML
