# pylint: disable=too-many-lines
"""Unit tests for the ChatManager orchestrator.

Tests cover:
- ChatManager construction and defaults
- Protocol response models (StatusResponse, ToolCallResponse, etc.)
- ChatContext dataclass
- SettingsItem and SlashCommandDef models
- callbacks() returns correct keys
- toolbar() returns a Toolbar instance
- send_message() emits and stores messages
- _on_user_message dispatches handler in background thread
- _handle_complete sends complete message
- _handle_stream streams str chunks and rich response types
- _on_stop_generation cancels active generation
- Thread CRUD: create, switch, delete, rename
- _on_request_state emits full initialization state
- _on_settings_change_event updates internal state
- _on_slash_command_event handles /clear + delegates to user callback
"""

# pylint: disable=missing-function-docstring,redefined-outer-name,unused-argument
# pylint: disable=use-implicit-booleaness-not-comparison,too-many-public-methods

from __future__ import annotations

import threading
import time

from typing import Any
from unittest.mock import MagicMock

import pytest

from pywry.chat_manager import (
    ArtifactResponse,
    Attachment,
    ChatContext,
    ChatManager,
    CitationResponse,
    CodeArtifact,
    HtmlArtifact,
    ImageArtifact,
    InputRequiredResponse,
    JsonArtifact,
    MarkdownArtifact,
    PlotlyArtifact,
    SettingsItem,
    SlashCommandDef,
    StatusResponse,
    TableArtifact,
    TextChunkResponse,
    ThinkingResponse,
    TodoItem,
    TodoUpdateResponse,
    ToolCallResponse,
    ToolResultResponse,
    _ArtifactBase,
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
        """Fire-and-forget emit — same as emit for testing."""
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
    """Generator handler that yields rich protocol types."""
    yield ThinkingResponse(text="Analyzing the request...")
    yield ThinkingResponse(text="Considering options.")
    yield StatusResponse(text="Searching...")
    yield ToolCallResponse(name="search", arguments={"q": "test"})
    yield ToolResultResponse(tool_id="call_abc", result="42")
    yield CitationResponse(url="https://example.com", title="Example")
    yield ArtifactResponse(title="code.py", content="print('hi')", language="python")
    yield TextChunkResponse(text="Done!")


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
# Protocol Model Tests
# =============================================================================


class TestProtocolModels:
    """Test protocol response models."""

    def test_status_response(self):
        r = StatusResponse(text="Searching...")
        assert r.type == "status"
        assert r.text == "Searching..."

    def test_tool_call_response(self):
        r = ToolCallResponse(name="search", arguments={"q": "test"})
        assert r.type == "tool_call"
        assert r.name == "search"
        assert r.arguments == {"q": "test"}
        assert r.tool_id.startswith("call_")

    def test_tool_call_custom_id(self):
        r = ToolCallResponse(tool_id="my_id", name="search")
        assert r.tool_id == "my_id"

    def test_tool_result_response(self):
        r = ToolResultResponse(tool_id="call_123", result="42")
        assert r.type == "tool_result"
        assert r.tool_id == "call_123"
        assert r.result == "42"
        assert r.is_error is False

    def test_tool_result_error(self):
        r = ToolResultResponse(tool_id="call_123", result="fail", is_error=True)
        assert r.is_error is True

    def test_citation_response(self):
        r = CitationResponse(url="https://x.com", title="X", snippet="stuff")
        assert r.type == "citation"
        assert r.url == "https://x.com"
        assert r.snippet == "stuff"

    def test_artifact_response(self):
        r = ArtifactResponse(title="code.py", content="print(1)", language="python")
        assert r.type == "artifact"
        assert r.artifact_type == "code"
        assert r.language == "python"

    def test_text_chunk_response(self):
        r = TextChunkResponse(text="hello")
        assert r.type == "text"
        assert r.text == "hello"

    def test_thinking_response(self):
        r = ThinkingResponse(text="analyzing...")
        assert r.type == "thinking"
        assert r.text == "analyzing..."


# =============================================================================
# ChatContext Tests
# =============================================================================


class TestChatContext:
    """Test ChatContext dataclass."""

    def test_defaults(self):
        ctx = ChatContext()
        assert ctx.thread_id == ""
        assert ctx.message_id == ""
        assert ctx.settings == {}
        assert isinstance(ctx.cancel_event, threading.Event)
        assert ctx.system_prompt == ""
        assert ctx.model == ""
        assert ctx.temperature == 0.7

    def test_custom_values(self):
        cancel = threading.Event()
        ctx = ChatContext(
            thread_id="t1",
            message_id="m1",
            settings={"model": "gpt-4"},
            cancel_event=cancel,
            system_prompt="You are helpful",
            model="gpt-4",
            temperature=0.5,
        )
        assert ctx.thread_id == "t1"
        assert ctx.settings["model"] == "gpt-4"
        assert ctx.cancel_event is cancel


# =============================================================================
# SettingsItem Tests
# =============================================================================


class TestSettingsItem:
    """Test SettingsItem model."""

    def test_action(self):
        s = SettingsItem(id="clear", label="Clear", type="action")
        assert s.type == "action"
        assert s.value is None

    def test_toggle(self):
        s = SettingsItem(id="stream", label="Stream", type="toggle", value=True)
        assert s.value is True

    def test_select(self):
        s = SettingsItem(
            id="model",
            label="Model",
            type="select",
            value="gpt-4",
            options=["gpt-4", "gpt-3.5"],
        )
        assert s.options == ["gpt-4", "gpt-3.5"]

    def test_range(self):
        s = SettingsItem(
            id="temp",
            label="Temperature",
            type="range",
            value=0.7,
            min=0,
            max=2,
            step=0.1,
        )
        assert s.min == 0
        assert s.max == 2
        assert s.step == 0.1

    def test_separator(self):
        s = SettingsItem(id="sep", type="separator")
        assert s.type == "separator"
        assert s.label == ""


# =============================================================================
# SlashCommandDef Tests
# =============================================================================


class TestSlashCommandDef:
    """Test SlashCommandDef model."""

    def test_with_slash(self):
        cmd = SlashCommandDef(name="/joke", description="Tell a joke")
        assert cmd.name == "/joke"

    def test_without_slash(self):
        cmd = SlashCommandDef(name="joke", description="Tell a joke")
        assert cmd.name == "/joke"

    def test_empty_description(self):
        cmd = SlashCommandDef(name="/help")
        assert cmd.description == ""


# =============================================================================
# ChatManager Construction Tests
# =============================================================================


class TestChatManagerInit:
    """Test ChatManager initialization."""

    def test_defaults(self):
        mgr = ChatManager(handler=echo_handler)
        assert mgr._system_prompt == ""
        assert mgr._model == ""
        assert mgr._temperature == 0.7
        assert mgr._welcome_message == ""
        assert mgr._settings_items == []
        assert mgr._slash_commands == []
        assert mgr._show_sidebar is True
        assert mgr._show_settings is True
        assert mgr._toolbar_width == "380px"
        assert mgr._collapsible is True
        assert mgr._resizable is True
        assert len(mgr._threads) == 1
        assert mgr._active_thread != ""

    def test_custom_settings(self):
        items = [
            SettingsItem(id="model", label="Model", type="select", value="gpt-4"),
        ]
        mgr = ChatManager(handler=echo_handler, settings=items)
        assert len(mgr._settings_items) == 1
        assert mgr._settings_values == {"model": "gpt-4"}

    def test_custom_slash_commands(self):
        cmds = [SlashCommandDef(name="/joke", description="Joke")]
        mgr = ChatManager(handler=echo_handler, slash_commands=cmds)
        assert len(mgr._slash_commands) == 1

    def test_active_thread_property(self):
        mgr = ChatManager(handler=echo_handler)
        assert mgr.active_thread_id == mgr._active_thread

    def test_settings_property(self):
        items = [SettingsItem(id="k", label="K", type="toggle", value=True)]
        mgr = ChatManager(handler=echo_handler, settings=items)
        assert mgr.settings == {"k": True}

    def test_threads_property(self):
        mgr = ChatManager(handler=echo_handler)
        threads = mgr.threads
        assert len(threads) == 1
        assert all(isinstance(v, list) for v in threads.values())


# =============================================================================
# callbacks() and toolbar() Tests
# =============================================================================


class TestCallbacksAndToolbar:
    """Test callbacks() and toolbar() public methods."""

    def test_callbacks_keys(self, manager):
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
        }
        assert set(cbs.keys()) == expected
        assert all(callable(v) for v in cbs.values())

    def test_toolbar_returns_toolbar(self, manager):
        tb = manager.toolbar()
        from pywry.toolbar import Toolbar

        assert isinstance(tb, Toolbar)

    def test_toolbar_position(self, manager):
        tb = manager.toolbar(position="left")
        assert tb.position == "left"


# =============================================================================
# bind() Tests
# =============================================================================


class TestBind:
    """Test bind()."""

    def test_bind_sets_widget(self, manager, widget):
        assert manager._widget is None
        manager.bind(widget)
        assert manager._widget is widget


# =============================================================================
# send_message() Tests
# =============================================================================


class TestSendMessage:
    """Test send_message() public helper."""

    def test_sends_and_stores(self, bound_manager, widget):
        thread_id = bound_manager.active_thread_id
        bound_manager.send_message("Hello!", thread_id)

        events = widget.get_events("chat:assistant-message")
        assert len(events) == 1
        assert events[0]["text"] == "Hello!"
        assert events[0]["threadId"] == thread_id

        # Message stored in thread history
        msgs = bound_manager._threads[thread_id]
        assert len(msgs) == 1
        assert msgs[0]["role"] == "assistant"
        assert msgs[0]["text"] == "Hello!"

    def test_defaults_to_active_thread(self, bound_manager, widget):
        bound_manager.send_message("Hi")
        events = widget.get_events("chat:assistant-message")
        assert events[0]["threadId"] == bound_manager.active_thread_id


# =============================================================================
# _on_user_message Tests
# =============================================================================


class TestOnUserMessage:
    """Test _on_user_message event handler."""

    def test_empty_text_ignored(self, bound_manager, widget):
        bound_manager._on_user_message({"text": ""}, "", "")
        assert len(widget.events) == 0

    def test_stores_user_message(self, bound_manager):
        tid = bound_manager.active_thread_id
        bound_manager._on_user_message({"text": "Hi", "threadId": tid}, "", "")
        msgs = bound_manager._threads[tid]
        assert any(m["role"] == "user" and m["text"] == "Hi" for m in msgs)

    def test_handler_runs_in_thread(self, widget):
        """Verify the handler is called and produces output."""
        mgr = ChatManager(handler=echo_handler)
        mgr.bind(widget)
        tid = mgr.active_thread_id

        mgr._on_user_message({"text": "Hello", "threadId": tid}, "", "")
        # Wait for background thread to finish
        time.sleep(0.5)

        # Should have typing indicator on/off + assistant message
        assistant_msgs = widget.get_events("chat:assistant-message")
        assert len(assistant_msgs) == 1
        assert "Echo: Hello" in assistant_msgs[0]["text"]


# =============================================================================
# _handle_complete Tests
# =============================================================================


class TestHandleComplete:
    """Test _handle_complete sends a full message."""

    def test_emits_and_stores(self, bound_manager, widget):
        tid = bound_manager.active_thread_id
        bound_manager._handle_complete("Full response", "msg_001", tid)

        events = widget.get_events("chat:assistant-message")
        assert len(events) == 1
        assert events[0]["text"] == "Full response"
        assert events[0]["messageId"] == "msg_001"

        msgs = bound_manager._threads[tid]
        assert len(msgs) == 1
        assert msgs[0]["text"] == "Full response"


# =============================================================================
# _handle_stream Tests
# =============================================================================


class TestHandleStream:
    """Test _handle_stream with various response types."""

    def test_string_chunks(self, bound_manager, widget):
        tid = bound_manager.active_thread_id
        cancel = threading.Event()

        def gen():
            yield "Hello "
            yield "World"

        bound_manager._handle_stream(gen(), "msg_001", tid, cancel)

        chunks = widget.get_events("chat:stream-chunk")
        # "Hello ", "World", and final done chunk
        assert len(chunks) == 3
        assert chunks[0]["chunk"] == "Hello "
        assert chunks[1]["chunk"] == "World"
        assert chunks[2]["done"] is True

        # Full text stored
        msgs = bound_manager._threads[tid]
        assert msgs[0]["text"] == "Hello World"

    def test_text_chunk_response(self, bound_manager, widget):
        tid = bound_manager.active_thread_id
        cancel = threading.Event()

        def gen():
            yield TextChunkResponse(text="Chunk1")
            yield TextChunkResponse(text="Chunk2")

        bound_manager._handle_stream(gen(), "msg_001", tid, cancel)

        chunks = widget.get_events("chat:stream-chunk")
        assert chunks[0]["chunk"] == "Chunk1"
        assert chunks[1]["chunk"] == "Chunk2"

    def test_status_response(self, bound_manager, widget):
        tid = bound_manager.active_thread_id
        cancel = threading.Event()

        def gen():
            yield StatusResponse(text="Searching...")
            yield "result"

        bound_manager._handle_stream(gen(), "msg_001", tid, cancel)

        statuses = widget.get_events("chat:status-update")
        assert len(statuses) == 1
        assert statuses[0]["text"] == "Searching..."

    def test_tool_call_response(self, bound_manager, widget):
        tid = bound_manager.active_thread_id
        cancel = threading.Event()

        def gen():
            yield ToolCallResponse(tool_id="tc1", name="search", arguments={"q": "test"})

        bound_manager._handle_stream(gen(), "msg_001", tid, cancel)

        tools = widget.get_events("chat:tool-call")
        assert len(tools) == 1
        assert tools[0]["name"] == "search"
        assert tools[0]["toolId"] == "tc1"

    def test_tool_result_response(self, bound_manager, widget):
        tid = bound_manager.active_thread_id
        cancel = threading.Event()

        def gen():
            yield ToolResultResponse(tool_id="tc1", result="42")

        bound_manager._handle_stream(gen(), "msg_001", tid, cancel)

        results = widget.get_events("chat:tool-result")
        assert len(results) == 1
        assert results[0]["result"] == "42"
        assert results[0]["isError"] is False

    def test_citation_response(self, bound_manager, widget):
        tid = bound_manager.active_thread_id
        cancel = threading.Event()

        def gen():
            yield CitationResponse(url="https://x.com", title="X", snippet="s")

        bound_manager._handle_stream(gen(), "msg_001", tid, cancel)

        citations = widget.get_events("chat:citation")
        assert len(citations) == 1
        assert citations[0]["url"] == "https://x.com"

    def test_artifact_response(self, bound_manager, widget):
        tid = bound_manager.active_thread_id
        cancel = threading.Event()

        def gen():
            yield ArtifactResponse(title="code.py", content="print(1)", language="python")

        bound_manager._handle_stream(gen(), "msg_001", tid, cancel)

        artifacts = widget.get_events("chat:artifact")
        assert len(artifacts) == 1
        assert artifacts[0]["title"] == "code.py"
        assert artifacts[0]["language"] == "python"

    def test_cancellation(self, bound_manager, widget):
        tid = bound_manager.active_thread_id
        cancel = threading.Event()

        def gen():
            yield "partial "
            cancel.set()
            yield "ignored"

        bound_manager._handle_stream(gen(), "msg_001", tid, cancel)

        chunks = widget.get_events("chat:stream-chunk")
        # First chunk + done-with-stopped
        done_chunks = [c for c in chunks if c.get("done")]
        assert any(c.get("stopped") for c in done_chunks)

    def test_thinking_response(self, bound_manager, widget):
        tid = bound_manager.active_thread_id
        cancel = threading.Event()

        def gen():
            yield ThinkingResponse(text="Step 1...")
            yield ThinkingResponse(text="Step 2...")
            yield "Answer"

        bound_manager._handle_stream(gen(), "msg_001", tid, cancel)

        thinking_events = widget.get_events("chat:thinking-chunk")
        assert len(thinking_events) == 2
        assert thinking_events[0]["text"] == "Step 1..."
        assert thinking_events[1]["text"] == "Step 2..."

        # Thinking done is emitted at end of stream
        done_events = widget.get_events("chat:thinking-done")
        assert len(done_events) == 1

        # Thinking is NOT in the stored text
        msgs = bound_manager._threads[tid]
        assert msgs[0]["text"] == "Answer"

    def test_rich_handler_all_types(self, widget):
        """Verify rich_handler emits all protocol types."""
        mgr = ChatManager(handler=rich_handler)
        mgr.bind(widget)
        tid = mgr.active_thread_id
        cancel = threading.Event()

        mgr._handle_stream(rich_handler([], None), "msg_001", tid, cancel)

        assert len(widget.get_events("chat:thinking-chunk")) == 2
        assert len(widget.get_events("chat:status-update")) == 1
        assert len(widget.get_events("chat:tool-call")) == 1
        assert len(widget.get_events("chat:tool-result")) == 1
        assert len(widget.get_events("chat:citation")) == 1
        assert len(widget.get_events("chat:artifact")) == 1
        assert len(widget.get_events("chat:thinking-done")) == 1
        assert widget.get_events("chat:stream-chunk")[-1]["done"] is True


# =============================================================================
# _on_stop_generation Tests
# =============================================================================


class TestStopGeneration:
    """Test _on_stop_generation."""

    def test_sets_cancel_event(self, bound_manager):
        cancel = threading.Event()
        tid = bound_manager.active_thread_id
        bound_manager._cancel_events[tid] = cancel
        assert not cancel.is_set()

        bound_manager._on_stop_generation({"threadId": tid}, "", "")
        assert cancel.is_set()

    def test_no_crash_on_missing_thread(self, bound_manager):
        # Should not raise
        bound_manager._on_stop_generation({"threadId": "nonexistent"}, "", "")


# =============================================================================
# Thread CRUD Tests
# =============================================================================


class TestThreadCRUD:
    """Test thread create, switch, delete, rename."""

    def test_create_thread(self, bound_manager, widget):
        old_count = len(bound_manager._threads)
        bound_manager._on_thread_create({}, "", "")

        assert len(bound_manager._threads) == old_count + 1
        # Active thread switched to new one
        assert bound_manager.active_thread_id != ""
        # Events emitted
        assert len(widget.get_events("chat:update-thread-list")) == 1
        assert len(widget.get_events("chat:switch-thread")) == 1

    def test_create_with_title(self, bound_manager, widget):
        bound_manager._on_thread_create({"title": "My Thread"}, "", "")
        new_tid = bound_manager.active_thread_id
        assert bound_manager._thread_titles[new_tid] == "My Thread"

    def test_switch_thread(self, bound_manager, widget):
        # Create a second thread
        bound_manager._on_thread_create({}, "", "")
        second_tid = bound_manager.active_thread_id
        first_tid = next(t for t in bound_manager._threads if t != second_tid)

        widget.clear()
        bound_manager._on_thread_switch({"threadId": first_tid}, "", "")

        assert bound_manager.active_thread_id == first_tid
        assert len(widget.get_events("chat:switch-thread")) == 1

    def test_switch_nonexistent_thread(self, bound_manager, widget):
        old = bound_manager.active_thread_id
        bound_manager._on_thread_switch({"threadId": "nonexistent"}, "", "")
        assert bound_manager.active_thread_id == old

    def test_delete_thread(self, bound_manager, widget):
        # Create a second thread so deletion doesn't leave empty
        bound_manager._on_thread_create({}, "", "")
        second_tid = bound_manager.active_thread_id
        widget.clear()

        bound_manager._on_thread_delete({"threadId": second_tid}, "", "")

        assert second_tid not in bound_manager._threads
        assert len(widget.get_events("chat:update-thread-list")) == 1

    def test_delete_active_switches(self, bound_manager, widget):
        # Create two threads, delete the active one
        first_tid = bound_manager.active_thread_id
        bound_manager._on_thread_create({}, "", "")
        second_tid = bound_manager.active_thread_id
        widget.clear()

        bound_manager._on_thread_delete({"threadId": second_tid}, "", "")
        assert bound_manager.active_thread_id == first_tid

    def test_rename_thread(self, bound_manager, widget):
        tid = bound_manager.active_thread_id
        bound_manager._on_thread_rename({"threadId": tid, "title": "New Name"}, "", "")
        assert bound_manager._thread_titles[tid] == "New Name"
        assert len(widget.get_events("chat:update-thread-list")) == 1


# =============================================================================
# _on_settings_change_event Tests
# =============================================================================


class TestSettingsChange:
    """Test settings change handler."""

    def test_updates_value(self, bound_manager):
        bound_manager._on_settings_change_event({"key": "model", "value": "claude-3"}, "", "")
        assert bound_manager._settings_values["model"] == "claude-3"

    def test_clear_history_action(self, bound_manager, widget):
        tid = bound_manager.active_thread_id
        bound_manager._threads[tid] = [{"role": "user", "text": "hi"}]

        bound_manager._on_settings_change_event({"key": "clear-history"}, "", "")
        assert bound_manager._threads[tid] == []
        assert len(widget.get_events("chat:clear")) == 1

    def test_delegates_to_callback(self):
        callback = MagicMock()
        mgr = ChatManager(handler=echo_handler, on_settings_change=callback)
        mgr.bind(FakeWidget())

        mgr._on_settings_change_event({"key": "model", "value": "gpt-4"}, "", "")
        callback.assert_called_once_with("model", "gpt-4")


# =============================================================================
# _on_slash_command_event Tests
# =============================================================================


class TestSlashCommand:
    """Test slash command handler."""

    def test_builtin_clear(self, bound_manager, widget):
        tid = bound_manager.active_thread_id
        bound_manager._threads[tid] = [{"role": "user", "text": "hi"}]

        bound_manager._on_slash_command_event({"command": "/clear", "threadId": tid}, "", "")
        assert bound_manager._threads[tid] == []
        assert len(widget.get_events("chat:clear")) == 1

    def test_delegates_to_callback(self):
        callback = MagicMock()
        mgr = ChatManager(handler=echo_handler, on_slash_command=callback)
        mgr.bind(FakeWidget())
        tid = mgr.active_thread_id

        mgr._on_slash_command_event({"command": "/joke", "args": "", "threadId": tid}, "", "")
        callback.assert_called_once_with("/joke", "", tid)


# =============================================================================
# _on_request_state Tests
# =============================================================================


class TestRequestState:
    """Test state initialization response."""

    def test_emits_state_response(self, bound_manager, widget):
        bound_manager._on_request_state({}, "", "")

        states = widget.get_events("chat:state-response")
        assert len(states) == 1
        assert "threads" in states[0]
        assert "activeThreadId" in states[0]

    def test_registers_slash_commands(self):
        cmds = [SlashCommandDef(name="/joke", description="Joke")]
        mgr = ChatManager(handler=echo_handler, slash_commands=cmds)
        w = FakeWidget()
        mgr.bind(w)

        mgr._on_request_state({}, "", "")

        registered = w.get_events("chat:register-command")
        names = [r["name"] for r in registered]
        assert "/joke" in names
        assert "/clear" in names  # always registered

    def test_registers_settings(self):
        items = [SettingsItem(id="model", label="Model", type="select", value="gpt-4")]
        mgr = ChatManager(handler=echo_handler, settings=items)
        w = FakeWidget()
        mgr.bind(w)

        mgr._on_request_state({}, "", "")

        settings = w.get_events("chat:register-settings-item")
        assert len(settings) == 1
        assert settings[0]["id"] == "model"

    def test_sends_welcome_message(self):
        mgr = ChatManager(handler=echo_handler, welcome_message="Welcome!")
        w = FakeWidget()
        mgr.bind(w)

        mgr._on_request_state({}, "", "")

        states = w.get_events("chat:state-response")
        assert len(states) == 1
        assert len(states[0]["messages"]) == 1
        assert states[0]["messages"][0]["content"] == "Welcome!"

    def test_no_welcome_if_empty(self, bound_manager, widget):
        bound_manager._on_request_state({}, "", "")

        states = widget.get_events("chat:state-response")
        assert len(states) == 1
        assert len(states[0]["messages"]) == 0

    def test_eager_aggrid_injection(self):
        """include_aggrid=True marks assets as already sent (page template loads them)."""
        mgr = ChatManager(handler=echo_handler, include_aggrid=True)
        w = FakeWidget()
        mgr.bind(w)

        # Assets are already on the page — _on_request_state must NOT re-inject.
        mgr._on_request_state({}, "", "")

        assets = w.get_events("chat:load-assets")
        assert len(assets) == 0
        assert mgr._aggrid_assets_sent is True

    def test_eager_plotly_injection(self):
        """include_plotly=True marks assets as already sent (page template loads them)."""
        mgr = ChatManager(handler=echo_handler, include_plotly=True)
        w = FakeWidget()
        mgr.bind(w)

        mgr._on_request_state({}, "", "")

        assets = w.get_events("chat:load-assets")
        assert len(assets) == 0
        assert mgr._plotly_assets_sent is True

    def test_eager_both_injection(self):
        """Both include flags mark both asset sets as sent — no re-injection."""
        mgr = ChatManager(handler=echo_handler, include_aggrid=True, include_plotly=True)
        w = FakeWidget()
        mgr.bind(w)

        mgr._on_request_state({}, "", "")

        assets = w.get_events("chat:load-assets")
        assert len(assets) == 0

    def test_no_eager_injection_by_default(self, bound_manager, widget):
        """Without include flags, no assets are injected on request-state."""
        bound_manager._on_request_state({}, "", "")

        assets = widget.get_events("chat:load-assets")
        assert len(assets) == 0

    def test_custom_aggrid_theme(self):
        """aggrid_theme parameter is used when injecting assets."""
        mgr = ChatManager(handler=echo_handler, include_aggrid=True, aggrid_theme="quartz")
        assert mgr._aggrid_theme == "quartz"


# =============================================================================
# _build_thread_list Tests
# =============================================================================


class TestBuildThreadList:
    """Test _build_thread_list helper."""

    def test_returns_list_of_dicts(self, manager):
        result = manager._build_thread_list()
        assert len(result) == 1
        assert "thread_id" in result[0]
        assert "title" in result[0]

    def test_uses_custom_titles(self, manager):
        tid = manager.active_thread_id
        manager._thread_titles[tid] = "Custom Title"
        result = manager._build_thread_list()
        assert result[0]["title"] == "Custom Title"


# =============================================================================
# Error handling in _run_handler Tests
# =============================================================================


class TestRunHandlerErrors:
    """Test error handling in _run_handler."""

    def test_handler_exception_sends_error_message(self):
        def bad_handler(messages, ctx):
            raise ValueError("Something broke")

        mgr = ChatManager(handler=bad_handler)
        w = FakeWidget()
        mgr.bind(w)
        tid = mgr.active_thread_id

        mgr._on_user_message({"text": "Hi", "threadId": tid}, "", "")
        time.sleep(0.5)

        msgs = w.get_events("chat:assistant-message")
        assert len(msgs) == 1
        assert "Something broke" in msgs[0]["text"]

    def test_generator_exception_sends_error(self):
        def broken_gen(messages, ctx):
            yield "partial"
            raise RuntimeError("Stream error")

        mgr = ChatManager(handler=broken_gen)
        w = FakeWidget()
        mgr.bind(w)
        tid = mgr.active_thread_id

        mgr._on_user_message({"text": "Hi", "threadId": tid}, "", "")
        time.sleep(0.5)

        msgs = w.get_events("chat:assistant-message")
        assert any("Stream error" in m.get("text", "") for m in msgs)


# =============================================================================
# Integration: streaming handler end-to-end
# =============================================================================


class TestStreamingIntegration:
    """End-to-end streaming handler test."""

    def test_stream_handler_produces_chunks(self):
        mgr = ChatManager(handler=stream_handler)
        w = FakeWidget()
        mgr.bind(w)
        tid = mgr.active_thread_id

        mgr._on_user_message({"text": "Hello World", "threadId": tid}, "", "")
        time.sleep(0.5)

        chunks = w.get_events("chat:stream-chunk")
        assert len(chunks) >= 3  # "Hello ", "World", done
        done_chunks = [c for c in chunks if c.get("done")]
        assert len(done_chunks) == 1

        # Full text stored
        msgs = mgr._threads[tid]
        assistant_msgs = [m for m in msgs if m["role"] == "assistant"]
        assert len(assistant_msgs) == 1
        assert assistant_msgs[0]["text"] == "Hello World"


# =============================================================================
# TodoItem and TodoUpdateResponse Tests
# =============================================================================


class TestTodoItem:
    """Test TodoItem model."""

    def test_defaults(self):
        item = TodoItem(id=1, title="Do something")
        assert item.id == 1
        assert item.title == "Do something"
        assert item.status == "not-started"

    def test_statuses(self):
        for status in ["not-started", "in-progress", "completed"]:
            item = TodoItem(id=1, title="test", status=status)
            assert item.status == status

    def test_string_id(self):
        item = TodoItem(id="task-abc", title="test")
        assert item.id == "task-abc"


class TestTodoUpdateResponse:
    """Test TodoUpdateResponse model."""

    def test_empty(self):
        r = TodoUpdateResponse()
        assert r.type == "todo"
        assert r.items == []

    def test_with_items(self):
        r = TodoUpdateResponse(
            items=[
                TodoItem(id=1, title="A", status="completed"),
                TodoItem(id=2, title="B", status="in-progress"),
            ]
        )
        assert len(r.items) == 2
        assert r.items[0].status == "completed"


class TestTodoManagement:
    """Test ChatManager todo public API."""

    def test_update_todos(self, widget):
        mgr = ChatManager(handler=echo_handler)
        mgr.bind(widget)

        items = [
            TodoItem(id=1, title="Step 1", status="completed"),
            TodoItem(id=2, title="Step 2", status="in-progress"),
        ]
        mgr.update_todos(items)

        events = widget.get_events("chat:todo-update")
        assert len(events) == 1
        assert len(events[0]["items"]) == 2
        assert events[0]["items"][0]["title"] == "Step 1"
        assert mgr._todo_items == items

    def test_clear_todos(self, widget):
        mgr = ChatManager(handler=echo_handler)
        mgr.bind(widget)
        mgr.update_todos([TodoItem(id=1, title="X")])
        widget.clear()

        mgr.clear_todos()

        events = widget.get_events("chat:todo-update")
        assert len(events) == 1
        assert events[0]["items"] == []
        assert mgr._todo_items == []

    def test_on_todo_clear_callback(self, widget):
        mgr = ChatManager(handler=echo_handler)
        mgr.bind(widget)
        mgr._todo_items = [TodoItem(id=1, title="X")]

        mgr._on_todo_clear({}, "", "")

        assert mgr._todo_items == []
        events = widget.get_events("chat:todo-update")
        assert events[0]["items"] == []

    def test_todo_in_callbacks(self):
        mgr = ChatManager(handler=echo_handler)
        cbs = mgr.callbacks()
        assert "chat:todo-clear" in cbs

    def test_todo_update_response_in_stream(self, widget):
        """Verify TodoUpdateResponse is dispatched during streaming."""

        def todo_handler(messages, ctx):
            yield TodoUpdateResponse(
                items=[
                    TodoItem(id=1, title="Thinking", status="in-progress"),
                ]
            )
            yield "Hello"
            yield TodoUpdateResponse(
                items=[
                    TodoItem(id=1, title="Thinking", status="completed"),
                ]
            )

        mgr = ChatManager(handler=todo_handler)
        mgr.bind(widget)
        tid = mgr.active_thread_id
        cancel = threading.Event()

        mgr._handle_stream(todo_handler([], None), "msg_001", tid, cancel)

        todo_events = widget.get_events("chat:todo-update")
        assert len(todo_events) == 2
        assert todo_events[0]["items"][0]["status"] == "in-progress"
        assert todo_events[1]["items"][0]["status"] == "completed"

        # Todo is NOT stored in message history
        msgs = mgr._threads[tid]
        assert msgs[0]["text"] == "Hello"

    def test_todo_items_stored_in_manager(self, widget):
        """Verify _todo_items is updated when TodoUpdateResponse is streamed."""

        def handler(messages, ctx):
            yield TodoUpdateResponse(
                items=[
                    TodoItem(id=1, title="A"),
                    TodoItem(id=2, title="B"),
                ]
            )

        mgr = ChatManager(handler=handler)
        mgr.bind(widget)
        tid = mgr.active_thread_id
        cancel = threading.Event()

        mgr._handle_stream(handler([], None), "msg_001", tid, cancel)
        assert len(mgr._todo_items) == 2


# =============================================================================
# InputRequiredResponse Tests
# =============================================================================


class TestInputRequiredResponse:
    """Test InputRequiredResponse model."""

    def test_defaults(self):
        r = InputRequiredResponse()
        assert r.type == "input_required"
        assert r.prompt == ""
        assert r.placeholder == "Type your response..."
        assert r.request_id.startswith("input_")
        assert r.input_type == "text"
        assert r.options is None

    def test_custom_values(self):
        r = InputRequiredResponse(
            prompt="Which file?",
            placeholder="Enter filename...",
            request_id="req_custom",
        )
        assert r.prompt == "Which file?"
        assert r.placeholder == "Enter filename..."
        assert r.request_id == "req_custom"

    def test_buttons_type(self):
        r = InputRequiredResponse(
            prompt="Approve?",
            input_type="buttons",
        )
        assert r.input_type == "buttons"
        assert r.options is None

    def test_buttons_with_custom_options(self):
        r = InputRequiredResponse(
            prompt="Pick one",
            input_type="buttons",
            options=["Accept", "Reject", "Skip"],
        )
        assert r.input_type == "buttons"
        assert r.options == ["Accept", "Reject", "Skip"]

    def test_radio_type(self):
        r = InputRequiredResponse(
            prompt="Select model:",
            input_type="radio",
            options=["GPT-4", "Claude", "Gemini"],
        )
        assert r.input_type == "radio"
        assert r.options == ["GPT-4", "Claude", "Gemini"]


class TestWaitForInput:
    """Test ChatContext.wait_for_input()."""

    def test_returns_response_text(self):
        ctx = ChatContext()
        ctx._input_response = "yes"
        ctx._input_event.set()

        result = ctx.wait_for_input()
        assert result == "yes"
        # Event is cleared after reading
        assert not ctx._input_event.is_set()
        # Response is cleared
        assert ctx._input_response == ""

    def test_returns_empty_on_cancel(self):
        ctx = ChatContext()
        ctx.cancel_event.set()

        result = ctx.wait_for_input()
        assert result == ""

    def test_returns_empty_on_timeout(self):
        ctx = ChatContext()
        result = ctx.wait_for_input(timeout=0.1)
        assert result == ""

    def test_blocks_until_set(self):
        ctx = ChatContext()

        def _set_later():
            time.sleep(0.1)
            ctx._input_response = "answer"
            ctx._input_event.set()

        t = threading.Thread(target=_set_later, daemon=True)
        t.start()

        result = ctx.wait_for_input()
        assert result == "answer"


class TestOnInputResponse:
    """Test ChatManager._on_input_response callback."""

    def test_resumes_handler(self, widget):
        ctx = ChatContext()
        mgr = ChatManager(handler=echo_handler)
        mgr.bind(widget)
        tid = mgr.active_thread_id

        # Simulate a pending input request
        mgr._pending_inputs["req_001"] = {
            "ctx": ctx,
            "thread_id": tid,
        }

        mgr._on_input_response(
            {"requestId": "req_001", "text": "yes", "threadId": tid},
            "",
            "",
        )

        # Context should have the response
        assert ctx._input_response == "yes"
        assert ctx._input_event.is_set()

        # Pending input cleared
        assert "req_001" not in mgr._pending_inputs

        # User response stored in thread history
        msgs = mgr._threads[tid]
        assert any(m["role"] == "user" and m["text"] == "yes" for m in msgs)

    def test_unknown_request_id_ignored(self, widget):
        mgr = ChatManager(handler=echo_handler)
        mgr.bind(widget)

        # Should not raise
        mgr._on_input_response({"requestId": "nonexistent", "text": "hello"}, "", "")

    def test_input_response_in_callbacks(self):
        mgr = ChatManager(handler=echo_handler)
        cbs = mgr.callbacks()
        assert "chat:input-response" in cbs


class TestInputRequiredInStream:
    """Test InputRequiredResponse dispatch in _handle_stream."""

    def test_finalizes_stream_and_emits_event(self, widget):
        """Verify stream is finalized and input-required event emitted."""
        ctx = ChatContext()

        def handler(messages, c):
            yield "Before question "
            yield InputRequiredResponse(
                prompt="Pick one",
                placeholder="A or B",
                request_id="req_test",
            )
            answer = ctx.wait_for_input(timeout=2.0)
            yield f"You picked: {answer}"

        mgr = ChatManager(handler=handler)
        mgr.bind(widget)
        tid = mgr.active_thread_id
        cancel = threading.Event()

        # Run in thread so we can simulate user response
        t = threading.Thread(
            target=mgr._handle_stream,
            args=(handler([], ctx), "msg_001", tid, cancel),
            kwargs={"ctx": ctx},
            daemon=True,
        )
        t.start()

        # Wait for input-required event
        for _ in range(50):
            if widget.get_events("chat:input-required"):
                break
            time.sleep(0.05)

        # Simulate user response
        ctx._input_response = "user answer"
        ctx._input_event.set()
        t.join(timeout=3.0)

        # Stream chunk done emitted (finalizing first batch)
        done_chunks = [c for c in widget.get_events("chat:stream-chunk") if c.get("done")]
        assert len(done_chunks) >= 1

        # Input-required event emitted
        ir_events = widget.get_events("chat:input-required")
        assert len(ir_events) == 1
        assert ir_events[0]["requestId"] == "req_test"
        assert ir_events[0]["prompt"] == "Pick one"
        assert ir_events[0]["placeholder"] == "A or B"
        assert ir_events[0]["inputType"] == "text"
        assert ir_events[0]["options"] == []

        # Thinking-done emitted to collapse any open block
        assert len(widget.get_events("chat:thinking-done")) >= 1

        # First batch stored in history
        msgs = mgr._threads[tid]
        first_msg = [m for m in msgs if m.get("text") == "Before question "]
        assert len(first_msg) == 1

    def test_continuation_uses_new_message_id(self, widget):
        """After input, streaming continues with a new message ID."""
        ctx = ChatContext()

        def handler(messages, c):
            yield "Part 1"
            yield InputRequiredResponse(request_id="req_x")
            ctx.wait_for_input(timeout=2.0)
            yield "Part 2"

        mgr = ChatManager(handler=handler)
        mgr.bind(widget)
        tid = mgr.active_thread_id
        cancel = threading.Event()

        t = threading.Thread(
            target=mgr._handle_stream,
            args=(handler([], ctx), "msg_001", tid, cancel),
            kwargs={"ctx": ctx},
            daemon=True,
        )
        t.start()

        for _ in range(50):
            if widget.get_events("chat:input-required"):
                break
            time.sleep(0.05)

        ctx._input_response = "yes"
        ctx._input_event.set()
        t.join(timeout=3.0)

        # Collect all stream-chunk messageIds
        chunks = widget.get_events("chat:stream-chunk")
        message_ids = {c["messageId"] for c in chunks}
        # Should have at least 2 different message IDs
        assert len(message_ids) >= 2

    def test_stores_pending_input(self, widget):
        """Verify pending input is stored for lookup by _on_input_response."""
        ctx = ChatContext()

        def handler(messages, c):
            yield InputRequiredResponse(request_id="req_pending")
            # Block forever — test won't reach here
            ctx.wait_for_input(timeout=0.05)

        mgr = ChatManager(handler=handler)
        mgr.bind(widget)
        tid = mgr.active_thread_id
        cancel = threading.Event()

        mgr._handle_stream(handler([], ctx), "msg_001", tid, cancel, ctx=ctx)

        # After handler times out, pending_inputs should have been
        # populated (and may still be there if not consumed)
        # The input-required event was emitted
        ir_events = widget.get_events("chat:input-required")
        assert len(ir_events) == 1
        assert ir_events[0]["requestId"] == "req_pending"

    def test_buttons_type_in_stream(self, widget):
        """Verify buttons input_type and options are emitted."""
        ctx = ChatContext()

        def handler(messages, c):
            yield InputRequiredResponse(
                prompt="Approve?",
                input_type="buttons",
                options=["Accept", "Reject"],
                request_id="req_btn",
            )
            ctx.wait_for_input(timeout=0.1)

        mgr = ChatManager(handler=handler)
        mgr.bind(widget)
        tid = mgr.active_thread_id
        cancel = threading.Event()

        mgr._handle_stream(handler([], ctx), "msg_001", tid, cancel, ctx=ctx)

        ir_events = widget.get_events("chat:input-required")
        assert len(ir_events) == 1
        assert ir_events[0]["inputType"] == "buttons"
        assert ir_events[0]["options"] == ["Accept", "Reject"]

    def test_radio_type_in_stream(self, widget):
        """Verify radio input_type and options are emitted."""
        ctx = ChatContext()

        def handler(messages, c):
            yield InputRequiredResponse(
                prompt="Select model:",
                input_type="radio",
                options=["GPT-4", "Claude", "Gemini"],
                request_id="req_radio",
            )
            ctx.wait_for_input(timeout=0.1)

        mgr = ChatManager(handler=handler)
        mgr.bind(widget)
        tid = mgr.active_thread_id
        cancel = threading.Event()

        mgr._handle_stream(handler([], ctx), "msg_001", tid, cancel, ctx=ctx)

        ir_events = widget.get_events("chat:input-required")
        assert len(ir_events) == 1
        assert ir_events[0]["inputType"] == "radio"
        assert ir_events[0]["options"] == ["GPT-4", "Claude", "Gemini"]

    def test_default_options_empty_list(self, widget):
        """When options is None, emitted data should have empty list."""
        ctx = ChatContext()

        def handler(messages, c):
            yield InputRequiredResponse(request_id="req_def")
            ctx.wait_for_input(timeout=0.1)

        mgr = ChatManager(handler=handler)
        mgr.bind(widget)
        tid = mgr.active_thread_id
        cancel = threading.Event()

        mgr._handle_stream(handler([], ctx), "msg_001", tid, cancel, ctx=ctx)

        ir_events = widget.get_events("chat:input-required")
        assert ir_events[0]["inputType"] == "text"
        assert ir_events[0]["options"] == []

    def test_e2e_input_required_response_flow(self, widget):
        """Full integration: InputRequired → user responds → handler continues."""
        ctx = ChatContext()

        def handler(messages, c):
            yield "Question: "
            yield InputRequiredResponse(
                prompt="Yes or no?",
                request_id="req_e2e",
            )
            answer = ctx.wait_for_input()
            yield f"Answer: {answer}"

        mgr = ChatManager(handler=handler)
        mgr.bind(widget)
        tid = mgr.active_thread_id
        cancel = threading.Event()

        # Run in a thread since _handle_stream will block at wait_for_input
        stream_thread = threading.Thread(
            target=mgr._handle_stream,
            args=(handler([], ctx), "msg_001", tid, cancel),
            kwargs={"ctx": ctx},
            daemon=True,
        )
        stream_thread.start()

        # Wait for the input-required event to be emitted
        for _ in range(50):
            if widget.get_events("chat:input-required"):
                break
            time.sleep(0.05)

        # Simulate user responding
        mgr._on_input_response(
            {"requestId": "req_e2e", "text": "yes", "threadId": tid},
            "",
            "",
        )

        stream_thread.join(timeout=2.0)
        assert not stream_thread.is_alive()

        # Verify the full conversation history
        msgs = mgr._threads[tid]
        texts = [m["text"] for m in msgs]
        assert "Question: " in texts
        assert "yes" in texts  # user response
        assert "Answer: yes" in texts  # handler continuation


# =============================================================================
# Artifact Model Tests — All Artifact Types
# =============================================================================


class TestArtifactModels:
    """Test each artifact model's defaults, type literals, and fields."""

    def test_artifact_base(self):
        a = _ArtifactBase()
        assert a.type == "artifact"
        assert a.title == ""

    def test_code_artifact_defaults(self):
        a = CodeArtifact()
        assert a.type == "artifact"
        assert a.artifact_type == "code"
        assert a.content == ""
        assert a.language == ""

    def test_code_artifact_fields(self):
        a = CodeArtifact(title="main.py", content="print(1)", language="python")
        assert a.title == "main.py"
        assert a.content == "print(1)"
        assert a.language == "python"

    def test_artifact_response_is_code_artifact(self):
        assert ArtifactResponse is CodeArtifact

    def test_markdown_artifact_defaults(self):
        a = MarkdownArtifact()
        assert a.artifact_type == "markdown"
        assert a.content == ""

    def test_markdown_artifact_fields(self):
        a = MarkdownArtifact(title="Notes", content="# Heading\n\nParagraph.")
        assert a.title == "Notes"
        assert a.content == "# Heading\n\nParagraph."

    def test_html_artifact_defaults(self):
        a = HtmlArtifact()
        assert a.artifact_type == "html"
        assert a.content == ""

    def test_html_artifact_fields(self):
        a = HtmlArtifact(title="Page", content="<h1>Hello</h1>")
        assert a.content == "<h1>Hello</h1>"

    def test_table_artifact_defaults(self):
        a = TableArtifact()
        assert a.artifact_type == "table"
        assert a.data == []
        assert a.column_defs is None
        assert a.grid_options is None
        assert a.height == "400px"

    def test_table_artifact_with_data(self):
        rows = [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]
        a = TableArtifact(title="Users", data=rows, height="300px")
        assert a.data == rows
        assert a.height == "300px"

    def test_table_artifact_with_column_defs(self):
        cols = [{"field": "name"}, {"field": "age"}]
        a = TableArtifact(data=[], column_defs=cols)
        assert a.column_defs == cols

    def test_table_artifact_with_grid_options(self):
        opts = {"pagination": True, "paginationPageSize": 10}
        a = TableArtifact(data=[], grid_options=opts)
        assert a.grid_options == opts

    def test_plotly_artifact_defaults(self):
        a = PlotlyArtifact()
        assert a.artifact_type == "plotly"
        assert a.figure == {}
        assert a.height == "400px"

    def test_plotly_artifact_with_figure(self):
        fig = {
            "data": [{"x": [1, 2], "y": [3, 4], "type": "scatter"}],
            "layout": {"title": "Test"},
        }
        a = PlotlyArtifact(title="Chart", figure=fig, height="500px")
        assert a.figure == fig
        assert a.height == "500px"

    def test_image_artifact_defaults(self):
        a = ImageArtifact()
        assert a.artifact_type == "image"
        assert a.url == ""
        assert a.alt == ""

    def test_image_artifact_fields(self):
        a = ImageArtifact(title="Logo", url="data:image/png;base64,abc", alt="PyWry Logo")
        assert a.url == "data:image/png;base64,abc"
        assert a.alt == "PyWry Logo"

    def test_json_artifact_defaults(self):
        a = JsonArtifact()
        assert a.artifact_type == "json"
        assert a.data is None

    def test_json_artifact_with_data(self):
        a = JsonArtifact(title="Config", data={"key": "value", "n": 42})
        assert a.data == {"key": "value", "n": 42}

    def test_all_are_artifact_base_subclasses(self):
        for cls in (
            CodeArtifact,
            MarkdownArtifact,
            HtmlArtifact,
            TableArtifact,
            PlotlyArtifact,
            ImageArtifact,
            JsonArtifact,
        ):
            assert issubclass(cls, _ArtifactBase)

    def test_isinstance_dispatch(self):
        items = [
            CodeArtifact(content="x"),
            MarkdownArtifact(content="# Hi"),
            HtmlArtifact(content="<p>"),
            TableArtifact(data=[]),
            PlotlyArtifact(figure={}),
            ImageArtifact(url="x.png"),
            JsonArtifact(data={"k": 1}),
        ]
        for item in items:
            assert isinstance(item, _ArtifactBase)


# =============================================================================
# Artifact Dispatch Tests — _dispatch_artifact + asset injection
# =============================================================================


class TestArtifactDispatch:
    """Test _dispatch_artifact with each artifact type."""

    def test_code_artifact_dispatch(self, bound_manager, widget):
        tid = bound_manager.active_thread_id
        cancel = threading.Event()

        def gen():
            yield CodeArtifact(title="code.py", content="print(1)", language="python")

        bound_manager._handle_stream(gen(), "msg_001", tid, cancel)

        artifacts = widget.get_events("chat:artifact")
        assert len(artifacts) == 1
        assert artifacts[0]["artifactType"] == "code"
        assert artifacts[0]["content"] == "print(1)"
        assert artifacts[0]["language"] == "python"
        assert artifacts[0]["title"] == "code.py"

    def test_markdown_artifact_dispatch(self, bound_manager, widget):
        tid = bound_manager.active_thread_id
        cancel = threading.Event()

        def gen():
            yield MarkdownArtifact(title="Notes", content="# Hello\n\nWorld")

        bound_manager._handle_stream(gen(), "msg_001", tid, cancel)

        artifacts = widget.get_events("chat:artifact")
        assert len(artifacts) == 1
        assert artifacts[0]["artifactType"] == "markdown"
        assert artifacts[0]["content"] == "# Hello\n\nWorld"

    def test_html_artifact_dispatch(self, bound_manager, widget):
        tid = bound_manager.active_thread_id
        cancel = threading.Event()

        def gen():
            yield HtmlArtifact(title="Page", content="<h1>Hi</h1>")

        bound_manager._handle_stream(gen(), "msg_001", tid, cancel)

        artifacts = widget.get_events("chat:artifact")
        assert len(artifacts) == 1
        assert artifacts[0]["artifactType"] == "html"
        assert artifacts[0]["content"] == "<h1>Hi</h1>"

    def test_table_artifact_dispatch(self, bound_manager, widget):
        tid = bound_manager.active_thread_id
        cancel = threading.Event()

        rows = [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]

        def gen():
            yield TableArtifact(title="Users", data=rows, height="300px")

        bound_manager._handle_stream(gen(), "msg_001", tid, cancel)

        # Assets should have been injected first
        asset_events = widget.get_events("chat:load-assets")
        assert len(asset_events) >= 1
        # Scripts should include AG Grid JS
        assert len(asset_events[0]["scripts"]) >= 1

        artifacts = widget.get_events("chat:artifact")
        assert len(artifacts) == 1
        assert artifacts[0]["artifactType"] == "table"
        assert artifacts[0]["rowData"] == rows
        assert artifacts[0]["height"] == "300px"
        assert "columns" in artifacts[0]

    def test_table_artifact_with_column_defs(self, bound_manager, widget):
        tid = bound_manager.active_thread_id
        cancel = threading.Event()
        cols = [{"field": "a"}, {"field": "b"}]

        def gen():
            yield TableArtifact(data=[{"a": 1, "b": 2}], column_defs=cols)

        bound_manager._handle_stream(gen(), "msg_001", tid, cancel)

        artifacts = widget.get_events("chat:artifact")
        assert artifacts[0]["columnDefs"] == cols

    def test_table_artifact_with_grid_options(self, bound_manager, widget):
        tid = bound_manager.active_thread_id
        cancel = threading.Event()
        opts = {"pagination": True}

        def gen():
            yield TableArtifact(data=[{"x": 1}], grid_options=opts)

        bound_manager._handle_stream(gen(), "msg_001", tid, cancel)

        artifacts = widget.get_events("chat:artifact")
        assert artifacts[0]["gridOptions"] == opts

    def test_plotly_artifact_dispatch(self, bound_manager, widget):
        tid = bound_manager.active_thread_id
        cancel = threading.Event()
        fig = {
            "data": [{"x": [1, 2], "y": [3, 4], "type": "scatter"}],
            "layout": {"title": "Test"},
        }

        def gen():
            yield PlotlyArtifact(title="Chart", figure=fig, height="500px")

        bound_manager._handle_stream(gen(), "msg_001", tid, cancel)

        # Plotly assets should be injected
        asset_events = widget.get_events("chat:load-assets")
        assert len(asset_events) >= 1

        artifacts = widget.get_events("chat:artifact")
        assert len(artifacts) == 1
        assert artifacts[0]["artifactType"] == "plotly"
        assert artifacts[0]["figure"] == fig
        assert artifacts[0]["height"] == "500px"

    def test_image_artifact_dispatch(self, bound_manager, widget):
        tid = bound_manager.active_thread_id
        cancel = threading.Event()

        def gen():
            yield ImageArtifact(title="Logo", url="data:image/png;base64,abc", alt="PyWry Logo")

        bound_manager._handle_stream(gen(), "msg_001", tid, cancel)

        artifacts = widget.get_events("chat:artifact")
        assert len(artifacts) == 1
        assert artifacts[0]["artifactType"] == "image"
        assert artifacts[0]["url"] == "data:image/png;base64,abc"
        assert artifacts[0]["alt"] == "PyWry Logo"

    def test_json_artifact_dispatch(self, bound_manager, widget):
        tid = bound_manager.active_thread_id
        cancel = threading.Event()
        data = {"key": "value", "nested": {"a": [1, 2]}}

        def gen():
            yield JsonArtifact(title="Config", data=data)

        bound_manager._handle_stream(gen(), "msg_001", tid, cancel)

        artifacts = widget.get_events("chat:artifact")
        assert len(artifacts) == 1
        assert artifacts[0]["artifactType"] == "json"
        assert artifacts[0]["data"] == data

    def test_aggrid_assets_sent_once(self, bound_manager, widget):
        """AG Grid assets are injected only on the first table artifact."""
        tid = bound_manager.active_thread_id
        cancel = threading.Event()

        def gen():
            yield TableArtifact(data=[{"a": 1}])
            yield TableArtifact(data=[{"b": 2}])

        bound_manager._handle_stream(gen(), "msg_001", tid, cancel)

        asset_events = widget.get_events("chat:load-assets")
        assert len(asset_events) == 1  # Only once
        assert bound_manager._aggrid_assets_sent is True

        artifacts = widget.get_events("chat:artifact")
        assert len(artifacts) == 2

    def test_plotly_assets_sent_once(self, bound_manager, widget):
        """Plotly assets are injected only on the first plotly artifact."""
        tid = bound_manager.active_thread_id
        cancel = threading.Event()

        def gen():
            yield PlotlyArtifact(figure={"data": []})
            yield PlotlyArtifact(figure={"data": []})

        bound_manager._handle_stream(gen(), "msg_001", tid, cancel)

        asset_events = widget.get_events("chat:load-assets")
        assert len(asset_events) == 1  # Only once
        assert bound_manager._plotly_assets_sent is True

    def test_mixed_artifacts_both_assets(self, bound_manager, widget):
        """Both AG Grid and Plotly assets injected when both types are used."""
        tid = bound_manager.active_thread_id
        cancel = threading.Event()

        def gen():
            yield TableArtifact(data=[{"x": 1}])
            yield PlotlyArtifact(figure={"data": []})

        bound_manager._handle_stream(gen(), "msg_001", tid, cancel)

        asset_events = widget.get_events("chat:load-assets")
        assert len(asset_events) == 2  # One for AG Grid, one for Plotly

    def test_artifact_backward_compat(self, bound_manager, widget):
        """ArtifactResponse alias still works as CodeArtifact."""
        tid = bound_manager.active_thread_id
        cancel = threading.Event()

        def gen():
            yield ArtifactResponse(title="old.py", content="x = 1", language="python")

        bound_manager._handle_stream(gen(), "msg_001", tid, cancel)

        artifacts = widget.get_events("chat:artifact")
        assert len(artifacts) == 1
        assert artifacts[0]["artifactType"] == "code"

    def test_table_artifact_dict_data(self, bound_manager, widget):
        """TableArtifact with dict-of-lists data (column-oriented)."""
        tid = bound_manager.active_thread_id
        cancel = threading.Event()
        data = {"name": ["Alice", "Bob"], "age": [30, 25]}

        def gen():
            yield TableArtifact(title="Users", data=data)

        bound_manager._handle_stream(gen(), "msg_001", tid, cancel)

        artifacts = widget.get_events("chat:artifact")
        assert len(artifacts) == 1
        assert len(artifacts[0]["rowData"]) == 2

    def test_rich_handler_with_new_artifacts(self, bound_manager, widget):
        """Integration test: stream handler yields mixed old and new types."""
        tid = bound_manager.active_thread_id
        cancel = threading.Event()

        def gen():
            yield StatusResponse(text="Working...")
            yield "Here is some text. "
            yield CodeArtifact(title="snippet.py", content="x = 1", language="python")
            yield MarkdownArtifact(title="Notes", content="**Bold** text")
            yield JsonArtifact(title="Data", data={"key": "val"})
            yield "Done!"

        bound_manager._handle_stream(gen(), "msg_001", tid, cancel)

        # Verify all event types were emitted
        assert len(widget.get_events("chat:status-update")) == 1
        chunks = widget.get_events("chat:stream-chunk")
        text_chunks = [c["chunk"] for c in chunks if "chunk" in c and not c.get("done")]
        assert "Here is some text. " in text_chunks
        assert "Done!" in text_chunks

        artifacts = widget.get_events("chat:artifact")
        assert len(artifacts) == 3
        types = [a["artifactType"] for a in artifacts]
        assert types == ["code", "markdown", "json"]


# =============================================================================
# Security — URL scheme validation
# =============================================================================


class TestURLSchemeValidation:
    """Ensure javascript: and other dangerous URL schemes are rejected."""

    def test_image_artifact_blocks_javascript_url(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ImageArtifact(url="javascript:alert(1)")

    def test_image_artifact_blocks_javascript_url_case_insensitive(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ImageArtifact(url="JaVaScRiPt:alert(1)")

    def test_image_artifact_blocks_javascript_url_with_whitespace(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ImageArtifact(url="  javascript:alert(1)")

    def test_image_artifact_allows_https(self):
        a = ImageArtifact(url="https://example.com/img.png")
        assert a.url == "https://example.com/img.png"

    def test_image_artifact_allows_data_uri(self):
        a = ImageArtifact(url="data:image/png;base64,abc123")
        assert a.url == "data:image/png;base64,abc123"

    def test_image_artifact_allows_empty(self):
        a = ImageArtifact(url="")
        assert a.url == ""

    def test_citation_blocks_javascript_url(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            CitationResponse(url="javascript:alert(1)")

    def test_citation_blocks_javascript_url_case_insensitive(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            CitationResponse(url="JAVASCRIPT:void(0)")

    def test_citation_allows_https(self):
        c = CitationResponse(url="https://example.com", title="Example")
        assert c.url == "https://example.com"

    def test_citation_allows_empty(self):
        c = CitationResponse(url="")
        assert c.url == ""


# =============================================================================
# Async Handler Tests
# =============================================================================


class TestAsyncHandler:
    """Test that ChatManager natively supports async functions and generators."""

    def test_async_coroutine_handler(self):
        """An async function returning a string works as a handler."""

        async def handler(messages, ctx):
            return f"Echo: {messages[-1]['text']}"

        mgr = ChatManager(handler=handler)
        w = FakeWidget()
        mgr.bind(w)
        tid = mgr.active_thread_id
        mgr._on_user_message({"text": "hello", "threadId": tid}, "", "")
        time.sleep(0.5)

        msgs = mgr._threads[tid]
        assistant = [m for m in msgs if m["role"] == "assistant"]
        assert len(assistant) == 1
        assert assistant[0]["text"] == "Echo: hello"

    def test_async_generator_handler(self):
        """An async generator yielding str chunks streams correctly."""

        async def handler(messages, ctx):
            for word in ["Hello", " ", "async", " ", "world"]:
                yield word

        mgr = ChatManager(handler=handler)
        w = FakeWidget()
        mgr.bind(w)
        tid = mgr.active_thread_id
        mgr._on_user_message({"text": "test", "threadId": tid}, "", "")
        time.sleep(0.5)

        chunks = w.get_events("chat:stream-chunk")
        text_chunks = [c["chunk"] for c in chunks if not c.get("done")]
        assert "".join(text_chunks) == "Hello async world"

        # Done signal sent
        done_chunks = [c for c in chunks if c.get("done")]
        assert len(done_chunks) == 1

        # Full text stored
        assistant = [m for m in mgr._threads[tid] if m["role"] == "assistant"]
        assert assistant[0]["text"] == "Hello async world"

    def test_async_generator_cancellation(self):
        """Async generator respects cancel_event."""
        import asyncio as _asyncio

        async def handler(messages, ctx):
            for i in range(100):
                if ctx.cancel_event.is_set():
                    return
                yield f"chunk{i} "
                await _asyncio.sleep(0.01)

        mgr = ChatManager(handler=handler)
        w = FakeWidget()
        mgr.bind(w)
        tid = mgr.active_thread_id
        mgr._on_user_message({"text": "go", "threadId": tid}, "", "")
        time.sleep(0.1)

        # Cancel mid-stream
        mgr._on_stop_generation({"threadId": tid}, "", "")
        time.sleep(0.3)

        chunks = w.get_events("chat:stream-chunk")
        # Should have been stopped before all 100 chunks
        text_chunks = [c["chunk"] for c in chunks if c.get("chunk")]
        assert len(text_chunks) < 100

    def test_async_generator_with_rich_responses(self):
        """Async generator can yield StatusResponse and other rich types."""

        async def handler(messages, ctx):
            yield StatusResponse(text="Thinking...")
            yield "The answer is "
            yield "42."

        mgr = ChatManager(handler=handler)
        w = FakeWidget()
        mgr.bind(w)
        tid = mgr.active_thread_id
        mgr._on_user_message({"text": "question", "threadId": tid}, "", "")
        time.sleep(0.5)

        statuses = w.get_events("chat:status-update")
        assert len(statuses) == 1
        assert statuses[0]["text"] == "Thinking..."

        assistant = [m for m in mgr._threads[tid] if m["role"] == "assistant"]
        assert assistant[0]["text"] == "The answer is 42."

    def test_async_handler_exception(self):
        """Async handler exceptions are caught and sent as error messages."""

        async def handler(messages, ctx):
            raise ValueError("async boom")

        mgr = ChatManager(handler=handler)
        w = FakeWidget()
        mgr.bind(w)
        tid = mgr.active_thread_id
        mgr._on_user_message({"text": "fail", "threadId": tid}, "", "")
        time.sleep(0.5)

        assistant_events = w.get_events("chat:assistant-message")
        assert any("async boom" in e.get("text", "") for e in assistant_events)


# =============================================================================
# Stream Buffering Tests
# =============================================================================


class TestStreamBuffering:
    """Verify time-based stream buffering batches text chunks."""

    def test_sync_chunks_batched(self, widget):
        """With buffering enabled, fast text chunks are combined."""
        mgr = ChatManager(handler=echo_handler)
        mgr._STREAM_FLUSH_INTERVAL = 10  # very high — force all into one batch
        mgr._STREAM_MAX_BUFFER = 10_000
        mgr.bind(widget)
        tid = mgr.active_thread_id
        cancel = threading.Event()

        def gen():
            yield "A"
            yield "B"
            yield "C"

        mgr._handle_stream(gen(), "msg_001", tid, cancel)

        chunks = widget.get_events("chat:stream-chunk")
        text_chunks = [c["chunk"] for c in chunks if c.get("chunk")]
        # All three should be batched into one combined chunk
        assert len(text_chunks) == 1
        assert text_chunks[0] == "ABC"
        # Done signal still sent
        assert chunks[-1]["done"] is True

    def test_sync_max_buffer_forces_flush(self, widget):
        """Chunks exceeding MAX_BUFFER flush immediately."""
        mgr = ChatManager(handler=echo_handler)
        mgr._STREAM_FLUSH_INTERVAL = 10  # high interval
        mgr._STREAM_MAX_BUFFER = 5  # but very small buffer
        mgr.bind(widget)
        tid = mgr.active_thread_id
        cancel = threading.Event()

        def gen():
            yield "AAAAAA"  # 6 chars > 5 — triggers flush
            yield "BB"  # 2 chars < 5 — stays in buffer

        mgr._handle_stream(gen(), "msg_001", tid, cancel)

        chunks = widget.get_events("chat:stream-chunk")
        text_chunks = [c["chunk"] for c in chunks if c.get("chunk")]
        assert len(text_chunks) == 2
        assert text_chunks[0] == "AAAAAA"
        assert text_chunks[1] == "BB"

    def test_sync_non_text_flushes_buffer(self, widget):
        """Non-text items flush any pending text buffer first."""
        mgr = ChatManager(handler=echo_handler)
        mgr._STREAM_FLUSH_INTERVAL = 10
        mgr._STREAM_MAX_BUFFER = 10_000
        mgr.bind(widget)
        tid = mgr.active_thread_id
        cancel = threading.Event()

        def gen():
            yield "before "
            yield StatusResponse(text="status!")
            yield "after"

        mgr._handle_stream(gen(), "msg_001", tid, cancel)

        chunks = widget.get_events("chat:stream-chunk")
        text_chunks = [c["chunk"] for c in chunks if c.get("chunk")]
        # "before " flushed before status, "after" flushed at end
        assert text_chunks[0] == "before "
        assert text_chunks[1] == "after"

        statuses = widget.get_events("chat:status-update")
        assert len(statuses) == 1

    def test_async_chunks_batched(self, widget):
        """Async generator text chunks are batched like sync ones."""
        import asyncio as _asyncio

        mgr = ChatManager(handler=echo_handler)
        mgr._STREAM_FLUSH_INTERVAL = 10
        mgr._STREAM_MAX_BUFFER = 10_000
        mgr.bind(widget)
        tid = mgr.active_thread_id
        cancel = threading.Event()

        async def agen():
            yield "X"
            yield "Y"
            yield "Z"

        _asyncio.run(mgr._handle_async_stream(agen(), "msg_001", tid, cancel))

        chunks = widget.get_events("chat:stream-chunk")
        text_chunks = [c["chunk"] for c in chunks if c.get("chunk")]
        assert len(text_chunks) == 1
        assert text_chunks[0] == "XYZ"

    def test_async_non_text_flushes_buffer(self, widget):
        """Async stream flushes text buffer before non-text items."""
        import asyncio as _asyncio

        mgr = ChatManager(handler=echo_handler)
        mgr._STREAM_FLUSH_INTERVAL = 10
        mgr._STREAM_MAX_BUFFER = 10_000
        mgr.bind(widget)
        tid = mgr.active_thread_id
        cancel = threading.Event()

        async def agen():
            yield "hello "
            yield ThinkingResponse(text="hmm")
            yield "world"

        _asyncio.run(mgr._handle_async_stream(agen(), "msg_001", tid, cancel))

        chunks = widget.get_events("chat:stream-chunk")
        text_chunks = [c["chunk"] for c in chunks if c.get("chunk")]
        assert text_chunks[0] == "hello "
        assert text_chunks[1] == "world"

        thinking = widget.get_events("chat:thinking-chunk")
        assert len(thinking) == 1

    def test_full_text_stored_correctly_with_buffering(self, widget):
        """Full text is accumulated regardless of buffering."""
        mgr = ChatManager(handler=echo_handler)
        mgr._STREAM_FLUSH_INTERVAL = 10
        mgr._STREAM_MAX_BUFFER = 10_000
        mgr.bind(widget)
        tid = mgr.active_thread_id
        cancel = threading.Event()

        def gen():
            yield "Hello "
            yield "beautiful "
            yield "world!"

        mgr._handle_stream(gen(), "msg_001", tid, cancel)

        msgs = mgr._threads[tid]
        assert msgs[0]["text"] == "Hello beautiful world!"

    def test_all_events_present_after_return(self, widget):
        """_handle_stream delivers all events before returning."""
        mgr = ChatManager(handler=echo_handler)
        mgr._STREAM_FLUSH_INTERVAL = 0  # immediate flush
        mgr._STREAM_MAX_BUFFER = 1
        mgr.bind(widget)
        tid = mgr.active_thread_id
        cancel = threading.Event()

        def gen():
            for i in range(20):
                yield f"chunk{i} "

        mgr._handle_stream(gen(), "msg_001", tid, cancel)

        # All chunks + done should be present immediately after return
        chunks = widget.get_events("chat:stream-chunk")
        text_chunks = [c["chunk"] for c in chunks if c.get("chunk")]
        assert "".join(text_chunks) == "".join(f"chunk{i} " for i in range(20))
        assert chunks[-1]["done"] is True


# =============================================================================
# Context Attachment Tests
# =============================================================================


class TestContextAttachments:
    """Tests for context attachment resolution and injection."""

    def test_attachment_dataclass_file(self):
        """File attachment stores path correctly."""
        import pathlib

        att = Attachment(type="file", name="test.py", path=pathlib.Path("/test_data/test.py"))
        assert att.type == "file"
        assert att.name == "test.py"
        assert att.path == pathlib.Path("/test_data/test.py")
        assert att.content == ""
        assert att.source == ""

    def test_attachment_dataclass_widget(self):
        """Widget attachment stores content correctly."""
        att = Attachment(type="widget", name="@Sales Data", content="a,b\n1,2")
        assert att.type == "widget"
        assert att.name == "@Sales Data"
        assert att.content == "a,b\n1,2"
        assert att.path is None

    def test_enable_context_default_false(self):
        """Context is disabled by default."""
        mgr = ChatManager(handler=echo_handler)
        assert mgr._enable_context is False

    def test_enable_context_constructor(self):
        """enable_context=True is stored."""
        mgr = ChatManager(handler=echo_handler, enable_context=True)
        assert mgr._enable_context is True

    def test_context_allowed_roots(self, tmp_path):
        """context_allowed_roots is stored (resolved)."""
        mgr = ChatManager(
            handler=echo_handler,
            enable_context=True,
            context_allowed_roots=[str(tmp_path)],
        )
        assert mgr._context_allowed_roots == [str(tmp_path)]

    def test_resolve_attachments_disabled(self, widget):
        """When context is disabled, no attachments are resolved."""
        mgr = ChatManager(handler=echo_handler, enable_context=False)
        mgr.bind(widget)
        result = mgr._resolve_attachments(
            [{"type": "file", "name": "test.py", "path": "/test_data/test.py"}]
        )
        assert result == []

    def test_resolve_attachments_with_paths(self, widget):
        """_resolve_attachments creates Attachments with Path objects."""
        import pathlib

        mgr = ChatManager(handler=echo_handler, enable_context=True)
        mgr.bind(widget)
        result = mgr._resolve_attachments(
            [
                {"type": "file", "name": "a.py", "path": "/data/a.py"},
                {"type": "file", "name": "b.json", "path": "/data/b.json"},
            ]
        )
        assert len(result) == 2
        assert result[0].name == "a.py"
        assert result[0].path == pathlib.Path("/data/a.py")
        assert result[1].name == "b.json"
        assert result[1].path == pathlib.Path("/data/b.json")

    def test_resolve_attachments_file_without_path_or_content_skipped(self, widget):
        """File attachment without path or content is skipped."""
        mgr = ChatManager(handler=echo_handler, enable_context=True)
        mgr.bind(widget)
        result = mgr._resolve_attachments(
            [
                {"type": "file", "name": "orphan.csv"},
            ]
        )
        assert result == []

    def test_resolve_attachments_browser_content_fallback(self, widget):
        """Browser mode: file with content but no path is resolved."""
        mgr = ChatManager(handler=echo_handler, enable_context=True)
        mgr.bind(widget)
        result = mgr._resolve_attachments(
            [
                {"type": "file", "name": "data.csv", "content": "a,b\n1,2"},
            ]
        )
        assert len(result) == 1
        assert result[0].name == "data.csv"
        assert result[0].path is None
        assert result[0].content == "a,b\n1,2"

    def test_get_attachment_browser_content(self):
        """get_attachment returns content for browser-mode files (no path)."""
        ctx = ChatContext(
            attachments=[
                Attachment(type="file", name="notes.txt", content="hello world"),
            ],
        )
        assert ctx.get_attachment("notes.txt") == "hello world"

    def test_attachment_summary_browser_content(self):
        """attachment_summary shows (file) without path for browser-mode files."""
        ctx = ChatContext(
            attachments=[
                Attachment(type="file", name="notes.txt", content="hello world"),
            ],
        )
        summary = ctx.attachment_summary
        assert "notes.txt" in summary
        assert "(file)" in summary

    def test_context_text_browser_content(self):
        """context_text includes content for browser-mode files."""
        ctx = ChatContext(
            attachments=[
                Attachment(type="file", name="data.csv", content="a,b\n1,2"),
            ],
        )
        text = ctx.context_text
        assert "a,b" in text
        assert "data.csv" in text

    def test_resolve_attachments_max_limit(self, widget):
        """Only _MAX_ATTACHMENTS are resolved."""
        from pywry.chat_manager import _MAX_ATTACHMENTS

        mgr = ChatManager(handler=echo_handler, enable_context=True)
        mgr.bind(widget)
        raw = [
            {"type": "file", "name": f"f{i}.txt", "path": f"/test_data/f{i}.txt"}
            for i in range(_MAX_ATTACHMENTS + 5)
        ]
        result = mgr._resolve_attachments(raw)
        assert len(result) == _MAX_ATTACHMENTS

    def test_context_tool_schema(self):
        """CONTEXT_TOOL is a valid OpenAI-style tool dict."""
        tool = ChatManager.CONTEXT_TOOL
        assert tool["type"] == "function"
        assert tool["function"]["name"] == "get_context"
        params = tool["function"]["parameters"]
        assert "name" in params["properties"]
        assert "name" in params["required"]

    def test_get_attachment_found(self):
        """ctx.get_attachment returns path string for files, content for widgets."""
        import pathlib

        ctx = ChatContext(
            attachments=[
                Attachment(type="file", name="test.py", path=pathlib.Path("/test_data/test.py")),
                Attachment(type="widget", name="@Sales", content="a,b"),
            ],
        )
        assert ctx.get_attachment("test.py") == str(pathlib.Path("/test_data/test.py"))
        assert ctx.get_attachment("@Sales") == "a,b"

    def test_get_attachment_not_found(self):
        """ctx.get_attachment returns error message when not found."""
        import pathlib

        ctx = ChatContext(
            attachments=[
                Attachment(type="file", name="test.py", path=pathlib.Path("/test_data/test.py")),
            ],
        )
        result = ctx.get_attachment("missing.txt")
        assert "not found" in result.lower()
        assert "test.py" in result

    def test_attachment_summary(self):
        """ctx.attachment_summary lists attached items."""
        import pathlib

        ctx = ChatContext(
            attachments=[
                Attachment(type="file", name="data.csv", path=pathlib.Path("/data/data.csv")),
            ],
        )
        summary = ctx.attachment_summary
        assert "data.csv" in summary
        assert "file" in summary

    def test_attachment_summary_empty(self):
        """ctx.attachment_summary is empty string when no attachments."""
        ctx = ChatContext()
        assert ctx.attachment_summary == ""

    def test_messages_stay_clean_with_attachments(self, widget):
        """Attachments go to ctx.attachments, messages list stays user/assistant only."""
        received_messages = []
        received_ctx = []

        def capture_handler(messages, ctx):
            received_messages.extend(messages)
            received_ctx.append(ctx)
            return "ok"

        mgr = ChatManager(handler=capture_handler, enable_context=True)
        mgr.bind(widget)

        mgr._on_user_message(
            {
                "text": "Analyze this",
                "attachments": [
                    {"type": "file", "name": "data.csv", "path": "/data/data.csv"},
                ],
            },
            "chat:user-message",
            "",
        )
        time.sleep(0.5)

        # Messages should only have user/assistant — no context role injected
        assert all(m["role"] in ("user", "assistant") for m in received_messages)
        # Attachments should be on ctx
        assert len(received_ctx) == 1
        assert len(received_ctx[0].attachments) == 1
        assert received_ctx[0].attachments[0].name == "data.csv"
        import pathlib

        assert received_ctx[0].attachments[0].path == pathlib.Path("/data/data.csv")

    def test_context_not_stored_in_threads(self, widget):
        """Context messages are NOT persisted in _threads."""
        mgr = ChatManager(handler=echo_handler, enable_context=True)
        mgr.bind(widget)

        mgr._on_user_message(
            {
                "text": "Hello",
                "attachments": [
                    {"type": "file", "name": "test.txt", "path": "/test_data/test.txt"},
                ],
            },
            "chat:user-message",
            "",
        )
        time.sleep(0.5)

        # _threads should only have user + assistant, NOT context
        thread = mgr._threads.get(mgr._active_thread, [])
        roles = [m["role"] for m in thread]
        assert "context" not in roles
        assert "user" in roles

    def test_chat_context_attachments_field(self, widget):
        """ChatContext.attachments is populated from resolved attachments."""
        received_ctx = []

        def capture_handler(messages, ctx):
            received_ctx.append(ctx)
            return "ok"

        mgr = ChatManager(handler=capture_handler, enable_context=True)
        mgr.bind(widget)

        mgr._on_user_message(
            {
                "text": "Check this",
                "attachments": [
                    {"type": "file", "name": "f.py", "path": "/test_data/f.py"},
                ],
            },
            "chat:user-message",
            "",
        )
        time.sleep(0.5)

        assert len(received_ctx) == 1
        assert len(received_ctx[0].attachments) == 1
        assert received_ctx[0].attachments[0].name == "f.py"

    def test_no_attachments_empty_list(self, widget):
        """When no attachments sent, ctx.attachments is empty list."""
        received_ctx = []

        def capture_handler(messages, ctx):
            received_ctx.append(ctx)
            return "ok"

        mgr = ChatManager(handler=capture_handler, enable_context=True)
        mgr.bind(widget)

        mgr._on_user_message(
            {"text": "Hello"},
            "chat:user-message",
            "",
        )
        time.sleep(0.5)

        assert len(received_ctx) == 1
        assert received_ctx[0].attachments == []

    def test_get_context_sources_no_app(self, widget):
        """_get_context_sources returns empty when no app."""
        mgr = ChatManager(handler=echo_handler, enable_context=True)
        mgr.bind(widget)
        assert mgr._get_context_sources() == []

    def test_context_sources_emitted_on_state_request(self, widget):
        """When context is enabled, context sources are emitted on request-state."""
        mgr = ChatManager(handler=echo_handler, enable_context=True)
        mgr.bind(widget)
        widget.clear()

        mgr._on_request_state({}, "chat:request-state", "")

        # Should have emitted chat:context-sources (but may be empty if no app)
        # At minimum, no error should occur
        state_events = widget.get_events("chat:state-response")
        assert len(state_events) == 1

    def test_register_context_source(self, widget):
        """register_context_source makes source appear in @ mention list."""
        mgr = ChatManager(handler=echo_handler, enable_context=True)
        mgr.register_context_source("sales-grid", "Sales Data")
        mgr.bind(widget)

        sources = mgr._get_context_sources()
        assert len(sources) == 1
        assert sources[0]["id"] == "sales-grid"
        assert sources[0]["name"] == "Sales Data"
        assert sources[0]["componentId"] == "sales-grid"

    def test_registered_source_emitted_on_request_state(self, widget):
        """Registered sources are emitted via chat:context-sources."""
        mgr = ChatManager(handler=echo_handler, enable_context=True)
        mgr.register_context_source("sales-chart", "Revenue Chart")
        mgr.bind(widget)
        widget.clear()

        mgr._on_request_state({}, "chat:request-state", "")

        ctx_events = widget.get_events("chat:context-sources")
        assert len(ctx_events) == 1
        assert len(ctx_events[0]["sources"]) == 1
        assert ctx_events[0]["sources"][0]["name"] == "Revenue Chart"

    def test_resolve_registered_source_with_content(self, widget):
        """_resolve_widget_attachment uses content extracted by frontend."""
        mgr = ChatManager(handler=echo_handler, enable_context=True)
        mgr.register_context_source("sales-grid", "Sales Data")
        mgr.bind(widget)

        # Frontend sends extracted content along with the widget_id
        att = mgr._resolve_widget_attachment(
            "sales-grid",
            content="Product,Revenue\nAlpha,100\nBeta,200",
        )
        assert att is not None
        assert att.name == "@Sales Data"
        assert att.content == "Product,Revenue\nAlpha,100\nBeta,200"
        assert att.type == "widget"
        assert att.source == "sales-grid"

    def test_resolve_registered_source_not_found(self, widget):
        """_resolve_widget_attachment returns None for unknown source."""
        mgr = ChatManager(handler=echo_handler, enable_context=True)
        mgr.bind(widget)

        att = mgr._resolve_widget_attachment("nonexistent")
        assert att is None

    def test_multiple_registered_sources(self, widget):
        """Multiple registered sources all appear in context list."""
        mgr = ChatManager(handler=echo_handler, enable_context=True)
        mgr.register_context_source("sales-grid", "Sales Data")
        mgr.register_context_source("sales-chart", "Revenue Chart")
        mgr.register_context_source("kpi-grid", "KPI Summary")
        mgr.bind(widget)

        sources = mgr._get_context_sources()
        names = [s["name"] for s in sources]
        assert "Sales Data" in names
        assert "Revenue Chart" in names
        assert "KPI Summary" in names

    def test_resolve_widget_without_content_or_app(self, widget):
        """_resolve_widget_attachment without content falls back gracefully."""
        mgr = ChatManager(handler=echo_handler, enable_context=True)
        mgr.register_context_source("sales-grid", "Sales Data")
        mgr.bind(widget)

        # No content provided and no app/inline_widgets => None
        att = mgr._resolve_widget_attachment("sales-grid")
        assert att is None


class TestFileAttachConfig:
    """Tests for the separate enable_file_attach / file_accept_types params."""

    def test_enable_file_attach_default_false(self):
        """File attach is disabled by default."""
        mgr = ChatManager(handler=echo_handler)
        assert mgr._enable_file_attach is False

    def test_enable_file_attach_true(self):
        """enable_file_attach=True requires file_accept_types."""
        mgr = ChatManager(
            handler=echo_handler,
            enable_file_attach=True,
            file_accept_types=[".csv"],
        )
        assert mgr._enable_file_attach is True

    def test_enable_file_attach_requires_accept_types(self):
        """ValueError when enable_file_attach=True without file_accept_types."""
        import pytest

        with pytest.raises(ValueError, match="file_accept_types is required"):
            ChatManager(handler=echo_handler, enable_file_attach=True)

    def test_file_accept_types_custom(self):
        """Custom file accept types are stored."""
        types = [".csv", ".json", ".xlsx"]
        mgr = ChatManager(
            handler=echo_handler,
            enable_file_attach=True,
            file_accept_types=types,
        )
        assert mgr._file_accept_types == types

    def test_file_attach_independent_of_context(self, widget):
        """File attachments work when enable_file_attach=True but enable_context=False."""
        import pathlib

        mgr = ChatManager(
            handler=echo_handler,
            enable_file_attach=True,
            file_accept_types=[".csv"],
            enable_context=False,
        )
        mgr.bind(widget)
        result = mgr._resolve_attachments(
            [
                {"type": "file", "name": "data.csv", "path": "/data/data.csv"},
            ]
        )
        assert len(result) == 1
        assert result[0].name == "data.csv"
        assert result[0].path == pathlib.Path("/data/data.csv")

    def test_context_only_no_file_attach(self, widget):
        """Widget attachments work when enable_context=True but enable_file_attach=False."""
        mgr = ChatManager(
            handler=echo_handler,
            enable_context=True,
            enable_file_attach=False,
        )
        mgr.register_context_source("sales-grid", "Sales Data")
        mgr.bind(widget)
        result = mgr._resolve_attachments(
            [
                {"type": "widget", "widgetId": "sales-grid", "content": "a,b\n1,2"},
            ]
        )
        assert len(result) == 1
        assert result[0].type == "widget"

    def test_both_disabled_resolves_nothing(self, widget):
        """When both flags are False, no attachments resolve."""
        mgr = ChatManager(handler=echo_handler)
        mgr.bind(widget)
        result = mgr._resolve_attachments(
            [
                {"type": "file", "name": "data.csv", "path": "/data/data.csv"},
            ]
        )
        assert result == []

    def test_both_enabled_resolves_all(self, widget):
        """When both flags are True, both files and widgets resolve."""
        import pathlib

        mgr = ChatManager(
            handler=echo_handler,
            enable_context=True,
            enable_file_attach=True,
            file_accept_types=[".csv"],
        )
        mgr.register_context_source("sales-grid", "Sales Data")
        mgr.bind(widget)
        result = mgr._resolve_attachments(
            [
                {"type": "file", "name": "data.csv", "path": "/data/data.csv"},
                {"type": "widget", "widgetId": "sales-grid", "content": "x,y\n1,2"},
            ]
        )
        assert len(result) == 2
        assert result[0].type == "file"
        assert result[0].path == pathlib.Path("/data/data.csv")
        assert result[1].type == "widget"
        assert result[1].content == "x,y\n1,2"

    def test_rejected_file_extension(self, widget):
        """Files with extensions not in file_accept_types are rejected."""
        mgr = ChatManager(
            handler=echo_handler,
            enable_file_attach=True,
            file_accept_types=[".csv", ".json"],
        )
        mgr.bind(widget)
        result = mgr._resolve_attachments(
            [
                {"type": "file", "name": "exploit.exe", "path": "/test_data/exploit.exe"},
            ]
        )
        assert result == []

    def test_accepted_file_extension(self, widget):
        """Files with extensions in file_accept_types are accepted."""
        mgr = ChatManager(
            handler=echo_handler,
            enable_file_attach=True,
            file_accept_types=[".csv", ".json"],
        )
        mgr.bind(widget)
        result = mgr._resolve_attachments(
            [
                {"type": "file", "name": "data.csv", "path": "/data/data.csv"},
            ]
        )
        assert len(result) == 1
        assert result[0].name == "data.csv"


# =============================================================================
# Full pipeline integration tests — prove file attachments actually work
# =============================================================================


class TestFileAttachPipeline:
    """End-to-end tests: _on_user_message → handler receives correct Attachment
    objects with the right fields, and ctx helpers return correct data."""

    @pytest.fixture()
    def widget(self):
        return FakeWidget()

    # -- Desktop mode (Tauri): handler receives path, reads file from disk --

    def test_desktop_file_path_reaches_handler(self, widget, tmp_path):
        """Full pipeline: desktop file attachment delivers a real readable Path."""
        f = tmp_path / "sales.csv"
        f.write_text("Product,Revenue\nAlpha,100\nBeta,200", encoding="utf-8")

        received = {}

        def handler(messages, ctx):
            received["ctx"] = ctx
            received["messages"] = list(messages)
            # Actually read the file — this is what the handler would do
            att = ctx.attachments[0]
            received["file_content"] = att.path.read_text(encoding="utf-8")
            return "Done"

        mgr = ChatManager(
            handler=handler,
            enable_file_attach=True,
            file_accept_types=[".csv"],
        )
        mgr.bind(widget)

        mgr._on_user_message(
            {
                "text": "Analyze sales",
                "attachments": [
                    {"type": "file", "name": "sales.csv", "path": str(f)},
                ],
            },
            "chat:user-message",
            "",
        )
        time.sleep(0.5)

        # Handler was called
        assert "ctx" in received
        ctx = received["ctx"]

        # Attachment has correct fields
        assert len(ctx.attachments) == 1
        att = ctx.attachments[0]
        assert att.type == "file"
        assert att.name == "sales.csv"
        assert att.path == f
        assert att.content == ""  # Desktop mode — content is empty

        # Handler could actually read the file
        assert received["file_content"] == "Product,Revenue\nAlpha,100\nBeta,200"

        # ctx.get_attachment returns path string for desktop files
        assert ctx.get_attachment("sales.csv") == str(f)

        # ctx.attachment_summary includes path
        assert str(f) in ctx.attachment_summary
        assert "sales.csv" in ctx.attachment_summary

        # ctx.context_text includes "Path:" for desktop files
        assert f"Path: {f}" in ctx.context_text

    # -- Browser mode (inline/iframe): handler receives content directly --

    def test_browser_file_content_reaches_handler(self, widget):
        """Full pipeline: browser file attachment delivers content directly."""
        csv_data = "Name,Age\nAlice,30\nBob,25"
        received = {}

        def handler(messages, ctx):
            received["ctx"] = ctx
            # In browser mode, content is already available — no disk read needed
            att = ctx.attachments[0]
            received["from_content"] = att.content
            received["from_get_attachment"] = ctx.get_attachment("people.csv")
            return "Done"

        mgr = ChatManager(
            handler=handler,
            enable_file_attach=True,
            file_accept_types=[".csv"],
        )
        mgr.bind(widget)

        mgr._on_user_message(
            {
                "text": "Who is older?",
                "attachments": [
                    {"type": "file", "name": "people.csv", "content": csv_data},
                ],
            },
            "chat:user-message",
            "",
        )
        time.sleep(0.5)

        assert "ctx" in received
        ctx = received["ctx"]

        # Attachment has correct fields for browser mode
        assert len(ctx.attachments) == 1
        att = ctx.attachments[0]
        assert att.type == "file"
        assert att.name == "people.csv"
        assert att.path is None  # Browser — no filesystem path
        assert att.content == csv_data

        # Handler got the content
        assert received["from_content"] == csv_data
        # get_attachment returns content when path is None
        assert received["from_get_attachment"] == csv_data

        # attachment_summary says (file) without path
        assert "people.csv (file)" in ctx.attachment_summary

        # context_text includes the actual content
        assert "Name,Age" in ctx.context_text
        assert "people.csv" in ctx.context_text

    # -- Mixed: desktop file + widget in same message --

    def test_mixed_file_and_widget_pipeline(self, widget, tmp_path):
        """Desktop file + widget attachment both reach handler correctly."""
        f = tmp_path / "config.json"
        f.write_text('{"debug": true}', encoding="utf-8")

        received = {}

        def handler(messages, ctx):
            received["ctx"] = ctx
            return "Done"

        mgr = ChatManager(
            handler=handler,
            enable_context=True,
            enable_file_attach=True,
            file_accept_types=[".json"],
        )
        mgr.register_context_source("metrics-grid", "Metrics")
        mgr.bind(widget)

        mgr._on_user_message(
            {
                "text": "Compare",
                "attachments": [
                    {"type": "file", "name": "config.json", "path": str(f)},
                    {"type": "widget", "widgetId": "metrics-grid", "content": "x,y\n1,2"},
                ],
            },
            "chat:user-message",
            "",
        )
        time.sleep(0.5)

        ctx = received["ctx"]
        assert len(ctx.attachments) == 2

        # File attachment
        file_att = ctx.attachments[0]
        assert file_att.type == "file"
        assert file_att.path == f
        assert file_att.content == ""
        assert ctx.get_attachment("config.json") == str(f)
        # Verify the file is actually readable
        assert file_att.path.read_text(encoding="utf-8") == '{"debug": true}'

        # Widget attachment
        widget_att = ctx.attachments[1]
        assert widget_att.type == "widget"
        assert widget_att.path is None
        assert widget_att.content == "x,y\n1,2"
        assert ctx.get_attachment("Metrics") == "x,y\n1,2"

        # Summary includes both
        summary = ctx.attachment_summary
        assert "config.json" in summary
        assert "Metrics" in summary

    # -- Mixed: browser files + widget in same message --

    def test_mixed_browser_file_and_widget_pipeline(self, widget):
        """Browser file + widget attachment both reach handler correctly."""
        received = {}

        def handler(messages, ctx):
            received["ctx"] = ctx
            return "Done"

        mgr = ChatManager(
            handler=handler,
            enable_context=True,
            enable_file_attach=True,
            file_accept_types=[".txt"],
        )
        mgr.register_context_source("chart", "Revenue Chart")
        mgr.bind(widget)

        mgr._on_user_message(
            {
                "text": "Analyze",
                "attachments": [
                    {"type": "file", "name": "notes.txt", "content": "buy low sell high"},
                    {"type": "widget", "widgetId": "chart", "content": "Q1:100,Q2:200"},
                ],
            },
            "chat:user-message",
            "",
        )
        time.sleep(0.5)

        ctx = received["ctx"]
        assert len(ctx.attachments) == 2

        # Browser file
        assert ctx.attachments[0].type == "file"
        assert ctx.attachments[0].path is None
        assert ctx.attachments[0].content == "buy low sell high"
        assert ctx.get_attachment("notes.txt") == "buy low sell high"

        # Widget
        assert ctx.attachments[1].type == "widget"
        assert ctx.get_attachment("Revenue Chart") == "Q1:100,Q2:200"

    # -- Context text injection into messages --

    def test_desktop_context_text_prepended_to_message(self, widget, tmp_path):
        """In desktop mode, context_text with file paths is prepended to user message."""
        f = tmp_path / "data.csv"
        f.write_text("a,b\n1,2", encoding="utf-8")

        received = {}

        def handler(messages, ctx):
            received["messages"] = list(messages)
            received["ctx"] = ctx
            return "ok"

        mgr = ChatManager(
            handler=handler,
            enable_file_attach=True,
            file_accept_types=[".csv"],
        )
        mgr.bind(widget)

        mgr._on_user_message(
            {
                "text": "check this",
                "attachments": [
                    {"type": "file", "name": "data.csv", "path": str(f)},
                ],
            },
            "chat:user-message",
            "",
        )
        time.sleep(0.5)

        # The last user message text should have context prepended
        last_user = [m for m in received["messages"] if m["role"] == "user"][-1]
        assert f"Path: {f}" in last_user["text"]
        assert "check this" in last_user["text"]

    def test_browser_context_text_prepended_to_message(self, widget):
        """In browser mode, context_text with file content is prepended to user message."""
        received = {}

        def handler(messages, ctx):
            received["messages"] = list(messages)
            return "ok"

        mgr = ChatManager(
            handler=handler,
            enable_file_attach=True,
            file_accept_types=[".csv"],
        )
        mgr.bind(widget)

        mgr._on_user_message(
            {
                "text": "check this",
                "attachments": [
                    {"type": "file", "name": "data.csv", "content": "x,y\n10,20"},
                ],
            },
            "chat:user-message",
            "",
        )
        time.sleep(0.5)

        last_user = [m for m in received["messages"] if m["role"] == "user"][-1]
        # Browser content should be inline in the message
        assert "x,y" in last_user["text"]
        assert "check this" in last_user["text"]

    # -- Rejected files never reach handler --

    def test_rejected_extension_never_reaches_handler(self, widget):
        """Files with wrong extensions are silently dropped before handler."""
        received = {}

        def handler(messages, ctx):
            received["ctx"] = ctx
            return "ok"

        mgr = ChatManager(
            handler=handler,
            enable_file_attach=True,
            file_accept_types=[".csv"],
        )
        mgr.bind(widget)

        mgr._on_user_message(
            {
                "text": "run this",
                "attachments": [
                    {"type": "file", "name": "malware.exe", "path": "/test_data/malware.exe"},
                ],
            },
            "chat:user-message",
            "",
        )
        time.sleep(0.5)

        # Handler was called but with NO attachments
        assert received["ctx"].attachments == []

    def test_empty_path_and_content_never_reaches_handler(self, widget):
        """File with neither path nor content is dropped."""
        received = {}

        def handler(messages, ctx):
            received["ctx"] = ctx
            return "ok"

        mgr = ChatManager(
            handler=handler,
            enable_file_attach=True,
            file_accept_types=[".csv"],
        )
        mgr.bind(widget)

        mgr._on_user_message(
            {
                "text": "test",
                "attachments": [
                    {"type": "file", "name": "ghost.csv"},
                ],
            },
            "chat:user-message",
            "",
        )
        time.sleep(0.5)

        assert received["ctx"].attachments == []

    # -- Emitted events contain attachment info --

    def test_tool_call_events_emitted_for_desktop_file(self, widget, tmp_path):
        """Attachment tool-call/tool-result events are emitted for desktop files."""
        f = tmp_path / "report.csv"
        f.write_text("a,b", encoding="utf-8")

        mgr = ChatManager(
            handler=echo_handler,
            enable_file_attach=True,
            file_accept_types=[".csv"],
        )
        mgr.bind(widget)
        widget.clear()

        mgr._on_user_message(
            {
                "text": "analyze",
                "attachments": [
                    {"type": "file", "name": "report.csv", "path": str(f)},
                ],
            },
            "chat:user-message",
            "",
        )
        time.sleep(0.5)

        # Should emit tool-call with name="attach_file"
        tool_calls = widget.get_events("chat:tool-call")
        assert len(tool_calls) >= 1
        assert tool_calls[0]["name"] == "attach_file"
        assert tool_calls[0]["arguments"]["name"] == "report.csv"

        # Should emit tool-result with path info
        tool_results = widget.get_events("chat:tool-result")
        assert len(tool_results) >= 1
        assert str(f) in tool_results[0]["result"]

    def test_tool_call_events_emitted_for_browser_file(self, widget):
        """Attachment tool-call/tool-result events are emitted for browser files."""
        mgr = ChatManager(
            handler=echo_handler,
            enable_file_attach=True,
            file_accept_types=[".txt"],
        )
        mgr.bind(widget)
        widget.clear()

        mgr._on_user_message(
            {
                "text": "read",
                "attachments": [
                    {"type": "file", "name": "notes.txt", "content": "hello"},
                ],
            },
            "chat:user-message",
            "",
        )
        time.sleep(0.5)

        tool_calls = widget.get_events("chat:tool-call")
        assert len(tool_calls) >= 1
        assert tool_calls[0]["name"] == "attach_file"

    # -- Multiple files in one message --

    def test_multiple_desktop_files(self, widget, tmp_path):
        """Multiple desktop files all reach the handler with correct paths."""
        f1 = tmp_path / "a.csv"
        f2 = tmp_path / "b.csv"
        f1.write_text("col1\n1", encoding="utf-8")
        f2.write_text("col2\n2", encoding="utf-8")

        received = {}

        def handler(messages, ctx):
            received["ctx"] = ctx
            return "ok"

        mgr = ChatManager(
            handler=handler,
            enable_file_attach=True,
            file_accept_types=[".csv"],
        )
        mgr.bind(widget)

        mgr._on_user_message(
            {
                "text": "compare",
                "attachments": [
                    {"type": "file", "name": "a.csv", "path": str(f1)},
                    {"type": "file", "name": "b.csv", "path": str(f2)},
                ],
            },
            "chat:user-message",
            "",
        )
        time.sleep(0.5)

        ctx = received["ctx"]
        assert len(ctx.attachments) == 2
        # Both files are independently readable
        assert ctx.attachments[0].path.read_text(encoding="utf-8") == "col1\n1"
        assert ctx.attachments[1].path.read_text(encoding="utf-8") == "col2\n2"
        # get_attachment resolves each by name
        assert ctx.get_attachment("a.csv") == str(f1)
        assert ctx.get_attachment("b.csv") == str(f2)

    def test_multiple_browser_files(self, widget):
        """Multiple browser files all reach the handler with correct content."""
        received = {}

        def handler(messages, ctx):
            received["ctx"] = ctx
            return "ok"

        mgr = ChatManager(
            handler=handler,
            enable_file_attach=True,
            file_accept_types=[".csv", ".json"],
        )
        mgr.bind(widget)

        mgr._on_user_message(
            {
                "text": "compare",
                "attachments": [
                    {"type": "file", "name": "data.csv", "content": "a,b\n1,2"},
                    {"type": "file", "name": "cfg.json", "content": '{"k": "v"}'},
                ],
            },
            "chat:user-message",
            "",
        )
        time.sleep(0.5)

        ctx = received["ctx"]
        assert len(ctx.attachments) == 2
        assert ctx.get_attachment("data.csv") == "a,b\n1,2"
        assert ctx.get_attachment("cfg.json") == '{"k": "v"}'
        # Both show up in summary
        assert "data.csv" in ctx.attachment_summary
        assert "cfg.json" in ctx.attachment_summary

    # -- Handler pattern: read or use content --

    def test_handler_reads_real_file_like_demo(self, widget, tmp_path):
        """Replicate the exact magentic demo pattern: handler reads att.path."""
        f = tmp_path / "report.csv"
        f.write_text("Product,Revenue\nAlpha,100\nBeta,200", encoding="utf-8")

        received = {}

        def handler(messages, ctx):
            # Exact pattern from pywry_demo_magentic.py get_context tool
            results = []
            for att in ctx.attachments:
                if att.path:
                    results.append(att.path.read_text(encoding="utf-8", errors="replace"))
                else:
                    results.append(att.content)
            received["results"] = results
            return "Done"

        mgr = ChatManager(
            handler=handler,
            enable_file_attach=True,
            file_accept_types=[".csv"],
        )
        mgr.bind(widget)

        mgr._on_user_message(
            {
                "text": "analyze",
                "attachments": [
                    {"type": "file", "name": "report.csv", "path": str(f)},
                ],
            },
            "chat:user-message",
            "",
        )
        time.sleep(0.5)

        assert received["results"] == ["Product,Revenue\nAlpha,100\nBeta,200"]

    def test_handler_uses_browser_content_like_demo(self, widget):
        """Replicate the demo pattern for browser mode: handler uses att.content."""
        received = {}

        def handler(messages, ctx):
            results = []
            for att in ctx.attachments:
                if att.path:
                    results.append(att.path.read_text(encoding="utf-8", errors="replace"))
                else:
                    results.append(att.content)
            received["results"] = results
            return "Done"

        mgr = ChatManager(
            handler=handler,
            enable_file_attach=True,
            file_accept_types=[".csv"],
        )
        mgr.bind(widget)

        mgr._on_user_message(
            {
                "text": "analyze",
                "attachments": [
                    {"type": "file", "name": "data.csv", "content": "x,y\n1,2"},
                ],
            },
            "chat:user-message",
            "",
        )
        time.sleep(0.5)

        assert received["results"] == ["x,y\n1,2"]
