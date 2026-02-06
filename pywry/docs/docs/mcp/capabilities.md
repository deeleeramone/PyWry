# MCP Capabilities

The PyWry MCP server provides 25+ tools, skills/prompts, and resources for AI agent interaction.

## Tools

### get_skills

Get component reference and context-appropriate guidance.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `skill` | `string` | No | Specific skill to retrieve |

**Available Skills:**

- `component_reference` — Complete component documentation (MANDATORY before creating widgets)
- `interactive_buttons` — Button callback patterns
- `native` — Desktop window mode
- `jupyter` — Notebook widget mode
- `deploy` — Production server mode
- `data_visualization` — Charts and tables
- `forms_and_inputs` — User input collection

---

### create_widget

Create an interactive widget with HTML content and toolbar components.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `html` | `string` | Yes | HTML content |
| `title` | `string` | No | Window title |
| `height` | `integer` | No | Widget height |
| `include_plotly` | `boolean` | No | Include Plotly.js |
| `include_aggrid` | `boolean` | No | Include AG Grid |
| `toolbars` | `array` | No | Toolbar definitions |
| `callbacks` | `object` | No | Event callbacks |

**Example:**

```json
{
  "name": "create_widget",
  "arguments": {
    "html": "<div id=\"counter\" style=\"font-size:48px;text-align:center\">0</div>",
    "title": "Counter",
    "height": 400,
    "toolbars": [{
      "position": "top",
      "items": [
        {"type": "button", "label": "+1", "event": "counter:increment", "variant": "primary"},
        {"type": "button", "label": "-1", "event": "counter:decrement", "variant": "neutral"}
      ]
    }]
  }
}
```

---

### show_plotly

Create a Plotly chart widget.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `figure_json` | `string` | Yes | Plotly figure as JSON |
| `title` | `string` | No | Window title |
| `height` | `integer` | No | Widget height |

**Example:**

```json
{
  "name": "show_plotly",
  "arguments": {
    "figure_json": "{\"data\": [{\"x\": [1,2,3], \"y\": [4,5,6], \"type\": \"bar\"}], \"layout\": {}}",
    "title": "Bar Chart",
    "height": 500
  }
}
```

---

### show_dataframe

Create an AG Grid table widget from JSON data.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `data_json` | `string` | Yes | JSON array of objects |
| `title` | `string` | No | Window title |
| `height` | `integer` | No | Widget height |

**Example:**

```json
{
  "name": "show_dataframe",
  "arguments": {
    "data_json": "[{\"name\": \"Alice\", \"age\": 30}, {\"name\": \"Bob\", \"age\": 25}]",
    "title": "People",
    "height": 400
  }
}
```

---

### set_content

Update element text or HTML by component ID.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `widget_id` | `string` | Yes | Target widget |
| `component_id` | `string` | Yes | Element ID to update |
| `text` | `string` | No | New text content |
| `html` | `string` | No | New HTML content |

**Example:**

```json
{
  "name": "set_content",
  "arguments": {
    "widget_id": "abc123",
    "component_id": "counter",
    "text": "42"
  }
}
```

---

### set_style

Update element CSS styles by component ID.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `widget_id` | `string` | Yes | Target widget |
| `component_id` | `string` | Yes | Element ID to update |
| `styles` | `object` | Yes | CSS styles as {property: value} |

**Example:**

```json
{
  "name": "set_style",
  "arguments": {
    "widget_id": "abc123",
    "component_id": "status",
    "styles": {"color": "green", "fontWeight": "bold"}
  }
}
```

---

### show_toast

Display a toast notification.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `widget_id` | `string` | Yes | Target widget |
| `message` | `string` | Yes | Toast message |
| `type` | `string` | No | info, success, warning, error |
| `duration` | `integer` | No | Auto-dismiss ms |

---

### update_theme

Switch widget theme.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `widget_id` | `string` | Yes | Target widget |
| `theme` | `string` | Yes | dark, light, or system |

---

### send_event

Send a custom event to a widget.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `widget_id` | `string` | Yes | Target widget |
| `event_type` | `string` | Yes | Event type |
| `data` | `object` | Yes | Event payload |

**Example:**

```json
{
  "name": "send_event",
  "arguments": {
    "widget_id": "abc123",
    "event_type": "grid:update-data",
    "data": {
      "data": [{"name": "New", "value": 100}],
      "strategy": "append"
    }
  }
}
```

---

### update_plotly

Update a Plotly figure.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `widget_id` | `string` | Yes | Target widget |
| `figure_json` | `string` | Yes | New figure JSON |

---

### get_events

Retrieve queued events from a widget.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `widget_id` | `string` | Yes | Target widget |

---

### build_div

Build a Div component HTML string.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `content` | `string` | Yes | Text or HTML content |
| `component_id` | `string` | No | ID for later updates |
| `style` | `string` | No | Inline CSS styles |
| `class_name` | `string` | No | CSS class name |

---

### build_ticker_item

Build a ticker item for Marquee components.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `ticker` | `string` | Yes | Unique ID for updates |
| `text` | `string` | No | Display text |
| `html` | `string` | No | HTML content |
| `style` | `string` | No | Inline CSS styles |

---

## Resources

The MCP server exposes documentation and source code:

| Resource URI | Description |
|--------------|-------------|
| `pywry://docs/readme` | README documentation |
| `pywry://docs/components` | Component reference |
| `pywry://source/{module}` | Python source code |

---

## Prompts/Skills

Pre-defined prompts for context-aware guidance:

| Prompt | Description |
|--------|-------------|
| `component_reference` | Complete component documentation |
| `interactive_buttons` | Button callback patterns |
| `native` | Desktop window mode guide |
| `jupyter` | Notebook widget guide |
| `iframe` | Embedded widget guide |
| `deploy` | Production server guide |
| `data_visualization` | Charts and tables guide |
| `forms_and_inputs` | User input collection guide |

---

## Component Types

Available toolbar component types:

| Type | Event Payload | Description |
|------|--------------|-------------|
| `button` | `{componentId, ...data}` | Clickable button |
| `select` | `{value, componentId}` | Single-select dropdown |
| `multiselect` | `{values: [], componentId}` | Multi-select dropdown |
| `toggle` | `{value: boolean, componentId}` | Toggle switch |
| `checkbox` | `{value: boolean, componentId}` | Checkbox |
| `radio` | `{value, componentId}` | Radio group |
| `tabs` | `{value, componentId}` | Tab group |
| `text` | `{value, componentId}` | Text input |
| `textarea` | `{value, componentId}` | Multi-line text |
| `search` | `{value, componentId}` | Search input |
| `number` | `{value: number, componentId}` | Number input |
| `date` | `{value: "YYYY-MM-DD", componentId}` | Date picker |
| `slider` | `{value: number, componentId}` | Slider |
| `range` | `{start, end, componentId}` | Range slider |
| `secret` | `{value: base64, componentId}` | Password input |
| `div` | No events | HTML container |
| `marquee` | `{value, componentId}` if clickable | Scrolling text |

---

## System Events

Events for updating widgets from Python/AI:

| Event | Payload | Description |
|-------|---------|-------------|
| `grid:update-data` | `{data, strategy}` | Update grid rows |
| `grid:request-state` | `{context}` | Request grid state |
| `grid:restore-state` | `{state}` | Restore grid state |
| `plotly:update-figure` | `{data, layout}` | Update chart |
| `pywry:set-content` | `{id, text/html}` | Update element content |
| `pywry:set-style` | `{id, styles}` | Update element styles |
| `pywry:alert` | `{message, type}` | Show toast |
| `pywry:update-theme` | `{theme}` | Change theme |
| `toolbar:set-value` | `{componentId, value}` | Set component value |
| `toolbar:request-state` | `{}` | Request toolbar values |

## Next Steps

- **[Examples](examples.md)** — More usage examples
- **[Setup](setup.md)** — Installation guide
- **[API Reference](../reference/mcp.md)** — Programmatic usage
