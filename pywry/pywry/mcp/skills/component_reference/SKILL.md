# PyWry Component Reference - MANDATORY SYNTAX

> **STOP. THIS IS THE AUTHORITATIVE REFERENCE FOR ALL COMPONENTS.**
> **YOU MUST USE THE EXACT EVENT SIGNATURES DOCUMENTED HERE.**
> **THERE ARE NO EXCEPTIONS. NO WORKAROUNDS. NO DEVIATIONS.**

---

## CRITICAL: System Events for Widget Updates

These are the ONLY events that work for updating widgets. Use `send_event` tool with these event types:

### AG Grid Data Updates

| Event Type | Payload | Description |
|------------|---------|-------------|
| `grid:update-data` | `{"data": [...rows...], "strategy": "set"}` | Replace all rows |
| `grid:update-data` | `{"data": [...rows...], "strategy": "append"}` | Append rows |
| `grid:update-data` | `{"data": [...rows...], "strategy": "update"}` | Update existing rows |
| `grid:update-columns` | `{"columnDefs": [...]}` | Update column definitions |
| `grid:update-cell` | `{"rowId": "row-1", "colId": "price", "value": 99.50}` | Update single cell |

### AG Grid State Persistence

| Event Type | Payload | Description |
|------------|---------|-------------|
| `grid:request-state` | `{}` | Request current grid state |
| `grid:request-state` | `{"gridId": "my-grid"}` | Request specific grid's state |
| `grid:restore-state` | `{"state": {...savedState...}}` | Restore saved grid state |
| `grid:reset-state` | `{"hard": false}` | Soft reset (keeps column order) |
| `grid:reset-state` | `{"hard": true}` | Hard reset (full reset) |

**Response Event:** `grid:state-response` with `{"gridId": "...", "state": {...}}`

**State Object Contents:**
- Column state (width, order, visibility, pinned, sort)
- Filter state (active filters per column)
- Sort state (sorted columns and direction)

### Plotly Chart Updates

| Event Type | Payload | Description |
|------------|---------|-------------|
| `plotly:update-figure` | `{"data": [...], "layout": {...}}` | Full figure update |
| `plotly:update-layout` | `{"layout": {...}}` | Layout only update |
| `plotly:reset-zoom` | `{}` | Reset chart zoom to original |

### Plotly State Persistence

| Event Type | Payload | Description |
|------------|---------|-------------|
| `plotly:request-state` | `{}` | Request current chart state |
| `plotly:request-state` | `{"chartId": "my-chart"}` | Request specific chart's state |

**Response Event:** `plotly:state-response` with `{"chartId": "...", "data": [...], "layout": {...}}`

### Plotly Data Export

| Event Type | Payload | Description |
|------------|---------|-------------|
| `plotly:export-data` | `{}` | Export chart data |
| `plotly:export-data` | `{"chartId": "my-chart"}` | Export specific chart's data |

**Response Event:** `plotly:export-response` with `{"data": [{"traceIndex": 0, "name": "...", "x": [...], "y": [...], "type": "..."}]}`

### DOM Content Updates

| Event Type | Payload | Description |
|------------|---------|-------------|
| `pywry:set-content` | `{"id": "elementId", "text": "..."}` | Set text content |
| `pywry:set-content` | `{"id": "elementId", "html": "..."}` | Set HTML content |
| `pywry:set-style` | `{"id": "elementId", "styles": {"color": "red"}}` | Update CSS styles |

### Theme Updates

| Event Type | Payload | Description |
|------------|---------|-------------|
| `pywry:update-theme` | `{"theme": "dark"}` | Switch theme (dark/light/system) |
| `pywry:update-theme` | `{"theme": "ag-theme-alpine-dark"}` | AG Grid theme |
| `pywry:update-theme` | `{"theme": "plotly_dark"}` | Plotly template |

### Toast Notifications

Use `show_toast` tool instead, or:

| Event Type | Payload | Description |
|------------|---------|-------------|
| `pywry:alert` | `{"message": "...", "type": "info"}` | info, success, warning, error |

### Toolbar Component State (Get/Set Values)

| Event Type | Payload | Description |
|------------|---------|-------------|
| `toolbar:set-value` | `{"componentId": "my-select", "value": "option2"}` | Set single component value |
| `toolbar:set-values` | `{"values": {"select-1": "A", "toggle-1": true}}` | Set multiple values at once |
| `toolbar:request-state` | `{"componentId": "my-input"}` | Request single component value |
| `toolbar:request-state` | `{"toolbarId": "top-toolbar"}` | Request all values in toolbar |
| `toolbar:request-state` | `{}` | Request all toolbar values |

**Response Event:** `toolbar:state-response` with `{"componentId": "...", "value": ...}` or `{"values": {...}}`

**Supported Components for set-value:**
- `select`: `{"componentId": "id", "value": "option-value"}`
- `multiselect`: `{"componentId": "id", "value": ["a", "b"]}`
- `toggle`: `{"componentId": "id", "value": true}`
- `checkbox`: `{"componentId": "id", "value": true}`
- `text/textarea/search`: `{"componentId": "id", "value": "text"}`
- `number`: `{"componentId": "id", "value": 42}`
- `slider`: `{"componentId": "id", "value": 50}`
- `range`: `{"componentId": "id", "value": {"start": 10, "end": 90}}`
- `tabs/radio`: `{"componentId": "id", "value": "tab-value"}`

**Note:** `secret` inputs cannot be set via toolbar:set-value for security.

---

## Table of Contents

1. [Button](#button)
2. [Select](#select)
3. [MultiSelect](#multiselect)
4. [Toggle](#toggle)
5. [Checkbox](#checkbox)
6. [RadioGroup](#radiogroup)
7. [TabGroup](#tabgroup)
8. [TextInput](#textinput)
9. [TextArea](#textarea)
10. [SearchInput](#searchinput)
11. [NumberInput](#numberinput)
12. [DateInput](#dateinput)
13. [SliderInput](#sliderinput)
14. [RangeInput](#rangeinput)
15. [SecretInput](#secretinput)
16. [Div](#div)
17. [Marquee](#marquee)
18. [TickerItem](#tickeritem)

---

## Button

A clickable button that emits an event.

### Properties

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `type` | `"button"` | ✅ YES | - | Component type identifier |
| `label` | `string` | ✅ YES | - | Button text |
| `event` | `string` | ✅ YES | - | Event name (format: `namespace:action`) |
| `variant` | `string` | ❌ | `"primary"` | Style: `primary`, `secondary`, `neutral`, `ghost`, `outline`, `danger`, `warning`, `icon` |
| `size` | `string` | ❌ | `null` | Size: `xs`, `sm`, `lg`, `xl` |
| `data` | `object` | ❌ | `{}` | Extra data payload sent with event |
| `disabled` | `boolean` | ❌ | `false` | Disable the button |
| `description` | `string` | ❌ | `""` | Tooltip on hover |

### Event Emitted

```javascript
{
  componentId: "button-abc123",   // Auto-generated component ID
  ...data                         // Your custom data object spread in
}
```

### Auto-Wired Actions

When event follows `elementId:action` pattern, these actions work automatically:

| Event Pattern | Behavior |
|---------------|----------|
| `myId:increment` | Finds `id="myId"`, parses as number, adds 1 |
| `myId:decrement` | Finds `id="myId"`, parses as number, subtracts 1 |
| `myId:reset` | Finds `id="myId"`, sets to 0 |
| `myId:toggle` | Finds `id="myId"`, toggles true/false |

### Example

```json
{
  "type": "button",
  "label": "Submit",
  "event": "form:submit",
  "variant": "primary",
  "data": {"formId": "contact"}
}
```

---

## Select

A single-select dropdown.

### Properties

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `type` | `"select"` | ✅ YES | - | Component type identifier |
| `event` | `string` | ✅ YES | - | Event name (format: `namespace:action`) |
| `options` | `array` | ✅ YES | - | Array of `{label, value}` objects |
| `selected` | `string` | ❌ | `""` | Initially selected value |
| `label` | `string` | ❌ | `""` | Label text |
| `searchable` | `boolean` | ❌ | `false` | Enable search filtering |
| `disabled` | `boolean` | ❌ | `false` | Disable the dropdown |

### Event Emitted

```javascript
{
  value: "selected_value",        // The selected option's value
  componentId: "select-abc123"
}
```

### Example

```json
{
  "type": "select",
  "label": "Theme:",
  "event": "theme:change",
  "options": [
    {"label": "Dark", "value": "dark"},
    {"label": "Light", "value": "light"},
    {"label": "System", "value": "system"}
  ],
  "selected": "dark"
}
```

---

## MultiSelect

A multi-select dropdown with checkboxes.

### Properties

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `type` | `"multiselect"` | ✅ YES | - | Component type identifier |
| `event` | `string` | ✅ YES | - | Event name |
| `options` | `array` | ✅ YES | - | Array of `{label, value}` objects |
| `selected` | `array` | ❌ | `[]` | Initially selected values |
| `label` | `string` | ❌ | `""` | Label text |
| `disabled` | `boolean` | ❌ | `false` | Disable the dropdown |

### Event Emitted

```javascript
{
  values: ["value1", "value2"],   // Array of selected values
  componentId: "multiselect-abc123"
}
```

### Example

```json
{
  "type": "multiselect",
  "label": "Columns:",
  "event": "columns:filter",
  "options": [
    {"label": "Name", "value": "name"},
    {"label": "Age", "value": "age"},
    {"label": "City", "value": "city"}
  ],
  "selected": ["name", "age"]
}
```

---

## Toggle

A toggle switch for boolean values.

### Properties

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `type` | `"toggle"` | ✅ YES | - | Component type identifier |
| `event` | `string` | ✅ YES | - | Event name |
| `value` | `boolean` | ❌ | `false` | Initial state |
| `label` | `string` | ❌ | `""` | Label text |
| `disabled` | `boolean` | ❌ | `false` | Disable the toggle |

### Event Emitted

```javascript
{
  value: true,                    // Boolean: true or false
  componentId: "toggle-abc123"
}
```

### Example

```json
{
  "type": "toggle",
  "label": "Dark Mode:",
  "event": "theme:toggle",
  "value": true
}
```

---

## Checkbox

A single checkbox for boolean values.

### Properties

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `type` | `"checkbox"` | ✅ YES | - | Component type identifier |
| `event` | `string` | ✅ YES | - | Event name |
| `value` | `boolean` | ❌ | `false` | Initial checked state |
| `label` | `string` | ✅ YES | - | Label text (displayed next to checkbox) |
| `disabled` | `boolean` | ❌ | `false` | Disable the checkbox |

### Event Emitted

```javascript
{
  value: true,                    // Boolean: true or false
  componentId: "checkbox-abc123"
}
```

### Example

```json
{
  "type": "checkbox",
  "label": "Enable notifications",
  "event": "settings:notify",
  "value": true
}
```

---

## RadioGroup

A group of radio buttons for single selection.

### Properties

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `type` | `"radio"` | ✅ YES | - | Component type identifier |
| `event` | `string` | ✅ YES | - | Event name |
| `options` | `array` | ✅ YES | - | Array of `{label, value}` objects |
| `selected` | `string` | ❌ | `""` | Initially selected value |
| `label` | `string` | ❌ | `""` | Group label |
| `direction` | `string` | ❌ | `"horizontal"` | Layout: `horizontal` or `vertical` |
| `disabled` | `boolean` | ❌ | `false` | Disable all radios |

### Event Emitted

```javascript
{
  value: "selected_value",        // The selected option's value
  componentId: "radio-abc123"
}
```

### Example

```json
{
  "type": "radio",
  "label": "View:",
  "event": "view:change",
  "options": [
    {"label": "List", "value": "list"},
    {"label": "Grid", "value": "grid"},
    {"label": "Card", "value": "card"}
  ],
  "selected": "list",
  "direction": "horizontal"
}
```

---

## TabGroup

Tab-style buttons for single selection (visually different from RadioGroup).

### Properties

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `type` | `"tabs"` | ✅ YES | - | Component type identifier |
| `event` | `string` | ✅ YES | - | Event name |
| `options` | `array` | ✅ YES | - | Array of `{label, value}` objects |
| `selected` | `string` | ❌ | `""` | Initially selected value |
| `label` | `string` | ❌ | `""` | Group label |
| `size` | `string` | ❌ | `"md"` | Size: `sm`, `md`, `lg` |
| `disabled` | `boolean` | ❌ | `false` | Disable all tabs |

### Event Emitted

```javascript
{
  value: "selected_value",        // The selected tab's value
  componentId: "tab-abc123"
}
```

### Example

```json
{
  "type": "tabs",
  "label": "Mode:",
  "event": "mode:switch",
  "options": [
    {"label": "Edit", "value": "edit"},
    {"label": "Preview", "value": "preview"},
    {"label": "Split", "value": "split"}
  ],
  "selected": "edit"
}
```

---

## TextInput

A single-line text input with debounced events.

### Properties

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `type` | `"text"` | ✅ YES | - | Component type identifier |
| `event` | `string` | ✅ YES | - | Event name |
| `value` | `string` | ❌ | `""` | Initial value |
| `placeholder` | `string` | ❌ | `""` | Placeholder text |
| `label` | `string` | ❌ | `""` | Label text |
| `debounce` | `integer` | ❌ | `300` | Debounce milliseconds |
| `disabled` | `boolean` | ❌ | `false` | Disable the input |

### Event Emitted

```javascript
{
  value: "user typed text",       // The current input value
  componentId: "text-abc123"
}
```

### Example

```json
{
  "type": "text",
  "label": "Name:",
  "event": "form:name",
  "placeholder": "Enter your name",
  "debounce": 300
}
```

---

## TextArea

A multi-line text area with resizing.

### Properties

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `type` | `"textarea"` | ✅ YES | - | Component type identifier |
| `event` | `string` | ✅ YES | - | Event name |
| `value` | `string` | ❌ | `""` | Initial value |
| `placeholder` | `string` | ❌ | `""` | Placeholder text |
| `label` | `string` | ❌ | `""` | Label text |
| `rows` | `integer` | ❌ | `3` | Number of visible rows |
| `cols` | `integer` | ❌ | `40` | Number of visible columns |
| `resize` | `string` | ❌ | `"both"` | Resize: `both`, `horizontal`, `vertical`, `none` |
| `debounce` | `integer` | ❌ | `300` | Debounce milliseconds |
| `disabled` | `boolean` | ❌ | `false` | Disable the textarea |

### Event Emitted

```javascript
{
  value: "multi-line\ntext content",  // The textarea content
  componentId: "textarea-abc123"
}
```

### Example

```json
{
  "type": "textarea",
  "label": "Notes:",
  "event": "form:notes",
  "placeholder": "Enter your notes...",
  "rows": 5,
  "resize": "vertical"
}
```

---

## SearchInput

A search input with magnifying glass icon.

### Properties

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `type` | `"search"` | ✅ YES | - | Component type identifier |
| `event` | `string` | ✅ YES | - | Event name |
| `value` | `string` | ❌ | `""` | Initial value |
| `placeholder` | `string` | ❌ | `"Search..."` | Placeholder text |
| `label` | `string` | ❌ | `""` | Label text |
| `debounce` | `integer` | ❌ | `300` | Debounce milliseconds |
| `disabled` | `boolean` | ❌ | `false` | Disable the input |

### Event Emitted

```javascript
{
  value: "search query",          // The search text
  componentId: "search-abc123"
}
```

### Example

```json
{
  "type": "search",
  "label": "Filter:",
  "event": "table:filter",
  "placeholder": "Type to filter...",
  "debounce": 200
}
```

---

## NumberInput

A numeric input with optional constraints.

### Properties

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `type` | `"number"` | ✅ YES | - | Component type identifier |
| `event` | `string` | ✅ YES | - | Event name |
| `value` | `number` | ❌ | `null` | Initial value |
| `min` | `number` | ❌ | `null` | Minimum value |
| `max` | `number` | ❌ | `null` | Maximum value |
| `step` | `number` | ❌ | `null` | Step increment |
| `label` | `string` | ❌ | `""` | Label text |
| `disabled` | `boolean` | ❌ | `false` | Disable the input |

### Event Emitted

```javascript
{
  value: 42,                      // The numeric value
  componentId: "number-abc123"
}
```

### Example

```json
{
  "type": "number",
  "label": "Quantity:",
  "event": "cart:quantity",
  "value": 1,
  "min": 1,
  "max": 100,
  "step": 1
}
```

---

## DateInput

A date picker input.

### Properties

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `type` | `"date"` | ✅ YES | - | Component type identifier |
| `event` | `string` | ✅ YES | - | Event name |
| `value` | `string` | ❌ | `""` | Initial date (YYYY-MM-DD) |
| `min` | `string` | ❌ | `""` | Minimum date (YYYY-MM-DD) |
| `max` | `string` | ❌ | `""` | Maximum date (YYYY-MM-DD) |
| `label` | `string` | ❌ | `""` | Label text |
| `disabled` | `boolean` | ❌ | `false` | Disable the input |

### Event Emitted

```javascript
{
  value: "2025-01-29",            // Date string in YYYY-MM-DD format
  componentId: "date-abc123"
}
```

### Example

```json
{
  "type": "date",
  "label": "Start Date:",
  "event": "filter:startDate",
  "value": "2025-01-01",
  "min": "2020-01-01",
  "max": "2030-12-31"
}
```

---

## SliderInput

A single-value slider.

### Properties

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `type` | `"slider"` | ✅ YES | - | Component type identifier |
| `event` | `string` | ✅ YES | - | Event name |
| `value` | `number` | ❌ | `50` | Initial value |
| `min` | `number` | ❌ | `0` | Minimum value |
| `max` | `number` | ❌ | `100` | Maximum value |
| `step` | `number` | ❌ | `1` | Step increment |
| `show_value` | `boolean` | ❌ | `true` | Show value display |
| `debounce` | `integer` | ❌ | `50` | Debounce milliseconds |
| `label` | `string` | ❌ | `""` | Label text |
| `disabled` | `boolean` | ❌ | `false` | Disable the slider |

### Event Emitted

```javascript
{
  value: 75,                      // The slider value
  componentId: "slider-abc123"
}
```

### Example

```json
{
  "type": "slider",
  "label": "Volume:",
  "event": "audio:volume",
  "value": 50,
  "min": 0,
  "max": 100,
  "step": 5,
  "show_value": true
}
```

---

## RangeInput

A dual-handle range slider for min/max selection.

### Properties

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `type` | `"range"` | ✅ YES | - | Component type identifier |
| `event` | `string` | ✅ YES | - | Event name |
| `start` | `number` | ❌ | `0` | Initial start value |
| `end` | `number` | ❌ | `100` | Initial end value |
| `min` | `number` | ❌ | `0` | Minimum value |
| `max` | `number` | ❌ | `100` | Maximum value |
| `step` | `number` | ❌ | `1` | Step increment |
| `show_value` | `boolean` | ❌ | `true` | Show value displays |
| `debounce` | `integer` | ❌ | `50` | Debounce milliseconds |
| `label` | `string` | ❌ | `""` | Label text |
| `disabled` | `boolean` | ❌ | `false` | Disable the slider |

### Event Emitted

```javascript
{
  start: 25,                      // Start/min value
  end: 75,                        // End/max value
  componentId: "range-abc123"
}
```

### Example

```json
{
  "type": "range",
  "label": "Price Range:",
  "event": "filter:price",
  "start": 100,
  "end": 500,
  "min": 0,
  "max": 1000,
  "step": 10,
  "show_value": true
}
```

---

## SecretInput

A password/secret input with visibility toggle and copy button.

### Properties

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `type` | `"secret"` | ✅ YES | - | Component type identifier |
| `event` | `string` | ✅ YES | - | Event name |
| `value` | `string` | ❌ | `""` | Initial secret value (stored securely) |
| `placeholder` | `string` | ❌ | `""` | Placeholder text |
| `label` | `string` | ❌ | `""` | Label text |
| `show_toggle` | `boolean` | ❌ | `true` | Show visibility toggle button |
| `show_copy` | `boolean` | ❌ | `true` | Show copy button |
| `debounce` | `integer` | ❌ | `300` | Debounce milliseconds |
| `disabled` | `boolean` | ❌ | `false` | Disable the input |

### Events Emitted

**On value change:**
```javascript
{
  value: "base64_encoded_value",  // Base64 encoded secret
  encoded: true,
  componentId: "secret-abc123"
}
```

**On reveal request:** (event: `{event}:reveal`)
```javascript
{
  componentId: "secret-abc123"
}
```

**On copy request:** (event: `{event}:copy`)
```javascript
{
  componentId: "secret-abc123"
}
```

### Example

```json
{
  "type": "secret",
  "label": "API Key:",
  "event": "settings:apiKey",
  "placeholder": "Enter your API key",
  "show_toggle": true,
  "show_copy": true
}
```

---

## Div

A container for custom HTML content.

### Properties

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `type` | `"div"` | ✅ YES | - | Component type identifier |
| `content` | `string` | ✅ YES | - | HTML content |
| `component_id` | `string` | ❌ | auto | ID for updates via `set_content` |
| `class_name` | `string` | ❌ | `""` | CSS class name |
| `style` | `string` | ❌ | `""` | Inline CSS styles |
| `children` | `array` | ❌ | `null` | Nested toolbar items |

### Event Emitted

No automatic events. Use for layout/display only, or add interactive children.

### Example

```json
{
  "type": "div",
  "content": "<span style=\"color: green\">Online</span>",
  "component_id": "status-display",
  "style": "padding: 8px; font-weight: bold"
}
```

---

## Marquee

A scrolling text ticker component.

### Properties

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `type` | `"marquee"` | ✅ YES | - | Component type identifier |
| `text` | `string` | ✅ YES | - | Scrolling text content |
| `event` | `string` | ❌ | - | Event name (if clickable) |
| `speed` | `number` | ❌ | `15` | Seconds per scroll cycle (1-300) |
| `direction` | `string` | ❌ | `"left"` | Direction: `left`, `right`, `up`, `down` |
| `behavior` | `string` | ❌ | `"scroll"` | Behavior: `scroll`, `alternate`, `slide`, `static` |
| `pause_on_hover` | `boolean` | ❌ | `true` | Pause on mouse hover |
| `gap` | `integer` | ❌ | `50` | Gap between content (pixels) |
| `clickable` | `boolean` | ❌ | `false` | Emit event on click |
| `separator` | `string` | ❌ | `""` | Separator between repeats |
| `component_id` | `string` | ❌ | auto | ID for updates |

### Event Emitted (when clickable)

```javascript
{
  value: "the marquee text",      // The text content
  componentId: "marquee-abc123"
}
```

### Update Events

Use `set_content` or `update_marquee` tools to update:

```javascript
// Update text
{id: "marquee-abc123", text: "New content!"}

// Update speed
{id: "marquee-abc123", speed: 10}

// Pause/resume
{id: "marquee-abc123", paused: true}
```

### Example

```json
{
  "type": "marquee",
  "text": "Breaking News: Market is up 5% • Weather: Sunny • More updates...",
  "speed": 20,
  "direction": "left",
  "pause_on_hover": true,
  "clickable": true,
  "event": "news:click"
}
```

---

## TickerItem

A helper for creating updatable items within a Marquee.

**Note:** TickerItem is used with `build_ticker_item` tool, not as a direct toolbar item.

### Properties

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `ticker` | `string` | ✅ YES | - | Unique identifier (e.g., "AAPL") |
| `text` | `string` | ❌ | `""` | Text content |
| `html` | `string` | ❌ | `""` | HTML content (overrides text) |
| `class_name` | `string` | ❌ | `""` | CSS classes |
| `style` | `string` | ❌ | `""` | Inline styles |

### Update via `update_ticker_item`

```javascript
{
  ticker: "AAPL",
  text: "AAPL $186.25 ▲",
  styles: {color: "#22c55e"},
  class_add: "stock-up",
  class_remove: "stock-down"
}
```

### Example

```python
# Build ticker items
items = [
    build_ticker_item(ticker="AAPL", text="AAPL $185.50"),
    build_ticker_item(ticker="GOOGL", text="GOOGL $142.20"),
]

# Use in marquee
marquee_text = " • ".join(items)
```

---

## Toolbar Container Structure

All components go inside the `toolbars` array. Each toolbar has:

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `position` | `string` | ✅ YES | - | Position: `top`, `bottom`, `left`, `right`, `header`, `footer`, `inside` |
| `items` | `array` | ✅ YES | - | Array of components |
| `class_name` | `string` | ❌ | `""` | CSS class for toolbar |

### Complete Example

```json
{
  "html": "<div id=\"content\">Main content here</div>",
  "title": "My Widget",
  "height": 600,
  "toolbars": [
    {
      "position": "top",
      "items": [
        {"type": "button", "label": "Save", "event": "file:save", "variant": "primary"},
        {"type": "button", "label": "Cancel", "event": "file:cancel", "variant": "secondary"},
        {"type": "select", "event": "file:format", "options": [
          {"label": "JSON", "value": "json"},
          {"label": "CSV", "value": "csv"}
        ], "selected": "json"}
      ]
    },
    {
      "position": "bottom",
      "items": [
        {"type": "div", "content": "Status: Ready", "component_id": "status"},
        {"type": "slider", "event": "zoom:level", "value": 100, "min": 50, "max": 200, "label": "Zoom:"}
      ]
    }
  ]
}
```

---

## Event Format Rules

### MANDATORY FORMAT: `namespace:action`

All events MUST follow this pattern:

- **namespace**: Starts with letter, alphanumeric only (e.g., `form`, `view`, `settings`)
- **action**: Starts with letter, can include letters, numbers, underscores, hyphens (e.g., `submit`, `change`, `api-key`)

### Valid Examples

✅ `form:submit`
✅ `view:change`
✅ `settings:api-key`
✅ `counter:increment`
✅ `filter:price-range`

### Invalid Examples

❌ `submit` (no namespace)
❌ `form-submit` (hyphen instead of colon)
❌ `123:action` (namespace starts with number)
❌ `:action` (empty namespace)
❌ `form:` (empty action)

### Reserved Namespaces (DO NOT USE)

- `pywry` - Internal PyWry events
- `plotly` - Plotly chart events (except `plotly:modebar-*`)
- `grid` - AG Grid events

---

## Summary: All Component Types

| Type Value | Component | Primary Event Payload |
|------------|-----------|----------------------|
| `button` | Button | `{componentId, ...data}` |
| `select` | Select | `{value, componentId}` |
| `multiselect` | MultiSelect | `{values: [], componentId}` |
| `toggle` | Toggle | `{value: boolean, componentId}` |
| `checkbox` | Checkbox | `{value: boolean, componentId}` |
| `radio` | RadioGroup | `{value, componentId}` |
| `tabs` | TabGroup | `{value, componentId}` |
| `text` | TextInput | `{value, componentId}` |
| `textarea` | TextArea | `{value, componentId}` |
| `search` | SearchInput | `{value, componentId}` |
| `number` | NumberInput | `{value: number, componentId}` |
| `date` | DateInput | `{value: "YYYY-MM-DD", componentId}` |
| `slider` | SliderInput | `{value: number, componentId}` |
| `range` | RangeInput | `{start, end, componentId}` |
| `secret` | SecretInput | `{value: base64, encoded: true, componentId}` |
| `div` | Div | No events (display only) |
| `marquee` | Marquee | `{value, componentId}` (if clickable) |

---

**END OF REFERENCE. USE THESE EXACT STRUCTURES. NO EXCEPTIONS.**
