"""Abstract base classes for pluggable state storage.

These interfaces define the contract for state backends, enabling
horizontal scaling via Redis or other external stores.
"""

# pylint: disable=unnecessary-ellipsis
# Ellipsis (...) is the standard Python idiom for abstract method bodies

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from pywry.chat import ChatMessage, ChatThread

    from .types import ConnectionInfo, EventMessage, UserSession, WidgetData


class WidgetStore(ABC):
    """Abstract widget storage interface.

    Handles storage and retrieval of widget HTML content and metadata.
    Implementations must be thread-safe and support async operations.

    Notes
    -----
    The widget store is the canonical source of widget HTML, metadata, and
    authentication tokens for both single-process and deploy-mode backends.
    """

    @abstractmethod
    async def register(
        self,
        widget_id: str,
        html: str,
        token: str | None = None,
        owner_worker_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Register a widget with its HTML content.

        Parameters
        ----------
        widget_id : str
            Unique identifier for the widget.
        html : str
            The HTML content of the widget.
        token : str or None
            Optional per-widget authentication token.
        owner_worker_id : str or None
            ID of the worker that created this widget.
        metadata : dict[str, Any] or None
            Additional metadata (title, theme, etc.).
        """
        ...

    @abstractmethod
    async def get(self, widget_id: str) -> WidgetData | None:
        """Get complete widget data.

        Parameters
        ----------
        widget_id : str
            The widget ID to retrieve.

        Returns
        -------
        WidgetData or None
            The widget data if found, None otherwise.
        """
        ...

    @abstractmethod
    async def get_html(self, widget_id: str) -> str | None:
        """Get widget HTML content.

        Parameters
        ----------
        widget_id : str
            The widget ID.

        Returns
        -------
        str or None
            The HTML content if found, None otherwise.
        """
        ...

    @abstractmethod
    async def get_token(self, widget_id: str) -> str | None:
        """Get widget authentication token.

        Parameters
        ----------
        widget_id : str
            The widget ID.

        Returns
        -------
        str or None
            The token if set, None otherwise.
        """
        ...

    @abstractmethod
    async def exists(self, widget_id: str) -> bool:
        """Check if a widget exists.

        Parameters
        ----------
        widget_id : str
            The widget ID.

        Returns
        -------
        bool
            True if the widget exists.
        """
        ...

    @abstractmethod
    async def delete(self, widget_id: str) -> bool:
        """Delete a widget.

        Parameters
        ----------
        widget_id : str
            The widget ID to delete.

        Returns
        -------
        bool
            True if the widget was deleted, False if it didn't exist.
        """
        ...

    @abstractmethod
    async def list_active(self) -> list[str]:
        """List all active widget IDs.

        Returns
        -------
        list[str]
            List of active widget IDs.
        """
        ...

    @abstractmethod
    async def update_html(self, widget_id: str, html: str) -> bool:
        """Update widget HTML content.

        Parameters
        ----------
        widget_id : str
            The widget ID.
        html : str
            The new HTML content.

        Returns
        -------
        bool
            True if updated, False if widget doesn't exist.
        """
        ...

    @abstractmethod
    async def update_token(self, widget_id: str, token: str) -> bool:
        """Update widget authentication token.

        Parameters
        ----------
        widget_id : str
            The widget ID.
        token : str
            The new authentication token.

        Returns
        -------
        bool
            True if updated, False if widget doesn't exist.
        """
        ...

    @abstractmethod
    async def count(self) -> int:
        """Get the number of active widgets.

        Returns
        -------
        int
            Number of active widgets.
        """
        ...


class EventBus(ABC):
    """Abstract event publishing interface.

    Handles cross-worker event delivery for callback dispatch
    and real-time updates.

    Notes
    -----
    EventBus implementations are expected to provide best-effort fan-out for
    widget and worker channels without assuming in-process execution.
    """

    @abstractmethod
    async def publish(self, channel: str, event: EventMessage) -> None:
        """Publish an event to a channel.

        Parameters
        ----------
        channel : str
            The channel name (e.g., "widget:{id}", "worker:{id}").
        event : EventMessage
            The event to publish.
        """
        ...

    @abstractmethod
    async def subscribe(self, channel: str) -> AsyncIterator[EventMessage]:
        """Subscribe to events on a channel.

        Parameters
        ----------
        channel : str
            The channel name.

        Yields
        ------
        EventMessage
            Events received on the channel.
        """
        ...
        yield  # type: ignore[misc]  # pragma: no cover

    @abstractmethod
    async def unsubscribe(self, channel: str) -> None:
        """Unsubscribe from a channel.

        Parameters
        ----------
        channel : str
            The channel to unsubscribe from.
        """
        ...


class ConnectionRouter(ABC):
    """Abstract connection routing interface.

    Tracks which worker owns which WebSocket connection,
    enabling cross-worker message routing.

    Notes
    -----
    Routers are used to decide where outbound callback and state events must be
    forwarded when multiple workers are serving widgets concurrently.
    """

    @abstractmethod
    async def register_connection(
        self,
        widget_id: str,
        worker_id: str,
        user_id: str | None = None,
        session_id: str | None = None,
    ) -> None:
        """Register that a widget is connected to a specific worker.

        Parameters
        ----------
        widget_id : str
            The widget ID.
        worker_id : str
            The worker ID that owns this connection.
        user_id : str or None
            Optional user ID for RBAC.
        session_id : str or None
            Optional session ID for tracking.
        """
        ...

    @abstractmethod
    async def get_connection_info(self, widget_id: str) -> ConnectionInfo | None:
        """Get connection information for a widget.

        Parameters
        ----------
        widget_id : str
            The widget ID.

        Returns
        -------
        ConnectionInfo or None
            Connection information if connected, None otherwise.
        """
        ...

    @abstractmethod
    async def get_owner(self, widget_id: str) -> str | None:
        """Get the worker ID that owns this widget's connection.

        Parameters
        ----------
        widget_id : str
            The widget ID.

        Returns
        -------
        str or None
            The worker ID if connected, None otherwise.
        """
        ...

    @abstractmethod
    async def refresh_heartbeat(self, widget_id: str) -> bool:
        """Refresh the heartbeat timestamp for a connection.

        Parameters
        ----------
        widget_id : str
            The widget ID.

        Returns
        -------
        bool
            True if refreshed, False if connection doesn't exist.
        """
        ...

    @abstractmethod
    async def unregister_connection(self, widget_id: str) -> bool:
        """Unregister a connection.

        Parameters
        ----------
        widget_id : str
            The widget ID.

        Returns
        -------
        bool
            True if unregistered, False if didn't exist.
        """
        ...

    @abstractmethod
    async def list_worker_connections(self, worker_id: str) -> list[str]:
        """List all widget IDs connected to a specific worker.

        Parameters
        ----------
        worker_id : str
            The worker ID.

        Returns
        -------
        list[str]
            List of widget IDs connected to this worker.
        """
        ...


class SessionStore(ABC):
    """Abstract session storage interface for RBAC support.

    Handles user sessions and access control for multi-tenant deployments.

    Notes
    -----
    Session stores back RBAC checks, session expiry, and multi-session user
    tracking for deploy-mode hosting.
    """

    @abstractmethod
    async def create_session(
        self,
        session_id: str,
        user_id: str,
        roles: list[str] | None = None,
        ttl: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> UserSession:
        """Create a new user session.

        Parameters
        ----------
        session_id : str
            Unique session identifier.
        user_id : str
            User identifier.
        roles : list[str] or None
            User roles for access control.
        ttl : int or None
            Time-to-live in seconds (None for no expiry).
        metadata : dict[str, Any] or None
            Additional session metadata.

        Returns
        -------
        UserSession
            The created session.
        """
        ...

    @abstractmethod
    async def get_session(self, session_id: str) -> UserSession | None:
        """Get a session by ID.

        Parameters
        ----------
        session_id : str
            The session ID.

        Returns
        -------
        UserSession or None
            The session if found and not expired, None otherwise.
        """
        ...

    @abstractmethod
    async def validate_session(self, session_id: str) -> bool:
        """Validate a session is active and not expired.

        Parameters
        ----------
        session_id : str
            The session ID.

        Returns
        -------
        bool
            True if the session is valid.
        """
        ...

    @abstractmethod
    async def delete_session(self, session_id: str) -> bool:
        """Delete a session.

        Parameters
        ----------
        session_id : str
            The session ID.

        Returns
        -------
        bool
            True if deleted, False if didn't exist.
        """
        ...

    @abstractmethod
    async def refresh_session(self, session_id: str, extend_ttl: int | None = None) -> bool:
        """Refresh a session's expiry time.

        Parameters
        ----------
        session_id : str
            The session ID.
        extend_ttl : int or None
            New TTL in seconds (None to use original TTL).

        Returns
        -------
        bool
            True if refreshed, False if session doesn't exist.
        """
        ...

    @abstractmethod
    async def list_user_sessions(self, user_id: str) -> list[UserSession]:
        """List all sessions for a user.

        Parameters
        ----------
        user_id : str
            The user ID.

        Returns
        -------
        list[UserSession]
            List of active sessions for this user.
        """
        ...

    @abstractmethod
    async def check_permission(
        self,
        session_id: str,
        resource_type: str,
        resource_id: str,
        permission: str,
    ) -> bool:
        """Check if a session has permission to access a resource.

        Parameters
        ----------
        session_id : str
            The session ID.
        resource_type : str
            The type of resource (e.g., "widget", "user").
        resource_id : str
            The resource identifier.
        permission : str
            The required permission (e.g., "read", "write", "admin").

        Returns
        -------
        bool
            True if the session has the required permission.
        """
        ...


class ChatStore(ABC):
    """Abstract chat storage interface.

    Handles storage and retrieval of chat threads and messages.
    Implementations must be thread-safe and support async operations.

    Notes
    -----
    Chat stores are scoped by widget ID so separate widgets can safely reuse the
    same backend without thread or message leakage.
    """

    @abstractmethod
    async def save_thread(self, widget_id: str, thread: ChatThread) -> None:
        """Save or update a chat thread.

        Parameters
        ----------
        widget_id : str
            The widget that owns this thread.
        thread : ChatThread
            The thread to save.
        """
        ...

    @abstractmethod
    async def get_thread(self, widget_id: str, thread_id: str) -> ChatThread | None:
        """Get a thread by ID.

        Parameters
        ----------
        widget_id : str
            The widget that owns this thread.
        thread_id : str
            The thread ID.

        Returns
        -------
        ChatThread or None
            The thread if found, None otherwise.
        """
        ...

    @abstractmethod
    async def list_threads(self, widget_id: str) -> list[ChatThread]:
        """List all threads for a widget.

        Parameters
        ----------
        widget_id : str
            The widget ID.

        Returns
        -------
        list[ChatThread]
            All threads for this widget.
        """
        ...

    @abstractmethod
    async def delete_thread(self, widget_id: str, thread_id: str) -> bool:
        """Delete a thread.

        Parameters
        ----------
        widget_id : str
            The widget ID.
        thread_id : str
            The thread to delete.

        Returns
        -------
        bool
            True if deleted, False if not found.
        """
        ...

    @abstractmethod
    async def append_message(self, widget_id: str, thread_id: str, message: ChatMessage) -> None:
        """Append a message to a thread.

        Implementations should enforce MAX_MESSAGES_PER_THREAD and
        evict oldest messages when exceeded.

        Parameters
        ----------
        widget_id : str
            The widget ID.
        thread_id : str
            The thread ID.
        message : ChatMessage
            The message to append.
        """
        ...

    @abstractmethod
    async def get_messages(
        self,
        widget_id: str,
        thread_id: str,
        limit: int = 50,
        before_id: str | None = None,
    ) -> list[ChatMessage]:
        """Get messages from a thread with cursor-based pagination.

        Parameters
        ----------
        widget_id : str
            The widget ID.
        thread_id : str
            The thread ID.
        limit : int
            Maximum number of messages to return.
        before_id : str or None
            Return messages before this message ID (for pagination).

        Returns
        -------
        list[ChatMessage]
            Messages in chronological order.
        """
        ...

    @abstractmethod
    async def clear_messages(self, widget_id: str, thread_id: str) -> None:
        """Clear all messages from a thread.

        Parameters
        ----------
        widget_id : str
            The widget ID.
        thread_id : str
            The thread ID.
        """
        ...


class ChartStore(ABC):
    """Abstract chart layout/settings storage interface.

    Handles persistence of TradingView chart layouts and settings
    templates.  Implementations must be thread-safe and support async
    operations.

    Notes
    -----
    Chart stores are scoped by ``user_id``.  In single-user mode the
    caller passes ``"default"``; in deploy mode the actual user identity
    is resolved from the session.
    """

    @abstractmethod
    async def save_layout(
        self,
        user_id: str,
        layout_id: str,
        name: str,
        data_json: str,
        *,
        summary: str = "",
    ) -> dict[str, Any]:
        """Save or update a chart layout.

        Parameters
        ----------
        user_id : str
            Owner of the layout.
        layout_id : str
            Unique layout identifier.
        name : str
            Human-readable layout name.
        data_json : str
            Serialized layout data (JSON string).
        summary : str
            Short description of indicators/drawings in the layout.

        Returns
        -------
        dict[str, Any]
            Index entry with id, name, savedAt, summary.
        """
        ...

    @abstractmethod
    async def get_layout(self, user_id: str, layout_id: str) -> str | None:
        """Get layout data by ID.

        Parameters
        ----------
        user_id : str
            Owner of the layout.
        layout_id : str
            Layout identifier.

        Returns
        -------
        str or None
            Raw JSON string of the layout, or None if not found.
        """
        ...

    @abstractmethod
    async def list_layouts(self, user_id: str) -> list[dict[str, Any]]:
        """List all layout index entries for a user.

        Parameters
        ----------
        user_id : str
            Owner of the layouts.

        Returns
        -------
        list[dict[str, Any]]
            Index entries sorted by savedAt descending.
        """
        ...

    @abstractmethod
    async def delete_layout(self, user_id: str, layout_id: str) -> bool:
        """Delete a layout.

        Parameters
        ----------
        user_id : str
            Owner of the layout.
        layout_id : str
            Layout identifier.

        Returns
        -------
        bool
            True if deleted, False if not found.
        """
        ...

    @abstractmethod
    async def rename_layout(self, user_id: str, layout_id: str, new_name: str) -> bool:
        """Rename a layout.

        Parameters
        ----------
        user_id : str
            Owner of the layout.
        layout_id : str
            Layout identifier.
        new_name : str
            New human-readable name.

        Returns
        -------
        bool
            True if renamed, False if not found.
        """
        ...

    async def update_layout_meta(
        self,
        user_id: str,
        layout_id: str,
        *,
        name: str = "",
        summary: str = "",
    ) -> bool:
        """Update metadata for an existing layout index entry.

        Parameters
        ----------
        user_id : str
            Owner of the layout.
        layout_id : str
            Layout identifier.
        name : str
            Human-readable name.
        summary : str
            Short description of layout contents.

        Returns
        -------
        bool
            True if updated, False if not found.
        """
        return await self.rename_layout(user_id, layout_id, name)

    @abstractmethod
    async def save_settings_template(self, user_id: str, template_json: str) -> None:
        """Save a custom settings template.

        Parameters
        ----------
        user_id : str
            Owner of the template.
        template_json : str
            Serialized template (JSON string).
        """
        ...

    @abstractmethod
    async def get_settings_template(self, user_id: str) -> str | None:
        """Get the custom settings template.

        Parameters
        ----------
        user_id : str
            Owner of the template.

        Returns
        -------
        str or None
            Raw JSON string, or None if no custom template is set.
        """
        ...

    @abstractmethod
    async def get_settings_default_id(self, user_id: str) -> str:
        """Get which settings template is active.

        Parameters
        ----------
        user_id : str
            Owner.

        Returns
        -------
        str
            ``"factory"`` or ``"custom"``.
        """
        ...

    @abstractmethod
    async def set_settings_default_id(self, user_id: str, template_id: str) -> None:
        """Set which settings template is active.

        Parameters
        ----------
        user_id : str
            Owner.
        template_id : str
            ``"factory"`` or ``"custom"``.
        """
        ...

    @abstractmethod
    async def clear_settings_template(self, user_id: str) -> None:
        """Remove the custom settings template and reset to factory.

        Parameters
        ----------
        user_id : str
            Owner.
        """
        ...
