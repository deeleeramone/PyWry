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
        langgraph = pytest.importorskip("langgraph")
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
            make_event("on_tool_end", name="write_todos", run_id="tc3",
                       data={"output": json.dumps(todos)}),
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
