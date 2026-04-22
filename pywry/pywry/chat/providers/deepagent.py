"""Deep Agents provider for the ACP session interface.

Wraps a LangChain Deep Agents ``CompiledGraph`` (the return value of
``create_deep_agent()``) to implement the ``ChatProvider`` ABC. Streams
LangGraph events and maps them to ACP ``SessionUpdate`` types.

All imports are lazy to avoid hard dependencies on ``deepagents``.
"""

from __future__ import annotations

import logging
import uuid

from typing import TYPE_CHECKING, Any, Literal

from . import ChatProvider


if TYPE_CHECKING:
    import asyncio

    from collections.abc import AsyncIterator

    from ..models import ContentBlock
    from ..session import AgentCapabilities, ClientCapabilities
    from ..updates import SessionUpdate


logger = logging.getLogger(__name__)

PYWRY_SYSTEM_PROMPT = """\
You are operating inside a PyWry chat interface.  Responses stream as \
markdown; tool calls render as collapsible cards showing the call, \
status, and result.  The user sees every tool call and its return.

Attachments prepended with ``--- Attached: <name> ---`` carry routing \
information (e.g. ``widget_id: <id>``) for tool calls — read the block \
before invoking tools that target that widget.

Be concise.  The chat is a conversation, not a report.  Prefer tool \
calls over prose whenever a tool can do the work.  Do not restate \
information the tool-call card already shows.  Do not fabricate data \
the tools did not return.  Do not describe your reasoning when the \
tool cards already make it visible.
"""

_TOOL_KIND_MAP: dict[str, str] = {
    "read_file": "read",
    "write_file": "edit",
    "edit_file": "edit",
    "ls": "search",
    "execute": "execute",
    "write_todos": "think",
    "task": "other",
}


def _map_tool_kind(tool_name: str) -> str:
    return _TOOL_KIND_MAP.get(tool_name, "other")


def _map_todo_status(status: str) -> Literal["pending", "in_progress", "completed"]:
    status_map: dict[str, Literal["pending", "in_progress", "completed"]] = {
        "todo": "pending",
        "in_progress": "in_progress",
        "in-progress": "in_progress",
        "done": "completed",
        "completed": "completed",
    }
    return status_map.get(status, "pending")


def _coerce_text(value: Any) -> str:
    """Flatten a LangChain content value (str | list | None) into plain text."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content") or ""
                if isinstance(text, str) and text:
                    parts.append(text)
        return "".join(parts)
    return str(value)


class _ToolCallTextFilter:
    """Strip leaked tool-call markup from a streamed text token sequence.

    Two distinct markup families bleed into the visible content stream
    on different model + integration combinations:

    1. ``functions.<name>:<idx>{<json args>}`` — qwen3-coder under
       ``langchain-nvidia-ai-endpoints`` emits tool calls inline using
       OpenAI's pre-2024 shorthand.  The integration parses some but
       not all of these into structured ``tool_calls``; the unparsed
       ones surface verbatim.
    2. ``<|tool_call_end|>`` / ``<|tool_calls_section_end|>`` /
       ``<|im_start|>`` / etc. — chat-template special tokens that
       leak through when the integration doesn't fully strip them
       from the model's raw output.

    Both kinds split arbitrarily across stream chunks, so the filter
    is stateful.  ``functions.X{...}`` blocks need brace counting
    with string-literal awareness (escaped quotes, embedded braces
    inside string args).  ``<|...|>`` tokens just need start/end
    pair matching.

    Usage::

        f = _ToolCallTextFilter()
        for chunk_text in stream:
            yield f.feed(chunk_text)
        yield f.flush()
    """

    _CALL_START = "functions."
    _SPECIAL_OPEN = "<|"
    _SPECIAL_CLOSE = "|>"

    def __init__(self) -> None:
        # Bytes received but not yet emitted — may be the start of a
        # ``functions.`` or ``<|`` marker we haven't fully matched.
        self._buffer = ""
        # Inside a ``functions.X{...}`` JSON arg block.
        self._in_call = False
        self._depth = 0
        self._in_string = False
        self._escape = False
        # Inside a ``<|...|>`` chat-template special token.
        self._in_special = False
        # Cache the unsafe-to-emit suffix patterns once.
        self._unsafe_prefixes = (self._CALL_START, self._SPECIAL_OPEN)
        self._unsafe_max = max(len(p) for p in self._unsafe_prefixes)

    def _step_in_call(self, ch: str) -> None:
        """Advance the brace/string state machine inside a ``functions.X{...}`` block."""
        if self._in_string:
            if self._escape:
                self._escape = False
            elif ch == "\\":
                self._escape = True
            elif ch == '"':
                self._in_string = False
            return
        if ch == '"':
            self._in_string = True
        elif ch == "{":
            self._depth += 1
        elif ch == "}":
            self._depth -= 1
            if self._depth <= 0:
                self._in_call = False
                self._depth = 0
                self._in_string = False
                self._escape = False

    def _step_in_special(self, ch: str, out: list[str]) -> None:
        """Advance the ``<|...|>`` state machine; recurse on tail after ``|>``."""
        self._buffer += ch
        close_idx = self._buffer.find(self._SPECIAL_CLOSE)
        if close_idx < 0:
            return
        rest = self._buffer[close_idx + len(self._SPECIAL_CLOSE) :]
        self._buffer = ""
        self._in_special = False
        if rest:
            out.append(self.feed(rest))

    def _try_open_call(self, out: list[str]) -> bool:
        """If a complete ``functions.<name>...{`` opener sits in buffer, enter call mode.

        Returns True if the buffer was consumed (caller skips other checks);
        False if the marker isn't fully present yet — caller must NOT keep
        scanning the buffer for ``<|`` (the ``functions.`` prefix already
        committed us to wait).
        """
        call_idx = self._buffer.find(self._CALL_START)
        if call_idx < 0:
            return False
        brace_idx = self._buffer.find("{", call_idx + len(self._CALL_START))
        if brace_idx < 0:
            # Marker present but no ``{`` yet — keep buffering, do not
            # fall through to the ``<|`` check (it would never match
            # ``functions.`` and we'd over-emit).
            return True
        if call_idx > 0:
            out.append(self._buffer[:call_idx])
        rest = self._buffer[brace_idx + 1 :]
        self._buffer = ""
        self._in_call = True
        self._depth = 1
        self._in_string = False
        self._escape = False
        if rest:
            out.append(self.feed(rest))
        return True

    def _try_open_special(self, out: list[str]) -> bool:
        """If a ``<|...|>`` token (or its open) is in buffer, drop it; return True."""
        special_idx = self._buffer.find(self._SPECIAL_OPEN)
        if special_idx < 0:
            return False
        close_idx = self._buffer.find(self._SPECIAL_CLOSE, special_idx + len(self._SPECIAL_OPEN))
        if close_idx >= 0:
            if special_idx > 0:
                out.append(self._buffer[:special_idx])
            rest = self._buffer[close_idx + len(self._SPECIAL_CLOSE) :]
            self._buffer = ""
            if rest:
                out.append(self.feed(rest))
            return True
        # Open seen but no close yet — drop everything from ``<|`` on,
        # emit the prefix, enter token-skip mode.
        if special_idx > 0:
            out.append(self._buffer[:special_idx])
        self._buffer = ""
        self._in_special = True
        return True

    def _flush_safe_prefix(self, out: list[str]) -> None:
        """Emit any buffer prefix that can't be the start of a marker we'd miss."""
        tail_unsafe = 0
        for prefix in self._unsafe_prefixes:
            # Largest n such that buffer[-n:] is a prefix of marker.
            for n in range(min(len(prefix), len(self._buffer)), 0, -1):
                if prefix.startswith(self._buffer[-n:]):
                    tail_unsafe = max(tail_unsafe, n)
                    break
        emit_len = len(self._buffer) - tail_unsafe
        if emit_len > 0:
            out.append(self._buffer[:emit_len])
            self._buffer = self._buffer[emit_len:]

    def feed(self, text: str) -> str:
        """Feed one chunk of streamed text and return the safe-to-emit prefix."""
        if not text:
            return ""
        out: list[str] = []
        for ch in text:
            if self._in_call:
                self._step_in_call(ch)
                continue
            if self._in_special:
                self._step_in_special(ch, out)
                continue
            self._buffer += ch
            if self._try_open_call(out):
                continue
            if self._try_open_special(out):
                continue
            self._flush_safe_prefix(out)
        return "".join(out)

    def flush(self) -> str:
        """End of stream — emit anything left in the buffer.

        An unterminated ``functions.X{...}`` block or ``<|...|>``
        token is discarded (the stream was cut mid-markup); a buffer
        of ordinary text is returned.
        """
        if self._in_call or self._in_special:
            self._buffer = ""
            self._in_call = False
            self._in_special = False
            self._depth = 0
            self._in_string = False
            self._escape = False
            return ""
        result = self._buffer
        self._buffer = ""
        return result


_STREAM_THINKING_TYPES = {"thinking", "reasoning"}
_STREAM_TOOL_TYPES = {"tool_use", "tool_call", "function_call"}


def _stream_part_text(part: Any) -> str:
    if not isinstance(part, dict):
        return ""
    return _coerce_text(part.get("text") or part.get("content"))


def _extract_answer_from_content(content: Any) -> str:
    """Pull assistant prose out of a chunk's ``content``, skipping non-prose parts."""
    if not isinstance(content, list):
        return _coerce_text(content)
    parts: list[str] = []
    for part in content:
        if not isinstance(part, dict):
            continue
        p_type = str(part.get("type", "")).lower()
        if p_type in _STREAM_THINKING_TYPES or p_type in _STREAM_TOOL_TYPES:
            continue
        parts.append(_stream_part_text(part))
    return "".join(parts)


def _extract_thinking_from_chunk(chunk: Any, content: Any) -> str:
    """Pull thinking/reasoning text out of a chunk's metadata + content parts."""
    additional_kwargs = getattr(chunk, "additional_kwargs", {}) or {}
    text = ""
    if isinstance(additional_kwargs, dict):
        text = _coerce_text(
            additional_kwargs.get("reasoning_content")
            or additional_kwargs.get("reasoning")
            or additional_kwargs.get("thinking")
        )
    if not text:
        text = _coerce_text(getattr(chunk, "reasoning_content", ""))
    if isinstance(content, list):
        for part in content:
            if (
                isinstance(part, dict)
                and str(part.get("type", "")).lower() in _STREAM_THINKING_TYPES
            ):
                text += _stream_part_text(part)
    return text


def _extract_stream_text(chunk: Any) -> tuple[str, str]:
    """Return ``(thinking_text, answer_text)`` from a model stream chunk.

    Skips structured tool-call content parts (``tool_use`` / ``tool_call``
    / ``function_call``) — those are surfaced as tool-call cards via the
    ``on_tool_*`` events, not as prose.  Inline ``functions.<name>:N{...}``
    tool-call markup that some models / integrations leak into the text
    stream is stripped downstream by ``_ToolCallTextFilter``, which has
    to be stateful because the markup splits across chunk boundaries.
    """
    if chunk is None:
        return "", ""
    content = getattr(chunk, "content", "")
    answer_text = _extract_answer_from_content(content)
    thinking_text = _extract_thinking_from_chunk(chunk, content)
    return thinking_text, answer_text


def _is_root_chain_end(event: dict[str, Any]) -> bool:
    """True when the root chain has finished — the signal to end the stream."""
    return event.get("event") == "on_chain_end" and not event.get("parent_ids")


def _strip_special_tokens(text: str) -> str:
    """Strip ``<|...|>`` chat-template special tokens from text.

    Tokens like ``<|tool_call_end|>`` or ``<|im_start|>`` are
    delimiters in the model's chat template that some integrations
    don't fully scrub from the streamed output.  They have no
    visible meaning in the assistant message — drop them.
    """
    if not text or "<|" not in text:
        return text
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        idx = text.find("<|", i)
        if idx < 0:
            out.append(text[i:])
            break
        close = text.find("|>", idx + 2)
        if close < 0:
            # Unterminated — keep what we have and bail.
            out.append(text[i:])
            break
        out.append(text[i:idx])
        i = close + 2
    return "".join(out)


def _parse_inline_tool_calls(text: str) -> tuple[str, list[dict[str, Any]]]:
    """Parse ``functions.<name>:<idx>{<json args>}`` blocks out of text.

    Some models (notably ``qwen3-coder`` on NVIDIA NIM) emit tool calls
    inline in the model's text stream using OpenAI's pre-2024
    ``functions.<tool>:<index>{<json>}`` shorthand instead of populating
    the structured ``tool_calls`` schema.  The LangChain integration
    doesn't know that format and surfaces the markup verbatim in
    ``content`` with an empty ``tool_calls`` list.  Result: the calls
    never fire and the markup leaks into the assistant message.

    This parser walks the text once, brace-counts JSON arg payloads
    with awareness of string literals (so escaped quotes and braces
    inside the args don't unbalance us), and returns:

    - ``cleaned``: the same text with every recognised block removed
      AND any ``<|...|>`` chat-template special tokens scrubbed.
    - ``calls``: a list of ``{"name", "args", "id", "type"}`` dicts in
      LangChain's structured ``tool_calls`` format, ready to assign to
      an ``AIMessage.tool_calls`` field.

    Malformed JSON inside a block is dropped from ``calls`` (the block
    is still stripped from the visible text — better to lose one bad
    call than splice raw markup into the chat).
    """
    if not text:
        return text, []
    if "functions." not in text:
        return _strip_special_tokens(text), []

    out: list[str] = []
    calls: list[dict[str, Any]] = []
    i = 0
    n = len(text)
    marker = "functions."
    while i < n:
        idx = text.find(marker, i)
        if idx < 0:
            out.append(text[i:])
            break
        out.append(text[i:idx])
        next_i, call = _consume_one_inline_call(text, idx, marker, out)
        if next_i is None:
            # Unterminated payload — drop everything from the marker on.
            break
        if call is not None:
            calls.append(call)
        i = next_i
    cleaned = _strip_special_tokens("".join(out))
    return cleaned, calls


def _consume_one_inline_call(
    text: str,
    idx: int,
    marker: str,
    out: list[str],
) -> tuple[int | None, dict[str, Any] | None]:
    """Try to parse one ``functions.<name>:<idx>{<json>}`` block at ``text[idx:]``.

    Returns ``(next_i, call)`` where ``next_i`` is the offset to resume
    scanning from (or ``None`` if the payload was unterminated and the
    caller should bail), and ``call`` is the parsed tool-call dict (or
    ``None`` if there was nothing parseable — the original text gets
    appended to ``out`` so the caller doesn't drop content).
    """
    n = len(text)
    j = idx + len(marker)
    name_start = j
    while j < n and (text[j].isalnum() or text[j] == "_"):
        j += 1
    name = text[name_start:j]
    if not name:
        # ``functions.`` with no identifier — keep that one char.
        out.append(text[idx])
        return idx + 1, None
    # Optional ``:<digits>`` index suffix, then optional whitespace.
    if j < n and text[j] == ":":
        k = j + 1
        while k < n and text[k].isdigit():
            k += 1
        j = k
    while j < n and text[j].isspace():
        j += 1
    if j >= n or text[j] != "{":
        # Looked like a call but no JSON payload — keep original text.
        out.append(text[idx:j])
        return j, None
    payload_end = _scan_balanced_braces(text, j)
    if payload_end is None:
        return None, None
    args = _try_parse_call_args(text[j:payload_end])
    if args is None:
        return payload_end, None
    return payload_end, {
        "name": name,
        "args": args,
        "id": f"call_{uuid.uuid4().hex[:12]}",
        "type": "tool_call",
    }


def _scan_balanced_braces(text: str, start: int) -> int | None:
    """Return the index just past the ``}`` that closes the block opened at ``text[start] == '{'``.

    String-literal aware so ``"}"`` inside a JSON string doesn't pop
    the depth.  Returns ``None`` if the block is unterminated.
    """
    depth = 1
    in_string = False
    escape = False
    k = start + 1
    n = len(text)
    while k < n and depth > 0:
        ch = text[k]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        k += 1
    return k if depth == 0 else None


def _try_parse_call_args(payload: str) -> dict[str, Any] | None:
    """JSON-decode a tool-call args payload, wrapping non-dicts as ``{"value": ...}``."""
    import json as _json

    try:
        args = _json.loads(payload)
    except (ValueError, TypeError):
        return None
    if not isinstance(args, dict):
        return {"value": args}
    return args


_plan_middleware_singleton: Any = None  # pylint: disable=invalid-name


def _next_pending_plan_step(state: dict[str, Any]) -> str | None:
    """Title of the first non-completed todo, or ``None`` if the plan is over.

    Returns ``None`` when the message log doesn't end on an
    ``AIMessage``, that ``AIMessage`` still has ``tool_calls``
    (LangGraph will route on its own), ``todos`` is empty / missing,
    any todo is ``failed`` (fail-fast contract), or every todo is
    already ``completed``.

    ``AIMessage`` is duck-typed so this stays callable when LangChain
    isn't installed.
    """
    messages = state.get("messages") or []
    if not messages:
        return None
    last = messages[-1]
    if last.__class__.__name__ != "AIMessage":
        return None
    if getattr(last, "tool_calls", None):
        return None
    todos = state.get("todos") or []
    if not isinstance(todos, list) or not todos:
        return None
    candidate: str | None = None
    for todo in todos:
        if not isinstance(todo, dict):
            continue
        status = todo.get("status")
        if status == "failed":
            return None
        if status != "completed" and candidate is None:
            candidate = str(todo.get("content") or todo.get("title") or "")
    return candidate


def _build_plan_continuation_middleware() -> Any:
    """Return a ``PlanContinuationMiddleware`` instance (or ``None``).

    Single responsibility: when the model exits with no tool calls
    BUT ``state.todos`` still has at least one non-completed,
    non-failed entry, ``jump_to=model`` with a one-line nudge naming
    the next unfinished step.  The model can either call its tool
    or call ``write_todos`` to mark it done — whichever matches
    reality.

    No nudge-counting, no tool-call inspection, no auto-completion
    of todos.  The model is the source of truth for plan state; the
    middleware just prevents premature exit.
    """
    global _plan_middleware_singleton  # noqa: PLW0603
    if _plan_middleware_singleton is not None:
        return _plan_middleware_singleton

    try:
        from langchain.agents.middleware import AgentMiddleware
        from langchain.agents.middleware.types import hook_config
        from langchain_core.messages import HumanMessage
    except ImportError:
        logger.debug(
            "langchain agents middleware not importable; "
            "skipping PlanContinuationMiddleware install",
            exc_info=True,
        )
        return None

    class PlanContinuationMiddleware(AgentMiddleware):
        """Re-inject the model with the next pending plan step on exit."""

        @hook_config(can_jump_to=["model"])
        def after_model(
            self,
            state: Any,
            runtime: Any,
        ) -> dict[str, Any] | None:
            next_step = _next_pending_plan_step(state)
            if next_step is None:
                return None
            nudge = (
                f"The plan still shows {next_step!r} as not completed.  "
                "Either call its tool now (if the work hasn't happened) "
                "or call ``write_todos`` to mark it completed (if it has)."
            )
            return {
                "jump_to": "model",
                "messages": [HumanMessage(content=nudge)],
            }

    _plan_middleware_singleton = PlanContinuationMiddleware()
    return _plan_middleware_singleton


_inline_tool_call_middleware_singleton: Any = None  # pylint: disable=invalid-name


def _flatten_message_content(content: Any) -> str | None:
    """Coalesce an AIMessage's ``content`` to a string (or ``None`` if unsupported)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            _coerce_text(p.get("text") or p.get("content")) if isinstance(p, dict) else str(p)
            for p in content
        )
    return None


def _scrub_text(text: str) -> tuple[str, list[dict[str, Any]]]:
    """Strip leaked tool-call markup from text; return ``(cleaned, parsed_calls)``."""
    if "functions." in text:
        return _parse_inline_tool_calls(text)
    if "<|" in text and "|>" in text:
        return _strip_special_tokens(text), []
    return text, []


def _rewrite_inline_tool_call_message(msg: Any) -> Any:
    """Convert leaked ``functions.X{...}`` markup in a message into structured tool_calls.

    Duck-types ``AIMessage`` so this is safe to call when LangChain
    isn't installed.  Returns the input unchanged if it isn't an
    ``AIMessage`` or if the content is structurally unrecognised.
    """
    if msg.__class__.__name__ != "AIMessage":
        return msg
    text = _flatten_message_content(getattr(msg, "content", None))
    if text is None:
        return msg
    cleaned, parsed_calls = _scrub_text(text)
    if cleaned == text and not parsed_calls:
        return msg
    # APPEND parsed inline calls to existing structured calls — a
    # single response can mix both formats; short-circuiting on a
    # non-empty existing list would silently drop the inline ones.
    existing_calls = list(getattr(msg, "tool_calls", None) or [])
    return msg.__class__(
        content=cleaned,
        tool_calls=existing_calls + parsed_calls,
        id=getattr(msg, "id", None),
        response_metadata=getattr(msg, "response_metadata", {}) or {},
        additional_kwargs=getattr(msg, "additional_kwargs", {}) or {},
    )


def _rewrite_response_messages(response: Any) -> Any:
    """Apply ``_rewrite_inline_tool_call_message`` to every result message in a response."""
    result = getattr(response, "result", None)
    if isinstance(result, list):
        response.result = [_rewrite_inline_tool_call_message(m) for m in result]
    return response


def _build_inline_tool_call_middleware() -> Any:
    """Return an ``InlineToolCallMiddleware`` instance (or ``None``).

    Some chat-model integrations don't parse the model's text-stream
    tool-call format into structured ``tool_calls``.  Concretely:
    ``langchain-nvidia-ai-endpoints`` driving ``qwen3-coder`` returns
    ``AIMessage`` objects whose ``content`` carries
    ``functions.<tool>:<idx>{<json>}`` markup but whose ``tool_calls``
    list is empty.  LangGraph's react agent routes on ``tool_calls`` —
    if it's empty the agent ends, the tools never fire, and the user
    sees the markup spliced into the assistant message.

    The wrapped model call passes every returned message through
    ``_rewrite_inline_tool_call_message``: inline markup gets parsed
    and APPENDED to whatever structured ``tool_calls`` already exist
    (a single response can mix both formats), and ``<|...|>``
    chat-template special tokens get scrubbed.

    Cached as a singleton because the class is stateless.
    """
    global _inline_tool_call_middleware_singleton  # noqa: PLW0603
    if _inline_tool_call_middleware_singleton is not None:
        return _inline_tool_call_middleware_singleton

    try:
        from langchain.agents.middleware import AgentMiddleware
    except ImportError:
        logger.debug(
            "langchain agents middleware not importable; skipping InlineToolCallMiddleware install",
            exc_info=True,
        )
        return None

    class InlineToolCallMiddleware(AgentMiddleware):
        """Convert leaked ``functions.X:N{...}`` markup into structured tool_calls."""

        def wrap_model_call(self, request: Any, handler: Any) -> Any:
            return _rewrite_response_messages(handler(request))

        async def awrap_model_call(self, request: Any, handler: Any) -> Any:
            return _rewrite_response_messages(await handler(request))

    _inline_tool_call_middleware_singleton = InlineToolCallMiddleware()
    return _inline_tool_call_middleware_singleton


def _coerce_todo_list(value: Any) -> list[dict[str, Any]] | None:
    """Return ``value`` as a list of todo-dicts, or ``None`` if it isn't."""
    if isinstance(value, list):
        filtered = [t for t in value if isinstance(t, dict)]
        return filtered or None
    return None


def _extract_todos_from_tool_output(output: Any) -> list[dict[str, Any]] | None:
    """Pull the todo list out of ``write_todos``'s tool output.

    Deep Agents implements ``write_todos`` as a LangGraph ``Command``
    that updates the graph state with ``update={"todos": [...], ...}``.
    The streamed ``on_tool_end`` event surfaces this Command object
    directly (not a JSON blob).  Older LangChain versions / custom tool
    wrappers sometimes yield a plain list or a JSON-encoded string of
    the same shape.  Handle all three.
    """
    import json as _json

    # ``Command(update={...})`` — pull ``update.todos``
    update = getattr(output, "update", None)
    if isinstance(update, dict):
        todos = _coerce_todo_list(update.get("todos"))
        if todos is not None:
            return todos

    # ``{"update": {"todos": [...]}}`` or ``{"todos": [...]}``
    if isinstance(output, dict):
        nested = output.get("update")
        if isinstance(nested, dict):
            todos = _coerce_todo_list(nested.get("todos"))
            if todos is not None:
                return todos
        return _coerce_todo_list(output.get("todos"))

    # Plain list of todo dicts
    if isinstance(output, list):
        return _coerce_todo_list(output)

    # JSON-encoded string — recurse once on the decoded value
    if isinstance(output, str):
        try:
            decoded = _json.loads(output)
        except (ValueError, TypeError):
            decoded = None
        return _extract_todos_from_tool_output(decoded) if decoded is not None else None

    return None


class DeepagentProvider(ChatProvider):
    """Provider wrapping a LangChain Deep Agents ``CompiledGraph``.

    Parameters
    ----------
    agent : CompiledGraph or None
        A pre-built agent from ``create_deep_agent()``. If ``None``,
        the provider calls ``create_deep_agent()`` internally using
        the other parameters.
    model : str
        Model identifier in ``provider:model`` format.
    tools : list[callable] or None
        Local LangChain-compatible tool callables.  Merged with any
        MCP-served tools before the agent is built.
    mcp_servers : dict[str, dict] or None
        MCP servers the agent should connect to, in the
        ``langchain_mcp_adapters.client.MultiServerMCPClient`` config
        format — one entry per server, keyed by a short name.  Example::

            {
                "pywry": {
                    "transport": "streamable_http",
                    "url": "http://127.0.0.1:8765/mcp",
                },
                "fs": {
                    "transport": "stdio",
                    "command": "uvx",
                    "args": ["mcp-server-filesystem", "/tmp"],
                },
            }

        On first agent build the provider connects to every server and
        converts the exposed MCP tools into LangChain tools, merging
        them with ``tools`` before calling ``create_deep_agent``.
        Requires the ``pywry[deepagent]`` extra (which pulls in
        ``langchain-mcp-adapters``).
    system_prompt : str
        System instructions for the agent.  By default this is *appended*
        to ``PYWRY_SYSTEM_PROMPT`` (the general-purpose guidance about
        the PyWry chat environment).  Pass ``replace_system_prompt=True``
        to fully override instead — useful when the caller's agent has
        a narrow tool surface and needs tighter output constraints than
        the general prompt allows.
    replace_system_prompt : bool
        If ``True``, ``system_prompt`` replaces ``PYWRY_SYSTEM_PROMPT``
        entirely instead of being appended.  Defaults to ``False``.
    checkpointer : Any or None
        LangGraph checkpointer for session persistence. If ``None``
        and ``auto_checkpointer=True``, one is created based on
        PyWry's state backend.
    store : Any or None
        LangGraph Memory Store for cross-session knowledge persistence.
        If ``None`` and ``auto_store=True``, an ``InMemoryStore`` is
        created so the agent retains knowledge within the process
        lifetime.
    memory : list[str] or None
        Paths to memory files (e.g. ``["/AGENTS.md"]``) that the
        agent can read and write for persistent context.
    interrupt_on : dict or None
        Tool names that require human approval before execution.
    backend : Any or None
        Deep Agents filesystem backend.
    subagents : list[dict] or None
        Subagent configurations.
    skills : list[str] or None
        File paths to Deep Agents skill markdown files that the agent
        can reference on demand.  PyWry ships seventeen of these under
        ``pywry.mcp.skills`` (``tvchart``, ``chat_agent``, ``events``,
        ``component_reference``, ``authentication``, etc.) — build the
        list with ``pathlib.Path(pywry.mcp.skills.__file__).parent /
        "<skill>" / "SKILL.md"``.  Forwarded verbatim to
        ``create_deep_agent(skills=...)``.
    middleware : list or None
        Deep Agents middleware callables.
    auto_checkpointer : bool
        Auto-select checkpointer based on PyWry state backend.  Runs on
        first ``_build_agent()`` so callers that bypass the async
        ``initialize()`` still get conversation-history persistence.
    auto_store : bool
        Auto-create an ``InMemoryStore`` if no ``store`` is provided.
        The store enables cross-thread memory persistence within the
        process lifetime.
    recursion_limit : int
        LangGraph recursion limit per prompt turn.  Every tool call
        costs 2-3 graph steps, so the default (``50``) leaves headroom
        for multi-tool turns without hiding pathological loops.
        LangGraph's own default is ``25``.
    """

    def __init__(
        self,
        agent: Any = None,
        *,
        model: str = "anthropic:claude-sonnet-4-6",
        tools: list[Any] | None = None,
        mcp_servers: dict[str, dict[str, Any]] | None = None,
        system_prompt: str = "",
        replace_system_prompt: bool = False,
        checkpointer: Any = None,
        store: Any = None,
        memory: list[str] | None = None,
        interrupt_on: dict[str, Any] | None = None,
        backend: Any = None,
        subagents: list[dict[str, Any]] | None = None,
        skills: list[str] | None = None,
        middleware: list[Any] | None = None,
        auto_checkpointer: bool = True,
        auto_store: bool = True,
        recursion_limit: int = 50,
        **kwargs: Any,
    ) -> None:
        self._agent = agent
        self._model = model
        self._tools = tools or []
        # Map of server_name -> connection config in the format
        # ``langchain_mcp_adapters.client.MultiServerMCPClient`` accepts.
        # Example::
        #
        #     {"pywry": {"transport": "streamable_http",
        #                "url": "http://127.0.0.1:8765/mcp"}}
        #     {"fs": {"transport": "stdio", "command": "uvx",
        #             "args": ["mcp-server-filesystem", "/tmp"]}}
        self._mcp_servers = mcp_servers or {}
        self._mcp_tools: list[Any] = []
        self._system_prompt = system_prompt
        self._replace_system_prompt = replace_system_prompt
        self._checkpointer = checkpointer
        self._store = store
        self._memory = memory
        self._interrupt_on = interrupt_on
        self._backend = backend
        self._subagents = subagents
        self._skills = skills
        self._middleware = middleware
        self._auto_checkpointer = auto_checkpointer
        self._auto_store = auto_store
        self._recursion_limit = recursion_limit
        self._kwargs = kwargs
        self._sessions: dict[str, str] = {}

    async def initialize(self, capabilities: ClientCapabilities) -> AgentCapabilities:
        """Build the agent and configure the checkpointer.

        Parameters
        ----------
        capabilities : ClientCapabilities
            Client features.

        Returns
        -------
        AgentCapabilities
            Agent features.
        """
        from ..session import AgentCapabilities, PromptCapabilities

        if self._checkpointer is None and self._auto_checkpointer:
            self._checkpointer = self._create_checkpointer()

        if self._store is None and self._auto_store:
            self._store = self._create_store()

        if self._agent is None:
            self._agent = self._build_agent()

        return AgentCapabilities(
            promptCapabilities=PromptCapabilities(image=True),
            loadSession=self._checkpointer is not None,
        )

    def _create_checkpointer(self) -> Any:
        try:
            from ...state._factory import get_state_backend
            from ...state.types import StateBackend

            backend = get_state_backend()
            if backend == StateBackend.REDIS:
                from langgraph.checkpoint.redis import (  # pylint: disable=import-error,no-name-in-module
                    RedisSaver,
                )

                from ...config import get_settings

                return RedisSaver(get_settings().deploy.redis_url)
            if backend == StateBackend.SQLITE:
                try:
                    from langgraph.checkpoint.sqlite import SqliteSaver

                    from ...config import get_settings

                    db_path = get_settings().deploy.sqlite_path.replace(".db", "_langgraph.db")
                    return SqliteSaver.from_conn_string(db_path)
                except ImportError:
                    pass
        except Exception:
            logger.debug("Could not auto-configure checkpointer from state backend", exc_info=True)

        try:
            from langgraph.checkpoint.memory import MemorySaver

            return MemorySaver()
        except ImportError:
            logger.debug("langgraph not installed, skipping checkpointer")
            return None

    def _create_store(self) -> Any:
        try:
            from langgraph.store.memory import InMemoryStore

            return InMemoryStore()
        except ImportError:
            logger.debug("langgraph not installed, skipping memory store")
            return None

    def _load_mcp_tools(self) -> list[Any]:
        """Connect to configured MCP servers and load their tools.

        Uses ``langchain_mcp_adapters.client.MultiServerMCPClient`` to
        connect to every server in ``self._mcp_servers`` and convert the
        exposed MCP tools into LangChain tools.  Returns an empty list
        when no servers are configured or the bridge package is missing.
        """
        if not self._mcp_servers:
            return []
        try:
            from langchain_mcp_adapters.client import (
                MultiServerMCPClient,
            )
        except ImportError:
            logger.warning(
                "mcp_servers configured but langchain-mcp-adapters is not "
                "installed; install with `pip install langchain-mcp-adapters` "
                "or `pip install pywry[deepagent]`",
            )
            return []

        try:
            import asyncio as _asyncio
            import warnings as _warnings

            # ``MultiServerMCPClient``'s type signature expects a
            # ``dict[str, StdioConnection | SSEConnection | ...]`` but
            # the runtime accepts plain dicts that carry a
            # ``transport`` key.  We keep ``_mcp_servers`` as
            # ``dict[str, dict[str, Any]]`` so the ACP surface isn't
            # coupled to the adapter's exported typed-dicts.
            client = MultiServerMCPClient(self._mcp_servers)  # type: ignore[arg-type]

            def _get_tools() -> list[Any]:
                # langchain-mcp-adapters <= 0.2.2 imports the deprecated
                # ``mcp.client.streamable_http.streamablehttp_client``.
                # The rename is upstream-only; filter the noise until
                # the adapter package catches up.
                with _warnings.catch_warnings():
                    _warnings.filterwarnings(
                        "ignore",
                        message="Use `streamable_http_client` instead.",
                        category=DeprecationWarning,
                    )
                    return _asyncio.run(client.get_tools())

            try:
                _asyncio.get_running_loop()
            except RuntimeError:
                # No running loop — safe to run directly on this thread.
                tools = _get_tools()
            else:
                # A loop is already running (we're inside an async
                # context).  Run the coroutine on a dedicated thread so
                # we don't collide with the active loop.
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    tools = pool.submit(_get_tools).result()
            return list(tools or [])
        except Exception:
            logger.exception("Failed to load tools from configured MCP servers")
            return []

    def _build_agent_kwargs(self, merged_tools: list[Any], system_prompt: str) -> dict[str, Any]:
        """Assemble the kwargs dict for ``create_deep_agent`` from provider state."""
        # Two framework-level middlewares with non-overlapping
        # responsibilities:
        #
        # * ``InlineToolCallMiddleware`` — protocol adapter.  Rewrites
        #   inline ``functions.<name>:<idx>{...}`` tool-call markup
        #   into structured ``tool_calls`` so LangGraph routes to the
        #   tool node.  Runs FIRST so the next middleware sees the
        #   rewritten message.
        # * ``PlanContinuationMiddleware`` — re-injects the next
        #   unfinished plan step when the model exits with no tool
        #   calls but pending todos remain.  Pure read of
        #   ``state.todos``; no bookkeeping, no auto-completion.
        inline_middleware = _build_inline_tool_call_middleware()
        plan_middleware = _build_plan_continuation_middleware()
        user_middleware = list(self._middleware or [])
        middleware: list[Any] = []
        if inline_middleware is not None:
            middleware.append(inline_middleware)
        if plan_middleware is not None:
            middleware.append(plan_middleware)
        middleware.extend(user_middleware)

        kwargs: dict[str, Any] = {"model": self._model, "system_prompt": system_prompt}
        optional: dict[str, Any] = {
            "tools": merged_tools or None,
            "checkpointer": self._checkpointer,
            "interrupt_on": self._interrupt_on,
            "backend": self._backend,
            "subagents": self._subagents,
            "skills": self._skills,
            "middleware": middleware or None,
            "store": self._store,
            "memory": self._memory,
        }
        kwargs.update({key: value for key, value in optional.items() if value})
        kwargs.update(self._kwargs)
        return kwargs

    def _build_agent(self) -> Any:
        from deepagents import create_deep_agent

        # Auto-create the checkpointer here too so callers that bypass
        # initialize() (e.g. building the agent eagerly before show()) still
        # get conversation-history persistence across turns within a thread.
        if self._checkpointer is None and self._auto_checkpointer:
            self._checkpointer = self._create_checkpointer()
        if self._store is None and self._auto_store:
            self._store = self._create_store()

        # Connect to MCP servers and load their tools (cached per build).
        if not self._mcp_tools and self._mcp_servers:
            self._mcp_tools = self._load_mcp_tools()
        merged_tools = list(self._tools) + list(self._mcp_tools)

        # ``replace_system_prompt=True`` fully overrides PYWRY_SYSTEM_PROMPT
        # — callers that want strict brevity (agents whose entire surface
        # is a handful of narrowly-defined tools and terse replies) can
        # turn off the general-purpose guidance that otherwise fights
        # their hard constraints.
        if self._replace_system_prompt and self._system_prompt:
            combined_prompt = self._system_prompt
        elif self._system_prompt:
            combined_prompt = PYWRY_SYSTEM_PROMPT + "\n\n" + self._system_prompt
        else:
            combined_prompt = PYWRY_SYSTEM_PROMPT

        kwargs = self._build_agent_kwargs(merged_tools, combined_prompt)
        return create_deep_agent(**kwargs)

    async def new_session(
        self,
        cwd: str,
        mcp_servers: list[dict[str, Any]] | None = None,
    ) -> str:
        """Create a session mapped to a LangGraph thread_id.

        Parameters
        ----------
        cwd : str
            Working directory context.
        mcp_servers : list[dict] or None
            ACP-style MCP server descriptors.  Each entry is converted to
            the ``MultiServerMCPClient`` config format and merged into
            the provider's existing ``mcp_servers`` map; the next agent
            build picks them up.

        Returns
        -------
        str
            Session identifier.
        """
        if mcp_servers:
            for entry in mcp_servers:
                if not isinstance(entry, dict):
                    continue
                name = entry.get("name") or f"acp_{uuid.uuid4().hex[:6]}"
                if "command" in entry or "args" in entry:
                    self._mcp_servers[name] = {
                        "transport": "stdio",
                        "command": entry.get("command", ""),
                        "args": entry.get("args", []),
                        "env": entry.get("env"),
                    }
                elif "url" in entry:
                    self._mcp_servers[name] = {
                        "transport": entry.get("transport", "streamable_http"),
                        "url": entry["url"],
                        "headers": entry.get("headers"),
                    }
            # Force a rebuild so the next prompt sees the new tools.
            self._mcp_tools = []
            self._agent = None

        session_id = f"da_{uuid.uuid4().hex[:8]}"
        thread_id = uuid.uuid4().hex
        self._sessions[session_id] = thread_id
        return session_id

    async def load_session(self, session_id: str, cwd: str) -> str:
        """Resume a session using its LangGraph thread_id.

        Parameters
        ----------
        session_id : str
            Session to restore.
        cwd : str
            Working directory.

        Returns
        -------
        str
            The restored session identifier.
        """
        if session_id not in self._sessions:
            msg = f"Session {session_id} not found"
            raise ValueError(msg)
        return session_id

    async def prompt(
        self,
        session_id: str,
        content: list[ContentBlock],
        cancel_event: asyncio.Event | None = None,
    ) -> AsyncIterator[SessionUpdate]:
        """Stream LangGraph events as ACP SessionUpdate objects.

        Parameters
        ----------
        session_id : str
            Active session identifier.
        content : list[ContentBlock]
            User message content blocks.
        cancel_event : asyncio.Event or None
            Cooperative cancellation signal.

        Yields
        ------
        SessionUpdate
            Typed update notifications.
        """
        from ..models import TextPart

        thread_id = self._sessions.get(session_id, session_id)
        user_text = "".join(p.text for p in content if isinstance(p, TextPart))
        config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": self._recursion_limit,
        }

        # Hold a reference to the inner async iterator so we can close
        # it explicitly when this generator exits — otherwise breaking
        # out of the loop (cancel, on_chain_end, caller-side ``break``)
        # leaves a pending ``aclose()`` task and Python emits
        # ``RuntimeWarning: coroutine method 'aclose' ... was never
        # awaited``.
        # Per-prompt filter that strips ``functions.<name>:N{...}``
        # tool-call markup leaking into the model's text stream.  The
        # markup splits across chunk boundaries so this MUST be
        # stateful across the whole stream.
        text_filter = _ToolCallTextFilter()

        event_iter = self._agent.astream_events(
            {"messages": [{"role": "user", "content": user_text}]},
            config=config,
            version="v2",
        )
        try:
            async for event in event_iter:
                if cancel_event and cancel_event.is_set():
                    return
                if _is_root_chain_end(event):
                    # Flush any pending buffer one last time so a
                    # legitimate trailing sentence isn't truncated by
                    # the filter's lookahead window.
                    tail = text_filter.flush()
                    if tail:
                        from ..updates import AgentMessageUpdate

                        yield AgentMessageUpdate(text=tail)
                    return
                async for update in self._dispatch_stream_event(event, text_filter):
                    yield update
        finally:
            aclose = getattr(event_iter, "aclose", None)
            if callable(aclose):
                try:
                    await aclose()
                except Exception:
                    logger.debug("astream_events.aclose() raised", exc_info=True)

    async def _stream_chat_model(
        self,
        event: dict[str, Any],
        text_filter: _ToolCallTextFilter | None,
    ) -> AsyncIterator[SessionUpdate]:
        """Yield ThinkingUpdate / AgentMessageUpdate for ``on_chat_model_stream``."""
        from ..updates import AgentMessageUpdate, ThinkingUpdate

        chunk = event.get("data", {}).get("chunk")
        thinking_text, answer_text = _extract_stream_text(chunk)
        if thinking_text:
            yield ThinkingUpdate(text=thinking_text)
        if not answer_text:
            return
        if text_filter is not None:
            answer_text = text_filter.feed(answer_text)
        if answer_text:
            yield AgentMessageUpdate(text=answer_text)

    async def _stream_tool_start(self, event: dict[str, Any]) -> AsyncIterator[SessionUpdate]:
        """Yield StatusUpdate (write_todos) or ToolCallUpdate for ``on_tool_start``."""
        from ..updates import StatusUpdate, ToolCallUpdate

        tool_name = event.get("name", "")
        # ``write_todos`` renders as the plan card above the input,
        # not as a tool-call card.  Surface a terse status instead.
        if tool_name == "write_todos":
            yield StatusUpdate(text="Planning...")
            return
        yield ToolCallUpdate(
            toolCallId=event.get("run_id", f"call_{uuid.uuid4().hex[:8]}"),
            name=tool_name,
            kind=_map_tool_kind(tool_name),
            status="in_progress",
        )

    async def _stream_misc_event(
        self, event: dict[str, Any], kind: str
    ) -> AsyncIterator[SessionUpdate]:
        """Yield updates for the smaller event kinds (errors, status, subagent)."""
        from ..updates import StatusUpdate, ToolCallUpdate

        if kind == "on_tool_error":
            tool_name = event.get("name", "")
            yield ToolCallUpdate(
                toolCallId=event.get("run_id", f"call_{uuid.uuid4().hex[:8]}"),
                name=tool_name,
                kind=_map_tool_kind(tool_name),
                status="failed",
            )
            return
        if kind == "on_chat_model_start":
            model_name = event.get("name", "")
            yield StatusUpdate(text=f"Thinking ({model_name})..." if model_name else "Thinking...")
            return
        if kind == "on_chain_start" and event.get("name") == "task":
            yield StatusUpdate(text="Delegating to subagent...")

    async def _dispatch_stream_event(
        self,
        event: dict[str, Any],
        text_filter: _ToolCallTextFilter | None = None,
    ) -> AsyncIterator[SessionUpdate]:
        """Route a single LangGraph streaming event to the matching update.

        ``text_filter`` is the per-prompt stateful stripper that removes
        leaked ``functions.<name>:N{...}`` tool-call markup from the
        assistant text stream.  Optional so tests / direct callers can
        skip it; production paths in ``prompt()`` always pass one.
        """
        kind = event.get("event", "")
        if kind == "on_chat_model_stream":
            async for update in self._stream_chat_model(event, text_filter):
                yield update
        elif kind == "on_tool_start":
            async for update in self._stream_tool_start(event):
                yield update
        elif kind == "on_tool_end":
            async for update in self._handle_tool_end(event):
                yield update
        else:
            async for update in self._stream_misc_event(event, kind):
                yield update

    async def _handle_tool_end(self, event: dict[str, Any]) -> AsyncIterator[SessionUpdate]:
        """Handle on_tool_end events, including write_todos → PlanUpdate."""
        import json

        from ..session import PlanEntry
        from ..updates import PlanUpdate, ToolCallUpdate

        tool_name = event.get("name", "")
        run_id = event.get("run_id", "")
        output = event.get("data", {}).get("output", "")

        if tool_name == "write_todos":
            todos = _extract_todos_from_tool_output(output)
            if todos:
                yield PlanUpdate(
                    entries=[
                        PlanEntry(
                            content=item.get("title", item.get("content", str(item))),
                            priority="medium",
                            status=_map_todo_status(item.get("status", "pending")),
                        )
                        for item in todos
                    ]
                )
                # The plan card IS the visualization — don't ALSO emit a
                # tool-call card whose ``result`` is the raw ``Command(
                # update={'todos': ...})`` repr.  That would double-render
                # the same information as prose chrome.
                return

        # Coerce LangChain ToolMessage / structured output to a plain string
        # so the UI can render it inside the collapsible tool-call card.
        result_text = ""
        if hasattr(output, "content"):
            result_text = str(output.content)
        elif isinstance(output, (dict, list)):
            try:
                result_text = json.dumps(output, default=str, indent=2)
            except Exception:
                result_text = str(output)
        elif output is not None:
            result_text = str(output)

        yield ToolCallUpdate(
            toolCallId=run_id or f"call_{uuid.uuid4().hex[:8]}",
            name=tool_name,
            kind=_map_tool_kind(tool_name),
            status="completed",
            content=[{"type": "text", "text": result_text}] if result_text else None,
        )

    async def cancel(self, session_id: str) -> None:
        """Cancel is handled cooperatively via ``cancel_event``.

        Parameters
        ----------
        session_id : str
            Session to cancel.
        """

    def truncate_session(  # pylint: disable=unused-argument
        self, session_id: str, kept_messages: list[Any]
    ) -> None:
        """Discard the LangGraph checkpointer state for a session.

        Called by ``ChatManager`` when the user edits or resends a message
        in the middle of a thread.  The next ``prompt`` call will rebuild
        the agent state from the surviving messages — but LangGraph's
        checkpointer keeps appending, so the cleanest fix is to forget
        the prior state entirely for this thread.

        Parameters
        ----------
        session_id : str
            ChatManager session id (also used as the LangGraph thread_id).
        kept_messages : list
            Messages that survive in the UI; passed for callers that may
            want to seed an alternate store.  This implementation only
            uses the session_id.
        """
        thread_id = self._sessions.get(session_id, session_id)
        checkpointer = self._checkpointer
        if checkpointer is None:
            return
        # The langgraph BaseCheckpointSaver exposes ``delete_thread`` on
        # newer releases; fall back to writing an empty state otherwise.
        try:
            delete_thread = getattr(checkpointer, "delete_thread", None)
            if callable(delete_thread):
                delete_thread(thread_id)  # pylint: disable=not-callable
                return
        except Exception:
            logger.debug("checkpointer.delete_thread failed", exc_info=True)
        try:
            adelete = getattr(checkpointer, "adelete_thread", None)
            if callable(adelete):
                import asyncio as _asyncio

                try:
                    _asyncio.get_running_loop()
                except RuntimeError:
                    _asyncio.run(adelete(thread_id))  # pylint: disable=not-callable
                else:
                    # A loop is already running — schedule the coroutine
                    # on a dedicated thread to avoid reentrancy.
                    import concurrent.futures

                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                        pool.submit(
                            lambda: _asyncio.run(adelete(thread_id))  # pylint: disable=not-callable
                        ).result()
                return
        except Exception:
            logger.debug("checkpointer.adelete_thread failed", exc_info=True)
        # Last-resort fallback: clear any in-memory dict the saver keeps.
        for attr in ("storage", "_storage", "memory"):
            store = getattr(checkpointer, attr, None)
            if isinstance(store, dict):
                store.pop(thread_id, None)
        # Force a fresh thread by remapping the session to a new id so
        # subsequent prompts run against an empty graph state.
        self._sessions[session_id] = f"{thread_id}:{uuid.uuid4().hex[:8]}"
