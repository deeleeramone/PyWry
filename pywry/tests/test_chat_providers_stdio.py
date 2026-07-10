"""Tests for the stdio ACP provider.

The provider speaks JSON-RPC 2.0 over a subprocess's stdin/stdout. To
exercise it without spawning a real binary, we mock
``asyncio.create_subprocess_exec`` and feed scripted byte streams in /
collect them out.

Coverage target: ``pywry/chat/providers/stdio.py``.
"""

from __future__ import annotations

import asyncio
import contextlib
import json

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pywry.chat.models import TextPart
from pywry.chat.providers.stdio import StdioProvider
from pywry.chat.session import ClientCapabilities


# =============================================================================
# Fake subprocess infrastructure
# =============================================================================


class _FakeStream:
    """An async-iterable byte-line stream backed by a deque-like list of bytes."""

    def __init__(self, lines: list[bytes] | None = None):
        # Pending lines yet to be emitted by the iterator
        self._lines: list[bytes] = list(lines or [])
        self._closed = False
        # Allow late-pushing lines so tests can interleave with await calls
        self._cond = asyncio.Condition()

    async def push(self, line: bytes) -> None:
        async with self._cond:
            self._lines.append(line)
            self._cond.notify_all()

    async def close(self) -> None:
        async with self._cond:
            self._closed = True
            self._cond.notify_all()

    def __aiter__(self):
        return self

    async def __anext__(self):
        async with self._cond:
            while not self._lines and not self._closed:
                await self._cond.wait()
            if self._lines:
                return self._lines.pop(0)
            raise StopAsyncIteration


class _FakeStdin:
    """Captures bytes written to it for assertions."""

    def __init__(self):
        self._writes: list[bytes] = []
        self.drained = 0

    def write(self, data: bytes) -> None:
        self._writes.append(data)

    async def drain(self) -> None:
        self.drained += 1

    @property
    def lines(self) -> list[dict[str, Any]]:
        """Decode written lines as JSON-RPC messages."""
        out: list[dict[str, Any]] = []
        for raw in self._writes:
            for line in raw.decode().splitlines():
                line = line.strip()
                if line:
                    out.append(json.loads(line))
        return out


class _FakeProcess:
    """Stand-in for asyncio.subprocess.Process."""

    def __init__(self, *, stdout=None, stdin=None, stderr=None, returncode=None):
        self.stdout = stdout
        self.stdin = stdin
        self.stderr = stderr
        self.returncode = returncode
        self.terminated = False
        self.waited = False

    def terminate(self):
        self.terminated = True

    async def wait(self):
        self.waited = True
        return self.returncode


def _patch_subprocess(proc: _FakeProcess, monkeypatch):
    """Patch asyncio.create_subprocess_exec to yield ``proc``."""

    async def _fake_create(*args, **kwargs):
        return proc

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_create)


# =============================================================================
# Static helper tests
# =============================================================================


class TestStaticHelpers:
    def test_serialize_content_blocks_with_pydantic_model(self):
        blocks = [TextPart(text="hello")]
        out = StdioProvider._serialize_content_blocks(blocks)
        assert out == [{"type": "text", "text": "hello", "annotations": None}]

    def test_serialize_content_blocks_with_raw_dict(self):
        out = StdioProvider._serialize_content_blocks([{"type": "text", "text": "raw"}])
        assert out == [{"type": "text", "text": "raw"}]

    def test_serialize_content_blocks_skips_unknown(self):
        out = StdioProvider._serialize_content_blocks([42, None, "ignored"])
        assert out == []

    def test_update_type_map_keys(self):
        m = StdioProvider._update_type_map()
        # All ACP discriminators are present
        for key in (
            "agent_message",
            "tool_call",
            "plan",
            "available_commands",
            "config_option",
            "current_mode",
            "permission_request",
            "x_status",
            "x_thinking",
        ):
            assert key in m

    def test_parse_update_unknown_type_returns_none(self):
        m = StdioProvider._update_type_map()
        assert StdioProvider._parse_update({"sessionUpdate": "no_such"}, m) is None

    def test_parse_update_strips_session_id(self):
        m = StdioProvider._update_type_map()
        result = StdioProvider._parse_update(
            {"sessionUpdate": "agent_message", "text": "hi", "sessionId": "X"}, m
        )
        assert result is not None
        assert result.text == "hi"

    def test_parse_update_renames_request_id_underscore(self):
        m = StdioProvider._update_type_map()
        result = StdioProvider._parse_update(
            {
                "sessionUpdate": "permission_request",
                "toolCallId": "tc1",
                "title": "permit?",
                "options": [],
                "_request_id": "req-7",
            },
            m,
        )
        assert result is not None
        assert result.request_id == "req-7"


# =============================================================================
# Constructor / state tests
# =============================================================================


class TestStdioProviderConstruction:
    def test_default_state(self):
        provider = StdioProvider(command="claude")
        assert provider._command == "claude"
        assert provider._args == []
        assert provider._env is None
        assert provider._process is None
        assert provider._pending == {}
        assert provider._update_queues == {}

    def test_with_args_and_env(self):
        provider = StdioProvider(command="x", args=["a", "b"], env={"K": "V"})
        assert provider._args == ["a", "b"]
        assert provider._env == {"K": "V"}


# =============================================================================
# Request/notification round-trip tests
# =============================================================================


class TestSendRequest:
    async def test_initialize_round_trip(self, monkeypatch):
        stdout = _FakeStream()
        stdin = _FakeStdin()
        stderr = _FakeStream()
        proc = _FakeProcess(stdout=stdout, stdin=stdin, stderr=stderr)
        _patch_subprocess(proc, monkeypatch)

        provider = StdioProvider(command="x", args=["--y"], env={"PATH": "/"})

        # Start initialize() concurrently
        init_task = asyncio.create_task(provider.initialize(ClientCapabilities()))

        # Wait for the request to be written
        for _ in range(50):
            if stdin.lines:
                break
            await asyncio.sleep(0.01)
        assert stdin.lines, "initialize request not written"
        req = stdin.lines[0]
        assert req["method"] == "initialize"
        assert req["params"]["protocolVersion"] == 1
        req_id = req["id"]

        # Reply via the fake stdout stream
        await stdout.push(
            (
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {"agentCapabilities": {"loadSession": True}},
                    }
                )
                + "\n"
            ).encode()
        )

        caps = await asyncio.wait_for(init_task, timeout=2.0)
        assert caps.load_session is True

        # Cleanup
        await stdout.close()
        await stderr.close()
        with contextlib.suppress(Exception):
            await asyncio.wait_for(provider.close(), timeout=1.0)

    async def test_send_notification_writes_to_stdin(self, monkeypatch):
        stdout = _FakeStream()
        stdin = _FakeStdin()
        stderr = _FakeStream()
        proc = _FakeProcess(stdout=stdout, stdin=stdin, stderr=stderr)
        _patch_subprocess(proc, monkeypatch)

        provider = StdioProvider(command="x")
        await provider._send_notification("session/cancel", {"sessionId": "S"})

        # Wait for write
        await asyncio.sleep(0.02)
        msgs = stdin.lines
        assert msgs
        last = msgs[-1]
        assert last["method"] == "session/cancel"
        assert last["params"] == {"sessionId": "S"}
        assert "id" not in last

        await stdout.close()
        await stderr.close()
        with contextlib.suppress(Exception):
            await provider.close()

    async def test_response_with_error_raises_runtime_error(self, monkeypatch):
        stdout = _FakeStream()
        stdin = _FakeStdin()
        stderr = _FakeStream()
        proc = _FakeProcess(stdout=stdout, stdin=stdin, stderr=stderr)
        _patch_subprocess(proc, monkeypatch)

        provider = StdioProvider(command="x")
        task = asyncio.create_task(provider._send_request("foo", {}))

        for _ in range(50):
            if stdin.lines:
                break
            await asyncio.sleep(0.01)
        req_id = stdin.lines[0]["id"]
        await stdout.push(
            (
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"message": "bad", "code": -1},
                    }
                )
                + "\n"
            ).encode()
        )
        with pytest.raises(RuntimeError, match="bad"):
            await asyncio.wait_for(task, timeout=2.0)

        await stdout.close()
        await stderr.close()
        with contextlib.suppress(Exception):
            await provider.close()

    async def test_send_request_raises_when_stdin_is_none(self, monkeypatch):
        proc = _FakeProcess(stdout=_FakeStream(), stdin=None, stderr=_FakeStream())
        _patch_subprocess(proc, monkeypatch)
        provider = StdioProvider(command="x")
        with pytest.raises(RuntimeError, match="no stdin"):
            await provider._send_request("foo")

    async def test_send_notification_raises_when_stdin_is_none(self, monkeypatch):
        proc = _FakeProcess(stdout=_FakeStream(), stdin=None, stderr=_FakeStream())
        _patch_subprocess(proc, monkeypatch)
        provider = StdioProvider(command="x")
        with pytest.raises(RuntimeError, match="no stdin"):
            await provider._send_notification("foo")


# =============================================================================
# Read loop / dispatch
# =============================================================================


class TestReadLoopDispatch:
    async def test_drain_stderr_consumes_lines(self, monkeypatch):
        stderr = _FakeStream(
            [
                b"  DEBUG: agent says hi  \n",
                b"\n",  # blank line ignored
                b"more output\n",
            ]
        )
        proc = _FakeProcess(stdout=_FakeStream(), stdin=_FakeStdin(), stderr=stderr)
        _patch_subprocess(proc, monkeypatch)

        provider = StdioProvider(command="x")
        await provider._ensure_started()
        # Drain immediately by closing stderr
        await stderr.close()
        # Wait briefly for the drain task to finish processing
        await asyncio.sleep(0.05)
        with contextlib.suppress(Exception):
            await provider.close()

    async def test_drain_stderr_returns_when_no_stderr(self):
        provider = StdioProvider(command="x")
        provider._process = _FakeProcess(stderr=None)
        # Should return immediately
        await provider._drain_stderr()

    async def test_drain_stderr_returns_when_no_process(self):
        provider = StdioProvider(command="x")
        provider._process = None
        await provider._drain_stderr()

    async def test_read_loop_raises_when_no_process(self):
        provider = StdioProvider(command="x")
        provider._process = None
        with pytest.raises(RuntimeError, match="stdio read loop started"):
            await provider._read_loop()

    async def test_read_loop_handles_bad_json(self, monkeypatch):
        stdout = _FakeStream(
            [
                b"not-a-json-line\n",
                b"\n",  # empty
            ]
        )
        proc = _FakeProcess(stdout=stdout, stdin=_FakeStdin(), stderr=_FakeStream())
        _patch_subprocess(proc, monkeypatch)
        provider = StdioProvider(command="x")
        await provider._ensure_started()
        await stdout.close()
        await asyncio.sleep(0.05)
        with contextlib.suppress(Exception):
            await provider.close()

    async def test_read_loop_dispatches_response(self, monkeypatch):
        stdin = _FakeStdin()
        stdout = _FakeStream()
        stderr = _FakeStream()
        proc = _FakeProcess(stdout=stdout, stdin=stdin, stderr=stderr)
        _patch_subprocess(proc, monkeypatch)

        provider = StdioProvider(command="x")
        # Set up a pending future and feed a response
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        provider._pending["abc"] = future
        await provider._ensure_started()
        await stdout.push(
            (json.dumps({"jsonrpc": "2.0", "id": "abc", "result": {"ok": True}}) + "\n").encode()
        )
        result = await asyncio.wait_for(future, timeout=2.0)
        assert result == {"ok": True}

        await stdout.close()
        await stderr.close()
        with contextlib.suppress(Exception):
            await provider.close()

    async def test_dispatch_unsupported_method_responds_with_error(self, monkeypatch):
        stdin = _FakeStdin()
        stdout = _FakeStream()
        stderr = _FakeStream()
        proc = _FakeProcess(stdout=stdout, stdin=stdin, stderr=stderr)
        _patch_subprocess(proc, monkeypatch)

        provider = StdioProvider(command="x")
        await provider._ensure_started()

        # Agent sends a request with an unknown method
        msg = {"jsonrpc": "2.0", "id": "agent-req-1", "method": "unknown/method", "params": {}}
        await provider._handle_agent_request(msg)
        # Stdin should now carry an error response
        await asyncio.sleep(0.02)
        msgs = stdin.lines
        last = msgs[-1]
        assert last["error"]["code"] == -32601
        assert "unknown/method" in last["error"]["message"]

        await stdout.close()
        await stderr.close()
        with contextlib.suppress(Exception):
            await provider.close()

    async def test_dispatch_permission_request_routes_to_queue(self, monkeypatch):
        stdin = _FakeStdin()
        stdout = _FakeStream()
        stderr = _FakeStream()
        proc = _FakeProcess(stdout=stdout, stdin=stdin, stderr=stderr)
        _patch_subprocess(proc, monkeypatch)

        provider = StdioProvider(command="x")
        await provider._ensure_started()
        # Pre-create a queue for a known session
        provider._update_queues["S1"] = asyncio.Queue()
        msg = {
            "jsonrpc": "2.0",
            "id": "agent-req-2",
            "method": "session/request_permission",
            "params": {
                "sessionId": "S1",
                "toolCallId": "tc1",
                "title": "Allow?",
                "options": [],
            },
        }
        await provider._handle_agent_request(msg)
        update = await provider._update_queues["S1"].get()
        assert update["sessionUpdate"] == "permission_request"
        assert update["_request_id"] == "agent-req-2"

        await stdout.close()
        await stderr.close()
        with contextlib.suppress(Exception):
            await provider.close()

    async def test_handle_notification_session_update_routed(self, monkeypatch):
        stdin = _FakeStdin()
        stdout = _FakeStream()
        stderr = _FakeStream()
        proc = _FakeProcess(stdout=stdout, stdin=stdin, stderr=stderr)
        _patch_subprocess(proc, monkeypatch)

        provider = StdioProvider(command="x")
        await provider._ensure_started()
        provider._update_queues["S1"] = asyncio.Queue()
        await provider._handle_notification(
            {
                "method": "session/update",
                "params": {"sessionId": "S1", "sessionUpdate": "agent_message", "text": "hi"},
            }
        )
        msg = await provider._update_queues["S1"].get()
        assert msg["sessionUpdate"] == "agent_message"

        await stdout.close()
        await stderr.close()
        with contextlib.suppress(Exception):
            await provider.close()

    async def test_handle_notification_unknown_method_dropped(self, monkeypatch):
        proc = _FakeProcess(stdout=_FakeStream(), stdin=_FakeStdin(), stderr=_FakeStream())
        _patch_subprocess(proc, monkeypatch)
        provider = StdioProvider(command="x")
        # No queue → silently dropped
        await provider._handle_notification({"method": "session/update", "params": {}})

    async def test_handle_agent_request_raises_when_stdin_is_none(self, monkeypatch):
        # When stdin is None on reentry, the agent-request handler must raise.
        proc_no_stdin = _FakeProcess(stdout=_FakeStream(), stdin=None, stderr=_FakeStream())
        _patch_subprocess(proc_no_stdin, monkeypatch)
        provider = StdioProvider(command="x")
        provider._process = proc_no_stdin
        with pytest.raises(RuntimeError, match="no stdin"):
            await provider._handle_agent_request({"method": "X", "id": "1", "params": {}})

    async def test_fail_pending_requests_wakes_up_callers(self, monkeypatch):
        provider = StdioProvider(command="x")
        loop = asyncio.get_running_loop()
        f1 = loop.create_future()
        f2 = loop.create_future()
        provider._pending["a"] = f1
        provider._pending["b"] = f2
        # Mark one already done — it should NOT have its exception set
        f2.set_result("already-done")
        provider._fail_pending_requests(RuntimeError("dead"))
        with pytest.raises(RuntimeError, match="dead"):
            await f1
        # Already-done future stays as-is
        assert f2.result() == "already-done"
        # Pending dict was reset
        assert provider._pending == {}


# =============================================================================
# new_session / prompt
# =============================================================================


class TestNewSessionAndPrompt:
    async def test_new_session_round_trip(self, monkeypatch):
        stdout = _FakeStream()
        stdin = _FakeStdin()
        stderr = _FakeStream()
        proc = _FakeProcess(stdout=stdout, stdin=stdin, stderr=stderr)
        _patch_subprocess(proc, monkeypatch)

        provider = StdioProvider(command="x")
        task = asyncio.create_task(provider.new_session("/cwd", mcp_servers=[{"name": "fs"}]))
        for _ in range(50):
            if stdin.lines:
                break
            await asyncio.sleep(0.01)
        req = stdin.lines[0]
        assert req["method"] == "session/new"
        assert req["params"]["cwd"] == "/cwd"
        assert req["params"]["mcpServers"] == [{"name": "fs"}]
        await stdout.push(
            (
                json.dumps({"jsonrpc": "2.0", "id": req["id"], "result": {"sessionId": "AGENT-7"}})
                + "\n"
            ).encode()
        )
        sid = await asyncio.wait_for(task, timeout=2.0)
        assert sid == "AGENT-7"
        # Queue created for session
        assert "AGENT-7" in provider._update_queues

        await stdout.close()
        await stderr.close()
        with contextlib.suppress(Exception):
            await provider.close()

    async def test_prompt_creates_queue_when_missing(self, monkeypatch):
        """First prompt for an unseen session_id auto-creates the queue."""
        stdout = _FakeStream()
        stdin = _FakeStdin()
        stderr = _FakeStream()
        proc = _FakeProcess(stdout=stdout, stdin=stdin, stderr=stderr)
        _patch_subprocess(proc, monkeypatch)

        provider = StdioProvider(command="x")

        async def collect():
            updates = []
            async for u in provider.prompt("brand-new", [TextPart(text="hi")]):
                updates.append(u)
            return updates

        task = asyncio.create_task(collect())
        # Wait for prompt request to be written
        for _ in range(100):
            await asyncio.sleep(0.01)
            if any(m.get("method") == "session/prompt" for m in stdin.lines):
                break
        assert "brand-new" in provider._update_queues

        # Ack the prompt to terminate the loop
        prompt_msg = next(m for m in stdin.lines if m.get("method") == "session/prompt")
        await stdout.push(
            (
                json.dumps(
                    {"jsonrpc": "2.0", "id": prompt_msg["id"], "result": {"stopReason": "end_turn"}}
                )
                + "\n"
            ).encode()
        )
        await asyncio.wait_for(task, timeout=2.0)

        await stdout.close()
        await stderr.close()
        with contextlib.suppress(Exception):
            await provider.close()

    async def test_prompt_yields_session_updates(self, monkeypatch):
        stdout = _FakeStream()
        stdin = _FakeStdin()
        stderr = _FakeStream()
        proc = _FakeProcess(stdout=stdout, stdin=stdin, stderr=stderr)
        _patch_subprocess(proc, monkeypatch)

        provider = StdioProvider(command="x")
        # Pre-create the queue
        provider._update_queues["S1"] = asyncio.Queue()

        async def collect():
            updates = []
            async for u in provider.prompt("S1", [TextPart(text="hi")]):
                updates.append(u)
            return updates

        task = asyncio.create_task(collect())

        # Wait for prompt request
        for _ in range(100):
            await asyncio.sleep(0.01)
            if any(m.get("method") == "session/prompt" for m in stdin.lines):
                break

        # Push a session/update notification
        await stdout.push(
            (
                json.dumps(
                    {
                        "method": "session/update",
                        "params": {
                            "sessionId": "S1",
                            "sessionUpdate": "agent_message",
                            "text": "Hello!",
                        },
                    }
                )
                + "\n"
            ).encode()
        )

        # Ack the prompt
        prompt_msg = next(m for m in stdin.lines if m.get("method") == "session/prompt")
        await stdout.push(
            (
                json.dumps(
                    {"jsonrpc": "2.0", "id": prompt_msg["id"], "result": {"stopReason": "end_turn"}}
                )
                + "\n"
            ).encode()
        )
        updates = await asyncio.wait_for(task, timeout=2.0)
        assert any(u.text == "Hello!" for u in updates if hasattr(u, "text"))

        await stdout.close()
        await stderr.close()
        with contextlib.suppress(Exception):
            await provider.close()

    async def test_prompt_drains_remaining_after_done(self, monkeypatch):
        """Once the prompt future resolves, any queued updates are drained."""
        stdout = _FakeStream()
        stdin = _FakeStdin()
        stderr = _FakeStream()
        proc = _FakeProcess(stdout=stdout, stdin=stdin, stderr=stderr)
        _patch_subprocess(proc, monkeypatch)

        provider = StdioProvider(command="x")
        q = asyncio.Queue()
        provider._update_queues["S1"] = q

        async def collect():
            updates = []
            async for u in provider.prompt("S1", [TextPart(text="hi")]):
                updates.append(u)
            return updates

        task = asyncio.create_task(collect())

        # Wait for prompt request
        for _ in range(100):
            await asyncio.sleep(0.01)
            if any(m.get("method") == "session/prompt" for m in stdin.lines):
                break

        # First: queue an update and ack the prompt right after — the
        # drain-after-loop branch should pick the update up.
        await q.put(
            {
                "sessionUpdate": "agent_message",
                "text": "drained-msg",
            }
        )
        prompt_msg = next(m for m in stdin.lines if m.get("method") == "session/prompt")
        await stdout.push(
            (
                json.dumps(
                    {"jsonrpc": "2.0", "id": prompt_msg["id"], "result": {"stopReason": "end_turn"}}
                )
                + "\n"
            ).encode()
        )

        updates = await asyncio.wait_for(task, timeout=3.0)
        assert any(getattr(u, "text", "") == "drained-msg" for u in updates)

        await stdout.close()
        await stderr.close()
        with contextlib.suppress(Exception):
            await provider.close()

    async def test_prompt_cancel_event_sends_session_cancel(self, monkeypatch):
        stdout = _FakeStream()
        stdin = _FakeStdin()
        stderr = _FakeStream()
        proc = _FakeProcess(stdout=stdout, stdin=stdin, stderr=stderr)
        _patch_subprocess(proc, monkeypatch)

        provider = StdioProvider(command="x")
        provider._update_queues["S1"] = asyncio.Queue()
        cancel = asyncio.Event()

        async def collect():
            updates = []
            async for u in provider.prompt("S1", [TextPart(text="hi")], cancel_event=cancel):
                updates.append(u)
            return updates

        task = asyncio.create_task(collect())

        # Wait for prompt request to be written
        for _ in range(200):
            await asyncio.sleep(0.005)
            if any(m.get("method") == "session/prompt" for m in stdin.lines):
                break

        # Cancel — the wait_for(0.1) will time out, see the flag, and emit
        # session/cancel before breaking.
        cancel.set()

        # Ack the prompt to let the future resolve
        prompt_msg = next(m for m in stdin.lines if m.get("method") == "session/prompt")
        await asyncio.sleep(0.15)  # allow at least one wait_for cycle
        await stdout.push(
            (
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": prompt_msg["id"],
                        "result": {"stopReason": "cancelled"},
                    }
                )
                + "\n"
            ).encode()
        )
        await asyncio.wait_for(task, timeout=2.0)
        # session/cancel notification should be present
        cancel_msgs = [m for m in stdin.lines if m.get("method") == "session/cancel"]
        assert cancel_msgs

        await stdout.close()
        await stderr.close()
        with contextlib.suppress(Exception):
            await provider.close()


# =============================================================================
# cancel + close
# =============================================================================


class TestCancelAndClose:
    async def test_cancel_sends_notification(self, monkeypatch):
        stdin = _FakeStdin()
        proc = _FakeProcess(stdout=_FakeStream(), stdin=stdin, stderr=_FakeStream())
        _patch_subprocess(proc, monkeypatch)
        provider = StdioProvider(command="x")
        await provider.cancel("S1")
        await asyncio.sleep(0.02)
        msgs = stdin.lines
        assert any(
            m.get("method") == "session/cancel" and m["params"]["sessionId"] == "S1" for m in msgs
        )

    async def test_close_terminates_running_process(self, monkeypatch):
        stdout = _FakeStream()
        stdin = _FakeStdin()
        stderr = _FakeStream()
        proc = _FakeProcess(stdout=stdout, stdin=stdin, stderr=stderr, returncode=None)
        _patch_subprocess(proc, monkeypatch)
        provider = StdioProvider(command="x")
        await provider._ensure_started()
        # Cancel the read loop pre-emptively; close() should call terminate()
        await stdout.close()
        await stderr.close()
        await provider.close()
        assert proc.terminated is True
        assert proc.waited is True

    async def test_close_no_op_when_process_exited(self):
        provider = StdioProvider(command="x")
        # No process started — should not raise
        await provider.close()

    async def test_close_skips_terminate_when_returncode_set(self, monkeypatch):
        stdout = _FakeStream()
        stdin = _FakeStdin()
        stderr = _FakeStream()
        proc = _FakeProcess(stdout=stdout, stdin=stdin, stderr=stderr, returncode=0)
        _patch_subprocess(proc, monkeypatch)
        provider = StdioProvider(command="x")
        await provider._ensure_started()
        await stdout.close()
        await stderr.close()
        await provider.close()
        # Already-exited process is left alone
        assert proc.terminated is False

    async def test_ensure_started_returns_existing_running_process(self, monkeypatch):
        stdout = _FakeStream()
        stdin = _FakeStdin()
        stderr = _FakeStream()
        proc = _FakeProcess(stdout=stdout, stdin=stdin, stderr=stderr, returncode=None)
        _patch_subprocess(proc, monkeypatch)
        provider = StdioProvider(command="x")
        first = await provider._ensure_started()
        second = await provider._ensure_started()
        assert first is second
        await stdout.close()
        await stderr.close()
        with contextlib.suppress(Exception):
            await provider.close()

    async def test_settle_prompt_future_cancels_undone(self):
        provider = StdioProvider(command="x")
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        # Not done — settle should cancel it
        await provider._settle_prompt_future(future)
        assert future.cancelled()

    async def test_settle_prompt_future_done_no_op(self):
        provider = StdioProvider(command="x")
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        future.set_result("ok")
        # Done — no action other than awaiting it
        await provider._settle_prompt_future(future)
        assert future.result() == "ok"


# =============================================================================
# Read-loop dispatch via real RPC messages (covers _dispatch_rpc_message branches)
# =============================================================================


class TestReadLoopFullDispatch:
    async def test_read_loop_routes_agent_request(self, monkeypatch):
        """RPC messages with both ``id`` and ``method`` are agent->client requests."""
        stdin = _FakeStdin()
        stdout = _FakeStream()
        stderr = _FakeStream()
        proc = _FakeProcess(stdout=stdout, stdin=stdin, stderr=stderr)
        _patch_subprocess(proc, monkeypatch)

        provider = StdioProvider(command="x")
        await provider._ensure_started()
        provider._update_queues["S1"] = asyncio.Queue()

        # Push an agent-request line via stdout — the read loop dispatches
        # it to _handle_agent_request, routing it to the queue.
        await stdout.push(
            (
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": "agent-1",
                        "method": "session/request_permission",
                        "params": {
                            "sessionId": "S1",
                            "toolCallId": "tc1",
                            "title": "?",
                            "options": [],
                        },
                    }
                )
                + "\n"
            ).encode()
        )
        update = await asyncio.wait_for(provider._update_queues["S1"].get(), timeout=2.0)
        assert update["sessionUpdate"] == "permission_request"

        await stdout.close()
        await stderr.close()
        with contextlib.suppress(Exception):
            await provider.close()

    async def test_read_loop_routes_notification(self, monkeypatch):
        """RPC messages with ``method`` and no ``id`` are notifications."""
        stdin = _FakeStdin()
        stdout = _FakeStream()
        stderr = _FakeStream()
        proc = _FakeProcess(stdout=stdout, stdin=stdin, stderr=stderr)
        _patch_subprocess(proc, monkeypatch)

        provider = StdioProvider(command="x")
        await provider._ensure_started()
        provider._update_queues["S1"] = asyncio.Queue()

        await stdout.push(
            (
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "method": "session/update",
                        "params": {
                            "sessionId": "S1",
                            "sessionUpdate": "agent_message",
                            "text": "ping",
                        },
                    }
                )
                + "\n"
            ).encode()
        )
        update = await asyncio.wait_for(provider._update_queues["S1"].get(), timeout=2.0)
        assert update["sessionUpdate"] == "agent_message"

        await stdout.close()
        await stderr.close()
        with contextlib.suppress(Exception):
            await provider.close()

    async def test_read_loop_unhandled_exception_fails_pending(self, monkeypatch):
        """A non-CancelledError exception inside the read loop fails pending requests."""

        class _ExplodingStream:
            def __aiter__(self):
                return self

            async def __anext__(self):
                raise RuntimeError("stdout read failed")

        stderr = _FakeStream()
        stdin = _FakeStdin()
        proc = _FakeProcess(stdout=_ExplodingStream(), stdin=stdin, stderr=stderr)
        _patch_subprocess(proc, monkeypatch)

        provider = StdioProvider(command="x")
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        provider._pending["x"] = future
        await provider._ensure_started()
        # The reader task should fail and propagate the error to pending futures
        with pytest.raises(RuntimeError):
            await asyncio.wait_for(future, timeout=2.0)

        await stderr.close()
        with contextlib.suppress(Exception):
            await provider.close()

    async def test_prompt_drain_after_loop_yields_remaining(self, monkeypatch):
        """When the prompt future resolves with extra updates queued, they
        are yielded by the post-loop drain.

        We patch ``asyncio.ensure_future`` inside the stdio module so the
        prompt's "future" is immediately done and pre-fill the queue —
        every queued update must come out via the post-loop drain.
        """
        from pywry.chat.providers import stdio as stdio_mod

        stdin = _FakeStdin()
        proc = _FakeProcess(stdout=_FakeStream(), stdin=stdin, stderr=_FakeStream())
        _patch_subprocess(proc, monkeypatch)

        provider = StdioProvider(command="x")
        q = asyncio.Queue()
        provider._update_queues["S1"] = q
        q.put_nowait({"sessionUpdate": "agent_message", "text": "drain-1"})
        q.put_nowait({"sessionUpdate": "agent_message", "text": "drain-2"})

        loop = asyncio.get_running_loop()
        already_done = loop.create_future()
        already_done.set_result({"stopReason": "end_turn"})

        original_ensure_future = asyncio.ensure_future
        call_count = {"n": 0}

        def fake_ensure_future(coro_or_future, *args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                # Close the unused coroutine to silence the warning, then
                # return our pre-resolved future.
                if hasattr(coro_or_future, "close"):
                    coro_or_future.close()
                return already_done
            return original_ensure_future(coro_or_future, *args, **kwargs)

        monkeypatch.setattr(stdio_mod.asyncio, "ensure_future", fake_ensure_future)

        updates = []
        async for u in provider.prompt("S1", [TextPart(text="hi")]):
            updates.append(u)
        texts = [getattr(u, "text", "") for u in updates]
        assert texts == ["drain-1", "drain-2"]

        with contextlib.suppress(Exception):
            await provider.close()
