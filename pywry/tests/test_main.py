"""Tests for the pywry.__main__ subprocess entry point.

These tests heavily mock pytauri, asyncio runtime, and IO streams so
the module can be exercised without spawning a real Tauri window.

The single largest hazard is that importing ``pywry.__main__`` rebinds
``sys.stdin``/``sys.stdout``/``sys.stderr`` on Windows (it wraps the
buffer in a UTF-8 ``TextIOWrapper``).  Because pytest captures those
streams, we patch them with ``unittest.mock.patch`` on the very first
import — in this module's import-time fixture — so subsequent tests
get clean references.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import threading
import types

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ──────────────────────────────────────────────────────────────────────
# Module-level import of pywry.__main__
# ──────────────────────────────────────────────────────────────────────


def _ensure_main_module() -> Any:
    """Import pywry.__main__ exactly once with safe stdio patches.

    We force-evict the cached module so we run the import-time block
    inside our patches; subsequent calls just return the loaded module.
    """
    if "pywry.__main__" in sys.modules:
        return sys.modules["pywry.__main__"]

    # ── Coverage compatibility ────────────────────────────────────────
    # ``coverage.Coverage.start()`` imports the source package (``pywry``)
    # to determine paths and then removes it from ``sys.modules`` via its
    # internal ``SysModuleSaver``.  However, ``_setup_pytauri_standalone``
    # has already mutated ``sys._pytauri_standalone = True`` while leaving
    # ``__pytauri_ext_mod__`` *unregistered*.  Subsequent calls then short-
    # circuit and never re-register the native extension.  Force a fresh
    # call so the extension is actually loaded.
    if getattr(sys, "_pytauri_standalone", False) and "__pytauri_ext_mod__" not in sys.modules:
        delattr(sys, "_pytauri_standalone")

    # Importing ``pywry`` first runs ``_setup_pytauri_standalone``, which
    # registers the native extension under ``sys.modules['__pytauri_ext_mod__']``.
    # Without this, the subsequent ``import pytauri_plugins`` inside
    # ``pywry.__main__`` fails because the entry-point lookup in
    # ``pytauri.ffi._ext_mod`` can't find the standalone marker.
    from pywry._freeze import _setup_pytauri_standalone

    _setup_pytauri_standalone()

    fake_stdin = io.TextIOWrapper(io.BytesIO(b""), encoding="utf-8")
    fake_stdout = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
    fake_stderr = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")

    real_stdin = sys.stdin
    real_stdout = sys.stdout
    real_stderr = sys.stderr

    sys.stdin = fake_stdin
    sys.stdout = fake_stdout
    sys.stderr = fake_stderr
    try:
        import pywry.__main__ as main_mod  # noqa: F401
    finally:
        sys.stdin = real_stdin
        sys.stdout = real_stdout
        sys.stderr = real_stderr

    return sys.modules["pywry.__main__"]


# Force-import at collection time so tests can rely on the module.
_main_mod = _ensure_main_module()


@pytest.fixture(autouse=True)
def _restore_stdio_streams():
    """Repair sys.stdin/stdout/stderr that __main__ may have rebound.

    Belt-and-suspenders — even with the import-time patch, some tests
    deliberately call ``main()`` which can mutate the streams again.
    """
    real_stdin = sys.stdin
    real_stdout = sys.stdout
    real_stderr = sys.stderr
    yield
    sys.stdin = real_stdin
    sys.stdout = real_stdout
    sys.stderr = real_stderr


# ──────────────────────────────────────────────────────────────────────
# log() / log_error()
# ──────────────────────────────────────────────────────────────────────


def _fake_sys_with_stderr(buf: io.StringIO) -> types.SimpleNamespace:
    """Build a ``sys`` proxy whose ``stderr`` writes into *buf*."""
    real_sys = _main_mod.sys
    fake = types.SimpleNamespace(
        stdin=real_sys.stdin,
        stdout=real_sys.stdout,
        stderr=buf,
        platform=real_sys.platform,
        modules=real_sys.modules,
        executable=real_sys.executable,
        exit=real_sys.exit,
    )
    for attr in dir(real_sys):
        if not hasattr(fake, attr) and not attr.startswith("_"):
            with contextlib.suppress(AttributeError, TypeError):
                setattr(fake, attr, getattr(real_sys, attr))
    return fake


class TestLogging:
    """Coverage for ``log`` and ``log_error`` helpers."""

    def test_log_writes_when_debug_enabled(self):
        buf = io.StringIO()
        with (
            patch.object(_main_mod, "DEBUG", True),
            patch.object(_main_mod, "sys", _fake_sys_with_stderr(buf)),
        ):
            _main_mod.log("hello")
        assert "[pywry] hello" in buf.getvalue()

    def test_log_silent_when_debug_disabled(self):
        buf = io.StringIO()
        with (
            patch.object(_main_mod, "DEBUG", False),
            patch.object(_main_mod, "sys", _fake_sys_with_stderr(buf)),
        ):
            _main_mod.log("hello")
        assert buf.getvalue() == ""

    def test_log_error_always_writes(self):
        buf = io.StringIO()
        with patch.object(_main_mod, "sys", _fake_sys_with_stderr(buf)):
            _main_mod.log_error("boom")
        assert "[pywry] ERROR: boom" in buf.getvalue()


# ──────────────────────────────────────────────────────────────────────
# _set_macos_dock_icon
# ──────────────────────────────────────────────────────────────────────


class TestMacOSDockIcon:
    """Cover all branches of the macOS dock-icon helper.

    The function is normally a no-op on non-darwin platforms.  By
    patching ``_main_mod.sys.platform`` and ``ctypes.cdll`` we can
    drive the darwin-only code paths from any host OS.
    """

    def test_returns_immediately_on_non_darwin(self):
        # On Windows/Linux this just returns; line coverage is hit.
        with patch.object(_main_mod.sys, "platform", "win32"):
            assert _main_mod._set_macos_dock_icon() is None

    def test_returns_when_no_icon_file(self, tmp_path):
        """Cover the Path.exists() == False branch (darwin only)."""
        # Force darwin path but make the assets directory empty so
        # both .icns and .png checks fail and the function returns.
        with (
            patch.object(_main_mod.sys, "platform", "darwin"),
            patch.object(_main_mod, "Path", side_effect=lambda *a, **kw: tmp_path),
        ):
            assert _main_mod._set_macos_dock_icon() is None

    def test_swallows_exceptions(self):
        """Internal errors are silently ignored."""
        from ctypes import cdll

        with (
            patch.object(_main_mod.sys, "platform", "darwin"),
            patch.object(cdll, "LoadLibrary", side_effect=OSError("boom")),
        ):
            # Should not raise
            assert _main_mod._set_macos_dock_icon() is None

    def test_full_darwin_path_with_icns(self, tmp_path):
        """Drive the full darwin success path by mocking ctypes.cdll.

        We patch the assets directory to one that contains a stub
        ``icon.icns`` so the ``Path.exists()`` short-circuits don't
        kick in, then provide a fake ``cdll.LoadLibrary`` that
        returns a mock objc lib.  The mock returns truthy values for
        every ``objc_msgSend`` call so the function reaches the
        final ``setApplicationIconImage:`` line.
        """
        # Build a stub assets dir with a fake icon
        assets_dir = tmp_path / "frontend" / "assets"
        assets_dir.mkdir(parents=True)
        (assets_dir / "icon.icns").write_bytes(b"fake")

        # Fake ``__file__`` so the function looks up our stub assets
        fake_main_file = tmp_path / "__main__.py"
        fake_main_file.write_text("")

        from ctypes import cdll

        # Build a fake objc-lib mock
        objc = MagicMock()
        # objc_msgSend returns a truthy void pointer
        objc.objc_msgSend.return_value = 1234
        objc.objc_getClass.return_value = 1
        objc.sel_registerName.return_value = 1
        appkit = MagicMock()

        def _load_lib(path):
            if "libobjc" in path:
                return objc
            return appkit

        with (
            patch.object(_main_mod.sys, "platform", "darwin"),
            patch.object(_main_mod, "__file__", str(fake_main_file)),
            patch.object(cdll, "LoadLibrary", side_effect=_load_lib),
        ):
            _main_mod._set_macos_dock_icon()
        # The final objc_msgSend should have been called for setApplicationIconImage
        assert objc.objc_msgSend.call_count >= 4

    def test_darwin_falls_back_to_png(self, tmp_path):
        """Cover the .icns-missing → .png-fallback branch."""
        assets_dir = tmp_path / "frontend" / "assets"
        assets_dir.mkdir(parents=True)
        # Only PNG, no ICNS
        (assets_dir / "icon.png").write_bytes(b"fake")

        fake_main_file = tmp_path / "__main__.py"
        fake_main_file.write_text("")

        from ctypes import cdll

        objc = MagicMock()
        objc.objc_msgSend.return_value = 1234
        objc.objc_getClass.return_value = 1
        objc.sel_registerName.return_value = 1
        appkit = MagicMock()

        def _load_lib(path):
            return objc if "libobjc" in path else appkit

        with (
            patch.object(_main_mod.sys, "platform", "darwin"),
            patch.object(_main_mod, "__file__", str(fake_main_file)),
            patch.object(cdll, "LoadLibrary", side_effect=_load_lib),
        ):
            _main_mod._set_macos_dock_icon()

    def test_darwin_objc_msgSend_returns_zero_for_app(self, tmp_path):
        """Cover the ``if not app:`` early-return branch."""
        assets_dir = tmp_path / "frontend" / "assets"
        assets_dir.mkdir(parents=True)
        (assets_dir / "icon.icns").write_bytes(b"fake")

        fake_main_file = tmp_path / "__main__.py"
        fake_main_file.write_text("")

        from ctypes import cdll

        objc = MagicMock()
        # First objc_msgSend (sharedApplication) returns 0/None → early return
        objc.objc_msgSend.return_value = 0
        objc.objc_getClass.return_value = 1
        objc.sel_registerName.return_value = 1

        with (
            patch.object(_main_mod.sys, "platform", "darwin"),
            patch.object(_main_mod, "__file__", str(fake_main_file)),
            patch.object(cdll, "LoadLibrary", return_value=objc),
        ):
            _main_mod._set_macos_dock_icon()
        # Only the sharedApplication call happened
        assert objc.objc_msgSend.call_count == 1

    def test_darwin_path_str_zero(self, tmp_path):
        """Cover ``if not path_str:`` early-return."""
        assets_dir = tmp_path / "frontend" / "assets"
        assets_dir.mkdir(parents=True)
        (assets_dir / "icon.icns").write_bytes(b"fake")

        fake_main_file = tmp_path / "__main__.py"
        fake_main_file.write_text("")

        from ctypes import cdll

        objc = MagicMock()
        # 1st call (sharedApp) -> 1; 2nd call (stringWithUTF8String:) -> 0
        objc.objc_msgSend.side_effect = [1, 0]
        objc.objc_getClass.return_value = 1
        objc.sel_registerName.return_value = 1

        with (
            patch.object(_main_mod.sys, "platform", "darwin"),
            patch.object(_main_mod, "__file__", str(fake_main_file)),
            patch.object(cdll, "LoadLibrary", return_value=objc),
        ):
            _main_mod._set_macos_dock_icon()
        assert objc.objc_msgSend.call_count == 2

    def test_darwin_image_zero(self, tmp_path):
        """Cover ``if not image:`` early-return."""
        assets_dir = tmp_path / "frontend" / "assets"
        assets_dir.mkdir(parents=True)
        (assets_dir / "icon.icns").write_bytes(b"fake")

        fake_main_file = tmp_path / "__main__.py"
        fake_main_file.write_text("")

        from ctypes import cdll

        objc = MagicMock()
        # 1: sharedApp, 2: NSString init, 3: NSImage alloc, 4: initWith…
        # initWithContentsOfFile returns 0 → early return
        objc.objc_msgSend.side_effect = [1, 2, 3, 0]
        objc.objc_getClass.return_value = 1
        objc.sel_registerName.return_value = 1

        with (
            patch.object(_main_mod.sys, "platform", "darwin"),
            patch.object(_main_mod, "__file__", str(fake_main_file)),
            patch.object(cdll, "LoadLibrary", return_value=objc),
        ):
            _main_mod._set_macos_dock_icon()


# ──────────────────────────────────────────────────────────────────────
# Module-level top-of-file code (setproctitle, macOS Carbon)
# ──────────────────────────────────────────────────────────────────────


class TestModuleTopLevelExec:
    """Drive coverage of code that runs only at module-import time.

    These blocks can't be re-executed by importing the module again
    (it's cached), so we extract the source lines and run them through
    ``compile`` + ``exec`` against the real file path.  Coverage maps
    the exec'd line numbers back to ``pywry/__main__.py``.
    """

    def _exec_lines(self, start_lineno: int, end_lineno: int, ns: dict) -> None:
        source_lines = Path(_main_mod.__file__).read_text(encoding="utf-8").splitlines(True)
        # Pad to preserve line numbers
        padding = "\n" * (start_lineno - 1)
        snippet = padding + "".join(source_lines[start_lineno - 1 : end_lineno])
        exec(compile(snippet, _main_mod.__file__, "exec"), ns)

    def test_setproctitle_import_error_branch(self):
        """Lines 14-20: setproctitle ImportError fallback.

        We force the import to fail by stuffing a None entry into
        ``sys.modules['setproctitle']``.  The ``try/except ImportError``
        block must swallow the ImportError silently.
        """
        with patch.dict(sys.modules, {"setproctitle": None}):
            ns: dict[str, Any] = {}
            # Lines 14-20: the try/except ImportError block
            self._exec_lines(14, 20, ns)
        # No assertion needed — coverage hits 19-20 (ImportError fallback)

    def test_macos_carbon_block_darwin(self):
        """Lines 27-40: macOS Carbon process-name block.

        Force ``sys.platform == 'darwin'`` and provide a fake
        ``ctypes.cdll`` whose ``LoadLibrary`` returns a mock that
        plays nicely with the calls below.
        """
        from ctypes import (
            Structure as _RealStructure,
            byref,
            c_uint32,
        )

        fake_carbon = MagicMock()

        # We exec the block with locally-bound names patched.
        ns: dict[str, Any] = {
            "sys": types.SimpleNamespace(platform="darwin"),
            "typing": __import__("typing"),
        }
        # Add ctypes patched so cdll.LoadLibrary returns the mock.
        import ctypes

        # The block does ``from ctypes import Structure, byref, c_uint32, cdll``
        # We need a local cdll whose LoadLibrary returns our mock.
        fake_cdll = MagicMock()
        fake_cdll.LoadLibrary.return_value = fake_carbon
        with patch.object(ctypes, "cdll", fake_cdll):
            # Lines 27-40
            self._exec_lines(27, 40, ns)

    def test_macos_carbon_block_oserror(self):
        """Lines 27-40 with ``OSError`` raised by ``LoadLibrary``."""
        import ctypes

        fake_cdll = MagicMock()
        fake_cdll.LoadLibrary.side_effect = OSError("no carbon")
        ns: dict[str, Any] = {
            "sys": types.SimpleNamespace(platform="darwin"),
            "typing": __import__("typing"),
        }
        with patch.object(ctypes, "cdll", fake_cdll):
            self._exec_lines(27, 40, ns)
        # OSError should be silently swallowed by the except clause.


# ──────────────────────────────────────────────────────────────────────
# _default_single_instance_callback
# ──────────────────────────────────────────────────────────────────────


class TestSingleInstanceCallback:
    """The callback should focus the existing 'main' window."""

    def test_focuses_existing_window(self):
        window = MagicMock()
        with patch.object(_main_mod.Manager, "get_webview_window", return_value=window):
            _main_mod._default_single_instance_callback(MagicMock(), [], "")
        window.show.assert_called_once()
        window.set_focus.assert_called_once()

    def test_no_window_returned_is_safe(self):
        with patch.object(_main_mod.Manager, "get_webview_window", return_value=None):
            _main_mod._default_single_instance_callback(MagicMock(), [], "")

    def test_swallows_manager_exception(self):
        with patch.object(
            _main_mod.Manager,
            "get_webview_window",
            side_effect=RuntimeError("boom"),
        ):
            _main_mod._default_single_instance_callback(MagicMock(), [], "")


# ──────────────────────────────────────────────────────────────────────
# _load_plugins
# ──────────────────────────────────────────────────────────────────────


class TestLoadPlugins:
    """All three init patterns plus error paths."""

    def test_unknown_plugin_raises(self):
        with pytest.raises(RuntimeError, match="Unknown Tauri plugin"):
            _main_mod._load_plugins(["does_not_exist"])

    def test_disabled_feature_flag_raises(self):
        # Pretend the dialog flag is False.
        with patch.object(_main_mod.pytauri_plugins, "PLUGIN_DIALOG", False):
            with pytest.raises(RuntimeError, match="not available"):
                _main_mod._load_plugins(["dialog"])

    def test_init_method_init(self):
        """Most plugins use ``mod.init()``."""
        fake_plugin = MagicMock(name="plugin")
        fake_module = MagicMock()
        fake_module.init.return_value = fake_plugin

        with patch.object(_main_mod.importlib, "import_module", return_value=fake_module):
            result = _main_mod._load_plugins(["dialog"])

        fake_module.init.assert_called_once_with()
        assert result == [fake_plugin]

    def test_init_method_builder(self):
        """``window_state`` etc. use ``Builder.build()``."""
        fake_plugin = MagicMock(name="plugin")
        fake_module = MagicMock()
        fake_module.Builder.build.return_value = fake_plugin

        with (
            patch.object(_main_mod.pytauri_plugins, "PLUGIN_WINDOW_STATE", True),
            patch.object(_main_mod.importlib, "import_module", return_value=fake_module),
        ):
            result = _main_mod._load_plugins(["window_state"])

        fake_module.Builder.build.assert_called_once_with()
        assert result == [fake_plugin]

    def test_init_method_callback(self):
        """``single_instance`` uses ``mod.init(callback)``."""
        fake_plugin = MagicMock(name="plugin")
        fake_module = MagicMock()
        fake_module.init.return_value = fake_plugin

        with (
            patch.object(_main_mod.pytauri_plugins, "PLUGIN_SINGLE_INSTANCE", True),
            patch.object(_main_mod.importlib, "import_module", return_value=fake_module),
        ):
            result = _main_mod._load_plugins(["single_instance"])

        # Callback variant passes _default_single_instance_callback
        fake_module.init.assert_called_once_with(_main_mod._default_single_instance_callback)
        assert result == [fake_plugin]


# ──────────────────────────────────────────────────────────────────────
# _stage_extra_capabilities
# ──────────────────────────────────────────────────────────────────────


class TestStageExtraCapabilities:
    """Copies the package + writes an extra TOML capability file."""

    def test_creates_extra_toml(self, tmp_path):
        # Build a minimal source dir with a capabilities subdir
        src = tmp_path / "src"
        src.mkdir()
        (src / "capabilities").mkdir()
        (src / "Tauri.toml").write_text("[build]\n", encoding="utf-8")

        out = _main_mod._stage_extra_capabilities(src, ["shell:allow-execute", "fs:allow-read"])
        try:
            extra = out / "capabilities" / "extra.toml"
            assert extra.exists()
            content = extra.read_text(encoding="utf-8")
            assert "shell:allow-execute" in content
            assert "fs:allow-read" in content
            assert 'identifier = "extra"' in content
        finally:
            import shutil

            shutil.rmtree(out, ignore_errors=True)


# ──────────────────────────────────────────────────────────────────────
# JsonIPC core methods
# ──────────────────────────────────────────────────────────────────────


class _StdoutCapture:
    """Stand-in for sys.stdout that records all writes."""

    def __init__(self) -> None:
        self.buf = io.StringIO()

    def write(self, s: str) -> int:
        return self.buf.write(s)

    def flush(self) -> None:  # pragma: no cover - trivial
        pass


@pytest.fixture
def capture_stdout(monkeypatch):
    """Capture writes that the module makes to ``sys.stdout``.

    pytest's capture plugin overrides ``sys.stdout`` for the test
    body itself, so direct ``sys.stdout = cap`` assignments inside
    fixtures are reverted before the test runs.  Instead we replace
    the *module-level* ``sys`` reference inside ``pywry.__main__``
    with a ``SimpleNamespace`` proxy whose ``.stdout`` is our buffer
    — JsonIPC.send() does ``sys.stdout.write(...)`` and therefore
    hits the proxy.
    """
    cap = _StdoutCapture()

    real_sys = _main_mod.sys
    fake_sys = types.SimpleNamespace(
        stdin=real_sys.stdin,
        stdout=cap,
        stderr=real_sys.stderr,
        platform=real_sys.platform,
        modules=real_sys.modules,
        executable=real_sys.executable,
        exit=real_sys.exit,
    )
    # Forward all other public attributes
    for attr in dir(real_sys):
        if not hasattr(fake_sys, attr) and not attr.startswith("_"):
            with contextlib.suppress(AttributeError, TypeError):
                setattr(fake_sys, attr, getattr(real_sys, attr))
    monkeypatch.setattr(_main_mod, "sys", fake_sys)
    return cap


@pytest.fixture
def ipc():
    return _main_mod.JsonIPC()


class TestJsonIPCSendMethods:
    def test_send_writes_json_line(self, ipc, capture_stdout):
        ipc.send({"type": "ready"})
        out = capture_stdout.buf.getvalue()
        assert out.endswith("\n")
        assert json.loads(out) == {"type": "ready"}

    def test_send_swallows_exception(self, ipc):
        # If json.dumps raises, send() must not propagate.
        with patch.object(_main_mod.json, "dumps", side_effect=TypeError("nope")):
            ipc.send({"x": object()})

    def test_send_ready(self, ipc, capture_stdout):
        ipc.send_ready()
        assert json.loads(capture_stdout.buf.getvalue())["type"] == "ready"

    def test_send_error(self, ipc, capture_stdout):
        # send_error writes to stderr and emits an error event.
        with patch.object(sys, "stderr", io.StringIO()):
            ipc.send_error("bad")
        msg = json.loads(capture_stdout.buf.getvalue())
        assert msg == {"type": "error", "error": "bad"}

    def test_send_result_success(self, ipc, capture_stdout):
        ipc.send_result("main", True)
        assert json.loads(capture_stdout.buf.getvalue()) == {
            "type": "result",
            "label": "main",
            "success": True,
        }

    def test_window_not_found_destroyed(self, ipc, capture_stdout):
        ipc._destroyed_windows.add("ghost")
        # Already-destroyed windows log at debug level → no stdout.
        ipc._window_not_found("ghost", "set_content")
        assert capture_stdout.buf.getvalue() == ""

    def test_window_not_found_real_error(self, ipc, capture_stdout):
        with patch.object(sys, "stderr", io.StringIO()):
            ipc._window_not_found("nope", "set_content")
        msg = json.loads(capture_stdout.buf.getvalue())
        assert msg["type"] == "error"
        assert "Window not found" in msg["error"]

    def test_window_not_found_no_context(self, ipc):
        with (
            patch.object(sys, "stderr", io.StringIO()),
            patch.object(ipc, "send"),
        ):
            ipc._window_not_found("nope", "")


class TestJsonIPCRequestResponse:
    def test_handle_response_no_request_id(self, ipc):
        assert ipc.handle_response({"foo": "bar"}) is False

    def test_handle_response_unknown_request_id(self, ipc):
        assert ipc.handle_response({"request_id": "missing"}) is False

    def test_handle_response_matches_pending(self, ipc):
        event = threading.Event()
        ipc._pending_requests["abc"] = event
        ok = ipc.handle_response({"request_id": "abc", "value": 42})
        assert ok
        assert event.is_set()
        assert ipc._pending_responses["abc"]["value"] == 42

    def test_send_request_and_wait_returns_response(self, ipc):
        # Pre-arrange: when send() is called we synchronously deliver the response.
        def _fake_send(msg):
            ipc.handle_response({"request_id": msg["request_id"], "value": "ok"})

        with patch.object(ipc, "send", side_effect=_fake_send):
            result = ipc.send_request_and_wait({"type": "x"}, timeout=2.0)
        assert result["value"] == "ok"

    def test_send_request_and_wait_timeout(self, ipc):
        with patch.object(ipc, "send"):
            result = ipc.send_request_and_wait({"type": "x"}, timeout=0.05)
        assert "timeout" in result["error"]


# ──────────────────────────────────────────────────────────────────────
# IPC command dispatcher
# ──────────────────────────────────────────────────────────────────────


class TestHandleCommand:
    """Each branch of the action dispatcher."""

    @pytest.mark.parametrize(
        "action,handler",
        [
            ("create", "create_window"),
            ("set_content", "set_content"),
            ("show", "show_window"),
            ("hide", "hide_window"),
            ("close", "close_window"),
            ("emit", "emit_event"),
            ("eval", "eval_js"),
            ("check_open", "check_window_open"),
            ("window_get", "window_get_property"),
            ("window_call", "window_call_method"),
            ("menu_create", "menu_create"),
            ("menu_set", "menu_set"),
            ("menu_popup", "menu_popup"),
            ("menu_update", "menu_update"),
            ("menu_remove", "menu_remove"),
            ("tray_create", "tray_create"),
            ("tray_update", "tray_update"),
            ("tray_remove", "tray_remove"),
            ("quit", "quit"),
        ],
    )
    def test_dispatch_routes(self, ipc, action, handler):
        with patch.object(ipc, handler) as mock_handler:
            ipc.handle_command({"action": action})
        if action == "quit":
            mock_handler.assert_called_once_with()
        else:
            mock_handler.assert_called_once()

    def test_unknown_action(self, ipc, capture_stdout):
        with patch.object(sys, "stderr", io.StringIO()):
            ipc.handle_command({"action": "unknown_xyz"})
        out = json.loads(capture_stdout.buf.getvalue())
        assert "Unknown action" in out["error"]


# ──────────────────────────────────────────────────────────────────────
# quit()
# ──────────────────────────────────────────────────────────────────────


class TestQuit:
    def test_quit_destroys_windows_and_calls_os_exit(self, ipc):
        ipc.app_handle = MagicMock()
        win = MagicMock()
        ipc.windows["a"] = win

        tray = MagicMock()
        ipc.trays["t"] = tray

        # Tray that raises during cleanup — must be swallowed.
        bad_tray = MagicMock()
        bad_tray.set_visible.side_effect = RuntimeError("boom")
        ipc.trays["bad"] = bad_tray

        # Manager.get_webview_window for "main" returns another window
        main_win = MagicMock()
        with (
            patch.object(_main_mod.Manager, "get_webview_window", return_value=main_win),
            patch.object(_main_mod.os, "_exit") as mock_exit,
        ):
            ipc.quit()

        win.destroy.assert_called_once()
        main_win.destroy.assert_called_once()
        mock_exit.assert_called_once_with(0)
        assert ipc.running is False

    def test_quit_when_window_destroy_raises(self, ipc):
        ipc.app_handle = MagicMock()
        win = MagicMock()
        win.destroy.side_effect = RuntimeError("boom")
        ipc.windows["a"] = win
        with (
            patch.object(
                _main_mod.Manager,
                "get_webview_window",
                side_effect=RuntimeError("boom"),
            ),
            patch.object(_main_mod.os, "_exit") as mock_exit,
        ):
            ipc.quit()
        mock_exit.assert_called_once_with(0)

    def test_quit_no_app_handle(self, ipc):
        # Skips the destroy-windows path when app_handle is None
        with patch.object(_main_mod.os, "_exit") as mock_exit:
            ipc.quit()
        mock_exit.assert_called_once_with(0)


# ──────────────────────────────────────────────────────────────────────
# create_window
# ──────────────────────────────────────────────────────────────────────


class TestCreateWindow:
    def test_no_app_handle_sends_error(self, ipc, capture_stdout):
        ipc.app_handle = None
        with patch.object(sys, "stderr", io.StringIO()):
            ipc.create_window({"label": "x"})
        out = json.loads(capture_stdout.buf.getvalue())
        assert out["type"] == "error"

    def test_existing_window_reused(self, ipc, capture_stdout):
        ipc.app_handle = MagicMock()
        existing = MagicMock()
        with (
            patch.object(_main_mod.Manager, "get_webview_window", return_value=existing),
            patch.object(_main_mod, "HEADLESS", False),
        ):
            ipc.create_window({"label": "main"})
        existing.show.assert_called_once()
        existing.set_focus.assert_called_once()
        assert ipc.windows["main"] is existing

    def test_existing_window_headless(self, ipc, capture_stdout):
        ipc.app_handle = MagicMock()
        existing = MagicMock()
        with (
            patch.object(_main_mod.Manager, "get_webview_window", return_value=existing),
            patch.object(_main_mod, "HEADLESS", True),
        ):
            ipc.create_window({"label": "main"})
        existing.show.assert_not_called()

    def test_manager_lookup_raises(self, ipc, capture_stdout):
        """Looking up an existing window can raise — should be logged then
        proceed to create a new one."""
        ipc.app_handle = MagicMock()

        new_window = MagicMock()
        with (
            patch.object(
                _main_mod.Manager,
                "get_webview_window",
                side_effect=RuntimeError("boom"),
            ),
            patch.object(_main_mod.WebviewWindowBuilder, "build", return_value=new_window),
            patch.object(_main_mod, "HEADLESS", False),
        ):
            ipc.create_window({"label": "x"})

        new_window.center.assert_called_once()
        new_window.show.assert_called_once()
        new_window.set_focus.assert_called_once()

    def test_build_with_all_options(self, ipc):
        ipc.app_handle = MagicMock()
        new_window = MagicMock()
        opts = {
            "resizable": False,
            "decorations": False,
            "always_on_top": True,
            "always_on_bottom": False,
            "transparent": True,
            "fullscreen": False,
            "maximized": False,
            "focused": True,
            "shadow": True,
            "skip_taskbar": False,
            "content_protected": False,
            "user_agent": "PyWry",
            "incognito": False,
            "initialization_script": "console.log('init')",
            "drag_and_drop": True,
            "visible": True,
        }
        with (
            patch.object(_main_mod.Manager, "get_webview_window", return_value=None),
            patch.object(
                _main_mod.WebviewWindowBuilder, "build", return_value=new_window
            ) as mock_build,
            patch.object(_main_mod, "HEADLESS", True),
        ):
            ipc.create_window(
                {"label": "x", "title": "T", "width": 100, "height": 200, "builder_opts": opts}
            )
        # Inner-size and visible are forwarded.
        called_kwargs = mock_build.call_args.kwargs
        assert called_kwargs["title"] == "T"
        assert called_kwargs["resizable"] is False
        assert called_kwargs["visible"] is False  # HEADLESS forces False

    def test_build_raises(self, ipc, capture_stdout):
        ipc.app_handle = MagicMock()
        with (
            patch.object(_main_mod.Manager, "get_webview_window", return_value=None),
            patch.object(
                _main_mod.WebviewWindowBuilder,
                "build",
                side_effect=RuntimeError("boom"),
            ),
            patch.object(sys, "stderr", io.StringIO()),
        ):
            ipc.create_window({"label": "x"})
        # Drain captured stdout — should contain an error entry
        lines = [ln for ln in capture_stdout.buf.getvalue().splitlines() if ln]
        assert any("error" in ln for ln in lines)


# ──────────────────────────────────────────────────────────────────────
# set_content
# ──────────────────────────────────────────────────────────────────────


class TestSetContent:
    def test_sets_dark_theme_background(self, ipc):
        win = MagicMock()
        ipc.windows["main"] = win
        ipc.app_handle = MagicMock()
        with (
            patch("time.sleep"),
            patch.object(ipc, "send_result"),
        ):
            ipc.set_content({"label": "main", "html": "<p>x</p>", "theme": "dark"})
        win.set_background_color.assert_called_with((30, 30, 30, 255))
        win.eval.assert_called_once()

    def test_sets_light_theme_background(self, ipc):
        win = MagicMock()
        ipc.windows["main"] = win
        ipc.app_handle = MagicMock()
        with (
            patch("time.sleep"),
            patch.object(ipc, "send_result"),
        ):
            ipc.set_content({"label": "main", "theme": "light", "html": ""})
        win.set_background_color.assert_called_with((255, 255, 255, 255))

    def test_imports_time_module(self, ipc):
        # Hits the inline ``import time`` line.
        win = MagicMock()
        ipc.windows["main"] = win
        ipc.app_handle = MagicMock()
        with (
            patch("time.sleep"),
            patch.object(ipc, "send_result"),
        ):
            ipc.set_content({"label": "main"})

    def test_window_resolved_via_manager(self, ipc):
        ipc.app_handle = MagicMock()
        win = MagicMock()
        with (
            patch.object(_main_mod.Manager, "get_webview_window", return_value=win),
            patch("time.sleep"),
            patch.object(ipc, "send_result"),
        ):
            ipc.set_content({"label": "ghost"})
        assert ipc.windows["ghost"] is win

    def test_window_not_found(self, ipc, capture_stdout):
        ipc.app_handle = None
        with patch.object(sys, "stderr", io.StringIO()):
            ipc.set_content({"label": "ghost"})
        assert "error" in capture_stdout.buf.getvalue()

    def test_eval_raises(self, ipc, capture_stdout):
        win = MagicMock()
        win.eval.side_effect = RuntimeError("boom")
        ipc.windows["main"] = win
        with (
            patch("time.sleep"),
            patch.object(sys, "stderr", io.StringIO()),
        ):
            ipc.set_content({"label": "main"})
        assert "error" in capture_stdout.buf.getvalue()


# ──────────────────────────────────────────────────────────────────────
# show / hide / close / check_open
# ──────────────────────────────────────────────────────────────────────


class TestShowHideClose:
    def test_show_window_in_cache(self, ipc):
        win = MagicMock()
        ipc.windows["a"] = win
        with patch.object(_main_mod, "HEADLESS", False), patch.object(ipc, "send_result"):
            ipc.show_window({"label": "a"})
        win.show.assert_called_once()

    def test_show_headless(self, ipc):
        win = MagicMock()
        ipc.windows["a"] = win
        with patch.object(_main_mod, "HEADLESS", True), patch.object(ipc, "send_result"):
            ipc.show_window({"label": "a"})
        win.show.assert_not_called()

    def test_show_via_manager(self, ipc):
        ipc.app_handle = MagicMock()
        win = MagicMock()
        with (
            patch.object(_main_mod.Manager, "get_webview_window", return_value=win),
            patch.object(_main_mod, "HEADLESS", False),
            patch.object(ipc, "send_result"),
        ):
            ipc.show_window({"label": "x"})
        assert ipc.windows["x"] is win

    def test_show_raises(self, ipc, capture_stdout):
        win = MagicMock()
        win.show.side_effect = RuntimeError("boom")
        ipc.windows["a"] = win
        with (
            patch.object(_main_mod, "HEADLESS", False),
            patch.object(sys, "stderr", io.StringIO()),
        ):
            ipc.show_window({"label": "a"})
        assert "error" in capture_stdout.buf.getvalue()

    def test_show_window_not_found(self, ipc, capture_stdout):
        ipc.app_handle = None
        with patch.object(sys, "stderr", io.StringIO()):
            ipc.show_window({"label": "ghost"})
        assert "error" in capture_stdout.buf.getvalue()

    def test_hide_window(self, ipc, capture_stdout):
        win = MagicMock()
        ipc.windows["a"] = win
        with patch.object(_main_mod, "HEADLESS", False):
            ipc.hide_window({"label": "a"})
        win.hide.assert_called_once()
        # Two messages emitted (event + result).
        msgs = [json.loads(ln) for ln in capture_stdout.buf.getvalue().splitlines() if ln]
        assert any(m.get("event_type") == "window:hidden" for m in msgs)

    def test_hide_headless(self, ipc):
        win = MagicMock()
        ipc.windows["a"] = win
        with (
            patch.object(_main_mod, "HEADLESS", True),
            patch.object(ipc, "send"),
            patch.object(ipc, "send_result"),
        ):
            ipc.hide_window({"label": "a"})
        win.hide.assert_not_called()

    def test_hide_via_manager(self, ipc):
        ipc.app_handle = MagicMock()
        win = MagicMock()
        with (
            patch.object(_main_mod.Manager, "get_webview_window", return_value=win),
            patch.object(_main_mod, "HEADLESS", True),
            patch.object(ipc, "send"),
            patch.object(ipc, "send_result"),
        ):
            ipc.hide_window({"label": "g"})
        assert ipc.windows["g"] is win

    def test_hide_raises(self, ipc, capture_stdout):
        win = MagicMock()
        win.hide.side_effect = RuntimeError("boom")
        ipc.windows["a"] = win
        with (
            patch.object(_main_mod, "HEADLESS", False),
            patch.object(sys, "stderr", io.StringIO()),
        ):
            ipc.hide_window({"label": "a"})
        assert "error" in capture_stdout.buf.getvalue()

    def test_hide_window_not_found(self, ipc, capture_stdout):
        ipc.app_handle = None
        with patch.object(sys, "stderr", io.StringIO()):
            ipc.hide_window({"label": "ghost"})
        assert "error" in capture_stdout.buf.getvalue()

    def test_close_window_in_cache(self, ipc):
        win = MagicMock()
        ipc.windows["a"] = win
        with patch.object(ipc, "send_result"):
            ipc.close_window({"label": "a"})
        win.destroy.assert_called_once()
        assert "a" not in ipc.windows

    def test_close_via_manager(self, ipc):
        ipc.app_handle = MagicMock()
        win = MagicMock()
        with (
            patch.object(_main_mod.Manager, "get_webview_window", return_value=win),
            patch.object(ipc, "send_result"),
        ):
            ipc.close_window({"label": "x"})
        win.destroy.assert_called_once()

    def test_close_raises(self, ipc, capture_stdout):
        win = MagicMock()
        win.destroy.side_effect = RuntimeError("boom")
        ipc.windows["a"] = win
        with patch.object(sys, "stderr", io.StringIO()):
            ipc.close_window({"label": "a"})
        assert "error" in capture_stdout.buf.getvalue()

    def test_close_window_not_found(self, ipc, capture_stdout):
        ipc.app_handle = None
        with patch.object(sys, "stderr", io.StringIO()):
            ipc.close_window({"label": "ghost"})
        assert "error" in capture_stdout.buf.getvalue()

    def test_check_window_open_cached(self, ipc, capture_stdout):
        ipc.windows["a"] = MagicMock()
        ipc.check_window_open({"label": "a"})
        out = json.loads(capture_stdout.buf.getvalue())
        assert out["is_open"] is True

    def test_check_window_open_via_manager(self, ipc, capture_stdout):
        ipc.app_handle = MagicMock()
        with patch.object(_main_mod.Manager, "get_webview_window", return_value=MagicMock()):
            ipc.check_window_open({"label": "g"})
        assert json.loads(capture_stdout.buf.getvalue())["is_open"] is True

    def test_check_window_open_manager_raises(self, ipc, capture_stdout):
        # Exception path inside ``with suppress(Exception)`` returns False.
        ipc.app_handle = MagicMock()
        with patch.object(
            _main_mod.Manager,
            "get_webview_window",
            side_effect=RuntimeError("boom"),
        ):
            ipc.check_window_open({"label": "g"})
        assert json.loads(capture_stdout.buf.getvalue())["is_open"] is False

    def test_check_window_open_no_app_handle(self, ipc, capture_stdout):
        ipc.app_handle = None
        ipc.check_window_open({"label": "missing"})
        assert json.loads(capture_stdout.buf.getvalue())["is_open"] is False


# ──────────────────────────────────────────────────────────────────────
# emit_event / _emit_to_window
# ──────────────────────────────────────────────────────────────────────


class TestEmitEvent:
    def test_missing_event_field(self, ipc, capture_stdout):
        with patch.object(sys, "stderr", io.StringIO()):
            ipc.emit_event({"label": "a"})
        msg = json.loads(capture_stdout.buf.getvalue())
        assert "missing 'event'" in msg["error"]

    def test_emit_wildcard(self, ipc, capture_stdout):
        win1, win2 = MagicMock(), MagicMock()
        ipc.windows = {"a": win1, "b": win2}
        ipc.emit_event({"label": "*", "event": "x:y", "payload": {"v": 1}})
        win1.eval.assert_called_once()
        win2.eval.assert_called_once()

    def test_emit_wildcard_one_raises(self, ipc):
        bad = MagicMock()
        bad.eval.side_effect = RuntimeError("boom")
        good = MagicMock()
        ipc.windows = {"a": bad, "b": good}
        with patch.object(ipc, "send_result"):
            ipc.emit_event({"label": "*", "event": "ns:e"})
        good.eval.assert_called_once()

    def test_emit_specific_window(self, ipc):
        win = MagicMock()
        ipc.windows["a"] = win
        with patch.object(ipc, "send_result"):
            ipc.emit_event({"label": "a", "event": "x:y", "payload": {"v": 1}})
        win.eval.assert_called_once()

    def test_emit_via_manager(self, ipc):
        ipc.app_handle = MagicMock()
        win = MagicMock()
        with (
            patch.object(_main_mod.Manager, "get_webview_window", return_value=win),
            patch.object(ipc, "send_result"),
        ):
            ipc.emit_event({"label": "g", "event": "x:y"})
        assert ipc.windows["g"] is win

    def test_emit_window_not_found(self, ipc, capture_stdout):
        ipc.app_handle = None
        with patch.object(sys, "stderr", io.StringIO()):
            ipc.emit_event({"label": "g", "event": "x:y"})
        assert "error" in capture_stdout.buf.getvalue()

    def test_emit_eval_raises(self, ipc, capture_stdout):
        win = MagicMock()
        win.eval.side_effect = RuntimeError("boom")
        ipc.windows["a"] = win
        with patch.object(sys, "stderr", io.StringIO()):
            ipc.emit_event({"label": "a", "event": "x:y"})
        assert "error" in capture_stdout.buf.getvalue()


# ──────────────────────────────────────────────────────────────────────
# eval_js
# ──────────────────────────────────────────────────────────────────────


class TestEvalJS:
    def test_missing_script(self, ipc, capture_stdout):
        with patch.object(sys, "stderr", io.StringIO()):
            ipc.eval_js({"label": "a"})
        msg = json.loads(capture_stdout.buf.getvalue())
        assert "missing 'script'" in msg["error"]

    def test_runs_script(self, ipc):
        win = MagicMock()
        ipc.windows["a"] = win
        with patch.object(ipc, "send_result"):
            ipc.eval_js({"label": "a", "script": "1+1"})
        win.eval.assert_called_once_with("1+1")

    def test_runs_via_manager(self, ipc):
        ipc.app_handle = MagicMock()
        win = MagicMock()
        with (
            patch.object(_main_mod.Manager, "get_webview_window", return_value=win),
            patch.object(ipc, "send_result"),
        ):
            ipc.eval_js({"label": "g", "script": "x"})
        assert ipc.windows["g"] is win

    def test_window_not_found(self, ipc, capture_stdout):
        ipc.app_handle = None
        with patch.object(sys, "stderr", io.StringIO()):
            ipc.eval_js({"label": "g", "script": "x"})
        assert "error" in capture_stdout.buf.getvalue()

    def test_eval_raises(self, ipc, capture_stdout):
        win = MagicMock()
        win.eval.side_effect = RuntimeError("boom")
        ipc.windows["a"] = win
        with patch.object(sys, "stderr", io.StringIO()):
            ipc.eval_js({"label": "a", "script": "1"})
        assert "error" in capture_stdout.buf.getvalue()


# ──────────────────────────────────────────────────────────────────────
# window_get / window_call
# ──────────────────────────────────────────────────────────────────────


class TestWindowGetSet:
    def test_window_get_no_property(self, ipc, capture_stdout):
        ipc.window_get_property({"label": "a", "request_id": "r"})
        msg = json.loads(capture_stdout.buf.getvalue())
        assert msg["success"] is False
        assert "missing 'property'" in msg["error"]

    def test_window_get_window_not_found(self, ipc, capture_stdout):
        ipc.app_handle = None
        ipc.window_get_property({"label": "a", "property": "title", "request_id": "r"})
        msg = json.loads(capture_stdout.buf.getvalue())
        assert msg["success"] is False
        assert "Window not found" in msg["error"]

    def test_window_get_success(self, ipc, capture_stdout):
        win = MagicMock()
        ipc.windows["a"] = win
        fake_dispatch = types.ModuleType("pywry.window_dispatch")
        fake_dispatch.get_window_property = lambda w, p, args: "Title"
        with patch.dict(sys.modules, {"pywry.window_dispatch": fake_dispatch}):
            ipc.window_get_property({"label": "a", "property": "title", "request_id": "r"})
        msg = json.loads(capture_stdout.buf.getvalue())
        assert msg["success"] is True
        assert msg["value"] == "Title"

    def test_window_get_dispatch_raises(self, ipc, capture_stdout):
        win = MagicMock()
        ipc.windows["a"] = win

        def _raise(*a, **k):
            raise RuntimeError("boom")

        fake_dispatch = types.ModuleType("pywry.window_dispatch")
        fake_dispatch.get_window_property = _raise
        with patch.dict(sys.modules, {"pywry.window_dispatch": fake_dispatch}):
            ipc.window_get_property({"label": "a", "property": "title", "request_id": "r"})
        msg = json.loads(capture_stdout.buf.getvalue())
        assert msg["success"] is False

    def test_window_call_no_method_with_request_id(self, ipc, capture_stdout):
        ipc.window_call_method({"label": "a", "request_id": "r"})
        msg = json.loads(capture_stdout.buf.getvalue())
        assert msg["success"] is False

    def test_window_call_no_method_no_request_id(self, ipc, capture_stdout):
        with patch.object(sys, "stderr", io.StringIO()):
            ipc.window_call_method({"label": "a"})
        # No stdout response, only stderr log.
        assert capture_stdout.buf.getvalue() == ""

    def test_window_call_no_window_with_request_id(self, ipc, capture_stdout):
        ipc.app_handle = None
        ipc.window_call_method({"label": "g", "method": "set_title", "request_id": "r"})
        msg = json.loads(capture_stdout.buf.getvalue())
        assert msg["success"] is False

    def test_window_call_no_window_no_request_id(self, ipc, capture_stdout):
        ipc.app_handle = None
        with patch.object(sys, "stderr", io.StringIO()):
            ipc.window_call_method({"label": "g", "method": "set_title"})
        assert capture_stdout.buf.getvalue() == ""

    def test_window_call_success_with_request_id(self, ipc, capture_stdout):
        win = MagicMock()
        ipc.windows["a"] = win
        fake_dispatch = types.ModuleType("pywry.window_dispatch")
        fake_dispatch.call_window_method = lambda w, m, a: "ok"
        with patch.dict(sys.modules, {"pywry.window_dispatch": fake_dispatch}):
            ipc.window_call_method({"label": "a", "method": "set_title", "request_id": "r"})
        msg = json.loads(capture_stdout.buf.getvalue())
        assert msg["success"] is True
        assert msg["value"] == "ok"

    def test_window_call_success_no_request_id(self, ipc, capture_stdout):
        win = MagicMock()
        ipc.windows["a"] = win
        fake_dispatch = types.ModuleType("pywry.window_dispatch")
        fake_dispatch.call_window_method = lambda w, m, a: None
        with patch.dict(sys.modules, {"pywry.window_dispatch": fake_dispatch}):
            ipc.window_call_method({"label": "a", "method": "set_title"})
        # No response expected.
        assert capture_stdout.buf.getvalue() == ""

    def test_window_call_raises_with_request_id(self, ipc, capture_stdout):
        win = MagicMock()
        ipc.windows["a"] = win

        def _raise(*a, **k):
            raise RuntimeError("boom")

        fake_dispatch = types.ModuleType("pywry.window_dispatch")
        fake_dispatch.call_window_method = _raise
        with (
            patch.object(sys, "stderr", io.StringIO()),
            patch.dict(sys.modules, {"pywry.window_dispatch": fake_dispatch}),
        ):
            ipc.window_call_method({"label": "a", "method": "set_title", "request_id": "r"})
        msg = json.loads(capture_stdout.buf.getvalue())
        assert msg["success"] is False

    def test_window_call_raises_no_request_id(self, ipc, capture_stdout):
        win = MagicMock()
        ipc.windows["a"] = win

        def _raise(*a, **k):
            raise RuntimeError("boom")

        fake_dispatch = types.ModuleType("pywry.window_dispatch")
        fake_dispatch.call_window_method = _raise
        with (
            patch.object(sys, "stderr", io.StringIO()),
            patch.dict(sys.modules, {"pywry.window_dispatch": fake_dispatch}),
        ):
            ipc.window_call_method({"label": "a", "method": "set_title"})
        assert capture_stdout.buf.getvalue() == ""

    def test_get_window_helper(self, ipc):
        # Direct test for the small helper.
        win = MagicMock()
        ipc.windows["a"] = win
        assert ipc._get_window("a") is win

        ipc.app_handle = MagicMock()
        win2 = MagicMock()
        with patch.object(_main_mod.Manager, "get_webview_window", return_value=win2):
            assert ipc._get_window("g") is win2
            assert ipc.windows["g"] is win2

        # No window
        ipc.app_handle = None
        assert ipc._get_window("none") is None


# ──────────────────────────────────────────────────────────────────────
# Menu builders
# ──────────────────────────────────────────────────────────────────────


def _install_fake_menu_module():
    """Patch ``pytauri.menu`` with a stand-in module."""
    fake = types.ModuleType("pytauri.menu")

    class _Item:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        def set_text(self, t):
            self._text = t

        def set_enabled(self, e):
            self._enabled = e

        def set_checked(self, c):
            self._checked = c

        def set_accelerator(self, a):
            self._accel = a

        def set_icon(self, i):
            self._icon = i

    class CheckMenuItem(_Item):
        @classmethod
        def with_id(cls, *args, **kwargs):
            return cls(*args, **kwargs)

    class IconMenuItem(_Item):
        @classmethod
        def with_id(cls, *args, **kwargs):
            return cls(*args, **kwargs)

        @classmethod
        def with_id_and_native_icon(cls, *args, **kwargs):
            return cls(*args, **kwargs)

    class MenuItem(_Item):
        @classmethod
        def with_id(cls, *args, **kwargs):
            return cls(*args, **kwargs)

    class PredefinedMenuItem:
        @staticmethod
        def separator(*args):
            return _Item(*args, kind="separator")

        @staticmethod
        def copy(*args):
            return _Item(*args, kind="copy")

    class Submenu(_Item):
        @classmethod
        def with_id_and_items(cls, *args, **kwargs):
            return cls(*args, **kwargs)

    class Menu:
        @classmethod
        def with_id_and_items(cls, app, mid, items):
            obj = MagicMock(spec=["append", "prepend", "insert", "remove"])
            obj.menu_id = mid
            obj.items = list(items)
            return obj

    class ContextMenu:
        popup_calls = []
        popup_at_calls = []

        @classmethod
        def popup(cls, *args, **kwargs):
            cls.popup_calls.append((args, kwargs))

        @classmethod
        def popup_at(cls, *args, **kwargs):
            cls.popup_at_calls.append((args, kwargs))

    class NativeIcon:
        Add = "Add"
        Trash = "Trash"

    fake.CheckMenuItem = CheckMenuItem
    fake.IconMenuItem = IconMenuItem
    fake.MenuItem = MenuItem
    fake.PredefinedMenuItem = PredefinedMenuItem
    fake.Submenu = Submenu
    fake.Menu = Menu
    fake.ContextMenu = ContextMenu
    fake.NativeIcon = NativeIcon
    return fake


def _install_fake_image_module():
    fake = types.ModuleType("pytauri.image")

    class Image:
        def __init__(self, raw, w, h):
            self.raw = raw
            self.w = w
            self.h = h

    fake.Image = Image
    return fake


class TestMenuBuilders:
    def test_build_predefined_separator(self, ipc):
        ipc.app_handle = MagicMock()
        with patch.dict(sys.modules, {"pytauri.menu": _install_fake_menu_module()}):
            item = ipc._build_menu_item({"kind": "predefined"})
        assert item is not None

    def test_build_predefined_with_text(self, ipc):
        ipc.app_handle = MagicMock()
        with patch.dict(sys.modules, {"pytauri.menu": _install_fake_menu_module()}):
            item = ipc._build_menu_item({"kind": "predefined", "kind_name": "copy", "text": "Copy"})
        assert item is not None

    def test_build_predefined_unknown_kind(self, ipc):
        ipc.app_handle = MagicMock()
        with patch.dict(sys.modules, {"pytauri.menu": _install_fake_menu_module()}):
            # Unknown kind_name falls back to ``separator``.
            item = ipc._build_menu_item({"kind": "predefined", "kind_name": "this_does_not_exist"})
        assert item is not None

    def test_build_check_item(self, ipc):
        ipc.app_handle = MagicMock()
        with patch.dict(sys.modules, {"pytauri.menu": _install_fake_menu_module()}):
            item = ipc._build_menu_item(
                {
                    "kind": "check",
                    "id": "c1",
                    "text": "Check",
                    "checked": True,
                    "accelerator": "CmdOrCtrl+K",
                }
            )
        assert ipc.menu_items["c1"] is item

    def test_build_icon_with_native_icon(self, ipc):
        ipc.app_handle = MagicMock()
        with patch.dict(sys.modules, {"pytauri.menu": _install_fake_menu_module()}):
            item = ipc._build_menu_item(
                {
                    "kind": "icon",
                    "id": "i1",
                    "text": "I",
                    "native_icon": "Add",
                }
            )
        assert ipc.menu_items["i1"] is item

    def test_build_icon_unknown_native_icon_falls_through(self, ipc):
        ipc.app_handle = MagicMock()
        with (
            patch.dict(sys.modules, {"pytauri.menu": _install_fake_menu_module()}),
            patch.dict(sys.modules, {"pytauri.image": _install_fake_image_module()}),
        ):
            # Unknown name → falls through to icon-bytes path; with no
            # bytes, icon_image is None and we pass to with_id with None.
            item = ipc._build_menu_item(
                {
                    "kind": "icon",
                    "id": "i2",
                    "text": "I",
                    "native_icon": "DoesNotExist",
                }
            )
        assert ipc.menu_items["i2"] is item

    def test_build_icon_with_bytes(self, ipc):
        ipc.app_handle = MagicMock()
        import base64

        b64 = base64.b64encode(b"\x00" * 16).decode("ascii")
        with (
            patch.dict(sys.modules, {"pytauri.menu": _install_fake_menu_module()}),
            patch.dict(sys.modules, {"pytauri.image": _install_fake_image_module()}),
        ):
            item = ipc._build_menu_item(
                {
                    "kind": "icon",
                    "id": "i3",
                    "text": "I",
                    "icon": b64,
                    "icon_width": 8,
                    "icon_height": 8,
                }
            )
        assert ipc.menu_items["i3"] is item

    def test_build_submenu(self, ipc):
        ipc.app_handle = MagicMock()
        with patch.dict(sys.modules, {"pytauri.menu": _install_fake_menu_module()}):
            item = ipc._build_menu_item(
                {
                    "kind": "submenu",
                    "id": "s1",
                    "text": "Sub",
                    "items": [{"kind": "item", "id": "child", "text": "C"}],
                }
            )
        assert ipc.menu_items["s1"] is item
        assert "child" in ipc.menu_items

    def test_build_default_menu_item(self, ipc):
        ipc.app_handle = MagicMock()
        with patch.dict(sys.modules, {"pytauri.menu": _install_fake_menu_module()}):
            item = ipc._build_menu_item({"kind": "item", "id": "x", "text": "X"})
        assert ipc.menu_items["x"] is item


class TestMenuOps:
    def test_menu_create_no_app(self, ipc, capture_stdout):
        ipc.app_handle = None
        with patch.object(sys, "stderr", io.StringIO()):
            ipc.menu_create({"menu_id": "m"})
        assert "error" in capture_stdout.buf.getvalue()

    def test_menu_create_success(self, ipc, capture_stdout):
        ipc.app_handle = MagicMock()
        with patch.dict(sys.modules, {"pytauri.menu": _install_fake_menu_module()}):
            ipc.menu_create({"menu_id": "m1", "items": [{"kind": "item", "id": "x", "text": "X"}]})
        out = json.loads(capture_stdout.buf.getvalue())
        assert out["menu_id"] == "m1"

    def test_menu_create_raises(self, ipc, capture_stdout):
        ipc.app_handle = MagicMock()
        with (
            patch.dict(sys.modules, {"pytauri.menu": _install_fake_menu_module()}),
            patch.object(ipc, "_build_menu_item", side_effect=RuntimeError("boom")),
            patch.object(sys, "stderr", io.StringIO()),
        ):
            ipc.menu_create({"menu_id": "m1", "items": [{}]})
        assert "Failed to create menu" in capture_stdout.buf.getvalue()

    def test_menu_set_unknown(self, ipc, capture_stdout):
        with patch.object(sys, "stderr", io.StringIO()):
            ipc.menu_set({"menu_id": "x"})
        assert "Menu not found" in capture_stdout.buf.getvalue()

    def test_menu_set_app(self, ipc):
        ipc.app_handle = MagicMock()
        ipc.menus["m"] = MagicMock()
        ipc.menu_set({"menu_id": "m", "target": "app"})
        ipc.app_handle.set_menu.assert_called_once()

    def test_menu_set_window_not_found(self, ipc, capture_stdout):
        ipc.app_handle = None
        ipc.menus["m"] = MagicMock()
        with patch.object(sys, "stderr", io.StringIO()):
            ipc.menu_set({"menu_id": "m", "target": "window", "label": "g"})
        assert "error" in capture_stdout.buf.getvalue()

    def test_menu_set_window(self, ipc):
        win = MagicMock()
        ipc.windows["a"] = win
        ipc.menus["m"] = MagicMock()
        ipc.menu_set({"menu_id": "m", "target": "window", "label": "a"})
        win.set_menu.assert_called_once()

    def test_menu_set_raises(self, ipc, capture_stdout):
        ipc.app_handle = MagicMock()
        ipc.app_handle.set_menu.side_effect = RuntimeError("boom")
        ipc.menus["m"] = MagicMock()
        with patch.object(sys, "stderr", io.StringIO()):
            ipc.menu_set({"menu_id": "m", "target": "app"})
        assert "menu_set failed" in capture_stdout.buf.getvalue()

    def test_menu_popup_unknown_menu(self, ipc, capture_stdout):
        with patch.object(sys, "stderr", io.StringIO()):
            ipc.menu_popup({"menu_id": "x"})
        assert "Menu not found" in capture_stdout.buf.getvalue()

    def test_menu_popup_window_not_found(self, ipc, capture_stdout):
        ipc.menus["m"] = MagicMock()
        ipc.app_handle = None
        with patch.object(sys, "stderr", io.StringIO()):
            ipc.menu_popup({"menu_id": "m", "label": "g"})
        assert "error" in capture_stdout.buf.getvalue()

    def test_menu_popup_no_position(self, ipc):
        ipc.menus["m"] = MagicMock()
        ipc.windows["a"] = MagicMock()
        with patch.dict(sys.modules, {"pytauri.menu": _install_fake_menu_module()}):
            ipc.menu_popup({"menu_id": "m", "label": "a"})

    def test_menu_popup_with_position(self, ipc):
        ipc.menus["m"] = MagicMock()
        ipc.windows["a"] = MagicMock()
        with patch.dict(sys.modules, {"pytauri.menu": _install_fake_menu_module()}):
            ipc.menu_popup({"menu_id": "m", "label": "a", "position": {"x": 1, "y": 2}})

    def test_menu_popup_raises(self, ipc, capture_stdout):
        ipc.menus["m"] = MagicMock()
        ipc.windows["a"] = MagicMock()

        # Make ContextMenu.popup raise
        fake_menu = _install_fake_menu_module()

        def _raise(*a, **k):
            raise RuntimeError("boom")

        fake_menu.ContextMenu.popup = _raise
        with (
            patch.dict(sys.modules, {"pytauri.menu": fake_menu}),
            patch.object(sys, "stderr", io.StringIO()),
        ):
            ipc.menu_popup({"menu_id": "m", "label": "a"})
        assert "menu_popup failed" in capture_stdout.buf.getvalue()

    @pytest.mark.parametrize(
        "op",
        [
            "append",
            "prepend",
            "insert",
            "remove",
            "set_text",
            "set_enabled",
            "set_checked",
            "set_accelerator",
            "set_icon",
        ],
    )
    def test_menu_update_operations(self, ipc, op):
        ipc.app_handle = MagicMock()
        # Build a real menu via fake module
        with patch.dict(sys.modules, {"pytauri.menu": _install_fake_menu_module()}):
            ipc.menu_create({"menu_id": "m", "items": []})
        # Pre-register a menu_item so id-based ops work
        fake_item = MagicMock()
        ipc.menu_items["x"] = fake_item

        cmd = {"menu_id": "m", "operation": op, "item_id": "x"}
        if op in ("append", "prepend", "insert"):
            cmd["item_data"] = {"kind": "item", "id": "y", "text": "Y"}
            with patch.dict(sys.modules, {"pytauri.menu": _install_fake_menu_module()}):
                ipc.menu_update(cmd)
        elif op == "set_icon":
            import base64

            cmd["icon"] = base64.b64encode(b"\x00" * 16).decode()
            with (
                patch.dict(sys.modules, {"pytauri.image": _install_fake_image_module()}),
            ):
                ipc.menu_update(cmd)
        else:
            ipc.menu_update(cmd)

    def test_menu_update_set_icon_clear(self, ipc):
        ipc.app_handle = MagicMock()
        with patch.dict(sys.modules, {"pytauri.menu": _install_fake_menu_module()}):
            ipc.menu_create({"menu_id": "m", "items": []})
        fake_item = MagicMock()
        ipc.menu_items["x"] = fake_item
        # No icon → calls set_icon(None)
        ipc.menu_update({"menu_id": "m", "operation": "set_icon", "item_id": "x"})
        fake_item.set_icon.assert_called_with(None)

    def test_menu_update_unknown_menu(self, ipc, capture_stdout):
        with patch.object(sys, "stderr", io.StringIO()):
            ipc.menu_update({"menu_id": "missing", "operation": "append"})
        assert "Menu not found" in capture_stdout.buf.getvalue()

    def test_menu_update_unknown_operation(self, ipc, capture_stdout):
        ipc.app_handle = MagicMock()
        with patch.dict(sys.modules, {"pytauri.menu": _install_fake_menu_module()}):
            ipc.menu_create({"menu_id": "m", "items": []})
        with patch.object(sys, "stderr", io.StringIO()):
            ipc.menu_update({"menu_id": "m", "operation": "nope"})
        assert "Unknown menu_update operation" in capture_stdout.buf.getvalue()

    def test_menu_update_remove_unknown_item_id(self, ipc):
        ipc.app_handle = MagicMock()
        with patch.dict(sys.modules, {"pytauri.menu": _install_fake_menu_module()}):
            ipc.menu_create({"menu_id": "m", "items": []})
        # Item not in self.menu_items → branch where item is falsy
        ipc.menu_update({"menu_id": "m", "operation": "remove", "item_id": "missing"})

    def test_menu_update_set_text_no_item(self, ipc):
        ipc.app_handle = MagicMock()
        with patch.dict(sys.modules, {"pytauri.menu": _install_fake_menu_module()}):
            ipc.menu_create({"menu_id": "m", "items": []})
        # Item not in self.menu_items
        ipc.menu_update({"menu_id": "m", "operation": "set_text", "item_id": "missing"})

    def test_menu_update_raises(self, ipc, capture_stdout):
        ipc.app_handle = MagicMock()
        with patch.dict(sys.modules, {"pytauri.menu": _install_fake_menu_module()}):
            ipc.menu_create({"menu_id": "m", "items": []})
        with (
            patch.object(ipc, "_build_menu_item", side_effect=RuntimeError("boom")),
            patch.object(sys, "stderr", io.StringIO()),
        ):
            ipc.menu_update({"menu_id": "m", "operation": "append", "item_data": {}})
        assert "menu_update failed" in capture_stdout.buf.getvalue()

    def test_menu_remove_existing(self, ipc):
        ipc.menus["m"] = MagicMock()
        ipc.menu_remove({"menu_id": "m"})
        assert "m" not in ipc.menus

    def test_menu_remove_missing(self, ipc):
        # Just logs; no error raised.
        ipc.menu_remove({"menu_id": "missing"})


# ──────────────────────────────────────────────────────────────────────
# Tray helpers
# ──────────────────────────────────────────────────────────────────────


def _install_fake_tray_module():
    fake = types.ModuleType("pytauri.tray")

    class TrayIcon:
        @classmethod
        def with_id(cls, app, tid):
            return MagicMock()

    class _ButtonState:
        def __init__(self, name):
            self._name = name

        def __str__(self):
            return f"State.{self._name}"

    class _Button:
        def __init__(self, name):
            self._name = name

        def __str__(self):
            return f"Button.{self._name}"

    class TrayIconEvent:
        class Click:
            def __init__(self, button="Left", state="Pressed", position=(1, 2)):
                self.button = _Button(button)
                self.button_state = _ButtonState(state)
                self.position = position

        class DoubleClick:
            def __init__(self, button="Left", position=(1, 2)):
                self.button = _Button(button)
                self.position = position

        class Enter:
            def __init__(self, position=(1, 2)):
                self.position = position

        class Leave:
            def __init__(self, position=(1, 2)):
                self.position = position

        class Move:
            def __init__(self, position=(1, 2)):
                self.position = position

    fake.TrayIcon = TrayIcon
    fake.TrayIconEvent = TrayIconEvent
    return fake


class TestTrayHelpers:
    def test_apply_tray_icon_from_bytes(self, ipc):
        import base64

        ipc.app_handle = MagicMock()
        tray = MagicMock()
        with patch.dict(sys.modules, {"pytauri.image": _install_fake_image_module()}):
            ipc._apply_tray_icon(
                tray,
                {
                    "icon": base64.b64encode(b"\x00" * 16).decode(),
                    "icon_width": 16,
                    "icon_height": 16,
                },
            )
        tray.set_icon.assert_called_once()

    def test_apply_tray_icon_default(self, ipc):
        ipc.app_handle = MagicMock()
        ipc.app_handle.default_window_icon.return_value = MagicMock()
        tray = MagicMock()
        ipc._apply_tray_icon(tray, {})
        tray.set_icon.assert_called_once()

    def test_apply_tray_icon_no_default(self, ipc):
        ipc.app_handle = MagicMock()
        ipc.app_handle.default_window_icon.return_value = None
        tray = MagicMock()
        ipc._apply_tray_icon(tray, {})
        tray.set_icon.assert_not_called()

    def test_apply_tray_menu(self, ipc):
        ipc.app_handle = MagicMock()
        tray = MagicMock()
        with patch.dict(sys.modules, {"pytauri.menu": _install_fake_menu_module()}):
            ipc._apply_tray_menu(
                tray,
                "T",
                {
                    "id": "tm",
                    "items": [
                        {"kind": "item", "id": "i1", "text": "X"},
                        {"kind": "item", "id": "", "text": "no_id"},
                    ],
                },
            )
        tray.set_menu.assert_called_once()
        assert "i1" in ipc.tray_menu_items

    def test_tray_create_no_app(self, ipc, capture_stdout):
        ipc.app_handle = None
        with patch.object(sys, "stderr", io.StringIO()):
            ipc.tray_create({"tray_id": "t"})
        assert "App not ready" in capture_stdout.buf.getvalue()

    def test_tray_create_full(self, ipc, capture_stdout):
        ipc.app_handle = MagicMock()
        # Pre-existing tray to exercise the cleanup branch
        old_tray = MagicMock()
        ipc.trays["t"] = old_tray
        with (
            patch.dict(sys.modules, {"pytauri.tray": _install_fake_tray_module()}),
            patch.dict(sys.modules, {"pytauri.menu": _install_fake_menu_module()}),
        ):
            ipc.tray_create(
                {
                    "tray_id": "t",
                    "tooltip": "tip",
                    "title": "title",
                    "menu": {"id": "m", "items": [{"kind": "item", "id": "x", "text": "X"}]},
                    "menu_on_left_click": False,
                    "request_id": "r",
                }
            )
        msg_lines = [ln for ln in capture_stdout.buf.getvalue().splitlines() if ln]
        assert any('"success": true' in ln for ln in msg_lines)
        # Trigger registered callbacks to cover their bodies.
        tray = ipc.trays["t"]
        # The on_tray_icon_event lambda was passed to tray.on_tray_icon_event
        on_tray_call = tray.on_tray_icon_event.call_args
        on_tray_handler = on_tray_call.args[0]
        with patch.dict(sys.modules, {"pytauri.tray": _install_fake_tray_module()}):
            from pytauri.tray import TrayIconEvent

            on_tray_handler(MagicMock(), TrayIconEvent.Click())
        # The on_menu_event handler
        on_menu_handler = tray.on_menu_event.call_args.args[0]
        on_menu_handler(MagicMock(), "menu-item-id")

    def test_tray_create_old_set_visible_raises(self, ipc):
        ipc.app_handle = MagicMock()
        old = MagicMock()
        old.set_visible.side_effect = RuntimeError("boom")
        ipc.trays["t"] = old
        with patch.dict(sys.modules, {"pytauri.tray": _install_fake_tray_module()}):
            ipc.tray_create({"tray_id": "t"})
        # Just make sure no exception escapes.

    def test_tray_create_raises(self, ipc, capture_stdout):
        ipc.app_handle = MagicMock()
        # Make TrayIcon.with_id raise
        fake = _install_fake_tray_module()

        def _raise(app, tid):
            raise RuntimeError("boom")

        fake.TrayIcon.with_id = classmethod(lambda cls, app, tid: _raise(app, tid))
        with (
            patch.dict(sys.modules, {"pytauri.tray": fake}),
            patch.object(sys, "stderr", io.StringIO()),
        ):
            ipc.tray_create({"tray_id": "t", "request_id": "r"})
        out = capture_stdout.buf.getvalue()
        assert "error" in out.lower()

    def test_tray_update_unknown(self, ipc, capture_stdout):
        with patch.object(sys, "stderr", io.StringIO()):
            ipc.tray_update({"tray_id": "missing"})
        assert "Tray not found" in capture_stdout.buf.getvalue()

    def test_tray_update_all_fields(self, ipc):
        import base64

        ipc.app_handle = MagicMock()
        tray = MagicMock()
        ipc.trays["t"] = tray
        with (
            patch.dict(sys.modules, {"pytauri.image": _install_fake_image_module()}),
            patch.dict(sys.modules, {"pytauri.menu": _install_fake_menu_module()}),
        ):
            ipc.tray_update(
                {
                    "tray_id": "t",
                    "tooltip": "tip",
                    "title": "title",
                    "visible": True,
                    "menu_on_left_click": False,
                    "icon": base64.b64encode(b"\x00" * 16).decode(),
                    "icon_width": 16,
                    "icon_height": 16,
                    "menu": {
                        "id": "tm",
                        "items": [
                            {"kind": "item", "id": "i1", "text": "X"},
                            {"kind": "item", "id": "", "text": "no_id"},
                        ],
                    },
                }
            )
        tray.set_tooltip.assert_called_once_with("tip")
        tray.set_title.assert_called_once_with("title")
        tray.set_visible.assert_called_once_with(True)
        tray.set_show_menu_on_left_click.assert_called_once_with(False)
        tray.set_icon.assert_called_once()
        tray.set_menu.assert_called_once()

    def test_tray_update_raises(self, ipc, capture_stdout):
        tray = MagicMock()
        tray.set_tooltip.side_effect = RuntimeError("boom")
        ipc.trays["t"] = tray
        with patch.object(sys, "stderr", io.StringIO()):
            ipc.tray_update({"tray_id": "t", "tooltip": "x"})
        assert "tray_update failed" in capture_stdout.buf.getvalue()

    def test_tray_remove_missing(self, ipc, capture_stdout):
        ipc.tray_remove({"tray_id": "missing", "request_id": "r"})
        msg = json.loads(capture_stdout.buf.getvalue())
        assert msg["success"] is False

    def test_tray_remove_missing_no_request_id(self, ipc, capture_stdout):
        ipc.tray_remove({"tray_id": "missing"})
        msg = json.loads(capture_stdout.buf.getvalue())
        assert msg["success"] is False
        assert "request_id" not in msg

    def test_tray_remove_existing(self, ipc, capture_stdout):
        tray = MagicMock()
        ipc.trays["t"] = tray
        ipc.tray_remove({"tray_id": "t", "request_id": "r"})
        msgs = [json.loads(ln) for ln in capture_stdout.buf.getvalue().splitlines() if ln]
        assert any(m.get("success") is True for m in msgs)
        assert "t" not in ipc.trays

    def test_tray_remove_set_visible_raises(self, ipc, capture_stdout):
        tray = MagicMock()
        tray.set_visible.side_effect = RuntimeError("boom")
        ipc.trays["t"] = tray
        ipc.tray_remove({"tray_id": "t"})
        msgs = [json.loads(ln) for ln in capture_stdout.buf.getvalue().splitlines() if ln]
        assert any(m.get("success") is True for m in msgs)


# ──────────────────────────────────────────────────────────────────────
# _handle_tray_event (each TrayIconEvent variant)
# ──────────────────────────────────────────────────────────────────────


class TestHandleTrayEvent:
    def test_click(self, ipc, capture_stdout):
        with patch.dict(sys.modules, {"pytauri.tray": _install_fake_tray_module()}):
            from pytauri.tray import TrayIconEvent

            ipc._handle_tray_event("t", TrayIconEvent.Click())
        msg = json.loads(capture_stdout.buf.getvalue())
        assert msg["event_type"] == "tray:click"
        assert msg["data"]["button"] == "left"

    def test_double_click(self, ipc, capture_stdout):
        with patch.dict(sys.modules, {"pytauri.tray": _install_fake_tray_module()}):
            from pytauri.tray import TrayIconEvent

            ipc._handle_tray_event("t", TrayIconEvent.DoubleClick())
        msg = json.loads(capture_stdout.buf.getvalue())
        assert msg["event_type"] == "tray:double-click"

    def test_enter(self, ipc, capture_stdout):
        with patch.dict(sys.modules, {"pytauri.tray": _install_fake_tray_module()}):
            from pytauri.tray import TrayIconEvent

            ipc._handle_tray_event("t", TrayIconEvent.Enter())
        msg = json.loads(capture_stdout.buf.getvalue())
        assert msg["event_type"] == "tray:enter"

    def test_leave(self, ipc, capture_stdout):
        with patch.dict(sys.modules, {"pytauri.tray": _install_fake_tray_module()}):
            from pytauri.tray import TrayIconEvent

            ipc._handle_tray_event("t", TrayIconEvent.Leave())
        msg = json.loads(capture_stdout.buf.getvalue())
        assert msg["event_type"] == "tray:leave"

    def test_move(self, ipc, capture_stdout):
        with patch.dict(sys.modules, {"pytauri.tray": _install_fake_tray_module()}):
            from pytauri.tray import TrayIconEvent

            ipc._handle_tray_event("t", TrayIconEvent.Move())
        msg = json.loads(capture_stdout.buf.getvalue())
        assert msg["event_type"] == "tray:move"

    def test_unknown_event(self, ipc, capture_stdout):
        # Unrelated object type — falls through (nothing emitted).
        with patch.dict(sys.modules, {"pytauri.tray": _install_fake_tray_module()}):
            ipc._handle_tray_event("t", object())
        assert capture_stdout.buf.getvalue() == ""


# ──────────────────────────────────────────────────────────────────────
# stdin_reader
# ──────────────────────────────────────────────────────────────────────


class TestStdinReader:
    def test_reads_and_dispatches(self, ipc):
        # Feed a single command then the iterator stops.
        cmds = ['{"action": "show", "label": "a"}\n']
        with (
            patch.object(_main_mod.sys, "stdin", iter(cmds)),
            patch.object(ipc, "show_window") as mock_show,
        ):
            _main_mod.stdin_reader(ipc)
        mock_show.assert_called_once()

    def test_blank_line_skipped(self, ipc):
        cmds = ["\n", "   \n"]
        with patch.object(_main_mod.sys, "stdin", iter(cmds)):
            _main_mod.stdin_reader(ipc)
        # Nothing crashed.

    def test_response_consumed_by_handle_response(self, ipc):
        ipc._pending_requests["r"] = threading.Event()
        cmds = ['{"request_id": "r", "value": 1}\n']
        with patch.object(_main_mod.sys, "stdin", iter(cmds)):
            _main_mod.stdin_reader(ipc)
        # The response was consumed; pending-response map populated.
        assert "r" in ipc._pending_responses

    def test_invalid_json(self, ipc, capture_stdout):
        cmds = ["not json\n"]
        with (
            patch.object(_main_mod.sys, "stdin", iter(cmds)),
            patch.object(sys, "stderr", io.StringIO()),
        ):
            _main_mod.stdin_reader(ipc)
        assert "Invalid JSON" in capture_stdout.buf.getvalue()

    def test_handler_raises(self, ipc, capture_stdout):
        cmds = ['{"action": "show", "label": "a"}\n']
        with (
            patch.object(_main_mod.sys, "stdin", iter(cmds)),
            patch.object(ipc, "show_window", side_effect=RuntimeError("boom")),
            patch.object(sys, "stderr", io.StringIO()),
        ):
            _main_mod.stdin_reader(ipc)
        assert "Command error" in capture_stdout.buf.getvalue()

    def test_outer_exception_logged(self, ipc):
        # Make sys.stdin iteration itself raise.
        class _BadStdin:
            def __iter__(self):
                raise RuntimeError("stdin lost")

        with (
            patch.object(_main_mod.sys, "stdin", _BadStdin()),
            patch.object(sys, "stderr", io.StringIO()),
        ):
            _main_mod.stdin_reader(ipc)

    def test_running_false_breaks(self, ipc):
        # quit handler will set ipc.running = False, then loop must exit.
        cmds = ['{"action": "quit"}\n', '{"action": "show"}\n']
        with (
            patch.object(_main_mod.sys, "stdin", iter(cmds)),
            patch.object(ipc, "quit", side_effect=lambda: setattr(ipc, "running", False)),
            patch.object(ipc, "show_window") as mock_show,
        ):
            _main_mod.stdin_reader(ipc)
        # Second command must NOT be dispatched
        mock_show.assert_not_called()


# ──────────────────────────────────────────────────────────────────────
# _handle_ready_event / _handle_close_requested
# ──────────────────────────────────────────────────────────────────────


class TestReadyAndCloseHandlers:
    def test_handle_ready_with_main_window(self, ipc):
        app_handle = MagicMock()
        main_win = MagicMock()
        with (
            patch.object(_main_mod, "_set_macos_dock_icon"),
            patch.object(_main_mod.Manager, "get_webview_window", return_value=main_win),
            patch.object(ipc, "send_ready"),
        ):
            _main_mod._handle_ready_event(ipc, app_handle)
        assert ipc.app_handle is app_handle
        assert ipc.windows["main"] is main_win

    def test_handle_ready_no_main_window(self, ipc):
        app_handle = MagicMock()
        with (
            patch.object(_main_mod, "_set_macos_dock_icon"),
            patch.object(_main_mod.Manager, "get_webview_window", return_value=None),
            patch.object(ipc, "send_ready"),
        ):
            _main_mod._handle_ready_event(ipc, app_handle)
        assert "main" not in ipc.windows

    def test_close_requested_single_mode_hide(self, ipc, capture_stdout):
        win = MagicMock()
        ipc.windows["a"] = win
        we = MagicMock()
        with patch.object(_main_mod, "WINDOW_MODE", "single"):
            _main_mod._handle_close_requested(ipc, MagicMock(), "a", we)
        win.hide.assert_called_once()
        msg = json.loads(capture_stdout.buf.getvalue())
        assert msg["event_type"] == "window:hidden"

    def test_close_requested_new_mode_destroy(self, ipc, capture_stdout):
        win = MagicMock()
        ipc.windows["a"] = win
        we = MagicMock()
        with patch.object(_main_mod, "WINDOW_MODE", "new"):
            _main_mod._handle_close_requested(ipc, MagicMock(), "a", we)
        win.destroy.assert_called_once()
        msg = json.loads(capture_stdout.buf.getvalue())
        assert msg["event_type"] == "window:closed"
        assert "a" in ipc._destroyed_windows

    def test_close_requested_multi_mode_close_setting(self, ipc, capture_stdout):
        win = MagicMock()
        ipc.windows["a"] = win
        we = MagicMock()
        with (
            patch.object(_main_mod, "WINDOW_MODE", "multi"),
            patch.object(_main_mod, "ON_WINDOW_CLOSE", "close"),
        ):
            _main_mod._handle_close_requested(ipc, MagicMock(), "a", we)
        win.destroy.assert_called_once()

    def test_close_requested_multi_mode_hide_setting(self, ipc, capture_stdout):
        win = MagicMock()
        ipc.windows["a"] = win
        we = MagicMock()
        with (
            patch.object(_main_mod, "WINDOW_MODE", "multi"),
            patch.object(_main_mod, "ON_WINDOW_CLOSE", "hide"),
        ):
            _main_mod._handle_close_requested(ipc, MagicMock(), "a", we)
        win.hide.assert_called_once()

    def test_close_requested_window_via_manager(self, ipc, capture_stdout):
        we = MagicMock()
        # No window in cache → Manager lookup
        win = MagicMock()
        with (
            patch.object(_main_mod, "WINDOW_MODE", "new"),
            patch.object(_main_mod.Manager, "get_webview_window", return_value=win),
        ):
            _main_mod._handle_close_requested(ipc, MagicMock(), "g", we)
        win.destroy.assert_called_once()

    def test_close_requested_no_window_at_all(self, ipc, capture_stdout):
        we = MagicMock()
        with (
            patch.object(_main_mod, "WINDOW_MODE", "new"),
            patch.object(_main_mod.Manager, "get_webview_window", return_value=None),
        ):
            _main_mod._handle_close_requested(ipc, MagicMock(), "g", we)
        # No exception; no window destroyed; just sends event.

    def test_close_requested_destroy_branch_no_window(self, ipc, capture_stdout):
        # Window goes in then gets removed.  Tests the ``if label in ipc.windows`` branch.
        ipc.windows["a"] = MagicMock()
        we = MagicMock()
        with (
            patch.object(_main_mod, "WINDOW_MODE", "new"),
            patch.object(_main_mod.Manager, "get_webview_window", return_value=None),
        ):
            _main_mod._handle_close_requested(ipc, MagicMock(), "a", we)
        assert "a" not in ipc.windows


# ──────────────────────────────────────────────────────────────────────
# _register_custom_commands
# ──────────────────────────────────────────────────────────────────────


class TestRegisterCustomCommands:
    def test_no_commands(self, ipc):
        commands = MagicMock()
        _main_mod._register_custom_commands(commands, ipc, [])
        commands.set_command.assert_not_called()

    def test_registers_each_command(self, ipc):
        commands = MagicMock()
        _main_mod._register_custom_commands(commands, ipc, ["foo", "bar"])
        names = [call.args[0] for call in commands.set_command.call_args_list]
        assert names == ["foo", "bar"]

    def test_forwarder_invokes_send_request(self, ipc):
        commands = MagicMock()
        _main_mod._register_custom_commands(commands, ipc, ["foo"])
        forwarder = commands.set_command.call_args.args[1]
        # Drive the async forwarder synchronously.
        import asyncio

        from pydantic import BaseModel

        class _Body(BaseModel):
            model_config = {"extra": "allow"}

        body = _Body.model_validate({"x": 1})
        with patch.object(ipc, "send_request_and_wait", return_value={"ok": True}) as mock_swap:
            res = asyncio.run(forwarder(body))
        assert res == {"ok": True}
        mock_swap.assert_called_once()
        sent_msg = mock_swap.call_args.args[0]
        assert sent_msg["type"] == "custom_command"
        assert sent_msg["command"] == "foo"


# ──────────────────────────────────────────────────────────────────────
# main()
# ──────────────────────────────────────────────────────────────────────


class _FakePortalCtx:
    """Async context manager that yields a fake portal."""

    def __init__(self):
        self.portal = MagicMock()
        self.portal.call.return_value = MagicMock()
        # wrap_async_context_manager returns an object with __enter__/__exit__
        cm = MagicMock()
        cm.__enter__ = lambda self_: None
        cm.__exit__ = lambda self_, *a: False
        self.portal.wrap_async_context_manager.return_value = cm

    def __enter__(self):
        return self.portal

    def __exit__(self, *a):
        return False


class TestMainEntrypoint:
    def _setup_main_environment(self, monkeypatch, app_run_callback=None):
        """Patch out everything the main() function depends on."""
        # Disable SIGINT setup
        monkeypatch.setattr(_main_mod.signal, "signal", lambda *a, **k: None)

        # Stub out register_commands (imported inside main)
        fake_commands_mod = types.ModuleType("pywry.commands")
        fake_commands_mod.register_commands = lambda c: None
        # pywry.commands is a package; we patch submodule import via sys.modules
        monkeypatch.setitem(sys.modules, "pywry.commands", fake_commands_mod)

        # Replace start_blocking_portal with our context manager
        monkeypatch.setattr(_main_mod, "start_blocking_portal", lambda *a, **k: _FakePortalCtx())

        # Replace create_task_group / context_factory / builder_factory
        monkeypatch.setattr(_main_mod, "create_task_group", MagicMock())
        monkeypatch.setattr(_main_mod, "context_factory", lambda d: MagicMock())

        fake_app = MagicMock()
        if app_run_callback is None:
            app_run_callback = lambda on_run: None  # noqa: E731
        fake_app.run.side_effect = app_run_callback
        fake_builder = MagicMock()
        fake_builder.build.return_value = fake_app
        monkeypatch.setattr(_main_mod, "builder_factory", lambda: fake_builder)

        # No real plugins
        monkeypatch.setattr(_main_mod, "_load_plugins", lambda names: [])
        # Commands() returns a stub
        fake_commands_obj = MagicMock()
        fake_commands_obj.generate_handler.return_value = lambda *a, **k: None
        monkeypatch.setattr(_main_mod, "Commands", lambda: fake_commands_obj)

        # Avoid spawning a real reader thread.
        class _FakeThread:
            def __init__(self, *a, **k):
                pass

            def start(self):
                pass

        monkeypatch.setattr(_main_mod.threading, "Thread", _FakeThread)

        return fake_app

    def test_main_runs_and_returns_zero(self, monkeypatch):
        called = []
        self._setup_main_environment(
            monkeypatch, app_run_callback=lambda on_run: called.append("ok")
        )
        rc = _main_mod.main()
        assert rc == 0
        assert called == ["ok"]

    def test_main_with_extra_capabilities(self, monkeypatch, tmp_path):
        # Build a minimal source dir
        src = tmp_path / "src"
        src.mkdir()
        (src / "capabilities").mkdir()
        # Patch __file__ so src_dir = tmp_path src
        monkeypatch.setattr(
            _main_mod,
            "__file__",
            str(src / "__main__.py"),
            raising=False,
        )
        monkeypatch.setenv("PYWRY_EXTRA_CAPABILITIES", "shell:allow-execute")
        self._setup_main_environment(monkeypatch)
        rc = _main_mod.main()
        assert rc == 0

    def test_main_with_custom_commands(self, monkeypatch):
        monkeypatch.setenv("PYWRY_CUSTOM_COMMANDS", "foo,bar")
        self._setup_main_environment(monkeypatch)
        rc = _main_mod.main()
        assert rc == 0

    def test_main_handles_exception(self, monkeypatch):
        # Make portal raise inside the with-block
        def _raise(*a, **k):
            raise RuntimeError("boom")

        self._setup_main_environment(monkeypatch)
        monkeypatch.setattr(_main_mod, "start_blocking_portal", _raise)
        with patch.object(sys, "stderr", io.StringIO()):
            rc = _main_mod.main()
        assert rc == 1

    def test_on_run_ready_event(self, monkeypatch):
        captured = {}

        def app_run(on_run):
            captured["on_run"] = on_run
            from pytauri import RunEvent

            # Drive a Ready event
            ready = RunEvent.Ready()
            on_run(MagicMock(), ready)

        self._setup_main_environment(monkeypatch, app_run_callback=app_run)
        with patch.object(_main_mod, "_handle_ready_event") as mock_ready:
            _main_mod.main()
        mock_ready.assert_called_once()

    def test_on_run_exit_requested_running(self, monkeypatch):
        from pytauri import RunEvent

        def app_run(on_run):
            ev = MagicMock(spec=RunEvent.ExitRequested)
            ev.api = MagicMock()
            # Force isinstance(ev, RunEvent.ExitRequested) to be True via spec.
            on_run(MagicMock(), ev)

        self._setup_main_environment(monkeypatch, app_run_callback=app_run)
        # ipc.running default is True
        rc = _main_mod.main()
        assert rc == 0

    def test_on_run_close_requested(self, monkeypatch):
        from pytauri import RunEvent, WindowEvent

        def app_run(on_run):
            outer = MagicMock(spec=RunEvent.WindowEvent)
            outer.event = MagicMock(spec=WindowEvent.CloseRequested)
            outer.event.api = MagicMock()
            outer.label = "a"
            on_run(MagicMock(), outer)

        self._setup_main_environment(monkeypatch, app_run_callback=app_run)
        with patch.object(_main_mod, "_handle_close_requested") as mock_close:
            _main_mod.main()
        mock_close.assert_called_once()

    def test_on_run_destroyed(self, monkeypatch):
        from pytauri import RunEvent, WindowEvent

        def app_run(on_run):
            outer = MagicMock(spec=RunEvent.WindowEvent)
            outer.event = MagicMock(spec=WindowEvent.Destroyed)
            outer.label = "a"
            on_run(MagicMock(), outer)

        self._setup_main_environment(monkeypatch, app_run_callback=app_run)
        rc = _main_mod.main()
        assert rc == 0

    def test_on_run_menu_event_app_level(self, monkeypatch, capture_stdout):
        from pytauri import RunEvent

        def app_run(on_run):
            ev = MagicMock(spec=RunEvent.MenuEvent)
            ev._0 = "x"
            on_run(MagicMock(), ev)

        self._setup_main_environment(monkeypatch, app_run_callback=app_run)
        rc = _main_mod.main()
        assert rc == 0
        # An event was emitted to "main" (default).
        msgs = [json.loads(ln) for ln in capture_stdout.buf.getvalue().splitlines() if ln]
        assert any(m.get("event_type") == "menu:click" for m in msgs)

    def test_on_run_menu_event_tray_skipped(self, monkeypatch, capture_stdout):
        """When the menu-event item id is registered as a tray item the
        global ``RunEvent.MenuEvent`` handler must short-circuit (line 1799).

        We patch JsonIPC so the instance created inside ``main()`` already
        contains the id in ``tray_menu_items``.
        """
        from pytauri import RunEvent

        # Build a JsonIPC instance ahead of time and seed it.
        seeded = _main_mod.JsonIPC()
        seeded.tray_menu_items.add("tray-item")

        def app_run(on_run):
            ev = MagicMock(spec=RunEvent.MenuEvent)
            ev._0 = "tray-item"
            on_run(MagicMock(), ev)

        self._setup_main_environment(monkeypatch, app_run_callback=app_run)
        # Ensure the JsonIPC() factory inside main() returns our seeded instance
        monkeypatch.setattr(_main_mod, "JsonIPC", lambda: seeded)
        rc = _main_mod.main()
        assert rc == 0

    def test_on_run_tray_event_fallback(self, monkeypatch):
        from pytauri import RunEvent

        def app_run(on_run):
            ev = MagicMock(spec=RunEvent.TrayIconEvent)
            on_run(MagicMock(), ev)

        self._setup_main_environment(monkeypatch, app_run_callback=app_run)
        rc = _main_mod.main()
        assert rc == 0


# ──────────────────────────────────────────────────────────────────────
# Module __main__ guard
# ──────────────────────────────────────────────────────────────────────


class TestModuleEntry:
    def test_main_function_exists(self):
        assert callable(_main_mod.main)

    def test_module_has_required_globals(self):
        for attr in (
            "JsonIPC",
            "stdin_reader",
            "_load_plugins",
            "_stage_extra_capabilities",
            "_handle_ready_event",
            "_handle_close_requested",
            "_register_custom_commands",
            "log",
            "log_error",
            "DEBUG",
            "HEADLESS",
            "WINDOW_MODE",
            "ON_WINDOW_CLOSE",
            "_default_single_instance_callback",
        ):
            assert hasattr(_main_mod, attr), f"missing: {attr}"

    def test_run_entry_guard_exec(self):
        """Cover the ``if __name__ == '__main__': sys.exit(main())`` guard.

        Read the bottom two lines of ``__main__.py`` and exec them with
        ``__name__ = '__main__'``.  This exercises only the guard line
        without re-running the entire (heavy) module body.  We still
        compile against the real file path so coverage attributes the
        executed lines back to ``pywry/__main__.py``.
        """
        # Read the file, find the guard line, build a tiny snippet that
        # preserves source line numbers.
        source_lines = Path(_main_mod.__file__).read_text(encoding="utf-8").splitlines(True)
        # Find line index of ``if __name__ == "__main__":`` (1-indexed)
        guard_idx = None
        for i, line in enumerate(source_lines, start=1):
            if line.startswith('if __name__ == "__main__":'):
                guard_idx = i
                break
        assert guard_idx is not None, "guard not found"

        # Pad with blank lines so compiled line numbers match
        snippet = ("\n" * (guard_idx - 1)) + "".join(source_lines[guard_idx - 1 :])

        with patch.object(_main_mod, "main", return_value=0):
            ns = {"__name__": "__main__", "sys": sys, "main": _main_mod.main}
            with pytest.raises(SystemExit) as excinfo:
                exec(compile(snippet, _main_mod.__file__, "exec"), ns)
            assert excinfo.value.code == 0
