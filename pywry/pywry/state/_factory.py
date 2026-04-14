"""Internal factory functions for state stores.

This module contains the factory functions to avoid circular imports
between __init__.py and server.py.
"""

from __future__ import annotations

import os
import uuid

from functools import lru_cache
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from .base import (
        ChartStore,
        ChatStore,
        ConnectionRouter,
        EventBus,
        SessionStore,
        WidgetStore,
    )

# pylint: disable=wrong-import-position
from .memory import (
    MemoryChartStore,
    MemoryChatStore,
    MemoryConnectionRouter,
    MemoryEventBus,
    MemorySessionStore,
    MemoryWidgetStore,
)
from .types import StateBackend


# pylint: enable=wrong-import-position


class _WorkerIdHolder:
    """Holder for worker ID to avoid global statement."""

    value: str | None = None


_worker_id_holder = _WorkerIdHolder()


def get_worker_id() -> str:
    """Get the unique worker ID for this process.

    The worker ID is used for connection routing and callback dispatch
    in multi-worker deployments.

    Returns
    -------
    str
        Unique worker identifier.
    """
    if _worker_id_holder.value is None:
        # Check environment variable first
        _worker_id_holder.value = os.environ.get("PYWRY_DEPLOY__WORKER_ID")
        if not _worker_id_holder.value:
            # Generate a unique ID for this worker
            _worker_id_holder.value = f"worker-{uuid.uuid4().hex[:8]}"
    return _worker_id_holder.value


def get_state_backend() -> StateBackend:
    """Get the configured state backend.

    Returns
    -------
    StateBackend
        The configured backend (MEMORY, REDIS, or SQLITE).

    Notes
    -----
    The backend is selected from the ``PYWRY_DEPLOY__STATE_BACKEND`` environment
    variable and defaults to in-memory storage.
    """
    backend = os.environ.get("PYWRY_DEPLOY__STATE_BACKEND", "memory").lower()
    if backend == "redis":
        return StateBackend.REDIS
    if backend == "sqlite":
        return StateBackend.SQLITE
    return StateBackend.MEMORY


def is_deploy_mode() -> bool:
    """Check if running in deploy mode.

    Deploy mode enables:
    - Redis state backend (if configured)
    - Multi-worker support
    - External state storage
    - Session/RBAC support

    Returns
    -------
    bool
        True if running in deploy mode.

    Notes
    -----
    Deploy mode may be enabled explicitly or inferred from a Redis-backed state
    configuration.
    """
    # Check for explicit deploy mode flag
    deploy_mode = os.environ.get("PYWRY_DEPLOY_MODE", "").lower()
    if deploy_mode in ("1", "true", "yes", "on"):
        return True

    # If Redis backend is configured, that implies deploy mode
    backend = os.environ.get("PYWRY_DEPLOY__STATE_BACKEND", "").lower()
    if backend == "redis":
        return True

    # Check for PYWRY_HEADLESS with state backend
    headless = os.environ.get("PYWRY_HEADLESS", "").lower()
    return headless in ("1", "true", "yes", "on") and bool(backend)


def _get_deploy_settings() -> DeploySettings:
    """Get deploy settings from configuration.

    Imports lazily to avoid circular imports.

    Returns
    -------
    DeploySettings
        Resolved deploy settings instance.
    """
    from pywry.config import DeploySettings

    return DeploySettings()


if TYPE_CHECKING:
    from pywry.config import DeploySettings


@lru_cache(maxsize=1)
def get_widget_store() -> WidgetStore:
    """Get the configured widget store instance.

    Uses Redis backend in deploy mode if configured, otherwise memory.

    Returns
    -------
    WidgetStore
        The widget store instance.

    Notes
    -----
    The returned store is cached per process and re-created only after calling
    ``clear_state_caches()``.
    """
    backend = get_state_backend()

    if backend == StateBackend.REDIS:
        from .redis import RedisWidgetStore

        settings = _get_deploy_settings()
        return RedisWidgetStore(
            redis_url=settings.redis_url,
            prefix=settings.redis_prefix,
            widget_ttl=settings.widget_ttl,
            pool_size=settings.redis_pool_size,
        )

    if backend == StateBackend.SQLITE:
        from .sqlite import SqliteWidgetStore

        settings = _get_deploy_settings()
        return SqliteWidgetStore(db_path=getattr(settings, "sqlite_path", "~/.config/pywry/pywry.db"))

    return MemoryWidgetStore()


@lru_cache(maxsize=1)
def get_event_bus() -> EventBus:
    """Get the configured event bus instance.

    Uses Redis Pub/Sub in deploy mode if configured, otherwise memory.

    Returns
    -------
    EventBus
        The event bus instance.

    Notes
    -----
    The returned bus is cached per process and may be backed by Redis Pub/Sub in
    deploy mode.
    """
    backend = get_state_backend()

    if backend == StateBackend.REDIS:
        from .redis import RedisEventBus

        settings = _get_deploy_settings()
        return RedisEventBus(
            redis_url=settings.redis_url,
            prefix=settings.redis_prefix,
            pool_size=settings.redis_pool_size,
        )

    if backend == StateBackend.SQLITE:
        from .sqlite import SqliteEventBus

        settings = _get_deploy_settings()
        return SqliteEventBus(db_path=getattr(settings, "sqlite_path", "~/.config/pywry/pywry.db"))

    return MemoryEventBus()


@lru_cache(maxsize=1)
def get_connection_router() -> ConnectionRouter:
    """Get the configured connection router instance.

    Uses Redis in deploy mode if configured, otherwise memory.

    Returns
    -------
    ConnectionRouter
        The connection router instance.

    Notes
    -----
    The returned router is cached per process and uses the configured backend.
    """
    backend = get_state_backend()

    if backend == StateBackend.REDIS:
        from .redis import RedisConnectionRouter

        settings = _get_deploy_settings()
        return RedisConnectionRouter(
            redis_url=settings.redis_url,
            prefix=settings.redis_prefix,
            connection_ttl=settings.connection_ttl,
            pool_size=settings.redis_pool_size,
        )

    if backend == StateBackend.SQLITE:
        from .sqlite import SqliteConnectionRouter

        settings = _get_deploy_settings()
        return SqliteConnectionRouter(db_path=getattr(settings, "sqlite_path", "~/.config/pywry/pywry.db"))

    return MemoryConnectionRouter()


@lru_cache(maxsize=1)
def get_session_store() -> SessionStore:
    """Get the configured session store instance.

    Uses Redis in deploy mode if configured, otherwise memory.

    Returns
    -------
    SessionStore
        The session store instance.

    Notes
    -----
    Session storage is primarily relevant in deploy-mode RBAC and multi-tenant
    scenarios, but a memory implementation is always available.
    """
    backend = get_state_backend()

    if backend == StateBackend.REDIS:
        from .redis import RedisSessionStore

        settings = _get_deploy_settings()
        return RedisSessionStore(
            redis_url=settings.redis_url,
            prefix=settings.redis_prefix,
            default_ttl=settings.session_ttl,
            pool_size=settings.redis_pool_size,
        )

    if backend == StateBackend.SQLITE:
        from .sqlite import SqliteSessionStore

        settings = _get_deploy_settings()
        return SqliteSessionStore(db_path=getattr(settings, "sqlite_path", "~/.config/pywry/pywry.db"))

    return MemorySessionStore()


@lru_cache(maxsize=1)
def get_chat_store() -> ChatStore:
    """Get the configured chat store instance.

    Uses Redis in deploy mode if configured, otherwise memory.

    Returns
    -------
    ChatStore
        The chat store instance.

    Notes
    -----
    Chat storage is cached per process and uses the same backend selection logic
    as the rest of the state subsystem.
    """
    backend = get_state_backend()

    if backend == StateBackend.REDIS:
        from .redis import RedisChatStore

        settings = _get_deploy_settings()
        return RedisChatStore(
            redis_url=settings.redis_url,
            prefix=settings.redis_prefix,
            chat_ttl=settings.widget_ttl,
            pool_size=settings.redis_pool_size,
        )

    if backend == StateBackend.SQLITE:
        from .sqlite import SqliteChatStore

        settings = _get_deploy_settings()
        return SqliteChatStore(db_path=getattr(settings, "sqlite_path", "~/.config/pywry/pywry.db"))

    return MemoryChatStore()


@lru_cache(maxsize=1)
def get_chart_store() -> ChartStore:
    """Get the configured chart store instance.

    Uses Redis in deploy mode, filesystem by default.

    Returns
    -------
    ChartStore
        The chart store instance.
    """
    backend = get_state_backend()

    if backend == StateBackend.REDIS:
        from .redis import RedisChartStore

        settings = _get_deploy_settings()
        return RedisChartStore(
            redis_url=settings.redis_url,
            prefix=settings.redis_prefix,
            pool_size=settings.redis_pool_size,
        )

    # Non-deploy: choose between file and memory based on TVChart config
    from pywry.config import get_settings

    tvchart = get_settings().tvchart
    if tvchart.storage_backend == "memory":
        return MemoryChartStore()

    from .file import FileChartStore

    return FileChartStore(base_path=tvchart.storage_path)


def clear_state_caches() -> None:
    """Clear all cached state store instances.

    Call this to force re-creation of stores (e.g., after config change).

    Notes
    -----
    This does not delete persisted backend data; it only clears in-process factory
    caches so subsequent accessor calls build fresh instances.
    """
    get_widget_store.cache_clear()
    get_event_bus.cache_clear()
    get_connection_router.cache_clear()
    get_session_store.cache_clear()
    get_chat_store.cache_clear()
    get_chart_store.cache_clear()
