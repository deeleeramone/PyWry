"""Global state for MCP server.

This module holds the shared state for the MCP server, including
the PyWry app instance and widget tracking.
"""

from __future__ import annotations

import contextlib
import threading
import uuid

from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from pywry import PyWry

# Global PyWry app instance for MCP server (mutable singleton, not a constant)
_app: PyWry | None = None

# Active widgets by ID
_widgets: dict[str, Any] = {}

# Widget configurations for export
_widget_configs: dict[str, dict[str, Any]] = {}

# Request/response correlation for tools that round-trip an event pair
# through the widget.  Keyed by request_id.
_pending_responses: dict[str, dict[str, Any]] = {}
_pending_events: dict[str, threading.Event] = {}
_pending_lock = threading.Lock()


def get_app() -> PyWry:
    """Get or create the global PyWry app instance.

    Adapts to the rendering environment:
    - Desktop (PYWRY_HEADLESS=0 or unset): Native windows via WindowMode.NEW_WINDOW
    - Headless (PYWRY_HEADLESS=1): Inline widgets via WindowMode.BROWSER

    Returns
    -------
    PyWry
        The global PyWry application instance.
    """
    import os

    global _app  # noqa: PLW0603
    if _app is None:
        from pywry import PyWry, WindowMode

        headless = os.environ.get("PYWRY_HEADLESS", "0") == "1"
        mode = WindowMode.BROWSER if headless else WindowMode.NEW_WINDOW
        _app = PyWry(mode=mode)
    return _app


def register_widget(widget_id: str, widget: Any) -> None:
    """Register a widget.

    Parameters
    ----------
    widget_id : str
        Unique identifier for the widget.
    widget : Any
        The widget instance.
    """
    _widgets[widget_id] = widget


def store_widget_config(widget_id: str, config: dict[str, Any]) -> None:
    """Store widget configuration for export.

    Parameters
    ----------
    widget_id : str
        The widget identifier.
    config : dict[str, Any]
        The widget configuration.
    """
    _widget_configs[widget_id] = config


def get_widgets() -> dict[str, Any]:
    """Get all widgets.

    Returns
    -------
    dict[str, Any]
        Dictionary of widget IDs to widget instances.
    """
    return _widgets


def get_widget(widget_id: str) -> Any | None:
    """Get a widget by ID.

    Parameters
    ----------
    widget_id : str
        The widget identifier.

    Returns
    -------
    Any or None
        The widget instance or None if not found.
    """
    return _widgets.get(widget_id)


def get_widget_config(widget_id: str) -> dict[str, Any] | None:
    """Get widget configuration by ID.

    Parameters
    ----------
    widget_id : str
        The widget identifier.

    Returns
    -------
    dict or None
        The widget configuration or None if not found.
    """
    return _widget_configs.get(widget_id)


def list_widget_ids() -> list[str]:
    """List all active widget IDs.

    Returns
    -------
    list of str
        List of widget identifiers.
    """
    return list(_widgets.keys())


def remove_widget(widget_id: str) -> bool:
    """Remove a widget.

    Parameters
    ----------
    widget_id : str
        The widget identifier.

    Returns
    -------
    bool
        True if widget was removed, False if not found.
    """
    if widget_id in _widgets:
        del _widgets[widget_id]
        _widget_configs.pop(widget_id, None)
        return True
    return False


# =============================================================================
# Request/response correlation
# =============================================================================


def request_response(
    widget: Any,
    request_event: str,
    response_event: str,
    payload: dict[str, Any],
    *,
    correlation_key: str = "context",
    response_correlation_key: str | None = None,
    timeout: float = 5.0,
) -> dict[str, Any] | None:
    """Emit a request event and block until the matching response arrives.

    Registers a one-shot handler on ``response_event`` that matches by a
    correlation token, generates the token, injects it into the payload
    under ``correlation_key``, emits ``request_event``, and waits up to
    ``timeout`` seconds for the response.

    Parameters
    ----------
    widget : Any
        The widget whose ``on``/``emit`` methods drive the round-trip.
    request_event : str
        Name of the Python→JS event to emit.
    response_event : str
        Name of the JS→Python event to listen for.
    payload : dict
        Request payload.  A correlation token is injected under
        ``correlation_key``; any existing value is overwritten.
    correlation_key : str
        Field name to use for the correlation token in the request
        payload (defaults to ``"context"``, matching PyWry convention).
    response_correlation_key : str or None
        Field name to read the correlation token from in the response.
        Defaults to ``correlation_key``.
    timeout : float
        Maximum seconds to wait for the response.

    Returns
    -------
    dict or None
        The response data, or ``None`` if the response didn't arrive
        within ``timeout``.
    """
    request_id = uuid.uuid4().hex
    response_correlation_key = response_correlation_key or correlation_key
    evt = threading.Event()

    with _pending_lock:
        _pending_events[request_id] = evt

    def _listener(data: Any, _event_type: str = "", _label: str = "") -> None:
        if not isinstance(data, dict):
            return
        token = data.get(response_correlation_key)
        if isinstance(token, str) and token == request_id:
            with _pending_lock:
                _pending_responses[request_id] = data
                pending = _pending_events.get(request_id)
            if pending:
                pending.set()

    try:
        widget.on(response_event, _listener)
    except Exception:
        with _pending_lock:
            _pending_events.pop(request_id, None)
        raise

    merged_payload = dict(payload or {})
    merged_payload[correlation_key] = request_id
    widget.emit(request_event, merged_payload)

    received = evt.wait(timeout)
    with _pending_lock:
        response = _pending_responses.pop(request_id, None)
        _pending_events.pop(request_id, None)
    return response if received else None


def capture_widget_events(
    widget: Any,
    widget_id: str,
    events: dict[str, list[dict[str, Any]]],
    event_names: list[str],
) -> None:
    """Register handlers that store incoming events in the MCP ``events`` dict.

    Used at widget creation time to populate ``ctx.events[widget_id]``
    with chart/drawing/tool-activity events so agents can retrieve them
    via the ``get_events`` tool.

    Parameters
    ----------
    widget : Any
        The widget whose ``on`` method will register listeners.
    widget_id : str
        Key under which events are bucketed in ``events``.
    events : dict
        The MCP-server-wide events dict (mutated in place).
    event_names : list[str]
        Event names to capture.  Each incoming event becomes an entry
        in ``events[widget_id]`` tagged with ``event`` and ``data``.
    """
    for name in event_names:

        def _make_handler(ev_name: str) -> Any:
            def _handler(data: Any, _event_type: str = "", _label: str = "") -> None:
                events.setdefault(widget_id, []).append({"event": ev_name, "data": data})

            return _handler

        with contextlib.suppress(Exception):
            widget.on(name, _make_handler(name))
