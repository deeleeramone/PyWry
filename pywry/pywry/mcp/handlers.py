"""MCP tool handlers for PyWry v2.0.0.

This module handles all tool call implementations using a dispatch pattern.
"""

from __future__ import annotations

import json
import os
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
    get_app,
    get_widget,
    list_widget_ids,
    register_widget,
    remove_widget,
    store_widget_config,
)


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

        if widget_id in inline_state.widgets:
            inline_state.widgets[widget_id]["persistent"] = True

        return {
            "widget_id": widget_id,
            "path": f"/widget/{widget_id}",
            "created": True,
            "export_uri": f"pywry://export/{widget_id}",
        }

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

    if ctx.headless:
        from ..inline import _state as inline_state

        if widget_id in inline_state.widgets:
            inline_state.widgets[widget_id]["persistent"] = True

    return {
        "widget_id": widget_id,
        "path": f"/widget/{widget_id}",
        "created": True,
    }


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

    if ctx.headless:
        from ..inline import _state as inline_state

        if widget_id in inline_state.widgets:
            inline_state.widgets[widget_id]["persistent"] = True

    return {
        "widget_id": widget_id,
        "path": f"/widget/{widget_id}",
        "created": True,
    }


# =============================================================================
# Widget Manipulation Handlers
# =============================================================================
def _get_widget_or_error(widget_id: str) -> tuple[Any | None, HandlerResult | None]:
    """Get widget by ID, returning error dict if not found."""
    widget = get_widget(widget_id)
    if not widget:
        return None, {"error": f"Widget not found: {widget_id}"}
    return widget, None


def _handle_set_content(ctx: HandlerContext) -> HandlerResult:
    widget_id = ctx.args["widget_id"]
    widget, error = _get_widget_or_error(widget_id)
    if error:
        return error
    assert widget is not None  # Type guard

    data = {"id": ctx.args["component_id"]}
    if "html" in ctx.args:
        data["html"] = ctx.args["html"]
    else:
        data["text"] = ctx.args.get("text", "")

    widget.emit("pywry:set-content", data)
    return {"widget_id": widget_id, "updated": True}


def _handle_set_style(ctx: HandlerContext) -> HandlerResult:
    widget_id = ctx.args["widget_id"]
    widget, error = _get_widget_or_error(widget_id)
    if error:
        return error
    assert widget is not None

    widget.emit(
        "pywry:set-style",
        {"id": ctx.args["component_id"], "styles": ctx.args["styles"]},
    )
    return {"widget_id": widget_id, "updated": True}


def _handle_show_toast(ctx: HandlerContext) -> HandlerResult:
    widget_id = ctx.args["widget_id"]
    widget, error = _get_widget_or_error(widget_id)
    if error:
        return error
    assert widget is not None

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
    widget_id = ctx.args["widget_id"]
    widget, error = _get_widget_or_error(widget_id)
    if error:
        return error
    assert widget is not None

    widget.emit("pywry:update-theme", {"theme": ctx.args["theme"]})
    return {"widget_id": widget_id, "theme": ctx.args["theme"]}


def _handle_inject_css(ctx: HandlerContext) -> HandlerResult:
    widget_id = ctx.args["widget_id"]
    widget, error = _get_widget_or_error(widget_id)
    if error:
        return error
    assert widget is not None

    widget.emit(
        "pywry:inject-css",
        {
            "css": ctx.args["css"],
            "id": ctx.args.get("style_id", "pywry-injected-style"),
        },
    )
    return {"widget_id": widget_id, "css_injected": True}


def _handle_remove_css(ctx: HandlerContext) -> HandlerResult:
    widget_id = ctx.args["widget_id"]
    widget, error = _get_widget_or_error(widget_id)
    if error:
        return error
    assert widget is not None

    widget.emit("pywry:remove-css", {"id": ctx.args["style_id"]})
    return {"widget_id": widget_id, "css_removed": True}


def _handle_navigate(ctx: HandlerContext) -> HandlerResult:
    widget_id = ctx.args["widget_id"]
    widget, error = _get_widget_or_error(widget_id)
    if error:
        return error
    assert widget is not None

    widget.emit("pywry:navigate", {"url": ctx.args["url"]})
    return {"widget_id": widget_id, "navigating_to": ctx.args["url"]}


def _handle_download(ctx: HandlerContext) -> HandlerResult:
    widget_id = ctx.args["widget_id"]
    widget, error = _get_widget_or_error(widget_id)
    if error:
        return error
    assert widget is not None

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
    widget_id = ctx.args["widget_id"]
    widget, error = _get_widget_or_error(widget_id)
    if error:
        return error
    assert widget is not None

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
    widget_id = ctx.args["widget_id"]
    widget, error = _get_widget_or_error(widget_id)
    if error:
        return error
    assert widget is not None

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

    widget_id = ctx.args["widget_id"]
    widget, error = _get_widget_or_error(widget_id)
    if error:
        return error
    assert widget is not None

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
    widget_id = ctx.args["widget_id"]
    widget, error = _get_widget_or_error(widget_id)
    if error:
        return error
    assert widget is not None

    widget.emit(ctx.args["event_type"], ctx.args.get("data", {}))
    return {
        "widget_id": widget_id,
        "event_sent": True,
        "event_type": ctx.args["event_type"],
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
    widget_id = ctx.args["widget_id"]
    widget_events = ctx.events.get(widget_id, [])
    if ctx.args.get("clear", False):
        ctx.events[widget_id] = []
    return {"widget_id": widget_id, "events": widget_events}


def _handle_destroy_widget(ctx: HandlerContext) -> HandlerResult:
    widget_id = ctx.args["widget_id"]
    ctx.events.pop(widget_id, None)
    remove_widget(widget_id)
    if ctx.headless:
        from ..inline import _state as inline_state

        inline_state.widgets.pop(widget_id, None)
    return {"widget_id": widget_id, "destroyed": True}


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
    widget_id = ctx.args["widget_id"]
    code = export_widget_code(widget_id)
    if not code:
        return {"error": f"Widget not found or no config stored: {widget_id}"}
    return {
        "widget_id": widget_id,
        "code": code,
        "language": "python",
        "note": "Save this code to a .py file to recreate the widget without MCP",
    }


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
    "list_resources": _handle_list_resources,
}


# =============================================================================
# Main Entry Point
# =============================================================================
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

    handler = _HANDLERS.get(name)
    if handler:
        return handler(ctx)

    return {"error": f"Unknown tool: {name}"}
