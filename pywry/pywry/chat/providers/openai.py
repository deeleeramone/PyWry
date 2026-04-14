"""OpenAI provider adapter for the ACP session interface.

Wraps the ``openai`` async client to implement the ``ChatProvider`` ABC.
All imports are lazy to avoid hard dependencies.
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


class OpenAIProvider(ChatProvider):
    """Provider backed by the ``openai`` async client.

    Parameters
    ----------
    **kwargs
        Keyword arguments forwarded to ``openai.AsyncOpenAI``
        (e.g. ``api_key``, ``base_url``).

    Raises
    ------
    ImportError
        If the ``openai`` package is not installed.
    """

    def __init__(self, **kwargs: Any) -> None:
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise ImportError("OpenAIProvider requires: pip install 'pywry[openai]'") from exc
        self._client = AsyncOpenAI(**kwargs)
        self._sessions: dict[str, dict[str, Any]] = {}

    async def initialize(
        self,
        capabilities: ClientCapabilities,
    ) -> AgentCapabilities:
        """Return text-only prompt capabilities.

        Parameters
        ----------
        capabilities : ClientCapabilities
            Client features (unused by OpenAI adapter).

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
            MCP server configs (unused by OpenAI adapter).

        Returns
        -------
        str
            Unique session identifier.
        """
        session_id = f"oai_{uuid.uuid4().hex[:8]}"
        self._sessions[session_id] = {
            "cwd": cwd,
            "system_prompt": "",
            "model": "gpt-4",
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
        messages: list[dict[str, Any]] = []

        if session.get("system_prompt"):
            messages.append(
                {
                    "role": "system",
                    "content": session["system_prompt"],
                }
            )

        # Convert content blocks to OpenAI message format
        user_text = "".join(p.text for p in content if isinstance(p, TextPart))
        messages.append({"role": "user", "content": user_text})

        stream_resp: Any = await self._client.chat.completions.create(
            model=session.get("model", "gpt-4"),
            messages=cast("Any", messages),
            temperature=session.get("temperature", 0.7),
            max_tokens=session.get("max_tokens", 4096),
            stream=True,
        )

        try:
            async for chunk in stream_resp:
                if cancel_event and cancel_event.is_set():
                    raise GenerationCancelledError()
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    yield AgentMessageUpdate(text=delta.content)
        finally:
            await stream_resp.response.aclose()

    async def cancel(self, session_id: str) -> None:
        """Cancel is handled cooperatively via ``cancel_event``.

        Parameters
        ----------
        session_id : str
            Session to cancel.
        """
