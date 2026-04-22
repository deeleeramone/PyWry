# pylint: disable=too-many-lines
"""Unit tests for the ChatManager orchestrator.

Tests cover:
- ChatManager construction and defaults
- ACP update types (AgentMessageUpdate, ToolCallUpdate, etc.)
- ChatContext dataclass
- SettingsItem model
- callbacks() returns correct keys
- toolbar() returns a Toolbar instance
- send_message() emits and stores messages
- _on_user_message dispatches handler in background thread
- _handle_complete sends complete message
- _handle_stream streams str chunks and SessionUpdate types
- _on_stop_generation cancels active generation
- Thread CRUD: create, switch, delete, rename
- _on_request_state emits full initialization state
- _on_settings_change_event updates internal state
- _on_slash_command_event handles /clear + delegates to user callback
"""

# pylint: disable=missing-function-docstring,redefined-outer-name,unused-argument
# pylint: disable=use-implicit-booleaness-not-comparison,too-many-public-methods

from __future__ import annotations

import time

from typing import Any
from unittest.mock import MagicMock

import pytest

from pywry.chat.artifacts import (
    CodeArtifact,
    HtmlArtifact,
    ImageArtifact,
    JsonArtifact,
    MarkdownArtifact,
    PlotlyArtifact,
    TableArtifact,
    TradingViewArtifact,
)
from pywry.chat.manager import (
    Attachment,
    ChatContext,
    ChatManager,
    SettingsItem,
)
from pywry.chat.session import PlanEntry
from pywry.chat.updates import (
    AgentMessageUpdate,
    ArtifactUpdate,
    CitationUpdate,
    PlanUpdate,
    StatusUpdate,
    ThinkingUpdate,
    ToolCallUpdate,
)


# =============================================================================
# Fixtures
# =============================================================================


class FakeWidget:
    """Minimal widget mock that records emitted events."""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

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


def echo_handler(messages, ctx):
    """Simple handler that returns the last user message."""
    return f"Echo: {messages[-1]['text']}"


def stream_handler(messages, ctx):
    """Generator handler that yields word-by-word."""
    words = messages[-1]["text"].split()
    for i, w in enumerate(words):
        if ctx.cancel_event.is_set():
            return
        yield w + (" " if i < len(words) - 1 else "")


def rich_handler(messages, ctx):
    """Generator handler that yields ACP update types."""
    yield ThinkingUpdate(text="Analyzing the request...")
    yield StatusUpdate(text="Searching...")
    yield ToolCallUpdate(
        toolCallId="call_1",
        name="search",
        kind="fetch",
        status="completed",
    )
    yield CitationUpdate(url="https://example.com", title="Example")
    yield ArtifactUpdate(
        artifact=CodeArtifact(title="code.py", content="x = 42", language="python")
    )
    yield AgentMessageUpdate(text="Done!")


@pytest.fixture
def widget():
    return FakeWidget()


@pytest.fixture(autouse=True)
def _disable_stream_buffering():
    """Disable stream buffering so tests see individual chunk events."""
    orig_interval = ChatManager._STREAM_FLUSH_INTERVAL
    orig_max = ChatManager._STREAM_MAX_BUFFER
    ChatManager._STREAM_FLUSH_INTERVAL = 0
    ChatManager._STREAM_MAX_BUFFER = 1
    yield
    ChatManager._STREAM_FLUSH_INTERVAL = orig_interval
    ChatManager._STREAM_MAX_BUFFER = orig_max


@pytest.fixture
def manager():
    return ChatManager(handler=echo_handler)


@pytest.fixture
def bound_manager(widget):
    mgr = ChatManager(handler=echo_handler)
    mgr.bind(widget)
    return mgr


# =============================================================================
# Update Type Tests
# =============================================================================


class TestUpdateTypes:
    """Test ACP update type models."""

    def test_status_update(self):
        r = StatusUpdate(text="Searching...")
        assert r.session_update == "x_status"
        assert r.text == "Searching..."

    def test_agent_message_update(self):
        r = AgentMessageUpdate(text="Hello!")
        assert r.session_update == "agent_message"
        assert r.text == "Hello!"

    def test_tool_call_update(self):
        r = ToolCallUpdate(
            toolCallId="call_1",
            name="search",
            kind="fetch",
            status="completed",
        )
        assert r.session_update == "tool_call"
        assert r.name == "search"
        assert r.kind == "fetch"

    def test_plan_update(self):
        r = PlanUpdate(
            entries=[
                PlanEntry(content="Step 1", priority="high", status="completed"),
            ]
        )
        assert r.session_update == "plan"
        assert len(r.entries) == 1

    def test_thinking_update(self):
        r = ThinkingUpdate(text="Let me think...")
        assert r.session_update == "x_thinking"

    def test_citation_update(self):
        r = CitationUpdate(url="https://example.com", title="Example")
        assert r.session_update == "x_citation"
        assert r.url == "https://example.com"


# =============================================================================
# Artifact Tests
# =============================================================================


class TestArtifactModels:
    """Test artifact model creation."""

    def test_code_artifact(self):
        a = CodeArtifact(title="test.py", content="x = 1", language="python")
        assert a.artifact_type == "code"
        assert a.language == "python"

    def test_markdown_artifact(self):
        a = MarkdownArtifact(title="README", content="# Hello")
        assert a.artifact_type == "markdown"

    def test_html_artifact(self):
        a = HtmlArtifact(title="page", content="<h1>Hi</h1>")
        assert a.artifact_type == "html"

    def test_table_artifact(self):
        a = TableArtifact(title="data", data=[{"a": 1}])
        assert a.artifact_type == "table"
        assert a.height == "400px"

    def test_plotly_artifact(self):
        a = PlotlyArtifact(title="chart", figure={"data": []})
        assert a.artifact_type == "plotly"

    def test_image_artifact(self):
        a = ImageArtifact(title="photo", url="data:image/png;base64,abc")
        assert a.artifact_type == "image"

    def test_json_artifact(self):
        a = JsonArtifact(title="config", data={"key": "value"})
        assert a.artifact_type == "json"

    def test_tradingview_artifact(self):
        from pywry.chat.artifacts import TradingViewSeries

        a = TradingViewArtifact(
            title="AAPL",
            series=[TradingViewSeries(type="candlestick", data=[])],
        )
        assert a.artifact_type == "tradingview"
        assert len(a.series) == 1


# =============================================================================
# ChatContext Tests
# =============================================================================


class TestChatContext:
    """Test ChatContext dataclass."""

    def test_defaults(self):
        ctx = ChatContext()
        assert ctx.thread_id == ""
        assert ctx.model == ""
        assert ctx.temperature == 0.7
        assert ctx.attachments == []
        assert not ctx.cancel_event.is_set()

    def test_attachment_summary_empty(self):
        ctx = ChatContext()
        assert ctx.attachment_summary == ""

    def test_attachment_summary_file(self):
        import pathlib

        ctx = ChatContext(
            attachments=[
                Attachment(type="file", name="report.csv", path=pathlib.Path("/data/report.csv")),
            ]
        )
        assert "report.csv" in ctx.attachment_summary
        assert "report.csv" in ctx.attachment_summary
        assert str(pathlib.Path("/data/report.csv")) in ctx.attachment_summary

    def test_attachment_summary_widget(self):
        ctx = ChatContext(
            attachments=[
                Attachment(type="widget", name="@Sales Data", content="data here"),
            ]
        )
        assert "@Sales Data" in ctx.attachment_summary

    def test_context_text(self):
        ctx = ChatContext(
            attachments=[
                Attachment(type="widget", name="@Grid", content="col1,col2\n1,2"),
            ]
        )
        text = ctx.context_text
        assert "Grid" in text
        assert "col1,col2" in text

    def test_get_attachment_found(self):
        ctx = ChatContext(
            attachments=[
                Attachment(type="widget", name="@Sales", content="revenue=100"),
            ]
        )
        assert ctx.get_attachment("Sales") == "revenue=100"
        assert ctx.get_attachment("@Sales") == "revenue=100"

    def test_get_attachment_not_found(self):
        ctx = ChatContext(attachments=[])
        result = ctx.get_attachment("Missing")
        assert "not found" in result

    def test_wait_for_input_cancel(self):
        ctx = ChatContext()
        ctx.cancel_event.set()
        result = ctx.wait_for_input(timeout=0.1)
        assert result == ""


# =============================================================================
# SettingsItem Tests
# =============================================================================


class TestSettingsItem:
    """Test SettingsItem model."""

    def test_action(self):
        s = SettingsItem(id="clear", label="Clear History", type="action")
        assert s.type == "action"

    def test_toggle(self):
        s = SettingsItem(id="stream", label="Streaming", type="toggle", value=True)
        assert s.value is True

    def test_select(self):
        s = SettingsItem(id="model", label="Model", type="select", options=["gpt-4", "gpt-4o"])
        assert len(s.options) == 2

    def test_range(self):
        s = SettingsItem(id="temp", label="Temperature", type="range", min=0.0, max=2.0, step=0.1)
        assert s.min == 0.0
        assert s.max == 2.0


# =============================================================================
# ChatManager Tests
# =============================================================================


class TestChatManager:
    """Test ChatManager construction and public API."""

    def test_construction(self):
        mgr = ChatManager(handler=echo_handler)
        assert mgr.active_thread_id  # has a default thread

    def test_requires_handler_or_provider(self):
        with pytest.raises(ValueError, match="Either"):
            ChatManager()

    def test_callbacks_returns_expected_keys(self, manager):
        cbs = manager.callbacks()
        expected = {
            "chat:user-message",
            "chat:stop-generation",
            "chat:slash-command",
            "chat:thread-create",
            "chat:thread-switch",
            "chat:thread-delete",
            "chat:thread-rename",
            "chat:settings-change",
            "chat:request-state",
            "chat:todo-clear",
            "chat:input-response",
            "chat:edit-message",
            "chat:resend-from",
        }
        assert set(cbs.keys()) == expected

    def test_settings_property(self):
        mgr = ChatManager(
            handler=echo_handler,
            settings=[
                SettingsItem(id="model", label="Model", type="select", value="gpt-4"),
            ],
        )
        assert mgr.settings["model"] == "gpt-4"

    def test_send_message(self, bound_manager, widget):
        bound_manager.send_message("Hello from code")
        events = widget.get_events("chat:assistant-message")
        assert len(events) == 1
        assert events[0]["text"] == "Hello from code"

    def test_send_message_stores_in_thread(self, bound_manager):
        tid = bound_manager.active_thread_id
        bound_manager.send_message("stored")
        assert len(bound_manager.threads[tid]) == 1
        assert bound_manager.threads[tid][0]["text"] == "stored"


class TestChatManagerHandlerDispatch:
    """Test handler invocation and stream processing."""

    def test_echo_handler(self, widget):
        mgr = ChatManager(handler=echo_handler)
        mgr.bind(widget)
        mgr._on_user_message(
            {"text": "hello", "threadId": mgr.active_thread_id},
            "chat:user-message",
            "",
        )
        # Wait for background thread
        time.sleep(0.3)
        events = widget.get_events("chat:assistant-message")
        assert any("Echo: hello" in e.get("text", "") for e in events)

    def test_stream_handler(self, widget):
        mgr = ChatManager(handler=stream_handler)
        mgr.bind(widget)
        mgr._on_user_message(
            {"text": "a b c", "threadId": mgr.active_thread_id},
            "chat:user-message",
            "",
        )
        time.sleep(0.3)
        chunks = widget.get_events("chat:stream-chunk")
        # Should have streaming chunks + done
        assert len(chunks) > 0
        done_chunks = [c for c in chunks if c.get("done")]
        assert len(done_chunks) >= 1

    def test_stop_generation(self, widget):
        def slow_handler(messages, ctx):
            for i in range(100):
                if ctx.cancel_event.is_set():
                    return
                yield f"chunk{i} "
                time.sleep(0.01)

        mgr = ChatManager(handler=slow_handler)
        mgr.bind(widget)
        mgr._on_user_message(
            {"text": "go", "threadId": mgr.active_thread_id},
            "chat:user-message",
            "",
        )
        time.sleep(0.05)
        mgr._on_stop_generation(
            {"threadId": mgr.active_thread_id},
            "chat:stop-generation",
            "",
        )
        time.sleep(0.3)
        chunks = widget.get_events("chat:stream-chunk")
        stopped = [c for c in chunks if c.get("stopped")]
        assert len(stopped) >= 1


class TestChatManagerThreads:
    """Test thread CRUD operations."""

    def test_create_thread(self, bound_manager, widget):
        bound_manager._on_thread_create({"title": "New Thread"}, "", "")
        events = widget.get_events("chat:update-thread-list")
        assert len(events) >= 1
        assert len(bound_manager.threads) == 2

    def test_switch_thread(self, bound_manager, widget):
        bound_manager._on_thread_create({"title": "Thread 2"}, "", "")
        new_tid = bound_manager.active_thread_id
        old_tid = next(t for t in bound_manager.threads if t != new_tid)
        bound_manager._on_thread_switch({"threadId": old_tid}, "", "")
        assert bound_manager.active_thread_id == old_tid

    def test_delete_thread(self, bound_manager, widget):
        bound_manager._on_thread_create({"title": "To Delete"}, "", "")
        tid = bound_manager.active_thread_id
        bound_manager._on_thread_delete({"threadId": tid}, "", "")
        assert tid not in bound_manager.threads

    def test_rename_thread(self, bound_manager, widget):
        tid = bound_manager.active_thread_id
        bound_manager._on_thread_rename({"threadId": tid, "title": "Renamed"}, "", "")
        events = widget.get_events("chat:update-thread-list")
        assert len(events) >= 1


class TestChatManagerState:
    """Test state management."""

    def test_request_state(self, bound_manager, widget):
        bound_manager._on_request_state({}, "", "")
        events = widget.get_events("chat:state-response")
        assert len(events) == 1
        state = events[0]
        assert "threads" in state
        assert "activeThreadId" in state

    def test_request_state_with_welcome(self, widget):
        mgr = ChatManager(handler=echo_handler, welcome_message="Welcome!")
        mgr.bind(widget)
        mgr._on_request_state({}, "", "")
        events = widget.get_events("chat:state-response")
        assert len(events) == 1
        messages = events[0]["messages"]
        assert any("Welcome!" in m.get("content", "") for m in messages)

    def test_settings_change(self, bound_manager, widget):
        callback = MagicMock()
        bound_manager._on_settings_change = callback
        bound_manager._on_settings_change_event({"key": "model", "value": "gpt-4o"}, "", "")
        assert bound_manager.settings["model"] == "gpt-4o"
        callback.assert_called_once_with("model", "gpt-4o")

    def test_slash_command_clear(self, bound_manager, widget):
        tid = bound_manager.active_thread_id
        bound_manager.send_message("test")
        assert len(bound_manager.threads[tid]) == 1
        bound_manager._on_slash_command_event({"command": "/clear", "threadId": tid}, "", "")
        assert len(bound_manager.threads[tid]) == 0


# =============================================================================
# Edit / Resend Tests
# =============================================================================


def _seed_thread(mgr: ChatManager) -> tuple[str, list[dict[str, Any]]]:
    """Populate the manager's active thread with a four-message conversation."""
    tid = mgr.active_thread_id
    msgs = [
        {"id": "msg_user_1", "role": "user", "text": "first question"},
        {"id": "msg_asst_1", "role": "assistant", "text": "first answer"},
        {"id": "msg_user_2", "role": "user", "text": "second question"},
        {"id": "msg_asst_2", "role": "assistant", "text": "second answer"},
    ]
    mgr._threads[tid] = list(msgs)
    return tid, msgs


class TestTruncateThreadAt:
    """Direct unit tests for the _truncate_thread_at helper."""

    def test_keep_target_drops_messages_after(self, bound_manager):
        tid, _ = _seed_thread(bound_manager)
        removed, removed_ids = bound_manager._truncate_thread_at(
            tid, "msg_user_2", keep_target=True
        )
        kept_ids = [m["id"] for m in bound_manager._threads[tid]]
        assert kept_ids == ["msg_user_1", "msg_asst_1", "msg_user_2"]
        assert removed_ids == ["msg_asst_2"]
        assert len(removed) == 1

    def test_drop_target_removes_message_and_after(self, bound_manager):
        tid, _ = _seed_thread(bound_manager)
        removed, removed_ids = bound_manager._truncate_thread_at(
            tid, "msg_user_2", keep_target=False
        )
        kept_ids = [m["id"] for m in bound_manager._threads[tid]]
        assert kept_ids == ["msg_user_1", "msg_asst_1"]
        assert removed_ids == ["msg_user_2", "msg_asst_2"]
        assert len(removed) == 2

    def test_unknown_message_id_no_op(self, bound_manager):
        tid, msgs = _seed_thread(bound_manager)
        removed, removed_ids = bound_manager._truncate_thread_at(tid, "ghost", keep_target=True)
        assert removed == []
        assert removed_ids == []
        # Thread untouched
        assert [m["id"] for m in bound_manager._threads[tid]] == [m["id"] for m in msgs]


class TestEditMessage:
    """Tests for _on_edit_message — replace text + truncate + regenerate."""

    def test_edit_emits_messages_deleted(self, bound_manager, widget):
        tid, _ = _seed_thread(bound_manager)
        bound_manager._on_edit_message(
            {"messageId": "msg_user_2", "threadId": tid, "text": "REVISED"},
            "chat:edit-message",
            "",
        )
        time.sleep(0.2)  # allow background thread
        deletions = widget.get_events("chat:messages-deleted")
        assert deletions, "expected at least one chat:messages-deleted event"
        d = deletions[0]
        assert d["editedMessageId"] == "msg_user_2"
        assert d["editedText"] == "REVISED"
        # Only the trailing assistant reply should be removed
        assert d["messageIds"] == ["msg_asst_2"]

    def test_edit_replaces_user_message_text(self, bound_manager, widget):
        tid, _ = _seed_thread(bound_manager)
        bound_manager._on_edit_message(
            {"messageId": "msg_user_2", "threadId": tid, "text": "REVISED"},
            "chat:edit-message",
            "",
        )
        time.sleep(0.2)
        thread = bound_manager._threads[tid]
        # Find the edited user message
        edited = next(m for m in thread if m.get("id") == "msg_user_2")
        assert edited["text"] == "REVISED"

    def test_edit_unknown_message_is_noop(self, bound_manager, widget):
        tid, msgs = _seed_thread(bound_manager)
        bound_manager._on_edit_message(
            {"messageId": "ghost", "threadId": tid, "text": "x"},
            "chat:edit-message",
            "",
        )
        # No deletion event, no thread mutation
        assert widget.get_events("chat:messages-deleted") == []
        assert [m["id"] for m in bound_manager._threads[tid]] == [m["id"] for m in msgs]

    def test_edit_empty_text_is_noop(self, bound_manager, widget):
        tid, _ = _seed_thread(bound_manager)
        bound_manager._on_edit_message(
            {"messageId": "msg_user_2", "threadId": tid, "text": "   "},
            "chat:edit-message",
            "",
        )
        assert widget.get_events("chat:messages-deleted") == []


class TestResendFrom:
    """Tests for _on_resend_from — drop target + everything after, regenerate."""

    def test_resend_keeps_target_and_drops_only_later_messages(self, bound_manager, widget):
        tid, _ = _seed_thread(bound_manager)
        bound_manager._on_resend_from(
            {"messageId": "msg_user_2", "threadId": tid},
            "chat:resend-from",
            "",
        )
        time.sleep(0.2)
        deletions = widget.get_events("chat:messages-deleted")
        assert deletions
        d = deletions[0]
        # The target user message stays — only the assistant reply (and
        # any subsequent turns) are dropped so "Resend" doesn't read as
        # "your message was erased".
        assert d["messageIds"] == ["msg_asst_2"]
        # No edited-message flags — the user message text is unchanged,
        # so the frontend doesn't need to re-render its content.
        assert "editedMessageId" not in d
        assert "editedText" not in d
        # Server-side thread keeps the target user message in place.
        surviving_ids = [m["id"] for m in bound_manager._threads[tid]]
        assert "msg_user_2" in surviving_ids
        assert "msg_asst_2" not in surviving_ids

    def test_resend_re_runs_handler_with_same_text(self, bound_manager, widget):
        tid, _ = _seed_thread(bound_manager)
        bound_manager._on_resend_from(
            {"messageId": "msg_user_2", "threadId": tid},
            "chat:resend-from",
            "",
        )
        time.sleep(0.3)
        # Echo handler returns "Echo: <text>" — verify the assistant reply
        # came back for the resent prompt.
        replies = widget.get_events("chat:assistant-message")
        assert any("Echo: second question" in r.get("text", "") for r in replies)

    def test_resend_unknown_message_is_noop(self, bound_manager, widget):
        tid, msgs = _seed_thread(bound_manager)
        bound_manager._on_resend_from(
            {"messageId": "ghost", "threadId": tid},
            "chat:resend-from",
            "",
        )
        assert widget.get_events("chat:messages-deleted") == []
        # Original thread is intact
        assert [m["id"] for m in bound_manager._threads[tid]] == [m["id"] for m in msgs]

    def test_resend_targeting_assistant_message_is_noop(self, bound_manager, widget):
        """Only user messages can be resent; assistant ids are ignored."""
        tid, msgs = _seed_thread(bound_manager)
        bound_manager._on_resend_from(
            {"messageId": "msg_asst_1", "threadId": tid},
            "chat:resend-from",
            "",
        )
        assert widget.get_events("chat:messages-deleted") == []
        assert [m["id"] for m in bound_manager._threads[tid]] == [m["id"] for m in msgs]


class TestUserMessageStoresId:
    """The frontend-generated messageId must round-trip into thread storage."""

    def test_user_message_uses_provided_id(self, bound_manager):
        tid = bound_manager.active_thread_id
        bound_manager._on_user_message(
            {"messageId": "msg_provided_42", "text": "hi", "threadId": tid},
            "chat:user-message",
            "",
        )
        time.sleep(0.2)
        first = bound_manager._threads[tid][0]
        assert first["id"] == "msg_provided_42"
        assert first["role"] == "user"

    def test_user_message_generates_id_if_absent(self, bound_manager):
        tid = bound_manager.active_thread_id
        bound_manager._on_user_message(
            {"text": "hi", "threadId": tid},
            "chat:user-message",
            "",
        )
        time.sleep(0.2)
        first = bound_manager._threads[tid][0]
        assert first["id"].startswith("msg_")

    def test_assistant_message_carries_id(self, bound_manager):
        tid = bound_manager.active_thread_id
        bound_manager._on_user_message(
            {"text": "hi", "threadId": tid},
            "chat:user-message",
            "",
        )
        time.sleep(0.3)
        # Echo handler completes synchronously; assistant message should be in thread
        msgs = bound_manager._threads[tid]
        asst = [m for m in msgs if m.get("role") == "assistant"]
        assert asst
        assert asst[0]["id"].startswith("msg_")


class TestWidgetAttachmentCarriesWidgetId:
    """Every @-mention attachment must surface the widget_id explicitly so an
    LLM agent reading the @-context can use it directly in MCP tool calls."""

    def _make_mgr(self) -> ChatManager:
        m = ChatManager(handler=echo_handler, enable_context=True)
        m.bind(FakeWidget())
        return m

    def test_registered_source_with_getdata_content_carries_widget_id(self):
        mgr = self._make_mgr()
        mgr.register_context_source("chart", "chart")
        att = mgr._resolve_widget_attachment(
            "chart", content="symbol: AAPL\ninterval: 1d", name="chart"
        )
        assert att is not None
        # The attachment content always starts with widget_id:
        first_line = att.content.splitlines()[0]
        assert first_line == "widget_id: chart"
        # The original getData payload is preserved after the header
        assert "symbol: AAPL" in att.content
        assert att.source == "chart"
        assert att.name == "@chart"

    def test_registered_source_without_getdata_still_carries_widget_id(self):
        mgr = self._make_mgr()
        mgr.register_context_source("chart", "chart")
        att = mgr._resolve_widget_attachment("chart")
        assert att is not None
        # Even with no JS-side getData payload, widget_id is in the content
        assert "widget_id: chart" in att.content
        assert att.source == "chart"

    def test_unregistered_widget_id_still_yields_attachment_with_id(self):
        mgr = self._make_mgr()
        # No register_context_source call — but the user mentioned an unknown
        # widgetId from the frontend.  The attachment must still surface it.
        att = mgr._resolve_widget_attachment("some-other-widget")
        assert att is not None
        assert "widget_id: some-other-widget" in att.content
        assert att.source == "some-other-widget"

    def test_resolve_attachments_dispatches_to_widget_helper(self):
        mgr = self._make_mgr()
        mgr.register_context_source("chart", "chart")
        attachments = mgr._resolve_attachments(
            [
                {
                    "type": "widget",
                    "widgetId": "chart",
                    "name": "chart",
                    "content": "symbol: AAPL",
                },
            ]
        )
        assert len(attachments) == 1
        att = attachments[0]
        assert att.type == "widget"
        assert att.source == "chart"
        # widget_id header is the bridge between @-context and MCP tool calls
        assert att.content.splitlines()[0] == "widget_id: chart"


class TestRegisteredContextAutoAttaches:
    """Every registered context source rides along on every user message
    automatically — the agent never has to remember a widget id between
    turns and the user never has to repeat @<name>."""

    def _make_mgr(self) -> ChatManager:
        m = ChatManager(handler=echo_handler, enable_context=True)
        m.bind(FakeWidget())
        return m

    def test_no_auto_attach_when_context_disabled(self):
        m = ChatManager(handler=echo_handler, enable_context=False)
        m.bind(FakeWidget())
        m.register_context_source("chart", "chart")
        merged = m._auto_attach_context_sources([])
        assert merged == []

    def test_no_auto_attach_when_no_sources_registered(self):
        mgr = self._make_mgr()
        merged = mgr._auto_attach_context_sources([])
        assert merged == []

    def test_registered_source_is_auto_attached(self):
        mgr = self._make_mgr()
        mgr.register_context_source("chart", "chart")
        merged = mgr._auto_attach_context_sources([])
        assert len(merged) == 1
        att = merged[0]
        assert att.source == "chart"
        assert att.auto_attached is True
        assert "widget_id: chart" in att.content

    def test_explicit_mention_takes_precedence(self):
        mgr = self._make_mgr()
        mgr.register_context_source("chart", "chart")
        explicit = Attachment(
            type="widget",
            name="@chart",
            content="widget_id: chart\n\nsymbol: AAPL",
            source="chart",
            auto_attached=False,
        )
        merged = mgr._auto_attach_context_sources([explicit])
        # Only the explicit mention survives — no duplicate
        assert len(merged) == 1
        assert merged[0] is explicit
        assert merged[0].auto_attached is False

    def test_auto_attach_runs_in_user_message_flow(self):
        """End-to-end: a user message with NO explicit @-mention should
        still cause the registered chart context to ride along."""
        mgr = self._make_mgr()
        mgr.register_context_source("chart", "chart")
        captured: list[Any] = []

        def handler(messages, ctx):
            captured.append(list(ctx.attachments))
            return "ok"

        mgr._handler = handler
        mgr._on_user_message(
            {"text": "hi", "threadId": mgr.active_thread_id},
            "chat:user-message",
            "",
        )
        time.sleep(0.3)
        assert captured, "handler was never invoked"
        attachments = captured[0]
        # Exactly one auto-attached widget — the chart
        assert len(attachments) == 1
        att = attachments[0]
        assert att.source == "chart"
        assert att.auto_attached is True
        assert "widget_id: chart" in att.content

    def test_inject_context_skips_ui_card_for_auto_attachments(self, widget):
        """Auto-attached context must NOT spam an ``attach_widget`` card
        on every turn — only explicit @-mentions get the visible card."""
        mgr = ChatManager(handler=echo_handler, enable_context=True)
        mgr.bind(widget)
        mgr.register_context_source("chart", "chart")
        mgr._on_user_message(
            {"text": "hi", "threadId": mgr.active_thread_id},
            "chat:user-message",
            "",
        )
        time.sleep(0.3)
        # No attach_widget tool-call cards from the auto-attach
        attach_cards = [
            d
            for e, d in widget.events
            if e == "chat:tool-call" and d.get("name", "").startswith("attach_")
        ]
        assert attach_cards == []

    def test_inject_context_includes_widget_id_in_user_message(self, widget):
        """The widget_id header must be embedded in the user-message text
        the agent receives so the agent can read it directly."""
        mgr = ChatManager(handler=echo_handler, enable_context=True)
        mgr.bind(widget)
        mgr.register_context_source("chart", "chart")
        captured: list[str] = []

        def handler(messages, ctx):
            captured.append(messages[-1].get("text", ""))
            return "ok"

        mgr._handler = handler
        mgr._on_user_message(
            {"text": "switch to MSFT", "threadId": mgr.active_thread_id},
            "chat:user-message",
            "",
        )
        time.sleep(0.3)
        assert captured
        injected = captured[0]
        # Both the @-context block and the original user text
        assert "widget_id: chart" in injected
        assert "switch to MSFT" in injected
