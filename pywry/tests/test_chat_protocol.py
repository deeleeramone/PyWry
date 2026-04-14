"""Protocol integration tests for the ACP chat system.

These tests verify that the protocol actually works end-to-end:
- Providers yield SessionUpdate objects that ChatManager dispatches correctly
- ACP wire format serialization produces the correct camelCase JSON
- Tool call lifecycle transitions produce correct event sequences
- TradingView artifacts dispatch with the right payload structure
- RBAC permission checks block or allow operations correctly
- Cancel signals propagate from the user through to the provider
- Plan updates produce structured frontend events
"""

from __future__ import annotations

import asyncio
import time

from typing import Any
from unittest.mock import MagicMock

import pytest

from pywry.chat.artifacts import (
    CodeArtifact,
    TradingViewArtifact,
    TradingViewSeries,
)
from pywry.chat.manager import ChatContext, ChatManager, SettingsItem
from pywry.chat.models import (
    ACPToolCall,
    AudioPart,
    ChatMessage,
    EmbeddedResource,
    EmbeddedResourcePart,
    ImagePart,
    ResourceLinkPart,
    TextPart,
)
from pywry.chat.permissions import ACP_PERMISSION_MAP, check_acp_permission
from pywry.chat.session import (
    AgentCapabilities,
    ClientCapabilities,
    PermissionRequest,
    PlanEntry,
    PromptCapabilities,
    SessionConfigOption,
    SessionMode,
)
from pywry.chat.updates import (
    AgentMessageUpdate,
    ArtifactUpdate,
    CitationUpdate,
    CommandsUpdate,
    ConfigOptionUpdate,
    ModeUpdate,
    PermissionRequestUpdate,
    PlanUpdate,
    StatusUpdate,
    ThinkingUpdate,
    ToolCallUpdate,
)


class FakeWidget:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def emit(self, event_type: str, data: dict[str, Any]) -> None:
        self.events.append((event_type, data))

    def emit_fire(self, event_type: str, data: dict[str, Any]) -> None:
        self.events.append((event_type, data))

    def get_events(self, event_type: str) -> list[dict]:
        return [d for e, d in self.events if e == event_type]


@pytest.fixture(autouse=True)
def _disable_stream_buffering():
    orig_interval = ChatManager._STREAM_FLUSH_INTERVAL
    orig_max = ChatManager._STREAM_MAX_BUFFER
    ChatManager._STREAM_FLUSH_INTERVAL = 0
    ChatManager._STREAM_MAX_BUFFER = 1
    yield
    ChatManager._STREAM_FLUSH_INTERVAL = orig_interval
    ChatManager._STREAM_MAX_BUFFER = orig_max


class TestACPWireFormat:
    """Verify models serialize to camelCase JSON matching the ACP spec."""

    def test_image_part_serializes_mime_type_as_camel(self):
        part = ImagePart(data="abc", mime_type="image/jpeg")
        dumped = part.model_dump(by_alias=True)
        assert "mimeType" in dumped
        assert dumped["mimeType"] == "image/jpeg"
        assert "mime_type" not in dumped

    def test_audio_part_serializes_mime_type_as_camel(self):
        part = AudioPart(data="abc", mime_type="audio/mp3")
        dumped = part.model_dump(by_alias=True)
        assert dumped["mimeType"] == "audio/mp3"

    def test_resource_link_serializes_mime_type_as_camel(self):
        part = ResourceLinkPart(uri="file:///a.txt", name="a", mime_type="text/plain")
        dumped = part.model_dump(by_alias=True)
        assert dumped["mimeType"] == "text/plain"

    def test_embedded_resource_serializes_mime_type_as_camel(self):
        res = EmbeddedResource(uri="file:///b.txt", mime_type="text/csv")
        dumped = res.model_dump(by_alias=True)
        assert dumped["mimeType"] == "text/csv"

    def test_tool_call_serializes_id_as_camel(self):
        tc = ACPToolCall(tool_call_id="call_1", name="search", kind="fetch")
        dumped = tc.model_dump(by_alias=True)
        assert "toolCallId" in dumped
        assert dumped["toolCallId"] == "call_1"
        assert "tool_call_id" not in dumped

    def test_agent_message_update_serializes_discriminator(self):
        u = AgentMessageUpdate(text="hello")
        dumped = u.model_dump(by_alias=True)
        assert dumped["sessionUpdate"] == "agent_message"

    def test_tool_call_update_serializes_all_camel_fields(self):
        u = ToolCallUpdate(tool_call_id="c1", name="read", kind="read", status="completed")
        dumped = u.model_dump(by_alias=True)
        assert dumped["sessionUpdate"] == "tool_call"
        assert dumped["toolCallId"] == "c1"

    def test_mode_update_serializes_camel_fields(self):
        u = ModeUpdate(
            current_mode_id="code",
            available_modes=[SessionMode(id="code", name="Code")],
        )
        dumped = u.model_dump(by_alias=True)
        assert dumped["currentModeId"] == "code"
        assert dumped["availableModes"][0]["id"] == "code"

    def test_permission_request_serializes_camel(self):
        req = PermissionRequest(tool_call_id="c1", title="Run command")
        dumped = req.model_dump(by_alias=True)
        assert dumped["toolCallId"] == "c1"

    def test_session_config_option_serializes_camel(self):
        opt = SessionConfigOption(id="model", name="Model", current_value="gpt-4")
        dumped = opt.model_dump(by_alias=True)
        assert dumped["currentValue"] == "gpt-4"

    def test_client_capabilities_serializes_camel(self):
        caps = ClientCapabilities(file_system=True, terminal=False)
        dumped = caps.model_dump(by_alias=True)
        assert dumped["fileSystem"] is True

    def test_agent_capabilities_serializes_camel(self):
        caps = AgentCapabilities(
            prompt_capabilities=PromptCapabilities(image=True, embedded_context=True),
            load_session=True,
            config_options=False,
        )
        dumped = caps.model_dump(by_alias=True)
        assert dumped["loadSession"] is True
        assert dumped["promptCapabilities"]["embeddedContext"] is True

    def test_snake_case_constructor_works(self):
        part = ImagePart(data="x", mime_type="image/png")
        assert part.mime_type == "image/png"

    def test_camel_case_constructor_works(self):
        part = ImagePart(data="x", mimeType="image/png")
        assert part.mime_type == "image/png"

    def test_chat_message_with_tool_calls_round_trips(self):
        msg = ChatMessage(
            role="assistant",
            content="calling tool",
            tool_calls=[ACPToolCall(tool_call_id="c1", name="search", kind="fetch")],
        )
        dumped = msg.model_dump(by_alias=True)
        assert dumped["tool_calls"][0]["toolCallId"] == "c1"
        restored = ChatMessage.model_validate(dumped)
        assert restored.tool_calls[0].tool_call_id == "c1"


class TestCallbackProviderRoundTrip:
    """Verify CallbackProvider yields SessionUpdate objects that can be consumed."""

    def test_string_callback_yields_agent_message(self):
        from pywry.chat.providers.callback import CallbackProvider

        def my_prompt(session_id, content, cancel_event):
            yield "hello "
            yield "world"

        provider = CallbackProvider(prompt_fn=my_prompt)
        updates = []

        async def collect():
            caps = await provider.initialize(ClientCapabilities())
            sid = await provider.new_session("/tmp")
            async for u in provider.prompt(sid, [TextPart(text="hi")]):
                updates.append(u)

        asyncio.run(collect())
        assert len(updates) == 2
        assert all(isinstance(u, AgentMessageUpdate) for u in updates)
        assert updates[0].text == "hello "
        assert updates[1].text == "world"

    def test_session_update_objects_pass_through(self):
        from pywry.chat.providers.callback import CallbackProvider

        def my_prompt(session_id, content, cancel_event):
            yield StatusUpdate(text="searching...")
            yield AgentMessageUpdate(text="found it")
            yield ToolCallUpdate(tool_call_id="c1", name="search", status="completed")

        provider = CallbackProvider(prompt_fn=my_prompt)
        updates = []

        async def collect():
            await provider.initialize(ClientCapabilities())
            sid = await provider.new_session("/tmp")
            async for u in provider.prompt(sid, [TextPart(text="find x")]):
                updates.append(u)

        asyncio.run(collect())
        assert isinstance(updates[0], StatusUpdate)
        assert isinstance(updates[1], AgentMessageUpdate)
        assert isinstance(updates[2], ToolCallUpdate)
        assert updates[2].tool_call_id == "c1"

    def test_no_callback_yields_fallback(self):
        from pywry.chat.providers.callback import CallbackProvider

        provider = CallbackProvider()
        updates = []

        async def collect():
            await provider.initialize(ClientCapabilities())
            sid = await provider.new_session("/tmp")
            async for u in provider.prompt(sid, [TextPart(text="hi")]):
                updates.append(u)

        asyncio.run(collect())
        assert len(updates) == 1
        assert "No prompt callback" in updates[0].text


class TestChatManagerProviderIntegration:
    """Verify ChatManager dispatches provider SessionUpdates to the correct frontend events."""

    def test_agent_message_produces_stream_chunks(self):
        def my_prompt(session_id, content, cancel_event):
            yield AgentMessageUpdate(text="hello ")
            yield AgentMessageUpdate(text="world")

        from pywry.chat.providers.callback import CallbackProvider

        provider = CallbackProvider(prompt_fn=my_prompt)
        widget = FakeWidget()
        mgr = ChatManager(provider=provider)
        mgr.bind(widget)
        mgr._session_id = "test"
        mgr._on_user_message(
            {"text": "hi", "threadId": mgr.active_thread_id},
            "chat:user-message",
            "",
        )
        time.sleep(0.5)
        chunks = widget.get_events("chat:stream-chunk")
        text_chunks = [c["chunk"] for c in chunks if c.get("chunk")]
        assert "hello " in text_chunks
        assert "world" in text_chunks

    def test_tool_call_update_produces_tool_call_event(self):
        def my_prompt(session_id, content, cancel_event):
            yield ToolCallUpdate(
                tool_call_id="c1",
                name="search",
                kind="fetch",
                status="in_progress",
            )
            yield ToolCallUpdate(
                tool_call_id="c1",
                name="search",
                kind="fetch",
                status="completed",
            )
            yield AgentMessageUpdate(text="done")

        from pywry.chat.providers.callback import CallbackProvider

        provider = CallbackProvider(prompt_fn=my_prompt)
        widget = FakeWidget()
        mgr = ChatManager(provider=provider)
        mgr.bind(widget)
        mgr._session_id = "test"
        mgr._on_user_message(
            {"text": "search", "threadId": mgr.active_thread_id},
            "chat:user-message",
            "",
        )
        time.sleep(0.5)
        tool_events = widget.get_events("chat:tool-call")
        assert len(tool_events) == 2
        assert tool_events[0]["status"] == "in_progress"
        assert tool_events[1]["status"] == "completed"
        assert tool_events[0]["toolCallId"] == "c1"

    def test_plan_update_produces_plan_event(self):
        def my_prompt(session_id, content, cancel_event):
            yield PlanUpdate(
                entries=[
                    PlanEntry(content="step 1", priority="high", status="completed"),
                    PlanEntry(content="step 2", priority="medium", status="in_progress"),
                ]
            )
            yield AgentMessageUpdate(text="working")

        from pywry.chat.providers.callback import CallbackProvider

        provider = CallbackProvider(prompt_fn=my_prompt)
        widget = FakeWidget()
        mgr = ChatManager(provider=provider)
        mgr.bind(widget)
        mgr._session_id = "test"
        mgr._on_user_message(
            {"text": "plan", "threadId": mgr.active_thread_id},
            "chat:user-message",
            "",
        )
        time.sleep(0.5)
        plan_events = widget.get_events("chat:plan-update")
        assert len(plan_events) >= 1
        entries = plan_events[0]["entries"]
        assert len(entries) == 2
        assert entries[0]["content"] == "step 1"
        assert entries[0]["status"] == "completed"
        assert entries[1]["priority"] == "medium"

    def test_status_and_thinking_produce_correct_events(self):
        def my_prompt(session_id, content, cancel_event):
            yield StatusUpdate(text="loading...")
            yield ThinkingUpdate(text="considering options\n")
            yield AgentMessageUpdate(text="answer")

        from pywry.chat.providers.callback import CallbackProvider

        provider = CallbackProvider(prompt_fn=my_prompt)
        widget = FakeWidget()
        mgr = ChatManager(provider=provider)
        mgr.bind(widget)
        mgr._session_id = "test"
        mgr._on_user_message(
            {"text": "go", "threadId": mgr.active_thread_id},
            "chat:user-message",
            "",
        )
        time.sleep(0.5)
        status = widget.get_events("chat:status-update")
        thinking = widget.get_events("chat:thinking-chunk")
        assert any(s["text"] == "loading..." for s in status)
        assert any(t["text"] == "considering options\n" for t in thinking)

    def test_permission_request_produces_permission_event(self):
        def my_prompt(session_id, content, cancel_event):
            yield PermissionRequestUpdate(
                tool_call_id="c1",
                title="Delete file",
                request_id="perm_1",
            )
            yield AgentMessageUpdate(text="waiting for approval")

        from pywry.chat.providers.callback import CallbackProvider

        provider = CallbackProvider(prompt_fn=my_prompt)
        widget = FakeWidget()
        mgr = ChatManager(provider=provider)
        mgr.bind(widget)
        mgr._session_id = "test"
        mgr._on_user_message(
            {"text": "delete", "threadId": mgr.active_thread_id},
            "chat:user-message",
            "",
        )
        time.sleep(0.5)
        perms = widget.get_events("chat:permission-request")
        assert len(perms) >= 1
        assert perms[0]["toolCallId"] == "c1"
        assert perms[0]["title"] == "Delete file"
        assert perms[0]["requestId"] == "perm_1"


class TestToolCallLifecycle:
    """Verify tool calls transition through the correct status sequence."""

    def test_pending_to_completed(self):
        def my_prompt(session_id, content, cancel_event):
            yield ToolCallUpdate(tool_call_id="c1", name="read_file", kind="read", status="pending")
            yield ToolCallUpdate(
                tool_call_id="c1", name="read_file", kind="read", status="in_progress"
            )
            yield ToolCallUpdate(
                tool_call_id="c1", name="read_file", kind="read", status="completed"
            )
            yield AgentMessageUpdate(text="file contents here")

        from pywry.chat.providers.callback import CallbackProvider

        provider = CallbackProvider(prompt_fn=my_prompt)
        widget = FakeWidget()
        mgr = ChatManager(provider=provider)
        mgr.bind(widget)
        mgr._session_id = "test"
        mgr._on_user_message(
            {"text": "read", "threadId": mgr.active_thread_id},
            "chat:user-message",
            "",
        )
        time.sleep(0.5)
        tool_events = widget.get_events("chat:tool-call")
        statuses = [e["status"] for e in tool_events]
        assert statuses == ["pending", "in_progress", "completed"]
        assert all(e["toolCallId"] == "c1" for e in tool_events)
        assert all(e["kind"] == "read" for e in tool_events)

    def test_failed_status(self):
        def my_prompt(session_id, content, cancel_event):
            yield ToolCallUpdate(tool_call_id="c2", name="exec", kind="execute", status="pending")
            yield ToolCallUpdate(tool_call_id="c2", name="exec", kind="execute", status="failed")
            yield AgentMessageUpdate(text="command failed")

        from pywry.chat.providers.callback import CallbackProvider

        provider = CallbackProvider(prompt_fn=my_prompt)
        widget = FakeWidget()
        mgr = ChatManager(provider=provider)
        mgr.bind(widget)
        mgr._session_id = "test"
        mgr._on_user_message(
            {"text": "exec", "threadId": mgr.active_thread_id},
            "chat:user-message",
            "",
        )
        time.sleep(0.5)
        tool_events = widget.get_events("chat:tool-call")
        assert tool_events[-1]["status"] == "failed"


class TestTradingViewArtifactDispatch:
    """Verify TradingViewArtifact produces the correct event payload."""

    def test_dispatch_produces_artifact_event_with_series(self):
        def my_prompt(session_id, content, cancel_event):
            yield ArtifactUpdate(
                artifact=TradingViewArtifact(
                    title="AAPL",
                    series=[
                        TradingViewSeries(
                            type="candlestick",
                            data=[
                                {
                                    "time": "2024-01-02",
                                    "open": 185,
                                    "high": 186,
                                    "low": 184,
                                    "close": 185,
                                }
                            ],
                        ),
                        TradingViewSeries(
                            type="line",
                            data=[{"time": "2024-01-02", "value": 185}],
                            options={"color": "#ff0000"},
                        ),
                    ],
                    options={"timeScale": {"timeVisible": True}},
                    height="500px",
                )
            )

        from pywry.chat.providers.callback import CallbackProvider

        provider = CallbackProvider(prompt_fn=my_prompt)
        widget = FakeWidget()
        mgr = ChatManager(provider=provider)
        mgr.bind(widget)
        mgr._session_id = "test"
        mgr._on_user_message(
            {"text": "chart", "threadId": mgr.active_thread_id},
            "chat:user-message",
            "",
        )
        time.sleep(0.5)
        artifacts = widget.get_events("chat:artifact")
        assert len(artifacts) >= 1
        a = artifacts[0]
        assert a["artifactType"] == "tradingview"
        assert a["title"] == "AAPL"
        assert a["height"] == "500px"
        assert len(a["series"]) == 2
        assert a["series"][0]["type"] == "candlestick"
        assert a["series"][1]["options"]["color"] == "#ff0000"
        assert a["options"]["timeScale"]["timeVisible"] is True

    def test_code_artifact_dispatch(self):
        def my_prompt(session_id, content, cancel_event):
            yield ArtifactUpdate(
                artifact=CodeArtifact(
                    title="main.py",
                    language="python",
                    content="x = 42",
                )
            )

        from pywry.chat.providers.callback import CallbackProvider

        provider = CallbackProvider(prompt_fn=my_prompt)
        widget = FakeWidget()
        mgr = ChatManager(provider=provider)
        mgr.bind(widget)
        mgr._session_id = "test"
        mgr._on_user_message(
            {"text": "code", "threadId": mgr.active_thread_id},
            "chat:user-message",
            "",
        )
        time.sleep(0.5)
        artifacts = widget.get_events("chat:artifact")
        assert len(artifacts) >= 1
        assert artifacts[0]["artifactType"] == "code"
        assert artifacts[0]["language"] == "python"
        assert artifacts[0]["content"] == "x = 42"


class TestRBACPermissions:
    """Verify permission checks block or allow operations correctly."""

    def test_permission_map_covers_all_operations(self):
        required_ops = [
            "session/new",
            "session/load",
            "session/prompt",
            "session/cancel",
            "session/set_config_option",
            "session/set_mode",
            "session/request_permission",
            "fs/read_text_file",
            "fs/write_text_file",
            "terminal/create",
            "terminal/kill",
        ]
        for op in required_ops:
            assert op in ACP_PERMISSION_MAP, f"{op} missing from permission map"

    def test_prompt_requires_write(self):
        assert ACP_PERMISSION_MAP["session/prompt"] == "write"

    def test_file_write_requires_admin(self):
        assert ACP_PERMISSION_MAP["fs/write_text_file"] == "admin"

    def test_file_read_requires_read(self):
        assert ACP_PERMISSION_MAP["fs/read_text_file"] == "read"

    def test_terminal_requires_admin(self):
        assert ACP_PERMISSION_MAP["terminal/create"] == "admin"

    @pytest.mark.asyncio
    async def test_no_session_allows_everything(self):
        result = await check_acp_permission(None, "w1", "session/prompt", None)
        assert result is True

    @pytest.mark.asyncio
    async def test_no_session_allows_admin_ops(self):
        result = await check_acp_permission(None, "w1", "fs/write_text_file", None)
        assert result is True

    @pytest.mark.asyncio
    async def test_unknown_operation_defaults_to_admin(self):
        assert ACP_PERMISSION_MAP.get("unknown/op") is None
        result = await check_acp_permission(None, "w1", "unknown/op", None)
        assert result is True


class TestCancelPropagation:
    """Verify cancel signal reaches the provider through ChatManager."""

    def test_cancel_stops_generation(self):
        chunks_yielded = []

        def my_prompt(session_id, content, cancel_event):
            for i in range(100):
                if cancel_event and cancel_event.is_set():
                    return
                chunks_yielded.append(i)
                yield AgentMessageUpdate(text=f"chunk{i} ")
                time.sleep(0.01)

        from pywry.chat.providers.callback import CallbackProvider

        provider = CallbackProvider(prompt_fn=my_prompt)
        widget = FakeWidget()
        mgr = ChatManager(provider=provider)
        mgr.bind(widget)
        mgr._session_id = "test"
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
        time.sleep(0.5)
        assert len(chunks_yielded) < 100
        done_chunks = [c for c in widget.get_events("chat:stream-chunk") if c.get("done")]
        assert len(done_chunks) >= 1


class TestLegacyHandlerWithNewUpdates:
    """Verify legacy handler functions can yield new SessionUpdate types."""

    def test_handler_yields_mixed_strings_and_updates(self):
        def handler(messages, ctx):
            yield "starting... "
            yield StatusUpdate(text="processing")
            yield PlanUpdate(
                entries=[
                    PlanEntry(content="task 1", priority="high", status="in_progress"),
                ]
            )
            yield "done"

        widget = FakeWidget()
        mgr = ChatManager(handler=handler)
        mgr.bind(widget)
        mgr._on_user_message(
            {"text": "go", "threadId": mgr.active_thread_id},
            "chat:user-message",
            "",
        )
        time.sleep(0.5)
        chunks = widget.get_events("chat:stream-chunk")
        status = widget.get_events("chat:status-update")
        plan = widget.get_events("chat:plan-update")
        text = "".join(c["chunk"] for c in chunks if c.get("chunk"))
        assert "starting" in text
        assert "done" in text
        assert any(s["text"] == "processing" for s in status)
        assert len(plan) >= 1
        assert plan[0]["entries"][0]["content"] == "task 1"


class TestCommandsAndConfigUpdates:
    """Verify commands and config option updates dispatch correctly."""

    def test_commands_update_registers_commands(self):
        from pywry.chat.models import ACPCommand

        def my_prompt(session_id, content, cancel_event):
            yield CommandsUpdate(
                commands=[
                    ACPCommand(name="test", description="Run tests"),
                    ACPCommand(name="deploy", description="Deploy app"),
                ]
            )
            yield AgentMessageUpdate(text="ready")

        from pywry.chat.providers.callback import CallbackProvider

        provider = CallbackProvider(prompt_fn=my_prompt)
        widget = FakeWidget()
        mgr = ChatManager(provider=provider)
        mgr.bind(widget)
        mgr._session_id = "test"
        mgr._on_user_message(
            {"text": "init", "threadId": mgr.active_thread_id},
            "chat:user-message",
            "",
        )
        time.sleep(0.5)
        cmds = widget.get_events("chat:register-command")
        names = [c["name"] for c in cmds]
        assert "test" in names
        assert "deploy" in names

    def test_config_option_update_dispatches(self):
        def my_prompt(session_id, content, cancel_event):
            yield ConfigOptionUpdate(
                options=[
                    SessionConfigOption(id="model", name="Model", current_value="gpt-4"),
                ]
            )
            yield AgentMessageUpdate(text="configured")

        from pywry.chat.providers.callback import CallbackProvider

        provider = CallbackProvider(prompt_fn=my_prompt)
        widget = FakeWidget()
        mgr = ChatManager(provider=provider)
        mgr.bind(widget)
        mgr._session_id = "test"
        mgr._on_user_message(
            {"text": "config", "threadId": mgr.active_thread_id},
            "chat:user-message",
            "",
        )
        time.sleep(0.5)
        configs = widget.get_events("chat:config-update")
        assert len(configs) >= 1
        assert configs[0]["options"][0]["id"] == "model"

    def test_mode_update_dispatches(self):
        def my_prompt(session_id, content, cancel_event):
            yield ModeUpdate(
                current_mode_id="code",
                available_modes=[
                    SessionMode(id="ask", name="Ask"),
                    SessionMode(id="code", name="Code"),
                ],
            )
            yield AgentMessageUpdate(text="mode set")

        from pywry.chat.providers.callback import CallbackProvider

        provider = CallbackProvider(prompt_fn=my_prompt)
        widget = FakeWidget()
        mgr = ChatManager(provider=provider)
        mgr.bind(widget)
        mgr._session_id = "test"
        mgr._on_user_message(
            {"text": "mode", "threadId": mgr.active_thread_id},
            "chat:user-message",
            "",
        )
        time.sleep(0.5)
        modes = widget.get_events("chat:mode-update")
        assert len(modes) >= 1
        assert modes[0]["currentModeId"] == "code"
        assert len(modes[0]["availableModes"]) == 2
