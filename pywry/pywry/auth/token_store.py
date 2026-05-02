"""Pluggable token storage backends.

Provides TokenStore ABC and concrete implementations for
in-memory, OS keyring, and Redis-backed token persistence.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import threading
import time

from abc import ABC, abstractmethod
from typing import Any

from ..state.types import OAuthTokenSet


logger = logging.getLogger("pywry.auth")


class TokenStore(ABC):
    """Abstract base class for OAuth2 token storage.

    All methods are async to support both local and network-backed stores.
    """

    @abstractmethod
    async def save(self, key: str, tokens: OAuthTokenSet) -> None:
        """Save tokens under the given key.

        Parameters
        ----------
        key : str
            Unique identifier (e.g., user ID or session key).
        tokens : OAuthTokenSet
            The token set to persist.
        """

    @abstractmethod
    async def load(self, key: str) -> OAuthTokenSet | None:
        """Load tokens for the given key.

        Parameters
        ----------
        key : str
            Unique identifier.

        Returns
        -------
        OAuthTokenSet or None
            The stored token set, or None if not found.
        """

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete tokens for the given key.

        Parameters
        ----------
        key : str
            Unique identifier.
        """

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if tokens exist for the given key.

        Parameters
        ----------
        key : str
            Unique identifier.

        Returns
        -------
        bool
            True if tokens are stored for this key.
        """

    @abstractmethod
    async def list_keys(self) -> list[str]:
        """List all stored token keys.

        Returns
        -------
        list[str]
            All keys with stored tokens.
        """


def _serialize_tokens(tokens: OAuthTokenSet) -> str:
    """Serialize an OAuthTokenSet to JSON."""
    return json.dumps(
        {
            "access_token": tokens.access_token,
            "token_type": tokens.token_type,
            "refresh_token": tokens.refresh_token,
            "expires_in": tokens.expires_in,
            "id_token": tokens.id_token,
            "scope": tokens.scope,
            "raw": tokens.raw,
            "issued_at": tokens.issued_at,
        }
    )


def _deserialize_tokens(data: str) -> OAuthTokenSet:
    """Deserialize an OAuthTokenSet from JSON."""
    obj = json.loads(data)
    return OAuthTokenSet(
        access_token=obj["access_token"],
        token_type=obj.get("token_type", "Bearer"),
        refresh_token=obj.get("refresh_token"),
        expires_in=obj.get("expires_in"),
        id_token=obj.get("id_token"),
        scope=obj.get("scope", ""),
        raw=obj.get("raw", {}),
        issued_at=obj.get("issued_at", time.time()),
    )


class MemoryTokenStore(TokenStore):
    """In-memory token store for development and single-process use.

    Thread-safe via asyncio.Lock, same pattern as MemorySessionStore.
    """

    def __init__(self) -> None:
        """Initialize the memory token store."""
        self._tokens: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def save(self, key: str, tokens: OAuthTokenSet) -> None:
        """Save tokens in memory."""
        async with self._lock:
            self._tokens[key] = _serialize_tokens(tokens)

    async def load(self, key: str) -> OAuthTokenSet | None:
        """Load tokens from memory."""
        async with self._lock:
            data = self._tokens.get(key)
            if data is None:
                return None
            return _deserialize_tokens(data)

    async def delete(self, key: str) -> None:
        """Delete tokens from memory."""
        async with self._lock:
            self._tokens.pop(key, None)

    async def exists(self, key: str) -> bool:
        """Check if tokens exist in memory."""
        async with self._lock:
            return key in self._tokens

    async def list_keys(self) -> list[str]:
        """List all token keys in memory."""
        async with self._lock:
            return list(self._tokens.keys())


class KeyringTokenStore(TokenStore):
    """OS keyring-backed token store for persistent native credentials.

    Requires the ``keyring`` package: ``pip install pywry[auth]``

    Parameters
    ----------
    service_name : str
        Service name for keyring storage (default "pywry-oauth").
    """

    def __init__(self, service_name: str = "pywry-oauth") -> None:
        """Initialize the keyring token store."""
        try:
            import keyring as _keyring
        except ImportError:
            msg = "Install keyring for persistent token storage: pip install pywry[auth]"
            raise ImportError(msg) from None
        self._service_name = service_name
        self._keyring = _keyring

    async def save(self, key: str, tokens: OAuthTokenSet) -> None:
        """Save tokens to the OS keyring."""
        data = _serialize_tokens(tokens)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._keyring.set_password, self._service_name, key, data)

    async def load(self, key: str) -> OAuthTokenSet | None:
        """Load tokens from the OS keyring."""
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, self._keyring.get_password, self._service_name, key)
        if data is None:
            return None
        return _deserialize_tokens(data)

    async def delete(self, key: str) -> None:
        """Delete tokens from the OS keyring."""
        loop = asyncio.get_event_loop()
        with contextlib.suppress(Exception):
            await loop.run_in_executor(None, self._keyring.delete_password, self._service_name, key)

    async def exists(self, key: str) -> bool:
        """Check if tokens exist in the OS keyring."""
        result = await self.load(key)
        return result is not None

    async def list_keys(self) -> list[str]:
        """List keys (not supported by all keyring backends).

        Returns an empty list as the keyring API does not provide
        a standard way to enumerate entries.
        """
        return []


class RedisTokenStore(TokenStore):
    """Redis-backed token store for multi-worker deployments.

    Uses Redis hash keys with optional TTL based on token ``expires_in``.

    Parameters
    ----------
    redis_url : str
        Redis connection URL.
    prefix : str
        Key prefix for namespacing (default "pywry").
    pool_size : int
        Connection pool size (default 10).
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        prefix: str = "pywry",
        pool_size: int = 10,
    ) -> None:
        """Initialize the Redis token store."""
        try:
            from redis.asyncio import Redis as RedisClient
        except ImportError:
            msg = "Redis backend requires the 'redis' package. Install with: pip install redis"
            raise ImportError(msg) from None

        self._prefix = prefix
        self._redis: Any = RedisClient.from_url(
            redis_url,
            max_connections=pool_size,
            decode_responses=True,
        )

    def _key(self, key: str) -> str:
        """Build a Redis key with prefix."""
        return f"{self._prefix}:oauth:tokens:{key}"

    async def save(self, key: str, tokens: OAuthTokenSet) -> None:
        """Save tokens to Redis with optional TTL."""
        redis_key = self._key(key)
        data = _serialize_tokens(tokens)
        if tokens.expires_in is not None and tokens.expires_in > 0:
            # Set TTL slightly longer than token expiry to allow refresh
            ttl = tokens.expires_in + 300  # 5 min buffer
            await self._redis.setex(redis_key, ttl, data)
        else:
            await self._redis.set(redis_key, data)

    async def load(self, key: str) -> OAuthTokenSet | None:
        """Load tokens from Redis."""
        data = await self._redis.get(self._key(key))
        if data is None:
            return None
        return _deserialize_tokens(data)

    async def delete(self, key: str) -> None:
        """Delete tokens from Redis."""
        await self._redis.delete(self._key(key))

    async def exists(self, key: str) -> bool:
        """Check if tokens exist in Redis."""
        return bool(await self._redis.exists(self._key(key)))

    async def list_keys(self) -> list[str]:
        """List all token keys in Redis."""
        pattern = f"{self._prefix}:oauth:tokens:*"
        prefix_len = len(f"{self._prefix}:oauth:tokens:")
        return [key[prefix_len:] async for key in self._redis.scan_iter(match=pattern)]


_token_store_instance: TokenStore | None = None
_token_store_lock = threading.Lock()


def get_token_store(backend: str = "memory", **kwargs: Any) -> TokenStore:
    """Factory function for token stores.

    Returns a singleton instance. Call ``reset_token_store()`` to clear
    the cached instance (e.g. in tests).

    Parameters
    ----------
    backend : str
        Storage backend: "memory", "keyring", or "redis".
    **kwargs : Any
        Additional keyword arguments passed to the store constructor.

    Returns
    -------
    TokenStore
        A configured token store instance.
    """
    global _token_store_instance  # noqa: PLW0603

    with _token_store_lock:
        if _token_store_instance is not None:
            return _token_store_instance

        if backend == "memory":
            _token_store_instance = MemoryTokenStore()
        elif backend == "keyring":
            service_name = kwargs.get("service_name", "pywry-oauth")
            _token_store_instance = KeyringTokenStore(service_name=service_name)
        elif backend == "redis":
            redis_url = kwargs.get("redis_url", "redis://localhost:6379/0")
            prefix = kwargs.get("prefix", "pywry")
            pool_size = kwargs.get("pool_size", 10)
            _token_store_instance = RedisTokenStore(
                redis_url=redis_url,
                prefix=prefix,
                pool_size=pool_size,
            )
        else:
            msg = f"Unknown token store backend: {backend}"
            raise ValueError(msg)

        return _token_store_instance


def reset_token_store() -> None:
    """Reset the singleton token store instance.

    Useful for tests that need a fresh token store between runs.
    """
    global _token_store_instance  # noqa: PLW0603

    with _token_store_lock:
        _token_store_instance = None
