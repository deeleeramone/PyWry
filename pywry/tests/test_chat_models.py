"""Unit tests for pywry.chat.models.

Covers:
- ACP content block types (TextPart, ImagePart, AudioPart, EmbeddedResource, etc.)
- ACPToolCall, ACPCommand, ACPCommandInput
- ChatMessage (validation, text_content, tool calls)
- ChatThread
- ChatConfig, ChatWidgetConfig
- GenerationHandle (cancel, append_chunk, partial_content, is_expired,
  task interaction)
- GenerationCancelledError
"""

from __future__ import annotations

import asyncio
import time

import pytest

from pywry.chat.models import (
    GENERATION_HANDLE_TTL,
    MAX_CONTENT_LENGTH,
    ACPCommand,
    ACPCommandInput,
    ACPToolCall,
    AudioPart,
    ChatConfig,
    ChatMessage,
    ChatThread,
    ChatWidgetConfig,
    EmbeddedResource,
    EmbeddedResourcePart,
    GenerationCancelledError,
    GenerationHandle,
    ImagePart,
    ResourceLinkPart,
    TextPart,
)


# =============================================================================
# ChatMessage
# =============================================================================


class TestChatMessage:
    """Test ChatMessage model."""

    def test_basic_creation(self) -> None:
        msg = ChatMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.text_content() == "Hello"
        assert msg.message_id
        assert msg.stopped is False

    def test_string_content(self) -> None:
        msg = ChatMessage(role="assistant", content="Hi there")
        assert msg.text_content() == "Hi there"

    def test_list_content_text_parts(self) -> None:
        msg = ChatMessage(
            role="assistant",
            content=[TextPart(text="Hello "), TextPart(text="world")],
        )
        assert msg.text_content() == "Hello world"

    def test_list_content_mixed_parts(self) -> None:
        msg = ChatMessage(
            role="assistant",
            content=[
                TextPart(text="See image: "),
                ImagePart(data="base64data", mimeType="image/png"),
            ],
        )
        assert msg.text_content() == "See image: "

    def test_list_with_non_text_parts_filtered(self) -> None:
        msg = ChatMessage(
            role="user",
            content=[TextPart(text="a"), ImagePart(data="abc"), TextPart(text="b")],
        )
        assert msg.text_content() == "ab"

    def test_content_length_validation(self) -> None:
        msg = ChatMessage(role="user", content="x" * 100)
        assert len(msg.text_content()) == 100

    def test_content_at_limit(self) -> None:
        msg = ChatMessage(role="user", content="x" * MAX_CONTENT_LENGTH)
        assert len(msg.content) == MAX_CONTENT_LENGTH

    def test_content_too_long_raises(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ChatMessage(role="user", content="x" * (MAX_CONTENT_LENGTH + 1))

    def test_list_content_skips_size_check(self) -> None:
        # Lists don't get the size check
        parts = [TextPart(text="a"), TextPart(text="b")]
        msg = ChatMessage(role="user", content=parts)
        assert msg.content == parts

    def test_tool_calls(self) -> None:
        msg = ChatMessage(
            role="assistant",
            content="I'll search for that.",
            tool_calls=[
                ACPToolCall(
                    toolCallId="call_1",
                    name="search",
                    kind="fetch",
                    arguments={"query": "test"},
                ),
            ],
        )
        assert len(msg.tool_calls) == 1
        assert msg.tool_calls[0].name == "search"
        assert msg.tool_calls[0].kind == "fetch"

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


# =============================================================================
# ChatThread
# =============================================================================


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


# =============================================================================
# ACPCommand
# =============================================================================


class TestACPCommand:
    """Test ACPCommand model."""

    def test_creation(self) -> None:
        cmd = ACPCommand(name="web", description="Search the web")
        assert cmd.name == "web"
        assert cmd.description == "Search the web"

    def test_with_input(self) -> None:
        cmd = ACPCommand(
            name="test",
            description="Run tests",
            input=ACPCommandInput(hint="Enter test name"),
        )
        assert cmd.input.hint == "Enter test name"


# =============================================================================
# ACPToolCall
# =============================================================================


class TestACPToolCall:
    """Test ACPToolCall model."""

    def test_creation(self) -> None:
        tc = ACPToolCall(
            toolCallId="call_1",
            title="Read file",
            name="fs_read",
            kind="read",
            status="pending",
        )
        assert tc.tool_call_id == "call_1"
        assert tc.kind == "read"
        assert tc.status == "pending"

    def test_defaults(self) -> None:
        tc = ACPToolCall(name="test")
        assert tc.tool_call_id  # auto-generated
        assert tc.kind == "other"
        assert tc.status == "pending"

    def test_with_arguments(self) -> None:
        tc = ACPToolCall(
            name="search",
            arguments={"query": "hello"},
        )
        assert tc.arguments["query"] == "hello"


# =============================================================================
# ChatConfig / ChatWidgetConfig
# =============================================================================


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


# =============================================================================
# Content parts
# =============================================================================


class TestContentParts:
    """Test ACP ContentBlock types."""

    def test_text_part(self) -> None:
        part = TextPart(text="hello")
        assert part.type == "text"
        assert part.text == "hello"

    def test_text_part_with_annotations(self) -> None:
        part = TextPart(text="hello", annotations={"source": "llm"})
        assert part.annotations["source"] == "llm"

    def test_image_part(self) -> None:
        part = ImagePart(data="base64data", mimeType="image/png")
        assert part.type == "image"
        assert part.data == "base64data"
        assert part.mime_type == "image/png"

    def test_audio_part(self) -> None:
        part = AudioPart(data="audiodata", mimeType="audio/wav")
        assert part.type == "audio"
        assert part.mime_type == "audio/wav"

    def test_resource_link_part(self) -> None:
        part = ResourceLinkPart(
            uri="pywry://resource/1",
            name="Doc",
            title="My Document",
            size=1024,
        )
        assert part.type == "resource_link"
        assert part.name == "Doc"
        assert part.title == "My Document"
        assert part.size == 1024

    def test_embedded_resource_part(self) -> None:
        part = EmbeddedResourcePart(
            resource=EmbeddedResource(
                uri="file:///doc.txt",
                mimeType="text/plain",
                text="Hello world",
            ),
        )
        assert part.type == "resource"
        assert part.resource.text == "Hello world"


# =============================================================================
# GenerationHandle
# =============================================================================


class TestGenerationHandle:
    """Test GenerationHandle dataclass."""

    def test_default_state(self) -> None:
        handle = GenerationHandle()
        assert handle.task is None
        assert not handle.cancel_event.is_set()
        assert handle.message_id == ""
        assert handle.partial_content == ""

    def test_creation_with_fields(self) -> None:
        handle = GenerationHandle(
            message_id="msg_1",
            widget_id="w_1",
            thread_id="t_1",
        )
        assert handle.message_id == "msg_1"
        assert not handle.cancel_event.is_set()

    def test_partial_content_concatenates_chunks(self) -> None:
        handle = GenerationHandle()
        handle.append_chunk("hello ")
        handle.append_chunk("world")
        assert handle.partial_content == "hello world"

    def test_append_after_cancel_is_noop(self) -> None:
        handle = GenerationHandle()
        handle.append_chunk("before")
        handle.cancel()
        handle.append_chunk("after")
        assert handle.partial_content == "before"

    def test_append_chunk_after_cancel_event_set_is_noop(self) -> None:
        handle = GenerationHandle()
        handle.cancel_event.set()
        handle.append_chunk("ignored")
        assert handle.partial_content == ""

    def test_is_expired_false_when_recent(self) -> None:
        handle = GenerationHandle()
        assert handle.is_expired is False

    def test_is_expired_true_when_past_ttl(self) -> None:
        handle = GenerationHandle()
        handle.created_at = time.time() - GENERATION_HANDLE_TTL - 1
        assert handle.is_expired is True

    def test_cancel_first_call_returns_true(self) -> None:
        handle = GenerationHandle()
        assert handle.cancel() is True
        assert handle.cancel_event.is_set()

    def test_cancel_second_call_returns_false(self) -> None:
        handle = GenerationHandle()
        handle.cancel()
        assert handle.cancel() is False

    def test_cancel_aborts_pending_task(self) -> None:
        async def run():
            async def _idle():
                await asyncio.sleep(60)

            task = asyncio.create_task(_idle())
            handle = GenerationHandle(task=task)
            try:
                assert handle.cancel() is True
                with pytest.raises(asyncio.CancelledError):
                    await task
            finally:
                if not task.done():
                    task.cancel()

        asyncio.run(run())

    def test_cancel_with_done_task_is_safe(self) -> None:
        async def run():
            async def _quick():
                return 1

            task = asyncio.create_task(_quick())
            await task
            handle = GenerationHandle(task=task)
            # Task already done — cancel() still returns True but doesn't raise
            assert handle.cancel() is True

        asyncio.run(run())


class TestGenerationCancelledError:
    def test_default_message_and_empty_partial(self) -> None:
        err = GenerationCancelledError()
        assert "Generation cancelled by user" in str(err)
        assert err.partial_content == ""

    def test_carries_partial_content(self) -> None:
        err = GenerationCancelledError("hello so far")
        assert err.partial_content == "hello so far"
