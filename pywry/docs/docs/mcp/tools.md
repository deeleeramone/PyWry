# Tools Reference

The MCP server exposes **25 tools** organized into five groups.
Every description, parameter name, type, and default below comes directly from the tool schemas in the source code.

!!! warning "Mandatory first step"
    Call `get_skills` with `skill="component_reference"` **before** creating any widget.
    The component reference is the authoritative source for event signatures,
    system events, and JSON schemas for all 18 toolbar component types.

---

## Discovery

### get_skills

Get context-appropriate skills and guidance for creating widgets.

The `component_reference` skill is **mandatory** — it contains the only correct event signatures and system events. Without it, the agent will not know the correct payloads for `grid:update-data`, `plotly:update-figure`, `toolbar:set-value`, etc.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `skill` | `string` | No | Skill to retrieve. If omitted, returns the full list with descriptions. |

**Skill IDs:** `component_reference`, `interactive_buttons`, `native`, `jupyter`, `iframe`, `deploy`, `css_selectors`, `styling`, `data_visualization`, `forms_and_inputs`, `modals`

**System events available via `component_reference`:**

| Event | Payload | Purpose |
|:---|:---|:---|
| `grid:update-data` | `{"data": [...], "strategy": "set\|append\|update"}` | Replace, append, or merge grid rows |
| `grid:request-state` | `{}` | Request grid state (response via `grid:state-response`) |
| `grid:restore-state` | `{"state": {...}}` | Restore a saved grid state |
| `grid:reset-state` | `{"hard": true\|false}` | Soft reset (keeps columns) or hard reset |
| `plotly:update-figure` | `{"data": [...], "layout": {...}}` | Replace chart data and layout |
| `plotly:request-state` | `{}` | Request chart state |
| `pywry:set-content` | `{"id": "...", "text": "..."}` or `{"id": "...", "html": "..."}` | Update a DOM element |
| `pywry:update-theme` | `{"theme": "dark\|light\|system"}` | Switch theme |
| `toolbar:set-value` | `{"componentId": "...", "value": "..."}` | Set a toolbar component's value |
| `toolbar:request-state` | `{}` | Request all toolbar values (response via `toolbar:state-response`) |

---

## Widget Creation

### create_widget

Create an interactive native window with HTML content and Pydantic toolbar components.

| Parameter | Type | Required | Default | Description |
|:---|:---|:---|:---|:---|
| `html` | `string` | **Yes** | — | HTML content. Use `id` attributes or `Div` components for dynamic content. |
| `title` | `string` | No | `"PyWry Widget"` | Window title |
| `height` | `integer` | No | `500` | Window height in pixels |
| `include_plotly` | `boolean` | No | `false` | Include Plotly.js |
| `include_aggrid` | `boolean` | No | `false` | Include AG Grid |
| `toolbars` | `array` | No | — | Toolbar definitions (see schema below) |
| `callbacks` | `object` | No | — | Map of event names → callback actions that run on the Python backend |

**Returns (native):** `{"widget_id": "...", "mode": "native", "created": true}`
**Returns (headless):** `{"widget_id": "...", "path": "/widget/...", "export_uri": "pywry://export/...", "created": true}`

#### How events work

Toolbar components fire events when users interact with them. Every component's `event` attribute names the event (e.g. `"app:save"`, `"filter:region"`). When the user clicks a button or changes a select, the event travels from the browser back to the Python backend:

```
Browser click → toolbar-handlers.js reads data-event
  → WebSocket / anywidget traitlet sync → Python backend
  → widget.on() handlers fire → callback(data, event_type, label)
```

Events are registered on the widget via `widget.on(event_name, callback)`. Every toolbar item's event is automatically registered so the MCP server can capture interactions and surface them through `get_events`.

#### Callbacks — wiring events to backend actions

The `callbacks` parameter lets you wire events directly to Python-side actions that execute on the backend when the event fires. Each entry maps an event name to an action config:

| Property | Type | Description |
|:---|:---|:---|
| `action` | `string` | One of `increment`, `decrement`, `set`, `toggle`, `emit` |
| `target` | `string` | `component_id` of the DOM element to update after the action |
| `state_key` | `string` | Key in a per-widget state dict on the backend (default: `"value"`) |
| `value` | `any` | Value to use for the `set` action |
| `emit_event` | `string` | Event to emit to the browser (for the `emit` action) |
| `emit_data` | `object` | Payload to emit with the event |

When a callback fires:

1. The action modifies the widget's backend state dict (e.g. `state["value"] += 1` for `increment`).
2. If `target` is set, the server emits `pywry:set-content` with `{"id": target, "text": str(new_value)}` to push the updated value to the browser immediately.
3. The `emit` action skips the state update and instead emits a custom event to the browser via `widget.emit()`.

This means the callback runs real Python code on the backend and pushes results to the browser — there is no client-side magic.

#### Events without callbacks → get_events

Toolbar events that are **not** covered by an explicit `callbacks` entry are still captured by the MCP server and queued. The agent reads them with [`get_events`](#get_events) and decides what to do (update a chart, change data, show a toast, etc.).

#### Toolbar schema

```json
{
  "position": "top",        // top | bottom | left | right | inside
  "items": [
    {
      "type": "button",     // any of the 18 component types
      "label": "Save",
      "event": "app:save",  // namespace:action (avoid pywry/plotly/grid namespaces)
      "variant": "primary", // primary | neutral | danger | success
      "size": "md"          // sm | md | lg
    }
  ]
}
```

#### Component types and their event payloads

| Type | Event payload | Key properties |
|:---|:---|:---|
| `button` | `{componentId, ...data}` | `label`, `event`, `variant` |
| `select` | `{value, componentId}` | `event`, `options`, `selected` |
| `multiselect` | `{values: [], componentId}` | `event`, `options` |
| `toggle` | `{value: boolean, componentId}` | `event`, `label` |
| `checkbox` | `{value: boolean, componentId}` | `event`, `label` |
| `radio` | `{value, componentId}` | `event`, `options` |
| `tabs` | `{value, componentId}` | `event`, `options` |
| `text` | `{value, componentId}` | `event`, `placeholder` |
| `textarea` | `{value, componentId}` | `event`, `rows` |
| `search` | `{value, componentId}` | `event`, `debounce` |
| `number` | `{value: number, componentId}` | `event`, `min`, `max`, `step` |
| `date` | `{value: "YYYY-MM-DD", componentId}` | `event` |
| `slider` | `{value: number, componentId}` | `event`, `min`, `max`, `step`, `show_value` |
| `range` | `{start, end, componentId}` | `event`, `min`, `max` |
| `secret` | `{value: base64, encoded: true, componentId}` | `event`, `show_toggle`, `show_copy` |
| `div` | *(no events)* | `content`, `component_id`, `style` |
| `marquee` | `{value, componentId}` *(if clickable)* | `text`, `speed`, `behavior`, `ticker_items` |

**Options format** (select, multiselect, radio, tabs):

```json
"options": [{"label": "Dark", "value": "dark"}, {"label": "Light", "value": "light"}]
```

---

### show_plotly

Create a Plotly chart widget. Pass figure JSON from `fig.to_json()`.

| Parameter | Type | Required | Default | Description |
|:---|:---|:---|:---|:---|
| `figure_json` | `string` | **Yes** | — | Plotly figure as a JSON string |
| `title` | `string` | No | `"Plotly Chart"` | Window title |
| `height` | `integer` | No | `500` | Window height |

**Returns:** `{"widget_id": "...", "path": "...", "created": true}`

To update later, use `update_plotly` or `send_event` with event `plotly:update-figure` and data `{"data": [...], "layout": {...}}`.

---

### show_dataframe

Create an AG Grid table widget from JSON data.

| Parameter | Type | Required | Default | Description |
|:---|:---|:---|:---|:---|
| `data_json` | `string` | **Yes** | — | Data as JSON array of row objects |
| `title` | `string` | No | `"Data Table"` | Window title |
| `height` | `integer` | No | `500` | Window height |

**Returns:** `{"widget_id": "...", "path": "...", "created": true}`

To update later, use `send_event` with event `grid:update-data` and data `{"data": [...], "strategy": "set"}`. Strategies: `set` (replace all rows), `append` (add rows), `update` (merge by row ID).

---

### build_div

Build a `Div` component's HTML string. Use `component_id` so the element can be targeted later with `set_content` or `set_style`.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `content` | `string` | **Yes** | Text or HTML content |
| `component_id` | `string` | No | ID attribute — required for `set_content`/`set_style` targeting |
| `style` | `string` | No | Inline CSS |
| `class_name` | `string` | No | CSS class |

**Returns:** `{"html": "<div id=\"counter\" style=\"...\">0</div>"}`

Use the returned `html` in `create_widget`'s `html` parameter.

---

### build_ticker_item

Build a `TickerItem` HTML span for use inside a Marquee. The `data-ticker` attribute lets `update_ticker_item` target it later.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `ticker` | `string` | **Yes** | Unique ID for targeting updates (e.g. `AAPL`, `BTC`) |
| `text` | `string` | No | Display text |
| `html` | `string` | No | HTML content (overrides `text`) |
| `class_name` | `string` | No | CSS classes |
| `style` | `string` | No | Inline CSS |

**Returns:** `{"html": "<span data-ticker=\"AAPL\" ...>...</span>", "ticker": "AAPL", "update_event": "toolbar:marquee-set-item"}`

---

## Widget Manipulation

All manipulation tools require a `widget_id` returned by a prior creation call.
Each tool emits a specific **system event** to the widget's frontend via WebSocket.

### set_content

Update an element's text or HTML by its `component_id`. Emits `pywry:set-content`.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | Target widget |
| `component_id` | `string` | **Yes** | Element ID to update |
| `text` | `string` | No | Plain text (sets `textContent`) |
| `html` | `string` | No | HTML string (sets `innerHTML`, overrides `text`) |

**Emits:** `pywry:set-content` → `{"id": "<component_id>", "text": "..."}` or `{"id": "<component_id>", "html": "..."}`

---

### set_style

Update CSS styles on an element. Emits `pywry:set-style`. Use camelCase property names.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | Target widget |
| `component_id` | `string` | **Yes** | Element ID to update |
| `styles` | `object` | **Yes** | CSS property → value pairs (camelCase keys) |

**Emits:** `pywry:set-style` → `{"id": "<component_id>", "styles": {"fontSize": "24px", "color": "red"}}`

---

### show_toast

Display a toast notification. Emits `pywry:alert`.

| Parameter | Type | Required | Default | Description |
|:---|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | — | Target widget |
| `message` | `string` | **Yes** | — | Notification text |
| `type` | `string` | No | `"info"` | `info`, `success`, `warning`, or `error` |
| `duration` | `integer` | No | `3000` | Auto-dismiss time in milliseconds |

**Emits:** `pywry:alert` → `{"message": "...", "type": "info", "duration": 3000}`

---

### update_theme

Switch a widget's color theme. Plotly charts and AG Grid auto-sync. Emits `pywry:update-theme`.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | Target widget |
| `theme` | `string` | **Yes** | `dark`, `light`, or `system` |

**Emits:** `pywry:update-theme` → `{"theme": "dark"}`

---

### inject_css

Inject CSS rules into a widget. Creates or updates a `<style>` element identified by `style_id`. Emits `pywry:inject-css`.

| Parameter | Type | Required | Default | Description |
|:---|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | — | Target widget |
| `css` | `string` | **Yes** | — | CSS rules to inject |
| `style_id` | `string` | No | `"pywry-injected-style"` | Unique ID for the `<style>` element |

**Emits:** `pywry:inject-css` → `{"css": "...", "id": "pywry-injected-style"}`

---

### remove_css

Remove a previously injected `<style>` element. Emits `pywry:remove-css`.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | Target widget |
| `style_id` | `string` | **Yes** | ID used when injecting |

**Emits:** `pywry:remove-css` → `{"id": "..."}`

---

### navigate

Client-side redirect inside a widget. Emits `pywry:navigate`.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | Target widget |
| `url` | `string` | **Yes** | URL to navigate to |

**Emits:** `pywry:navigate` → `{"url": "https://..."}`

---

### download

Trigger a file download in the browser. Emits `pywry:download`.

| Parameter | Type | Required | Default | Description |
|:---|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | — | Target widget |
| `content` | `string` | **Yes** | — | File content |
| `filename` | `string` | **Yes** | — | Suggested filename |
| `mime_type` | `string` | No | `"application/octet-stream"` | MIME type |

**Emits:** `pywry:download` → `{"content": "...", "filename": "...", "mimeType": "text/csv"}`

---

### update_plotly

Update a Plotly chart in an existing widget.

| Parameter | Type | Required | Default | Description |
|:---|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | — | Target widget |
| `figure_json` | `string` | **Yes** | — | New Plotly figure JSON |
| `layout_only` | `boolean` | No | `false` | If `true`, only update layout (not data traces) |

**Emits:**

- `layout_only=false` → `plotly:update-figure` → `{"data": [...], "layout": {...}}`
- `layout_only=true` → `plotly:update-layout` → `{"layout": {...}}`

---

### update_marquee

Update a Marquee component's content, speed, or play state.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | Target widget |
| `component_id` | `string` | **Yes** | Marquee component ID |
| `text` | `string` | No | New text content |
| `html` | `string` | No | New HTML content |
| `speed` | `number` | No | Animation speed in seconds |
| `paused` | `boolean` | No | Pause/resume |
| `ticker_update` | `object` | No | Update a single ticker item (has `ticker`, `text`, `html`, `styles`, `class_add`, `class_remove`) |

**Emits:**

- With `ticker_update` → `toolbar:marquee-set-item` → ticker update payload
- Without `ticker_update` → `toolbar:marquee-set-content` → `{"id": "...", ...}`

---

### update_ticker_item

Update a single ticker item inside a Marquee by its `ticker` ID. Uses `TickerItem.update_payload()` internally. Updates **all** elements matching the ticker (marquee content is duplicated for seamless scrolling).

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | Target widget |
| `ticker` | `string` | **Yes** | Ticker ID (e.g. `AAPL`, `BTC`) |
| `text` | `string` | No | New text |
| `html` | `string` | No | New HTML |
| `styles` | `object` | No | CSS property → value pairs |
| `class_add` | `string` or `array` | No | CSS class(es) to add |
| `class_remove` | `string` or `array` | No | CSS class(es) to remove |

**Emits:** `toolbar:marquee-set-item` → generated by `TickerItem.update_payload()`

---

## Widget Management

### list_widgets

List all active widgets.

**Parameters:** None

**Returns:**

```json
{"widgets": [{"widget_id": "w-abc123", "path": "/widget/w-abc123"}], "count": 1}
```

---

### get_events

Read queued user-interaction events from a widget. Every toolbar component event is registered via `widget.on()` on the backend, and the MCP server captures each firing into a per-widget buffer. Events that have explicit `callbacks` still fire their backend action **and** get queued here — events without callbacks are only queued.

| Parameter | Type | Required | Default | Description |
|:---|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | — | Target widget |
| `clear` | `boolean` | No | `false` | Clear the event buffer after reading |

**Returns:**

```json
{
  "widget_id": "w-abc123",
  "events": [
    {"event_type": "app:save", "data": {"componentId": "save-btn"}, "label": "app:save"},
    {"event_type": "app:region", "data": {"value": "north", "componentId": "region-select"}, "label": "app:region"}
  ]
}
```

Events include `event_type`, `data` (the component's event payload), and `label`.

---

### destroy_widget

Destroy a widget and clean up all associated resources (event buffers, callbacks, state, inline-mode registrations).

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | Widget to destroy |

---

## send_event

The low-level escape hatch. Send **any** event type to a widget's frontend. This is the same mechanism all the manipulation tools use internally — `set_content` emits `pywry:set-content`, `show_toast` emits `pywry:alert`, etc.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | Target widget |
| `event_type` | `string` | **Yes** | Event name |
| `data` | `object` | **Yes** | Event payload |

All three parameters are **required**.

### AG Grid events

| Event | Payload | Effect |
|:---|:---|:---|
| `grid:update-data` | `{"data": [...rows], "strategy": "set"}` | Replace all rows |
| `grid:update-data` | `{"data": [...rows], "strategy": "append"}` | Append rows |
| `grid:update-data` | `{"data": [...rows], "strategy": "update"}` | Update existing rows |
| `grid:update-columns` | `{"columnDefs": [...]}` | Replace column definitions |
| `grid:update-cell` | `{"rowId": "row-1", "colId": "price", "value": 99.50}` | Update a single cell |
| `grid:request-state` | `{}` | Request grid state (response via `grid:state-response`) |
| `grid:restore-state` | `{"state": {...savedState}}` | Restore a previously saved state |
| `grid:reset-state` | `{"hard": false}` | Soft reset (keeps columns) |
| `grid:reset-state` | `{"hard": true}` | Hard reset (full reset) |

### Plotly events

| Event | Payload | Effect |
|:---|:---|:---|
| `plotly:update-figure` | `{"data": [...], "layout": {...}, "config": {...}}` | Replace data + layout |
| `plotly:update-layout` | `{"layout": {...}}` | Update layout only |
| `plotly:reset-zoom` | `{}` | Reset chart zoom |
| `plotly:request-state` | `{}` | Request state (response via `plotly:state-response`) |
| `plotly:export-data` | `{}` | Export data (response via `plotly:export-response`) |

### Toolbar events

| Event | Payload | Effect |
|:---|:---|:---|
| `toolbar:set-value` | `{"componentId": "my-select", "value": "option2"}` | Set one component's value |
| `toolbar:set-values` | `{"values": {"id1": "v1", "id2": true}}` | Set multiple values at once |
| `toolbar:request-state` | `{}` | Request all values (response via `toolbar:state-response`) |

### DOM events

| Event | Payload | Effect |
|:---|:---|:---|
| `pywry:set-content` | `{"id": "elementId", "text": "..."}` | Set element `textContent` |
| `pywry:set-content` | `{"id": "elementId", "html": "..."}` | Set element `innerHTML` |
| `pywry:set-style` | `{"id": "elementId", "styles": {"color": "red", "fontSize": "18px"}}` | Update CSS styles |
| `pywry:update-theme` | `{"theme": "dark\|light\|system"}` | Switch theme |
| `pywry:alert` | `{"message": "...", "type": "info\|success\|warning\|error"}` | Show toast |
| `pywry:navigate` | `{"url": "https://..."}` | Client-side redirect |
| `pywry:download` | `{"content": "...", "filename": "...", "mimeType": "text/plain"}` | Trigger file download |

### Marquee events

| Event | Payload | Effect |
|:---|:---|:---|
| `toolbar:marquee-set-item` | `{"ticker": "AAPL", "text": "AAPL $185", "styles": {"color": "green"}}` | Update one ticker item |
| `toolbar:marquee-set-content` | `{"id": "...", "text": "..."}` | Replace marquee content |

---

## Resources & Export

### get_component_docs

Retrieve documentation for a toolbar component type, including properties and usage examples.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `component` | `string` | **Yes** | Component type |

**Available:** `button`, `select`, `multiselect`, `toggle`, `checkbox`, `radio`, `tabs`, `text`, `textarea`, `search`, `number`, `date`, `slider`, `range`, `div`, `secret`, `marquee`, `ticker_item`

---

### get_component_source

Get the Python source code for a component class via `inspect.getsource()`.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `component` | `string` | **Yes** | Component type (also accepts `toolbar` and `option`) |

---

### export_widget

Export an active widget as standalone Python code that recreates it without MCP.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `widget_id` | `string` | **Yes** | Widget to export |

**Returns:** `{"widget_id": "...", "code": "...", "language": "python", "note": "..."}`

---

### list_resources

List all available MCP resources with their URIs.

**Parameters:** None

**Returns:** Resource URIs for:

- `pywry://component/{name}` — Component documentation
- `pywry://source/{name}` — Component source code
- `pywry://export/{widget_id}` — Widget export
- `pywry://docs/events` — Built-in events reference
- `pywry://docs/quickstart` — Quick start guide

---

## Error Handling

All tool calls return JSON. On error the response includes an `error` key:

```json
{"error": "Traceback (most recent call last):\n  ..."}
```

The agent can use the traceback to diagnose and retry.
