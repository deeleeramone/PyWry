"""MCP tool definitions for PyWry v2.0.0.

This module provides all tool schemas and the get_tools function
for the MCP server.
"""

from mcp.types import Tool

from .docs import COMPONENT_DOCS
from .skills import list_skills


# =============================================================================
# Component Types
# =============================================================================

COMPONENT_TYPES = [
    "button",
    "select",
    "multiselect",
    "toggle",
    "checkbox",
    "radio",
    "tabs",
    "text",
    "textarea",
    "search",
    "number",
    "date",
    "slider",
    "range",
    "div",
    "secret",
    "marquee",
]

# =============================================================================
# Tool Schemas
# =============================================================================

TOOLBAR_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "type": {
            "type": "string",
            "enum": COMPONENT_TYPES,
            "description": "Component type",
        },
        "label": {"type": "string", "description": "Label text"},
        "event": {"type": "string", "description": "Event name to emit on interaction"},
        "value": {"description": "Current value (type depends on component)"},
        "options": {
            "type": "array",
            "description": "Options for select/multiselect/radio/tabs",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "value": {"type": "string"},
                },
            },
        },
        "selected": {"description": "Selected value(s)"},
        "placeholder": {"type": "string"},
        "disabled": {"type": "boolean", "default": False},
        "variant": {
            "type": "string",
            "enum": ["primary", "neutral", "danger", "success"],
        },
        "size": {"type": "string", "enum": ["sm", "md", "lg"]},
        "min": {"type": "number"},
        "max": {"type": "number"},
        "step": {"type": "number"},
        "rows": {"type": "integer", "description": "Rows for textarea"},
        "debounce": {"type": "integer", "description": "Debounce ms for search/inputs"},
        "show_value": {"type": "boolean", "description": "Show value for slider/range"},
        "direction": {
            "type": "string",
            "enum": ["horizontal", "vertical", "left", "right", "up", "down"],
        },
        "content": {"type": "string", "description": "HTML content for div"},
        "component_id": {
            "type": "string",
            "description": "ID for div (for set_content)",
        },
        "style": {"type": "string", "description": "Inline CSS styles"},
        "class_name": {"type": "string", "description": "CSS class name"},
        "data": {"type": "object", "description": "Extra data to include in events"},
        # RangeInput properties
        "start": {"type": "number", "description": "Start value for range slider"},
        "end": {"type": "number", "description": "End value for range slider"},
        # SecretInput properties
        "show_toggle": {
            "type": "boolean",
            "description": "Show visibility toggle for secret",
        },
        "show_copy": {"type": "boolean", "description": "Show copy button for secret"},
        # Marquee properties
        "text": {"type": "string", "description": "Scrolling text for marquee"},
        "speed": {"type": "number", "description": "Animation speed in seconds"},
        "behavior": {
            "type": "string",
            "enum": ["scroll", "alternate", "slide", "static"],
        },
        "pause_on_hover": {
            "type": "boolean",
            "description": "Pause on hover for marquee",
        },
        "gap": {
            "type": "integer",
            "description": "Gap between repeated content for marquee",
        },
        "clickable": {"type": "boolean", "description": "Whether marquee is clickable"},
        "separator": {
            "type": "string",
            "description": "Separator between repeated content",
        },
        "ticker_items": {
            "type": "array",
            "description": "Ticker items for marquee (auto-builds HTML)",
            "items": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Unique ID for updates",
                    },
                    "text": {"type": "string"},
                    "html": {"type": "string"},
                    "class_name": {"type": "string"},
                    "style": {"type": "string"},
                },
            },
        },
    },
    "required": ["type"],
}

TOOLBAR_SCHEMA = {
    "type": "object",
    "properties": {
        "position": {
            "type": "string",
            "enum": ["top", "bottom", "left", "right", "inside"],
            "default": "top",
        },
        "items": {
            "type": "array",
            "items": TOOLBAR_ITEM_SCHEMA,
        },
        "class_name": {"type": "string"},
    },
}


def get_tools() -> list[Tool]:
    """Return all MCP tools with complete schemas.

    Returns
    -------
    list[Tool]
        List of all available MCP tools.

    """
    return [
        # =====================================================================
        # Skills / Context Discovery
        # =====================================================================
        Tool(
            name="get_skills",
            description="""Get context-appropriate skills and guidance for creating widgets.

⚠️ **MANDATORY FIRST STEP**: Call this with skill="component_reference" BEFORE creating ANY widget.
The component_reference contains the ONLY correct event signatures and system events.

**System Events for Updates (from component_reference):**
- `grid:update-data` with `{"data": [...], "strategy": "set|append|update"}`
- `grid:request-state` / `grid:restore-state` / `grid:reset-state` for state persistence
- `plotly:update-figure` with `{"data": [...], "layout": {...}}`
- `plotly:request-state` for chart state persistence
- `pywry:set-content` with `{"id": "...", "text": "..."}` or `{"id": "...", "html": "..."}`
- `pywry:update-theme` with `{"theme": "dark|light|system"}`
- `toolbar:set-value` / `toolbar:request-state` for toolbar component state

Available skills:
- **component_reference** (MANDATORY): Complete reference for ALL 18 component types, system events, and exact event signatures
- **interactive_buttons**: How to make buttons work automatically with auto-wired callbacks
- native: Desktop window with full control
- jupyter: Inline widgets in notebook cells
- iframe: Embedded in external web pages
- deploy: Production multi-user server
- data_visualization: Charts, tables, live data
- forms_and_inputs: User input collection

Call without arguments to list all skills, or specify a skill name.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "skill": {
                        "type": "string",
                        "description": "Specific skill to retrieve (optional)",
                        "enum": [s["id"] for s in list_skills()],
                    },
                },
            },
        ),
        # =====================================================================
        # Widget Creation
        # =====================================================================
        Tool(
            name="create_widget",
            description="""Create an interactive native window with HTML content and Pydantic toolbar components.

⚠️ **CALL get_skills(skill="component_reference") FIRST** for complete documentation.

**MANDATORY SYNTAX** - Use EXACTLY this structure:

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

**BUTTON EVENTS AUTO-WIRE** when following pattern `elementId:action`:
- `counter:increment` → adds 1 to element with id="counter"
- `counter:decrement` → subtracts 1
- `counter:reset` → sets to 0
- `status:toggle` → toggles true/false

**ALL COMPONENT TYPES AND EVENT SIGNATURES**:

| Type | Event Payload | Required Props |
|------|--------------|----------------|
| button | `{componentId, ...data}` | label, event |
| select | `{value, componentId}` | event, options |
| multiselect | `{values: [], componentId}` | event, options |
| toggle | `{value: boolean, componentId}` | event |
| checkbox | `{value: boolean, componentId}` | event, label |
| radio | `{value, componentId}` | event, options |
| tabs | `{value, componentId}` | event, options |
| text | `{value, componentId}` | event |
| textarea | `{value, componentId}` | event |
| search | `{value, componentId}` | event |
| number | `{value: number, componentId}` | event |
| date | `{value: "YYYY-MM-DD", componentId}` | event |
| slider | `{value: number, componentId}` | event |
| range | `{start, end, componentId}` | event |
| secret | `{value: base64, encoded: true, componentId}` | event |
| div | NO EVENTS | content |
| marquee | `{value, componentId}` (if clickable) | text |

**EVENT FORMAT RULES**:
- MUST be `namespace:action` format (e.g., `form:submit`, `view:change`)
- Reserved namespaces (DO NOT USE): `pywry`, `plotly`, `grid`

**OPTIONS FORMAT** (for select/multiselect/radio/tabs):
```json
"options": [{"label": "Dark", "value": "dark"}, {"label": "Light", "value": "light"}]
```

**TOOLBAR POSITIONS**: top, bottom, left, right, header, footer, inside""",
            inputSchema={
                "type": "object",
                "properties": {
                    "html": {
                        "type": "string",
                        "description": "HTML content. Use Div component for dynamic content.",
                    },
                    "title": {"type": "string", "default": "PyWry Widget"},
                    "height": {"type": "integer", "default": 500},
                    "include_plotly": {"type": "boolean", "default": False},
                    "include_aggrid": {"type": "boolean", "default": False},
                    "toolbars": {
                        "type": "array",
                        "description": "Toolbars with components",
                        "items": TOOLBAR_SCHEMA,
                    },
                    "callbacks": {
                        "type": "object",
                        "description": "Map of event names to callback actions",
                        "additionalProperties": {
                            "type": "object",
                            "properties": {
                                "action": {
                                    "type": "string",
                                    "enum": [
                                        "increment",
                                        "decrement",
                                        "set",
                                        "toggle",
                                        "emit",
                                    ],
                                    "description": "Action type",
                                },
                                "target": {
                                    "type": "string",
                                    "description": "component_id to update",
                                },
                                "state_key": {
                                    "type": "string",
                                    "description": "Key in widget state to track",
                                },
                                "value": {
                                    "description": "Value for set action",
                                },
                                "emit_event": {
                                    "type": "string",
                                    "description": "Event to emit (for emit action)",
                                },
                                "emit_data": {
                                    "type": "object",
                                    "description": "Data to emit with event",
                                },
                            },
                        },
                    },
                },
                "required": ["html"],
            },
        ),
        Tool(
            name="build_div",
            description="""Build a Div component HTML string. Use component_id to update later.

**MANDATORY SYNTAX**:
```json
{"content": "0", "component_id": "counter", "style": "font-size:48px;text-align:center"}
```

Returns: `{"html": "<div id=\"counter\" style=\"...\">0</div>"}`

Use the returned html in create_widget's html parameter.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Text or HTML content",
                    },
                    "component_id": {
                        "type": "string",
                        "description": "ID for updates via set_content",
                    },
                    "style": {"type": "string", "description": "Inline CSS styles"},
                    "class_name": {"type": "string", "description": "CSS class name"},
                },
                "required": ["content"],
            },
        ),
        Tool(
            name="build_ticker_item",
            description="""Build a TickerItem for Marquee. Can be updated dynamically via update_ticker_item.

**MANDATORY SYNTAX**:
```json
{"ticker": "AAPL", "text": "AAPL: $150.00", "style": "color: green"}
```

Returns HTML span with data-ticker attribute for targeting updates.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Unique ID for targeting updates (e.g., 'AAPL', 'BTC')",
                    },
                    "text": {"type": "string", "description": "Display text"},
                    "html": {
                        "type": "string",
                        "description": "HTML content (overrides text)",
                    },
                    "class_name": {"type": "string", "description": "CSS classes"},
                    "style": {"type": "string", "description": "Inline CSS styles"},
                },
                "required": ["ticker"],
            },
        ),
        Tool(
            name="show_plotly",
            description="""Create a Plotly chart widget. Pass figure JSON from fig.to_json().

**To update the chart later**, use `send_event` with:
- event_type: `plotly:update-figure`
- data: `{"data": [...], "layout": {...}}`

Or use `update_plotly` tool with new figure_json.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "figure_json": {
                        "type": "string",
                        "description": "Plotly figure as JSON",
                    },
                    "title": {"type": "string", "default": "Plotly Chart"},
                    "height": {"type": "integer", "default": 500},
                },
                "required": ["figure_json"],
            },
        ),
        Tool(
            name="show_dataframe",
            description="""Create an AG Grid table widget from JSON data.

**To update the grid data later**, use `send_event` with:
- event_type: `grid:update-data`
- data: `{"data": [...new rows...], "strategy": "set"}`

Strategy options: "set" (replace all), "append" (add rows), "update" (update existing)""",
            inputSchema={
                "type": "object",
                "properties": {
                    "data_json": {
                        "type": "string",
                        "description": "Data as JSON array of objects",
                    },
                    "title": {"type": "string", "default": "Data Table"},
                    "height": {"type": "integer", "default": 500},
                },
                "required": ["data_json"],
            },
        ),
        # =====================================================================
        # Widget Manipulation
        # =====================================================================
        Tool(
            name="set_content",
            description="""Update element text/HTML by component_id.

Uses pywry:set-content event. The element must have a component_id set
(e.g., via Div component or id attribute in HTML).""",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "component_id": {
                        "type": "string",
                        "description": "Element ID to update",
                    },
                    "text": {"type": "string", "description": "New text content"},
                    "html": {
                        "type": "string",
                        "description": "New HTML content (overrides text)",
                    },
                },
                "required": ["widget_id", "component_id"],
            },
        ),
        Tool(
            name="set_style",
            description="""Update element CSS styles by component_id.

Uses pywry:set-style event. Pass styles as camelCase properties.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "component_id": {
                        "type": "string",
                        "description": "Element ID to update",
                    },
                    "styles": {
                        "type": "object",
                        "description": "CSS styles as {property: value}",
                        "additionalProperties": {"type": "string"},
                    },
                },
                "required": ["widget_id", "component_id", "styles"],
            },
        ),
        Tool(
            name="show_toast",
            description="Display a toast notification in the widget.",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "message": {"type": "string"},
                    "type": {
                        "type": "string",
                        "enum": ["info", "success", "warning", "error"],
                        "default": "info",
                    },
                    "duration": {"type": "integer", "default": 3000},
                },
                "required": ["widget_id", "message"],
            },
        ),
        Tool(
            name="update_theme",
            description="Switch widget theme to dark/light/system.",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "theme": {
                        "type": "string",
                        "enum": ["dark", "light", "system"],
                    },
                },
                "required": ["widget_id", "theme"],
            },
        ),
        Tool(
            name="inject_css",
            description="""Inject CSS styles into a widget.

Creates or updates a <style> element with the given CSS.
Use a unique style_id to update the same styles later.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "css": {"type": "string", "description": "CSS rules to inject"},
                    "style_id": {
                        "type": "string",
                        "description": "Unique ID for the style element (for updates)",
                        "default": "pywry-injected-style",
                    },
                },
                "required": ["widget_id", "css"],
            },
        ),
        Tool(
            name="remove_css",
            description="Remove previously injected CSS by style_id.",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "style_id": {
                        "type": "string",
                        "description": "ID of style element to remove",
                    },
                },
                "required": ["widget_id", "style_id"],
            },
        ),
        Tool(
            name="navigate",
            description="Navigate the widget to a new URL (client-side redirect).",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "url": {"type": "string", "description": "URL to navigate to"},
                },
                "required": ["widget_id", "url"],
            },
        ),
        Tool(
            name="download",
            description="Trigger a file download in the browser.",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "content": {"type": "string", "description": "File content"},
                    "filename": {"type": "string", "description": "Download filename"},
                    "mime_type": {
                        "type": "string",
                        "description": "MIME type (e.g., text/csv, application/json)",
                        "default": "application/octet-stream",
                    },
                },
                "required": ["widget_id", "content", "filename"],
            },
        ),
        Tool(
            name="update_plotly",
            description="Update an existing Plotly chart with new data/layout.",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "figure_json": {
                        "type": "string",
                        "description": "New figure JSON from fig.to_json()",
                    },
                    "layout_only": {
                        "type": "boolean",
                        "description": "If true, only update layout (not data)",
                        "default": False,
                    },
                },
                "required": ["widget_id", "figure_json"],
            },
        ),
        Tool(
            name="update_marquee",
            description="""Update marquee content, speed, or state.

Can update text, individual ticker items, speed, or pause/resume animation.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "component_id": {
                        "type": "string",
                        "description": "Marquee component ID",
                    },
                    "text": {"type": "string", "description": "New text content"},
                    "html": {"type": "string", "description": "New HTML content"},
                    "speed": {
                        "type": "number",
                        "description": "New animation speed in seconds",
                    },
                    "paused": {
                        "type": "boolean",
                        "description": "Pause/resume animation",
                    },
                    "ticker_update": {
                        "type": "object",
                        "description": "Update a single ticker item",
                        "properties": {
                            "ticker": {
                                "type": "string",
                                "description": "Ticker ID to update",
                            },
                            "text": {"type": "string"},
                            "html": {"type": "string"},
                            "styles": {"type": "object"},
                            "class_add": {"type": "string"},
                            "class_remove": {"type": "string"},
                        },
                    },
                },
                "required": ["widget_id", "component_id"],
            },
        ),
        Tool(
            name="update_ticker_item",
            description="""Update a single ticker item in a Marquee by its ticker ID.

Uses TickerItem.update_payload() pattern to generate the event.
Updates ALL elements matching the ticker (handles duplicated marquee content).""",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "ticker": {
                        "type": "string",
                        "description": "Ticker ID to update (e.g., 'AAPL', 'BTC')",
                    },
                    "text": {"type": "string", "description": "New text content"},
                    "html": {"type": "string", "description": "New HTML content"},
                    "styles": {
                        "type": "object",
                        "description": "CSS styles to apply (e.g., {color: 'green'})",
                        "additionalProperties": {"type": "string"},
                    },
                    "class_add": {
                        "description": "CSS class(es) to add",
                        "oneOf": [
                            {"type": "string"},
                            {"type": "array", "items": {"type": "string"}},
                        ],
                    },
                    "class_remove": {
                        "description": "CSS class(es) to remove",
                        "oneOf": [
                            {"type": "string"},
                            {"type": "array", "items": {"type": "string"}},
                        ],
                    },
                },
                "required": ["widget_id", "ticker"],
            },
        ),
        # =====================================================================
        # Widget Management
        # =====================================================================
        Tool(
            name="list_widgets",
            description="List all active widgets with their URLs.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_events",
            description="""Get events from a widget (button clicks, input changes, etc.).

Events include: event_type, data, and label. Use clear=true to clear after reading.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "clear": {"type": "boolean", "default": False},
                },
                "required": ["widget_id"],
            },
        ),
        Tool(
            name="destroy_widget",
            description="Destroy a widget and clean up resources.",
            inputSchema={
                "type": "object",
                "properties": {"widget_id": {"type": "string"}},
                "required": ["widget_id"],
            },
        ),
        Tool(
            name="send_event",
            description="""Send a custom event to a widget.

**AG Grid Data Updates (CRITICAL - use these exact formats):**
- grid:update-data: {"data": [...rows...], "strategy": "set"} - Replace all data
- grid:update-data: {"data": [...rows...], "strategy": "append"} - Append rows
- grid:update-data: {"data": [...rows...], "strategy": "update"} - Update existing
- grid:update-columns: {"columnDefs": [...]} - Update columns
- grid:update-cell: {"rowId": "row-1", "colId": "price", "value": 99.50} - Update cell

**AG Grid State Persistence:**
- grid:request-state: {} - Request state (response via grid:state-response)
- grid:restore-state: {"state": {...savedState...}} - Restore saved state
- grid:reset-state: {"hard": false} - Soft reset (keeps columns)
- grid:reset-state: {"hard": true} - Hard reset (full reset)

**Plotly Chart Updates:**
- plotly:update-figure: {"data": [...], "layout": {...}, "config": {...}}
- plotly:update-layout: {"layout": {...}}
- plotly:reset-zoom: {} - Reset chart zoom

**Plotly State Persistence:**
- plotly:request-state: {} - Request state (response via plotly:state-response)
- plotly:export-data: {} - Export data (response via plotly:export-response)

**Toolbar Component State (Get/Set Values):**
- toolbar:set-value: {"componentId": "my-select", "value": "option2"} - Set one
- toolbar:set-values: {"values": {"id1": "v1", "id2": true}} - Set multiple
- toolbar:request-state: {} - Request all values (response via toolbar:state-response)

**DOM Content Updates:**
- pywry:set-content: {"id": "elementId", "text": "..."} or {"id": "elementId", "html": "..."}
- pywry:set-style: {"id": "elementId", "styles": {"color": "red", "fontSize": "18px"}}

**Theme Updates:**
- pywry:update-theme: {"theme": "dark"} or {"theme": "light"} or {"theme": "system"}

**Other Events:**
- pywry:alert: {"message": "...", "type": "info|success|warning|error"}
- pywry:navigate: {"url": "https://..."}
- pywry:download: {"content": "...", "filename": "file.txt", "mimeType": "text/plain"}
- toolbar:marquee-set-item: {"ticker": "AAPL", "text": "AAPL $185", "styles": {"color": "green"}}""",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {"type": "string"},
                    "event_type": {"type": "string"},
                    "data": {"type": "object"},
                },
                "required": ["widget_id", "event_type", "data"],
            },
        ),
        # =====================================================================
        # Resources / Export
        # =====================================================================
        Tool(
            name="get_component_docs",
            description="""Get documentation for a PyWry component.

Returns detailed documentation including properties and usage examples.
Available components: button, select, multiselect, toggle, checkbox, radio,
tabs, text, textarea, search, number, date, slider, range, div, secret,
marquee, ticker_item.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "component": {
                        "type": "string",
                        "description": "Component name",
                        "enum": list(COMPONENT_DOCS.keys()),
                    },
                },
                "required": ["component"],
            },
        ),
        Tool(
            name="get_component_source",
            description="""Get source code for a PyWry component class.

Returns the Python source code for implementing the component.
Useful for understanding implementation details or extending components.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "component": {
                        "type": "string",
                        "description": "Component name",
                        "enum": [*list(COMPONENT_DOCS.keys()), "toolbar", "option"],
                    },
                },
                "required": ["component"],
            },
        ),
        Tool(
            name="export_widget",
            description="""Export a created widget as Python code.

Generates standalone Python code that recreates the widget without MCP.
Use this to save your work or share widget implementations.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "widget_id": {
                        "type": "string",
                        "description": "ID of the widget to export",
                    },
                },
                "required": ["widget_id"],
            },
        ),
        Tool(
            name="list_resources",
            description="""List all available resources.

Returns URIs for:
- Component documentation (pywry://component/{name})
- Component source code (pywry://source/{name})
- Widget exports (pywry://export/{widget_id})
- Built-in events reference (pywry://docs/events)
- Quick start guide (pywry://docs/quickstart)""",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]
