"""Tests for ``pywry.mcp.docs``.

Covers the static component documentation registry and the built-in
event documentation table.
"""

from __future__ import annotations


class TestComponentDocs:
    def test_button_present(self) -> None:
        from pywry.mcp.docs import COMPONENT_DOCS

        assert "button" in COMPONENT_DOCS
        assert COMPONENT_DOCS["button"]["name"] == "Button"

    def test_all_expected_types_present(self) -> None:
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

    def test_every_component_has_properties(self) -> None:
        from pywry.mcp.docs import COMPONENT_DOCS

        for comp_name, doc in COMPONENT_DOCS.items():
            assert "properties" in doc, f"{comp_name} missing properties"
            assert isinstance(doc["properties"], dict)

    def test_every_component_has_example(self) -> None:
        from pywry.mcp.docs import COMPONENT_DOCS

        for comp_name, doc in COMPONENT_DOCS.items():
            assert "example" in doc, f"{comp_name} missing example"
            assert len(doc["example"]) > 0


class TestBuiltinEvents:
    def test_dict_is_non_empty(self) -> None:
        from pywry.mcp.docs import BUILTIN_EVENTS

        assert isinstance(BUILTIN_EVENTS, dict)
        assert len(BUILTIN_EVENTS) > 0

    def test_known_events_documented(self) -> None:
        from pywry.mcp.docs import BUILTIN_EVENTS

        assert "pywry:set-content" in BUILTIN_EVENTS or "pywry:update-theme" in BUILTIN_EVENTS
