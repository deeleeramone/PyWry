"""MCP Resources for PyWry documentation and widget export.

This module handles resource listing, templates, and reading for the MCP server.
"""

from __future__ import annotations

import inspect
import json
import re

from typing import TYPE_CHECKING, Any

from pywry.mcp.docs import BUILTIN_EVENTS, COMPONENT_DOCS
from pywry.mcp.skills import get_skill
from pywry.mcp.state import get_widget_config, list_widget_ids


if TYPE_CHECKING:
    from mcp.types import Resource, ResourceTemplate


def get_component_source(component_name: str) -> str | None:
    """Get source code for a component class from toolbar.py.

    Parameters
    ----------
    component_name : str
        Name of the component (e.g., 'button', 'select').

    Returns
    -------
    str or None
        Source code of the component class or None if not found.
    """
    from pywry import toolbar

    # Map short names to class names
    class_map = {
        "button": "Button",
        "select": "Select",
        "multiselect": "MultiSelect",
        "toggle": "Toggle",
        "checkbox": "Checkbox",
        "radio": "RadioGroup",
        "tabs": "TabGroup",
        "text": "TextInput",
        "textarea": "TextArea",
        "search": "SearchInput",
        "number": "NumberInput",
        "date": "DateInput",
        "slider": "SliderInput",
        "range": "RangeInput",
        "div": "Div",
        "secret": "SecretInput",
        "marquee": "Marquee",
        "ticker_item": "TickerItem",
        "toolbar": "Toolbar",
        "toolbar_item": "ToolbarItem",
        "option": "Option",
    }

    class_name = class_map.get(component_name.lower(), component_name)

    if hasattr(toolbar, class_name):
        cls = getattr(toolbar, class_name)
        try:
            source = inspect.getsource(cls)
        except (OSError, TypeError):
            return None
        # Clean up the source - remove long docstrings
        source = re.sub(r'"""[\s\S]*?"""', '"""...docstring..."""', source, count=1)
        return source
    return None


def export_widget_code(widget_id: str) -> str | None:
    """Generate Python code to recreate a widget.

    Parameters
    ----------
    widget_id : str
        ID of the widget to export.

    Returns
    -------
    str or None
        Python code to recreate the widget or None if not found.
    """
    config = get_widget_config(widget_id)
    if not config:
        return None

    lines = [
        '"""Exported PyWry Widget"""',
        "",
        "from pywry import PyWry",
        "from pywry.toolbar import (",
        "    Button, Checkbox, DateInput, Div, Marquee, MultiSelect,",
        "    NumberInput, Option, RadioGroup, RangeInput, SearchInput,",
        "    SecretInput, Select, SliderInput, TabGroup, TextArea,",
        "    TextInput, TickerItem, Toggle, Toolbar,",
        ")",
        "",
    ]

    # Generate toolbar code
    for i, tb in enumerate(config.get("toolbars", [])):
        items_code = []
        for item in tb.get("items", []):
            item_code = _generate_component_code(item)
            if item_code:
                items_code.append(item_code)

        items_joined = ",\n        ".join(items_code)
        tb_code = f"""toolbar_{i} = Toolbar(
    position="{tb.get("position", "top")}",
    items=[
        {items_joined},
    ]
)"""
        lines.append(tb_code)
        lines.append("")

    # Generate main widget code
    html_content = config.get("html", "")
    toolbars_arg = ", ".join(f"toolbar_{i}" for i in range(len(config.get("toolbars", []))))

    # Escape content for Div
    content_escaped = html_content.replace('"', '\\"').replace("\n", "\\n")

    lines.extend(
        [
            "# Create content using Div component",
            "content = Div(",
            f'    content="{content_escaped}",',
            '    component_id="main-content",',
            '    style="",',
            ")",
            "",
            "# Create the widget",
            "app = PyWry()",
            "widget = app.show(",
            "    html=content.build_html(),",
            f'    title="{config.get("title", "PyWry Widget")}",',
            f"    height={config.get('height', 500)},",
            f"    include_plotly={config.get('include_plotly', False)},",
            f"    include_aggrid={config.get('include_aggrid', False)},",
            f"    toolbars=[{toolbars_arg}] if {bool(toolbars_arg)} else None,",
            ")",
            "",
            "# Event handling example",
            "def on_event(data, event_type, label=''):",
            '    print(f"Event: {event_type}, Data: {data}")',
            "",
            "# Update content dynamically",
            '# widget.emit("pywry:set-content", {"id": "main-content", "text": "New content"})',
            "",
            "# Register event handlers for toolbar items",
            "# widget.on('event:name', on_event)",
            "",
            "# Keep running",
            "# app.block()",
        ]
    )

    return "\n".join(lines)


def _generate_component_code(item: dict[str, Any]) -> str | None:
    """Generate code for a single component."""
    t = item.get("type", "button")

    def format_options(opts: list[dict[str, Any]] | None) -> str:
        return (
            "["
            + ", ".join(
                f'Option(label="{o.get("label", "")}", value="{o.get("value", o.get("label", ""))}")'
                for o in (opts or [])
            )
            + "]"
        )

    if t == "button":
        return f"""Button(
            label="{item.get("label", "Button")}",
            event="{item.get("event", "app:click")}",
            variant="{item.get("variant", "neutral")}",
        )"""

    if t == "select":
        return f"""Select(
            label="{item.get("label", "")}",
            event="{item.get("event", "app:select")}",
            options={format_options(item.get("options"))},
            selected="{item.get("selected", "")}",
        )"""

    if t == "toggle":
        return f"""Toggle(
            label="{item.get("label", "Toggle")}",
            event="{item.get("event", "app:toggle")}",
            value={item.get("value", False)},
        )"""

    if t == "div":
        content = item.get("content", "").replace('"', '\\"')
        return f"""Div(
            content="{content}",
            component_id="{item.get("component_id", "")}",
        )"""

    # Generic fallback
    return f"# {t}: {item}"


def get_resources() -> list[Resource]:
    """Return all MCP resources.

    Returns
    -------
    list of Resource
        All available MCP resources.
    """
    from mcp.types import Resource

    # Component documentation resources
    resources = [
        Resource(
            uri=f"pywry://component/{comp_name}",  # type: ignore[arg-type]
            name=f"Component: {comp_doc['name']}",
            description=comp_doc["description"],
            mimeType="text/markdown",
        )
        for comp_name, comp_doc in COMPONENT_DOCS.items()
    ]

    # Static resources
    resources.extend(
        [
            Resource(
                uri="pywry://docs/events",  # type: ignore[arg-type]
                name="Built-in Events Reference",
                description="Documentation for all built-in PyWry events",
                mimeType="text/markdown",
            ),
            Resource(
                uri="pywry://source/components",  # type: ignore[arg-type]
                name="Component Source Code",
                description="Source code for all PyWry toolbar components",
                mimeType="text/x-python",
            ),
            Resource(
                uri="pywry://docs/quickstart",  # type: ignore[arg-type]
                name="Quick Start Guide",
                description="Getting started with PyWry widgets",
                mimeType="text/markdown",
            ),
        ]
    )

    # Widget export (for active widgets)
    resources.extend(
        [
            Resource(
                uri=f"pywry://export/{widget_id}",  # type: ignore[arg-type]
                name=f"Export: {widget_id}",
                description=f"Python code to recreate widget {widget_id}",
                mimeType="text/x-python",
            )
            for widget_id in list_widget_ids()
        ]
    )

    return resources


def get_resource_templates() -> list[ResourceTemplate]:
    """Return resource templates for parameterized access.

    Returns
    -------
    list of ResourceTemplate
        Available resource templates.
    """
    from mcp.types import ResourceTemplate

    return [
        ResourceTemplate(
            uriTemplate="pywry://component/{component}",
            name="Component Documentation",
            description="Get documentation for a specific component (button, select, toggle, etc.)",
        ),
        ResourceTemplate(
            uriTemplate="pywry://source/{component}",
            name="Component Source Code",
            description="Get source code for a specific component class",
        ),
        ResourceTemplate(
            uriTemplate="pywry://export/{widget_id}",
            name="Widget Export",
            description="Export a created widget as Python code",
        ),
        ResourceTemplate(
            uriTemplate="pywry://skill/{skill}",
            name="Skill Guidance",
            description="Get guidance for a specific skill (css_selectors, styling, native, jupyter, etc.)",
        ),
    ]


def read_component_doc(comp_name: str) -> str | None:
    """Read component documentation.

    Parameters
    ----------
    comp_name : str
        Component name.

    Returns
    -------
    str or None
        Markdown documentation or None if not found.
    """
    doc = COMPONENT_DOCS.get(comp_name)
    if not doc:
        return None

    lines = [
        f"# {doc['name']}",
        "",
        doc["description"],
        "",
        "## Properties",
        "",
    ]
    for prop, desc in doc.get("properties", {}).items():
        lines.append(f"- **{prop}**: {desc}")
    lines.extend(
        [
            "",
            "## Example",
            "",
            "```python",
            doc.get("example", ""),
            "```",
        ]
    )
    return "\n".join(lines)


def read_source_code(comp_name: str) -> str | None:
    """Read component source code.

    Parameters
    ----------
    comp_name : str
        Component name or 'components' for all.

    Returns
    -------
    str or None
        Source code or None if not found.
    """
    if comp_name == "components":
        sources = [
            f"# === {name.upper()} ===\n{source}"
            for name in COMPONENT_DOCS
            if (source := get_component_source(name))
        ]
        return "\n\n".join(sources)
    return get_component_source(comp_name)


def read_events_doc() -> str:
    """Read built-in events documentation.

    Returns
    -------
    str
        Markdown documentation of all built-in events.
    """
    lines = [
        "# Built-in PyWry Events",
        "",
        "These events are handled by the widget runtime and have dedicated MCP tools.",
        "",
    ]
    for event, info in BUILTIN_EVENTS.items():
        lines.extend(
            [
                f"## `{event}`",
                "",
                info["description"],
                "",
                f"**MCP Tool:** `{info['tool']}`",
                "",
                "**Payload:**",
                "```json",
                json.dumps(info["payload"], indent=2),
                "```",
                "",
            ]
        )
    return "\n".join(lines)


def read_skill_doc(skill_name: str) -> str | None:
    """Read skill documentation.

    Parameters
    ----------
    skill_name : str
        Name of the skill.

    Returns
    -------
    str or None
        Skill documentation or None if not found.
    """
    skill = get_skill(skill_name)
    if skill:
        return f"# {skill['name']}\n\n{skill['description']}\n\n{skill['guidance']}"
    return None


def read_quickstart_guide() -> str:
    """Return the quick start guide content.

    Returns
    -------
    str
        Quick start guide markdown.
    """
    return """# PyWry Quick Start Guide

## Creating a Widget

```python
from pywry import PyWry
from pywry.toolbar import Button, Div, Select, Option, Toolbar

app = PyWry()

# Create content using Div component (supports dynamic updates)
content = Div(
    content="Hello World",
    component_id="main-content",
    style="padding: 20px; font-size: 18px;",
    class_name="content-area",
)

# Create toolbar with controls
toolbar = Toolbar(
    position="top",
    items=[
        Button(label="Refresh", event="app:refresh"),
        Select(
            label="View:",
            event="view:change",
            options=[Option(label="Table"), Option(label="Chart")],
            selected="Table"
        ),
    ]
)

# Show widget - content.build_html() generates the HTML
widget = app.show(
    html=content.build_html(),
    title="My Widget",
    toolbars=[toolbar]
)

# Update content later using component_id
widget.emit("pywry:set-content", {"id": "main-content", "text": "Updated!"})
```

## Using Div for Dynamic Content

The `Div` component is the preferred way to create updateable content:

```python
from pywry.toolbar import Div

# Create a Div with all attributes
status_div = Div(
    content="<strong>Status:</strong> Ready",
    component_id="status",  # Required for updates via set_content
    style="color: var(--text-primary); padding: 10px;",
    class_name="status-indicator",
)

# Build HTML string for use in app.show()
html = status_div.build_html()
# Output: <div id="status" class="status-indicator" style="...">...</div>
```

## MCP Tools Overview

### Widget Creation
- `create_widget`: Create with HTML and toolbars
- `show_plotly`: Create Plotly chart
- `show_dataframe`: Create AG Grid table

### Widget Updates
- `set_content`: Update element text/HTML
- `set_style`: Update element styles
- `show_toast`: Show notification
- `update_theme`: Change theme

### Event Handling
- `get_events`: Get pending events
- `send_event`: Send custom event

### Widget Management
- `list_widgets`: List active widgets
- `destroy_widget`: Clean up widget

## Component Types

| Type | Description |
|------|-------------|
| button | Clickable button |
| select | Single-choice dropdown |
| multiselect | Multi-choice dropdown |
| toggle | On/off switch |
| checkbox | Boolean checkbox |
| radio | Radio button group |
| tabs | Tab navigation |
| text | Text input |
| textarea | Multi-line text |
| search | Search with debounce |
| number | Numeric input |
| date | Date picker |
| slider | Single value slider |
| range | Two-handle range |
| div | Dynamic HTML container |
| secret | Password/API key input |
| marquee | Scrolling ticker |
"""


def read_resource(uri: str) -> str | None:
    """Read resource content by URI.

    Parameters
    ----------
    uri : str
        Resource URI (e.g., 'pywry://component/button').

    Returns
    -------
    str or None
        Resource content or None if not found.
    """
    # Use dispatch table for cleaner routing
    handlers: dict[str, tuple[str, Any]] = {
        "pywry://component/": ("prefix", read_component_doc),
        "pywry://source/": ("prefix", read_source_code),
        "pywry://export/": ("prefix", export_widget_code),
        "pywry://skill/": ("prefix", read_skill_doc),
        "pywry://docs/events": ("exact", read_events_doc),
        "pywry://docs/quickstart": ("exact", read_quickstart_guide),
    }

    for pattern, (match_type, handler) in handlers.items():
        if match_type == "exact" and uri == pattern:
            return handler()  # type: ignore[no-any-return]
        if match_type == "prefix" and uri.startswith(pattern):
            return handler(uri.replace(pattern, ""))  # type: ignore[no-any-return]

    return None
