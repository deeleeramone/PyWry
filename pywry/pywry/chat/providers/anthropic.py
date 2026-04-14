"""Anthropic provider adapter for the ACP session interface.

Wraps the ``anthropic`` async client to implement the ``ChatProvider``
ABC. All imports are lazy to avoid hard dependencies.
"""

from __future__ import annotations

import uuid

from typing import TYPE_CHECKING, Any, cast

from . import ChatProvider


if TYPE_CHECKING:
    import asyncio

    from collections.abc import AsyncIterator

    from ..models import ContentBlock
    from ..session import AgentCapabilities, ClientCapabilities
    from ..updates import SessionUpdate


class AnthropicProvider(ChatProvider):
    """Provider backed by the ``anthropic`` async client.

    Parameters
    ----------
    **kwargs
        Keyword arguments forwarded to ``anthropic.AsyncAnthropic``
        (e.g. ``api_key``).

    Raises
    ------
    ImportError
        If the ``anthropic`` package is not installed.
    """

    def __init__(self, **kwargs: Any) -> None:
        try:
            from anthropic import AsyncAnthropic
        except ImportError as exc:
            raise ImportError("AnthropicProvider requires: pip install 'pywry[anthropic]'") from exc
        self._client = AsyncAnthropic(**kwargs)
        self._sessions: dict[str, dict[str, Any]] = {}

    async def initialize(
        self,
        capabilities: ClientCapabilities,
    ) -> AgentCapabilities:
        """Return text+image prompt capabilities.

        Parameters
        ----------
        capabilities : ClientCapabilities
            Client features (unused by Anthropic adapter).

        Returns
        -------
        AgentCapabilities
            Advertises text and image prompt support.
        """
        from ..session import AgentCapabilities, PromptCapabilities

        return AgentCapabilities(
            promptCapabilities=PromptCapabilities(image=True),
        )

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
            MCP server configs (unused by Anthropic adapter).

        Returns
        -------
        str
            Unique session identifier.
        """
        session_id = f"ant_{uuid.uuid4().hex[:8]}"
        self._sessions[session_id] = {
            "cwd": cwd,
            "system_prompt": "",
            "model": "claude-sonnet-4-20250514",
            "temperature": 0.7,
            "max_tokens": 4096,
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

        session = self._sessions.get(session_id, {})

        # Convert content blocks to Anthropic message format
        user_text = "".join(p.text for p in content if isinstance(p, TextPart))
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": user_text},
        ]

        async with self._client.messages.stream(
            model=session.get("model", "claude-sonnet-4-20250514"),
            messages=cast("Any", messages),
            system=session.get("system_prompt", ""),
            temperature=session.get("temperature", 0.7),
            max_tokens=session.get("max_tokens", 4096),
        ) as stream:
            async for text in stream.text_stream:
                if cancel_event and cancel_event.is_set():
                    raise GenerationCancelledError()
                yield AgentMessageUpdate(text=text)

    async def cancel(self, session_id: str) -> None:
        """Cancel is handled cooperatively via ``cancel_event``.

        Parameters
        ----------
        session_id : str
            Session to cancel.
        """
