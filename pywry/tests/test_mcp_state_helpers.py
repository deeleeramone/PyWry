"""Unit tests for the MCP state-module helpers.

Covers:
- ``request_response`` — the request/response correlation helper used
  by tvchart_list_indicators / tvchart_request_state.
- ``capture_widget_events`` — passive listener wiring used at chart
  creation to bucket JS-side events into the MCP events dict.
"""

from __future__ import annotations

import threading

from typing import Any
from unittest.mock import MagicMock

import pytest

from pywry.mcp.state import capture_widget_events, request_response


class _FakeWidget:
    """Minimal widget surface that mimics ``on``/``emit`` behaviour."""

    def __init__(self) -> None:
        self.handlers: dict[str, list[Any]] = {}
        self.emitted: list[tuple[str, dict[str, Any]]] = []

    def on(self, event: str, handler: Any) -> None:
        self.handlers.setdefault(event, []).append(handler)

    def emit(self, event: str, payload: dict[str, Any]) -> None:
        self.emitted.append((event, payload))


# ---------------------------------------------------------------------------
# request_response
# ---------------------------------------------------------------------------


def test_request_response_round_trip_returns_matching_payload() -> None:
    """A response with the matching correlation token is returned to the caller."""
    widget = _FakeWidget()

    def emit(event: str, payload: dict[str, Any]) -> None:
        widget.emitted.append((event, payload))
        # Echo back via the registered listener
        for handler in widget.handlers.get("widget:state-response", []):
            handler({"context": payload["context"], "value": 42}, "", "")

    widget.emit = emit  # type: ignore
    out = request_response(
        widget,
        "widget:state-request",
        "widget:state-response",
        {},
        timeout=1.0,
    )
    assert out is not None
    assert out["value"] == 42
    # The request received the auto-generated correlation token
    assert "context" in widget.emitted[0][1]


def test_request_response_returns_none_on_timeout() -> None:
    widget = _FakeWidget()
    out = request_response(
        widget,
        "widget:state-request",
        "widget:state-response",
        {},
        timeout=0.05,
    )
    assert out is None


def test_request_response_ignores_mismatched_correlation_tokens() -> None:
    """Stray responses with a different correlation token must not unblock the wait."""
    widget = _FakeWidget()

    def emit(event: str, payload: dict[str, Any]) -> None:
        widget.emitted.append((event, payload))
        # Send a response with the WRONG token — caller must time out
        for handler in widget.handlers.get("widget:state-response", []):
            handler({"context": "wrong-token", "value": 99}, "", "")

    widget.emit = emit  # type: ignore
    out = request_response(
        widget,
        "widget:state-request",
        "widget:state-response",
        {},
        timeout=0.1,
    )
    assert out is None


def test_request_response_supports_custom_correlation_keys() -> None:
    widget = _FakeWidget()

    def emit(event: str, payload: dict[str, Any]) -> None:
        widget.emitted.append((event, payload))
        for handler in widget.handlers.get("widget:state-response", []):
            handler({"requestId": payload["requestId"], "ok": True}, "", "")

    widget.emit = emit  # type: ignore
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


def test_request_response_concurrent_requests_isolated() -> None:
    """Two concurrent round-trips must each receive their own response."""
    widget = _FakeWidget()
    pending: dict[str, threading.Event] = {}

    def emit(event: str, payload: dict[str, Any]) -> None:
        token = payload["context"]
        widget.emitted.append((event, payload))
        # Deliver the response on a worker thread — the listener filters
        # by correlation token so cross-talk is not allowed.
        evt = pending.setdefault(token, threading.Event())

        def _deliver() -> None:
            evt.wait(0.05)
            for handler in widget.handlers.get("widget:state-response", []):
                handler({"context": token, "echo": token}, "", "")

        threading.Thread(target=_deliver, daemon=True).start()
        # Release the deliverer immediately
        evt.set()

    widget.emit = emit  # type: ignore
    a = request_response(widget, "req", "widget:state-response", {}, timeout=1.0)
    b = request_response(widget, "req", "widget:state-response", {}, timeout=1.0)
    assert a is not None and b is not None
    assert a["echo"] != b["echo"]


def test_request_response_ignores_non_dict_responses() -> None:
    widget = _FakeWidget()

    def emit(event: str, payload: dict[str, Any]) -> None:
        widget.emitted.append((event, payload))
        # Non-dict response — listener must reject it
        for handler in widget.handlers.get("widget:state-response", []):
            handler("not-a-dict", "", "")
        # Then a real one
        for handler in widget.handlers.get("widget:state-response", []):
            handler({"context": payload["context"], "ok": True}, "", "")

    widget.emit = emit  # type: ignore
    out = request_response(widget, "req", "widget:state-response", {}, timeout=1.0)
    assert out == {"context": out["context"], "ok": True}


# ---------------------------------------------------------------------------
# capture_widget_events
# ---------------------------------------------------------------------------


def test_capture_widget_events_buckets_events_by_widget_id() -> None:
    widget = _FakeWidget()
    events: dict[str, list[dict[str, Any]]] = {}
    capture_widget_events(widget, "chart-1", events, ["tvchart:click", "tvchart:drawing-added"])

    # Simulate the JS frontend firing events
    widget.handlers["tvchart:click"][0]({"x": 1, "y": 2}, "", "")
    widget.handlers["tvchart:drawing-added"][0]({"id": "d-1"}, "", "")

    assert events["chart-1"] == [
        {"event": "tvchart:click", "data": {"x": 1, "y": 2}},
        {"event": "tvchart:drawing-added", "data": {"id": "d-1"}},
    ]


def test_capture_widget_events_registers_handler_per_event_name() -> None:
    widget = _FakeWidget()
    events: dict[str, list[dict[str, Any]]] = {}
    capture_widget_events(widget, "chart-1", events, ["a", "b", "c"])
    assert set(widget.handlers.keys()) == {"a", "b", "c"}


def test_capture_widget_events_ignores_widget_on_failure() -> None:
    """If widget.on raises for one event the others should still register."""
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


def test_capture_widget_events_separate_widget_buckets() -> None:
    widget_a = _FakeWidget()
    widget_b = _FakeWidget()
    events: dict[str, list[dict[str, Any]]] = {}
    capture_widget_events(widget_a, "chart-A", events, ["tvchart:click"])
    capture_widget_events(widget_b, "chart-B", events, ["tvchart:click"])
    widget_a.handlers["tvchart:click"][0]({"x": 1}, "", "")
    widget_b.handlers["tvchart:click"][0]({"x": 2}, "", "")
    assert events["chart-A"] == [{"event": "tvchart:click", "data": {"x": 1}}]
    assert events["chart-B"] == [{"event": "tvchart:click", "data": {"x": 2}}]


# ---------------------------------------------------------------------------
# pytest setup — ensure fixtures don't leak the global pending dicts
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_pending() -> None:
    from pywry.mcp import state as mcp_state

    mcp_state._pending_responses.clear()
    mcp_state._pending_events.clear()
    yield
    mcp_state._pending_responses.clear()
    mcp_state._pending_events.clear()
