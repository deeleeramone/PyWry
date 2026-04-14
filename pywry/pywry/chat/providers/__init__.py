"""ACP-conformant provider interface and factory.

All providers implement the ``ChatProvider`` ABC, which follows the
ACP session lifecycle: ``initialize`` → ``new_session`` → ``prompt``
loop → ``cancel``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    import asyncio

    from collections.abc import AsyncIterator

    from ..models import ContentBlock
    from ..session import (
        AgentCapabilities,
        ClientCapabilities,
        SessionConfigOption,
    )
    from ..updates import SessionUpdate


class ChatProvider(ABC):
    """Abstract base class for ACP-conformant chat providers.

    Providers adapt third-party LLM clients or external ACP agents to
    the ACP session lifecycle. They accept content blocks, manage
    sessions, and yield typed ``SessionUpdate`` notifications.
    """

    @abstractmethod
    async def initialize(
        self,
        capabilities: ClientCapabilities,
    ) -> AgentCapabilities:
        """Negotiate protocol version and capabilities.

        Parameters
        ----------
        capabilities : ClientCapabilities
            Features the client supports.

        Returns
        -------
        AgentCapabilities
            Features the agent supports.
        """

    @abstractmethod
    async def new_session(
        self,
        cwd: str,
        mcp_servers: list[dict[str, Any]] | None = None,
    ) -> str:
        """Create a new conversation session.

        Parameters
        ----------
        cwd : str
            Working directory context for file operations.
        mcp_servers : list[dict[str, Any]] | None
            Optional MCP server configurations.

        Returns
        -------
        str
            Unique session identifier.
        """

    @abstractmethod
    async def prompt(
        self,
        session_id: str,
        content: list[ContentBlock],
        cancel_event: asyncio.Event | None = None,
    ) -> AsyncIterator[SessionUpdate]:
        """Process a user prompt and stream session updates.

        Parameters
        ----------
        session_id : str
            Active session identifier from ``new_session()``.
        content : list[ContentBlock]
            User message content blocks.
        cancel_event : asyncio.Event | None, optional
            Cooperative cancellation signal.

        Yields
        ------
        SessionUpdate
            Typed update notifications.
        """
        yield  # type: ignore[misc]  # pragma: no cover

    @abstractmethod
    async def cancel(self, session_id: str) -> None:
        """Cancel an ongoing prompt turn.

        Parameters
        ----------
        session_id : str
            Session to cancel.
        """

    async def load_session(self, session_id: str, cwd: str) -> str:
        """Resume a prior session.

        Parameters
        ----------
        session_id : str
            Session identifier to restore.
        cwd : str
            Working directory context.

        Returns
        -------
        str
            The restored session identifier.

        Raises
        ------
        NotImplementedError
            If the provider does not support session loading.
        """
        raise NotImplementedError(f"{type(self).__name__} does not support session loading")

    async def set_config_option(
        self,
        session_id: str,
        option_id: str,
        value: str,
    ) -> list[SessionConfigOption]:
        """Change a config option, return full config state.

        Parameters
        ----------
        session_id : str
            Active session identifier.
        option_id : str
            Config option to change.
        value : str
            New value.

        Returns
        -------
        list[SessionConfigOption]
            Complete set of config options with current values.
        """
        return []

    async def set_mode(self, session_id: str, mode_id: str) -> None:
        """Switch agent mode.

        Parameters
        ----------
        session_id : str
            Active session identifier.
        mode_id : str
            Mode to activate.
        """
        return


def get_provider(name: str, **kwargs: Any) -> ChatProvider:
    """Create a provider instance by name.

    Parameters
    ----------
    name : str
        Provider name. Supported values: ``"openai"``, ``"anthropic"``,
        ``"callback"``, ``"magentic"``, ``"stdio"``.
    **kwargs
        Passed to the provider constructor.

    Returns
    -------
    ChatProvider
        Instantiated provider.

    Raises
    ------
    ValueError
        If provider name is unknown.
    """
    providers: dict[str, str] = {
        "openai": ".openai",
        "anthropic": ".anthropic",
        "callback": ".callback",
        "magentic": ".magentic",
        "stdio": ".stdio",
        "deepagent": ".deepagent",
    }

    module_name = providers.get(name)
    if not module_name:
        available = ", ".join(providers)
        raise ValueError(f"Unknown provider: {name!r}. Available: {available}")

    import importlib

    module = importlib.import_module(module_name, package=__package__)

    # Convention: each module exports a class named {Name}Provider
    cls_name = name.capitalize() + "Provider"
    cls = getattr(module, cls_name)
    return cls(**kwargs)
