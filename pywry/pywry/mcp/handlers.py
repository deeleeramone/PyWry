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
    from ..chat import ChatThread, _default_slash_commands, build_chat_html
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

    # Register default slash commands
    for cmd in _default_slash_commands():
        widget.emit(
            "chat:register-command",
            {
                "name": cmd.name,
                "description": cmd.description,
            },
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

        if widget_id in inline_state.widgets:
            inline_state.widgets[widget_id]["persistent"] = True

        return {
            "widget_id": widget_id,
            "thread_id": thread_id,
            "path": f"/widget/{widget_id}",
            "created": True,
        }

    return {
        "widget_id": widget_id,
        "thread_id": thread_id,
        "mode": "native",
        "message": "Chat window opened",
        "created": True,
    }


def _handle_chat_send_message(ctx: HandlerContext) -> HandlerResult:
    widget_id = ctx.args["widget_id"]
    widget, error = _get_widget_or_error(widget_id)
    if error:
        return error
    assert widget is not None

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
    widget_id = ctx.args["widget_id"]
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
    widget_id = ctx.args["widget_id"]
    action = ctx.args["action"]
    thread_id = ctx.args.get("thread_id")
    title = ctx.args.get("title", "New Chat")

    widget, error = _get_widget_or_error(widget_id)
    if error:
        return error
    assert widget is not None

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
    widget_id = ctx.args["widget_id"]
    name = ctx.args["name"]
    description = ctx.args.get("description", "")

    widget, error = _get_widget_or_error(widget_id)
    if error:
        return error
    assert widget is not None

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
    widget_id = ctx.args["widget_id"]
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
    widget_id = ctx.args["widget_id"]
    widget, error = _get_widget_or_error(widget_id)
    if error:
        return error
    assert widget is not None

    settings: dict[str, Any] = {}
    for key in ("model", "temperature", "max_tokens", "system_prompt", "streaming"):
        if key in ctx.args:
            settings[key] = ctx.args[key]

    if settings:
        widget.emit("chat:update-settings", settings)

    return {"widget_id": widget_id, "settings": settings, "applied": True}


def _handle_chat_set_typing(ctx: HandlerContext) -> HandlerResult:
    widget_id = ctx.args["widget_id"]
    widget, error = _get_widget_or_error(widget_id)
    if error:
        return error
    assert widget is not None

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
