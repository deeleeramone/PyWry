"""Tests for JavaScript bridge scripts.

Tests the PyWry JavaScript bridge and event system scripts,
which are now loaded from frontend/src/ files.
"""

from pywry.scripts import _get_bridge_js, build_init_script


class TestBridgeJs:
    """Tests for the bridge JS loaded from frontend/src/bridge.js."""

    def test_defines_window_pywry(self):
        js = _get_bridge_js()
        assert "window.pywry" in js

    def test_defines_result_function(self):
        js = _get_bridge_js()
        assert "result" in js

    def test_defines_emit_function(self):
        js = _get_bridge_js()
        assert "emit" in js

    def test_defines_on_function(self):
        js = _get_bridge_js()
        assert ".on" in js

    def test_defines_off_function(self):
        js = _get_bridge_js()
        assert ".off" in js

    def test_defines_dispatch_function(self):
        js = _get_bridge_js()
        assert "dispatch" in js

    def test_is_string(self):
        js = _get_bridge_js()
        assert isinstance(js, str)

    def test_is_not_empty(self):
        js = _get_bridge_js()
        assert len(js) > 0

    def test_uses_strict_mode(self):
        js = _get_bridge_js()
        assert "'use strict'" in js

    def test_uses_iife(self):
        js = _get_bridge_js()
        assert "(function()" in js

    def test_handles_json_payload(self):
        js = _get_bridge_js()
        assert "payload" in js

    def test_checks_for_tauri(self):
        js = _get_bridge_js()
        assert "__TAURI__" in js

    def test_uses_pytauri_invoke(self):
        js = _get_bridge_js()
        assert "pytauri" in js
        assert "pyInvoke" in js

    def test_open_file_function(self):
        js = _get_bridge_js()
        assert "openFile" in js

    def test_wildcard_handlers_supported(self):
        js = _get_bridge_js()
        assert "'*'" in js


class TestBuildInitScript:
    """Tests for build_init_script function."""

    def test_returns_string(self):
        script = build_init_script(window_label="main")
        assert isinstance(script, str)

    def test_includes_window_label(self):
        script = build_init_script(window_label="test-window")
        assert "test-window" in script

    def test_includes_pywry_bridge(self):
        script = build_init_script(window_label="main")
        assert "pywry" in script

    def test_different_labels_produce_different_scripts(self):
        script1 = build_init_script(window_label="window-1")
        script2 = build_init_script(window_label="window-2")
        assert "window-1" in script1
        assert "window-2" in script2

    def test_hot_reload_included_when_enabled(self):
        script = build_init_script(window_label="main", enable_hot_reload=True)
        assert "Hot reload" in script or "saveScrollPosition" in script

    def test_hot_reload_excluded_when_disabled(self):
        script = build_init_script(window_label="main", enable_hot_reload=False)
        assert "saveScrollPosition" not in script
