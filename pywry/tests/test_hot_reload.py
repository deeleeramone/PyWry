"""Unit tests for hot reload manager.

Tests cover:
- HotReloadManager initialization (defaults + injected dependencies)
- Start/stop lifecycle
- Window enable/disable for hot reload
- CSS injection
- Page refresh
- File change handling
- get_watched_files queries
- Global singleton get/stop functions
- All branches required for 100% coverage

Dependencies (FileWatcher, AssetLoader, callbacks) are injected via mocks
so we exercise HotReloadManager's logic directly.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import pywry.hot_reload as hot_reload_mod

from pywry.hot_reload import (
    HotReloadManager,
    get_hot_reload_manager,
    stop_hot_reload_manager,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_settings() -> MagicMock:
    """Mock HotReloadSettings with css_reload='inject' by default."""
    settings = MagicMock()
    settings.debounce_ms = 100
    settings.css_reload = "inject"
    settings.enabled = True
    return settings


@pytest.fixture
def mock_asset_loader() -> MagicMock:
    """Mock AssetLoader that resolves paths and returns non-empty CSS."""
    loader = MagicMock()
    loader.resolve_path = MagicMock(side_effect=lambda p: Path(p).resolve())
    loader.get_asset_id = MagicMock(side_effect=lambda p: f"asset_{p.name}")
    loader.load_css = MagicMock(return_value="body { color: red; }")
    loader.invalidate = MagicMock()
    return loader


@pytest.fixture
def mock_file_watcher() -> MagicMock:
    """Mock FileWatcher with no-op start/stop/watch methods."""
    return MagicMock()


@pytest.fixture
def manager(
    mock_settings: MagicMock,
    mock_asset_loader: MagicMock,
    mock_file_watcher: MagicMock,
) -> HotReloadManager:
    """HotReloadManager wired to all-mock dependencies."""
    return HotReloadManager(
        settings=mock_settings,
        asset_loader=mock_asset_loader,
        file_watcher=mock_file_watcher,
    )


def _make_content(
    css_files: list[Path] | None = None,
    script_files: list[Path] | None = None,
    watch: bool = True,
) -> MagicMock:
    """Create a mock HtmlContent."""
    content = MagicMock()
    content.css_files = css_files or []
    content.script_files = script_files or []
    content.watch = watch
    return content


# =============================================================================
# Initialization Tests
# =============================================================================


class TestHotReloadManagerInit:
    """Test HotReloadManager initialization."""

    def test_default_initialization_creates_real_settings(self) -> None:
        """With settings=None, a real HotReloadSettings is constructed."""
        with (
            patch("pywry.hot_reload.get_asset_loader") as mock_get_loader,
            patch("pywry.hot_reload.get_file_watcher") as mock_get_watcher,
        ):
            mock_get_loader.return_value = MagicMock()
            mock_get_watcher.return_value = MagicMock()

            manager = HotReloadManager()

            assert manager.is_running is False
            from pywry.config import HotReloadSettings

            assert isinstance(manager.settings, HotReloadSettings)

    def test_initialization_with_injected_dependencies(
        self,
        manager: HotReloadManager,
        mock_settings: MagicMock,
    ) -> None:
        """Injected settings are used and is_running starts False."""
        assert manager.settings is mock_settings
        assert manager.is_running is False


# =============================================================================
# Start/Stop Tests
# =============================================================================


class TestHotReloadManagerStartStop:
    """Test HotReloadManager start/stop lifecycle."""

    def test_start_starts_watcher(
        self, manager: HotReloadManager, mock_file_watcher: MagicMock
    ) -> None:
        """Starting the manager starts the underlying file watcher."""
        manager.start()
        assert manager.is_running is True
        mock_file_watcher.start.assert_called_once()

    def test_start_idempotent(
        self, manager: HotReloadManager, mock_file_watcher: MagicMock
    ) -> None:
        """Calling start twice only starts the watcher once."""
        manager.start()
        manager.start()
        mock_file_watcher.start.assert_called_once()

    def test_stop_stops_watcher(
        self, manager: HotReloadManager, mock_file_watcher: MagicMock
    ) -> None:
        """Stopping the manager stops the underlying file watcher."""
        manager.start()
        manager.stop()
        assert manager.is_running is False
        mock_file_watcher.stop.assert_called_once()

    def test_stop_without_start_is_safe(
        self, manager: HotReloadManager, mock_file_watcher: MagicMock
    ) -> None:
        """Stopping without starting does not call watcher.stop."""
        manager.stop()
        mock_file_watcher.stop.assert_not_called()


# =============================================================================
# Callback Configuration Tests
# =============================================================================


class TestCallbacks:
    """Test callback assignment."""

    def test_set_inject_css_callback(self, manager: HotReloadManager) -> None:
        """The configured callback is stored on the manager."""
        callback = MagicMock()
        manager.set_inject_css_callback(callback)
        assert manager._inject_css_callback is callback

    def test_set_refresh_callback(self, manager: HotReloadManager) -> None:
        """The configured refresh callback is stored on the manager."""
        callback = MagicMock()
        manager.set_refresh_callback(callback)
        assert manager._refresh_callback is callback


# =============================================================================
# Enable/Disable Window Tests
# =============================================================================


class TestEnableDisableWindow:
    """Test enabling/disabling hot reload for windows."""

    def test_enable_with_css_starts_watching(
        self,
        manager: HotReloadManager,
        mock_file_watcher: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Enabling for a window with CSS files registers each with the watcher."""
        css_file = tmp_path / "style.css"
        css_file.write_text("body {}")
        content = _make_content(css_files=[css_file])

        manager.enable_for_window("window1", content)

        mock_file_watcher.watch.assert_called_once()
        # Third positional arg is the label
        assert mock_file_watcher.watch.call_args[0][2] == "window1"

    def test_enable_with_script_starts_watching(
        self,
        manager: HotReloadManager,
        mock_file_watcher: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Enabling for a window with script files registers each with the watcher."""
        script_file = tmp_path / "app.js"
        script_file.write_text("console.log('hello');")
        content = _make_content(script_files=[script_file])

        manager.enable_for_window("window1", content)
        mock_file_watcher.watch.assert_called_once()

    def test_enable_with_watch_false_does_nothing(
        self,
        manager: HotReloadManager,
        mock_file_watcher: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Content with watch=False does not register any files."""
        css_file = tmp_path / "style.css"
        css_file.write_text("body {}")
        content = _make_content(css_files=[css_file], watch=False)

        manager.enable_for_window("window1", content)
        mock_file_watcher.watch.assert_not_called()

    def test_disable_for_window_unwatches(
        self,
        manager: HotReloadManager,
        mock_file_watcher: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Disabling for a window unwatches it from the underlying watcher."""
        css_file = tmp_path / "style.css"
        css_file.write_text("body {}")
        content = _make_content(css_files=[css_file])

        manager.enable_for_window("window1", content)
        manager.disable_for_window("window1")

        mock_file_watcher.unwatch_label.assert_called_once_with("window1")


# =============================================================================
# CSS Reload Tests
# =============================================================================


class TestReloadCss:
    """Test CSS reloading functionality."""

    def test_reload_css_success(self, manager: HotReloadManager, tmp_path: Path) -> None:
        """A successful reload invalidates the cache and invokes the callback."""
        css_file = tmp_path / "style.css"
        css_file.write_text("body { color: blue; }")
        content = _make_content(css_files=[css_file])

        inject_callback = MagicMock()
        manager.set_inject_css_callback(inject_callback)
        manager.enable_for_window("window1", content)

        result = manager.reload_css("window1")

        assert result is True
        inject_callback.assert_called_once()

    def test_reload_css_no_callback_returns_false(
        self, manager: HotReloadManager, tmp_path: Path
    ) -> None:
        """Without a configured callback, reload_css returns False."""
        css_file = tmp_path / "style.css"
        css_file.write_text("body {}")
        content = _make_content(css_files=[css_file])

        manager.enable_for_window("window1", content)
        result = manager.reload_css("window1")
        assert result is False

    def test_reload_css_unknown_window_returns_false(self, manager: HotReloadManager) -> None:
        """Reloading an unknown window returns False."""
        result = manager.reload_css("unknown_window")
        assert result is False

    def test_reload_css_with_unknown_path_returns_false(
        self, manager: HotReloadManager, tmp_path: Path
    ) -> None:
        """Passing a specific path not in css_files returns False."""
        css_file = tmp_path / "style.css"
        css_file.write_text("body {}")
        unknown_path = tmp_path / "other.css"
        content = _make_content(css_files=[css_file])

        manager.set_inject_css_callback(MagicMock())
        manager.enable_for_window("win1", content)

        result = manager.reload_css("win1", path=unknown_path)
        assert result is False

    def test_reload_css_callback_exception_returns_false(
        self, manager: HotReloadManager, tmp_path: Path
    ) -> None:
        """When inject_css_callback raises, reload_css logs and returns False."""
        css_file = tmp_path / "style.css"
        css_file.write_text("body {}")
        content = _make_content(css_files=[css_file])

        bad_cb = MagicMock(side_effect=RuntimeError("inject failed"))
        manager.set_inject_css_callback(bad_cb)
        manager.enable_for_window("win1", content)

        result = manager.reload_css("win1")
        assert result is False
        bad_cb.assert_called_once()

    def test_reload_css_empty_content_skips_callback(
        self,
        mock_settings: MagicMock,
        mock_file_watcher: MagicMock,
        tmp_path: Path,
    ) -> None:
        """When load_css returns empty content, the inject callback is not invoked."""
        css_file = tmp_path / "style.css"
        css_file.write_text("")

        loader = MagicMock()
        loader.resolve_path = MagicMock(side_effect=lambda p: Path(p).resolve())
        loader.get_asset_id = MagicMock(side_effect=lambda p: f"asset_{p.name}")
        loader.load_css = MagicMock(return_value="")  # empty
        loader.invalidate = MagicMock()

        content = _make_content(css_files=[css_file])
        manager = HotReloadManager(
            settings=mock_settings,
            asset_loader=loader,
            file_watcher=mock_file_watcher,
        )
        inject_cb = MagicMock()
        manager.set_inject_css_callback(inject_cb)
        manager.enable_for_window("win1", content)

        result = manager.reload_css("win1")
        assert result is False
        inject_cb.assert_not_called()


# =============================================================================
# Refresh Window Tests
# =============================================================================


class TestRefreshWindow:
    """Test window refresh functionality."""

    def test_refresh_window_success(self, manager: HotReloadManager) -> None:
        """A successful refresh invokes the configured callback."""
        refresh_callback = MagicMock()
        manager.set_refresh_callback(refresh_callback)

        result = manager.refresh_window("window1")

        assert result is True
        refresh_callback.assert_called_once_with("window1")

    def test_refresh_window_no_callback_returns_false(self, manager: HotReloadManager) -> None:
        """Without a refresh callback, refresh_window returns False."""
        result = manager.refresh_window("window1")
        assert result is False

    def test_refresh_window_callback_exception_returns_false(
        self, manager: HotReloadManager
    ) -> None:
        """A raising callback is caught and refresh_window returns False."""
        refresh_callback = MagicMock(side_effect=RuntimeError("Refresh failed"))
        manager.set_refresh_callback(refresh_callback)

        result = manager.refresh_window("window1")
        assert result is False


# =============================================================================
# File Change Handler Tests
# =============================================================================


class TestFileChangeHandler:
    """Test file change event handling and CSS reload modes."""

    def test_css_change_inject_mode_calls_inject_callback(
        self,
        mock_settings: MagicMock,
        mock_asset_loader: MagicMock,
        mock_file_watcher: MagicMock,
        tmp_path: Path,
    ) -> None:
        """CSS change with css_reload='inject' invokes the inject callback."""
        css_file = tmp_path / "style.css"
        css_file.write_text("body {}")

        mock_settings.css_reload = "inject"
        manager = HotReloadManager(
            settings=mock_settings,
            asset_loader=mock_asset_loader,
            file_watcher=mock_file_watcher,
        )

        inject_callback = MagicMock()
        manager.set_inject_css_callback(inject_callback)
        manager.enable_for_window("window1", _make_content(css_files=[css_file]))

        manager._on_file_change(mock_asset_loader.resolve_path(css_file), "window1")
        inject_callback.assert_called_once()

    def test_css_change_refresh_mode_calls_refresh_callback(
        self,
        mock_settings: MagicMock,
        mock_asset_loader: MagicMock,
        mock_file_watcher: MagicMock,
        tmp_path: Path,
    ) -> None:
        """CSS change with css_reload='refresh' triggers a full refresh."""
        css_file = tmp_path / "style.css"
        css_file.write_text("body {}")

        mock_settings.css_reload = "refresh"
        manager = HotReloadManager(
            settings=mock_settings,
            asset_loader=mock_asset_loader,
            file_watcher=mock_file_watcher,
        )

        refresh_callback = MagicMock()
        manager.set_refresh_callback(refresh_callback)
        manager.enable_for_window("window1", _make_content(css_files=[css_file]))

        manager._on_file_change(mock_asset_loader.resolve_path(css_file), "window1")
        refresh_callback.assert_called_once_with("window1")

    def test_script_change_always_refreshes(
        self,
        manager: HotReloadManager,
        mock_asset_loader: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Script changes always trigger a full refresh, regardless of mode."""
        script_file = tmp_path / "app.js"
        script_file.write_text("console.log('hello');")

        refresh_callback = MagicMock()
        manager.set_refresh_callback(refresh_callback)
        manager.enable_for_window("window1", _make_content(script_files=[script_file]))

        manager._on_file_change(mock_asset_loader.resolve_path(script_file), "window1")
        refresh_callback.assert_called_once_with("window1")

    def test_unknown_window_ignored(self, manager: HotReloadManager) -> None:
        """File changes for unknown windows are silently ignored."""
        refresh_callback = MagicMock()
        manager.set_refresh_callback(refresh_callback)

        manager._on_file_change(Path("/some/file.css"), "unknown_window")
        refresh_callback.assert_not_called()

    def test_unknown_path_for_known_window_ignored(
        self, manager: HotReloadManager, tmp_path: Path
    ) -> None:
        """If the window is registered but the path isn't tracked, nothing fires."""
        css_file = tmp_path / "style.css"
        css_file.write_text("body {}")
        unknown = tmp_path / "ghost.css"
        content = _make_content(css_files=[css_file])

        inject_cb = MagicMock()
        refresh_cb = MagicMock()
        manager.set_inject_css_callback(inject_cb)
        manager.set_refresh_callback(refresh_cb)
        manager.enable_for_window("win1", content)

        manager._on_file_change(unknown.resolve(), "win1")

        inject_cb.assert_not_called()
        refresh_cb.assert_not_called()


# =============================================================================
# Get Watched Files Tests
# =============================================================================


class TestGetWatchedFiles:
    """Test get_watched_files queries."""

    def test_get_watched_files_specific_window(
        self, manager: HotReloadManager, tmp_path: Path
    ) -> None:
        """Querying by label returns just that label's files."""
        css_file = tmp_path / "style.css"
        css_file.write_text("body {}")

        manager.enable_for_window("window1", _make_content(css_files=[css_file]))
        files = manager.get_watched_files("window1")

        assert "window1" in files
        assert len(files["window1"]) == 1

    def test_get_watched_files_all(self, manager: HotReloadManager, tmp_path: Path) -> None:
        """Querying without arguments returns every registered window."""
        css1 = tmp_path / "style1.css"
        css2 = tmp_path / "style2.css"
        css1.write_text("body {}")
        css2.write_text("p {}")

        manager.enable_for_window("window1", _make_content(css_files=[css1]))
        manager.enable_for_window("window2", _make_content(css_files=[css2]))

        files = manager.get_watched_files()
        assert "window1" in files
        assert "window2" in files

    def test_get_watched_files_unknown_label_returns_empty(self, manager: HotReloadManager) -> None:
        """Querying an unknown label returns an empty dict."""
        assert manager.get_watched_files("unknown-window") == {}


# =============================================================================
# Global Manager Singleton Tests
# =============================================================================


class TestGlobalManagerFunctions:
    """Test get_hot_reload_manager / stop_hot_reload_manager singleton functions."""

    def test_get_creates_singleton(self) -> None:
        """Repeated get_hot_reload_manager() calls return the same instance."""
        stop_hot_reload_manager()
        try:
            mgr1 = get_hot_reload_manager()
            mgr2 = get_hot_reload_manager()
            assert mgr1 is mgr2
        finally:
            stop_hot_reload_manager()

    def test_stop_clears_singleton(self) -> None:
        """stop_hot_reload_manager clears the module-level reference."""
        stop_hot_reload_manager()
        try:
            mgr = get_hot_reload_manager()
            assert hot_reload_mod._hot_reload_manager is mgr

            stop_hot_reload_manager()
            assert hot_reload_mod._hot_reload_manager is None

            # Subsequent get returns a new instance
            new_mgr = get_hot_reload_manager()
            assert new_mgr is not mgr
        finally:
            stop_hot_reload_manager()

    def test_stop_when_not_set_is_noop(self) -> None:
        """stop_hot_reload_manager is safe when no manager exists."""
        hot_reload_mod._hot_reload_manager = None
        stop_hot_reload_manager()
        assert hot_reload_mod._hot_reload_manager is None

    def test_stop_invokes_manager_stop(self) -> None:
        """stop_hot_reload_manager invokes stop() on the live manager."""
        mock_manager = MagicMock()
        hot_reload_mod._hot_reload_manager = mock_manager
        try:
            stop_hot_reload_manager()
            mock_manager.stop.assert_called_once()
            assert hot_reload_mod._hot_reload_manager is None
        finally:
            hot_reload_mod._hot_reload_manager = None
