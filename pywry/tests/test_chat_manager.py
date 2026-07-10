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
- Artifact dispatch for every artifact type
- Asset injection for AG Grid / Plotly / TradingView (emit + anywidget paths)
- @-context attachments and auto-attached widget context
- Edit/Resend flows including provider integration
"""

from __future__ import annotations

import asyncio
import builtins
import pathlib
import threading
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
    TradingViewSeries,
)
from pywry.chat.manager import (
    Attachment,
    ChatContext,
    ChatManager,
    SettingsItem,
    _StreamState,
    _tool_result_text,
)
from pywry.chat.session import AgentCapabilities, PlanEntry
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
# Module-level fixtures and helpers
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


class FakeWidgetNoEmitFire:
    """Widget without ``emit_fire`` — exercises the fallback in ``_emit_fire``."""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def emit(self, event_type: str, data: dict[str, Any]) -> None:
        self.events.append((event_type, data))

    def get_events(self, event_type: str) -> list[dict]:
        return [d for e, d in self.events if e == event_type]


class FakeAnywidget:
    """Stand-in for an anywidget-style widget — captures ``set_trait`` calls."""

    def __init__(self) -> None:
        self.traits: dict[str, Any] = {}
        self.events: list[tuple[str, dict]] = []

    def emit(self, event_type: str, data: dict[str, Any]) -> None:
        self.events.append((event_type, data))

    def emit_fire(self, event_type: str, data: dict[str, Any]) -> None:
        self.events.append((event_type, data))

    def set_trait(self, key: str, value: Any) -> None:
        self.traits[key] = value


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


class _MinimalAsyncProvider:
    """Minimal async-iterable provider used as a stand-in for ChatProvider.

    Subclasses override :meth:`prompt` to yield the updates the test needs.
    """

    async def initialize(self, _caps):
        return AgentCapabilities()

    async def new_session(self, _cwd, mcp_servers=None):
        return "sid"

    async def cancel(self, _sid):
        return None

    async def prompt(self, _sid, _content, _cancel_event=None):
        if False:
            yield  # pragma: no cover


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


# =============================================================================
# Module helpers
# =============================================================================


class TestToolResultText:
    """Test the _tool_result_text content flattener."""

    def test_string(self):
        assert _tool_result_text("hi") == "hi"

    def test_list_of_text_parts(self):
        result = _tool_result_text([{"type": "text", "text": "a"}, {"type": "text", "text": "b"}])
        assert result == "ab"

    def test_list_with_strings(self):
        result = _tool_result_text(["str", {"type": "text", "text": "x"}])
        assert result == "strx"

    def test_other_returns_empty(self):
        assert _tool_result_text(42) == ""
        assert _tool_result_text(None) == ""


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

    def test_attachment_summary_file_with_path(self):
        ctx = ChatContext(
            attachments=[
                Attachment(type="file", name="report.csv", path=pathlib.Path("/data/report.csv")),
            ]
        )
        assert "report.csv" in ctx.attachment_summary
        assert str(pathlib.Path("/data/report.csv")) in ctx.attachment_summary

    def test_attachment_summary_file_without_path(self):
        ctx = ChatContext(attachments=[Attachment(type="file", name="a.csv")])
        assert "a.csv (file)" in ctx.attachment_summary

    def test_attachment_summary_widget(self):
        ctx = ChatContext(
            attachments=[
                Attachment(type="widget", name="@Sales Data", content="data here"),
            ]
        )
        assert "@Sales Data" in ctx.attachment_summary

    def test_context_text_empty(self):
        assert ChatContext().context_text == ""

    def test_context_text_widget(self):
        ctx = ChatContext(
            attachments=[
                Attachment(type="widget", name="@Grid", content="col1,col2\n1,2"),
            ]
        )
        text = ctx.context_text
        assert "Grid" in text
        assert "col1,col2" in text

    def test_context_text_file_with_path(self):
        ctx = ChatContext(
            attachments=[
                Attachment(type="file", name="data.csv", path=pathlib.Path("/tmp/data.csv")),
            ]
        )
        text = ctx.context_text
        assert "data.csv" in text
        assert "Path:" in text

    def test_get_attachment_widget(self):
        ctx = ChatContext(
            attachments=[
                Attachment(type="widget", name="@Sales", content="revenue=100"),
            ]
        )
        assert ctx.get_attachment("Sales") == "revenue=100"
        assert ctx.get_attachment("@Sales") == "revenue=100"

    def test_get_attachment_file_returns_path_string(self):
        ctx = ChatContext(
            attachments=[
                Attachment(type="file", name="data.csv", path=pathlib.Path("/tmp/data.csv")),
            ]
        )
        # File attachments resolve to the path string
        assert "data.csv" in ctx.get_attachment("data.csv")

    def test_get_attachment_not_found(self):
        ctx = ChatContext(attachments=[])
        result = ctx.get_attachment("Missing")
        assert "not found" in result

    def test_wait_for_input_cancel(self):
        ctx = ChatContext()
        ctx.cancel_event.set()
        assert ctx.wait_for_input(timeout=0.1) == ""

    def test_wait_for_input_timeout(self):
        ctx = ChatContext()
        start = time.time()
        assert ctx.wait_for_input(timeout=0.05) == ""
        assert (time.time() - start) < 1.0

    def test_wait_for_input_returns_response(self):
        ctx = ChatContext()
        ctx._input_response = "answer"
        ctx._input_event.set()
        assert ctx.wait_for_input() == "answer"
        assert not ctx._input_event.is_set()


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
# Construction / configuration
# =============================================================================


class TestChatManagerInit:
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

    def test_file_attach_without_accept_types_raises(self):
        with pytest.raises(ValueError, match="file_accept_types is required"):
            ChatManager(handler=echo_handler, enable_file_attach=True)

    def test_file_attach_with_accept_types_ok(self):
        mgr = ChatManager(
            handler=echo_handler,
            enable_file_attach=True,
            file_accept_types=[".csv"],
        )
        assert mgr._file_accept_types == [".csv"]

    def test_context_allowed_roots_resolved(self, tmp_path):
        mgr = ChatManager(
            handler=echo_handler,
            context_allowed_roots=[str(tmp_path)],
        )
        assert mgr._context_allowed_roots == [str(pathlib.Path(tmp_path).resolve())]

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


class TestBind:
    """Test the ``bind()`` method and its lazy anywidget import."""

    def test_bind_to_fake_widget_sets_widget(self, widget):
        mgr = ChatManager(handler=echo_handler)
        mgr.bind(widget)
        assert mgr._widget is widget
        # FakeWidget isn't an anywidget instance
        assert mgr._is_anywidget is False

    def test_bind_falls_back_when_anywidget_missing(self, monkeypatch):
        import sys

        mgr = ChatManager(handler=echo_handler)
        # The lazy ``from ..widget import PyWryChatWidget`` inside bind() must
        # raise to hit the fallback.  Force the cached pywry.widget module to
        # raise on the PyWryChatWidget lookup.
        cached = sys.modules.get("pywry.widget")
        if cached is not None:
            # Create a shim that raises AttributeError → caught as ImportError
            # path requires a real ImportError; replace the module with a
            # module-like object whose attribute access fails.
            class _BrokenWidgetModule:
                def __getattr__(self, name):
                    if name == "PyWryChatWidget":
                        raise ImportError("PyWryChatWidget missing")
                    return getattr(cached, name)

            monkeypatch.setitem(sys.modules, "pywry.widget", _BrokenWidgetModule())

        widget = FakeWidget()
        mgr.bind(widget)
        assert mgr._widget is widget
        assert mgr._is_anywidget is False


class TestToolbarMethod:
    """Test the ``toolbar()`` factory."""

    def test_returns_toolbar_instance(self):
        from pywry.toolbar import Toolbar

        mgr = ChatManager(handler=echo_handler)
        tb = mgr.toolbar()
        assert isinstance(tb, Toolbar)


# =============================================================================
# Handler dispatch
# =============================================================================


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

    def test_handler_exception_emits_error_message(self, widget):
        def bad_handler(messages, ctx):
            raise ValueError("oops")

        mgr = ChatManager(handler=bad_handler)
        mgr.bind(widget)
        mgr._on_user_message(
            {"text": "hi", "threadId": mgr.active_thread_id},
            "chat:user-message",
            "",
        )
        time.sleep(0.3)
        msgs = widget.get_events("chat:assistant-message")
        assert any("Error: oops" in m.get("text", "") for m in msgs)

    def test_user_message_empty_text_returns(self, widget):
        mgr = ChatManager(handler=echo_handler)
        mgr.bind(widget)
        mgr._on_user_message(
            {"text": "   ", "threadId": mgr.active_thread_id},
            "chat:user-message",
            "",
        )
        # No assistant message generated, no typing indicator emitted
        assert widget.get_events("chat:assistant-message") == []
        assert widget.get_events("chat:typing-indicator") == []


class TestHandlerResultDispatch:
    """Cover the four return-value paths for handlers."""

    def test_coroutine_returning_string(self, widget):
        async def handler(messages, ctx):
            return "async-result"

        mgr = ChatManager(handler=handler)
        mgr.bind(widget)
        mgr._on_user_message(
            {"text": "hi", "threadId": mgr.active_thread_id},
            "chat:user-message",
            "",
        )
        time.sleep(0.4)
        msgs = widget.get_events("chat:assistant-message")
        assert any("async-result" in m.get("text", "") for m in msgs)

    def test_coroutine_returning_async_generator(self, widget):
        async def gen():
            yield "x"
            yield "y"

        async def handler(messages, ctx):
            return gen()

        mgr = ChatManager(handler=handler)
        mgr.bind(widget)
        mgr._on_user_message(
            {"text": "hi", "threadId": mgr.active_thread_id},
            "chat:user-message",
            "",
        )
        time.sleep(0.4)
        chunks = widget.get_events("chat:stream-chunk")
        assert chunks

    def test_coroutine_returning_other_type(self, widget):
        async def handler(messages, ctx):
            return 42

        mgr = ChatManager(handler=handler)
        mgr.bind(widget)
        mgr._on_user_message(
            {"text": "hi", "threadId": mgr.active_thread_id},
            "chat:user-message",
            "",
        )
        time.sleep(0.4)
        msgs = widget.get_events("chat:assistant-message")
        assert any("42" in m.get("text", "") for m in msgs)

    def test_sync_iterator_handler(self, widget):
        def handler(messages, ctx):
            return iter(["x", "y"])

        mgr = ChatManager(handler=handler)
        mgr.bind(widget)
        mgr._on_user_message(
            {"text": "hi", "threadId": mgr.active_thread_id},
            "chat:user-message",
            "",
        )
        time.sleep(0.3)
        chunks = widget.get_events("chat:stream-chunk")
        assert chunks

    def test_async_generator_returned_directly(self, widget):
        async def agen():
            yield "x"

        def handler(messages, ctx):
            return agen()

        mgr = ChatManager(handler=handler)
        mgr.bind(widget)
        mgr._on_user_message(
            {"text": "hi", "threadId": mgr.active_thread_id},
            "chat:user-message",
            "",
        )
        time.sleep(0.3)
        chunks = widget.get_events("chat:stream-chunk")
        assert chunks

    def test_other_return_type_stringified(self, widget):
        def handler(messages, ctx):
            return 3.14

        mgr = ChatManager(handler=handler)
        mgr.bind(widget)
        mgr._on_user_message(
            {"text": "hi", "threadId": mgr.active_thread_id},
            "chat:user-message",
            "",
        )
        time.sleep(0.3)
        msgs = widget.get_events("chat:assistant-message")
        assert any("3.14" in m.get("text", "") for m in msgs)


class TestStreamCancelPaths:
    """Cancellation paths in the sync/async stream handlers."""

    def test_handle_stream_cancel_mid_stream(self, widget):
        mgr = ChatManager(handler=echo_handler)
        mgr.bind(widget)

        cancel = threading.Event()

        def gen():
            yield "a"
            cancel.set()
            yield "b"

        mgr._handle_stream(gen(), "msg-1", "thread-1", cancel)
        chunks = widget.get_events("chat:stream-chunk")
        stopped = [c for c in chunks if c.get("stopped")]
        assert stopped

    async def test_handle_async_stream_cancel_path(self, widget):
        mgr = ChatManager(handler=echo_handler)
        mgr.bind(widget)

        cancel = threading.Event()

        async def agen():
            yield "x"
            cancel.set()
            yield "y"

        await mgr._handle_async_stream(agen(), "msg-1", "thread-1", cancel)
        chunks = widget.get_events("chat:stream-chunk")
        stopped = [c for c in chunks if c.get("stopped")]
        assert stopped

    async def test_handle_async_stream_no_items_still_finalizes(self, widget):
        mgr = ChatManager(handler=echo_handler)
        mgr.bind(widget)
        cancel = threading.Event()

        async def agen():
            if False:
                yield  # pragma: no cover

        await mgr._handle_async_stream(agen(), "msg-1", "thread-1", cancel)
        # The async stream must still emit stream-done even on empty output
        chunks = widget.get_events("chat:stream-chunk")
        done = [c for c in chunks if c.get("done")]
        assert done


# =============================================================================
# Asset injection
# =============================================================================


class TestAssetInjection:
    """Test lazy asset injection for AG Grid / Plotly / TradingView."""

    def test_aggrid_assets_inject_via_emit(self, widget):
        mgr = ChatManager(handler=echo_handler)
        mgr.bind(widget)
        mgr._inject_aggrid_assets()
        events = widget.get_events("chat:load-assets")
        assert len(events) == 1
        assert events[0]["scripts"]
        # Idempotent
        mgr._inject_aggrid_assets()
        assert len(widget.get_events("chat:load-assets")) == 1

    def test_plotly_assets_inject_via_emit(self, widget):
        mgr = ChatManager(handler=echo_handler)
        mgr.bind(widget)
        mgr._inject_plotly_assets()
        events = widget.get_events("chat:load-assets")
        assert events
        assert events[0]["scripts"]

    def test_plotly_assets_idempotent_when_include_plotly_true(self, widget):
        # include_plotly=True marks _plotly_assets_sent=True at init —
        # no load-assets event when we call inject afterward.
        mgr = ChatManager(handler=echo_handler, include_plotly=True)
        mgr.bind(widget)
        mgr._inject_plotly_assets()
        assert widget.get_events("chat:load-assets") == []

    def test_tradingview_assets_inject_via_emit(self, widget):
        mgr = ChatManager(handler=echo_handler)
        mgr.bind(widget)
        mgr._inject_tradingview_assets()
        assert widget.get_events("chat:load-assets")
        # Idempotent
        widget.clear()
        mgr._inject_tradingview_assets()
        assert widget.get_events("chat:load-assets") == []

    def test_anywidget_aggrid_uses_set_trait(self):
        mgr = ChatManager(handler=echo_handler)
        w = FakeAnywidget()
        mgr.bind(w)
        mgr._is_anywidget = True
        mgr._inject_aggrid_assets()
        assert "_asset_js" in w.traits
        assert "_asset_css" in w.traits

    def test_anywidget_plotly_uses_set_trait(self):
        mgr = ChatManager(handler=echo_handler)
        w = FakeAnywidget()
        mgr.bind(w)
        mgr._is_anywidget = True
        mgr._inject_plotly_assets()
        assert "_asset_js" in w.traits

    def test_anywidget_tradingview_uses_set_trait(self):
        mgr = ChatManager(handler=echo_handler)
        w = FakeAnywidget()
        mgr.bind(w)
        mgr._is_anywidget = True
        mgr._inject_tradingview_assets()
        assert "_asset_js" in w.traits


# =============================================================================
# Artifact dispatch
# =============================================================================


class TestArtifactDispatch:
    """Test the _dispatch_artifact method for every artifact type."""

    def _setup(self):
        mgr = ChatManager(handler=echo_handler)
        widget = FakeWidget()
        mgr.bind(widget)
        return mgr, widget

    def test_dispatch_code(self):
        mgr, widget = self._setup()
        artifact = CodeArtifact(title="t", content="x = 1", language="python")
        mgr._dispatch_artifact(artifact, "msg-1", "thread-1")
        events = widget.get_events("chat:artifact")
        assert events[0]["content"] == "x = 1"
        assert events[0]["language"] == "python"

    def test_dispatch_markdown(self):
        mgr, widget = self._setup()
        mgr._dispatch_artifact(MarkdownArtifact(title="t", content="# Hi"), "m", "t")
        assert widget.get_events("chat:artifact")[0]["content"] == "# Hi"

    def test_dispatch_html(self):
        mgr, widget = self._setup()
        mgr._dispatch_artifact(HtmlArtifact(title="t", content="<b>x</b>"), "m", "t")
        assert "<b>x</b>" in widget.get_events("chat:artifact")[0]["content"]

    def test_dispatch_table(self):
        mgr, widget = self._setup()
        artifact = TableArtifact(title="t", data=[{"a": 1, "b": 2}])
        mgr._dispatch_artifact(artifact, "m", "t")
        events = widget.get_events("chat:artifact")
        assert events
        assert events[0]["rowData"]
        assert events[0]["columns"]

    def test_dispatch_table_with_column_defs_and_options(self):
        mgr, widget = self._setup()
        artifact = TableArtifact(
            title="t",
            data=[{"a": 1}],
            column_defs=[{"field": "a"}],
            grid_options={"rowHeight": 50},
        )
        mgr._dispatch_artifact(artifact, "m", "t")
        events = widget.get_events("chat:artifact")
        assert events[0]["columnDefs"] == [{"field": "a"}]
        assert events[0]["gridOptions"] == {"rowHeight": 50}

    def test_dispatch_plotly(self):
        mgr, widget = self._setup()
        artifact = PlotlyArtifact(title="t", figure={"data": [], "layout": {}})
        mgr._dispatch_artifact(artifact, "m", "t")
        events = widget.get_events("chat:artifact")
        assert events
        assert events[0]["figure"]["data"] == []

    def test_dispatch_tradingview(self):
        mgr, widget = self._setup()
        artifact = TradingViewArtifact(
            title="t",
            series=[TradingViewSeries(type="candlestick", data=[])],
            options={"timezone": "UTC"},
        )
        mgr._dispatch_artifact(artifact, "m", "t")
        events = widget.get_events("chat:artifact")
        assert events
        assert events[0]["options"] == {"timezone": "UTC"}
        assert events[0]["series"][0]["type"] == "candlestick"

    def test_dispatch_image(self):
        mgr, widget = self._setup()
        mgr._dispatch_artifact(
            ImageArtifact(title="t", url="https://example.com/x.png", alt="x"), "m", "t"
        )
        assert widget.get_events("chat:artifact")[0]["url"] == "https://example.com/x.png"

    def test_dispatch_json(self):
        mgr, widget = self._setup()
        mgr._dispatch_artifact(JsonArtifact(title="t", data={"k": "v"}), "m", "t")
        assert widget.get_events("chat:artifact")[0]["data"] == {"k": "v"}


# =============================================================================
# Session-update dispatcher
# =============================================================================


class TestSessionUpdateDispatch:
    """_dispatch_session_update routes each update type to the right event."""

    def _setup(self):
        mgr = ChatManager(handler=echo_handler)
        widget = FakeWidget()
        mgr.bind(widget)
        return mgr, widget, _StreamState("m")

    def test_dispatch_status(self):
        mgr, widget, state = self._setup()
        mgr._dispatch_session_update(StatusUpdate(text="working"), state, "t", None)
        events = widget.get_events("chat:status-update")
        assert events and events[0]["text"] == "working"

    def test_dispatch_thinking(self):
        mgr, widget, state = self._setup()
        mgr._dispatch_session_update(ThinkingUpdate(text="hmm"), state, "t", None)
        events = widget.get_events("chat:thinking-chunk")
        assert events and events[0]["text"] == "hmm"

    def test_dispatch_citation(self):
        mgr, widget, state = self._setup()
        mgr._dispatch_session_update(
            CitationUpdate(url="https://x", title="T", snippet="s"), state, "t", None
        )
        events = widget.get_events("chat:citation")
        assert events and events[0]["url"] == "https://x"

    def test_dispatch_tool_call_in_progress(self):
        mgr, widget, state = self._setup()
        mgr._dispatch_session_update(
            ToolCallUpdate(toolCallId="t1", name="x", kind="other", status="in_progress"),
            state,
            "t",
            None,
        )
        events = widget.get_events("chat:tool-call")
        assert events and events[0]["name"] == "x"

    def test_dispatch_tool_call_completed_emits_result(self):
        mgr, widget, state = self._setup()
        mgr._dispatch_session_update(
            ToolCallUpdate(
                toolCallId="t1",
                name="x",
                kind="other",
                status="completed",
                content=[{"type": "text", "text": "result"}],
            ),
            state,
            "t",
            None,
        )
        events = widget.get_events("chat:tool-result")
        assert events
        assert events[0]["result"] == "result"

    def test_dispatch_artifact_update(self):
        mgr, widget, state = self._setup()
        mgr._dispatch_session_update(
            ArtifactUpdate(artifact=CodeArtifact(title="x", content="x = 1", language="python")),
            state,
            "t",
            None,
        )
        assert widget.get_events("chat:artifact")

    def test_process_handler_item_artifact_passes_through(self):
        mgr, widget, state = self._setup()
        # ArtifactBase instances dispatched directly (not wrapped in ArtifactUpdate)
        mgr._process_handler_item(MarkdownArtifact(title="x", content="# Hi"), state, "t", None)
        assert widget.get_events("chat:artifact")

    def test_process_handler_item_string_buffers(self):
        mgr, widget, state = self._setup()
        mgr._process_handler_item("hello", state, "t", None)
        # STREAM_FLUSH_INTERVAL=0 → flushed immediately
        assert widget.get_events("chat:stream-chunk")

    def test_process_handler_item_plain_object_silent(self):
        mgr, widget, state = self._setup()
        # Non-string, non-artifact, no .session_update attr — silently dispatches
        # to _dispatch_session_update which has no branch for it.
        mgr._process_handler_item(object(), state, "t", None)
        # Nothing visible came out
        assert widget.get_events("chat:stream-chunk") == []


# =============================================================================
# _is_accepted_file
# =============================================================================


class TestIsAcceptedFile:
    def test_no_filter_accepts_all(self):
        mgr = ChatManager(handler=echo_handler)
        assert mgr._is_accepted_file("anything.zip") is True

    def test_extension_accepted(self):
        mgr = ChatManager(
            handler=echo_handler,
            enable_file_attach=True,
            file_accept_types=[".csv", ".json"],
        )
        assert mgr._is_accepted_file("data.csv") is True
        assert mgr._is_accepted_file("schema.json") is True

    def test_extension_rejected(self):
        mgr = ChatManager(
            handler=echo_handler,
            enable_file_attach=True,
            file_accept_types=[".csv"],
        )
        assert mgr._is_accepted_file("malware.exe") is False


# =============================================================================
# _emit_fire fallback
# =============================================================================


class TestEmitFireFallback:
    def test_widget_without_emit_fire_falls_back_to_emit(self):
        mgr = ChatManager(handler=echo_handler)
        widget = FakeWidgetNoEmitFire()
        mgr.bind(widget)
        mgr._emit_fire("chat:test", {"x": 1})
        assert widget.get_events("chat:test")


# =============================================================================
# Attachment resolution
# =============================================================================


class TestResolveAttachments:
    """Test the public _resolve_attachments method."""

    def test_file_with_path_resolved(self, tmp_path):
        mgr = ChatManager(
            handler=echo_handler,
            enable_file_attach=True,
            file_accept_types=[".csv"],
        )
        f = tmp_path / "x.csv"
        f.write_text("a,b\n1,2")
        result = mgr._resolve_attachments([{"type": "file", "name": "x.csv", "path": str(f)}])
        assert len(result) == 1
        assert result[0].type == "file"
        assert result[0].path == f

    def test_file_with_only_content(self):
        mgr = ChatManager(
            handler=echo_handler,
            enable_file_attach=True,
            file_accept_types=[".csv"],
        )
        result = mgr._resolve_attachments([{"type": "file", "name": "x.csv", "content": "data"}])
        assert len(result) == 1
        assert result[0].content == "data"

    def test_file_rejected_extension(self):
        mgr = ChatManager(
            handler=echo_handler,
            enable_file_attach=True,
            file_accept_types=[".csv"],
        )
        result = mgr._resolve_attachments([{"type": "file", "name": "evil.exe", "content": "x"}])
        assert result == []

    def test_file_no_path_no_content_skipped(self):
        mgr = ChatManager(
            handler=echo_handler,
            enable_file_attach=True,
            file_accept_types=[".csv"],
        )
        result = mgr._resolve_attachments([{"type": "file", "name": "x.csv"}])
        assert result == []

    def test_widget_without_id_skipped(self):
        mgr = ChatManager(handler=echo_handler, enable_context=True)
        result = mgr._resolve_attachments([{"type": "widget"}])
        assert result == []

    def test_no_context_or_file_attach_returns_empty(self):
        mgr = ChatManager(handler=echo_handler)
        result = mgr._resolve_attachments([{"type": "file", "name": "x.csv"}])
        assert result == []


class TestResolveWidgetAttachment:
    """Test the _resolve_widget_attachment helper across binding states."""

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
        first_line = att.content.splitlines()[0]
        assert first_line == "widget_id: chart"
        assert "symbol: AAPL" in att.content
        assert att.source == "chart"
        assert att.name == "@chart"

    def test_registered_source_without_getdata_still_carries_widget_id(self):
        mgr = self._make_mgr()
        mgr.register_context_source("chart", "chart")
        att = mgr._resolve_widget_attachment("chart")
        assert att is not None
        assert "widget_id: chart" in att.content
        assert att.source == "chart"

    def test_unregistered_widget_id_still_yields_attachment_with_id(self):
        mgr = self._make_mgr()
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
        assert att.content.splitlines()[0] == "widget_id: chart"

    def test_no_widget_returns_attachment_with_widget_id(self):
        mgr = ChatManager(handler=echo_handler, enable_context=True)
        # No widget bound
        att = mgr._resolve_widget_attachment("missing-id")
        assert att is not None
        assert "widget_id: missing-id" in att.content

    def test_widget_without_app_attribute_returns_id_only(self):
        mgr = ChatManager(handler=echo_handler, enable_context=True)
        mgr.bind(FakeWidget())  # Has no ._app
        att = mgr._resolve_widget_attachment("missing-widget")
        assert att is not None
        assert "widget_id: missing-widget" in att.content

    def test_widget_with_app_no_inline_widgets(self):
        mgr = ChatManager(handler=echo_handler, enable_context=True)

        class _Widget:
            def __init__(self):
                self._app = MagicMock()
                self._app._inline_widgets = {}

            def emit(self, *_a, **_k):
                pass

        mgr.bind(_Widget())
        att = mgr._resolve_widget_attachment("absent")
        assert att is not None
        assert "widget_id: absent" in att.content

    def test_widget_with_inline_widget_renders_html_size(self):
        mgr = ChatManager(handler=echo_handler, enable_context=True)

        class _InlineWidget:
            label = "MyChart"
            html = "<h1>chart</h1>"

        class _App:
            def __init__(self):
                self._inline_widgets = {"chart-id": _InlineWidget()}

        class _Widget:
            def __init__(self):
                self._app = _App()

            def emit(self, *_a, **_k):
                pass

        mgr.bind(_Widget())
        att = mgr._resolve_widget_attachment("chart-id")
        assert att is not None
        assert "widget_id: chart-id" in att.content
        assert "MyChart" in att.content
        assert "HTML widget" in att.content

    def test_resolve_widget_attachment_handles_exception(self):
        mgr = ChatManager(handler=echo_handler, enable_context=True)

        class _BadWidget:
            @property
            def _app(self):
                raise RuntimeError("boom")

            def emit(self, *_a, **_k):
                pass

        mgr.bind(_BadWidget())
        att = mgr._resolve_widget_attachment("foo")
        assert att is not None
        assert "widget_id: foo" in att.content


class TestGetContextSources:
    """Test the context-source enumeration used by the @-mention popup."""

    def test_returns_registered_sources(self):
        mgr = ChatManager(handler=echo_handler, enable_context=True)
        mgr.register_context_source("a", "Alpha")
        mgr.register_context_source("b", "Beta")
        sources = mgr._get_context_sources()
        ids = {s["id"] for s in sources}
        assert ids == {"a", "b"}

    def test_includes_inline_widgets_not_in_registry(self):
        mgr = ChatManager(handler=echo_handler, enable_context=True)
        mgr.register_context_source("registered", "Reg")

        class _Inline:
            label = "InlineWidget"

        class _App:
            def __init__(self):
                self._inline_widgets = {
                    "registered": _Inline(),
                    "auto": _Inline(),
                }

        class _Widget:
            def __init__(self):
                self._app = _App()

            def emit(self, *_a, **_k):
                pass

        mgr.bind(_Widget())
        sources = mgr._get_context_sources()
        ids = {s["id"] for s in sources}
        assert "auto" in ids
        # Only one entry per id
        assert len([s for s in sources if s["id"] == "registered"]) == 1

    def test_handles_app_lookup_error(self):
        mgr = ChatManager(handler=echo_handler, enable_context=True)

        class _BadApp:
            @property
            def _inline_widgets(self):
                raise RuntimeError("boom")

        class _Widget:
            _app = _BadApp()

            def emit(self, *_a, **_k):
                pass

        mgr.bind(_Widget())
        assert mgr._get_context_sources() == []


# =============================================================================
# Auto-attached registered context sources
# =============================================================================


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
        assert m._auto_attach_context_sources([]) == []

    def test_no_auto_attach_when_no_sources_registered(self):
        assert self._make_mgr()._auto_attach_context_sources([]) == []

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
        assert "widget_id: chart" in injected
        assert "switch to MSFT" in injected


class TestInjectContext:
    """Direct tests for _inject_context."""

    def test_explicit_file_attachment_emits_tool_card(self, tmp_path):
        mgr = ChatManager(
            handler=echo_handler,
            enable_file_attach=True,
            file_accept_types=[".csv"],
        )
        widget = FakeWidget()
        mgr.bind(widget)

        ctx = ChatContext(
            attachments=[
                Attachment(
                    type="file",
                    name="data.csv",
                    path=tmp_path / "data.csv",
                    auto_attached=False,
                ),
            ]
        )
        messages = [{"role": "user", "text": "use it"}]
        result = mgr._inject_context(messages, ctx, "m", "t")
        # Tool-call + tool-result cards emitted
        assert widget.get_events("chat:tool-call")
        assert widget.get_events("chat:tool-result")
        # Last user message was prefixed with the context block
        last_user = next(m for m in result if m["role"] == "user")
        assert "data.csv" in last_user["text"]

    def test_widget_attachment_no_path_uses_attach_widget_card(self):
        mgr = ChatManager(handler=echo_handler, enable_context=True)
        widget = FakeWidget()
        mgr.bind(widget)
        ctx = ChatContext(
            attachments=[
                Attachment(
                    type="widget",
                    name="@chart",
                    content="widget_id: chart\nsymbol: BTC",
                    auto_attached=False,
                ),
            ]
        )
        messages = [{"role": "user", "text": "what is this?"}]
        mgr._inject_context(messages, ctx, "m", "t")
        cards = widget.get_events("chat:tool-call")
        assert any(c.get("name") == "attach_widget" for c in cards)
        results = widget.get_events("chat:tool-result")
        assert any("Attached chart" in r.get("result", "") for r in results)

    def test_no_user_message_passes_through(self):
        mgr = ChatManager(handler=echo_handler, enable_context=True)
        mgr.bind(FakeWidget())
        ctx = ChatContext(attachments=[Attachment(type="widget", name="@x", content="ctx")])
        messages = [{"role": "system", "text": "sys"}]
        # No user message — system passes through unchanged
        assert mgr._inject_context(messages, ctx, "m", "t") == messages


# =============================================================================
# Thread CRUD
# =============================================================================


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

    def test_switch_unknown_thread_no_op(self, bound_manager):
        bound_manager._on_thread_switch({"threadId": "nope"}, "chat:thread-switch", "")
        assert bound_manager.active_thread_id != "nope"

    def test_switch_emits_existing_messages(self, bound_manager, widget):
        # Add a thread with messages
        bound_manager._on_thread_create({"title": "T2"}, "chat:thread-create", "")
        new_tid = bound_manager.active_thread_id
        bound_manager._threads[new_tid] = [
            {"id": "1", "role": "user", "text": "u"},
            {"id": "2", "role": "assistant", "text": "a"},
        ]
        widget.clear()
        bound_manager._on_thread_switch({"threadId": new_tid}, "chat:thread-switch", "")
        msgs = widget.get_events("chat:assistant-message")
        assert len(msgs) == 2
        assert any(m.get("role") == "user" for m in msgs)


# =============================================================================
# State management / request-state
# =============================================================================


class TestChatManagerState:
    """Test the request-state and settings-change event handlers."""

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

    def test_clear_history_setting_clears_active_thread(self, bound_manager, widget):
        tid = bound_manager.active_thread_id
        bound_manager._threads[tid] = [{"id": "1", "role": "user", "text": "x"}]
        bound_manager._on_settings_change_event(
            {"key": "clear-history", "value": True},
            "chat:settings-change",
            "",
        )
        assert bound_manager._threads[tid] == []
        assert widget.get_events("chat:clear")

    def test_slash_command_clear(self, bound_manager, widget):
        tid = bound_manager.active_thread_id
        bound_manager.send_message("test")
        assert len(bound_manager.threads[tid]) == 1
        bound_manager._on_slash_command_event({"command": "/clear", "threadId": tid}, "", "")
        assert len(bound_manager.threads[tid]) == 0


class TestSlashCommandAndSettingsEmission:
    """Test slash-command / settings-item / context-source emission paths."""

    def test_slash_command_models_emitted(self, widget):
        from pywry.chat.models import ACPCommand

        cmds = [ACPCommand(name="web", description="search the web")]
        mgr = ChatManager(handler=echo_handler, slash_commands=cmds)
        mgr.bind(widget)
        mgr._on_request_state({}, "chat:request-state", "")
        cmd_events = widget.get_events("chat:register-command")
        names = [e["name"] for e in cmd_events]
        assert "web" in names
        assert "/clear" in names

    def test_settings_items_registered(self, widget):
        mgr = ChatManager(
            handler=echo_handler,
            settings=[SettingsItem(id="model", label="Model", type="select", options=["a", "b"])],
        )
        mgr.bind(widget)
        mgr._on_request_state({}, "chat:request-state", "")
        settings_events = widget.get_events("chat:register-settings-item")
        assert len(settings_events) == 1
        assert settings_events[0]["id"] == "model"

    def test_context_sources_emitted_when_enabled(self, widget):
        mgr = ChatManager(handler=echo_handler, enable_context=True)
        mgr.register_context_source("c1", "Chart")
        mgr.bind(widget)
        mgr._on_request_state({}, "chat:request-state", "")
        events = widget.get_events("chat:context-sources")
        assert events
        assert events[0]["sources"][0]["id"] == "c1"


class TestSmallEventHandlers:
    """todo-clear / input-response / slash-command delegation."""

    def test_todo_clear_emits_empty_items(self, widget):
        mgr = ChatManager(handler=echo_handler)
        mgr.bind(widget)
        mgr._on_todo_clear({}, "chat:todo-clear", "")
        assert widget.get_events("chat:todo-update") == [{"items": []}]

    def test_input_response_no_pending_request_no_op(self):
        mgr = ChatManager(handler=echo_handler)
        # No pending input — silently dropped
        mgr._on_input_response(
            {"text": "hi", "requestId": "req-x", "threadId": mgr.active_thread_id},
            "chat:input-response",
            "",
        )

    def test_input_response_resolves_pending(self):
        mgr = ChatManager(handler=echo_handler)
        ctx = ChatContext()
        mgr._pending_inputs["req-1"] = {"ctx": ctx}
        mgr._on_input_response(
            {"text": "answer", "requestId": "req-1", "threadId": mgr.active_thread_id},
            "chat:input-response",
            "",
        )
        assert ctx._input_response == "answer"
        assert ctx._input_event.is_set()
        assert mgr._threads[mgr.active_thread_id]

    def test_slash_command_delegates_to_user_handler(self):
        seen: list = []

        def on_slash(name, args, tid):
            seen.append((name, args, tid))

        mgr = ChatManager(handler=echo_handler, on_slash_command=on_slash)
        mgr.bind(FakeWidget())
        mgr._on_slash_command_event(
            {"command": "/foo", "args": "x y", "threadId": mgr.active_thread_id},
            "chat:slash-command",
            "",
        )
        assert seen == [("/foo", "x y", mgr.active_thread_id)]


# =============================================================================
# Edit / Resend Tests
# =============================================================================


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
        time.sleep(0.2)
        deletions = widget.get_events("chat:messages-deleted")
        assert deletions, "expected at least one chat:messages-deleted event"
        d = deletions[0]
        assert d["editedMessageId"] == "msg_user_2"
        assert d["editedText"] == "REVISED"
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
        edited = next(m for m in thread if m.get("id") == "msg_user_2")
        assert edited["text"] == "REVISED"

    def test_edit_unknown_message_is_noop(self, bound_manager, widget):
        tid, msgs = _seed_thread(bound_manager)
        bound_manager._on_edit_message(
            {"messageId": "ghost", "threadId": tid, "text": "x"},
            "chat:edit-message",
            "",
        )
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

    def test_edit_cancels_active_generation(self, widget):
        mgr = ChatManager(handler=echo_handler)
        mgr.bind(widget)
        tid = mgr.active_thread_id
        cancel = threading.Event()
        mgr._cancel_events[tid] = cancel
        mgr._threads[tid] = [
            {"id": "msg_user_1", "role": "user", "text": "first"},
            {"id": "msg_asst_1", "role": "assistant", "text": "reply"},
        ]
        mgr._on_edit_message(
            {"messageId": "msg_user_1", "threadId": tid, "text": "REVISED"},
            "chat:edit-message",
            "",
        )
        time.sleep(0.2)
        assert cancel.is_set()


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
        # The target user message stays — only the assistant reply (and any
        # subsequent turns) are dropped so "Resend" doesn't read as "your
        # message was erased".
        assert d["messageIds"] == ["msg_asst_2"]
        assert "editedMessageId" not in d
        assert "editedText" not in d
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
        assert [m["id"] for m in bound_manager._threads[tid]] == [m["id"] for m in msgs]

    def test_resend_empty_message_id_returns(self, widget):
        mgr = ChatManager(handler=echo_handler)
        mgr.bind(widget)
        mgr._on_resend_from(
            {"messageId": "", "threadId": mgr.active_thread_id},
            "chat:resend-from",
            "",
        )
        assert widget.get_events("chat:messages-deleted") == []

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

    def test_resend_cancels_active_generation(self, widget):
        mgr = ChatManager(handler=echo_handler)
        mgr.bind(widget)
        tid = mgr.active_thread_id
        cancel = threading.Event()
        mgr._cancel_events[tid] = cancel
        mgr._threads[tid] = [
            {"id": "msg_user_1", "role": "user", "text": "first"},
            {"id": "msg_asst_1", "role": "assistant", "text": "reply"},
        ]
        mgr._on_resend_from(
            {"messageId": "msg_user_1", "threadId": tid},
            "chat:resend-from",
            "",
        )
        time.sleep(0.2)
        assert cancel.is_set()


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
        msgs = bound_manager._threads[tid]
        asst = [m for m in msgs if m.get("role") == "assistant"]
        assert asst
        assert asst[0]["id"].startswith("msg_")


# =============================================================================
# Provider integration
# =============================================================================


class TestProviderRun:
    """Test the ACP-provider execution path through _run_provider."""

    def test_provider_exception_emits_error_message(self, widget):
        class _Provider(_MinimalAsyncProvider):
            async def prompt(self, _sid, _content, _cancel_event=None):
                raise RuntimeError("provider boom")
                if False:
                    yield  # pragma: no cover

        mgr = ChatManager(provider=_Provider())
        mgr.bind(widget)
        mgr._on_user_message(
            {"text": "hi", "threadId": mgr.active_thread_id},
            "chat:user-message",
            "",
        )
        time.sleep(0.5)
        msgs = widget.get_events("chat:assistant-message")
        assert any("Error: provider boom" in m.get("text", "") for m in msgs)

    async def test_provider_no_updates_still_clears_typing_indicator(self, widget):
        """When the provider yields zero updates, the after-loop typing-off
        emit still runs."""

        class _Provider(_MinimalAsyncProvider):
            async def prompt(self, _sid, _content, _cancel_event=None):
                # Yield no updates — typing_hidden stays False inside _run_provider
                if False:
                    yield  # pragma: no cover

        mgr = ChatManager(provider=_Provider())
        mgr.bind(widget)
        mgr._on_user_message(
            {"text": "hi", "threadId": mgr.active_thread_id},
            "chat:user-message",
            "",
        )
        time.sleep(0.4)
        events = widget.get_events("chat:typing-indicator")
        offs = [e for e in events if e.get("typing") is False]
        assert offs


class TestTruncateProviderState:
    """_truncate_provider_state forwards to provider.truncate_session."""

    def test_no_provider_no_op(self):
        mgr = ChatManager(handler=echo_handler)
        mgr._truncate_provider_state("t", [])  # silent

    def test_calls_provider_truncate_session(self):
        called: list = []

        class _Provider(_MinimalAsyncProvider):
            def truncate_session(self, sid, kept):
                called.append((sid, kept))

        mgr = ChatManager(provider=_Provider())
        mgr._truncate_provider_state("thread-1", [{"id": "x"}])
        assert called == [("thread-1", [{"id": "x"}])]

    def test_provider_without_truncate_session_no_op(self):
        mgr = ChatManager(provider=_MinimalAsyncProvider())
        mgr._truncate_provider_state("t", [])

    def test_provider_truncate_exception_swallowed(self):
        class _Provider(_MinimalAsyncProvider):
            def truncate_session(self, _sid, _kept):
                raise RuntimeError("boom")

        mgr = ChatManager(provider=_Provider())
        mgr._truncate_provider_state("t", [])


class TestResendWithProvider:
    def test_resend_with_provider_runs_provider_path(self, widget):
        """The resend dispatch picks the provider path when ``_provider`` is set."""

        class _Provider(_MinimalAsyncProvider):
            async def prompt(self, _sid, _content, _cancel_event=None):
                yield AgentMessageUpdate(text="provider-reply")

        mgr = ChatManager(provider=_Provider())
        mgr.bind(widget)
        tid = mgr.active_thread_id
        mgr._threads[tid] = [
            {"id": "msg_user_1", "role": "user", "text": "first"},
            {"id": "msg_asst_1", "role": "assistant", "text": "reply"},
        ]
        mgr._on_resend_from(
            {"messageId": "msg_user_1", "threadId": tid},
            "chat:resend-from",
            "",
        )
        time.sleep(0.5)
        assert any(
            "provider-reply" in c.get("chunk", "") for c in widget.get_events("chat:stream-chunk")
        )
