"""Tests for pywry.commands package."""

from __future__ import annotations

import json
import sys

from unittest.mock import MagicMock, patch

import pytest

from pywry.commands import (
    COMMAND_HANDLERS,
    EventPayload,
    OpenPayload,
    ResultPayload,
    dispatch_command,
    handle_aggrid_event,
    handle_open_file,
    handle_open_url,
    handle_plotly_event,
    handle_pywry_event,
    handle_pywry_result,
    handle_window_close,
    register_commands,
    send_event_to_parent,
    serialize_response,
)


@pytest.fixture(autouse=True)
def _clear_callbacks():
    from pywry.callbacks import get_registry

    get_registry().clear()
    yield
    get_registry().clear()


class TestPayloadModels:
    def test_event_payload(self):
        p = EventPayload(label="w", event_type="evt:x", data={"k": 1})
        assert p.label == "w"
        assert p.event_type == "evt:x"
        assert p.data == {"k": 1}

    def test_result_payload(self):
        p = ResultPayload(data={"a": 1}, window_label="w")
        assert p.data == {"a": 1}
        assert p.window_label == "w"

    def test_open_payload(self):
        p = OpenPayload(target="https://example.com")
        assert p.target == "https://example.com"


class TestHandlePywryResult:
    def test_returns_success(self, capsys):
        result = handle_pywry_result("w", {"value": 42})
        assert result == {"success": True}
        # Should write JSON event to stdout
        out = capsys.readouterr().out
        assert "pywry:result" in out
        assert '"value": 42' in out


class TestHandlePywryEvent:
    def test_returns_dispatched_status(self, capsys):
        from pywry.callbacks import get_registry

        called = []
        get_registry().register("w", "evt:x", lambda d, et, l: called.append(d))

        result = handle_pywry_event("w", {"type": "evt:x", "data": {"a": 1}})
        assert result["success"] is True
        assert result["dispatched"] >= 1
        assert called == [{"a": 1}]

    def test_no_callbacks_dispatched_zero(self):
        result = handle_pywry_event("w", {"type": "no:event", "data": {}})
        assert result["dispatched"] == 0

    def test_missing_type_defaults_to_empty(self):
        result = handle_pywry_event("w", {})
        assert result["success"] is True


class TestHandlePlotlyEvent:
    def test_dispatches_namespaced_event(self):
        from pywry.callbacks import get_registry

        seen = []
        get_registry().register("w", "plotly:click", lambda d, et, l: seen.append(d))
        result = handle_plotly_event("w", {"plotly_event": "click", "data": {"x": 1}})
        assert result["success"] is True
        assert seen == [{"x": 1}]

    def test_default_event_is_click(self):
        result = handle_plotly_event("w", {"data": {}})
        assert result["success"] is True


class TestHandleAggridEvent:
    def test_dispatches_namespaced_event(self):
        from pywry.callbacks import get_registry

        seen = []
        get_registry().register("w", "aggrid:selection", lambda d, et, l: seen.append(d))
        result = handle_aggrid_event("w", {"grid_event": "selection", "data": {"row": 1}})
        assert result["success"] is True
        assert seen == [{"row": 1}]

    def test_default_event_is_selection(self):
        result = handle_aggrid_event("w", {"data": {}})
        assert result["success"] is True


class TestHandleWindowClose:
    def test_destroys_callbacks_and_dispatches_close(self):
        from pywry.callbacks import get_registry

        registry = get_registry()
        seen = []
        registry.register("w", "pywry:close", lambda d, et, l: seen.append(d))
        registry.register("w", "evt:other", lambda d, et, l: seen.append(("other", d)))

        result = handle_window_close("w")
        assert result["success"] is True
        # close was dispatched
        assert any("label" in s for s in seen if isinstance(s, dict))
        # registry destroyed
        assert "w" not in registry._callbacks

    def test_handles_lifecycle_callback_failure(self):
        from pywry.window_manager import get_lifecycle

        lifecycle = get_lifecycle()
        resources = lifecycle.register_window("w-fail")

        def _fail(label, reason):
            raise RuntimeError("oops")

        resources.on_close.append(_fail)

        # Should not raise even if on_close callback fails
        result = handle_window_close("w-fail")
        assert result["success"] is True


class TestHandleOpenFile:
    def test_missing_file_returns_error(self):
        result = handle_open_file("/nonexistent/path/abc.xyz")
        assert result["success"] is False
        assert "error" in result

    def test_existing_file_opens(self, tmp_path, monkeypatch):
        f = tmp_path / "test.txt"
        f.write_text("hi")

        if sys.platform == "win32":
            with patch("os.startfile") as mock_start:
                mock_start.return_value = None
                result = handle_open_file(str(f))
            assert result["success"] is True
        elif sys.platform == "darwin":
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                result = handle_open_file(str(f))
            assert result["success"] is True
        else:
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                result = handle_open_file(str(f))
            assert result["success"] is True

    def test_subprocess_error(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hi")
        if sys.platform == "win32":
            with patch("os.startfile", side_effect=OSError("denied")):
                result = handle_open_file(str(f))
        else:
            import subprocess

            with patch(
                "subprocess.run",
                side_effect=subprocess.SubprocessError("denied"),
            ):
                result = handle_open_file(str(f))
        assert result["success"] is False


class TestHandleOpenUrl:
    def test_opens_url(self):
        with patch("webbrowser.open") as mock_open:
            mock_open.return_value = True
            result = handle_open_url("https://example.com")
        assert result["success"] is True

    def test_open_url_error(self):
        with patch("webbrowser.open", side_effect=OSError("no browser")):
            result = handle_open_url("https://x")
        assert result["success"] is False


class TestSendEventToParent:
    def test_writes_json_to_stdout(self, capsys):
        send_event_to_parent("w", "evt:x", {"k": "v"})
        out = capsys.readouterr().out
        assert "evt:x" in out
        # Make sure it's parseable JSON
        msg = json.loads(out.strip())
        assert msg["type"] == "event"
        assert msg["label"] == "w"
        assert msg["event_type"] == "evt:x"

    def test_handles_stdout_failure(self):
        # Patch stdout.write to raise — should not propagate
        with patch.object(sys.stdout, "write", side_effect=OSError("closed")):
            send_event_to_parent("w", "x:y", {})


class TestDispatchCommand:
    def test_unknown_command_returns_error(self):
        result = dispatch_command("not_a_command", {})
        assert result["success"] is False
        assert "Unknown command" in result["error"]

    def test_open_file_command(self, tmp_path):
        f = tmp_path / "exists.txt"
        f.write_text("data")

        if sys.platform == "win32":
            with patch("os.startfile") as mock_start:
                mock_start.return_value = None
                result = dispatch_command("open_file", {"path": str(f)})
        else:
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                result = dispatch_command("open_file", {"path": str(f)})
        assert result["success"] is True

    def test_open_url_command(self):
        with patch("pywry.commands.handle_open_url") as mock_open:
            mock_open.return_value = {"success": True}
            result = dispatch_command("open_url", {"url": "https://x"})
        assert result["success"] is True

    def test_window_close_command(self):
        result = dispatch_command("window_close", {"label": "w"})
        assert result["success"] is True

    def test_pywry_event_command(self):
        result = dispatch_command(
            "pywry_event", {"label": "w", "data": {"type": "evt:x", "data": {}}}
        )
        assert result["success"] is True

    def test_handler_exception_caught(self):
        # COMMAND_HANDLERS holds direct refs at module load — patch the dict.
        def boom(*_args, **_kw):
            raise ValueError("bad")

        original = COMMAND_HANDLERS["pywry_event"]
        COMMAND_HANDLERS["pywry_event"] = boom
        try:
            result = dispatch_command("pywry_event", {"label": "w", "data": {}})
        finally:
            COMMAND_HANDLERS["pywry_event"] = original
        assert result["success"] is False


class TestSerializeResponse:
    def test_serializes_dict_to_json(self):
        s = serialize_response({"success": True, "value": 42})
        # Re-parse and verify
        d = json.loads(s)
        assert d["success"] is True
        assert d["value"] == 42


class TestRegisterCommands:
    def test_registers_with_commands_object(self):
        commands = MagicMock()
        # commands.command() returns a decorator
        decorator = MagicMock()
        decorator.side_effect = lambda fn: fn
        commands.command.return_value = decorator

        register_commands(commands)
        # Should have called .command() at least 4 times for the 4 endpoints
        assert commands.command.call_count >= 4


class TestCommandHandlersMap:
    def test_all_expected_handlers(self):
        keys = set(COMMAND_HANDLERS.keys())
        assert "pywry_result" in keys
        assert "pywry_event" in keys
        assert "plotly_event" in keys
        assert "aggrid_event" in keys
        assert "window_close" in keys
        assert "open_file" in keys
        assert "open_url" in keys


class TestRegisterCommandsAsyncWrappers:
    """Exercise the @commands.command decorated async wrappers in register_commands.

    The decorator is captured so we can call the wrappers directly to cover their
    bodies (the try/except blocks around handle_* delegations).
    """

    def test_command_wrappers_invoke_handlers(self):
        captured = []

        class _CommandsStub:
            def command(self_inner):
                def deco(fn):
                    captured.append(fn)
                    return fn

                return deco

        register_commands(_CommandsStub())
        # Should have captured the four async commands
        assert len(captured) == 4

        import asyncio

        # pywry_event success
        body = EventPayload(label="w", event_type="evt:y", data={"a": 1})
        result = asyncio.run(captured[0](body))
        assert result["success"] is True

        # pywry_event error path
        with (
            patch("pywry.commands.handle_pywry_event", side_effect=RuntimeError("x")),
            pytest.raises(RuntimeError),
        ):
            asyncio.run(captured[0](body))

        # pywry_result
        rp = ResultPayload(data={"x": 1}, window_label="w")
        result = asyncio.run(captured[1](rp))
        assert result["success"] is True

        # pywry_open_file (returns success/failure dict)
        op = OpenPayload(target="/nonexistent/abc")
        result = asyncio.run(captured[2](op))
        assert "success" in result

        # pywry_open_url
        with patch("webbrowser.open", return_value=True):
            result = asyncio.run(captured[3](OpenPayload(target="https://x")))
        assert result["success"] is True


class TestPlatformSpecificOpenFile:
    """Cover the darwin and linux branches of handle_open_file."""

    def test_darwin_branch(self, tmp_path):
        f = tmp_path / "x.txt"
        f.write_text("data")

        with patch("pywry.commands.sys") as mock_sys:
            mock_sys.platform = "darwin"
            with patch("pywry.commands.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                result = handle_open_file(str(f))
        assert result["success"] is True

    def test_linux_branch(self, tmp_path):
        f = tmp_path / "x.txt"
        f.write_text("data")

        with patch("pywry.commands.sys") as mock_sys:
            mock_sys.platform = "linux"
            with patch("pywry.commands.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                result = handle_open_file(str(f))
        assert result["success"] is True


class TestWindowCloseLifecycleException:
    def test_lifecycle_lookup_failure_swallowed(self):
        # If get_lifecycle itself raises, the except branch logs but proceeds.
        with patch(
            "pywry.window_manager.lifecycle.get_lifecycle",
            side_effect=RuntimeError("no lifecycle"),
        ):
            result = handle_window_close("any-label")
        assert result["success"] is True


def test_window_commands_module_passthroughs():
    """Cover window_commands.py thin passthroughs."""
    from pywry.commands import window_commands as wc

    with patch("pywry.commands.window_commands.handle_window_close") as m:
        m.return_value = {"success": True}
        assert wc.on_window_close("w") == {"success": True}

    with patch("pywry.commands.window_commands.handle_pywry_result") as m:
        m.return_value = {"success": True}
        assert wc.on_pywry_result("w", {"d": 1}) == {"success": True}

    with patch("pywry.commands.window_commands.handle_pywry_event") as m:
        m.return_value = {"success": True}
        assert wc.on_pywry_event("w", {"type": "evt:x"}) == {"success": True}

    with patch("pywry.commands.window_commands.handle_plotly_event") as m:
        m.return_value = {"success": True}
        assert wc.on_plotly_event("w", {}) == {"success": True}

    with patch("pywry.commands.window_commands.handle_aggrid_event") as m:
        m.return_value = {"success": True}
        assert wc.on_aggrid_event("w", {}) == {"success": True}

    with patch("pywry.commands.window_commands.handle_open_file") as m:
        m.return_value = {"success": True}
        assert wc.on_open_file("/x") == {"success": True}

    with patch("pywry.commands.window_commands.handle_open_url") as m:
        m.return_value = {"success": True}
        assert wc.on_open_url("https://x") == {"success": True}
