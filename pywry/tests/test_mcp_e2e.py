"""End-to-end tests for MCP server implementation.

These are REAL tests that actually:
- Use real MCP handlers with real PyWry code
- Create real widgets with real HTML content
- Verify events are actually captured
- Test the full widget lifecycle

Run with: pytest tests/test_mcp_e2e.py -v
"""

# pylint: disable=too-many-lines,redefined-outer-name

from __future__ import annotations

import os

from typing import Any

import pytest


# Check if MCP is available
try:
    import mcp  # noqa: F401  # pylint: disable=unused-import

    HAS_MCP = True
except ImportError:
    HAS_MCP = False


pytestmark = pytest.mark.skipif(not HAS_MCP, reason="mcp package not installed")


@pytest.fixture
def clean_state():
    """Clean all PyWry state before and after each test."""
    from pywry.mcp import state

    # Store originals
    original_app = state._app
    original_widgets = state._widgets.copy()
    original_configs = state._widget_configs.copy()
    original_headless = os.environ.get("PYWRY_HEADLESS")

    # Clean state
    state._app = None
    state._widgets.clear()
    state._widget_configs.clear()
    os.environ["PYWRY_HEADLESS"] = "1"

    yield

    # Restore
    state._app = original_app
    state._widgets.clear()
    state._widgets.update(original_widgets)
    state._widget_configs.clear()
    state._widget_configs.update(original_configs)

    if original_headless is None:
        os.environ.pop("PYWRY_HEADLESS", None)
    else:
        os.environ["PYWRY_HEADLESS"] = original_headless


# =============================================================================
# Real Handler Tests - No Server Needed, Uses Real PyWry Code
# =============================================================================


class TestMCPHandlersReal:
    """Test MCP handlers with real PyWry code execution.

    These tests use the real handle_tool function and real PyWry widget code,
    just without starting a network server.
    """

    @pytest.mark.asyncio
    async def test_real_create_widget_with_toolbars(self, _clean_state):
        """Test creating a real widget with toolbars using actual PyWry code."""
        from pywry.mcp.handlers import handle_tool

        events: dict[str, list[dict[str, Any]]] = {}

        def make_callback(_wid: str):
            def cb(data: Any, event_type: str, label: str = "") -> None:
                if _wid not in events:
                    events[_wid] = []
                events[_wid].append({"event_type": event_type, "data": data, "label": label})

            return cb

        # Create widget with real toolbars
        result = await handle_tool(
            "create_widget",
            {
                "html": '<div id="counter" style="font-size:48px;text-align:center;padding:50px">0</div>',
                "title": "Real Counter Widget",
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
            events,
            make_callback,
        )

        # Verify widget was created
        assert "widget_id" in result, f"Widget creation failed: {result}"
        assert result.get("created") is True
        widget_id = result["widget_id"]

        # Verify widget is in state
        from pywry.mcp.state import get_widget, get_widget_config

        widget = get_widget(widget_id)
        assert widget is not None, "Widget not stored in state"

        # Verify config was stored
        config = get_widget_config(widget_id)
        assert config is not None, "Widget config not stored"
        assert config["title"] == "Real Counter Widget"
        assert len(config["toolbars"]) == 1
        assert len(config["toolbars"][0]["items"]) == 3

    @pytest.mark.asyncio
    async def test_real_widget_manipulation(self, _clean_state):
        """Test manipulating a real widget."""
        from pywry.mcp.handlers import handle_tool
        from pywry.mcp.state import _widgets

        events: dict[str, list[dict[str, Any]]] = {}

        def make_callback(_wid: str):
            return lambda d, e, lbl: None

        # Create widget first
        result = await handle_tool(
            "create_widget",
            {
                "html": '<div id="message">Hello</div>',
                "title": "Manipulation Test",
            },
            events,
            make_callback,
        )

        widget_id = result["widget_id"]
        widget = _widgets[widget_id]

        # Track emitted events
        emitted_events: list[tuple[str, dict]] = []
        original_emit = widget.emit

        def tracking_emit(event_type: str, data: dict) -> None:
            emitted_events.append((event_type, data))
            return original_emit(event_type, data)

        widget.emit = tracking_emit

        # Test set_content
        await handle_tool(
            "set_content",
            {"widget_id": widget_id, "component_id": "message", "text": "Updated!"},
            events,
            make_callback,
        )

        assert len(emitted_events) >= 1
        last_event = emitted_events[-1]
        assert last_event[0] == "pywry:set-content"
        assert last_event[1]["id"] == "message"
        assert last_event[1]["text"] == "Updated!"

        # Test set_style
        await handle_tool(
            "set_style",
            {
                "widget_id": widget_id,
                "component_id": "message",
                "styles": {"color": "red", "fontSize": "24px"},
            },
            events,
            make_callback,
        )

        last_event = emitted_events[-1]
        assert last_event[0] == "pywry:set-style"
        assert last_event[1]["styles"]["color"] == "red"

    @pytest.mark.asyncio
    async def test_real_widget_with_select_component(self, _clean_state):
        """Test creating widget with Select component."""
        from pywry.mcp.handlers import handle_tool

        events: dict[str, list[dict[str, Any]]] = {}

        def make_callback(_wid: str):
            return lambda d, e, lbl: None

        result = await handle_tool(
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
            events,
            make_callback,
        )

        assert "widget_id" in result
        assert result.get("created") is True

    @pytest.mark.asyncio
    async def test_real_widget_with_slider(self, _clean_state):
        """Test creating widget with Slider component."""
        from pywry.mcp.handlers import handle_tool

        events: dict[str, list[dict[str, Any]]] = {}

        def make_callback(_wid: str):
            return lambda d, e, lbl: None

        result = await handle_tool(
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
            events,
            make_callback,
        )

        assert "widget_id" in result
        assert result.get("created") is True

    @pytest.mark.asyncio
    async def test_real_widget_with_marquee(self, _clean_state):
        """Test creating widget with Marquee ticker."""
        from pywry.mcp.handlers import handle_tool

        events: dict[str, list[dict[str, Any]]] = {}

        def make_callback(_wid: str):
            return lambda d, e, lbl: None

        result = await handle_tool(
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
            events,
            make_callback,
        )

        assert "widget_id" in result
        assert result.get("created") is True

    @pytest.mark.asyncio
    async def test_real_export_widget_code(self, _clean_state):
        """Test exporting a real widget as Python code."""
        from pywry.mcp.handlers import handle_tool

        events: dict[str, list[dict[str, Any]]] = {}

        def make_callback(_wid: str):
            return lambda d, e, lbl: None

        # Create widget
        create_result = await handle_tool(
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
            events,
            make_callback,
        )

        widget_id = create_result["widget_id"]

        # Export widget
        export_result = await handle_tool(
            "export_widget",
            {"widget_id": widget_id},
            events,
            make_callback,
        )

        assert "code" in export_result, f"Export failed: {export_result}"
        code = export_result["code"]

        # Verify the code is valid Python
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

    @pytest.mark.asyncio
    async def test_real_widget_lifecycle(self, _clean_state):
        """Test complete widget lifecycle: create -> list -> destroy."""
        from pywry.mcp.handlers import handle_tool
        from pywry.mcp.state import _widgets

        events: dict[str, list[dict[str, Any]]] = {}

        def make_callback(_wid: str):
            return lambda d, e, lbl: None

        # Create widget
        create_result = await handle_tool(
            "create_widget",
            {"html": "<div>Lifecycle Test</div>", "title": "Lifecycle"},
            events,
            make_callback,
        )
        widget_id = create_result["widget_id"]
        assert widget_id in _widgets

        # List widgets
        list_result = await handle_tool("list_widgets", {}, events, make_callback)
        assert list_result["count"] >= 1
        widget_ids = [w["widget_id"] for w in list_result["widgets"]]
        assert widget_id in widget_ids

        # Destroy widget
        destroy_result = await handle_tool(
            "destroy_widget",
            {"widget_id": widget_id},
            events,
            make_callback,
        )
        assert destroy_result["destroyed"] is True
        assert widget_id not in _widgets


# =============================================================================
# Real Skill and Resource Tests
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
            skill_file = Path(SKILLS_DIR) / f"{skill_id}.md"
            assert skill_file.exists(), f"Skill file missing: {skill_file}"

    def test_component_source_from_real_toolbar_module(self):
        """Test that component source is extracted from real toolbar.py."""
        from pywry.mcp.resources import get_component_source

        # Test a few components
        for comp in ["button", "select", "toggle", "slider", "marquee"]:
            source = get_component_source(comp)
            assert source is not None, f"No source for {comp}"
            assert "class" in source.lower(), f"Source for {comp} doesn't look like a class"
            assert len(source) > 50, f"Source for {comp} too short"

    def test_resource_uris_are_readable(self):
        """Test that all resource URIs can be read."""
        from pywry.mcp.resources import get_resources, read_resource

        resources = get_resources()

        # Test a sample of resources
        tested = 0
        for resource in resources[:10]:
            uri = str(resource.uri)
            content = read_resource(uri)
            if content is not None:
                assert len(content) > 0, f"Empty content for {uri}"
                tested += 1

        assert tested >= 5, "Too few resources were readable"


# =============================================================================
# Real Component Building Tests
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
            # Component should have a build_html method
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

            # Should contain the event name
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

        # Each toolbar should generate HTML
        for toolbar in toolbars:
            html = toolbar.build_html()
            assert len(html) > 50
            assert "toolbar" in html.lower() or "pywry" in html.lower()


# =============================================================================
# Real Event Flow Tests
# =============================================================================


class TestMCPRealEventFlow:
    """Test real event handling and callback execution."""

    @pytest.mark.asyncio
    async def test_events_are_captured_in_events_dict(self, _clean_state):
        """Test that widget events are captured in the events dictionary."""
        from pywry.mcp.handlers import handle_tool
        from pywry.mcp.server import _make_event_callback

        events: dict[str, list[dict[str, Any]]] = {}

        def make_callback(wid: str):
            return _make_event_callback(events, wid)

        # Create widget
        result = await handle_tool(
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
            events,
            make_callback,
        )

        widget_id = result["widget_id"]
        assert widget_id in events

        # Simulate an event
        callback = make_callback(widget_id)
        callback({"clicked": True}, "btn:click", "Click Me")

        # Verify event was captured
        assert len(events[widget_id]) >= 1
        last_event = events[widget_id][-1]
        assert last_event["event_type"] == "btn:click"
        assert last_event["data"]["clicked"] is True

    @pytest.mark.asyncio
    async def test_get_events_returns_captured_events(self, _clean_state):
        """Test that get_events handler returns captured events."""
        from pywry.mcp.handlers import handle_tool
        from pywry.mcp.server import _make_event_callback

        events: dict[str, list[dict[str, Any]]] = {}

        def make_callback(wid: str):
            return _make_event_callback(events, wid)

        # Create widget
        result = await handle_tool(
            "create_widget",
            {"html": "<div>Test</div>"},
            events,
            make_callback,
        )
        widget_id = result["widget_id"]

        # Simulate events
        cb = make_callback(widget_id)
        cb({"x": 1}, "evt:one", "")
        cb({"x": 2}, "evt:two", "")
        cb({"x": 3}, "evt:three", "")

        # Get events via handler
        get_result = await handle_tool(
            "get_events",
            {"widget_id": widget_id, "clear": False},
            events,
            make_callback,
        )

        assert len(get_result["events"]) >= 3

        # Clear events
        clear_result = await handle_tool(
            "get_events",
            {"widget_id": widget_id, "clear": True},
            events,
            make_callback,
        )
        assert len(clear_result["events"]) >= 3
        assert events[widget_id] == []


# =============================================================================
# Resource Reading Tests
# =============================================================================


class TestResourceReading:
    """Test reading MCP resources."""

    def test_read_resource_component(self) -> None:
        """read_resource returns component documentation."""
        from pywry.mcp.resources import read_resource

        content = read_resource("pywry://component/button")

        assert content is not None
        assert "Button" in content
        assert "Properties" in content

    def test_read_resource_events(self) -> None:
        """read_resource returns events documentation."""
        from pywry.mcp.resources import read_resource

        content = read_resource("pywry://docs/events")

        assert content is not None
        assert len(content) > 100

    def test_read_resource_skill(self) -> None:
        """read_resource returns skill guidance."""
        from pywry.mcp.resources import read_resource

        content = read_resource("pywry://skill/native")

        assert content is not None
        assert len(content) > 200

    def test_read_resource_source(self) -> None:
        """read_resource returns component source."""
        from pywry.mcp.resources import read_resource

        content = read_resource("pywry://source/button")

        assert content is not None
        assert "class" in content.lower() or "Button" in content

    def test_read_resource_not_found(self) -> None:
        """read_resource returns None for unknown resource."""
        from pywry.mcp.resources import read_resource

        content = read_resource("pywry://unknown/resource")

        assert content is None


# =============================================================================
# Callback Integration Tests
# =============================================================================


class TestEventCallbackIntegration:
    """Test event callback system."""

    def test_event_callback_stores_events(self) -> None:
        """Event callback properly stores events."""
        from pywry.mcp.server import _make_event_callback

        events: dict[str, list[dict[str, Any]]] = {}
        callback = _make_event_callback(events, "test-widget")

        # Simulate events
        callback({"x": 10, "y": 20}, "button:click", "Save Button")
        callback({"value": "hello"}, "input:change", "Name Input")

        assert "test-widget" in events
        assert len(events["test-widget"]) == 2

        event1 = events["test-widget"][0]
        assert event1["event_type"] == "button:click"
        assert event1["data"] == {"x": 10, "y": 20}
        assert event1["label"] == "Save Button"

    def test_event_callback_creates_widget_entry(self) -> None:
        """Event callback creates widget entry if not exists."""
        from pywry.mcp.server import _make_event_callback

        events: dict[str, list[dict[str, Any]]] = {}
        callback = _make_event_callback(events, "new-widget")

        assert "new-widget" not in events

        callback({}, "init", "")

        assert "new-widget" in events
