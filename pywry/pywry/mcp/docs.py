"""Component and event documentation for MCP resources.

This module contains the static documentation for all PyWry components
and built-in events, used by the MCP resource system.
"""

from __future__ import annotations

from typing import Any


# Component documentation with usage examples
COMPONENT_DOCS: dict[str, dict[str, Any]] = {
    "button": {
        "name": "Button",
        "description": "Clickable button that emits an event with optional data payload",
        "properties": {
            "label": "Button text",
            "event": "Event name to emit on click",
            "variant": "primary|neutral|danger|success|ghost|outline|icon|warning",
            "size": "xs|sm|md|lg|xl (optional)",
            "data": "dict - Extra data to include in event",
            "disabled": "bool - Whether button is disabled",
        },
        "example": """Button(
    label="Export CSV",
    event="export:csv",
    variant="primary",
    data={"format": "csv"}
)""",
    },
    "select": {
        "name": "Select",
        "description": "Single-choice dropdown with searchable option",
        "properties": {
            "label": "Label text",
            "event": "Event name on selection change",
            "options": "list[Option] - Available choices",
            "selected": "Currently selected value",
            "searchable": "bool - Enable search filtering",
            "placeholder": "Placeholder text",
        },
        "example": """Select(
    label="Country",
    event="form:country",
    options=[
        Option(label="USA", value="us"),
        Option(label="Canada", value="ca"),
    ],
    selected="us",
    searchable=True
)""",
    },
    "multiselect": {
        "name": "MultiSelect",
        "description": "Multiple-choice dropdown",
        "properties": {
            "label": "Label text",
            "event": "Event name on selection change",
            "options": "list[Option] - Available choices",
            "selected": "list[str] - Currently selected values",
        },
        "example": """MultiSelect(
    label="Tags",
    event="form:tags",
    options=[Option(label="Python"), Option(label="JavaScript"), Option(label="Rust")],
    selected=["Python"]
)""",
    },
    "toggle": {
        "name": "Toggle",
        "description": "On/off switch",
        "properties": {
            "label": "Label text",
            "event": "Event name on toggle",
            "value": "bool - Current state",
        },
        "example": """Toggle(
    label="Dark Mode",
    event="settings:darkmode",
    value=True
)""",
    },
    "checkbox": {
        "name": "Checkbox",
        "description": "Boolean checkbox",
        "properties": {
            "label": "Label text",
            "event": "Event name on change",
            "value": "bool - Checked state",
            "disabled": "bool - Whether disabled",
        },
        "example": """Checkbox(
    label="I agree to terms",
    event="form:agree",
    value=False
)""",
    },
    "radio": {
        "name": "RadioGroup",
        "description": "Single-choice visible radio buttons",
        "properties": {
            "label": "Group label",
            "event": "Event name on selection",
            "options": "list[Option] - Available choices",
            "selected": "Currently selected value",
            "direction": "horizontal|vertical",
        },
        "example": """RadioGroup(
    label="Size",
    event="product:size",
    options=[Option(label="S"), Option(label="M"), Option(label="L")],
    selected="M",
    direction="horizontal"
)""",
    },
    "tabs": {
        "name": "TabGroup",
        "description": "Tab-style navigation",
        "properties": {
            "event": "Event name on tab change",
            "options": "list[Option] - Tab options",
            "selected": "Currently selected tab value",
            "size": "sm|md|lg",
        },
        "example": """TabGroup(
    event="view:tab",
    options=[Option(label="Chart"), Option(label="Table"), Option(label="Settings")],
    selected="Chart"
)""",
    },
    "text": {
        "name": "TextInput",
        "description": "Single-line text input",
        "properties": {
            "label": "Label text",
            "event": "Event name on input",
            "value": "Current text value",
            "placeholder": "Placeholder text",
        },
        "example": """TextInput(
    label="Name",
    event="form:name",
    placeholder="Enter your name"
)""",
    },
    "textarea": {
        "name": "TextArea",
        "description": "Multi-line text input",
        "properties": {
            "label": "Label text",
            "event": "Event name on input",
            "value": "Current text value",
            "placeholder": "Placeholder text",
            "rows": "int - Number of visible rows",
        },
        "example": """TextArea(
    label="Description",
    event="form:description",
    rows=5,
    placeholder="Enter description..."
)""",
    },
    "search": {
        "name": "SearchInput",
        "description": "Search input with debounce",
        "properties": {
            "label": "Label text",
            "event": "Event name on search",
            "value": "Current search value",
            "placeholder": "Placeholder text",
            "debounce": "int - Debounce delay in ms",
        },
        "example": """SearchInput(
    label="Search",
    event="data:search",
    placeholder="Search...",
    debounce=300
)""",
    },
    "number": {
        "name": "NumberInput",
        "description": "Numeric input with min/max/step",
        "properties": {
            "label": "Label text",
            "event": "Event name on change",
            "value": "Current number value",
            "min": "Minimum value",
            "max": "Maximum value",
            "step": "Step increment",
        },
        "example": """NumberInput(
    label="Quantity",
    event="cart:quantity",
    value=1,
    min=1,
    max=100,
    step=1
)""",
    },
    "date": {
        "name": "DateInput",
        "description": "Date picker",
        "properties": {
            "label": "Label text",
            "event": "Event name on change",
            "value": "Current date (YYYY-MM-DD)",
            "min": "Minimum date",
            "max": "Maximum date",
        },
        "example": """DateInput(
    label="Start Date",
    event="report:startdate",
    value="2025-01-01",
    min="2020-01-01"
)""",
    },
    "slider": {
        "name": "SliderInput",
        "description": "Single-value slider",
        "properties": {
            "label": "Label text",
            "event": "Event name on change",
            "value": "Current value",
            "min": "Minimum value",
            "max": "Maximum value",
            "step": "Step increment",
            "show_value": "bool - Show current value",
        },
        "example": """SliderInput(
    label="Volume",
    event="audio:volume",
    value=50,
    min=0,
    max=100,
    show_value=True
)""",
    },
    "range": {
        "name": "RangeInput",
        "description": "Two-handle range slider",
        "properties": {
            "label": "Label text",
            "event": "Event name on change",
            "start": "Start value",
            "end": "End value",
            "min": "Minimum value",
            "max": "Maximum value",
            "step": "Step increment",
            "show_value": "bool - Show current values",
        },
        "example": """RangeInput(
    label="Price Range",
    event="filter:price",
    start=100,
    end=500,
    min=0,
    max=1000,
    step=10,
    show_value=True
)""",
    },
    "div": {
        "name": "Div",
        "description": "Container for dynamic HTML content",
        "properties": {
            "content": "HTML content",
            "component_id": "ID for set_content updates",
            "style": "Inline CSS styles",
            "class_name": "CSS class name",
        },
        "example": """Div(
    content="<strong>Loading...</strong>",
    component_id="status-display",
    style="padding: 10px; color: var(--text-primary);"
)""",
    },
    "secret": {
        "name": "SecretInput",
        "description": "Password/API key input with reveal/copy",
        "properties": {
            "label": "Label text",
            "event": "Event name (also emits event:reveal, event:copy)",
            "value": "SecretStr - The secret value",
            "placeholder": "Placeholder text",
            "show_toggle": "bool - Show reveal toggle",
            "show_copy": "bool - Show copy button",
        },
        "example": """SecretInput(
    label="API Key",
    event="settings:apikey",
    placeholder="Enter API key...",
    show_toggle=True,
    show_copy=True
)""",
    },
    "marquee": {
        "name": "Marquee",
        "description": "Scrolling text/ticker component",
        "properties": {
            "text": "Text or HTML content",
            "event": "Event name on click (if clickable)",
            "speed": "Animation speed in seconds",
            "direction": "left|right|up|down",
            "behavior": "scroll|alternate|slide|static",
            "pause_on_hover": "bool - Pause on hover",
            "gap": "int - Gap between repeated content",
            "clickable": "bool - Whether clickable",
            "separator": "Separator between repeats",
            "ticker_items": "list[TickerItem] - For stock tickers",
        },
        "example": """Marquee(
    text="Breaking News: Markets rally...",
    speed=15,
    direction="left",
    pause_on_hover=True
)""",
    },
    "ticker_item": {
        "name": "TickerItem",
        "description": "Individual ticker for Marquee updates",
        "properties": {
            "ticker": "Unique ID for updates",
            "text": "Display text",
            "html": "Custom HTML (overrides text)",
            "class_name": "CSS class",
            "style": "Inline styles",
        },
        "example": """TickerItem(
    ticker="AAPL",
    text="AAPL $185.50 ▲1.2%",
    style="color: #22c55e;"
)

# Update later with:
update_ticker_item(widget_id, ticker="AAPL",
    text="AAPL $186.00 ▲1.5%",
    styles={"color": "#22c55e"})""",
    },
}

# Built-in events documentation
BUILTIN_EVENTS: dict[str, dict[str, Any]] = {
    "pywry:set-content": {
        "description": "Update element text/HTML by component ID",
        "tool": "set_content",
        "payload": {"id": "component_id", "text": "new text", "html": "or html"},
    },
    "pywry:set-style": {
        "description": "Update element CSS styles by component ID",
        "tool": "set_style",
        "payload": {"id": "component_id", "styles": {"color": "red"}},
    },
    "pywry:alert": {
        "description": "Show toast notification",
        "tool": "show_toast",
        "payload": {"message": "text", "type": "success|error|info|warning"},
    },
    "pywry:update-theme": {
        "description": "Switch widget theme",
        "tool": "update_theme",
        "payload": {"theme": "dark|light|system"},
    },
    "pywry:inject-css": {
        "description": "Inject CSS styles",
        "tool": "inject_css",
        "payload": {"css": "styles", "id": "optional-id"},
    },
    "pywry:remove-css": {
        "description": "Remove injected CSS",
        "tool": "remove_css",
        "payload": {"id": "css-id"},
    },
    "pywry:navigate": {
        "description": "Client-side navigation",
        "tool": "navigate",
        "payload": {"url": "https://..."},
    },
    "pywry:download": {
        "description": "Trigger file download",
        "tool": "download",
        "payload": {
            "content": "data",
            "filename": "file.txt",
            "mimeType": "text/plain",
        },
    },
    "plotly:update-figure": {
        "description": "Update Plotly chart data and layout",
        "tool": "update_plotly",
        "payload": {"data": [], "layout": {}},
    },
    "plotly:update-layout": {
        "description": "Update Plotly layout only (faster)",
        "tool": "update_plotly (layout_only=True)",
        "payload": {"layout": {}},
    },
    "toolbar:marquee-set-content": {
        "description": "Update marquee text/speed",
        "tool": "update_marquee",
        "payload": {"id": "marquee-id", "text": "new text", "speed": 10},
    },
    "toolbar:marquee-set-item": {
        "description": "Update individual ticker item",
        "tool": "update_ticker_item",
        "payload": {"ticker": "AAPL", "text": "new text", "styles": {}},
    },
}

# Supported component types for tool schemas
COMPONENT_TYPES: list[str] = [
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
