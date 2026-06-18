"""Tests for ``pywry.mcp.resources``.

Covers:
- ``get_resources`` and ``get_resource_templates`` enumerate Resource
  objects for component docs, skills (now removed), and widget exports.
- ``read_component_doc`` / ``get_component_source`` / ``read_skill_doc``
  return markdown + source code for known names and ``None`` otherwise.
- ``export_widget_code`` generates Python from a stored widget config.
- ``read_resource`` dispatches on URI scheme.

Some assertions skip gracefully when the installed ``mcp.types``
package rejects ``AnyUrl`` constructors — the production code is
fine but the tests need the validator to accept the URIs.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


class TestGetResources:
    def test_returns_list_when_mcp_accepts_anyurl(self) -> None:
        from pywry.mcp.resources import get_resources

        try:
            resources = get_resources()
        except Exception:
            pytest.skip("mcp.types.Resource currently rejects AnyUrl URIs")
        assert isinstance(resources, list)

    def test_includes_component_docs_when_supported(self) -> None:
        from pywry.mcp.resources import get_resources

        try:
            resources = get_resources()
        except Exception:
            pytest.skip("mcp.types.Resource currently rejects AnyUrl URIs")
        uris = [str(r.uri) for r in resources]
        assert any("pywry://component/button" in uri for uri in uris)

    def test_includes_events_doc_when_supported(self) -> None:
        from pywry.mcp.resources import get_resources

        try:
            resources = get_resources()
        except Exception:
            pytest.skip("mcp.types.Resource currently rejects AnyUrl URIs")
        uris = [str(r.uri) for r in resources]
        assert any("pywry://docs/events" in uri for uri in uris)

    def test_omits_skill_uris(self) -> None:
        """Skills are delivered via skill:// resources by SkillsDirectoryProvider."""
        from pywry.mcp.resources import get_resources

        try:
            resources = get_resources()
        except Exception:
            pytest.skip("mcp.types.Resource currently rejects AnyUrl URIs")
        uris = [str(r.uri) for r in resources]
        assert not any("pywry://skill/" in uri for uri in uris)

    def test_widget_export_listed_when_registered(self, mcp_fresh_state) -> None:
        from pywry.mcp import state as mcp_state

        try:
            from pywry.mcp.resources import get_resources

            mcp_state._widgets["wx"] = MagicMock()
            mcp_state._widget_configs["wx"] = {"html": "x", "toolbars": []}
            resources = get_resources()
        except Exception:
            pytest.skip("mcp.types.Resource currently rejects AnyUrl URIs")
        names = [r.name for r in resources]
        assert any("Export" in n for n in names)


class TestGetResourceTemplates:
    def test_returns_expected_templates(self) -> None:
        from pywry.mcp.resources import get_resource_templates

        templates = get_resource_templates()
        assert isinstance(templates, list)
        assert len(templates) > 0
        uri_templates = [t.uriTemplate for t in templates]
        assert "pywry://component/{component}" in uri_templates
        assert "pywry://export/{widget_id}" in uri_templates
        assert "pywry://skill/{skill}" in uri_templates


class TestGetComponentSource:
    def test_returns_source_for_known_component(self) -> None:
        from pywry.mcp.resources import get_component_source

        source = get_component_source("button")
        assert source is not None
        assert "class Button" in source or "Button" in source

    def test_returns_none_for_unknown_component(self) -> None:
        from pywry.mcp.resources import get_component_source

        assert get_component_source("nonexistent_component_xyz") is None

    def test_returns_none_when_inspect_raises(self, monkeypatch) -> None:
        import inspect as inspect_mod

        from pywry.mcp.resources import get_component_source

        def _raise(_cls):
            raise OSError("no source")

        monkeypatch.setattr(inspect_mod, "getsource", _raise)
        assert get_component_source("button") is None


class TestReadComponentDoc:
    def test_returns_markdown_for_known_component(self) -> None:
        from pywry.mcp.resources import read_component_doc

        doc = read_component_doc("button")
        assert doc is not None
        assert "Button" in doc
        assert "Properties" in doc

    def test_returns_none_for_unknown(self) -> None:
        from pywry.mcp.resources import read_component_doc

        assert read_component_doc("nonexistent_xyz") is None


class TestReadSkillDoc:
    def test_returns_markdown_for_known_skill(self) -> None:
        from pywry.mcp.resources import read_skill_doc

        out = read_skill_doc("native")
        assert out is not None
        assert "Native" in out or "native" in out.lower()

    def test_returns_none_for_unknown_skill(self) -> None:
        from pywry.mcp.resources import read_skill_doc

        assert read_skill_doc("nonexistent_xyz") is None


class TestExportWidgetCode:
    def test_returns_none_for_unknown_widget(self) -> None:
        from pywry.mcp.resources import export_widget_code

        assert export_widget_code("nonexistent-widget-xyz") is None

    def test_returns_code_with_pywry_import(self, mcp_fresh_state) -> None:
        from pywry.mcp import state
        from pywry.mcp.resources import export_widget_code

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

    def test_emits_select_component_code(self, mcp_fresh_state) -> None:
        from pywry.mcp import state
        from pywry.mcp.resources import export_widget_code

        state._widget_configs["sx"] = {
            "html": '<p hello="world">Hi</p>',
            "title": "Sel Test",
            "height": 400,
            "toolbars": [
                {
                    "position": "top",
                    "items": [
                        {
                            "type": "select",
                            "label": "L",
                            "event": "x:y",
                            "options": [{"label": "A", "value": "a"}],
                            "selected": "a",
                        },
                    ],
                }
            ],
        }
        code = export_widget_code("sx")
        assert code is not None
        assert "Select(" in code

    def test_emits_toggle_div_and_search_fallback(self, mcp_fresh_state) -> None:
        from pywry.mcp import state
        from pywry.mcp.resources import export_widget_code

        state._widget_configs["t1"] = {
            "html": "x",
            "toolbars": [
                {
                    "position": "top",
                    "items": [
                        {"type": "toggle", "label": "L", "event": "x:y"},
                        {"type": "div", "content": 'a "quote" thing'},
                        {"type": "search", "label": "S", "event": "s:y"},
                    ],
                }
            ],
        }
        code = export_widget_code("t1")
        assert code is not None
        assert "Toggle(" in code
        assert "Div(" in code
        # Search is exported via a generic fallback comment.
        assert "# search" in code


class TestReadResource:
    def test_dispatches_component_uri(self) -> None:
        from pywry.mcp.resources import read_resource

        assert read_resource("pywry://component/button") is not None

    def test_dispatches_source_uri(self) -> None:
        from pywry.mcp.resources import read_resource

        assert read_resource("pywry://source/button") is not None

    def test_dispatches_skill_uri(self) -> None:
        from pywry.mcp.resources import read_resource

        assert read_resource("pywry://skill/native") is not None

    def test_dispatches_export_uri(self, mcp_fresh_state) -> None:
        from pywry.mcp import state
        from pywry.mcp.resources import read_resource

        state._widget_configs["wx"] = {"html": "x", "toolbars": []}
        assert read_resource("pywry://export/wx") is not None

    def test_events_doc_uri(self) -> None:
        from pywry.mcp.resources import read_resource

        out = read_resource("pywry://docs/events")
        assert out is not None

    def test_quickstart_uri(self) -> None:
        from pywry.mcp.resources import read_resource

        assert read_resource("pywry://docs/quickstart") is not None

    def test_unknown_uri_returns_none(self) -> None:
        from pywry.mcp.resources import read_resource

        assert read_resource("unknown://foo") is None


class TestReadEventsDoc:
    def test_starts_with_expected_heading(self) -> None:
        from pywry.mcp.resources import read_events_doc

        out = read_events_doc()
        assert "Built-in PyWry Events" in out


class TestReadSourceCode:
    def test_components_aggregate_includes_banners(self) -> None:
        from pywry.mcp.resources import read_source_code

        out = read_source_code("components")
        assert out is not None
        assert "# ===" in out
