"""MCP tool handlers for PyWry v2.0.0.

This module handles all tool call implementations using a dispatch pattern.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid

from collections.abc import Callable
from typing import Any

from .builders import build_toolbars
from .docs import COMPONENT_DOCS
from .resources import (
    export_widget_code,
    get_component_source,
    get_resource_templates,
    get_resources,
)
from .skills import get_skill, list_skills
from .state import (
    capture_widget_events,
    get_app,
    get_widget,
    list_widget_ids,
    register_widget,
    remove_widget,
    request_response,
    store_widget_config,
)


logger = logging.getLogger(__name__)


# Default set of tvchart events that are captured into the MCP events
# dict so agents can retrieve them via the ``get_events`` tool.
_TVCHART_CAPTURE_EVENTS = [
    "tvchart:click",
    "tvchart:crosshair-move",
    "tvchart:visible-range-change",
    "tvchart:drawing-added",
    "tvchart:drawing-deleted",
    "tvchart:open-layout-request",
    "tvchart:interval-change",
    "tvchart:chart-type-change",
]


# Type aliases
EventsDict = dict[str, list[dict[str, Any]]]
MakeCallback = Callable[[str], Callable[[Any, str, str], None]]
HandlerResult = dict[str, Any]


# =============================================================================
# Handler Context - passed to all handlers
# =============================================================================
class HandlerContext:
    """Context object containing shared state for handlers."""

    def __init__(
        self,
        args: dict[str, Any],
        events: EventsDict,
        make_callback: MakeCallback,
        headless: bool,
    ) -> None:
        self.args = args
        self.events = events
        self.make_callback = make_callback
        self.headless = headless


# =============================================================================
# Skills Handlers
# =============================================================================
def _handle_get_skills(ctx: HandlerContext) -> HandlerResult:
    skill_name = ctx.args.get("skill")
    if skill_name:
        skill = get_skill(skill_name)
        if skill:
            return {
                "skill": skill_name,
                "name": skill["name"],
                "description": skill["description"],
                "guidance": skill["guidance"],
            }
        return {"error": f"Unknown skill: {skill_name}"}
    return {
        "available_skills": [
            {
                "key": skill_info["id"],
                "name": skill_info["name"],
                "description": skill_info["description"],
            }
            for skill_info in list_skills()
        ],
        "usage": "Call get_skills(skill='<key>') for detailed guidance",
    }


# =============================================================================
# Widget Creation Helpers
# =============================================================================
def _apply_action(
    action: str,
    config: dict[str, Any],
    state: dict[str, Any],
    widget: Any,
    target: str | None,
) -> None:
    """Apply an action and optionally update the UI."""
    state_key = config.get("state_key", "value")

    if action == "increment":
        state[state_key] = state.get(state_key, 0) + 1
    elif action == "decrement":
        state[state_key] = state.get(state_key, 0) - 1
    elif action == "set":
        state[state_key] = config.get("value", 0)
    elif action == "toggle":
        state[state_key] = not state.get(state_key, False)
    elif action == "emit":
        emit_event = config.get("emit_event")
        if emit_event:
            widget.emit(emit_event, config.get("emit_data", {}))
        return

    if target:
        widget.emit("pywry:set-content", {"id": target, "text": str(state[state_key])})


def _make_action_callback(
    action_config: dict[str, Any],
    state: dict[str, Any],
    holder: dict[str, Any],
) -> Callable[[Any, str, str], None]:
    """Create a callback function from action configuration."""
    action = action_config.get("action", "emit")
    target = action_config.get("target")

    def callback(
        data: Any,  # pylint: disable=unused-argument
        event_type: str,  # pylint: disable=unused-argument
        label: str,  # pylint: disable=unused-argument
    ) -> None:
        widget = holder.get("widget")
        if widget:
            _apply_action(action, action_config, state, widget, target)

    return callback


def _infer_callbacks_from_toolbars(
    toolbars: list[Any],
    callbacks_config: dict[str, Any],
) -> None:
    """Auto-infer callbacks from toolbar button event patterns."""
    for toolbar in toolbars:
        for item in toolbar.items:
            if not (hasattr(item, "event") and item.event):
                continue
            event = item.event
            parts = event.split(":")
            if len(parts) != 2:
                continue
            target_id, action_name = parts
            if action_name in ("increment", "decrement"):
                callbacks_config[event] = {
                    "action": action_name,
                    "target": target_id,
                    "state_key": "value",
                }
            elif action_name == "reset":
                callbacks_config[event] = {
                    "action": "set",
                    "target": target_id,
                    "state_key": "value",
                    "value": 0,
                }
            elif action_name == "toggle":
                callbacks_config[event] = {
                    "action": "toggle",
                    "target": target_id,
                    "state_key": "value",
                }


def _register_widget_events(
    widget: Any,
    toolbars: list[Any] | None,
    callback: Callable[[Any, str, str], None],
) -> None:
    """Register event callbacks for toolbar items."""
    if toolbars:
        for toolbar in toolbars:
            for item in toolbar.items:
                if hasattr(item, "event") and item.event:
                    widget.on(item.event, callback)


# =============================================================================
# Widget Creation Handlers
# =============================================================================
def _handle_create_widget(ctx: HandlerContext) -> HandlerResult:
    app = get_app()
    args = ctx.args

    toolbars_data = args.get("toolbars", [])
    toolbars = build_toolbars(toolbars_data) if toolbars_data else None

    callbacks_config = args.get("callbacks", {})
    widget_state: dict[str, Any] = {}
    widget_holder: dict[str, Any] = {"widget": None}

    if not callbacks_config and toolbars:
        _infer_callbacks_from_toolbars(toolbars, callbacks_config)

    callbacks_dict: dict[str, Any] = {}
    for event_name, action_config in callbacks_config.items():
        callbacks_dict[event_name] = _make_action_callback(
            action_config, widget_state, widget_holder
        )

    widget = app.show(
        args["html"],
        title=args.get("title", "PyWry Widget"),
        height=args.get("height", 500),
        include_plotly=args.get("include_plotly", False),
        include_aggrid=args.get("include_aggrid", False),
        toolbars=toolbars,
        callbacks=callbacks_dict if callbacks_dict else None,
    )

    widget_holder["widget"] = widget
    widget_id = getattr(widget, "widget_id", None) or uuid.uuid4().hex
    callback = ctx.make_callback(widget_id)
    ctx.events[widget_id] = []

    _register_widget_events(widget, toolbars, callback)
    register_widget(widget_id, widget)

    store_widget_config(
        widget_id,
        {
            "html": args.get("html", ""),
            "title": args.get("title", "PyWry Widget"),
            "height": args.get("height", 500),
            "include_plotly": args.get("include_plotly", False),
            "include_aggrid": args.get("include_aggrid", False),
            "toolbars": toolbars_data,
        },
    )

    if ctx.headless:
        from ..inline import _state as inline_state
        from .app_artifact import attach_app_artifact

        if widget_id in inline_state.widgets:
            inline_state.widgets[widget_id]["persistent"] = True

        result: HandlerResult = {
            "widget_id": widget_id,
            "path": f"/widget/{widget_id}",
            "created": True,
            "export_uri": f"pywry://export/{widget_id}",
        }
        return attach_app_artifact(
            result, widget_id, title=args.get("title", "PyWry Widget")
        )

    return {
        "widget_id": widget_id,
        "mode": "native",
        "message": "Native window opened",
        "created": True,
    }


def _handle_build_div(ctx: HandlerContext) -> HandlerResult:
    from ..toolbar import Div

    div = Div(
        content=ctx.args.get("content", ""),
        component_id=ctx.args.get("component_id") or "",
        style=ctx.args.get("style") or "",
        class_name=ctx.args.get("class_name") or "",
    )
    return {"html": div.build_html()}


def _handle_build_ticker_item(ctx: HandlerContext) -> HandlerResult:
    from ..toolbar import TickerItem

    ticker_item = TickerItem(
        ticker=ctx.args["ticker"],
        text=ctx.args.get("text", ""),
        html=ctx.args.get("html", ""),
        class_name=ctx.args.get("class_name", ""),
        style=ctx.args.get("style", ""),
    )
    return {
        "html": ticker_item.build_html(),
        "ticker": ctx.args["ticker"],
        "update_event": "toolbar:marquee-set-item",
    }


def _handle_show_plotly(ctx: HandlerContext) -> HandlerResult:
    import plotly.graph_objects as go

    fig_dict = json.loads(ctx.args["figure_json"])
    fig = go.Figure(fig_dict)

    app = get_app()
    widget = app.show_plotly(
        figure=fig,
        title=ctx.args.get("title", "Plotly Chart"),
        height=ctx.args.get("height", 500),
    )

    widget_id = getattr(widget, "widget_id", None) or uuid.uuid4().hex
    register_widget(widget_id, widget)

    result: HandlerResult = {
        "widget_id": widget_id,
        "path": f"/widget/{widget_id}",
        "created": True,
    }

    if ctx.headless:
        from ..inline import _state as inline_state
        from .app_artifact import attach_app_artifact

        if widget_id in inline_state.widgets:
            inline_state.widgets[widget_id]["persistent"] = True
        result = attach_app_artifact(
            result, widget_id, title=ctx.args.get("title", "Plotly Chart")
        )

    return result


def _handle_show_dataframe(ctx: HandlerContext) -> HandlerResult:
    data = json.loads(ctx.args["data_json"])

    app = get_app()
    widget = app.show_dataframe(
        data=data,
        title=ctx.args.get("title", "Data Table"),
        height=ctx.args.get("height", 500),
    )

    widget_id = getattr(widget, "widget_id", None) or uuid.uuid4().hex
    register_widget(widget_id, widget)

    result: HandlerResult = {
        "widget_id": widget_id,
        "path": f"/widget/{widget_id}",
        "created": True,
    }

    if ctx.headless:
        from ..inline import _state as inline_state
        from .app_artifact import attach_app_artifact

        if widget_id in inline_state.widgets:
            inline_state.widgets[widget_id]["persistent"] = True
        result = attach_app_artifact(
            result, widget_id, title=ctx.args.get("title", "Data Table")
        )

    return result


def _handle_show_tvchart(ctx: HandlerContext) -> HandlerResult:
    data = json.loads(ctx.args["data_json"])

    app = get_app()
    widget = app.show_tvchart(
        data=data,
        title=ctx.args.get("title", "Chart"),
        height=ctx.args.get("height", 500),
        chart_options=ctx.args.get("chart_options"),
        series_options=ctx.args.get("series_options"),
    )

    widget_id = getattr(widget, "widget_id", None) or uuid.uuid4().hex
    register_widget(widget_id, widget)
    capture_widget_events(widget, widget_id, ctx.events, _TVCHART_CAPTURE_EVENTS)

    result: HandlerResult = {
        "widget_id": widget_id,
        "path": f"/widget/{widget_id}",
        "created": True,
    }

    if ctx.headless:
        from ..inline import _state as inline_state
        from .app_artifact import attach_app_artifact

        if widget_id in inline_state.widgets:
            inline_state.widgets[widget_id]["persistent"] = True
        result = attach_app_artifact(
            result, widget_id, title=ctx.args.get("title", "Chart")
        )

    return result


# =============================================================================
# Widget Manipulation Handlers
# =============================================================================
def _resolve_widget_id(widget_id: str | None) -> tuple[str | None, HandlerResult | None]:
    """Resolve the target widget id, defaulting to the sole registered widget.

    The MCP schema documents ``widget_id`` as required because
    multi-widget servers genuinely need it to disambiguate.  At dispatch
    time, however, a single-widget server can resolve the id from its
    own registry — every component has an id, the server already knows
    it, the agent shouldn't have to repeat what the server knows.

    Resolution rules:
    - ``widget_id`` provided → use it as-is.
    - Missing AND exactly one widget registered → use that widget.
    - Missing AND zero or many widgets → error listing the candidates.
    """
    if widget_id:
        return widget_id, None
    ids = list_widget_ids()
    if len(ids) == 1:
        return ids[0], None
    if not ids:
        return None, {
            "error": "widget_id is required (no widgets are registered yet).",
        }
    return None, {
        "error": (
            "widget_id is required when multiple widgets exist. "
            f"Registered widgets: {', '.join(ids)}."
        ),
    }


def _get_widget_or_error(widget_id: str | None) -> tuple[Any | None, HandlerResult | None]:
    """Resolve a widget by id (auto-defaulting to the sole registered widget).

    Returns the widget instance plus ``None``, or ``None`` plus a
    structured error dict listing the registered ids so the caller can
    self-correct.
    """
    resolved_id, error = _resolve_widget_id(widget_id)
    if error is not None or resolved_id is None:
        return None, error or {"error": "widget_id could not be resolved."}
    widget = get_widget(resolved_id)
    if not widget:
        ids = list_widget_ids()
        return None, {
            "error": (
                f"Widget not found: {resolved_id}."
                + (
                    f" Registered widgets: {', '.join(ids)}."
                    if ids
                    else " No widgets are registered yet."
                )
            ),
        }
    return widget, None


# =============================================================================
# TVChart Handlers — every tvchart:* event exposed as a first-class tool
# =============================================================================


def _fetch_tvchart_state(widget: Any, timeout: float = 1.5) -> dict[str, Any] | None:
    """Round-trip ``tvchart:request-state`` and strip the correlation token.

    The frontend answers with ``{chartId, error: "not found"}`` when
    the chart entry is mid-rebuild (destroy → recreate on a symbol or
    interval mutation).  Treat that as "state unavailable right now"
    and return ``None``.
    """
    response = request_response(
        widget,
        "tvchart:request-state",
        "tvchart:state-response",
        {},
        timeout=timeout,
    )
    if response is None:
        return None
    response.pop("context", None)
    if response.get("error"):
        return None
    return response


def _wait_for_data_settled(
    widget: Any,
    matcher: Callable[[dict[str, Any]], bool],
    *,
    timeout: float = 8.0,
) -> dict[str, Any] | None:
    """Block until the frontend signals a data-response has fully settled.

    The ``tvchart:data-settled`` event is emitted by the data-response
    handler after the destroy-recreate (symbol / interval change) or
    the in-place update (compare / overlay add) completes — including
    the 150ms tail for indicator re-add.  Waiting on it is strictly
    better than polling ``tvchart:request-state``: there's no race
    with the rebuild window and the payload is the exact post-mutation
    state snapshot.

    The matcher lets the caller ignore an unrelated concurrent
    mutation's settled event (e.g. compare-add firing while we're
    waiting for a symbol-change to settle).  Returns the first
    matching payload, or ``None`` on timeout.
    """
    import threading as _threading

    result: dict[str, dict[str, Any] | None] = {"payload": None}
    done = _threading.Event()

    def _listener(data: Any, _event_type: str = "", _label: str = "") -> None:
        if done.is_set() or not isinstance(data, dict):
            return
        if data.get("error"):
            return
        if matcher(data):
            result["payload"] = data
            done.set()

    # Register an event listener, wait for a matching payload, tear it
    # down.  ``widget.on`` returns an unsubscribe callable on most
    # PyWry backends; fall back to a best-effort untracked listener
    # otherwise.
    unsubscribe = None
    try:
        unsubscribe = widget.on("tvchart:data-settled", _listener)
    except Exception:
        logger.debug("widget.on('tvchart:data-settled') failed", exc_info=True)
    try:
        done.wait(timeout=timeout)
    finally:
        if callable(unsubscribe):
            try:
                unsubscribe()
            except Exception:
                logger.debug("unsubscribe failed", exc_info=True)
    return result["payload"]


def _poll_tvchart_state(
    widget: Any,
    *,
    matcher: Callable[[dict[str, Any]], bool],
    total_timeout: float = 6.0,
    poll_interval: float = 0.2,
    settle_delay: float = 0.4,
) -> dict[str, Any] | None:
    """Poll ``tvchart:request-state`` until the chart reflects a mutation.

    Many chart mutations kick off multi-hop async chains in the frontend
    (symbol-search -> datafeed-resolve -> data-request -> data-response -> destroy-recreate).
    The chart entry is genuinely unavailable during the destroy-recreate
    window and the frontend answers with ``{error: "not found"}`` that
    ``_fetch_tvchart_state`` already turns into ``None``.

    ``settle_delay`` is a short initial wait BEFORE the first poll so
    we don't race into the rebuild window before it's even started —
    otherwise the first fetch can return the still-alive pre-mutation
    state, matcher fails against an unchanged symbol, and we burn the
    poll budget waiting for a rebuild that already finished.
    """
    if settle_delay > 0:
        time.sleep(settle_delay)
    deadline = time.monotonic() + total_timeout
    latest: dict[str, Any] | None = None
    while True:
        state = _fetch_tvchart_state(widget, timeout=max(0.5, poll_interval * 4))
        if state is not None:
            latest = state
            if matcher(state):
                return state
        if time.monotonic() >= deadline:
            return latest
        time.sleep(poll_interval)


def _minimal_confirm_state(state: dict[str, Any] | None) -> dict[str, Any]:
    """Reduce a full state snapshot to fields safe for a mutation result.

    Confirmation results must not carry raw OHLCV bars, per-bar timestamps,
    drawings, or visible-range data.  Exposing any of those tempts the
    model into paraphrasing them into the reply (e.g. "last close: $...",
    which the model then rounds, reformats, or invents outright if the
    field is sparse).  Keep to identity fields only — the chart UI is
    what the user reads for prices.
    """
    if not isinstance(state, dict):
        return {}
    compares = state.get("compareSymbols")
    indicators_in = state.get("indicators") or []
    indicators_out: list[dict[str, Any]] = []
    if isinstance(indicators_in, list):
        for ind in indicators_in:
            if not isinstance(ind, dict):
                continue
            indicators_out.append(
                {
                    k: ind.get(k)
                    for k in ("seriesId", "name", "type", "period", "secondarySymbol")
                    if ind.get(k) is not None
                }
            )
    out = {
        "symbol": state.get("symbol") or None,
        "interval": state.get("interval") or None,
        "chartType": state.get("chartType") or None,
    }
    if isinstance(compares, dict) and compares:
        out["compareSymbols"] = {k: str(v) for k, v in compares.items()}
    if indicators_out:
        out["indicators"] = indicators_out
    return {k: v for k, v in out.items() if v is not None}


def _emit_tvchart(
    ctx: HandlerContext,
    event_type: str,
    payload: dict[str, Any],
    *,
    extras: dict[str, Any] | None = None,
) -> HandlerResult:
    """Shared helper: resolve widget, emit event, return a uniform result."""
    widget_id = ctx.args.get("widget_id")
    resolved_id, error = _resolve_widget_id(widget_id)
    if error is not None or resolved_id is None:
        return error or {"error": "widget_id could not be resolved."}
    widget = get_widget(resolved_id)
    if not widget:
        ids = list_widget_ids()
        return {
            "error": (
                f"Widget not found: {resolved_id}."
                + (
                    f" Registered widgets: {', '.join(ids)}."
                    if ids
                    else " No widgets are registered yet."
                )
            ),
        }
    chart_id = ctx.args.get("chart_id")
    merged = {k: v for k, v in (payload or {}).items() if v is not None}
    if chart_id is not None:
        merged["chartId"] = chart_id
    widget.emit(event_type, merged)
    result: HandlerResult = {
        "widget_id": resolved_id,
        "event_sent": True,
        "event_type": event_type,
    }
    if extras:
        result.update(extras)
    return result


def _handle_tvchart_update_series(ctx: HandlerContext) -> HandlerResult:
    return _emit_tvchart(
        ctx,
        "tvchart:update",
        {
            "bars": ctx.args.get("bars"),
            "volume": ctx.args.get("volume"),
            "seriesId": ctx.args.get("series_id"),
            "fitContent": ctx.args.get("fit_content", True),
        },
    )


def _handle_tvchart_update_bar(ctx: HandlerContext) -> HandlerResult:
    return _emit_tvchart(
        ctx,
        "tvchart:stream",
        {
            "bar": ctx.args.get("bar"),
            "seriesId": ctx.args.get("series_id"),
        },
    )


def _handle_tvchart_add_series(ctx: HandlerContext) -> HandlerResult:
    series_id = ctx.args["series_id"]
    return _emit_tvchart(
        ctx,
        "tvchart:add-series",
        {
            "seriesId": series_id,
            "bars": ctx.args.get("bars"),
            "seriesType": ctx.args.get("series_type", "Line"),
            "seriesOptions": ctx.args.get("series_options") or {},
        },
        extras={"series_id": series_id},
    )


def _handle_tvchart_remove_series(ctx: HandlerContext) -> HandlerResult:
    series_id = ctx.args["series_id"]
    return _emit_tvchart(
        ctx,
        "tvchart:remove-series",
        {"seriesId": series_id},
        extras={"series_id": series_id},
    )


def _handle_tvchart_add_markers(ctx: HandlerContext) -> HandlerResult:
    return _emit_tvchart(
        ctx,
        "tvchart:add-markers",
        {
            "markers": ctx.args.get("markers"),
            "seriesId": ctx.args.get("series_id"),
        },
    )


def _handle_tvchart_add_price_line(ctx: HandlerContext) -> HandlerResult:
    return _emit_tvchart(
        ctx,
        "tvchart:add-price-line",
        {
            "price": ctx.args.get("price"),
            "color": ctx.args.get("color", "#2196F3"),
            "lineWidth": ctx.args.get("line_width", 1),
            "title": ctx.args.get("title", ""),
            "seriesId": ctx.args.get("series_id"),
        },
    )


def _handle_tvchart_apply_options(ctx: HandlerContext) -> HandlerResult:
    return _emit_tvchart(
        ctx,
        "tvchart:apply-options",
        {
            "chartOptions": ctx.args.get("chart_options"),
            "seriesOptions": ctx.args.get("series_options"),
            "seriesId": ctx.args.get("series_id"),
        },
    )


def _handle_tvchart_add_indicator(ctx: HandlerContext) -> HandlerResult:
    return _emit_tvchart(
        ctx,
        "tvchart:add-indicator",
        {
            "name": ctx.args.get("name"),
            "period": ctx.args.get("period"),
            "color": ctx.args.get("color"),
            "source": ctx.args.get("source"),
            "method": ctx.args.get("method"),
            "multiplier": ctx.args.get("multiplier"),
            "maType": ctx.args.get("ma_type"),
            "offset": ctx.args.get("offset"),
        },
    )


def _handle_tvchart_remove_indicator(ctx: HandlerContext) -> HandlerResult:
    series_id = ctx.args["series_id"]
    return _emit_tvchart(
        ctx,
        "tvchart:remove-indicator",
        {"seriesId": series_id},
        extras={"series_id": series_id},
    )


def _handle_tvchart_list_indicators(ctx: HandlerContext) -> HandlerResult:
    widget_id = ctx.args.get("widget_id")
    widget, error = _get_widget_or_error(widget_id)
    if error is not None or widget is None:
        return error or {"error": "widget_id could not be resolved."}
    payload: dict[str, Any] = {}
    chart_id = ctx.args.get("chart_id")
    if chart_id is not None:
        payload["chartId"] = chart_id
    response = request_response(
        widget,
        "tvchart:list-indicators",
        "tvchart:list-indicators-response",
        payload,
        timeout=float(ctx.args.get("timeout", 5.0)),
    )
    if response is None:
        return {"widget_id": widget_id, "error": "Indicator listing timed out"}
    return {
        "widget_id": widget_id,
        "indicators": response.get("indicators", []),
        "chartId": response.get("chartId"),
    }


def _handle_tvchart_show_indicators(ctx: HandlerContext) -> HandlerResult:
    return _emit_tvchart(ctx, "tvchart:show-indicators", {})


def _handle_tvchart_symbol_search(ctx: HandlerContext) -> HandlerResult:
    widget_id = ctx.args.get("widget_id")
    resolved_id, error = _resolve_widget_id(widget_id)
    if error is not None or resolved_id is None:
        return error or {"error": "widget_id could not be resolved."}
    widget = get_widget(resolved_id)
    if not widget:
        return {"error": f"Widget not found: {resolved_id}."}

    query = ctx.args.get("query")
    auto_select = ctx.args.get("auto_select", True)
    payload: dict[str, Any] = {"query": query, "autoSelect": auto_select}
    chart_id = ctx.args.get("chart_id")
    if chart_id is not None:
        payload["chartId"] = chart_id
    symbol_type = ctx.args.get("symbol_type")
    if symbol_type:
        payload["symbolType"] = symbol_type
    exchange = ctx.args.get("exchange")
    if exchange:
        payload["exchange"] = exchange
    # Capture the pre-emit symbol so we can tell whether the chart
    # changed at all — even a fuzzy search ("microsoft" -> "MSFT") is a
    # successful change, not a failure, and the note below must reflect
    # that rather than complaining the literal query wasn't found.  Only
    # worth fetching when we're actually going to auto-commit a query.
    will_confirm = bool(query) and bool(auto_select)
    pre_symbol = ""
    if will_confirm:
        pre_state = _fetch_tvchart_state(widget, timeout=0.6) or {}
        pre_symbol = str(pre_state.get("symbol") or "").upper()
    payload = {k: v for k, v in payload.items() if v is not None}
    widget.emit("tvchart:symbol-search", payload)

    result: HandlerResult = {
        "widget_id": resolved_id,
        "event_sent": True,
        "event_type": "tvchart:symbol-search",
    }
    if not will_confirm:
        # Just opened the dialog for the user — no mutation to confirm.
        return result

    target = str(query).upper()
    target_bare = target.rsplit(":", maxsplit=1)[-1].strip() if ":" in target else target

    def _matches(state: dict[str, Any]) -> bool:
        current = str(state.get("symbol") or "").upper()
        if not current:
            return False
        # Exact / bare-ticker match — or any change away from the
        # pre-emit symbol.  The latter covers fuzzy searches like
        # "microsoft" -> "MSFT" where the query is a company name
        # rather than a ticker; the chart still genuinely committed
        # the user's intent and the tool result should reflect that.
        if current in (target, target_bare):
            return True
        return bool(pre_symbol) and current != pre_symbol

    # Block until the frontend emits tvchart:data-settled for the main
    # series — that fires AFTER the destroy-recreate and all post-
    # mutation work (legend refresh, indicator re-add) has completed.
    state = _wait_for_data_settled(widget, _matches)
    if state is not None:
        result["confirmed"] = True
        # Identity fields only — no bars/raw data (the agent would
        # paraphrase them into fabricated "last close: $..." text).
        result.update(_minimal_confirm_state(state))
    else:
        result["confirmed"] = False
        result["reason"] = (
            f"Search for '{query}' did not land on the chart within the "
            "timeout.  No matching symbol was found or the chart is still "
            "loading data."
        )
    return result


def _build_compare_payload(ctx: HandlerContext) -> dict[str, Any]:
    """Assemble the ``tvchart:compare`` event payload from handler args."""
    payload: dict[str, Any] = {}
    query = ctx.args.get("query")
    if query:
        payload["query"] = query
        payload["autoAdd"] = ctx.args.get("auto_add", True)
    for src, dst in (
        ("chart_id", "chartId"),
        ("symbol_type", "symbolType"),
        ("exchange", "exchange"),
    ):
        value = ctx.args.get(src)
        if value is not None and value != "":
            payload[dst] = value
    return payload


def _snapshot_compare_set(widget: Any) -> set[str]:
    """Return the upper-cased tickers currently in ``state.compareSymbols``."""
    state = _fetch_tvchart_state(widget, timeout=0.6) or {}
    compares = state.get("compareSymbols") or {}
    if not isinstance(compares, dict):
        return set()
    return {str(s).upper() for s in compares.values()}


def _handle_tvchart_compare(ctx: HandlerContext) -> HandlerResult:
    widget_id = ctx.args.get("widget_id")
    resolved_id, error = _resolve_widget_id(widget_id)
    if error is not None or resolved_id is None:
        return error or {"error": "widget_id could not be resolved."}
    widget = get_widget(resolved_id)
    if not widget:
        return {"error": f"Widget not found: {resolved_id}."}

    payload = _build_compare_payload(ctx)
    query = ctx.args.get("query")
    auto_add = ctx.args.get("auto_add", True)

    # Snapshot existing compares so fuzzy adds ("microsoft" → "MSFT")
    # register as success.  Only needed when we're actually going to
    # confirm a mutation.
    will_confirm = bool(query) and bool(auto_add)
    pre_compare_set = _snapshot_compare_set(widget) if will_confirm else set()

    widget.emit("tvchart:compare", payload)

    result: HandlerResult = {
        "widget_id": resolved_id,
        "event_sent": True,
        "event_type": "tvchart:compare",
    }
    if not will_confirm:
        # Just opened the dialog for the user — no mutation to confirm.
        return result

    target = str(query).upper()
    target_bare = target.rsplit(":", maxsplit=1)[-1].strip() if ":" in target else target

    accepted_tickers = {target, target_bare}

    def _matches(state: dict[str, Any]) -> bool:
        compares = state.get("compareSymbols") or {}
        if not isinstance(compares, dict):
            return False
        current_set = {str(s).upper() for s in compares.values()}
        # Exact or bare-ticker match on the newly-added compare.
        if any(sym in accepted_tickers for sym in current_set):
            return True
        # Fuzzy match: any new compare that wasn't there before counts
        # — "microsoft" committing as "MSFT" is still success.
        return bool(current_set - pre_compare_set)

    # Block until the frontend emits tvchart:data-settled with the new
    # compare in state — that fires AFTER the compare series is added
    # and all post-mutation work has completed.  Compare chains search
    # → resolve → data-request → response → series add, so give it a
    # generous window.
    state = _wait_for_data_settled(widget, _matches, timeout=12.0)
    if state is not None:
        result["confirmed"] = True
        result.update(_minimal_confirm_state(state))
    else:
        result["confirmed"] = False
        result["reason"] = (
            f"Compare symbol '{target}' did not land on the chart within the "
            "timeout.  No matching symbol was found or data is still loading."
        )
    return result


def _handle_tvchart_change_interval(ctx: HandlerContext) -> HandlerResult:
    widget_id = ctx.args.get("widget_id")
    resolved_id, error = _resolve_widget_id(widget_id)
    if error is not None or resolved_id is None:
        return error or {"error": "widget_id could not be resolved."}
    widget = get_widget(resolved_id)
    if not widget:
        return {"error": f"Widget not found: {resolved_id}."}

    value = ctx.args.get("value")
    payload: dict[str, Any] = {"value": value}
    chart_id = ctx.args.get("chart_id")
    if chart_id is not None:
        payload["chartId"] = chart_id
    payload = {k: v for k, v in payload.items() if v is not None}
    widget.emit("tvchart:interval-change", payload)

    result: HandlerResult = {
        "widget_id": resolved_id,
        "event_sent": True,
        "event_type": "tvchart:interval-change",
    }
    if not value:
        return result

    target = str(value).strip()

    def _matches(state: dict[str, Any]) -> bool:
        current = str(state.get("interval") or "").strip()
        if not current:
            return False

        # Frontend may report "1D" where caller asked "D"; normalise both
        # to a canonical comparison (strip leading "1" for a lone digit).
        def _norm(s: str) -> str:
            s = s.upper()
            return s[1:] if s.startswith("1") and len(s) > 1 else s

        return _norm(current) == _norm(target)

    # Block until the frontend emits tvchart:data-settled reflecting
    # the new interval — that fires AFTER the destroy-recreate and all
    # post-mutation work has completed.
    state = _wait_for_data_settled(widget, _matches)
    if state is not None:
        result["confirmed"] = True
        result.update(_minimal_confirm_state(state))
    else:
        result["confirmed"] = False
        result["reason"] = f"Interval did not change to '{target}' within the timeout."
    return result


def _handle_tvchart_set_visible_range(ctx: HandlerContext) -> HandlerResult:
    return _emit_zoom_and_confirm(
        ctx,
        "tvchart:time-scale",
        {
            "visibleRange": {
                "from": ctx.args.get("from_time"),
                "to": ctx.args.get("to_time"),
            },
        },
    )


def _handle_tvchart_fit_content(ctx: HandlerContext) -> HandlerResult:
    return _emit_zoom_and_confirm(ctx, "tvchart:time-scale", {"fitContent": True})


def _handle_tvchart_time_range(ctx: HandlerContext) -> HandlerResult:
    return _emit_zoom_and_confirm(
        ctx,
        "tvchart:time-range",
        {"value": ctx.args.get("value")},
    )


def _emit_zoom_and_confirm(
    ctx: HandlerContext,
    event_type: str,
    payload: dict[str, Any],
) -> HandlerResult:
    """Emit a zoom/range mutation and wait for the frontend's confirmation.

    The frontend emits ``tvchart:data-settled`` synchronously after
    applying the timeScale/range call — that's the
    confirm-operation-complete signal.

    No state polling: register the listener, emit the event, block on
    ``threading.Event`` until the settled event fires (or timeout),
    return the payload the frontend sent.  If the event never fires
    (frontend dropped it because the value was invalid, the chart was
    mid-rebuild, etc.), we report ``confirmed: false`` rather than
    silently claiming success.
    """
    widget_id = ctx.args.get("widget_id")
    resolved_id, error = _resolve_widget_id(widget_id)
    if error is not None or resolved_id is None:
        return error or {"error": "widget_id could not be resolved."}
    widget = get_widget(resolved_id)
    if not widget:
        return {"error": f"Widget not found: {resolved_id}."}

    merged = {k: v for k, v in payload.items() if v is not None}
    chart_id = ctx.args.get("chart_id")
    if chart_id is not None:
        merged["chartId"] = chart_id
    widget.emit(event_type, merged)

    # Accept any settled event — the frontend emits one
    # synchronously right after applying the zoom/range, so the
    # first event on the bus IS the confirmation for this mutation.
    state = _wait_for_data_settled(widget, lambda _s: True, timeout=4.0)
    result: HandlerResult = {
        "widget_id": resolved_id,
        "event_sent": True,
        "event_type": event_type,
    }
    if state is not None:
        result["confirmed"] = True
        result.update(_minimal_confirm_state(state))
        new_range = state.get("visibleRange") or state.get("visibleLogicalRange")
        if new_range:
            result["visibleRange"] = new_range
    else:
        result["confirmed"] = False
        result["reason"] = (
            "Zoom/range change did not land on the chart within the "
            "timeout — verify the ``value`` argument matches one of "
            "the accepted presets (1D, 1W, 1M, 3M, 6M, 1Y, 5Y, YTD)."
        )
    return result


def _handle_tvchart_time_range_picker(ctx: HandlerContext) -> HandlerResult:
    return _emit_tvchart(ctx, "tvchart:time-range-picker", {})


def _handle_tvchart_log_scale(ctx: HandlerContext) -> HandlerResult:
    return _emit_tvchart(
        ctx,
        "tvchart:log-scale",
        {"value": bool(ctx.args.get("value"))},
    )


def _handle_tvchart_auto_scale(ctx: HandlerContext) -> HandlerResult:
    return _emit_tvchart(
        ctx,
        "tvchart:auto-scale",
        {"value": bool(ctx.args.get("value"))},
    )


def _handle_tvchart_chart_type(ctx: HandlerContext) -> HandlerResult:
    return _emit_tvchart(
        ctx,
        "tvchart:chart-type-change",
        {
            "value": ctx.args.get("value"),
            "seriesId": ctx.args.get("series_id"),
        },
    )


def _handle_tvchart_drawing_tool(ctx: HandlerContext) -> HandlerResult:
    mode = str(ctx.args.get("mode", "")).lower()
    event_map = {
        "cursor": "tvchart:tool-cursor",
        "crosshair": "tvchart:tool-crosshair",
        "magnet": "tvchart:tool-magnet",
        "eraser": "tvchart:tool-eraser",
        "visibility": "tvchart:tool-visibility",
        "lock": "tvchart:tool-lock",
    }
    event_type = event_map.get(mode)
    if event_type is None:
        return {"error": f"Unknown drawing tool mode: {mode}"}
    return _emit_tvchart(ctx, event_type, {})


def _handle_tvchart_undo(ctx: HandlerContext) -> HandlerResult:
    return _emit_tvchart(ctx, "tvchart:undo", {})


def _handle_tvchart_redo(ctx: HandlerContext) -> HandlerResult:
    return _emit_tvchart(ctx, "tvchart:redo", {})


def _handle_tvchart_show_settings(ctx: HandlerContext) -> HandlerResult:
    return _emit_tvchart(ctx, "tvchart:show-settings", {})


def _handle_tvchart_toggle_dark_mode(ctx: HandlerContext) -> HandlerResult:
    return _emit_tvchart(
        ctx,
        "tvchart:toggle-dark-mode",
        {"value": bool(ctx.args.get("value"))},
    )


def _handle_tvchart_screenshot(ctx: HandlerContext) -> HandlerResult:
    return _emit_tvchart(ctx, "tvchart:screenshot", {})


def _handle_tvchart_fullscreen(ctx: HandlerContext) -> HandlerResult:
    return _emit_tvchart(ctx, "tvchart:fullscreen", {})


def _handle_tvchart_save_layout(ctx: HandlerContext) -> HandlerResult:
    return _emit_tvchart(
        ctx,
        "tvchart:save-layout",
        {"name": ctx.args.get("name")},
    )


def _handle_tvchart_open_layout(ctx: HandlerContext) -> HandlerResult:
    return _emit_tvchart(ctx, "tvchart:open-layout", {})


def _handle_tvchart_save_state(ctx: HandlerContext) -> HandlerResult:
    widget_id = ctx.args.get("widget_id")
    widget, error = _get_widget_or_error(widget_id)
    if error is not None or widget is None:
        return error or {"error": "widget_id could not be resolved."}
    widget.emit("tvchart:save-state", {})
    return {"widget_id": widget_id, "event_sent": True, "event_type": "tvchart:save-state"}


def _handle_tvchart_request_state(ctx: HandlerContext) -> HandlerResult:
    widget_id = ctx.args.get("widget_id")
    widget, error = _get_widget_or_error(widget_id)
    if error is not None or widget is None:
        return error or {"error": "widget_id could not be resolved."}
    payload: dict[str, Any] = {}
    chart_id = ctx.args.get("chart_id")
    if chart_id is not None:
        payload["chartId"] = chart_id
    response = request_response(
        widget,
        "tvchart:request-state",
        "tvchart:state-response",
        payload,
        timeout=float(ctx.args.get("timeout", 5.0)),
    )
    if response is None:
        return {"widget_id": widget_id, "error": "State request timed out"}
    # Strip the correlation token before returning.
    response.pop("context", None)
    return {"widget_id": widget_id, "state": response}


def _handle_set_content(ctx: HandlerContext) -> HandlerResult:
    widget_id = ctx.args.get("widget_id")
    widget, error = _get_widget_or_error(widget_id)
    if error is not None or widget is None:
        return error or {"error": "widget_id could not be resolved."}

    data = {"id": ctx.args["component_id"]}
    if "html" in ctx.args:
        data["html"] = ctx.args["html"]
    else:
        data["text"] = ctx.args.get("text", "")

    widget.emit("pywry:set-content", data)
    return {"widget_id": widget_id, "updated": True}


def _handle_set_style(ctx: HandlerContext) -> HandlerResult:
    widget_id = ctx.args.get("widget_id")
    widget, error = _get_widget_or_error(widget_id)
    if error is not None or widget is None:
        return error or {"error": "widget_id could not be resolved."}

    widget.emit(
        "pywry:set-style",
        {"id": ctx.args["component_id"], "styles": ctx.args["styles"]},
    )
    return {"widget_id": widget_id, "updated": True}


def _handle_show_toast(ctx: HandlerContext) -> HandlerResult:
    widget_id = ctx.args.get("widget_id")
    widget, error = _get_widget_or_error(widget_id)
    if error is not None or widget is None:
        return error or {"error": "widget_id could not be resolved."}

    widget.emit(
        "pywry:alert",
        {
            "message": ctx.args["message"],
            "type": ctx.args.get("type", "info"),
            "duration": ctx.args.get("duration", 3000),
        },
    )
    return {"widget_id": widget_id, "toast_shown": True}


def _handle_update_theme(ctx: HandlerContext) -> HandlerResult:
    widget_id = ctx.args.get("widget_id")
    widget, error = _get_widget_or_error(widget_id)
    if error is not None or widget is None:
        return error or {"error": "widget_id could not be resolved."}

    widget.emit("pywry:update-theme", {"theme": ctx.args["theme"]})
    return {"widget_id": widget_id, "theme": ctx.args["theme"]}


def _handle_inject_css(ctx: HandlerContext) -> HandlerResult:
    widget_id = ctx.args.get("widget_id")
    widget, error = _get_widget_or_error(widget_id)
    if error is not None or widget is None:
        return error or {"error": "widget_id could not be resolved."}

    widget.emit(
        "pywry:inject-css",
        {
            "css": ctx.args["css"],
            "id": ctx.args.get("style_id", "pywry-injected-style"),
        },
    )
    return {"widget_id": widget_id, "css_injected": True}


def _handle_remove_css(ctx: HandlerContext) -> HandlerResult:
    widget_id = ctx.args.get("widget_id")
    widget, error = _get_widget_or_error(widget_id)
    if error is not None or widget is None:
        return error or {"error": "widget_id could not be resolved."}

    widget.emit("pywry:remove-css", {"id": ctx.args["style_id"]})
    return {"widget_id": widget_id, "css_removed": True}


def _handle_navigate(ctx: HandlerContext) -> HandlerResult:
    widget_id = ctx.args.get("widget_id")
    widget, error = _get_widget_or_error(widget_id)
    if error is not None or widget is None:
        return error or {"error": "widget_id could not be resolved."}

    widget.emit("pywry:navigate", {"url": ctx.args["url"]})
    return {"widget_id": widget_id, "navigating_to": ctx.args["url"]}


def _handle_download(ctx: HandlerContext) -> HandlerResult:
    widget_id = ctx.args.get("widget_id")
    widget, error = _get_widget_or_error(widget_id)
    if error is not None or widget is None:
        return error or {"error": "widget_id could not be resolved."}

    widget.emit(
        "pywry:download",
        {
            "content": ctx.args["content"],
            "filename": ctx.args["filename"],
            "mimeType": ctx.args.get("mime_type", "application/octet-stream"),
        },
    )
    return {"widget_id": widget_id, "download_triggered": ctx.args["filename"]}


def _handle_update_plotly(ctx: HandlerContext) -> HandlerResult:
    widget_id = ctx.args.get("widget_id")
    widget, error = _get_widget_or_error(widget_id)
    if error is not None or widget is None:
        return error or {"error": "widget_id could not be resolved."}

    fig_dict = json.loads(ctx.args["figure_json"])

    if ctx.args.get("layout_only", False):
        widget.emit("plotly:update-layout", {"layout": fig_dict.get("layout", {})})
    else:
        widget.emit(
            "plotly:update-figure",
            {
                "data": fig_dict.get("data", []),
                "layout": fig_dict.get("layout", {}),
            },
        )
    return {"widget_id": widget_id, "plotly_updated": True}


def _handle_update_marquee(ctx: HandlerContext) -> HandlerResult:
    widget_id = ctx.args.get("widget_id")
    widget, error = _get_widget_or_error(widget_id)
    if error is not None or widget is None:
        return error or {"error": "widget_id could not be resolved."}

    ticker_update = ctx.args.get("ticker_update")
    if ticker_update:
        widget.emit("toolbar:marquee-set-item", ticker_update)
        return {
            "widget_id": widget_id,
            "ticker_updated": ticker_update.get("ticker"),
        }

    marquee_data: dict[str, Any] = {"id": ctx.args["component_id"]}
    for key in ("text", "html", "speed", "paused"):
        if key in ctx.args:
            marquee_data[key] = ctx.args[key]

    widget.emit("toolbar:marquee-set-content", marquee_data)
    return {"widget_id": widget_id, "marquee_updated": True}


def _handle_update_ticker_item(ctx: HandlerContext) -> HandlerResult:
    from ..toolbar import TickerItem

    widget_id = ctx.args.get("widget_id")
    widget, error = _get_widget_or_error(widget_id)
    if error is not None or widget is None:
        return error or {"error": "widget_id could not be resolved."}

    ticker_item = TickerItem(ticker=ctx.args["ticker"])
    event_type, payload = ticker_item.update_payload(
        text=ctx.args.get("text"),
        html_content=ctx.args.get("html"),
        styles=ctx.args.get("styles"),
        class_add=ctx.args.get("class_add"),
        class_remove=ctx.args.get("class_remove"),
    )

    widget.emit(event_type, payload)
    return {
        "widget_id": widget_id,
        "ticker": ctx.args["ticker"],
        "event": event_type,
        "payload": payload,
    }


def _handle_send_event(ctx: HandlerContext) -> HandlerResult:
    event_type = ctx.args.get("event_type")
    if not event_type:
        return {"error": "event_type is required (e.g. 'tvchart:symbol-search')."}
    widget_id = ctx.args.get("widget_id")
    resolved_id, error = _resolve_widget_id(widget_id)
    if error is not None or resolved_id is None:
        return error or {"error": "widget_id could not be resolved."}
    widget = get_widget(resolved_id)
    if not widget:
        ids = list_widget_ids()
        return {
            "error": (
                f"Widget not found: {resolved_id}."
                + (
                    f" Registered widgets: {', '.join(ids)}."
                    if ids
                    else " No widgets are registered yet."
                )
            ),
        }
    widget.emit(event_type, ctx.args.get("data") or {})
    return {
        "widget_id": resolved_id,
        "event_sent": True,
        "event_type": event_type,
    }


# =============================================================================
# Widget Management Handlers
# =============================================================================
def _handle_list_widgets(ctx: HandlerContext) -> HandlerResult:
    if ctx.headless:
        from ..inline import _state as inline_state

        widgets = [{"widget_id": wid, "path": f"/widget/{wid}"} for wid in inline_state.widgets]
    else:
        widgets = [{"widget_id": wid, "path": f"/widget/{wid}"} for wid in list_widget_ids()]
    return {"widgets": widgets, "count": len(widgets)}


def _handle_get_events(ctx: HandlerContext) -> HandlerResult:
    resolved_id, error = _resolve_widget_id(ctx.args.get("widget_id"))
    if error is not None or resolved_id is None:
        return error or {"error": "widget_id could not be resolved."}
    widget_events = ctx.events.get(resolved_id, [])
    if ctx.args.get("clear", False):
        ctx.events[resolved_id] = []
    return {"widget_id": resolved_id, "events": widget_events}


def _handle_destroy_widget(ctx: HandlerContext) -> HandlerResult:
    resolved_id, error = _resolve_widget_id(ctx.args.get("widget_id"))
    if error is not None or resolved_id is None:
        return error or {"error": "widget_id could not be resolved."}
    ctx.events.pop(resolved_id, None)
    remove_widget(resolved_id)
    if ctx.headless:
        from ..inline import _state as inline_state

        inline_state.widgets.pop(resolved_id, None)
    return {"widget_id": resolved_id, "destroyed": True}


# =============================================================================
# Resources / Export Handlers
# =============================================================================
def _handle_get_component_docs(ctx: HandlerContext) -> HandlerResult:
    comp_name = ctx.args["component"]
    doc = COMPONENT_DOCS.get(comp_name)
    if not doc:
        return {"error": f"Unknown component: {comp_name}"}
    return {
        "component": comp_name,
        "name": doc["name"],
        "description": doc["description"],
        "properties": doc.get("properties", {}),
        "example": doc.get("example", ""),
    }


def _handle_get_component_source(ctx: HandlerContext) -> HandlerResult:
    comp_name = ctx.args["component"]
    source = get_component_source(comp_name)
    if not source:
        return {"error": f"Source not found for: {comp_name}"}
    return {"component": comp_name, "source": source, "language": "python"}


def _handle_export_widget(ctx: HandlerContext) -> HandlerResult:
    resolved_id, error = _resolve_widget_id(ctx.args.get("widget_id"))
    if error is not None or resolved_id is None:
        return error or {"error": "widget_id could not be resolved."}
    widget_id = resolved_id
    code = export_widget_code(widget_id)
    if not code:
        return {"error": f"Widget not found or no config stored: {widget_id}"}
    return {
        "widget_id": widget_id,
        "code": code,
        "language": "python",
        "note": "Save this code to a .py file to recreate the widget without MCP",
    }


def _handle_get_widget_app(ctx: HandlerContext) -> HandlerResult:
    from .app_artifact import attach_app_artifact

    resolved_id, error = _resolve_widget_id(ctx.args.get("widget_id"))
    if error is not None or resolved_id is None:
        return error or {"error": "widget_id could not be resolved."}
    widget_id = resolved_id

    result: HandlerResult = {"widget_id": widget_id}
    result = attach_app_artifact(
        result,
        widget_id,
        title=ctx.args.get("title", "") or "",
        height=ctx.args.get("height", "600px") or "600px",
    )
    if "_app_artifact" not in result:
        return {
            "error": (
                f"Widget HTML not available for {widget_id} — "
                "is the widget running in a mode (headless/browser) that "
                "stores its HTML?"
            )
        }
    result["revision"] = result["_app_artifact"]["revision"]
    return result


def _handle_list_resources(_ctx: HandlerContext) -> HandlerResult:
    resources = get_resources()
    return {
        "resources": [
            {"uri": str(r.uri), "name": r.name, "description": r.description} for r in resources
        ],
        "templates": [
            {
                "uri_template": t.uriTemplate,
                "name": t.name,
                "description": t.description,
            }
            for t in get_resource_templates()
        ],
    }


# =============================================================================
# Chat Handlers
# =============================================================================

# Active generation handles: {widget_id: {thread_id: GenerationHandle}}
_active_generations: dict[str, dict[str, Any]] = {}

# Chat configs: {widget_id: ChatWidgetConfig}
_chat_configs: dict[str, Any] = {}

# Chat threads: {widget_id: {thread_id: ChatThread}}
_chat_thread_store: dict[str, dict[str, Any]] = {}

# Chat message history: {widget_id: {thread_id: [messages]}}
_chat_message_store: dict[str, dict[str, list[dict[str, Any]]]] = {}


def _handle_create_chat_widget(ctx: HandlerContext) -> HandlerResult:
    from ..chat import ChatThread, build_chat_html
    from .builders import build_chat_widget_config, build_toolbars as _build_toolbars

    app = get_app()
    args = ctx.args

    widget_config = build_chat_widget_config(args)
    _chat_configs[args.get("widget_id", "")] = widget_config

    chat_html = build_chat_html(
        show_sidebar=widget_config.show_sidebar,
        show_settings=widget_config.show_settings,
    )

    # Build optional surrounding toolbars
    toolbars_data = args.get("toolbars", [])
    toolbars = _build_toolbars(toolbars_data) if toolbars_data else None

    widget = app.show(
        chat_html,
        title=widget_config.title,
        height=widget_config.height,
        toolbars=toolbars,
    )

    widget_id = getattr(widget, "widget_id", None) or uuid.uuid4().hex
    callback = ctx.make_callback(widget_id)
    ctx.events[widget_id] = []

    register_widget(widget_id, widget)
    _chat_configs[widget_id] = widget_config

    # Create default thread
    thread_id = "thread_" + uuid.uuid4().hex[:8]
    default_thread = ChatThread(thread_id=thread_id, title="New Chat")
    _chat_thread_store.setdefault(widget_id, {})[thread_id] = default_thread
    _chat_message_store.setdefault(widget_id, {})[thread_id] = []

    # Register default slash command
    widget.emit(
        "chat:register-command",
        {"name": "/clear", "description": "Clear the conversation"},
    )

    # Register custom slash commands
    if widget_config.chat_config.slash_commands:
        for cmd in widget_config.chat_config.slash_commands:
            widget.emit(
                "chat:register-command",
                {
                    "name": cmd.name,
                    "description": cmd.description,
                },
            )

    # Push initial settings
    widget.emit(
        "chat:update-settings",
        {
            "model": widget_config.chat_config.model,
            "temperature": widget_config.chat_config.temperature,
            "system_prompt": widget_config.chat_config.system_prompt,
        },
    )

    # Push initial thread list
    widget.emit(
        "chat:update-thread-list",
        {
            "threads": [{"thread_id": thread_id, "title": "New Chat"}],
        },
    )
    widget.emit("chat:switch-thread", {"threadId": thread_id})

    # Register chat event callbacks
    widget.on("chat:user-message", callback)
    widget.on("chat:slash-command", callback)
    widget.on("chat:thread-create", callback)
    widget.on("chat:thread-switch", callback)
    widget.on("chat:thread-delete", callback)
    widget.on("chat:settings-change", callback)
    widget.on("chat:request-history", callback)
    widget.on("chat:stop-generation", callback)
    widget.on("chat:request-state", callback)

    if ctx.headless:
        from ..inline import _state as inline_state
        from .app_artifact import attach_app_artifact

        if widget_id in inline_state.widgets:
            inline_state.widgets[widget_id]["persistent"] = True

        result: HandlerResult = {
            "widget_id": widget_id,
            "thread_id": thread_id,
            "path": f"/widget/{widget_id}",
            "created": True,
        }
        return attach_app_artifact(
            result, widget_id, title=widget_config.title
        )

    return {
        "widget_id": widget_id,
        "thread_id": thread_id,
        "mode": "native",
        "message": "Chat window opened",
        "created": True,
    }


def _handle_chat_send_message(ctx: HandlerContext) -> HandlerResult:
    resolved_id, error = _resolve_widget_id(ctx.args.get("widget_id"))
    if error is not None or resolved_id is None:
        return error or {"error": "widget_id could not be resolved."}
    widget, werror = _get_widget_or_error(resolved_id)
    if werror is not None or widget is None:
        return werror or {"error": f"Widget not found: {resolved_id}."}
    widget_id = resolved_id

    text = ctx.args["text"]
    thread_id = ctx.args.get("thread_id")
    config = _chat_configs.get(widget_id)
    if not config:
        return {"error": f"No chat config for widget {widget_id}"}

    message_id = "msg_" + uuid.uuid4().hex[:8]

    # Emit the user message to frontend
    widget.emit(
        "chat:assistant-message",
        {
            "messageId": message_id,
            "text": f"Received: {text}",
            "threadId": thread_id,
        },
    )

    # Store message in history
    if thread_id:
        store = _chat_message_store.setdefault(widget_id, {})
        store.setdefault(thread_id, []).append(
            {
                "message_id": message_id,
                "role": "user",
                "text": text,
            }
        )

    return {
        "widget_id": widget_id,
        "message_id": message_id,
        "thread_id": thread_id,
        "sent": True,
    }


def _handle_chat_stop_generation(ctx: HandlerContext) -> HandlerResult:
    resolved_id, error = _resolve_widget_id(ctx.args.get("widget_id"))
    if error is not None or resolved_id is None:
        return error or {"error": "widget_id could not be resolved."}
    widget_id = resolved_id
    thread_id = ctx.args.get("thread_id")

    widget_gens = _active_generations.get(widget_id, {})
    handle = widget_gens.get(thread_id) if thread_id else None

    if handle and not handle.cancel_event.is_set():
        handle.cancel()
        partial = handle.partial_content

        widget, _ = _get_widget_or_error(widget_id)
        if widget:
            widget.emit(
                "chat:generation-stopped",
                {
                    "messageId": handle.message_id,
                    "threadId": thread_id,
                    "partialContent": partial,
                },
            )

        return {
            "widget_id": widget_id,
            "thread_id": thread_id,
            "message_id": handle.message_id,
            "stopped": True,
            "partial_content": partial,
        }

    return {
        "widget_id": widget_id,
        "thread_id": thread_id,
        "stopped": False,
        "message": "No active generation to stop",
    }


def _handle_chat_manage_thread(ctx: HandlerContext) -> HandlerResult:
    resolved_id, error = _resolve_widget_id(ctx.args.get("widget_id"))
    if error is not None or resolved_id is None:
        return error or {"error": "widget_id could not be resolved."}
    widget_id = resolved_id
    action = ctx.args["action"]
    thread_id = ctx.args.get("thread_id")
    title = ctx.args.get("title", "New Chat")

    widget, werror = _get_widget_or_error(widget_id)
    if werror is not None or widget is None:
        return werror or {"error": f"Widget not found: {widget_id}."}

    handlers = {
        "create": _thread_create,
        "switch": _thread_switch,
        "delete": _thread_delete,
        "rename": _thread_rename,
        "list": _thread_list,
    }
    handler = handlers.get(action)
    if handler is None:
        return {"error": f"Unknown thread action: {action}"}
    return handler(widget, widget_id, thread_id, title)


def _thread_create(
    widget: Any, widget_id: str, _thread_id: str | None, title: str
) -> HandlerResult:
    """Create a new chat thread."""
    from ..chat import ChatThread

    new_id = "thread_" + uuid.uuid4().hex[:8]
    new_thread = ChatThread(thread_id=new_id, title=title)
    _chat_thread_store.setdefault(widget_id, {})[new_id] = new_thread
    _chat_message_store.setdefault(widget_id, {})[new_id] = []
    widget.emit(
        "chat:update-thread-list",
        {
            "threads": [{"thread_id": new_id, "title": title}],
        },
    )
    widget.emit("chat:switch-thread", {"threadId": new_id})
    return {"widget_id": widget_id, "thread_id": new_id, "action": "create", "title": title}


def _thread_switch(
    widget: Any, widget_id: str, thread_id: str | None, _title: str
) -> HandlerResult:
    """Switch to an existing thread."""
    if not thread_id:
        return {"error": "thread_id required for switch"}
    widget.emit("chat:switch-thread", {"threadId": thread_id})
    return {"widget_id": widget_id, "thread_id": thread_id, "action": "switch"}


def _thread_delete(
    _widget: Any, widget_id: str, thread_id: str | None, _title: str
) -> HandlerResult:
    """Delete a thread."""
    if not thread_id:
        return {"error": "thread_id required for delete"}
    _chat_thread_store.get(widget_id, {}).pop(thread_id, None)
    _chat_message_store.get(widget_id, {}).pop(thread_id, None)
    return {"widget_id": widget_id, "thread_id": thread_id, "action": "delete", "deleted": True}


def _thread_rename(
    _widget: Any, widget_id: str, thread_id: str | None, title: str
) -> HandlerResult:
    """Rename a thread."""
    if not thread_id:
        return {"error": "thread_id required for rename"}
    thread_obj = _chat_thread_store.get(widget_id, {}).get(thread_id)
    if thread_obj and hasattr(thread_obj, "title"):
        thread_obj.title = title
    return {"widget_id": widget_id, "thread_id": thread_id, "action": "rename", "title": title}


def _thread_list(
    _widget: Any, widget_id: str, _thread_id: str | None, _title: str
) -> HandlerResult:
    """List all threads."""
    threads = [
        {"thread_id": tid, "title": getattr(t, "title", "Untitled")}
        for tid, t in _chat_thread_store.get(widget_id, {}).items()
    ]
    return {"widget_id": widget_id, "action": "list", "threads": threads}


def _handle_chat_register_command(ctx: HandlerContext) -> HandlerResult:
    widget_id = ctx.args.get("widget_id")
    name = ctx.args["name"]
    description = ctx.args.get("description", "")

    widget, error = _get_widget_or_error(widget_id)
    if error is not None or widget is None:
        return error or {"error": "widget_id could not be resolved."}

    if not name.startswith("/"):
        name = "/" + name

    widget.emit(
        "chat:register-command",
        {
            "name": name,
            "description": description,
        },
    )

    return {"widget_id": widget_id, "name": name, "description": description, "registered": True}


def _handle_chat_get_history(ctx: HandlerContext) -> HandlerResult:
    resolved_id, error = _resolve_widget_id(ctx.args.get("widget_id"))
    if error is not None or resolved_id is None:
        return error or {"error": "widget_id could not be resolved."}
    widget_id = resolved_id
    thread_id = ctx.args.get("thread_id")
    limit = ctx.args.get("limit", 50)
    before_id = ctx.args.get("before_id")

    all_messages = _chat_message_store.get(widget_id, {}).get(thread_id or "", [])

    # Filter: only messages before `before_id` if specified
    if before_id:
        filtered = []
        for msg in all_messages:
            if msg.get("message_id") == before_id:
                break
            filtered.append(msg)
        all_messages = filtered

    # Apply limit (take last N messages)
    messages = all_messages[-limit:] if limit else all_messages
    has_more = len(all_messages) > len(messages)

    return {
        "widget_id": widget_id,
        "thread_id": thread_id,
        "messages": messages,
        "has_more": has_more,
        "cursor": messages[0]["message_id"] if messages and has_more else None,
    }


def _handle_chat_update_settings(ctx: HandlerContext) -> HandlerResult:
    widget_id = ctx.args.get("widget_id")
    widget, error = _get_widget_or_error(widget_id)
    if error is not None or widget is None:
        return error or {"error": "widget_id could not be resolved."}

    settings: dict[str, Any] = {}
    for key in ("model", "temperature", "max_tokens", "system_prompt", "streaming"):
        if key in ctx.args:
            settings[key] = ctx.args[key]

    if settings:
        widget.emit("chat:update-settings", settings)

    return {"widget_id": widget_id, "settings": settings, "applied": True}


def _handle_chat_set_typing(ctx: HandlerContext) -> HandlerResult:
    widget_id = ctx.args.get("widget_id")
    widget, error = _get_widget_or_error(widget_id)
    if error is not None or widget is None:
        return error or {"error": "widget_id could not be resolved."}

    typing = ctx.args.get("typing", True)
    thread_id = ctx.args.get("thread_id")

    widget.emit("chat:typing-indicator", {"typing": typing, "threadId": thread_id})

    return {"widget_id": widget_id, "typing": typing, "thread_id": thread_id}


# =============================================================================
# Handler Dispatch Table
# =============================================================================
_HANDLERS: dict[str, Callable[[HandlerContext], HandlerResult]] = {
    # Skills
    "get_skills": _handle_get_skills,
    # Widget Creation
    "create_widget": _handle_create_widget,
    "build_div": _handle_build_div,
    "build_ticker_item": _handle_build_ticker_item,
    "show_plotly": _handle_show_plotly,
    "show_dataframe": _handle_show_dataframe,
    "show_tvchart": _handle_show_tvchart,
    # TVChart — first-class tools for every chart operation
    "tvchart_update_series": _handle_tvchart_update_series,
    "tvchart_update_bar": _handle_tvchart_update_bar,
    "tvchart_add_series": _handle_tvchart_add_series,
    "tvchart_remove_series": _handle_tvchart_remove_series,
    "tvchart_add_markers": _handle_tvchart_add_markers,
    "tvchart_add_price_line": _handle_tvchart_add_price_line,
    "tvchart_apply_options": _handle_tvchart_apply_options,
    "tvchart_add_indicator": _handle_tvchart_add_indicator,
    "tvchart_remove_indicator": _handle_tvchart_remove_indicator,
    "tvchart_list_indicators": _handle_tvchart_list_indicators,
    "tvchart_show_indicators": _handle_tvchart_show_indicators,
    "tvchart_symbol_search": _handle_tvchart_symbol_search,
    "tvchart_compare": _handle_tvchart_compare,
    "tvchart_change_interval": _handle_tvchart_change_interval,
    "tvchart_set_visible_range": _handle_tvchart_set_visible_range,
    "tvchart_fit_content": _handle_tvchart_fit_content,
    "tvchart_time_range": _handle_tvchart_time_range,
    "tvchart_time_range_picker": _handle_tvchart_time_range_picker,
    "tvchart_log_scale": _handle_tvchart_log_scale,
    "tvchart_auto_scale": _handle_tvchart_auto_scale,
    "tvchart_chart_type": _handle_tvchart_chart_type,
    "tvchart_drawing_tool": _handle_tvchart_drawing_tool,
    "tvchart_undo": _handle_tvchart_undo,
    "tvchart_redo": _handle_tvchart_redo,
    "tvchart_show_settings": _handle_tvchart_show_settings,
    "tvchart_toggle_dark_mode": _handle_tvchart_toggle_dark_mode,
    "tvchart_screenshot": _handle_tvchart_screenshot,
    "tvchart_fullscreen": _handle_tvchart_fullscreen,
    "tvchart_save_layout": _handle_tvchart_save_layout,
    "tvchart_open_layout": _handle_tvchart_open_layout,
    "tvchart_save_state": _handle_tvchart_save_state,
    "tvchart_request_state": _handle_tvchart_request_state,
    # Widget Manipulation
    "set_content": _handle_set_content,
    "set_style": _handle_set_style,
    "show_toast": _handle_show_toast,
    "update_theme": _handle_update_theme,
    "inject_css": _handle_inject_css,
    "remove_css": _handle_remove_css,
    "navigate": _handle_navigate,
    "download": _handle_download,
    "update_plotly": _handle_update_plotly,
    "update_marquee": _handle_update_marquee,
    "update_ticker_item": _handle_update_ticker_item,
    "send_event": _handle_send_event,
    # Widget Management
    "list_widgets": _handle_list_widgets,
    "get_events": _handle_get_events,
    "destroy_widget": _handle_destroy_widget,
    # Resources / Export
    "get_component_docs": _handle_get_component_docs,
    "get_component_source": _handle_get_component_source,
    "export_widget": _handle_export_widget,
    "get_widget_app": _handle_get_widget_app,
    "list_resources": _handle_list_resources,
    # Chat
    "create_chat_widget": _handle_create_chat_widget,
    "chat_send_message": _handle_chat_send_message,
    "chat_stop_generation": _handle_chat_stop_generation,
    "chat_manage_thread": _handle_chat_manage_thread,
    "chat_register_command": _handle_chat_register_command,
    "chat_get_history": _handle_chat_get_history,
    "chat_update_settings": _handle_chat_update_settings,
    "chat_set_typing": _handle_chat_set_typing,
}


# =============================================================================
# Main Entry Point
# =============================================================================
def _check_required_args(name: str, args: dict[str, Any]) -> str | None:
    """Return an error for any schema-required args the caller omitted.

    The per-tool ``inputSchema.required`` list is the canonical source.
    Without this gate a handler would silently emit an event with
    ``None`` values (e.g. ``tvchart_change_interval`` with no ``value``
    still fires ``tvchart:interval-change`` with an empty payload; the
    frontend drops it and the agent sees ``event_sent: true`` and
    assumes the chart changed).  ``widget_id`` is deliberately excluded
    here — ``_resolve_widget_id`` auto-fills it from the sole registered
    widget on single-widget servers.
    """
    from .tools import get_tools

    for tool in get_tools():
        if tool.name != name:
            continue
        required = tool.inputSchema.get("required", []) or []
        missing = [
            p for p in required if p != "widget_id" and (args.get(p) is None or args.get(p) == "")
        ]
        if missing:
            return (
                f"Missing required argument(s) for {name}: "
                f"{', '.join(missing)}.  Re-invoke the tool with all "
                "required fields populated."
            )
        return None
    return None


async def handle_tool(
    name: str,
    args: dict[str, Any],
    events: EventsDict,
    make_callback: MakeCallback,
) -> HandlerResult:
    """Handle MCP tool calls using dispatch pattern.

    Parameters
    ----------
    name : str
        The name of the tool to execute.
    args : dict[str, Any]
        Arguments passed to the tool.
    events : EventsDict
        Event storage dictionary.
    make_callback : MakeCallback
        Factory function to create event callbacks.

    Returns
    -------
    HandlerResult
        Tool execution result.
    """
    headless = os.environ.get("PYWRY_HEADLESS", "0") == "1"
    ctx = HandlerContext(args, events, make_callback, headless)

    error_msg = _check_required_args(name, args)
    if error_msg:
        return {"error": error_msg}

    handler = _HANDLERS.get(name)
    if handler:
        return handler(ctx)

    return {"error": f"Unknown tool: {name}"}
