"""Tests for Tauri plugin integration.

Tests verify:
- Dialog and FS plugins are properly registered
- Dynamic plugin loading from config / env vars works
- Tauri APIs are available in the webview
- File save dialog functionality works
- Plugin capabilities are correctly configured
"""

# pylint: disable=unused-argument

# pylint: disable=unsubscriptable-object

import time

from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Any, TypeVar

import pytest

from pywry import runtime
from pywry.app import PyWry
from pywry.config import AVAILABLE_TAURI_PLUGINS, TAURI_PLUGIN_REGISTRY
from pywry.models import ThemeMode, WindowMode

# Import shared test utilities from tests.conftest
from tests.conftest import ReadyWaiter, show_and_wait_ready, wait_for_result


F = TypeVar("F", bound=Callable[..., Any])


def retry_on_subprocess_failure(max_attempts: int = 3, delay: float = 1.0) -> Callable[[F], F]:
    """Retry decorator for tests that may fail due to transient subprocess issues."""

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_error: Exception | None = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except (TimeoutError, AssertionError) as e:
                    last_error = e
                    if attempt < max_attempts - 1:
                        runtime.stop()
                        time.sleep(delay * (attempt + 1))
            raise last_error  # type: ignore[misc]

        return wrapper  # type: ignore[return-value]

    return decorator


# Note: cleanup_runtime fixture is now in conftest.py and auto-used


# =============================================================================
# Unit Tests - Plugin Configuration
# =============================================================================


class TestPluginCapabilities:
    """Tests for Tauri plugin capabilities configuration."""

    def test_capabilities_file_exists(self):
        """Capabilities file exists in the correct location."""
        capabilities_file = Path(__file__).parent.parent / "pywry" / "capabilities" / "default.toml"
        assert capabilities_file.exists(), f"Capabilities file not found at {capabilities_file}"

    def test_capabilities_has_dialog_permission(self):
        """Capabilities file includes dialog:default permission."""
        capabilities_file = Path(__file__).parent.parent / "pywry" / "capabilities" / "default.toml"
        content = capabilities_file.read_text(encoding="utf-8")
        assert "dialog:default" in content, "dialog:default permission not found in capabilities"

    def test_capabilities_has_fs_permission(self):
        """Capabilities file includes fs:default permission."""
        capabilities_file = Path(__file__).parent.parent / "pywry" / "capabilities" / "default.toml"
        content = capabilities_file.read_text(encoding="utf-8")
        assert "fs:default" in content, "fs:default permission not found in capabilities"

    def test_capabilities_has_pytauri_permission(self):
        """Capabilities file includes pytauri:default for IPC."""
        capabilities_file = Path(__file__).parent.parent / "pywry" / "capabilities" / "default.toml"
        content = capabilities_file.read_text(encoding="utf-8")
        assert "pytauri:default" in content, "pytauri:default permission not found in capabilities"

    def test_capabilities_has_all_plugin_permissions(self):
        """Capabilities file includes '<plugin>:default' for plugins that register manifests."""
        capabilities_file = Path(__file__).parent.parent / "pywry" / "capabilities" / "default.toml"
        content = capabilities_file.read_text(encoding="utf-8")
        # Plugin names in capabilities use hyphens (e.g. clipboard-manager, not clipboard_manager)
        # NOTE: persisted-scope and single-instance do NOT register Tauri capability
        # manifests, so they are intentionally excluded from default.toml.
        expected = {
            "autostart:default",
            "clipboard-manager:default",
            "deep-link:default",
            "dialog:default",
            "fs:default",
            "global-shortcut:default",
            "http:default",
            "notification:default",
            "opener:default",
            "os:default",
            "positioner:default",
            "process:default",
            "shell:default",
            "updater:default",
            "upload:default",
            "websocket:default",
            "window-state:default",
        }
        for perm in expected:
            assert perm in content, f"{perm} not found in capabilities"

        # These must NOT be in the file — they cause Tauri panics
        assert "persisted-scope:default" not in content
        assert "single-instance:default" not in content


class TestPluginRegistry:
    """Tests for the Tauri plugin registry constants."""

    def test_registry_has_19_entries(self):
        """TAURI_PLUGIN_REGISTRY contains exactly 19 plugins."""
        assert len(TAURI_PLUGIN_REGISTRY) == 19

    def test_available_plugins_matches_registry(self):
        """AVAILABLE_TAURI_PLUGINS matches registry keys."""
        assert frozenset(TAURI_PLUGIN_REGISTRY) == AVAILABLE_TAURI_PLUGINS

    def test_registry_values_are_tuples(self):
        """Each registry value is a (flag_name, module_path, init_method) tuple."""
        valid_methods = {"init", "builder", "callback"}
        for name, (flag, module, method) in TAURI_PLUGIN_REGISTRY.items():
            assert flag.startswith("PLUGIN_"), f"{name}: flag {flag!r} doesn't start with PLUGIN_"
            assert module.startswith("pytauri_plugins."), (
                f"{name}: module {module!r} has wrong prefix"
            )
            assert method in valid_methods, f"{name}: init_method {method!r} not in {valid_methods}"

    def test_builder_plugins_have_builder_method(self):
        """Plugins with init_method='builder' must have Builder.build()."""
        builder_plugins = [
            name for name, (_, _, m) in TAURI_PLUGIN_REGISTRY.items() if m == "builder"
        ]
        assert set(builder_plugins) == {"updater", "window_state", "global_shortcut"}

    def test_callback_plugins_have_callback_method(self):
        """Plugins with init_method='callback' must require a callback arg."""
        callback_plugins = [
            name for name, (_, _, m) in TAURI_PLUGIN_REGISTRY.items() if m == "callback"
        ]
        assert callback_plugins == ["single_instance"]


class TestRuntimePluginSetters:
    """Tests for runtime.set_tauri_plugins() and set_extra_capabilities()."""

    def test_set_tauri_plugins_updates_state(self):
        """set_tauri_plugins() updates the module-level variable."""
        runtime.set_tauri_plugins(["dialog", "fs", "notification"])
        assert runtime._TAURI_PLUGINS == "dialog,fs,notification"
        # Restore default
        runtime.set_tauri_plugins(["dialog", "fs"])

    def test_set_extra_capabilities_updates_state(self):
        """set_extra_capabilities() updates the module-level variable."""
        runtime.set_extra_capabilities(["shell:allow-execute"])
        assert runtime._EXTRA_CAPABILITIES == "shell:allow-execute"
        # Restore default
        runtime.set_extra_capabilities([])


class TestCustomCommandRegistration:
    """Tests for custom command registration in runtime."""

    def setup_method(self):
        """Clear custom command state before each test."""
        with runtime._custom_command_lock:
            runtime._custom_command_handlers.clear()
            runtime._CUSTOM_COMMANDS = ""

    def teardown_method(self):
        """Restore clean state."""
        with runtime._custom_command_lock:
            runtime._custom_command_handlers.clear()
            runtime._CUSTOM_COMMANDS = ""

    def test_register_sync_handler(self):
        """register_custom_command stores a sync handler."""

        def my_handler(data):
            return {"ok": True}

        runtime.register_custom_command("my_cmd", my_handler)
        assert "my_cmd" in runtime._custom_command_handlers
        assert runtime._CUSTOM_COMMANDS == "my_cmd"

    def test_register_async_handler(self):
        """register_custom_command stores an async handler."""

        async def my_async(data):
            return {"ok": True}

        runtime.register_custom_command("async_cmd", my_async)
        assert "async_cmd" in runtime._custom_command_handlers

    def test_register_multiple_commands(self):
        """Multiple commands produce comma-separated env var value."""
        runtime.register_custom_command("cmd_a", lambda d: d)
        runtime.register_custom_command("cmd_b", lambda d: d)
        assert runtime._CUSTOM_COMMANDS == "cmd_a,cmd_b"

    def test_get_custom_commands_returns_copy(self):
        """get_custom_commands returns an independent copy."""
        runtime.register_custom_command("x", lambda d: d)
        copy = runtime.get_custom_commands()
        assert "x" in copy
        copy.pop("x")
        assert "x" in runtime._custom_command_handlers  # original unchanged

    def test_custom_commands_env_var_in_start(self):
        """PYWRY_CUSTOM_COMMANDS is in the env passed to subprocess."""
        main_file = Path(__file__).parent.parent / "pywry" / "runtime.py"
        content = main_file.read_text(encoding="utf-8")
        assert "PYWRY_CUSTOM_COMMANDS" in content


class TestAppCommandDecorator:
    """Tests for PyWry.command() decorator."""

    def setup_method(self):
        """Clear custom command state."""
        with runtime._custom_command_lock:
            runtime._custom_command_handlers.clear()
            runtime._CUSTOM_COMMANDS = ""

    def teardown_method(self):
        """Restore clean state."""
        with runtime._custom_command_lock:
            runtime._custom_command_handlers.clear()
            runtime._CUSTOM_COMMANDS = ""

    def test_command_decorator_registers_handler(self):
        """@app.command() registers the handler in runtime."""
        app = PyWry(theme=ThemeMode.DARK)

        @app.command()
        def greet(data):
            return {"msg": f"Hello {data.get('name', 'world')}"}

        assert "greet" in runtime._custom_command_handlers
        assert runtime._custom_command_handlers["greet"] is greet

    def test_command_decorator_with_custom_name(self):
        """@app.command('name') uses the custom name."""
        app = PyWry(theme=ThemeMode.DARK)

        @app.command("fetch_data")
        def _internal_fetch(data):
            return {"rows": []}

        assert "fetch_data" in runtime._custom_command_handlers
        assert "_internal_fetch" not in runtime._custom_command_handlers

    def test_command_decorator_preserves_function(self):
        """Decorator returns the original function unchanged."""
        app = PyWry(theme=ThemeMode.DARK)

        @app.command()
        def my_func(data):
            return data

        assert my_func({"a": 1}) == {"a": 1}

    def test_command_async_handler(self):
        """@app.command() works with async handlers."""
        app = PyWry(theme=ThemeMode.DARK)

        @app.command("async_op")
        async def _op(data):
            return {"done": True}

        assert "async_op" in runtime._custom_command_handlers

    def test_multiple_commands(self):
        """Multiple @app.command() calls register all commands."""
        app = PyWry(theme=ThemeMode.DARK)

        @app.command()
        def cmd_a(data):
            return {}

        @app.command()
        def cmd_b(data):
            return {}

        assert runtime._CUSTOM_COMMANDS == "cmd_a,cmd_b"

    def test_command_rejects_non_callable(self):
        """@app.command() raises TypeError for non-callable."""
        app = PyWry(theme=ThemeMode.DARK)
        with pytest.raises(TypeError, match="must be callable"):
            app.command()("not_a_function")

    def test_command_rejects_browser_mode(self):
        """@app.command() raises RuntimeError in BROWSER mode."""
        app = PyWry(mode=WindowMode.BROWSER, theme=ThemeMode.DARK)
        with pytest.raises(RuntimeError, match="native window mode"):

            @app.command()
            def handler(data):
                return {}

    def test_command_rejects_after_subprocess_started(self):
        """@app.command() raises RuntimeError if subprocess already running."""
        from unittest.mock import patch

        app = PyWry(theme=ThemeMode.DARK)
        with (
            patch.object(runtime, "is_running", return_value=True),
            pytest.raises(RuntimeError, match="before show"),
        ):

            @app.command()
            def late_handler(data):
                return {}

    def test_command_allows_native_modes(self):
        """@app.command() works in all three native window modes."""
        for mode in (WindowMode.NEW_WINDOW, WindowMode.SINGLE_WINDOW, WindowMode.MULTI_WINDOW):
            _app = PyWry(mode=mode, theme=ThemeMode.DARK)
            cmd_name = f"test_{mode.value}"

            @_app.command(cmd_name)  # pylint: disable=cell-var-from-loop
            def handler(data):
                return {}

            assert cmd_name in runtime._custom_command_handlers


class TestMenuTrayNativeModeValidation:
    """Tests that create_menu() and create_tray() reject non-native modes."""

    def test_create_menu_rejects_browser_mode(self):
        """create_menu() raises RuntimeError in BROWSER mode."""
        app = PyWry(mode=WindowMode.BROWSER, theme=ThemeMode.DARK)
        with pytest.raises(RuntimeError, match="native window mode"):
            app.create_menu("file_menu")

    def test_create_tray_rejects_browser_mode(self):
        """create_tray() raises RuntimeError in BROWSER mode."""
        app = PyWry(mode=WindowMode.BROWSER, theme=ThemeMode.DARK)
        with pytest.raises(RuntimeError, match="native window mode"):
            app.create_tray("app_tray")

    def test_create_menu_rejects_notebook_mode(self):
        """create_menu() raises RuntimeError in NOTEBOOK mode."""
        app = PyWry(mode=WindowMode.NOTEBOOK, theme=ThemeMode.DARK)
        with pytest.raises(RuntimeError, match="native window mode"):
            app.create_menu("file_menu")

    def test_create_tray_rejects_notebook_mode(self):
        """create_tray() raises RuntimeError in NOTEBOOK mode."""
        app = PyWry(mode=WindowMode.NOTEBOOK, theme=ThemeMode.DARK)
        with pytest.raises(RuntimeError, match="native window mode"):
            app.create_tray("app_tray")

    def test_require_native_mode_error_includes_feature_name(self):
        """Error message includes the feature name that was rejected."""
        app = PyWry(mode=WindowMode.BROWSER, theme=ThemeMode.DARK)
        with pytest.raises(RuntimeError, match="create_menu"):
            app.create_menu("test")
        with pytest.raises(RuntimeError, match="create_tray"):
            app.create_tray("test")

    def test_require_native_mode_error_includes_current_mode(self):
        """Error message includes the current mode value."""
        app = PyWry(mode=WindowMode.BROWSER, theme=ThemeMode.DARK)
        with pytest.raises(RuntimeError, match="browser"):
            app.create_menu("test")


class TestHandleCustomCommand:
    """Unit tests for runtime._handle_custom_command execution."""

    def setup_method(self):
        """Register a known handler for each test."""
        with runtime._custom_command_lock:
            runtime._custom_command_handlers.clear()
            runtime._CUSTOM_COMMANDS = ""

    def teardown_method(self):
        """Restore clean state."""
        with runtime._custom_command_lock:
            runtime._custom_command_handlers.clear()
            runtime._CUSTOM_COMMANDS = ""

    def test_sync_handler_returns_result(self):
        """_handle_custom_command executes sync handler and sends response."""
        from unittest.mock import patch

        def greet(data):
            return {"greeting": f"Hello {data.get('name', 'world')}"}

        runtime.register_custom_command("greet", greet)

        sent = []
        with patch.object(runtime, "send_command", side_effect=sent.append):
            runtime._handle_custom_command(
                {
                    "command": "greet",
                    "data": {"name": "Alice"},
                    "request_id": "req-001",
                }
            )

        assert len(sent) == 1
        resp = sent[0]
        assert resp["request_id"] == "req-001"
        assert resp["success"] is True
        assert resp["greeting"] == "Hello Alice"

    def test_async_handler_returns_result(self):
        """_handle_custom_command executes async handler and sends response."""
        from unittest.mock import patch

        async def async_greet(data):
            return {"async": True, "name": data.get("name")}

        runtime.register_custom_command("async_greet", async_greet)

        sent = []
        with patch.object(runtime, "send_command", side_effect=sent.append):
            runtime._handle_custom_command(
                {
                    "command": "async_greet",
                    "data": {"name": "Bob"},
                    "request_id": "req-002",
                }
            )

        assert len(sent) == 1
        resp = sent[0]
        assert resp["request_id"] == "req-002"
        assert resp["success"] is True
        assert resp["async"] is True
        assert resp["name"] == "Bob"

    def test_unknown_command_returns_error(self):
        """_handle_custom_command returns error for unregistered command."""
        from unittest.mock import patch

        sent = []
        with patch.object(runtime, "send_command", side_effect=sent.append):
            runtime._handle_custom_command(
                {
                    "command": "nonexistent",
                    "data": {},
                    "request_id": "req-003",
                }
            )

        assert len(sent) == 1
        resp = sent[0]
        assert resp["request_id"] == "req-003"
        assert resp["success"] is False
        assert "No handler" in resp["error"]

    def test_handler_exception_returns_error(self):
        """_handle_custom_command catches handler exceptions."""
        from unittest.mock import patch

        def bad_handler(data):
            msg = "something went wrong"
            raise ValueError(msg)

        runtime.register_custom_command("bad", bad_handler)

        sent = []
        with patch.object(runtime, "send_command", side_effect=sent.append):
            runtime._handle_custom_command(
                {
                    "command": "bad",
                    "data": {},
                    "request_id": "req-004",
                }
            )

        assert len(sent) == 1
        resp = sent[0]
        assert resp["request_id"] == "req-004"
        assert resp["success"] is False
        assert "something went wrong" in resp["error"]

    def test_non_dict_result_wrapped(self):
        """If handler returns non-dict, it is wrapped as {result: value}."""
        from unittest.mock import patch

        def returns_string(data):
            return "just a string"

        runtime.register_custom_command("str_cmd", returns_string)

        sent = []
        with patch.object(runtime, "send_command", side_effect=sent.append):
            runtime._handle_custom_command(
                {
                    "command": "str_cmd",
                    "data": {},
                    "request_id": "req-005",
                }
            )

        assert len(sent) == 1
        resp = sent[0]
        assert resp["success"] is True
        assert resp["result"] == "just a string"


class TestMainCustomCommandRegistration:
    """Tests for custom command handling in __main__.py."""

    def test_main_reads_custom_commands_env(self):
        """__main__.py reads PYWRY_CUSTOM_COMMANDS env var."""
        main_file = Path(__file__).parent.parent / "pywry" / "__main__.py"
        content = main_file.read_text(encoding="utf-8")
        assert "PYWRY_CUSTOM_COMMANDS" in content

    def test_main_has_register_custom_commands_function(self):
        """__main__.py defines _register_custom_commands()."""
        main_file = Path(__file__).parent.parent / "pywry" / "__main__.py"
        content = main_file.read_text(encoding="utf-8")
        assert "def _register_custom_commands(" in content

    def test_main_has_default_single_instance_callback(self):
        """__main__.py defines _default_single_instance_callback()."""
        main_file = Path(__file__).parent.parent / "pywry" / "__main__.py"
        content = main_file.read_text(encoding="utf-8")
        assert "def _default_single_instance_callback(" in content


class TestPluginImports:
    """Tests for plugin module imports."""

    def test_can_import_dialog_plugin(self):
        """Dialog plugin can be imported."""
        from pytauri_plugins import dialog

        assert hasattr(dialog, "init"), "dialog.init() function not found"

    def test_can_import_fs_plugin(self):
        """FS plugin can be imported."""
        from pytauri_plugins import fs

        assert hasattr(fs, "init"), "fs.init() function not found"


class TestMainModulePluginRegistration:
    """Tests for plugin registration in __main__.py."""

    def test_main_has_plugin_registry(self):
        """__main__.py imports _PLUGIN_REGISTRY from config."""
        main_file = Path(__file__).parent.parent / "pywry" / "__main__.py"
        content = main_file.read_text(encoding="utf-8")
        assert "_PLUGIN_REGISTRY" in content, "_PLUGIN_REGISTRY not found in __main__.py"
        assert "TAURI_PLUGIN_REGISTRY" in content, "import from config not found"

    def test_main_has_load_plugins_function(self):
        """__main__.py defines _load_plugins() for dynamic loading."""
        main_file = Path(__file__).parent.parent / "pywry" / "__main__.py"
        content = main_file.read_text(encoding="utf-8")
        assert "def _load_plugins(" in content, "_load_plugins function not found"

    def test_main_reads_env_var(self):
        """__main__.py reads PYWRY_TAURI_PLUGINS env var."""
        main_file = Path(__file__).parent.parent / "pywry" / "__main__.py"
        content = main_file.read_text(encoding="utf-8")
        assert "PYWRY_TAURI_PLUGINS" in content, "PYWRY_TAURI_PLUGINS env var not read"

    def test_main_registers_plugins_dynamically(self):
        """__main__.py passes dynamic plugins list to builder.build()."""
        main_file = Path(__file__).parent.parent / "pywry" / "__main__.py"
        content = main_file.read_text(encoding="utf-8")
        assert "plugins=plugins" in content or "plugins = plugins" in content, (
            "Dynamic plugins list not passed to builder.build()"
        )

    def test_main_reads_extra_capabilities_env(self):
        """__main__.py reads PYWRY_EXTRA_CAPABILITIES env var."""
        main_file = Path(__file__).parent.parent / "pywry" / "__main__.py"
        content = main_file.read_text(encoding="utf-8")
        assert "PYWRY_EXTRA_CAPABILITIES" in content, (
            "PYWRY_EXTRA_CAPABILITIES env var not consumed in __main__.py"
        )

    def test_main_calls_stage_extra_capabilities(self):
        """__main__.py calls _stage_extra_capabilities when extra caps are present."""
        main_file = Path(__file__).parent.parent / "pywry" / "__main__.py"
        content = main_file.read_text(encoding="utf-8")
        assert "_stage_extra_capabilities(" in content, (
            "_stage_extra_capabilities not called in main()"
        )

    def test_main_cleans_up_temp_dir(self):
        """__main__.py cleans up staged temp dir in a finally block."""
        main_file = Path(__file__).parent.parent / "pywry" / "__main__.py"
        content = main_file.read_text(encoding="utf-8")
        assert "shutil.rmtree(tmp_caps_dir" in content, "Temp dir cleanup not found in __main__.py"


def _import_stage_extra_capabilities():
    """Import _stage_extra_capabilities from __main__.py safely.

    Importing pywry.__main__ replaces sys.stdin/stdout/stderr with fresh
    UTF-8 TextIOWrapper objects (on Windows) that wrap the *same* buffer.
    This corrupts pytest's capture system.  We swap in decoy BytesIO-backed
    streams before the import so the originals are never touched, then
    restore them immediately after.
    """
    import io
    import sys

    orig = sys.stdin, sys.stdout, sys.stderr
    # Give __main__'s module-level code decoy streams to wrap
    sys.stdin = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
    sys.stdout = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
    sys.stderr = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
    try:
        from pywry.__main__ import _stage_extra_capabilities
    finally:
        sys.stdin, sys.stdout, sys.stderr = orig
    return _stage_extra_capabilities


class TestStageExtraCapabilities:
    """Tests for _stage_extra_capabilities() in __main__.py."""

    def test_creates_temp_dir_with_extra_toml(self, tmp_path: Path):
        """Staging creates a capabilities/extra.toml with requested permissions."""
        fn = _import_stage_extra_capabilities()

        src_dir = tmp_path / "src"
        caps_dir = src_dir / "capabilities"
        caps_dir.mkdir(parents=True)
        (caps_dir / "default.toml").write_text(
            'identifier = "default"\npermissions = ["dialog:default"]\n',
            encoding="utf-8",
        )
        (src_dir / "Tauri.toml").write_text("[tauri]\n", encoding="utf-8")

        result = fn(src_dir, ["shell:allow-execute", "http:default"])

        try:
            extra_toml = result / "capabilities" / "extra.toml"
            assert extra_toml.exists(), "extra.toml not created"
            content = extra_toml.read_text(encoding="utf-8")
            assert 'identifier = "extra"' in content
            assert '"shell:allow-execute"' in content
            assert '"http:default"' in content
        finally:
            import shutil

            shutil.rmtree(result, ignore_errors=True)

    def test_preserves_original_default_toml(self, tmp_path: Path):
        """Staging copies default.toml without modifying the original."""
        fn = _import_stage_extra_capabilities()

        src_dir = tmp_path / "src"
        caps_dir = src_dir / "capabilities"
        caps_dir.mkdir(parents=True)
        original_content = 'identifier = "default"\npermissions = ["dialog:default"]\n'
        (caps_dir / "default.toml").write_text(original_content, encoding="utf-8")
        (src_dir / "Tauri.toml").write_text("[tauri]\n", encoding="utf-8")

        result = fn(src_dir, ["notification:default"])

        try:
            # Original file untouched
            assert (caps_dir / "default.toml").read_text(encoding="utf-8") == original_content
            # Copied default.toml in temp dir also intact
            copied = (result / "capabilities" / "default.toml").read_text(encoding="utf-8")
            assert copied == original_content
        finally:
            import shutil

            shutil.rmtree(result, ignore_errors=True)

    def test_returns_path_object(self, tmp_path: Path):
        """Staging returns a Path pointing to the temp directory."""
        fn = _import_stage_extra_capabilities()

        src_dir = tmp_path / "src"
        caps_dir = src_dir / "capabilities"
        caps_dir.mkdir(parents=True)
        (caps_dir / "default.toml").write_text(
            'identifier = "default"\npermissions = []\n',
            encoding="utf-8",
        )

        result = fn(src_dir, ["os:default"])

        try:
            assert isinstance(result, Path)
            assert result.is_dir()
            assert (result / "capabilities").is_dir()
        finally:
            import shutil

            shutil.rmtree(result, ignore_errors=True)

    def test_extra_toml_has_wildcard_windows(self, tmp_path: Path):
        """Extra capability file targets all windows with wildcard."""
        fn = _import_stage_extra_capabilities()

        src_dir = tmp_path / "src"
        caps_dir = src_dir / "capabilities"
        caps_dir.mkdir(parents=True)
        (caps_dir / "default.toml").write_text(
            'identifier = "default"\npermissions = []\n',
            encoding="utf-8",
        )

        result = fn(src_dir, ["process:default"])

        try:
            content = (result / "capabilities" / "extra.toml").read_text(encoding="utf-8")
            assert 'windows = ["*"]' in content
        finally:
            import shutil

            shutil.rmtree(result, ignore_errors=True)

    def test_copies_tauri_toml(self, tmp_path: Path):
        """Staging copies Tauri.toml alongside capabilities."""
        fn = _import_stage_extra_capabilities()

        src_dir = tmp_path / "src"
        caps_dir = src_dir / "capabilities"
        caps_dir.mkdir(parents=True)
        (caps_dir / "default.toml").write_text(
            'identifier = "default"\npermissions = []\n',
            encoding="utf-8",
        )
        tauri_content = '[tauri]\nidentifier = "com.pywry"\n'
        (src_dir / "Tauri.toml").write_text(tauri_content, encoding="utf-8")

        result = fn(src_dir, ["os:default"])

        try:
            assert (result / "Tauri.toml").exists(), "Tauri.toml not copied"
            assert (result / "Tauri.toml").read_text(encoding="utf-8") == tauri_content
        finally:
            import shutil

            shutil.rmtree(result, ignore_errors=True)


# =============================================================================
# Integration Tests - JS API Availability
# =============================================================================


@pytest.mark.e2e
class TestTauriAPIsAvailable:
    """E2E tests verifying Tauri APIs are available in webview."""

    def test_tauri_global_exists(self):
        """window.__TAURI__ object exists in webview."""
        app = PyWry(theme=ThemeMode.DARK)
        label = show_and_wait_ready(app, "<div>Test</div>", title="Tauri Check")

        result = wait_for_result(
            label,
            """
            pywry.result({
                hasTauri: typeof window.__TAURI__ !== 'undefined',
                tauriType: typeof window.__TAURI__
            });
        """,
        )

        assert result is not None, "No result from window"
        assert result["hasTauri"], "window.__TAURI__ not found"
        assert result["tauriType"] == "object", "window.__TAURI__ is not an object"
        app.close()

    def test_dialog_api_available(self):
        """window.__TAURI__.dialog API is available."""
        app = PyWry(theme=ThemeMode.DARK)
        label = show_and_wait_ready(app, "<div>Test</div>", title="Dialog Check")

        result = wait_for_result(
            label,
            """
            pywry.result({
                hasDialog: typeof window.__TAURI__?.dialog !== 'undefined',
                hasSave: typeof window.__TAURI__?.dialog?.save === 'function',
                hasOpen: typeof window.__TAURI__?.dialog?.open === 'function',
                hasMessage: typeof window.__TAURI__?.dialog?.message === 'function'
            });
        """,
        )

        assert result is not None, "No result from window"
        assert result["hasDialog"], "window.__TAURI__.dialog not found"
        assert result["hasSave"], "dialog.save() function not found"
        assert result["hasOpen"], "dialog.open() function not found"
        assert result["hasMessage"], "dialog.message() function not found"
        app.close()

    def test_fs_api_available(self):
        """window.__TAURI__.fs API is available."""
        app = PyWry(theme=ThemeMode.DARK)
        label = show_and_wait_ready(app, "<div>Test</div>", title="FS Check")

        result = wait_for_result(
            label,
            """
            pywry.result({
                hasFs: typeof window.__TAURI__?.fs !== 'undefined',
                hasWriteTextFile: typeof window.__TAURI__?.fs?.writeTextFile === 'function',
                hasReadTextFile: typeof window.__TAURI__?.fs?.readTextFile === 'function'
            });
        """,
        )

        assert result is not None, "No result from window"
        assert result["hasFs"], "window.__TAURI__.fs not found"
        assert result["hasWriteTextFile"], "fs.writeTextFile() function not found"
        assert result["hasReadTextFile"], "fs.readTextFile() function not found"
        app.close()

    def test_pytauri_api_available(self):
        """window.__TAURI__.pytauri API is available for IPC."""
        app = PyWry(theme=ThemeMode.DARK)
        label = show_and_wait_ready(app, "<div>Test</div>", title="PyTauri Check")

        result = wait_for_result(
            label,
            """
            pywry.result({
                hasPytauri: typeof window.__TAURI__?.pytauri !== 'undefined',
                hasPyInvoke: typeof window.__TAURI__?.pytauri?.pyInvoke === 'function'
            });
        """,
        )

        assert result is not None, "No result from window"
        assert result["hasPytauri"], "window.__TAURI__.pytauri not found"
        assert result["hasPyInvoke"], "pytauri.pyInvoke() function not found"
        app.close()


@pytest.mark.e2e
class TestAGGridExportIntegration:
    """E2E tests for AG Grid export with Tauri dialog."""

    def test_aggrid_has_export_context_menu(self):
        """AG Grid context menu includes export options."""
        app = PyWry(theme=ThemeMode.DARK)
        data = [{"Symbol": "AAPL", "Price": 150.25}]

        waiter = ReadyWaiter(timeout=10.0)
        callbacks = {"pywry:ready": waiter.on_ready}
        widget = app.show_dataframe(data, callbacks=callbacks, title="Export Test")
        label = widget.label if hasattr(widget, "label") else widget
        waiter.wait()
        time.sleep(0.5)  # Wait for AG Grid to fully render

        # Verify the grid is set up and Tauri APIs are available
        result = wait_for_result(
            label,
            """
            (function() {
                // Get the PYWRY_AGGRID_BUILD_OPTIONS function
                var buildFn = window.PYWRY_AGGRID_BUILD_OPTIONS;
                var hasBuildFn = typeof buildFn === 'function';

                // Check that Tauri dialog is accessible
                var hasTauriDialog = typeof window.__TAURI__?.dialog?.save === 'function';
                var hasTauriFs = typeof window.__TAURI__?.fs?.writeTextFile === 'function';

                pywry.result({
                    hasBuildFn: hasBuildFn,
                    hasTauriDialog: hasTauriDialog,
                    hasTauriFs: hasTauriFs
                });
            })();
        """,
        )

        assert result is not None, "No result from window"
        assert result["hasBuildFn"], "PYWRY_AGGRID_BUILD_OPTIONS function not found"
        assert result["hasTauriDialog"], "Tauri dialog.save() not available for export"
        assert result["hasTauriFs"], "Tauri fs.writeTextFile() not available for export"
        app.close()

    def test_aggrid_export_functions_check_tauri_first(self):
        """AG Grid export checks for Tauri before browser API."""
        # Read the aggrid-defaults.js to verify the logic
        aggrid_js_file = (
            Path(__file__).parent.parent / "pywry" / "frontend" / "src" / "aggrid-defaults.js"
        )
        content = aggrid_js_file.read_text(encoding="utf-8")

        # Verify Tauri is checked BEFORE showSaveFilePicker
        tauri_check_pos = content.find("if (window.__TAURI__)")
        browser_check_pos = content.find("if (window.showSaveFilePicker)")

        assert tauri_check_pos != -1, "Tauri check not found in aggrid-defaults.js"
        assert browser_check_pos != -1, "Browser fallback not found in aggrid-defaults.js"
        assert tauri_check_pos < browser_check_pos, (
            "Tauri check should come BEFORE browser fallback in saveWithFilePicker"
        )


@pytest.mark.e2e
class TestSaveDialogFunctionality:
    """E2E tests for save dialog functionality."""

    @retry_on_subprocess_failure(max_attempts=3, delay=1.0)
    def test_save_with_file_picker_function_exists(self):
        """saveWithFilePicker helper function is defined in grid context."""
        app = PyWry(theme=ThemeMode.DARK)
        data = [{"a": 1}]

        waiter = ReadyWaiter(timeout=10.0)
        callbacks = {"pywry:ready": waiter.on_ready}
        widget = app.show_dataframe(data, callbacks=callbacks, title="SavePicker Test")
        label = widget.label if hasattr(widget, "label") else widget
        if not waiter.wait():
            raise TimeoutError(f"Window '{label}' did not become ready within 10s")
        time.sleep(0.5)

        # The saveWithFilePicker is a local function inside the context menu builder
        # We can verify the grid is set up and Tauri APIs are available
        result = wait_for_result(
            label,
            """
            pywry.result({
                gridExists: !!document.querySelector('.ag-root-wrapper'),
                hasTauriDialog: typeof window.__TAURI__?.dialog?.save === 'function',
                hasTauriFs: typeof window.__TAURI__?.fs?.writeTextFile === 'function'
            });
        """,
        )

        assert result is not None, "No result from window"
        assert result["gridExists"], "AG Grid not rendered"
        assert result["hasTauriDialog"], "Tauri dialog not available"
        assert result["hasTauriFs"], "Tauri fs not available"
        app.close()


@pytest.mark.e2e
class TestCustomCommandE2E:
    """E2E tests for custom pyInvoke commands round-tripping to Python."""

    @retry_on_subprocess_failure(max_attempts=3, delay=1.0)
    def test_custom_command_round_trip(self):
        """JS pyInvoke calls a custom command and receives the result."""
        app = PyWry(theme=ThemeMode.DARK)

        handler_calls = []

        @app.command("echo_back")
        def echo_back(data):
            handler_calls.append(data)
            return {"echoed": data.get("message", ""), "from_python": True}

        label = show_and_wait_ready(app, "<div>Custom Cmd</div>", title="Custom Cmd")

        # Call our custom command from JS and capture the result
        result = wait_for_result(
            label,
            """
            (async function() {
                try {
                    var resp = await window.__TAURI__.pytauri.pyInvoke(
                        'echo_back', { message: 'hello from JS' }
                    );
                    pywry.result({
                        success: true,
                        response: resp
                    });
                } catch (e) {
                    pywry.result({
                        success: false,
                        error: e.toString()
                    });
                }
            })();
            """,
        )

        assert result is not None, "No result from JS"
        assert result["success"], f"pyInvoke failed: {result.get('error')}"

        # Verify the Python handler was actually called
        assert len(handler_calls) >= 1, "Python handler was never called"
        assert handler_calls[0].get("message") == "hello from JS"

        # Verify the result came back to JS
        resp = result["response"]
        assert resp["echoed"] == "hello from JS"
        assert resp["from_python"] is True
        app.close()

    @retry_on_subprocess_failure(max_attempts=3, delay=1.0)
    def test_custom_command_error_propagates(self):
        """JS pyInvoke surfaces Python handler errors."""
        app = PyWry(theme=ThemeMode.DARK)

        @app.command("fail_cmd")
        def fail_cmd(data):
            msg = "intentional test error"
            raise RuntimeError(msg)

        label = show_and_wait_ready(app, "<div>Error Cmd</div>", title="Error Cmd")

        result = wait_for_result(
            label,
            """
            (async function() {
                try {
                    var resp = await window.__TAURI__.pytauri.pyInvoke(
                        'fail_cmd', { input: 1 }
                    );
                    // If we get here, the command returned a response
                    // (pytauri may serialize the error as a success response)
                    pywry.result({
                        threw: false,
                        response: resp
                    });
                } catch (e) {
                    pywry.result({
                        threw: true,
                        error: e.toString()
                    });
                }
            })();
            """,
        )

        assert result is not None, "No result from JS"
        # The error may surface as a JS exception OR as a response with
        # success=false depending on how pytauri serialises it.
        if result.get("threw"):
            assert "intentional test error" in result["error"]
        else:
            resp = result["response"]
            assert resp.get("success") is False or "intentional test error" in str(resp)
        app.close()

    @retry_on_subprocess_failure(max_attempts=3, delay=1.0)
    def test_async_custom_command_round_trip(self):
        """JS pyInvoke works with an async Python handler."""
        app = PyWry(theme=ThemeMode.DARK)

        @app.command("async_double")
        async def async_double(data):
            value = data.get("n", 0)
            return {"doubled": value * 2}

        label = show_and_wait_ready(app, "<div>Async Cmd</div>", title="Async Cmd")

        result = wait_for_result(
            label,
            """
            (async function() {
                try {
                    var resp = await window.__TAURI__.pytauri.pyInvoke(
                        'async_double', { n: 21 }
                    );
                    pywry.result({ success: true, response: resp });
                } catch (e) {
                    pywry.result({ success: false, error: e.toString() });
                }
            })();
            """,
        )

        assert result is not None, "No result from JS"
        assert result["success"], f"pyInvoke failed: {result.get('error')}"
        assert result["response"]["doubled"] == 42
        app.close()
