"""Magentic provider adapter for the ACP session interface.

Wraps any ``magentic.ChatModel`` backend to implement the
``ChatProvider`` ABC, enabling plug-and-play access to 100+ LLM
providers via magentic.
"""

from __future__ import annotations

import uuid

from typing import TYPE_CHECKING, Any

from . import ChatProvider


if TYPE_CHECKING:
    import asyncio

    from collections.abc import AsyncIterator

    from ..models import ContentBlock
    from ..session import AgentCapabilities, ClientCapabilities
    from ..updates import SessionUpdate


class MagenticProvider(ChatProvider):
    """Provider wrapping a magentic ``ChatModel`` backend.

    Parameters
    ----------
    model : ChatModel | str
        A pre-configured magentic ``ChatModel`` instance, **or** a
        model name string (creates an ``OpenaiChatModel``).
    **kwargs
        Extra keyword arguments forwarded to ``OpenaiChatModel``
        when *model* is a string.

    Raises
    ------
    ImportError
        If the ``magentic`` package is not installed.
    """

    def __init__(self, model: Any, **kwargs: Any) -> None:
        try:
            from magentic.chat_model.base import ChatModel
        except ImportError as exc:
            raise ImportError("MagenticProvider requires: pip install 'pywry[magentic]'") from exc

        if isinstance(model, str):
            from magentic import OpenaiChatModel

            model = OpenaiChatModel(model, **kwargs)
        elif not isinstance(model, ChatModel):
            raise TypeError(f"Expected ChatModel or model name string, got {type(model).__name__}")
        self._model = model
        self._sessions: dict[str, dict[str, Any]] = {}

    async def initialize(
        self,
        capabilities: ClientCapabilities,
    ) -> AgentCapabilities:
        """Return text-only prompt capabilities.

        Parameters
        ----------
        capabilities : ClientCapabilities
            Client features (unused).

        Returns
        -------
        AgentCapabilities
            Default capabilities.
        """
        from ..session import AgentCapabilities

        return AgentCapabilities()

    async def new_session(
        self,
        cwd: str,
        mcp_servers: list[dict[str, Any]] | None = None,
    ) -> str:
        """Create an in-memory session tracker.

        Parameters
        ----------
        cwd : str
            Working directory context.
        mcp_servers : list[dict[str, Any]] | None
            MCP server configs (unused).

        Returns
        -------
        str
            Unique session identifier.
        """
        session_id = f"mag_{uuid.uuid4().hex[:8]}"
        self._sessions[session_id] = {
            "cwd": cwd,
            "system_prompt": "",
        }
        return session_id

    async def prompt(
        self,
        session_id: str,
        content: list[ContentBlock],
        cancel_event: asyncio.Event | None = None,
    ) -> AsyncIterator[SessionUpdate]:
        """Stream response chunks as ``AgentMessageUpdate``.

        Parameters
        ----------
        session_id : str
            Active session identifier.
        content : list[ContentBlock]
            User message content blocks.
        cancel_event : asyncio.Event | None, optional
            Cooperative cancellation signal.

        Yields
        ------
        SessionUpdate
            ``AgentMessageUpdate`` for each text chunk.
        """
        from ..models import GenerationCancelledError, TextPart
        from ..updates import AgentMessageUpdate

        try:
            from magentic import Chat, SystemMessage, UserMessage
            from magentic.streaming import AsyncStreamedStr
        except ImportError:
            yield AgentMessageUpdate(text="magentic is not installed.")
            return

        session = self._sessions.get(session_id, {})
        messages: list[Any] = []

        if session.get("system_prompt"):
            messages.append(SystemMessage(session["system_prompt"]))

        user_text = "".join(p.text for p in content if isinstance(p, TextPart))
        messages.append(UserMessage(user_text))

        chat = Chat(
            messages=messages,
            model=self._model,
            output_types=[AsyncStreamedStr],
        )
        chat = await chat.asubmit()
        async for chunk in chat.last_message.content:
            if cancel_event and cancel_event.is_set():
                raise GenerationCancelledError()
            yield AgentMessageUpdate(text=chunk)

    async def cancel(self, session_id: str) -> None:
        """Cancel is handled cooperatively via ``cancel_event``.

        Parameters
        ----------
        session_id : str
            Session to cancel.
        """
