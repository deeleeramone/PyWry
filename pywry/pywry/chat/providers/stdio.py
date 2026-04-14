"""Stdio provider for connecting to external ACP agents.

Spawns a subprocess and speaks JSON-RPC 2.0 over stdin/stdout,
implementing the ``ChatProvider`` ABC as an ACP client.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid

from typing import Any

from . import ChatProvider


log = logging.getLogger(__name__)


class StdioProvider(ChatProvider):
    """Connect to an external ACP agent via stdio JSON-RPC 2.0.

    Parameters
    ----------
    command : str
        Executable to spawn (e.g. ``"claude"``).
    args : list[str] | None
        Command-line arguments.
    env : dict[str, str] | None
        Environment variable overrides.

    Examples
    --------
    >>> provider = StdioProvider(command="claude", args=["--agent"])
    >>> caps = await provider.initialize(ClientCapabilities())
    >>> session_id = await provider.new_session("/path/to/project")
    """

    def __init__(
        self,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self._command = command
        self._args = args or []
        self._env = env
        self._process: asyncio.subprocess.Process | None = None
        self._pending: dict[str | int, asyncio.Future[Any]] = {}
        self._reader_task: asyncio.Task[None] | None = None
        self._update_queues: dict[str, asyncio.Queue[Any]] = {}

    async def _ensure_started(self) -> asyncio.subprocess.Process:
        """Spawn the subprocess if not already running.

        Returns
        -------
        asyncio.subprocess.Process
            The running subprocess.
        """
        if self._process is not None and self._process.returncode is None:
            return self._process

        self._process = await asyncio.create_subprocess_exec(
            self._command,
            *self._args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self._env,
        )
        self._reader_task = asyncio.create_task(self._read_loop())
        return self._process

    async def _read_loop(self) -> None:
        """Read JSON-RPC messages from stdout line-by-line."""
        assert self._process is not None
        assert self._process.stdout is not None

        async for raw_line in self._process.stdout:
            stripped = raw_line.strip()
            if not stripped:
                continue
            try:
                msg = json.loads(stripped)
            except json.JSONDecodeError:
                log.warning("Non-JSON line from agent: %s", stripped[:200])
                continue

            if "id" in msg and "result" in msg:
                # Response to a request we sent
                future = self._pending.pop(msg["id"], None)
                if future and not future.done():
                    future.set_result(msg.get("result"))
            elif "id" in msg and "error" in msg:
                future = self._pending.pop(msg["id"], None)
                if future and not future.done():
                    future.set_exception(RuntimeError(msg["error"].get("message", "RPC error")))
            elif "method" in msg and "id" not in msg:
                # Notification from agent (no id = no response expected)
                await self._handle_notification(msg)
            elif "method" in msg and "id" in msg:
                # Request from agent (needs response)
                await self._handle_agent_request(msg)

    async def _send_request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        """Send a JSON-RPC request and wait for the response.

        Parameters
        ----------
        method : str
            RPC method name.
        params : dict[str, Any] | None
            Method parameters.

        Returns
        -------
        Any
            The result from the response.
        """
        proc = await self._ensure_started()
        assert proc.stdin is not None

        req_id = str(uuid.uuid4().hex[:8])
        msg = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params or {},
        }

        future: asyncio.Future[Any] = asyncio.get_event_loop().create_future()
        self._pending[req_id] = future

        proc.stdin.write((json.dumps(msg) + "\n").encode())
        await proc.stdin.drain()

        return await future

    async def _send_notification(self, method: str, params: dict[str, Any] | None = None) -> None:
        """Send a JSON-RPC notification (no response expected).

        Parameters
        ----------
        method : str
            RPC method name.
        params : dict[str, Any] | None
            Method parameters.
        """
        proc = await self._ensure_started()
        assert proc.stdin is not None

        msg = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
        }

        proc.stdin.write((json.dumps(msg) + "\n").encode())
        await proc.stdin.drain()

    async def _handle_notification(self, msg: dict[str, Any]) -> None:
        """Route agent notifications to the appropriate session queue.

        Parameters
        ----------
        msg : dict[str, Any]
            JSON-RPC notification message.
        """
        method = msg.get("method", "")
        params = msg.get("params", {})

        if method == "session/update":
            session_id = params.get("sessionId", "")
            queue = self._update_queues.get(session_id)
            if queue:
                await queue.put(params)

    async def _handle_agent_request(self, msg: dict[str, Any]) -> None:
        """Handle requests from the agent (permission, fs, terminal).

        Parameters
        ----------
        msg : dict[str, Any]
            JSON-RPC request message from the agent.
        """
        method = msg.get("method", "")
        req_id = msg.get("id")
        params = msg.get("params", {})
        proc = await self._ensure_started()
        assert proc.stdin is not None

        if method == "session/request_permission":
            # Route to session update queue as a permission request
            session_id = params.get("sessionId", "")
            queue = self._update_queues.get(session_id)
            if queue:
                await queue.put(
                    {
                        "sessionUpdate": "permission_request",
                        "toolCallId": params.get("toolCallId", ""),
                        "title": params.get("title", ""),
                        "options": params.get("options", []),
                        "_request_id": req_id,
                    }
                )
        else:
            # Unsupported method — respond with error
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not supported: {method}",
                },
            }
            proc.stdin.write((json.dumps(resp) + "\n").encode())
            await proc.stdin.drain()

    async def initialize(
        self,
        capabilities: Any,
    ) -> Any:
        """Send ``initialize`` to the agent subprocess.

        Parameters
        ----------
        capabilities : ClientCapabilities
            Client features to advertise.

        Returns
        -------
        AgentCapabilities
            Features the agent supports.
        """
        from ..session import AgentCapabilities

        result = await self._send_request(
            "initialize",
            {
                "protocolVersion": 1,
                "clientCapabilities": (
                    capabilities.model_dump() if hasattr(capabilities, "model_dump") else {}
                ),
            },
        )

        return AgentCapabilities(**(result.get("agentCapabilities", {})))

    async def new_session(
        self,
        cwd: str,
        mcp_servers: list[dict[str, Any]] | None = None,
    ) -> str:
        """Send ``session/new`` to the agent.

        Parameters
        ----------
        cwd : str
            Working directory context.
        mcp_servers : list[dict[str, Any]] | None
            MCP server configurations.

        Returns
        -------
        str
            Session identifier from the agent.
        """
        result = await self._send_request(
            "session/new",
            {
                "cwd": cwd,
                "mcpServers": mcp_servers or [],
            },
        )
        session_id = result.get("sessionId", "")
        self._update_queues[session_id] = asyncio.Queue()
        return session_id

    async def prompt(
        self,
        session_id: str,
        content: list[Any],
        cancel_event: asyncio.Event | None = None,
    ) -> Any:
        """Send ``session/prompt`` and yield session updates.

        Parameters
        ----------
        session_id : str
            Active session identifier.
        content : list[ContentBlock]
            User message content blocks.
        cancel_event : asyncio.Event | None, optional
            Cooperative cancellation signal.

        Yields
        ------
        SessionUpdate
            Typed update notifications from the agent.
        """
        from ..updates import (
            AgentMessageUpdate,
            CommandsUpdate,
            ConfigOptionUpdate,
            ModeUpdate,
            PermissionRequestUpdate,
            PlanUpdate,
            StatusUpdate,
            ThinkingUpdate,
            ToolCallUpdate,
        )

        queue = self._update_queues.get(session_id)
        if queue is None:
            queue = asyncio.Queue()
            self._update_queues[session_id] = queue

        # Serialize content blocks
        content_dicts = []
        for block in content:
            if hasattr(block, "model_dump"):
                content_dicts.append(block.model_dump())
            elif isinstance(block, dict):
                content_dicts.append(block)

        # Send the prompt — response comes when the turn completes
        prompt_future = asyncio.ensure_future(
            self._send_request(
                "session/prompt",
                {
                    "sessionId": session_id,
                    "prompt": content_dicts,
                },
            )
        )

        # Map update type strings to models
        update_map = {
            "agent_message": AgentMessageUpdate,
            "tool_call": ToolCallUpdate,
            "plan": PlanUpdate,
            "available_commands": CommandsUpdate,
            "config_option": ConfigOptionUpdate,
            "current_mode": ModeUpdate,
            "permission_request": PermissionRequestUpdate,
            "x_status": StatusUpdate,
            "x_thinking": ThinkingUpdate,
        }

        while not prompt_future.done():
            try:
                update = await asyncio.wait_for(queue.get(), timeout=0.1)
            except asyncio.TimeoutError:
                if cancel_event and cancel_event.is_set():
                    await self._send_notification(
                        "session/cancel",
                        {
                            "sessionId": session_id,
                        },
                    )
                    break
                continue

            update_type = update.get("sessionUpdate", "")
            model_cls = update_map.get(update_type)
            if model_cls:
                yield model_cls(
                    **{k: v for k, v in update.items() if k not in ("sessionId", "_request_id")}
                )

        # Drain remaining updates
        while not queue.empty():
            update = queue.get_nowait()
            update_type = update.get("sessionUpdate", "")
            model_cls = update_map.get(update_type)
            if model_cls:
                yield model_cls(
                    **{k: v for k, v in update.items() if k not in ("sessionId", "_request_id")}
                )

    async def cancel(self, session_id: str) -> None:
        """Send ``session/cancel`` notification.

        Parameters
        ----------
        session_id : str
            Session to cancel.
        """
        await self._send_notification(
            "session/cancel",
            {
                "sessionId": session_id,
            },
        )

    async def close(self) -> None:
        """Terminate the subprocess and clean up.

        Call this when done with the provider to release system resources.
        """
        if self._reader_task:
            self._reader_task.cancel()
        if self._process and self._process.returncode is None:
            self._process.terminate()
            await self._process.wait()
