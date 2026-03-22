"""High-level ChatManager — zero-boilerplate orchestrator for the chat component.

The ``ChatManager`` abstracts away threading, event wiring, thread CRUD,
streaming, cancellation, and state sync.  Developers provide a handler
function and the manager does the rest.

Minimal usage::

    from pywry import PyWry, build_chat_html, Toolbar, Div, HtmlContent

    app = PyWry(title="My Chat")


    def my_handler(messages, ctx):
        # Call your LLM API here and yield chunks
        for chunk in call_llm(messages):
            yield chunk


    chat = ChatManager(handler=my_handler)
    widget = app.show(
        HtmlContent(html="<h1>App</h1>"),
        toolbars=[chat.toolbar()],
        callbacks=chat.callbacks(),
    )
    chat.bind(widget)
    app.block()

The handler function can be:

- A **sync function** returning ``str`` — sends a complete message.
- A **sync generator** yielding ``str`` chunks — streams token-by-token.
- A **sync generator** yielding ``ChatResponse`` objects — streams tokens
  plus tool calls, citations, artifacts, and status updates.
- An **async** variant of any of the above.

The ``ChatContext`` object passed to the handler contains the thread ID,
current settings, cancel event (for cooperative cancellation), system
prompt, model, and temperature.
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

from pydantic import BaseModel, Field, field_validator


log = logging.getLogger(__name__)


# =============================================================================
# Protocol Models — rich responses from handlers
# =============================================================================


class ToolCallResponse(BaseModel):
    """Handler requests a tool invocation to be shown in the UI.

    Attributes
    ----------
    type : Literal["tool_call"]
        Response discriminator for tool-call UI events.
    tool_id : str
        Stable identifier used to correlate a later tool result.
    name : str
        Tool name displayed to the user and routed by the handler.
    arguments : dict[str, Any]
        Structured tool arguments associated with the invocation.
    """

    type: Literal["tool_call"] = "tool_call"
    tool_id: str = Field(default_factory=lambda: f"call_{uuid.uuid4().hex[:8]}")
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolResultResponse(BaseModel):
    """Result of a tool invocation shown in the UI.

    Attributes
    ----------
    type : Literal["tool_result"]
        Response discriminator for tool-result UI events.
    tool_id : str
        Identifier of the tool call this result satisfies.
    result : str
        Human-readable tool output rendered in the transcript.
    is_error : bool
        Indicates the tool invocation failed.
    """

    type: Literal["tool_result"] = "tool_result"
    tool_id: str
    result: str = ""
    is_error: bool = False


class CitationResponse(BaseModel):
    """Citation or source reference attached to a response.

    Attributes
    ----------
    type : Literal["citation"]
        Response discriminator for citation UI events.
    url : str
        Citation URL shown to the user.
    title : str
        Human-readable citation title.
    snippet : str
        Supporting excerpt associated with the citation.
    """

    type: Literal["citation"] = "citation"
    url: str = ""
    title: str = ""
    snippet: str = ""

    @field_validator("url")
    @classmethod
    def _block_dangerous_schemes(cls, v: str) -> str:
        """Reject unsafe citation URL schemes.

        Parameters
        ----------
        v : str
            Candidate citation URL.

        Returns
        -------
        str
            The original URL when it is safe to render.

        Raises
        ------
        ValueError
            Raised when the URL uses the ``javascript:`` scheme.
        """
        import re

        if re.match(r"\s*javascript\s*:", v, re.IGNORECASE):
            raise ValueError("javascript: URLs are not allowed")
        return v


class _ArtifactBase(BaseModel):
    """Base class for all artifact types yielded from handlers.

    Artifacts are rendered as standalone blocks in the chat UI — they are
    **not** streamed token-by-token and are **not** stored in conversation
    history.  Each subclass carries type-specific fields and the dispatch
    layer in ``_handle_stream()`` maps them to the correct JS renderer.
    """

    type: Literal["artifact"] = "artifact"
    artifact_type: str = ""
    title: str = ""


class CodeArtifact(_ArtifactBase):
    """Code snippet artifact rendered with syntax highlighting.

    Attributes
    ----------
    artifact_type : Literal["code"]
        Artifact subtype discriminator.
    content : str
        Source code or text snippet to render.
    language : str
        Optional language hint for syntax highlighting.
    """

    artifact_type: Literal["code"] = "code"
    content: str = ""
    language: str = ""


class MarkdownArtifact(_ArtifactBase):
    """Markdown artifact rendered as formatted HTML.

    Attributes
    ----------
    artifact_type : Literal["markdown"]
        Artifact subtype discriminator.
    content : str
        Markdown source to render.
    """

    artifact_type: Literal["markdown"] = "markdown"
    content: str = ""


class HtmlArtifact(_ArtifactBase):
    """Raw HTML artifact rendered in a sandboxed container.

    Attributes
    ----------
    artifact_type : Literal["html"]
        Artifact subtype discriminator.
    content : str
        Raw HTML content to render.
    """

    artifact_type: Literal["html"] = "html"
    content: str = ""


class TableArtifact(_ArtifactBase):
    """Tabular data rendered as an AG Grid widget.

    Accepts the same data formats as ``normalize_data()`` in grid.py:
    pandas DataFrame, list of dicts, dict of lists, or single dict.

    Attributes
    ----------
    artifact_type : Literal["table"]
        Artifact subtype discriminator.
    data : list[dict[str, Any]] | dict[str, Any]
        Table rows or source object to normalize into rows.
    column_defs : list[dict[str, Any]] | None
        Optional AG Grid column definitions.
    grid_options : dict[str, Any] | None
        Optional AG Grid configuration overrides.
    height : str
        CSS height used by the table container.
    """

    artifact_type: Literal["table"] = "table"
    data: list[dict[str, Any]] | dict[str, Any] = Field(default_factory=list)
    column_defs: list[dict[str, Any]] | None = None
    grid_options: dict[str, Any] | None = None
    height: str = "400px"


class PlotlyArtifact(_ArtifactBase):
    """Plotly chart artifact rendered as an interactive widget.

    ``figure`` accepts a standard Plotly figure dict:
    ``{"data": [...traces], "layout": {...}, "config": {...}}``.

    Attributes
    ----------
    artifact_type : Literal["plotly"]
        Artifact subtype discriminator.
    figure : dict[str, Any]
        Plotly figure payload passed to the frontend renderer.
    height : str
        CSS height used by the chart container.
    """

    artifact_type: Literal["plotly"] = "plotly"
    figure: dict[str, Any] = Field(default_factory=dict)
    height: str = "400px"


class ImageArtifact(_ArtifactBase):
    """Image artifact rendered as an ``<img>`` element.

    ``url`` can be a data URI (``data:image/png;base64,...``) or an
    HTTP(S) URL.

    Attributes
    ----------
    artifact_type : Literal["image"]
        Artifact subtype discriminator.
    url : str
        Image URL or data URI.
    alt : str
        Alternate text for the rendered image.
    """

    artifact_type: Literal["image"] = "image"
    url: str = ""
    alt: str = ""

    @field_validator("url")
    @classmethod
    def _block_dangerous_schemes(cls, v: str) -> str:
        """Reject unsafe image URL schemes.

        Parameters
        ----------
        v : str
            Candidate image URL.

        Returns
        -------
        str
            The original URL when it is safe to render.

        Raises
        ------
        ValueError
            Raised when the URL uses the ``javascript:`` scheme.
        """
        import re

        if re.match(r"\s*javascript\s*:", v, re.IGNORECASE):
            raise ValueError("javascript: URLs are not allowed")
        return v


class JsonArtifact(_ArtifactBase):
    """Structured data rendered as a collapsible JSON tree.

    Attributes
    ----------
    artifact_type : Literal["json"]
        Artifact subtype discriminator.
    data : Any
        Arbitrary JSON-serializable payload to display.
    """

    artifact_type: Literal["json"] = "json"
    data: Any = None


# Backward-compat alias
ArtifactResponse = CodeArtifact


class StatusResponse(BaseModel):
    """Transient status message shown inline in the UI.

    Attributes
    ----------
    type : Literal["status"]
        Response discriminator for status updates.
    text : str
        Human-readable status text.
    """

    type: Literal["status"] = "status"
    text: str = ""


class ThinkingResponse(BaseModel):
    """Streaming thinking or reasoning chunk.

    Rendered as a collapsible inline block in the UI.  Thinking tokens
    are streamed in real-time and are NOT stored in conversation history.
    The block auto-collapses when the handler finishes.

    Attributes
    ----------
    type : Literal["thinking"]
        Response discriminator for thinking chunks.
    text : str
        Incremental reasoning text to render.
    """

    type: Literal["thinking"] = "thinking"
    text: str = ""


class TextChunkResponse(BaseModel):
    """Explicit text chunk alternative to yielding bare strings.

    Attributes
    ----------
    type : Literal["text"]
        Response discriminator for text chunks.
    text : str
        Incremental assistant text to append to the transcript.
    """

    type: Literal["text"] = "text"
    text: str = ""


class TodoItem(BaseModel):
    """Single todo item in the agent's task list.

    Rendered as a collapsible list above the chat input bar.
    The agent manages items; the user can clear the list.

    Attributes
    ----------
    id : int | str
        Stable todo-item identifier.
    title : str
        User-visible todo label.
    status : Literal["not-started", "in-progress", "completed"]
        Current progress state for the item.
    """

    id: int | str
    title: str
    status: Literal["not-started", "in-progress", "completed"] = "not-started"


class TodoUpdateResponse(BaseModel):
    """Push the full todo list to the UI.

    Yielded from a handler to update the todo list above the input bar.
    The list is NOT stored in conversation history.

    Attributes
    ----------
    type : Literal["todo"]
        Response discriminator for todo-list updates.
    items : list[TodoItem]
        Full replacement set of todo items to display.
    """

    type: Literal["todo"] = "todo"
    items: list[TodoItem] = Field(default_factory=list)


class InputRequiredResponse(BaseModel):
    """Pause generation to request user input mid-stream.

    When yielded from a handler, the current streaming batch is finalized
    and the chat input is re-enabled so the user can respond.  The handler
    then calls ``ctx.wait_for_input()`` to block until the response arrives.

    Compatible with:

    - **OpenAI API**: maps to the pattern where the assistant asks a
      clarifying question and the conversation continues with the user's
      reply.
    - **MCP A2A**: maps to Task status ``input_required`` — the agent
      pauses execution until the client supplies additional input.

    Example::

        def handler(messages, ctx):
            yield "Which file should I modify?"
            yield InputRequiredResponse(placeholder="Enter filename...")
            filename = ctx.wait_for_input()
            if not filename:
                return  # Cancelled
            yield f"Modifying **{filename}**..."

    Attributes
    ----------
    type : Literal["input_required"]
        Response discriminator for interactive pauses.
    prompt : str
        Optional prompt shown above the resumed input control.
    placeholder : str
        Placeholder text for the temporary input control.
    request_id : str
        Stable identifier for correlating the user response.
    input_type : Literal["text", "buttons", "radio"]
        Input control variant to render.
    options : list[str] | None
        Choices for button or radio-style prompts.
    """

    type: Literal["input_required"] = "input_required"
    prompt: str = ""
    placeholder: str = "Type your response..."
    request_id: str = Field(default_factory=lambda: f"input_{uuid.uuid4().hex[:8]}")
    input_type: Literal["text", "buttons", "radio"] = "text"
    options: list[str] | None = None


# Union of all response types a handler can yield
ChatResponse = (
    str
    | TextChunkResponse
    | ThinkingResponse
    | ToolCallResponse
    | ToolResultResponse
    | CitationResponse
    | _ArtifactBase
    | CodeArtifact
    | MarkdownArtifact
    | HtmlArtifact
    | TableArtifact
    | PlotlyArtifact
    | ImageArtifact
    | JsonArtifact
    | StatusResponse
    | TodoUpdateResponse
    | InputRequiredResponse
)


# =============================================================================
# Attachment — resolved file/widget context for a message
# =============================================================================


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
        For file attachments — the full filesystem path.  The handler
        is responsible for reading/processing the file.
    content : str
        For widget attachments — live data extracted from the component.
        Empty string for file attachments.
    source : str
        Original source identifier (widget ID or path string).
    """

    type: str
    name: str
    path: pathlib.Path | None = None
    content: str = ""
    source: str = ""


# Safety constants for context attachments
_MAX_ATTACHMENTS = 20  # max attachments per message


# =============================================================================
# ChatContext — passed to every handler invocation
# =============================================================================


@dataclass
class ChatContext:
    """Context object passed to handler functions.

    Attributes
    ----------
    thread_id : str
        Active thread ID.
    message_id : str
        The assistant message ID being generated.
    settings : dict
        Current settings values (from the settings dropdown).
    cancel_event : threading.Event
        Set when the user clicks Stop. Check this between chunks.
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

    # ---- convenience helpers for the tool-based context pattern ----

    @property
    def attachment_summary(self) -> str:
        """One-line summary of attached context for system/user prompts.

        Returns an empty string when there are no attachments.
        Example output::

            Attached context: report.csv (file: C:/data/report.csv), @Sales Data (widget)

        Returns
        -------
        str
            Summary line suitable for prompt construction.
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

        For file attachments with a ``path`` (desktop/Tauri), includes only
        the path — the handler is responsible for reading file content.
        For file attachments with ``content`` (browser/inline), includes
        the content directly.
        For widget attachments, includes the extracted content.

        Empty string when there are no attachments.

        Returns
        -------
        str
            Multi-block attachment context ready to insert into prompts.
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

        For file attachments with a ``path`` (desktop/Tauri), returns the
        file path as a string — the handler should read the file itself.
        For file attachments with ``content`` (browser/inline), or widget
        attachments, returns the content directly.

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

    # Internal — used by InputRequiredResponse / wait_for_input()
    _input_event: threading.Event = field(default_factory=threading.Event, init=False, repr=False)
    _input_response: str = field(default="", init=False, repr=False)

    def wait_for_input(self, timeout: float | None = None) -> str:
        """Block until the user provides input via ``InputRequiredResponse``.

        Call this after yielding ``InputRequiredResponse`` to pause the
        handler until the user responds.  Returns the user's text.
        Returns empty string on cancellation or timeout.

        Compatible with both the OpenAI API pattern (tool calls requiring
        user confirmation) and MCP A2A ``input_required`` task status.

        Parameters
        ----------
        timeout : float, optional
            Maximum seconds to wait.  ``None`` means wait indefinitely
            (until user responds or generation is cancelled).

        Returns
        -------
        str
            User-supplied input, or an empty string on cancellation or timeout.
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


# =============================================================================
# SettingsItem — declarative settings menu entries
# =============================================================================


class SettingsItem(BaseModel):
    """Settings menu item shown in the gear dropdown.

    Attributes
    ----------
    id : str
        Stable identifier for the setting.
    label : str
        User-visible label.
    type : Literal["action", "toggle", "select", "range", "separator"]
        Control type rendered in the settings menu.
    value : Any
        Current value or payload associated with the setting.
    options : list[str] | None
        Allowed values for ``select`` controls.
    min : float | None
        Minimum value for ``range`` controls.
    max : float | None
        Maximum value for ``range`` controls.
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


# =============================================================================
# Slash command descriptor
# =============================================================================


class SlashCommandDef(BaseModel):
    """A slash command registration."""

    name: str
    description: str = ""

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        if not self.name.startswith("/"):
            self.name = f"/{self.name}"


# Type alias for message dicts in thread history
MessageDict = dict[str, Any]

# Handler type: receives (messages, context) → str | Iterator[str|ChatResponse]
HandlerFunc = Callable[..., Any]


class _StreamState:
    """Mutable state container for stream text buffering."""

    __slots__ = ("buffer", "full_text", "last_flush", "message_id")

    def __init__(self, message_id: str) -> None:
        self.message_id = message_id
        self.full_text = ""
        self.buffer = ""
        self.last_flush = time.monotonic()


# =============================================================================
# ChatManager
# =============================================================================


class ChatManager:
    """Zero-boilerplate orchestrator for the PyWry chat component.

    Handles all event wiring, thread management, streaming, cancellation,
    and state synchronization.  The developer provides a handler function
    and optional configuration.

    Parameters
    ----------
    handler : callable
        Function that receives ``(messages, ctx)`` where ``messages`` is a
        ``list[dict]`` of conversation history and ``ctx`` is a
        ``ChatContext``.  Can return ``str``, yield ``str`` chunks, or
        yield ``ChatResponse`` objects for rich content.
    system_prompt : str
        System prompt prepended to every request.
    model : str
        Model identifier (passed to handler via context).
    temperature : float
        Temperature (passed to handler via context).
    welcome_message : str
        Markdown message sent when the chat initializes.
    settings : list[SettingsItem]
        Settings items rendered in the gear dropdown.
    slash_commands : list[SlashCommandDef]
        Slash commands registered in the chat input.
    on_slash_command : callable, optional
        Callback ``(command, args, thread_id)`` for slash commands not
        handled by built-in behavior.
    on_settings_change : callable, optional
        Callback ``(key, value)`` when a setting changes.
    show_sidebar : bool
        Show the conversation picker in the header.
    show_settings : bool
        Show the gear icon in the header.
    toolbar_width : str
        CSS width for the chat toolbar.
    toolbar_min_width : str
        CSS min-width for the chat toolbar.
    collapsible : bool
        Whether the chat toolbar is collapsible.
    resizable : bool
        Whether the chat toolbar is resizable.
    include_plotly : bool
        Include Plotly.js library eagerly on initialization.
    include_aggrid : bool
        Include AG Grid library eagerly on initialization.
    aggrid_theme : str
        AG Grid theme name (e.g. ``"alpine"``, ``"quartz"``, ``"balham"``).
    enable_context : bool
        Enable the context attachment system (@ mentions for live widgets).
    enable_file_attach : bool
        Enable the file attachment button (📎), drag-and-drop, and the
        hidden file input.  Independent of ``enable_context``.  Both can
        be enabled simultaneously.
    file_accept_types : list[str] | None
        **Required when** ``enable_file_attach=True``.  Specifies which
        file extensions are allowed, e.g. ``[".csv", ".json", ".xlsx"]``.
        Each entry must be a dot-prefixed extension.  Files that don't
        match are rejected on both the frontend and backend.
    context_allowed_roots : list[str] | None
        Restrict file attachments to these directories.  ``None`` means
        allow any readable path.

    Examples
    --------
    Simplest usage — echo bot::

        def echo(messages, ctx):
            return f"You said: {messages[-1]['text']}"


        chat = ChatManager(handler=echo)

    Streaming generator::

        def stream_handler(messages, ctx):
            for word in call_my_api(messages):
                if ctx.cancel_event.is_set():
                    return
                yield word


        chat = ChatManager(handler=stream_handler)

    Rich responses with tool calls::

        def agent_handler(messages, ctx):
            yield StatusResponse(text="Searching...")
            results = search(messages[-1]["text"])
            yield ToolCallResponse(name="search", arguments={"q": messages[-1]["text"]})
            yield ToolResultResponse(tool_id="...", result=str(results))
            for chunk in summarize(results):
                yield chunk


        chat = ChatManager(handler=agent_handler)
    """

    # ---- Library-supplied tool schema for on-demand context retrieval ----
    # Pass this to your LLM's tools list when ctx.attachments is non-empty.
    # When the LLM calls "get_context", resolve it with ctx.get_attachment(name).
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
                        "description": "The attachment name (from the list of attached items).",
                    },
                },
                "required": ["name"],
            },
        },
    }

    def __init__(
        self,
        handler: HandlerFunc,
        *,
        system_prompt: str = "",
        model: str = "",
        temperature: float = 0.7,
        welcome_message: str = "",
        settings: Sequence[SettingsItem] | None = None,
        slash_commands: Sequence[SlashCommandDef] | None = None,
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
        self._threads: dict[str, list[MessageDict]] = {}
        self._thread_titles: dict[str, str] = {}
        self._active_thread: str = ""
        self._cancel_events: dict[str, threading.Event] = {}
        self._settings_values: dict[str, Any] = {
            s.id: s.value for s in self._settings_items if s.type != "separator"
        }
        self._todo_items: list[TodoItem] = []
        self._pending_inputs: dict[str, dict[str, Any]] = {}
        # When include_aggrid/include_plotly are True the page template
        # already loads the full library via build_aggrid_script /
        # build_plotly_script.  Mark them as "sent" so _inject_*_assets()
        # won't re-inject them through chat:load-assets (which would
        # duplicate the <script> tags and corrupt the already-rendered grid).
        self._aggrid_assets_sent: bool = include_aggrid
        self._plotly_assets_sent: bool = include_plotly
        # Explicitly registered context sources for @mention
        self._context_sources: dict[str, dict[str, Any]] = {}

        # Create default thread
        default_id = f"thread_{uuid.uuid4().hex[:8]}"
        self._threads[default_id] = []
        self._thread_titles[default_id] = "Chat 1"
        self._active_thread = default_id

    # =========================================================================
    # Public API
    # =========================================================================

    def register_context_source(
        self,
        component_id: str,
        name: str,
    ) -> None:
        """Register a live dashboard component as an @-mentionable context source.

        When the user types ``@`` in the chat, registered sources appear
        in the autocomplete popup.  When selected and sent, the frontend
        extracts live data from the component and includes it in the
        message.

        Parameters
        ----------
        component_id
            The unique ID of the component (e.g. the ``grid_id`` passed to
            ``build_grid_config``, the ``chart_id`` passed to
            ``build_plotly_init_script``, a toolbar's ``component_id``, etc.).
        name
            Human-readable label shown in the popup (e.g. ``"Sales Data"``).
        """
        self._context_sources[component_id] = {
            "name": name,
        }

    def bind(self, widget: Any) -> None:
        """Bind to a widget after ``app.show()``.

        Must be called before ``app.block()``.  Pushes initial state
        (welcome message, slash commands, context sources) immediately
        so the frontend doesn't miss the ``chat:request-state`` event
        that may have fired before the widget was bound.
        """
        self._widget = widget
        # Push initial state now that we can emit.  The JS may have already
        # sent ``chat:request-state`` while ``_widget`` was still None,
        # causing ``_emit`` to silently drop the response.
        self._on_request_state({}, "chat:request-state", "")

    def toolbar(
        self,
        *,
        position: Literal["header", "footer", "top", "bottom", "left", "right", "inside"] = "right",
    ) -> Any:
        """Build a Toolbar containing the chat panel.

        Returns a ``Toolbar`` instance ready to pass to ``app.show(toolbars=...)``.
        """
        from .chat import build_chat_html
        from .toolbar import Div, Toolbar as ToolbarCls

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
            style=f"width: {self._toolbar_width}; min-width: {self._toolbar_min_width};",
            items=[
                Div(
                    content=html,
                    component_id="chat-container",
                    style="width: 100%; height: 100%; display: flex; flex-direction: column;",
                ),
            ],
        )

    def callbacks(self) -> dict[str, Callable[..., Any]]:
        """Return the callbacks dict to pass to ``app.show(callbacks=...)``.

        This wires up ALL chat events automatically.
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

    # =========================================================================
    # Event handlers (wired automatically via callbacks())
    # =========================================================================

    def _emit(self, event: str, data: dict[str, Any]) -> None:
        """Emit an event via the bound widget."""
        if self._widget is not None:
            self._widget.emit(event, data)

    def _emit_fire(self, event: str, data: dict[str, Any]) -> None:
        """Fire-and-forget emit — non-blocking, for high-frequency streaming."""
        if self._widget is not None:
            if hasattr(self._widget, "emit_fire"):
                self._widget.emit_fire(event, data)
            else:
                self._widget.emit(event, data)

    def _inject_aggrid_assets(self) -> None:
        """Lazy-inject AG Grid JS/CSS on first table artifact."""
        if self._aggrid_assets_sent:
            return
        from .assets import get_aggrid_css, get_aggrid_defaults_js, get_aggrid_js
        from .models import ThemeMode

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
        from .assets import get_plotly_defaults_js, get_plotly_js, get_plotly_templates_js

        self._emit(
            "chat:load-assets",
            {
                "scripts": [get_plotly_js(), get_plotly_templates_js(), get_plotly_defaults_js()],
                "styles": [],
            },
        )
        self._plotly_assets_sent = True

    # =========================================================================
    # Context resolution — files & widgets → Attachment objects
    # =========================================================================

    def _is_accepted_file(self, filename: str) -> bool:
        """Check if the file extension is in the developer's allowed list."""
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
        """Create an Attachment for a widget/component reference.

        When *content* is provided (extracted by the frontend from the
        live component), it is used directly.  Otherwise falls back to
        auto-discovered inline widgets.
        """
        # 1. Content already extracted by frontend — use it directly
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

        # 2. Fall back to auto-discovered inline widgets
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
        """Resolve raw attachment dicts from the frontend into Attachments.

        **Desktop (Tauri)**: file attachments carry a ``path`` — a full
        filesystem path.  The handler is responsible for reading file
        content.

        **Browser (inline / iframe)**: the File API cannot expose
        filesystem paths, so file attachments carry ``content`` instead
        (read by the frontend via ``FileReader``).

        Widget attachments always carry ``content`` extracted by the
        frontend from the live component.
        """
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
                    log.warning(
                        "File %r rejected — extension not in file_accept_types",
                        file_name,
                    )
                    continue
                if not file_path and not file_content:
                    log.warning("File %r has no path or content, skipping", file_name)
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
        """List available context sources for the @ mention popup."""
        sources: list[dict[str, str]] = []

        # 1. Explicitly registered component sources
        for src_id, src in self._context_sources.items():
            sources.append(
                {
                    "id": src_id,
                    "name": src["name"],
                    "type": "widget",
                    "componentId": src_id,
                }
            )

        # 2. Auto-discovered inline widgets
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

    def _dispatch_artifact(
        self,
        item: _ArtifactBase,
        message_id: str,
        thread_id: str,
    ) -> None:
        """Dispatch an artifact to the frontend with type-specific payloads.

        For TableArtifact / PlotlyArtifact, assets are lazy-injected on
        first use and data is normalized before sending.
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
            from .grid import normalize_data

            data = item.data
            # Support pandas DataFrames via duck typing
            if (hasattr(data, "to_dict") and hasattr(data, "columns")) or isinstance(
                data, (dict, list)
            ):
                grid_data = normalize_data(data)
            else:
                grid_data = normalize_data(data)

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

        elif isinstance(item, ImageArtifact):
            base["url"] = item.url
            base["alt"] = item.alt

        elif isinstance(item, JsonArtifact):
            base["data"] = item.data

        self._emit("chat:artifact", base)

    def _on_user_message(self, data: Any, _event_type: str, _label: str) -> None:
        """Handle incoming user message — run handler in background thread."""
        text = data.get("text", "").strip()
        thread_id = data.get("threadId", self._active_thread) or self._active_thread
        if not text:
            return

        self._active_thread = thread_id

        # Store user message
        self._threads.setdefault(thread_id, [])
        self._threads[thread_id].append({"role": "user", "text": text})

        # Prepare generation
        message_id = f"msg_{uuid.uuid4().hex[:8]}"
        cancel = threading.Event()
        self._cancel_events[thread_id] = cancel

        # Show typing
        self._emit("chat:typing-indicator", {"typing": True, "threadId": thread_id})

        # Resolve attachments (if context is enabled)
        raw_attachments = data.get("attachments", [])
        attachments = self._resolve_attachments(raw_attachments) if raw_attachments else []

        # Build context
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

        # Build messages list for handler
        messages = list(self._threads.get(thread_id, []))

        # Run in background thread
        t = threading.Thread(
            target=self._run_handler,
            args=(messages, ctx, message_id, thread_id, cancel),
            daemon=True,
        )
        t.start()

    def _inject_context(
        self,
        messages: list[MessageDict],
        ctx: ChatContext,
        message_id: str,
        thread_id: str,
    ) -> list[MessageDict]:
        """Inject attachment context into messages and emit tool-call events."""
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
            if att.type == "file" and att.path:
                result_text = f"Attached {label} → {att.path}"
            else:
                result_text = f"Attached {label}"
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
        """Route handler return value to the appropriate processing path."""
        if inspect.isgenerator(result):
            self._emit("chat:typing-indicator", {"typing": False, "threadId": thread_id})
            self._handle_stream(result, message_id, thread_id, cancel, ctx=ctx)
        elif inspect.isasyncgen(result):
            asyncio.run(
                self._handle_async_stream(
                    result,
                    message_id,
                    thread_id,
                    cancel,
                    ctx=ctx,
                )
            )
        elif inspect.iscoroutine(result):
            resolved = asyncio.run(result)
            if inspect.isasyncgen(resolved):
                asyncio.run(
                    self._handle_async_stream(
                        resolved,
                        message_id,
                        thread_id,
                        cancel,
                        ctx=ctx,
                    )
                )
            elif isinstance(resolved, str):
                self._emit("chat:typing-indicator", {"typing": False, "threadId": thread_id})
                self._handle_complete(resolved, message_id, thread_id)
            else:
                self._emit("chat:typing-indicator", {"typing": False, "threadId": thread_id})
                self._handle_complete(str(resolved), message_id, thread_id)
        elif isinstance(result, str):
            self._emit("chat:typing-indicator", {"typing": False, "threadId": thread_id})
            self._handle_complete(result, message_id, thread_id)
        elif isinstance(result, Iterator):
            self._emit("chat:typing-indicator", {"typing": False, "threadId": thread_id})
            self._handle_stream(result, message_id, thread_id, cancel, ctx=ctx)
        else:
            self._emit("chat:typing-indicator", {"typing": False, "threadId": thread_id})
            self._handle_complete(str(result), message_id, thread_id)

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
            result = self._handler(messages, ctx)
            self._dispatch_handler_result(result, message_id, thread_id, cancel, ctx)
        except Exception as exc:
            # Send error as assistant message
            self._emit("chat:typing-indicator", {"typing": False, "threadId": thread_id})
            error_text = f"Error: {exc}"
            self._emit(
                "chat:assistant-message",
                {
                    "messageId": message_id,
                    "text": error_text,
                    "threadId": thread_id,
                },
            )
            self._threads.setdefault(thread_id, [])
            self._threads[thread_id].append({"role": "assistant", "text": error_text})
        finally:
            self._cancel_events.pop(thread_id, None)

    def _handle_complete(self, text: str, message_id: str, thread_id: str) -> None:
        """Send a complete (non-streamed) assistant message."""
        self._emit(
            "chat:assistant-message",
            {
                "messageId": message_id,
                "text": text,
                "threadId": thread_id,
            },
        )
        self._threads.setdefault(thread_id, [])
        self._threads[thread_id].append({"role": "assistant", "text": text})

    # Streaming flush constants — tune for smooth rendering
    _STREAM_FLUSH_INTERVAL: float = 0.030  # 30 ms between flushes
    _STREAM_MAX_BUFFER: int = 300  # flush immediately above this many chars

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
        """Add text to the stream buffer and auto-flush if threshold reached."""
        state.buffer += text
        state.full_text += text
        if state.buffer and (
            time.monotonic() - state.last_flush >= self._STREAM_FLUSH_INTERVAL
            or len(state.buffer) >= self._STREAM_MAX_BUFFER
        ):
            self._flush_buffer(state)

    def _handle_input_required(
        self,
        item: InputRequiredResponse,
        state: _StreamState,
        thread_id: str,
        ctx: ChatContext | None,
    ) -> None:
        """Handle an InputRequiredResponse during streaming."""
        self._emit_fire(
            "chat:thinking-done",
            {
                "messageId": state.message_id,
                "threadId": thread_id,
            },
        )
        self._emit_fire(
            "chat:stream-chunk",
            {
                "messageId": state.message_id,
                "chunk": "",
                "done": True,
            },
        )
        if state.full_text:
            self._threads.setdefault(thread_id, [])
            self._threads[thread_id].append(
                {
                    "role": "assistant",
                    "text": state.full_text,
                }
            )
            state.full_text = ""
        if ctx is not None:
            ctx._input_event.clear()
            self._pending_inputs[item.request_id] = {
                "ctx": ctx,
                "thread_id": thread_id,
            }
        self._emit_fire(
            "chat:input-required",
            {
                "messageId": state.message_id,
                "threadId": thread_id,
                "requestId": item.request_id,
                "prompt": item.prompt,
                "placeholder": item.placeholder,
                "inputType": item.input_type,
                "options": item.options or [],
            },
        )
        state.message_id = f"msg_{uuid.uuid4().hex[:8]}"

    def _process_stream_item(
        self,
        item: Any,
        state: _StreamState,
        thread_id: str,
        ctx: ChatContext | None,
    ) -> None:
        """Dispatch a single stream item to the appropriate handler."""
        if isinstance(item, (str, TextChunkResponse)):
            self._buffer_text(state, item if isinstance(item, str) else item.text)

        elif isinstance(item, ThinkingResponse):
            self._flush_buffer(state)
            self._emit_fire(
                "chat:thinking-chunk",
                {
                    "messageId": state.message_id,
                    "text": item.text,
                    "threadId": thread_id,
                },
            )

        elif isinstance(item, StatusResponse):
            self._flush_buffer(state)
            self._emit_fire(
                "chat:status-update",
                {
                    "messageId": state.message_id,
                    "text": item.text,
                    "threadId": thread_id,
                },
            )

        elif isinstance(item, ToolCallResponse):
            self._flush_buffer(state)
            self._emit_fire(
                "chat:tool-call",
                {
                    "messageId": state.message_id,
                    "toolId": item.tool_id,
                    "name": item.name,
                    "arguments": item.arguments,
                    "threadId": thread_id,
                },
            )

        elif isinstance(item, ToolResultResponse):
            self._flush_buffer(state)
            self._emit_fire(
                "chat:tool-result",
                {
                    "messageId": state.message_id,
                    "toolId": item.tool_id,
                    "result": item.result,
                    "isError": item.is_error,
                    "threadId": thread_id,
                },
            )

        elif isinstance(item, CitationResponse):
            self._flush_buffer(state)
            self._emit_fire(
                "chat:citation",
                {
                    "messageId": state.message_id,
                    "url": item.url,
                    "title": item.title,
                    "snippet": item.snippet,
                    "threadId": thread_id,
                },
            )

        elif isinstance(item, _ArtifactBase):
            self._flush_buffer(state)
            self._dispatch_artifact(item, state.message_id, thread_id)

        elif isinstance(item, TodoUpdateResponse):
            self._flush_buffer(state)
            self._todo_items = list(item.items)
            self._emit_fire(
                "chat:todo-update",
                {
                    "items": [t.model_dump() for t in item.items],
                },
            )

        elif isinstance(item, InputRequiredResponse):
            self._flush_buffer(state)
            self._handle_input_required(item, state, thread_id, ctx)

    def _finalize_stream(self, state: _StreamState, thread_id: str) -> None:
        """Flush remaining buffer and send stream-done events."""
        self._flush_buffer(state)
        self._emit_fire(
            "chat:thinking-done",
            {
                "messageId": state.message_id,
                "threadId": thread_id,
            },
        )
        self._emit_fire(
            "chat:stream-chunk",
            {
                "messageId": state.message_id,
                "chunk": "",
                "done": True,
            },
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
                {
                    "role": "assistant",
                    "text": state.full_text,
                    "stopped": True,
                }
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
        """Stream chunks from a generator, handling rich response types."""
        state = _StreamState(message_id)

        for item in gen:
            if cancel.is_set():
                self._handle_cancel(state, thread_id)
                return
            self._process_stream_item(item, state, thread_id, ctx)

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
        """Stream chunks from an async generator, handling rich response types."""
        state = _StreamState(message_id)
        typing_hidden = False

        async for item in agen:
            if not typing_hidden:
                typing_hidden = True
                self._emit("chat:typing-indicator", {"typing": False, "threadId": thread_id})
            if cancel.is_set():
                self._handle_cancel(state, thread_id)
                return
            self._process_stream_item(item, state, thread_id, ctx)

        if not typing_hidden:
            self._emit("chat:typing-indicator", {"typing": False, "threadId": thread_id})
        self._finalize_stream(state, thread_id)

    def _on_stop_generation(self, data: Any, _event_type: str, _label: str) -> None:
        """Cancel active generation."""
        thread_id = data.get("threadId", self._active_thread)
        cancel = self._cancel_events.get(thread_id)
        if cancel:
            cancel.set()

    def _on_todo_clear(self, _data: Any, _event_type: str, _label: str) -> None:
        """Handle user clearing the todo list."""
        self._todo_items = []
        self._emit("chat:todo-update", {"items": []})

    def _on_input_response(self, data: Any, _event_type: str, _label: str) -> None:
        """Handle user's response to an InputRequiredResponse."""
        text = data.get("text", "").strip()
        request_id = data.get("requestId", "")
        thread_id = data.get("threadId", self._active_thread) or self._active_thread

        pending = self._pending_inputs.pop(request_id, None)
        if pending is None:
            return

        # Store user's response in thread history
        self._threads.setdefault(thread_id, [])
        self._threads[thread_id].append({"role": "user", "text": text})

        # Resume the blocked handler
        ctx = pending.get("ctx")
        if ctx is not None:
            ctx._input_response = text
            ctx._input_event.set()

    def _on_slash_command_event(self, data: Any, _event_type: str, _label: str) -> None:
        """Handle slash command from frontend."""
        command = data.get("command", "")
        args = data.get("args", "")
        thread_id = data.get("threadId", self._active_thread) or self._active_thread

        # Built-in /clear
        if command == "/clear":
            self._emit("chat:clear", {"threadId": thread_id})
            self._threads[thread_id] = []
            return

        # Delegate to user callback
        if self._on_slash_command:
            self._on_slash_command(command, args, thread_id)

    def _on_thread_create(self, data: Any, _event_type: str, _label: str) -> None:
        """Create a new thread."""
        thread_id = f"thread_{uuid.uuid4().hex[:8]}"
        title = data.get("title", f"Chat {len(self._threads) + 1}")
        self._threads[thread_id] = []
        self._thread_titles[thread_id] = title
        self._active_thread = thread_id

        self._emit("chat:update-thread-list", {"threads": self._build_thread_list()})
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

        # Re-send message history for this thread
        for msg in self._threads.get(thread_id, []):
            msg_id = f"msg_{uuid.uuid4().hex[:8]}"
            role = msg.get("role", "assistant")
            if role == "user":
                # User messages need to appear too
                self._emit(
                    "chat:assistant-message",
                    {
                        "messageId": msg_id,
                        "text": msg.get("text", ""),
                        "threadId": thread_id,
                        "role": "user",
                    },
                )
            else:
                self._emit(
                    "chat:assistant-message",
                    {
                        "messageId": msg_id,
                        "text": msg.get("text", ""),
                        "threadId": thread_id,
                    },
                )

    def _on_thread_delete(self, data: Any, _event_type: str, _label: str) -> None:
        """Delete a thread."""
        thread_id = data.get("threadId", "")
        self._threads.pop(thread_id, None)
        self._thread_titles.pop(thread_id, None)
        self._cancel_events.pop(thread_id, None)

        if self._active_thread == thread_id:
            self._active_thread = next(iter(self._threads), "")

        self._emit("chat:update-thread-list", {"threads": self._build_thread_list()})
        if self._active_thread:
            self._emit("chat:switch-thread", {"threadId": self._active_thread})

    def _on_thread_rename(self, data: Any, _event_type: str, _label: str) -> None:
        """Rename a thread."""
        thread_id = data.get("threadId", "")
        new_title = data.get("title", "")
        if thread_id in self._thread_titles and new_title:
            self._thread_titles[thread_id] = new_title
        self._emit("chat:update-thread-list", {"threads": self._build_thread_list()})

    def _on_settings_change_event(self, data: Any, _event_type: str, _label: str) -> None:
        """Handle settings change."""
        key = data.get("key", "")
        value = data.get("value")

        # Update internal tracking
        self._settings_values[key] = value

        # Built-in: clear-history action
        if key == "clear-history":
            self._threads[self._active_thread] = []
            self._emit("chat:clear", {})
            return

        # Delegate to user callback
        if self._on_settings_change:
            self._on_settings_change(key, value)

    def _on_request_state(self, _data: Any, _event_type: str, _label: str) -> None:
        """Respond to initialization request from frontend JS."""
        # Pre-populate welcome message into thread so it's included in state
        if self._welcome_message and not self._threads.get(self._active_thread):
            welcome_id = f"msg_{uuid.uuid4().hex[:8]}"
            self._threads.setdefault(self._active_thread, [])
            self._threads[self._active_thread].append(
                {
                    "id": welcome_id,
                    "role": "assistant",
                    "text": self._welcome_message,
                }
            )

        # Push thread list + active thread (includes welcome if just added)
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

        # Register slash commands
        for cmd in self._slash_commands:
            self._emit(
                "chat:register-command",
                {
                    "name": cmd.name,
                    "description": cmd.description,
                },
            )
        # Always register /clear
        self._emit(
            "chat:register-command",
            {
                "name": "/clear",
                "description": "Clear the conversation",
            },
        )

        # Register settings items
        for item in self._settings_items:
            self._emit("chat:register-settings-item", item.model_dump())

        # Send available context sources for @mention popup
        if self._enable_context:
            sources = self._get_context_sources()
            if sources:
                self._emit("chat:context-sources", {"sources": sources})

    def update_todos(self, items: list[TodoItem]) -> None:
        """Push a todo list update to the chat UI.

        Call from handlers, slash commands, or any callback.
        """
        self._todo_items = list(items)
        self._emit(
            "chat:todo-update",
            {
                "items": [item.model_dump() for item in self._todo_items],
            },
        )

    def clear_todos(self) -> None:
        """Clear the todo list."""
        self._todo_items = []
        self._emit("chat:todo-update", {"items": []})

    def send_message(self, text: str, thread_id: str | None = None) -> None:
        """Send a programmatic assistant message to the chat.

        Useful from slash-command handlers or other callbacks that want to
        inject a message directly (without going through the handler).
        """
        tid = thread_id or self._active_thread
        msg_id = f"msg_{uuid.uuid4().hex[:8]}"
        self._emit(
            "chat:assistant-message",
            {
                "messageId": msg_id,
                "text": text,
                "threadId": tid,
            },
        )
        self._threads.setdefault(tid, [])
        self._threads[tid].append({"role": "assistant", "text": text})

    # =========================================================================
    # Helpers
    # =========================================================================

    def _build_thread_list(self) -> list[dict[str, str]]:
        """Build thread list dicts for the frontend."""
        return [
            {
                "thread_id": tid,
                "title": self._thread_titles.get(tid, f"Chat {i + 1}"),
            }
            for i, tid in enumerate(self._threads)
        ]
