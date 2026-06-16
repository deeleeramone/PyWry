"""Tests for in-memory state store implementations."""

from __future__ import annotations

import asyncio
import time

from unittest.mock import patch

import pytest

from pywry.chat.models import ChatMessage, ChatThread
from pywry.state.memory import (
    MemoryChartStore,
    MemoryChatStore,
    MemoryConnectionRouter,
    MemoryEventBus,
    MemorySessionStore,
    MemoryWidgetStore,
    create_memory_stores,
)
from pywry.state.types import EventMessage


# --- MemoryWidgetStore Tests ---


class TestMemoryWidgetStore:
    """Tests for MemoryWidgetStore."""

    @pytest.fixture
    def store(self) -> MemoryWidgetStore:
        return MemoryWidgetStore()

    async def test_register_and_get(self, store: MemoryWidgetStore) -> None:
        await store.register(
            widget_id="test-widget-1",
            html="<h1>Hello</h1>",
            token="secret-token",
            owner_worker_id="worker-1",
            metadata={"title": "Test Widget"},
        )

        widget = await store.get("test-widget-1")
        assert widget is not None
        assert widget.widget_id == "test-widget-1"
        assert widget.html == "<h1>Hello</h1>"
        assert widget.token == "secret-token"
        assert widget.owner_worker_id == "worker-1"
        assert widget.metadata == {"title": "Test Widget"}
        assert widget.created_at > 0

    async def test_get_nonexistent(self, store: MemoryWidgetStore) -> None:
        assert await store.get("nonexistent") is None

    async def test_get_html(self, store: MemoryWidgetStore) -> None:
        await store.register("widget-1", "<p>Content</p>")
        assert await store.get_html("widget-1") == "<p>Content</p>"

    async def test_get_html_missing(self, store: MemoryWidgetStore) -> None:
        assert await store.get_html("missing") is None

    async def test_get_token(self, store: MemoryWidgetStore) -> None:
        await store.register("widget-1", "<p>Content</p>", token="my-token")
        assert await store.get_token("widget-1") == "my-token"

    async def test_get_token_missing(self, store: MemoryWidgetStore) -> None:
        assert await store.get_token("missing") is None

    async def test_exists(self, store: MemoryWidgetStore) -> None:
        assert not await store.exists("widget-1")
        await store.register("widget-1", "<p>Content</p>")
        assert await store.exists("widget-1")

    async def test_delete(self, store: MemoryWidgetStore) -> None:
        await store.register("widget-1", "<p>Content</p>")
        assert await store.exists("widget-1")

        assert await store.delete("widget-1") is True
        assert not await store.exists("widget-1")

        # Delete nonexistent should return False
        assert await store.delete("widget-1") is False

    async def test_list_active(self, store: MemoryWidgetStore) -> None:
        await store.register("widget-1", "<p>1</p>")
        await store.register("widget-2", "<p>2</p>")
        await store.register("widget-3", "<p>3</p>")

        active = await store.list_active()
        assert set(active) == {"widget-1", "widget-2", "widget-3"}

    async def test_update_html(self, store: MemoryWidgetStore) -> None:
        await store.register("widget-1", "<p>Original</p>")

        assert await store.update_html("widget-1", "<p>Updated</p>") is True
        assert await store.get_html("widget-1") == "<p>Updated</p>"

        # Update nonexistent should return False
        assert await store.update_html("nonexistent", "<p>New</p>") is False

    async def test_update_token(self, store: MemoryWidgetStore) -> None:
        await store.register("w1", "<p>x</p>", token="old")
        assert await store.update_token("w1", "new") is True
        assert await store.get_token("w1") == "new"

    async def test_update_token_missing(self, store: MemoryWidgetStore) -> None:
        assert await store.update_token("missing", "tok") is False

    async def test_count(self, store: MemoryWidgetStore) -> None:
        assert await store.count() == 0

        await store.register("widget-1", "<p>1</p>")
        assert await store.count() == 1

        await store.register("widget-2", "<p>2</p>")
        assert await store.count() == 2

        await store.delete("widget-1")
        assert await store.count() == 1


# --- MemoryEventBus Tests ---


class TestMemoryEventBus:
    """Tests for MemoryEventBus."""

    @pytest.fixture
    def bus(self) -> MemoryEventBus:
        return MemoryEventBus()

    async def test_publish_subscribe(self, bus: MemoryEventBus) -> None:
        """Subscriber receives published events in order."""
        received_events: list[EventMessage] = []

        async def subscriber() -> None:
            async for event in bus.subscribe("test-channel"):
                received_events.append(event)
                if len(received_events) >= 2:
                    break

        task = asyncio.create_task(subscriber())
        await asyncio.sleep(0.05)

        event1 = EventMessage(
            event_type="click",
            widget_id="widget-1",
            data={"x": 100},
            source_worker_id="worker-1",
        )
        event2 = EventMessage(
            event_type="change",
            widget_id="widget-1",
            data={"value": "test"},
            source_worker_id="worker-1",
        )

        await bus.publish("test-channel", event1)
        await bus.publish("test-channel", event2)

        await asyncio.wait_for(task, timeout=1.0)

        assert len(received_events) == 2
        assert received_events[0].event_type == "click"
        assert received_events[1].event_type == "change"

    async def test_unsubscribe(self, bus: MemoryEventBus) -> None:
        """Unsubscribe removes the channel."""
        bus.subscribe("test-channel")  # registers iterator (lazy)
        await bus.unsubscribe("test-channel")
        assert "test-channel" not in bus._channels

    async def test_publish_full_queue_drops_event(self, bus: MemoryEventBus) -> None:
        """Publish silently drops events when a subscriber queue is full."""
        full_queue: asyncio.Queue[EventMessage] = asyncio.Queue(maxsize=1)
        full_queue.put_nowait(
            EventMessage(event_type="filler", widget_id="w", data={}, source_worker_id="s")
        )

        async with bus._lock:
            bus._channels["ch"] = [full_queue]

        # Must not raise even though queue is full
        await bus.publish(
            "ch",
            EventMessage(event_type="x", widget_id="w", data={}, source_worker_id="s"),
        )
        # Filler is still there; new event was dropped
        assert full_queue.qsize() == 1

    async def test_subscribe_cleans_up_channel_on_break(self, bus: MemoryEventBus) -> None:
        """When the subscriber generator exits, its queue is removed."""

        async def consumer() -> None:
            async for _event in bus.subscribe("cleanup-test"):
                break

        consumer_task = asyncio.create_task(consumer())
        await asyncio.sleep(0.05)
        await bus.publish(
            "cleanup-test",
            EventMessage(event_type="x", widget_id="w", data={}, source_worker_id="s"),
        )
        await asyncio.wait_for(consumer_task, timeout=1.0)

        await asyncio.sleep(0.05)
        assert (
            "cleanup-test" not in bus._channels
            or len(bus._channels["cleanup-test"]) == 0
        )


# --- MemoryConnectionRouter Tests ---


class TestMemoryConnectionRouter:
    """Tests for MemoryConnectionRouter."""

    @pytest.fixture
    def router(self) -> MemoryConnectionRouter:
        return MemoryConnectionRouter()

    async def test_register_connection(self, router: MemoryConnectionRouter) -> None:
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

    async def test_get_connection_info_missing(self, router: MemoryConnectionRouter) -> None:
        assert await router.get_connection_info("missing") is None

    async def test_get_owner(self, router: MemoryConnectionRouter) -> None:
        await router.register_connection("widget-1", "worker-1")
        assert await router.get_owner("widget-1") == "worker-1"
        assert await router.get_owner("nonexistent") is None

    async def test_refresh_heartbeat(self, router: MemoryConnectionRouter) -> None:
        await router.register_connection("widget-1", "worker-1")

        info_before = await router.get_connection_info("widget-1")
        assert info_before is not None
        old_heartbeat = info_before.last_heartbeat

        # 50ms ensures Windows timer resolution distinguishes the two timestamps
        await asyncio.sleep(0.05)

        assert await router.refresh_heartbeat("widget-1") is True

        info_after = await router.get_connection_info("widget-1")
        assert info_after is not None
        assert info_after.last_heartbeat > old_heartbeat

    async def test_refresh_heartbeat_missing(self, router: MemoryConnectionRouter) -> None:
        assert await router.refresh_heartbeat("missing") is False

    async def test_unregister_connection(self, router: MemoryConnectionRouter) -> None:
        await router.register_connection("widget-1", "worker-1")
        assert await router.get_connection_info("widget-1") is not None

        assert await router.unregister_connection("widget-1") is True
        assert await router.get_connection_info("widget-1") is None

        # Unregister nonexistent
        assert await router.unregister_connection("widget-1") is False

    async def test_list_worker_connections(self, router: MemoryConnectionRouter) -> None:
        await router.register_connection("widget-1", "worker-1")
        await router.register_connection("widget-2", "worker-1")
        await router.register_connection("widget-3", "worker-2")

        worker1_connections = await router.list_worker_connections("worker-1")
        assert set(worker1_connections) == {"widget-1", "widget-2"}

        worker2_connections = await router.list_worker_connections("worker-2")
        assert worker2_connections == ["widget-3"]

    async def test_list_worker_connections_missing_worker(
        self, router: MemoryConnectionRouter
    ) -> None:
        assert await router.list_worker_connections("missing-worker") == []


# --- MemorySessionStore Tests ---


class TestMemorySessionStore:
    """Tests for MemorySessionStore."""

    @pytest.fixture
    def store(self) -> MemorySessionStore:
        return MemorySessionStore()

    async def test_create_session(self, store: MemorySessionStore) -> None:
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

    async def test_get_session(self, store: MemorySessionStore) -> None:
        await store.create_session("session-1", "user-1", roles=["viewer"])

        session = await store.get_session("session-1")
        assert session is not None
        assert session.user_id == "user-1"

        assert await store.get_session("nonexistent") is None

    async def test_validate_session(self, store: MemorySessionStore) -> None:
        await store.create_session("session-1", "user-1")
        assert await store.validate_session("session-1") is True
        assert await store.validate_session("nonexistent") is False

    async def test_refresh_session(self, store: MemorySessionStore) -> None:
        await store.create_session("session-1", "user-1")

        await asyncio.sleep(0.05)
        assert await store.refresh_session("session-1") is True
        assert await store.refresh_session("nonexistent") is False

    async def test_refresh_session_already_expired(self, store: MemorySessionStore) -> None:
        await store.create_session("s1", "u1", ttl=1)
        async with store._lock:
            store._sessions["s1"].expires_at = time.time() - 100

        assert await store.refresh_session("s1") is False

    async def test_refresh_session_extend_ttl_explicit(self, store: MemorySessionStore) -> None:
        await store.create_session("s1", "u1", ttl=10)
        async with store._lock:
            old_expires = store._sessions["s1"].expires_at

        await asyncio.sleep(0.05)
        assert await store.refresh_session("s1", extend_ttl=600) is True
        async with store._lock:
            new_expires = store._sessions["s1"].expires_at
        assert new_expires is not None
        assert old_expires is not None
        assert new_expires > old_expires

    async def test_refresh_session_no_ttl(self, store: MemorySessionStore) -> None:
        """Session without TTL stays active and refreshes without changing expires_at."""
        await store.create_session("s1", "u1")
        async with store._lock:
            assert store._sessions["s1"].expires_at is None

        assert await store.refresh_session("s1") is True

    async def test_refresh_session_with_ttl_no_extend_reuses_original(
        self, store: MemorySessionStore
    ) -> None:
        """Refresh without extend_ttl uses original duration."""
        await store.create_session("s1", "u1", ttl=600)
        async with store._lock:
            old_expires = store._sessions["s1"].expires_at
            assert old_expires is not None

        await asyncio.sleep(0.05)
        assert await store.refresh_session("s1") is True
        async with store._lock:
            new_expires = store._sessions["s1"].expires_at
        assert new_expires is not None
        assert new_expires > old_expires

    async def test_delete_session(self, store: MemorySessionStore) -> None:
        await store.create_session("session-1", "user-1")
        assert await store.validate_session("session-1") is True

        assert await store.delete_session("session-1") is True
        assert await store.validate_session("session-1") is False
        assert await store.delete_session("session-1") is False

    async def test_session_expired_get_returns_none(self, store: MemorySessionStore) -> None:
        """Expired sessions return None and are cleaned up from both indexes."""
        await store.create_session("s1", "u1", ttl=1)
        async with store._lock:
            assert "s1" in store._user_sessions["u1"]
            store._sessions["s1"].expires_at = time.time() - 100

        assert await store.get_session("s1") is None
        async with store._lock:
            assert "s1" not in store._sessions
            assert "s1" not in store._user_sessions.get("u1", set())

    async def test_list_user_sessions(self, store: MemorySessionStore) -> None:
        await store.create_session("session-1", "user-1")
        await store.create_session("session-2", "user-1")
        await store.create_session("session-3", "user-2")

        user1_sessions = await store.list_user_sessions("user-1")
        assert len(user1_sessions) == 2
        assert {s.session_id for s in user1_sessions} == {"session-1", "session-2"}

    async def test_list_user_sessions_empty(self, store: MemorySessionStore) -> None:
        assert await store.list_user_sessions("ghost-user") == []

    async def test_list_user_sessions_drops_expired(self, store: MemorySessionStore) -> None:
        await store.create_session("active", "u1", ttl=600)
        await store.create_session("expired", "u1", ttl=1)
        async with store._lock:
            store._sessions["expired"].expires_at = time.time() - 100

        sessions = await store.list_user_sessions("u1")
        assert len(sessions) == 1
        assert sessions[0].session_id == "active"
        assert "expired" not in store._sessions

    async def test_check_permission(self, store: MemorySessionStore) -> None:
        store.set_role_permissions("admin", {"read", "write", "delete"})
        store.set_role_permissions("viewer", {"read"})

        await store.create_session("admin-session", "admin-user", roles=["admin"])
        await store.create_session("viewer-session", "viewer-user", roles=["viewer"])

        assert await store.check_permission("admin-session", "widget", "1", "read")
        assert await store.check_permission("admin-session", "widget", "1", "write")
        assert await store.check_permission("admin-session", "widget", "1", "delete")

        assert await store.check_permission("viewer-session", "widget", "1", "read")
        assert not await store.check_permission("viewer-session", "widget", "1", "write")
        assert not await store.check_permission("viewer-session", "widget", "1", "delete")

    async def test_check_permission_session_missing(self, store: MemorySessionStore) -> None:
        assert await store.check_permission("missing", "widget", "w1", "read") is False

    async def test_check_permission_no_matching_role(self, store: MemorySessionStore) -> None:
        await store.create_session("s1", "u1", roles=["custom-role"])
        assert await store.check_permission("s1", "widget", "w1", "read") is False

    async def test_set_role_permissions(self, store: MemorySessionStore) -> None:
        store.set_role_permissions("custom-role", {"my-perm"})
        await store.create_session("s1", "u1", roles=["custom-role"])
        assert await store.check_permission("s1", "widget", "w1", "my-perm") is True

    async def test_session_with_ttl(self, store: MemorySessionStore) -> None:
        await store.create_session("short-session", "user-1", ttl=1)
        assert await store.validate_session("short-session") is True

        session = await store.get_session("short-session")
        assert session is not None
        assert session.expires_at is not None
        assert session.expires_at > time.time()


# --- MemoryChatStore Tests ---


class TestMemoryChatStore:
    """Tests for MemoryChatStore."""

    @pytest.fixture
    def store(self) -> MemoryChatStore:
        return MemoryChatStore()

    async def test_save_and_get_thread(self, store: MemoryChatStore) -> None:
        await store.save_thread("w1", ChatThread(thread_id="t1", title="Test"))
        result = await store.get_thread("w1", "t1")
        assert result is not None
        assert result.thread_id == "t1"

    async def test_get_thread_missing(self, store: MemoryChatStore) -> None:
        assert await store.get_thread("w1", "missing") is None

    async def test_get_thread_missing_widget(self, store: MemoryChatStore) -> None:
        assert await store.get_thread("missing-widget", "t1") is None

    async def test_list_threads(self, store: MemoryChatStore) -> None:
        await store.save_thread("w1", ChatThread(thread_id="t1", title="A"))
        await store.save_thread("w1", ChatThread(thread_id="t2", title="B"))
        threads = await store.list_threads("w1")
        assert len(threads) == 2

    async def test_list_threads_empty_widget(self, store: MemoryChatStore) -> None:
        assert await store.list_threads("missing") == []

    async def test_delete_thread(self, store: MemoryChatStore) -> None:
        await store.save_thread("w1", ChatThread(thread_id="t1", title="A"))
        assert await store.delete_thread("w1", "t1") is True
        assert await store.get_thread("w1", "t1") is None

    async def test_delete_thread_missing(self, store: MemoryChatStore) -> None:
        assert await store.delete_thread("w1", "missing") is False

    async def test_delete_thread_missing_widget(self, store: MemoryChatStore) -> None:
        assert await store.delete_thread("ghost", "t1") is False

    async def test_append_message(self, store: MemoryChatStore) -> None:
        await store.save_thread("w1", ChatThread(thread_id="t1", title="A"))
        await store.append_message(
            "w1", "t1", ChatMessage(role="user", content="hello", message_id="m1")
        )

        thread = await store.get_thread("w1", "t1")
        assert thread is not None
        assert len(thread.messages) == 1
        assert thread.messages[0].text_content() == "hello"

    async def test_append_message_no_thread(self, store: MemoryChatStore) -> None:
        """Appending to a nonexistent thread is a silent no-op."""
        await store.append_message(
            "w1", "missing", ChatMessage(role="user", content="hi", message_id="m1")
        )

    async def test_append_message_evicts_oldest(self, store: MemoryChatStore) -> None:
        await store.save_thread("w1", ChatThread(thread_id="t1", title="A"))

        with patch("pywry.chat.MAX_MESSAGES_PER_THREAD", 3):
            for i in range(10):
                await store.append_message(
                    "w1",
                    "t1",
                    ChatMessage(role="user", content=f"msg{i}", message_id=f"m{i}"),
                )

            messages = await store.get_messages("w1", "t1")
            assert len(messages) == 3
            # Oldest are evicted, only most recent 3 remain
            assert messages[0].text_content() == "msg7"

    async def test_get_messages(self, store: MemoryChatStore) -> None:
        await store.save_thread("w1", ChatThread(thread_id="t1", title="A"))
        for i in range(5):
            await store.append_message(
                "w1",
                "t1",
                ChatMessage(role="user", content=f"msg{i}", message_id=f"m{i}"),
            )

        messages = await store.get_messages("w1", "t1", limit=3)
        assert len(messages) == 3

    async def test_get_messages_no_thread(self, store: MemoryChatStore) -> None:
        assert await store.get_messages("w1", "missing") == []

    async def test_get_messages_no_widget(self, store: MemoryChatStore) -> None:
        assert await store.get_messages("ghost", "t1") == []

    async def test_get_messages_before_id(self, store: MemoryChatStore) -> None:
        await store.save_thread("w1", ChatThread(thread_id="t1", title="A"))
        for i in range(5):
            await store.append_message(
                "w1",
                "t1",
                ChatMessage(role="user", content=f"msg{i}", message_id=f"m{i}"),
            )

        messages = await store.get_messages("w1", "t1", before_id="m3")
        # before_id excludes m3 and everything after
        ids = {m.message_id for m in messages}
        assert "m3" not in ids
        assert "m4" not in ids
        assert len(messages) == 3

    async def test_get_messages_before_id_not_found(self, store: MemoryChatStore) -> None:
        await store.save_thread("w1", ChatThread(thread_id="t1", title="A"))
        await store.append_message(
            "w1", "t1", ChatMessage(role="user", content="hi", message_id="m1")
        )
        # before_id doesn't match any message -> all messages returned
        messages = await store.get_messages("w1", "t1", before_id="ghost")
        assert len(messages) == 1

    async def test_clear_messages(self, store: MemoryChatStore) -> None:
        await store.save_thread("w1", ChatThread(thread_id="t1", title="A"))
        await store.append_message(
            "w1", "t1", ChatMessage(role="user", content="hi", message_id="m1")
        )
        await store.clear_messages("w1", "t1")
        assert await store.get_messages("w1", "t1") == []

    async def test_clear_messages_no_thread(self, store: MemoryChatStore) -> None:
        """Clearing a nonexistent thread is a silent no-op."""
        await store.clear_messages("w1", "missing")

    async def test_cleanup_widget(self, store: MemoryChatStore) -> None:
        await store.save_thread("w1", ChatThread(thread_id="t1", title="A"))
        await store.cleanup_widget("w1")
        assert await store.list_threads("w1") == []

    async def test_cleanup_widget_missing(self, store: MemoryChatStore) -> None:
        """Cleanup of an unknown widget is a silent no-op."""
        await store.cleanup_widget("ghost")


# --- MemoryChartStore Tests ---


class TestMemoryChartStore:
    """Tests for MemoryChartStore."""

    @pytest.fixture
    def store(self) -> MemoryChartStore:
        return MemoryChartStore()

    async def test_save_and_get_layout(self, store: MemoryChartStore) -> None:
        entry = await store.save_layout(
            user_id="u1", layout_id="l1", name="Layout 1", data_json='{"x": 1}'
        )
        assert entry["id"] == "l1"
        assert entry["name"] == "Layout 1"
        assert await store.get_layout("u1", "l1") == '{"x": 1}'

    async def test_save_layout_with_summary(self, store: MemoryChartStore) -> None:
        entry = await store.save_layout(
            user_id="u1",
            layout_id="l1",
            name="L1",
            data_json="{}",
            summary="A summary",
        )
        assert entry["summary"] == "A summary"

    async def test_get_layout_missing(self, store: MemoryChartStore) -> None:
        assert await store.get_layout("u1", "missing") is None

    async def test_save_layout_replaces(self, store: MemoryChartStore) -> None:
        await store.save_layout("u1", "l1", "Old", "{}")
        await store.save_layout("u1", "l1", "New", '{"v": 2}')
        layouts = await store.list_layouts("u1")
        assert len(layouts) == 1
        assert layouts[0]["name"] == "New"

    async def test_save_layout_caps_index_at_200(self, store: MemoryChartStore) -> None:
        for i in range(250):
            await store.save_layout("u1", f"l{i}", f"L{i}", "{}")
        assert len(await store.list_layouts("u1")) == 200

    async def test_list_layouts_empty(self, store: MemoryChartStore) -> None:
        assert await store.list_layouts("u1") == []

    async def test_delete_layout(self, store: MemoryChartStore) -> None:
        await store.save_layout("u1", "l1", "L1", "{}")
        assert await store.delete_layout("u1", "l1") is True
        assert await store.get_layout("u1", "l1") is None

    async def test_delete_layout_missing(self, store: MemoryChartStore) -> None:
        assert await store.delete_layout("u1", "missing") is False

    async def test_rename_layout(self, store: MemoryChartStore) -> None:
        await store.save_layout("u1", "l1", "Old", "{}")
        assert await store.rename_layout("u1", "l1", "New") is True
        layouts = await store.list_layouts("u1")
        assert layouts[0]["name"] == "New"

    async def test_rename_layout_missing(self, store: MemoryChartStore) -> None:
        assert await store.rename_layout("u1", "missing", "X") is False

    async def test_update_layout_meta_name_only(self, store: MemoryChartStore) -> None:
        await store.save_layout("u1", "l1", "Old", "{}", summary="orig")
        assert await store.update_layout_meta("u1", "l1", name="New") is True
        layouts = await store.list_layouts("u1")
        assert layouts[0]["name"] == "New"
        # Summary unchanged
        assert layouts[0]["summary"] == "orig"

    async def test_update_layout_meta_summary_only(self, store: MemoryChartStore) -> None:
        await store.save_layout("u1", "l1", "Original", "{}", summary="orig")
        assert await store.update_layout_meta("u1", "l1", summary="new sum") is True
        layouts = await store.list_layouts("u1")
        assert layouts[0]["summary"] == "new sum"
        # Name unchanged
        assert layouts[0]["name"] == "Original"

    async def test_update_layout_meta_missing(self, store: MemoryChartStore) -> None:
        assert await store.update_layout_meta("u1", "missing", name="X") is False

    async def test_settings_template_roundtrip(self, store: MemoryChartStore) -> None:
        assert await store.get_settings_template("u1") is None
        await store.save_settings_template("u1", '{"tpl": 1}')
        assert await store.get_settings_template("u1") == '{"tpl": 1}'

    async def test_settings_default_id_default(self, store: MemoryChartStore) -> None:
        assert await store.get_settings_default_id("u1") == "factory"

    async def test_set_settings_default_id_valid(self, store: MemoryChartStore) -> None:
        await store.set_settings_default_id("u1", "custom")
        assert await store.get_settings_default_id("u1") == "custom"

    async def test_set_settings_default_id_invalid_falls_back(
        self, store: MemoryChartStore
    ) -> None:
        await store.set_settings_default_id("u1", "bogus")
        assert await store.get_settings_default_id("u1") == "factory"

    async def test_clear_settings_template(self, store: MemoryChartStore) -> None:
        await store.save_settings_template("u1", "{}")
        await store.set_settings_default_id("u1", "custom")
        await store.clear_settings_template("u1")

        assert await store.get_settings_template("u1") is None
        assert await store.get_settings_default_id("u1") == "factory"


# --- Factory ---


class TestCreateMemoryStores:
    """Tests for create_memory_stores factory."""

    def test_returns_all_stores(self) -> None:
        widget, bus, router, sessions = create_memory_stores()
        assert isinstance(widget, MemoryWidgetStore)
        assert isinstance(bus, MemoryEventBus)
        assert isinstance(router, MemoryConnectionRouter)
        assert isinstance(sessions, MemorySessionStore)
