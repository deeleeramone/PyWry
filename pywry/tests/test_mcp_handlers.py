"""Tests for ``pywry.mcp.handlers`` — tool dispatch and per-tool handlers.

Covers:
- ``HandlerContext`` construction and the ``_HANDLERS`` dispatch table.
- The ``_handle_*`` functions for create_widget, show_*, set/get/destroy,
  widget manipulation (content/style/toast/theme/css/navigate/download/
  plotly/marquee/ticker/send_event), chat tools, tvchart helpers, and
  resource/export handlers.
- Helper internals: ``_apply_action``, ``_make_action_callback``,
  ``_infer_callbacks_from_toolbars``, ``_register_widget_events``,
  ``_resolve_widget_id``, ``_get_widget_or_error``, ``_check_required_args``,
  ``_minimal_confirm_state``, ``_fetch_tvchart_state``,
  ``_wait_for_data_settled``, ``_poll_tvchart_state``,
  ``_snapshot_compare_set``, ``_build_compare_payload``.
- The async ``handle_tool`` entry point: unknown tools, missing required
  args, and pass-through to ``get_skills``.
- Defensive ``error or {default}`` branches reachable only by stubbing
  the resolver — guard the production code path.
"""

from __future__ import annotations

import json
import threading
import time

from typing import Any
from unittest.mock import MagicMock, patch

import pytest


pytest.importorskip("mcp")
pytest.importorskip("fastmcp")

# Pull shared fixtures + helper from conftest.
from tests.conftest import make_handler_ctx as _make_ctx


# ---------------------------------------------------------------------------
# _apply_action helper
# ---------------------------------------------------------------------------


class TestApplyAction:
    def test_increment(self) -> None:
        from pywry.mcp.handlers import _apply_action

        state: dict[str, Any] = {"value": 5}
        widget = MagicMock()
        _apply_action("increment", {"state_key": "value"}, state, widget, "counter")
        assert state["value"] == 6
        widget.emit.assert_called_once()

    def test_decrement(self) -> None:
        from pywry.mcp.handlers import _apply_action

        state: dict[str, Any] = {"value": 10}
        widget = MagicMock()
        _apply_action("decrement", {"state_key": "value"}, state, widget, "counter")
        assert state["value"] == 9

    def test_set(self) -> None:
        from pywry.mcp.handlers import _apply_action

        state: dict[str, Any] = {"value": 5}
        widget = MagicMock()
        _apply_action("set", {"state_key": "value", "value": 100}, state, widget, None)
        assert state["value"] == 100

    def test_toggle(self) -> None:
        from pywry.mcp.handlers import _apply_action

        state: dict[str, Any] = {"value": False}
        widget = MagicMock()
        _apply_action("toggle", {"state_key": "value"}, state, widget, "status")
        assert state["value"] is True

    def test_emit(self) -> None:
        from pywry.mcp.handlers import _apply_action

        state: dict[str, Any] = {}
        widget = MagicMock()
        _apply_action(
            "emit",
            {"emit_event": "custom:event", "emit_data": {"key": "value"}},
            state,
            widget,
            None,
        )
        widget.emit.assert_called_once_with("custom:event", {"key": "value"})

    def test_emit_no_event_is_noop(self) -> None:
        """Action 'emit' with no emit_event returns without crashing."""
        from pywry.mcp.handlers import _apply_action

        widget = MagicMock()
        _apply_action("emit", {}, {}, widget, None)
        widget.emit.assert_not_called()


# ---------------------------------------------------------------------------
# _make_action_callback
# ---------------------------------------------------------------------------


class TestMakeActionCallback:
    def test_invokes_apply_action_when_widget_present(self) -> None:
        from pywry.mcp.handlers import _make_action_callback

        state: dict[str, Any] = {"value": 0}
        widget = MagicMock()
        holder = {"widget": widget}
        cb = _make_action_callback(
            {"action": "increment", "target": "x", "state_key": "value"}, state, holder
        )
        cb(None, "x:increment", "label")
        assert state["value"] == 1
        widget.emit.assert_called_with("pywry:set-content", {"id": "x", "text": "1"})

    def test_no_op_when_holder_empty(self) -> None:
        from pywry.mcp.handlers import _make_action_callback

        state: dict[str, Any] = {}
        holder: dict[str, Any] = {"widget": None}
        cb = _make_action_callback({"action": "increment"}, state, holder)
        cb(None, "x:increment", "label")
        assert state == {}


# ---------------------------------------------------------------------------
# _infer_callbacks_from_toolbars + _register_widget_events
# ---------------------------------------------------------------------------


class TestInferCallbacks:
    def test_auto_wires_known_actions(self) -> None:
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
        assert callbacks["counter:increment"]["action"] == "increment"
        assert callbacks["counter:decrement"]["action"] == "decrement"
        assert callbacks["counter:reset"]["action"] == "set"

    def test_skips_items_without_event(self) -> None:
        from pywry.mcp.handlers import _infer_callbacks_from_toolbars

        item = MagicMock()
        item.event = ""
        toolbar = MagicMock()
        toolbar.items = [item]
        callbacks: dict[str, Any] = {}
        _infer_callbacks_from_toolbars([toolbar], callbacks)
        assert callbacks == {}

    def test_skips_events_without_two_parts(self) -> None:
        from pywry.mcp.handlers import _infer_callbacks_from_toolbars

        item = MagicMock()
        item.event = "noprefix"
        toolbar = MagicMock()
        toolbar.items = [item]
        callbacks: dict[str, Any] = {}
        _infer_callbacks_from_toolbars([toolbar], callbacks)
        assert callbacks == {}

    def test_skips_unrecognized_action(self) -> None:
        """Unknown action segments are left for explicit configuration."""
        from pywry.mcp.handlers import _infer_callbacks_from_toolbars

        item = MagicMock()
        item.event = "x:save"
        toolbar = MagicMock()
        toolbar.items = [item]
        callbacks: dict[str, Any] = {}
        _infer_callbacks_from_toolbars([toolbar], callbacks)
        assert callbacks == {}

    def test_toggle_inferred_from_x_toggle(self) -> None:
        from pywry.mcp.handlers import _infer_callbacks_from_toolbars

        item = MagicMock()
        item.event = "x:toggle"
        toolbar = MagicMock()
        toolbar.items = [item]
        cbs: dict = {}
        _infer_callbacks_from_toolbars([toolbar], cbs)
        assert cbs["x:toggle"]["action"] == "toggle"

    def test_register_widget_events_no_toolbars_is_noop(self) -> None:
        from pywry.mcp.handlers import _register_widget_events

        widget = MagicMock()
        _register_widget_events(widget, None, lambda *a, **k: None)
        widget.on.assert_not_called()

    def test_register_widget_events_only_wires_items_with_event(self) -> None:
        from pywry.mcp.handlers import _register_widget_events

        item_with = MagicMock()
        item_with.event = "x:click"
        item_no = MagicMock()
        item_no.event = ""
        toolbar = MagicMock()
        toolbar.items = [item_with, item_no]

        widget = MagicMock()
        cb = lambda *a, **k: None  # noqa: E731
        _register_widget_events(widget, [toolbar], cb)
        widget.on.assert_called_once_with("x:click", cb)


# ---------------------------------------------------------------------------
# _resolve_widget_id + _get_widget_or_error + _check_required_args
# ---------------------------------------------------------------------------


class TestResolveHelpers:
    def test_resolve_widget_id_provided(self) -> None:
        from pywry.mcp.handlers import _resolve_widget_id

        wid, err = _resolve_widget_id("explicit")
        assert wid == "explicit"
        assert err is None

    def test_resolve_widget_id_no_widgets(self, mcp_fresh_state) -> None:
        from pywry.mcp.handlers import _resolve_widget_id

        wid, err = _resolve_widget_id(None)
        assert wid is None
        assert err is not None

    def test_resolve_widget_id_single(self, mcp_fresh_state) -> None:
        from pywry.mcp import state as mcp_state
        from pywry.mcp.handlers import _resolve_widget_id

        mcp_state._widgets["only"] = MagicMock()
        wid, err = _resolve_widget_id(None)
        assert wid == "only"
        assert err is None

    def test_resolve_widget_id_multi_returns_error(self, mcp_fresh_state) -> None:
        from pywry.mcp import state as mcp_state
        from pywry.mcp.handlers import _resolve_widget_id

        mcp_state._widgets["a"] = MagicMock()
        mcp_state._widgets["b"] = MagicMock()
        wid, err = _resolve_widget_id(None)
        assert wid is None
        assert err is not None
        assert "a" in err["error"] and "b" in err["error"]

    def test_get_widget_or_error_found(self, mcp_fresh_state) -> None:
        from pywry.mcp import state as mcp_state
        from pywry.mcp.handlers import _get_widget_or_error

        widget = MagicMock()
        mcp_state._widgets["found-widget"] = widget
        out, err = _get_widget_or_error("found-widget")
        assert out is widget
        assert err is None

    def test_get_widget_or_error_not_found(self, mcp_fresh_state) -> None:
        from pywry.mcp.handlers import _get_widget_or_error

        out, err = _get_widget_or_error("missing")
        assert out is None
        assert err is not None
        assert "error" in err

    def test_check_required_args_no_match_returns_none(self) -> None:
        from pywry.mcp.handlers import _check_required_args

        assert _check_required_args("not_a_real_tool", {}) is None

    def test_check_required_args_widget_id_excluded(self) -> None:
        """widget_id is auto-resolved, so it's never reported as missing."""
        from pywry.mcp.handlers import _check_required_args

        assert _check_required_args("destroy_widget", {}) is None


# ---------------------------------------------------------------------------
# HandlerContext + _handle_get_skills
# ---------------------------------------------------------------------------


class TestHandlerContext:
    def test_init(self) -> None:
        from pywry.mcp.handlers import HandlerContext

        args = {"key": "value"}
        events: dict[str, list[dict[str, Any]]] = {}
        ctx = HandlerContext(args, events, lambda w: lambda d, e, lbl: None, headless=True)
        assert ctx.args == args
        assert ctx.events == events
        assert ctx.headless is True


class TestHandleGetSkills:
    def test_lists_all(self) -> None:
        from pywry.mcp.handlers import _handle_get_skills

        out = _handle_get_skills(_make_ctx({}))
        assert "available_skills" in out
        assert isinstance(out["available_skills"], list)

    def test_returns_specific_skill(self) -> None:
        from pywry.mcp.handlers import _handle_get_skills

        out = _handle_get_skills(_make_ctx({"skill": "native"}))
        assert out["skill"] == "native"
        assert "guidance" in out

    def test_unknown_skill_returns_error(self) -> None:
        from pywry.mcp.handlers import _handle_get_skills

        out = _handle_get_skills(_make_ctx({"skill": "nonexistent_xyz"}))
        assert "error" in out


# ---------------------------------------------------------------------------
# _handle_build_div + _handle_build_ticker_item
# ---------------------------------------------------------------------------


class TestBuildHandlers:
    def test_build_div(self) -> None:
        from pywry.mcp.handlers import _handle_build_div

        out = _handle_build_div(_make_ctx({"content": "Hello", "component_id": "greeting"}))
        assert "html" in out
        assert "greeting" in out["html"]
        assert "Hello" in out["html"]

    def test_build_ticker_item(self) -> None:
        from pywry.mcp.handlers import _handle_build_ticker_item

        out = _handle_build_ticker_item(_make_ctx({"ticker": "AAPL", "text": "Apple: $150"}))
        assert "html" in out
        assert out["ticker"] == "AAPL"


# ---------------------------------------------------------------------------
# _handle_get_component_docs
# ---------------------------------------------------------------------------


class TestGetComponentDocs:
    def test_found(self) -> None:
        from pywry.mcp.handlers import _handle_get_component_docs

        out = _handle_get_component_docs(_make_ctx({"component": "button"}))
        assert out["component"] == "button"
        assert "name" in out
        assert "properties" in out

    def test_not_found(self) -> None:
        from pywry.mcp.handlers import _handle_get_component_docs

        out = _handle_get_component_docs(_make_ctx({"component": "unknown_xyz"}))
        assert "error" in out


# ---------------------------------------------------------------------------
# _handle_create_widget
# ---------------------------------------------------------------------------


class TestHandleCreateWidget:
    def test_native_mode(self, mcp_fresh_state) -> None:
        from pywry.mcp.handlers import _handle_create_widget

        widget = MagicMock()
        widget.widget_id = "abc"
        app = MagicMock()
        app.show.return_value = widget

        with patch("pywry.mcp.handlers.get_app", return_value=app):
            out = _handle_create_widget(
                _make_ctx({"html": "<div></div>", "title": "T"}, headless=False)
            )

        assert out["mode"] == "native"
        assert out["widget_id"] == "abc"
        assert out["created"] is True

    def test_headless_attaches_app_artifact(self, mcp_fresh_state) -> None:
        from pywry.inline import _state as inline_state
        from pywry.mcp.handlers import _handle_create_widget

        widget = MagicMock()
        widget.widget_id = "headless-1"
        app = MagicMock()
        app.show.return_value = widget

        inline_state.widgets["headless-1"] = {"html": "<html>x</html>", "persistent": False}
        try:
            with patch("pywry.mcp.handlers.get_app", return_value=app):
                out = _handle_create_widget(
                    _make_ctx(
                        {"html": "<p></p>", "title": "Headless", "height": 600},
                        headless=True,
                    )
                )
            assert inline_state.widgets["headless-1"]["persistent"] is True
            assert out["created"] is True
            assert out["widget_id"] == "headless-1"
            assert "_app_artifact" in out
        finally:
            inline_state.widgets.pop("headless-1", None)
            inline_state.widget_revisions.pop("headless-1", None)

    def test_toolbars_without_callbacks_infers_them(self, mcp_fresh_state) -> None:
        from pywry.mcp.handlers import _handle_create_widget

        widget = MagicMock()
        widget.widget_id = "wt"
        app = MagicMock()
        app.show.return_value = widget

        with patch("pywry.mcp.handlers.get_app", return_value=app):
            _handle_create_widget(
                _make_ctx(
                    {
                        "html": "<div></div>",
                        "toolbars": [
                            {
                                "position": "top",
                                "items": [
                                    {
                                        "type": "button",
                                        "label": "+",
                                        "event": "counter:increment",
                                    }
                                ],
                            }
                        ],
                    },
                    headless=False,
                )
            )
        callbacks = app.show.call_args[1]["callbacks"]
        assert "counter:increment" in callbacks

    def test_explicit_callbacks_passed_through(self, mcp_fresh_state) -> None:
        from pywry.mcp.handlers import _handle_create_widget

        widget = MagicMock()
        widget.widget_id = "wid"
        app = MagicMock()
        app.show.return_value = widget

        with patch("pywry.mcp.handlers.get_app", return_value=app):
            _handle_create_widget(
                _make_ctx(
                    {
                        "html": "<div></div>",
                        "callbacks": {
                            "btn:click": {"action": "increment", "target": "counter"},
                        },
                    },
                    headless=False,
                )
            )
        kwargs = app.show.call_args[1]
        assert "callbacks" in kwargs


# ---------------------------------------------------------------------------
# _handle_show_plotly / _handle_show_dataframe / _handle_show_tvchart
# ---------------------------------------------------------------------------


class TestShowHelpers:
    def test_show_plotly_native(self, mcp_fresh_state) -> None:
        from pywry.mcp.handlers import _handle_show_plotly

        widget = MagicMock()
        widget.widget_id = "plot1"
        app = MagicMock()
        app.show_plotly.return_value = widget

        fig_dict = {"data": [], "layout": {}}
        with patch("pywry.mcp.handlers.get_app", return_value=app):
            out = _handle_show_plotly(
                _make_ctx({"figure_json": json.dumps(fig_dict), "title": "P"})
            )
        assert out["created"] is True
        assert out["widget_id"] == "plot1"
        app.show_plotly.assert_called_once()

    def test_show_plotly_headless(self, mcp_fresh_state) -> None:
        from pywry.inline import _state as inline_state
        from pywry.mcp.handlers import _handle_show_plotly

        widget = MagicMock()
        widget.widget_id = "plot2"
        app = MagicMock()
        app.show_plotly.return_value = widget
        inline_state.widgets["plot2"] = {"html": "<html></html>"}
        try:
            with patch("pywry.mcp.handlers.get_app", return_value=app):
                out = _handle_show_plotly(
                    _make_ctx({"figure_json": json.dumps({"data": []})}, headless=True)
                )
            assert "_app_artifact" in out
            assert inline_state.widgets["plot2"]["persistent"] is True
        finally:
            inline_state.widgets.pop("plot2", None)
            inline_state.widget_revisions.pop("plot2", None)

    def test_show_dataframe_native(self, mcp_fresh_state) -> None:
        from pywry.mcp.handlers import _handle_show_dataframe

        widget = MagicMock()
        widget.widget_id = "df1"
        app = MagicMock()
        app.show_dataframe.return_value = widget

        with patch("pywry.mcp.handlers.get_app", return_value=app):
            out = _handle_show_dataframe(
                _make_ctx({"data_json": json.dumps([{"a": 1}]), "title": "T"})
            )
        assert out["created"] is True
        assert out["widget_id"] == "df1"

    def test_show_dataframe_headless(self, mcp_fresh_state) -> None:
        from pywry.inline import _state as inline_state
        from pywry.mcp.handlers import _handle_show_dataframe

        widget = MagicMock()
        widget.widget_id = "df2"
        app = MagicMock()
        app.show_dataframe.return_value = widget
        inline_state.widgets["df2"] = {"html": "<html></html>"}
        try:
            with patch("pywry.mcp.handlers.get_app", return_value=app):
                out = _handle_show_dataframe(
                    _make_ctx({"data_json": json.dumps([{"a": 1}])}, headless=True)
                )
            assert "_app_artifact" in out
        finally:
            inline_state.widgets.pop("df2", None)
            inline_state.widget_revisions.pop("df2", None)

    def test_show_tvchart_native(self, mcp_fresh_state) -> None:
        from pywry.mcp.handlers import _handle_show_tvchart

        widget = MagicMock()
        widget.widget_id = "tv1"
        app = MagicMock()
        app.show_tvchart.return_value = widget

        with patch("pywry.mcp.handlers.get_app", return_value=app):
            out = _handle_show_tvchart(
                _make_ctx(
                    {
                        "data_json": json.dumps(
                            [{"time": 1, "open": 1, "high": 1, "low": 1, "close": 1}]
                        )
                    }
                )
            )
        assert out["created"] is True
        assert out["widget_id"] == "tv1"

    def test_show_tvchart_headless(self, mcp_fresh_state) -> None:
        from pywry.inline import _state as inline_state
        from pywry.mcp.handlers import _handle_show_tvchart

        widget = MagicMock()
        widget.widget_id = "tv2"
        app = MagicMock()
        app.show_tvchart.return_value = widget
        inline_state.widgets["tv2"] = {"html": "<html></html>"}
        try:
            with patch("pywry.mcp.handlers.get_app", return_value=app):
                out = _handle_show_tvchart(_make_ctx({"data_json": "[]"}, headless=True))
            assert "_app_artifact" in out
        finally:
            inline_state.widgets.pop("tv2", None)
            inline_state.widget_revisions.pop("tv2", None)


# ---------------------------------------------------------------------------
# Widget manipulation handlers (set_content, set_style, ...)
# ---------------------------------------------------------------------------


class TestSetContent:
    def test_with_text(self, mcp_widget) -> None:
        from pywry.mcp.handlers import _handle_set_content

        out = _handle_set_content(_make_ctx({"widget_id": "w", "component_id": "x", "text": "hi"}))
        assert out["updated"] is True
        mcp_widget.emit.assert_called_with("pywry:set-content", {"id": "x", "text": "hi"})

    def test_with_html(self, mcp_widget) -> None:
        from pywry.mcp.handlers import _handle_set_content

        _handle_set_content(_make_ctx({"widget_id": "w", "component_id": "x", "html": "<b>hi</b>"}))
        mcp_widget.emit.assert_called_with("pywry:set-content", {"id": "x", "html": "<b>hi</b>"})

    def test_widget_missing(self, mcp_fresh_state) -> None:
        from pywry.mcp.handlers import _handle_set_content

        out = _handle_set_content(
            _make_ctx({"widget_id": "ghost", "component_id": "x", "text": "hi"})
        )
        assert "error" in out


class TestSetStyle:
    def test_emits_set_style(self, mcp_widget) -> None:
        from pywry.mcp.handlers import _handle_set_style

        out = _handle_set_style(
            _make_ctx({"widget_id": "w", "component_id": "x", "styles": {"color": "red"}})
        )
        assert out["updated"] is True
        mcp_widget.emit.assert_called_with(
            "pywry:set-style", {"id": "x", "styles": {"color": "red"}}
        )

    def test_widget_missing(self, mcp_fresh_state) -> None:
        from pywry.mcp.handlers import _handle_set_style

        out = _handle_set_style(
            _make_ctx({"widget_id": "ghost", "component_id": "x", "styles": {}})
        )
        assert "error" in out


class TestShowToast:
    def test_emits_alert(self, mcp_widget) -> None:
        from pywry.mcp.handlers import _handle_show_toast

        out = _handle_show_toast(
            _make_ctx(
                {
                    "widget_id": "w",
                    "message": "Hello",
                    "type": "success",
                    "duration": 5000,
                }
            )
        )
        assert out["toast_shown"] is True
        mcp_widget.emit.assert_called_with(
            "pywry:alert",
            {"message": "Hello", "type": "success", "duration": 5000},
        )

    def test_widget_missing(self, mcp_fresh_state) -> None:
        from pywry.mcp.handlers import _handle_show_toast

        out = _handle_show_toast(_make_ctx({"widget_id": "ghost", "message": "x"}))
        assert "error" in out


class TestUpdateTheme:
    def test_emits_theme(self, mcp_widget) -> None:
        from pywry.mcp.handlers import _handle_update_theme

        out = _handle_update_theme(_make_ctx({"widget_id": "w", "theme": "dark"}))
        assert out["theme"] == "dark"
        mcp_widget.emit.assert_called_with("pywry:update-theme", {"theme": "dark"})

    def test_widget_missing(self, mcp_fresh_state) -> None:
        from pywry.mcp.handlers import _handle_update_theme

        out = _handle_update_theme(_make_ctx({"widget_id": "ghost", "theme": "dark"}))
        assert "error" in out


class TestInjectCss:
    def test_default_style_id(self, mcp_widget) -> None:
        from pywry.mcp.handlers import _handle_inject_css

        out = _handle_inject_css(_make_ctx({"widget_id": "w", "css": "body{}"}))
        assert out["css_injected"] is True
        mcp_widget.emit.assert_called_with(
            "pywry:inject-css", {"css": "body{}", "id": "pywry-injected-style"}
        )

    def test_custom_style_id(self, mcp_widget) -> None:
        from pywry.mcp.handlers import _handle_inject_css

        _handle_inject_css(_make_ctx({"widget_id": "w", "css": "body{}", "style_id": "x"}))
        mcp_widget.emit.assert_called_with("pywry:inject-css", {"css": "body{}", "id": "x"})

    def test_widget_missing(self, mcp_fresh_state) -> None:
        from pywry.mcp.handlers import _handle_inject_css

        out = _handle_inject_css(_make_ctx({"widget_id": "ghost", "css": "x"}))
        assert "error" in out


class TestRemoveCss:
    def test_emits_remove(self, mcp_widget) -> None:
        from pywry.mcp.handlers import _handle_remove_css

        out = _handle_remove_css(_make_ctx({"widget_id": "w", "style_id": "x"}))
        assert out["css_removed"] is True
        mcp_widget.emit.assert_called_with("pywry:remove-css", {"id": "x"})

    def test_widget_missing(self, mcp_fresh_state) -> None:
        from pywry.mcp.handlers import _handle_remove_css

        out = _handle_remove_css(_make_ctx({"widget_id": "ghost", "style_id": "x"}))
        assert "error" in out


class TestNavigate:
    def test_emits_url(self, mcp_widget) -> None:
        from pywry.mcp.handlers import _handle_navigate

        out = _handle_navigate(_make_ctx({"widget_id": "w", "url": "https://example.com"}))
        assert out["navigating_to"] == "https://example.com"
        mcp_widget.emit.assert_called_with("pywry:navigate", {"url": "https://example.com"})

    def test_widget_missing(self, mcp_fresh_state) -> None:
        from pywry.mcp.handlers import _handle_navigate

        out = _handle_navigate(_make_ctx({"widget_id": "ghost", "url": "https://x"}))
        assert "error" in out


class TestDownload:
    def test_default_mime(self, mcp_widget) -> None:
        from pywry.mcp.handlers import _handle_download

        out = _handle_download(_make_ctx({"widget_id": "w", "content": "abc", "filename": "f.txt"}))
        assert out["download_triggered"] == "f.txt"
        mcp_widget.emit.assert_called_with(
            "pywry:download",
            {
                "content": "abc",
                "filename": "f.txt",
                "mimeType": "application/octet-stream",
            },
        )

    def test_custom_mime(self, mcp_widget) -> None:
        from pywry.mcp.handlers import _handle_download

        _handle_download(
            _make_ctx(
                {
                    "widget_id": "w",
                    "content": "{}",
                    "filename": "f.json",
                    "mime_type": "application/json",
                }
            )
        )
        mcp_widget.emit.assert_called_with(
            "pywry:download",
            {"content": "{}", "filename": "f.json", "mimeType": "application/json"},
        )

    def test_widget_missing(self, mcp_fresh_state) -> None:
        from pywry.mcp.handlers import _handle_download

        out = _handle_download(
            _make_ctx({"widget_id": "ghost", "content": "x", "filename": "f.txt"})
        )
        assert "error" in out


class TestUpdatePlotly:
    def test_full(self, mcp_widget) -> None:
        from pywry.mcp.handlers import _handle_update_plotly

        fig_dict = {"data": [{"x": [1]}], "layout": {"title": "T"}}
        out = _handle_update_plotly(
            _make_ctx(
                {
                    "widget_id": "w",
                    "figure_json": json.dumps(fig_dict),
                    "layout_only": False,
                }
            )
        )
        assert out["plotly_updated"] is True
        mcp_widget.emit.assert_called_with(
            "plotly:update-figure",
            {"data": fig_dict["data"], "layout": fig_dict["layout"]},
        )

    def test_layout_only(self, mcp_widget) -> None:
        from pywry.mcp.handlers import _handle_update_plotly

        fig_dict = {"data": [{"x": [1]}], "layout": {"title": "T"}}
        _handle_update_plotly(
            _make_ctx(
                {
                    "widget_id": "w",
                    "figure_json": json.dumps(fig_dict),
                    "layout_only": True,
                }
            )
        )
        mcp_widget.emit.assert_called_with("plotly:update-layout", {"layout": fig_dict["layout"]})

    def test_widget_missing(self, mcp_fresh_state) -> None:
        from pywry.mcp.handlers import _handle_update_plotly

        out = _handle_update_plotly(_make_ctx({"widget_id": "ghost", "figure_json": "{}"}))
        assert "error" in out


class TestUpdateMarquee:
    def test_full_payload(self, mcp_widget) -> None:
        from pywry.mcp.handlers import _handle_update_marquee

        out = _handle_update_marquee(
            _make_ctx(
                {
                    "widget_id": "w",
                    "component_id": "ticker",
                    "text": "BTC: 100k",
                    "speed": 20,
                    "paused": False,
                }
            )
        )
        assert out["marquee_updated"] is True
        mcp_widget.emit.assert_called_with(
            "toolbar:marquee-set-content",
            {"id": "ticker", "text": "BTC: 100k", "speed": 20, "paused": False},
        )

    def test_with_ticker_update(self, mcp_widget) -> None:
        from pywry.mcp.handlers import _handle_update_marquee

        out = _handle_update_marquee(
            _make_ctx(
                {
                    "widget_id": "w",
                    "component_id": "ticker",
                    "ticker_update": {"ticker": "AAPL", "text": "150"},
                }
            )
        )
        assert out["ticker_updated"] == "AAPL"
        mcp_widget.emit.assert_called_with(
            "toolbar:marquee-set-item", {"ticker": "AAPL", "text": "150"}
        )

    def test_widget_missing(self, mcp_fresh_state) -> None:
        from pywry.mcp.handlers import _handle_update_marquee

        out = _handle_update_marquee(_make_ctx({"widget_id": "ghost", "component_id": "x"}))
        assert "error" in out


class TestUpdateTickerItem:
    def test_basic(self, mcp_widget) -> None:
        from pywry.mcp.handlers import _handle_update_ticker_item

        out = _handle_update_ticker_item(
            _make_ctx(
                {
                    "widget_id": "w",
                    "ticker": "AAPL",
                    "text": "150",
                    "styles": {"color": "green"},
                }
            )
        )
        assert out["ticker"] == "AAPL"
        assert "event" in out
        assert mcp_widget.emit.called

    def test_widget_missing(self, mcp_fresh_state) -> None:
        from pywry.mcp.handlers import _handle_update_ticker_item

        out = _handle_update_ticker_item(_make_ctx({"widget_id": "ghost", "ticker": "x"}))
        assert "error" in out


class TestSendEvent:
    def test_missing_event_type(self, mcp_widget) -> None:
        from pywry.mcp.handlers import _handle_send_event

        out = _handle_send_event(_make_ctx({"widget_id": "w"}))
        assert "error" in out
        assert "event_type" in out["error"]

    def test_widget_not_found(self, mcp_fresh_state) -> None:
        from pywry.mcp.handlers import _handle_send_event

        out = _handle_send_event(_make_ctx({"widget_id": "ghost", "event_type": "x:y"}))
        assert "error" in out

    def test_no_widgets_registered(self, mcp_fresh_state) -> None:
        """``_resolve_widget_id`` returns no-widgets error when nothing registered."""
        from pywry.mcp.handlers import _handle_send_event

        out = _handle_send_event(_make_ctx({"event_type": "x:y"}))
        assert "error" in out


# ---------------------------------------------------------------------------
# Widget management: list / destroy / get_events
# ---------------------------------------------------------------------------


class TestWidgetManagementHandlers:
    def test_list_widgets_native_path(self, mcp_fresh_state) -> None:
        from pywry.mcp import state as mcp_state
        from pywry.mcp.handlers import _handle_list_widgets

        mcp_state._widgets["a"] = MagicMock()
        out = _handle_list_widgets(_make_ctx({}, headless=False))
        assert out["count"] == 1
        assert out["widgets"][0]["widget_id"] == "a"

    def test_list_widgets_headless_path(self, mcp_fresh_state) -> None:
        from pywry.inline import _state as inline_state
        from pywry.mcp.handlers import _handle_list_widgets

        inline_state.widgets.clear()
        inline_state.widgets["wA"] = {"html": ""}
        try:
            out = _handle_list_widgets(_make_ctx({}, headless=True))
            assert out["count"] == 1
            assert out["widgets"][0]["widget_id"] == "wA"
        finally:
            inline_state.widgets.pop("wA", None)

    def test_list_widgets_empty(self, mcp_fresh_state) -> None:
        from pywry.mcp.handlers import _handle_list_widgets

        out = _handle_list_widgets(_make_ctx({}))
        assert out["count"] == 0

    def test_get_events_returns_events(self, mcp_fresh_state) -> None:
        from pywry.mcp.handlers import _handle_get_events

        events: dict[str, list[dict[str, Any]]] = {
            "widget-1": [{"event_type": "click", "data": {}, "label": "btn"}]
        }
        out = _handle_get_events(
            _make_ctx({"widget_id": "widget-1", "clear": False}, events=events)
        )
        assert "events" in out
        assert len(out["events"]) == 1

    def test_get_events_clear(self, mcp_fresh_state) -> None:
        from pywry.mcp.handlers import _handle_get_events

        events: dict[str, list[dict[str, Any]]] = {
            "widget-2": [{"event_type": "submit", "data": {}, "label": ""}]
        }
        _handle_get_events(_make_ctx({"widget_id": "widget-2", "clear": True}, events=events))
        assert not events["widget-2"]

    def test_get_events_widget_id_required_when_empty(self, mcp_fresh_state) -> None:
        from pywry.mcp.handlers import _handle_get_events

        out = _handle_get_events(_make_ctx({}))
        assert "error" in out

    def test_get_events_auto_resolves_single(self, mcp_widget) -> None:
        from pywry.mcp.handlers import _handle_get_events

        events = {"w": [{"event_type": "x", "data": {}, "label": ""}]}
        out = _handle_get_events(_make_ctx({}, events=events))
        assert out["widget_id"] == "w"
        assert len(out["events"]) == 1

    def test_destroy_widget(self, mcp_fresh_state) -> None:
        from pywry.mcp.handlers import _handle_destroy_widget
        from pywry.mcp.state import _widgets

        _widgets.clear()
        _widgets["to-destroy"] = MagicMock()
        events: dict[str, list[dict[str, Any]]] = {"to-destroy": []}

        out = _handle_destroy_widget(_make_ctx({"widget_id": "to-destroy"}, events=events))
        assert out["destroyed"] is True
        assert "to-destroy" not in _widgets

    def test_destroy_widget_headless_clears_inline(self, mcp_widget) -> None:
        from pywry.inline import _state as inline_state
        from pywry.mcp.handlers import _handle_destroy_widget

        inline_state.widgets["w"] = {"html": ""}
        try:
            out = _handle_destroy_widget(_make_ctx({"widget_id": "w"}, headless=True))
            assert out["destroyed"] is True
            assert "w" not in inline_state.widgets
        finally:
            inline_state.widgets.pop("w", None)

    def test_destroy_widget_no_widgets_no_widget_id(self, mcp_fresh_state) -> None:
        from pywry.mcp.handlers import _handle_destroy_widget

        out = _handle_destroy_widget(_make_ctx({}))
        assert "error" in out

    def test_destroy_widget_ambiguous(self, mcp_fresh_state) -> None:
        from pywry.mcp import state as mcp_state
        from pywry.mcp.handlers import _handle_destroy_widget

        mcp_state._widgets["a"] = MagicMock()
        mcp_state._widgets["b"] = MagicMock()
        out = _handle_destroy_widget(_make_ctx({}))
        assert "error" in out


# ---------------------------------------------------------------------------
# Dispatch table + handle_tool entry point
# ---------------------------------------------------------------------------


class TestDispatchTable:
    def test_all_core_handlers_registered(self) -> None:
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


class TestHandleTool:
    async def test_unknown_returns_error(self) -> None:
        from pywry.mcp.handlers import handle_tool

        out = await handle_tool("unknown_tool_xyz", {}, {}, lambda w: lambda d, e, lbl: None)
        assert "error" in out
        assert "Unknown tool" in out["error"]

    async def test_missing_required_args(self) -> None:
        """The required-arg gate fires before the handler runs."""
        from pywry.mcp.handlers import handle_tool

        # set_content requires component_id; omit it.
        out = await handle_tool(
            "set_content", {"widget_id": "x"}, {}, lambda w: lambda *a, **k: None
        )
        assert "error" in out
        assert "component_id" in out["error"]

    async def test_get_skills_pass_through(self) -> None:
        from pywry.mcp.handlers import handle_tool

        out = await handle_tool("get_skills", {}, {}, lambda w: lambda d, e, lbl: None)
        assert "available_skills" in out


# ---------------------------------------------------------------------------
# Resource / export handlers
# ---------------------------------------------------------------------------


class TestResourceHandlers:
    def test_get_component_source_found(self) -> None:
        from pywry.mcp.handlers import _handle_get_component_source

        out = _handle_get_component_source(_make_ctx({"component": "button"}))
        assert "source" in out
        assert out["component"] == "button"

    def test_get_component_source_not_found(self) -> None:
        from pywry.mcp.handlers import _handle_get_component_source

        out = _handle_get_component_source(_make_ctx({"component": "nonexistent_xyz"}))
        assert "error" in out

    def test_export_widget_found(self, mcp_fresh_state) -> None:
        from pywry.mcp import state as mcp_state
        from pywry.mcp.handlers import _handle_export_widget

        mcp_state._widgets["w"] = MagicMock()
        mcp_state._widget_configs["w"] = {
            "html": "<div></div>",
            "title": "T",
            "height": 400,
            "toolbars": [],
        }
        out = _handle_export_widget(_make_ctx({"widget_id": "w"}))
        assert "code" in out
        assert "from pywry import PyWry" in out["code"]

    def test_export_widget_no_config(self, mcp_fresh_state) -> None:
        from pywry.mcp import state as mcp_state
        from pywry.mcp.handlers import _handle_export_widget

        mcp_state._widgets["w"] = MagicMock()
        out = _handle_export_widget(_make_ctx({"widget_id": "w"}))
        assert "error" in out

    def test_export_widget_no_widget(self, mcp_fresh_state) -> None:
        from pywry.mcp.handlers import _handle_export_widget

        out = _handle_export_widget(_make_ctx({}))
        assert "error" in out

    def test_list_resources(self, monkeypatch) -> None:
        """Stub get_resources() to bypass the AnyUrl validation issue."""
        from pywry.mcp import handlers

        fake = MagicMock()
        fake.uri = "pywry://component/button"
        fake.name = "Component: Button"
        fake.description = "x"

        monkeypatch.setattr(handlers, "get_resources", lambda: [fake])
        out = handlers._handle_list_resources(_make_ctx({}))
        assert "resources" in out
        assert "templates" in out
        assert len(out["resources"]) == 1

    def test_get_widget_app_no_widgets(self, mcp_fresh_state) -> None:
        from pywry.mcp.handlers import _handle_get_widget_app

        out = _handle_get_widget_app(_make_ctx({}))
        assert "error" in out

    def test_get_widget_app_html_missing(self, mcp_fresh_state) -> None:
        from pywry.inline import _state as inline_state
        from pywry.mcp import state as mcp_state
        from pywry.mcp.handlers import _handle_get_widget_app

        mcp_state._widgets["w"] = MagicMock()
        inline_state.widgets.pop("w", None)
        out = _handle_get_widget_app(_make_ctx({"widget_id": "w"}))
        assert "error" in out


# ---------------------------------------------------------------------------
# TVChart internals — _minimal_confirm_state, _fetch_tvchart_state,
# _wait_for_data_settled, _poll_tvchart_state
# ---------------------------------------------------------------------------


class TestMinimalConfirmState:
    def test_non_dict_returns_empty(self) -> None:
        from pywry.mcp.handlers import _minimal_confirm_state

        assert _minimal_confirm_state(None) == {}
        assert _minimal_confirm_state("not-a-dict") == {}  # type: ignore

    def test_strips_unsafe_fields(self) -> None:
        from pywry.mcp.handlers import _minimal_confirm_state

        out = _minimal_confirm_state(
            {
                "symbol": "AAPL",
                "interval": "1D",
                "chartType": "Candles",
                "compareSymbols": {"a": "GOOG"},
                "indicators": [
                    {"seriesId": "ind_1", "name": "SMA", "type": "sma", "period": 20},
                    "not-a-dict",  # ignored
                ],
                "rawData": [],  # explicitly stripped
            }
        )
        assert out["symbol"] == "AAPL"
        assert out["compareSymbols"] == {"a": "GOOG"}
        assert out["indicators"][0]["name"] == "SMA"
        assert "rawData" not in out

    def test_omits_empty_compare(self) -> None:
        from pywry.mcp.handlers import _minimal_confirm_state

        out = _minimal_confirm_state({"symbol": "X", "compareSymbols": {}})
        assert "compareSymbols" not in out


class TestFetchTvchartState:
    def test_returns_none_on_error(self) -> None:
        from pywry.mcp.handlers import _fetch_tvchart_state

        with patch(
            "pywry.mcp.handlers.request_response",
            return_value={"chartId": "x", "error": "not found"},
        ):
            assert _fetch_tvchart_state(MagicMock()) is None

    def test_returns_none_on_timeout(self) -> None:
        from pywry.mcp.handlers import _fetch_tvchart_state

        with patch("pywry.mcp.handlers.request_response", return_value=None):
            assert _fetch_tvchart_state(MagicMock()) is None

    def test_strips_correlation_token(self) -> None:
        from pywry.mcp.handlers import _fetch_tvchart_state

        with patch(
            "pywry.mcp.handlers.request_response",
            return_value={"context": "tok", "symbol": "X"},
        ):
            out = _fetch_tvchart_state(MagicMock())
        assert out is not None
        assert "context" not in out
        assert out["symbol"] == "X"


class TestWaitForDataSettled:
    def test_returns_payload_on_match(self) -> None:
        from pywry.mcp.handlers import _wait_for_data_settled

        widget = MagicMock()
        captured: dict[str, Any] = {}

        def fake_on(event: str, listener: Any) -> Any:
            captured["listener"] = listener

            def unsubscribe() -> None:
                captured["unsubscribed"] = True

            return unsubscribe

        widget.on = fake_on

        def trigger():
            time.sleep(0.05)
            captured["listener"]({"symbol": "AAPL"}, "", "")

        threading.Thread(target=trigger, daemon=True).start()
        out = _wait_for_data_settled(widget, lambda s: s.get("symbol") == "AAPL", timeout=1.0)
        assert out is not None
        assert out["symbol"] == "AAPL"
        assert captured.get("unsubscribed") is True

    def test_ignores_non_dict_and_errors(self) -> None:
        from pywry.mcp.handlers import _wait_for_data_settled

        widget = MagicMock()
        captured: dict[str, Any] = {}

        def fake_on(event: str, listener: Any) -> Any:
            captured["listener"] = listener
            return None

        widget.on = fake_on

        def trigger():
            time.sleep(0.05)
            captured["listener"]("not-a-dict", "", "")
            captured["listener"]({"error": "x"}, "", "")
            captured["listener"]({"symbol": "AAPL"}, "", "")

        threading.Thread(target=trigger, daemon=True).start()
        out = _wait_for_data_settled(widget, lambda s: s.get("symbol") == "AAPL", timeout=1.0)
        assert out is not None

    def test_widget_on_raises(self) -> None:
        """When widget.on raises, the helper still returns on timeout."""
        from pywry.mcp.handlers import _wait_for_data_settled

        widget = MagicMock()
        widget.on.side_effect = RuntimeError("nope")
        out = _wait_for_data_settled(widget, lambda _s: True, timeout=0.1)
        assert out is None

    def test_unsubscribe_raises(self) -> None:
        """A raising unsubscribe callback must not propagate."""
        from pywry.mcp.handlers import _wait_for_data_settled

        widget = MagicMock()
        captured: dict[str, Any] = {}

        def fake_on(event: str, listener: Any) -> Any:
            captured["listener"] = listener

            def bad_unsubscribe() -> None:
                raise RuntimeError("boom")

            return bad_unsubscribe

        widget.on = fake_on
        out = _wait_for_data_settled(widget, lambda _s: True, timeout=0.1)
        assert out is None


class TestPollTvchartState:
    def test_matches_after_settle(self) -> None:
        from pywry.mcp.handlers import _poll_tvchart_state

        states = [{"symbol": "OLD"}, {"symbol": "NEW"}]

        def fake_fetch(_w, timeout=1.0):
            return states.pop(0) if states else None

        with patch("pywry.mcp.handlers._fetch_tvchart_state", side_effect=fake_fetch):
            out = _poll_tvchart_state(
                MagicMock(),
                matcher=lambda s: s.get("symbol") == "NEW",
                total_timeout=1.0,
                poll_interval=0.05,
                settle_delay=0.0,
            )
        assert out is not None
        assert out["symbol"] == "NEW"

    def test_with_settle_delay(self, monkeypatch) -> None:
        """``settle_delay > 0`` triggers the leading time.sleep call."""
        from pywry.mcp import handlers as h

        called: dict[str, float] = {}
        original_sleep = h.time.sleep

        def fake_sleep(seconds):
            called["sleep"] = seconds
            original_sleep(0)

        monkeypatch.setattr(h.time, "sleep", fake_sleep)
        with patch.object(h, "_fetch_tvchart_state", return_value={"symbol": "X"}):
            h._poll_tvchart_state(
                MagicMock(),
                matcher=lambda s: s.get("symbol") == "X",
                total_timeout=0.5,
                poll_interval=0.05,
                settle_delay=0.1,
            )
        assert called.get("sleep") == 0.1

    def test_returns_latest_on_timeout(self) -> None:
        from pywry.mcp.handlers import _poll_tvchart_state

        def fake_fetch(_w, timeout=1.0):
            return {"symbol": "OLD"}

        with patch("pywry.mcp.handlers._fetch_tvchart_state", side_effect=fake_fetch):
            out = _poll_tvchart_state(
                MagicMock(),
                matcher=lambda s: s.get("symbol") == "NEW",
                total_timeout=0.05,
                poll_interval=0.02,
                settle_delay=0.0,
            )
        assert out is not None
        assert out["symbol"] == "OLD"


# ---------------------------------------------------------------------------
# Symbol search / compare / change-interval confirmed paths
# ---------------------------------------------------------------------------


class TestTvchartConfirmPaths:
    def test_symbol_search_confirmed_via_settled(self, mcp_widget, monkeypatch) -> None:
        from pywry.mcp import handlers as h

        monkeypatch.setattr(
            h,
            "_wait_for_data_settled",
            lambda *_a, **_kw: {"symbol": "MSFT", "interval": "1D"},
        )
        monkeypatch.setattr(h, "_fetch_tvchart_state", lambda *_a, **_kw: {"symbol": "AAPL"})
        out = h._handle_tvchart_symbol_search(
            _make_ctx({"widget_id": "w", "query": "MSFT", "auto_select": True})
        )
        assert out["confirmed"] is True
        assert out["symbol"] == "MSFT"

    def test_symbol_search_confirmed_fuzzy(self, mcp_widget, monkeypatch) -> None:
        from pywry.mcp import handlers as h

        monkeypatch.setattr(h, "_wait_for_data_settled", lambda *_a, **_kw: {"symbol": "MSFT"})
        monkeypatch.setattr(h, "_fetch_tvchart_state", lambda *_a, **_kw: {"symbol": "AAPL"})
        out = h._handle_tvchart_symbol_search(
            _make_ctx({"widget_id": "w", "query": "microsoft", "auto_select": True})
        )
        assert out["confirmed"] is True

    def test_symbol_search_unconfirmed_emits_reason(self, mcp_widget, monkeypatch) -> None:
        from pywry.mcp import handlers as h

        monkeypatch.setattr(h, "_wait_for_data_settled", lambda *_a, **_kw: None)
        monkeypatch.setattr(h, "_fetch_tvchart_state", lambda *_a, **_kw: None)
        out = h._handle_tvchart_symbol_search(
            _make_ctx({"widget_id": "w", "query": "MSFT", "auto_select": True})
        )
        assert out["confirmed"] is False
        assert "reason" in out

    def test_compare_confirmed(self, mcp_widget, monkeypatch) -> None:
        from pywry.mcp import handlers as h

        monkeypatch.setattr(
            h,
            "_wait_for_data_settled",
            lambda *_a, **_kw: {"compareSymbols": {"a": "GOOGL"}},
        )
        monkeypatch.setattr(h, "_fetch_tvchart_state", lambda *_a, **_kw: None)
        out = h._handle_tvchart_compare(
            _make_ctx({"widget_id": "w", "query": "GOOGL", "auto_add": True})
        )
        assert out["confirmed"] is True

    def test_compare_unconfirmed(self, mcp_widget, monkeypatch) -> None:
        from pywry.mcp import handlers as h

        monkeypatch.setattr(h, "_wait_for_data_settled", lambda *_a, **_kw: None)
        monkeypatch.setattr(h, "_fetch_tvchart_state", lambda *_a, **_kw: None)
        out = h._handle_tvchart_compare(
            _make_ctx({"widget_id": "w", "query": "GOOGL", "auto_add": True})
        )
        assert out["confirmed"] is False

    def test_change_interval_confirmed(self, mcp_widget, monkeypatch) -> None:
        from pywry.mcp import handlers as h

        monkeypatch.setattr(
            h,
            "_wait_for_data_settled",
            lambda *_a, **_kw: {"interval": "5m", "symbol": "AAPL"},
        )
        out = h._handle_tvchart_change_interval(_make_ctx({"widget_id": "w", "value": "5m"}))
        assert out["confirmed"] is True

    def test_change_interval_normalises_1d(self, mcp_widget, monkeypatch) -> None:
        """Frontend reports "1D" while caller asked "D" — must still match."""
        from pywry.mcp import handlers as h

        monkeypatch.setattr(h, "_wait_for_data_settled", lambda *_a, **_kw: {"interval": "1D"})
        out = h._handle_tvchart_change_interval(_make_ctx({"widget_id": "w", "value": "D"}))
        assert out["confirmed"] is True

    def test_change_interval_matcher_branches(self, mcp_widget, monkeypatch) -> None:
        """Probe the inner ``_matches`` closure with several states."""
        from pywry.mcp import handlers as h

        def fake_wait(_widget, matcher, **_kw):
            assert matcher({"interval": "5m"}) is True
            assert matcher({"interval": ""}) is False
            return {"interval": "5m"}

        monkeypatch.setattr(h, "_wait_for_data_settled", fake_wait)
        out = h._handle_tvchart_change_interval(_make_ctx({"widget_id": "w", "value": "5m"}))
        assert out["confirmed"] is True

    def test_symbol_search_matcher_branches(self, mcp_widget, monkeypatch) -> None:
        from pywry.mcp import handlers as h

        monkeypatch.setattr(h, "_fetch_tvchart_state", lambda *_a, **_kw: {"symbol": "OLD"})

        def fake_wait(_widget, matcher, **_kw):
            assert matcher({"symbol": ""}) is False
            assert matcher({"symbol": "MSFT"}) is True
            assert matcher({"symbol": "AAPL"}) is True
            return {"symbol": "MSFT"}

        monkeypatch.setattr(h, "_wait_for_data_settled", fake_wait)
        out = h._handle_tvchart_symbol_search(
            _make_ctx({"widget_id": "w", "query": "MSFT", "auto_select": True})
        )
        assert out["confirmed"] is True

    def test_compare_matcher_branches(self, mcp_widget, monkeypatch) -> None:
        from pywry.mcp import handlers as h

        monkeypatch.setattr(
            h,
            "_fetch_tvchart_state",
            lambda *_a, **_kw: {"compareSymbols": {"a": "PRE"}},
        )

        def fake_wait(_widget, matcher, **_kw):
            assert matcher({"compareSymbols": "not a dict"}) is False
            assert matcher({"compareSymbols": {"x": "GOOGL"}}) is True
            assert matcher({"compareSymbols": {"a": "PRE", "b": "NEW"}}) is True
            assert matcher({"compareSymbols": {"a": "PRE"}}) is False
            return {"compareSymbols": {"x": "GOOGL"}}

        monkeypatch.setattr(h, "_wait_for_data_settled", fake_wait)
        out = h._handle_tvchart_compare(
            _make_ctx({"widget_id": "w", "query": "GOOGL", "auto_add": True})
        )
        assert out["confirmed"] is True

    def test_symbol_search_with_chart_id_and_filters(self, mcp_widget, monkeypatch) -> None:
        from pywry.mcp import handlers as h

        monkeypatch.setattr(h, "_wait_for_data_settled", lambda *_a, **_kw: None)
        monkeypatch.setattr(h, "_fetch_tvchart_state", lambda *_a, **_kw: None)
        out = h._handle_tvchart_symbol_search(
            _make_ctx(
                {
                    "widget_id": "w",
                    "query": "SPY",
                    "auto_select": True,
                    "chart_id": "alt",
                    "symbol_type": "etf",
                    "exchange": "NYSEARCA",
                }
            )
        )
        emit_calls = mcp_widget.emit.call_args_list
        emitted = [c.args for c in emit_calls if c.args[0] == "tvchart:symbol-search"]
        assert emitted
        payload = emitted[0][1]
        assert payload["chartId"] == "alt"
        assert payload["symbolType"] == "etf"
        assert payload["exchange"] == "NYSEARCA"
        assert out["confirmed"] is False

    def test_change_interval_no_value_returns_event_only(self, mcp_widget, monkeypatch) -> None:
        from pywry.mcp import handlers as h

        out = h._handle_tvchart_change_interval(_make_ctx({"widget_id": "w"}))
        assert out["event_sent"] is True
        assert "confirmed" not in out

    def test_emit_zoom_confirmed(self, mcp_widget, monkeypatch) -> None:
        from pywry.mcp import handlers as h

        monkeypatch.setattr(
            h,
            "_wait_for_data_settled",
            lambda *_a, **_kw: {
                "symbol": "AAPL",
                "visibleRange": {"from": 1, "to": 2},
            },
        )
        out = h._handle_tvchart_set_visible_range(
            _make_ctx({"widget_id": "w", "from_time": 1, "to_time": 2})
        )
        assert out["confirmed"] is True
        assert out["visibleRange"] == {"from": 1, "to": 2}

    def test_emit_zoom_logical_range_fallback(self, mcp_widget, monkeypatch) -> None:
        """When ``visibleRange`` is absent, ``visibleLogicalRange`` is used."""
        from pywry.mcp import handlers as h

        monkeypatch.setattr(
            h,
            "_wait_for_data_settled",
            lambda *_a, **_kw: {
                "symbol": "AAPL",
                "visibleLogicalRange": {"from": 0.0, "to": 10.0},
            },
        )
        out = h._handle_tvchart_fit_content(_make_ctx({"widget_id": "w"}))
        assert out["confirmed"] is True
        assert out["visibleRange"] == {"from": 0.0, "to": 10.0}

    def test_emit_zoom_unconfirmed(self, mcp_widget, monkeypatch) -> None:
        from pywry.mcp import handlers as h

        monkeypatch.setattr(h, "_wait_for_data_settled", lambda *_a, **_kw: None)
        out = h._handle_tvchart_time_range(_make_ctx({"widget_id": "w", "value": "1Y"}))
        assert out["confirmed"] is False
        assert "reason" in out

    def test_emit_zoom_invalid_widget(self, mcp_fresh_state) -> None:
        from pywry.mcp import handlers as h

        out = h._handle_tvchart_set_visible_range(
            _make_ctx({"widget_id": "ghost", "from_time": 1, "to_time": 2})
        )
        assert "error" in out

    def test_change_interval_invalid_widget(self, mcp_fresh_state) -> None:
        from pywry.mcp import handlers as h

        out = h._handle_tvchart_change_interval(_make_ctx({"widget_id": "ghost", "value": "1m"}))
        assert "error" in out

    def test_compare_invalid_widget(self, mcp_fresh_state) -> None:
        from pywry.mcp import handlers as h

        out = h._handle_tvchart_compare(_make_ctx({"widget_id": "ghost", "query": "x"}))
        assert "error" in out

    def test_symbol_search_invalid_widget(self, mcp_fresh_state) -> None:
        from pywry.mcp import handlers as h

        out = h._handle_tvchart_symbol_search(_make_ctx({"widget_id": "ghost", "query": "x"}))
        assert "error" in out

    def test_snapshot_compare_set_non_dict(self, monkeypatch) -> None:
        from pywry.mcp import handlers as h

        monkeypatch.setattr(
            h,
            "_fetch_tvchart_state",
            lambda *_a, **_kw: {"compareSymbols": "not a dict"},
        )
        assert h._snapshot_compare_set(MagicMock()) == set()

    def test_build_compare_payload_filters_blanks(self) -> None:
        from pywry.mcp.handlers import _build_compare_payload

        ctx = _make_ctx({"query": "AAPL", "exchange": "", "symbol_type": "stock", "chart_id": None})
        payload = _build_compare_payload(ctx)
        assert "exchange" not in payload
        assert "chartId" not in payload
        assert payload["symbolType"] == "stock"


# ---------------------------------------------------------------------------
# tvchart_save_state / tvchart_request_state / list_indicators
# ---------------------------------------------------------------------------


class TestTvchartStateHandlers:
    def test_save_state_widget_missing(self, mcp_fresh_state) -> None:
        from pywry.mcp.handlers import _handle_tvchart_save_state

        out = _handle_tvchart_save_state(_make_ctx({"widget_id": "ghost"}))
        assert "error" in out

    def test_request_state_widget_missing(self, mcp_fresh_state) -> None:
        from pywry.mcp.handlers import _handle_tvchart_request_state

        out = _handle_tvchart_request_state(_make_ctx({"widget_id": "ghost"}))
        assert "error" in out

    def test_request_state_with_chart_id(self, mcp_widget, monkeypatch) -> None:
        from pywry.mcp import handlers as h

        captured: dict[str, Any] = {}

        def fake_request_response(*_a, **_kw):
            captured["called"] = True
            return {"context": "tok", "chartId": "alt", "symbol": "AAPL"}

        monkeypatch.setattr(h, "request_response", fake_request_response)
        out = h._handle_tvchart_request_state(_make_ctx({"widget_id": "w", "chart_id": "alt"}))
        assert captured.get("called") is True
        assert out["state"]["symbol"] == "AAPL"
        assert "context" not in out["state"]

    def test_list_indicators_widget_missing(self, mcp_fresh_state) -> None:
        from pywry.mcp.handlers import _handle_tvchart_list_indicators

        out = _handle_tvchart_list_indicators(_make_ctx({"widget_id": "ghost"}))
        assert "error" in out

    def test_list_indicators_chart_id_in_payload(self, mcp_widget, monkeypatch) -> None:
        from pywry.mcp import handlers as h

        captured: dict[str, Any] = {}

        def fake_request_response(_widget, _req, _resp, payload, **_kw):
            captured["payload"] = payload
            return {"context": "tok", "indicators": []}

        monkeypatch.setattr(h, "request_response", fake_request_response)
        h._handle_tvchart_list_indicators(_make_ctx({"widget_id": "w", "chart_id": "alt"}))
        assert captured["payload"]["chartId"] == "alt"

    def test_change_interval_with_chart_id(self, mcp_widget, monkeypatch) -> None:
        from pywry.mcp import handlers as h

        monkeypatch.setattr(h, "_wait_for_data_settled", lambda *_a, **_kw: None)
        h._handle_tvchart_change_interval(
            _make_ctx({"widget_id": "w", "value": "5m", "chart_id": "alt"})
        )
        emit_calls = [
            c.args for c in mcp_widget.emit.call_args_list if c.args[0] == "tvchart:interval-change"
        ]
        assert emit_calls[0][1]["chartId"] == "alt"

    def test_emit_zoom_with_chart_id(self, mcp_widget, monkeypatch) -> None:
        from pywry.mcp import handlers as h

        monkeypatch.setattr(h, "_wait_for_data_settled", lambda *_a, **_kw: None)
        h._handle_tvchart_set_visible_range(
            _make_ctx(
                {
                    "widget_id": "w",
                    "from_time": 1,
                    "to_time": 2,
                    "chart_id": "alt",
                }
            )
        )
        emit = next(c.args for c in mcp_widget.emit.call_args_list)
        assert emit[1]["chartId"] == "alt"


# ---------------------------------------------------------------------------
# Chat handlers
# ---------------------------------------------------------------------------


def _build_fake_chat_widget_config(slash_commands: list | None = None):
    """Mock for ChatWidgetConfig with optional slash_commands attribute."""
    cfg = MagicMock()
    cfg.title = "Chat"
    cfg.height = 700
    cfg.show_sidebar = True
    cfg.show_settings = True
    cfg.chat_config = MagicMock()
    cfg.chat_config.model = "gpt-4"
    cfg.chat_config.temperature = 0.7
    cfg.chat_config.system_prompt = ""
    cfg.chat_config.slash_commands = slash_commands or []
    return cfg


class TestChatHandlers:
    def test_create_chat_widget_native(self, mcp_fresh_state) -> None:
        from pywry.mcp.handlers import _handle_create_chat_widget

        widget = MagicMock()
        widget.widget_id = "chat1"
        app = MagicMock()
        app.show.return_value = widget

        with (
            patch("pywry.mcp.handlers.get_app", return_value=app),
            patch(
                "pywry.mcp.builders.build_chat_widget_config",
                return_value=_build_fake_chat_widget_config(),
            ),
        ):
            out = _handle_create_chat_widget(
                _make_ctx({"title": "C", "model": "gpt-4", "system_prompt": "Hi"})
            )
        assert out["created"] is True
        assert out["widget_id"] == "chat1"
        assert "thread_id" in out

    def test_create_chat_widget_headless(self, mcp_fresh_state) -> None:
        from pywry.inline import _state as inline_state
        from pywry.mcp.handlers import _handle_create_chat_widget

        widget = MagicMock()
        widget.widget_id = "chat-h"
        app = MagicMock()
        app.show.return_value = widget
        inline_state.widgets["chat-h"] = {"html": "<html></html>"}
        try:
            with (
                patch("pywry.mcp.handlers.get_app", return_value=app),
                patch(
                    "pywry.mcp.builders.build_chat_widget_config",
                    return_value=_build_fake_chat_widget_config(),
                ),
            ):
                out = _handle_create_chat_widget(_make_ctx({"title": "Hello"}, headless=True))
            assert "_app_artifact" in out
        finally:
            inline_state.widgets.pop("chat-h", None)
            inline_state.widget_revisions.pop("chat-h", None)

    def test_create_chat_widget_with_slash_commands(self, mcp_fresh_state) -> None:
        from pywry.mcp.handlers import _handle_create_chat_widget

        widget = MagicMock()
        widget.widget_id = "chatx"
        app = MagicMock()
        app.show.return_value = widget

        slash = MagicMock()
        slash.name = "/help"
        slash.description = "Help"
        cfg = _build_fake_chat_widget_config(slash_commands=[slash])

        with (
            patch("pywry.mcp.handlers.get_app", return_value=app),
            patch("pywry.mcp.builders.build_chat_widget_config", return_value=cfg),
        ):
            _handle_create_chat_widget(_make_ctx({"title": "C"}))

        emitted = [
            c.args[1]
            for c in widget.emit.call_args_list
            if c.args and c.args[0] == "chat:register-command"
        ]
        names = {p.get("name") for p in emitted}
        assert "/help" in names

    def test_create_chat_widget_with_toolbars(self, mcp_fresh_state) -> None:
        from pywry.mcp.handlers import _handle_create_chat_widget

        widget = MagicMock()
        widget.widget_id = "chat-tb"
        app = MagicMock()
        app.show.return_value = widget
        with (
            patch("pywry.mcp.handlers.get_app", return_value=app),
            patch(
                "pywry.mcp.builders.build_chat_widget_config",
                return_value=_build_fake_chat_widget_config(),
            ),
        ):
            out = _handle_create_chat_widget(
                _make_ctx(
                    {
                        "title": "C",
                        "toolbars": [
                            {
                                "position": "top",
                                "items": [{"type": "button", "label": "X", "event": "x:click"}],
                            }
                        ],
                    }
                )
            )
        assert out["created"] is True

    def test_send_message(self, mcp_widget) -> None:
        from pywry.mcp import handlers as h

        h._chat_configs["w"] = MagicMock()
        try:
            out = h._handle_chat_send_message(
                _make_ctx({"widget_id": "w", "text": "hi", "thread_id": "t1"})
            )
            assert out["sent"] is True
            assert out["thread_id"] == "t1"
            assert out["message_id"].startswith("msg_")
        finally:
            h._chat_configs.pop("w", None)

    def test_send_message_no_config(self, mcp_widget) -> None:
        from pywry.mcp.handlers import _handle_chat_send_message

        out = _handle_chat_send_message(_make_ctx({"widget_id": "w", "text": "hi"}))
        assert "error" in out

    def test_send_message_widget_missing(self, mcp_fresh_state) -> None:
        from pywry.mcp.handlers import _handle_chat_send_message

        out = _handle_chat_send_message(_make_ctx({"widget_id": "ghost", "text": "hi"}))
        assert "error" in out

    def test_stop_generation_no_handle(self, mcp_widget) -> None:
        from pywry.mcp.handlers import _handle_chat_stop_generation

        out = _handle_chat_stop_generation(_make_ctx({"widget_id": "w", "thread_id": "t1"}))
        assert out["stopped"] is False

    def test_stop_generation_active(self, mcp_widget) -> None:
        from pywry.mcp import handlers as h

        handle = MagicMock()
        handle.cancel_event.is_set.return_value = False
        handle.partial_content = "partial"
        handle.message_id = "msg_x"
        h._active_generations["w"] = {"t1": handle}
        try:
            out = h._handle_chat_stop_generation(_make_ctx({"widget_id": "w", "thread_id": "t1"}))
            assert out["stopped"] is True
            handle.cancel.assert_called_once()
        finally:
            h._active_generations.pop("w", None)

    def test_stop_generation_no_widgets_no_id(self, mcp_fresh_state) -> None:
        from pywry.mcp.handlers import _handle_chat_stop_generation

        out = _handle_chat_stop_generation(_make_ctx({}))
        assert "error" in out

    def test_manage_thread_create(self, mcp_widget) -> None:
        from pywry.mcp.handlers import _handle_chat_manage_thread

        out = _handle_chat_manage_thread(
            _make_ctx({"widget_id": "w", "action": "create", "title": "T"})
        )
        assert out["action"] == "create"
        assert out["thread_id"].startswith("thread_")

    def test_manage_thread_switch(self, mcp_widget) -> None:
        from pywry.mcp.handlers import _handle_chat_manage_thread

        out = _handle_chat_manage_thread(
            _make_ctx({"widget_id": "w", "action": "switch", "thread_id": "thread_x"})
        )
        assert out["action"] == "switch"

    def test_manage_thread_switch_missing_id(self, mcp_widget) -> None:
        from pywry.mcp.handlers import _handle_chat_manage_thread

        out = _handle_chat_manage_thread(_make_ctx({"widget_id": "w", "action": "switch"}))
        assert "error" in out

    def test_manage_thread_delete(self, mcp_widget) -> None:
        from pywry.mcp import handlers as h

        h._chat_thread_store.setdefault("w", {})["thread_x"] = MagicMock()
        h._chat_message_store.setdefault("w", {})["thread_x"] = []
        try:
            out = h._handle_chat_manage_thread(
                _make_ctx(
                    {
                        "widget_id": "w",
                        "action": "delete",
                        "thread_id": "thread_x",
                    }
                )
            )
            assert out["deleted"] is True
            assert "thread_x" not in h._chat_thread_store["w"]
        finally:
            h._chat_thread_store.pop("w", None)
            h._chat_message_store.pop("w", None)

    def test_manage_thread_delete_missing_id(self, mcp_widget) -> None:
        from pywry.mcp.handlers import _handle_chat_manage_thread

        out = _handle_chat_manage_thread(_make_ctx({"widget_id": "w", "action": "delete"}))
        assert "error" in out

    def test_manage_thread_rename(self, mcp_widget) -> None:
        from pywry.mcp import handlers as h

        thread = MagicMock()
        thread.title = "Old"
        h._chat_thread_store.setdefault("w", {})["thread_x"] = thread
        try:
            out = h._handle_chat_manage_thread(
                _make_ctx(
                    {
                        "widget_id": "w",
                        "action": "rename",
                        "thread_id": "thread_x",
                        "title": "New",
                    }
                )
            )
            assert out["action"] == "rename"
            assert thread.title == "New"
        finally:
            h._chat_thread_store.pop("w", None)

    def test_manage_thread_rename_missing_id(self, mcp_widget) -> None:
        from pywry.mcp.handlers import _handle_chat_manage_thread

        out = _handle_chat_manage_thread(_make_ctx({"widget_id": "w", "action": "rename"}))
        assert "error" in out

    def test_manage_thread_list(self, mcp_widget) -> None:
        from pywry.mcp import handlers as h

        thread = MagicMock()
        thread.title = "Some"
        h._chat_thread_store.setdefault("w", {})["thread_y"] = thread
        try:
            out = h._handle_chat_manage_thread(_make_ctx({"widget_id": "w", "action": "list"}))
            assert out["action"] == "list"
            assert any(t["thread_id"] == "thread_y" for t in out["threads"])
        finally:
            h._chat_thread_store.pop("w", None)

    def test_manage_thread_unknown_action(self, mcp_widget) -> None:
        from pywry.mcp.handlers import _handle_chat_manage_thread

        out = _handle_chat_manage_thread(_make_ctx({"widget_id": "w", "action": "totally-unknown"}))
        assert "error" in out

    def test_manage_thread_widget_missing(self, mcp_fresh_state) -> None:
        from pywry.mcp.handlers import _handle_chat_manage_thread

        out = _handle_chat_manage_thread(_make_ctx({"widget_id": "ghost", "action": "create"}))
        assert "error" in out

    def test_register_command_adds_slash(self, mcp_widget) -> None:
        from pywry.mcp.handlers import _handle_chat_register_command

        out = _handle_chat_register_command(
            _make_ctx({"widget_id": "w", "name": "help", "description": "Help"})
        )
        assert out["registered"] is True
        assert out["name"].startswith("/")

    def test_register_command_already_slashed(self, mcp_widget) -> None:
        from pywry.mcp.handlers import _handle_chat_register_command

        out = _handle_chat_register_command(
            _make_ctx({"widget_id": "w", "name": "/clear", "description": ""})
        )
        assert out["name"] == "/clear"

    def test_register_command_widget_missing(self, mcp_fresh_state) -> None:
        from pywry.mcp.handlers import _handle_chat_register_command

        out = _handle_chat_register_command(_make_ctx({"widget_id": "ghost", "name": "/x"}))
        assert "error" in out

    def test_get_history_with_before_id(self, mcp_widget) -> None:
        from pywry.mcp import handlers as h

        h._chat_message_store.setdefault("w", {})["t1"] = [
            {"message_id": "m1", "role": "user", "text": "a"},
            {"message_id": "m2", "role": "user", "text": "b"},
            {"message_id": "m3", "role": "user", "text": "c"},
        ]
        try:
            out = h._handle_chat_get_history(
                _make_ctx(
                    {
                        "widget_id": "w",
                        "thread_id": "t1",
                        "limit": 10,
                        "before_id": "m3",
                    }
                )
            )
            assert len(out["messages"]) == 2
        finally:
            h._chat_message_store.pop("w", None)

    def test_get_history_paginated(self, mcp_widget) -> None:
        from pywry.mcp import handlers as h

        msgs = [{"message_id": f"m{i}", "role": "user", "text": str(i)} for i in range(5)]
        h._chat_message_store.setdefault("w", {})["t1"] = msgs
        try:
            out = h._handle_chat_get_history(
                _make_ctx({"widget_id": "w", "thread_id": "t1", "limit": 2})
            )
            assert len(out["messages"]) == 2
            assert out["has_more"] is True
            assert out["cursor"] is not None
        finally:
            h._chat_message_store.pop("w", None)

    def test_get_history_no_thread(self, mcp_widget) -> None:
        from pywry.mcp.handlers import _handle_chat_get_history

        out = _handle_chat_get_history(_make_ctx({"widget_id": "w"}))
        assert out["messages"] == []
        assert out["has_more"] is False

    def test_update_settings(self, mcp_widget) -> None:
        from pywry.mcp.handlers import _handle_chat_update_settings

        out = _handle_chat_update_settings(
            _make_ctx(
                {
                    "widget_id": "w",
                    "model": "gpt-4o",
                    "temperature": 0.5,
                    "max_tokens": 1000,
                    "system_prompt": "x",
                    "streaming": False,
                }
            )
        )
        assert out["applied"] is True
        assert out["settings"]["model"] == "gpt-4o"

    def test_update_settings_no_changes(self, mcp_widget) -> None:
        from pywry.mcp.handlers import _handle_chat_update_settings

        out = _handle_chat_update_settings(_make_ctx({"widget_id": "w"}))
        assert out["applied"] is True
        assert out["settings"] == {}

    def test_update_settings_widget_missing(self, mcp_fresh_state) -> None:
        from pywry.mcp.handlers import _handle_chat_update_settings

        out = _handle_chat_update_settings(_make_ctx({"widget_id": "ghost"}))
        assert "error" in out

    def test_set_typing(self, mcp_widget) -> None:
        from pywry.mcp.handlers import _handle_chat_set_typing

        out = _handle_chat_set_typing(
            _make_ctx({"widget_id": "w", "typing": True, "thread_id": "t1"})
        )
        assert out["typing"] is True

    def test_set_typing_widget_missing(self, mcp_fresh_state) -> None:
        from pywry.mcp.handlers import _handle_chat_set_typing

        out = _handle_chat_set_typing(_make_ctx({"widget_id": "ghost"}))
        assert "error" in out


# ---------------------------------------------------------------------------
# Defensive ``error or {default}`` branches — only hit when
# ``_resolve_widget_id`` returns (None, None), which is impossible in
# production.  Tests stub the resolver so each defensive default fires.
# ---------------------------------------------------------------------------


@pytest.fixture
def stub_resolve_returns_none(monkeypatch):
    """Force ``_resolve_widget_id`` to return the impossible (None, None)."""
    from pywry.mcp import handlers

    monkeypatch.setattr(handlers, "_resolve_widget_id", lambda _wid: (None, None))
    yield


class TestDefensiveResolverBranches:
    def test_get_widget_or_error_default(self, stub_resolve_returns_none) -> None:
        from pywry.mcp.handlers import _get_widget_or_error

        widget, err = _get_widget_or_error("anything")
        assert widget is None
        assert err == {"error": "widget_id could not be resolved."}

    def test_symbol_search_default(self, mcp_widget, stub_resolve_returns_none) -> None:
        from pywry.mcp.handlers import _handle_tvchart_symbol_search

        out = _handle_tvchart_symbol_search(_make_ctx({"widget_id": "w"}))
        assert out["error"] == "widget_id could not be resolved."

    def test_compare_default(self, mcp_widget, stub_resolve_returns_none) -> None:
        from pywry.mcp.handlers import _handle_tvchart_compare

        out = _handle_tvchart_compare(_make_ctx({"widget_id": "w"}))
        assert out["error"] == "widget_id could not be resolved."

    def test_change_interval_default(self, mcp_widget, stub_resolve_returns_none) -> None:
        from pywry.mcp.handlers import _handle_tvchart_change_interval

        out = _handle_tvchart_change_interval(_make_ctx({"widget_id": "w"}))
        assert out["error"] == "widget_id could not be resolved."

    def test_emit_zoom_default(self, mcp_widget, stub_resolve_returns_none) -> None:
        from pywry.mcp.handlers import _handle_tvchart_set_visible_range

        out = _handle_tvchart_set_visible_range(_make_ctx({"widget_id": "w"}))
        assert out["error"] == "widget_id could not be resolved."

    def test_send_event_default(self, mcp_widget, stub_resolve_returns_none) -> None:
        from pywry.mcp.handlers import _handle_send_event

        out = _handle_send_event(_make_ctx({"widget_id": "w", "event_type": "x:y"}))
        assert out["error"] == "widget_id could not be resolved."

    def test_chat_send_default(self, mcp_widget, stub_resolve_returns_none) -> None:
        from pywry.mcp.handlers import _handle_chat_send_message

        out = _handle_chat_send_message(_make_ctx({"widget_id": "w", "text": "hi"}))
        assert out["error"] == "widget_id could not be resolved."

    def test_chat_manage_thread_default(self, mcp_widget, stub_resolve_returns_none) -> None:
        from pywry.mcp.handlers import _handle_chat_manage_thread

        out = _handle_chat_manage_thread(_make_ctx({"widget_id": "w", "action": "create"}))
        assert out["error"] == "widget_id could not be resolved."

    def test_chat_get_history_default(self, mcp_widget, stub_resolve_returns_none) -> None:
        from pywry.mcp.handlers import _handle_chat_get_history

        out = _handle_chat_get_history(_make_ctx({"widget_id": "w"}))
        assert out["error"] == "widget_id could not be resolved."

    def test_chat_stop_generation_default(self, mcp_widget, stub_resolve_returns_none) -> None:
        from pywry.mcp.handlers import _handle_chat_stop_generation

        out = _handle_chat_stop_generation(_make_ctx({"widget_id": "w"}))
        assert out["error"] == "widget_id could not be resolved."

    def test_get_widget_app_default(self, mcp_widget, stub_resolve_returns_none) -> None:
        from pywry.mcp.handlers import _handle_get_widget_app

        out = _handle_get_widget_app(_make_ctx({"widget_id": "w"}))
        assert out["error"] == "widget_id could not be resolved."

    def test_emit_zoom_widget_missing(self, mcp_fresh_state, monkeypatch) -> None:
        """``_emit_zoom_and_confirm`` returns the widget-not-found error path."""
        from pywry.mcp import handlers as h

        monkeypatch.setattr(h, "_resolve_widget_id", lambda _w: ("missing", None))
        out = h._handle_tvchart_set_visible_range(
            _make_ctx({"widget_id": "missing", "from_time": 1, "to_time": 2})
        )
        assert "error" in out

    def test_change_interval_widget_missing(self, mcp_fresh_state, monkeypatch) -> None:
        from pywry.mcp import handlers as h

        monkeypatch.setattr(h, "_resolve_widget_id", lambda _w: ("missing", None))
        out = h._handle_tvchart_change_interval(_make_ctx({"widget_id": "missing", "value": "5m"}))
        assert "error" in out

    def test_compare_widget_missing(self, mcp_fresh_state, monkeypatch) -> None:
        from pywry.mcp import handlers as h

        monkeypatch.setattr(h, "_resolve_widget_id", lambda _w: ("missing", None))
        out = h._handle_tvchart_compare(_make_ctx({"widget_id": "missing", "query": "x"}))
        assert "error" in out

    def test_symbol_search_widget_missing(self, mcp_fresh_state, monkeypatch) -> None:
        from pywry.mcp import handlers as h

        monkeypatch.setattr(h, "_resolve_widget_id", lambda _w: ("missing", None))
        out = h._handle_tvchart_symbol_search(_make_ctx({"widget_id": "missing", "query": "x"}))
        assert "error" in out
