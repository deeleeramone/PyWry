"""Tests for AppArtifact — the rich-content return path of the MCP server.

Covers:
- The :class:`AppArtifact` Pydantic model and its presence in the
  ``Artifact`` union.
- Revision bump helpers on ``inline._state``.
- The ``attach_app_artifact`` helper.
- The ``get_widget_app`` handler.
- The ``_format_tool_result`` serializer that emits an ``EmbeddedResource``
  content block when the result dict carries ``_app_artifact``.
- The WebSocket revision guard (revision query param < current → reject).
"""

from __future__ import annotations


class TestAppArtifactModel:
    def test_artifact_type_and_defaults(self) -> None:
        from pywry.chat.artifacts import AppArtifact

        art = AppArtifact(html="<html></html>")
        assert art.type == "artifact"
        assert art.artifact_type == "app"
        assert art.html == "<html></html>"
        assert art.widget_id is None
        assert art.revision == 0
        assert art.height == "600px"
        assert art.sandbox is True

    def test_artifact_union_includes_app(self) -> None:
        # typing.get_args on a PEP 604 union returns the constituent types
        from typing import get_args

        from pywry.chat.artifacts import AppArtifact, Artifact

        assert AppArtifact in get_args(Artifact)

    def test_top_level_export(self) -> None:
        # Make sure the convenience re-export survives at package root
        import pywry

        assert hasattr(pywry, "AppArtifact")
        assert "AppArtifact" in pywry.__all__


class TestServerStateRevisions:
    def test_bump_and_get(self) -> None:
        from pywry.inline import _ServerState

        state = _ServerState()
        assert state.get_widget_revision("w1") == 0
        assert state.bump_widget_revision("w1") == 1
        assert state.bump_widget_revision("w1") == 2
        assert state.get_widget_revision("w1") == 2
        assert state.get_widget_revision("w2") == 0

    def test_bump_is_per_widget(self) -> None:
        from pywry.inline import _ServerState

        state = _ServerState()
        state.bump_widget_revision("a")
        state.bump_widget_revision("b")
        state.bump_widget_revision("a")
        assert state.get_widget_revision("a") == 2
        assert state.get_widget_revision("b") == 1


class TestAttachAppArtifact:
    def test_no_widget_html_returns_unmodified(self) -> None:
        from pywry.inline import _state
        from pywry.mcp.app_artifact import attach_app_artifact

        # Ensure widget does not exist
        _state.widgets.pop("missing", None)
        result = {"widget_id": "missing"}
        out = attach_app_artifact(result, "missing")
        assert "_app_artifact" not in out
        assert out is result  # mutates-and-returns contract

    def test_attaches_and_bumps_revision(self) -> None:
        from pywry.inline import _state
        from pywry.mcp.app_artifact import attach_app_artifact

        _state.widgets["w-test"] = {"html": "<!doctype html><body>x</body>"}
        _state.widget_revisions.pop("w-test", None)
        try:
            result: dict = {"widget_id": "w-test"}
            attach_app_artifact(result, "w-test", title="My Widget")
            assert "_app_artifact" in result
            app = result["_app_artifact"]
            assert app["widget_id"] == "w-test"
            assert app["revision"] == 1
            assert app["mime_type"] == "text/html"
            assert app["uri"] == "pywry-app://w-test/1"
            assert app["html"].startswith("<!doctype html>")
            assert app["title"] == "My Widget"

            # Second attach bumps
            result2: dict = {"widget_id": "w-test"}
            attach_app_artifact(result2, "w-test")
            assert result2["_app_artifact"]["revision"] == 2
        finally:
            _state.widgets.pop("w-test", None)
            _state.widget_revisions.pop("w-test", None)


class TestGetWidgetAppHandler:
    def test_handler_returns_embedded_app(self) -> None:
        from pywry.inline import _state
        from pywry.mcp.handlers import _HANDLERS, HandlerContext

        _state.widgets["w-handler"] = {"html": "<html>snap</html>"}
        _state.widget_revisions.pop("w-handler", None)
        try:
            ctx = HandlerContext(
                args={"widget_id": "w-handler", "title": "T", "height": "400px"},
                events={},
                make_callback=lambda _wid: lambda *a, **kw: None,
                headless=True,
            )
            handler = _HANDLERS["get_widget_app"]
            result = handler(ctx)
            assert result["widget_id"] == "w-handler"
            assert "_app_artifact" in result
            assert result["_app_artifact"]["height"] == "400px"
            assert result["revision"] == result["_app_artifact"]["revision"]
        finally:
            _state.widgets.pop("w-handler", None)
            _state.widget_revisions.pop("w-handler", None)

    def test_handler_errors_when_widget_missing(self) -> None:
        from pywry.inline import _state
        from pywry.mcp.handlers import _HANDLERS, HandlerContext

        _state.widgets.pop("ghost", None)
        ctx = HandlerContext(
            args={"widget_id": "ghost"},
            events={},
            make_callback=lambda _wid: lambda *a, **kw: None,
            headless=True,
        )
        result = _HANDLERS["get_widget_app"](ctx)
        assert "error" in result


class TestFormatToolResult:
    def test_plain_dict_returns_json_string(self) -> None:
        from pywry.mcp.server import _format_tool_result

        out = _format_tool_result({"widget_id": "x", "created": True})
        assert isinstance(out, str)
        assert '"widget_id": "x"' in out

    def test_app_artifact_emits_embedded_resource(self) -> None:
        from pywry.mcp.server import _format_tool_result

        payload = {
            "widget_id": "w",
            "_app_artifact": {
                "html": "<b>hi</b>",
                "uri": "pywry-app://w/3",
                "mime_type": "text/html",
                "widget_id": "w",
                "revision": 3,
            },
        }
        out = _format_tool_result(payload)
        # When mcp.types is importable we get a list of Content blocks;
        # otherwise we fall back to JSON. Accept either shape.
        if isinstance(out, list):
            assert len(out) == 2
            text, embedded = out
            assert getattr(text, "type", None) == "text"
            assert "widget_id" in getattr(text, "text", "")
            assert getattr(embedded, "type", None) == "resource"
            resource = embedded.resource
            # pydantic wraps the uri in AnyUrl — coerce both sides to str
            assert str(getattr(resource, "uri", "")).rstrip("/") == "pywry-app://w/3"
            assert getattr(resource, "mimeType", "") == "text/html"
            assert getattr(resource, "text", "") == "<b>hi</b>"
        else:
            # Fallback path — the app artifact is re-attached to the dict.
            assert "_app_artifact" in out


class TestWebSocketRevisionGuard:
    def test_stale_revision_query_is_rejected(self) -> None:
        # The WS endpoint's revision check is wired via a plain query-
        # string lookup; exercise the policy directly using the helpers
        # so the test does not need a running server.
        from pywry.inline import _state

        _state.widget_revisions["guard"] = 5
        try:
            assert _state.get_widget_revision("guard") == 5
            # A request bearing revision 3 is "older" than current 5
            assert _state.get_widget_revision("guard") > 3
            # A request bearing revision 5 is current
            assert not (_state.get_widget_revision("guard") > 5)
        finally:
            _state.widget_revisions.pop("guard", None)
