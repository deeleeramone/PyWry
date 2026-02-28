"""Unit tests for MCP implementation.

Tests cover all MCP submodules:
- builders: Toolbar building from config dicts
- docs: Component documentation
- handlers: Tool handlers and dispatch
- prompts: Skill prompts
- resources: Resource listing and reading
- skills: Skill loading and metadata
- state: Global state management
- tools: Tool definitions and schemas
"""

# pylint: disable=protected-access,redefined-outer-name,too-many-lines
# pylint: disable=E1121,

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# =============================================================================
# Test State Module
# =============================================================================


class TestStateModule:
    """Tests for pywry.mcp.state module."""

    def test_global_app_singleton(self) -> None:
        """get_app returns same instance."""
        from pywry.mcp import state

        # Clear any existing app
        state._app = None

        with patch.dict("os.environ", {"PYWRY_HEADLESS": "0"}, clear=False):
            app1 = state.get_app()
            app2 = state.get_app()
            assert app1 is app2

        # Cleanup
        state._app = None

    def test_get_app_headless_mode(self) -> None:
        """get_app uses BROWSER mode when PYWRY_HEADLESS=1."""
        from pywry.mcp import state

        state._app = None

        with patch.dict("os.environ", {"PYWRY_HEADLESS": "1"}, clear=False):
            app = state.get_app()
            from pywry.window_manager.modes.browser import BrowserMode

            # Check that the mode is a BrowserMode instance
            assert isinstance(app._mode, BrowserMode)

        state._app = None

    def test_register_widget(self) -> None:
        """register_widget stores widget correctly."""
        from pywry.mcp.state import _widgets, register_widget

        _widgets.clear()

        mock_widget = MagicMock()
        register_widget("test-123", mock_widget)

        assert "test-123" in _widgets
        assert _widgets["test-123"] is mock_widget

        _widgets.clear()

    def test_get_widget_found(self) -> None:
        """get_widget returns widget when found."""
        from pywry.mcp.state import _widgets, get_widget

        _widgets.clear()
        mock_widget = MagicMock()
        _widgets["test-widget"] = mock_widget

        result = get_widget("test-widget")
        assert result is mock_widget

        _widgets.clear()

    def test_get_widget_not_found(self) -> None:
        """get_widget returns None when not found."""
        from pywry.mcp.state import _widgets, get_widget

        _widgets.clear()
        result = get_widget("nonexistent")
        assert result is None

    def test_list_widget_ids(self) -> None:
        """list_widget_ids returns all widget IDs."""
        from pywry.mcp.state import _widgets, list_widget_ids

        _widgets.clear()
        _widgets["widget-1"] = MagicMock()
        _widgets["widget-2"] = MagicMock()

        ids = list_widget_ids()
        assert set(ids) == {"widget-1", "widget-2"}

        _widgets.clear()

    def test_remove_widget_exists(self) -> None:
        """remove_widget removes widget and returns True."""
        from pywry.mcp.state import _widget_configs, _widgets, remove_widget

        _widgets.clear()
        _widget_configs.clear()
        _widgets["to-remove"] = MagicMock()
        _widget_configs["to-remove"] = {"html": "<div></div>"}

        result = remove_widget("to-remove")
        assert result is True
        assert "to-remove" not in _widgets
        assert "to-remove" not in _widget_configs

    def test_remove_widget_not_exists(self) -> None:
        """remove_widget returns False when widget not found."""
        from pywry.mcp.state import _widgets, remove_widget

        _widgets.clear()
        result = remove_widget("nonexistent")
        assert result is False

    def test_store_widget_config(self) -> None:
        """store_widget_config stores configuration."""
        from pywry.mcp.state import _widget_configs, store_widget_config

        _widget_configs.clear()
        config = {"html": "<p>Test</p>", "title": "Test Widget"}
        store_widget_config("cfg-widget", config)

        assert "cfg-widget" in _widget_configs
        assert _widget_configs["cfg-widget"]["title"] == "Test Widget"

        _widget_configs.clear()

    def test_get_widget_config(self) -> None:
        """get_widget_config returns stored configuration."""
        from pywry.mcp.state import _widget_configs, get_widget_config

        _widget_configs.clear()
        _widget_configs["my-widget"] = {"html": "<div>Content</div>"}

        result = get_widget_config("my-widget")
        assert result == {"html": "<div>Content</div>"}

        _widget_configs.clear()

    def test_get_widget_config_not_found(self) -> None:
        """get_widget_config returns None when not found."""
        from pywry.mcp.state import _widget_configs, get_widget_config

        _widget_configs.clear()
        result = get_widget_config("nonexistent")
        assert result is None

    def test_get_widgets(self) -> None:
        """get_widgets returns all widgets dict."""
        from pywry.mcp.state import _widgets, get_widgets

        _widgets.clear()
        mock1 = MagicMock()
        mock2 = MagicMock()
        _widgets["w1"] = mock1
        _widgets["w2"] = mock2

        result = get_widgets()
        assert result == _widgets
        assert len(result) == 2

        _widgets.clear()


# =============================================================================
# Test Skills Module
# =============================================================================


class TestSkillsModule:
    """Tests for pywry.mcp.skills module."""

    def test_list_skills_returns_list(self) -> None:
        """list_skills returns a list of skill metadata."""
        from pywry.mcp.skills import list_skills

        skills = list_skills()
        assert isinstance(skills, list)
        assert len(skills) > 0

    def test_list_skills_has_required_keys(self) -> None:
        """Each skill has id, name, and description."""
        from pywry.mcp.skills import list_skills

        for skill in list_skills():
            assert "id" in skill
            assert "name" in skill
            assert "description" in skill

    def test_get_skill_found(self) -> None:
        """get_skill returns skill with guidance."""
        from pywry.mcp.skills import get_skill

        skill = get_skill("native")
        assert skill is not None
        assert "name" in skill
        assert "description" in skill
        assert "guidance" in skill
        assert len(skill["guidance"]) > 0

    def test_get_skill_not_found(self) -> None:
        """get_skill returns None for unknown skill."""
        from pywry.mcp.skills import get_skill

        result = get_skill("nonexistent_skill_xyz")
        assert result is None

    def test_load_skill_caching(self) -> None:
        """load_skill uses lru_cache."""
        from pywry.mcp.skills import load_skill

        # Call twice - should be cached
        result1 = load_skill("native")
        result2 = load_skill("native")
        assert result1 is result2  # Same object from cache

    def test_skill_metadata_order(self) -> None:
        """component_reference is first in SKILL_METADATA."""
        from pywry.mcp.skills import SKILL_METADATA

        keys = list(SKILL_METADATA.keys())
        assert keys[0] == "component_reference"

    def test_get_all_skills(self) -> None:
        """get_all_skills returns all skills with guidance."""
        from pywry.mcp.skills import get_all_skills

        all_skills = get_all_skills()
        assert isinstance(all_skills, dict)
        assert "native" in all_skills
        assert "guidance" in all_skills["native"]


# =============================================================================
# Test Docs Module
# =============================================================================


class TestDocsModule:
    """Tests for pywry.mcp.docs module."""

    def test_component_docs_has_button(self) -> None:
        """COMPONENT_DOCS contains button documentation."""
        from pywry.mcp.docs import COMPONENT_DOCS

        assert "button" in COMPONENT_DOCS
        assert COMPONENT_DOCS["button"]["name"] == "Button"

    def test_component_docs_has_all_types(self) -> None:
        """COMPONENT_DOCS contains all component types."""
        from pywry.mcp.docs import COMPONENT_DOCS

        expected = [
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
        ]
        for comp in expected:
            assert comp in COMPONENT_DOCS, f"Missing component: {comp}"

    def test_component_doc_has_properties(self) -> None:
        """Each component doc has properties dict."""
        from pywry.mcp.docs import COMPONENT_DOCS

        for comp_name, doc in COMPONENT_DOCS.items():
            assert "properties" in doc, f"{comp_name} missing properties"
            assert isinstance(doc["properties"], dict)

    def test_component_doc_has_example(self) -> None:
        """Each component doc has example code."""
        from pywry.mcp.docs import COMPONENT_DOCS

        for comp_name, doc in COMPONENT_DOCS.items():
            assert "example" in doc, f"{comp_name} missing example"
            assert len(doc["example"]) > 0

    def test_builtin_events_exists(self) -> None:
        """BUILTIN_EVENTS contains event documentation."""
        from pywry.mcp.docs import BUILTIN_EVENTS

        # BUILTIN_EVENTS is a dict mapping event names to their documentation
        assert isinstance(BUILTIN_EVENTS, dict)
        assert len(BUILTIN_EVENTS) > 0
        # Check for known built-in events
        assert "pywry:set-content" in BUILTIN_EVENTS or "pywry:update-theme" in BUILTIN_EVENTS


# =============================================================================
# Test Builders Module
# =============================================================================


class TestBuildersModule:
    """Tests for pywry.mcp.builders module."""

    def test_build_button(self) -> None:
        """_build_button creates Button component."""
        from pywry.mcp.builders import _build_button
        from pywry.toolbar import Button

        cfg = {"label": "Test", "event": "app:test", "variant": "primary"}
        result = _build_button(cfg)

        assert isinstance(result, Button)
        assert result.label == "Test"
        assert result.event == "app:test"
        assert result.variant == "primary"

    def test_build_select(self) -> None:
        """_build_select creates Select component."""
        from pywry.mcp.builders import _build_select
        from pywry.toolbar import Select

        cfg = {
            "label": "Choose",
            "event": "form:select",
            "options": [{"label": "A", "value": "a"}, {"label": "B", "value": "b"}],
            "selected": "a",
        }
        result = _build_select(cfg)

        assert isinstance(result, Select)
        assert result.label == "Choose"
        assert len(result.options) == 2

    def test_build_toggle(self) -> None:
        """_build_toggle creates Toggle component."""
        from pywry.mcp.builders import _build_toggle
        from pywry.toolbar import Toggle

        cfg = {"label": "Enable", "event": "app:toggle", "value": True}
        result = _build_toggle(cfg)

        assert isinstance(result, Toggle)
        assert result.value is True

    def test_build_checkbox(self) -> None:
        """_build_checkbox creates Checkbox component."""
        from pywry.mcp.builders import _build_checkbox
        from pywry.toolbar import Checkbox

        cfg = {"label": "Agree", "event": "form:agree", "value": False}
        result = _build_checkbox(cfg)

        assert isinstance(result, Checkbox)
        assert result.label == "Agree"

    def test_build_text(self) -> None:
        """_build_text creates TextInput component."""
        from pywry.mcp.builders import _build_text
        from pywry.toolbar import TextInput

        cfg = {"label": "Name", "event": "form:name", "placeholder": "Enter name"}
        result = _build_text(cfg)

        assert isinstance(result, TextInput)
        assert result.placeholder == "Enter name"

    def test_build_number(self) -> None:
        """_build_number creates NumberInput component."""
        from pywry.mcp.builders import _build_number
        from pywry.toolbar import NumberInput

        cfg = {"label": "Qty", "event": "form:qty", "min": 1, "max": 100, "step": 1}
        result = _build_number(cfg)

        assert isinstance(result, NumberInput)
        assert result.min == 1
        assert result.max == 100

    def test_build_slider(self) -> None:
        """_build_slider creates SliderInput component."""
        from pywry.mcp.builders import _build_slider
        from pywry.toolbar import SliderInput

        cfg = {"event": "app:slider", "value": 50, "min": 0, "max": 100}
        result = _build_slider(cfg)

        assert isinstance(result, SliderInput)
        assert result.value == 50

    def test_build_div(self) -> None:
        """_build_div creates Div component."""
        from pywry.mcp.builders import _build_div
        from pywry.toolbar import Div

        cfg = {"content": "<p>Hello</p>", "component_id": "my-div"}
        result = _build_div(cfg)

        assert isinstance(result, Div)
        assert result.component_id == "my-div"

    def test_build_marquee(self) -> None:
        """_build_marquee creates Marquee component."""
        from pywry.mcp.builders import _build_marquee
        from pywry.toolbar import Marquee

        cfg = {"text": "Scrolling text", "speed": 10}
        result = _build_marquee(cfg)

        assert isinstance(result, Marquee)
        assert result.speed == 10

    def test_build_marquee_with_ticker_items(self) -> None:
        """_build_marquee handles ticker_items."""
        from pywry.mcp.builders import _build_marquee

        cfg = {
            "ticker_items": [
                {"ticker": "AAPL", "text": "AAPL: $150"},
                {"ticker": "GOOG", "text": "GOOG: $2800"},
            ]
        }
        result = _build_marquee(cfg)
        assert "data-ticker" in result.text

    def test_build_options(self) -> None:
        """_build_options creates Option list."""
        from pywry.mcp.builders import _build_options
        from pywry.toolbar import Option

        opts_data = [{"label": "One", "value": "1"}, {"label": "Two", "value": "2"}]
        result = _build_options(opts_data)

        assert len(result) == 2
        assert all(isinstance(o, Option) for o in result)
        assert result[0].value == "1"

    def test_build_toolbar_item(self) -> None:
        """build_toolbar_item dispatches to correct builder."""
        from pywry.mcp.builders import build_toolbar_item
        from pywry.toolbar import Button, Toggle

        btn = build_toolbar_item({"type": "button", "label": "Click", "event": "app:click"})
        assert isinstance(btn, Button)

        toggle = build_toolbar_item({"type": "toggle", "label": "On/Off", "event": "app:toggle"})
        assert isinstance(toggle, Toggle)

    def test_build_toolbar_item_unknown_type(self) -> None:
        """build_toolbar_item returns None for unknown type."""
        from pywry.mcp.builders import build_toolbar_item

        result = build_toolbar_item({"type": "unknown_component"})
        assert result is None

    def test_build_toolbars(self) -> None:
        """build_toolbars creates Toolbar list."""
        from pywry.mcp.builders import build_toolbars
        from pywry.toolbar import Toolbar

        data = [
            {
                "position": "top",
                "items": [
                    {"type": "button", "label": "Save", "event": "app:save"},
                    {"type": "button", "label": "Load", "event": "app:load"},
                ],
            },
            {
                "position": "bottom",
                "items": [{"type": "toggle", "label": "Dark", "event": "app:theme"}],
            },
        ]

        result = build_toolbars(data)
        assert len(result) == 2
        assert all(isinstance(t, Toolbar) for t in result)
        assert result[0].position == "top"
        assert len(result[0].items) == 2

    def test_build_multiselect(self) -> None:
        """_build_multiselect creates MultiSelect component."""
        from pywry.mcp.builders import _build_multiselect
        from pywry.toolbar import MultiSelect

        cfg = {
            "label": "Tags",
            "event": "form:tags",
            "options": [{"label": "A", "value": "a"}, {"label": "B", "value": "b"}],
            "selected": ["a"],
        }
        result = _build_multiselect(cfg)

        assert isinstance(result, MultiSelect)
        assert result.selected == ["a"]

    def test_build_radio(self) -> None:
        """_build_radio creates RadioGroup component."""
        from pywry.mcp.builders import _build_radio
        from pywry.toolbar import RadioGroup

        cfg = {
            "label": "Size",
            "event": "form:size",
            "options": [{"label": "S"}, {"label": "M"}, {"label": "L"}],
            "selected": "M",
        }
        result = _build_radio(cfg)

        assert isinstance(result, RadioGroup)
        assert result.selected == "M"

    def test_build_tabs(self) -> None:
        """_build_tabs creates TabGroup component."""
        from pywry.mcp.builders import _build_tabs
        from pywry.toolbar import TabGroup

        cfg = {
            "event": "view:tab",
            "options": [
                {"label": "Chart", "value": "chart"},
                {"label": "Table", "value": "table"},
            ],
            "selected": "chart",
        }
        result = _build_tabs(cfg)

        assert isinstance(result, TabGroup)
        assert result.selected == "chart"

    def test_build_textarea(self) -> None:
        """_build_textarea creates TextArea component."""
        from pywry.mcp.builders import _build_textarea
        from pywry.toolbar import TextArea

        cfg = {"label": "Notes", "event": "form:notes", "rows": 5}
        result = _build_textarea(cfg)

        assert isinstance(result, TextArea)
        assert result.rows == 5

    def test_build_search(self) -> None:
        """_build_search creates SearchInput component."""
        from pywry.mcp.builders import _build_search
        from pywry.toolbar import SearchInput

        cfg = {"label": "Search", "event": "data:search", "debounce": 500}
        result = _build_search(cfg)

        assert isinstance(result, SearchInput)
        assert result.debounce == 500

    def test_build_date(self) -> None:
        """_build_date creates DateInput component."""
        from pywry.mcp.builders import _build_date
        from pywry.toolbar import DateInput

        cfg = {"label": "Date", "event": "form:date", "value": "2024-01-15"}
        result = _build_date(cfg)

        assert isinstance(result, DateInput)
        assert result.value == "2024-01-15"

    def test_build_range(self) -> None:
        """_build_range creates RangeInput component."""
        from pywry.mcp.builders import _build_range
        from pywry.toolbar import RangeInput

        cfg = {"event": "app:range", "start": 10, "end": 90, "min": 0, "max": 100}
        result = _build_range(cfg)

        assert isinstance(result, RangeInput)
        assert result.start == 10
        assert result.end == 90

    def test_build_secret(self) -> None:
        """_build_secret creates SecretInput component."""
        from pywry.mcp.builders import _build_secret
        from pywry.toolbar import SecretInput

        cfg = {"label": "API Key", "event": "form:api_key", "show_toggle": True}
        result = _build_secret(cfg)

        assert isinstance(result, SecretInput)
        assert result.show_toggle is True


# =============================================================================
# Test Tools Module
# =============================================================================


class TestToolsModule:
    """Tests for pywry.mcp.tools module."""

    def test_get_tools_returns_list(self) -> None:
        """get_tools returns list of Tool objects."""
        from pywry.mcp.tools import get_tools

        tools = get_tools()
        assert isinstance(tools, list)
        assert len(tools) > 0

    def test_get_tools_has_create_widget(self) -> None:
        """Tools include create_widget."""
        from pywry.mcp.tools import get_tools

        tools = get_tools()
        names = [t.name for t in tools]
        assert "create_widget" in names

    def test_get_tools_has_get_skills(self) -> None:
        """Tools include get_skills."""
        from pywry.mcp.tools import get_tools

        tools = get_tools()
        names = [t.name for t in tools]
        assert "get_skills" in names

    def test_get_tools_has_manipulation_tools(self) -> None:
        """Tools include widget manipulation tools."""
        from pywry.mcp.tools import get_tools

        tools = get_tools()
        names = [t.name for t in tools]

        expected = ["set_content", "set_style", "show_toast", "update_theme"]
        for tool_name in expected:
            assert tool_name in names, f"Missing tool: {tool_name}"

    def test_get_tools_has_management_tools(self) -> None:
        """Tools include widget management tools."""
        from pywry.mcp.tools import get_tools

        tools = get_tools()
        names = [t.name for t in tools]

        expected = ["list_widgets", "get_events", "destroy_widget"]
        for tool_name in expected:
            assert tool_name in names, f"Missing tool: {tool_name}"

    def test_tool_has_input_schema(self) -> None:
        """Each tool has inputSchema."""
        from pywry.mcp.tools import get_tools

        for tool in get_tools():
            assert tool.inputSchema is not None
            assert "type" in tool.inputSchema
            assert tool.inputSchema["type"] == "object"

    def test_component_types_list(self) -> None:
        """COMPONENT_TYPES contains all expected types."""
        from pywry.mcp.tools import COMPONENT_TYPES

        expected = [
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
        for comp in expected:
            assert comp in COMPONENT_TYPES


# =============================================================================
# Test Prompts Module
# =============================================================================


class TestPromptsModule:
    """Tests for pywry.mcp.prompts module."""

    def test_get_prompts_returns_list(self) -> None:
        """get_prompts returns list of Prompt objects."""
        from pywry.mcp.prompts import get_prompts

        prompts = get_prompts()
        assert isinstance(prompts, list)
        assert len(prompts) > 0

    def test_prompts_have_skill_prefix(self) -> None:
        """All prompts have 'skill:' prefix."""
        from pywry.mcp.prompts import get_prompts

        for prompt in get_prompts():
            assert prompt.name.startswith("skill:"), f"Missing prefix: {prompt.name}"

    def test_get_prompt_content_found(self) -> None:
        """get_prompt_content returns content for valid prompt."""
        from pywry.mcp.prompts import get_prompt_content

        result = get_prompt_content("skill:native")
        assert result is not None
        assert result.description is not None
        assert len(result.messages) > 0

    def test_get_prompt_content_not_found(self) -> None:
        """get_prompt_content returns None for invalid prompt."""
        from pywry.mcp.prompts import get_prompt_content

        result = get_prompt_content("skill:nonexistent_xyz")
        assert result is None

    def test_get_prompt_content_without_prefix(self) -> None:
        """get_prompt_content returns None without skill: prefix."""
        from pywry.mcp.prompts import get_prompt_content

        result = get_prompt_content("native")
        assert result is None


# =============================================================================
# Test Resources Module
# =============================================================================


class TestResourcesModule:
    """Tests for pywry.mcp.resources module."""

    def test_get_resources_returns_list(self) -> None:
        """get_resources returns list of Resource objects."""
        from pywry.mcp.resources import get_resources

        resources = get_resources()
        assert isinstance(resources, list)
        assert len(resources) > 0

    def test_resources_include_components(self) -> None:
        """Resources include component documentation."""
        from pywry.mcp.resources import get_resources

        resources = get_resources()
        uris = [str(r.uri) for r in resources]

        assert any("pywry://component/button" in uri for uri in uris)

    def test_resources_include_events_doc(self) -> None:
        """Resources include events documentation."""
        from pywry.mcp.resources import get_resources

        resources = get_resources()
        uris = [str(r.uri) for r in resources]

        assert any("pywry://docs/events" in uri for uri in uris)

    def test_resources_include_skills(self) -> None:
        """Skills are served via skill:// URIs by SkillsDirectoryProvider (not pywry:// URIs)."""
        # Skills are now delivered by SkillsDirectoryProvider as skill:// resources.
        # The pywry.mcp.resources module no longer lists pywry://skill/ URIs.
        from pywry.mcp.resources import get_resources

        resources = get_resources()
        uris = [str(r.uri) for r in resources]

        # Verify no legacy pywry://skill/ URIs remain
        assert not any("pywry://skill/" in uri for uri in uris)

    def test_get_resource_templates(self) -> None:
        """get_resource_templates returns template list."""
        from pywry.mcp.resources import get_resource_templates

        templates = get_resource_templates()
        assert isinstance(templates, list)
        assert len(templates) > 0

        # Check for expected templates
        uri_templates = [t.uriTemplate for t in templates]
        assert "pywry://component/{component}" in uri_templates
        assert "pywry://export/{widget_id}" in uri_templates

    def test_get_component_source_found(self) -> None:
        """get_component_source returns source code."""
        from pywry.mcp.resources import get_component_source

        source = get_component_source("button")
        assert source is not None
        assert "class Button" in source or "Button" in source

    def test_get_component_source_not_found(self) -> None:
        """get_component_source returns None for unknown component."""
        from pywry.mcp.resources import get_component_source

        source = get_component_source("nonexistent_component_xyz")
        assert source is None

    def test_export_widget_code_not_found(self) -> None:
        """export_widget_code returns None for unknown widget."""
        from pywry.mcp.resources import export_widget_code

        code = export_widget_code("nonexistent-widget-xyz")
        assert code is None

    def test_export_widget_code_with_config(self) -> None:
        """export_widget_code generates code for configured widget."""
        from pywry.mcp import state
        from pywry.mcp.resources import export_widget_code

        state._widget_configs.clear()
        state._widget_configs["test-export"] = {
            "html": "<div>Test</div>",
            "title": "Export Test",
            "height": 400,
            "toolbars": [
                {
                    "position": "top",
                    "items": [{"type": "button", "label": "Click", "event": "app:click"}],
                }
            ],
        }

        code = export_widget_code("test-export")
        assert code is not None
        assert "from pywry import PyWry" in code
        assert "Export Test" in code

        state._widget_configs.clear()

    def test_read_component_doc(self) -> None:
        """read_component_doc returns markdown for component."""
        from pywry.mcp.resources import read_component_doc

        doc = read_component_doc("button")
        assert doc is not None
        assert "Button" in doc
        assert "Properties" in doc

    def test_read_component_doc_not_found(self) -> None:
        """read_component_doc returns None for unknown component."""
        from pywry.mcp.resources import read_component_doc

        doc = read_component_doc("nonexistent_xyz")
        assert doc is None


# =============================================================================
# Test Handlers Module
# =============================================================================


class TestHandlersModule:
    """Tests for pywry.mcp.handlers module."""

    def test_handler_context_init(self) -> None:
        """HandlerContext initializes correctly."""
        from pywry.mcp.handlers import HandlerContext

        args = {"key": "value"}
        events: dict[str, list[dict[str, Any]]] = {}

        def make_cb(wid: str):
            return lambda d, e, lbl: None

        ctx = HandlerContext(args, events, make_cb, headless=True)

        assert ctx.args == args
        assert ctx.events == events
        assert ctx.headless is True

    def test_handle_get_skills_list(self) -> None:
        """_handle_get_skills lists all skills."""
        from pywry.mcp.handlers import HandlerContext, _handle_get_skills

        ctx = HandlerContext({}, {}, lambda w: lambda d, e, lbl: None, headless=False)
        result = _handle_get_skills(ctx)

        assert "available_skills" in result
        assert isinstance(result["available_skills"], list)

    def test_handle_get_skills_specific(self) -> None:
        """_handle_get_skills returns specific skill."""
        from pywry.mcp.handlers import HandlerContext, _handle_get_skills

        ctx = HandlerContext(
            {"skill": "native"}, {}, lambda w: lambda d, e, lbl: None, headless=False
        )
        result = _handle_get_skills(ctx)

        assert "skill" in result
        assert result["skill"] == "native"
        assert "guidance" in result

    def test_handle_get_skills_not_found(self) -> None:
        """_handle_get_skills returns error for unknown skill."""
        from pywry.mcp.handlers import HandlerContext, _handle_get_skills

        ctx = HandlerContext(
            {"skill": "nonexistent_xyz"},
            {},
            lambda w: lambda d, e, lbl: None,
            headless=False,
        )
        result = _handle_get_skills(ctx)

        assert "error" in result

    def test_handle_build_div(self) -> None:
        """_handle_build_div generates HTML."""
        from pywry.mcp.handlers import HandlerContext, _handle_build_div

        ctx = HandlerContext(
            {"content": "Hello", "component_id": "greeting"},
            {},
            lambda w: lambda d, e, lbl: None,
            headless=False,
        )
        result = _handle_build_div(ctx)

        assert "html" in result
        assert "greeting" in result["html"]
        assert "Hello" in result["html"]

    def test_handle_build_ticker_item(self) -> None:
        """_handle_build_ticker_item generates ticker HTML."""
        from pywry.mcp.handlers import HandlerContext, _handle_build_ticker_item

        ctx = HandlerContext(
            {"ticker": "AAPL", "text": "Apple: $150"},
            {},
            lambda w: lambda d, e, lbl: None,
            headless=False,
        )
        result = _handle_build_ticker_item(ctx)

        assert "html" in result
        assert "ticker" in result
        assert result["ticker"] == "AAPL"

    def test_handle_get_component_docs(self) -> None:
        """_handle_get_component_docs returns documentation."""
        from pywry.mcp.handlers import HandlerContext, _handle_get_component_docs

        ctx = HandlerContext(
            {"component": "button"},
            {},
            lambda w: lambda d, e, lbl: None,
            headless=False,
        )
        result = _handle_get_component_docs(ctx)

        assert "component" in result
        assert result["component"] == "button"
        assert "name" in result
        assert "properties" in result

    def test_handle_get_component_docs_not_found(self) -> None:
        """_handle_get_component_docs returns error for unknown component."""
        from pywry.mcp.handlers import HandlerContext, _handle_get_component_docs

        ctx = HandlerContext(
            {"component": "unknown_xyz"},
            {},
            lambda w: lambda d, e, lbl: None,
            headless=False,
        )
        result = _handle_get_component_docs(ctx)

        assert "error" in result

    def test_handle_list_widgets_empty(self) -> None:
        """_handle_list_widgets returns empty list when no widgets."""
        from pywry.mcp.handlers import HandlerContext, _handle_list_widgets
        from pywry.mcp.state import _widgets

        _widgets.clear()

        ctx = HandlerContext({}, {}, lambda w: lambda d, e, lbl: None, headless=False)
        result = _handle_list_widgets(ctx)

        assert "widgets" in result
        assert result["count"] == 0

    def test_handle_get_events(self) -> None:
        """_handle_get_events returns widget events."""
        from pywry.mcp.handlers import HandlerContext, _handle_get_events

        events: dict[str, list[dict[str, Any]]] = {
            "widget-1": [{"event_type": "click", "data": {}, "label": "btn"}]
        }

        ctx = HandlerContext(
            {"widget_id": "widget-1", "clear": False},
            events,
            lambda w: lambda d, e, lbl: None,
            headless=False,
        )
        result = _handle_get_events(ctx)

        assert "events" in result
        assert len(result["events"]) == 1

    def test_handle_get_events_with_clear(self) -> None:
        """_handle_get_events clears events when requested."""
        from pywry.mcp.handlers import HandlerContext, _handle_get_events

        events: dict[str, list[dict[str, Any]]] = {
            "widget-2": [{"event_type": "submit", "data": {}, "label": ""}]
        }

        ctx = HandlerContext(
            {"widget_id": "widget-2", "clear": True},
            events,
            lambda w: lambda d, e, lbl: None,
            headless=False,
        )
        _handle_get_events(ctx)

        assert not events["widget-2"]

    def test_handle_destroy_widget(self) -> None:
        """_handle_destroy_widget removes widget."""
        from pywry.mcp.handlers import HandlerContext, _handle_destroy_widget
        from pywry.mcp.state import _widgets

        _widgets.clear()
        _widgets["to-destroy"] = MagicMock()

        events: dict[str, list[dict[str, Any]]] = {"to-destroy": []}

        ctx = HandlerContext(
            {"widget_id": "to-destroy"},
            events,
            lambda w: lambda d, e, lbl: None,
            headless=False,
        )
        result = _handle_destroy_widget(ctx)

        assert result["destroyed"] is True
        assert "to-destroy" not in _widgets

        _widgets.clear()

    def test_handlers_dispatch_table(self) -> None:
        """_HANDLERS contains all expected handlers."""
        from pywry.mcp.handlers import _HANDLERS

        expected = [
            "get_skills",
            "create_widget",
            "build_div",
            "build_ticker_item",
            "set_content",
            "set_style",
            "show_toast",
            "list_widgets",
            "get_events",
            "destroy_widget",
        ]

        for name in expected:
            assert name in _HANDLERS, f"Missing handler: {name}"

    def test_get_widget_or_error_found(self) -> None:
        """_get_widget_or_error returns widget when found."""
        from pywry.mcp.handlers import _get_widget_or_error
        from pywry.mcp.state import _widgets

        _widgets.clear()
        mock_widget = MagicMock()
        _widgets["found-widget"] = mock_widget

        widget, error = _get_widget_or_error("found-widget")

        assert widget is mock_widget
        assert error is None

        _widgets.clear()

    def test_get_widget_or_error_not_found(self) -> None:
        """_get_widget_or_error returns error when not found."""
        from pywry.mcp.handlers import _get_widget_or_error
        from pywry.mcp.state import _widgets

        _widgets.clear()

        widget, error = _get_widget_or_error("missing-widget")

        assert widget is None
        assert error is not None
        assert "error" in error

    @pytest.mark.asyncio
    async def test_handle_tool_unknown(self) -> None:
        """handle_tool returns error for unknown tool."""
        from pywry.mcp.handlers import handle_tool

        result = await handle_tool("unknown_tool_xyz", {}, {}, lambda w: lambda d, e, lbl: None)

        assert "error" in result
        assert "Unknown tool" in result["error"]

    @pytest.mark.asyncio
    async def test_handle_tool_get_skills(self) -> None:
        """handle_tool dispatches to get_skills handler."""
        from pywry.mcp.handlers import handle_tool

        result = await handle_tool("get_skills", {}, {}, lambda w: lambda d, e, lbl: None)

        assert "available_skills" in result


# =============================================================================
# Test Server Module
# =============================================================================


class TestServerModule:
    """Tests for pywry.mcp.server module."""

    def test_has_mcp_flag(self) -> None:
        """HAS_MCP flag indicates mcp package availability."""
        from pywry.mcp.server import HAS_MCP

        # Should be True if tests can import mcp
        assert isinstance(HAS_MCP, bool)

    def test_make_event_callback(self) -> None:
        """_make_event_callback creates working callback."""
        from pywry.mcp.server import _events, _make_event_callback

        _events.pop("widget-1", None)
        callback = _make_event_callback("widget-1")

        callback({"clicked": True}, "button:click", "Save")

        assert "widget-1" in _events
        assert len(_events["widget-1"]) == 1
        assert _events["widget-1"][0]["event_type"] == "button:click"

        _events.pop("widget-1", None)

    def test_create_server(self) -> None:
        """create_server returns configured Server."""
        from pywry.mcp.server import HAS_MCP, create_server

        if not HAS_MCP:
            pytest.skip("mcp package not available")

        server = create_server()
        assert server is not None
        assert server.name == "pywry-widgets"

    def test_create_server_custom_name(self) -> None:
        """create_server accepts custom name."""
        from pywry.config import MCPSettings
        from pywry.mcp.server import HAS_MCP, create_server

        if not HAS_MCP:
            pytest.skip("mcp package not available")

        server = create_server(MCPSettings(name="my-custom-server"))
        assert server.name == "my-custom-server"


# =============================================================================
# Test Handler Helper Functions
# =============================================================================


class TestHandlerHelpers:
    """Tests for handler helper functions."""

    def test_apply_action_increment(self) -> None:
        """_apply_action handles increment."""
        from pywry.mcp.handlers import _apply_action

        state: dict[str, Any] = {"value": 5}
        mock_widget = MagicMock()

        _apply_action("increment", {"state_key": "value"}, state, mock_widget, "counter")

        assert state["value"] == 6
        mock_widget.emit.assert_called_once()

    def test_apply_action_decrement(self) -> None:
        """_apply_action handles decrement."""
        from pywry.mcp.handlers import _apply_action

        state: dict[str, Any] = {"value": 10}
        mock_widget = MagicMock()

        _apply_action("decrement", {"state_key": "value"}, state, mock_widget, "counter")

        assert state["value"] == 9

    def test_apply_action_set(self) -> None:
        """_apply_action handles set."""
        from pywry.mcp.handlers import _apply_action

        state: dict[str, Any] = {"value": 5}
        mock_widget = MagicMock()

        _apply_action("set", {"state_key": "value", "value": 100}, state, mock_widget, None)

        assert state["value"] == 100

    def test_apply_action_toggle(self) -> None:
        """_apply_action handles toggle."""
        from pywry.mcp.handlers import _apply_action

        state: dict[str, Any] = {"value": False}
        mock_widget = MagicMock()

        _apply_action("toggle", {"state_key": "value"}, state, mock_widget, "status")

        assert state["value"] is True

    def test_apply_action_emit(self) -> None:
        """_apply_action handles emit."""
        from pywry.mcp.handlers import _apply_action

        state: dict[str, Any] = {}
        mock_widget = MagicMock()

        _apply_action(
            "emit",
            {"emit_event": "custom:event", "emit_data": {"key": "value"}},
            state,
            mock_widget,
            None,
        )

        mock_widget.emit.assert_called_once_with("custom:event", {"key": "value"})

    def test_infer_callbacks_from_toolbars(self) -> None:
        """_infer_callbacks_from_toolbars auto-wires callbacks."""
        from pywry.mcp.handlers import _infer_callbacks_from_toolbars
        from pywry.toolbar import Button, Toolbar

        toolbars = [
            Toolbar(
                position="top",
                items=[
                    Button(label="+", event="counter:increment"),
                    Button(label="-", event="counter:decrement"),
                    Button(label="Reset", event="counter:reset"),
                ],
            )
        ]

        callbacks: dict[str, Any] = {}
        _infer_callbacks_from_toolbars(toolbars, callbacks)

        assert "counter:increment" in callbacks
        assert callbacks["counter:increment"]["action"] == "increment"
        assert "counter:decrement" in callbacks
        assert callbacks["counter:decrement"]["action"] == "decrement"
        assert "counter:reset" in callbacks
        assert callbacks["counter:reset"]["action"] == "set"


# =============================================================================
# Test Install Module
# =============================================================================


class TestInstallModule:
    """Tests for pywry.mcp.install module."""

    def test_list_bundled_skills_returns_list(self) -> None:
        """list_bundled_skills returns a non-empty list of skill names."""
        from pywry.mcp.install import list_bundled_skills

        skills = list_bundled_skills()
        assert isinstance(skills, list)
        assert len(skills) > 0

    def test_list_bundled_skills_sorted(self) -> None:
        """list_bundled_skills returns skills in sorted order."""
        from pywry.mcp.install import list_bundled_skills

        skills = list_bundled_skills()
        assert skills == sorted(skills)

    def test_list_bundled_skills_has_native(self) -> None:
        """list_bundled_skills includes the 'native' skill."""
        from pywry.mcp.install import list_bundled_skills

        assert "native" in list_bundled_skills()

    def test_vendor_dirs_mapping(self) -> None:
        """VENDOR_DIRS contains expected platform keys."""
        from pywry.mcp.install import VENDOR_DIRS

        expected_keys = {
            "claude",
            "cursor",
            "vscode",
            "copilot",
            "codex",
            "gemini",
            "goose",
            "opencode",
        }
        assert expected_keys <= set(VENDOR_DIRS.keys())

    def test_all_targets_sorted(self) -> None:
        """ALL_TARGETS is sorted."""
        from pywry.mcp.install import ALL_TARGETS

        assert sorted(ALL_TARGETS) == ALL_TARGETS

    def test_install_skills_dry_run(self, tmp_path: Any) -> None:
        """install_skills with dry_run=True does not write any files."""
        from pywry.mcp.install import install_skills

        results = install_skills(
            targets=[],  # empty → all
            overwrite=False,
            custom_dir=tmp_path / "skills",
            dry_run=True,
        )

        # Nothing should have been created
        assert not (tmp_path / "skills").exists()
        # Results should be present with dry_run status
        assert "custom" in results
        for status in results["custom"].values():
            assert status == "dry_run"

    def test_install_skills_to_custom_dir(self, tmp_path: Any) -> None:
        """install_skills copies skill directories to the target path."""
        from pywry.mcp.install import install_skills, list_bundled_skills

        custom_target = tmp_path / "skills"
        results = install_skills(
            targets=[],
            overwrite=False,
            custom_dir=custom_target,
        )

        assert "custom" in results
        for status in results["custom"].values():
            assert status in ("installed", "skipped", "dry_run") or status.startswith("error:")

        # At least one skill should have been installed
        installed = [v for v in results["custom"].values() if v == "installed"]
        assert len(installed) > 0

        # Each installed skill should have its SKILL.md
        for skill_name in list_bundled_skills():
            assert (custom_target / skill_name / "SKILL.md").exists()

    def test_install_skills_skip_existing(self, tmp_path: Any) -> None:
        """install_skills with overwrite=False skips existing skill dirs."""
        from pywry.mcp.install import install_skills

        custom_target = tmp_path / "skills"

        # First install
        install_skills(targets=[], custom_dir=custom_target)

        # Modify one skill to detect if it gets overwritten
        sentinel = custom_target / "native" / "sentinel.txt"
        sentinel.write_text("original", encoding="utf-8")

        # Second install without overwrite
        results = install_skills(targets=[], custom_dir=custom_target, overwrite=False)
        assert results["custom"].get("native") == "skipped"
        assert sentinel.exists()  # file untouched

    def test_install_skills_overwrite(self, tmp_path: Any) -> None:
        """install_skills with overwrite=True replaces existing skill dirs."""
        from pywry.mcp.install import install_skills

        custom_target = tmp_path / "skills"

        # First install
        install_skills(targets=[], custom_dir=custom_target)

        # Plant a sentinel file that should be removed on overwrite
        sentinel = custom_target / "native" / "sentinel.txt"
        sentinel.write_text("original", encoding="utf-8")

        # Second install with overwrite
        results = install_skills(targets=[], custom_dir=custom_target, overwrite=True)
        assert results["custom"].get("native") == "installed"
        assert not sentinel.exists()  # old file gone

    def test_install_skills_unknown_target_raises(self) -> None:
        """install_skills raises ValueError for unknown vendor targets."""
        from pywry.mcp.install import install_skills

        with pytest.raises(ValueError, match="Unknown target"):
            install_skills(targets=["nonexistent_vendor_xyz"])

    def test_install_skills_subset_of_skills(self, tmp_path: Any) -> None:
        """install_skills installs only the requested skill_names."""
        from pywry.mcp.install import install_skills

        custom_target = tmp_path / "skills"
        results = install_skills(
            targets=[],
            custom_dir=custom_target,
            skill_names=["native"],
        )

        assert results["custom"].get("native") == "installed"
        assert (custom_target / "native" / "SKILL.md").exists()
        # Other skills should NOT have been installed
        from pywry.mcp.install import list_bundled_skills

        other_skills = [s for s in list_bundled_skills() if s != "native"]
        for skill in other_skills:
            assert not (custom_target / skill).exists()

    def test_install_skills_all_keyword(self) -> None:
        """install_skills accepts 'all' to expand to every vendor."""
        from pywry.mcp.install import ALL_TARGETS, install_skills

        # We can't write to real vendor dirs in tests, so just use dry_run
        results = install_skills(targets=["all"], dry_run=True)
        assert set(results.keys()) == set(ALL_TARGETS)


# =============================================================================
# Test Agentic Module
# =============================================================================


class TestAgenticModule:
    """Tests for pywry.mcp.agentic module."""

    # ------------------------------------------------------------------
    # Pydantic model validation
    # ------------------------------------------------------------------

    def test_component_spec_defaults(self) -> None:
        """ComponentSpec validates with minimal required fields."""
        from pywry.mcp.agentic import ComponentSpec

        comp = ComponentSpec(type="button", label="Refresh", event="chart:refresh")
        assert comp.type == "button"
        assert comp.variant == "neutral"
        assert comp.options == []

    def test_toolbar_spec(self) -> None:
        """ToolbarSpec holds position and items."""
        from pywry.mcp.agentic import ComponentSpec, ToolbarSpec

        tb = ToolbarSpec(
            position="top",
            items=[ComponentSpec(type="button", label="Go", event="app:go")],
        )
        assert tb.position == "top"
        assert len(tb.items) == 1

    def test_widget_plan_defaults(self) -> None:
        """WidgetPlan validates and applies defaults."""
        from pywry.mcp.agentic import WidgetPlan

        plan = WidgetPlan(
            title="Test App",
            description="A test widget",
            html_content="<p>Hello</p>",
        )
        assert plan.width == 900
        assert plan.height == 600
        assert plan.include_plotly is False
        assert plan.include_aggrid is False
        assert plan.toolbars == []
        assert plan.callbacks == []

    def test_callback_spec(self) -> None:
        """CallbackSpec captures event→action mapping."""
        from pywry.mcp.agentic import CallbackSpec

        cb = CallbackSpec(event="counter:increment", action="increment")
        assert cb.action == "increment"
        assert cb.target == ""

    # ------------------------------------------------------------------
    # _plan_to_create_args helper
    # ------------------------------------------------------------------

    def test_plan_to_create_args_basic(self) -> None:
        """_plan_to_create_args returns expected keys."""
        from pywry.mcp.agentic import ComponentSpec, ToolbarSpec, WidgetPlan, _plan_to_create_args

        plan = WidgetPlan(
            title="My App",
            description="Test",
            html_content="<p>content</p>",
            toolbars=[
                ToolbarSpec(
                    position="top",
                    items=[ComponentSpec(type="button", label="Click", event="app:click")],
                )
            ],
        )
        args = _plan_to_create_args(plan)
        assert args["title"] == "My App"
        assert args["html"] == "<p>content</p>"
        assert "toolbars" in args
        assert len(args["toolbars"]) == 1
        assert args["toolbars"][0]["position"] == "top"
        assert args["toolbars"][0]["items"][0]["type"] == "button"

    def test_plan_to_create_args_callbacks(self) -> None:
        """_plan_to_create_args converts CallbackSpec list to dict."""
        from pywry.mcp.agentic import CallbackSpec, WidgetPlan, _plan_to_create_args

        plan = WidgetPlan(
            title="App",
            description="x",
            html_content="<p></p>",
            callbacks=[CallbackSpec(event="btn:click", action="increment")],
        )
        args = _plan_to_create_args(plan)
        assert "callbacks" in args
        assert args["callbacks"]["btn:click"]["action"] == "increment"

    def test_plan_to_create_args_no_toolbars(self) -> None:
        """_plan_to_create_args omits toolbars key when plan has none."""
        from pywry.mcp.agentic import WidgetPlan, _plan_to_create_args

        plan = WidgetPlan(title="A", description="b", html_content="<p></p>")
        args = _plan_to_create_args(plan)
        assert "toolbars" not in args
        assert "callbacks" not in args

    # ------------------------------------------------------------------
    # _generate_project_files helper
    # ------------------------------------------------------------------

    def test_generate_project_files_keys(self) -> None:
        """_generate_project_files always produces main.py, requirements.txt, README.md."""
        from pywry.mcp.agentic import _generate_project_files

        files = _generate_project_files({}, "my_app")
        assert "main.py" in files
        assert "requirements.txt" in files
        assert "README.md" in files

    def test_generate_project_files_requirements_content(self) -> None:
        """requirements.txt contains pywry dependency."""
        from pywry.mcp.agentic import _generate_project_files

        files = _generate_project_files({}, "my_app")
        assert "pywry" in files["requirements.txt"]

    def test_generate_project_files_readme_title(self) -> None:
        """README.md uses the project name as its heading."""
        from pywry.mcp.agentic import _generate_project_files

        files = _generate_project_files({}, "cool_project")
        assert "# cool_project" in files["README.md"]

    # ------------------------------------------------------------------
    # export_project — integration with state (mocked ctx)
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_export_project_missing_widget(self) -> None:
        """export_project returns error when widget_id not in state."""
        import json

        from unittest.mock import AsyncMock

        from pywry.mcp.agentic import export_project

        ctx = MagicMock()
        ctx.report_progress = AsyncMock()

        result = await export_project(
            widget_ids=["does-not-exist"],
            ctx=ctx,
        )
        data = json.loads(result)
        assert "error" in data
        assert "does-not-exist" in data["error"]

    @pytest.mark.asyncio
    async def test_export_project_generates_files(self) -> None:
        """export_project creates project files for a known widget."""
        import json

        from unittest.mock import AsyncMock

        from pywry.mcp.agentic import export_project
        from pywry.mcp.state import store_widget_config

        # Seed a widget config
        store_widget_config(
            "test-export-001",
            {
                "title": "Test Widget",
                "html": "<p>Hello</p>",
                "width": 800,
                "height": 500,
                "include_plotly": False,
                "include_aggrid": False,
                "toolbars": [],
            },
        )

        ctx = MagicMock()
        ctx.report_progress = AsyncMock()

        result = await export_project(
            widget_ids=["test-export-001"],
            ctx=ctx,
            project_name="test_proj",
        )
        data = json.loads(result)
        assert "files" in data
        assert "main.py" in data["files"]
        assert "requirements.txt" in data["files"]
        assert "README.md" in data["files"]

    @pytest.mark.asyncio
    async def test_export_project_writes_to_disk(self, tmp_path: Any) -> None:
        """export_project writes files when output_dir is provided."""
        import json

        from unittest.mock import AsyncMock

        from pywry.mcp.agentic import export_project
        from pywry.mcp.state import store_widget_config

        store_widget_config(
            "test-export-002",
            {
                "title": "Disk Widget",
                "html": "<p>Hi</p>",
                "width": 800,
                "height": 500,
                "include_plotly": False,
                "include_aggrid": False,
                "toolbars": [],
            },
        )

        ctx = MagicMock()
        ctx.report_progress = AsyncMock()

        result = await export_project(
            widget_ids=["test-export-002"],
            ctx=ctx,
            project_name="disk_proj",
            output_dir=str(tmp_path),
        )
        data = json.loads(result)
        assert "files_written" in data
        proj_root = tmp_path / "disk_proj"
        assert (proj_root / "main.py").exists()
        assert (proj_root / "requirements.txt").exists()
        assert (proj_root / "README.md").exists()

    # ------------------------------------------------------------------
    # build_app — sampling mocked
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_build_app_returns_widget_id_and_code(self) -> None:
        """build_app returns widget_id and python_code when sampling succeeds."""
        import json

        from unittest.mock import AsyncMock

        from pywry.mcp.agentic import WidgetPlan, build_app

        # Build a minimal valid plan the mock will return
        mock_plan = WidgetPlan(
            title="Counter",
            description="A simple counter widget",
            html_content="<div id='counter'>0</div>",
        )

        mock_sample_result = MagicMock()
        mock_sample_result.result = mock_plan

        ctx = MagicMock()
        ctx.report_progress = AsyncMock()
        ctx.sample = AsyncMock(return_value=mock_sample_result)

        result = await build_app(
            description="A simple counter",
            ctx=ctx,
        )
        data = json.loads(result)
        assert "widget_id" in data
        assert "python_code" in data
        assert "Counter" in data["title"]
        assert len(data["widget_id"]) > 0
        # python_code must contain at least the title
        assert "Counter" in data["python_code"]

    # ------------------------------------------------------------------
    # plan_widget — sampling mocked
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_plan_widget_returns_valid_json(self) -> None:
        """plan_widget returns a JSON-serialized WidgetPlan."""
        import json

        from unittest.mock import AsyncMock

        from pywry.mcp.agentic import WidgetPlan, plan_widget

        mock_plan = WidgetPlan(
            title="Price Dashboard",
            description="Crypto price display",
            html_content="<div>BTC: $100k</div>",
        )
        mock_result = MagicMock()
        mock_result.result = mock_plan

        ctx = MagicMock()
        ctx.report_progress = AsyncMock()
        ctx.sample = AsyncMock(return_value=mock_result)

        result = await plan_widget("crypto price dashboard", ctx)
        data = json.loads(result)
        # Must contain WidgetPlan fields
        assert data["title"] == "Price Dashboard"
        assert "html_content" in data
        assert "toolbars" in data

    # ------------------------------------------------------------------
    # Skills metadata includes the new skill
    # ------------------------------------------------------------------

    def test_autonomous_building_in_skill_metadata(self) -> None:
        """SKILL_METADATA includes autonomous_building."""
        from pywry.mcp.skills import SKILL_METADATA

        assert "autonomous_building" in SKILL_METADATA

    def test_autonomous_building_skill_file_exists(self) -> None:
        """autonomous_building/SKILL.md exists on disk."""
        from pywry.mcp.skills import SKILLS_DIR

        assert (SKILLS_DIR / "autonomous_building" / "SKILL.md").exists()

    def test_load_autonomous_building_skill(self) -> None:
        """load_skill('autonomous_building') returns non-empty content."""
        from pywry.mcp.skills import load_skill

        content = load_skill("autonomous_building")
        assert content is not None
        assert len(content) > 100
        assert "build_app" in content
