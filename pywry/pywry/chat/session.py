"""ACP session primitives for the Chat component.

This module defines modes, configuration options, capabilities, stop
reasons, plan entries, and permission models — all aligned to the
`Agent Client Protocol <https://agentclientprotocol.com>`_ session
specification.
"""

from __future__ import annotations

import uuid

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


StopReason = Literal[
    "end_turn",
    "max_tokens",
    "max_turn_requests",
    "refusal",
    "cancelled",
]
"""ACP stop reason returned when a prompt turn completes."""


class SessionMode(BaseModel):
    """An operational mode advertised by the agent.

    Modes affect system prompts, tool availability, and permission
    requirements. Common examples: *Ask*, *Architect*, *Code*.

    Attributes
    ----------
    id : str
        Unique identifier for the mode.
    name : str
        Human-readable title.
    description : str | None
        Optional explanation of mode behaviour.
    """

    id: str
    name: str
    description: str | None = None


class ConfigOptionChoice(BaseModel):
    """A single selectable value for a ``SessionConfigOption``.

    Attributes
    ----------
    value : str
        Machine-readable option value.
    name : str
        Human-readable label.
    description : str | None
        Optional longer description.
    """

    value: str
    name: str
    description: str | None = None


class SessionConfigOption(BaseModel):
    """A configurable, session-level setting exposed by the agent.

    Attributes
    ----------
    id : str
        Unique identifier for the option.
    name : str
        Human-readable label.
    description : str | None
        Optional details about the option's purpose.
    category : str | None
        Semantic category — ``"mode"``, ``"model"``,
        ``"thought_level"``, or a custom string.
    type : str
        Currently only ``"select"`` is supported by ACP.
    currentValue : str
        The active setting value.
    options : list[ConfigOptionChoice]
        Available choices.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    description: str | None = None
    category: str | None = None
    type: Literal["select"] = "select"
    current_value: str = Field(default="", alias="currentValue")
    options: list[ConfigOptionChoice] = Field(default_factory=list)


class PlanEntry(BaseModel):
    """A single entry in an agent execution plan.

    Attributes
    ----------
    content : str
        Human-readable description of the task.
    priority : str
        Importance level — ``"high"``, ``"medium"``, or ``"low"``.
    status : str
        Current state — ``"pending"``, ``"in_progress"``, or
        ``"completed"``.
    """

    content: str
    priority: Literal["high", "medium", "low"] = "medium"
    status: Literal["pending", "in_progress", "completed"] = "pending"


class PermissionOption(BaseModel):
    """A single option presented in a permission request.

    Attributes
    ----------
    id : str
        Option identifier (e.g. ``"allow_once"``).
    label : str
        Human-readable button text.
    """

    id: str
    label: str


class PermissionRequest(BaseModel):
    """Agent request for user permission before tool execution.

    Attributes
    ----------
    toolCallId : str
        The tool call requiring permission.
    title : str
        Human-readable description of what the tool will do.
    options : list[PermissionOption]
        Available user choices.
    request_id : str
        Stable identifier for correlating the response.
    """

    model_config = ConfigDict(populate_by_name=True)

    tool_call_id: str = Field(alias="toolCallId")
    title: str = ""
    options: list[PermissionOption] = Field(
        default_factory=lambda: [
            PermissionOption(id="allow_once", label="Allow once"),
            PermissionOption(id="allow_always", label="Allow always"),
            PermissionOption(id="reject_once", label="Reject"),
            PermissionOption(id="reject_always", label="Always reject"),
        ]
    )
    request_id: str = Field(default_factory=lambda: f"perm_{uuid.uuid4().hex[:8]}")


PermissionOutcome = Literal[
    "allow_once",
    "allow_always",
    "reject_once",
    "reject_always",
    "cancelled",
]
"""User's response to a ``PermissionRequest``."""


class PromptCapabilities(BaseModel):
    """Content types the agent supports in prompts.

    Attributes
    ----------
    image : bool
        Agent accepts image content blocks.
    audio : bool
        Agent accepts audio content blocks.
    embeddedContext : bool
        Agent accepts embedded resource content blocks.
    """

    model_config = ConfigDict(populate_by_name=True)

    image: bool = False
    audio: bool = False
    embedded_context: bool = Field(default=False, alias="embeddedContext")


class ClientCapabilities(BaseModel):
    """Capabilities the client advertises during ``initialize``.

    Attributes
    ----------
    fileSystem : bool
        Client supports ``fs/read_text_file`` and
        ``fs/write_text_file`` methods.
    terminal : bool
        Client supports ``terminal/*`` methods.
    """

    model_config = ConfigDict(populate_by_name=True)

    file_system: bool = Field(default=False, alias="fileSystem")
    terminal: bool = False


class AgentCapabilities(BaseModel):
    """Capabilities the agent advertises during ``initialize``.

    Attributes
    ----------
    promptCapabilities : PromptCapabilities | None
        Supported prompt content types.
    loadSession : bool
        Agent supports ``session/load``.
    configOptions : bool
        Agent supports ``session/set_config_option``.
    modes : bool
        Agent supports ``session/set_mode``.
    """

    model_config = ConfigDict(populate_by_name=True)

    prompt_capabilities: PromptCapabilities | None = Field(default=None, alias="promptCapabilities")
    load_session: bool = Field(default=False, alias="loadSession")
    config_options: bool = Field(default=False, alias="configOptions")
    modes: bool = False


class AgentInfo(BaseModel):
    """Metadata about an ACP agent.

    Attributes
    ----------
    name : str
        Machine-readable agent name.
    title : str | None
        Human-readable title.
    version : str | None
        Agent version string.
    """

    name: str = ""
    title: str | None = None
    version: str | None = None
