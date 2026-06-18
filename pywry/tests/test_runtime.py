"""Unit tests for pywry.runtime targeting line coverage.

These tests heavily mock the pytauri subprocess so the actual subprocess
is never started.  They exercise:

* Module-level setters (set_window_mode, set_tauri_plugins, etc.)
* IPC functions: send_command, get_response, send_command_with_response
* Window-level RPC helpers: window_get, window_call
* Per-window IPC: create_window, set_content, close/show/hide, eval_js,
  inject_css/remove_css, refresh_*, emit_event(_fire)
* Reader/writer thread internals via direct invocation
* Custom command dispatch: register_custom_command, _handle_custom_command,
  _dispatch_event, _handle_content_request
* start()/stop() lifecycle (with subprocess.Popen mocked)
"""

from __future__ import annotations

import json
import threading
import time

from queue import Empty, Queue
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

import pywry.runtime as runtime_mod

from pywry.callbacks import get_registry
from pywry.window_manager import get_lifecycle


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _reset_runtime_module():
    """Reset all module-level state in pywry.runtime."""
    runtime_mod._process = None
    runtime_mod._reader_thread = None
    runtime_mod._writer_thread = None
    runtime_mod._ready_event.clear()
    runtime_mod._running = False
    runtime_mod._registry = None

    # Drain queues
    while not runtime_mod._outgoing.empty():
        try:
            runtime_mod._outgoing.get_nowait()
        except Empty:
            break
    while not runtime_mod._responses.empty():
        try:
            runtime_mod._responses.get_nowait()
        except Empty:
            break

    runtime_mod._custom_command_handlers.clear()
    runtime_mod._CUSTOM_COMMANDS = ""
    runtime_mod._ON_WINDOW_CLOSE = "hide"
    runtime_mod._WINDOW_MODE = "new"
    runtime_mod._TAURI_PLUGINS = "dialog,fs"
    runtime_mod._EXTRA_CAPABILITIES = ""

    with runtime_mod._pending_lock:
        runtime_mod._pending_requests.clear()
        runtime_mod._pending_responses.clear()


@pytest.fixture(autouse=True)
def reset_runtime():
    """Reset module-level state between tests."""
    _reset_runtime_module()
    get_registry().clear()
    get_lifecycle().clear()
    yield
    _reset_runtime_module()
    get_registry().clear()
    get_lifecycle().clear()


# ---------------------------------------------------------------------------
# is_headless
# ---------------------------------------------------------------------------


class TestIsHeadless:
    def test_returns_true_when_pywry_headless_set(self, monkeypatch):
        monkeypatch.setenv("PYWRY_HEADLESS", "1")
        assert runtime_mod.is_headless() is True

    def test_returns_true_for_truthy_values(self, monkeypatch):
        for v in ("true", "yes", "on", "TRUE"):
            monkeypatch.setenv("PYWRY_HEADLESS", v)
            assert runtime_mod.is_headless() is True

    def test_returns_false_when_unset(self, monkeypatch):
        monkeypatch.delenv("PYWRY_HEADLESS", raising=False)
        assert runtime_mod.is_headless() is False

    def test_returns_false_for_falsy_values(self, monkeypatch):
        for v in ("0", "false", "no", "off", ""):
            monkeypatch.setenv("PYWRY_HEADLESS", v)
            assert runtime_mod.is_headless() is False


# ---------------------------------------------------------------------------
# Setters
# ---------------------------------------------------------------------------


class TestSetters:
    def test_set_on_window_close_valid(self):
        runtime_mod.set_on_window_close("close")
        assert runtime_mod._ON_WINDOW_CLOSE == "close"
        runtime_mod.set_on_window_close("hide")
        assert runtime_mod._ON_WINDOW_CLOSE == "hide"

    def test_set_on_window_close_invalid_defaults_to_hide(self):
        runtime_mod.set_on_window_close("nonsense")
        assert runtime_mod._ON_WINDOW_CLOSE == "hide"

    def test_set_window_mode_valid(self):
        for mode in ("single", "multi", "new"):
            runtime_mod.set_window_mode(mode)
            assert mode == runtime_mod._WINDOW_MODE

    def test_set_window_mode_invalid_defaults_to_new(self):
        runtime_mod.set_window_mode("invalid")
        assert runtime_mod._WINDOW_MODE == "new"

    def test_set_tauri_plugins(self):
        runtime_mod.set_tauri_plugins(["dialog", "fs", "notification"])
        assert runtime_mod._TAURI_PLUGINS == "dialog,fs,notification"

    def test_set_tauri_plugins_empty(self):
        runtime_mod.set_tauri_plugins([])
        assert runtime_mod._TAURI_PLUGINS == ""

    def test_set_extra_capabilities(self):
        runtime_mod.set_extra_capabilities(["shell:allow-execute", "fs:allow-read"])
        assert runtime_mod._EXTRA_CAPABILITIES == "shell:allow-execute,fs:allow-read"

    def test_set_extra_capabilities_empty(self):
        runtime_mod.set_extra_capabilities([])
        assert runtime_mod._EXTRA_CAPABILITIES == ""


# ---------------------------------------------------------------------------
# Custom command registration
# ---------------------------------------------------------------------------


class TestRegisterCustomCommand:
    def test_register_handler(self):
        def handler(data):
            return {"ok": True}

        runtime_mod.register_custom_command("foo", handler)
        cmds = runtime_mod.get_custom_commands()
        assert cmds == {"foo": handler}
        assert runtime_mod._CUSTOM_COMMANDS == "foo"

    def test_register_multiple_handlers(self):
        runtime_mod.register_custom_command("a", lambda d: d)
        runtime_mod.register_custom_command("b", lambda d: d)
        cmds = runtime_mod.get_custom_commands()
        assert set(cmds.keys()) == {"a", "b"}
        assert "a" in runtime_mod._CUSTOM_COMMANDS
        assert "b" in runtime_mod._CUSTOM_COMMANDS

    def test_get_custom_commands_returns_copy(self):
        runtime_mod.register_custom_command("foo", lambda d: d)
        cmds = runtime_mod.get_custom_commands()
        cmds["bar"] = lambda d: d
        assert "bar" not in runtime_mod._custom_command_handlers


# ---------------------------------------------------------------------------
# get_pywry_dir / is_running / wait_ready
# ---------------------------------------------------------------------------


class TestProcessQueries:
    def test_get_pywry_dir_returns_path(self):
        from pathlib import Path

        d = runtime_mod.get_pywry_dir()
        assert isinstance(d, Path)
        assert d.is_absolute()

    def test_is_running_when_no_process(self):
        runtime_mod._process = None
        assert runtime_mod.is_running() is False

    def test_is_running_with_alive_process(self):
        proc = MagicMock()
        proc.poll.return_value = None  # None means running
        runtime_mod._process = proc
        assert runtime_mod.is_running() is True

    def test_is_running_with_dead_process(self):
        proc = MagicMock()
        proc.poll.return_value = 0  # Exit code = dead
        runtime_mod._process = proc
        assert runtime_mod.is_running() is False

    def test_wait_ready_returns_immediately_when_set(self):
        runtime_mod._ready_event.set()
        assert runtime_mod.wait_ready(timeout=0.1) is True

    def test_wait_ready_times_out(self):
        runtime_mod._ready_event.clear()
        assert runtime_mod.wait_ready(timeout=0.05) is False


# ---------------------------------------------------------------------------
# send_command / get_response
# ---------------------------------------------------------------------------


class TestSendGetCommands:
    def test_send_command_enqueues(self):
        cmd = {"action": "test", "label": "x"}
        runtime_mod.send_command(cmd)
        assert runtime_mod._outgoing.qsize() == 1
        out = runtime_mod._outgoing.get_nowait()
        assert out == cmd

    def test_get_response_from_queue(self):
        msg = {"success": True, "value": 42}
        runtime_mod._responses.put(msg)
        result = runtime_mod.get_response(timeout=0.5)
        assert result == msg

    def test_get_response_timeout_returns_none(self):
        result = runtime_mod.get_response(timeout=0.05)
        assert result is None


class TestSendCommandWithResponse:
    def test_response_is_correlated_via_request_id(self):
        # Simulate a producer that mimics the stdout reader: when a request_id
        # is registered, set its event with a response.
        cmd = {"action": "ping"}

        def producer():
            time.sleep(0.05)
            with runtime_mod._pending_lock:
                # Find the registered request_id
                if runtime_mod._pending_requests:
                    rid = next(iter(runtime_mod._pending_requests))
                    runtime_mod._pending_responses[rid] = {
                        "request_id": rid,
                        "success": True,
                        "value": "ok",
                    }
                    runtime_mod._pending_requests[rid].set()

        t = threading.Thread(target=producer, daemon=True)
        t.start()

        result = runtime_mod.send_command_with_response(cmd, timeout=2.0)
        t.join(timeout=1.0)
        assert result is not None
        assert result.get("value") == "ok"

    def test_timeout_returns_none(self):
        cmd = {"action": "ping"}
        result = runtime_mod.send_command_with_response(cmd, timeout=0.1)
        assert result is None
        # Cleanup happened
        with runtime_mod._pending_lock:
            assert len(runtime_mod._pending_requests) == 0


# ---------------------------------------------------------------------------
# window_get / window_call
# ---------------------------------------------------------------------------


class TestWindowGet:
    def test_returns_value_on_success(self):
        with patch.object(
            runtime_mod,
            "send_command_with_response",
            return_value={"success": True, "value": 42},
        ):
            assert runtime_mod.window_get("main", "size") == 42

    def test_raises_timeout_error_on_timeout(self):
        from pywry.exceptions import IPCTimeoutError

        with (
            patch.object(
                runtime_mod,
                "send_command_with_response",
                return_value=None,
            ),
            pytest.raises(IPCTimeoutError),
        ):
            runtime_mod.window_get("main", "size")

    def test_raises_property_error_on_failure(self):
        from pywry.exceptions import PropertyError

        with (
            patch.object(
                runtime_mod,
                "send_command_with_response",
                return_value={"success": False, "error": "missing"},
            ),
            pytest.raises(PropertyError),
        ):
            runtime_mod.window_get("main", "size")

    def test_passes_args(self):
        captured = {}

        def fake_send(cmd, timeout):
            captured["cmd"] = cmd
            return {"success": True, "value": 1}

        with patch.object(runtime_mod, "send_command_with_response", side_effect=fake_send):
            runtime_mod.window_get("main", "monitor", args={"x": 10})
        assert captured["cmd"]["args"] == {"x": 10}


class TestWindowCall:
    def test_fire_and_forget_default(self):
        with patch.object(runtime_mod, "send_command") as mock_send:
            result = runtime_mod.window_call("main", "set_title", args={"title": "hi"})
            assert result is None
            mock_send.assert_called_once()
            sent = mock_send.call_args.args[0]
            assert sent["action"] == "window_call"
            assert sent["method"] == "set_title"
            assert sent["args"] == {"title": "hi"}

    def test_with_response_success(self):
        with patch.object(
            runtime_mod,
            "send_command_with_response",
            return_value={"success": True, "result": 99},
        ):
            assert runtime_mod.window_call("main", "ping", expect_response=True) == 99

    def test_with_response_timeout(self):
        from pywry.exceptions import IPCTimeoutError

        with (
            patch.object(
                runtime_mod,
                "send_command_with_response",
                return_value=None,
            ),
            pytest.raises(IPCTimeoutError),
        ):
            runtime_mod.window_call("main", "ping", expect_response=True)

    def test_with_response_failure(self):
        from pywry.exceptions import WindowError

        with (
            patch.object(
                runtime_mod,
                "send_command_with_response",
                return_value={"success": False, "error": "boom"},
            ),
            pytest.raises(WindowError),
        ):
            runtime_mod.window_call("main", "ping", expect_response=True)

    def test_no_args(self):
        with patch.object(runtime_mod, "send_command") as mock_send:
            runtime_mod.window_call("main", "foo")
            sent = mock_send.call_args.args[0]
            assert sent["args"] == {}


# ---------------------------------------------------------------------------
# create_window, set_content, close/show/hide
# ---------------------------------------------------------------------------


class TestCreateWindow:
    def test_success(self):
        with (
            patch.object(runtime_mod, "send_command") as mock_send,
            patch.object(runtime_mod, "get_response", return_value={"success": True}),
        ):
            assert runtime_mod.create_window("main", title="X", width=100, height=200) is True
            sent = mock_send.call_args.args[0]
            assert sent["label"] == "main"
            assert sent["width"] == 100

    def test_with_builder_opts(self):
        with (
            patch.object(runtime_mod, "send_command") as mock_send,
            patch.object(runtime_mod, "get_response", return_value={"success": True}),
        ):
            runtime_mod.create_window("main", resizable=False, transparent=True)
            sent = mock_send.call_args.args[0]
            assert sent["builder_opts"] == {"resizable": False, "transparent": True}

    def test_failure_no_response(self):
        with (
            patch.object(runtime_mod, "send_command"),
            patch.object(runtime_mod, "get_response", return_value=None),
        ):
            assert runtime_mod.create_window("main") is False

    def test_failure_unsuccessful(self):
        with (
            patch.object(runtime_mod, "send_command"),
            patch.object(runtime_mod, "get_response", return_value={"success": False}),
        ):
            assert runtime_mod.create_window("main") is False


class TestSetContent:
    def test_success(self):
        with (
            patch.object(runtime_mod, "send_command") as mock_send,
            patch.object(runtime_mod, "get_response", return_value={"success": True}),
        ):
            assert runtime_mod.set_content("main", "<p>hi</p>", "dark") is True
            sent = mock_send.call_args.args[0]
            assert sent["html"] == "<p>hi</p>"
            assert sent["theme"] == "dark"

    def test_failure(self):
        with (
            patch.object(runtime_mod, "send_command"),
            patch.object(runtime_mod, "get_response", return_value=None),
        ):
            assert runtime_mod.set_content("main", "x") is False


class TestCheckWindowOpen:
    def test_open(self):
        with (
            patch.object(runtime_mod, "send_command"),
            patch.object(runtime_mod, "get_response", return_value={"is_open": True}),
        ):
            assert runtime_mod.check_window_open("main") is True

    def test_not_open(self):
        with (
            patch.object(runtime_mod, "send_command"),
            patch.object(runtime_mod, "get_response", return_value={"is_open": False}),
        ):
            assert runtime_mod.check_window_open("main") is False

    def test_no_response(self):
        with (
            patch.object(runtime_mod, "send_command"),
            patch.object(runtime_mod, "get_response", return_value=None),
        ):
            assert runtime_mod.check_window_open("main") is False


class TestCloseWindow:
    def test_success(self):
        with (
            patch.object(runtime_mod, "send_command"),
            patch.object(runtime_mod, "get_response", return_value={"success": True}),
        ):
            assert runtime_mod.close_window("main") is True

    def test_no_response(self):
        with (
            patch.object(runtime_mod, "send_command"),
            patch.object(runtime_mod, "get_response", return_value=None),
        ):
            assert runtime_mod.close_window("main") is False


class TestShowHideWindow:
    def test_show_window(self):
        with (
            patch.object(runtime_mod, "send_command") as mock_send,
            patch.object(runtime_mod, "get_response", return_value={"success": True}),
        ):
            assert runtime_mod.show_window("main") is True
            assert mock_send.call_args.args[0]["action"] == "show"

    def test_show_window_failure(self):
        with (
            patch.object(runtime_mod, "send_command"),
            patch.object(runtime_mod, "get_response", return_value=None),
        ):
            assert runtime_mod.show_window("main") is False

    def test_hide_window(self):
        with (
            patch.object(runtime_mod, "send_command") as mock_send,
            patch.object(runtime_mod, "get_response", return_value={"success": True}),
        ):
            assert runtime_mod.hide_window("main") is True
            assert mock_send.call_args.args[0]["action"] == "hide"

    def test_hide_window_failure(self):
        with (
            patch.object(runtime_mod, "send_command"),
            patch.object(runtime_mod, "get_response", return_value=None),
        ):
            assert runtime_mod.hide_window("main") is False


# ---------------------------------------------------------------------------
# inject_css / remove_css / refresh_window / refresh_all_windows / emit
# ---------------------------------------------------------------------------


class TestCssAndRefresh:
    def test_inject_css_success(self):
        with (
            patch.object(runtime_mod, "send_command") as mock_send,
            patch.object(runtime_mod, "get_response", return_value={"success": True}),
        ):
            assert runtime_mod.inject_css("main", "body{}", "css1") is True
            sent = mock_send.call_args.args[0]
            assert sent["event"] == "pywry:inject-css"
            assert sent["payload"]["id"] == "css1"

    def test_inject_css_failure(self):
        with (
            patch.object(runtime_mod, "send_command"),
            patch.object(runtime_mod, "get_response", return_value=None),
        ):
            assert runtime_mod.inject_css("main", "body{}", "css1") is False

    def test_remove_css_success(self):
        with (
            patch.object(runtime_mod, "send_command") as mock_send,
            patch.object(runtime_mod, "get_response", return_value={"success": True}),
        ):
            assert runtime_mod.remove_css("main", "css1") is True
            sent = mock_send.call_args.args[0]
            assert sent["event"] == "pywry:remove-css"

    def test_remove_css_failure(self):
        with (
            patch.object(runtime_mod, "send_command"),
            patch.object(runtime_mod, "get_response", return_value=None),
        ):
            assert runtime_mod.remove_css("main", "css1") is False

    def test_refresh_window_no_lifecycle_entry(self):
        # No window in lifecycle -> returns False
        assert runtime_mod.refresh_window("nonexistent") is False

    def test_refresh_window_destroyed(self):
        from pywry.window_manager import WindowResources

        lifecycle = get_lifecycle()
        res = WindowResources(label="main")
        res.is_destroyed = True
        lifecycle._windows["main"] = res
        assert runtime_mod.refresh_window("main") is False

    def test_refresh_window_no_html(self):
        from pywry.window_manager import WindowResources

        lifecycle = get_lifecycle()
        res = WindowResources(label="main")
        res.html_content = None
        lifecycle._windows["main"] = res
        assert runtime_mod.refresh_window("main") is False

    def test_refresh_window_with_content(self):
        from pywry.models import ThemeMode, WindowConfig
        from pywry.window_manager import WindowResources

        lifecycle = get_lifecycle()
        res = WindowResources(label="main")
        res.html_content = "<p>hello</p>"
        res.last_config = WindowConfig(theme=ThemeMode.LIGHT)
        lifecycle._windows["main"] = res

        with patch.object(runtime_mod, "set_content", return_value=True) as mock_set:
            assert runtime_mod.refresh_window("main") is True
            mock_set.assert_called_once_with("main", "<p>hello</p>", "light")

    def test_refresh_all_windows_success(self):
        with (
            patch.object(runtime_mod, "send_command") as mock_send,
            patch.object(runtime_mod, "get_response", return_value={"success": True}),
        ):
            assert runtime_mod.refresh_all_windows() is True
            sent = mock_send.call_args.args[0]
            assert sent["label"] == "*"
            assert sent["event"] == "pywry:refresh"

    def test_refresh_all_windows_failure(self):
        with (
            patch.object(runtime_mod, "send_command"),
            patch.object(runtime_mod, "get_response", return_value=None),
        ):
            assert runtime_mod.refresh_all_windows() is False

    def test_emit_event_success(self):
        with (
            patch.object(runtime_mod, "send_command") as mock_send,
            patch.object(runtime_mod, "get_response", return_value={"success": True}),
        ):
            assert runtime_mod.emit_event("main", "foo:bar", {"x": 1}) is True
            sent = mock_send.call_args.args[0]
            assert sent["event"] == "foo:bar"
            assert sent["payload"] == {"x": 1}

    def test_emit_event_default_payload(self):
        with (
            patch.object(runtime_mod, "send_command") as mock_send,
            patch.object(runtime_mod, "get_response", return_value={"success": True}),
        ):
            runtime_mod.emit_event("main", "foo:bar")
            sent = mock_send.call_args.args[0]
            assert sent["payload"] == {}

    def test_emit_event_failure(self):
        with (
            patch.object(runtime_mod, "send_command"),
            patch.object(runtime_mod, "get_response", return_value=None),
        ):
            assert runtime_mod.emit_event("main", "x") is False

    def test_emit_event_fire_drains_responses(self):
        # Pre-fill responses queue
        for _ in range(5):
            runtime_mod._responses.put({"stale": True})
        with patch.object(runtime_mod, "send_command") as mock_send:
            runtime_mod.emit_event_fire("main", "foo:bar", {"x": 1})
            sent = mock_send.call_args.args[0]
            assert sent["event"] == "foo:bar"
        # Queue should be drained
        assert runtime_mod._responses.qsize() == 0

    def test_emit_event_fire_default_payload(self):
        with patch.object(runtime_mod, "send_command") as mock_send:
            runtime_mod.emit_event_fire("main", "foo:bar")
            sent = mock_send.call_args.args[0]
            assert sent["payload"] == {}

    def test_eval_js_success(self):
        with (
            patch.object(runtime_mod, "send_command") as mock_send,
            patch.object(runtime_mod, "get_response", return_value={"success": True}),
        ):
            assert runtime_mod.eval_js("main", "alert(1)") is True
            sent = mock_send.call_args.args[0]
            assert sent["action"] == "eval"
            assert sent["script"] == "alert(1)"

    def test_eval_js_failure(self):
        with (
            patch.object(runtime_mod, "send_command"),
            patch.object(runtime_mod, "get_response", return_value=None),
        ):
            assert runtime_mod.eval_js("main", "x") is False


# ---------------------------------------------------------------------------
# _dispatch_event / _handle_content_request
# ---------------------------------------------------------------------------


class TestDispatchEvent:
    def test_basic_event_dispatch(self):
        registry = get_registry()
        called = []

        def handler(data, *_args):
            called.append(data)

        registry.register("main", "custom:event", handler)
        runtime_mod._dispatch_event(
            {"label": "main", "event_type": "custom:event", "data": {"v": 1}}
        )
        assert called == [{"v": 1}]

    def test_content_ready_renamed_to_pywry_ready(self):
        registry = get_registry()
        called = []

        def handler(data, *_args):
            called.append(data)

        registry.register("main", "pywry:ready", handler)
        runtime_mod._dispatch_event({"label": "main", "event_type": "content:ready", "data": {}})
        assert len(called) == 1

    def test_content_request_falls_back_to_handler(self):
        # No registered user handler -> calls _handle_content_request
        with patch.object(runtime_mod, "_handle_content_request") as mock_h:
            runtime_mod._dispatch_event(
                {"label": "main", "event_type": "pywry:content-request", "data": {}}
            )
            mock_h.assert_called_once()

    def test_content_request_user_handler_takes_precedence(self):
        registry = get_registry()
        called = []

        def handler(data, *_args):
            called.append(data)

        registry.register("main", "pywry:content-request", handler)
        with patch.object(runtime_mod, "_handle_content_request") as mock_h:
            runtime_mod._dispatch_event(
                {"label": "main", "event_type": "pywry:content-request", "data": {"foo": 1}}
            )
            mock_h.assert_not_called()
            assert len(called) == 1

    def test_refresh_request_falls_back(self):
        with patch.object(runtime_mod, "_handle_content_request") as mock_h:
            runtime_mod._dispatch_event(
                {"label": "main", "event_type": "pywry:refresh-request", "data": {}}
            )
            mock_h.assert_called_once()

    def test_default_label_when_missing(self):
        # No label -> defaults to "main"
        registry = get_registry()
        called = []

        def handler(data, *_args):
            called.append(data)

        registry.register("main", "x:y", handler)
        runtime_mod._dispatch_event({"event_type": "x:y", "data": {}})
        assert len(called) == 1


class TestHandleContentRequest:
    def test_no_lifecycle_entry(self):
        # Should not raise
        runtime_mod._handle_content_request("nonexistent")

    def test_destroyed_window(self):
        from pywry.window_manager import WindowResources

        lifecycle = get_lifecycle()
        res = WindowResources(label="main")
        res.is_destroyed = True
        lifecycle._windows["main"] = res
        # No raise
        runtime_mod._handle_content_request("main")

    def test_no_html(self):
        from pywry.window_manager import WindowResources

        lifecycle = get_lifecycle()
        res = WindowResources(label="main")
        res.html_content = None
        lifecycle._windows["main"] = res
        # No raise
        runtime_mod._handle_content_request("main")

    def test_debounces_recent_set(self):
        from datetime import datetime

        from pywry.window_manager import WindowResources

        lifecycle = get_lifecycle()
        res = WindowResources(label="main")
        res.html_content = "<p>x</p>"
        res.content_set_at = datetime.now()
        lifecycle._windows["main"] = res

        with patch.object(runtime_mod, "set_content") as mock_set:
            runtime_mod._handle_content_request("main")
            mock_set.assert_not_called()

    def test_uses_window_label_from_data(self):
        from pywry.models import ThemeMode, WindowConfig
        from pywry.window_manager import WindowResources

        lifecycle = get_lifecycle()
        res = WindowResources(label="other")
        res.html_content = "<p>hi</p>"
        res.last_config = WindowConfig(theme=ThemeMode.DARK)
        lifecycle._windows["other"] = res

        with patch.object(runtime_mod, "set_content", return_value=True) as mock_set:
            runtime_mod._handle_content_request("main", {"window_label": "other"})
            mock_set.assert_called_once_with("other", "<p>hi</p>", "dark")

    def test_resends_content_with_default_theme(self):
        from pywry.window_manager import WindowResources

        lifecycle = get_lifecycle()
        res = WindowResources(label="main")
        res.html_content = "<p>hi</p>"
        res.last_config = None  # No config
        lifecycle._windows["main"] = res

        with patch.object(runtime_mod, "set_content", return_value=True) as mock_set:
            runtime_mod._handle_content_request("main")
            mock_set.assert_called_once_with("main", "<p>hi</p>", "dark")


# ---------------------------------------------------------------------------
# Custom command handler
# ---------------------------------------------------------------------------


class TestHandleCustomCommand:
    def test_unknown_command_returns_error(self):
        sent = []
        with patch.object(runtime_mod, "send_command", side_effect=sent.append):
            runtime_mod._handle_custom_command({"command": "nope", "data": {}, "request_id": "r1"})
        assert sent and sent[0]["success"] is False
        assert "No handler registered" in sent[0]["error"]

    def test_sync_handler_returning_dict(self):
        runtime_mod.register_custom_command("foo", lambda d: {"ok": True})
        sent = []
        with patch.object(runtime_mod, "send_command", side_effect=sent.append):
            runtime_mod._handle_custom_command({"command": "foo", "data": {}, "request_id": "r1"})
        assert sent[0]["success"] is True
        assert sent[0]["ok"] is True

    def test_sync_handler_returning_non_dict(self):
        runtime_mod.register_custom_command("foo", lambda d: 42)
        sent = []
        with patch.object(runtime_mod, "send_command", side_effect=sent.append):
            runtime_mod._handle_custom_command({"command": "foo", "data": {}, "request_id": "r1"})
        assert sent[0]["success"] is True
        assert sent[0]["result"] == 42

    def test_handler_raises(self):
        def boom(_data):
            raise ValueError("boom!")

        runtime_mod.register_custom_command("foo", boom)
        sent = []
        with patch.object(runtime_mod, "send_command", side_effect=sent.append):
            runtime_mod._handle_custom_command({"command": "foo", "data": {}, "request_id": "r1"})
        assert sent[0]["success"] is False
        assert "boom!" in sent[0]["error"]

    def test_async_handler_uses_portal(self):
        async def afoo(_data):
            return {"async": True}

        runtime_mod.register_custom_command("afoo", afoo)
        sent = []
        # Simulate portal.call returning a dict
        fake_portal = MagicMock()
        fake_portal.call.return_value = {"async": True}
        with (
            patch.object(runtime_mod, "_ensure_portal", return_value=fake_portal),
            patch.object(runtime_mod, "send_command", side_effect=sent.append),
        ):
            runtime_mod._handle_custom_command({"command": "afoo", "data": {}, "request_id": "r1"})
        assert sent[0]["success"] is True
        assert sent[0]["async"] is True

    def test_async_handler_portal_runtime_error_falls_back_to_asyncio_run(self):
        async def afoo(_data):
            return {"fb": True}

        runtime_mod.register_custom_command("afoo", afoo)
        sent = []
        with (
            patch.object(runtime_mod, "_ensure_portal", side_effect=RuntimeError("portal fail")),
            patch.object(runtime_mod, "send_command", side_effect=sent.append),
        ):
            runtime_mod._handle_custom_command({"command": "afoo", "data": {}, "request_id": "r1"})
        assert sent[0]["success"] is True
        assert sent[0]["fb"] is True


# ---------------------------------------------------------------------------
# Reader/writer threads (drive directly)
# ---------------------------------------------------------------------------


class TestStdoutReader:
    def _make_proc_with_lines(self, lines: list[str]) -> MagicMock:
        proc = MagicMock()
        # readline returns one line per call, then "" to indicate EOF
        proc.stdout.readline = MagicMock(side_effect=[*lines, ""])
        return proc

    def test_dispatches_event_messages(self):
        proc = self._make_proc_with_lines(
            [json.dumps({"type": "event", "label": "main", "event_type": "x:y", "data": {}}) + "\n"]
        )
        runtime_mod._process = proc
        runtime_mod._running = True

        registry = get_registry()
        called = []
        registry.register("main", "x:y", lambda d, *_: called.append(d))

        runtime_mod._stdout_reader()
        # _running stays True until we set it False or stdout returns ""
        assert called == [{}]

    def test_sets_ready_on_ready_message(self):
        proc = self._make_proc_with_lines([json.dumps({"type": "ready"}) + "\n"])
        runtime_mod._process = proc
        runtime_mod._running = True
        runtime_mod._ready_event.clear()
        runtime_mod._stdout_reader()
        assert runtime_mod._ready_event.is_set()

    def test_dispatches_custom_command(self):
        proc = self._make_proc_with_lines(
            [
                json.dumps(
                    {"type": "custom_command", "command": "foo", "data": {}, "request_id": "r1"}
                )
                + "\n"
            ]
        )
        runtime_mod._process = proc
        runtime_mod._running = True
        with patch.object(runtime_mod, "_handle_custom_command") as mock_h:
            runtime_mod._stdout_reader()
            mock_h.assert_called_once()

    def test_correlated_response(self):
        proc = self._make_proc_with_lines([json.dumps({"request_id": "r1", "value": 42}) + "\n"])
        runtime_mod._process = proc
        runtime_mod._running = True
        ev = threading.Event()
        with runtime_mod._pending_lock:
            runtime_mod._pending_requests["r1"] = ev

        runtime_mod._stdout_reader()
        assert ev.is_set()
        with runtime_mod._pending_lock:
            assert runtime_mod._pending_responses["r1"]["value"] == 42

    def test_uncorrelated_response_goes_to_queue(self):
        proc = self._make_proc_with_lines([json.dumps({"unmatched": True}) + "\n"])
        runtime_mod._process = proc
        runtime_mod._running = True
        runtime_mod._stdout_reader()
        # Should be in _responses
        assert runtime_mod._responses.qsize() == 1
        msg = runtime_mod._responses.get_nowait()
        assert msg.get("unmatched") is True

    def test_handles_invalid_json(self):
        proc = self._make_proc_with_lines(["not-json\n"])
        runtime_mod._process = proc
        runtime_mod._running = True
        # Should swallow JSONDecodeError silently
        runtime_mod._stdout_reader()

    def test_handles_blank_line(self):
        proc = self._make_proc_with_lines(["\n", ""])
        runtime_mod._process = proc
        runtime_mod._running = True
        runtime_mod._stdout_reader()

    def test_exits_when_running_false(self):
        runtime_mod._running = False
        runtime_mod._process = None
        # Should immediately exit
        runtime_mod._stdout_reader()

    def test_handles_outermost_exception(self):
        # readline raising a non-Empty exception should be swallowed by the outer except
        proc = MagicMock()
        proc.stdout.readline = MagicMock(side_effect=SystemError("crash"))
        runtime_mod._process = proc
        runtime_mod._running = True
        runtime_mod._stdout_reader()


class TestStdinWriter:
    def test_writes_pending_commands(self):
        proc = MagicMock()
        proc.stdin.closed = False
        proc.stdin.write = MagicMock()
        proc.stdin.flush = MagicMock()
        runtime_mod._process = proc
        runtime_mod._running = True
        runtime_mod._outgoing.put({"action": "x"})

        # Run writer in a separate thread; let it write once then stop
        def stopper():
            time.sleep(0.2)
            runtime_mod._running = False

        t = threading.Thread(target=stopper, daemon=True)
        t.start()
        runtime_mod._stdin_writer()
        t.join(timeout=1.0)
        proc.stdin.write.assert_called()

    def test_handles_broken_pipe(self):
        proc = MagicMock()
        proc.stdin.closed = False
        proc.stdin.write = MagicMock(side_effect=BrokenPipeError("closed"))
        proc.stdin.flush = MagicMock()
        runtime_mod._process = proc
        runtime_mod._running = True
        runtime_mod._outgoing.put({"action": "x"})

        runtime_mod._stdin_writer()
        # Should swallow BrokenPipeError and exit

    def test_exits_when_stdin_closed(self):
        proc = MagicMock()
        proc.stdin.closed = True
        runtime_mod._process = proc
        runtime_mod._running = True
        runtime_mod._stdin_writer()  # immediate exit

    def test_handles_unexpected_exception(self):
        proc = MagicMock()
        proc.stdin.closed = False
        proc.stdin.write = MagicMock(side_effect=RuntimeError("boom"))
        proc.stdin.flush = MagicMock()
        runtime_mod._process = proc
        runtime_mod._running = True
        runtime_mod._outgoing.put({"action": "x"})
        runtime_mod._stdin_writer()

    def test_handles_outermost_exception(self):
        # The outer try in _stdin_writer wraps the entire while loop. To
        # trigger that branch we need the loop guard itself to raise, which
        # means making attribute access on _process.stdin throw.
        proc = MagicMock()

        # closed property raises -> not _process.stdin.closed evaluation hits outer except
        type(proc.stdin).closed = property(
            lambda _self: (_ for _ in ()).throw(SystemError("outer"))
        )
        runtime_mod._process = proc
        runtime_mod._running = True
        runtime_mod._stdin_writer()

    def test_breaks_when_running_flips_inside_loop(self):
        # cmd is fetched, then inside the loop _running becomes False so the
        # writer breaks before write/flush.
        proc = MagicMock()
        proc.stdin.closed = False
        proc.stdin.write = MagicMock()
        proc.stdin.flush = MagicMock()
        runtime_mod._process = proc
        runtime_mod._running = True

        original = runtime_mod._outgoing

        class StopAfterGet:
            def __init__(self):
                self._first = True

            def get(self, *_args, **_kwargs):
                if self._first:
                    self._first = False
                    runtime_mod._running = False
                    return {"action": "x"}
                raise Empty()

        runtime_mod._outgoing = StopAfterGet()  # type: ignore[assignment]
        try:
            runtime_mod._stdin_writer()
        finally:
            runtime_mod._outgoing = original

        proc.stdin.write.assert_not_called()


# ---------------------------------------------------------------------------
# start() / stop()
# ---------------------------------------------------------------------------


class TestStartStop:
    def test_start_already_running_returns_true(self):
        proc = MagicMock()
        proc.poll.return_value = None
        runtime_mod._process = proc
        assert runtime_mod.start() is True

    def test_start_failure_to_spawn(self):
        with (
            patch.object(runtime_mod.subprocess, "Popen", side_effect=OSError("cannot spawn")),
            patch("pywry._freeze.get_subprocess_command", return_value=["x"]),
            patch("pywry._freeze.is_frozen", return_value=False),
        ):
            assert runtime_mod.start() is False
            assert runtime_mod._running is False

    def test_start_succeeds_with_ready_signal(self):
        # Simulate a process that prints {"type":"ready"} and then EOFs.
        proc = MagicMock()
        proc.stdout.readline = MagicMock(side_effect=[json.dumps({"type": "ready"}) + "\n", ""])
        proc.stderr.readline = MagicMock(side_effect=[""])
        proc.stdin.closed = False
        proc.stdin.write = MagicMock()
        proc.stdin.flush = MagicMock()
        proc.poll.return_value = None

        with (
            patch.object(runtime_mod.subprocess, "Popen", return_value=proc),
            patch("pywry._freeze.get_subprocess_command", return_value=["x"]),
            patch("pywry._freeze.is_frozen", return_value=False),
            patch.object(runtime_mod, "atexit"),
        ):
            assert runtime_mod.start() is True
            assert runtime_mod._running is True

        # Cleanup
        runtime_mod._running = False

    def test_start_times_out_waiting_for_ready(self):
        # Simulate a process that never says ready
        proc = MagicMock()
        proc.stdout.readline = MagicMock(side_effect=[""])  # immediate EOF
        proc.stderr.readline = MagicMock(side_effect=[""])
        proc.stdin.closed = False
        proc.stdin.write = MagicMock()
        proc.stdin.flush = MagicMock()
        proc.poll.return_value = None
        proc.wait = MagicMock(return_value=0)
        proc.terminate = MagicMock()

        runtime_mod._ready_event.clear()
        # Use a very small wait timeout via patching wait_ready
        with (
            patch.object(runtime_mod.subprocess, "Popen", return_value=proc),
            patch("pywry._freeze.get_subprocess_command", return_value=["x"]),
            patch("pywry._freeze.is_frozen", return_value=False),
            patch.object(runtime_mod, "wait_ready", return_value=False),
        ):
            assert runtime_mod.start() is False

    def test_start_includes_extra_capabilities_and_custom_commands_in_env(self):
        runtime_mod.set_extra_capabilities(["cap1"])
        runtime_mod.register_custom_command("ccmd", lambda d: {})

        captured_env = {}

        def fake_popen(*args, **kwargs):
            captured_env["env"] = kwargs.get("env", {})
            proc = MagicMock()
            proc.stdout.readline = MagicMock(side_effect=[json.dumps({"type": "ready"}) + "\n", ""])
            proc.stderr.readline = MagicMock(side_effect=[""])
            proc.stdin.closed = False
            proc.poll.return_value = None
            return proc

        with (
            patch.object(runtime_mod.subprocess, "Popen", side_effect=fake_popen),
            patch("pywry._freeze.get_subprocess_command", return_value=["x"]),
            patch("pywry._freeze.is_frozen", return_value=True),
            patch.object(runtime_mod, "atexit"),
        ):
            runtime_mod.start()

        assert "PYWRY_EXTRA_CAPABILITIES" in captured_env["env"]
        assert "PYWRY_CUSTOM_COMMANDS" in captured_env["env"]
        assert captured_env["env"].get("PYWRY_IS_SUBPROCESS") == "1"

        runtime_mod._running = False

    def test_start_stderr_reader_writes_to_stderr(self):
        # Simulate stderr lines that the inner stderr_reader thread should drain.
        proc = MagicMock()
        proc.stdout.readline = MagicMock(side_effect=[json.dumps({"type": "ready"}) + "\n", ""])
        proc.stderr.readline = MagicMock(side_effect=["bad line\n", ""])
        proc.stdin.closed = False
        proc.stdin.write = MagicMock()
        proc.stdin.flush = MagicMock()
        proc.poll.return_value = None

        with (
            patch.object(runtime_mod.subprocess, "Popen", return_value=proc),
            patch("pywry._freeze.get_subprocess_command", return_value=["x"]),
            patch("pywry._freeze.is_frozen", return_value=False),
            patch.object(runtime_mod, "atexit"),
        ):
            assert runtime_mod.start() is True
            # Give stderr reader thread a chance to consume the line
            time.sleep(0.2)

        runtime_mod._running = False

    def test_start_stderr_reader_handles_exception(self):
        """Force the stderr_reader inner thread to hit its except branch by
        making stderr.readline raise an unrecognised exception."""
        proc = MagicMock()
        proc.stdout.readline = MagicMock(side_effect=[json.dumps({"type": "ready"}) + "\n", ""])
        proc.stderr.readline = MagicMock(side_effect=RuntimeError("stderr crash"))
        proc.stdin.closed = False
        proc.stdin.write = MagicMock()
        proc.stdin.flush = MagicMock()
        proc.poll.return_value = None

        with (
            patch.object(runtime_mod.subprocess, "Popen", return_value=proc),
            patch("pywry._freeze.get_subprocess_command", return_value=["x"]),
            patch("pywry._freeze.is_frozen", return_value=False),
            patch.object(runtime_mod, "atexit"),
        ):
            assert runtime_mod.start() is True
            # Give the stderr_reader thread time to hit its except branch
            time.sleep(0.3)

        runtime_mod._running = False

    def test_stop_when_not_running(self):
        runtime_mod._process = None
        runtime_mod._running = False
        # Should not raise
        runtime_mod.stop()

    def test_stop_terminates_subprocess(self):
        proc = MagicMock()
        proc.stdin.closed = False
        proc.stdin.write = MagicMock()
        proc.stdin.flush = MagicMock()
        proc.stdout = MagicMock()
        proc.stderr = MagicMock()
        proc.wait = MagicMock(return_value=0)
        runtime_mod._process = proc
        runtime_mod._running = True

        runtime_mod._outgoing.put({"action": "stale"})
        runtime_mod._responses.put({"stale": True})

        ev = threading.Event()
        with runtime_mod._pending_lock:
            runtime_mod._pending_requests["x"] = ev

        runtime_mod.stop()

        assert runtime_mod._process is None
        assert runtime_mod._outgoing.qsize() == 0
        assert runtime_mod._responses.qsize() == 0
        # Pending events all set
        assert ev.is_set()

    def test_stop_handles_wait_failure_with_terminate(self):
        proc = MagicMock()
        proc.stdin.closed = False
        proc.stdin.write = MagicMock()
        proc.stdin.flush = MagicMock()
        # First wait raises -> terminate path
        proc.wait = MagicMock(side_effect=[Exception("timeout"), 0])
        proc.terminate = MagicMock()
        runtime_mod._process = proc
        runtime_mod._running = True

        runtime_mod.stop()
        proc.terminate.assert_called()

    def test_stop_handles_wait_double_failure_kills(self):
        proc = MagicMock()
        proc.stdin.closed = False
        proc.stdin.write = MagicMock()
        proc.stdin.flush = MagicMock()
        proc.wait = MagicMock(side_effect=[Exception("fail"), Exception("again")])
        proc.terminate = MagicMock()
        proc.kill = MagicMock()
        runtime_mod._process = proc
        runtime_mod._running = True

        runtime_mod.stop()
        proc.kill.assert_called()

    def test_stop_handles_broken_stdin_write(self):
        proc = MagicMock()
        proc.stdin.closed = False
        proc.stdin.write = MagicMock(side_effect=BrokenPipeError("closed"))
        proc.stdin.flush = MagicMock()
        proc.wait = MagicMock(return_value=0)
        runtime_mod._process = proc
        runtime_mod._running = True

        runtime_mod.stop()  # should not raise

    def test_stop_handles_queue_race_condition(self):
        """When empty() returns False but get_nowait() races and raises Empty,
        the loop must break gracefully."""

        class RaceQueue:
            def empty(self):
                return False  # Always claim non-empty

            def get_nowait(self):
                raise Empty()

            def put(self, *_a, **_k):
                pass

        original_out = runtime_mod._outgoing
        original_resp = runtime_mod._responses
        runtime_mod._outgoing = RaceQueue()  # type: ignore[assignment]
        runtime_mod._responses = RaceQueue()  # type: ignore[assignment]
        try:
            runtime_mod._process = None
            runtime_mod._running = False
            runtime_mod.stop()
        finally:
            runtime_mod._outgoing = original_out
            runtime_mod._responses = original_resp


# ---------------------------------------------------------------------------
# Portal management
# ---------------------------------------------------------------------------


class TestPortal:
    def test_get_portal_returns_none_when_uninitialized(self):
        runtime_mod._portal = None
        assert runtime_mod.get_portal() is None

    def test_ensure_portal_caches(self):
        # Set up a fake portal
        fake_portal = MagicMock()

        class FakeStack:
            def enter_context(self, ctx):
                return fake_portal

            def __exit__(self, *args):
                return None

        with (
            patch.object(runtime_mod, "ExitStack", return_value=FakeStack()),
            patch("anyio.from_thread.start_blocking_portal"),
        ):
            runtime_mod._exit_stack = None
            runtime_mod._portal = None
            p1 = runtime_mod._ensure_portal()
            p2 = runtime_mod._ensure_portal()
            assert p1 is p2 is fake_portal

        # Cleanup
        runtime_mod._cleanup_portal()

    def test_cleanup_portal_clears_state(self):
        # Set up a fake stack to clean
        called = []
        fake_stack = MagicMock()
        fake_stack.__exit__ = MagicMock(return_value=None, side_effect=lambda *a: called.append(1))
        runtime_mod._exit_stack = fake_stack
        runtime_mod._portal = MagicMock()

        runtime_mod._cleanup_portal()

        assert runtime_mod._exit_stack is None
        assert runtime_mod._portal is None
        assert called == [1]

    def test_cleanup_portal_handles_exit_failure(self):
        fake_stack = MagicMock()
        fake_stack.__exit__ = MagicMock(side_effect=Exception("oops"))
        runtime_mod._exit_stack = fake_stack
        runtime_mod._portal = MagicMock()

        # Should not raise
        runtime_mod._cleanup_portal()

        assert runtime_mod._exit_stack is None
        assert runtime_mod._portal is None

    def test_cleanup_portal_no_op_when_nothing_to_clean(self):
        runtime_mod._exit_stack = None
        runtime_mod._portal = None
        runtime_mod._cleanup_portal()  # no-op


# ---------------------------------------------------------------------------
# _get_registry caching
# ---------------------------------------------------------------------------


class TestGetRegistry:
    def test_get_registry_caches(self):
        runtime_mod._registry = None
        r1 = runtime_mod._get_registry()
        r2 = runtime_mod._get_registry()
        assert r1 is r2
