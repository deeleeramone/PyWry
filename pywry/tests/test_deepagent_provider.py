"""Tests for ``pywry.chat.providers.deepagent``.

Uses a fake CompiledGraph that yields scripted ``astream_events`` to verify
the provider maps LangGraph events to ACP SessionUpdate types, plus direct
tests for the module-level helpers (text filter, todo extraction, inline
tool-call rewriter, etc.) and the truncate-session behaviour.
"""

from __future__ import annotations

import asyncio
import builtins
import sys

from typing import Any
from unittest.mock import MagicMock

import pytest

from pywry.chat.models import TextPart
from pywry.chat.providers import deepagent as da
from pywry.chat.providers.deepagent import (
    DeepagentProvider,
    _coerce_text,
    _coerce_todo_list,
    _consume_one_inline_call,
    _extract_answer_from_content,
    _extract_stream_text,
    _extract_thinking_from_chunk,
    _extract_todos_from_tool_output,
    _flatten_message_content,
    _is_root_chain_end,
    _map_todo_status,
    _map_tool_kind,
    _next_pending_plan_step,
    _parse_inline_tool_calls,
    _rewrite_inline_tool_call_message,
    _rewrite_response_messages,
    _scan_balanced_braces,
    _stream_part_text,
    _strip_special_tokens,
    _ToolCallTextFilter,
    _try_parse_call_args,
)
from pywry.chat.session import ClientCapabilities
from pywry.chat.updates import (
    AgentMessageUpdate,
    PlanUpdate,
    StatusUpdate,
    ThinkingUpdate,
    ToolCallUpdate,
)


# =============================================================================
# Module-level fixtures / helpers
# =============================================================================


class FakeChunk:
    def __init__(self, content: str = "", additional_kwargs: dict | None = None):
        self.content = content
        self.additional_kwargs = additional_kwargs or {}


def make_event(event: str, name: str = "", data: dict | None = None, run_id: str = "r1", **extra):
    return {
        "event": event,
        "name": name,
        "data": data or {},
        "run_id": run_id,
        **extra,
    }


class FakeAgent:
    """Yields a scripted list of events from ``astream_events``."""

    def __init__(self, events: list[dict]):
        self._events = events

    def astream_events(self, _input_data: dict, config: dict = None, version: str = "v2"):
        async def _gen():
            for e in self._events:
                yield e

        return _gen()


async def _drain_prompt(provider: DeepagentProvider, sid: str, text: str = "hi"):
    out = []
    async for u in provider.prompt(sid, [TextPart(text=text)]):
        out.append(u)
    return out


class AIMessage:
    """Duck-typed AIMessage.

    The middleware checks ``msg.__class__.__name__ == 'AIMessage'`` and the
    rewriter reconstructs the message by calling the class as a constructor,
    so this needs to accept the same kwargs as LangChain's AIMessage.
    """

    def __init__(
        self,
        content=None,
        tool_calls=None,
        id=None,
        response_metadata=None,
        additional_kwargs=None,
    ):
        self.content = content
        self.tool_calls = tool_calls
        self.id = id or "msg-id"
        self.response_metadata = response_metadata or {}
        self.additional_kwargs = additional_kwargs or {}


class _NotAIMessage:
    """Any class with a name other than ``AIMessage`` exits the rewriter early."""


@pytest.fixture
def provider_factory():
    """Build a DeepagentProvider with autosetup disabled and an optional agent."""

    def _make(agent=None, **kwargs):
        defaults = {"auto_checkpointer": False, "auto_store": False}
        defaults.update(kwargs)
        return DeepagentProvider(agent=agent, **defaults)

    return _make


# =============================================================================
# Tool-kind / todo-status mapping
# =============================================================================


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


class TestMapTodoStatus:
    def test_known_statuses(self):
        assert _map_todo_status("todo") == "pending"
        assert _map_todo_status("in_progress") == "in_progress"
        assert _map_todo_status("in-progress") == "in_progress"
        assert _map_todo_status("done") == "completed"
        assert _map_todo_status("completed") == "completed"

    def test_unknown_falls_back_to_pending(self):
        assert _map_todo_status("foo") == "pending"


# =============================================================================
# _coerce_text and stream-text helpers
# =============================================================================


class TestCoerceText:
    def test_none(self):
        assert _coerce_text(None) == ""

    def test_string(self):
        assert _coerce_text("hello") == "hello"

    def test_list_of_strings(self):
        assert _coerce_text(["a", "b"]) == "ab"

    def test_list_of_dicts_text_key(self):
        assert _coerce_text([{"text": "a"}, {"text": "b"}]) == "ab"

    def test_list_of_dicts_content_fallback(self):
        assert _coerce_text([{"content": "x"}]) == "x"

    def test_list_skips_non_string_text(self):
        assert _coerce_text([{"text": 42}]) == ""

    def test_other_type_str(self):
        assert _coerce_text(123) == "123"


class TestExtractAnswerFromContent:
    def test_string_content(self):
        assert _extract_answer_from_content("hello") == "hello"

    def test_list_skips_thinking_parts(self):
        content = [
            {"type": "thinking", "text": "skip-me"},
            {"type": "text", "text": "keep-me"},
        ]
        assert _extract_answer_from_content(content) == "keep-me"

    def test_list_skips_tool_call_parts(self):
        content = [
            {"type": "tool_use", "text": "skip-me"},
            {"type": "text", "text": "keep-me"},
        ]
        assert _extract_answer_from_content(content) == "keep-me"

    def test_list_skips_non_dict_parts(self):
        assert _extract_answer_from_content([42, {"type": "text", "text": "x"}]) == "x"


class TestExtractThinkingFromChunk:
    def test_metadata_reasoning_content(self):
        chunk = MagicMock()
        chunk.additional_kwargs = {"reasoning_content": "internal"}
        assert _extract_thinking_from_chunk(chunk, "") == "internal"

    def test_metadata_reasoning_fallback(self):
        chunk = MagicMock()
        chunk.additional_kwargs = {"reasoning": "internal-r"}
        assert _extract_thinking_from_chunk(chunk, "") == "internal-r"

    def test_metadata_thinking_fallback(self):
        chunk = MagicMock()
        chunk.additional_kwargs = {"thinking": "internal-t"}
        assert _extract_thinking_from_chunk(chunk, "") == "internal-t"

    def test_falls_back_to_attribute(self):
        class _Chunk:
            additional_kwargs: dict = {}
            reasoning_content = "attr"

        assert _extract_thinking_from_chunk(_Chunk(), "") == "attr"

    def test_appends_thinking_parts_from_content_list(self):
        chunk = MagicMock()
        chunk.additional_kwargs = {}
        chunk.reasoning_content = ""
        content = [
            {"type": "thinking", "text": "more"},
            {"type": "text", "text": "ignored"},
        ]
        assert "more" in _extract_thinking_from_chunk(chunk, content)

    def test_handles_non_dict_additional_kwargs(self):
        class _Chunk:
            additional_kwargs = ["not", "a", "dict"]
            reasoning_content = "fallback-attr"

        assert _extract_thinking_from_chunk(_Chunk(), "") == "fallback-attr"


class TestExtractStreamText:
    def test_none_chunk(self):
        assert _extract_stream_text(None) == ("", "")

    def test_full_chunk(self):
        chunk = MagicMock()
        chunk.content = [{"type": "text", "text": "answer"}]
        chunk.additional_kwargs = {"reasoning_content": "thought"}
        thinking, answer = _extract_stream_text(chunk)
        assert thinking == "thought"
        assert answer == "answer"


class TestStreamPartText:
    def test_non_dict_returns_empty(self):
        assert _stream_part_text("not a dict") == ""
        assert _stream_part_text(None) == ""
        assert _stream_part_text(42) == ""


class TestIsRootChainEnd:
    def test_yes(self):
        assert _is_root_chain_end({"event": "on_chain_end", "parent_ids": []}) is True

    def test_not_chain_end(self):
        assert _is_root_chain_end({"event": "other"}) is False

    def test_has_parents(self):
        assert _is_root_chain_end({"event": "on_chain_end", "parent_ids": ["p1"]}) is False


# =============================================================================
# _ToolCallTextFilter — drives real text-stream behaviour
# =============================================================================


class TestToolCallTextFilter:
    """End-to-end behaviour of the leaked-tool-call stream filter."""

    def test_empty_feed_returns_empty(self):
        f = _ToolCallTextFilter()
        assert f.feed("") == ""

    def test_passes_through_normal_text(self):
        f = _ToolCallTextFilter()
        assert f.feed("hello world. ") == "hello world. "

    def test_strips_complete_functions_call(self):
        f = _ToolCallTextFilter()
        out = f.feed('before functions.foo:1{"a": 1} after')
        assert "functions.foo" not in out
        assert "before" in out
        assert "after" in (out + f.flush())

    def test_strips_special_token(self):
        f = _ToolCallTextFilter()
        out = f.feed("hello <|tool_call_end|> world")
        flushed = f.flush()
        full = out + flushed
        assert "tool_call_end" not in full
        assert "hello" in full
        assert "world" in full

    def test_buffers_partial_marker_across_chunks(self):
        """The ``functions.`` prefix splits across chunks — filter must stay
        stateful and never emit the prefix as plain text."""
        f = _ToolCallTextFilter()
        out1 = f.feed("function")
        assert "function" not in out1  # held back as unsafe-prefix tail
        out2 = f.feed("s.")
        out3 = f.feed('foo{"a": 1}')
        flushed = f.flush()
        full = out1 + out2 + out3 + flushed
        assert "functions." not in full

    def test_unterminated_call_block_dropped_on_flush(self):
        f = _ToolCallTextFilter()
        f.feed('hello functions.foo{"a": 1')  # no closing brace
        assert f.flush() == ""  # buffer dropped on flush

    def test_unterminated_special_token_dropped_on_flush(self):
        f = _ToolCallTextFilter()
        f.feed("hello <|im_start")  # no closing |>
        assert f.flush() == ""

    def test_flush_returns_remaining_safe_buffer(self):
        f = _ToolCallTextFilter()
        f.feed("ok ")
        assert f.flush() == ""

        # Bytes whose tail is an unsafe-prefix of "functions." stay buffered
        # until flush — feed() emits the safe prefix, flush() returns the tail.
        f2 = _ToolCallTextFilter()
        emitted = f2.feed("ok funct")
        flushed = f2.flush()
        assert emitted == "ok "
        assert flushed == "funct"

    def test_string_with_braces_inside_args(self):
        """The brace counter must be string-literal aware: ``"}"`` in the
        JSON args must not pop the depth."""
        f = _ToolCallTextFilter()
        out = f.feed('functions.x:0{"v": "{}"} ok')
        flushed = f.flush()
        full = out + flushed
        assert "functions.x" not in full
        assert "ok" in full

    def test_escaped_quote_inside_string(self):
        f = _ToolCallTextFilter()
        out = f.feed(r'functions.x{"v":"a\"b"} ok')
        flushed = f.flush()
        full = out + flushed
        assert "functions.x" not in full
        assert "ok" in full

    def test_special_token_with_tail_recursion(self):
        """A special token in the middle of normal text — text on both
        sides is preserved, the token is dropped."""
        f = _ToolCallTextFilter()
        out = f.feed("alpha<|x|>beta")
        flushed = f.flush()
        full = out + flushed
        assert "alpha" in full
        assert "beta" in full
        assert "<|x|>" not in full

    def test_in_call_nested_braces(self):
        """Nested ``{`` inside the JSON args must increment depth so the
        outer ``}`` doesn't close the call prematurely."""
        f = _ToolCallTextFilter()
        out = f.feed('functions.x{"a":{"b":1}} done')
        flushed = f.flush()
        full = out + flushed
        assert "functions.x" not in full
        assert "done" in full

    def test_special_token_close_split_across_chunks(self):
        """The ``|>`` close arrives in a later chunk than the ``<|`` open —
        filter must finish in the ``in_special`` state mid-stream."""
        f = _ToolCallTextFilter()
        f.feed("<|abc")
        out = f.feed("def|>tail")
        flushed = f.flush()
        full = out + flushed
        assert "tail" in full
        assert "<|" not in full


# =============================================================================
# _strip_special_tokens / _parse_inline_tool_calls / helpers
# =============================================================================


class TestStripSpecialTokens:
    def test_no_token_passes_through(self):
        assert _strip_special_tokens("plain") == "plain"

    def test_strips_single_token(self):
        assert _strip_special_tokens("a<|x|>b") == "ab"

    def test_unterminated_keeps_remainder(self):
        result = _strip_special_tokens("a<|never closing")
        assert "a" in result

    def test_empty_input(self):
        assert _strip_special_tokens("") == ""


class TestParseInlineToolCalls:
    def test_empty(self):
        cleaned, calls = _parse_inline_tool_calls("")
        assert cleaned == ""
        assert calls == []

    def test_no_marker_strips_special_tokens(self):
        cleaned, calls = _parse_inline_tool_calls("hello <|tk|> world")
        assert cleaned == "hello  world"
        assert calls == []

    def test_one_call(self):
        cleaned, calls = _parse_inline_tool_calls('go functions.foo{"a": 1} done')
        assert "functions.foo" not in cleaned
        assert len(calls) == 1
        assert calls[0]["name"] == "foo"
        assert calls[0]["args"] == {"a": 1}

    def test_call_with_index_suffix(self):
        _, calls = _parse_inline_tool_calls('functions.foo:42{"x": "y"}')
        assert calls[0]["name"] == "foo"
        assert calls[0]["args"] == {"x": "y"}

    def test_invalid_json_dropped(self):
        _, calls = _parse_inline_tool_calls("functions.foo{42}")
        assert calls == []

    def test_array_args_dropped(self):
        _, calls = _parse_inline_tool_calls("functions.foo{[1,2,3]}")
        # ``{[1,2,3]}`` isn't valid JSON — call dropped
        assert calls == []

    def test_unterminated_payload_drops_tail(self):
        cleaned, _ = _parse_inline_tool_calls('keep functions.foo{"a":1')
        assert "keep" in cleaned
        assert "functions" not in cleaned

    def test_no_name_keeps_one_char(self):
        cleaned, _ = _parse_inline_tool_calls("functions.")
        assert "f" in cleaned

    def test_marker_no_brace_keeps_text(self):
        _, calls = _parse_inline_tool_calls("functions.foo done")
        assert calls == []


class TestConsumeOneInlineCall:
    def test_no_name_returns_idx_plus_one(self):
        out: list[str] = []
        next_i, call = _consume_one_inline_call("functions.@bar", 0, "functions.", out)
        assert next_i == 1
        assert call is None

    def test_index_suffix_then_no_brace(self):
        out: list[str] = []
        next_i, call = _consume_one_inline_call("functions.foo:5  ", 0, "functions.", out)
        assert call is None
        assert next_i is not None


class TestScanBalancedBraces:
    def test_balanced(self):
        assert _scan_balanced_braces("{a}", 0) == 3

    def test_nested(self):
        assert _scan_balanced_braces("{a{b}c}", 0) == 7

    def test_string_with_brace(self):
        s = '{"v": "}"}'
        assert _scan_balanced_braces(s, 0) == len(s)

    def test_unterminated(self):
        assert _scan_balanced_braces("{abc", 0) is None

    def test_escaped_quote(self):
        s = '{"v":"a\\"b"}'
        assert _scan_balanced_braces(s, 0) == len(s)


class TestTryParseCallArgs:
    def test_valid_dict(self):
        assert _try_parse_call_args('{"a": 1}') == {"a": 1}

    def test_invalid_json(self):
        assert _try_parse_call_args("not-json") is None

    def test_non_dict_wrapped(self):
        assert _try_parse_call_args("[1,2,3]") == {"value": [1, 2, 3]}


# =============================================================================
# _coerce_todo_list / _extract_todos_from_tool_output
# =============================================================================


class TestCoerceTodoList:
    def test_list_of_dicts(self):
        assert _coerce_todo_list([{"a": 1}, {"b": 2}]) == [{"a": 1}, {"b": 2}]

    def test_skips_non_dicts(self):
        assert _coerce_todo_list([{"a": 1}, "junk", 3]) == [{"a": 1}]

    def test_empty_list_becomes_none(self):
        assert _coerce_todo_list([]) is None

    def test_non_list_returns_none(self):
        assert _coerce_todo_list("not a list") is None
        assert _coerce_todo_list(None) is None
        assert _coerce_todo_list({"foo": "bar"}) is None


class TestExtractTodosFromToolOutput:
    def test_command_object_with_update(self):
        class _Cmd:
            update = {"todos": [{"content": "x"}]}

        assert _extract_todos_from_tool_output(_Cmd()) == [{"content": "x"}]

    def test_dict_with_nested_update(self):
        out = {"update": {"todos": [{"x": 1}]}}
        assert _extract_todos_from_tool_output(out) == [{"x": 1}]

    def test_dict_with_top_level_todos(self):
        out = {"todos": [{"x": 2}]}
        assert _extract_todos_from_tool_output(out) == [{"x": 2}]

    def test_plain_list(self):
        assert _extract_todos_from_tool_output([{"a": 1}]) == [{"a": 1}]

    def test_json_string(self):
        assert _extract_todos_from_tool_output('[{"a": 1}]') == [{"a": 1}]

    def test_invalid_json_string_returns_none(self):
        assert _extract_todos_from_tool_output("not json {") is None

    def test_unsupported_type(self):
        assert _extract_todos_from_tool_output(42) is None


# =============================================================================
# Middleware helpers — _next_pending_plan_step / message rewriter
# =============================================================================


class TestNextPendingPlanStep:
    def test_no_messages(self):
        assert _next_pending_plan_step({}) is None
        assert _next_pending_plan_step({"messages": []}) is None

    def test_last_not_ai_message(self):
        state = {"messages": [_NotAIMessage()], "todos": [{"status": "pending"}]}
        assert _next_pending_plan_step(state) is None

    def test_pending_tool_calls_skips(self):
        msg = AIMessage(tool_calls=[{"name": "x"}])
        state = {"messages": [msg], "todos": [{"status": "pending"}]}
        assert _next_pending_plan_step(state) is None

    def test_no_todos(self):
        msg = AIMessage()
        assert _next_pending_plan_step({"messages": [msg]}) is None
        assert _next_pending_plan_step({"messages": [msg], "todos": []}) is None
        assert _next_pending_plan_step({"messages": [msg], "todos": "not a list"}) is None

    def test_failed_todo_blocks(self):
        msg = AIMessage()
        state = {
            "messages": [msg],
            "todos": [{"status": "completed"}, {"status": "failed"}],
        }
        assert _next_pending_plan_step(state) is None

    def test_skips_non_dict_todos(self):
        msg = AIMessage()
        state = {
            "messages": [msg],
            "todos": ["junk", {"status": "pending", "content": "next"}],
        }
        assert _next_pending_plan_step(state) == "next"

    def test_returns_first_non_completed(self):
        msg = AIMessage()
        state = {
            "messages": [msg],
            "todos": [
                {"status": "completed", "content": "done"},
                {"status": "pending", "content": "todo-1"},
                {"status": "pending", "content": "todo-2"},
            ],
        }
        assert _next_pending_plan_step(state) == "todo-1"

    def test_falls_back_to_title(self):
        msg = AIMessage()
        state = {"messages": [msg], "todos": [{"status": "pending", "title": "T"}]}
        assert _next_pending_plan_step(state) == "T"

    def test_all_completed_returns_none(self):
        msg = AIMessage()
        state = {
            "messages": [msg],
            "todos": [{"status": "completed"}, {"status": "completed"}],
        }
        assert _next_pending_plan_step(state) is None


class TestFlattenMessageContent:
    def test_string(self):
        assert _flatten_message_content("hi") == "hi"

    def test_list_of_dicts(self):
        assert _flatten_message_content([{"text": "a"}, {"text": "b"}]) == "ab"

    def test_list_of_non_dict(self):
        assert _flatten_message_content([42, "x"]) == "42x"

    def test_unsupported_type(self):
        assert _flatten_message_content(None) is None


class TestRewriteInlineToolCallMessage:
    def test_non_ai_message_passthrough(self):
        msg = _NotAIMessage()
        assert _rewrite_inline_tool_call_message(msg) is msg

    def test_no_changes_returns_input(self):
        msg = AIMessage(content="plain text", tool_calls=None)
        out = _rewrite_inline_tool_call_message(msg)
        assert out is msg

    def test_strips_tokens_and_appends_calls(self):
        msg = AIMessage(
            content='hello <|tok|>functions.f{"x":1} world',
            tool_calls=[{"name": "existing", "args": {}}],
        )
        out = _rewrite_inline_tool_call_message(msg)
        assert out is not msg
        assert "functions.f" not in out.content
        names = [c["name"] for c in out.tool_calls]
        assert "existing" in names
        assert "f" in names

    def test_unsupported_content_passthrough(self):
        msg = AIMessage(content=12345)
        assert _rewrite_inline_tool_call_message(msg) is msg

    def test_special_tokens_only_rewrites(self):
        """No ``functions.`` markup but ``<|...|>`` tokens — message is
        still rewritten with cleaned content."""
        msg = AIMessage(content="hello <|tk|> world")
        out = _rewrite_inline_tool_call_message(msg)
        assert out is not msg
        assert "<|tk|>" not in out.content
        assert "hello" in out.content
        assert "world" in out.content


class TestRewriteResponseMessages:
    def test_response_with_list_result_rewrites(self):
        class _Resp:
            def __init__(self, result):
                self.result = result

        plain = AIMessage(content="plain")
        markup = AIMessage(content='hello functions.f{"x":1}')
        resp = _Resp([plain, markup])
        out = _rewrite_response_messages(resp)
        assert out is resp
        assert isinstance(resp.result, list)
        assert "functions.f" not in resp.result[1].content

    def test_response_without_list_result(self):
        class _Resp:
            result = None

        resp = _Resp()
        assert _rewrite_response_messages(resp) is resp


# =============================================================================
# Construction
# =============================================================================


class TestDeepagentProviderConstruction:
    def test_with_pre_built_agent(self, provider_factory):
        agent = FakeAgent([])
        provider = provider_factory(agent=agent)
        assert provider._agent is agent

    def test_without_agent_stores_params(self):
        provider = DeepagentProvider(model="openai:gpt-4o", system_prompt="be helpful")
        assert provider._agent is None
        assert provider._model == "openai:gpt-4o"

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


# =============================================================================
# initialize() / new_session() / load_session()
# =============================================================================


class TestDeepagentProviderInitialize:
    async def test_returns_capabilities(self, provider_factory):
        provider = provider_factory(agent=FakeAgent([]))
        caps = await provider.initialize(ClientCapabilities())
        assert caps.prompt_capabilities is not None
        assert caps.prompt_capabilities.image is True

    async def test_with_checkpointer_enables_load(self, provider_factory):
        pytest.importorskip("langgraph")
        from langgraph.checkpoint.memory import MemorySaver

        provider = provider_factory(agent=FakeAgent([]), checkpointer=MemorySaver())
        caps = await provider.initialize(ClientCapabilities())
        assert caps.load_session is True

    async def test_without_checkpointer_disables_load(self, provider_factory):
        provider = provider_factory(agent=FakeAgent([]))
        caps = await provider.initialize(ClientCapabilities())
        assert caps.load_session is False

    async def test_auto_creates_checkpointer_and_store(self):
        """When ``auto_checkpointer=True`` / ``auto_store=True`` and the
        provider has no agent yet, initialize() populates both side-effects."""
        provider = DeepagentProvider(
            agent=MagicMock(),
            auto_checkpointer=True,
            auto_store=True,
        )
        sentinel_cp = object()
        sentinel_store = object()
        provider._create_checkpointer = lambda: sentinel_cp  # type: ignore[assignment]
        provider._create_store = lambda: sentinel_store  # type: ignore[assignment]
        caps = await provider.initialize(ClientCapabilities())
        assert provider._checkpointer is sentinel_cp
        assert provider._store is sentinel_store
        assert caps.load_session is True

    async def test_builds_agent_when_none(self):
        provider = DeepagentProvider(auto_checkpointer=False, auto_store=False)
        sentinel = MagicMock()
        provider._build_agent = lambda: sentinel  # type: ignore[assignment]
        await provider.initialize(ClientCapabilities())
        assert provider._agent is sentinel


class TestDeepagentProviderSessions:
    async def test_new_session_returns_id(self, provider_factory):
        provider = provider_factory(agent=FakeAgent([]))
        await provider.initialize(ClientCapabilities())
        sid = await provider.new_session("/tmp")
        assert sid.startswith("da_")

    async def test_load_nonexistent_session_raises(self, provider_factory):
        provider = provider_factory(agent=FakeAgent([]))
        await provider.initialize(ClientCapabilities())
        with pytest.raises(ValueError, match="not found"):
            await provider.load_session("nonexistent", "/tmp")

    async def test_load_existing_returns_id(self):
        provider = DeepagentProvider(model="x", auto_checkpointer=False, auto_store=False)
        provider._sessions["sess1"] = "thread-A"
        assert await provider.load_session("sess1", "/cwd") == "sess1"


class TestNewSessionMcpServers:
    async def test_merges_stdio_descriptor(self, provider_factory):
        provider = provider_factory(agent=FakeAgent([]))
        await provider.initialize(ClientCapabilities())
        await provider.new_session(
            "/tmp",
            mcp_servers=[
                {"name": "fs", "command": "uvx", "args": ["mcp-server-filesystem", "/tmp"]},
            ],
        )
        entry = provider._mcp_servers["fs"]
        assert entry["transport"] == "stdio"
        assert entry["command"] == "uvx"
        assert entry["args"] == ["mcp-server-filesystem", "/tmp"]
        # Mutating mcp_servers forces an agent + tool rebuild on next prompt
        assert provider._agent is None
        assert provider._mcp_tools == []

    async def test_merges_http_descriptor(self, provider_factory):
        provider = provider_factory(agent=FakeAgent([]))
        await provider.initialize(ClientCapabilities())
        await provider.new_session(
            "/tmp",
            mcp_servers=[{"name": "pywry", "url": "http://127.0.0.1:8765/mcp"}],
        )
        entry = provider._mcp_servers["pywry"]
        assert entry["transport"] == "streamable_http"
        assert entry["url"] == "http://127.0.0.1:8765/mcp"

    async def test_no_mcp_keeps_existing_agent(self, provider_factory):
        agent = FakeAgent([])
        provider = provider_factory(agent=agent)
        await provider.initialize(ClientCapabilities())
        await provider.new_session("/tmp")
        assert provider._agent is agent

    async def test_skips_non_dict_entry(self):
        provider = DeepagentProvider(
            agent=MagicMock(), auto_checkpointer=False, auto_store=False
        )
        await provider.initialize(ClientCapabilities())
        await provider.new_session("/tmp", mcp_servers=["junk", 42])
        assert provider._mcp_servers == {}

    async def test_no_name_falls_back_to_uuid_prefix(self):
        provider = DeepagentProvider(
            agent=MagicMock(), auto_checkpointer=False, auto_store=False
        )
        await provider.initialize(ClientCapabilities())
        await provider.new_session("/tmp", mcp_servers=[{"command": "x", "args": []}])
        assert any(k.startswith("acp_") for k in provider._mcp_servers)


# =============================================================================
# Streaming behaviour
# =============================================================================


class TestDeepagentProviderStreaming:
    async def test_text_chunks(self, provider_factory):
        events = [
            make_event("on_chat_model_stream", data={"chunk": FakeChunk("hello ")}),
            make_event("on_chat_model_stream", data={"chunk": FakeChunk("world")}),
        ]
        provider = provider_factory(agent=FakeAgent(events))
        await provider.initialize(ClientCapabilities())
        sid = await provider.new_session("/tmp")

        updates = await _drain_prompt(provider, sid)
        assert len(updates) == 2
        assert all(isinstance(u, AgentMessageUpdate) for u in updates)
        assert updates[0].text == "hello "
        assert updates[1].text == "world"

    async def test_tool_call_lifecycle(self, provider_factory):
        events = [
            make_event("on_tool_start", name="read_file", run_id="tc1"),
            make_event("on_tool_end", name="read_file", run_id="tc1", data={"output": "contents"}),
        ]
        provider = provider_factory(agent=FakeAgent(events))
        await provider.initialize(ClientCapabilities())
        sid = await provider.new_session("/tmp")

        updates = await _drain_prompt(provider, sid, "read")
        assert len(updates) == 2
        assert isinstance(updates[0], ToolCallUpdate)
        assert updates[0].status == "in_progress"
        assert updates[0].kind == "read"
        assert isinstance(updates[1], ToolCallUpdate)
        assert updates[1].status == "completed"

    async def test_tool_error(self, provider_factory):
        events = [
            make_event("on_tool_start", name="execute", run_id="tc2"),
            make_event("on_tool_error", name="execute", run_id="tc2"),
        ]
        provider = provider_factory(agent=FakeAgent(events))
        await provider.initialize(ClientCapabilities())
        sid = await provider.new_session("/tmp")

        updates = await _drain_prompt(provider, sid, "run")
        assert updates[-1].status == "failed"

    async def test_write_todos_produces_plan_update(self, provider_factory):
        import json

        todos = [
            {"title": "Read docs", "status": "done"},
            {"title": "Write code", "status": "in_progress"},
        ]
        events = [
            make_event("on_tool_start", name="write_todos", run_id="tc3"),
            make_event(
                "on_tool_end",
                name="write_todos",
                run_id="tc3",
                data={"output": json.dumps(todos)},
            ),
        ]
        provider = provider_factory(agent=FakeAgent(events))
        await provider.initialize(ClientCapabilities())
        sid = await provider.new_session("/tmp")

        updates = await _drain_prompt(provider, sid, "plan")
        plan_updates = [u for u in updates if isinstance(u, PlanUpdate)]
        assert len(plan_updates) == 1
        assert len(plan_updates[0].entries) == 2
        assert plan_updates[0].entries[0].content == "Read docs"
        assert plan_updates[0].entries[0].status == "completed"
        assert plan_updates[0].entries[1].status == "in_progress"

    async def test_write_todos_langgraph_command_output(self, provider_factory):
        """Deep Agents' ``write_todos`` returns a LangGraph ``Command`` with
        ``update={"todos": [...]}`` — the extractor must pull the list out
        of that shape, not just the legacy plain-JSON list.

        The plan card IS the visualization — no raw Command repr should
        double-render as a tool-call card.
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
        provider = provider_factory(agent=FakeAgent(events))
        await provider.initialize(ClientCapabilities())
        sid = await provider.new_session("/tmp")

        updates = await _drain_prompt(provider, sid, "plan")
        plan_updates = [u for u in updates if isinstance(u, PlanUpdate)]
        assert len(plan_updates) == 1
        assert [e.content for e in plan_updates[0].entries] == [
            "Switch ticker to BTC-USD",
            "Change interval to 1m",
        ]
        assert [e.status for e in plan_updates[0].entries] == ["completed", "in_progress"]
        tool_completed = [
            u
            for u in updates
            if isinstance(u, ToolCallUpdate) and u.status == "completed" and u.name == "write_todos"
        ]
        assert tool_completed == []

    async def test_writes_todos_emits_planning_status_only_at_start(self, provider_factory):
        events = [make_event("on_tool_start", name="write_todos")]
        provider = provider_factory(agent=FakeAgent(events))
        await provider.initialize(ClientCapabilities())
        sid = await provider.new_session("/tmp")

        out = await _drain_prompt(provider, sid)
        statuses = [u for u in out if isinstance(u, StatusUpdate)]
        assert any("Planning" in s.text for s in statuses)

    async def test_cancel_stops_streaming(self, provider_factory):
        events = [
            make_event("on_chat_model_stream", data={"chunk": FakeChunk(f"chunk{i}")})
            for i in range(100)
        ]
        provider = provider_factory(agent=FakeAgent(events))
        await provider.initialize(ClientCapabilities())
        sid = await provider.new_session("/tmp")

        cancel = asyncio.Event()
        updates = []
        async for u in provider.prompt(sid, [TextPart(text="go")], cancel_event=cancel):
            updates.append(u)
            if len(updates) == 3:
                cancel.set()

        assert len(updates) < 100

    async def test_chat_model_start_yields_status(self, provider_factory):
        events = [
            make_event("on_chat_model_start", name="ChatOpenAI"),
            make_event("on_chat_model_stream", data={"chunk": FakeChunk("answer")}),
        ]
        provider = provider_factory(agent=FakeAgent(events))
        await provider.initialize(ClientCapabilities())
        sid = await provider.new_session("/tmp")

        updates = await _drain_prompt(provider, sid)
        assert isinstance(updates[0], StatusUpdate)
        assert "ChatOpenAI" in updates[0].text
        assert isinstance(updates[1], AgentMessageUpdate)

    async def test_chat_model_start_no_name_yields_thinking(self, provider_factory):
        events = [make_event("on_chat_model_start", name="")]
        provider = provider_factory(agent=FakeAgent(events))
        await provider.initialize(ClientCapabilities())
        sid = await provider.new_session("/tmp")

        out = await _drain_prompt(provider, sid)
        statuses = [u for u in out if isinstance(u, StatusUpdate)]
        assert any(s.text == "Thinking..." for s in statuses)

    async def test_subagent_task_emits_status(self, provider_factory):
        events = [make_event("on_chain_start", name="task")]
        provider = provider_factory(agent=FakeAgent(events))
        await provider.initialize(ClientCapabilities())
        sid = await provider.new_session("/tmp")

        out = await _drain_prompt(provider, sid)
        statuses = [u for u in out if isinstance(u, StatusUpdate)]
        assert any("Delegating to subagent" in s.text for s in statuses)

    async def test_chat_model_stream_yields_thinking_only(self, provider_factory):
        events = [
            make_event(
                "on_chat_model_stream",
                data={"chunk": FakeChunk("", additional_kwargs={"reasoning_content": "internal"})},
            )
        ]
        provider = provider_factory(agent=FakeAgent(events))
        await provider.initialize(ClientCapabilities())
        sid = await provider.new_session("/tmp")

        out = await _drain_prompt(provider, sid)
        thinking = [u for u in out if isinstance(u, ThinkingUpdate)]
        assert thinking and thinking[0].text == "internal"

    async def test_prompt_builds_agent_lazily(self):
        """When ``self._agent is None``, prompt() calls ``_build_agent``."""
        provider = DeepagentProvider(model="x", auto_checkpointer=False, auto_store=False)
        sentinel_agent = FakeAgent([])
        provider._build_agent = lambda: sentinel_agent  # type: ignore[assignment]
        sid = await provider.new_session("/tmp")
        assert provider._agent is None
        await _drain_prompt(provider, sid)
        assert provider._agent is sentinel_agent

    async def test_chain_end_emits_safe_buffer_tail(self, provider_factory):
        """An unsafe-prefix tail in the filter buffer (``"hi func"``) gets
        emitted as the chain-end flush since neither ``in_call`` nor
        ``in_special`` is true."""
        events = [
            make_event("on_chat_model_stream", data={"chunk": FakeChunk("hi func")}),
            make_event("on_chain_end", data={}, parent_ids=[]),
        ]
        provider = provider_factory(agent=FakeAgent(events))
        await provider.initialize(ClientCapabilities())
        sid = await provider.new_session("/tmp")

        out = await _drain_prompt(provider, sid)
        full = "".join(getattr(u, "text", "") for u in out if isinstance(u, AgentMessageUpdate))
        assert "func" in full

    async def test_chain_end_flushes_dropping_unclosed_markup(self, provider_factory):
        """A partial ``functions.`` prefix never completes — chain-end flush
        drops it (the buffer is in ``in_call`` would-be state).  Only the
        safe text before the marker survives."""
        events = [
            make_event("on_chat_model_stream", data={"chunk": FakeChunk("hello fun")}),
            make_event("on_chain_end", data={}, parent_ids=[]),
        ]
        provider = provider_factory(agent=FakeAgent(events))
        await provider.initialize(ClientCapabilities())
        sid = await provider.new_session("/tmp")

        out = await _drain_prompt(provider, sid)
        texts = [getattr(u, "text", "") for u in out if isinstance(u, AgentMessageUpdate)]
        assert any("hello" in t for t in texts)


# =============================================================================
# _handle_tool_end edge cases
# =============================================================================


class TestHandleToolEnd:
    async def test_object_content(self, provider_factory):
        class _Out:
            content = "tool-out-text"

        events = [make_event("on_tool_end", name="ls", run_id="r1", data={"output": _Out()})]
        provider = provider_factory(agent=FakeAgent(events))
        await provider.initialize(ClientCapabilities())
        sid = await provider.new_session("/tmp")

        out = await _drain_prompt(provider, sid)
        completed = [u for u in out if isinstance(u, ToolCallUpdate) and u.status == "completed"]
        assert completed
        assert completed[0].content[0]["text"] == "tool-out-text"

    async def test_dict_output_json_encoded(self, provider_factory):
        events = [make_event("on_tool_end", name="ls", run_id="r1", data={"output": {"a": 1}})]
        provider = provider_factory(agent=FakeAgent(events))
        await provider.initialize(ClientCapabilities())
        sid = await provider.new_session("/tmp")

        out = await _drain_prompt(provider, sid)
        completed = [u for u in out if isinstance(u, ToolCallUpdate) and u.status == "completed"]
        assert completed
        assert '"a": 1' in completed[0].content[0]["text"]

    async def test_scalar_output_stringified(self, provider_factory):
        events = [make_event("on_tool_end", name="ls", run_id="r1", data={"output": 42})]
        provider = provider_factory(agent=FakeAgent(events))
        await provider.initialize(ClientCapabilities())
        sid = await provider.new_session("/tmp")

        out = await _drain_prompt(provider, sid)
        completed = [u for u in out if isinstance(u, ToolCallUpdate) and u.status == "completed"]
        assert completed
        assert "42" in completed[0].content[0]["text"]

    async def test_none_output_omits_content(self, provider_factory):
        events = [make_event("on_tool_end", name="ls", run_id="r1", data={"output": None})]
        provider = provider_factory(agent=FakeAgent(events))
        await provider.initialize(ClientCapabilities())
        sid = await provider.new_session("/tmp")

        out = await _drain_prompt(provider, sid)
        completed = [u for u in out if isinstance(u, ToolCallUpdate) and u.status == "completed"]
        assert completed
        assert completed[0].content is None

    async def test_no_run_id_uses_generated_id(self, provider_factory):
        events = [make_event("on_tool_end", name="ls", run_id="", data={"output": "x"})]
        provider = provider_factory(agent=FakeAgent(events))
        await provider.initialize(ClientCapabilities())
        sid = await provider.new_session("/tmp")

        out = await _drain_prompt(provider, sid)
        completed = [u for u in out if isinstance(u, ToolCallUpdate) and u.status == "completed"]
        assert completed
        assert completed[0].tool_call_id.startswith("call_")

    async def test_json_fallback_on_dump_failure(self, provider_factory):
        """When the dict has a value whose ``__str__`` raises, ``json.dumps(
        ..., default=str)`` raises — fall back to plain ``str(output)``."""

        class _Boom:
            def __str__(self):
                raise RuntimeError("boom")

        events = [
            make_event("on_tool_end", name="ls", run_id="r1", data={"output": {"k": _Boom()}}),
        ]
        provider = provider_factory(agent=FakeAgent(events))
        await provider.initialize(ClientCapabilities())
        sid = await provider.new_session("/tmp")

        out = await _drain_prompt(provider, sid)
        completed = [u for u in out if isinstance(u, ToolCallUpdate) and u.status == "completed"]
        assert completed
        assert completed[0].content is not None


# =============================================================================
# Config / recursion-limit
# =============================================================================


class TestRecursionLimitInPromptConfig:
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
        await _drain_prompt(provider, sid)
        assert captured["config"]["recursion_limit"] == 42
        assert captured["config"]["configurable"]["thread_id"]


# =============================================================================
# Internal helpers — _create_checkpointer / _create_store / _load_mcp_tools
# =============================================================================


class TestCreateCheckpointer:
    def test_returns_memory_saver_when_no_backend(self, monkeypatch):
        provider = DeepagentProvider(model="x", auto_checkpointer=False, auto_store=False)
        # Force the state-backend probe to fail → fall through to MemorySaver
        fake_state_factory = MagicMock()
        fake_state_factory.get_state_backend = lambda: (_ for _ in ()).throw(RuntimeError("nope"))
        monkeypatch.setitem(sys.modules, "pywry.state._factory", fake_state_factory)
        result = provider._create_checkpointer()
        assert result is not None  # MemorySaver

    def test_returns_none_when_langgraph_missing(self, monkeypatch):
        provider = DeepagentProvider(model="x", auto_checkpointer=False, auto_store=False)
        fake_state_factory = MagicMock()
        fake_state_factory.get_state_backend = lambda: (_ for _ in ()).throw(RuntimeError("nope"))
        monkeypatch.setitem(sys.modules, "pywry.state._factory", fake_state_factory)

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "langgraph.checkpoint.memory":
                raise ImportError("no langgraph")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        assert provider._create_checkpointer() is None

    def test_redis_path_uses_redis_saver(self, monkeypatch):
        from pywry.state.types import StateBackend

        provider = DeepagentProvider(model="x", auto_checkpointer=False, auto_store=False)

        fake_state_factory = MagicMock()
        fake_state_factory.get_state_backend = lambda: StateBackend.REDIS
        monkeypatch.setitem(sys.modules, "pywry.state._factory", fake_state_factory)

        sentinel = object()
        fake_saver_module = MagicMock()
        fake_saver_module.RedisSaver = lambda url: sentinel
        monkeypatch.setitem(sys.modules, "langgraph.checkpoint.redis", fake_saver_module)

        fake_settings_obj = MagicMock()
        fake_settings_obj.deploy.redis_url = "redis://localhost:6379"
        fake_config_module = MagicMock()
        fake_config_module.get_settings = lambda: fake_settings_obj
        monkeypatch.setitem(sys.modules, "pywry.config", fake_config_module)

        assert provider._create_checkpointer() is sentinel

    def test_sqlite_path_uses_sqlite_saver(self, monkeypatch):
        from pywry.state.types import StateBackend

        provider = DeepagentProvider(model="x", auto_checkpointer=False, auto_store=False)

        fake_state_factory = MagicMock()
        fake_state_factory.get_state_backend = lambda: StateBackend.SQLITE
        monkeypatch.setitem(sys.modules, "pywry.state._factory", fake_state_factory)

        sentinel = object()

        class _SqliteSaver:
            @classmethod
            def from_conn_string(cls, _db_path):
                return sentinel

        fake_saver_module = MagicMock()
        fake_saver_module.SqliteSaver = _SqliteSaver
        monkeypatch.setitem(sys.modules, "langgraph.checkpoint.sqlite", fake_saver_module)

        fake_settings_obj = MagicMock()
        fake_settings_obj.deploy.sqlite_path = "/tmp/state.db"
        fake_config_module = MagicMock()
        fake_config_module.get_settings = lambda: fake_settings_obj
        monkeypatch.setitem(sys.modules, "pywry.config", fake_config_module)

        assert provider._create_checkpointer() is sentinel

    def test_sqlite_path_falls_through_when_sqlite_missing(self, monkeypatch):
        from pywry.state.types import StateBackend

        provider = DeepagentProvider(model="x", auto_checkpointer=False, auto_store=False)

        fake_state_factory = MagicMock()
        fake_state_factory.get_state_backend = lambda: StateBackend.SQLITE
        monkeypatch.setitem(sys.modules, "pywry.state._factory", fake_state_factory)

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "langgraph.checkpoint.sqlite":
                raise ImportError("no sqlite")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        # Should fall back to MemorySaver
        assert provider._create_checkpointer() is not None


class TestCreateStore:
    def test_returns_in_memory_store(self):
        provider = DeepagentProvider(model="x", auto_checkpointer=False, auto_store=False)
        assert provider._create_store() is not None

    def test_returns_none_when_langgraph_missing(self, monkeypatch):
        provider = DeepagentProvider(model="x", auto_checkpointer=False, auto_store=False)
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "langgraph.store.memory":
                raise ImportError("no langgraph")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        assert provider._create_store() is None


class TestLoadMcpTools:
    def test_no_servers_returns_empty(self):
        provider = DeepagentProvider(model="x", auto_checkpointer=False, auto_store=False)
        assert provider._load_mcp_tools() == []

    def test_no_adapter_warns_and_returns_empty(self, monkeypatch):
        provider = DeepagentProvider(
            model="x",
            mcp_servers={"fs": {"transport": "stdio"}},
            auto_checkpointer=False,
            auto_store=False,
        )
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "langchain_mcp_adapters.client":
                raise ImportError("no adapter")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        assert provider._load_mcp_tools() == []

    def test_with_running_loop_uses_threadpool(self, monkeypatch):
        """When called from inside an event loop, the implementation runs
        ``client.get_tools()`` on a threadpool executor."""
        provider = DeepagentProvider(
            model="x",
            mcp_servers={"fs": {"transport": "stdio"}},
            auto_checkpointer=False,
            auto_store=False,
        )

        async def _get_tools():
            return ["tool-A", "tool-B"]

        class _Client:
            def __init__(self, _cfg):
                pass

            def get_tools(self):
                return _get_tools()

        fake_client_module = MagicMock()
        fake_client_module.MultiServerMCPClient = _Client
        monkeypatch.setitem(sys.modules, "langchain_mcp_adapters.client", fake_client_module)

        async def _runner():
            return provider._load_mcp_tools()

        assert asyncio.run(_runner()) == ["tool-A", "tool-B"]

    def test_get_tools_failure_returns_empty(self, monkeypatch):
        provider = DeepagentProvider(
            model="x",
            mcp_servers={"fs": {"transport": "stdio"}},
            auto_checkpointer=False,
            auto_store=False,
        )

        class _Client:
            def __init__(self, _cfg):
                pass

            def get_tools(self):
                raise RuntimeError("boom")

        fake_client_module = MagicMock()
        fake_client_module.MultiServerMCPClient = _Client
        monkeypatch.setitem(sys.modules, "langchain_mcp_adapters.client", fake_client_module)
        assert provider._load_mcp_tools() == []


# =============================================================================
# _build_agent_kwargs / _build_agent
# =============================================================================


class TestBuildAgentKwargs:
    def test_minimal_kwargs(self, monkeypatch):
        # Stub middleware factories so they don't pull in langchain
        monkeypatch.setattr(da, "_build_inline_tool_call_middleware", lambda: None)
        monkeypatch.setattr(da, "_build_plan_continuation_middleware", lambda: None)

        provider = DeepagentProvider(
            model="x",
            auto_checkpointer=False,
            auto_store=False,
        )
        kwargs = provider._build_agent_kwargs([], "system-prompt")
        assert kwargs["model"] == "x"
        assert kwargs["system_prompt"] == "system-prompt"
        # Middlewares are None and user list is empty → not added
        assert "middleware" not in kwargs

    def test_full_kwargs_with_user_middleware(self, monkeypatch):
        sentinel_inline = object()
        sentinel_plan = object()
        sentinel_user = object()
        monkeypatch.setattr(da, "_build_inline_tool_call_middleware", lambda: sentinel_inline)
        monkeypatch.setattr(da, "_build_plan_continuation_middleware", lambda: sentinel_plan)

        provider = DeepagentProvider(
            model="x",
            tools=[lambda: None],
            interrupt_on={"tool": "ask"},
            backend="memory",
            subagents=[{"name": "sub"}],
            skills=["/path/SKILL.md"],
            middleware=[sentinel_user],
            checkpointer=object(),
            store=object(),
            memory=["/AGENTS.md"],
            auto_checkpointer=False,
            auto_store=False,
        )
        kwargs = provider._build_agent_kwargs(provider._tools, "p")
        assert kwargs["middleware"] == [sentinel_inline, sentinel_plan, sentinel_user]
        for key in (
            "tools",
            "checkpointer",
            "interrupt_on",
            "backend",
            "subagents",
            "skills",
            "store",
            "memory",
        ):
            assert key in kwargs


class TestBuildAgent:
    """Drive _build_agent through every system-prompt branch and MCP integration."""

    def _patch_create_deep_agent(self, monkeypatch, captured):
        import types

        fake_module = types.ModuleType("deepagents")

        def _fake_create_deep_agent(**kwargs):
            captured.update(kwargs)
            return MagicMock(name="agent")

        fake_module.create_deep_agent = _fake_create_deep_agent
        monkeypatch.setitem(sys.modules, "deepagents", fake_module)
        monkeypatch.setattr(da, "_build_inline_tool_call_middleware", lambda: None)
        monkeypatch.setattr(da, "_build_plan_continuation_middleware", lambda: None)

    def test_default_system_prompt_is_pywry(self, monkeypatch):
        captured: dict = {}
        self._patch_create_deep_agent(monkeypatch, captured)
        provider = DeepagentProvider(model="x", auto_checkpointer=False, auto_store=False)
        provider._build_agent()
        assert captured["system_prompt"] == da.PYWRY_SYSTEM_PROMPT

    def test_appended_system_prompt(self, monkeypatch):
        captured: dict = {}
        self._patch_create_deep_agent(monkeypatch, captured)
        provider = DeepagentProvider(
            model="x",
            system_prompt="be brief",
            auto_checkpointer=False,
            auto_store=False,
        )
        provider._build_agent()
        assert da.PYWRY_SYSTEM_PROMPT in captured["system_prompt"]
        assert "be brief" in captured["system_prompt"]

    def test_replace_system_prompt(self, monkeypatch):
        captured: dict = {}
        self._patch_create_deep_agent(monkeypatch, captured)
        provider = DeepagentProvider(
            model="x",
            system_prompt="only-this",
            replace_system_prompt=True,
            auto_checkpointer=False,
            auto_store=False,
        )
        provider._build_agent()
        assert captured["system_prompt"] == "only-this"
        assert da.PYWRY_SYSTEM_PROMPT not in captured["system_prompt"]

    def test_loads_mcp_tools_when_servers_configured(self, monkeypatch):
        captured: dict = {}
        self._patch_create_deep_agent(monkeypatch, captured)
        provider = DeepagentProvider(
            model="x",
            mcp_servers={"fs": {"transport": "stdio"}},
            auto_checkpointer=False,
            auto_store=False,
        )
        provider._load_mcp_tools = lambda: ["tool-X"]  # type: ignore[assignment]
        provider._build_agent()
        assert "tool-X" in captured["tools"]


class TestAutoCheckpointerInBuildAgent:
    """The auto-checkpointer must be set up by _build_agent so callers that
    bypass the async initialize() still get conversation persistence."""

    def test_build_agent_creates_checkpointer_when_missing(self, monkeypatch):
        import types

        provider = DeepagentProvider(model="openai:gpt-4o", auto_checkpointer=True)
        assert provider._checkpointer is None

        fake_module = types.ModuleType("deepagents")
        fake_module.create_deep_agent = lambda **kwargs: object()
        monkeypatch.setitem(sys.modules, "deepagents", fake_module)

        provider._build_agent()
        assert provider._checkpointer is not None

    def test_build_agent_does_not_overwrite_existing_checkpointer(self, monkeypatch):
        import types

        sentinel = object()
        provider = DeepagentProvider(
            model="openai:gpt-4o", checkpointer=sentinel, auto_checkpointer=True
        )

        fake_module = types.ModuleType("deepagents")
        fake_module.create_deep_agent = lambda **kwargs: object()
        monkeypatch.setitem(sys.modules, "deepagents", fake_module)

        provider._build_agent()
        assert provider._checkpointer is sentinel


# =============================================================================
# truncate_session
# =============================================================================


class TestTruncateSession:
    def test_no_op_when_checkpointer_missing(self):
        provider = DeepagentProvider(model="x", auto_checkpointer=False, auto_store=False)
        provider.truncate_session("session-1", [])  # no-op, no raise

    def test_calls_delete_thread_when_available(self):
        deleted: list[str] = []

        class _Saver:
            def delete_thread(self, thread_id: str) -> None:
                deleted.append(thread_id)

        provider = DeepagentProvider(
            model="x", checkpointer=_Saver(), auto_checkpointer=False, auto_store=False
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
            model="x", checkpointer=saver, auto_checkpointer=False, auto_store=False
        )
        provider._sessions["sess-1"] = "thread-A"
        provider.truncate_session("sess-1", [])
        assert "thread-A" not in saver.storage
        assert "thread-B" in saver.storage  # other threads untouched

    def test_falls_back_to_adelete_thread_when_sync_missing(self):
        deleted: list[str] = []

        class _AsyncSaver:
            async def adelete_thread(self, thread_id: str) -> None:
                deleted.append(thread_id)

        provider = DeepagentProvider(
            model="x", checkpointer=_AsyncSaver(), auto_checkpointer=False, auto_store=False
        )
        provider._sessions["s1"] = "thread-A"
        provider.truncate_session("s1", [])
        assert deleted == ["thread-A"]

    def test_remaps_session_id_after_dict_pop(self):
        class _DictSaver:
            def __init__(self):
                self.storage = {"thread-A": "junk"}

        saver = _DictSaver()
        provider = DeepagentProvider(
            model="x", checkpointer=saver, auto_checkpointer=False, auto_store=False
        )
        provider._sessions["s1"] = "thread-A"
        provider.truncate_session("s1", [])
        assert "thread-A" not in saver.storage
        assert provider._sessions["s1"].startswith("thread-A:")

    def test_delete_thread_exception_falls_through_to_adelete(self):
        deleted: list[str] = []

        class _BoomSaver:
            def delete_thread(self, _tid: str) -> None:
                raise RuntimeError("boom")

            def adelete_thread(self, tid: str):
                async def _go():
                    deleted.append(tid)

                return _go()

        provider = DeepagentProvider(
            model="x", checkpointer=_BoomSaver(), auto_checkpointer=False, auto_store=False
        )
        provider._sessions["s1"] = "thread-A"
        provider.truncate_session("s1", [])
        assert deleted == ["thread-A"]

    def test_async_inside_running_loop_uses_threadpool(self):
        """Calling truncate_session from inside a running loop dispatches the
        async deletion via a dedicated thread."""
        deleted: list[str] = []

        class _AsyncSaver:
            async def adelete_thread(self, tid: str) -> None:
                deleted.append(tid)

        provider = DeepagentProvider(
            model="x", checkpointer=_AsyncSaver(), auto_checkpointer=False, auto_store=False
        )
        provider._sessions["s1"] = "thread-A"

        async def _run():
            provider.truncate_session("s1", [])

        asyncio.run(_run())
        assert deleted == ["thread-A"]

    def test_adelete_exception_falls_through_to_dict_pop(self):
        class _Saver:
            def __init__(self):
                self.storage = {"thread-A": "x"}

            async def adelete_thread(self, _tid: str) -> None:
                raise RuntimeError("adelete failed")

        saver = _Saver()
        provider = DeepagentProvider(
            model="x", checkpointer=saver, auto_checkpointer=False, auto_store=False
        )
        provider._sessions["s1"] = "thread-A"
        provider.truncate_session("s1", [])
        assert "thread-A" not in saver.storage


# =============================================================================
# Middleware factories — only exercised when langchain is installed
# =============================================================================


class TestBuildMiddlewares:
    """The middleware factories return None when langchain is missing and
    behave as cached singletons otherwise."""

    def test_inline_tool_call_middleware_returns_singleton(self, monkeypatch):
        monkeypatch.setattr(da, "_inline_tool_call_middleware_singleton", None)
        first = da._build_inline_tool_call_middleware()
        if first is not None:
            second = da._build_inline_tool_call_middleware()
            assert first is second

    def test_inline_tool_call_middleware_returns_none_when_langchain_missing(self, monkeypatch):
        monkeypatch.setattr(da, "_inline_tool_call_middleware_singleton", None)
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "langchain.agents.middleware":
                raise ImportError("no langchain agents")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        assert da._build_inline_tool_call_middleware() is None

    def test_plan_continuation_middleware_returns_singleton(self, monkeypatch):
        monkeypatch.setattr(da, "_plan_middleware_singleton", None)
        first = da._build_plan_continuation_middleware()
        if first is not None:
            second = da._build_plan_continuation_middleware()
            assert first is second

    def test_plan_continuation_middleware_returns_none_when_langchain_missing(self, monkeypatch):
        monkeypatch.setattr(da, "_plan_middleware_singleton", None)
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "langchain.agents.middleware":
                raise ImportError("no langchain")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        assert da._build_plan_continuation_middleware() is None

    def test_plan_continuation_after_model_returns_nudge(self, monkeypatch):
        monkeypatch.setattr(da, "_plan_middleware_singleton", None)
        mw = da._build_plan_continuation_middleware()
        if mw is None:
            pytest.skip("langchain.agents.middleware not installed")
        msg = AIMessage()
        state = {
            "messages": [msg],
            "todos": [{"status": "pending", "content": "do-it"}],
        }
        result = mw.after_model(state, runtime=None)
        assert result is not None
        assert result["jump_to"] == "model"
        assert "do-it" in result["messages"][0].content

    def test_plan_continuation_after_model_returns_none_when_no_pending(self, monkeypatch):
        monkeypatch.setattr(da, "_plan_middleware_singleton", None)
        mw = da._build_plan_continuation_middleware()
        if mw is None:
            pytest.skip("langchain.agents.middleware not installed")
        assert mw.after_model({}, runtime=None) is None

    def test_inline_tool_call_middleware_wrap_model_call_sync(self, monkeypatch):
        monkeypatch.setattr(da, "_inline_tool_call_middleware_singleton", None)
        mw = da._build_inline_tool_call_middleware()
        if mw is None:
            pytest.skip("langchain.agents.middleware not installed")

        class _Resp:
            def __init__(self, result):
                self.result = result

        msg = AIMessage(content="plain")

        def handler(_request):
            return _Resp([msg])

        out = mw.wrap_model_call(request="ignored", handler=handler)
        assert out.result == [msg]

    def test_inline_tool_call_middleware_awrap_model_call(self, monkeypatch):
        monkeypatch.setattr(da, "_inline_tool_call_middleware_singleton", None)
        mw = da._build_inline_tool_call_middleware()
        if mw is None:
            pytest.skip("langchain.agents.middleware not installed")

        class _Resp:
            def __init__(self, result):
                self.result = result

        msg = AIMessage(content="plain")

        async def handler(_request):
            return _Resp([msg])

        async def _run():
            return await mw.awrap_model_call(request="r", handler=handler)

        assert asyncio.run(_run()).result == [msg]


# =============================================================================
# prompt() finally block — aclose error swallowed
# =============================================================================


class TestPromptFinallyBlock:
    async def test_aclose_exception_swallowed(self, provider_factory):
        class _BadIter:
            def __aiter__(self):
                return self

            async def __anext__(self):
                raise StopAsyncIteration

            async def aclose(self):
                raise RuntimeError("aclose-failure")

        class _Agent:
            def astream_events(self, _payload, config=None, version="v2"):
                return _BadIter()

        provider = provider_factory(agent=_Agent())
        await provider.initialize(ClientCapabilities())
        sid = await provider.new_session("/tmp")
        # The aclose error inside the finally block is logged and swallowed
        async for _ in provider.prompt(sid, [TextPart(text="hi")]):
            pass
