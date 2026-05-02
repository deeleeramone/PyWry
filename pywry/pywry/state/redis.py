"""Redis state store implementations.

Production backend for multi-worker deployments with horizontal scaling.
Requires the `redis` package: pip install redis

Features:
- Widget HTML/token storage with TTL
- Cross-worker event bus via Pub/Sub
- Connection routing for WebSocket affinity
- Session management for RBAC
"""

from __future__ import annotations

import contextlib
import json
import time
import uuid

from typing import TYPE_CHECKING, Any, cast

from .base import ChartStore, ChatStore, ConnectionRouter, EventBus, SessionStore, WidgetStore
from .types import ConnectionInfo, EventMessage, UserSession, WidgetData


if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from redis.asyncio import Redis


# Check for redis package
try:
    from redis.asyncio import Redis as RedisClient

    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False
    RedisClient = None  # type: ignore


def _check_redis() -> None:
    """Check if redis package is available."""
    if not HAS_REDIS:
        msg = "Redis backend requires the 'redis' package. Install with: pip install redis"
        raise ImportError(msg)


class RedisWidgetStore(WidgetStore):
    """Redis-backed widget store for horizontal scaling.

    Uses Redis hashes for widget data with automatic TTL expiry.
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        prefix: str = "pywry",
        widget_ttl: int = 86400,  # 24 hours
        pool_size: int = 10,
        *,
        redis_client: Redis | None = None,
    ) -> None:
        """Initialize the Redis widget store.

        Parameters
        ----------
        redis_url : str
            Redis connection URL.
        prefix : str
            Key prefix for all Redis keys.
        widget_ttl : int
            Widget data TTL in seconds.
        pool_size : int
            Connection pool size.
        redis_client : Redis, optional
            Pre-configured Redis client (for testing with fakeredis).
        """
        _check_redis()
        self._redis_url = redis_url
        self._prefix = prefix
        self._widget_ttl = widget_ttl
        self._pool_size = pool_size
        self._client = redis_client

    def _widget_key(self, widget_id: str) -> str:
        """Get Redis key for a widget."""
        return f"{self._prefix}:widget:{widget_id}"

    def _active_set_key(self) -> str:
        """Get Redis key for active widgets set."""
        return f"{self._prefix}:widgets:active"

    async def _redis(self) -> Any:
        """Get a Redis connection.

        Creates a fresh connection each call to avoid event loop binding issues.
        The connection should be closed after use with `await client.aclose()`.
        """
        if self._client is not None:
            return self._client
        return RedisClient.from_url(
            self._redis_url,
            decode_responses=True,
        )

    async def register(
        self,
        widget_id: str,
        html: str,
        token: str | None = None,
        owner_worker_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Register a widget with its HTML content."""
        r = await self._redis()
        key = self._widget_key(widget_id)

        data = {
            "html": html,
            "created_at": str(time.time()),
        }
        if token:
            data["token"] = token
        if owner_worker_id:
            data["owner_worker_id"] = owner_worker_id
        if metadata:
            data["metadata"] = json.dumps(metadata)

        async with r.pipeline() as pipe:
            await pipe.hset(key, mapping=data)
            await pipe.expire(key, self._widget_ttl)
            await pipe.sadd(self._active_set_key(), widget_id)
            await pipe.execute()

    async def get(self, widget_id: str) -> WidgetData | None:
        """Get complete widget data."""
        r = await self._redis()
        data = await r.hgetall(self._widget_key(widget_id))

        if not data:
            return None

        metadata = {}
        if "metadata" in data:
            with contextlib.suppress(json.JSONDecodeError):
                metadata = json.loads(data["metadata"])

        return WidgetData(
            widget_id=widget_id,
            html=data.get("html", ""),
            token=data.get("token"),
            created_at=float(data.get("created_at", 0)),
            owner_worker_id=data.get("owner_worker_id"),
            metadata=metadata,
        )

    async def get_html(self, widget_id: str) -> str | None:
        """Get widget HTML content."""
        r = await self._redis()
        result = await r.hget(self._widget_key(widget_id), "html")
        return cast("str | None", result)

    async def get_token(self, widget_id: str) -> str | None:
        """Get widget authentication token."""
        r = await self._redis()
        result = await r.hget(self._widget_key(widget_id), "token")
        return cast("str | None", result)

    async def exists(self, widget_id: str) -> bool:
        """Check if a widget exists."""
        r = await self._redis()
        result = await r.sismember(self._active_set_key(), widget_id)
        return cast("bool", result)

    async def delete(self, widget_id: str) -> bool:
        """Delete a widget."""
        r = await self._redis()
        async with r.pipeline() as pipe:
            await pipe.delete(self._widget_key(widget_id))
            await pipe.srem(self._active_set_key(), widget_id)
            results = await pipe.execute()
        return cast("bool", results[0] > 0)

    async def list_active(self) -> list[str]:
        """List all active widget IDs."""
        r = await self._redis()
        members = await r.smembers(self._active_set_key())
        return list(members)

    async def update_html(self, widget_id: str, html: str) -> bool:
        """Update widget HTML content."""
        r = await self._redis()
        key = self._widget_key(widget_id)
        if not await r.exists(key):
            return False
        await r.hset(key, "html", html)
        await r.expire(key, self._widget_ttl)  # Refresh TTL
        return True

    async def update_token(self, widget_id: str, token: str) -> bool:
        """Update widget authentication token."""
        r = await self._redis()
        key = self._widget_key(widget_id)
        if not await r.exists(key):
            return False
        await r.hset(key, "token", token)
        await r.expire(key, self._widget_ttl)  # Refresh TTL
        return True

    async def count(self) -> int:
        """Get the number of active widgets."""
        r = await self._redis()
        result = await r.scard(self._active_set_key())
        return cast("int", result)

    async def close(self) -> None:
        """Close any resources (no-op for connection-per-call pattern)."""


class RedisEventBus(EventBus):
    """Redis Pub/Sub for cross-worker event delivery.

    Uses Redis Pub/Sub for real-time event distribution.
    Events are fire-and-forget (no persistence).
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        prefix: str = "pywry",
        pool_size: int = 10,
        *,
        redis_client: Redis | None = None,
    ) -> None:
        """Initialize the Redis event bus.

        Parameters
        ----------
        redis_url : str
            Redis connection URL.
        prefix : str
            Key prefix for channel names.
        pool_size : int
            Connection pool size.
        redis_client : Redis, optional
            Pre-configured Redis client (for testing with fakeredis).
        """
        _check_redis()
        self._redis_url = redis_url
        self._prefix = prefix
        self._pool_size = pool_size
        self._client = redis_client
        self._pubsub_connections: dict[str, Any] = {}

    def _channel_name(self, channel: str) -> str:
        """Get full Redis channel name."""
        return f"{self._prefix}:channel:{channel}"

    async def _redis(self) -> Any:
        """Get a Redis connection."""
        if self._client is not None:
            return self._client
        return RedisClient.from_url(
            self._redis_url,
            decode_responses=True,
        )

    async def publish(self, channel: str, event: EventMessage) -> None:
        """Publish an event to a channel."""
        r = await self._redis()
        event_data = {
            "event_type": event.event_type,
            "widget_id": event.widget_id,
            "data": event.data,
            "source_worker_id": event.source_worker_id,
            "target_worker_id": event.target_worker_id,
            "timestamp": event.timestamp or time.time(),
            "message_id": event.message_id or str(uuid.uuid4()),
        }
        await r.publish(self._channel_name(channel), json.dumps(event_data))

    async def subscribe(self, channel: str) -> AsyncIterator[EventMessage]:
        """Subscribe to events on a channel."""
        r = await self._redis()
        pubsub = r.pubsub()
        await pubsub.subscribe(self._channel_name(channel))

        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        yield EventMessage(
                            event_type=data.get("event_type", ""),
                            widget_id=data.get("widget_id", ""),
                            data=data.get("data", {}),
                            source_worker_id=data.get("source_worker_id", ""),
                            target_worker_id=data.get("target_worker_id"),
                            timestamp=data.get("timestamp", 0),
                            message_id=data.get("message_id", ""),
                        )
                    except json.JSONDecodeError:
                        continue
        finally:
            await pubsub.unsubscribe(self._channel_name(channel))
            await pubsub.close()

    async def unsubscribe(self, channel: str) -> None:
        """Unsubscribe from a channel.

        Note: Subscriptions are managed by the subscribe generator.
        This is a no-op for cleanup.
        """

    async def close(self) -> None:
        """Close any resources (no-op for connection-per-call pattern)."""


class RedisConnectionRouter(ConnectionRouter):
    """Track which worker owns which WebSocket connection.

    Uses Redis hashes with TTL for connection tracking.
    Heartbeat refresh extends the TTL.
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        prefix: str = "pywry",
        connection_ttl: int = 300,  # 5 minutes
        pool_size: int = 10,
        *,
        redis_client: Redis | None = None,
    ) -> None:
        """Initialize the Redis connection router.

        Parameters
        ----------
        redis_url : str
            Redis connection URL.
        prefix : str
            Key prefix for Redis keys.
        connection_ttl : int
            Connection TTL in seconds (refresh via heartbeat).
        pool_size : int
            Connection pool size.
        redis_client : Redis, optional
            Pre-configured Redis client (for testing with fakeredis).
        """
        _check_redis()
        self._redis_url = redis_url
        self._prefix = prefix
        self._connection_ttl = connection_ttl
        self._pool_size = pool_size
        self._client = redis_client

    def _conn_key(self, widget_id: str) -> str:
        """Get Redis key for a connection."""
        return f"{self._prefix}:conn:{widget_id}"

    def _worker_set_key(self, worker_id: str) -> str:
        """Get Redis key for worker's connections set."""
        return f"{self._prefix}:worker:{worker_id}:connections"

    async def _redis(self) -> Any:
        """Get a Redis connection."""
        if self._client is not None:
            return self._client
        return RedisClient.from_url(
            self._redis_url,
            decode_responses=True,
        )

    async def register_connection(
        self,
        widget_id: str,
        worker_id: str,
        user_id: str | None = None,
        session_id: str | None = None,
    ) -> None:
        """Register that a widget is connected to a specific worker."""
        r = await self._redis()
        now = time.time()

        data = {
            "worker_id": worker_id,
            "connected_at": str(now),
            "last_heartbeat": str(now),
        }
        if user_id:
            data["user_id"] = user_id
        if session_id:
            data["session_id"] = session_id

        key = self._conn_key(widget_id)
        async with r.pipeline() as pipe:
            await pipe.hset(key, mapping=data)
            await pipe.expire(key, self._connection_ttl)
            await pipe.sadd(self._worker_set_key(worker_id), widget_id)
            await pipe.execute()

    async def get_connection_info(self, widget_id: str) -> ConnectionInfo | None:
        """Get connection information for a widget."""
        r = await self._redis()
        data = await r.hgetall(self._conn_key(widget_id))

        if not data:
            return None

        return ConnectionInfo(
            widget_id=widget_id,
            worker_id=data.get("worker_id", ""),
            connected_at=float(data.get("connected_at", 0)),
            last_heartbeat=float(data.get("last_heartbeat", 0)),
            user_id=data.get("user_id"),
            session_id=data.get("session_id"),
        )

    async def get_owner(self, widget_id: str) -> str | None:
        """Get the worker ID that owns this widget's connection."""
        r = await self._redis()
        result = await r.hget(self._conn_key(widget_id), "worker_id")
        return cast("str | None", result)

    async def refresh_heartbeat(self, widget_id: str) -> bool:
        """Refresh the heartbeat timestamp for a connection."""
        r = await self._redis()
        key = self._conn_key(widget_id)
        if not await r.exists(key):
            return False
        await r.hset(key, "last_heartbeat", str(time.time()))
        await r.expire(key, self._connection_ttl)
        return True

    async def unregister_connection(self, widget_id: str) -> bool:
        """Unregister a connection."""
        r = await self._redis()
        key = self._conn_key(widget_id)

        # Get worker_id first for cleanup
        worker_id = await r.hget(key, "worker_id")
        if not worker_id:
            return False

        async with r.pipeline() as pipe:
            await pipe.delete(key)
            await pipe.srem(self._worker_set_key(worker_id), widget_id)
            await pipe.execute()
        return True

    async def list_worker_connections(self, worker_id: str) -> list[str]:
        """List all widget IDs connected to a specific worker."""
        r = await self._redis()
        members = await r.smembers(self._worker_set_key(worker_id))
        return list(members)

    async def close(self) -> None:
        """Close any resources (no-op for connection-per-call pattern)."""


class RedisSessionStore(SessionStore):
    """Redis-backed session store for RBAC support.

    Uses Redis hashes for session data with automatic TTL expiry.
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        prefix: str = "pywry",
        default_ttl: int = 86400,  # 24 hours
        pool_size: int = 10,
        *,
        redis_client: Redis | None = None,
    ) -> None:
        """Initialize the Redis session store.

        Parameters
        ----------
        redis_url : str
            Redis connection URL.
        prefix : str
            Key prefix for Redis keys.
        default_ttl : int
            Default session TTL in seconds.
        pool_size : int
            Connection pool size.
        redis_client : Redis, optional
            Pre-configured Redis client (for testing with fakeredis).
        """
        _check_redis()
        self._redis_url = redis_url
        self._prefix = prefix
        self._default_ttl = default_ttl
        self._pool_size = pool_size
        self._client = redis_client
        # Role permissions stored in Redis hash
        self._role_perms_key = f"{self._prefix}:role_permissions"

    def _session_key(self, session_id: str) -> str:
        """Get Redis key for a session."""
        return f"{self._prefix}:session:{session_id}"

    def _user_sessions_key(self, user_id: str) -> str:
        """Get Redis key for user's sessions set."""
        return f"{self._prefix}:user:{user_id}:sessions"

    async def _redis(self) -> Any:
        """Get a Redis connection."""
        if self._client is not None:
            return self._client
        return RedisClient.from_url(
            self._redis_url,
            decode_responses=True,
        )

    async def create_session(
        self,
        session_id: str,
        user_id: str,
        roles: list[str] | None = None,
        ttl: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> UserSession:
        """Create a new user session."""
        r = await self._redis()
        now = time.time()
        actual_ttl = ttl if ttl is not None else self._default_ttl
        expires_at = now + actual_ttl

        session = UserSession(
            session_id=session_id,
            user_id=user_id,
            roles=roles or [],
            created_at=now,
            expires_at=expires_at,
            metadata=metadata or {},
        )

        key = self._session_key(session_id)
        data = {
            "user_id": user_id,
            "roles": json.dumps(roles or []),
            "created_at": str(now),
            "expires_at": str(expires_at),
            "ttl": str(actual_ttl),
            "metadata": json.dumps(metadata or {}),
        }

        async with r.pipeline() as pipe:
            await pipe.hset(key, mapping=data)
            await pipe.expire(key, actual_ttl)
            await pipe.sadd(self._user_sessions_key(user_id), session_id)
            await pipe.execute()

        return session

    async def get_session(self, session_id: str) -> UserSession | None:
        """Get a session by ID."""
        r = await self._redis()
        data = await r.hgetall(self._session_key(session_id))

        if not data:
            return None

        roles: list[str] = []
        if "roles" in data:
            with contextlib.suppress(json.JSONDecodeError):
                roles = json.loads(data["roles"])

        metadata: dict[str, Any] = {}
        if "metadata" in data:
            with contextlib.suppress(json.JSONDecodeError):
                metadata = json.loads(data["metadata"])

        expires_at = float(data.get("expires_at", 0))

        # Check Python-side expiry as belt-and-suspenders alongside Redis TTL.
        # Redis expires keys lazily, so under load a key may briefly outlive
        # its TTL.  Checking the stored timestamp catches that case.
        if expires_at and expires_at < time.time():
            return None

        return UserSession(
            session_id=session_id,
            user_id=data.get("user_id", ""),
            roles=roles,
            created_at=float(data.get("created_at", 0)),
            expires_at=expires_at,
            metadata=metadata,
        )

    async def validate_session(self, session_id: str) -> bool:
        """Validate a session is active and not expired."""
        session = await self.get_session(session_id)
        return session is not None

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        r = await self._redis()
        key = self._session_key(session_id)

        # Get user_id for cleanup
        user_id = await r.hget(key, "user_id")
        if not user_id:
            return False

        async with r.pipeline() as pipe:
            await pipe.delete(key)
            await pipe.srem(self._user_sessions_key(user_id), session_id)
            await pipe.execute()
        return True

    async def refresh_session(self, session_id: str, extend_ttl: int | None = None) -> bool:
        """Refresh a session's expiry time."""
        r = await self._redis()
        key = self._session_key(session_id)

        data = await r.hgetall(key)
        if not data:
            return False

        # Calculate new TTL
        if extend_ttl is not None:
            new_ttl = extend_ttl
        else:
            # Use original TTL
            new_ttl = int(float(data.get("ttl", self._default_ttl)))

        new_expires = time.time() + new_ttl

        async with r.pipeline() as pipe:
            await pipe.hset(key, "expires_at", str(new_expires))
            await pipe.expire(key, new_ttl)
            await pipe.execute()
        return True

    async def list_user_sessions(self, user_id: str) -> list[UserSession]:
        """List all sessions for a user."""
        r = await self._redis()
        session_ids = await r.smembers(self._user_sessions_key(user_id))

        sessions = []
        for sid in session_ids:
            session = await self.get_session(sid)
            if session:
                sessions.append(session)
            else:
                # Clean up stale reference
                await r.srem(self._user_sessions_key(user_id), sid)

        return sessions

    async def check_permission(
        self,
        session_id: str,
        resource_type: str,
        resource_id: str,
        permission: str,
    ) -> bool:
        """Check if a session has permission to access a resource."""
        session = await self.get_session(session_id)
        if session is None:
            return False

        r = await self._redis()

        # Check role-based permissions
        for role in session.roles:
            role_perms = await r.hget(self._role_perms_key, role)
            if role_perms:
                try:
                    perms = json.loads(role_perms)
                    if permission in perms:
                        return True
                except json.JSONDecodeError:
                    pass

        # Check resource-specific permissions in session metadata
        resource_perms = session.metadata.get("permissions", {})
        resource_key = f"{resource_type}:{resource_id}"
        if resource_key in resource_perms:
            return permission in resource_perms[resource_key]

        return False

    async def set_role_permissions(self, role: str, permissions: list[str] | set[str]) -> None:
        """Configure permissions for a role."""
        r = await self._redis()
        # Convert set to list for JSON serialization
        perms_list = list(permissions) if isinstance(permissions, set) else permissions
        await r.hset(self._role_perms_key, role, json.dumps(perms_list))

    async def close(self) -> None:
        """Close any resources (no-op for connection-per-call pattern)."""


class RedisChatStore(ChatStore):
    """Redis-backed chat store for multi-worker deployments.

    Uses Redis hashes for thread metadata and lists for message storage.
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        prefix: str = "pywry",
        chat_ttl: int = 86400,  # 24 hours
        pool_size: int = 10,
        *,
        redis_client: Redis | None = None,
    ) -> None:
        """Initialize the Redis chat store.

        Parameters
        ----------
        redis_url : str
            Redis connection URL.
        prefix : str
            Key prefix for all Redis keys.
        chat_ttl : int
            Chat data TTL in seconds.
        pool_size : int
            Connection pool size.
        redis_client : Redis, optional
            Pre-configured Redis client (for testing with fakeredis).
        """
        _check_redis()
        self._redis_url = redis_url
        self._prefix = prefix
        self._chat_ttl = chat_ttl
        self._pool_size = pool_size
        self._client = redis_client

    def _thread_key(self, widget_id: str, thread_id: str) -> str:
        """Redis key for a thread's metadata hash."""
        return f"{self._prefix}:chat:{widget_id}:thread:{thread_id}"

    def _threads_set_key(self, widget_id: str) -> str:
        """Redis key for set of thread IDs per widget."""
        return f"{self._prefix}:chat:{widget_id}:threads"

    def _messages_key(self, widget_id: str, thread_id: str) -> str:
        """Redis key for a thread's message list."""
        return f"{self._prefix}:chat:{widget_id}:{thread_id}:messages"

    async def _redis(self) -> Any:
        """Get a Redis connection."""
        if self._client is not None:
            return self._client
        return RedisClient.from_url(
            self._redis_url,
            decode_responses=True,
        )

    async def save_thread(self, widget_id: str, thread: Any) -> None:
        """Save or update a chat thread."""
        r = await self._redis()
        key = self._thread_key(widget_id, thread.thread_id)

        data = {
            "thread_id": thread.thread_id,
            "title": thread.title,
            "created_at": str(thread.created_at),
            "updated_at": str(thread.updated_at),
            "status": thread.status,
            "metadata": json.dumps(thread.metadata),
        }

        async with r.pipeline() as pipe:
            await pipe.hset(key, mapping=data)
            await pipe.expire(key, self._chat_ttl)
            await pipe.sadd(self._threads_set_key(widget_id), thread.thread_id)
            await pipe.execute()

    async def get_thread(self, widget_id: str, thread_id: str) -> Any:
        """Get a thread by ID."""
        from pywry.chat import ChatThread

        r = await self._redis()
        data = await r.hgetall(self._thread_key(widget_id, thread_id))
        if not data:
            return None

        metadata: dict[str, Any] = {}
        if "metadata" in data:
            with contextlib.suppress(json.JSONDecodeError):
                metadata = json.loads(data["metadata"])

        return ChatThread(
            thread_id=data.get("thread_id", thread_id),
            title=data.get("title", "New Chat"),
            created_at=float(data.get("created_at", 0)),
            updated_at=float(data.get("updated_at", 0)),
            status=data.get("status", "active"),
            metadata=metadata,
            # Messages are stored separately in a list, not loaded here
            messages=[],
        )

    async def list_threads(self, widget_id: str) -> list[Any]:
        """List all threads for a widget."""
        r = await self._redis()
        thread_ids = await r.smembers(self._threads_set_key(widget_id))
        threads = []
        for tid in thread_ids:
            thread = await self.get_thread(widget_id, tid)
            if thread is not None:
                threads.append(thread)
        return threads

    async def delete_thread(self, widget_id: str, thread_id: str) -> bool:
        """Delete a thread and its messages."""
        r = await self._redis()
        key = self._thread_key(widget_id, thread_id)
        msgs_key = self._messages_key(widget_id, thread_id)

        existed = await r.exists(key)
        async with r.pipeline() as pipe:
            await pipe.delete(key)
            await pipe.delete(msgs_key)
            await pipe.srem(self._threads_set_key(widget_id), thread_id)
            await pipe.execute()
        return bool(existed)

    async def append_message(self, widget_id: str, thread_id: str, message: Any) -> None:
        """Append a message to a thread."""
        from pywry.chat import MAX_MESSAGES_PER_THREAD

        r = await self._redis()
        msgs_key = self._messages_key(widget_id, thread_id)

        msg_json = message.model_dump_json()
        async with r.pipeline() as pipe:
            await pipe.rpush(msgs_key, msg_json)
            # Trim to keep only the latest MAX_MESSAGES_PER_THREAD
            await pipe.ltrim(msgs_key, -MAX_MESSAGES_PER_THREAD, -1)
            await pipe.expire(msgs_key, self._chat_ttl)
            await pipe.execute()

        # Update thread's updated_at
        thread_key = self._thread_key(widget_id, thread_id)
        await r.hset(thread_key, "updated_at", str(time.time()))
        await r.expire(thread_key, self._chat_ttl)

    async def get_messages(
        self,
        widget_id: str,
        thread_id: str,
        limit: int = 50,
        before_id: str | None = None,
    ) -> list[Any]:
        """Get messages with cursor-based pagination."""
        from pywry.chat import ChatMessage

        r = await self._redis()
        msgs_key = self._messages_key(widget_id, thread_id)

        # Get all raw messages
        raw_msgs = await r.lrange(msgs_key, 0, -1)
        messages: list[ChatMessage] = []
        for raw in raw_msgs:
            with contextlib.suppress(Exception):
                messages.append(ChatMessage.model_validate_json(raw))

        if before_id is not None:
            idx = next(
                (i for i, m in enumerate(messages) if m.message_id == before_id),
                None,
            )
            if idx is not None:
                messages = messages[:idx]

        return messages[-limit:]

    async def clear_messages(self, widget_id: str, thread_id: str) -> None:
        """Clear all messages from a thread."""
        r = await self._redis()
        await r.delete(self._messages_key(widget_id, thread_id))

        thread_key = self._thread_key(widget_id, thread_id)
        await r.hset(thread_key, "updated_at", str(time.time()))

    async def close(self) -> None:
        """Close any resources."""


class RedisChartStore(ChartStore):
    """Redis-backed chart layout/settings store for multi-worker deployments.

    Uses Redis hashes for layout metadata, strings for layout data, and
    sorted sets for the layout index.
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        prefix: str = "pywry",
        chart_ttl: int = 2_592_000,  # 30 days
        pool_size: int = 10,
        *,
        redis_client: Redis | None = None,
    ) -> None:
        _check_redis()
        self._redis_url = redis_url
        self._prefix = prefix
        self._chart_ttl = chart_ttl
        self._pool_size = pool_size
        self._client = redis_client

    # -- Key helpers -------------------------------------------------------

    def _layout_key(self, user_id: str, layout_id: str) -> str:
        return f"{self._prefix}:chart:{user_id}:layout:{layout_id}"

    def _meta_key(self, user_id: str, layout_id: str) -> str:
        return f"{self._prefix}:chart:{user_id}:layout_meta:{layout_id}"

    def _index_key(self, user_id: str) -> str:
        return f"{self._prefix}:chart:{user_id}:layouts"

    def _template_key(self, user_id: str) -> str:
        return f"{self._prefix}:chart:{user_id}:settings_template"

    def _default_id_key(self, user_id: str) -> str:
        return f"{self._prefix}:chart:{user_id}:settings_default_id"

    async def _redis(self) -> Any:
        if self._client is not None:
            return self._client
        return RedisClient.from_url(self._redis_url, decode_responses=True)

    # -- Layout operations -------------------------------------------------

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
            "savedAt": str(now),
            "summary": summary,
        }
        r = await self._redis()
        async with r.pipeline() as pipe:
            await pipe.set(self._layout_key(user_id, layout_id), data_json)
            await pipe.expire(self._layout_key(user_id, layout_id), self._chart_ttl)
            await pipe.hset(self._meta_key(user_id, layout_id), mapping=entry)
            await pipe.expire(self._meta_key(user_id, layout_id), self._chart_ttl)
            await pipe.zadd(self._index_key(user_id), {layout_id: now})
            await pipe.expire(self._index_key(user_id), self._chart_ttl)
            await pipe.execute()
        entry["savedAt"] = now
        return entry

    async def get_layout(self, user_id: str, layout_id: str) -> str | None:
        """Get layout data by ID."""
        r = await self._redis()
        val: str | None = await r.get(self._layout_key(user_id, layout_id))
        return val

    async def list_layouts(self, user_id: str) -> list[dict[str, Any]]:
        """List all layout index entries."""
        r = await self._redis()
        # Sorted set stores layout_id → score (savedAt), newest first
        ids_with_scores = await r.zrevrangebyscore(
            self._index_key(user_id), "+inf", "-inf", withscores=True, start=0, num=200
        )
        results: list[dict[str, Any]] = []
        for lid, score in ids_with_scores:
            meta = await r.hgetall(self._meta_key(user_id, lid))
            if meta:
                meta["savedAt"] = int(float(meta.get("savedAt", score)))
                results.append(meta)
            else:
                results.append({"id": lid, "name": lid, "savedAt": int(score), "summary": ""})
        return results

    async def delete_layout(self, user_id: str, layout_id: str) -> bool:
        """Delete a layout."""
        r = await self._redis()
        existed = await r.exists(self._layout_key(user_id, layout_id))
        async with r.pipeline() as pipe:
            await pipe.delete(self._layout_key(user_id, layout_id))
            await pipe.delete(self._meta_key(user_id, layout_id))
            await pipe.zrem(self._index_key(user_id), layout_id)
            await pipe.execute()
        return bool(existed)

    async def rename_layout(self, user_id: str, layout_id: str, new_name: str) -> bool:
        """Rename a layout."""
        r = await self._redis()
        key = self._meta_key(user_id, layout_id)
        if not await r.exists(key):
            return False
        now = int(time.time() * 1000)
        async with r.pipeline() as pipe:
            await pipe.hset(key, "name", new_name)
            await pipe.hset(key, "savedAt", str(now))
            await pipe.expire(key, self._chart_ttl)
            await pipe.zadd(self._index_key(user_id), {layout_id: now})
            await pipe.execute()
        return True

    async def update_layout_meta(
        self,
        user_id: str,
        layout_id: str,
        *,
        name: str = "",
        summary: str = "",
    ) -> bool:
        """Update metadata for an existing layout index entry."""
        r = await self._redis()
        key = self._meta_key(user_id, layout_id)
        if not await r.exists(key):
            return False
        mapping: dict[str, str] = {}
        if name:
            mapping["name"] = name
        if summary:
            mapping["summary"] = summary
        if mapping:
            await r.hset(key, mapping=mapping)
            await r.expire(key, self._chart_ttl)
        return True

    # -- Settings template operations --------------------------------------

    async def save_settings_template(self, user_id: str, template_json: str) -> None:
        """Save a custom settings template."""
        r = await self._redis()
        await r.set(self._template_key(user_id), template_json, ex=self._chart_ttl)

    async def get_settings_template(self, user_id: str) -> str | None:
        """Get the custom settings template."""
        r = await self._redis()
        val: str | None = await r.get(self._template_key(user_id))
        return val

    async def get_settings_default_id(self, user_id: str) -> str:
        """Get which settings template is active."""
        r = await self._redis()
        val = await r.get(self._default_id_key(user_id))
        return val if val in ("factory", "custom") else "factory"

    async def set_settings_default_id(self, user_id: str, template_id: str) -> None:
        """Set which settings template is active."""
        val = template_id if template_id in ("factory", "custom") else "factory"
        r = await self._redis()
        await r.set(self._default_id_key(user_id), val, ex=self._chart_ttl)

    async def clear_settings_template(self, user_id: str) -> None:
        """Remove the custom settings template and reset to factory."""
        r = await self._redis()
        async with r.pipeline() as pipe:
            await pipe.delete(self._template_key(user_id))
            await pipe.set(self._default_id_key(user_id), "factory", ex=self._chart_ttl)
            await pipe.execute()

    async def close(self) -> None:
        """Close any resources."""


# Factory function for creating Redis stores
def create_redis_stores(
    redis_url: str = "redis://localhost:6379/0",
    prefix: str = "pywry",
    widget_ttl: int = 86400,
    connection_ttl: int = 300,
    session_ttl: int = 86400,
    pool_size: int = 10,
) -> tuple[
    RedisWidgetStore,
    RedisEventBus,
    RedisConnectionRouter,
    RedisSessionStore,
]:
    """Create all Redis state stores with shared configuration.

    Parameters
    ----------
    redis_url : str
        Redis connection URL.
    prefix : str
        Key prefix for all Redis keys.
    widget_ttl : int
        Widget data TTL in seconds.
    connection_ttl : int
        Connection routing TTL in seconds.
    session_ttl : int
        Session TTL in seconds.
    pool_size : int
        Connection pool size per store.

    Returns
    -------
    tuple
        (widget_store, event_bus, connection_router, session_store)
    """
    _check_redis()
    return (
        RedisWidgetStore(
            redis_url=redis_url,
            prefix=prefix,
            widget_ttl=widget_ttl,
            pool_size=pool_size,
        ),
        RedisEventBus(
            redis_url=redis_url,
            prefix=prefix,
            pool_size=pool_size,
        ),
        RedisConnectionRouter(
            redis_url=redis_url,
            prefix=prefix,
            connection_ttl=connection_ttl,
            pool_size=pool_size,
        ),
        RedisSessionStore(
            redis_url=redis_url,
            prefix=prefix,
            default_ttl=session_ttl,
            pool_size=pool_size,
        ),
    )
