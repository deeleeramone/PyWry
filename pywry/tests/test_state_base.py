"""Tests for the abstract base classes and default no-op implementations."""

from __future__ import annotations

import time

from typing import Any
from unittest.mock import AsyncMock

import pytest

from pywry.state.base import (
    ChartStore,
    ChatStore,
    ConnectionRouter,
    EventBus,
    SessionStore,
    WidgetStore,
)
from pywry.state.types import OAuthTokenSet


class TestOAuthTokenSet:
    """Tests for the OAuthTokenSet dataclass properties."""

    def test_no_expiry(self) -> None:
        token = OAuthTokenSet(access_token="x", expires_in=None)
        assert token.is_expired is False
        assert token.expires_at is None

    def test_with_expiry_not_expired(self) -> None:
        token = OAuthTokenSet(access_token="x", expires_in=3600, issued_at=time.time())
        assert token.is_expired is False
        assert token.expires_at is not None
        assert token.expires_at > time.time()

    def test_with_expiry_expired(self) -> None:
        token = OAuthTokenSet(
            access_token="x",
            expires_in=10,
            issued_at=time.time() - 100,
        )
        assert token.is_expired is True
        assert token.expires_at is not None
        assert token.expires_at < time.time()


# --- ChatStore default no-op methods ---


class _MinimalChatStore(ChatStore):
    """Minimal ChatStore implementing only the abstract methods so we can
    invoke the inherited default audit-trail no-ops."""

    async def save_thread(self, widget_id, thread):
        return None

    async def get_thread(self, widget_id, thread_id):
        return None

    async def list_threads(self, widget_id):
        return []

    async def delete_thread(self, widget_id, thread_id):
        return False

    async def append_message(self, widget_id, thread_id, message):
        return None

    async def get_messages(self, widget_id, thread_id, limit=50, before_id=None):
        return []

    async def clear_messages(self, widget_id, thread_id):
        return None


class TestChatStoreDefaultNoOps:
    """Default audit-trail methods on the abstract base."""

    @pytest.fixture
    def store(self) -> _MinimalChatStore:
        return _MinimalChatStore()

    async def test_log_tool_call_default_returns_none(self, store: _MinimalChatStore) -> None:
        result = await store.log_tool_call("m1", "tc1", "search", arguments={"q": "x"})
        assert result is None

    async def test_log_artifact_default_returns_none(self, store: _MinimalChatStore) -> None:
        result = await store.log_artifact("m1", "code", title="t", content="x")
        assert result is None

    async def test_log_token_usage_default_returns_none(self, store: _MinimalChatStore) -> None:
        result = await store.log_token_usage("m1", model="gpt-4", prompt_tokens=10)
        assert result is None

    async def test_log_resource_default_returns_none(self, store: _MinimalChatStore) -> None:
        result = await store.log_resource("t1", "file:///x", name="x", mime_type="text/plain")
        assert result is None

    async def test_log_skill_default_returns_none(self, store: _MinimalChatStore) -> None:
        result = await store.log_skill("t1", "myskill")
        assert result is None

    async def test_get_tool_calls_default_returns_empty(self, store: _MinimalChatStore) -> None:
        result = await store.get_tool_calls("m1")
        assert result == []

    async def test_get_artifacts_default_returns_empty(self, store: _MinimalChatStore) -> None:
        result = await store.get_artifacts("m1")
        assert result == []

    async def test_get_usage_stats_default_returns_zeros(self, store: _MinimalChatStore) -> None:
        result = await store.get_usage_stats()
        assert result == {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cost_usd": 0.0,
            "count": 0,
        }

    async def test_get_total_cost_default_returns_zero(self, store: _MinimalChatStore) -> None:
        result = await store.get_total_cost()
        assert result == 0.0

    async def test_search_messages_default_returns_empty(self, store: _MinimalChatStore) -> None:
        result = await store.search_messages("query")
        assert result == []


# --- ChartStore default update_layout_meta ---


class _MinimalChartStore(ChartStore):
    """Minimal ChartStore so we can test the default `update_layout_meta`."""

    def __init__(self) -> None:
        self.rename_calls: list[tuple[str, str, str]] = []

    async def save_layout(
        self,
        user_id: str,
        layout_id: str,
        name: str,
        data_json: str,
        *,
        summary: str = "",
    ) -> dict[str, Any]:
        return {"id": layout_id}

    async def get_layout(self, user_id: str, layout_id: str) -> str | None:
        return None

    async def list_layouts(self, user_id: str) -> list[dict[str, Any]]:
        return []

    async def delete_layout(self, user_id: str, layout_id: str) -> bool:
        return False

    async def rename_layout(self, user_id: str, layout_id: str, new_name: str) -> bool:
        self.rename_calls.append((user_id, layout_id, new_name))
        return True

    async def save_settings_template(self, user_id: str, template_json: str) -> None:
        return None

    async def get_settings_template(self, user_id: str) -> str | None:
        return None

    async def get_settings_default_id(self, user_id: str) -> str:
        return "factory"

    async def set_settings_default_id(self, user_id: str, template_id: str) -> None:
        return None

    async def clear_settings_template(self, user_id: str) -> None:
        return None


class TestChartStoreDefault:
    """Tests for the default update_layout_meta implementation."""

    async def test_update_layout_meta_calls_rename(self) -> None:
        store = _MinimalChartStore()
        result = await store.update_layout_meta("u1", "l1", name="New", summary="ignored")
        assert result is True
        # Default implementation calls rename_layout
        assert store.rename_calls == [("u1", "l1", "New")]


# --- EventBus subscribe default raises NotImplementedError ---


class _MinimalEventBus(EventBus):
    """Minimal EventBus so we can hit the abstract `subscribe` default body."""

    async def publish(self, channel, event):
        return None

    def subscribe(self, channel):  # type: ignore[override]
        # Call the abstract method directly to hit line 241
        return EventBus.subscribe(self, channel)

    async def unsubscribe(self, channel):
        return None


class TestEventBusSubscribe:
    """Test that EventBus.subscribe default raises NotImplementedError."""

    def test_subscribe_default_raises(self) -> None:
        bus = _MinimalEventBus()
        with pytest.raises(NotImplementedError):
            bus.subscribe("ch")
