"""Pydantic models and constants for the Chat component.

This module defines the data models for chat messages, threads,
slash commands, configuration, and the generation handle used
for cooperative stop-generation cancellation.
"""

from __future__ import annotations

import asyncio
import time
import uuid

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


# =============================================================================
# Resource Safety Constants
# =============================================================================

MAX_RENDERED_MESSAGES = 200
"""DOM nodes kept in viewport (JS-side cap)."""

MAX_MESSAGE_SIZE = 500_000
"""Characters per message before truncation in UI."""

MAX_CODE_BLOCK_LINES = 500
"""Lines per code block before collapse in UI."""

MAX_CONTENT_LENGTH = 100_000
"""Characters per ChatMessage.content (model validation)."""

MAX_MESSAGES_PER_THREAD = 1_000
"""Messages per thread before oldest are evicted."""

MAX_THREADS_PER_WIDGET = 50
"""Threads per widget before rejection."""

STREAM_TIMEOUT_SECONDS = 30
"""No-chunk timeout — force-cancel if LLM stalls."""

SEND_COOLDOWN_MS = 1_000
"""Minimum interval between user messages (JS-side)."""

EVENT_QUEUE_MAX_SIZE = 500
"""Per-widget chat event queue size."""

TASK_REAPER_INTERVAL = 600
"""Orphan task check interval in seconds."""

GENERATION_HANDLE_TTL = 300
"""Seconds before a GenerationHandle auto-expires."""


# =============================================================================
# Content Parts — MCP content type forward-compat
# =============================================================================


class TextPart(BaseModel):
    """Plain text content part.

    Attributes
    ----------
    type : Literal["text"]
        Discriminator used when serializing mixed chat content parts.
    text : str
        Plain text payload to render in the transcript.
    """

    type: Literal["text"] = "text"
    text: str


class ImagePart(BaseModel):
    """Base64 image content part.

    Attributes
    ----------
    type : Literal["image"]
        Discriminator used when serializing mixed chat content parts.
    data : str
        Base64-encoded image payload.
    mime_type : str
        MIME type for the encoded image payload.
    """

    type: Literal["image"] = "image"
    data: str
    mime_type: str = "image/png"


class ResourceLinkPart(BaseModel):
    """Resource link content part.

    Attributes
    ----------
    type : Literal["resource_link"]
        Discriminator used when serializing mixed chat content parts.
    uri : str
        Resource URI exposed to the frontend or MCP consumer.
    name : str | None
        Optional human-readable label for the resource.
    mime_type : str | None
        Optional MIME type associated with the linked resource.
    """

    type: Literal["resource_link"] = "resource_link"
    uri: str
    name: str | None = None
    mime_type: str | None = None


ChatContentPart = TextPart | ImagePart | ResourceLinkPart


# =============================================================================
# Tool Call Models — OpenAI/Anthropic format for agentic interop
# =============================================================================


class ToolCallFunction(BaseModel):
    """Function call payload embedded in a tool invocation.

    Attributes
    ----------
    name : str
        Tool function name requested by the model.
    arguments : str
        JSON string of tool arguments in provider-native format.
    """

    name: str
    arguments: str = ""


class ToolCall(BaseModel):
    """Tool invocation attached to an assistant message.

    Attributes
    ----------
    id : str
        Stable tool-call identifier used to correlate tool results.
    type : Literal["function"]
        Tool-call type discriminator.
    function : ToolCallFunction
        Function name and serialized arguments requested by the model.
    """

    id: str = Field(default_factory=lambda: f"call_{uuid.uuid4().hex[:12]}")
    type: Literal["function"] = "function"
    function: ToolCallFunction


# =============================================================================
# Core Chat Models
# =============================================================================


class ChatMessage(BaseModel):
    """A single chat message.

    Attributes
    ----------
    role : Literal["user", "assistant", "system", "tool"]
        Semantic role of the message within the conversation.
    content : str | list[ChatContentPart]
        Message body as plain text or structured content parts.
    message_id : str
        Stable message identifier used across UI and backend events.
    timestamp : float
        Unix timestamp when the message was created.
    metadata : dict[str, Any]
        Arbitrary provider- or application-specific metadata.
    tool_calls : list[ToolCall] | None
        Requested tool invocations attached to assistant messages.
    tool_call_id : str | None
        Tool-call identifier when this message is a tool result.
    model : str | None
        Model name that produced the message, when known.
    usage : dict[str, Any] | None
        Token or billing metadata returned by the provider.
    stopped : bool
        Indicates generation stopped early, typically due to cancellation.
    """

    role: Literal["user", "assistant", "system", "tool"]
    content: str | list[ChatContentPart] = ""
    message_id: str = Field(default_factory=lambda: f"msg_{uuid.uuid4().hex[:12]}")
    timestamp: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None
    model: str | None = None
    usage: dict[str, Any] | None = None
    stopped: bool = False

    @field_validator("content")
    @classmethod
    def validate_content_length(cls, v: str | list[ChatContentPart]) -> str | list[ChatContentPart]:
        """Reject content exceeding MAX_CONTENT_LENGTH.

        Parameters
        ----------
        v : str | list[ChatContentPart]
            Candidate message content provided to the model.

        Returns
        -------
        str | list[ChatContentPart]
            The original content when it satisfies size limits.

        Raises
        ------
        ValueError
            Raised when plain-text content exceeds MAX_CONTENT_LENGTH.
        """
        if isinstance(v, str) and len(v) > MAX_CONTENT_LENGTH:
            msg = (
                f"Message content exceeds {MAX_CONTENT_LENGTH} characters "
                f"({len(v)} chars). Truncate or split the message."
            )
            raise ValueError(msg)
        return v

    def text_content(self) -> str:
        """Return the plain-text content regardless of content type.

        Returns
        -------
        str
            The plain-text message body, flattening structured text parts.
        """
        if isinstance(self.content, str):
            return self.content
        return "".join(p.text for p in self.content if isinstance(p, TextPart))

    class Config:
        """Pydantic model configuration."""

        populate_by_name = True


class ChatThread(BaseModel):
    """A conversation thread containing messages.

    Attributes
    ----------
    thread_id : str
        Stable identifier for the conversation thread.
    title : str
        Human-readable thread title shown in the UI.
    messages : list[ChatMessage]
        Ordered transcript of messages in the thread.
    created_at : float
        Unix timestamp when the thread was created.
    updated_at : float
        Unix timestamp when the thread was last updated.
    metadata : dict[str, Any]
        Arbitrary application-specific thread metadata.
    status : Literal["active", "archived"]
        Lifecycle state of the thread in the chat UI.
    """

    thread_id: str = Field(default_factory=lambda: f"thread_{uuid.uuid4().hex[:8]}")
    title: str = "New Chat"
    messages: list[ChatMessage] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)
    status: Literal["active", "archived"] = "active"


class SlashCommand(BaseModel):
    """A slash command registered for the chat input.

    Attributes
    ----------
    name : str
        Slash-prefixed command name entered by the user.
    description : str
        Human-readable description displayed in command pickers.
    handler_event : str
        Backend event name fired when the command is invoked.
    args_schema : dict[str, Any] | None
        Optional JSON schema describing accepted command arguments.
    builtin : bool
        Indicates whether the command ships with PyWry by default.
    """

    name: str
    description: str = ""
    handler_event: str = ""
    args_schema: dict[str, Any] | None = None
    builtin: bool = False

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Normalize slash-command names.

        Parameters
        ----------
        v : str
            Candidate slash-command name.

        Returns
        -------
        str
            Normalized lowercase name guaranteed to start with ``/``.
        """
        if not v.startswith("/"):
            v = f"/{v}"
        return v.lower()


# =============================================================================
# Helpers
# =============================================================================


def _default_slash_commands() -> list[SlashCommand]:
    """Built-in slash commands available in every chat widget.

    Returns
    -------
    list[SlashCommand]
        Default command set installed when no explicit list is provided.
    """
    return [
        SlashCommand(
            name="/clear",
            description="Clear the current conversation",
            handler_event="chat:clear",
            builtin=True,
        ),
        SlashCommand(
            name="/export",
            description="Export conversation as JSON",
            handler_event="chat:export",
            builtin=True,
        ),
        SlashCommand(
            name="/model",
            description="Switch the LLM model",
            handler_event="chat:switch-model",
            args_schema={"type": "object", "properties": {"model": {"type": "string"}}},
            builtin=True,
        ),
        SlashCommand(
            name="/system",
            description="Set the system prompt",
            handler_event="chat:set-system",
            args_schema={"type": "object", "properties": {"prompt": {"type": "string"}}},
            builtin=True,
        ),
    ]


# =============================================================================
# Configuration Models
# =============================================================================


class ChatConfig(BaseModel):
    """Configuration for the chat engine.

    Attributes
    ----------
    system_prompt : str | None
        Optional system prompt prepended to model conversations.
    model : str
        Default model identifier used for generations.
    temperature : float
        Sampling temperature passed to provider backends.
    max_tokens : int
        Maximum token budget requested per generation.
    streaming : bool
        Enables streaming responses when supported by the provider.
    persist : bool
        Persists chat history between sessions when enabled.
    slash_commands : list[SlashCommand]
        Commands exposed in the chat input UI.
    provider : str | None
        Explicit provider name when overriding model-based selection.
    provider_config : dict[str, Any]
        Arbitrary provider-specific configuration values.
    """

    system_prompt: str | None = None
    model: str = "gpt-4"
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1)
    streaming: bool = True
    persist: bool = False
    slash_commands: list[SlashCommand] = Field(default_factory=_default_slash_commands)
    provider: str | None = None
    provider_config: dict[str, Any] = Field(default_factory=dict)


class ChatWidgetConfig(BaseModel):
    """Full widget configuration including UI and chat settings.

    Attributes
    ----------
    title : str
        Window or panel title presented to the user.
    width : int
        Initial widget width in pixels.
    height : int
        Initial widget height in pixels.
    theme : Literal["dark", "light", "system"]
        Preferred widget theme.
    show_sidebar : bool
        Controls visibility of conversation-management UI.
    show_settings : bool
        Controls visibility of chat settings controls.
    toolbar_position : Literal["top", "bottom"]
        Placement of widget toolbar controls.
    chat_config : ChatConfig
        Nested chat-engine configuration.
    """

    title: str = "Chat"
    width: int = Field(default=600, ge=200)
    height: int = Field(default=700, ge=300)
    theme: Literal["dark", "light", "system"] = "dark"
    show_sidebar: bool = True
    show_settings: bool = True
    toolbar_position: Literal["top", "bottom"] = "top"
    chat_config: ChatConfig = Field(default_factory=ChatConfig)


# =============================================================================
# MCP Task State — maps 1:1 to MCP Task data type
# =============================================================================


class ChatTaskState(BaseModel):
    """Tracks an MCP task lifecycle for a chat_send_message call.

    Attributes
    ----------
    task_id : str
        Stable identifier for the MCP task.
    thread_id : str
        Conversation thread associated with the task.
    message_id : str
        Message that initiated the task.
    status : Literal["working", "input_required", "completed", "failed", "cancelled"]
        Current MCP task status.
    status_message : str
        Human-readable progress or error status.
    created_at : float
        Unix timestamp when the task state was created.
    poll_interval : float | None
        Suggested polling interval for clients watching task progress.
    """

    task_id: str = Field(default_factory=lambda: f"task_{uuid.uuid4().hex[:12]}")
    thread_id: str = ""
    message_id: str = ""
    status: Literal["working", "input_required", "completed", "failed", "cancelled"] = "working"
    status_message: str = ""
    created_at: float = Field(default_factory=time.time)
    poll_interval: float | None = None


# =============================================================================
# GenerationHandle — in-flight LLM generation tracker
# =============================================================================


@dataclass
class GenerationHandle:
    """Tracks an in-flight LLM generation for stop-button cancellation.

    The cooperative cancellation pattern follows OAuthFlow._cancellation_event
    in auth/flow.py: the cancel_event is checked between chunks, and
    task.cancel() serves as a backup for non-cooperative generators.

    Attributes
    ----------
    task : asyncio.Task[Any] | None
        Async task performing the active generation, when available.
    cancel_event : asyncio.Event
        Cooperative cancellation signal checked by streaming providers.
    message_id : str
        Assistant message being populated by the generation.
    widget_id : str
        Widget instance associated with the generation.
    thread_id : str
        Conversation thread associated with the generation.
    created_at : float
        Unix timestamp when the handle was created.
    _content_parts : list[str]
        Internal list of streamed chunks accumulated so far.
    """

    task: asyncio.Task[Any] | None = None
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    message_id: str = ""
    widget_id: str = ""
    thread_id: str = ""
    created_at: float = field(default_factory=time.time)
    _content_parts: list[str] = field(default_factory=list)

    @property
    def is_expired(self) -> bool:
        """Check if this handle has exceeded its TTL.

        Returns
        -------
        bool
            True when the handle is older than GENERATION_HANDLE_TTL.
        """
        return (time.time() - self.created_at) > GENERATION_HANDLE_TTL

    @property
    def partial_content(self) -> str:
        """Return content accumulated so far.

        Returns
        -------
        str
            Concatenated streamed chunks recorded on the handle.
        """
        return "".join(self._content_parts)

    def append_chunk(self, chunk: str) -> None:
        """Record a streamed chunk.

        Parameters
        ----------
        chunk : str
            Incremental content emitted by a streaming provider.
        """
        if self.cancel_event.is_set():
            return
        self._content_parts.append(chunk)

    def cancel(self) -> bool:
        """Request cooperative cancellation.

        Returns
        -------
        bool
            True if cancellation was newly requested, False if already cancelled.
        """
        if self.cancel_event.is_set():
            return False
        self.cancel_event.set()
        if self.task is not None and not self.task.done():
            self.task.cancel()
        return True


# =============================================================================
# Exceptions
# =============================================================================


class GenerationCancelledError(Exception):
    """Raised by providers when cancel_event is detected mid-stream."""

    def __init__(self, partial_content: str = "") -> None:
        super().__init__("Generation cancelled by user")
        self.partial_content = partial_content


def build_chat_html(
    *,
    show_sidebar: bool = True,
    show_settings: bool = True,
    enable_context: bool = False,
    enable_file_attach: bool = False,
    file_accept_types: list[str] | None = None,
    container_id: str = "",
    header_actions: str = "",
) -> str:
    """Build the HTML structure for a chat widget.

    The layout follows VS Code's Copilot Chat pattern: a compact header
    bar with conversation management and settings, a full-width scrollable
    message area, and an input bar at the bottom.  All components are
    inside a single ``pywry-chat`` container.

    Parameters
    ----------
    show_sidebar : bool
        Include the thread/conversation picker in the header bar.
        When False the conversation dropdown is hidden but new-chat
        and other header buttons remain.
    show_settings : bool
        Include the settings toggle button in the header.
    enable_context : bool
        Enable @mention widget references in the chat input.
    enable_file_attach : bool
        Show the attach button (📎) and enable drag-and-drop file
        attachments.  Independent of ``enable_context``.
    file_accept_types : list[str] | None
        Restrict the file picker to specific extensions (e.g.
        ``[".csv", ".json"]``).  ``None`` uses a broad default set.
    container_id : str
        Optional id for the outer container div.
    header_actions : str
        Extra HTML injected into the header-actions area (right side
        of the header bar).  Developers can add custom buttons here.

    Returns
    -------
    str
        HTML string for the chat widget.
    """
    # Conversation picker (dropdown) in header
    sidebar_html = ""
    if show_sidebar:
        sidebar_html = (
            '<div class="pywry-chat-conv-picker">'
            '<button id="pywry-chat-conv-btn" class="pywry-chat-conv-btn" data-tooltip="Switch conversation">'
            '<span id="pywry-chat-conv-title" class="pywry-chat-conv-title">New Chat</span>'
            '<svg width="12" height="12" viewBox="0 0 12 12" class="pywry-chat-chevron">'
            '<path d="M3 5l3 3 3-3" stroke="currentColor" fill="none" stroke-width="1.5"/>'
            "</svg>"
            "</button>"
            '<div id="pywry-chat-conv-dropdown" class="pywry-chat-conv-dropdown">'
            '<div id="pywry-chat-sidebar" class="pywry-chat-thread-list"></div>'
            "</div>"
            "</div>"
        )

    settings_html = ""
    if show_settings:
        settings_html = (
            '<div class="pywry-chat-settings-menu">'
            '<button id="pywry-chat-settings-toggle" class="pywry-chat-header-btn" data-tooltip="Settings">'
            '<svg width="16" height="16" viewBox="0 0 16 16">'
            '<path d="M9.1 4.4L8.6 2H7.4l-.5 2.4-.7.3-2-1.3-.9.8 1.3 2-.3.7L2 7.4v1.2l2.4.5.3.7-1.3 2 .8.9 2-1.3.7.3.5 2.4h1.2l.5-2.4.7-.3 2 1.3.9-.8-1.3-2 .3-.7 2.4-.5V7.4l-2.4-.5-.3-.7 1.3-2-.8-.9-2 1.3-.7-.3zM8 10a2 2 0 110-4 2 2 0 010 4z" '
            'fill="currentColor"/>'
            "</svg>"
            "</button>"
            '<div id="pywry-chat-settings" class="pywry-chat-settings-dropdown"></div>'
            "</div>"
        )

    container_attr = f' id="{container_id}"' if container_id else ""

    # Build data attribute for accepted file types (frontend validation)
    accept_data = ""
    if file_accept_types and enable_file_attach:
        import html as html_mod

        accept_data = f' data-accept-types="{html_mod.escape(",".join(file_accept_types))}"'

    return (
        f'<div class="pywry-chat"{container_attr}{accept_data}>'
        # Header bar
        '<div class="pywry-chat-header">'
        '<div class="pywry-chat-header-left">' + sidebar_html + "</div>"
        '<div class="pywry-chat-header-actions">'
        + header_actions
        + '<button id="pywry-chat-new-thread" class="pywry-chat-header-btn" data-tooltip="New chat">'
        '<svg width="16" height="16" viewBox="0 0 16 16">'
        '<path d="M8 3v10M3 8h10" stroke="currentColor" fill="none" stroke-width="1.5" stroke-linecap="round"/>'
        "</svg>"
        "</button>"
        '<button id="pywry-chat-fullscreen-btn" class="pywry-chat-header-btn" data-tooltip="Toggle full width">'
        '<svg width="16" height="16" viewBox="0 0 16 16" class="pywry-chat-fullscreen-expand">'
        '<path d="M2 2h5v1.5H4.3L7 6.2 5.9 7.3 3.5 4.6V7H2V2zm12 12h-5v-1.5h2.7L9 9.8l1.1-1.1 2.4 2.7V9H14v5z" fill="currentColor"/>'
        "</svg>"
        '<svg width="16" height="16" viewBox="0 0 16 16" class="pywry-chat-fullscreen-collapse" style="display:none">'
        '<path d="M7 7H2v1.5h2.7L2 11.2l1.1 1.1L5.5 9.6V12H7V7zm2 2h5V7.5h-2.7L14 4.8 12.9 3.7 10.5 6.4V4H9v5z" fill="currentColor"/>'
        "</svg>"
        "</button>" + settings_html + "</div>"
        "</div>"
        # Messages
        '<div id="pywry-chat-messages" class="pywry-chat-messages"></div>'
        '<div id="pywry-chat-typing" class="pywry-chat-typing">Thinking</div>'
        '<div id="pywry-chat-new-msg-badge" class="pywry-chat-new-msg-badge">New messages</div>'
        # Todo list (above input bar)
        '<div id="pywry-chat-todo" class="pywry-chat-todo"></div>'
        # Input bar
        '<div class="pywry-chat-input-bar">'
        '<div id="pywry-chat-cmd-palette" class="pywry-chat-cmd-palette"></div>'
        # Mention popup (@ autocomplete) — must be inside input-bar for positioning
        + (
            '<div id="pywry-chat-mention-popup" class="pywry-chat-mention-popup"></div>'
            if enable_context
            else ""
        )
        +
        # Attachments bar (pills showing attached files/widgets)
        '<div id="pywry-chat-attachments-bar" class="pywry-chat-attachments-bar"></div>'
        '<div class="pywry-chat-input-row">'
        + (
            # Attach button (📎) — only when file attach is enabled
            '<button id="pywry-chat-attach-btn" class="pywry-chat-attach-btn" data-tooltip="Attach file">'
            '<svg width="16" height="16" viewBox="0 0 16 16">'
            '<path d="M11.5 1.5a2.5 2.5 0 00-3.54 0L3.04 6.42a4 4 0 005.66 5.66l4.24-4.24-1.06-1.06-4.24 4.24a2.5 2.5 0 01-3.54-3.54l4.95-4.95a1 1 0 011.41 1.41L5.52 8.89a.5.5 0 00.7.7l4.25-4.24 1.06 1.06-4.24 4.24a2 2 0 01-2.83-2.83l4.95-4.95a2.5 2.5 0 013.54 3.54l-4.95 4.95a3.5 3.5 0 01-4.95-4.95L8.33 2.33" '
            'fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>'
            "</svg>"
            "</button>"
            if enable_file_attach
            else ""
        )
        + '<textarea id="pywry-chat-input" rows="1" placeholder="Ask a question..."></textarea>'
        '<button id="pywry-chat-send" class="pywry-chat-send-btn" data-tooltip="Send message">'
        '<svg width="16" height="16" viewBox="0 0 16 16">'
        '<path d="M1 8l6-6v4h7v4H7v4L1 8z" fill="currentColor"/>'
        "</svg>"
        "</button>"
        "</div>"
        "</div>"
        # Drop overlay (shown during drag-over)
        + (
            '<div id="pywry-chat-drop-overlay" class="pywry-chat-drop-overlay">'
            '<div class="pywry-chat-drop-overlay-content">'
            '<svg width="32" height="32" viewBox="0 0 16 16">'
            '<path d="M11.5 1.5a2.5 2.5 0 00-3.54 0L3.04 6.42a4 4 0 005.66 5.66l4.24-4.24-1.06-1.06-4.24 4.24a2.5 2.5 0 01-3.54-3.54l4.95-4.95a1 1 0 011.41 1.41L5.52 8.89a.5.5 0 00.7.7l4.25-4.24 1.06 1.06-4.24 4.24a2 2 0 01-2.83-2.83l4.95-4.95a2.5 2.5 0 013.54 3.54l-4.95 4.95a3.5 3.5 0 01-4.95-4.95L8.33 2.33" '
            'fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>'
            "</svg>"
            "<span>Drop files to attach</span>"
            "</div>"
            "</div>"
            if enable_file_attach
            else ""
        )
        + "</div>"
    )
