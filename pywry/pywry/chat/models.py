"""ACP-aligned data models for the Chat component.

This module defines content blocks, tool calls, messages, threads,
commands, configuration, and generation tracking — all conforming to the
`Agent Client Protocol <https://agentclientprotocol.com>`_ content and
session schemas.
"""

from __future__ import annotations

import asyncio
import time
import uuid

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


MAX_RENDERED_MESSAGES: int = 200
"""DOM nodes kept in viewport (JS-side cap)."""

MAX_MESSAGE_SIZE: int = 500_000
"""Characters per message before truncation in UI."""

MAX_CODE_BLOCK_LINES: int = 500
"""Lines per code block before collapse in UI."""

MAX_CONTENT_LENGTH: int = 100_000
"""Characters per ``ChatMessage.content`` (model validation)."""

MAX_MESSAGES_PER_THREAD: int = 1_000
"""Messages per thread before oldest are evicted."""

MAX_THREADS_PER_WIDGET: int = 50
"""Threads per widget before rejection."""

STREAM_TIMEOUT_SECONDS: int = 30
"""No-chunk timeout — force-cancel if LLM stalls."""

SEND_COOLDOWN_MS: int = 1_000
"""Minimum interval between user messages (JS-side)."""

EVENT_QUEUE_MAX_SIZE: int = 500
"""Per-widget chat event queue size."""

TASK_REAPER_INTERVAL: int = 600
"""Orphan task check interval in seconds."""

GENERATION_HANDLE_TTL: int = 300
"""Seconds before a ``GenerationHandle`` auto-expires."""


class TextPart(BaseModel):
    """Plain text content block.

    Attributes
    ----------
    type : str
        Discriminator — always ``"text"``.
    text : str
        Plain text payload.
    annotations : dict[str, Any] | None
        Optional ACP annotations.
    """

    type: Literal["text"] = "text"
    text: str
    annotations: dict[str, Any] | None = None


class ImagePart(BaseModel):
    """Base64-encoded image content block.

    Attributes
    ----------
    type : str
        Discriminator — always ``"image"``.
    data : str
        Base64-encoded image bytes.
    mime_type : str
        MIME type (e.g. ``"image/png"``). Serializes as ``mimeType``.
    uri : str | None
        Optional source URI.
    annotations : dict[str, Any] | None
        Optional ACP annotations.
    """

    model_config = ConfigDict(populate_by_name=True)

    type: Literal["image"] = "image"
    data: str
    mime_type: str = Field(default="image/png", alias="mimeType")
    uri: str | None = None
    annotations: dict[str, Any] | None = None


class AudioPart(BaseModel):
    """Base64-encoded audio content block.

    Attributes
    ----------
    type : str
        Discriminator — always ``"audio"``.
    data : str
        Base64-encoded audio bytes.
    mimeType : str
        MIME type (e.g. ``"audio/wav"``).
    annotations : dict[str, Any] | None
        Optional ACP annotations.
    """

    model_config = ConfigDict(populate_by_name=True)

    type: Literal["audio"] = "audio"
    data: str
    mime_type: str = Field(default="audio/wav", alias="mimeType")
    annotations: dict[str, Any] | None = None


class EmbeddedResource(BaseModel):
    """Resource content embedded directly in a content block.

    Attributes
    ----------
    uri : str
        Resource URI.
    mimeType : str | None
        MIME type of the resource.
    text : str | None
        Text content (for text resources).
    blob : str | None
        Base64-encoded blob (for binary resources).
    """

    model_config = ConfigDict(populate_by_name=True)

    uri: str
    mime_type: str | None = Field(default=None, alias="mimeType")
    text: str | None = None
    blob: str | None = None


class EmbeddedResourcePart(BaseModel):
    """Complete resource content embedded in a content block.

    Preferred for ``@``-mentions and file references where the agent
    cannot directly access the resource.

    Attributes
    ----------
    type : str
        Discriminator — always ``"resource"``.
    resource : EmbeddedResource
        The embedded resource payload.
    annotations : dict[str, Any] | None
        Optional ACP annotations.
    """

    type: Literal["resource"] = "resource"
    resource: EmbeddedResource
    annotations: dict[str, Any] | None = None


class ResourceLinkPart(BaseModel):
    """Reference to an agent-accessible resource without embedding content.

    Attributes
    ----------
    type : str
        Discriminator — always ``"resource_link"``.
    uri : str
        Resource URI.
    name : str
        Human-readable label.
    mimeType : str | None
        MIME type of the linked resource.
    title : str | None
        Display title.
    description : str | None
        Longer description of the resource.
    size : int | None
        Resource size in bytes.
    annotations : dict[str, Any] | None
        Optional ACP annotations.
    """

    model_config = ConfigDict(populate_by_name=True)

    type: Literal["resource_link"] = "resource_link"
    uri: str
    name: str = ""
    mime_type: str | None = Field(default=None, alias="mimeType")
    title: str | None = None
    description: str | None = None
    size: int | None = None
    annotations: dict[str, Any] | None = None


ContentBlock = TextPart | ImagePart | AudioPart | EmbeddedResourcePart | ResourceLinkPart
"""ACP ``ContentBlock`` discriminated union — all five content types."""

ToolCallKind = Literal[
    "read",
    "edit",
    "delete",
    "move",
    "search",
    "execute",
    "think",
    "fetch",
    "other",
]
"""ACP tool call kind taxonomy."""

ToolCallStatus = Literal["pending", "in_progress", "completed", "failed"]
"""ACP tool call lifecycle state."""


class ToolCallLocation(BaseModel):
    """File location affected by a tool call.

    Attributes
    ----------
    path : str
        Absolute file path.
    line : int | None
        Optional 1-based line number.
    """

    path: str
    line: int | None = None


class ACPToolCall(BaseModel):
    """ACP tool invocation attached to an assistant message.

    Attributes
    ----------
    toolCallId : str
        Unique identifier within the session.
    title : str
        Human-readable description shown in the UI.
    name : str
        Tool name.
    kind : str
        Category from the ACP taxonomy.
    status : str
        Lifecycle state.
    arguments : dict[str, Any]
        Tool arguments.
    content : list[ContentBlock] | None
        Result content blocks (populated on completion).
    locations : list[ToolCallLocation] | None
        Affected file paths with optional line numbers.
    """

    model_config = ConfigDict(populate_by_name=True)

    tool_call_id: str = Field(
        default_factory=lambda: f"call_{uuid.uuid4().hex[:12]}", alias="toolCallId"
    )
    title: str = ""
    name: str = ""
    kind: ToolCallKind = "other"
    status: ToolCallStatus = "pending"
    arguments: dict[str, Any] = Field(default_factory=dict)
    content: list[ContentBlock] | None = None    locations: list[ToolCallLocation] | None = None


class ACPCommandInput(BaseModel):
    """Input hints for an ACP slash command.

    Attributes
    ----------
    hint : str
        Unstructured text guidance for the command input.
    """

    hint: str = ""


class ACPCommand(BaseModel):
    """ACP slash command advertised by the agent.

    Attributes
    ----------
    name : str
        Command name (e.g. ``"web"``, ``"test"``).
    description : str
        Human-readable description.
    input : ACPCommandInput | None
        Optional input hints.
    """

    name: str
    description: str = ""
    input: ACPCommandInput | None = None


class ChatMessage(BaseModel):
    """A single chat message.

    Attributes
    ----------
    role : str
        Semantic role — ``"user"``, ``"assistant"``, ``"system"``,
        or ``"tool"``.
    content : str | list[ContentBlock]
        Message body as plain text or ACP content blocks.
    message_id : str
        Stable identifier used across UI and backend events.
    timestamp : float
        Unix timestamp when the message was created.
    metadata : dict[str, Any]
        Arbitrary provider- or application-specific metadata.
    tool_calls : list[ACPToolCall] | None
        Tool invocations attached to assistant messages.
    tool_call_id : str | None
        Tool-call identifier when this message is a tool result.
    model : str | None
        Model name that produced the message.
    usage : dict[str, Any] | None
        Token or billing metadata.
    stopped : bool
        Whether generation stopped early (e.g. cancellation).
    """

    role: Literal["user", "assistant", "system", "tool"]
    content: str | list[ContentBlock] = ""    message_id: str = Field(default_factory=lambda: f"msg_{uuid.uuid4().hex[:12]}")
    timestamp: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)
    tool_calls: list[ACPToolCall] | None = None
    tool_call_id: str | None = None
    model: str | None = None
    usage: dict[str, Any] | None = None
    stopped: bool = False

    @field_validator("content")
    @classmethod
    def validate_content_length(
        cls,
        v: str | list[ContentBlock],
    ) -> str | list[ContentBlock]:
        """Reject content exceeding ``MAX_CONTENT_LENGTH``.

        Parameters
        ----------
        v : str | list[ContentBlock]
            Candidate message content.

        Returns
        -------
        str | list[ContentBlock]
            The original content when it satisfies size limits.

        Raises
        ------
        ValueError
            When plain-text content exceeds ``MAX_CONTENT_LENGTH``.
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

    model_config = ConfigDict(populate_by_name=True)


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
    status : str
        Lifecycle state — ``"active"`` or ``"archived"``.
    """

    thread_id: str = Field(default_factory=lambda: f"thread_{uuid.uuid4().hex[:8]}")
    title: str = "New Chat"
    messages: list[ChatMessage] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)
    status: Literal["active", "archived"] = "active"


class ChatConfig(BaseModel):
    """Configuration for the chat engine.

    Attributes
    ----------
    system_prompt : str | None
        Optional system prompt prepended to model conversations.
    model : str
        Default model identifier.
    temperature : float
        Sampling temperature.
    max_tokens : int
        Maximum token budget per generation.
    streaming : bool
        Enable streaming responses.
    persist : bool
        Persist chat history between sessions.
    """

    system_prompt: str | None = None
    model: str = "gpt-4"
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1)
    streaming: bool = True
    persist: bool = False


class ChatWidgetConfig(BaseModel):
    """Full widget configuration including UI and chat settings.

    Attributes
    ----------
    title : str
        Window or panel title.
    width : int
        Initial widget width in pixels.
    height : int
        Initial widget height in pixels.
    theme : str
        Preferred widget theme.
    show_sidebar : bool
        Show conversation-management UI.
    show_settings : bool
        Show chat settings controls.
    toolbar_position : str
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


class ChatTaskState(BaseModel):
    """Tracks an MCP task lifecycle for a ``chat_send_message`` call.

    Attributes
    ----------
    task_id : str
        Stable identifier for the MCP task.
    thread_id : str
        Conversation thread associated with the task.
    message_id : str
        Message that initiated the task.
    status : str
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


@dataclass
class GenerationHandle:
    """Tracks an in-flight LLM generation for stop-button cancellation.

    Uses cooperative cancellation: ``cancel_event`` is checked between
    chunks, and ``task.cancel()`` serves as a backup for non-cooperative
    generators.

    Attributes
    ----------
    task : asyncio.Task[Any] | None
        Async task performing the active generation.
    cancel_event : asyncio.Event
        Cooperative cancellation signal.
    message_id : str
        Assistant message being populated.
    widget_id : str
        Widget instance associated with the generation.
    thread_id : str
        Conversation thread associated with the generation.
    created_at : float
        Unix timestamp when the handle was created.
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
            ``True`` when the handle is older than
            ``GENERATION_HANDLE_TTL``.
        """
        return (time.time() - self.created_at) > GENERATION_HANDLE_TTL

    @property
    def partial_content(self) -> str:
        """Return content accumulated so far.

        Returns
        -------
        str
            Concatenated streamed chunks.
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
            ``True`` if cancellation was newly requested, ``False`` if
            already cancelled.
        """
        if self.cancel_event.is_set():
            return False
        self.cancel_event.set()
        if self.task is not None and not self.task.done():
            self.task.cancel()
        return True


class GenerationCancelledError(Exception):
    """Raised by providers when ``cancel_event`` is detected mid-stream.

    Attributes
    ----------
    partial_content : str
        Content accumulated before cancellation.
    """

    def __init__(self, partial_content: str = "") -> None:
        super().__init__("Generation cancelled by user")
        self.partial_content = partial_content
