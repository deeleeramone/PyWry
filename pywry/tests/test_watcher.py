"""Unit tests for file watcher module.

Tests cover:
- WatchedFile dataclass
- WindowDebouncer dataclass
- FileWatcher class with mocked Observer and Timer
- Debounce functionality
- Global watcher functions
- _WatchHandler event forwarding
- All branches required for 100% coverage

All tests use mocks for file system and threading operations where appropriate.
"""

from __future__ import annotations

import threading
import time

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pywry.watcher import (
    FileWatcher,
    WatchedFile,
    WindowDebouncer,
    _WatchHandler,
    get_file_watcher,
    stop_file_watcher,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def css_file(tmp_path: Path) -> Path:
    """Create a CSS file in tmp_path."""
    f = tmp_path / "style.css"
    f.write_text("body {}")
    return f


@pytest.fixture
def watcher() -> FileWatcher:
    """Create a fresh FileWatcher with default settings."""
    return FileWatcher()


@pytest.fixture
def mocked_observer():
    """Patch pywry.watcher.Observer and yield the (class, instance) pair."""
    with patch("pywry.watcher.Observer") as mock_observer_class:
        mock_observer = MagicMock()
        mock_observer.emitters = []
        mock_observer_class.return_value = mock_observer
        yield mock_observer_class, mock_observer


# =============================================================================
# WatchedFile Tests
# =============================================================================


class TestWatchedFile:
    """Test WatchedFile dataclass."""

    def test_creation(self) -> None:
        """Test creating a WatchedFile with required fields."""
        callback = MagicMock()
        watched = WatchedFile(
            path=Path("/test/file.txt"),
            callback=callback,
            label="window1",
        )
        assert watched.path == Path("/test/file.txt")
        assert watched.callback is callback
        assert watched.label == "window1"
        assert watched.last_triggered == 0.0

    def test_last_triggered_custom(self) -> None:
        """Test last_triggered with custom value."""
        watched = WatchedFile(
            path=Path("/test/file.txt"),
            callback=MagicMock(),
            label="window1",
            last_triggered=12345.0,
        )
        assert watched.last_triggered == 12345.0


# =============================================================================
# WindowDebouncer Tests
# =============================================================================


class TestWindowDebouncer:
    """Test WindowDebouncer dataclass."""

    def test_default_values(self) -> None:
        """Test default values."""
        debouncer = WindowDebouncer()
        assert debouncer.pending_paths == set()
        assert debouncer.timer is None
        assert isinstance(debouncer.lock, type(threading.Lock()))

    def test_pending_paths(self) -> None:
        """Test adding pending paths."""
        debouncer = WindowDebouncer()
        debouncer.pending_paths.add(Path("/test/file1.txt"))
        debouncer.pending_paths.add(Path("/test/file2.txt"))
        assert len(debouncer.pending_paths) == 2

    def test_lock_is_usable(self) -> None:
        """Test that the lock is usable as a context manager."""
        debouncer = WindowDebouncer()
        with debouncer.lock:
            debouncer.pending_paths.add(Path("/test/file.txt"))
        assert Path("/test/file.txt") in debouncer.pending_paths


# =============================================================================
# FileWatcher Initialization & Debounce Property Tests
# =============================================================================


class TestFileWatcherInit:
    """Test FileWatcher initialization and debounce_ms property."""

    def test_default_debounce(self) -> None:
        """Test default debounce time."""
        watcher = FileWatcher()
        assert watcher.debounce_ms == 100

    def test_custom_debounce(self) -> None:
        """Test custom debounce time."""
        watcher = FileWatcher(debounce_ms=500)
        assert watcher.debounce_ms == 500

    def test_debounce_setter_accepts_valid(self) -> None:
        """Test debounce_ms setter updates both the ms and seconds values."""
        watcher = FileWatcher()
        watcher.debounce_ms = 750
        assert watcher.debounce_ms == 750
        assert watcher._debounce_sec == 0.75

    def test_debounce_setter_clamps_to_minimum(self) -> None:
        """Test that debounce has an enforced minimum of 10ms."""
        watcher = FileWatcher()
        watcher.debounce_ms = 5  # Below minimum
        assert watcher.debounce_ms == 10
        watcher.debounce_ms = -10
        assert watcher.debounce_ms == 10


# =============================================================================
# FileWatcher Watch/Unwatch Tests
# =============================================================================


class TestFileWatcherWatch:
    """Test FileWatcher watch/unwatch methods."""

    def test_watch_existing_file(self, watcher: FileWatcher, css_file: Path) -> None:
        """Test watching an existing file populates _watches."""
        callback = MagicMock()
        watcher.watch(css_file, callback, "window1")

        resolved = css_file.resolve()
        assert resolved in watcher._watches
        assert len(watcher._watches[resolved]) == 1
        assert watcher._watches[resolved][0].callback is callback

    def test_watch_nonexistent_file_does_nothing(
        self, watcher: FileWatcher, tmp_path: Path
    ) -> None:
        """Test watching a non-existent file is a no-op."""
        nonexistent = tmp_path / "nonexistent.txt"
        watcher.watch(nonexistent, MagicMock(), "window1")
        assert nonexistent.resolve() not in watcher._watches

    def test_watch_path_string(self, watcher: FileWatcher, css_file: Path) -> None:
        """Test watching with string path instead of Path object."""
        watcher.watch(str(css_file), MagicMock(), "window1")
        assert css_file.resolve() in watcher._watches

    def test_watch_multiple_callbacks(self, watcher: FileWatcher, css_file: Path) -> None:
        """Test watching same file with multiple callbacks."""
        watcher.watch(css_file, MagicMock(), "window1")
        watcher.watch(css_file, MagicMock(), "window2")
        assert len(watcher._watches[css_file.resolve()]) == 2

    def test_watch_while_running_schedules_directory(self, mocked_observer, tmp_path: Path) -> None:
        """When watch() is called while running, the directory is scheduled
        with the observer.
        """
        _, mock_observer = mocked_observer
        watcher = FileWatcher()
        watcher.start()

        test_file = tmp_path / "live.css"
        test_file.write_text("body {}")
        watcher.watch(test_file, MagicMock(), "labelA")

        scheduled_paths = [c.args[1] for c in mock_observer.schedule.call_args_list]
        assert str(test_file.parent.resolve()) in scheduled_paths

    def test_unwatch_file(self, watcher: FileWatcher, css_file: Path) -> None:
        """Test unwatching a file removes it from _watches."""
        watcher.watch(css_file, MagicMock(), "window1")
        watcher.unwatch(css_file)
        assert css_file.resolve() not in watcher._watches

    def test_unwatch_nonexistent_is_safe(self, watcher: FileWatcher) -> None:
        """Test unwatching a file that was never watched is a no-op."""
        watcher.unwatch(Path("/nonexistent/file.txt"))

    def test_unwatch_by_label_keeps_other_labels(
        self, watcher: FileWatcher, css_file: Path
    ) -> None:
        """Unwatching with a specific label keeps other labels intact."""
        watcher.watch(css_file, MagicMock(), "win1")
        watcher.watch(css_file, MagicMock(), "win2")
        watcher.unwatch(css_file, label="win1")

        resolved = css_file.resolve()
        assert resolved in watcher._watches
        assert len(watcher._watches[resolved]) == 1
        assert watcher._watches[resolved][0].label == "win2"

    def test_unwatch_by_label_removes_path_when_last(
        self, watcher: FileWatcher, css_file: Path
    ) -> None:
        """When unwatching the only remaining label for a path, the path
        entry is deleted entirely.
        """
        watcher.watch(css_file, MagicMock(), "win-only")
        watcher.unwatch(css_file, label="win-only")
        assert css_file.resolve() not in watcher._watches

    def test_unwatch_label_all(self, watcher: FileWatcher, tmp_path: Path) -> None:
        """unwatch_label removes every file watched only by that label."""
        file1 = tmp_path / "test1.txt"
        file2 = tmp_path / "test2.txt"
        file1.write_text("content1")
        file2.write_text("content2")

        watcher.watch(file1, MagicMock(), "window1")
        watcher.watch(file2, MagicMock(), "window1")
        watcher.unwatch_label("window1")

        assert file1.resolve() not in watcher._watches
        assert file2.resolve() not in watcher._watches

    def test_unwatch_label_keeps_path_when_other_labels_remain(
        self, watcher: FileWatcher, tmp_path: Path
    ) -> None:
        """unwatch_label leaves path entries that other labels still watch."""
        f1 = tmp_path / "one.css"
        f2 = tmp_path / "two.css"
        f1.write_text("a {}")
        f2.write_text("b {}")

        watcher.watch(f1, MagicMock(), "win1")
        watcher.watch(f2, MagicMock(), "win1")
        watcher.watch(f1, MagicMock(), "win2")  # win2 also watches f1

        watcher.unwatch_label("win1")

        # f2 fully unwatched
        assert f2.resolve() not in watcher._watches
        # f1 still has win2 watching it
        assert f1.resolve() in watcher._watches
        assert len(watcher._watches[f1.resolve()]) == 1
        assert watcher._watches[f1.resolve()][0].label == "win2"

    def test_unwatch_label_nonexistent_is_safe(self, watcher: FileWatcher) -> None:
        """Test unwatching a label that was never used is a no-op."""
        watcher.unwatch_label("nonexistent_window")

    def test_unwatch_label_cancels_pending_timer(self, css_file: Path) -> None:
        """unwatch_label cancels a pending debouncer timer and clears state."""
        watcher = FileWatcher(debounce_ms=10000)  # long so timer doesn't fire
        watcher.watch(css_file, MagicMock(), "winT")

        # Trigger a change to create a debouncer with an active timer
        watcher._on_file_change(css_file.resolve())

        assert "winT" in watcher._debouncers
        debouncer = watcher._debouncers["winT"]
        assert debouncer.timer is not None

        watcher.unwatch_label("winT")

        # Debouncer was removed
        assert "winT" not in watcher._debouncers


# =============================================================================
# FileWatcher Start/Stop Tests
# =============================================================================


class TestFileWatcherStartStop:
    """Test FileWatcher start/stop methods."""

    def test_start_creates_observer(self, mocked_observer) -> None:
        """Test that start creates an Observer and marks watcher running."""
        mock_observer_class, mock_observer = mocked_observer
        watcher = FileWatcher()
        watcher.start()

        mock_observer_class.assert_called_once()
        mock_observer.start.assert_called_once()
        assert watcher._running is True

    def test_start_idempotent(self, mocked_observer) -> None:
        """Test that calling start twice doesn't create two observers."""
        mock_observer_class, _ = mocked_observer
        watcher = FileWatcher()
        watcher.start()
        watcher.start()
        mock_observer_class.assert_called_once()

    def test_start_schedules_known_directories(self, mocked_observer, tmp_path: Path) -> None:
        """start() must call _ensure_directory_watched for every tracked directory."""
        _, mock_observer = mocked_observer
        f1 = tmp_path / "a.css"
        f2 = tmp_path / "b.css"
        f1.write_text("a {}")
        f2.write_text("b {}")

        watcher = FileWatcher()
        watcher.watch(f1, MagicMock(), "w1")
        watcher.watch(f2, MagicMock(), "w1")

        # Not yet running - schedule shouldn't have been called
        assert mock_observer.schedule.call_count == 0

        watcher.start()

        # After start, schedule must have been called for the parent dir
        scheduled_paths = [c.args[1] for c in mock_observer.schedule.call_args_list]
        assert str(tmp_path.resolve()) in scheduled_paths

    def test_stop_stops_observer(self, mocked_observer) -> None:
        """Test that stop stops the Observer and marks watcher not running."""
        _, mock_observer = mocked_observer
        watcher = FileWatcher()
        watcher.start()
        watcher.stop()

        mock_observer.stop.assert_called_once()
        mock_observer.join.assert_called_once()
        assert watcher._running is False

    def test_stop_without_start_is_safe(self, mocked_observer) -> None:
        """Test that stop without start is safe."""
        mock_observer_class, _ = mocked_observer
        watcher = FileWatcher()
        watcher.stop()
        mock_observer_class.assert_not_called()

    def test_stop_cancels_pending_timers(self, mocked_observer, css_file: Path) -> None:
        """stop() cancels pending debouncer timers and clears them."""
        _, mock_observer = mocked_observer
        watcher = FileWatcher(debounce_ms=10000)
        watcher.watch(css_file, MagicMock(), "win")
        watcher.start()

        # Trigger change so debouncer timer is set
        watcher._on_file_change(css_file.resolve())
        debouncer = watcher._debouncers["win"]
        assert debouncer.timer is not None

        watcher.stop()

        assert watcher._debouncers == {}
        mock_observer.stop.assert_called_once()
        assert watcher._running is False


# =============================================================================
# _ensure_directory_watched edge cases
# =============================================================================


class TestEnsureDirectoryWatched:
    """Test _ensure_directory_watched branches."""

    def test_no_observer_returns_early(self, watcher: FileWatcher, tmp_path: Path) -> None:
        """Without start(), observer is None and the call is a no-op."""
        watcher._ensure_directory_watched(tmp_path)

    def test_no_handler_returns_early(self, watcher: FileWatcher, tmp_path: Path) -> None:
        """With observer set but handler is None, schedule is not called."""
        watcher._observer = MagicMock()
        watcher._handler = None
        watcher._ensure_directory_watched(tmp_path)
        watcher._observer.schedule.assert_not_called()

    def test_already_watched_directory_skips_schedule(
        self, mocked_observer, tmp_path: Path
    ) -> None:
        """Already-watched directories don't get scheduled again."""
        _, mock_observer = mocked_observer
        fake_watch = MagicMock()
        fake_watch.path = str(tmp_path.resolve())
        fake_emitter = MagicMock()
        fake_emitter.watch = fake_watch
        mock_observer.emitters = [fake_emitter]

        watcher = FileWatcher()
        watcher.start()
        mock_observer.schedule.reset_mock()

        watcher._ensure_directory_watched(tmp_path.resolve())
        mock_observer.schedule.assert_not_called()

    def test_schedule_exception_is_swallowed(self, mocked_observer, tmp_path: Path) -> None:
        """Schedule failures are logged and swallowed (no exception raised)."""
        _, mock_observer = mocked_observer
        mock_observer.schedule.side_effect = OSError("nope")

        watcher = FileWatcher()
        watcher.start()
        # Should not raise even though schedule failed
        watcher._ensure_directory_watched(tmp_path)


# =============================================================================
# File Change Callback Tests
# =============================================================================


class TestFileChangeCallbacks:
    """Test file change callback triggering and debouncing."""

    def test_on_file_change_triggers_callback(self, css_file: Path) -> None:
        """Test that file changes trigger callbacks after the debounce period."""
        callback = MagicMock()
        watcher = FileWatcher(debounce_ms=10)
        watcher.watch(css_file, callback, "window1")

        resolved = css_file.resolve()
        watcher._on_file_change(resolved)

        # Wait for debounce (longer wait for CI timer scheduling variance)
        time.sleep(0.2)

        callback.assert_called_once_with(resolved, "window1")

    def test_on_file_change_unwatched_file_ignored(
        self, watcher: FileWatcher, css_file: Path, tmp_path: Path
    ) -> None:
        """Changes to unwatched files don't fire callbacks."""
        callback = MagicMock()
        watcher.watch(css_file, callback, "window1")

        # Simulate change to a different, unwatched file
        unwatched_file = tmp_path / "other.txt"
        watcher._on_file_change(unwatched_file.resolve())

        time.sleep(0.2)
        callback.assert_not_called()

    def test_on_file_change_empty_watches_returns_early(self, css_file: Path) -> None:
        """_on_file_change with an empty watch list returns without scheduling."""
        watcher = FileWatcher(debounce_ms=10)
        watcher.watch(css_file, MagicMock(), "w1")
        # Manually empty the list to hit the `not watches` branch
        watcher._watches[css_file.resolve()] = []

        watcher._on_file_change(css_file.resolve())
        assert "w1" not in watcher._debouncers

    def test_debounce_batches_rapid_changes(self, css_file: Path) -> None:
        """Rapid changes within the debounce window are coalesced into one callback."""
        callback = MagicMock()
        watcher = FileWatcher(debounce_ms=50)
        watcher.watch(css_file, callback, "window1")

        resolved = css_file.resolve()
        watcher._on_file_change(resolved)
        watcher._on_file_change(resolved)
        watcher._on_file_change(resolved)

        time.sleep(0.3)
        assert callback.call_count == 1

    def test_callback_exception_is_handled(self, css_file: Path) -> None:
        """Callback exceptions don't crash the watcher; the callback still fires."""
        bad_callback = MagicMock(side_effect=RuntimeError("Callback error"))
        watcher = FileWatcher(debounce_ms=10)
        watcher.watch(css_file, bad_callback, "window1")

        watcher._on_file_change(css_file.resolve())
        time.sleep(0.2)

        bad_callback.assert_called_once()


# =============================================================================
# _WatchHandler Tests
# =============================================================================


class TestWatchHandler:
    """Test _WatchHandler.on_modified event forwarding."""

    def test_directory_event_ignored(self) -> None:
        """Directory modification events are skipped (not forwarded)."""
        watcher_mock = MagicMock()
        handler = _WatchHandler(watcher_mock)

        event = MagicMock()
        event.is_directory = True
        handler.on_modified(event)

        watcher_mock._on_file_change.assert_not_called()

    def test_file_event_forwards_resolved_path(self, tmp_path: Path) -> None:
        """File events are forwarded as resolved Path objects to the watcher."""
        watcher_mock = MagicMock()
        handler = _WatchHandler(watcher_mock)

        f = tmp_path / "x.css"
        event = MagicMock()
        event.is_directory = False
        event.src_path = str(f)
        handler.on_modified(event)

        watcher_mock._on_file_change.assert_called_once()
        passed_path = watcher_mock._on_file_change.call_args[0][0]
        assert isinstance(passed_path, Path)
        assert passed_path == f.resolve()

    def test_bytes_src_path_is_decoded(self, tmp_path: Path) -> None:
        """Watchdog can deliver src_path as bytes; the handler decodes it."""
        watcher_mock = MagicMock()
        handler = _WatchHandler(watcher_mock)

        f = tmp_path / "y.css"
        event = MagicMock()
        event.is_directory = False
        event.src_path = str(f).encode()
        handler.on_modified(event)

        watcher_mock._on_file_change.assert_called_once()
        passed_path = watcher_mock._on_file_change.call_args[0][0]
        assert isinstance(passed_path, Path)
        assert passed_path == f.resolve()


# =============================================================================
# Global Watcher Functions Tests
# =============================================================================


class TestGlobalWatcherFunctions:
    """Test get_file_watcher / stop_file_watcher singleton functions."""

    def test_get_file_watcher_creates_singleton(self) -> None:
        """Repeated get_file_watcher() calls return the same instance."""
        stop_file_watcher()
        try:
            w1 = get_file_watcher()
            w2 = get_file_watcher()
            assert w1 is w2
        finally:
            stop_file_watcher()

    def test_get_file_watcher_respects_debounce(self) -> None:
        """First call sets the debounce time."""
        stop_file_watcher()
        try:
            watcher = get_file_watcher(debounce_ms=250)
            assert watcher.debounce_ms == 250
        finally:
            stop_file_watcher()

    def test_stop_file_watcher_resets_singleton(self) -> None:
        """After stop_file_watcher, get_file_watcher creates a fresh instance."""
        stop_file_watcher()
        try:
            w1 = get_file_watcher()
            w1.start()
            stop_file_watcher()

            w2 = get_file_watcher()
            assert w2 is not w1
        finally:
            stop_file_watcher()
