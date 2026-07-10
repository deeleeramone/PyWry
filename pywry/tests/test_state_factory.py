"""Tests for the state factory functions."""

from __future__ import annotations

import os

from typing import TYPE_CHECKING

import pytest

from pywry.state import _factory
from pywry.state._factory import (
    _DEFAULT_SQLITE_PATH,
    _resolve_sqlite_path,
    _WorkerIdHolder,
    clear_state_caches,
    get_chart_store,
    get_chat_store,
    get_connection_router,
    get_event_bus,
    get_session_store,
    get_state_backend,
    get_widget_store,
    get_worker_id,
    is_deploy_mode,
)
from pywry.state.types import StateBackend


if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def _reset_caches_and_holders():
    """Reset caches between tests."""
    clear_state_caches()
    _factory._worker_id_holder.value = None
    _WorkerIdHolder.value = None
    yield
    clear_state_caches()
    _factory._worker_id_holder.value = None
    _WorkerIdHolder.value = None


class TestGetWorkerId:
    """Tests for get_worker_id."""

    def test_uses_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PYWRY_DEPLOY__WORKER_ID", "my-worker-id")
        assert get_worker_id() == "my-worker-id"

    def test_generates_when_no_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PYWRY_DEPLOY__WORKER_ID", raising=False)
        wid = get_worker_id()
        assert wid.startswith("worker-")
        assert len(wid) == len("worker-") + 8

    def test_caches_result(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PYWRY_DEPLOY__WORKER_ID", raising=False)
        wid1 = get_worker_id()
        wid2 = get_worker_id()
        assert wid1 == wid2


class TestGetStateBackend:
    """Tests for get_state_backend."""

    def test_default_is_memory(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PYWRY_DEPLOY__STATE_BACKEND", raising=False)
        assert get_state_backend() == StateBackend.MEMORY

    def test_redis_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PYWRY_DEPLOY__STATE_BACKEND", "redis")
        assert get_state_backend() == StateBackend.REDIS

    def test_sqlite_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PYWRY_DEPLOY__STATE_BACKEND", "sqlite")
        assert get_state_backend() == StateBackend.SQLITE

    def test_unknown_falls_back_to_memory(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PYWRY_DEPLOY__STATE_BACKEND", "unknown")
        assert get_state_backend() == StateBackend.MEMORY

    def test_uppercase_normalized(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PYWRY_DEPLOY__STATE_BACKEND", "REDIS")
        assert get_state_backend() == StateBackend.REDIS


class TestIsDeployMode:
    """Tests for is_deploy_mode."""

    def test_explicit_deploy_mode_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PYWRY_DEPLOY_MODE", "1")
        assert is_deploy_mode() is True

    def test_explicit_deploy_mode_yes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PYWRY_DEPLOY_MODE", "yes")
        assert is_deploy_mode() is True

    def test_explicit_deploy_mode_on(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PYWRY_DEPLOY_MODE", "on")
        assert is_deploy_mode() is True

    def test_redis_backend_implies_deploy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PYWRY_DEPLOY_MODE", raising=False)
        monkeypatch.setenv("PYWRY_DEPLOY__STATE_BACKEND", "redis")
        assert is_deploy_mode() is True

    def test_headless_with_backend_is_deploy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PYWRY_DEPLOY_MODE", raising=False)
        monkeypatch.setenv("PYWRY_DEPLOY__STATE_BACKEND", "sqlite")
        monkeypatch.setenv("PYWRY_HEADLESS", "1")
        assert is_deploy_mode() is True

    def test_headless_no_backend_is_not_deploy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PYWRY_DEPLOY_MODE", raising=False)
        monkeypatch.delenv("PYWRY_DEPLOY__STATE_BACKEND", raising=False)
        monkeypatch.setenv("PYWRY_HEADLESS", "1")
        assert is_deploy_mode() is False

    def test_no_env_is_not_deploy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PYWRY_DEPLOY_MODE", raising=False)
        monkeypatch.delenv("PYWRY_DEPLOY__STATE_BACKEND", raising=False)
        monkeypatch.delenv("PYWRY_HEADLESS", raising=False)
        assert is_deploy_mode() is False


class TestResolveSqlitePath:
    """Tests for _resolve_sqlite_path helper."""

    def test_explicit_path(self) -> None:
        from unittest.mock import MagicMock

        settings = MagicMock()
        settings.sqlite_path = "/tmp/test.db"
        result = _resolve_sqlite_path(settings)
        assert "/tmp/test.db" in result.replace("\\", "/")

    def test_user_path_expanded(self) -> None:
        from unittest.mock import MagicMock

        settings = MagicMock()
        settings.sqlite_path = "~/db.sqlite"
        result = _resolve_sqlite_path(settings)
        assert "~" not in result

    def test_default_when_missing(self) -> None:
        from unittest.mock import MagicMock

        # Object without sqlite_path attribute
        settings = MagicMock(spec=[])
        result = _resolve_sqlite_path(settings)
        # Default is ~/.config/pywry/pywry.db
        assert "pywry.db" in result

    def test_falsy_attr_uses_default(self) -> None:
        from unittest.mock import MagicMock

        settings = MagicMock()
        settings.sqlite_path = ""
        result = _resolve_sqlite_path(settings)
        # Falls back to default
        assert "pywry.db" in result


class TestGetWidgetStore:
    """Tests for get_widget_store."""

    def test_memory_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PYWRY_DEPLOY__STATE_BACKEND", raising=False)
        from pywry.state.memory import MemoryWidgetStore

        store = get_widget_store()
        assert isinstance(store, MemoryWidgetStore)

    def test_redis_backend(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PYWRY_DEPLOY__STATE_BACKEND", "redis")
        from pywry.state.redis import RedisWidgetStore

        store = get_widget_store()
        assert isinstance(store, RedisWidgetStore)

    def test_sqlite_backend(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("PYWRY_DEPLOY__STATE_BACKEND", "sqlite")
        # Use a temp path to avoid touching the user's real db
        monkeypatch.setenv("PYWRY_DEPLOY__SQLITE_PATH", str(tmp_path / "test.db"))
        from pywry.state.sqlite import SqliteWidgetStore

        store = get_widget_store()
        assert isinstance(store, SqliteWidgetStore)

    def test_caches_instance(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PYWRY_DEPLOY__STATE_BACKEND", raising=False)
        s1 = get_widget_store()
        s2 = get_widget_store()
        assert s1 is s2


class TestGetEventBus:
    """Tests for get_event_bus."""

    def test_memory_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PYWRY_DEPLOY__STATE_BACKEND", raising=False)
        from pywry.state.memory import MemoryEventBus

        bus = get_event_bus()
        assert isinstance(bus, MemoryEventBus)

    def test_redis_backend(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PYWRY_DEPLOY__STATE_BACKEND", "redis")
        from pywry.state.redis import RedisEventBus

        bus = get_event_bus()
        assert isinstance(bus, RedisEventBus)

    def test_sqlite_uses_memory_bus(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PYWRY_DEPLOY__STATE_BACKEND", "sqlite")
        from pywry.state.memory import MemoryEventBus

        bus = get_event_bus()
        # SQLite mode reuses memory bus
        assert isinstance(bus, MemoryEventBus)


class TestGetConnectionRouter:
    """Tests for get_connection_router."""

    def test_memory_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PYWRY_DEPLOY__STATE_BACKEND", raising=False)
        from pywry.state.memory import MemoryConnectionRouter

        router = get_connection_router()
        assert isinstance(router, MemoryConnectionRouter)

    def test_redis_backend(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PYWRY_DEPLOY__STATE_BACKEND", "redis")
        from pywry.state.redis import RedisConnectionRouter

        router = get_connection_router()
        assert isinstance(router, RedisConnectionRouter)

    def test_sqlite_uses_memory_router(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PYWRY_DEPLOY__STATE_BACKEND", "sqlite")
        from pywry.state.memory import MemoryConnectionRouter

        router = get_connection_router()
        assert isinstance(router, MemoryConnectionRouter)


class TestGetSessionStore:
    """Tests for get_session_store."""

    def test_memory_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PYWRY_DEPLOY__STATE_BACKEND", raising=False)
        from pywry.state.memory import MemorySessionStore

        store = get_session_store()
        assert isinstance(store, MemorySessionStore)

    def test_redis_backend(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PYWRY_DEPLOY__STATE_BACKEND", "redis")
        from pywry.state.redis import RedisSessionStore

        store = get_session_store()
        assert isinstance(store, RedisSessionStore)

    def test_sqlite_backend(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("PYWRY_DEPLOY__STATE_BACKEND", "sqlite")
        monkeypatch.setenv("PYWRY_DEPLOY__SQLITE_PATH", str(tmp_path / "test.db"))
        from pywry.state.sqlite import SqliteSessionStore

        store = get_session_store()
        assert isinstance(store, SqliteSessionStore)


class TestGetChatStore:
    """Tests for get_chat_store."""

    def test_memory_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PYWRY_DEPLOY__STATE_BACKEND", raising=False)
        from pywry.state.memory import MemoryChatStore

        store = get_chat_store()
        assert isinstance(store, MemoryChatStore)

    def test_redis_backend(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PYWRY_DEPLOY__STATE_BACKEND", "redis")
        from pywry.state.redis import RedisChatStore

        store = get_chat_store()
        assert isinstance(store, RedisChatStore)

    def test_sqlite_backend(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("PYWRY_DEPLOY__STATE_BACKEND", "sqlite")
        monkeypatch.setenv("PYWRY_DEPLOY__SQLITE_PATH", str(tmp_path / "test.db"))
        from pywry.state.sqlite import SqliteChatStore

        store = get_chat_store()
        assert isinstance(store, SqliteChatStore)


class TestGetChartStore:
    """Tests for get_chart_store."""

    def test_redis_backend(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PYWRY_DEPLOY__STATE_BACKEND", "redis")
        from pywry.state.redis import RedisChartStore

        store = get_chart_store()
        assert isinstance(store, RedisChartStore)

    def test_memory_via_tvchart_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PYWRY_DEPLOY__STATE_BACKEND", raising=False)
        # Configure tvchart memory backend
        monkeypatch.setenv("PYWRY_TVCHART__STORAGE_BACKEND", "memory")

        from pywry.config import get_settings
        from pywry.state.memory import MemoryChartStore

        # Clear settings cache
        get_settings.cache_clear()

        store = get_chart_store()
        assert isinstance(store, MemoryChartStore)

    def test_file_via_tvchart_config(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.delenv("PYWRY_DEPLOY__STATE_BACKEND", raising=False)
        # Default tvchart backend is "file"
        monkeypatch.delenv("PYWRY_TVCHART__STORAGE_BACKEND", raising=False)
        monkeypatch.setenv("PYWRY_TVCHART__STORAGE_PATH", str(tmp_path))

        from pywry.config import get_settings
        from pywry.state.file import FileChartStore

        # Clear settings cache
        get_settings.cache_clear()

        store = get_chart_store()
        assert isinstance(store, FileChartStore)


class TestClearStateCaches:
    """Tests for clear_state_caches."""

    def test_clear_recreates_stores(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PYWRY_DEPLOY__STATE_BACKEND", raising=False)
        s1 = get_widget_store()
        clear_state_caches()
        s2 = get_widget_store()
        assert s1 is not s2

    def test_clear_clears_all_factories(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PYWRY_DEPLOY__STATE_BACKEND", raising=False)
        # Populate all caches
        get_widget_store()
        get_event_bus()
        get_connection_router()
        get_session_store()
        get_chat_store()
        get_chart_store()
        # Clear should not raise
        clear_state_caches()


class TestDefaultConstants:
    """Sanity tests for module-level constants."""

    def test_default_sqlite_path(self) -> None:
        assert _DEFAULT_SQLITE_PATH == "~/.config/pywry/pywry.db"

    def test_get_deploy_settings_returns_settings(self) -> None:
        from pywry.state._factory import _get_deploy_settings

        settings = _get_deploy_settings()
        assert hasattr(settings, "redis_url")
