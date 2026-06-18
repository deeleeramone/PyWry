"""Unit tests for the chat component.

Tests cover:
- ChatStateMixin: all chat state management methods
- ChatStore ABC + MemoryChatStore implementation
- Chat builder functions
- build_chat_html
- Provider factory
- Session primitives
- SessionUpdate types
- Artifacts validation
- Permissions

Model tests live in ``test_chat_models.py``.
"""

from __future__ import annotations

from typing import Any

import pytest

from pywry.chat import (
    ChatMessage,
    ChatThread,
    build_chat_html,
)
from pywry.state_mixins import ChatStateMixin, EmittingWidget


# =============================================================================
# Fixtures
# =============================================================================


class MockEmitter(EmittingWidget):
    """Mock emitter for testing chat mixin."""

    def __init__(self) -> None:
        self.emitted_events: list[tuple[str, dict]] = []

    def emit(self, event_type: str, data: dict[str, Any]) -> None:
        self.emitted_events.append((event_type, data))

    def get_last_event(self) -> tuple[str, dict[str, Any]] | None:
        return self.emitted_events[-1] if self.emitted_events else None

    def get_events_by_type(self, event_type: str) -> list[dict]:
        return [data for evt, data in self.emitted_events if evt == event_type]


class MockChatWidget(MockEmitter, ChatStateMixin):
    """Mock widget combining emitter with ChatStateMixin."""


# =============================================================================
# ChatStateMixin Tests
# =============================================================================


class TestChatStateMixin:
    """Test ChatStateMixin event emission."""

    def test_send_chat_message(self) -> None:
        w = MockChatWidget()
        w.send_chat_message("Hello!", thread_id="t_1", message_id="msg_1")
        evt_type, data = w.get_last_event()
        assert evt_type == "chat:assistant-message"
        assert data["messageId"] == "msg_1"
        assert data["text"] == "Hello!"

    def test_stream_chat_chunk(self) -> None:
        w = MockChatWidget()
        w.stream_chat_chunk("tok", "msg_1", thread_id="t_1")
        evt_type, data = w.get_last_event()
        assert evt_type == "chat:stream-chunk"
        assert data["chunk"] == "tok"
        assert data["done"] is False

    def test_set_chat_typing(self) -> None:
        w = MockChatWidget()
        w.set_chat_typing(True)
        evt_type, data = w.get_last_event()
        assert evt_type == "chat:typing-indicator"
        assert data["typing"] is True

    def test_switch_chat_thread(self) -> None:
        w = MockChatWidget()
        w.switch_chat_thread("t_2")
        evt_type, data = w.get_last_event()
        assert evt_type == "chat:switch-thread"
        assert data["threadId"] == "t_2"

    def test_clear_chat(self) -> None:
        w = MockChatWidget()
        w.clear_chat()
        evt_type, _ = w.get_last_event()
        assert evt_type == "chat:clear"

    def test_register_chat_command(self) -> None:
        w = MockChatWidget()
        w.register_chat_command("/help", "Show help")
        evt_type, data = w.get_last_event()
        assert evt_type == "chat:register-command"
        assert data["name"] == "/help"

    def test_request_chat_state(self) -> None:
        w = MockChatWidget()
        w.request_chat_state()
        evt_type, _ = w.get_last_event()
        assert evt_type == "chat:request-state"


# =============================================================================
# MemoryChatStore Tests
# =============================================================================


class TestMemoryChatStore:
    """Test MemoryChatStore implementation."""

    @pytest.fixture
    def store(self):
        from pywry.state.memory import MemoryChatStore

        return MemoryChatStore()

    @pytest.mark.asyncio
    async def test_save_and_get_thread(self, store) -> None:
        thread = ChatThread(thread_id="t1", title="Test")
        await store.save_thread("w1", thread)
        result = await store.get_thread("w1", "t1")
        assert result is not None
        assert result.thread_id == "t1"

    @pytest.mark.asyncio
    async def test_list_threads(self, store) -> None:
        await store.save_thread("w1", ChatThread(thread_id="t1", title="Chat 1"))
        await store.save_thread("w1", ChatThread(thread_id="t2", title="Chat 2"))
        threads = await store.list_threads("w1")
        assert len(threads) == 2

    @pytest.mark.asyncio
    async def test_delete_thread(self, store) -> None:
        await store.save_thread("w1", ChatThread(thread_id="t1", title="Chat"))
        await store.delete_thread("w1", "t1")
        result = await store.get_thread("w1", "t1")
        assert result is None

    @pytest.mark.asyncio
    async def test_append_message(self, store) -> None:
        await store.save_thread("w1", ChatThread(thread_id="t1", title="Chat"))
        msg = ChatMessage(role="user", content="Hello")
        await store.append_message("w1", "t1", msg)
        messages = await store.get_messages("w1", "t1")
        assert len(messages) == 1
        assert messages[0].text_content() == "Hello"

    @pytest.mark.asyncio
    async def test_get_messages_pagination(self, store) -> None:
        await store.save_thread("w1", ChatThread(thread_id="t1", title="Chat"))
        for i in range(5):
            msg = ChatMessage(role="user", content=f"msg{i}", message_id=f"m{i}")
            await store.append_message("w1", "t1", msg)
        messages = await store.get_messages("w1", "t1", limit=3)
        assert len(messages) == 3

    @pytest.mark.asyncio
    async def test_clear_messages(self, store) -> None:
        await store.save_thread("w1", ChatThread(thread_id="t1", title="Chat"))
        await store.append_message("w1", "t1", ChatMessage(role="user", content="Hello"))
        await store.clear_messages("w1", "t1")
        messages = await store.get_messages("w1", "t1")
        assert len(messages) == 0

    @pytest.mark.asyncio
    async def test_get_nonexistent_thread(self, store) -> None:
        result = await store.get_thread("w1", "nonexistent")
        assert result is None


# =============================================================================
# Builder Tests
# =============================================================================


class TestChatBuilders:
    """Test chat builder functions."""

    def test_build_chat_config(self) -> None:
        from pywry.mcp.builders import build_chat_config

        config = build_chat_config(
            {
                "model": "claude-3",
                "temperature": 0.5,
                "system_prompt": "Be helpful",
            }
        )
        assert config.model == "claude-3"
        assert config.temperature == 0.5
        assert config.system_prompt == "Be helpful"

    def test_build_chat_config_defaults(self) -> None:
        from pywry.mcp.builders import build_chat_config

        config = build_chat_config({})
        assert config.model == "gpt-4"
        assert config.streaming is True

    def test_build_chat_widget_config(self) -> None:
        from pywry.mcp.builders import build_chat_widget_config

        config = build_chat_widget_config(
            {
                "title": "My Chat",
                "height": 700,
                "model": "gpt-4o",
                "show_sidebar": False,
            }
        )
        assert config.title == "My Chat"
        assert config.chat_config.model == "gpt-4o"
        assert config.show_sidebar is False


# =============================================================================
# build_chat_html Tests
# =============================================================================


class TestBuildChatHtml:
    """Test build_chat_html helper."""

    def test_default_includes_sidebar(self) -> None:
        html = build_chat_html()
        assert "pywry-chat-sidebar" in html
        assert "pywry-chat-messages" in html
        assert "pywry-chat-input" in html

    def test_no_sidebar(self) -> None:
        html = build_chat_html(show_sidebar=False)
        assert "pywry-chat-sidebar" not in html

    def test_no_settings(self) -> None:
        html = build_chat_html(show_settings=False)
        assert "pywry-chat-settings-toggle" not in html

    def test_container_id(self) -> None:
        html = build_chat_html(container_id="my-chat")
        assert 'id="my-chat"' in html

    def test_file_attach_disabled_by_default(self) -> None:
        html = build_chat_html()
        assert "pywry-chat-attach-btn" not in html

    def test_file_attach_enabled(self) -> None:
        html = build_chat_html(enable_file_attach=True, file_accept_types=[".csv"])
        assert "pywry-chat-attach-btn" in html
        assert "pywry-chat-drop-overlay" in html


# =============================================================================
# Provider Tests
# =============================================================================


class TestProviderFactory:
    """Test provider factory function."""

    def test_callback_provider(self) -> None:
        from pywry.chat import get_provider

        provider = get_provider("callback")
        assert provider is not None

    def test_openai_provider_name_resolves(self) -> None:
        pytest.importorskip("openai")
        from pywry.chat import get_provider

        provider = get_provider("openai", api_key="sk-test")
        assert type(provider).__name__ == "OpenAIProvider"

    def test_unknown_provider_raises(self) -> None:
        from pywry.chat import get_provider

        with pytest.raises(ValueError, match="Unknown provider"):
            get_provider("nonexistent")


# =============================================================================
# Session Primitives Tests
# =============================================================================


class TestSessionPrimitives:
    """Test ACP session models."""

    def test_session_mode(self) -> None:
        from pywry.chat.session import SessionMode

        mode = SessionMode(id="code", name="Code Mode", description="Write code")
        assert mode.id == "code"
        assert mode.name == "Code Mode"

    def test_session_config_option(self) -> None:
        from pywry.chat.session import ConfigOptionChoice, SessionConfigOption

        opt = SessionConfigOption(
            id="model",
            name="Model",
            category="model",
            currentValue="gpt-4",
            options=[
                ConfigOptionChoice(value="gpt-4", name="GPT-4"),
                ConfigOptionChoice(value="gpt-4o", name="GPT-4o"),
            ],
        )
        assert opt.current_value == "gpt-4"
        assert len(opt.options) == 2

    def test_plan_entry(self) -> None:
        from pywry.chat.session import PlanEntry

        entry = PlanEntry(content="Fix the bug", priority="high", status="in_progress")
        assert entry.priority == "high"
        assert entry.status == "in_progress"

    def test_permission_request(self) -> None:
        from pywry.chat.session import PermissionRequest

        req = PermissionRequest(toolCallId="call_1", title="Execute shell command")
        assert req.tool_call_id == "call_1"
        assert len(req.options) == 4  # default options

    def test_capabilities(self) -> None:
        from pywry.chat.session import AgentCapabilities, ClientCapabilities

        client = ClientCapabilities(fileSystem=True, terminal=False)
        assert client.file_system is True

        agent = AgentCapabilities(loadSession=True, configOptions=True)
        assert agent.load_session is True


# =============================================================================
# Update Types Tests
# =============================================================================


class TestUpdateTypes:
    """Test SessionUpdate models."""

    def test_agent_message_update(self) -> None:
        from pywry.chat.updates import AgentMessageUpdate

        u = AgentMessageUpdate(text="Hello")
        assert u.session_update == "agent_message"
        assert u.text == "Hello"

    def test_tool_call_update(self) -> None:
        from pywry.chat.updates import ToolCallUpdate

        u = ToolCallUpdate(
            toolCallId="call_1",
            name="search",
            kind="fetch",
            status="in_progress",
        )
        assert u.session_update == "tool_call"
        assert u.status == "in_progress"

    def test_plan_update(self) -> None:
        from pywry.chat.session import PlanEntry
        from pywry.chat.updates import PlanUpdate

        u = PlanUpdate(
            entries=[
                PlanEntry(content="Step 1", priority="high", status="completed"),
                PlanEntry(content="Step 2", priority="medium", status="pending"),
            ]
        )
        assert u.session_update == "plan"
        assert len(u.entries) == 2

    def test_status_update(self) -> None:
        from pywry.chat.updates import StatusUpdate

        u = StatusUpdate(text="Searching...")
        assert u.session_update == "x_status"

    def test_thinking_update(self) -> None:
        from pywry.chat.updates import ThinkingUpdate

        u = ThinkingUpdate(text="Let me think about this...")
        assert u.session_update == "x_thinking"


# =============================================================================
# Artifact Tests
# =============================================================================


class TestArtifacts:
    """Test artifact models."""

    def test_code_artifact(self) -> None:
        from pywry.chat.artifacts import CodeArtifact

        a = CodeArtifact(title="example.py", content="x = 42", language="python")
        assert a.artifact_type == "code"

    def test_tradingview_artifact(self) -> None:
        from pywry.chat.artifacts import TradingViewArtifact, TradingViewSeries

        a = TradingViewArtifact(
            title="AAPL",
            series=[
                TradingViewSeries(
                    type="candlestick",
                    data=[
                        {"time": "2024-01-02", "open": 185, "high": 186, "low": 184, "close": 185}
                    ],
                ),
                TradingViewSeries(
                    type="line",
                    data=[{"time": "2024-01-02", "value": 185}],
                    options={"color": "#f9e2af"},
                ),
            ],
            height="500px",
        )
        assert a.artifact_type == "tradingview"
        assert len(a.series) == 2
        assert a.series[0].type == "candlestick"
        assert a.series[1].type == "line"

    def test_image_artifact_blocks_javascript_url(self) -> None:
        from pydantic import ValidationError

        from pywry.chat.artifacts import ImageArtifact

        with pytest.raises(ValidationError):
            ImageArtifact(url="javascript:alert(1)")


# =============================================================================
# Permissions Tests
# =============================================================================


class TestPermissions:
    """Test RBAC permission mappings."""

    def test_permission_map(self) -> None:
        from pywry.chat.permissions import ACP_PERMISSION_MAP

        assert ACP_PERMISSION_MAP["session/prompt"] == "write"
        assert ACP_PERMISSION_MAP["fs/write_text_file"] == "admin"
        assert ACP_PERMISSION_MAP["fs/read_text_file"] == "read"

    @pytest.mark.asyncio
    async def test_check_permission_no_session(self) -> None:
        from pywry.chat.permissions import check_acp_permission

        result = await check_acp_permission(None, "w1", "session/prompt", None)
        assert result is True  # No auth = allow all
