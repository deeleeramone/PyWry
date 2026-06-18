"""Tests for the ServerStateManager."""

from __future__ import annotations

import asyncio

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pywry.state.server import (
    ServerStateManager,
    _StateHolder,
    get_server_state,
    reset_server_state,
)
from pywry.state.types import EventMessage, WidgetData


@pytest.fixture(autouse=True)
def _reset_state_caches():
    """Ensure clean state before/after each test."""
    from pywry.state import _factory
    from pywry.state.callbacks import _RegistryHolder

    _factory.clear_state_caches()
    _RegistryHolder.instance = None
    reset_server_state()
    yield
    _factory.clear_state_caches()
    _RegistryHolder.instance = None
    reset_server_state()


class TestServerStateManagerLocalMode:
    """Tests in local mode (deploy_mode=False)."""

    @pytest.fixture
    def manager(self, monkeypatch: pytest.MonkeyPatch) -> ServerStateManager:
        # Force local mode
        monkeypatch.delenv("PYWRY_DEPLOY_MODE", raising=False)
        monkeypatch.delenv("PYWRY_DEPLOY__STATE_BACKEND", raising=False)
        monkeypatch.delenv("PYWRY_HEADLESS", raising=False)
        return ServerStateManager()

    async def test_register_and_get_widget_local(self, manager: ServerStateManager) -> None:
        await manager.register_widget(
            widget_id="w1",
            html="<h1>Hello</h1>",
            token="tok1",
            metadata={"title": "Test"},
        )

        widget = await manager.get_widget("w1")
        assert widget is not None
        assert widget.widget_id == "w1"
        assert widget.html == "<h1>Hello</h1>"
        assert widget.token == "tok1"
        assert widget.metadata == {"title": "Test"}

    async def test_register_widget_no_token_no_metadata(self, manager: ServerStateManager) -> None:
        await manager.register_widget(widget_id="w1", html="<p>x</p>")
        widget = await manager.get_widget("w1")
        assert widget is not None
        assert widget.token is None
        assert widget.metadata == {}

    async def test_get_nonexistent_widget(self, manager: ServerStateManager) -> None:
        widget = await manager.get_widget("missing")
        assert widget is None

    async def test_get_widget_html(self, manager: ServerStateManager) -> None:
        await manager.register_widget("w1", "<h1>x</h1>")
        html = await manager.get_widget_html("w1")
        assert html == "<h1>x</h1>"

    async def test_get_widget_html_missing(self, manager: ServerStateManager) -> None:
        result = await manager.get_widget_html("missing")
        assert result is None

    async def test_update_widget_html(self, manager: ServerStateManager) -> None:
        await manager.register_widget("w1", "<h1>old</h1>")
        result = await manager.update_widget_html("w1", "<h1>new</h1>")
        assert result is True
        assert await manager.get_widget_html("w1") == "<h1>new</h1>"

    async def test_update_widget_html_missing(self, manager: ServerStateManager) -> None:
        result = await manager.update_widget_html("missing", "<h1>x</h1>")
        assert result is False

    async def test_widget_exists(self, manager: ServerStateManager) -> None:
        assert await manager.widget_exists("w1") is False
        await manager.register_widget("w1", "<h1>x</h1>")
        assert await manager.widget_exists("w1") is True

    async def test_remove_widget(self, manager: ServerStateManager) -> None:
        await manager.register_widget("w1", "<h1>x</h1>", token="tok1")
        result = await manager.remove_widget("w1")
        assert result is True
        assert await manager.widget_exists("w1") is False

    async def test_remove_widget_missing(self, manager: ServerStateManager) -> None:
        result = await manager.remove_widget("missing")
        assert result is False

    async def test_list_widgets(self, manager: ServerStateManager) -> None:
        await manager.register_widget("w1", "<h1>1</h1>")
        await manager.register_widget("w2", "<h1>2</h1>")
        widgets = await manager.list_widgets()
        assert set(widgets) == {"w1", "w2"}

    async def test_widgets_property(self, manager: ServerStateManager) -> None:
        await manager.register_widget("w1", "<h1>x</h1>")
        widgets = manager.widgets
        assert "w1" in widgets
        assert widgets["w1"]["html"] == "<h1>x</h1>"

    async def test_widget_tokens_property(self, manager: ServerStateManager) -> None:
        await manager.register_widget("w1", "<h1>x</h1>", token="tok1")
        tokens = manager.widget_tokens
        assert tokens["w1"] == "tok1"

    async def test_connections_property(self, manager: ServerStateManager) -> None:
        connections = manager.connections
        assert connections == {}

    async def test_event_queues_property(self, manager: ServerStateManager) -> None:
        queues = manager.event_queues
        assert queues == {}

    async def test_register_connection_local(self, manager: ServerStateManager) -> None:
        ws = MagicMock()
        queue = await manager.register_connection("w1", ws)
        assert isinstance(queue, asyncio.Queue)
        assert manager.connections["w1"] is ws

    async def test_unregister_connection(self, manager: ServerStateManager) -> None:
        ws = MagicMock()
        await manager.register_connection("w1", ws)
        await manager.unregister_connection("w1")
        assert "w1" not in manager.connections
        assert "w1" not in manager.event_queues

    async def test_unregister_connection_missing(self, manager: ServerStateManager) -> None:
        # No-op for missing connections
        await manager.unregister_connection("missing")

    async def test_get_connection(self, manager: ServerStateManager) -> None:
        ws = MagicMock()
        await manager.register_connection("w1", ws)
        result = await manager.get_connection("w1")
        assert result is ws

    async def test_get_connection_missing(self, manager: ServerStateManager) -> None:
        result = await manager.get_connection("missing")
        assert result is None

    async def test_get_event_queue(self, manager: ServerStateManager) -> None:
        ws = MagicMock()
        await manager.register_connection("w1", ws)
        result = await manager.get_event_queue("w1")
        assert isinstance(result, asyncio.Queue)

    async def test_get_event_queue_missing(self, manager: ServerStateManager) -> None:
        result = await manager.get_event_queue("missing")
        assert result is None

    async def test_register_callback(self, manager: ServerStateManager) -> None:
        await manager.register_widget("w1", "<h1>x</h1>")

        def cb(data: dict, widget_id: str, event_type: str) -> str:
            return "ok"

        await manager.register_callback("w1", "click", cb)
        result = await manager.get_callback("w1", "click")
        assert result is cb

    async def test_register_callback_no_widget(self, manager: ServerStateManager) -> None:
        # Register callback without prior widget registration
        async def cb(*args) -> None:
            pass

        # Should still register but local widgets dict won't be updated
        await manager.register_callback("orphan", "click", cb)
        result = await manager.get_callback("orphan", "click")
        assert result is cb

    async def test_register_callback_creates_callbacks_dict(
        self, manager: ServerStateManager
    ) -> None:
        """Test the branch where local widget exists but has no callbacks dict."""
        await manager.register_widget("w1", "<h1>x</h1>")
        # Manually delete the callbacks dict to test the branch
        del manager._local_widgets["w1"]["callbacks"]

        async def cb(*args) -> None:
            pass

        await manager.register_callback("w1", "click", cb)
        assert "callbacks" in manager._local_widgets["w1"]
        assert manager._local_widgets["w1"]["callbacks"]["click"] is cb

    async def test_get_callback_missing(self, manager: ServerStateManager) -> None:
        result = await manager.get_callback("missing", "click")
        assert result is None

    async def test_invoke_callback(self, manager: ServerStateManager) -> None:
        async def cb(data: dict, widget_id: str, event_type: str) -> str:
            return f"{widget_id}:{event_type}"

        await manager.register_callback("w1", "click", cb)
        success, result = await manager.invoke_callback("w1", "click", {})
        assert success is True
        assert result == "w1:click"

    async def test_invoke_callback_missing(self, manager: ServerStateManager) -> None:
        success, result = await manager.invoke_callback("missing", "click", {})
        assert success is False
        assert result is None

    async def test_broadcast_event_local(self, manager: ServerStateManager) -> None:
        ws = MagicMock()
        queue = await manager.register_connection("w1", ws)

        await manager.broadcast_event("w1", "click", {"x": 100})

        assert queue.qsize() == 1
        msg = queue.get_nowait()
        assert msg == {"type": "click", "data": {"x": 100}}

    async def test_broadcast_event_no_queue(self, manager: ServerStateManager) -> None:
        # No connection registered - should be no-op
        await manager.broadcast_event("missing", "click", {"x": 100})

    async def test_send_to_widget(self, manager: ServerStateManager) -> None:
        ws = MagicMock()
        queue = await manager.register_connection("w1", ws)

        result = await manager.send_to_widget("w1", {"type": "msg", "data": "hello"})
        assert result is True
        assert queue.qsize() == 1

    async def test_send_to_widget_no_queue_local(self, manager: ServerStateManager) -> None:
        # Local mode, no queue, no broadcast
        result = await manager.send_to_widget("missing", {"type": "msg"})
        assert result is False

    async def test_create_session(self, manager: ServerStateManager) -> None:
        session_id = await manager.create_session(
            "user1", roles=["admin"], metadata={"name": "Alice"}
        )
        assert session_id is not None
        assert isinstance(session_id, str)

    async def test_create_session_default_roles(self, manager: ServerStateManager) -> None:
        session_id = await manager.create_session("user1")
        assert session_id is not None

    async def test_get_session(self, manager: ServerStateManager) -> None:
        session_id = await manager.create_session("user1", roles=["admin"])
        session = await manager.get_session(session_id)
        assert session is not None
        assert session.user_id == "user1"

    async def test_get_session_missing(self, manager: ServerStateManager) -> None:
        session = await manager.get_session("missing")
        assert session is None

    async def test_cleanup(self, manager: ServerStateManager) -> None:
        await manager.register_widget("w1", "<h1>x</h1>", token="tok")
        ws = MagicMock()
        await manager.register_connection("w1", ws)

        await manager.cleanup()

        assert len(manager._local_widgets) == 0
        assert len(manager._local_widget_tokens) == 0
        assert len(manager._local_connections) == 0


class TestServerStateManagerProperties:
    """Tests for property accessors."""

    def test_deploy_mode_property(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PYWRY_DEPLOY_MODE", raising=False)
        monkeypatch.delenv("PYWRY_DEPLOY__STATE_BACKEND", raising=False)
        manager = ServerStateManager()
        assert manager.deploy_mode is False

        monkeypatch.setenv("PYWRY_DEPLOY_MODE", "1")
        assert manager.deploy_mode is True

    def test_worker_id_property(self) -> None:
        manager = ServerStateManager()
        wid = manager.worker_id
        assert wid is not None
        assert isinstance(wid, str)


class TestServerStateManagerInitialization:
    """Tests for the lazy initialization mechanism."""

    async def test_ensure_initialized_idempotent(self) -> None:
        manager = ServerStateManager()
        manager._ensure_initialized()
        first_widget_store = manager._widget_store
        # Calling again does not re-init
        manager._ensure_initialized()
        assert manager._widget_store is first_widget_store

    async def test_get_async_lock_creates_lock(self) -> None:
        manager = ServerStateManager()
        assert manager._async_lock is None
        lock = await manager._get_async_lock()
        assert lock is manager._async_lock
        # Subsequent call returns same lock
        lock2 = await manager._get_async_lock()
        assert lock2 is lock

    def test_ensure_initialized_double_check_locking(self) -> None:
        """Test the inner _initialized check inside the lock acquisition."""
        manager = ServerStateManager()
        # Acquire the lock and set initialized=True before another caller
        # in a different thread enters _ensure_initialized
        from threading import Thread

        results: list[bool] = []

        def call_init() -> None:
            manager._ensure_initialized()
            results.append(manager._initialized)

        # Pre-acquire the lock to force the second thread to wait
        with manager._lock:
            t = Thread(target=call_init, daemon=True)
            t.start()
            # Wait briefly so thread reaches the lock acquisition
            import time

            time.sleep(0.05)
            # Set initialized while holding the lock
            manager._initialized = True
            manager._widget_store = MagicMock()
            manager._event_bus = MagicMock()
            manager._connection_router = MagicMock()
            manager._session_store = MagicMock()
            manager._callback_registry = MagicMock()
        t.join(timeout=2.0)
        # Second thread should have hit the inner check and returned
        assert results == [True]


class TestServerStateManagerDeployMode:
    """Tests for deploy mode using mocked stores."""

    @pytest.fixture
    def manager_deploy(self, monkeypatch: pytest.MonkeyPatch) -> ServerStateManager:
        """Manager forced into deploy mode with mocked stores."""
        monkeypatch.setenv("PYWRY_DEPLOY_MODE", "1")
        manager = ServerStateManager()

        # Mock all the stores
        manager._widget_store = AsyncMock()
        manager._event_bus = AsyncMock()
        manager._connection_router = AsyncMock()
        manager._session_store = AsyncMock()
        manager._callback_registry = AsyncMock()
        manager._initialized = True
        return manager

    async def test_register_widget_deploy(self, manager_deploy: ServerStateManager) -> None:
        await manager_deploy.register_widget(
            "w1", "<h1>x</h1>", token="tok", metadata={"theme": "dark"}
        )
        manager_deploy._widget_store.register.assert_awaited_once()
        call_kwargs = manager_deploy._widget_store.register.call_args.kwargs
        assert call_kwargs["widget_id"] == "w1"
        assert call_kwargs["html"] == "<h1>x</h1>"
        assert call_kwargs["token"] == "tok"
        assert call_kwargs["owner_worker_id"] == manager_deploy.worker_id
        assert call_kwargs["metadata"] == {"theme": "dark"}

    async def test_get_widget_deploy(self, manager_deploy: ServerStateManager) -> None:
        widget = WidgetData(widget_id="w1", html="<p>x</p>")
        manager_deploy._widget_store.get.return_value = widget

        result = await manager_deploy.get_widget("w1")
        assert result is widget

    async def test_get_widget_html_deploy(self, manager_deploy: ServerStateManager) -> None:
        manager_deploy._widget_store.get_html.return_value = "<h1>x</h1>"
        result = await manager_deploy.get_widget_html("w1")
        assert result == "<h1>x</h1>"

    async def test_update_widget_html_deploy(self, manager_deploy: ServerStateManager) -> None:
        manager_deploy._widget_store.update_html.return_value = True
        result = await manager_deploy.update_widget_html("w1", "<p>new</p>")
        assert result is True

    async def test_widget_exists_deploy(self, manager_deploy: ServerStateManager) -> None:
        manager_deploy._widget_store.exists.return_value = True
        result = await manager_deploy.widget_exists("w1")
        assert result is True

    async def test_remove_widget_deploy(self, manager_deploy: ServerStateManager) -> None:
        manager_deploy._widget_store.delete.return_value = True
        result = await manager_deploy.remove_widget("w1")
        assert result is True
        manager_deploy._callback_registry.unregister_widget.assert_awaited()

    async def test_list_widgets_deploy(self, manager_deploy: ServerStateManager) -> None:
        manager_deploy._widget_store.list_active.return_value = ["w1", "w2"]
        result = await manager_deploy.list_widgets()
        assert result == ["w1", "w2"]

    async def test_register_connection_deploy(self, manager_deploy: ServerStateManager) -> None:
        ws = MagicMock()
        await manager_deploy.register_connection("w1", ws)
        manager_deploy._connection_router.register_connection.assert_awaited()

    async def test_unregister_connection_deploy(self, manager_deploy: ServerStateManager) -> None:
        ws = MagicMock()
        await manager_deploy.register_connection("w1", ws)
        await manager_deploy.unregister_connection("w1")
        manager_deploy._connection_router.unregister_connection.assert_awaited()

    async def test_broadcast_event_deploy(self, manager_deploy: ServerStateManager) -> None:
        await manager_deploy.broadcast_event("w1", "click", {"x": 1})
        manager_deploy._event_bus.publish.assert_awaited_once()
        call = manager_deploy._event_bus.publish.call_args
        assert call.kwargs["channel"] == "widget:w1"
        event = call.kwargs["event"]
        assert isinstance(event, EventMessage)
        assert event.event_type == "click"

    async def test_send_to_widget_no_queue_deploy(self, manager_deploy: ServerStateManager) -> None:
        # No queue -> publish via event bus
        result = await manager_deploy.send_to_widget("w1", {"type": "msg", "data": "x"})
        assert result is True
        manager_deploy._event_bus.publish.assert_awaited_once()

    async def test_send_to_widget_with_queue_deploy(
        self, manager_deploy: ServerStateManager
    ) -> None:
        # Manually inject an event queue
        queue: asyncio.Queue = asyncio.Queue()
        manager_deploy._local_event_queues["w1"] = queue

        result = await manager_deploy.send_to_widget("w1", {"x": 1})
        assert result is True
        assert queue.qsize() == 1
        # Event bus should NOT be used
        manager_deploy._event_bus.publish.assert_not_awaited()


class TestServerStateSingleton:
    """Tests for the singleton accessor."""

    def test_get_server_state_returns_singleton(self) -> None:
        _StateHolder.instance = None
        s1 = get_server_state()
        s2 = get_server_state()
        assert s1 is s2

    def test_reset_server_state(self) -> None:
        s1 = get_server_state()
        reset_server_state()
        s2 = get_server_state()
        assert s1 is not s2
