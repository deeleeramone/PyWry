"""Tests for pywry.mcp.tools."""

from __future__ import annotations

import pytest


pytest.importorskip("mcp")


from pywry.mcp.tools import COMPONENT_TYPES, TOOLBAR_ITEM_SCHEMA, TOOLBAR_SCHEMA, get_tools


class TestToolSchemas:
    def test_component_types_includes_basic(self):
        assert "button" in COMPONENT_TYPES
        assert "select" in COMPONENT_TYPES
        assert "marquee" in COMPONENT_TYPES

    def test_toolbar_item_schema_requires_type(self):
        assert "type" in TOOLBAR_ITEM_SCHEMA["required"]
        assert TOOLBAR_ITEM_SCHEMA["properties"]["type"]["enum"] == COMPONENT_TYPES

    def test_toolbar_schema_has_position_and_items(self):
        props = TOOLBAR_SCHEMA["properties"]
        assert "position" in props
        assert "items" in props


class TestGetTools:
    def test_returns_non_empty_list(self):
        tools = get_tools()
        assert isinstance(tools, list)
        assert len(tools) > 0

    def test_includes_core_tools(self):
        names = {t.name for t in get_tools()}
        for tool in [
            "get_skills",
            "create_widget",
            "build_div",
            "show_plotly",
            "show_dataframe",
            "show_tvchart",
            "set_content",
            "set_style",
            "show_toast",
            "update_theme",
            "list_widgets",
            "destroy_widget",
            "send_event",
            "get_events",
        ]:
            assert tool in names, f"Missing tool: {tool}"

    def test_tvchart_tools_present(self):
        names = {t.name for t in get_tools()}
        for tool in [
            "tvchart_update_series",
            "tvchart_update_bar",
            "tvchart_add_series",
            "tvchart_remove_series",
            "tvchart_add_markers",
            "tvchart_add_price_line",
            "tvchart_add_indicator",
        ]:
            assert tool in names

    def test_chat_tools_present(self):
        names = {t.name for t in get_tools()}
        for tool in [
            "create_chat_widget",
            "chat_send_message",
            "chat_stop_generation",
            "chat_manage_thread",
            "chat_register_command",
            "chat_get_history",
            "chat_update_settings",
            "chat_set_typing",
        ]:
            assert tool in names

    def test_each_tool_has_name_and_description(self):
        for tool in get_tools():
            assert tool.name
            assert tool.description
            assert tool.inputSchema is not None

    def test_input_schemas_are_dicts(self):
        for tool in get_tools():
            assert isinstance(tool.inputSchema, dict)
