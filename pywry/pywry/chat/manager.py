"""High-level ChatManager — ACP-native orchestrator for the chat component.

The ``ChatManager`` abstracts away threading, event wiring, thread CRUD,
streaming, cancellation, and state sync. Developers provide a
``ChatProvider`` and the manager handles the ACP session lifecycle.

Minimal usage::

    from pywry import PyWry
    from pywry.chat import ChatManager, build_chat_html
    from pywry.chat.providers.openai import OpenAIProvider

    app = PyWry(title="My Chat")
    provider = OpenAIProvider(api_key="sk-...")
    chat = ChatManager(provider=provider)

    widget = app.show(
        HtmlContent(html="<h1>App</h1>"),
        toolbars=[chat.toolbar()],
        callbacks=chat.callbacks(),
    )
    chat.bind(widget)
    app.block()
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import pathlib
import threading
import time
import uuid

from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from typing import Any, ClassVar, Literal

from pydantic import BaseModel

from .artifacts import (
    CodeArtifact,
    HtmlArtifact,
    ImageArtifact,
    JsonArtifact,
    MarkdownArtifact,
    PlotlyArtifact,
    TableArtifact,
    TradingViewArtifact,
    _ArtifactBase,
)
from .updates import (
    AgentMessageUpdate,
    ArtifactUpdate,
    CitationUpdate,
    CommandsUpdate,
    ConfigOptionUpdate,
    ModeUpdate,
    PermissionRequestUpdate,
    PlanUpdate,
    StatusUpdate,
    ThinkingUpdate,
    ToolCallUpdate,
)


log = logging.getLogger(__name__)


@dataclass
class Attachment:
    """A resolved context attachment (file or widget reference).

    Attributes
    ----------
    type : str
        Source type — ``"file"`` or ``"widget"``.
    name : str
        Display name (e.g. ``"report.pdf"``, ``"@MyGrid"``).
    path : pathlib.Path | None
        For file attachments — the full filesystem path.
    content : str
        For widget attachments — live data extracted from the component.
    source : str
        Original source identifier.
    """

    type: str
    name: str
    path: pathlib.Path | None = None
    content: str = ""
    source: str = ""


_MAX_ATTACHMENTS = 20


@dataclass
class ChatContext:
    """Context object passed to handler functions.

    Attributes
    ----------
    thread_id : str
        Active thread ID.
    message_id : str
        The assistant message ID being generated.
    settings : dict[str, Any]
        Current settings values.
    cancel_event : threading.Event
        Set when the user clicks Stop.
    system_prompt : str
        System prompt configured for the chat.
    model : str
        Model name configured for the chat.
    temperature : float
        Temperature configured for the chat.
    attachments : list[Attachment]
        Resolved context attachments for the current message.
    """

    thread_id: str = ""
    message_id: str = ""
    settings: dict[str, Any] = field(default_factory=dict)
    cancel_event: threading.Event = field(default_factory=threading.Event)
    system_prompt: str = ""
    model: str = ""
    temperature: float = 0.7
    attachments: list[Attachment] = field(default_factory=list)

    @property
    def attachment_summary(self) -> str:
        """One-line summary of attached context for system/user prompts.

        Returns
        -------
        str
            Summary line, or empty string when no attachments.
        """
        if not self.attachments:
            return ""
        parts: list[str] = []
        for att in self.attachments:
            if att.type == "file":
                if att.path:
                    parts.append(f"{att.name} (file: {att.path})")
                else:
                    parts.append(f"{att.name} (file)")
            else:
                parts.append(f"{att.name} ({att.type})")
        return "Attached context: " + ", ".join(parts)

    @property
    def context_text(self) -> str:
        """Pre-formatted attachment content ready to inject into prompts.

        Returns
        -------
        str
            Multi-block attachment context, or empty string.
        """
        if not self.attachments:
            return ""
        parts: list[str] = []
        for att in self.attachments:
            label = att.name.lstrip("@").strip()
            if att.type == "file" and att.path:
                parts.append(f"--- Attached file: {label} ---\nPath: {att.path}\n--- End ---")
            elif att.content:
                parts.append(f"--- Attached: {label} ---\n{att.content}\n--- End ---")
        return "\n\n".join(parts)

    def get_attachment(self, name: str) -> str:
        """Retrieve attachment content or path by name.

        Parameters
        ----------
        name : str
            Attachment name, with or without a leading ``@``.

        Returns
        -------
        str
            Attachment path or content, or a not-found message.
        """
        lookup = name.lstrip("@").strip()
        for att in self.attachments:
            att_name = att.name.lstrip("@").strip()
            if att_name == lookup:
                if att.type == "file" and att.path:
                    return str(att.path)
                return att.content
        available = ", ".join(a.name for a in self.attachments)
        return f"Attachment '{name}' not found. Available: {available}"

    _input_event: threading.Event = field(default_factory=threading.Event, init=False, repr=False)
    _input_response: str = field(default="", init=False, repr=False)

    def wait_for_input(self, timeout: float | None = None) -> str:
        """Block until the user provides input.

        Parameters
        ----------
        timeout : float | None, optional
            Maximum seconds to wait. ``None`` waits indefinitely.

        Returns
        -------
        str
            User-supplied input, or empty string on cancellation/timeout.
        """
        deadline = (time.time() + timeout) if timeout else None
        while not self._input_event.is_set():
            if self.cancel_event.is_set():
                return ""
            remaining = None
            if deadline is not None:
                remaining = deadline - time.time()
                if remaining <= 0:
                    return ""
            self._input_event.wait(timeout=min(0.1, remaining or 0.1))
        self._input_event.clear()
        response = self._input_response
        self._input_response = ""
        return response


class SettingsItem(BaseModel):
    """Settings menu item shown in the gear dropdown.

    Attributes
    ----------
    id : str
        Stable identifier.
    label : str
        User-visible label.
    type : str
        Control type.
    value : Any
        Current value.
    options : list[str] | None
        Allowed values for ``select`` controls.
    min : float | None
        Minimum for ``range`` controls.
    max : float | None
        Maximum for ``range`` controls.
    step : float | None
        Increment for ``range`` controls.
    """

    id: str
    label: str = ""
    type: Literal["action", "toggle", "select", "range", "separator"] = "action"
    value: Any = None
    options: list[str] | None = None
    min: float | None = None
    max: float | None = None
    step: float | None = None


MessageDict = dict[str, Any]
HandlerFunc = Callable[..., Any]


class _StreamState:
    """Mutable state container for stream text buffering."""

    __slots__ = ("buffer", "full_text", "last_flush", "message_id")

    def __init__(self, message_id: str) -> None:
        self.message_id = message_id
        self.full_text = ""
        self.buffer = ""
        self.last_flush = time.monotonic()


class ChatManager:
    """ACP-native orchestrator for the PyWry chat component.

    Handles event wiring, thread management, streaming, cancellation,
    and state synchronization. Accepts either a ``ChatProvider`` instance
    (ACP session lifecycle) or a handler function.

    Parameters
    ----------
    provider : ChatProvider | None
        ACP-conformant provider instance.
    handler : callable | None
        Handler function ``(messages, ctx) -> str | Iterator``.
        Exactly one of ``provider`` or ``handler`` must be supplied.
    system_prompt : str
        System prompt prepended to every request.
    model : str
        Model identifier passed to handler via context.
    temperature : float
        Temperature passed to handler via context.
    welcome_message : str
        Markdown message sent when the chat initializes.
    settings : list[SettingsItem] | None
        Settings items for the gear dropdown.
    on_settings_change : callable | None
        Callback ``(key, value)`` when a setting changes.
    show_sidebar : bool
        Show the conversation picker.
    show_settings : bool
        Show the gear icon.
    toolbar_width : str
        CSS width for the chat toolbar.
    toolbar_min_width : str
        CSS min-width for the chat toolbar.
    collapsible : bool
        Whether the toolbar is collapsible.
    resizable : bool
        Whether the toolbar is resizable.
    include_plotly : bool
        Include Plotly.js eagerly.
    include_aggrid : bool
        Include AG Grid eagerly.
    aggrid_theme : str
        AG Grid theme name.
    enable_context : bool
        Enable @-mention widget references.
    enable_file_attach : bool
        Enable file attachment button.
    file_accept_types : list[str] | None
        Allowed file extensions (required when ``enable_file_attach=True``).
    context_allowed_roots : list[str] | None
        Restrict file attachments to these directories.
    """

    CONTEXT_TOOL: ClassVar[dict[str, Any]] = {
        "type": "function",
        "function": {
            "name": "get_context",
            "description": (
                "Retrieve the full content of an attached file or widget. "
                "Call this when you need to read, analyze, or reference "
                "an attachment the user has provided."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The attachment name.",
                    },
                },
                "required": ["name"],
            },
        },
    }

    def __init__(
        self,
        provider: Any = None,
        handler: HandlerFunc | None = None,
        *,
        system_prompt: str = "",
        model: str = "",
        temperature: float = 0.7,
        welcome_message: str = "",
        settings: Sequence[SettingsItem] | None = None,
        slash_commands: Sequence[Any] | None = None,
        on_slash_command: Callable[..., Any] | None = None,
        on_settings_change: Callable[..., Any] | None = None,
        show_sidebar: bool = True,
        show_settings: bool = True,
        toolbar_width: str = "380px",
        toolbar_min_width: str = "280px",
        collapsible: bool = True,
        resizable: bool = True,
        include_plotly: bool = False,
        include_aggrid: bool = False,
        aggrid_theme: str = "alpine",
        enable_context: bool = False,
        enable_file_attach: bool = False,
        file_accept_types: list[str] | None = None,
        context_allowed_roots: list[str] | None = None,
    ) -> None:
        if provider is None and handler is None:
            raise ValueError("Either 'provider' or 'handler' must be supplied")

        self._provider = provider
        self._handler = handler
        self._system_prompt = system_prompt
        self._model = model
        self._temperature = temperature
        self._welcome_message = welcome_message
        self._settings_items = list(settings) if settings else []
        self._slash_commands = list(slash_commands) if slash_commands else []
        self._on_slash_command = on_slash_command
        self._on_settings_change = on_settings_change
        self._show_sidebar = show_sidebar
        self._show_settings = show_settings
        self._toolbar_width = toolbar_width
        self._toolbar_min_width = toolbar_min_width
        self._collapsible = collapsible
        self._resizable = resizable
        self._include_plotly = include_plotly
        self._include_aggrid = include_aggrid
        self._aggrid_theme = aggrid_theme
        self._enable_context = enable_context
        self._enable_file_attach = enable_file_attach
        if enable_file_attach and not file_accept_types:
            raise ValueError(
                "file_accept_types is required when enable_file_attach=True. "
                "Specify the extensions your app handles, e.g. "
                'file_accept_types=[".csv", ".json", ".xlsx"]'
            )
        self._file_accept_types = file_accept_types
        self._context_allowed_roots = (
            [str(pathlib.Path(r).resolve()) for r in context_allowed_roots]
            if context_allowed_roots
            else None
        )

        # Internal state
        self._widget: Any = None
        self._is_anywidget: bool = False
        self._threads: dict[str, list[MessageDict]] = {}
        self._thread_titles: dict[str, str] = {}
        self._active_thread: str = ""
        self._cancel_events: dict[str, threading.Event] = {}
        self._settings_values: dict[str, Any] = {
            s.id: s.value for s in self._settings_items if s.type != "separator"
        }
        self._pending_inputs: dict[str, dict[str, Any]] = {}
        self._aggrid_assets_sent: bool = include_aggrid
        self._plotly_assets_sent: bool = include_plotly
        self._tradingview_assets_sent: bool = False
        self._context_sources: dict[str, dict[str, Any]] = {}

        # ACP session state
        self._session_id: str = ""

        # Create default thread
        default_id = f"thread_{uuid.uuid4().hex[:8]}"
        self._threads[default_id] = []
        self._thread_titles[default_id] = "Chat 1"
        self._active_thread = default_id

    def register_context_source(self, component_id: str, name: str) -> None:
        """Register a live component as an @-mentionable context source.

        Parameters
        ----------
        component_id : str
            Unique ID of the component.
        name : str
            Human-readable label shown in the popup.
        """
        self._context_sources[component_id] = {"name": name}

    def bind(self, widget: Any) -> None:
        """Bind to a widget after ``app.show()``.

        Parameters
        ----------
        widget : Any
            The widget instance returned by ``app.show()``.
        """
        self._widget = widget
        try:
            from ..widget import PyWryChatWidget

            self._is_anywidget = isinstance(widget, PyWryChatWidget)
        except ImportError:
            self._is_anywidget = False

    def toolbar(
        self,
        *,
        position: Literal["header", "footer", "top", "bottom", "left", "right", "inside"] = "right",
    ) -> Any:
        """Build a Toolbar containing the chat panel.

        Returns
        -------
        Any
            A ``Toolbar`` instance for ``app.show(toolbars=...)``.
        """
        from ..toolbar import Div, Toolbar as ToolbarCls
        from .html import build_chat_html

        html = build_chat_html(
            show_sidebar=self._show_sidebar,
            show_settings=self._show_settings,
            enable_context=self._enable_context,
            enable_file_attach=self._enable_file_attach,
            file_accept_types=self._file_accept_types,
        )
        return ToolbarCls(
            position=position,
            collapsible=self._collapsible,
            resizable=self._resizable,
            style=(f"width: {self._toolbar_width}; min-width: {self._toolbar_min_width};"),
            items=[
                Div(
                    content=html,
                    component_id="chat-container",
                    style="width: 100%; height: 100%; display: flex; flex-direction: column;",
                ),
            ],
        )

    def callbacks(self) -> dict[str, Callable[..., Any]]:
        """Return the callbacks dict for ``app.show(callbacks=...)``.

        Returns
        -------
        dict[str, Callable]
            Event handler mappings for all chat events.
        """
        return {
            "chat:user-message": self._on_user_message,
            "chat:stop-generation": self._on_stop_generation,
            "chat:slash-command": self._on_slash_command_event,
            "chat:thread-create": self._on_thread_create,
            "chat:thread-switch": self._on_thread_switch,
            "chat:thread-delete": self._on_thread_delete,
            "chat:thread-rename": self._on_thread_rename,
            "chat:settings-change": self._on_settings_change_event,
            "chat:request-state": self._on_request_state,
            "chat:todo-clear": self._on_todo_clear,
            "chat:input-response": self._on_input_response,
        }

    @property
    def active_thread_id(self) -> str:
        """The currently active thread ID."""
        return self._active_thread

    @property
    def settings(self) -> dict[str, Any]:
        """Current settings values."""
        return dict(self._settings_values)

    @property
    def threads(self) -> dict[str, list[MessageDict]]:
        """Thread history (read-only view)."""
        return dict(self._threads)

    def send_message(self, text: str, thread_id: str | None = None) -> None:
        """Send a programmatic assistant message.

        Parameters
        ----------
        text : str
            Message text.
        thread_id : str | None
            Target thread. Defaults to active thread.
        """
        tid = thread_id or self._active_thread
        msg_id = f"msg_{uuid.uuid4().hex[:8]}"
        self._emit(
            "chat:assistant-message",
            {"messageId": msg_id, "text": text, "threadId": tid},
        )
        self._threads.setdefault(tid, [])
        self._threads[tid].append({"role": "assistant", "text": text})

    def _emit(self, event: str, data: dict[str, Any]) -> None:
        """Emit an event via the bound widget."""
        if self._widget is not None:
            self._widget.emit(event, data)

    def _emit_fire(self, event: str, data: dict[str, Any]) -> None:
        """Fire-and-forget emit for high-frequency streaming."""
        if self._widget is not None:
            if hasattr(self._widget, "emit_fire"):
                self._widget.emit_fire(event, data)
            else:
                self._widget.emit(event, data)

    def _inject_aggrid_assets(self) -> None:
        """Lazy-inject AG Grid JS/CSS on first table artifact."""
        if self._aggrid_assets_sent:
            return
        from ..assets import get_aggrid_css, get_aggrid_defaults_js, get_aggrid_js
        from ..models import ThemeMode

        if self._is_anywidget:
            self._widget.set_trait(
                "_asset_js",
                get_aggrid_js() + "\n" + get_aggrid_defaults_js(),
            )
            self._widget.set_trait(
                "_asset_css",
                get_aggrid_css(self._aggrid_theme, ThemeMode.DARK),
            )
        else:
            self._emit(
                "chat:load-assets",
                {
                    "scripts": [get_aggrid_js(), get_aggrid_defaults_js()],
                    "styles": [get_aggrid_css(self._aggrid_theme, ThemeMode.DARK)],
                },
            )
        self._aggrid_assets_sent = True

    def _inject_plotly_assets(self) -> None:
        """Lazy-inject Plotly JS on first plotly artifact."""
        if self._plotly_assets_sent:
            return
        from ..assets import get_plotly_defaults_js, get_plotly_js, get_plotly_templates_js

        scripts = [get_plotly_js(), get_plotly_templates_js(), get_plotly_defaults_js()]
        if self._is_anywidget:
            self._widget.set_trait("_asset_js", "\n".join(scripts))
        else:
            self._emit(
                "chat:load-assets",
                {"scripts": scripts, "styles": []},
            )
        self._plotly_assets_sent = True

    def _inject_tradingview_assets(self) -> None:
        """Lazy-inject TradingView lightweight-charts on first TV artifact."""
        if self._tradingview_assets_sent:
            return
        from ..assets import get_tvchart_js

        js = get_tvchart_js()
        if self._is_anywidget:
            self._widget.set_trait("_asset_js", js)
        else:
            self._emit(
                "chat:load-assets",
                {"scripts": [js], "styles": []},
            )
        self._tradingview_assets_sent = True

    def _dispatch_artifact(
        self,
        item: _ArtifactBase,
        message_id: str,
        thread_id: str,
    ) -> None:
        """Dispatch an artifact to the frontend.

        Parameters
        ----------
        item : _ArtifactBase
            Concrete artifact instance.
        message_id : str
            Current assistant message ID.
        thread_id : str
            Current thread ID.
        """
        base: dict[str, Any] = {
            "messageId": message_id,
            "artifactType": item.artifact_type,
            "title": item.title,
            "threadId": thread_id,
        }

        if isinstance(item, CodeArtifact):
            base["content"] = item.content
            base["language"] = item.language

        elif isinstance(item, (MarkdownArtifact, HtmlArtifact)):
            base["content"] = item.content

        elif isinstance(item, TableArtifact):
            self._inject_aggrid_assets()
            from ..grid import normalize_data

            grid_data = normalize_data(item.data)
            base["rowData"] = grid_data.row_data
            base["columns"] = grid_data.columns
            base["columnTypes"] = grid_data.column_types
            base["height"] = item.height
            if item.column_defs is not None:
                base["columnDefs"] = item.column_defs
            if item.grid_options is not None:
                base["gridOptions"] = item.grid_options

        elif isinstance(item, PlotlyArtifact):
            self._inject_plotly_assets()
            base["figure"] = item.figure
            base["height"] = item.height

        elif isinstance(item, TradingViewArtifact):
            self._inject_tradingview_assets()
            base["series"] = [s.model_dump() for s in item.series]
            base["options"] = item.options
            base["height"] = item.height

        elif isinstance(item, ImageArtifact):
            base["url"] = item.url
            base["alt"] = item.alt

        elif isinstance(item, JsonArtifact):
            base["data"] = item.data

        self._emit("chat:artifact", base)

    def _is_accepted_file(self, filename: str) -> bool:
        """Check if file extension is allowed."""
        if not self._file_accept_types:
            return True
        ext = pathlib.Path(filename).suffix.lower()
        return ext in {t.lower() for t in self._file_accept_types}

    def _resolve_widget_attachment(
        self,
        widget_id: str,
        content: str | None = None,
        name: str | None = None,
    ) -> Attachment | None:
        """Create an Attachment for a widget/component reference."""
        if content:
            display_name = name or widget_id
            registered = self._context_sources.get(widget_id)
            if registered:
                display_name = registered["name"]
            return Attachment(
                type="widget",
                name=f"@{display_name}",
                content=content,
                source=widget_id,
            )
        try:
            app = getattr(self._widget, "_app", None) if self._widget else None
            if app is None:
                return None
            widgets = getattr(app, "_inline_widgets", {})
            target = widgets.get(widget_id)
            if target is None:
                return None
            label = getattr(target, "label", widget_id)
            content_parts = [f"# Widget: {label}"]
            html_content = getattr(target, "html", None)
            if html_content:
                content_parts.append(f"Widget type: HTML widget ({len(html_content)} chars)")
            return Attachment(
                type="widget",
                name=f"@{label}",
                content="\n\n".join(content_parts),
                source=widget_id,
            )
        except Exception:
            log.warning("Could not resolve widget %r", widget_id, exc_info=True)
            return None

    def _resolve_attachments(
        self,
        raw_attachments: list[dict[str, Any]],
    ) -> list[Attachment]:
        """Resolve raw attachment dicts into Attachment objects."""
        if not (self._enable_context or self._enable_file_attach):
            return []
        resolved: list[Attachment] = []
        for item in raw_attachments[:_MAX_ATTACHMENTS]:
            att_type = item.get("type", "file")
            att: Attachment | None = None
            if att_type == "file":
                file_name = item.get("name", "attachment")
                file_path = item.get("path", "")
                file_content = item.get("content", "")
                if not self._is_accepted_file(file_name):
                    log.warning("File %r rejected — extension not allowed", file_name)
                    continue
                if not file_path and not file_content:
                    log.warning("File %r has no path or content", file_name)
                    continue
                att = Attachment(
                    type="file",
                    name=file_name,
                    path=pathlib.Path(file_path) if file_path else None,
                    content=file_content,
                    source=file_path or file_name,
                )
            elif att_type == "widget":
                widget_id = item.get("widgetId", "")
                if widget_id:
                    att = self._resolve_widget_attachment(
                        widget_id,
                        content=item.get("content"),
                        name=item.get("name"),
                    )
            if att is not None:
                resolved.append(att)
        return resolved

    def _get_context_sources(self) -> list[dict[str, str]]:
        """List available context sources for the @-mention popup."""
        sources: list[dict[str, str]] = []
        for src_id, src in self._context_sources.items():
            sources.append(
                {
                    "id": src_id,
                    "name": src["name"],
                    "type": "widget",
                    "componentId": src_id,
                }
            )
        seen = set(self._context_sources.keys())
        try:
            app = getattr(self._widget, "_app", None) if self._widget else None
            if app:
                widgets = getattr(app, "_inline_widgets", {})
                for wid, w in widgets.items():
                    if wid not in seen:
                        label = getattr(w, "label", wid)
                        sources.append({"id": wid, "name": label, "type": "widget"})
        except Exception:
            log.debug("Could not auto-discover inline widgets", exc_info=True)
        return sources

    def _dispatch_text_update(
        self,
        update: ThinkingUpdate | StatusUpdate | CitationUpdate,
        state: _StreamState,
        thread_id: str,
    ) -> None:
        """Dispatch thinking, status, or citation updates."""
        self._flush_buffer(state)
        if isinstance(update, ThinkingUpdate):
            self._emit_fire(
                "chat:thinking-chunk",
                {"messageId": state.message_id, "text": update.text, "threadId": thread_id},
            )
        elif isinstance(update, StatusUpdate):
            self._emit_fire(
                "chat:status-update",
                {"messageId": state.message_id, "text": update.text, "threadId": thread_id},
            )
        else:
            self._emit_fire(
                "chat:citation",
                {
                    "messageId": state.message_id,
                    "url": update.url,
                    "title": update.title,
                    "snippet": update.snippet,
                    "threadId": thread_id,
                },
            )

    def _dispatch_config_update(
        self,
        update: CommandsUpdate | ConfigOptionUpdate | ModeUpdate,
        state: _StreamState,
    ) -> None:
        """Dispatch commands, config, or mode updates."""
        self._flush_buffer(state)
        if isinstance(update, CommandsUpdate):
            for cmd in update.commands:
                self._emit(
                    "chat:register-command", {"name": cmd.name, "description": cmd.description}
                )
        elif isinstance(update, ConfigOptionUpdate):
            self._emit("chat:config-update", {"options": [o.model_dump() for o in update.options]})
        else:
            self._emit(
                "chat:mode-update",
                {
                    "currentModeId": update.current_mode_id,
                    "availableModes": [m.model_dump() for m in update.available_modes],
                },
            )

    def _dispatch_session_update(
        self,
        update: Any,
        state: _StreamState,
        thread_id: str,
        ctx: ChatContext | None,
    ) -> None:
        """Dispatch a single SessionUpdate to the frontend."""
        if isinstance(update, AgentMessageUpdate):
            self._buffer_text(state, update.text)

        elif isinstance(update, (ThinkingUpdate, StatusUpdate, CitationUpdate)):
            self._dispatch_text_update(update, state, thread_id)

        elif isinstance(update, ToolCallUpdate):
            self._flush_buffer(state)
            self._emit_fire(
                "chat:tool-call",
                {
                    "messageId": state.message_id,
                    "toolCallId": update.tool_call_id,
                    "title": update.title,
                    "name": update.name,
                    "kind": update.kind,
                    "status": update.status,
                    "threadId": thread_id,
                },
            )

        elif isinstance(update, PlanUpdate):
            self._flush_buffer(state)
            self._emit_fire(
                "chat:plan-update", {"entries": [e.model_dump() for e in update.entries]}
            )

        elif isinstance(update, (CommandsUpdate, ConfigOptionUpdate, ModeUpdate)):
            self._dispatch_config_update(update, state)

        elif isinstance(update, PermissionRequestUpdate):
            self._flush_buffer(state)
            self._emit_fire(
                "chat:permission-request",
                {
                    "toolCallId": update.tool_call_id,
                    "title": update.title,
                    "options": [o.model_dump() for o in update.options],
                    "requestId": update.request_id,
                    "threadId": thread_id,
                },
            )

        elif isinstance(update, ArtifactUpdate):
            self._flush_buffer(state)
            if isinstance(update.artifact, _ArtifactBase):
                self._dispatch_artifact(update.artifact, state.message_id, thread_id)

    def _process_handler_item(
        self,
        item: Any,
        state: _StreamState,
        thread_id: str,
        ctx: ChatContext | None,
    ) -> None:
        """Dispatch a handler yield item.

        Handles plain strings, SessionUpdate objects, and artifacts.
        """
        # Check if it's a SessionUpdate first (new-style)
        if hasattr(item, "session_update"):
            self._dispatch_session_update(item, state, thread_id, ctx)
            return

        if isinstance(item, str):
            self._buffer_text(state, item)

        elif isinstance(item, _ArtifactBase):
            self._flush_buffer(state)
            self._dispatch_artifact(item, state.message_id, thread_id)

        else:
            # Try to handle as SessionUpdate anyway
            self._dispatch_session_update(item, state, thread_id, ctx)

    _STREAM_FLUSH_INTERVAL: float = 0.030
    _STREAM_MAX_BUFFER: int = 300

    def _flush_buffer(self, state: _StreamState) -> None:
        """Flush buffered text to the frontend."""
        if state.buffer:
            self._emit_fire(
                "chat:stream-chunk",
                {
                    "messageId": state.message_id,
                    "chunk": state.buffer,
                    "done": False,
                },
            )
            state.buffer = ""
            state.last_flush = time.monotonic()

    def _buffer_text(self, state: _StreamState, text: str) -> None:
        """Add text to buffer, auto-flush on threshold."""
        state.buffer += text
        state.full_text += text
        if state.buffer and (
            time.monotonic() - state.last_flush >= self._STREAM_FLUSH_INTERVAL
            or len(state.buffer) >= self._STREAM_MAX_BUFFER
        ):
            self._flush_buffer(state)

    def _finalize_stream(self, state: _StreamState, thread_id: str) -> None:
        """Flush remaining buffer and send stream-done events."""
        self._flush_buffer(state)
        self._emit_fire(
            "chat:thinking-done",
            {"messageId": state.message_id, "threadId": thread_id},
        )
        self._emit_fire(
            "chat:stream-chunk",
            {"messageId": state.message_id, "chunk": "", "done": True},
        )
        if state.full_text:
            self._threads.setdefault(thread_id, [])
            self._threads[thread_id].append({"role": "assistant", "text": state.full_text})

    def _handle_cancel(self, state: _StreamState, thread_id: str) -> None:
        """Handle stream cancellation."""
        self._flush_buffer(state)
        self._emit_fire(
            "chat:stream-chunk",
            {
                "messageId": state.message_id,
                "chunk": "",
                "done": True,
                "stopped": True,
            },
        )
        if state.full_text:
            self._threads.setdefault(thread_id, [])
            self._threads[thread_id].append(
                {"role": "assistant", "text": state.full_text, "stopped": True}
            )

    def _handle_stream(
        self,
        gen: Any,
        message_id: str,
        thread_id: str,
        cancel: threading.Event,
        *,
        ctx: ChatContext | None = None,
    ) -> None:
        """Stream from a sync generator."""
        state = _StreamState(message_id)
        for item in gen:
            if cancel.is_set():
                self._handle_cancel(state, thread_id)
                return
            self._process_handler_item(item, state, thread_id, ctx)
        if cancel.is_set():
            self._handle_cancel(state, thread_id)
        else:
            self._finalize_stream(state, thread_id)

    async def _handle_async_stream(
        self,
        agen: Any,
        message_id: str,
        thread_id: str,
        cancel: threading.Event,
        *,
        ctx: ChatContext | None = None,
    ) -> None:
        """Stream from an async generator."""
        state = _StreamState(message_id)
        typing_hidden = False
        async for item in agen:
            if not typing_hidden:
                typing_hidden = True
                self._emit(
                    "chat:typing-indicator",
                    {"typing": False, "threadId": thread_id},
                )
            if cancel.is_set():
                self._handle_cancel(state, thread_id)
                return
            self._process_handler_item(item, state, thread_id, ctx)
        if not typing_hidden:
            self._emit(
                "chat:typing-indicator",
                {"typing": False, "threadId": thread_id},
            )
        self._finalize_stream(state, thread_id)

    def _inject_context(
        self,
        messages: list[MessageDict],
        ctx: ChatContext,
        message_id: str,
        thread_id: str,
    ) -> list[MessageDict]:
        """Inject attachment context into messages."""
        if not (ctx.attachments and messages):
            return messages
        for att in ctx.attachments:
            label = att.name.lstrip("@").strip()
            tool_id = f"ctx_{uuid.uuid4().hex[:8]}"
            self._emit_fire(
                "chat:tool-call",
                {
                    "messageId": message_id,
                    "toolId": tool_id,
                    "name": f"attach_{att.type}",
                    "arguments": {"name": label},
                    "threadId": thread_id,
                },
            )
            result_text = (
                f"Attached {label} → {att.path}"
                if att.type == "file" and att.path
                else f"Attached {label}"
            )
            self._emit_fire(
                "chat:tool-result",
                {
                    "messageId": message_id,
                    "toolId": tool_id,
                    "result": result_text,
                    "isError": False,
                    "threadId": thread_id,
                },
            )
        ctx_text = ctx.context_text
        if ctx_text:
            for i in range(len(messages) - 1, -1, -1):
                if messages[i].get("role") == "user":
                    messages = list(messages)
                    messages[i] = {
                        **messages[i],
                        "text": ctx_text + "\n\n" + messages[i].get("text", ""),
                    }
                    break
        return messages

    def _dispatch_handler_result(
        self,
        result: Any,
        message_id: str,
        thread_id: str,
        cancel: threading.Event,
        ctx: ChatContext,
    ) -> None:
        """Route handler return value to processing path."""
        if inspect.isgenerator(result):
            self._emit(
                "chat:typing-indicator",
                {"typing": False, "threadId": thread_id},
            )
            self._handle_stream(result, message_id, thread_id, cancel, ctx=ctx)
        elif inspect.isasyncgen(result):
            asyncio.run(self._handle_async_stream(result, message_id, thread_id, cancel, ctx=ctx))
        elif inspect.iscoroutine(result):
            resolved = asyncio.run(result)
            if inspect.isasyncgen(resolved):
                asyncio.run(
                    self._handle_async_stream(resolved, message_id, thread_id, cancel, ctx=ctx)
                )
            elif isinstance(resolved, str):
                self._emit(
                    "chat:typing-indicator",
                    {"typing": False, "threadId": thread_id},
                )
                self._handle_complete(resolved, message_id, thread_id)
            else:
                self._emit(
                    "chat:typing-indicator",
                    {"typing": False, "threadId": thread_id},
                )
                self._handle_complete(str(resolved), message_id, thread_id)
        elif isinstance(result, str):
            self._emit(
                "chat:typing-indicator",
                {"typing": False, "threadId": thread_id},
            )
            self._handle_complete(result, message_id, thread_id)
        elif isinstance(result, Iterator):
            self._emit(
                "chat:typing-indicator",
                {"typing": False, "threadId": thread_id},
            )
            self._handle_stream(result, message_id, thread_id, cancel, ctx=ctx)
        else:
            self._emit(
                "chat:typing-indicator",
                {"typing": False, "threadId": thread_id},
            )
            self._handle_complete(str(result), message_id, thread_id)

    def _handle_complete(self, text: str, message_id: str, thread_id: str) -> None:
        """Send a complete (non-streamed) assistant message."""
        self._emit(
            "chat:assistant-message",
            {"messageId": message_id, "text": text, "threadId": thread_id},
        )
        self._threads.setdefault(thread_id, [])
        self._threads[thread_id].append({"role": "assistant", "text": text})

    def _run_handler(
        self,
        messages: list[MessageDict],
        ctx: ChatContext,
        message_id: str,
        thread_id: str,
        cancel: threading.Event,
    ) -> None:
        """Execute the handler in a background thread."""
        try:
            messages = self._inject_context(messages, ctx, message_id, thread_id)
            result = self._handler(messages, ctx)  # type: ignore[misc]
            self._dispatch_handler_result(result, message_id, thread_id, cancel, ctx)
        except Exception as exc:
            self._emit(
                "chat:typing-indicator",
                {"typing": False, "threadId": thread_id},
            )
            error_text = f"Error: {exc}"
            self._emit(
                "chat:assistant-message",
                {"messageId": message_id, "text": error_text, "threadId": thread_id},
            )
            self._threads.setdefault(thread_id, [])
            self._threads[thread_id].append({"role": "assistant", "text": error_text})
        finally:
            self._cancel_events.pop(thread_id, None)

    def _on_user_message(self, data: Any, _event_type: str, _label: str) -> None:
        """Handle incoming user message."""
        text = data.get("text", "").strip()
        thread_id = data.get("threadId", self._active_thread) or self._active_thread
        if not text:
            return

        self._active_thread = thread_id
        self._threads.setdefault(thread_id, [])
        self._threads[thread_id].append({"role": "user", "text": text})

        message_id = f"msg_{uuid.uuid4().hex[:8]}"
        cancel = threading.Event()
        self._cancel_events[thread_id] = cancel

        self._emit(
            "chat:typing-indicator",
            {"typing": True, "threadId": thread_id},
        )

        raw_attachments = data.get("attachments", [])
        attachments = self._resolve_attachments(raw_attachments) if raw_attachments else []

        ctx = ChatContext(
            thread_id=thread_id,
            message_id=message_id,
            settings=dict(self._settings_values),
            cancel_event=cancel,
            system_prompt=self._system_prompt,
            model=self._model,
            temperature=self._temperature,
            attachments=attachments,
        )

        messages = list(self._threads.get(thread_id, []))

        if self._handler is not None:
            t = threading.Thread(
                target=self._run_handler,
                args=(messages, ctx, message_id, thread_id, cancel),
                daemon=True,
            )
            t.start()
        elif self._provider is not None:
            t = threading.Thread(
                target=self._run_provider,
                args=(messages, ctx, message_id, thread_id, cancel),
                daemon=True,
            )
            t.start()

    def _run_provider(
        self,
        messages: list[MessageDict],
        ctx: ChatContext,
        message_id: str,
        thread_id: str,
        cancel: threading.Event,
    ) -> None:
        """Execute the ACP provider prompt in a background thread."""
        from .models import TextPart

        try:
            messages = self._inject_context(messages, ctx, message_id, thread_id)

            # Convert messages to ContentBlock list
            content_blocks: list[Any] = []
            if messages:
                last = messages[-1]
                content_blocks.append(TextPart(text=last.get("text", "")))

            cancel_event = asyncio.Event()

            async def _run() -> None:
                state = _StreamState(message_id)
                typing_hidden = False
                async for update in self._provider.prompt(
                    self._session_id, content_blocks, cancel_event
                ):
                    if not typing_hidden:
                        typing_hidden = True
                        self._emit(
                            "chat:typing-indicator",
                            {"typing": False, "threadId": thread_id},
                        )
                    if cancel.is_set():
                        cancel_event.set()
                        self._handle_cancel(state, thread_id)
                        return
                    self._dispatch_session_update(update, state, thread_id, ctx)
                if not typing_hidden:
                    self._emit(
                        "chat:typing-indicator",
                        {"typing": False, "threadId": thread_id},
                    )
                self._finalize_stream(state, thread_id)

            asyncio.run(_run())
        except Exception as exc:
            self._emit(
                "chat:typing-indicator",
                {"typing": False, "threadId": thread_id},
            )
            error_text = f"Error: {exc}"
            self._emit(
                "chat:assistant-message",
                {"messageId": message_id, "text": error_text, "threadId": thread_id},
            )
            self._threads.setdefault(thread_id, [])
            self._threads[thread_id].append({"role": "assistant", "text": error_text})
        finally:
            self._cancel_events.pop(thread_id, None)

    def _on_stop_generation(self, data: Any, _event_type: str, _label: str) -> None:
        """Cancel active generation."""
        thread_id = data.get("threadId", self._active_thread)
        cancel = self._cancel_events.get(thread_id)
        if cancel:
            cancel.set()

    def _on_todo_clear(self, _data: Any, _event_type: str, _label: str) -> None:
        """Handle user clearing the plan/todo list."""
        self._emit("chat:todo-update", {"items": []})

    def _on_input_response(self, data: Any, _event_type: str, _label: str) -> None:
        """Handle user response to an input-required prompt."""
        text = data.get("text", "").strip()
        request_id = data.get("requestId", "")
        thread_id = data.get("threadId", self._active_thread) or self._active_thread
        pending = self._pending_inputs.pop(request_id, None)
        if pending is None:
            return
        self._threads.setdefault(thread_id, [])
        self._threads[thread_id].append({"role": "user", "text": text})
        ctx = pending.get("ctx")
        if ctx is not None:
            ctx._input_response = text
            ctx._input_event.set()

    def _on_slash_command_event(self, data: Any, _event_type: str, _label: str) -> None:
        """Handle slash command from frontend."""
        command = data.get("command", "")
        args = data.get("args", "")
        thread_id = data.get("threadId", self._active_thread) or self._active_thread
        if command == "/clear":
            self._emit("chat:clear", {"threadId": thread_id})
            self._threads[thread_id] = []
            return
        if self._on_slash_command:
            self._on_slash_command(command, args, thread_id)

    def _on_thread_create(self, data: Any, _event_type: str, _label: str) -> None:
        """Create a new thread."""
        thread_id = f"thread_{uuid.uuid4().hex[:8]}"
        title = data.get("title", f"Chat {len(self._threads) + 1}")
        self._threads[thread_id] = []
        self._thread_titles[thread_id] = title
        self._active_thread = thread_id
        self._emit(
            "chat:update-thread-list",
            {"threads": self._build_thread_list()},
        )
        self._emit("chat:switch-thread", {"threadId": thread_id})
        self._emit("chat:clear", {})

    def _on_thread_switch(self, data: Any, _event_type: str, _label: str) -> None:
        """Switch to an existing thread."""
        thread_id = data.get("threadId", "")
        if thread_id not in self._threads:
            return
        self._active_thread = thread_id
        self._emit("chat:switch-thread", {"threadId": thread_id})
        self._emit("chat:clear", {})
        for msg in self._threads.get(thread_id, []):
            msg_id = f"msg_{uuid.uuid4().hex[:8]}"
            role = msg.get("role", "assistant")
            payload: dict[str, Any] = {
                "messageId": msg_id,
                "text": msg.get("text", ""),
                "threadId": thread_id,
            }
            if role == "user":
                payload["role"] = "user"
            self._emit("chat:assistant-message", payload)

    def _on_thread_delete(self, data: Any, _event_type: str, _label: str) -> None:
        """Delete a thread."""
        thread_id = data.get("threadId", "")
        self._threads.pop(thread_id, None)
        self._thread_titles.pop(thread_id, None)
        self._cancel_events.pop(thread_id, None)
        if self._active_thread == thread_id:
            self._active_thread = next(iter(self._threads), "")
        self._emit(
            "chat:update-thread-list",
            {"threads": self._build_thread_list()},
        )
        if self._active_thread:
            self._emit("chat:switch-thread", {"threadId": self._active_thread})

    def _on_thread_rename(self, data: Any, _event_type: str, _label: str) -> None:
        """Rename a thread."""
        thread_id = data.get("threadId", "")
        new_title = data.get("title", "")
        if thread_id in self._thread_titles and new_title:
            self._thread_titles[thread_id] = new_title
        self._emit(
            "chat:update-thread-list",
            {"threads": self._build_thread_list()},
        )

    def _on_settings_change_event(self, data: Any, _event_type: str, _label: str) -> None:
        """Handle settings change."""
        key = data.get("key", "")
        value = data.get("value")
        self._settings_values[key] = value
        if key == "clear-history":
            self._threads[self._active_thread] = []
            self._emit("chat:clear", {})
            return
        if self._on_settings_change:
            self._on_settings_change(key, value)

    def _on_request_state(self, _data: Any, _event_type: str, _label: str) -> None:
        """Respond to initialization request from frontend JS."""
        if self._welcome_message and not self._threads.get(self._active_thread):
            welcome_id = f"msg_{uuid.uuid4().hex[:8]}"
            self._threads.setdefault(self._active_thread, [])
            self._threads[self._active_thread].append(
                {"id": welcome_id, "role": "assistant", "text": self._welcome_message}
            )
        self._emit(
            "chat:state-response",
            {
                "threads": self._build_thread_list(),
                "activeThreadId": self._active_thread,
                "messages": [
                    {
                        "id": m.get("id", f"msg_{uuid.uuid4().hex[:8]}"),
                        "role": m["role"],
                        "content": m.get("text", ""),
                    }
                    for m in self._threads.get(self._active_thread, [])
                ],
            },
        )
        for cmd in self._slash_commands:
            name = getattr(cmd, "name", str(cmd))
            desc = getattr(cmd, "description", "")
            self._emit(
                "chat:register-command",
                {"name": name, "description": desc},
            )
        self._emit(
            "chat:register-command",
            {"name": "/clear", "description": "Clear the conversation"},
        )
        for item in self._settings_items:
            self._emit("chat:register-settings-item", item.model_dump())
        if self._enable_context:
            sources = self._get_context_sources()
            if sources:
                self._emit("chat:context-sources", {"sources": sources})

    def _build_thread_list(self) -> list[dict[str, str]]:
        """Build thread list dicts for the frontend."""
        return [
            {
                "thread_id": tid,
                "title": self._thread_titles.get(tid, f"Chat {i + 1}"),
            }
            for i, tid in enumerate(self._threads)
        ]
