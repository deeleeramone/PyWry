"""In-memory state store implementations.

Default backend for single-process deployments and development.
"""

from __future__ import annotations

import asyncio
import contextlib
import time

from typing import TYPE_CHECKING, Any

from .base import ChartStore, ChatStore, ConnectionRouter, EventBus, SessionStore, WidgetStore
from .types import ConnectionInfo, EventMessage, UserSession, WidgetData


if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from pywry.chat import ChatMessage, ChatThread


class MemoryWidgetStore(WidgetStore):
    """In-memory widget store for single-process deployments.

    Thread-safe implementation using asyncio locks.

    Attributes
    ----------
    _widgets : dict[str, WidgetData]
        In-memory mapping of widget IDs to widget state.
    _lock : asyncio.Lock
        Synchronizes concurrent access to the in-memory mapping.
    """

    def __init__(self) -> None:
        """Initialize the in-memory widget store."""
        self._widgets: dict[str, WidgetData] = {}
        self._lock = asyncio.Lock()

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
            Widget identifier.
        html : str
            Initial widget HTML.
        token : str | None, optional
            Optional authentication token associated with the widget.
        owner_worker_id : str | None, optional
            Worker ID recorded for deploy-mode compatibility.
        metadata : dict[str, Any] | None, optional
            Arbitrary widget metadata.
        """
        async with self._lock:
            self._widgets[widget_id] = WidgetData(
                widget_id=widget_id,
                html=html,
                token=token,
                created_at=time.time(),
                owner_worker_id=owner_worker_id,
                metadata=metadata or {},
            )

    async def get(self, widget_id: str) -> WidgetData | None:
        """Get complete widget data.

        Parameters
        ----------
        widget_id : str
            Widget identifier to retrieve.

        Returns
        -------
        WidgetData | None
            Stored widget data, or None when the widget is unknown.
        """
        async with self._lock:
            return self._widgets.get(widget_id)

    async def get_html(self, widget_id: str) -> str | None:
        """Get widget HTML content.

        Parameters
        ----------
        widget_id : str
            Widget identifier.

        Returns
        -------
        str | None
            Stored HTML, or None when the widget is unknown.
        """
        async with self._lock:
            widget = self._widgets.get(widget_id)
            return widget.html if widget else None

    async def get_token(self, widget_id: str) -> str | None:
        """Get widget authentication token.

        Parameters
        ----------
        widget_id : str
            Widget identifier.

        Returns
        -------
        str | None
            Stored token, or None when no token is set.
        """
        async with self._lock:
            widget = self._widgets.get(widget_id)
            return widget.token if widget else None

    async def exists(self, widget_id: str) -> bool:
        """Check if a widget exists.

        Parameters
        ----------
        widget_id : str
            Widget identifier.

        Returns
        -------
        bool
            True when the widget exists in memory.
        """
        async with self._lock:
            return widget_id in self._widgets

    async def delete(self, widget_id: str) -> bool:
        """Delete a widget.

        Parameters
        ----------
        widget_id : str
            Widget identifier.

        Returns
        -------
        bool
            True when the widget existed and was removed.
        """
        async with self._lock:
            if widget_id in self._widgets:
                del self._widgets[widget_id]
                return True
            return False

    async def list_active(self) -> list[str]:
        """List all active widget IDs.

        Returns
        -------
        list[str]
            All widget IDs currently stored in memory.
        """
        async with self._lock:
            return list(self._widgets.keys())

    async def update_html(self, widget_id: str, html: str) -> bool:
        """Update widget HTML content.

        Parameters
        ----------
        widget_id : str
            Widget identifier.
        html : str
            Replacement HTML content.

        Returns
        -------
        bool
            True when the widget existed and was updated.
        """
        async with self._lock:
            if widget_id in self._widgets:
                self._widgets[widget_id].html = html
                return True
            return False

    async def update_token(self, widget_id: str, token: str) -> bool:
        """Update widget authentication token.

        Parameters
        ----------
        widget_id : str
            Widget identifier.
        token : str
            Replacement authentication token.

        Returns
        -------
        bool
            True when the widget existed and was updated.
        """
        async with self._lock:
            if widget_id in self._widgets:
                self._widgets[widget_id].token = token
                return True
            return False

    async def count(self) -> int:
        """Get the number of active widgets.

        Returns
        -------
        int
            Count of widgets stored in memory.
        """
        async with self._lock:
            return len(self._widgets)


class MemoryEventBus(EventBus):
    """In-memory event bus for single-process deployments.

    Uses asyncio.Queue for inter-task communication.

    Attributes
    ----------
    _channels : dict[str, list[asyncio.Queue[EventMessage]]]
        Active subscriber queues keyed by channel name.
    _lock : asyncio.Lock
        Synchronizes channel registration and removal.
    """

    def __init__(self) -> None:
        """Initialize the in-memory event bus."""
        self._channels: dict[str, list[asyncio.Queue[EventMessage]]] = {}
        self._lock = asyncio.Lock()

    async def publish(self, channel: str, event: EventMessage) -> None:
        """Publish an event to a channel.

        Parameters
        ----------
        channel : str
            Channel name to publish to.
        event : EventMessage
            Event payload to fan out to subscribers.
        """
        async with self._lock:
            queues = self._channels.get(channel, [])
            for q in queues:
                with contextlib.suppress(asyncio.QueueFull):
                    q.put_nowait(event)

    async def subscribe(self, channel: str) -> AsyncIterator[EventMessage]:
        """Subscribe to events on a channel.

        Parameters
        ----------
        channel : str
            Channel name to subscribe to.

        Yields
        ------
        EventMessage
            Event payloads published to the subscribed channel.
        """
        q: asyncio.Queue[EventMessage] = asyncio.Queue(maxsize=1000)

        async with self._lock:
            if channel not in self._channels:
                self._channels[channel] = []
            self._channels[channel].append(q)

        try:
            while True:
                event = await q.get()
                yield event
        finally:
            async with self._lock:
                if channel in self._channels:
                    with contextlib.suppress(ValueError):
                        self._channels[channel].remove(q)
                    if not self._channels[channel]:
                        del self._channels[channel]

    async def unsubscribe(self, channel: str) -> None:
        """Unsubscribe from a channel.

        Parameters
        ----------
        channel : str
            Channel name whose subscribers should be removed.

        Notes
        -----
        This implementation clears all subscribers for the channel.
        """
        async with self._lock:
            self._channels.pop(channel, None)


class MemoryConnectionRouter(ConnectionRouter):
    """In-memory connection router for single-process deployments.

    Attributes
    ----------
    _connections : dict[str, ConnectionInfo]
        Connection metadata keyed by widget ID.
    _worker_connections : dict[str, set[str]]
        Reverse index of widget IDs by owning worker.
    _lock : asyncio.Lock
        Synchronizes access to connection registries.
    """

    def __init__(self) -> None:
        """Initialize the in-memory connection router."""
        self._connections: dict[str, ConnectionInfo] = {}
        self._worker_connections: dict[str, set[str]] = {}
        self._lock = asyncio.Lock()

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
            Widget identifier.
        worker_id : str
            Worker currently serving the widget connection.
        user_id : str | None, optional
            Optional user identifier associated with the connection.
        session_id : str | None, optional
            Optional session identifier associated with the connection.
        """
        async with self._lock:
            now = time.time()
            self._connections[widget_id] = ConnectionInfo(
                widget_id=widget_id,
                worker_id=worker_id,
                connected_at=now,
                last_heartbeat=now,
                user_id=user_id,
                session_id=session_id,
            )
            if worker_id not in self._worker_connections:
                self._worker_connections[worker_id] = set()
            self._worker_connections[worker_id].add(widget_id)

    async def get_connection_info(self, widget_id: str) -> ConnectionInfo | None:
        """Get connection information for a widget.

        Parameters
        ----------
        widget_id : str
            Widget identifier.

        Returns
        -------
        ConnectionInfo | None
            Stored connection metadata, or None when disconnected.
        """
        async with self._lock:
            return self._connections.get(widget_id)

    async def get_owner(self, widget_id: str) -> str | None:
        """Get the worker ID that owns this widget's connection.

        Parameters
        ----------
        widget_id : str
            Widget identifier.

        Returns
        -------
        str | None
            Owning worker ID, or None when disconnected.
        """
        async with self._lock:
            conn = self._connections.get(widget_id)
            return conn.worker_id if conn else None

    async def refresh_heartbeat(self, widget_id: str) -> bool:
        """Refresh the heartbeat timestamp for a connection.

        Parameters
        ----------
        widget_id : str
            Widget identifier.

        Returns
        -------
        bool
            True when the connection exists and was updated.
        """
        async with self._lock:
            if widget_id in self._connections:
                self._connections[widget_id].last_heartbeat = time.time()
                return True
            return False

    async def unregister_connection(self, widget_id: str) -> bool:
        """Unregister a connection.

        Parameters
        ----------
        widget_id : str
            Widget identifier.

        Returns
        -------
        bool
            True when the connection existed and was removed.
        """
        async with self._lock:
            if widget_id in self._connections:
                conn = self._connections.pop(widget_id)
                if conn.worker_id in self._worker_connections:
                    self._worker_connections[conn.worker_id].discard(widget_id)
                return True
            return False

    async def list_worker_connections(self, worker_id: str) -> list[str]:
        """List all widget IDs connected to a specific worker.

        Parameters
        ----------
        worker_id : str
            Worker identifier.

        Returns
        -------
        list[str]
            Widget IDs currently assigned to the worker.
        """
        async with self._lock:
            return list(self._worker_connections.get(worker_id, set()))


class MemorySessionStore(SessionStore):
    """In-memory session store for RBAC support.

    For single-process deployments and development.

    Attributes
    ----------
    _sessions : dict[str, UserSession]
        Active sessions keyed by session ID.
    _user_sessions : dict[str, set[str]]
        Reverse index of session IDs by user.
    _role_permissions : dict[str, set[str]]
        Simple in-memory role-to-permission mapping.
    _lock : asyncio.Lock
        Synchronizes session and permission updates.
    """

    def __init__(self) -> None:
        """Initialize the in-memory session store."""
        self._sessions: dict[str, UserSession] = {}
        self._user_sessions: dict[str, set[str]] = {}
        # Simple role-based permissions: role -> set of permissions
        self._role_permissions: dict[str, set[str]] = {
            "admin": {"read", "write", "admin"},
            "editor": {"read", "write"},
            "viewer": {"read"},
        }
        self._lock = asyncio.Lock()

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
            Session identifier.
        user_id : str
            User identifier.
        roles : list[str] | None, optional
            Roles granted to the user.
        ttl : int | None, optional
            Session lifetime in seconds.
        metadata : dict[str, Any] | None, optional
            Arbitrary session metadata.

        Returns
        -------
        UserSession
            Newly created in-memory session record.
        """
        async with self._lock:
            now = time.time()
            expires_at = now + ttl if ttl else None

            session = UserSession(
                session_id=session_id,
                user_id=user_id,
                roles=roles or [],
                created_at=now,
                expires_at=expires_at,
                metadata=metadata or {},
            )

            self._sessions[session_id] = session
            if user_id not in self._user_sessions:
                self._user_sessions[user_id] = set()
            self._user_sessions[user_id].add(session_id)

            return session

    async def get_session(self, session_id: str) -> UserSession | None:
        """Get a session by ID.

        Parameters
        ----------
        session_id : str
            Session identifier.

        Returns
        -------
        UserSession | None
            Active session record, or None when absent or expired.
        """
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None

            # Check expiry
            if session.expires_at and session.expires_at < time.time():
                # Session expired, clean up
                self._sessions.pop(session_id, None)
                if session.user_id in self._user_sessions:
                    self._user_sessions[session.user_id].discard(session_id)
                return None

            return session

    async def validate_session(self, session_id: str) -> bool:
        """Validate a session is active and not expired.

        Parameters
        ----------
        session_id : str
            Session identifier.

        Returns
        -------
        bool
            True when the session exists and has not expired.
        """
        session = await self.get_session(session_id)
        return session is not None

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session.

        Parameters
        ----------
        session_id : str
            Session identifier.

        Returns
        -------
        bool
            True when the session existed and was removed.
        """
        async with self._lock:
            if session_id in self._sessions:
                session = self._sessions.pop(session_id)
                if session.user_id in self._user_sessions:
                    self._user_sessions[session.user_id].discard(session_id)
                return True
            return False

    async def refresh_session(self, session_id: str, extend_ttl: int | None = None) -> bool:
        """Refresh a session's expiry time.

        Parameters
        ----------
        session_id : str
            Session identifier.
        extend_ttl : int | None, optional
            New TTL in seconds. When omitted, the original TTL duration is reused.

        Returns
        -------
        bool
            True when the session exists and remains active after refresh.
        """
        async with self._lock:
            if session_id not in self._sessions:
                return False

            session = self._sessions[session_id]

            # Check if already expired
            if session.expires_at and session.expires_at < time.time():
                return False

            # Extend TTL if provided
            if extend_ttl is not None:
                session.expires_at = time.time() + extend_ttl
            elif session.expires_at is not None:
                # Use original TTL duration
                original_ttl = session.expires_at - session.created_at
                session.expires_at = time.time() + original_ttl

            return True

    async def list_user_sessions(self, user_id: str) -> list[UserSession]:
        """List all sessions for a user.

        Parameters
        ----------
        user_id : str
            User identifier.

        Returns
        -------
        list[UserSession]
            Active sessions currently associated with the user.
        """
        async with self._lock:
            session_ids = self._user_sessions.get(user_id, set())
            sessions = []
            now = time.time()

            for sid in list(session_ids):
                session = self._sessions.get(sid)
                if session:
                    # Check expiry
                    if session.expires_at and session.expires_at < now:
                        # Clean up expired
                        self._sessions.pop(sid, None)
                        session_ids.discard(sid)
                    else:
                        sessions.append(session)

            return sessions

    async def check_permission(
        self,
        session_id: str,
        _resource_type: str,
        _resource_id: str,
        permission: str,
    ) -> bool:
        """Check if a session has permission to access a resource.

        Currently implements simple role-based access control.
        Resource-specific permissions can be added via metadata.

        Parameters
        ----------
        session_id : str
            Session identifier.
        _resource_type : str
            Resource type placeholder for interface compatibility.
        _resource_id : str
            Resource identifier placeholder for interface compatibility.
        permission : str
            Permission to test.

        Returns
        -------
        bool
            True when any of the session's roles grants the requested permission.
        """
        session = await self.get_session(session_id)
        if session is None:
            return False

        # Check role-based permissions
        for role in session.roles:
            role_perms = self._role_permissions.get(role, set())
            if permission in role_perms:
                return True

        return False

    def set_role_permissions(self, role: str, permissions: set[str]) -> None:
        """Configure permissions for a role.

        Parameters
        ----------
        role : str
            Role name to update.
        permissions : set[str]
            Permissions granted to the role.

        Notes
        -----
        This method is synchronous because it is intended for startup-time setup.
        """
        self._role_permissions[role] = permissions


class MemoryChatStore(ChatStore):
    """In-memory chat store for single-process deployments.

    Thread-safe implementation using asyncio locks.

    Attributes
    ----------
    _threads : dict[str, dict[str, ChatThread]]
        Chat threads organized first by widget ID and then by thread ID.
    _lock : asyncio.Lock
        Synchronizes concurrent access to chat state.
    """

    def __init__(self) -> None:
        """Initialize the in-memory chat store."""
        # {widget_id: {thread_id: ChatThread}}
        self._threads: dict[str, dict[str, ChatThread]] = {}
        self._lock = asyncio.Lock()

    async def save_thread(self, widget_id: str, thread: ChatThread) -> None:
        """Save or update a chat thread.

        Parameters
        ----------
        widget_id : str
            Widget identifier that owns the thread.
        thread : ChatThread
            Thread record to store.
        """
        async with self._lock:
            if widget_id not in self._threads:
                self._threads[widget_id] = {}
            self._threads[widget_id][thread.thread_id] = thread

    async def get_thread(self, widget_id: str, thread_id: str) -> ChatThread | None:
        """Get a thread by ID.

        Parameters
        ----------
        widget_id : str
            Widget identifier.
        thread_id : str
            Thread identifier.

        Returns
        -------
        ChatThread | None
            Stored thread, or None when not found.
        """
        async with self._lock:
            widget_threads = self._threads.get(widget_id, {})
            return widget_threads.get(thread_id)

    async def list_threads(self, widget_id: str) -> list[ChatThread]:
        """List all threads for a widget.

        Parameters
        ----------
        widget_id : str
            Widget identifier.

        Returns
        -------
        list[ChatThread]
            Threads currently stored for the widget.
        """
        async with self._lock:
            widget_threads = self._threads.get(widget_id, {})
            return list(widget_threads.values())

    async def delete_thread(self, widget_id: str, thread_id: str) -> bool:
        """Delete a thread.

        Parameters
        ----------
        widget_id : str
            Widget identifier.
        thread_id : str
            Thread identifier.

        Returns
        -------
        bool
            True when the thread existed and was removed.
        """
        async with self._lock:
            widget_threads = self._threads.get(widget_id, {})
            if thread_id in widget_threads:
                del widget_threads[thread_id]
                return True
            return False

    async def append_message(self, widget_id: str, thread_id: str, message: ChatMessage) -> None:
        """Append a message to a thread, evicting oldest entries if needed.

        Parameters
        ----------
        widget_id : str
            Widget identifier.
        thread_id : str
            Thread identifier.
        message : ChatMessage
            Message to append to the thread.

        Notes
        -----
        When the thread exceeds ``MAX_MESSAGES_PER_THREAD``, only the most recent
        messages are retained.
        """
        from pywry.chat import MAX_MESSAGES_PER_THREAD

        async with self._lock:
            widget_threads = self._threads.get(widget_id, {})
            thread = widget_threads.get(thread_id)
            if thread is None:
                return
            thread.messages.append(message)
            # Evict oldest messages when over limit
            if len(thread.messages) > MAX_MESSAGES_PER_THREAD:
                thread.messages = thread.messages[-MAX_MESSAGES_PER_THREAD:]
            thread.updated_at = time.time()

    async def get_messages(
        self,
        widget_id: str,
        thread_id: str,
        limit: int = 50,
        before_id: str | None = None,
    ) -> list[ChatMessage]:
        """Get messages with cursor-based pagination.

        Parameters
        ----------
        widget_id : str
            Widget identifier.
        thread_id : str
            Thread identifier.
        limit : int, optional
            Maximum number of messages to return.
        before_id : str | None, optional
            Cursor message ID; only earlier messages are returned.

        Returns
        -------
        list[ChatMessage]
            Messages in chronological order, truncated to the requested window.
        """
        async with self._lock:
            widget_threads = self._threads.get(widget_id, {})
            thread = widget_threads.get(thread_id)
            if thread is None:
                return []

            msgs = thread.messages

            if before_id is not None:
                # Find the index of the cursor message
                idx = next(
                    (i for i, m in enumerate(msgs) if m.message_id == before_id),
                    None,
                )
                if idx is not None:
                    msgs = msgs[:idx]

            return msgs[-limit:]

    async def clear_messages(self, widget_id: str, thread_id: str) -> None:
        """Clear all messages from a thread.

        Parameters
        ----------
        widget_id : str
            Widget identifier.
        thread_id : str
            Thread identifier.
        """
        async with self._lock:
            widget_threads = self._threads.get(widget_id, {})
            thread = widget_threads.get(thread_id)
            if thread is not None:
                thread.messages = []
                thread.updated_at = time.time()

    async def cleanup_widget(self, widget_id: str) -> None:
        """Remove all chat data for a widget.

        Parameters
        ----------
        widget_id : str
            Widget identifier whose chat state should be discarded.
        """
        async with self._lock:
            self._threads.pop(widget_id, None)


class MemoryChartStore(ChartStore):
    """In-memory chart layout/settings store.

    No persistence across restarts.  Useful for tests and ephemeral
    notebook sessions.
    """

    def __init__(self) -> None:
        self._layouts: dict[str, str] = {}  # layout_id -> json
        self._index: list[dict[str, Any]] = []
        self._template: str | None = None
        self._default_id: str = "factory"
        self._lock = asyncio.Lock()

    async def save_layout(
        self,
        user_id: str,
        layout_id: str,
        name: str,
        data_json: str,
        *,
        summary: str = "",
    ) -> dict[str, Any]:
        """Save or update a chart layout."""
        now = int(time.time() * 1000)
        entry: dict[str, Any] = {
            "id": layout_id,
            "name": name,
            "savedAt": now,
            "summary": summary,
        }
        async with self._lock:
            self._layouts[layout_id] = data_json
            self._index = [e for e in self._index if e.get("id") != layout_id]
            self._index.insert(0, entry)
            self._index = self._index[:200]
        return entry

    async def get_layout(self, user_id: str, layout_id: str) -> str | None:
        """Get layout data by ID."""
        async with self._lock:
            return self._layouts.get(layout_id)

    async def list_layouts(self, user_id: str) -> list[dict[str, Any]]:
        """List all layout index entries."""
        async with self._lock:
            return list(self._index)

    async def delete_layout(self, user_id: str, layout_id: str) -> bool:
        """Delete a layout."""
        async with self._lock:
            if layout_id not in self._layouts:
                return False
            del self._layouts[layout_id]
            self._index = [e for e in self._index if e.get("id") != layout_id]
            return True

    async def rename_layout(self, user_id: str, layout_id: str, new_name: str) -> bool:
        """Rename a layout."""
        async with self._lock:
            for entry in self._index:
                if entry.get("id") == layout_id:
                    entry["name"] = new_name
                    entry["savedAt"] = int(time.time() * 1000)
                    self._index.sort(key=lambda e: e.get("savedAt", 0), reverse=True)
                    return True
            return False

    async def update_layout_meta(
        self,
        user_id: str,
        layout_id: str,
        *,
        name: str = "",
        summary: str = "",
    ) -> bool:
        """Update metadata for an existing layout index entry."""
        async with self._lock:
            for entry in self._index:
                if entry.get("id") == layout_id:
                    if name:
                        entry["name"] = name
                    if summary:
                        entry["summary"] = summary
                    return True
            return False

    async def save_settings_template(self, user_id: str, template_json: str) -> None:
        """Save a custom settings template."""
        async with self._lock:
            self._template = template_json

    async def get_settings_template(self, user_id: str) -> str | None:
        """Get the custom settings template."""
        async with self._lock:
            return self._template

    async def get_settings_default_id(self, user_id: str) -> str:
        """Get which settings template is active."""
        async with self._lock:
            return self._default_id

    async def set_settings_default_id(self, user_id: str, template_id: str) -> None:
        """Set which settings template is active."""
        val = template_id if template_id in ("factory", "custom") else "factory"
        async with self._lock:
            self._default_id = val

    async def clear_settings_template(self, user_id: str) -> None:
        """Remove the custom settings template and reset to factory."""
        async with self._lock:
            self._template = None
            self._default_id = "factory"


# Factory function for creating memory stores
def create_memory_stores() -> tuple[
    MemoryWidgetStore,
    MemoryEventBus,
    MemoryConnectionRouter,
    MemorySessionStore,
]:
    """Create all in-memory state stores.

    Returns
    -------
    tuple
        (widget_store, event_bus, connection_router, session_store)

    Notes
    -----
    Chat storage is created separately because it is not required by every
    runtime path that uses the basic widget state stores.
    """
    return (
        MemoryWidgetStore(),
        MemoryEventBus(),
        MemoryConnectionRouter(),
        MemorySessionStore(),
    )
