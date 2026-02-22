"""Tests for Tauri plugin integration.

Tests verify:
- Dialog and FS plugins are properly registered
- Dynamic plugin loading from config / env vars works
- Tauri APIs are available in the webview
- File save dialog functionality works
- Plugin capabilities are correctly configured
"""

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
from pywry.models import ThemeMode

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
        """Each registry value is a (flag_name, module_path) tuple."""
        for name, (flag, module) in TAURI_PLUGIN_REGISTRY.items():
            assert flag.startswith("PLUGIN_"), f"{name}: flag {flag!r} doesn't start with PLUGIN_"
            assert module.startswith("pytauri_plugins."), (
                f"{name}: module {module!r} has wrong prefix"
            )


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
