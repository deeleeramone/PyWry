"""Callback provider adapter for the ACP session interface.

Wraps user-supplied Python callables to implement the ``ChatProvider``
ABC. The callable should accept ``(session_id, content_blocks,
cancel_event)`` and yield ``SessionUpdate`` objects or plain strings.
"""

from __future__ import annotations

import asyncio
import uuid

from typing import TYPE_CHECKING, Any

from . import ChatProvider


if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from ..models import ContentBlock
    from ..session import AgentCapabilities, ClientCapabilities
    from ..updates import SessionUpdate


class CallbackProvider(ChatProvider):
    """Provider backed by user-supplied Python callables.

    Parameters
    ----------
    prompt_fn : callable, optional
        Callable invoked on each prompt. It may be sync or async,
        and should yield ``SessionUpdate`` objects or plain strings
        (which are wrapped as ``AgentMessageUpdate``).
    """

    def __init__(self, prompt_fn: Any = None) -> None:
        self._prompt_fn = prompt_fn

    async def initialize(
        self,
        capabilities: ClientCapabilities,
    ) -> AgentCapabilities:
        """Return minimal capabilities.

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
        """Create a lightweight session identifier.

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
        return f"cb_{uuid.uuid4().hex[:8]}"

    async def prompt(
        self,
        session_id: str,
        content: list[ContentBlock],
        cancel_event: asyncio.Event | None = None,
    ) -> AsyncIterator[SessionUpdate]:
        """Invoke the user callback and yield session updates.

        Plain strings yielded by the callback are wrapped as
        ``AgentMessageUpdate``. ``SessionUpdate`` instances are
        yielded as-is.

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
            Updates from the callback.
        """
        from ..updates import AgentMessageUpdate

        if not self._prompt_fn:
            yield AgentMessageUpdate(text="No prompt callback configured.")
            return

        import inspect

        result = self._prompt_fn(session_id, content, cancel_event)

        if inspect.isgenerator(result) or inspect.isasyncgen(result):
            async for update in self._iter_result(result, cancel_event):
                yield update
            return

        if inspect.iscoroutine(result):
            result = await result

        if isinstance(result, str):
            yield AgentMessageUpdate(text=result)
            return

        if hasattr(result, "__aiter__") or hasattr(result, "__next__"):
            async for update in self._iter_result(result, cancel_event):
                yield update
            return

        yield AgentMessageUpdate(text=str(result))

    @staticmethod
    async def _iter_result(result: Any, cancel_event: Any) -> AsyncIterator[SessionUpdate]:
        """Iterate a sync or async result, wrapping strings."""
        from ..models import GenerationCancelledError
        from ..updates import AgentMessageUpdate

        def _wrap(item: Any) -> Any:
            return AgentMessageUpdate(text=item) if isinstance(item, str) else item

        if hasattr(result, "__aiter__"):
            async for item in result:
                if cancel_event and cancel_event.is_set():
                    raise GenerationCancelledError()
                yield _wrap(item)
        elif hasattr(result, "__iter__"):
            for item in result:
                if cancel_event and cancel_event.is_set():
                    raise GenerationCancelledError()
                yield _wrap(item)

    async def cancel(self, session_id: str) -> None:
        """Cancel is handled cooperatively via ``cancel_event``.

        Parameters
        ----------
        session_id : str
            Session to cancel.
        """
