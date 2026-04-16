"""ACP ``SessionUpdate`` discriminated union and update types.

These models represent the typed notifications an ACP agent sends to the
client during a prompt turn via ``session/update``. Each variant maps to
a specific ``session_update`` discriminator value.

Types with no ACP equivalent (``StatusUpdate``, ``ThinkingUpdate``,
``ArtifactUpdate``) use an ``x_`` prefix to indicate they are PyWry
extensions.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .models import ACPCommand
from .session import (
    PermissionOption,
    PlanEntry,
    SessionConfigOption,
    SessionMode,
)


class AgentMessageUpdate(BaseModel):
    """Streaming text chunk from the agent."""

    session_update: Literal["agent_message"] = Field(default="agent_message", alias="sessionUpdate")
    text: str = ""
    model_config = ConfigDict(populate_by_name=True)


class ToolCallUpdate(BaseModel):
    """Tool invocation notification or status update."""

    model_config = ConfigDict(populate_by_name=True)

    session_update: Literal["tool_call"] = Field(default="tool_call", alias="sessionUpdate")
    tool_call_id: str = Field(default="", alias="toolCallId")
    title: str = ""
    name: str = ""
    kind: str = "other"
    status: str = "pending"
    content: Any = None
    locations: Any = None


class PlanUpdate(BaseModel):
    """Agent execution plan."""

    model_config = ConfigDict(populate_by_name=True)

    session_update: Literal["plan"] = Field(default="plan", alias="sessionUpdate")
    entries: list[PlanEntry] = Field(default_factory=list)


class CommandsUpdate(BaseModel):
    """Available slash commands from the agent."""

    model_config = ConfigDict(populate_by_name=True)

    session_update: Literal["available_commands"] = Field(
        default="available_commands", alias="sessionUpdate"
    )
    commands: list[ACPCommand] = Field(default_factory=list)


class ConfigOptionUpdate(BaseModel):
    """Config option state change."""

    model_config = ConfigDict(populate_by_name=True)

    session_update: Literal["config_option"] = Field(default="config_option", alias="sessionUpdate")
    options: list[SessionConfigOption] = Field(default_factory=list)


class ModeUpdate(BaseModel):
    """Agent mode change notification."""

    model_config = ConfigDict(populate_by_name=True)

    session_update: Literal["current_mode"] = Field(default="current_mode", alias="sessionUpdate")
    current_mode_id: str = Field(default="", alias="currentModeId")
    available_modes: list[SessionMode] = Field(default_factory=list, alias="availableModes")


class PermissionRequestUpdate(BaseModel):
    """Agent requests user permission before tool execution."""

    model_config = ConfigDict(populate_by_name=True)

    session_update: Literal["permission_request"] = Field(
        default="permission_request", alias="sessionUpdate"
    )
    tool_call_id: str = Field(default="", alias="toolCallId")
    title: str = ""
    options: list[PermissionOption] = Field(default_factory=list)
    request_id: str = Field(default="", alias="requestId")


class StatusUpdate(BaseModel):
    """Transient status message shown inline in the UI."""

    model_config = ConfigDict(populate_by_name=True)

    session_update: Literal["x_status"] = Field(default="x_status", alias="sessionUpdate")
    text: str = ""


class ThinkingUpdate(BaseModel):
    """Streaming thinking or reasoning chunk.

    Rendered as a collapsible inline block. Thinking tokens are streamed
    in real-time and are not stored in conversation history.
    """

    model_config = ConfigDict(populate_by_name=True)

    session_update: Literal["x_thinking"] = Field(default="x_thinking", alias="sessionUpdate")
    text: str = ""


class ArtifactUpdate(BaseModel):
    """Rich artifact rendered in the chat UI.

    The ``artifact`` field contains a concrete artifact model from
    ``chat.artifacts``.
    """

    model_config = ConfigDict(populate_by_name=True)

    session_update: Literal["x_artifact"] = Field(default="x_artifact", alias="sessionUpdate")
    artifact: Any = None


class CitationUpdate(BaseModel):
    """Citation or source reference attached to a response."""

    model_config = ConfigDict(populate_by_name=True)

    session_update: Literal["x_citation"] = Field(default="x_citation", alias="sessionUpdate")
    url: str = ""
    title: str = ""
    snippet: str = ""


SessionUpdate = Annotated[
    AgentMessageUpdate
    | ToolCallUpdate
    | PlanUpdate
    | CommandsUpdate
    | ConfigOptionUpdate
    | ModeUpdate
    | PermissionRequestUpdate
    | StatusUpdate
    | ThinkingUpdate
    | ArtifactUpdate
    | CitationUpdate,
    Field(discriminator="session_update"),
]
"""Discriminated union of all session update types."""
