"""Deep Agents provider for the ACP session interface.

Wraps a LangChain Deep Agents ``CompiledGraph`` (the return value of
``create_deep_agent()``) to implement the ``ChatProvider`` ABC. Streams
LangGraph events and maps them to ACP ``SessionUpdate`` types.

All imports are lazy to avoid hard dependencies on ``deepagents``.
"""

from __future__ import annotations

import logging
import uuid

from typing import TYPE_CHECKING, Any

from . import ChatProvider

if TYPE_CHECKING:
    import asyncio
    from collections.abc import AsyncIterator

    from ..models import ContentBlock
    from ..session import AgentCapabilities, ClientCapabilities
    from ..updates import SessionUpdate


logger = logging.getLogger(__name__)

PYWRY_SYSTEM_PROMPT = """\
You are operating inside a PyWry chat interface — a rich desktop/notebook/browser \
UI that renders your responses in real time.

## How Your Output Renders

- **Text** streams token-by-token into the chat transcript as markdown. Use headings, \
bold, lists, code blocks, and links freely — they render with full formatting.
- **Tool calls** appear as collapsible cards showing the tool name, status \
(pending → in progress → completed/failed), and result. The user sees what you're \
doing as you do it.
- **write_todos** renders as a structured plan above the chat input with status \
icons for each entry. Use it to show your thinking process and track multi-step work.
- **Subagent delegation** (the `task` tool) shows a status indicator while the \
subagent works.

## Rich Artifacts

When you produce structured output, the UI can render it as an interactive artifact \
block instead of plain text. The following artifact types are supported:

- **Code blocks** in markdown fences render with syntax highlighting and a copy button.
- **Tables** — when you write data to a file in CSV/JSON format, the UI can render \
it as a sortable, filterable AG Grid table.
- **Charts** — Plotly figure JSON renders as an interactive chart. TradingView \
candlestick data renders as a financial chart.
- **Images** — URLs and data URIs render inline.
- **JSON** — structured data renders as a collapsible tree viewer.

Prefer structured output (tables, code blocks, JSON) over describing data in prose \
when the user asks for data, results, or analysis.

## Context & Attachments

The user may attach files or reference live dashboard widgets using @mentions. \
When attachments are present, their content is prepended to the user's message. \
Read the attached content carefully before responding — it contains the data the \
user is asking about.

## Conversation History

The full conversation history for this thread is available to you. Reference \
earlier messages when the user asks follow-up questions. Use the thread context \
to maintain continuity across multiple exchanges.

## Guidelines

- Stream your response naturally — the user sees text appear in real time.
- Use write_todos to break down complex tasks before starting work.
- Show your work: tool calls are visible, so the user can follow your reasoning.
- When producing code, use markdown fenced code blocks with the language specified.
- When asked to analyze data, produce structured output (tables, charts) not \
just descriptions.
- Be concise. The chat UI is a conversation, not a document.
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


def _map_todo_status(status: str) -> str:
    status_map = {
        "todo": "pending",
        "in_progress": "in_progress",
        "in-progress": "in_progress",
        "done": "completed",
        "completed": "completed",
    }
    return status_map.get(status, "pending")


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
        Custom tool functions.
    system_prompt : str
        System instructions for the agent.
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
        Skill file paths.
    middleware : list or None
        Deep Agents middleware callables.
    auto_checkpointer : bool
        Auto-select checkpointer based on PyWry state backend.
    auto_store : bool
        Auto-create an ``InMemoryStore`` if no ``store`` is provided.
        The store enables cross-thread memory persistence within the
        process lifetime.
    """

    def __init__(
        self,
        agent: Any = None,
        *,
        model: str = "anthropic:claude-sonnet-4-6",
        tools: list[Any] | None = None,
        system_prompt: str = "",
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
        **kwargs: Any,
    ) -> None:
        self._agent = agent
        self._model = model
        self._tools = tools or []
        self._system_prompt = system_prompt
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
                from langgraph.checkpoint.redis import RedisSaver
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

        from langgraph.checkpoint.memory import MemorySaver

        return MemorySaver()

    def _create_store(self) -> Any:
        from langgraph.store.memory import InMemoryStore

        return InMemoryStore()

    def _build_agent(self) -> Any:
        from deepagents import create_deep_agent

        combined_prompt = PYWRY_SYSTEM_PROMPT
        if self._system_prompt:
            combined_prompt = combined_prompt + "\n\n" + self._system_prompt

        kwargs: dict[str, Any] = {
            "model": self._model,
            "system_prompt": combined_prompt,
        }
        if self._tools:
            kwargs["tools"] = self._tools
        if self._checkpointer:
            kwargs["checkpointer"] = self._checkpointer
        if self._interrupt_on:
            kwargs["interrupt_on"] = self._interrupt_on
        if self._backend:
            kwargs["backend"] = self._backend
        if self._subagents:
            kwargs["subagents"] = self._subagents
        if self._skills:
            kwargs["skills"] = self._skills
        if self._middleware:
            kwargs["middleware"] = self._middleware
        if self._store:
            kwargs["store"] = self._store
        if self._memory:
            kwargs["memory"] = self._memory
        kwargs.update(self._kwargs)
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
            MCP server configs (unused).

        Returns
        -------
        str
            Session identifier.
        """
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
        from ..updates import AgentMessageUpdate, StatusUpdate, ToolCallUpdate

        thread_id = self._sessions.get(session_id, session_id)
        user_text = "".join(p.text for p in content if isinstance(p, TextPart))

        config = {"configurable": {"thread_id": thread_id}}

        async for event in self._agent.astream_events(
            {"messages": [{"role": "user", "content": user_text}]},
            config=config,
            version="v2",
        ):
            if cancel_event and cancel_event.is_set():
                return

            kind = event.get("event", "")

            if kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    yield AgentMessageUpdate(text=chunk.content)

            elif kind == "on_tool_start":
                tool_name = event.get("name", "")
                yield ToolCallUpdate(
                    tool_call_id=event.get("run_id", f"call_{uuid.uuid4().hex[:8]}"),
                    name=tool_name,
                    kind=_map_tool_kind(tool_name),
                    status="in_progress",
                )

            elif kind == "on_tool_end":
                async for update in self._handle_tool_end(event):
                    yield update

            elif kind == "on_tool_error":
                tool_name = event.get("name", "")
                yield ToolCallUpdate(
                    tool_call_id=event.get("run_id", f"call_{uuid.uuid4().hex[:8]}"),
                    name=tool_name,
                    kind=_map_tool_kind(tool_name),
                    status="failed",
                )

            elif kind == "on_chat_model_start":
                model_name = event.get("name", "")
                if model_name:
                    yield StatusUpdate(text=f"Thinking ({model_name})...")

            elif kind == "on_chain_start" and event.get("name") == "task":
                yield StatusUpdate(text="Delegating to subagent...")

    async def _handle_tool_end(self, event: dict[str, Any]) -> AsyncIterator[SessionUpdate]:
        """Handle on_tool_end events, including write_todos → PlanUpdate."""
        import json

        from ..session import PlanEntry
        from ..updates import PlanUpdate, ToolCallUpdate

        tool_name = event.get("name", "")
        run_id = event.get("run_id", "")
        output = event.get("data", {}).get("output", "")

        if tool_name == "write_todos":
            try:
                todos = json.loads(output) if isinstance(output, str) else output
                if isinstance(todos, list):
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
            except Exception:
                logger.debug("Could not parse write_todos output", exc_info=True)

        yield ToolCallUpdate(
            tool_call_id=run_id or f"call_{uuid.uuid4().hex[:8]}",
            name=tool_name,
            kind=_map_tool_kind(tool_name),
            status="completed",
        )

    async def cancel(self, session_id: str) -> None:
        """Cancel is handled cooperatively via ``cancel_event``.

        Parameters
        ----------
        session_id : str
            Session to cancel.
        """
