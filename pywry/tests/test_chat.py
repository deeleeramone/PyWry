"""Unit tests for the chat component.

Tests cover:
- Chat Pydantic models (ChatMessage, ChatThread, ChatConfig, etc.)
- GenerationHandle (cancel, append_chunk, partial_content, is_expired)
- ChatStateMixin: all chat state management methods
- ChatStore ABC + MemoryChatStore implementation
- Chat builder functions
"""

from __future__ import annotations

import time

from typing import Any

import pytest

from pywry.chat import (
    GENERATION_HANDLE_TTL,
    MAX_CONTENT_LENGTH,
    ChatConfig,
    ChatMessage,
    ChatThread,
    ChatWidgetConfig,
    GenerationHandle,
    ImagePart,
    ResourceLinkPart,
    SlashCommand,
    TextPart,
    ToolCall,
    ToolCallFunction,
    _default_slash_commands,
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
# ChatMessage Tests
# =============================================================================


class TestChatMessage:
    """Test ChatMessage model."""

    def test_basic_creation(self) -> None:
        msg = ChatMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.text_content() == "Hello"
        assert msg.message_id  # auto-generated
        assert msg.stopped is False

    def test_string_content(self) -> None:
        msg = ChatMessage(role="assistant", content="Hi there")
        assert msg.text_content() == "Hi there"

    def test_list_content_text_parts(self) -> None:
        msg = ChatMessage(
            role="assistant",
            content=[
                TextPart(text="Hello "),
                TextPart(text="world"),
            ],
        )
        assert msg.text_content() == "Hello world"

    def test_list_content_mixed_parts(self) -> None:
        msg = ChatMessage(
            role="assistant",
            content=[
                TextPart(text="See image: "),
                ImagePart(data="base64data", mime_type="image/png"),
            ],
        )
        assert msg.text_content() == "See image: "

    def test_content_length_validation(self) -> None:
        # Should not raise for content within limit
        msg = ChatMessage(role="user", content="x" * 100)
        assert len(msg.text_content()) == 100

    def test_content_too_long_raises(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ChatMessage(role="user", content="x" * (MAX_CONTENT_LENGTH + 1))

    def test_tool_calls(self) -> None:
        msg = ChatMessage(
            role="assistant",
            content="I'll search for that.",
            tool_calls=[
                ToolCall(
                    id="call_1",
                    function=ToolCallFunction(
                        name="search",
                        arguments='{"query": "test"}',
                    ),
                ),
            ],
        )
        assert len(msg.tool_calls) == 1
        assert msg.tool_calls[0].function.name == "search"

    def test_stopped_field(self) -> None:
        msg = ChatMessage(role="assistant", content="Partial", stopped=True)
        assert msg.stopped is True

    def test_metadata(self) -> None:
        msg = ChatMessage(
            role="assistant",
            content="Result",
            metadata={"model": "gpt-4", "usage": {"tokens": 42}},
        )
        assert msg.metadata["model"] == "gpt-4"


class TestChatThread:
    """Test ChatThread model."""

    def test_creation(self) -> None:
        thread = ChatThread(thread_id="t1", title="Test Thread")
        assert thread.thread_id == "t1"
        assert thread.title == "Test Thread"
        assert thread.messages == []

    def test_with_messages(self) -> None:
        msg = ChatMessage(role="user", content="Hello")
        thread = ChatThread(thread_id="t1", title="Chat", messages=[msg])
        assert len(thread.messages) == 1


class TestSlashCommand:
    """Test SlashCommand model."""

    def test_auto_prefix(self) -> None:
        cmd = SlashCommand(name="clear", description="Clear chat")
        assert cmd.name == "/clear"

    def test_already_prefixed(self) -> None:
        cmd = SlashCommand(name="/help", description="Help")
        assert cmd.name == "/help"


class TestChatConfig:
    """Test ChatConfig model."""

    def test_defaults(self) -> None:
        config = ChatConfig()
        assert config.model == "gpt-4"
        assert config.temperature == 0.7
        assert config.max_tokens == 4096
        assert config.streaming is True
        assert config.persist is False

    def test_custom_values(self) -> None:
        config = ChatConfig(
            system_prompt="You are helpful.",
            model="claude-3",
            temperature=0.3,
        )
        assert config.system_prompt == "You are helpful."
        assert config.model == "claude-3"


class TestChatWidgetConfig:
    """Test ChatWidgetConfig model."""

    def test_defaults(self) -> None:
        config = ChatWidgetConfig()
        assert config.title == "Chat"
        assert config.height == 700
        assert config.show_sidebar is True

    def test_with_chat_config(self) -> None:
        config = ChatWidgetConfig(
            title="AI Assistant",
            chat_config=ChatConfig(model="gpt-4o"),
        )
        assert config.chat_config.model == "gpt-4o"


class TestDefaultSlashCommands:
    """Test _default_slash_commands."""

    def test_returns_commands(self) -> None:
        cmds = _default_slash_commands()
        assert len(cmds) == 4
        names = [c.name for c in cmds]
        assert "/clear" in names
        assert "/export" in names
        assert "/model" in names
        assert "/system" in names


# =============================================================================
# GenerationHandle Tests
# =============================================================================


class TestGenerationHandle:
    """Test GenerationHandle dataclass."""

    def test_creation(self) -> None:
        handle = GenerationHandle(
            message_id="msg_1",
            widget_id="w_1",
            thread_id="t_1",
        )
        assert handle.message_id == "msg_1"
        assert not handle.cancel_event.is_set()

    def test_cancel(self) -> None:
        handle = GenerationHandle(
            message_id="msg_1",
            widget_id="w_1",
            thread_id="t_1",
        )
        handle.cancel()
        assert handle.cancel_event.is_set()

    def test_append_chunk(self) -> None:
        handle = GenerationHandle(
            message_id="msg_1",
            widget_id="w_1",
            thread_id="t_1",
        )
        handle.append_chunk("Hello ")
        handle.append_chunk("world")
        assert handle.partial_content == "Hello world"

    def test_append_after_cancel_is_noop(self) -> None:
        handle = GenerationHandle(
            message_id="msg_1",
            widget_id="w_1",
            thread_id="t_1",
        )
        handle.append_chunk("before")
        handle.cancel()
        handle.append_chunk("after")
        assert handle.partial_content == "before"

    def test_is_expired(self) -> None:
        handle = GenerationHandle(
            message_id="msg_1",
            widget_id="w_1",
            thread_id="t_1",
        )
        assert not handle.is_expired
        # Manually set created_at to past
        handle.created_at = time.time() - GENERATION_HANDLE_TTL - 1
        assert handle.is_expired


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
        assert data["threadId"] == "t_1"

    def test_stream_chat_chunk(self) -> None:
        w = MockChatWidget()
        w.stream_chat_chunk("tok", "msg_1", thread_id="t_1")
        evt_type, data = w.get_last_event()
        assert evt_type == "chat:stream-chunk"
        assert data["chunk"] == "tok"
        assert data["done"] is False

    def test_stream_chat_chunk_done(self) -> None:
        w = MockChatWidget()
        w.stream_chat_chunk("", "msg_1", done=True)
        _evt_type, data = w.get_last_event()
        assert data["done"] is True

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

    def test_update_chat_thread_list(self) -> None:
        w = MockChatWidget()
        threads = [{"thread_id": "t1", "title": "Chat 1"}]
        w.update_chat_thread_list(threads)
        evt_type, data = w.get_last_event()
        assert evt_type == "chat:update-thread-list"
        assert data["threads"] == threads

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
        assert data["description"] == "Show help"

    def test_update_chat_settings(self) -> None:
        w = MockChatWidget()
        w.update_chat_settings({"model": "gpt-4o", "temperature": 0.5})
        evt_type, data = w.get_last_event()
        assert evt_type == "chat:update-settings"
        assert data["model"] == "gpt-4o"
        assert data["temperature"] == 0.5

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
        assert result.title == "Test"

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
        # Get last 3
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

    def test_build_chat_config_with_commands(self) -> None:
        from pywry.mcp.builders import build_chat_config

        config = build_chat_config(
            {
                "slash_commands": [
                    {"name": "help", "description": "Show help"},
                    {"name": "/test"},
                ],
            }
        )
        assert len(config.slash_commands) == 2
        assert config.slash_commands[0].name == "/help"

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
        assert config.height == 700
        assert config.chat_config.model == "gpt-4o"
        assert config.show_sidebar is False


# =============================================================================
# build_chat_html Tests
# =============================================================================


class TestBuildChatHtml:
    """Test build_chat_html helper."""

    def test_default_includes_sidebar(self) -> None:
        from pywry.chat import build_chat_html

        html = build_chat_html()
        assert "pywry-chat-sidebar" in html
        assert "pywry-chat-messages" in html
        assert "pywry-chat-input" in html
        assert "pywry-chat-settings-toggle" in html

    def test_no_sidebar(self) -> None:
        from pywry.chat import build_chat_html

        html = build_chat_html(show_sidebar=False)
        assert "pywry-chat-sidebar" not in html
        assert "pywry-chat-messages" in html

    def test_no_settings(self) -> None:
        from pywry.chat import build_chat_html

        html = build_chat_html(show_settings=False)
        assert "pywry-chat-settings-toggle" not in html

    def test_container_id(self) -> None:
        from pywry.chat import build_chat_html

        html = build_chat_html(container_id="my-chat")
        assert 'id="my-chat"' in html

    def test_file_attach_disabled_by_default(self) -> None:
        from pywry.chat import build_chat_html

        html = build_chat_html()
        assert "pywry-chat-attach-btn" not in html
        assert "pywry-chat-drop-overlay" not in html

    def test_file_attach_enabled(self) -> None:
        from pywry.chat import build_chat_html

        html = build_chat_html(enable_file_attach=True, file_accept_types=[".csv"])
        assert "pywry-chat-attach-btn" in html
        assert "pywry-chat-drop-overlay" in html

    def test_file_attach_requires_accept_in_html(self) -> None:
        """When file_accept_types is provided, data-accept-types attribute is set."""
        from pywry.chat import build_chat_html

        html = build_chat_html(
            enable_file_attach=True,
            file_accept_types=[".csv", ".json"],
        )
        assert 'data-accept-types=".csv,.json"' in html

    def test_file_attach_custom_accept(self) -> None:
        from pywry.chat import build_chat_html

        html = build_chat_html(
            enable_file_attach=True,
            file_accept_types=[".csv", ".xlsx"],
        )
        assert 'data-accept-types=".csv,.xlsx"' in html

    def test_context_without_file_attach(self) -> None:
        from pywry.chat import build_chat_html

        html = build_chat_html(enable_context=True, enable_file_attach=False)
        # @ mention popup should be present
        assert "pywry-chat-mention-popup" in html
        # File attach should NOT be present
        assert "pywry-chat-attach-btn" not in html
        assert "pywry-chat-drop-overlay" not in html

    def test_file_attach_without_context(self) -> None:
        from pywry.chat import build_chat_html

        html = build_chat_html(
            enable_file_attach=True,
            file_accept_types=[".csv"],
            enable_context=False,
        )
        # File attach should be present
        assert "pywry-chat-attach-btn" in html
        assert "pywry-chat-drop-overlay" in html
        # @ mention popup should NOT be present
        assert "pywry-chat-mention-popup" not in html

    def test_both_context_and_file_attach(self) -> None:
        from pywry.chat import build_chat_html

        html = build_chat_html(
            enable_context=True,
            enable_file_attach=True,
            file_accept_types=[".csv"],
        )
        assert "pywry-chat-mention-popup" in html
        assert "pywry-chat-attach-btn" in html
        assert "pywry-chat-drop-overlay" in html


# =============================================================================
# Content Part Tests
# =============================================================================


class TestContentParts:
    """Test ChatContentPart types."""

    def test_text_part(self) -> None:
        part = TextPart(text="hello")
        assert part.type == "text"
        assert part.text == "hello"

    def test_image_part(self) -> None:
        part = ImagePart(data="base64data", mime_type="image/png")
        assert part.type == "image"
        assert part.data == "base64data"
        assert part.mime_type == "image/png"

    def test_resource_link_part(self) -> None:
        part = ResourceLinkPart(uri="pywry://resource/1", name="Doc")
        assert part.type == "resource_link"
        assert part.name == "Doc"


# =============================================================================
# Provider Tests (import only, no API calls)
# =============================================================================


class TestProviderFactory:
    """Test provider factory function."""

    def test_callback_provider(self) -> None:
        from pywry.chat_providers import get_provider

        provider = get_provider("callback")
        assert provider is not None

    def test_unknown_provider_raises(self) -> None:
        from pywry.chat_providers import get_provider

        with pytest.raises(ValueError, match="Unknown provider"):
            get_provider("nonexistent")

    def test_callback_provider_with_fns(self) -> None:
        from pywry.chat_providers import CallbackProvider

        def my_gen(messages, config):
            return "Hello!"

        provider = CallbackProvider(generate_fn=my_gen)
        assert provider._generate_fn is my_gen


class TestMagenticProvider:
    """Test MagenticProvider (mocked — no real magentic dependency required)."""

    def test_import_error_without_magentic(self) -> None:
        """MagenticProvider raises ImportError when magentic is not installed."""
        import sys

        # Temporarily make magentic unimportable
        sentinel = sys.modules.get("magentic")
        sentinel_cm = sys.modules.get("magentic.chat_model")
        sentinel_cmb = sys.modules.get("magentic.chat_model.base")
        sys.modules["magentic"] = None  # type: ignore[assignment]
        sys.modules["magentic.chat_model"] = None  # type: ignore[assignment]
        sys.modules["magentic.chat_model.base"] = None  # type: ignore[assignment]
        try:
            # Re-import to pick up the blocked module
            from pywry.chat_providers import MagenticProvider

            with pytest.raises(ImportError, match="magentic"):
                MagenticProvider(model="gpt-4o")
        finally:
            if sentinel is None:
                sys.modules.pop("magentic", None)
            else:
                sys.modules["magentic"] = sentinel
            if sentinel_cm is None:
                sys.modules.pop("magentic.chat_model", None)
            else:
                sys.modules["magentic.chat_model"] = sentinel_cm
            if sentinel_cmb is None:
                sys.modules.pop("magentic.chat_model.base", None)
            else:
                sys.modules["magentic.chat_model.base"] = sentinel_cmb

    def test_registered_in_providers(self) -> None:
        """MagenticProvider is accessible via get_provider('magentic')."""
        from pywry.chat_providers import _PROVIDERS, MagenticProvider

        assert "magentic" in _PROVIDERS
        assert _PROVIDERS["magentic"] is MagenticProvider

    def test_type_error_on_bad_model(self) -> None:
        """MagenticProvider rejects non-ChatModel, non-string model args."""
        pytest.importorskip("magentic")
        from pywry.chat_providers import MagenticProvider

        with pytest.raises(TypeError, match="Expected a magentic ChatModel"):
            MagenticProvider(model=12345)

    def test_string_model_creates_openai_chat_model(self, monkeypatch) -> None:
        """Passing a model name string auto-wraps in OpenaiChatModel."""
        magentic = pytest.importorskip("magentic")
        from pywry.chat_providers import MagenticProvider

        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake-key")
        provider = MagenticProvider(model="gpt-4o-mini")
        assert isinstance(provider._model, magentic.OpenaiChatModel)

    def test_accepts_chat_model_instance(self, monkeypatch) -> None:
        """Passing a ChatModel instance is stored directly."""
        magentic = pytest.importorskip("magentic")
        from pywry.chat_providers import MagenticProvider

        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake-key")
        model = magentic.OpenaiChatModel("gpt-4o")
        provider = MagenticProvider(model=model)
        assert provider._model is model

    def test_build_messages_with_system_prompt(self, monkeypatch) -> None:
        """_build_messages prepends system prompt and maps roles."""
        magentic = pytest.importorskip("magentic")
        from pywry.chat import ChatConfig, ChatMessage
        from pywry.chat_providers import MagenticProvider

        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake-key")
        provider = MagenticProvider(model="gpt-4o")
        messages = [
            ChatMessage(role="user", content="Hello"),
            ChatMessage(role="assistant", content="Hi there"),
        ]
        config = ChatConfig(system_prompt="You are helpful.")
        result = provider._build_messages(messages, config)

        assert len(result) == 3
        assert isinstance(result[0], magentic.SystemMessage)
        assert isinstance(result[1], magentic.UserMessage)
        assert isinstance(result[2], magentic.AssistantMessage)

    def test_build_messages_no_system_prompt(self, monkeypatch) -> None:
        """_build_messages omits system message when not configured."""
        magentic = pytest.importorskip("magentic")
        from pywry.chat import ChatConfig, ChatMessage
        from pywry.chat_providers import MagenticProvider

        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake-key")
        provider = MagenticProvider(model="gpt-4o")
        messages = [ChatMessage(role="user", content="test")]
        config = ChatConfig(system_prompt=None)
        result = provider._build_messages(messages, config)

        assert len(result) == 1
        assert isinstance(result[0], magentic.UserMessage)

    def test_string_model_with_kwargs(self, monkeypatch) -> None:
        """String model with extra kwargs are forwarded to OpenaiChatModel."""
        magentic = pytest.importorskip("magentic")
        from pywry.chat_providers import MagenticProvider

        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake-key")
        provider = MagenticProvider(
            model="gpt-4o",
            base_url="http://localhost:11434/v1/",
        )
        assert isinstance(provider._model, magentic.OpenaiChatModel)
