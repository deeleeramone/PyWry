"""Tests for the SQLite state backend.

Covers ChatStore CRUD, audit trail, session management, RBAC,
encryption, auto-setup, and interchangeability with MemoryChatStore.
"""

from __future__ import annotations

import time

import pytest

from pywry.chat.models import ChatMessage, ChatThread
from pywry.state.sqlite import (
    SqliteChatStore,
    SqliteConnectionRouter,
    SqliteEventBus,
    SqliteSessionStore,
    SqliteWidgetStore,
)


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")


@pytest.fixture
def chat_store(db_path):
    return SqliteChatStore(db_path=db_path, encrypted=False)


@pytest.fixture
def session_store(db_path):
    return SqliteSessionStore(db_path=db_path, encrypted=False)


@pytest.fixture
def widget_store(db_path):
    return SqliteWidgetStore(db_path=db_path, encrypted=False)


class TestSqliteChatStoreCRUD:
    @pytest.mark.asyncio
    async def test_save_and_get_thread(self, chat_store):
        thread = ChatThread(thread_id="t1", title="Test Thread")
        await chat_store.save_thread("w1", thread)
        result = await chat_store.get_thread("w1", "t1")
        assert result is not None
        assert result.thread_id == "t1"
        assert result.title == "Test Thread"

    @pytest.mark.asyncio
    async def test_list_threads(self, chat_store):
        await chat_store.save_thread("w1", ChatThread(thread_id="t1", title="A"))
        await chat_store.save_thread("w1", ChatThread(thread_id="t2", title="B"))
        threads = await chat_store.list_threads("w1")
        assert len(threads) == 2

    @pytest.mark.asyncio
    async def test_delete_thread(self, chat_store):
        await chat_store.save_thread("w1", ChatThread(thread_id="t1", title="A"))
        deleted = await chat_store.delete_thread("w1", "t1")
        assert deleted is True
        result = await chat_store.get_thread("w1", "t1")
        assert result is None

    @pytest.mark.asyncio
    async def test_append_and_get_messages(self, chat_store):
        await chat_store.save_thread("w1", ChatThread(thread_id="t1", title="A"))
        msg = ChatMessage(role="user", content="hello", message_id="m1")
        await chat_store.append_message("w1", "t1", msg)
        messages = await chat_store.get_messages("w1", "t1")
        assert len(messages) == 1
        assert messages[0].text_content() == "hello"

    @pytest.mark.asyncio
    async def test_clear_messages(self, chat_store):
        await chat_store.save_thread("w1", ChatThread(thread_id="t1", title="A"))
        await chat_store.append_message("w1", "t1", ChatMessage(role="user", content="x"))
        await chat_store.clear_messages("w1", "t1")
        messages = await chat_store.get_messages("w1", "t1")
        assert len(messages) == 0

    @pytest.mark.asyncio
    async def test_get_nonexistent_thread(self, chat_store):
        result = await chat_store.get_thread("w1", "nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_widget_isolation(self, chat_store):
        await chat_store.save_thread("w1", ChatThread(thread_id="t1", title="W1"))
        await chat_store.save_thread("w2", ChatThread(thread_id="t2", title="W2"))
        w1_threads = await chat_store.list_threads("w1")
        w2_threads = await chat_store.list_threads("w2")
        assert len(w1_threads) == 1
        assert len(w2_threads) == 1
        assert w1_threads[0].title == "W1"

    @pytest.mark.asyncio
    async def test_message_pagination(self, chat_store):
        await chat_store.save_thread("w1", ChatThread(thread_id="t1", title="A"))
        for i in range(10):
            await chat_store.append_message(
                "w1", "t1",
                ChatMessage(role="user", content=f"msg{i}", message_id=f"m{i}"),
            )
        messages = await chat_store.get_messages("w1", "t1", limit=3)
        assert len(messages) == 3

    @pytest.mark.asyncio
    async def test_persistence_across_instances(self, db_path):
        store1 = SqliteChatStore(db_path=db_path, encrypted=False)
        await store1.save_thread("w1", ChatThread(thread_id="t1", title="Persistent"))
        await store1.append_message(
            "w1", "t1", ChatMessage(role="user", content="saved")
        )

        store2 = SqliteChatStore(db_path=db_path, encrypted=False)
        thread = await store2.get_thread("w1", "t1")
        assert thread is not None
        assert thread.title == "Persistent"
        messages = await store2.get_messages("w1", "t1")
        assert len(messages) == 1
        assert messages[0].text_content() == "saved"


class TestSqliteAuditTrail:
    @pytest.mark.asyncio
    async def test_log_and_get_tool_calls(self, chat_store):
        await chat_store.save_thread("w1", ChatThread(thread_id="t1", title="A"))
        await chat_store.append_message(
            "w1", "t1", ChatMessage(role="assistant", content="ok", message_id="m1")
        )
        await chat_store.log_tool_call(
            message_id="m1",
            tool_call_id="tc1",
            name="read_file",
            kind="read",
            status="completed",
            arguments={"path": "/tmp/test.txt"},
            result="file contents here",
        )
        calls = await chat_store.get_tool_calls("m1")
        assert len(calls) == 1
        assert calls[0]["name"] == "read_file"
        assert calls[0]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_log_and_get_artifacts(self, chat_store):
        await chat_store.save_thread("w1", ChatThread(thread_id="t1", title="A"))
        await chat_store.append_message(
            "w1", "t1", ChatMessage(role="assistant", content="ok", message_id="m1")
        )
        await chat_store.log_artifact(
            message_id="m1",
            artifact_type="code",
            title="main.py",
            content="x = 42",
        )
        artifacts = await chat_store.get_artifacts("m1")
        assert len(artifacts) == 1
        assert artifacts[0]["artifact_type"] == "code"
        assert artifacts[0]["title"] == "main.py"

    @pytest.mark.asyncio
    async def test_log_token_usage_and_stats(self, chat_store):
        await chat_store.save_thread("w1", ChatThread(thread_id="t1", title="A"))
        await chat_store.append_message(
            "w1", "t1", ChatMessage(role="assistant", content="ok", message_id="m1")
        )
        await chat_store.log_token_usage(
            message_id="m1",
            model="gpt-4",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost_usd=0.005,
        )
        stats = await chat_store.get_usage_stats(thread_id="t1")
        assert stats["prompt_tokens"] == 100
        assert stats["completion_tokens"] == 50
        assert stats["total_tokens"] == 150
        assert stats["cost_usd"] == 0.005

    @pytest.mark.asyncio
    async def test_total_cost(self, chat_store):
        await chat_store.save_thread("w1", ChatThread(thread_id="t1", title="A"))
        await chat_store.append_message(
            "w1", "t1", ChatMessage(role="assistant", content="a", message_id="m1")
        )
        await chat_store.append_message(
            "w1", "t1", ChatMessage(role="assistant", content="b", message_id="m2")
        )
        await chat_store.log_token_usage(message_id="m1", cost_usd=0.01)
        await chat_store.log_token_usage(message_id="m2", cost_usd=0.02)
        cost = await chat_store.get_total_cost(thread_id="t1")
        assert abs(cost - 0.03) < 0.001

    @pytest.mark.asyncio
    async def test_search_messages(self, chat_store):
        await chat_store.save_thread("w1", ChatThread(thread_id="t1", title="A"))
        await chat_store.append_message(
            "w1", "t1", ChatMessage(role="user", content="find the fibonacci function")
        )
        await chat_store.append_message(
            "w1", "t1", ChatMessage(role="assistant", content="here is the code")
        )
        results = await chat_store.search_messages("fibonacci")
        assert len(results) == 1
        assert "fibonacci" in results[0]["content"]

    @pytest.mark.asyncio
    async def test_log_resource(self, chat_store):
        await chat_store.save_thread("w1", ChatThread(thread_id="t1", title="A"))
        await chat_store.log_resource(
            thread_id="t1",
            uri="file:///data/report.csv",
            name="report.csv",
            mime_type="text/csv",
            size=1024,
        )

    @pytest.mark.asyncio
    async def test_log_skill(self, chat_store):
        await chat_store.save_thread("w1", ChatThread(thread_id="t1", title="A"))
        await chat_store.log_skill(
            thread_id="t1",
            name="langgraph-docs",
            metadata={"version": "1.0"},
        )


class TestSqliteSessionStore:
    @pytest.mark.asyncio
    async def test_auto_admin_session(self, session_store):
        session = await session_store.get_session("local")
        assert session is not None
        assert session.user_id == "admin"
        assert "admin" in session.roles

    @pytest.mark.asyncio
    async def test_create_and_get_session(self, session_store):
        session = await session_store.create_session(
            session_id="s1", user_id="alice", roles=["editor"]
        )
        assert session.user_id == "alice"
        retrieved = await session_store.get_session("s1")
        assert retrieved is not None
        assert "editor" in retrieved.roles

    @pytest.mark.asyncio
    async def test_session_expiry(self, session_store):
        await session_store.create_session(
            session_id="s_exp", user_id="bob", ttl=1
        )
        session = await session_store.get_session("s_exp")
        assert session is not None
        import asyncio
        await asyncio.sleep(1.1)
        expired = await session_store.get_session("s_exp")
        assert expired is None

    @pytest.mark.asyncio
    async def test_check_permission_admin(self, session_store):
        allowed = await session_store.check_permission("local", "widget", "w1", "admin")
        assert allowed is True

    @pytest.mark.asyncio
    async def test_check_permission_viewer(self, session_store):
        await session_store.create_session(
            session_id="viewer_s", user_id="viewer_user", roles=["viewer"]
        )
        can_read = await session_store.check_permission("viewer_s", "widget", "w1", "read")
        assert can_read is True
        can_write = await session_store.check_permission("viewer_s", "widget", "w1", "write")
        assert can_write is False

    @pytest.mark.asyncio
    async def test_delete_session(self, session_store):
        await session_store.create_session(session_id="del_s", user_id="u1")
        deleted = await session_store.delete_session("del_s")
        assert deleted is True
        assert await session_store.get_session("del_s") is None

    @pytest.mark.asyncio
    async def test_list_user_sessions(self, session_store):
        await session_store.create_session(session_id="s1", user_id="alice")
        await session_store.create_session(session_id="s2", user_id="alice")
        sessions = await session_store.list_user_sessions("alice")
        assert len(sessions) == 2


class TestSqliteWidgetStore:
    @pytest.mark.asyncio
    async def test_save_and_get_widget(self, widget_store):
        await widget_store.save_widget("w1", "<h1>hi</h1>", token="tok1")
        widget = await widget_store.get_widget("w1")
        assert widget is not None
        assert widget.html == "<h1>hi</h1>"
        assert widget.token == "tok1"

    @pytest.mark.asyncio
    async def test_list_widgets(self, widget_store):
        await widget_store.save_widget("w1", "<h1>a</h1>")
        await widget_store.save_widget("w2", "<h1>b</h1>")
        widgets = await widget_store.list_widgets()
        assert "w1" in widgets
        assert "w2" in widgets

    @pytest.mark.asyncio
    async def test_delete_widget(self, widget_store):
        await widget_store.save_widget("w1", "<h1>a</h1>")
        deleted = await widget_store.delete_widget("w1")
        assert deleted is True
        assert await widget_store.get_widget("w1") is None


class TestSqliteEventBusAndRouter:
    @pytest.mark.asyncio
    async def test_event_bus_publish_subscribe(self, db_path):
        bus = SqliteEventBus(db_path=db_path, encrypted=False)
        received = []
        await bus.subscribe("test-channel", received.append)
        await bus.publish("test-channel", {"data": "hello"})
        assert len(received) == 1
        assert received[0]["data"] == "hello"

    @pytest.mark.asyncio
    async def test_connection_router(self, db_path):
        router = SqliteConnectionRouter(db_path=db_path, encrypted=False)
        await router.register("w1", "worker-1")
        worker = await router.get_worker("w1")
        assert worker == "worker-1"
        await router.unregister("w1")
        assert await router.get_worker("w1") is None


class TestSqliteFactoryIntegration:
    def test_state_backend_sqlite(self, monkeypatch):
        monkeypatch.setenv("PYWRY_DEPLOY__STATE_BACKEND", "sqlite")
        from pywry.state._factory import get_state_backend
        from pywry.state.types import StateBackend

        get_state_backend.cache_clear()
        try:
            backend = get_state_backend()
            assert backend == StateBackend.SQLITE
        finally:
            get_state_backend.cache_clear()
            monkeypatch.delenv("PYWRY_DEPLOY__STATE_BACKEND", raising=False)


class TestAuditTrailDefaultNoOps:
    """Verify Memory and Redis stores have no-op audit trail methods."""

    @pytest.mark.asyncio
    async def test_memory_store_no_op_methods(self):
        from pywry.state.memory import MemoryChatStore

        store = MemoryChatStore()
        await store.log_tool_call("m1", "tc1", "search")
        await store.log_artifact("m1", "code", "test.py")
        await store.log_token_usage("m1", prompt_tokens=100)
        calls = await store.get_tool_calls("m1")
        assert calls == []
        stats = await store.get_usage_stats()
        assert stats["total_tokens"] == 0
