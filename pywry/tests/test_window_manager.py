"""Unit tests for pywry.window_manager package using mocks.

These tests focus on bringing window_manager modules to 100% coverage by
mocking the runtime and pytauri layers — no native windows are spawned.
"""

from __future__ import annotations

import sys

from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from pywry.callbacks import get_registry
from pywry.models import HtmlContent, ThemeMode, WindowConfig, WindowMode
from pywry.window_manager import (
    BrowserMode,
    MultiWindowMode,
    NewWindowMode,
    SingleWindowMode,
    WindowController,
    WindowLifecycle,
    WindowResources,
    get_lifecycle,
)
from pywry.window_manager.lifecycle import _LifecycleHolder
from pywry.window_manager.modes.base import WindowModeBase


# =============================================================================
# Helpers
# =============================================================================


@pytest.fixture(autouse=True)
def reset_lifecycle_singleton():
    """Reset the lifecycle singleton between tests to prevent cross-test state."""
    # Reset the singleton's storage dict, not the singleton itself
    lifecycle = get_lifecycle()
    lifecycle._windows.clear()  # type: ignore[attr-defined]
    get_registry().clear()
    yield
    lifecycle = get_lifecycle()
    lifecycle._windows.clear()  # type: ignore[attr-defined]
    get_registry().clear()


def _make_runtime_mock() -> MagicMock:
    """Build a default runtime mock that approximates a healthy subprocess."""
    rt = MagicMock()
    rt.is_running.return_value = True
    rt.start.return_value = True
    rt.create_window.return_value = True
    rt.show_window.return_value = True
    rt.hide_window.return_value = True
    rt.close_window.return_value = True
    rt.check_window_open.return_value = True
    rt.set_content.return_value = True
    rt.emit_event.return_value = True
    return rt


# =============================================================================
# WindowResources / WindowLifecycle direct tests
# =============================================================================


class TestWindowResources:
    """Test the WindowResources dataclass."""

    def test_defaults(self):
        """All fields default to expected initial values."""
        r = WindowResources(label="x")
        assert r.label == "x"
        assert isinstance(r.created_at, datetime)
        assert r.html_content is None
        assert r.scripts_injected == []
        assert r.libraries_loaded == []
        assert r.custom_data == {}
        assert r.is_destroyed is False
        assert r.last_content is None
        assert r.last_config is None
        assert r.watched_css == []
        assert r.watched_scripts == []
        assert r.css_asset_ids == {}
        assert r.content_set_at is None
        assert r.on_close == []
        assert r.close_reason is None


class TestWindowLifecycle:
    """Tests for the WindowLifecycle singleton."""

    def test_singleton_returns_same_instance(self):
        """The constructor always returns the same instance."""
        a = WindowLifecycle()
        b = WindowLifecycle()
        assert a is b

    def test_clear_resets_windows(self):
        """clear() empties the tracked windows dict."""
        lifecycle = get_lifecycle()
        lifecycle._windows["x"] = WindowResources(label="x")
        lifecycle.clear()
        assert lifecycle._windows == {}

    def test_get_returns_resources(self):
        """get() returns tracked resources."""
        lifecycle = get_lifecycle()
        lifecycle._windows["a"] = WindowResources(label="a")
        assert lifecycle.get("a") is not None
        assert lifecycle.get("missing") is None

    def test_exists(self):
        """exists() returns True for live windows, False for destroyed/missing."""
        lifecycle = get_lifecycle()
        lifecycle._windows["live"] = WindowResources(label="live")
        dead = WindowResources(label="dead")
        dead.is_destroyed = True
        lifecycle._windows["dead"] = dead

        assert lifecycle.exists("live") is True
        assert lifecycle.exists("dead") is False
        assert lifecycle.exists("missing") is False

    def test_register_window_new(self):
        """register_window adds a new resource if none exists."""
        lifecycle = get_lifecycle()
        res = lifecycle.register_window("new")
        assert res.label == "new"
        assert "new" in lifecycle._windows

    def test_register_window_existing(self):
        """register_window restores destroyed flag if resource already tracked."""
        lifecycle = get_lifecycle()
        existing = WindowResources(label="existing")
        existing.is_destroyed = True
        lifecycle._windows["existing"] = existing
        res = lifecycle.register_window("existing")
        assert res is existing
        assert res.is_destroyed is False

    def test_get_active_windows(self):
        """get_active_windows returns labels of non-destroyed windows."""
        lifecycle = get_lifecycle()
        lifecycle._windows["a"] = WindowResources(label="a")
        b = WindowResources(label="b")
        b.is_destroyed = True
        lifecycle._windows["b"] = b
        active = lifecycle.get_active_windows()
        assert "a" in active
        assert "b" not in active

    def test_get_labels(self):
        """get_labels mirrors get_active_windows."""
        lifecycle = get_lifecycle()
        lifecycle._windows["a"] = WindowResources(label="a")
        b = WindowResources(label="b")
        b.is_destroyed = True
        lifecycle._windows["b"] = b
        assert lifecycle.get_labels() == ["a"]

    def test_get_stats(self):
        """get_stats reports total/active counts and labels."""
        lifecycle = get_lifecycle()
        lifecycle._windows["a"] = WindowResources(label="a")
        b = WindowResources(label="b")
        b.is_destroyed = True
        lifecycle._windows["b"] = b
        stats = lifecycle.get_stats()
        assert stats["total_tracked"] == 2
        assert stats["active"] == 1
        assert stats["labels"] == ["a"]

    def test_create_starts_runtime_when_not_running(self):
        """create() starts runtime if not running, then handles main."""
        lifecycle = get_lifecycle()
        with (
            patch("pywry.runtime.is_running", return_value=False),
            patch("pywry.runtime.start", return_value=True),
            patch("pywry.runtime.show_window", return_value=True) as show_mock,
        ):
            res = lifecycle.create("main")
            assert res.label == "main"
            show_mock.assert_called_once_with("main")

    def test_create_runtime_start_failure(self):
        """create() returns barebones resources if subprocess won't start."""
        lifecycle = get_lifecycle()
        with (
            patch("pywry.runtime.is_running", return_value=False),
            patch("pywry.runtime.start", return_value=False),
        ):
            res = lifecycle.create("xyz")
            assert res.label == "xyz"
            assert "xyz" in lifecycle._windows

    def test_create_main_existing_window_runtime_running(self):
        """When runtime is running and main already open, show it."""
        lifecycle = get_lifecycle()
        with (
            patch("pywry.runtime.is_running", return_value=True),
            patch("pywry.runtime.check_window_open", return_value=True),
            patch("pywry.runtime.show_window", return_value=True) as show_mock,
        ):
            lifecycle.create("main")
            show_mock.assert_called_once_with("main")

    def test_create_main_recreates_when_closed(self):
        """When runtime is running but main was closed, create_window is called."""
        lifecycle = get_lifecycle()
        with (
            patch("pywry.runtime.is_running", return_value=True),
            patch("pywry.runtime.check_window_open", return_value=False),
            patch("pywry.runtime.create_window", return_value=True) as create_mock,
        ):
            lifecycle.create("main", title="T", width=100, height=200)
            create_mock.assert_called_once()
            args = create_mock.call_args
            assert args[0][0] == "main"

    def test_create_non_main(self):
        """create() for a non-main label always calls create_window."""
        lifecycle = get_lifecycle()
        with (
            patch("pywry.runtime.is_running", return_value=True),
            patch("pywry.runtime.create_window", return_value=True) as create_mock,
        ):
            lifecycle.create("custom-1", title="X")
            create_mock.assert_called_once()

    def test_create_destroys_existing(self):
        """create() destroys an existing window with the same label first."""
        lifecycle = get_lifecycle()
        lifecycle._windows["dup"] = WindowResources(label="dup")
        with (
            patch("pywry.runtime.is_running", return_value=True),
            patch("pywry.runtime.create_window", return_value=True),
            patch("pywry.runtime.close_window", return_value=True),
        ):
            lifecycle.create("dup")
            # Should now be tracked again as a fresh resource
            assert "dup" in lifecycle._windows

    def test_set_content_no_resources(self):
        """set_content returns False if window unknown."""
        lifecycle = get_lifecycle()
        assert lifecycle.set_content("missing", "<html>") is False

    def test_set_content_destroyed(self):
        """set_content returns False if resources marked destroyed."""
        lifecycle = get_lifecycle()
        r = WindowResources(label="x")
        r.is_destroyed = True
        lifecycle._windows["x"] = r
        assert lifecycle.set_content("x", "<html>") is False

    def test_set_content_success(self):
        """set_content updates html_content and timestamp on success."""
        lifecycle = get_lifecycle()
        lifecycle._windows["x"] = WindowResources(label="x")
        config = WindowConfig()
        with patch("pywry.runtime.set_content", return_value=True):
            ok = lifecycle.set_content("x", "<html>", "dark", config=config)
        assert ok is True
        res = lifecycle.get("x")
        assert res.html_content == "<html>"
        assert res.last_config is config
        assert res.content_set_at is not None

    def test_set_content_failure_logs(self):
        """set_content returns False if runtime returns False."""
        lifecycle = get_lifecycle()
        lifecycle._windows["x"] = WindowResources(label="x")
        with patch("pywry.runtime.set_content", return_value=False):
            ok = lifecycle.set_content("x", "<html>")
        assert ok is False

    def test_is_open_unknown(self):
        """is_open returns False for unknown windows."""
        lifecycle = get_lifecycle()
        assert lifecycle.is_open("missing") is False

    def test_is_open_known_via_runtime(self):
        """is_open delegates to runtime.check_window_open for known windows."""
        lifecycle = get_lifecycle()
        lifecycle._windows["x"] = WindowResources(label="x")
        with patch("pywry.runtime.check_window_open", return_value=True):
            assert lifecycle.is_open("x") is True
        with patch("pywry.runtime.check_window_open", return_value=False):
            assert lifecycle.is_open("x") is False

    def test_store_content_for_refresh_unknown(self):
        """Unknown labels return False."""
        lifecycle = get_lifecycle()
        content = HtmlContent(html="<div>x</div>")
        config = WindowConfig()
        assert lifecycle.store_content_for_refresh("missing", content, config) is False

    def test_store_content_for_refresh_destroyed(self):
        """Destroyed windows return False."""
        lifecycle = get_lifecycle()
        r = WindowResources(label="d")
        r.is_destroyed = True
        lifecycle._windows["d"] = r
        content = HtmlContent(html="<div>x</div>")
        config = WindowConfig()
        assert lifecycle.store_content_for_refresh("d", content, config) is False

    def test_store_content_for_refresh_success(self):
        """Stores last_content/last_config on success."""
        lifecycle = get_lifecycle()
        lifecycle._windows["x"] = WindowResources(label="x")
        content = HtmlContent(html="<div>x</div>")
        config = WindowConfig()
        ok = lifecycle.store_content_for_refresh("x", content, config)
        assert ok is True
        res = lifecycle.get("x")
        assert res.last_content is content
        assert res.last_config is config

    def test_get_content_for_refresh_unknown(self):
        """Unknown windows return (None, None)."""
        lifecycle = get_lifecycle()
        assert lifecycle.get_content_for_refresh("missing") == (None, None)

    def test_get_content_for_refresh_destroyed(self):
        """Destroyed windows return (None, None)."""
        lifecycle = get_lifecycle()
        r = WindowResources(label="d")
        r.is_destroyed = True
        lifecycle._windows["d"] = r
        assert lifecycle.get_content_for_refresh("d") == (None, None)

    def test_get_content_for_refresh_success(self):
        """Stored content/config returned correctly."""
        lifecycle = get_lifecycle()
        r = WindowResources(label="x")
        content = HtmlContent(html="<a/>")
        config = WindowConfig()
        r.last_content = content
        r.last_config = config
        lifecycle._windows["x"] = r
        c, cfg = lifecycle.get_content_for_refresh("x")
        assert c is content
        assert cfg is config

    def test_add_watched_file_unknown(self):
        """Unknown windows return False."""
        lifecycle = get_lifecycle()
        assert lifecycle.add_watched_file("missing", Path("a.css"), "css") is False

    def test_add_watched_file_destroyed(self):
        """Destroyed windows return False."""
        lifecycle = get_lifecycle()
        r = WindowResources(label="d")
        r.is_destroyed = True
        lifecycle._windows["d"] = r
        assert lifecycle.add_watched_file("d", Path("a.css"), "css") is False

    def test_add_watched_file_css(self):
        """CSS file gets tracked, including asset_id."""
        lifecycle = get_lifecycle()
        lifecycle._windows["x"] = WindowResources(label="x")
        path = Path("a.css")
        ok = lifecycle.add_watched_file("x", path, "css", asset_id="aid-1")
        assert ok is True
        res = lifecycle.get("x")
        assert path in res.watched_css
        assert res.css_asset_ids[path] == "aid-1"

    def test_add_watched_file_css_no_asset_id(self):
        """CSS file tracked without asset_id."""
        lifecycle = get_lifecycle()
        lifecycle._windows["x"] = WindowResources(label="x")
        path = Path("a.css")
        ok = lifecycle.add_watched_file("x", path, "css")
        assert ok is True

    def test_add_watched_file_css_duplicate_ignored(self):
        """Duplicate CSS file is not re-appended."""
        lifecycle = get_lifecycle()
        lifecycle._windows["x"] = WindowResources(label="x")
        path = Path("a.css")
        lifecycle.add_watched_file("x", path, "css")
        lifecycle.add_watched_file("x", path, "css")
        assert lifecycle.get("x").watched_css.count(path) == 1

    def test_add_watched_file_script(self):
        """Script file tracked successfully."""
        lifecycle = get_lifecycle()
        lifecycle._windows["x"] = WindowResources(label="x")
        path = Path("a.js")
        ok = lifecycle.add_watched_file("x", path, "script")
        assert ok is True
        res = lifecycle.get("x")
        assert path in res.watched_scripts

    def test_add_watched_file_script_duplicate(self):
        """Duplicate script file not re-appended."""
        lifecycle = get_lifecycle()
        lifecycle._windows["x"] = WindowResources(label="x")
        path = Path("a.js")
        lifecycle.add_watched_file("x", path, "script")
        lifecycle.add_watched_file("x", path, "script")
        assert lifecycle.get("x").watched_scripts.count(path) == 1

    def test_clear_watched_files_unknown(self):
        """Returns False for unknown window."""
        lifecycle = get_lifecycle()
        assert lifecycle.clear_watched_files("missing") is False

    def test_clear_watched_files_success(self):
        """Clears all watched files."""
        lifecycle = get_lifecycle()
        r = WindowResources(label="x")
        r.watched_css.append(Path("a.css"))
        r.watched_scripts.append(Path("a.js"))
        r.css_asset_ids[Path("a.css")] = "aid"
        lifecycle._windows["x"] = r
        ok = lifecycle.clear_watched_files("x")
        assert ok is True
        assert r.watched_css == []
        assert r.watched_scripts == []
        assert r.css_asset_ids == {}

    def test_add_script_unknown(self):
        """add_script returns False on missing window."""
        lifecycle = get_lifecycle()
        assert lifecycle.add_script("missing", "n") is False

    def test_add_script_destroyed(self):
        """add_script returns False on destroyed window."""
        lifecycle = get_lifecycle()
        r = WindowResources(label="d")
        r.is_destroyed = True
        lifecycle._windows["d"] = r
        assert lifecycle.add_script("d", "n") is False

    def test_add_script_dedup(self):
        """add_script does not duplicate entries."""
        lifecycle = get_lifecycle()
        lifecycle._windows["x"] = WindowResources(label="x")
        lifecycle.add_script("x", "s1")
        lifecycle.add_script("x", "s1")
        assert lifecycle.get("x").scripts_injected == ["s1"]

    def test_add_library(self):
        """add_library tracks libraries with dedup."""
        lifecycle = get_lifecycle()
        lifecycle._windows["x"] = WindowResources(label="x")
        assert lifecycle.add_library("x", "plotly") is True
        assert lifecycle.add_library("x", "plotly") is True
        assert lifecycle.get("x").libraries_loaded == ["plotly"]

    def test_add_library_unknown(self):
        """add_library on missing returns False."""
        lifecycle = get_lifecycle()
        assert lifecycle.add_library("missing", "p") is False

    def test_add_library_destroyed(self):
        """add_library on destroyed returns False."""
        lifecycle = get_lifecycle()
        r = WindowResources(label="d")
        r.is_destroyed = True
        lifecycle._windows["d"] = r
        assert lifecycle.add_library("d", "p") is False

    def test_set_get_data(self):
        """set_data and get_data round-trip."""
        lifecycle = get_lifecycle()
        lifecycle._windows["x"] = WindowResources(label="x")
        assert lifecycle.set_data("x", "k", 42) is True
        assert lifecycle.get_data("x", "k") == 42
        assert lifecycle.get_data("x", "missing", "fallback") == "fallback"

    def test_set_data_unknown(self):
        """set_data returns False for unknown window."""
        lifecycle = get_lifecycle()
        assert lifecycle.set_data("missing", "k", 1) is False

    def test_set_data_destroyed(self):
        """set_data on destroyed returns False."""
        lifecycle = get_lifecycle()
        r = WindowResources(label="d")
        r.is_destroyed = True
        lifecycle._windows["d"] = r
        assert lifecycle.set_data("d", "k", 1) is False

    def test_get_data_unknown_returns_default(self):
        """get_data on missing window returns default."""
        lifecycle = get_lifecycle()
        assert lifecycle.get_data("missing", "k", "def") == "def"

    def test_get_data_destroyed_returns_default(self):
        """get_data on destroyed returns default."""
        lifecycle = get_lifecycle()
        r = WindowResources(label="d")
        r.is_destroyed = True
        lifecycle._windows["d"] = r
        assert lifecycle.get_data("d", "k", "def") == "def"

    def test_destroy_unknown(self):
        """destroy on missing returns False."""
        lifecycle = get_lifecycle()
        assert lifecycle.destroy("missing") is False

    def test_destroy_already_destroyed(self):
        """destroy on already-destroyed returns False."""
        lifecycle = get_lifecycle()
        r = WindowResources(label="d")
        r.is_destroyed = True
        lifecycle._windows["d"] = r
        assert lifecycle.destroy("d") is False

    def test_destroy_fires_callbacks(self):
        """destroy invokes on_close callbacks before cleanup."""
        lifecycle = get_lifecycle()
        r = WindowResources(label="x")
        called: list[tuple[str, str]] = []
        r.on_close.append(lambda lbl, reason: called.append((lbl, reason)))
        lifecycle._windows["x"] = r
        with patch("pywry.runtime.close_window", return_value=True):
            assert lifecycle.destroy("x") is True
        assert called == [("x", "programmatic")]
        assert "x" not in lifecycle._windows

    def test_destroy_swallows_callback_errors(self):
        """destroy continues when on_close handlers raise."""
        lifecycle = get_lifecycle()
        r = WindowResources(label="x")

        def boom(_lbl, _reason):
            raise ValueError("boom")

        r.on_close.append(boom)
        lifecycle._windows["x"] = r
        with patch("pywry.runtime.close_window", return_value=True):
            assert lifecycle.destroy("x") is True

    def test_destroy_all(self):
        """destroy_all closes all tracked windows and returns count."""
        lifecycle = get_lifecycle()
        lifecycle._windows["a"] = WindowResources(label="a")
        lifecycle._windows["b"] = WindowResources(label="b")
        with patch("pywry.runtime.close_window", return_value=True):
            count = lifecycle.destroy_all()
        assert count == 2

    def test_destroy_all_empty(self):
        """destroy_all returns 0 when nothing tracked."""
        lifecycle = get_lifecycle()
        assert lifecycle.destroy_all() == 0

    def test_get_lifecycle_creates_holder_instance(self):
        """get_lifecycle initializes the holder when None."""
        # Access then reset to ensure path covered
        _LifecycleHolder.instance = None
        instance = get_lifecycle()
        assert instance is not None
        # second call should return same instance
        assert get_lifecycle() is instance


# =============================================================================
# WindowController tests
# =============================================================================


class TestWindowController:
    """Tests for WindowController dispatch logic."""

    def test_init_default_mode(self):
        """Default mode is NEW_WINDOW."""
        c = WindowController()
        assert c.mode == WindowMode.NEW_WINDOW
        assert isinstance(c._mode, NewWindowMode)

    def test_init_single_window(self):
        """Initialize with SINGLE_WINDOW mode."""
        c = WindowController(WindowMode.SINGLE_WINDOW)
        assert c.mode == WindowMode.SINGLE_WINDOW
        assert isinstance(c._mode, SingleWindowMode)

    def test_init_multi_window(self):
        """Initialize with MULTI_WINDOW mode."""
        c = WindowController(WindowMode.MULTI_WINDOW)
        assert c.mode == WindowMode.MULTI_WINDOW
        assert isinstance(c._mode, MultiWindowMode)

    def test_init_unknown_mode_falls_through_to_multi(self):
        """Unknown enum-value falls through to MultiWindowMode (else branch)."""
        # Use NOTEBOOK which is not specifically handled
        c = WindowController(WindowMode.NOTEBOOK)
        assert isinstance(c._mode, MultiWindowMode)

    def test_set_mode_no_op_when_same(self):
        """Setting the same mode is a no-op."""
        c = WindowController(WindowMode.NEW_WINDOW)
        original_mode = c._mode
        c.set_mode(WindowMode.NEW_WINDOW)
        assert c._mode is original_mode

    def test_set_mode_changes_handler_and_closes_old(self):
        """set_mode closes existing windows and swaps the handler."""
        c = WindowController(WindowMode.NEW_WINDOW)
        with patch.object(c._mode, "close_all", return_value=0) as close_all:
            c.set_mode(WindowMode.MULTI_WINDOW)
            close_all.assert_called_once()
        assert c.mode == WindowMode.MULTI_WINDOW
        assert isinstance(c._mode, MultiWindowMode)

    def test_show_delegates(self):
        """show() forwards to mode handler."""
        c = WindowController(WindowMode.NEW_WINDOW)
        with patch.object(c._mode, "show", return_value="lbl") as show_mock:
            result = c.show(WindowConfig(), "<html>", callbacks=None)
        assert result == "lbl"
        show_mock.assert_called_once()

    def test_close_delegates(self):
        """close() forwards to mode handler."""
        c = WindowController(WindowMode.NEW_WINDOW)
        with patch.object(c._mode, "close", return_value=True) as close_mock:
            assert c.close("lbl") is True
        close_mock.assert_called_once_with("lbl")

    def test_close_all_delegates(self):
        """close_all() forwards to mode handler."""
        c = WindowController(WindowMode.NEW_WINDOW)
        with patch.object(c._mode, "close_all", return_value=3):
            assert c.close_all() == 3

    def test_is_open_delegates(self):
        """is_open() forwards to mode handler."""
        c = WindowController(WindowMode.NEW_WINDOW)
        with patch.object(c._mode, "is_open", return_value=True) as mock:
            assert c.is_open("x") is True
        mock.assert_called_once_with("x")

    def test_update_content_delegates(self):
        """update_content() forwards to mode handler."""
        c = WindowController(WindowMode.NEW_WINDOW)
        with patch.object(c._mode, "update_content", return_value=True) as mock:
            assert c.update_content("x", "<html>", "light") is True
        mock.assert_called_once_with("x", "<html>", "light")

    def test_send_event_delegates(self):
        """send_event() forwards to mode handler."""
        c = WindowController(WindowMode.NEW_WINDOW)
        with patch.object(c._mode, "send_event", return_value=True) as mock:
            assert c.send_event("x", "evt", {"a": 1}) is True
        mock.assert_called_once_with("x", "evt", {"a": 1})

    def test_get_labels_delegates(self):
        """get_labels() forwards to mode handler."""
        c = WindowController(WindowMode.NEW_WINDOW)
        with patch.object(c._mode, "get_labels", return_value=["a", "b"]):
            assert c.get_labels() == ["a", "b"]

    def test_get_stats(self):
        """get_stats includes mode, window count, labels and lifecycle stats."""
        c = WindowController(WindowMode.MULTI_WINDOW)
        with patch.object(c._mode, "get_labels", return_value=["a"]):
            stats = c.get_stats()
        assert stats["mode"] == "multi_window"
        assert stats["window_count"] == 1
        assert stats["labels"] == ["a"]
        assert "lifecycle" in stats


# =============================================================================
# WindowModeBase show_window/hide_window
# =============================================================================


class _TestableMode(WindowModeBase):
    """Concrete subclass exposing only the abstract methods for base testing."""

    def show(self, config, html, callbacks=None, label=None):  # type: ignore[override]
        return label or "x"

    def close(self, label):  # type: ignore[override]
        return True

    def is_open(self, label):  # type: ignore[override]
        return True

    def update_content(self, label, html, theme="dark"):  # type: ignore[override]
        return True

    def send_event(self, label, event_type, data):  # type: ignore[override]
        return True

    def get_labels(self):  # type: ignore[override]
        return []

    def close_all(self):  # type: ignore[override]
        return 0


class TestWindowModeBase:
    """Tests for the default show_window/hide_window implementations on the base."""

    def test_show_window(self):
        """Base show_window delegates to runtime.show_window."""
        m = _TestableMode()
        with patch("pywry.runtime.show_window", return_value=True) as mock:
            assert m.show_window("x") is True
        mock.assert_called_once_with("x")

    def test_hide_window(self):
        """Base hide_window delegates to runtime.hide_window."""
        m = _TestableMode()
        with patch("pywry.runtime.hide_window", return_value=False) as mock:
            assert m.hide_window("x") is False
        mock.assert_called_once_with("x")


# =============================================================================
# NewWindowMode tests
# =============================================================================


class TestNewWindowModeUnit:
    """Unit tests for NewWindowMode using mocks."""

    def test_generate_label_unique(self):
        """Generated labels are unique and follow the prefix pattern."""
        m = NewWindowMode()
        a = m._generate_label("foo")
        b = m._generate_label("foo")
        assert a != b
        assert a.startswith("foo-")

    def test_show_creates_window(self):
        """show() creates window via lifecycle and sends content."""
        m = NewWindowMode()
        config = WindowConfig(theme=ThemeMode.DARK)
        with patch("pywry.window_manager.modes.new_window.get_lifecycle") as gl_mock:
            life = MagicMock()
            gl_mock.return_value = life
            label = m.show(config, "<html>")
        assert label.startswith("pywry-")
        life.create.assert_called_once()
        life.set_content.assert_called_once()
        assert m._windows[label] is True

    def test_show_with_callbacks(self):
        """show() registers callbacks."""
        m = NewWindowMode()
        config = WindowConfig(theme=ThemeMode.LIGHT)

        def my_cb(_data, _et, _label):
            pass

        with patch("pywry.window_manager.modes.new_window.get_lifecycle"):
            label = m.show(config, "<html>", callbacks={"app:foo": my_cb})

        registry = get_registry()
        # The callback should be reachable
        dispatched = registry.dispatch(label, "app:foo", {"x": 1})
        assert dispatched

    def test_show_with_explicit_label(self):
        """show() honors explicit label parameter."""
        m = NewWindowMode()
        config = WindowConfig()
        with patch("pywry.window_manager.modes.new_window.get_lifecycle"):
            label = m.show(config, "<html>", label="explicit-label")
        assert label == "explicit-label"

    def test_show_theme_light_branch(self):
        """show() converts non-dark/system themes to 'light'."""
        m = NewWindowMode()
        config = WindowConfig(theme=ThemeMode.LIGHT)
        with patch("pywry.window_manager.modes.new_window.get_lifecycle") as gl_mock:
            life = MagicMock()
            gl_mock.return_value = life
            m.show(config, "<html>")
        # Inspect set_content call args
        args, kwargs = life.set_content.call_args
        # 4th positional or theme kwarg
        assert "light" in args or kwargs.get("theme") == "light"

    def test_window_hidden_callback_updates_visibility(self):
        """window:hidden callback marks window as not visible."""
        m = NewWindowMode()
        with patch("pywry.window_manager.modes.new_window.get_lifecycle"):
            label = m.show(WindowConfig(), "<html>")
        registry = get_registry()
        registry.dispatch(label, "window:hidden", {})
        registry._drain(timeout=2.0)
        assert m._windows[label] is False

    def test_window_closed_callback_removes(self):
        """window:closed callback removes the window from tracking."""
        m = NewWindowMode()
        with patch("pywry.window_manager.modes.new_window.get_lifecycle"):
            label = m.show(WindowConfig(), "<html>")
        registry = get_registry()
        registry.dispatch(label, "window:closed", {})
        registry._drain(timeout=2.0)
        assert label not in m._windows

    def test_close_unknown(self):
        """close on missing label warns and returns False."""
        m = NewWindowMode()
        assert m.close("missing") is False

    def test_close_known(self):
        """close on known label destroys lifecycle and removes tracking."""
        m = NewWindowMode()
        m._windows["x"] = True
        with patch("pywry.window_manager.modes.new_window.get_lifecycle") as gl:
            life = MagicMock()
            gl.return_value = life
            assert m.close("x") is True
        life.destroy.assert_called_once_with("x")
        assert "x" not in m._windows

    def test_is_open_true(self):
        """is_open returns True when both visible and lifecycle exists."""
        m = NewWindowMode()
        m._windows["x"] = True
        with patch("pywry.window_manager.modes.new_window.get_lifecycle") as gl:
            life = MagicMock()
            life.exists.return_value = True
            gl.return_value = life
            assert m.is_open("x") is True

    def test_is_open_false_invisible(self):
        """is_open returns False when not visible."""
        m = NewWindowMode()
        m._windows["x"] = False
        assert m.is_open("x") is False

    def test_is_open_false_missing(self):
        """is_open returns False for missing label."""
        m = NewWindowMode()
        assert m.is_open("missing") is False

    def test_update_content_unknown(self):
        """update_content for unknown returns False."""
        m = NewWindowMode()
        assert m.update_content("missing", "<html>") is False

    def test_update_content_known(self):
        """update_content delegates to lifecycle.set_content."""
        m = NewWindowMode()
        m._windows["x"] = True
        with patch("pywry.window_manager.modes.new_window.get_lifecycle") as gl:
            life = MagicMock()
            gl.return_value = life
            assert m.update_content("x", "<html>", "light") is True
        life.set_content.assert_called_once_with("x", "<html>", "light")

    def test_send_event_unknown(self):
        """send_event for unknown returns False."""
        m = NewWindowMode()
        assert m.send_event("missing", "evt", {}) is False

    def test_send_event_known(self):
        """send_event delegates to runtime.emit_event."""
        m = NewWindowMode()
        m._windows["x"] = True
        with patch("pywry.runtime.emit_event", return_value=True) as emit_mock:
            assert m.send_event("x", "app:evt", {"a": 1}) is True
        emit_mock.assert_called_once_with("x", "app:evt", {"a": 1})

    def test_get_labels_returns_visible(self):
        """get_labels returns only visible labels."""
        m = NewWindowMode()
        m._windows["a"] = True
        m._windows["b"] = False
        labels = m.get_labels()
        assert "a" in labels
        assert "b" not in labels

    def test_close_all(self):
        """close_all closes every tracked window."""
        m = NewWindowMode()
        m._windows["a"] = True
        m._windows["b"] = False
        with patch("pywry.window_manager.modes.new_window.get_lifecycle") as gl:
            gl.return_value = MagicMock()
            count = m.close_all()
        assert count == 2
        assert m._windows == {}


# =============================================================================
# MultiWindowMode tests
# =============================================================================


class TestMultiWindowModeUnit:
    """Unit tests for MultiWindowMode."""

    def test_generate_label(self):
        """Auto-generated labels start with given prefix."""
        m = MultiWindowMode()
        lbl = m._generate_label("chart")
        assert lbl.startswith("chart-")

    def test_show_creates_new_window_with_auto_label(self):
        """show() creates new window with auto-generated label."""
        m = MultiWindowMode()
        config = WindowConfig(title="My App", theme=ThemeMode.DARK)
        with patch("pywry.window_manager.modes.multi_window.get_lifecycle") as gl:
            life = MagicMock()
            gl.return_value = life
            label = m.show(config, "<html>")
        assert label.startswith("my-app-")
        assert m._windows[label] is True

    def test_show_creates_new_window_with_explicit_label(self):
        """Explicit label is used when window doesn't already exist."""
        m = MultiWindowMode()
        config = WindowConfig(theme=ThemeMode.LIGHT)
        with patch("pywry.window_manager.modes.multi_window.get_lifecycle"):
            label = m.show(config, "<html>", label="my-window")
        assert label == "my-window"

    def test_show_updates_existing(self):
        """show() with existing label updates content (no recreate)."""
        m = MultiWindowMode()
        m._windows["existing"] = True
        config = WindowConfig(theme=ThemeMode.DARK)
        with patch("pywry.window_manager.modes.multi_window.get_lifecycle") as gl:
            life = MagicMock()
            gl.return_value = life
            label = m.show(config, "<html>", label="existing")
        # No create call, only set_content
        life.create.assert_not_called()
        life.set_content.assert_called_once()
        assert label == "existing"

    def test_show_with_callbacks_new(self):
        """Callbacks registered for newly created window."""
        m = MultiWindowMode()
        config = WindowConfig(theme=ThemeMode.SYSTEM)

        def cb(_d, _e, _l):
            pass

        with patch("pywry.window_manager.modes.multi_window.get_lifecycle"):
            label = m.show(config, "<html>", callbacks={"app:evt": cb}, label="lbl")
        registry = get_registry()
        assert registry.dispatch(label, "app:evt", {})

    def test_show_with_callbacks_existing(self):
        """Callbacks registered when updating existing window."""
        m = MultiWindowMode()
        m._windows["existing"] = True
        config = WindowConfig(theme=ThemeMode.LIGHT)

        def cb(_d, _e, _l):
            pass

        with patch("pywry.window_manager.modes.multi_window.get_lifecycle"):
            m.show(config, "<html>", callbacks={"app:evt": cb}, label="existing")
        registry = get_registry()
        assert registry.dispatch("existing", "app:evt", {})

    def test_window_hidden_callback(self):
        """window:hidden marks visibility False."""
        m = MultiWindowMode()
        with patch("pywry.window_manager.modes.multi_window.get_lifecycle"):
            label = m.show(WindowConfig(), "<html>", label="lbl")
        registry = get_registry()
        registry.dispatch(label, "window:hidden", {})
        registry._drain(timeout=2.0)
        assert m._windows[label] is False

    def test_window_closed_callback(self):
        """window:closed removes label from tracking."""
        m = MultiWindowMode()
        with patch("pywry.window_manager.modes.multi_window.get_lifecycle"):
            label = m.show(WindowConfig(), "<html>", label="lbl")
        registry = get_registry()
        registry.dispatch(label, "window:closed", {})
        registry._drain(timeout=2.0)
        assert label not in m._windows

    def test_close_unknown(self):
        """close() on unknown returns False."""
        m = MultiWindowMode()
        assert m.close("missing") is False

    def test_close_known(self):
        """close() on known destroys lifecycle and removes tracking."""
        m = MultiWindowMode()
        m._windows["x"] = True
        with patch("pywry.window_manager.modes.multi_window.get_lifecycle") as gl:
            life = MagicMock()
            gl.return_value = life
            assert m.close("x") is True
        life.destroy.assert_called_once_with("x")
        assert "x" not in m._windows

    def test_is_open_present(self):
        """is_open returns True when visible and lifecycle exists."""
        m = MultiWindowMode()
        m._windows["x"] = True
        with patch("pywry.window_manager.modes.multi_window.get_lifecycle") as gl:
            life = MagicMock()
            life.exists.return_value = True
            gl.return_value = life
            assert m.is_open("x") is True

    def test_is_open_false_when_hidden(self):
        """is_open returns False when not visible."""
        m = MultiWindowMode()
        m._windows["x"] = False
        assert m.is_open("x") is False

    def test_update_content_unknown(self):
        """update_content unknown returns False."""
        m = MultiWindowMode()
        assert m.update_content("missing", "<html>") is False

    def test_update_content_success(self):
        """update_content delegates to lifecycle."""
        m = MultiWindowMode()
        m._windows["x"] = True
        with patch("pywry.window_manager.modes.multi_window.get_lifecycle") as gl:
            life = MagicMock()
            gl.return_value = life
            assert m.update_content("x", "<html>", "light") is True
        life.set_content.assert_called_once_with("x", "<html>", "light")

    def test_send_event_unknown(self):
        """send_event unknown returns False."""
        m = MultiWindowMode()
        assert m.send_event("missing", "evt", {}) is False

    def test_send_event_success(self):
        """send_event delegates to runtime.emit_event."""
        m = MultiWindowMode()
        m._windows["x"] = True
        with patch("pywry.runtime.emit_event", return_value=True) as emit:
            assert m.send_event("x", "evt", 42) is True
        emit.assert_called_once_with("x", "evt", 42)

    def test_send_event_all(self):
        """send_event_all sends to every tracked window."""
        m = MultiWindowMode()
        m._windows["a"] = True
        m._windows["b"] = True
        with patch("pywry.runtime.emit_event", return_value=True):
            count = m.send_event_all("evt", {})
        assert count == 2

    def test_send_event_all_partial_failure(self):
        """send_event_all counts only successful windows."""
        m = MultiWindowMode()
        m._windows["a"] = True
        m._windows["b"] = True
        with patch("pywry.runtime.emit_event", side_effect=[True, False]):
            count = m.send_event_all("evt", {})
        assert count == 1

    def test_get_labels_visible_only(self):
        """get_labels filters out hidden windows."""
        m = MultiWindowMode()
        m._windows["a"] = True
        m._windows["b"] = False
        labels = m.get_labels()
        assert "a" in labels
        assert "b" not in labels

    def test_close_all(self):
        """close_all closes every window and returns count."""
        m = MultiWindowMode()
        m._windows["a"] = True
        m._windows["b"] = False
        with patch("pywry.window_manager.modes.multi_window.get_lifecycle"):
            assert m.close_all() == 2

    def test_get_window_count(self):
        """get_window_count returns total tracked count."""
        m = MultiWindowMode()
        m._windows["a"] = True
        m._windows["b"] = False
        assert m.get_window_count() == 2

    def test_show_window_unknown(self):
        """show_window for unmanaged label returns False."""
        m = MultiWindowMode()
        assert m.show_window("missing") is False

    def test_show_window_success(self):
        """show_window delegates to runtime.show_window and updates visibility."""
        m = MultiWindowMode()
        m._windows["x"] = False
        with patch("pywry.runtime.show_window", return_value=True):
            assert m.show_window("x") is True
        assert m._windows["x"] is True

    def test_show_window_runtime_failure(self):
        """show_window respects runtime failure (does not change visibility)."""
        m = MultiWindowMode()
        m._windows["x"] = False
        with patch("pywry.runtime.show_window", return_value=False):
            assert m.show_window("x") is False
        assert m._windows["x"] is False

    def test_hide_window_unknown(self):
        """hide_window for unmanaged label returns False."""
        m = MultiWindowMode()
        assert m.hide_window("missing") is False

    def test_hide_window_success(self):
        """hide_window delegates to runtime.hide_window and updates tracking."""
        m = MultiWindowMode()
        m._windows["x"] = True
        with patch("pywry.runtime.hide_window", return_value=True):
            assert m.hide_window("x") is True
        assert m._windows["x"] is False

    def test_hide_window_runtime_failure(self):
        """hide_window respects runtime failure."""
        m = MultiWindowMode()
        m._windows["x"] = True
        with patch("pywry.runtime.hide_window", return_value=False):
            assert m.hide_window("x") is False
        assert m._windows["x"] is True


# =============================================================================
# SingleWindowMode tests
# =============================================================================


class TestSingleWindowModeUnit:
    """Unit tests for SingleWindowMode."""

    def test_init_default_label(self):
        """Default label is 'main'."""
        m = SingleWindowMode()
        assert m.label == "main"
        assert m._is_created is False
        assert m._is_visible is False

    def test_init_custom_label(self):
        """Custom label is honored."""
        m = SingleWindowMode("chart")
        assert m.label == "chart"

    def test_visibility_handler_registered(self):
        """window:hidden handler is registered at construction."""
        m = SingleWindowMode("custom")
        m._is_visible = True
        registry = get_registry()
        registry.dispatch("custom", "window:hidden", {})
        registry._drain(timeout=2.0)
        assert m._is_visible is False

    def test_ensure_window_runtime_start_failure(self):
        """_ensure_window returns silently if runtime won't start."""
        m = SingleWindowMode("x")
        lifecycle = MagicMock()
        config = WindowConfig()
        with (
            patch("pywry.runtime.is_running", return_value=False),
            patch("pywry.runtime.start", return_value=False),
        ):
            m._ensure_window(lifecycle, config)
        # No lifecycle register should happen
        lifecycle.register_window.assert_not_called()

    def test_ensure_window_existing_shows(self):
        """_ensure_window shows the existing window when already open."""
        m = SingleWindowMode("x")
        lifecycle = MagicMock()
        config = WindowConfig()
        with (
            patch("pywry.runtime.is_running", return_value=True),
            patch("pywry.runtime.check_window_open", return_value=True),
            patch("pywry.runtime.show_window", return_value=True),
        ):
            m._ensure_window(lifecycle, config)
        lifecycle.register_window.assert_called_once_with("x")

    def test_ensure_window_create_when_missing(self):
        """_ensure_window creates window when not yet open."""
        m = SingleWindowMode("x")
        lifecycle = MagicMock()
        config = WindowConfig()
        with (
            patch("pywry.runtime.is_running", return_value=True),
            patch("pywry.runtime.check_window_open", return_value=False),
            patch("pywry.runtime.create_window", return_value=True) as cw,
        ):
            m._ensure_window(lifecycle, config)
        cw.assert_called_once()

    def test_ensure_window_show_then_disappears(self):
        """_ensure_window retries when window disappears after show."""
        m = SingleWindowMode("x")
        lifecycle = MagicMock()
        config = WindowConfig()
        # First check: open. Show succeeds. Verify check returns False (gone).
        # Then second iteration also checks.
        check_results = [True, False, True, True]
        with (
            patch("pywry.runtime.is_running", return_value=True),
            patch("pywry.runtime.check_window_open", side_effect=check_results),
            patch("pywry.runtime.show_window", return_value=True),
            patch("pywry.runtime.create_window", return_value=True),
            patch("time.sleep"),
        ):
            m._ensure_window(lifecycle, config)

    def test_ensure_window_show_returns_false_then_succeeds(self):
        """_ensure_window retries when show_window initially fails."""
        m = SingleWindowMode("x")
        lifecycle = MagicMock()
        config = WindowConfig()
        # First: check open True, show False -> retry. Then check open True, show True, check True.
        with (
            patch("pywry.runtime.is_running", return_value=True),
            patch("pywry.runtime.check_window_open", side_effect=[True, True, True]),
            patch("pywry.runtime.show_window", side_effect=[False, True]),
            patch("time.sleep"),
        ):
            m._ensure_window(lifecycle, config)

    def test_ensure_window_create_failure_retries(self):
        """_ensure_window retries on create_window failures."""
        m = SingleWindowMode("x")
        lifecycle = MagicMock()
        config = WindowConfig()
        with (
            patch("pywry.runtime.is_running", return_value=True),
            patch("pywry.runtime.check_window_open", return_value=False),
            patch("pywry.runtime.create_window", side_effect=[False, True]),
            patch("time.sleep"),
        ):
            m._ensure_window(lifecycle, config)

    def test_ensure_window_all_retries_fail(self):
        """_ensure_window logs warning when retries exhausted but still calls register."""
        m = SingleWindowMode("x")
        lifecycle = MagicMock()
        config = WindowConfig()
        with (
            patch("pywry.runtime.is_running", return_value=True),
            patch("pywry.runtime.check_window_open", return_value=False),
            patch("pywry.runtime.create_window", return_value=False),
            patch("time.sleep"),
        ):
            m._ensure_window(lifecycle, config)
        # register_window still called despite failure
        lifecycle.register_window.assert_called_once_with("x")

    def test_show_creates_window_first_time(self):
        """show() creates window on first call."""
        m = SingleWindowMode("x")
        config = WindowConfig(theme=ThemeMode.DARK)
        with (
            patch("pywry.window_manager.modes.single_window.get_lifecycle") as gl,
            patch.object(m, "_ensure_window") as ensure,
        ):
            life = MagicMock()
            life.exists.side_effect = [False, True]
            gl.return_value = life
            label = m.show(config, "<html>")
        ensure.assert_called_once()
        assert label == "x"
        assert m._is_created is True
        assert m._is_visible is True

    def test_show_existing_window(self):
        """show() shows existing window without recreating."""
        m = SingleWindowMode("x")
        config = WindowConfig(theme=ThemeMode.LIGHT)
        with (
            patch("pywry.window_manager.modes.single_window.get_lifecycle") as gl,
            patch("pywry.runtime.show_window", return_value=True) as show,
        ):
            life = MagicMock()
            life.exists.return_value = True
            gl.return_value = life
            m.show(config, "<html>")
        show.assert_called()

    def test_show_with_callbacks(self):
        """show() registers callbacks."""
        m = SingleWindowMode("x")
        config = WindowConfig(theme=ThemeMode.DARK)

        def cb(_d, _e, _l):
            pass

        with (
            patch("pywry.window_manager.modes.single_window.get_lifecycle") as gl,
            patch("pywry.runtime.show_window", return_value=True),
        ):
            life = MagicMock()
            life.exists.return_value = True
            gl.return_value = life
            m.show(config, "<html>", callbacks={"app:evt": cb})
        registry = get_registry()
        assert registry.dispatch("x", "app:evt", {})

    def test_show_lifecycle_register_when_not_exists_after_show(self):
        """show() registers lifecycle if exists check fails after _ensure_window."""
        m = SingleWindowMode("x")
        config = WindowConfig()
        with (
            patch("pywry.window_manager.modes.single_window.get_lifecycle") as gl,
            patch.object(m, "_ensure_window"),
        ):
            life = MagicMock()
            # Initial exists False, then still False after ensure (so register hits)
            life.exists.side_effect = [False, False]
            gl.return_value = life
            m.show(config, "<html>")
        life.register_window.assert_called_once_with("x")

    def test_show_set_content_failure(self):
        """show() handles failed set_content gracefully."""
        m = SingleWindowMode("x")
        config = WindowConfig()
        with (
            patch("pywry.window_manager.modes.single_window.get_lifecycle") as gl,
            patch.object(m, "_ensure_window"),
        ):
            life = MagicMock()
            life.exists.return_value = True
            life.set_content.return_value = False
            gl.return_value = life
            label = m.show(config, "<html>")
        assert label == "x"

    def test_close_wrong_label(self):
        """close on wrong label returns False."""
        m = SingleWindowMode("x")
        m._is_created = True
        assert m.close("y") is False

    def test_close_not_created(self):
        """close when window not yet created returns False."""
        m = SingleWindowMode("x")
        assert m.close("x") is False

    def test_close_success(self):
        """close marks lifecycle destroyed and stops tracking."""
        m = SingleWindowMode("x")
        m._is_created = True
        m._is_visible = True
        with (
            patch("pywry.window_manager.modes.single_window.get_lifecycle") as gl,
            patch("pywry.runtime.close_window", return_value=True),
            patch("pywry.runtime.check_window_open", return_value=False),
            patch("time.sleep"),
        ):
            life = MagicMock()
            res = WindowResources(label="x")
            life.get.return_value = res
            gl.return_value = life
            assert m.close("x") is True
            assert res.is_destroyed is True
        assert m._is_created is False
        assert m._is_visible is False

    def test_close_no_resources_in_lifecycle(self):
        """close handles missing lifecycle resources without crashing."""
        m = SingleWindowMode("x")
        m._is_created = True
        with (
            patch("pywry.window_manager.modes.single_window.get_lifecycle") as gl,
            patch("pywry.runtime.close_window", return_value=True),
            patch("pywry.runtime.check_window_open", return_value=False),
            patch("time.sleep"),
        ):
            life = MagicMock()
            life.get.return_value = None
            gl.return_value = life
            assert m.close("x") is True

    def test_close_close_not_confirmed(self):
        """close logs debug when timeout reached without confirmation."""
        m = SingleWindowMode("x")
        m._is_created = True
        with (
            patch("pywry.window_manager.modes.single_window.get_lifecycle") as gl,
            patch("pywry.runtime.close_window", return_value=True),
            patch("pywry.runtime.check_window_open", return_value=True),
            patch("time.sleep"),
        ):
            life = MagicMock()
            life.get.return_value = None
            gl.return_value = life
            assert m.close("x") is True

    def test_is_open_true(self):
        """is_open when label matches and created."""
        m = SingleWindowMode("x")
        m._is_created = True
        assert m.is_open("x") is True

    def test_is_open_wrong_label(self):
        """is_open False when label mismatch."""
        m = SingleWindowMode("x")
        m._is_created = True
        assert m.is_open("y") is False

    def test_is_open_not_created(self):
        """is_open False when not yet created."""
        m = SingleWindowMode("x")
        assert m.is_open("x") is False

    def test_update_content_wrong_label(self):
        """update_content fails when label mismatch."""
        m = SingleWindowMode("x")
        m._is_created = True
        assert m.update_content("y", "<html>") is False

    def test_update_content_not_created(self):
        """update_content fails when not yet created."""
        m = SingleWindowMode("x")
        assert m.update_content("x", "<html>") is False

    def test_update_content_success(self):
        """update_content delegates to lifecycle."""
        m = SingleWindowMode("x")
        m._is_created = True
        with patch("pywry.window_manager.modes.single_window.get_lifecycle") as gl:
            life = MagicMock()
            gl.return_value = life
            assert m.update_content("x", "<html>", "light") is True
        life.set_content.assert_called_once_with("x", "<html>", "light")

    def test_send_event_wrong_label(self):
        """send_event wrong label returns False."""
        m = SingleWindowMode("x")
        m._is_created = True
        assert m.send_event("y", "e", {}) is False

    def test_send_event_not_created(self):
        """send_event not created returns False."""
        m = SingleWindowMode("x")
        assert m.send_event("x", "e", {}) is False

    def test_send_event_success(self):
        """send_event delegates to runtime.emit_event."""
        m = SingleWindowMode("x")
        m._is_created = True
        with patch("pywry.runtime.emit_event", return_value=True) as emit:
            assert m.send_event("x", "evt", {"a": 1}) is True
        emit.assert_called_once_with("x", "evt", {"a": 1})

    def test_get_labels_visible(self):
        """get_labels returns label only when visible."""
        m = SingleWindowMode("x")
        m._is_visible = True
        assert m.get_labels() == ["x"]

    def test_get_labels_hidden(self):
        """get_labels returns empty when not visible."""
        m = SingleWindowMode("x")
        assert m.get_labels() == []

    def test_close_all_when_created(self):
        """close_all closes the single window if created."""
        m = SingleWindowMode("x")
        m._is_created = True
        with patch.object(m, "close", return_value=True) as close_mock:
            assert m.close_all() == 1
        close_mock.assert_called_once_with("x")

    def test_close_all_when_not_created(self):
        """close_all returns 0 when not created."""
        m = SingleWindowMode("x")
        assert m.close_all() == 0


# =============================================================================
# BrowserMode tests
# =============================================================================


class FakeWidget:
    """Stand-in for InlineWidget used in BrowserMode tests."""

    def __init__(self, widget_id: str):
        self.widget_id = widget_id
        self.opened = False
        self.updates: list[str] = []
        self.events: list[tuple[str, Any]] = []

    def open_in_browser(self):
        self.opened = True

    def update_html(self, html: str):
        self.updates.append(html)

    def emit(self, event_type: str, data: Any):
        self.events.append((event_type, data))


class TestBrowserModeUnit:
    """Unit tests for BrowserMode that mock the inline module."""

    def test_init_empty(self):
        """Newly constructed mode has no widgets."""
        m = BrowserMode()
        assert m._widgets == {}

    def test_show_basic_dark_default(self):
        """show() creates widget and opens browser with dark theme by default."""
        m = BrowserMode()
        config = WindowConfig(title="T", height=480)
        widget = FakeWidget("wid-1")
        with patch("pywry.inline.show", return_value=widget) as inline_show:
            wid_id = m.show(config, "<html>")
        assert wid_id == "wid-1"
        assert widget.opened is True
        assert m._widgets["wid-1"] is widget
        # Theme inferred from config - default is DARK
        kwargs = inline_show.call_args.kwargs
        assert kwargs["theme"] == "dark"
        assert kwargs["title"] == "T"
        assert kwargs["height"] == 480
        assert kwargs["width"] == "100%"

    def test_show_theme_light_string(self):
        """If config.theme is string 'light', theme is light."""
        m = BrowserMode()

        class StringThemeConfig:
            title = "T"
            height = 480
            theme = "light"

        widget = FakeWidget("w")
        with patch("pywry.inline.show", return_value=widget) as inline_show:
            m.show(StringThemeConfig(), "<html>")
        assert inline_show.call_args.kwargs["theme"] == "light"

    def test_show_theme_no_theme_attr(self):
        """If config has no theme attr, defaults to dark."""
        m = BrowserMode()

        class NoThemeConfig:
            title = "T"
            height = 480

        widget = FakeWidget("w")
        with patch("pywry.inline.show", return_value=widget) as inline_show:
            m.show(NoThemeConfig(), "<html>")
        assert inline_show.call_args.kwargs["theme"] == "dark"

    def test_show_theme_value_dark(self):
        """ThemeMode enum DARK -> 'dark'."""
        m = BrowserMode()
        config = WindowConfig(theme=ThemeMode.DARK)
        widget = FakeWidget("w")
        with patch("pywry.inline.show", return_value=widget) as inline_show:
            m.show(config, "<html>")
        assert inline_show.call_args.kwargs["theme"] == "dark"

    def test_show_theme_value_light(self):
        """ThemeMode enum LIGHT -> 'light'."""
        m = BrowserMode()
        config = WindowConfig(theme=ThemeMode.LIGHT)
        widget = FakeWidget("w")
        with patch("pywry.inline.show", return_value=widget) as inline_show:
            m.show(config, "<html>")
        assert inline_show.call_args.kwargs["theme"] == "light"

    def test_show_with_callbacks(self):
        """show() forwards callbacks to inline.show."""
        m = BrowserMode()
        config = WindowConfig()
        widget = FakeWidget("w")

        def cb(_d, _e, _l):
            pass

        with patch("pywry.inline.show", return_value=widget) as inline_show:
            m.show(config, "<html>", callbacks={"app:evt": cb})
        assert inline_show.call_args.kwargs["callbacks"] == {"app:evt": cb}

    def test_close_existing(self):
        """close() removes widget and triggers disconnect."""
        m = BrowserMode()
        widget = FakeWidget("w")
        m._widgets["w"] = widget
        with patch("pywry.inline._handle_widget_disconnect") as disc:
            assert m.close("w") is True
        disc.assert_called_once_with("w", "close_called")
        assert "w" not in m._widgets

    def test_close_unknown(self):
        """close() unknown returns False."""
        m = BrowserMode()
        assert m.close("missing") is False

    def test_close_all(self):
        """close_all closes every widget."""
        m = BrowserMode()
        m._widgets["a"] = FakeWidget("a")
        m._widgets["b"] = FakeWidget("b")
        with patch("pywry.inline._handle_widget_disconnect"):
            assert m.close_all() == 2
        assert m._widgets == {}

    def test_close_all_empty(self):
        """close_all returns 0 when no widgets."""
        m = BrowserMode()
        assert m.close_all() == 0

    def test_is_open(self):
        """is_open reflects tracking dict."""
        m = BrowserMode()
        m._widgets["a"] = FakeWidget("a")
        assert m.is_open("a") is True
        assert m.is_open("b") is False

    def test_update_content_unknown(self):
        """update_content unknown returns False."""
        m = BrowserMode()
        assert m.update_content("missing", "<html>") is False

    def test_update_content_success(self):
        """update_content delegates to widget.update_html."""
        m = BrowserMode()
        widget = FakeWidget("w")
        m._widgets["w"] = widget
        assert m.update_content("w", "<new>") is True
        assert widget.updates == ["<new>"]

    def test_send_event_unknown(self):
        """send_event unknown returns False."""
        m = BrowserMode()
        assert m.send_event("missing", "e", {}) is False

    def test_send_event_success(self):
        """send_event delegates to widget.emit."""
        m = BrowserMode()
        widget = FakeWidget("w")
        m._widgets["w"] = widget
        assert m.send_event("w", "evt", {"x": 1}) is True
        assert widget.events == [("evt", {"x": 1})]

    def test_get_labels(self):
        """get_labels returns widget IDs."""
        m = BrowserMode()
        m._widgets["a"] = FakeWidget("a")
        m._widgets["b"] = FakeWidget("b")
        labels = m.get_labels()
        assert set(labels) == {"a", "b"}

    def test_get_widget(self):
        """get_widget returns the actual widget instance or None."""
        m = BrowserMode()
        widget = FakeWidget("a")
        m._widgets["a"] = widget
        assert m.get_widget("a") is widget
        assert m.get_widget("missing") is None
