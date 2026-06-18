"""Unit tests for OAuth2 token storage backends."""

from __future__ import annotations

import asyncio
import json
import sys
import time

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pywry.auth.token_store import (
    KeyringTokenStore,
    MemoryTokenStore,
    RedisTokenStore,
    _deserialize_tokens,
    _serialize_tokens,
    get_token_store,
    reset_token_store,
)
from pywry.state.types import OAuthTokenSet


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture()
def sample_tokens() -> OAuthTokenSet:
    """Create sample tokens for testing."""
    return OAuthTokenSet(
        access_token="at_test_123",
        token_type="Bearer",
        refresh_token="rt_test_456",
        expires_in=3600,
        id_token="id_tok",
        scope="openid email",
        issued_at=time.time(),
    )


@pytest.fixture()
def memory_store() -> MemoryTokenStore:
    """Create a MemoryTokenStore."""
    return MemoryTokenStore()


# ── Serialization ───────────────────────────────────────────────────


class TestSerialization:
    """Tests for token serialization helpers."""

    def test_round_trip(self, sample_tokens: OAuthTokenSet) -> None:
        """Tokens survive serialize→deserialize round trip."""
        data = _serialize_tokens(sample_tokens)
        restored = _deserialize_tokens(data)
        assert restored.access_token == sample_tokens.access_token
        assert restored.token_type == sample_tokens.token_type
        assert restored.refresh_token == sample_tokens.refresh_token
        assert restored.expires_in == sample_tokens.expires_in
        assert restored.scope == sample_tokens.scope

    def test_serialize_is_json(self, sample_tokens: OAuthTokenSet) -> None:
        """Serialized output is valid JSON."""
        data = _serialize_tokens(sample_tokens)
        parsed = json.loads(data)
        assert parsed["access_token"] == "at_test_123"

    def test_deserialize_missing_fields(self) -> None:
        """Deserialize handles missing optional fields gracefully."""
        data = json.dumps({"access_token": "at_minimal"})
        tokens = _deserialize_tokens(data)
        assert tokens.access_token == "at_minimal"
        assert tokens.token_type == "Bearer"
        assert tokens.refresh_token is None


# ── MemoryTokenStore ────────────────────────────────────────────────


class TestMemoryTokenStore:
    """Tests for MemoryTokenStore."""

    def test_save_and_load(
        self, memory_store: MemoryTokenStore, sample_tokens: OAuthTokenSet
    ) -> None:
        """Save and load round-trip."""
        asyncio.run(memory_store.save("user1", sample_tokens))
        loaded = asyncio.run(memory_store.load("user1"))
        assert loaded is not None
        assert loaded.access_token == sample_tokens.access_token
        assert loaded.refresh_token == sample_tokens.refresh_token

    def test_load_missing(self, memory_store: MemoryTokenStore) -> None:
        """Load returns None for missing key."""
        loaded = asyncio.run(memory_store.load("nonexistent"))
        assert loaded is None

    def test_exists(self, memory_store: MemoryTokenStore, sample_tokens: OAuthTokenSet) -> None:
        """exists() returns True after save."""
        asyncio.run(memory_store.save("u1", sample_tokens))
        assert asyncio.run(memory_store.exists("u1"))
        assert not asyncio.run(memory_store.exists("u2"))

    def test_delete(self, memory_store: MemoryTokenStore, sample_tokens: OAuthTokenSet) -> None:
        """delete() removes tokens."""
        asyncio.run(memory_store.save("u1", sample_tokens))
        asyncio.run(memory_store.delete("u1"))
        assert not asyncio.run(memory_store.exists("u1"))

    def test_delete_missing(self, memory_store: MemoryTokenStore) -> None:
        """delete() on missing key does not raise."""
        asyncio.run(memory_store.delete("missing"))

    def test_list_keys(self, memory_store: MemoryTokenStore, sample_tokens: OAuthTokenSet) -> None:
        """list_keys() returns all stored keys."""
        asyncio.run(memory_store.save("a", sample_tokens))
        asyncio.run(memory_store.save("b", sample_tokens))
        keys = asyncio.run(memory_store.list_keys())
        assert set(keys) == {"a", "b"}

    def test_overwrite(self, memory_store: MemoryTokenStore, sample_tokens: OAuthTokenSet) -> None:
        """Saving under the same key overwrites."""
        asyncio.run(memory_store.save("u1", sample_tokens))
        new_tokens = OAuthTokenSet(
            access_token="at_new",
            expires_in=7200,
            issued_at=time.time(),
        )
        asyncio.run(memory_store.save("u1", new_tokens))
        loaded = asyncio.run(memory_store.load("u1"))
        assert loaded is not None
        assert loaded.access_token == "at_new"


# ── KeyringTokenStore ───────────────────────────────────────────────


@pytest.fixture()
def fake_keyring_store() -> tuple[KeyringTokenStore, MagicMock]:
    """Build a KeyringTokenStore with its _keyring attribute replaced by a mock."""
    fake = MagicMock()
    store = KeyringTokenStore(service_name="pywry-test")
    store._keyring = fake
    return store, fake


class TestKeyringTokenStoreImport:
    """Tests for KeyringTokenStore optional-dependency handling."""

    def test_import_error(self) -> None:
        """Missing keyring raises ImportError."""
        with (
            patch.dict("sys.modules", {"keyring": None}),
            pytest.raises(ImportError, match="keyring"),
        ):
            KeyringTokenStore()


class TestKeyringTokenStore:
    """CRUD operations against KeyringTokenStore using a mocked keyring backend."""

    def test_save_calls_set_password(
        self,
        fake_keyring_store: tuple[KeyringTokenStore, MagicMock],
    ) -> None:
        """save() invokes keyring.set_password with serialized tokens."""
        store, fake = fake_keyring_store
        fake.set_password = MagicMock()
        tokens = OAuthTokenSet(access_token="at_k", expires_in=3600)
        asyncio.run(store.save("user1", tokens))

        fake.set_password.assert_called_once()
        args = fake.set_password.call_args[0]
        assert args[0] == "pywry-test"
        assert args[1] == "user1"
        assert "at_k" in args[2]

    def test_load_returns_tokens(
        self,
        fake_keyring_store: tuple[KeyringTokenStore, MagicMock],
    ) -> None:
        """load() round-trips tokens from keyring."""
        store, fake = fake_keyring_store
        tokens = OAuthTokenSet(access_token="at_k", expires_in=3600)
        fake.get_password = MagicMock(return_value=_serialize_tokens(tokens))
        result = asyncio.run(store.load("user1"))
        assert result is not None
        assert result.access_token == "at_k"

    def test_load_missing_returns_none(
        self,
        fake_keyring_store: tuple[KeyringTokenStore, MagicMock],
    ) -> None:
        """load() returns None for missing key."""
        store, fake = fake_keyring_store
        fake.get_password = MagicMock(return_value=None)
        result = asyncio.run(store.load("missing"))
        assert result is None

    def test_delete_calls_delete_password(
        self,
        fake_keyring_store: tuple[KeyringTokenStore, MagicMock],
    ) -> None:
        """delete() invokes keyring.delete_password."""
        store, fake = fake_keyring_store
        fake.delete_password = MagicMock()
        asyncio.run(store.delete("user1"))
        fake.delete_password.assert_called_once()

    def test_delete_swallows_exceptions(
        self,
        fake_keyring_store: tuple[KeyringTokenStore, MagicMock],
    ) -> None:
        """delete() swallows keyring errors instead of bubbling them up."""
        store, fake = fake_keyring_store
        fake.delete_password = MagicMock(side_effect=RuntimeError("not found"))
        # Must not raise
        asyncio.run(store.delete("missing"))

    def test_exists_via_load(
        self,
        fake_keyring_store: tuple[KeyringTokenStore, MagicMock],
    ) -> None:
        """exists() uses load() under the hood and returns True/False accordingly."""
        store, fake = fake_keyring_store
        fake.get_password = MagicMock(
            return_value=_serialize_tokens(OAuthTokenSet(access_token="x"))
        )
        assert asyncio.run(store.exists("u")) is True

        fake.get_password = MagicMock(return_value=None)
        assert asyncio.run(store.exists("u")) is False

    def test_list_keys_returns_empty(
        self,
        fake_keyring_store: tuple[KeyringTokenStore, MagicMock],
    ) -> None:
        """list_keys() always returns [] since keyring offers no enumeration API."""
        store, _ = fake_keyring_store
        keys = asyncio.run(store.list_keys())
        assert keys == []


# ── RedisTokenStore ─────────────────────────────────────────────────


@pytest.fixture()
def fake_redis_store() -> tuple[RedisTokenStore, AsyncMock]:
    """Build a RedisTokenStore with its _redis attribute replaced by a mock."""
    store = RedisTokenStore(redis_url="redis://localhost:6379/0", prefix="pywry-test")
    fake = AsyncMock()
    store._redis = fake
    return store, fake


class TestRedisTokenStoreImport:
    """Tests for RedisTokenStore optional-dependency handling."""

    def test_missing_redis_raises(self) -> None:
        """RedisTokenStore raises ImportError when redis.asyncio is absent."""
        original = sys.modules.get("redis.asyncio")
        sys.modules["redis.asyncio"] = None  # type: ignore[assignment]
        try:
            with pytest.raises(ImportError, match="Redis backend"):
                RedisTokenStore()
        finally:
            if original is not None:
                sys.modules["redis.asyncio"] = original
            else:
                sys.modules.pop("redis.asyncio", None)


class TestRedisTokenStore:
    """CRUD operations against RedisTokenStore using a mocked async client."""

    def test_key_format(self, fake_redis_store: tuple[RedisTokenStore, AsyncMock]) -> None:
        """_key() builds the correct Redis key."""
        store, _ = fake_redis_store
        assert store._key("u1") == "pywry-test:oauth:tokens:u1"

    def test_save_with_expiry_uses_setex(
        self,
        fake_redis_store: tuple[RedisTokenStore, AsyncMock],
    ) -> None:
        """save() with expires_in uses setex with TTL + 300s buffer."""
        store, fake = fake_redis_store
        fake.setex = AsyncMock(return_value=True)
        tokens = OAuthTokenSet(access_token="at", expires_in=3600)
        asyncio.run(store.save("user1", tokens))
        fake.setex.assert_awaited_once()
        args = fake.setex.call_args[0]
        assert args[0] == "pywry-test:oauth:tokens:user1"
        assert args[1] == 3600 + 300  # buffer
        assert "at" in args[2]

    def test_save_no_expiry_uses_set(
        self,
        fake_redis_store: tuple[RedisTokenStore, AsyncMock],
    ) -> None:
        """save() without expires_in uses plain SET (no TTL)."""
        store, fake = fake_redis_store
        fake.set = AsyncMock(return_value=True)
        tokens = OAuthTokenSet(access_token="at_noexp", expires_in=None)
        asyncio.run(store.save("u1", tokens))
        fake.set.assert_awaited_once()

    def test_save_zero_expiry_uses_set(
        self,
        fake_redis_store: tuple[RedisTokenStore, AsyncMock],
    ) -> None:
        """save() with expires_in=0 uses plain SET (not SETEX)."""
        store, fake = fake_redis_store
        fake.set = AsyncMock(return_value=True)
        tokens = OAuthTokenSet(access_token="at_zero", expires_in=0)
        asyncio.run(store.save("u1", tokens))
        fake.set.assert_awaited_once()

    def test_load_returns_tokens(
        self,
        fake_redis_store: tuple[RedisTokenStore, AsyncMock],
    ) -> None:
        """load() deserializes tokens from Redis."""
        store, fake = fake_redis_store
        tokens = OAuthTokenSet(access_token="at_loaded", expires_in=600)
        fake.get = AsyncMock(return_value=_serialize_tokens(tokens))
        result = asyncio.run(store.load("u1"))
        assert result is not None
        assert result.access_token == "at_loaded"

    def test_load_missing(
        self,
        fake_redis_store: tuple[RedisTokenStore, AsyncMock],
    ) -> None:
        """load() returns None when Redis key missing."""
        store, fake = fake_redis_store
        fake.get = AsyncMock(return_value=None)
        result = asyncio.run(store.load("missing"))
        assert result is None

    def test_delete(self, fake_redis_store: tuple[RedisTokenStore, AsyncMock]) -> None:
        """delete() invokes Redis DELETE with the prefixed key."""
        store, fake = fake_redis_store
        fake.delete = AsyncMock(return_value=1)
        asyncio.run(store.delete("u1"))
        fake.delete.assert_awaited_with("pywry-test:oauth:tokens:u1")

    def test_exists(self, fake_redis_store: tuple[RedisTokenStore, AsyncMock]) -> None:
        """exists() reflects Redis EXISTS as a boolean."""
        store, fake = fake_redis_store
        fake.exists = AsyncMock(return_value=1)
        assert asyncio.run(store.exists("u1")) is True

        fake.exists = AsyncMock(return_value=0)
        assert asyncio.run(store.exists("u1")) is False

    def test_list_keys_via_scan_iter(
        self,
        fake_redis_store: tuple[RedisTokenStore, AsyncMock],
    ) -> None:
        """list_keys() iterates Redis SCAN and strips the prefix."""
        store, fake = fake_redis_store

        async def fake_scan_iter(match: str) -> Any:
            for key in [
                "pywry-test:oauth:tokens:user1",
                "pywry-test:oauth:tokens:user2",
            ]:
                yield key

        fake.scan_iter = fake_scan_iter

        keys = asyncio.run(store.list_keys())
        assert sorted(keys) == ["user1", "user2"]


# ── get_token_store factory ─────────────────────────────────────────


class TestGetTokenStore:
    """Tests for the get_token_store factory."""

    def test_memory_backend(self) -> None:
        """'memory' returns a MemoryTokenStore."""
        reset_token_store()
        store = get_token_store("memory")
        assert isinstance(store, MemoryTokenStore)
        reset_token_store()

    def test_default_is_memory(self) -> None:
        """Default backend is memory."""
        reset_token_store()
        store = get_token_store()
        assert isinstance(store, MemoryTokenStore)
        reset_token_store()

    def test_unknown_backend_raises(self) -> None:
        """Unknown backend raises ValueError."""
        reset_token_store()
        with pytest.raises(ValueError, match="Unknown"):
            get_token_store("nonexistent")

    def test_get_returns_cached_singleton(self) -> None:
        """Subsequent calls return the same instance."""
        reset_token_store()
        first = get_token_store("memory")
        second = get_token_store("memory")
        assert first is second
        reset_token_store()

    def test_get_keyring_backend(self) -> None:
        """`keyring` backend instantiates KeyringTokenStore."""
        reset_token_store()
        store = get_token_store("keyring", service_name="pywry-test-extra")
        assert isinstance(store, KeyringTokenStore)
        assert store._service_name == "pywry-test-extra"
        reset_token_store()

    def test_get_redis_backend(self) -> None:
        """`redis` backend instantiates RedisTokenStore."""
        reset_token_store()
        store = get_token_store(
            "redis",
            redis_url="redis://localhost:6379/0",
            prefix="px-test",
            pool_size=5,
        )
        assert isinstance(store, RedisTokenStore)
        assert store._prefix == "px-test"
        reset_token_store()
