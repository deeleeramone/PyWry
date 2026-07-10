"""Tests for ``pywry.mcp.state``.

Covers:
- Singleton ``get_app()`` and ``PYWRY_HEADLESS`` mode switch.
- Widget registry: register / get / list / remove / get_widgets.
- Widget config store: store / get.
- ``request_response()`` — request/response correlation helper used by
  ``tvchart_list_indicators`` / ``tvchart_request_state``.
- ``capture_widget_events()`` — passive listener wiring used at chart
  creation to bucket JS-side events into the MCP events dict.
"""

from __future__ import annotations

import threading

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from pywry.mcp.state import capture_widget_events, request_response


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeWidget:
    """Minimal widget surface that mimics ``on``/``emit`` behaviour."""

    def __init__(self) -> None:
        self.handlers: dict[str, list[Any]] = {}
        self.emitted: list[tuple[str, dict[str, Any]]] = []

    def on(self, event: str, handler: Any) -> None:
        self.handlers.setdefault(event, []).append(handler)

    def emit(self, event: str, payload: dict[str, Any]) -> None:
        self.emitted.append((event, payload))


@pytest.fixture(autouse=True)
def _clear_pending() -> None:
    """Clear the global pending dicts between tests."""
    from pywry.mcp import state as mcp_state

    mcp_state._pending_responses.clear()
    mcp_state._pending_events.clear()
    yield
    mcp_state._pending_responses.clear()
    mcp_state._pending_events.clear()


# ---------------------------------------------------------------------------
# get_app singleton
# ---------------------------------------------------------------------------


class TestGetApp:
    def test_returns_same_instance(self) -> None:
        from pywry.mcp import state

        state._app = None
        with patch.dict("os.environ", {"PYWRY_HEADLESS": "0"}, clear=False):
            app1 = state.get_app()
            app2 = state.get_app()
            assert app1 is app2
        state._app = None

    def test_headless_mode_uses_browser_mode(self) -> None:
        from pywry.mcp import state
        from pywry.window_manager.modes.browser import BrowserMode

        state._app = None
        with patch.dict("os.environ", {"PYWRY_HEADLESS": "1"}, clear=False):
            app = state.get_app()
            assert isinstance(app._mode, BrowserMode)
        state._app = None


# ---------------------------------------------------------------------------
# Widget registry helpers
# ---------------------------------------------------------------------------


class TestWidgetRegistry:
    def test_register_widget(self) -> None:
        from pywry.mcp.state import _widgets, register_widget

        _widgets.clear()
        mock_widget = MagicMock()
        register_widget("test-123", mock_widget)
        assert _widgets["test-123"] is mock_widget
        _widgets.clear()

    def test_get_widget_found(self) -> None:
        from pywry.mcp.state import _widgets, get_widget

        _widgets.clear()
        mock_widget = MagicMock()
        _widgets["w"] = mock_widget
        assert get_widget("w") is mock_widget
        _widgets.clear()

    def test_get_widget_not_found(self) -> None:
        from pywry.mcp.state import _widgets, get_widget

        _widgets.clear()
        assert get_widget("nonexistent") is None

    def test_list_widget_ids(self) -> None:
        from pywry.mcp.state import _widgets, list_widget_ids

        _widgets.clear()
        _widgets["a"] = MagicMock()
        _widgets["b"] = MagicMock()
        assert set(list_widget_ids()) == {"a", "b"}
        _widgets.clear()

    def test_remove_widget_clears_config_too(self) -> None:
        from pywry.mcp.state import _widget_configs, _widgets, remove_widget

        _widgets.clear()
        _widget_configs.clear()
        _widgets["x"] = MagicMock()
        _widget_configs["x"] = {"html": "<div></div>"}
        assert remove_widget("x") is True
        assert "x" not in _widgets
        assert "x" not in _widget_configs

    def test_remove_widget_returns_false_when_absent(self) -> None:
        from pywry.mcp.state import _widgets, remove_widget

        _widgets.clear()
        assert remove_widget("nonexistent") is False

    def test_get_widgets(self) -> None:
        from pywry.mcp.state import _widgets, get_widgets

        _widgets.clear()
        _widgets["a"] = MagicMock()
        _widgets["b"] = MagicMock()
        result = get_widgets()
        assert result is _widgets
        assert len(result) == 2
        _widgets.clear()


# ---------------------------------------------------------------------------
# Widget config store
# ---------------------------------------------------------------------------


class TestWidgetConfigStore:
    def test_store_and_get_widget_config(self) -> None:
        from pywry.mcp.state import _widget_configs, get_widget_config, store_widget_config

        _widget_configs.clear()
        store_widget_config("w", {"html": "<p>x</p>", "title": "T"})
        cfg = get_widget_config("w")
        assert cfg is not None
        assert cfg["title"] == "T"
        _widget_configs.clear()

    def test_get_widget_config_not_found(self) -> None:
        from pywry.mcp.state import _widget_configs, get_widget_config

        _widget_configs.clear()
        assert get_widget_config("nonexistent") is None


# ---------------------------------------------------------------------------
# request_response
# ---------------------------------------------------------------------------


class TestRequestResponse:
    def test_round_trip_returns_matching_payload(self) -> None:
        widget = _FakeWidget()

        def emit(event: str, payload: dict[str, Any]) -> None:
            widget.emitted.append((event, payload))
            for handler in widget.handlers.get("widget:state-response", []):
                handler({"context": payload["context"], "value": 42}, "", "")

        widget.emit = emit  # type: ignore[assignment]
        out = request_response(
            widget,
            "widget:state-request",
            "widget:state-response",
            {},
            timeout=1.0,
        )
        assert out is not None
        assert out["value"] == 42
        assert "context" in widget.emitted[0][1]

    def test_returns_none_on_timeout(self) -> None:
        widget = _FakeWidget()
        out = request_response(
            widget,
            "widget:state-request",
            "widget:state-response",
            {},
            timeout=0.05,
        )
        assert out is None

    def test_ignores_mismatched_correlation_tokens(self) -> None:
        widget = _FakeWidget()

        def emit(event: str, payload: dict[str, Any]) -> None:
            widget.emitted.append((event, payload))
            for handler in widget.handlers.get("widget:state-response", []):
                handler({"context": "wrong-token", "value": 99}, "", "")

        widget.emit = emit  # type: ignore[assignment]
        out = request_response(
            widget,
            "widget:state-request",
            "widget:state-response",
            {},
            timeout=0.1,
        )
        assert out is None

    def test_supports_custom_correlation_keys(self) -> None:
        widget = _FakeWidget()

        def emit(event: str, payload: dict[str, Any]) -> None:
            widget.emitted.append((event, payload))
            for handler in widget.handlers.get("widget:state-response", []):
                handler({"requestId": payload["requestId"], "ok": True}, "", "")

        widget.emit = emit  # type: ignore[assignment]
        out = request_response(
            widget,
            "widget:state-request",
            "widget:state-response",
            {},
            correlation_key="requestId",
            timeout=1.0,
        )
        assert out is not None
        assert out["ok"] is True

    def test_concurrent_requests_isolated(self) -> None:
        widget = _FakeWidget()
        pending: dict[str, threading.Event] = {}

        def emit(event: str, payload: dict[str, Any]) -> None:
            token = payload["context"]
            widget.emitted.append((event, payload))
            evt = pending.setdefault(token, threading.Event())

            def _deliver() -> None:
                evt.wait(0.05)
                for handler in widget.handlers.get("widget:state-response", []):
                    handler({"context": token, "echo": token}, "", "")

            threading.Thread(target=_deliver, daemon=True).start()
            evt.set()

        widget.emit = emit  # type: ignore[assignment]
        a = request_response(widget, "req", "widget:state-response", {}, timeout=1.0)
        b = request_response(widget, "req", "widget:state-response", {}, timeout=1.0)
        assert a is not None and b is not None
        assert a["echo"] != b["echo"]

    def test_ignores_non_dict_responses(self) -> None:
        widget = _FakeWidget()

        def emit(event: str, payload: dict[str, Any]) -> None:
            widget.emitted.append((event, payload))
            for handler in widget.handlers.get("widget:state-response", []):
                handler("not-a-dict", "", "")
            for handler in widget.handlers.get("widget:state-response", []):
                handler({"context": payload["context"], "ok": True}, "", "")

        widget.emit = emit  # type: ignore[assignment]
        out = request_response(widget, "req", "widget:state-response", {}, timeout=1.0)
        assert out is not None
        assert out["ok"] is True

    def test_propagates_widget_on_exception(self) -> None:
        widget = MagicMock()
        widget.on.side_effect = RuntimeError("nope")

        with pytest.raises(RuntimeError, match="nope"):
            request_response(widget, "req", "resp", {}, timeout=0.1)


# ---------------------------------------------------------------------------
# capture_widget_events
# ---------------------------------------------------------------------------


class TestCaptureWidgetEvents:
    def test_buckets_events_by_widget_id(self) -> None:
        widget = _FakeWidget()
        events: dict[str, list[dict[str, Any]]] = {}
        capture_widget_events(widget, "chart-1", events, ["tvchart:click", "tvchart:drawing-added"])
        widget.handlers["tvchart:click"][0]({"x": 1, "y": 2}, "", "")
        widget.handlers["tvchart:drawing-added"][0]({"id": "d-1"}, "", "")
        assert events["chart-1"] == [
            {"event": "tvchart:click", "data": {"x": 1, "y": 2}},
            {"event": "tvchart:drawing-added", "data": {"id": "d-1"}},
        ]

    def test_registers_handler_per_event_name(self) -> None:
        widget = _FakeWidget()
        events: dict[str, list[dict[str, Any]]] = {}
        capture_widget_events(widget, "chart-1", events, ["a", "b", "c"])
        assert set(widget.handlers.keys()) == {"a", "b", "c"}

    def test_ignores_widget_on_failure(self) -> None:
        widget = MagicMock()
        calls: list[str] = []

        def fake_on(event: str, _handler: Any) -> None:
            calls.append(event)
            if event == "boom":
                raise RuntimeError("nope")

        widget.on = fake_on
        events: dict[str, list[dict[str, Any]]] = {}
        capture_widget_events(widget, "chart-1", events, ["ok-1", "boom", "ok-2"])
        assert calls == ["ok-1", "boom", "ok-2"]

    def test_separate_widget_buckets(self) -> None:
        widget_a = _FakeWidget()
        widget_b = _FakeWidget()
        events: dict[str, list[dict[str, Any]]] = {}
        capture_widget_events(widget_a, "chart-A", events, ["tvchart:click"])
        capture_widget_events(widget_b, "chart-B", events, ["tvchart:click"])
        widget_a.handlers["tvchart:click"][0]({"x": 1}, "", "")
        widget_b.handlers["tvchart:click"][0]({"x": 2}, "", "")
        assert events["chart-A"] == [{"event": "tvchart:click", "data": {"x": 1}}]
        assert events["chart-B"] == [{"event": "tvchart:click", "data": {"x": 2}}]
