"""End-to-end tests for MCP server implementation.

These are REAL tests that actually:
- Create a real FastMCP server via ``create_server()``
- Connect a FastMCP ``Client`` over in-memory MCP transport
- Call tools through the MCP JSON-RPC protocol
- Read resources through the MCP protocol
- Get prompts (skills) through the MCP protocol
- Verify results returned through the full protocol stack

Run with: pytest tests/test_mcp_e2e.py -v
"""

# pylint: disable=too-many-lines,redefined-outer-name, unused-argument
# pylint: disable=E1121

from __future__ import annotations

import json
import os

from typing import Any

import pytest


# Check if MCP + fastmcp are available
try:
    import mcp  # noqa: F401  # pylint: disable=unused-import

    from fastmcp import Client  # noqa: F401  # pylint: disable=unused-import

    HAS_MCP = True
except ImportError:
    HAS_MCP = False


pytestmark = pytest.mark.skipif(not HAS_MCP, reason="mcp/fastmcp packages not installed")


# =============================================================================
# Helpers
# =============================================================================


def _parse_tool_result(result: Any) -> dict[str, Any]:
    """Extract and parse JSON from a CallToolResult returned by Client.call_tool()."""
    text = result.content[0].text
    return json.loads(text)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def clean_state():
    """Clean all PyWry state before and after each test."""
    from pywry.mcp import state
    from pywry.mcp.server import _events

    # Store originals
    original_app = state._app
    original_widgets = state._widgets.copy()
    original_configs = state._widget_configs.copy()
    original_headless = os.environ.get("PYWRY_HEADLESS")

    # Clean state
    state._app = None
    state._widgets.clear()
    state._widget_configs.clear()
    _events.clear()
    os.environ["PYWRY_HEADLESS"] = "1"

    yield

    # Restore
    state._app = original_app
    state._widgets.clear()
    state._widgets.update(original_widgets)
    state._widget_configs.clear()
    state._widget_configs.update(original_configs)
    _events.clear()

    if original_headless is None:
        os.environ.pop("PYWRY_HEADLESS", None)
    else:
        os.environ["PYWRY_HEADLESS"] = original_headless


@pytest.fixture
async def mcp_client(clean_state):
    """Create a real MCP server and connect a Client via in-memory transport.

    This exercises the full MCP protocol: JSON-RPC serialisation, tool schema
    validation, content-type wrapping, etc.
    """
    from fastmcp import Client

    from pywry.mcp.server import create_server

    server = create_server()
    async with Client(server) as client:
        yield client


# =============================================================================
# Server Lifecycle Tests
# =============================================================================


class TestMCPServerLifecycle:
    """Test real MCP server initialisation and capability discovery."""

    @pytest.mark.asyncio
    async def test_server_ping(self, mcp_client):
        """Server responds to MCP ping."""
        await mcp_client.ping()

    @pytest.mark.asyncio
    async def test_list_tools(self, mcp_client):
        """Server advertises all registered tools."""
        tools = await mcp_client.list_tools()
        tool_names = {t.name for t in tools}

        # Core tools must be present
        for expected in (
            "create_widget",
            "list_widgets",
            "destroy_widget",
            "get_events",
            "set_content",
            "set_style",
            "export_widget",
            "get_skills",
        ):
            assert expected in tool_names, f"Missing tool: {expected}"

    @pytest.mark.asyncio
    async def test_list_resources(self, mcp_client):
        """Server advertises registered resources."""
        resources = await mcp_client.list_resources()
        uris = {str(r.uri) for r in resources}

        # Component docs and skill resources should be present
        assert any("component" in u for u in uris), f"No component resources in {uris}"
        assert any("skill" in u for u in uris), f"No skill resources in {uris}"

    @pytest.mark.asyncio
    async def test_list_prompts(self, mcp_client):
        """Server advertises skills as MCP resources via skill:// URI scheme."""
        resources = await mcp_client.list_resources()
        uris = {str(r.uri) for r in resources}

        # Skills are now served as skill:// resources via SkillsDirectoryProvider
        assert any("skill://native" in u for u in uris), f"No native skill resource in {uris}"
        assert any("component_reference" in u for u in uris), (
            f"No component_reference skill resource in {uris}"
        )


# =============================================================================
# Tool Execution - Widget Creation
# =============================================================================


class TestMCPToolCreateWidget:
    """Test widget creation through the real MCP protocol."""

    @pytest.mark.asyncio
    async def test_create_widget_basic(self, mcp_client):
        """Create a simple widget through MCP and verify result."""
        result = await mcp_client.call_tool(
            "create_widget",
            {
                "html": "<div>Hello MCP</div>",
                "title": "Basic Widget",
            },
        )
        data = _parse_tool_result(result)

        assert data.get("created") is True
        assert "widget_id" in data

    @pytest.mark.asyncio
    async def test_create_widget_with_toolbars(self, mcp_client):
        """Create a widget with toolbars through MCP protocol."""
        result = await mcp_client.call_tool(
            "create_widget",
            {
                "html": '<div id="counter">0</div>',
                "title": "Counter Widget",
                "height": 400,
                "toolbars": [
                    {
                        "position": "top",
                        "items": [
                            {
                                "type": "button",
                                "label": "+1",
                                "event": "counter:increment",
                                "variant": "primary",
                            },
                            {
                                "type": "button",
                                "label": "-1",
                                "event": "counter:decrement",
                                "variant": "neutral",
                            },
                            {
                                "type": "button",
                                "label": "Reset",
                                "event": "counter:reset",
                                "variant": "danger",
                            },
                        ],
                    }
                ],
            },
        )
        data = _parse_tool_result(result)

        assert data.get("created") is True
        assert "widget_id" in data

        # Verify widget state in server
        from pywry.mcp.state import get_widget, get_widget_config

        widget = get_widget(data["widget_id"])
        assert widget is not None

        config = get_widget_config(data["widget_id"])
        assert config is not None
        assert config["title"] == "Counter Widget"
        assert len(config["toolbars"]) == 1
        assert len(config["toolbars"][0]["items"]) == 3

    @pytest.mark.asyncio
    async def test_create_widget_with_select(self, mcp_client):
        """Create a widget with a Select component through MCP."""
        result = await mcp_client.call_tool(
            "create_widget",
            {
                "html": '<div id="selected-value">None</div>',
                "title": "Select Test",
                "toolbars": [
                    {
                        "position": "top",
                        "items": [
                            {
                                "type": "select",
                                "label": "Choose Theme",
                                "event": "theme:change",
                                "options": [
                                    {"label": "Dark", "value": "dark"},
                                    {"label": "Light", "value": "light"},
                                    {"label": "System", "value": "system"},
                                ],
                                "selected": "dark",
                            }
                        ],
                    }
                ],
            },
        )
        data = _parse_tool_result(result)
        assert data.get("created") is True

    @pytest.mark.asyncio
    async def test_create_widget_with_slider(self, mcp_client):
        """Create a widget with a Slider component through MCP."""
        result = await mcp_client.call_tool(
            "create_widget",
            {
                "html": '<div id="slider-value">50</div>',
                "title": "Slider Test",
                "toolbars": [
                    {
                        "position": "bottom",
                        "items": [
                            {
                                "type": "slider",
                                "label": "Volume",
                                "event": "volume:change",
                                "value": 50,
                                "min": 0,
                                "max": 100,
                                "step": 5,
                                "show_value": True,
                            }
                        ],
                    }
                ],
            },
        )
        data = _parse_tool_result(result)
        assert data.get("created") is True

    @pytest.mark.asyncio
    async def test_create_widget_with_marquee(self, mcp_client):
        """Create a widget with a Marquee ticker through MCP."""
        result = await mcp_client.call_tool(
            "create_widget",
            {
                "html": '<div id="content">Stock Ticker</div>',
                "title": "Marquee Test",
                "toolbars": [
                    {
                        "position": "top",
                        "items": [
                            {
                                "type": "marquee",
                                "text": "AAPL: $150.00 • GOOG: $2800.00 • MSFT: $380.00",
                                "speed": 15,
                                "pause_on_hover": True,
                            }
                        ],
                    }
                ],
            },
        )
        data = _parse_tool_result(result)
        assert data.get("created") is True


# =============================================================================
# Tool Execution - Widget Lifecycle
# =============================================================================


class TestMCPToolWidgetLifecycle:
    """Test full widget lifecycle through MCP protocol."""

    @pytest.mark.asyncio
    async def test_create_list_destroy(self, mcp_client):
        """Complete lifecycle: create -> list -> destroy via MCP protocol."""
        # Create
        create_result = await mcp_client.call_tool(
            "create_widget",
            {"html": "<div>Lifecycle Test</div>", "title": "Lifecycle"},
        )
        create_data = _parse_tool_result(create_result)
        widget_id = create_data["widget_id"]
        assert create_data["created"] is True

        # List
        list_result = await mcp_client.call_tool("list_widgets", {})
        list_data = _parse_tool_result(list_result)
        assert list_data["count"] >= 1
        assert widget_id in [w["widget_id"] for w in list_data["widgets"]]

        # Destroy
        destroy_result = await mcp_client.call_tool(
            "destroy_widget",
            {"widget_id": widget_id},
        )
        destroy_data = _parse_tool_result(destroy_result)
        assert destroy_data["destroyed"] is True

        # Verify gone
        from pywry.mcp.state import get_widget

        assert get_widget(widget_id) is None

    @pytest.mark.asyncio
    async def test_export_widget(self, mcp_client):
        """Export a widget as Python code through MCP protocol."""
        # Create widget
        create_result = await mcp_client.call_tool(
            "create_widget",
            {
                "html": '<div id="app">App Content</div>',
                "title": "Exportable Widget",
                "height": 600,
                "toolbars": [
                    {
                        "position": "top",
                        "items": [
                            {"type": "button", "label": "Save", "event": "app:save"},
                            {
                                "type": "toggle",
                                "label": "Dark Mode",
                                "event": "app:theme",
                            },
                        ],
                    }
                ],
            },
        )
        widget_id = _parse_tool_result(create_result)["widget_id"]

        # Export through MCP
        export_result = await mcp_client.call_tool(
            "export_widget",
            {"widget_id": widget_id},
        )
        export_data = _parse_tool_result(export_result)

        assert "code" in export_data, f"Export failed: {export_data}"
        code = export_data["code"]

        assert "from pywry import PyWry" in code
        assert "Exportable Widget" in code
        assert "Button" in code
        assert "Toggle" in code
        assert "Toolbar" in code

        # Verify it compiles
        try:
            compile(code, "<exported>", "exec")
        except SyntaxError as e:
            pytest.fail(f"Exported code has syntax error: {e}")


# =============================================================================
# Tool Execution - Widget Manipulation
# =============================================================================


class TestMCPToolWidgetManipulation:
    """Test widget manipulation tools through MCP protocol."""

    @pytest.mark.asyncio
    async def test_set_content(self, mcp_client):
        """Set content on a widget element through MCP."""
        # Create widget
        create_result = await mcp_client.call_tool(
            "create_widget",
            {"html": '<div id="message">Hello</div>', "title": "Manipulation Test"},
        )
        widget_id = _parse_tool_result(create_result)["widget_id"]

        # Set content via MCP protocol
        result = await mcp_client.call_tool(
            "set_content",
            {"widget_id": widget_id, "component_id": "message", "text": "Updated!"},
        )
        data = _parse_tool_result(result)
        assert "error" not in data

    @pytest.mark.asyncio
    async def test_set_style(self, mcp_client):
        """Set styles on a widget element through MCP."""
        create_result = await mcp_client.call_tool(
            "create_widget",
            {"html": '<div id="box">Styled</div>', "title": "Style Test"},
        )
        widget_id = _parse_tool_result(create_result)["widget_id"]

        result = await mcp_client.call_tool(
            "set_style",
            {
                "widget_id": widget_id,
                "component_id": "box",
                "styles": {"color": "red", "fontSize": "24px"},
            },
        )
        data = _parse_tool_result(result)
        assert "error" not in data


# =============================================================================
# Event Flow Tests
# =============================================================================


class TestMCPEventFlow:
    """Test event capture and retrieval through MCP protocol."""

    @pytest.mark.asyncio
    async def test_events_captured_and_retrievable(self, mcp_client):
        """Events are captured in server state and retrievable via get_events."""
        from pywry.mcp.server import _events, _make_event_callback

        # Create widget through MCP
        create_result = await mcp_client.call_tool(
            "create_widget",
            {
                "html": "<div>Event Test</div>",
                "toolbars": [
                    {
                        "position": "top",
                        "items": [
                            {
                                "type": "button",
                                "label": "Click Me",
                                "event": "btn:click",
                            }
                        ],
                    }
                ],
            },
        )
        widget_id = _parse_tool_result(create_result)["widget_id"]
        assert widget_id in _events

        # Simulate a browser event (callback fires when user clicks in the real UI)
        callback = _make_event_callback(widget_id)
        callback({"clicked": True}, "btn:click", "Click Me")

        # Retrieve events through MCP protocol
        get_result = await mcp_client.call_tool(
            "get_events",
            {"widget_id": widget_id, "clear": False},
        )
        events_data = _parse_tool_result(get_result)

        assert len(events_data["events"]) >= 1
        last = events_data["events"][-1]
        assert last["event_type"] == "btn:click"
        assert last["data"]["clicked"] is True

    @pytest.mark.asyncio
    async def test_get_events_with_clear(self, mcp_client):
        """get_events with clear=True empties the event buffer."""
        from pywry.mcp.server import _events, _make_event_callback

        # Create widget
        create_result = await mcp_client.call_tool(
            "create_widget",
            {"html": "<div>Test</div>"},
        )
        widget_id = _parse_tool_result(create_result)["widget_id"]

        # Simulate events
        cb = _make_event_callback(widget_id)
        cb({"x": 1}, "evt:one", "")
        cb({"x": 2}, "evt:two", "")
        cb({"x": 3}, "evt:three", "")

        # Get and clear through MCP
        clear_result = await mcp_client.call_tool(
            "get_events",
            {"widget_id": widget_id, "clear": True},
        )
        data = _parse_tool_result(clear_result)
        assert len(data["events"]) >= 3

        # Buffer should be empty now
        assert _events[widget_id] == []

        # Confirm via MCP
        empty_result = await mcp_client.call_tool(
            "get_events",
            {"widget_id": widget_id, "clear": False},
        )
        empty_data = _parse_tool_result(empty_result)
        assert len(empty_data["events"]) == 0


# =============================================================================
# Skills (Resources) Tests - Through MCP Protocol
# =============================================================================


class TestMCPSkills:
    """Test skills are accessible as MCP resources via skill:// URI scheme."""

    @pytest.mark.asyncio
    async def test_get_skills_tool(self, mcp_client):
        """get_skills tool returns available skill list through MCP."""
        result = await mcp_client.call_tool("get_skills", {})
        data = _parse_tool_result(result)

        assert "available_skills" in data
        skill_keys = [s["key"] for s in data["available_skills"]]
        assert "native" in skill_keys
        assert "component_reference" in skill_keys

    @pytest.mark.asyncio
    async def test_get_skills_specific(self, mcp_client):
        """get_skills returns detailed guidance for a specific skill."""
        result = await mcp_client.call_tool("get_skills", {"skill": "native"})
        data = _parse_tool_result(result)

        assert "guidance" in data
        assert len(data["guidance"]) > 200

    @pytest.mark.asyncio
    async def test_skill_resource_native(self, mcp_client):
        """Native skill is accessible as a skill:// resource via SkillsDirectoryProvider."""
        result = await mcp_client.read_resource("skill://native/SKILL.md")

        assert result is not None
        text = result[0].text if hasattr(result[0], "text") else str(result[0])
        assert len(text) > 200

    @pytest.mark.asyncio
    async def test_skill_resource_component_reference(self, mcp_client):
        """component_reference skill is accessible as a skill:// resource."""
        result = await mcp_client.read_resource("skill://component_reference/SKILL.md")

        assert result is not None
        text = result[0].text if hasattr(result[0], "text") else str(result[0])
        assert len(text) >= 1


# =============================================================================
# Resource Reading Tests - Through MCP Protocol
# =============================================================================


class TestMCPResources:
    """Test MCP resource reading through the protocol."""

    @pytest.mark.asyncio
    async def test_read_component_doc(self, mcp_client):
        """Read component documentation via MCP resource protocol."""
        content = await mcp_client.read_resource("pywry://component/button")

        assert content is not None
        text = content[0].text
        assert "Button" in text
        assert "Properties" in text

    @pytest.mark.asyncio
    async def test_read_events_doc(self, mcp_client):
        """Read events documentation via MCP resource protocol."""
        content = await mcp_client.read_resource("pywry://docs/events")

        assert content is not None
        text = content[0].text
        assert len(text) > 100

    @pytest.mark.asyncio
    async def test_read_skill_resource(self, mcp_client):
        """Read skill guidance via MCP resource protocol (skill:// URI scheme)."""
        content = await mcp_client.read_resource("skill://native/SKILL.md")

        assert content is not None
        text = content[0].text
        assert len(text) > 200

    @pytest.mark.asyncio
    async def test_read_source_resource(self, mcp_client):
        """Read component source code via MCP resource protocol."""
        content = await mcp_client.read_resource("pywry://source/button")

        assert content is not None
        text = content[0].text
        assert "class" in text.lower() or "Button" in text

    @pytest.mark.asyncio
    async def test_read_quickstart_resource(self, mcp_client):
        """Read quickstart guide via MCP resource protocol."""
        content = await mcp_client.read_resource("pywry://docs/quickstart")

        assert content is not None
        text = content[0].text
        assert len(text) > 50


# =============================================================================
# Component Docs Tool Tests - Through MCP Protocol
# =============================================================================


class TestMCPComponentDocs:
    """Test component documentation tools through MCP protocol."""

    @pytest.mark.asyncio
    async def test_get_component_docs(self, mcp_client):
        """Retrieve component docs via MCP tool call."""
        result = await mcp_client.call_tool(
            "get_component_docs",
            {"component": "button"},
        )
        data = _parse_tool_result(result)

        assert data["component"] == "button"
        assert "name" in data
        assert "description" in data

    @pytest.mark.asyncio
    async def test_get_component_source(self, mcp_client):
        """Retrieve component source code via MCP tool call."""
        result = await mcp_client.call_tool(
            "get_component_source",
            {"component": "button"},
        )
        data = _parse_tool_result(result)

        assert data["component"] == "button"
        assert "source" in data
        assert "class" in data["source"].lower() or "Button" in data["source"]


# =============================================================================
# Real Component Building Tests (non-protocol, kept for coverage)
# =============================================================================


class TestMCPRealComponentBuilding:
    """Test that components are built correctly from config."""

    def test_build_all_component_types(self):
        """Test building all component types from config."""
        from pywry.mcp.builders import build_toolbar_item

        configs = [
            {"type": "button", "label": "Click", "event": "test:click"},
            {
                "type": "select",
                "label": "Choose",
                "event": "test:select",
                "options": [{"label": "A", "value": "a"}],
            },
            {
                "type": "multiselect",
                "label": "Multi",
                "event": "test:multi",
                "options": [],
            },
            {"type": "toggle", "label": "Toggle", "event": "test:toggle"},
            {"type": "checkbox", "label": "Check", "event": "test:check"},
            {
                "type": "radio",
                "label": "Radio",
                "event": "test:radio",
                "options": [{"label": "X"}],
            },
            {"type": "tabs", "event": "test:tabs", "options": [{"label": "Tab1"}]},
            {"type": "text", "label": "Text", "event": "test:text"},
            {"type": "textarea", "label": "Area", "event": "test:area"},
            {"type": "search", "label": "Search", "event": "test:search"},
            {"type": "number", "label": "Num", "event": "test:num"},
            {"type": "date", "label": "Date", "event": "test:date"},
            {"type": "slider", "label": "Slide", "event": "test:slide"},
            {"type": "range", "event": "test:range"},
            {"type": "div", "content": "Content"},
            {"type": "secret", "label": "Secret", "event": "test:secret"},
            {"type": "marquee", "text": "Scrolling"},
        ]

        for config in configs:
            component = build_toolbar_item(config)
            assert component is not None, f"Failed to build {config['type']}"
            assert hasattr(component, "build_html"), f"{config['type']} missing build_html"

    def test_built_components_generate_valid_html(self):
        """Test that built components generate valid HTML."""
        from pywry.mcp.builders import build_toolbar_item

        configs = [
            {
                "type": "button",
                "label": "Test Button",
                "event": "app:click",
                "variant": "primary",
            },
            {
                "type": "select",
                "label": "Test Select",
                "event": "app:select",
                "options": [{"label": "Opt", "value": "opt"}],
            },
            {
                "type": "slider",
                "label": "Test Slider",
                "event": "app:slide",
                "min": 0,
                "max": 100,
            },
        ]

        for config in configs:
            component = build_toolbar_item(config)
            assert component is not None
            html = component.build_html()

            assert len(html) > 10, f"HTML too short for {config['type']}"
            assert "<" in html and ">" in html, f"Invalid HTML for {config['type']}"

            if "event" in config:
                assert config["event"] in html or "data-event" in html, (
                    f"Event not in HTML for {config['type']}"
                )

    def test_toolbar_builds_with_multiple_items(self):
        """Test building a complete toolbar with multiple items."""
        from pywry.mcp.builders import build_toolbars

        toolbar_config = [
            {
                "position": "top",
                "items": [
                    {
                        "type": "button",
                        "label": "Save",
                        "event": "file:save",
                        "variant": "primary",
                    },
                    {
                        "type": "button",
                        "label": "Load",
                        "event": "file:load",
                        "variant": "neutral",
                    },
                    {
                        "type": "select",
                        "label": "Format",
                        "event": "file:format",
                        "options": [
                            {"label": "JSON", "value": "json"},
                            {"label": "CSV", "value": "csv"},
                        ],
                    },
                ],
            },
            {
                "position": "bottom",
                "items": [
                    {
                        "type": "slider",
                        "label": "Zoom",
                        "event": "view:zoom",
                        "min": 50,
                        "max": 200,
                        "value": 100,
                    },
                ],
            },
        ]

        toolbars = build_toolbars(toolbar_config)

        assert len(toolbars) == 2
        assert toolbars[0].position == "top"
        assert len(toolbars[0].items) == 3
        assert toolbars[1].position == "bottom"
        assert len(toolbars[1].items) == 1

        for toolbar in toolbars:
            html = toolbar.build_html()
            assert len(html) > 50
            assert "toolbar" in html.lower() or "pywry" in html.lower()


# =============================================================================
# Real Skill and Resource Tests (non-protocol, kept for coverage)
# =============================================================================


class TestMCPRealSkillsAndResources:
    """Test skills and resources work correctly with real file loading."""

    def test_all_skills_load_without_error(self):
        """Test that all skills can be loaded from disk."""
        from pywry.mcp.skills import SKILL_METADATA, load_skill

        for skill_id in SKILL_METADATA:
            content = load_skill(skill_id)
            assert content is not None, f"Failed to load skill: {skill_id}"
            assert len(content) > 100, f"Skill {skill_id} content too short"

    def test_skill_files_exist_on_disk(self):
        """Test that skill markdown files actually exist."""
        from pathlib import Path

        from pywry.mcp.skills import SKILL_METADATA, SKILLS_DIR

        for skill_id in SKILL_METADATA:
            skill_file = Path(SKILLS_DIR) / skill_id / "SKILL.md"
            assert skill_file.exists(), f"Skill file missing: {skill_file}"

    def test_component_source_from_real_toolbar_module(self):
        """Test that component source is extracted from real toolbar.py."""
        from pywry.mcp.resources import get_component_source

        for comp in ["button", "select", "toggle", "slider", "marquee"]:
            source = get_component_source(comp)
            assert source is not None, f"No source for {comp}"
            assert "class" in source.lower(), f"Source for {comp} doesn't look like a class"
            assert len(source) > 50, f"Source for {comp} too short"

    def test_resource_uris_are_readable(self):
        """Test that all resource URIs can be read."""
        from pywry.mcp.resources import get_resources, read_resource

        resources = get_resources()

        tested = 0
        for resource in resources[:10]:
            uri = str(resource.uri)
            content = read_resource(uri)
            if content is not None:
                assert len(content) > 0, f"Empty content for {uri}"
                tested += 1

        assert tested >= 5, "Too few resources were readable"


# =============================================================================
# Callback Integration Tests (server internals)
# =============================================================================


class TestEventCallbackIntegration:
    """Test event callback system at the server module level."""

    def test_event_callback_stores_events(self) -> None:
        """Event callback properly stores events in module-level dict."""
        from pywry.mcp.server import _events, _make_event_callback

        _events.clear()
        callback = _make_event_callback("test-widget")

        callback({"x": 10, "y": 20}, "button:click", "Save Button")
        callback({"value": "hello"}, "input:change", "Name Input")

        assert "test-widget" in _events
        assert len(_events["test-widget"]) == 2

        event1 = _events["test-widget"][0]
        assert event1["event_type"] == "button:click"
        assert event1["data"] == {"x": 10, "y": 20}
        assert event1["label"] == "Save Button"

    def test_event_callback_creates_widget_entry(self) -> None:
        """Event callback creates widget entry if not exists."""
        from pywry.mcp.server import _events, _make_event_callback

        _events.clear()
        callback = _make_event_callback("new-widget")

        assert "new-widget" not in _events

        callback({}, "init", "")

        assert "new-widget" in _events
