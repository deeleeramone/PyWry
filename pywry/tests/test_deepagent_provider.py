"""Tests for the DeepAgentProvider.

Uses a mock CompiledGraph that yields known astream_events
to verify the provider maps LangGraph events to ACP SessionUpdate types.
"""

from __future__ import annotations

import asyncio

import pytest

from pywry.chat.models import TextPart
from pywry.chat.providers.deepagent import DeepagentProvider, _map_tool_kind
from pywry.chat.session import ClientCapabilities
from pywry.chat.updates import (
    AgentMessageUpdate,
    PlanUpdate,
    StatusUpdate,
    ToolCallUpdate,
)


class FakeChunk:
    def __init__(self, content: str = ""):
        self.content = content


def make_event(event: str, name: str = "", data: dict | None = None, run_id: str = "r1"):
    return {"event": event, "name": name, "data": data or {}, "run_id": run_id}


async def fake_stream_events(events: list[dict]):
    for e in events:
        yield e


class FakeAgent:
    def __init__(self, events: list[dict]):
        self._events = events

    def astream_events(self, input_data: dict, config: dict, version: str = "v2"):
        return fake_stream_events(self._events)


class TestToolKindMapping:
    def test_read_file(self):
        assert _map_tool_kind("read_file") == "read"

    def test_write_file(self):
        assert _map_tool_kind("write_file") == "edit"

    def test_execute(self):
        assert _map_tool_kind("execute") == "execute"

    def test_write_todos(self):
        assert _map_tool_kind("write_todos") == "think"

    def test_unknown_tool(self):
        assert _map_tool_kind("my_custom_tool") == "other"


class TestDeepagentProviderConstruction:
    def test_with_pre_built_agent(self):
        agent = FakeAgent([])
        provider = DeepagentProvider(agent=agent)
        assert provider._agent is agent

    def test_without_agent_stores_params(self):
        provider = DeepagentProvider(model="openai:gpt-4o", system_prompt="be helpful")
        assert provider._agent is None
        assert provider._model == "openai:gpt-4o"


class TestDeepagentProviderInitialize:
    @pytest.mark.asyncio
    async def test_initialize_returns_capabilities(self):
        agent = FakeAgent([])
        provider = DeepagentProvider(agent=agent, auto_checkpointer=False, auto_store=False)
        caps = await provider.initialize(ClientCapabilities())
        assert caps.prompt_capabilities is not None
        assert caps.prompt_capabilities.image is True

    @pytest.mark.asyncio
    async def test_initialize_with_checkpointer_enables_load(self):
        pytest.importorskip("langgraph")
        from langgraph.checkpoint.memory import MemorySaver

        agent = FakeAgent([])
        provider = DeepagentProvider(
            agent=agent, checkpointer=MemorySaver(), auto_checkpointer=False, auto_store=False
        )
        caps = await provider.initialize(ClientCapabilities())
        assert caps.load_session is True

    @pytest.mark.asyncio
    async def test_initialize_without_checkpointer_disables_load(self):
        agent = FakeAgent([])
        provider = DeepagentProvider(agent=agent, auto_checkpointer=False, auto_store=False)
        caps = await provider.initialize(ClientCapabilities())
        assert caps.load_session is False


class TestDeepagentProviderSessions:
    @pytest.mark.asyncio
    async def test_new_session_returns_id(self):
        agent = FakeAgent([])
        provider = DeepagentProvider(agent=agent, auto_checkpointer=False, auto_store=False)
        await provider.initialize(ClientCapabilities())
        sid = await provider.new_session("/tmp")
        assert sid.startswith("da_")

    @pytest.mark.asyncio
    async def test_load_nonexistent_session_raises(self):
        agent = FakeAgent([])
        provider = DeepagentProvider(agent=agent, auto_checkpointer=False, auto_store=False)
        await provider.initialize(ClientCapabilities())
        with pytest.raises(ValueError, match="not found"):
            await provider.load_session("nonexistent", "/tmp")


class TestDeepagentProviderStreaming:
    @pytest.mark.asyncio
    async def test_text_chunks(self):
        events = [
            make_event("on_chat_model_stream", data={"chunk": FakeChunk("hello ")}),
            make_event("on_chat_model_stream", data={"chunk": FakeChunk("world")}),
        ]
        agent = FakeAgent(events)
        provider = DeepagentProvider(agent=agent, auto_checkpointer=False, auto_store=False)
        await provider.initialize(ClientCapabilities())
        sid = await provider.new_session("/tmp")

        updates = []
        async for u in provider.prompt(sid, [TextPart(text="hi")]):
            updates.append(u)

        assert len(updates) == 2
        assert all(isinstance(u, AgentMessageUpdate) for u in updates)
        assert updates[0].text == "hello "
        assert updates[1].text == "world"

    @pytest.mark.asyncio
    async def test_tool_call_lifecycle(self):
        events = [
            make_event("on_tool_start", name="read_file", run_id="tc1"),
            make_event("on_tool_end", name="read_file", run_id="tc1", data={"output": "contents"}),
        ]
        agent = FakeAgent(events)
        provider = DeepagentProvider(agent=agent, auto_checkpointer=False, auto_store=False)
        await provider.initialize(ClientCapabilities())
        sid = await provider.new_session("/tmp")

        updates = []
        async for u in provider.prompt(sid, [TextPart(text="read")]):
            updates.append(u)

        assert len(updates) == 2
        assert isinstance(updates[0], ToolCallUpdate)
        assert updates[0].status == "in_progress"
        assert updates[0].kind == "read"
        assert isinstance(updates[1], ToolCallUpdate)
        assert updates[1].status == "completed"

    @pytest.mark.asyncio
    async def test_tool_error(self):
        events = [
            make_event("on_tool_start", name="execute", run_id="tc2"),
            make_event("on_tool_error", name="execute", run_id="tc2"),
        ]
        agent = FakeAgent(events)
        provider = DeepagentProvider(agent=agent, auto_checkpointer=False, auto_store=False)
        await provider.initialize(ClientCapabilities())
        sid = await provider.new_session("/tmp")

        updates = []
        async for u in provider.prompt(sid, [TextPart(text="run")]):
            updates.append(u)

        assert updates[-1].status == "failed"

    @pytest.mark.asyncio
    async def test_write_todos_produces_plan_update(self):
        import json

        todos = [
            {"title": "Read docs", "status": "done"},
            {"title": "Write code", "status": "in_progress"},
        ]
        events = [
            make_event("on_tool_start", name="write_todos", run_id="tc3"),
            make_event(
                "on_tool_end", name="write_todos", run_id="tc3", data={"output": json.dumps(todos)}
            ),
        ]
        agent = FakeAgent(events)
        provider = DeepagentProvider(agent=agent, auto_checkpointer=False, auto_store=False)
        await provider.initialize(ClientCapabilities())
        sid = await provider.new_session("/tmp")

        updates = []
        async for u in provider.prompt(sid, [TextPart(text="plan")]):
            updates.append(u)

        plan_updates = [u for u in updates if isinstance(u, PlanUpdate)]
        assert len(plan_updates) == 1
        assert len(plan_updates[0].entries) == 2
        assert plan_updates[0].entries[0].content == "Read docs"
        assert plan_updates[0].entries[0].status == "completed"
        assert plan_updates[0].entries[1].status == "in_progress"

    @pytest.mark.asyncio
    async def test_write_todos_langgraph_command_output_produces_plan_update(self):
        """Deep Agents' ``write_todos`` returns a LangGraph ``Command`` with
        ``update={"todos": [...]}`` — the extractor must pull the list out
        of that shape, not just the legacy plain-JSON list.
        """

        class _Command:
            def __init__(self, update: dict) -> None:
                self.update = update

        todos = [
            {"content": "Switch ticker to BTC-USD", "status": "completed"},
            {"content": "Change interval to 1m", "status": "in_progress"},
        ]
        events = [
            make_event("on_tool_start", name="write_todos", run_id="tc9"),
            make_event(
                "on_tool_end",
                name="write_todos",
                run_id="tc9",
                data={"output": _Command(update={"todos": todos})},
            ),
        ]
        agent = FakeAgent(events)
        provider = DeepagentProvider(agent=agent, auto_checkpointer=False, auto_store=False)
        await provider.initialize(ClientCapabilities())
        sid = await provider.new_session("/tmp")

        updates = []
        async for u in provider.prompt(sid, [TextPart(text="plan")]):
            updates.append(u)

        plan_updates = [u for u in updates if isinstance(u, PlanUpdate)]
        assert len(plan_updates) == 1
        assert [e.content for e in plan_updates[0].entries] == [
            "Switch ticker to BTC-USD",
            "Change interval to 1m",
        ]
        assert [e.status for e in plan_updates[0].entries] == ["completed", "in_progress"]
        # The plan card IS the visualization — no raw Command repr should
        # double-render as a tool-call card.
        tool_completed = [
            u
            for u in updates
            if isinstance(u, ToolCallUpdate) and u.status == "completed" and u.name == "write_todos"
        ]
        assert tool_completed == []

    @pytest.mark.asyncio
    async def test_cancel_stops_streaming(self):
        events = [
            make_event("on_chat_model_stream", data={"chunk": FakeChunk(f"chunk{i}")})
            for i in range(100)
        ]
        agent = FakeAgent(events)
        provider = DeepagentProvider(agent=agent, auto_checkpointer=False, auto_store=False)
        await provider.initialize(ClientCapabilities())
        sid = await provider.new_session("/tmp")

        cancel = asyncio.Event()
        updates = []
        count = 0
        async for u in provider.prompt(sid, [TextPart(text="go")], cancel_event=cancel):
            updates.append(u)
            count += 1
            if count == 3:
                cancel.set()

        assert len(updates) < 100

    @pytest.mark.asyncio
    async def test_chat_model_start_yields_status(self):
        events = [
            make_event("on_chat_model_start", name="ChatOpenAI"),
            make_event("on_chat_model_stream", data={"chunk": FakeChunk("answer")}),
        ]
        agent = FakeAgent(events)
        provider = DeepagentProvider(agent=agent, auto_checkpointer=False, auto_store=False)
        await provider.initialize(ClientCapabilities())
        sid = await provider.new_session("/tmp")

        updates = []
        async for u in provider.prompt(sid, [TextPart(text="hi")]):
            updates.append(u)

        assert isinstance(updates[0], StatusUpdate)
        assert "ChatOpenAI" in updates[0].text
        assert isinstance(updates[1], AgentMessageUpdate)


# =============================================================================
# MCP integration / recursion_limit / truncate_session
# =============================================================================


class TestDeepagentProviderConstructor:
    def test_default_recursion_limit_is_50(self):
        provider = DeepagentProvider(model="openai:gpt-4o")
        assert provider._recursion_limit == 50

    def test_custom_recursion_limit(self):
        provider = DeepagentProvider(model="openai:gpt-4o", recursion_limit=200)
        assert provider._recursion_limit == 200

    def test_mcp_servers_default_empty(self):
        provider = DeepagentProvider(model="openai:gpt-4o")
        assert provider._mcp_servers == {}
        assert provider._mcp_tools == []

    def test_mcp_servers_stored_on_init(self):
        servers = {
            "pywry": {"transport": "streamable_http", "url": "http://127.0.0.1:8765/mcp"},
        }
        provider = DeepagentProvider(model="openai:gpt-4o", mcp_servers=servers)
        assert provider._mcp_servers == servers


class TestRecursionLimitInPromptConfig:
    @pytest.mark.asyncio
    async def test_recursion_limit_passed_in_config(self):
        captured: dict = {}

        class _Capturing:
            def astream_events(self, _input, config, version="v2"):
                captured["config"] = config

                async def _empty():
                    if False:
                        yield

                return _empty()

        provider = DeepagentProvider(
            agent=_Capturing(),
            auto_checkpointer=False,
            auto_store=False,
            recursion_limit=42,
        )
        await provider.initialize(ClientCapabilities())
        sid = await provider.new_session("/tmp")
        async for _ in provider.prompt(sid, [TextPart(text="hi")]):
            pass
        assert captured["config"]["recursion_limit"] == 42
        assert captured["config"]["configurable"]["thread_id"]


class TestNewSessionMcpServers:
    @pytest.mark.asyncio
    async def test_new_session_merges_stdio_descriptor(self):
        provider = DeepagentProvider(
            agent=FakeAgent([]),
            auto_checkpointer=False,
            auto_store=False,
        )
        await provider.initialize(ClientCapabilities())
        await provider.new_session(
            "/tmp",
            mcp_servers=[
                {"name": "fs", "command": "uvx", "args": ["mcp-server-filesystem", "/tmp"]},
            ],
        )
        assert "fs" in provider._mcp_servers
        entry = provider._mcp_servers["fs"]
        assert entry["transport"] == "stdio"
        assert entry["command"] == "uvx"
        assert entry["args"] == ["mcp-server-filesystem", "/tmp"]
        # Forces a rebuild on next prompt
        assert provider._agent is None
        assert provider._mcp_tools == []

    @pytest.mark.asyncio
    async def test_new_session_merges_http_descriptor(self):
        provider = DeepagentProvider(
            agent=FakeAgent([]),
            auto_checkpointer=False,
            auto_store=False,
        )
        await provider.initialize(ClientCapabilities())
        await provider.new_session(
            "/tmp",
            mcp_servers=[
                {"name": "pywry", "url": "http://127.0.0.1:8765/mcp"},
            ],
        )
        entry = provider._mcp_servers["pywry"]
        assert entry["transport"] == "streamable_http"
        assert entry["url"] == "http://127.0.0.1:8765/mcp"

    @pytest.mark.asyncio
    async def test_new_session_no_mcp_keeps_existing_agent(self):
        agent = FakeAgent([])
        provider = DeepagentProvider(
            agent=agent,
            auto_checkpointer=False,
            auto_store=False,
        )
        await provider.initialize(ClientCapabilities())
        await provider.new_session("/tmp")
        # Without mcp_servers param the agent is preserved
        assert provider._agent is agent


class TestLoadMcpTools:
    def test_returns_empty_when_no_servers_configured(self):
        provider = DeepagentProvider(model="openai:gpt-4o")
        assert provider._load_mcp_tools() == []


class TestTruncateSession:
    def test_no_op_when_checkpointer_missing(self):
        provider = DeepagentProvider(
            model="openai:gpt-4o",
            auto_checkpointer=False,
            auto_store=False,
        )
        # Should not raise even without a checkpointer
        provider.truncate_session("session-1", [])

    def test_calls_delete_thread_when_available(self):
        deleted: list[str] = []

        class _Saver:
            def delete_thread(self, thread_id: str) -> None:
                deleted.append(thread_id)

        provider = DeepagentProvider(
            model="openai:gpt-4o",
            checkpointer=_Saver(),
            auto_checkpointer=False,
            auto_store=False,
        )
        provider._sessions["sess-1"] = "thread-A"
        provider.truncate_session("sess-1", [])
        assert deleted == ["thread-A"]

    def test_falls_back_to_dict_storage_pop(self):
        class _DictSaver:
            def __init__(self) -> None:
                self.storage: dict[str, dict] = {"thread-A": {"x": 1}, "thread-B": {"y": 2}}

        saver = _DictSaver()
        provider = DeepagentProvider(
            model="openai:gpt-4o",
            checkpointer=saver,
            auto_checkpointer=False,
            auto_store=False,
        )
        provider._sessions["sess-1"] = "thread-A"
        provider.truncate_session("sess-1", [])
        assert "thread-A" not in saver.storage
        assert "thread-B" in saver.storage  # other threads untouched


class TestAutoCheckpointerInBuildAgent:
    """The auto-checkpointer must be set up by _build_agent so callers that
    bypass the async initialize() still get conversation persistence."""

    def test_build_agent_creates_checkpointer_when_missing(self, monkeypatch):
        # Pre-empt the actual create_deep_agent import; we only care about
        # the side-effect on self._checkpointer.
        provider = DeepagentProvider(
            model="openai:gpt-4o",
            auto_checkpointer=True,
        )
        assert provider._checkpointer is None

        # Patch create_deep_agent to a stub so _build_agent doesn't need
        # the real deepagents package.
        import sys
        import types

        fake_module = types.ModuleType("deepagents")
        fake_module.create_deep_agent = lambda **kwargs: object()
        monkeypatch.setitem(sys.modules, "deepagents", fake_module)

        provider._build_agent()
        # Checkpointer was set as a side-effect
        assert provider._checkpointer is not None

    def test_build_agent_does_not_overwrite_existing_checkpointer(self, monkeypatch):
        sentinel = object()
        provider = DeepagentProvider(
            model="openai:gpt-4o",
            checkpointer=sentinel,
            auto_checkpointer=True,
        )

        import sys
        import types

        fake_module = types.ModuleType("deepagents")
        fake_module.create_deep_agent = lambda **kwargs: object()
        monkeypatch.setitem(sys.modules, "deepagents", fake_module)

        provider._build_agent()
        assert provider._checkpointer is sentinel
