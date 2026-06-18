"""Tests for Redis state store implementations.

Uses fakeredis to simulate Redis without requiring a real server.
"""

from __future__ import annotations

import asyncio
import builtins
import json
import time

from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio

from pywry.chat.models import ChatMessage, ChatThread
from pywry.state.types import EventMessage


# Check if fakeredis is available
try:
    import fakeredis.aioredis

    HAS_FAKEREDIS = True
except ImportError:
    HAS_FAKEREDIS = False


pytestmark = pytest.mark.skipif(
    not HAS_FAKEREDIS,
    reason="fakeredis not installed (pip install fakeredis)",
)


@pytest.fixture
def fake_redis() -> fakeredis.aioredis.FakeRedis:
    """Create a fresh fake Redis client for each test."""
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


# --- _check_redis ---


class TestCheckRedis:
    """Tests for the redis package availability check."""

    def test_raises_when_has_redis_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from pywry.state import redis as redis_module

        monkeypatch.setattr(redis_module, "HAS_REDIS", False)
        with pytest.raises(ImportError, match="Redis backend"):
            redis_module._check_redis()

    def test_returns_when_redis_available(self) -> None:
        from pywry.state.redis import _check_redis

        # Should not raise (redis is installed in the test env)
        _check_redis()


# --- Decode helpers ---


class TestDecodeHelpers:
    """Cover the _to_str and _decode_set utility branches."""

    def test_to_str_bytes_utf8(self):
        from pywry.state.redis import _to_str

        assert _to_str(b"hello") == "hello"

    def test_to_str_unicode_decode_error_returns_bytes(self):
        from pywry.state.redis import _to_str

        invalid = b"\xff\xfe\xfd"
        assert _to_str(invalid) == invalid

    def test_to_str_str_passthrough(self):
        from pywry.state.redis import _to_str

        assert _to_str("text") == "text"

    def test_to_str_int_passthrough(self):
        from pywry.state.redis import _to_str

        assert _to_str(42) == 42

    def test_decode_set_empty(self):
        from pywry.state.redis import _decode_set

        assert _decode_set(None) == set()
        assert _decode_set([]) == set()
        assert _decode_set(set()) == set()

    def test_decode_set_mixed(self):
        from pywry.state.redis import _decode_set

        assert _decode_set([b"a", b"b", "c"]) == {"a", "b", "c"}


# --- Behavior when redis package is missing ---


class TestNoRedisInstalled:
    """Test behavior when redis package is not installed."""

    def test_widget_store_init_raises_when_no_redis(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from pywry.state import redis as redis_module

        monkeypatch.setattr(redis_module, "HAS_REDIS", False)
        with pytest.raises(ImportError):
            redis_module.RedisWidgetStore()

    def test_event_bus_init_raises_when_no_redis(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from pywry.state import redis as redis_module

        monkeypatch.setattr(redis_module, "HAS_REDIS", False)
        with pytest.raises(ImportError):
            redis_module.RedisEventBus()

    def test_create_redis_stores_raises_when_no_redis(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from pywry.state import redis as redis_module

        monkeypatch.setattr(redis_module, "HAS_REDIS", False)
        with pytest.raises(ImportError):
            redis_module.create_redis_stores()

    def test_module_reload_with_no_redis(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Reload pywry.state.redis with redis.asyncio import patched to fail.

        Exercises the ``try / except ImportError`` block that defines
        HAS_REDIS and the RedisClient = None fallback.
        """
        import importlib
        import sys

        cached_keys = [k for k in list(sys.modules.keys()) if k.startswith("redis")]
        saved = {k: sys.modules[k] for k in cached_keys}

        try:
            for key in cached_keys:
                del sys.modules[key]

            real_import = builtins.__import__

            def fake_import(name, *args, **kwargs):
                if name == "redis.asyncio" or (
                    name == "redis" and args and "asyncio" in (args[2] or [])
                ):
                    raise ImportError("simulated missing redis")
                return real_import(name, *args, **kwargs)

            with patch.object(builtins, "__import__", side_effect=fake_import):
                if "pywry.state.redis" in sys.modules:
                    del sys.modules["pywry.state.redis"]
                import pywry.state.redis as fresh

                assert fresh.HAS_REDIS is False
                assert fresh.RedisClient is None
        finally:
            for k, v in saved.items():
                sys.modules[k] = v
            if "pywry.state.redis" in sys.modules:
                del sys.modules["pywry.state.redis"]
            importlib.import_module("pywry.state.redis")


# --- RedisWidgetStore Tests ---


class TestRedisWidgetStore:
    """Tests for RedisWidgetStore."""

    @pytest_asyncio.fixture
    async def store(self, fake_redis: fakeredis.aioredis.FakeRedis):
        from pywry.state.redis import RedisWidgetStore

        return RedisWidgetStore(redis_client=fake_redis, prefix="test:")

    async def test_register_and_get(self, store) -> None:
        await store.register(
            widget_id="widget-1",
            html="<h1>Hello</h1>",
            token="secret-token",
            owner_worker_id="worker-1",
            metadata={"title": "Test Widget"},
        )

        widget = await store.get("widget-1")
        assert widget is not None
        assert widget.widget_id == "widget-1"
        assert widget.html == "<h1>Hello</h1>"
        assert widget.token == "secret-token"
        assert widget.owner_worker_id == "worker-1"
        assert widget.metadata == {"title": "Test Widget"}
        assert widget.created_at > 0

    async def test_get_nonexistent(self, store) -> None:
        assert await store.get("nonexistent") is None

    async def test_get_html(self, store) -> None:
        await store.register("widget-1", "<p>Content</p>")
        assert await store.get_html("widget-1") == "<p>Content</p>"

    async def test_get_token(self, store) -> None:
        await store.register("widget-1", "<p>Content</p>", token="my-token")
        assert await store.get_token("widget-1") == "my-token"

    async def test_exists(self, store) -> None:
        assert not await store.exists("widget-1")
        await store.register("widget-1", "<p>Content</p>")
        assert await store.exists("widget-1")

    async def test_delete(self, store) -> None:
        await store.register("widget-1", "<p>Content</p>")
        assert await store.exists("widget-1")

        assert await store.delete("widget-1") is True
        assert not await store.exists("widget-1")

        # Delete nonexistent should return False
        assert await store.delete("widget-1") is False

    async def test_list_active(self, store) -> None:
        await store.register("widget-1", "<p>1</p>")
        await store.register("widget-2", "<p>2</p>")
        await store.register("widget-3", "<p>3</p>")

        active = await store.list_active()
        assert set(active) == {"widget-1", "widget-2", "widget-3"}

    async def test_update_html(self, store) -> None:
        await store.register("widget-1", "<p>Original</p>")

        assert await store.update_html("widget-1", "<p>Updated</p>") is True
        assert await store.get_html("widget-1") == "<p>Updated</p>"

        # Update nonexistent should return False
        assert await store.update_html("nonexistent", "<p>New</p>") is False

    async def test_update_token(self, store) -> None:
        await store.register("w1", "<p>x</p>", token="old")
        assert await store.update_token("w1", "new") is True
        assert await store.get_token("w1") == "new"

    async def test_update_token_missing(self, store) -> None:
        assert await store.update_token("missing", "tok") is False

    async def test_count(self, store) -> None:
        assert await store.count() == 0

        await store.register("widget-1", "<p>1</p>")
        assert await store.count() == 1

        await store.register("widget-2", "<p>2</p>")
        assert await store.count() == 2

        await store.delete("widget-1")
        assert await store.count() == 1

    async def test_get_with_corrupt_metadata(self, store, fake_redis) -> None:
        """Corrupt JSON metadata is suppressed, returning empty dict."""
        await store.register("w1", "<p>x</p>", metadata={"a": 1})
        await fake_redis.hset(store._widget_key("w1"), "metadata", "not valid json")

        widget = await store.get("w1")
        assert widget is not None
        assert widget.metadata == {}

    async def test_close_is_noop(self, store) -> None:
        await store.close()

    async def test_redis_uses_url_when_no_client(self) -> None:
        """When no client is provided, _redis() uses RedisClient.from_url."""
        from pywry.state.redis import RedisWidgetStore

        with patch("pywry.state.redis.RedisClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.from_url.return_value = mock_client
            store = RedisWidgetStore(redis_url="redis://test:1234/0", prefix="x")
            r = await store._redis()
            assert r is mock_client
            mock_client_cls.from_url.assert_called_with(
                "redis://test:1234/0", decode_responses=True
            )


# --- RedisEventBus Tests ---


class TestRedisEventBus:
    """Tests for RedisEventBus, including publish/subscribe end-to-end."""

    @pytest_asyncio.fixture
    async def bus(self, fake_redis: fakeredis.aioredis.FakeRedis):
        from pywry.state.redis import RedisEventBus

        return RedisEventBus(redis_client=fake_redis, prefix="test:")

    async def test_publish_does_not_raise(self, bus) -> None:
        await bus.publish(
            "test-channel",
            EventMessage(
                event_type="click",
                widget_id="widget-1",
                data={"x": 100},
                source_worker_id="worker-1",
            ),
        )

    async def test_publish_and_subscribe(self, bus) -> None:
        """Subscriber receives a published event end-to-end."""
        received: list[EventMessage] = []

        async def consumer() -> None:
            async for event in bus.subscribe("ch1"):
                received.append(event)
                if len(received) >= 1:
                    break

        task = asyncio.create_task(consumer())
        await asyncio.sleep(0.1)

        await bus.publish(
            "ch1",
            EventMessage(
                event_type="click",
                widget_id="w1",
                data={"x": 100},
                source_worker_id="src",
            ),
        )

        try:
            await asyncio.wait_for(task, timeout=2.0)
        except asyncio.TimeoutError:
            task.cancel()
            pytest.fail("did not receive event")

        assert len(received) == 1
        assert received[0].event_type == "click"

    async def test_subscribe_suppresses_decode_errors(self, bus, fake_redis) -> None:
        """Invalid JSON messages are silently skipped; subsequent valid ones are delivered."""
        received: list[EventMessage] = []

        async def consumer() -> None:
            async for event in bus.subscribe("ch"):
                received.append(event)
                if len(received) >= 1:
                    break

        task = asyncio.create_task(consumer())
        await asyncio.sleep(0.1)

        # Publish invalid JSON, then a valid event
        await fake_redis.publish(bus._channel_name("ch"), "not-json")
        await asyncio.sleep(0.05)
        await bus.publish(
            "ch",
            EventMessage(event_type="x", widget_id="w", data={}, source_worker_id="s"),
        )

        try:
            await asyncio.wait_for(task, timeout=2.0)
        except asyncio.TimeoutError:
            task.cancel()
            pytest.fail("did not receive event")

        assert len(received) == 1

    async def test_subscribe_event_with_minimal_fields(self, bus, fake_redis) -> None:
        """Deserialization uses defaults for missing fields."""
        received: list[EventMessage] = []

        async def consumer() -> None:
            async for event in bus.subscribe("ch"):
                received.append(event)
                if len(received) >= 1:
                    break

        task = asyncio.create_task(consumer())
        await asyncio.sleep(0.1)

        await fake_redis.publish(
            bus._channel_name("ch"),
            json.dumps({"event_type": "minimal"}),
        )

        try:
            await asyncio.wait_for(task, timeout=2.0)
        except asyncio.TimeoutError:
            task.cancel()
            pytest.fail("did not receive event")

        assert received[0].event_type == "minimal"
        assert received[0].widget_id == ""

    async def test_unsubscribe_noop(self, bus) -> None:
        await bus.unsubscribe("ch")

    async def test_close_noop(self, bus) -> None:
        await bus.close()

    async def test_redis_uses_url_when_no_client(self) -> None:
        from pywry.state.redis import RedisEventBus

        with patch("pywry.state.redis.RedisClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.from_url.return_value = mock_client
            bus = RedisEventBus(redis_url="redis://test:1234/0")
            assert await bus._redis() is mock_client


# --- RedisConnectionRouter Tests ---


class TestRedisConnectionRouter:
    """Tests for RedisConnectionRouter."""

    @pytest_asyncio.fixture
    async def router(self, fake_redis: fakeredis.aioredis.FakeRedis):
        from pywry.state.redis import RedisConnectionRouter

        return RedisConnectionRouter(redis_client=fake_redis, prefix="test:")

    async def test_register_connection(self, router) -> None:
        await router.register_connection(
            widget_id="widget-1",
            worker_id="worker-1",
            user_id="user-1",
            session_id="session-1",
        )

        info = await router.get_connection_info("widget-1")
        assert info is not None
        assert info.widget_id == "widget-1"
        assert info.worker_id == "worker-1"
        assert info.user_id == "user-1"
        assert info.session_id == "session-1"
        assert info.connected_at > 0

    async def test_get_owner(self, router) -> None:
        await router.register_connection("widget-1", "worker-1")
        assert await router.get_owner("widget-1") == "worker-1"
        assert await router.get_owner("nonexistent") is None

    async def test_refresh_heartbeat(self, router) -> None:
        await router.register_connection("widget-1", "worker-1")

        info_before = await router.get_connection_info("widget-1")
        assert info_before is not None
        old_heartbeat = info_before.last_heartbeat

        await asyncio.sleep(0.05)
        assert await router.refresh_heartbeat("widget-1") is True

        info_after = await router.get_connection_info("widget-1")
        assert info_after is not None
        assert info_after.last_heartbeat > old_heartbeat

    async def test_refresh_heartbeat_missing(self, router) -> None:
        assert await router.refresh_heartbeat("missing") is False

    async def test_unregister_connection(self, router) -> None:
        await router.register_connection("widget-1", "worker-1")
        assert await router.get_connection_info("widget-1") is not None

        assert await router.unregister_connection("widget-1") is True
        assert await router.get_connection_info("widget-1") is None

        # Unregister nonexistent
        assert await router.unregister_connection("widget-1") is False

    async def test_list_worker_connections(self, router) -> None:
        await router.register_connection("widget-1", "worker-1")
        await router.register_connection("widget-2", "worker-1")
        await router.register_connection("widget-3", "worker-2")

        worker1_connections = await router.list_worker_connections("worker-1")
        assert set(worker1_connections) == {"widget-1", "widget-2"}

        worker2_connections = await router.list_worker_connections("worker-2")
        assert worker2_connections == ["widget-3"]

    async def test_close_noop(self, router) -> None:
        await router.close()

    async def test_redis_uses_url_when_no_client(self) -> None:
        from pywry.state.redis import RedisConnectionRouter

        with patch("pywry.state.redis.RedisClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.from_url.return_value = mock_client
            router = RedisConnectionRouter(redis_url="redis://test:1234/0")
            assert await router._redis() is mock_client


# --- RedisSessionStore Tests ---


class TestRedisSessionStore:
    """Tests for RedisSessionStore."""

    @pytest_asyncio.fixture
    async def store(self, fake_redis: fakeredis.aioredis.FakeRedis):
        from pywry.state.redis import RedisSessionStore

        return RedisSessionStore(redis_client=fake_redis, prefix="test:")

    async def test_create_session(self, store) -> None:
        session = await store.create_session(
            session_id="session-1",
            user_id="user-1",
            roles=["admin", "editor"],
            metadata={"name": "Test User"},
        )

        assert session.session_id == "session-1"
        assert session.user_id == "user-1"
        assert session.roles == ["admin", "editor"]
        assert session.metadata == {"name": "Test User"}
        assert session.created_at > 0

    async def test_get_session(self, store) -> None:
        await store.create_session("session-1", "user-1", roles=["viewer"])

        session = await store.get_session("session-1")
        assert session is not None
        assert session.user_id == "user-1"

        assert await store.get_session("nonexistent") is None

    async def test_get_session_corrupt_roles(self, store, fake_redis) -> None:
        """Corrupt JSON roles is suppressed, returning empty list."""
        await store.create_session("s1", "u1", roles=["admin"])
        await fake_redis.hset(store._session_key("s1"), "roles", "not json")

        session = await store.get_session("s1")
        assert session is not None
        assert session.roles == []

    async def test_get_session_corrupt_metadata(self, store, fake_redis) -> None:
        await store.create_session("s1", "u1", metadata={"x": 1})
        await fake_redis.hset(store._session_key("s1"), "metadata", "bogus")

        session = await store.get_session("s1")
        assert session is not None
        assert session.metadata == {}

    async def test_get_session_python_side_expired(self, store, fake_redis) -> None:
        """Python-side expiry check catches keys that Redis hasn't expired yet."""
        await store.create_session("s1", "u1", ttl=600)
        await fake_redis.hset(store._session_key("s1"), "expires_at", str(time.time() - 100))

        assert await store.get_session("s1") is None

    async def test_validate_session(self, store) -> None:
        await store.create_session("session-1", "user-1")
        assert await store.validate_session("session-1") is True
        assert await store.validate_session("nonexistent") is False

    async def test_refresh_session(self, store) -> None:
        await store.create_session("session-1", "user-1")

        session_before = await store.get_session("session-1")
        assert session_before is not None
        old_expires = session_before.expires_at

        await asyncio.sleep(0.05)
        assert await store.refresh_session("session-1") is True

        session_after = await store.get_session("session-1")
        assert session_after is not None
        assert session_after.expires_at >= old_expires

    async def test_refresh_session_missing(self, store) -> None:
        assert await store.refresh_session("missing") is False

    async def test_refresh_session_with_extend_ttl(self, store) -> None:
        await store.create_session("s1", "u1", ttl=10)
        assert await store.refresh_session("s1", extend_ttl=600) is True

    async def test_refresh_session_no_extend_uses_stored_ttl(self, store) -> None:
        await store.create_session("s1", "u1", ttl=300)
        assert await store.refresh_session("s1") is True

    async def test_delete_session(self, store) -> None:
        await store.create_session("session-1", "user-1")
        assert await store.validate_session("session-1") is True
        assert await store.delete_session("session-1") is True
        assert await store.validate_session("session-1") is False

    async def test_delete_session_missing(self, store) -> None:
        assert await store.delete_session("missing") is False

    async def test_list_user_sessions(self, store) -> None:
        await store.create_session("session-1", "user-1")
        await store.create_session("session-2", "user-1")
        await store.create_session("session-3", "user-2")

        user1_sessions = await store.list_user_sessions("user-1")
        assert len(user1_sessions) == 2
        assert {s.session_id for s in user1_sessions} == {"session-1", "session-2"}

    async def test_list_user_sessions_cleans_stale_refs(self, store, fake_redis) -> None:
        """Stale references to deleted sessions are removed from the user index."""
        await store.create_session("s1", "u1", ttl=600)
        await fake_redis.sadd(store._user_sessions_key("u1"), "ghost")

        sessions = await store.list_user_sessions("u1")
        assert len(sessions) == 1
        members = await fake_redis.smembers(store._user_sessions_key("u1"))
        assert "ghost" not in members

    async def test_check_permission(self, store) -> None:
        await store.set_role_permissions("admin", {"read", "write", "delete"})
        await store.set_role_permissions("viewer", {"read"})

        await store.create_session("admin-session", "admin-user", roles=["admin"])
        await store.create_session("viewer-session", "viewer-user", roles=["viewer"])

        assert await store.check_permission("admin-session", "widget", "1", "read")
        assert await store.check_permission("admin-session", "widget", "1", "write")
        assert await store.check_permission("admin-session", "widget", "1", "delete")

        assert await store.check_permission("viewer-session", "widget", "1", "read")
        assert not await store.check_permission("viewer-session", "widget", "1", "write")
        assert not await store.check_permission("viewer-session", "widget", "1", "delete")

    async def test_check_permission_session_missing(self, store) -> None:
        assert await store.check_permission("missing", "widget", "w1", "read") is False

    async def test_check_permission_role_perms_corrupt(self, store, fake_redis) -> None:
        """Corrupt JSON role permissions are silently skipped."""
        await store.create_session("s1", "u1", roles=["bad-role"])
        await fake_redis.hset(store._role_perms_key, "bad-role", "not json")

        assert await store.check_permission("s1", "widget", "w1", "read") is False

    async def test_check_permission_resource_specific(self, store) -> None:
        """Resource-specific permission via session metadata grants access."""
        metadata = {"permissions": {"widget:w1": ["read"]}}
        await store.create_session("s1", "u1", roles=["unknown"], metadata=metadata)

        assert await store.check_permission("s1", "widget", "w1", "read") is True
        assert await store.check_permission("s1", "widget", "w1", "write") is False

    async def test_set_role_permissions_with_set(self, store, fake_redis) -> None:
        """Set input is converted to list for JSON serialization."""
        await store.set_role_permissions("custom", {"a", "b", "c"})
        raw = await fake_redis.hget(store._role_perms_key, "custom")
        perms = json.loads(raw)
        assert set(perms) == {"a", "b", "c"}

    async def test_set_role_permissions_with_list(self, store, fake_redis) -> None:
        await store.set_role_permissions("custom", ["a", "b"])
        raw = await fake_redis.hget(store._role_perms_key, "custom")
        assert json.loads(raw) == ["a", "b"]

    async def test_close_noop(self, store) -> None:
        await store.close()

    async def test_redis_uses_url_when_no_client(self) -> None:
        from pywry.state.redis import RedisSessionStore

        with patch("pywry.state.redis.RedisClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.from_url.return_value = mock_client
            store = RedisSessionStore(redis_url="redis://test:1234/0")
            assert await store._redis() is mock_client


# --- RedisChatStore Tests ---


class TestRedisChatStore:
    """Tests for RedisChatStore."""

    @pytest_asyncio.fixture
    async def store(self, fake_redis: fakeredis.aioredis.FakeRedis):
        from pywry.state.redis import RedisChatStore

        return RedisChatStore(redis_client=fake_redis, prefix="t")

    async def test_save_and_get_thread(self, store) -> None:
        thread = ChatThread(thread_id="t1", title="Test", metadata={"x": 1})
        await store.save_thread("w1", thread)

        result = await store.get_thread("w1", "t1")
        assert result is not None
        assert result.title == "Test"
        assert result.metadata == {"x": 1}

    async def test_get_thread_missing(self, store) -> None:
        assert await store.get_thread("w1", "missing") is None

    async def test_get_thread_corrupt_metadata(self, store, fake_redis) -> None:
        thread = ChatThread(thread_id="t1", title="Test", metadata={"x": 1})
        await store.save_thread("w1", thread)
        await fake_redis.hset(store._thread_key("w1", "t1"), "metadata", "not json")

        result = await store.get_thread("w1", "t1")
        assert result is not None
        assert result.metadata == {}

    async def test_list_threads(self, store) -> None:
        await store.save_thread("w1", ChatThread(thread_id="t1", title="A"))
        await store.save_thread("w1", ChatThread(thread_id="t2", title="B"))
        assert len(await store.list_threads("w1")) == 2

    async def test_list_threads_empty(self, store) -> None:
        assert await store.list_threads("ghost") == []

    async def test_delete_thread(self, store) -> None:
        await store.save_thread("w1", ChatThread(thread_id="t1", title="A"))
        await store.append_message("w1", "t1", ChatMessage(role="user", content="hi"))
        assert await store.delete_thread("w1", "t1") is True
        assert await store.get_thread("w1", "t1") is None

    async def test_delete_thread_missing(self, store) -> None:
        assert await store.delete_thread("w1", "missing") is False

    async def test_append_message(self, store) -> None:
        await store.save_thread("w1", ChatThread(thread_id="t1", title="A"))
        await store.append_message(
            "w1", "t1", ChatMessage(role="user", content="hello", message_id="m1")
        )

        messages = await store.get_messages("w1", "t1")
        assert len(messages) == 1
        assert messages[0].text_content() == "hello"

    async def test_append_message_trims_to_max(self, store) -> None:
        """Messages list is trimmed to MAX_MESSAGES_PER_THREAD."""
        await store.save_thread("w1", ChatThread(thread_id="t1", title="A"))

        with patch("pywry.chat.MAX_MESSAGES_PER_THREAD", 3):
            for i in range(10):
                await store.append_message(
                    "w1",
                    "t1",
                    ChatMessage(role="user", content=f"msg{i}", message_id=f"m{i}"),
                )

            assert len(await store.get_messages("w1", "t1")) == 3

    async def test_get_messages_empty(self, store) -> None:
        assert await store.get_messages("w1", "t1") == []

    async def test_get_messages_with_corrupt_data(self, store, fake_redis) -> None:
        """A corrupt message in the list is skipped silently."""
        await store.save_thread("w1", ChatThread(thread_id="t1", title="A"))
        await store.append_message("w1", "t1", ChatMessage(role="user", content="ok"))
        await fake_redis.rpush(store._messages_key("w1", "t1"), "not-valid-json")

        messages = await store.get_messages("w1", "t1")
        assert len(messages) == 1

    async def test_get_messages_before_id(self, store) -> None:
        await store.save_thread("w1", ChatThread(thread_id="t1", title="A"))
        for i in range(5):
            await store.append_message(
                "w1",
                "t1",
                ChatMessage(role="user", content=f"msg{i}", message_id=f"m{i}"),
            )

        messages = await store.get_messages("w1", "t1", before_id="m3")
        ids = {m.message_id for m in messages}
        assert "m3" not in ids
        assert "m4" not in ids

    async def test_get_messages_before_id_not_found(self, store) -> None:
        """When before_id doesn't match, all messages are returned."""
        await store.save_thread("w1", ChatThread(thread_id="t1", title="A"))
        await store.append_message(
            "w1", "t1", ChatMessage(role="user", content="hi", message_id="m1")
        )
        messages = await store.get_messages("w1", "t1", before_id="ghost")
        assert len(messages) == 1

    async def test_get_messages_with_limit(self, store) -> None:
        await store.save_thread("w1", ChatThread(thread_id="t1", title="A"))
        for i in range(10):
            await store.append_message(
                "w1",
                "t1",
                ChatMessage(role="user", content=f"msg{i}", message_id=f"m{i}"),
            )

        assert len(await store.get_messages("w1", "t1", limit=3)) == 3

    async def test_clear_messages(self, store) -> None:
        await store.save_thread("w1", ChatThread(thread_id="t1", title="A"))
        await store.append_message("w1", "t1", ChatMessage(role="user", content="hi"))
        await store.clear_messages("w1", "t1")
        assert await store.get_messages("w1", "t1") == []

    async def test_close_noop(self, store) -> None:
        await store.close()

    async def test_redis_uses_url_when_no_client(self) -> None:
        from pywry.state.redis import RedisChatStore

        with patch("pywry.state.redis.RedisClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.from_url.return_value = mock_client
            store = RedisChatStore(redis_url="redis://test:1234/0")
            assert await store._redis() is mock_client


# --- RedisChartStore Tests ---


class TestRedisChartStore:
    """Tests for RedisChartStore."""

    @pytest_asyncio.fixture
    async def store(self, fake_redis: fakeredis.aioredis.FakeRedis):
        from pywry.state.redis import RedisChartStore

        return RedisChartStore(redis_client=fake_redis, prefix="t")

    async def test_save_and_get_layout(self, store) -> None:
        entry = await store.save_layout(
            user_id="u1",
            layout_id="l1",
            name="Layout 1",
            data_json='{"x": 1}',
            summary="A summary",
        )
        assert entry["id"] == "l1"
        assert entry["name"] == "Layout 1"
        assert entry["summary"] == "A summary"
        assert await store.get_layout("u1", "l1") == '{"x": 1}'

    async def test_get_layout_missing(self, store) -> None:
        assert await store.get_layout("u1", "missing") is None

    async def test_list_layouts_empty(self, store) -> None:
        assert await store.list_layouts("u1") == []

    async def test_list_layouts_returns_newest_first(self, store) -> None:
        await store.save_layout("u1", "l1", "First", "{}")
        await store.save_layout("u1", "l2", "Second", "{}")
        layouts = await store.list_layouts("u1")
        assert layouts[0]["id"] == "l2"
        assert layouts[1]["id"] == "l1"

    async def test_list_layouts_orphan_id_uses_score(self, store, fake_redis) -> None:
        """An ID in the index without metadata falls back to score-derived entry."""
        await fake_redis.zadd(store._index_key("u1"), {"orphan-id": 1234567})
        layouts = await store.list_layouts("u1")
        orphan = next(layout for layout in layouts if layout["id"] == "orphan-id")
        assert orphan["name"] == "orphan-id"
        assert orphan["savedAt"] == 1234567

    async def test_delete_layout(self, store) -> None:
        await store.save_layout("u1", "l1", "L1", "{}")
        assert await store.delete_layout("u1", "l1") is True
        assert await store.get_layout("u1", "l1") is None

    async def test_delete_layout_missing(self, store) -> None:
        assert await store.delete_layout("u1", "missing") is False

    async def test_rename_layout(self, store) -> None:
        await store.save_layout("u1", "l1", "Old", "{}")
        assert await store.rename_layout("u1", "l1", "New") is True

        layouts = await store.list_layouts("u1")
        assert layouts[0]["name"] == "New"

    async def test_rename_layout_missing(self, store) -> None:
        assert await store.rename_layout("u1", "missing", "X") is False

    async def test_update_layout_meta(self, store) -> None:
        await store.save_layout("u1", "l1", "Old", "{}", summary="orig")
        assert await store.update_layout_meta("u1", "l1", name="New", summary="new sum") is True

        layouts = await store.list_layouts("u1")
        assert layouts[0]["name"] == "New"
        assert layouts[0]["summary"] == "new sum"

    async def test_update_layout_meta_missing(self, store) -> None:
        assert await store.update_layout_meta("u1", "missing", name="X") is False

    async def test_update_layout_meta_no_changes(self, store) -> None:
        """Calling update with empty name and summary still returns True (no-op)."""
        await store.save_layout("u1", "l1", "L1", "{}")
        assert await store.update_layout_meta("u1", "l1") is True

    async def test_settings_template_roundtrip(self, store) -> None:
        await store.save_settings_template("u1", '{"tpl": 1}')
        assert await store.get_settings_template("u1") == '{"tpl": 1}'

    async def test_get_settings_template_missing(self, store) -> None:
        assert await store.get_settings_template("u1") is None

    async def test_get_settings_default_id_default(self, store) -> None:
        assert await store.get_settings_default_id("u1") == "factory"

    async def test_set_settings_default_id_valid(self, store) -> None:
        await store.set_settings_default_id("u1", "custom")
        assert await store.get_settings_default_id("u1") == "custom"

    async def test_set_settings_default_id_invalid_falls_back(self, store) -> None:
        await store.set_settings_default_id("u1", "bogus")
        assert await store.get_settings_default_id("u1") == "factory"

    async def test_clear_settings_template(self, store) -> None:
        await store.save_settings_template("u1", "{}")
        await store.set_settings_default_id("u1", "custom")
        await store.clear_settings_template("u1")
        assert await store.get_settings_template("u1") is None
        assert await store.get_settings_default_id("u1") == "factory"

    async def test_close_noop(self, store) -> None:
        await store.close()

    async def test_redis_uses_url_when_no_client(self) -> None:
        from pywry.state.redis import RedisChartStore

        with patch("pywry.state.redis.RedisClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.from_url.return_value = mock_client
            store = RedisChartStore(redis_url="redis://test:1234/0")
            assert await store._redis() is mock_client


# --- create_redis_stores factory ---


class TestCreateRedisStores:
    """Tests for the create_redis_stores factory function."""

    def test_returns_all_stores(self) -> None:
        from pywry.state.redis import (
            RedisConnectionRouter,
            RedisEventBus,
            RedisSessionStore,
            RedisWidgetStore,
            create_redis_stores,
        )

        widget, bus, router, sessions = create_redis_stores(
            redis_url="redis://localhost:1234/0",
            prefix="custom",
            widget_ttl=100,
            connection_ttl=50,
            session_ttl=200,
            pool_size=5,
        )
        assert isinstance(widget, RedisWidgetStore)
        assert isinstance(bus, RedisEventBus)
        assert isinstance(router, RedisConnectionRouter)
        assert isinstance(sessions, RedisSessionStore)

    def test_propagates_settings(self) -> None:
        from pywry.state.redis import create_redis_stores

        widget, _bus, router, sessions = create_redis_stores(
            redis_url="redis://example:1234/0",
            prefix="myapp",
            widget_ttl=999,
            connection_ttl=11,
            session_ttl=333,
            pool_size=7,
        )
        assert widget._redis_url == "redis://example:1234/0"
        assert widget._prefix == "myapp"
        assert widget._widget_ttl == 999
        assert router._connection_ttl == 11
        assert sessions._default_ttl == 333
