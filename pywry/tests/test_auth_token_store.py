"""Unit tests for OAuth2 token storage backends."""

# pylint: disable=redefined-outer-name

from __future__ import annotations

import asyncio
import json
import time

from unittest.mock import patch

import pytest

from pywry.auth.token_store import (
    MemoryTokenStore,
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


class TestKeyringTokenStore:
    """Tests for KeyringTokenStore with mocked keyring."""

    def test_import_error(self) -> None:
        """Missing keyring raises ImportError."""
        with patch.dict("sys.modules", {"keyring": None}):
            from pywry.auth.token_store import KeyringTokenStore

            with pytest.raises(ImportError, match="keyring"):
                KeyringTokenStore()


# ── get_token_store factory ─────────────────────────────────────────


class TestGetTokenStore:
    """Tests for the get_token_store factory."""

    def test_memory_backend(self) -> None:
        """'memory' returns a MemoryTokenStore."""
        reset_token_store()
        store = get_token_store("memory")
        assert isinstance(store, MemoryTokenStore)

    def test_default_is_memory(self) -> None:
        """Default backend is memory."""
        reset_token_store()
        store = get_token_store()
        assert isinstance(store, MemoryTokenStore)

    def test_unknown_backend_raises(self) -> None:
        """Unknown backend raises ValueError."""
        reset_token_store()
        with pytest.raises(ValueError, match="Unknown"):
            get_token_store("nonexistent")
