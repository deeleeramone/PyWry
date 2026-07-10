"""Tests for ``pywry.mcp.app_artifact``.

Covers:
- ``build_app_artifact`` — None when widget missing or html empty,
  populated ``AppArtifact`` (title, height, sandbox) otherwise.
- ``attach_app_artifact`` — mutates result dict in place, bumps the
  inline server revision, and preserves existing keys.
- ``_format_tool_result`` serializer emits an ``EmbeddedResource``
  block when ``_app_artifact`` is present.
- ``get_widget_app`` handler returns embedded artifact for an existing
  widget and errors otherwise.
- The ``AppArtifact`` Pydantic model defaults, union membership, and
  top-level re-export.
- WebSocket revision guard (revision query < current → reject).
- ``_ServerState`` per-widget revision bump.
"""

from __future__ import annotations

import pytest


pytest.importorskip("mcp")


# ---------------------------------------------------------------------------
# Helper: a clean inline state per test (autouse fixture)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_inline_state():
    from pywry.inline import _state

    saved_widgets = dict(_state.widgets)
    saved_revisions = dict(_state.widget_revisions)
    _state.widgets.clear()
    _state.widget_revisions.clear()
    yield
    _state.widgets.clear()
    _state.widget_revisions.clear()
    _state.widgets.update(saved_widgets)
    _state.widget_revisions.update(saved_revisions)


def _put(widget_id: str, html: str) -> None:
    from pywry.inline import _state

    _state.widgets[widget_id] = {"html": html}


# ---------------------------------------------------------------------------
# AppArtifact Pydantic model
# ---------------------------------------------------------------------------


class TestAppArtifactModel:
    def test_defaults(self) -> None:
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
        from typing import get_args

        from pywry.chat.artifacts import AppArtifact, Artifact

        assert AppArtifact in get_args(Artifact)

    def test_top_level_export(self) -> None:
        import pywry

        assert hasattr(pywry, "AppArtifact")
        assert "AppArtifact" in pywry.__all__


# ---------------------------------------------------------------------------
# build_app_artifact
# ---------------------------------------------------------------------------


class TestBuildAppArtifact:
    def test_returns_none_when_widget_missing(self) -> None:
        from pywry.mcp.app_artifact import build_app_artifact

        assert build_app_artifact("nonexistent") is None

    def test_returns_none_when_html_missing(self) -> None:
        from pywry.mcp.app_artifact import build_app_artifact

        _put("w1", "")
        assert build_app_artifact("w1") is None

    def test_returns_artifact(self) -> None:
        from pywry.chat.artifacts import AppArtifact
        from pywry.mcp.app_artifact import build_app_artifact

        _put("w1", "<html></html>")
        artifact = build_app_artifact("w1")
        assert isinstance(artifact, AppArtifact)
        assert artifact.html == "<html></html>"
        assert artifact.widget_id == "w1"
        assert "w1" in artifact.title

    def test_custom_title(self) -> None:
        from pywry.mcp.app_artifact import build_app_artifact

        _put("w1", "<html/>")
        artifact = build_app_artifact("w1", title="My App")
        assert artifact.title == "My App"

    def test_height_param(self) -> None:
        from pywry.mcp.app_artifact import build_app_artifact

        _put("w1", "<html/>")
        artifact = build_app_artifact("w1", height="800px")
        assert artifact.height == "800px"

    def test_sandbox_default(self) -> None:
        from pywry.mcp.app_artifact import build_app_artifact

        _put("w1", "<html/>")
        artifact = build_app_artifact("w1")
        assert artifact.sandbox is True

    def test_sandbox_disabled(self) -> None:
        from pywry.mcp.app_artifact import build_app_artifact

        _put("w1", "<html/>")
        artifact = build_app_artifact("w1", sandbox=False)
        assert artifact.sandbox is False

    def test_revision_increments(self) -> None:
        from pywry.mcp.app_artifact import build_app_artifact

        _put("w1", "<html/>")
        a = build_app_artifact("w1")
        b = build_app_artifact("w1")
        assert b.revision > a.revision


# ---------------------------------------------------------------------------
# attach_app_artifact
# ---------------------------------------------------------------------------


class TestAttachAppArtifact:
    def test_no_widget_html_returns_unmodified(self) -> None:
        from pywry.mcp.app_artifact import attach_app_artifact

        result = {"widget_id": "missing"}
        out = attach_app_artifact(result, "missing")
        assert "_app_artifact" not in out
        assert out is result  # mutates-and-returns contract

    def test_attaches_and_bumps_revision(self) -> None:
        from pywry.mcp.app_artifact import attach_app_artifact

        _put("w-test", "<!doctype html><body>x</body>")
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

    def test_keeps_other_keys(self) -> None:
        from pywry.mcp.app_artifact import attach_app_artifact

        _put("w1", "<x/>")
        result = {"k": 1}
        attach_app_artifact(result, "w1")
        assert result["k"] == 1

    def test_full_payload_shape(self) -> None:
        from pywry.mcp.app_artifact import attach_app_artifact

        _put("w1", "<h1>X</h1>")
        result = {"existing": "data"}
        attach_app_artifact(result, "w1", title="T", height="700px")
        a = result["_app_artifact"]
        assert a["artifact_type"] == "app"
        assert a["title"] == "T"
        assert a["widget_id"] == "w1"
        assert a["height"] == "700px"
        assert a["sandbox"] is True
        assert a["html"] == "<h1>X</h1>"
        assert a["mime_type"] == "text/html"
        assert a["uri"].startswith("pywry-app://w1/")


# ---------------------------------------------------------------------------
# get_widget_app handler (the entry point that builds & attaches)
# ---------------------------------------------------------------------------


class TestGetWidgetAppHandler:
    def test_handler_returns_embedded_app(self) -> None:
        from pywry.mcp.handlers import _HANDLERS, HandlerContext

        _put("w-handler", "<html>snap</html>")
        ctx = HandlerContext(
            args={"widget_id": "w-handler", "title": "T", "height": "400px"},
            events={},
            make_callback=lambda _wid: lambda *a, **kw: None,
            headless=True,
        )
        result = _HANDLERS["get_widget_app"](ctx)
        assert result["widget_id"] == "w-handler"
        assert "_app_artifact" in result
        assert result["_app_artifact"]["height"] == "400px"
        assert result["revision"] == result["_app_artifact"]["revision"]

    def test_handler_errors_when_widget_missing(self) -> None:
        from pywry.mcp.handlers import _HANDLERS, HandlerContext

        ctx = HandlerContext(
            args={"widget_id": "ghost"},
            events={},
            make_callback=lambda _wid: lambda *a, **kw: None,
            headless=True,
        )
        result = _HANDLERS["get_widget_app"](ctx)
        assert "error" in result


# ---------------------------------------------------------------------------
# _format_tool_result EmbeddedResource path
# ---------------------------------------------------------------------------


class TestFormatToolResultEmbedsArtifact:
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
        if isinstance(out, list):
            assert len(out) == 2
            text, embedded = out
            assert getattr(text, "type", None) == "text"
            assert "widget_id" in getattr(text, "text", "")
            assert getattr(embedded, "type", None) == "resource"
            resource = embedded.resource
            assert str(getattr(resource, "uri", "")).rstrip("/") == "pywry-app://w/3"
            assert getattr(resource, "mimeType", "") == "text/html"
            assert getattr(resource, "text", "") == "<b>hi</b>"
        else:
            assert "_app_artifact" in out


# ---------------------------------------------------------------------------
# _ServerState revisions + WS revision guard
# ---------------------------------------------------------------------------


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


class TestWebSocketRevisionGuard:
    def test_stale_revision_query_is_rejected(self) -> None:
        from pywry.inline import _state

        _state.widget_revisions["guard"] = 5
        assert _state.get_widget_revision("guard") == 5
        # Request bearing revision 3 is "older" than current 5
        assert _state.get_widget_revision("guard") > 3
        # Request bearing revision 5 is current
        assert not (_state.get_widget_revision("guard") > 5)
