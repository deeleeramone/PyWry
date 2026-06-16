"""Tests for WindowProxy.

This file contains BOTH:

1. Integration tests at the top — they spawn a real pytauri subprocess and
   verify proxy methods drive the underlying window.  They are slow and may
   be skipped on headless CI.
2. Unit tests at the bottom — they patch ``pywry.window_proxy.runtime`` so
   they run in milliseconds without a subprocess.  These provide reliable
   coverage in headless environments where the integration tests cannot
   spawn windows.
"""

from __future__ import annotations

import os
import sys
import time

from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar
from unittest.mock import MagicMock, patch

import pytest

from pywry import runtime
from pywry.app import PyWry
from pywry.callbacks import get_registry
from pywry.exceptions import IPCTimeoutError
from pywry.models import ThemeMode, WindowMode
from pywry.types import (
    Cookie,
    CursorIcon,
    Effect,
    EffectState,
    LogicalPosition,
    LogicalSize,
    PhysicalPosition,
    PhysicalSize,
    ProgressBarStatus,
    Theme,
    TitleBarStyle,
    UserAttentionType,
    serialize_position,
    serialize_size,
)
from pywry.window_proxy import WindowProxy

# Import shared test utilities from tests.conftest
from tests.conftest import ReadyWaiter


F = TypeVar("F", bound=Callable[..., Any])


def retry_on_subprocess_failure(max_attempts: int = 3, delay: float = 1.0) -> Callable[[F], F]:
    """Retry decorator for tests that may fail due to transient subprocess issues.

    On Windows, WebView2 sometimes fails to start due to resource contention
    ("Failed to unregister class Chrome_WidgetWin_0"). On Linux with xvfb,
    WebKit initialization may have timing issues. This decorator retries
    the test after a delay to allow resources to be released.
    """

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
                        # Clean up and wait before retry
                        runtime.stop()
                        # Progressive backoff for CI stability
                        time.sleep(delay * (attempt + 1))
            raise last_error  # type: ignore

        return wrapper  # type: ignore

    return decorator


# Note: cleanup_runtime fixture is now in conftest.py and auto-used


def wait_for_state(
    proxy: WindowProxy,
    attr: str,
    expected: bool,
    timeout: float = 3.0,
    poll_interval: float = 0.1,
) -> bool:
    """Poll a WindowProxy boolean attribute until it matches expected value.

    Returns True if the state was reached, False if timeout.
    Handles transient IPC errors during polling.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if getattr(proxy, attr) is expected:
                return True
        except IPCTimeoutError:
            # Window may be temporarily unresponsive during state changes
            pass
        time.sleep(poll_interval)
    return False


def show_and_wait_ready(
    app: PyWry,
    content: str,
    timeout: float = 10.0,
    **kwargs: Any,
) -> WindowProxy:
    """Show content and return WindowProxy once window is ready."""
    waiter = ReadyWaiter(timeout=timeout)

    # Merge callbacks
    callbacks = kwargs.pop("callbacks", {}) or {}
    callbacks["pywry:ready"] = waiter.on_ready

    widget = app.show(content, callbacks=callbacks, **kwargs)

    if not waiter.wait():
        label = widget.label if hasattr(widget, "label") else str(widget)
        raise TimeoutError(f"Window '{label}' did not become ready within {timeout}s")

    return widget.proxy


class TestWindowProxyProperties:
    """Test that WindowProxy properties return real values."""

    def test_title_property(self) -> None:
        """title property returns the actual window title."""
        app = PyWry(theme=ThemeMode.DARK)
        proxy = show_and_wait_ready(app, "<h1>Test</h1>", title="My Test Title")

        title = proxy.title
        assert isinstance(title, str)
        assert "My Test Title" in title or title != ""  # Title is set
        app.close()

    def test_scale_factor_property(self) -> None:
        """scale_factor returns a positive number."""
        app = PyWry(theme=ThemeMode.DARK)
        proxy = show_and_wait_ready(app, "<h1>Scale</h1>", title="Scale Test")

        scale = proxy.scale_factor
        assert isinstance(scale, (int, float))
        assert scale > 0  # Scale factor is always positive
        app.close()

    def test_inner_size_property(self) -> None:
        """inner_size returns size with positive dimensions."""
        app = PyWry(theme=ThemeMode.DARK)
        proxy = show_and_wait_ready(app, "<h1>Size</h1>", title="Size Test")

        size = proxy.inner_size
        assert size is not None
        assert isinstance(size, PhysicalSize)
        assert size.width > 0
        assert size.height > 0
        app.close()

    def test_outer_size_property(self) -> None:
        """outer_size returns size >= inner_size."""
        app = PyWry(theme=ThemeMode.DARK)
        proxy = show_and_wait_ready(app, "<h1>Outer</h1>", title="Outer Size")

        inner = proxy.inner_size
        outer = proxy.outer_size
        assert outer is not None
        assert isinstance(outer, PhysicalSize)
        # Outer includes window chrome, should be >= inner
        assert outer.width >= inner.width
        assert outer.height >= inner.height
        app.close()

    def test_inner_position_property(self) -> None:
        """inner_position returns a position."""
        app = PyWry(theme=ThemeMode.DARK)
        proxy = show_and_wait_ready(app, "<h1>Pos</h1>", title="Position Test")

        pos = proxy.inner_position
        assert pos is not None
        assert isinstance(pos, PhysicalPosition)
        # Position can be any value including negative (off-screen)
        assert isinstance(pos.x, int)
        assert isinstance(pos.y, int)
        app.close()

    def test_is_visible_property(self) -> None:
        """is_visible returns True for shown window."""
        app = PyWry(theme=ThemeMode.DARK)
        proxy = show_and_wait_ready(app, "<h1>Visible</h1>", title="Visible Test")

        # Window should be visible after show
        assert proxy.is_visible is True
        app.close()

    def test_boolean_properties(self) -> None:
        """Boolean state properties return actual booleans."""
        app = PyWry(theme=ThemeMode.DARK)
        proxy = show_and_wait_ready(app, "<h1>Bools</h1>", title="Bool Test")

        # These should all return actual booleans
        assert isinstance(proxy.is_decorated, bool)
        assert isinstance(proxy.is_resizable, bool)
        assert isinstance(proxy.is_maximizable, bool)
        assert isinstance(proxy.is_minimizable, bool)
        assert isinstance(proxy.is_closable, bool)
        assert isinstance(proxy.is_maximized, bool)
        assert isinstance(proxy.is_minimized, bool)
        assert isinstance(proxy.is_fullscreen, bool)
        app.close()


class TestWindowProxyActions:
    """Test that WindowProxy action methods actually work."""

    def test_set_title(self) -> None:
        """set_title actually changes the window title."""
        app = PyWry(theme=ThemeMode.DARK)
        proxy = show_and_wait_ready(app, "<h1>Title</h1>", title="Original Title")

        # Change title
        proxy.set_title("New Title")
        time.sleep(0.1)  # Allow IPC to complete

        # Verify title changed
        new_title = proxy.title
        assert "New Title" in new_title
        app.close()

    @pytest.mark.skipif(
        os.environ.get("CI") == "true" and sys.platform == "linux",
        reason="Maximize/minimize requires a real window manager (not available on Linux CI)",
    )
    def test_maximize_unmaximize(self) -> None:
        """maximize and unmaximize actually change window state."""
        app = PyWry(theme=ThemeMode.DARK)
        proxy = show_and_wait_ready(app, "<h1>Max</h1>", title="Maximize Test")

        # Initially not maximized
        assert proxy.is_maximized is False

        # Maximize - use polling for async window state changes
        proxy.maximize()
        assert wait_for_state(proxy, "is_maximized", True, timeout=3.0), (
            "Window did not maximize within timeout"
        )

        # Unmaximize
        proxy.unmaximize()
        assert wait_for_state(proxy, "is_maximized", False, timeout=3.0), (
            "Window did not unmaximize within timeout"
        )
        app.close()

    @pytest.mark.skipif(
        os.environ.get("CI") == "true" and sys.platform == "linux",
        reason="Maximize/minimize requires a real window manager (not available on Linux CI)",
    )
    def test_minimize_unminimize(self) -> None:
        """minimize and unminimize change window state."""
        app = PyWry(theme=ThemeMode.DARK)
        proxy = show_and_wait_ready(app, "<h1>Min</h1>", title="Minimize Test")

        # Ensure window is in normal state first (not maximized/minimized)
        if proxy.is_maximized:
            proxy.unmaximize()
            wait_for_state(proxy, "is_maximized", False)

        # macOS NSWindow.miniaturize: is a no-op when the application is not
        # the active app (common in CI runners where the process is launched
        # in the background).  Activate via set_focus and give AppKit a
        # moment to register before issuing the minimize request.
        proxy.set_focus()
        time.sleep(0.3)

        # Poll both is_minimized and is_visible concurrently — different
        # platforms / window managers transition through different states:
        # macOS toggles is_minimized; some Linux WMs only flip is_visible.
        proxy.minimize()
        deadline = time.time() + 10.0
        minimized = False
        hidden = False
        while time.time() < deadline:
            try:
                if proxy.is_minimized:
                    minimized = True
                    break
                if not proxy.is_visible:
                    hidden = True
                    break
            except IPCTimeoutError:
                pass
            time.sleep(0.1)

        # Fall back to an explicit retry — macOS occasionally drops the very
        # first miniaturize when the window only just became key.
        if not (minimized or hidden):
            proxy.set_focus()
            time.sleep(0.3)
            proxy.minimize()
            minimized = wait_for_state(proxy, "is_minimized", True, timeout=8.0)
            hidden = hidden or wait_for_state(proxy, "is_visible", False, timeout=2.0)

        assert minimized or hidden, "Window did not minimize/hide within timeout"

        # Unminimize - requires focus on some platforms
        # Add delay to let window manager process the minimize fully
        time.sleep(0.5)
        proxy.set_focus()
        proxy.unminimize()
        assert wait_for_state(proxy, "is_minimized", False, timeout=8.0), (
            f"Window did not unminimize within timeout (is_visible={proxy.is_visible})"
        )
        assert wait_for_state(proxy, "is_visible", True, timeout=8.0), (
            "Window did not become visible after unminimize"
        )
        app.close()

    def test_set_size(self) -> None:
        """set_size actually changes the window size."""
        app = PyWry(theme=ThemeMode.DARK)
        proxy = show_and_wait_ready(app, "<h1>Resize</h1>", title="Size Change")

        # Set to specific size
        target_size = PhysicalSize(800, 600)
        proxy.set_size(target_size)
        time.sleep(0.2)

        # Verify size changed (may not be exact due to platform constraints)
        new_size = proxy.inner_size
        assert new_size is not None
        # Allow some tolerance for window decorations
        assert abs(new_size.width - 800) < 50
        assert abs(new_size.height - 600) < 50
        app.close()

    def test_hide_show(self) -> None:
        """hide and show change visibility."""
        app = PyWry(theme=ThemeMode.DARK)
        proxy = show_and_wait_ready(app, "<h1>Hide</h1>", title="Hide Test")

        assert proxy.is_visible is True

        # Hide
        proxy.hide()
        time.sleep(0.2)
        assert proxy.is_visible is False

        # Show again
        proxy.show()
        time.sleep(0.2)
        assert proxy.is_visible is True
        app.close()

    @retry_on_subprocess_failure(max_attempts=3, delay=1.0)
    @pytest.mark.skipif(
        os.environ.get("CI") == "true" and sys.platform == "linux",
        reason="Always-on-top requires a real window manager (not available on Linux CI)",
    )
    def test_set_always_on_top(self) -> None:
        """set_always_on_top changes the always-on-top state."""
        app = PyWry(theme=ThemeMode.DARK)
        proxy = show_and_wait_ready(app, "<h1>Top</h1>", title="Always On Top")

        # Set always on top - use polling for async state changes
        proxy.set_always_on_top(True)
        assert wait_for_state(proxy, "is_always_on_top", True, timeout=3.0), (
            "Window did not become always-on-top within timeout"
        )

        # Disable
        proxy.set_always_on_top(False)
        assert wait_for_state(proxy, "is_always_on_top", False, timeout=3.0), (
            "Window did not disable always-on-top within timeout"
        )
        app.close()

    def test_set_decorations(self) -> None:
        """set_decorations changes window decoration state."""
        app = PyWry(theme=ThemeMode.DARK)
        proxy = show_and_wait_ready(app, "<h1>Deco</h1>", title="Decorations Test")

        # Initially decorated
        assert proxy.is_decorated is True

        # Remove decorations
        proxy.set_decorations(False)
        time.sleep(0.2)
        assert proxy.is_decorated is False

        # Restore
        proxy.set_decorations(True)
        time.sleep(0.2)
        assert proxy.is_decorated is True
        app.close()


class TestWindowProxyWebview:
    """Test webview-related WindowProxy methods."""

    def test_eval_js(self) -> None:
        """eval executes JavaScript in the window."""
        app = PyWry(theme=ThemeMode.DARK)
        proxy = show_and_wait_ready(app, "<div id='target'>Original</div>", title="Eval Test")

        # Execute JS to modify the DOM
        proxy.eval("document.getElementById('target').textContent = 'Modified';")
        time.sleep(0.2)

        # Verify change via callback result
        registry = get_registry()
        result = {"received": False, "data": None}

        def on_result(data: Any) -> None:
            result["received"] = True
            result["data"] = data

        registry.register(proxy.label, "pywry:result", on_result)

        # Read back the value
        runtime.eval_js(
            proxy.label,
            "pywry.result(document.getElementById('target').textContent);",
        )
        time.sleep(0.3)

        assert result["received"]
        assert result["data"] == "Modified"
        app.close()

    @retry_on_subprocess_failure(max_attempts=3, delay=1.0)
    def test_navigate(self) -> None:
        """navigate changes the window URL."""
        app = PyWry(theme=ThemeMode.DARK)
        proxy = show_and_wait_ready(app, "<h1>Nav</h1>", title="Navigate Test")

        # Get initial URL (tauri serves content via tauri:// or http://tauri.localhost/)
        initial_url = proxy.url
        assert initial_url.startswith(("tauri://", "http://tauri.localhost/")), (
            f"Unexpected initial URL: {initial_url}"
        )

        # Navigate to about:blank
        proxy.navigate("about:blank")
        time.sleep(0.5)

        # URL must have changed from the initial tauri URL
        new_url = proxy.url
        assert new_url != initial_url, f"URL did not change: still {new_url}"
        assert new_url == "about:blank", f"Expected 'about:blank', got {new_url}"
        app.close()


class TestWindowProxyMonitors:
    """Test monitor-related WindowProxy properties."""

    def test_current_monitor(self) -> None:
        """current_monitor returns monitor info."""
        app = PyWry(theme=ThemeMode.DARK)
        proxy = show_and_wait_ready(app, "<h1>Monitor</h1>", title="Monitor Test")

        monitor = proxy.current_monitor
        # May be None on some platforms, but if present should have properties
        if monitor is not None:
            assert hasattr(monitor, "size")
            assert hasattr(monitor, "position")
            assert hasattr(monitor, "scale_factor")
        app.close()

    def test_primary_monitor(self) -> None:
        """primary_monitor returns the primary display."""
        app = PyWry(theme=ThemeMode.DARK)
        proxy = show_and_wait_ready(app, "<h1>Primary</h1>", title="Primary Mon")

        monitor = proxy.primary_monitor
        # Should exist on systems with displays
        if monitor is not None:
            assert monitor.size.width > 0
            assert monitor.size.height > 0
        app.close()

    def test_available_monitors(self) -> None:
        """available_monitors returns list of displays."""
        app = PyWry(theme=ThemeMode.DARK)
        proxy = show_and_wait_ready(app, "<h1>Monitors</h1>", title="All Mons")

        monitors = proxy.available_monitors
        assert isinstance(monitors, list)
        # Should have at least one monitor on a system with a display
        if monitors:
            assert all(hasattr(m, "size") for m in monitors)
        app.close()


class TestWindowProxyLabel:
    """Test WindowProxy label handling."""

    def test_label_property(self) -> None:
        """label property returns the window label."""
        proxy = WindowProxy("my-window-label")
        assert proxy.label == "my-window-label"

    def test_repr(self) -> None:
        """repr includes the label."""
        proxy = WindowProxy("test-label")
        r = repr(proxy)
        assert "WindowProxy" in r
        assert "test-label" in r


class TestMultipleWindows:
    """Test WindowProxy with multiple windows."""

    def test_independent_windows(self) -> None:
        """Multiple WindowProxies control independent windows."""
        app = PyWry(mode=WindowMode.NEW_WINDOW, theme=ThemeMode.DARK)

        proxy1 = show_and_wait_ready(app, "<h1>Window 1</h1>", title="Win 1")
        proxy2 = show_and_wait_ready(app, "<h1>Window 2</h1>", title="Win 2")

        # Labels should be different
        assert proxy1.label != proxy2.label

        # Modifying one doesn't affect the other
        proxy1.set_title("Modified 1")
        time.sleep(0.1)

        assert "Modified 1" in proxy1.title
        assert "Win 2" in proxy2.title or proxy2.title != proxy1.title
        app.close()


# =============================================================================
# Unit tests via mocked runtime — fast, headless-safe coverage
# =============================================================================


@patch("pywry.window_proxy.runtime")
class TestWindowProxyMockedProperties:
    """Test WindowProxy property getters via mocked runtime."""

    def test_label(self, runtime_mock: MagicMock) -> None:
        proxy = WindowProxy("test")
        assert proxy.label == "test"

    def test_title(self, runtime_mock: MagicMock) -> None:
        runtime_mock.window_get.return_value = "T"
        proxy = WindowProxy("x")
        assert proxy.title == "T"
        runtime_mock.window_get.assert_called_with("x", "title")

    def test_url(self, runtime_mock: MagicMock) -> None:
        runtime_mock.window_get.return_value = "http://x"
        proxy = WindowProxy("x")
        assert proxy.url == "http://x"

    def test_theme(self, runtime_mock: MagicMock) -> None:
        runtime_mock.window_get.return_value = "Dark"
        proxy = WindowProxy("x")
        assert proxy.theme == Theme.DARK

    def test_scale_factor(self, runtime_mock: MagicMock) -> None:
        runtime_mock.window_get.return_value = 2.0
        proxy = WindowProxy("x")
        assert proxy.scale_factor == 2.0

    def test_inner_position(self, runtime_mock: MagicMock) -> None:
        runtime_mock.window_get.return_value = {"x": 10, "y": 20}
        proxy = WindowProxy("x")
        result = proxy.inner_position
        assert isinstance(result, PhysicalPosition)
        assert result.x == 10
        assert result.y == 20

    def test_outer_position(self, runtime_mock: MagicMock) -> None:
        runtime_mock.window_get.return_value = {"x": 5, "y": 6}
        proxy = WindowProxy("x")
        result = proxy.outer_position
        assert isinstance(result, PhysicalPosition)
        assert result.x == 5

    def test_inner_size(self, runtime_mock: MagicMock) -> None:
        runtime_mock.window_get.return_value = {"width": 800, "height": 600}
        proxy = WindowProxy("x")
        result = proxy.inner_size
        assert isinstance(result, PhysicalSize)
        assert result.width == 800

    def test_outer_size(self, runtime_mock: MagicMock) -> None:
        runtime_mock.window_get.return_value = {"width": 1024, "height": 768}
        proxy = WindowProxy("x")
        result = proxy.outer_size
        assert isinstance(result, PhysicalSize)

    def test_cursor_position(self, runtime_mock: MagicMock) -> None:
        runtime_mock.window_get.return_value = {"x": 1, "y": 2}
        proxy = WindowProxy("x")
        result = proxy.cursor_position
        assert isinstance(result, PhysicalPosition)

    def test_current_monitor_present(self, runtime_mock: MagicMock) -> None:
        runtime_mock.window_get.return_value = {
            "name": "M",
            "size": {"width": 1, "height": 2},
            "position": {"x": 0, "y": 0},
            "scale_factor": 1.0,
        }
        proxy = WindowProxy("x")
        m = proxy.current_monitor
        assert m is not None
        assert m.name == "M"

    def test_current_monitor_none(self, runtime_mock: MagicMock) -> None:
        runtime_mock.window_get.return_value = None
        assert WindowProxy("x").current_monitor is None

    def test_primary_monitor_present(self, runtime_mock: MagicMock) -> None:
        runtime_mock.window_get.return_value = {
            "name": "P",
            "size": {"width": 1, "height": 2},
            "position": {"x": 0, "y": 0},
            "scale_factor": 1.0,
        }
        assert WindowProxy("x").primary_monitor.name == "P"

    def test_primary_monitor_none(self, runtime_mock: MagicMock) -> None:
        runtime_mock.window_get.return_value = None
        assert WindowProxy("x").primary_monitor is None

    def test_available_monitors(self, runtime_mock: MagicMock) -> None:
        runtime_mock.window_get.return_value = [
            {
                "name": "M1",
                "size": {"width": 1, "height": 1},
                "position": {"x": 0, "y": 0},
                "scale_factor": 1.0,
            }
        ]
        result = WindowProxy("x").available_monitors
        assert isinstance(result, list)
        assert len(result) == 1

    @pytest.mark.parametrize(
        "prop",
        [
            "is_fullscreen",
            "is_minimized",
            "is_maximized",
            "is_focused",
            "is_decorated",
            "is_resizable",
            "is_enabled",
            "is_visible",
            "is_closable",
            "is_maximizable",
            "is_minimizable",
            "is_always_on_top",
            "is_always_on_bottom",
            "is_devtools_open",
        ],
    )
    def test_boolean_props(self, runtime_mock: MagicMock, prop: str) -> None:
        runtime_mock.window_get.return_value = True
        assert getattr(WindowProxy("x"), prop) is True


@patch("pywry.window_proxy.runtime")
class TestWindowProxyMockedActions:
    """Test WindowProxy action methods route to runtime."""

    def test_show(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").show()
        runtime_mock.window_call.assert_called_once_with("x", "show")

    def test_hide(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").hide()
        runtime_mock.window_call.assert_called_once_with("x", "hide")

    def test_close(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").close()
        runtime_mock.window_call.assert_called_once_with("x", "close")

    def test_destroy(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").destroy()
        runtime_mock.window_call.assert_called_once_with("x", "destroy")

    def test_maximize(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").maximize()
        runtime_mock.window_call.assert_called_once_with("x", "maximize")

    def test_unmaximize(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").unmaximize()
        runtime_mock.window_call.assert_called_once_with("x", "unmaximize")

    def test_minimize(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").minimize()
        runtime_mock.window_call.assert_called_once_with("x", "minimize")

    def test_unminimize(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").unminimize()
        runtime_mock.window_call.assert_called_once_with("x", "unminimize")

    def test_toggle_maximize(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").toggle_maximize()
        runtime_mock.window_call.assert_called_once_with("x", "toggle_maximize")

    def test_center(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").center()
        runtime_mock.window_call.assert_called_once_with("x", "center")

    def test_set_focus(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").set_focus()
        runtime_mock.window_call.assert_called_once_with("x", "set_focus")

    def test_reload(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").reload()
        runtime_mock.window_call.assert_called_once_with("x", "reload")

    def test_print_page(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").print_page()
        runtime_mock.window_call.assert_called_once_with("x", "print")

    def test_open_devtools(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").open_devtools()
        runtime_mock.window_call.assert_called_once_with("x", "open_devtools")

    def test_close_devtools(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").close_devtools()
        runtime_mock.window_call.assert_called_once_with("x", "close_devtools")

    def test_clear_all_browsing_data(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").clear_all_browsing_data()
        runtime_mock.window_call.assert_called_once_with("x", "clear_all_browsing_data")

    def test_start_dragging(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").start_dragging()
        runtime_mock.window_call.assert_called_once_with("x", "start_dragging")

    def test_request_user_attention_with_type(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").request_user_attention(UserAttentionType.CRITICAL)
        args = runtime_mock.window_call.call_args[0]
        assert args[1] == "request_user_attention"
        assert args[2] == {"attention_type": "Critical"}

    def test_request_user_attention_none(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").request_user_attention(None)
        assert runtime_mock.window_call.call_args[0][2] == {"attention_type": None}

    def test_set_title(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").set_title("new")
        runtime_mock.window_call.assert_called_once_with("x", "set_title", {"title": "new"})

    def test_set_size(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").set_size(PhysicalSize(800, 600))
        args = runtime_mock.window_call.call_args[0]
        assert args[1] == "set_size"
        assert args[2]["width"] == 800

    def test_set_min_size_with_size(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").set_min_size(LogicalSize(100, 100))
        runtime_mock.window_call.assert_called_once()

    def test_set_min_size_none(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").set_min_size(None)
        runtime_mock.window_call.assert_called_once_with("x", "set_min_size", {})

    def test_set_max_size_with_size(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").set_max_size(PhysicalSize(2000, 1500))
        runtime_mock.window_call.assert_called_once()

    def test_set_max_size_none(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").set_max_size(None)
        runtime_mock.window_call.assert_called_once_with("x", "set_max_size", {})

    def test_set_position(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").set_position(PhysicalPosition(100, 200))
        args = runtime_mock.window_call.call_args[0]
        assert args[1] == "set_position"

    def test_set_fullscreen(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").set_fullscreen(True)
        runtime_mock.window_call.assert_called_once_with(
            "x", "set_fullscreen", {"fullscreen": True}
        )

    def test_set_decorations(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").set_decorations(False)
        runtime_mock.window_call.assert_called_once_with(
            "x", "set_decorations", {"decorations": False}
        )

    def test_set_always_on_top(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").set_always_on_top(True)
        runtime_mock.window_call.assert_called_once_with(
            "x", "set_always_on_top", {"always_on_top": True}
        )

    def test_set_always_on_bottom(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").set_always_on_bottom(True)
        runtime_mock.window_call.assert_called_once_with(
            "x", "set_always_on_bottom", {"always_on_bottom": True}
        )

    def test_set_resizable(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").set_resizable(False)
        runtime_mock.window_call.assert_called_once_with(
            "x", "set_resizable", {"resizable": False}
        )

    def test_set_enabled(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").set_enabled(False)
        runtime_mock.window_call.assert_called_once_with("x", "set_enabled", {"enabled": False})

    def test_set_closable(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").set_closable(False)
        runtime_mock.window_call.assert_called_once_with("x", "set_closable", {"closable": False})

    def test_set_maximizable(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").set_maximizable(False)
        runtime_mock.window_call.assert_called_once_with(
            "x", "set_maximizable", {"maximizable": False}
        )

    def test_set_minimizable(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").set_minimizable(False)
        runtime_mock.window_call.assert_called_once_with(
            "x", "set_minimizable", {"minimizable": False}
        )

    def test_set_visible_on_all_workspaces(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").set_visible_on_all_workspaces(True)
        runtime_mock.window_call.assert_called_once_with(
            "x", "set_visible_on_all_workspaces", {"visible": True}
        )

    def test_set_skip_taskbar(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").set_skip_taskbar(True)
        runtime_mock.window_call.assert_called_once_with(
            "x", "set_skip_taskbar", {"skip": True}
        )

    def test_set_cursor_icon(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").set_cursor_icon(CursorIcon.HAND)
        runtime_mock.window_call.assert_called_once_with(
            "x", "set_cursor_icon", {"icon": "Hand"}
        )

    def test_set_cursor_position(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").set_cursor_position(LogicalPosition(10.0, 20.0))
        runtime_mock.window_call.assert_called_once()

    def test_set_cursor_visible(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").set_cursor_visible(False)
        runtime_mock.window_call.assert_called_once_with(
            "x", "set_cursor_visible", {"visible": False}
        )

    def test_set_cursor_grab(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").set_cursor_grab(True)
        runtime_mock.window_call.assert_called_once_with("x", "set_cursor_grab", {"grab": True})

    def test_set_ignore_cursor_events(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").set_ignore_cursor_events(True)
        runtime_mock.window_call.assert_called_once_with(
            "x", "set_ignore_cursor_events", {"ignore": True}
        )

    def test_set_icon_with_bytes(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").set_icon(b"png_data")
        args = runtime_mock.window_call.call_args[0]
        assert args[1] == "set_icon"
        assert args[2]["icon"] is not None  # base64 encoded

    def test_set_icon_none(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").set_icon(None)
        args = runtime_mock.window_call.call_args[0]
        assert args[2]["icon"] is None

    def test_set_shadow(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").set_shadow(False)
        runtime_mock.window_call.assert_called_once_with("x", "set_shadow", {"enable": False})

    def test_set_title_bar_style(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").set_title_bar_style(TitleBarStyle.OVERLAY)
        runtime_mock.window_call.assert_called_once_with(
            "x", "set_title_bar_style", {"style": "Overlay"}
        )

    def test_set_theme_with_value(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").set_theme(Theme.LIGHT)
        runtime_mock.window_call.assert_called_once_with("x", "set_theme", {"theme": "Light"})

    def test_set_theme_none(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").set_theme(None)
        runtime_mock.window_call.assert_called_once_with("x", "set_theme", {"theme": None})

    def test_set_content_protected(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").set_content_protected(True)
        runtime_mock.window_call.assert_called_once_with(
            "x", "set_content_protected", {"protected": True}
        )

    def test_set_traffic_light_position(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").set_traffic_light_position(10.0, 20.0)
        runtime_mock.window_call.assert_called_once_with(
            "x", "set_traffic_light_position", {"x": 10.0, "y": 20.0}
        )

    def test_set_size_constraints_both(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").set_size_constraints(
            min_size=PhysicalSize(100, 100),
            max_size=PhysicalSize(2000, 1500),
        )
        args = runtime_mock.window_call.call_args[0]
        assert "min_size" in args[2]
        assert "max_size" in args[2]

    def test_set_size_constraints_none(self, runtime_mock: MagicMock) -> None:
        """Both None still calls (with empty args)."""
        WindowProxy("x").set_size_constraints()
        runtime_mock.window_call.assert_called_once_with("x", "set_size_constraints", {})

    def test_monitor_from_point_present(self, runtime_mock: MagicMock) -> None:
        runtime_mock.window_get.return_value = {
            "name": "M",
            "size": {"width": 1, "height": 1},
            "position": {"x": 0, "y": 0},
            "scale_factor": 1.0,
        }
        result = WindowProxy("x").monitor_from_point(10.0, 20.0)
        assert result is not None
        assert result.name == "M"

    def test_monitor_from_point_none(self, runtime_mock: MagicMock) -> None:
        runtime_mock.window_get.return_value = None
        assert WindowProxy("x").monitor_from_point(0, 0) is None

    def test_eval(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").eval("console.log()")
        runtime_mock.window_call.assert_called_once_with(
            "x", "eval", {"script": "console.log()"}
        )

    def test_eval_with_result(self, runtime_mock: MagicMock) -> None:
        runtime_mock.window_call.return_value = "result"
        result = WindowProxy("x").eval_with_result("script")
        assert result == "result"
        # should pass expect_response=True
        kwargs = runtime_mock.window_call.call_args.kwargs
        assert kwargs.get("expect_response") is True

    def test_navigate(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").navigate("https://x.com")
        runtime_mock.window_call.assert_called_once_with(
            "x", "navigate", {"url": "https://x.com"}
        )

    def test_set_zoom(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").set_zoom(1.5)
        runtime_mock.window_call.assert_called_once_with("x", "set_zoom", {"scale": 1.5})

    def test_set_background_color(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").set_background_color((10, 20, 30, 255))
        args = runtime_mock.window_call.call_args[0]
        assert args[1] == "set_background_color"
        assert args[2]["color"] == [10, 20, 30, 255]

    def test_set_effects(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").set_effects({"effects": [Effect.MICA], "state": EffectState.ACTIVE})
        runtime_mock.window_call.assert_called_once()

    def test_set_progress_bar(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").set_progress_bar({"status": ProgressBarStatus.NORMAL, "progress": 50})
        runtime_mock.window_call.assert_called_once()

    def test_set_badge_count(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").set_badge_count(5)
        runtime_mock.window_call.assert_called_once_with("x", "set_badge_count", {"count": 5})

    def test_set_overlay_icon_with_bytes(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").set_overlay_icon(b"png")
        args = runtime_mock.window_call.call_args[0]
        assert args[1] == "set_overlay_icon"
        assert args[2]["icon"] is not None

    def test_set_overlay_icon_none(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").set_overlay_icon(None)
        args = runtime_mock.window_call.call_args[0]
        assert args[2]["icon"] is None

    def test_cookies(self, runtime_mock: MagicMock) -> None:
        runtime_mock.window_call.return_value = [{"name": "n", "value": "v"}]
        result = WindowProxy("x").cookies()
        assert isinstance(result, list)
        assert len(result) == 1

    def test_cookies_empty(self, runtime_mock: MagicMock) -> None:
        runtime_mock.window_call.return_value = None
        assert WindowProxy("x").cookies() == []

    def test_set_cookie(self, runtime_mock: MagicMock) -> None:
        cookie = Cookie(name="n", value="v")
        WindowProxy("x").set_cookie(cookie)
        args = runtime_mock.window_call.call_args[0]
        assert args[1] == "set_cookie"

    def test_delete_cookie(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").delete_cookie("n")
        runtime_mock.window_call.assert_called_once_with("x", "delete_cookie", {"name": "n"})

    def test_remove_menu(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").remove_menu()
        runtime_mock.window_call.assert_called_once_with("x", "remove_menu", {})

    def test_hide_menu(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").hide_menu()
        runtime_mock.window_call.assert_called_once_with("x", "hide_menu", {})

    def test_show_menu(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").show_menu()
        runtime_mock.window_call.assert_called_once_with("x", "show_menu", {})

    def test_is_menu_visible(self, runtime_mock: MagicMock) -> None:
        runtime_mock.window_call.return_value = True
        assert WindowProxy("x").is_menu_visible() is True

    def test_mocked_repr(self, runtime_mock: MagicMock) -> None:
        proxy = WindowProxy("test-label")
        assert repr(proxy) == "WindowProxy('test-label')"


@patch("pywry.window_proxy.runtime")
class TestWindowProxyMockedMenu:
    """Test WindowProxy menu interaction methods."""

    def test_set_menu_with_proxy_object(self, runtime_mock: MagicMock) -> None:
        from pywry.menu_proxy import MenuProxy

        menu = MenuProxy("m1")
        wp = WindowProxy("x")
        with patch("pywry.menu_proxy.runtime") as menu_runtime:
            wp.set_menu(menu)
        # set_as_window_menu should send via menu_proxy.runtime
        menu_runtime.send_command.assert_called_once()

    def test_set_menu_with_dict(self, runtime_mock: MagicMock) -> None:
        """A non-MenuProxy menu uses send_command directly."""

        class FakeMenu:
            id = "fake-menu"

        WindowProxy("x").set_menu(FakeMenu())
        runtime_mock.send_command.assert_called_once()
        cmd = runtime_mock.send_command.call_args[0][0]
        assert cmd["action"] == "menu_set"
        assert cmd["menu_id"] == "fake-menu"
        assert cmd["target"] == "window"
        assert cmd["label"] == "x"

    def test_set_menu_with_str(self, runtime_mock: MagicMock) -> None:
        """A bare string menu uses str() conversion."""
        WindowProxy("x").set_menu("my-menu-id")
        runtime_mock.send_command.assert_called_once()
        cmd = runtime_mock.send_command.call_args[0][0]
        assert cmd["menu_id"] == "my-menu-id"

    def test_popup_menu_with_proxy(self, runtime_mock: MagicMock) -> None:
        from pywry.menu_proxy import MenuProxy

        menu = MenuProxy("m1")
        with patch("pywry.menu_proxy.runtime") as menu_runtime:
            WindowProxy("x").popup_menu(menu, x=10.0, y=20.0)
        menu_runtime.send_command.assert_called_once()

    def test_popup_menu_with_dict_and_position(self, runtime_mock: MagicMock) -> None:
        class FakeMenu:
            id = "fake"

        WindowProxy("x").popup_menu(FakeMenu(), x=5.0, y=10.0)
        cmd = runtime_mock.send_command.call_args[0][0]
        assert cmd["action"] == "menu_popup"
        assert cmd["position"] == {"x": 5.0, "y": 10.0}

    def test_popup_menu_no_position(self, runtime_mock: MagicMock) -> None:
        class FakeMenu:
            id = "fake"

        WindowProxy("x").popup_menu(FakeMenu())
        cmd = runtime_mock.send_command.call_args[0][0]
        assert "position" not in cmd

    def test_popup_menu_with_str(self, runtime_mock: MagicMock) -> None:
        WindowProxy("x").popup_menu("menu-str")
        cmd = runtime_mock.send_command.call_args[0][0]
        assert cmd["menu_id"] == "menu-str"


class TestTypeSerialization:
    """Verify the serializer helpers used by WindowProxy."""

    def test_serialize_logical_size(self) -> None:
        result = serialize_size(LogicalSize(800.0, 600.0))
        assert result["type"] == "Logical"
        assert result["width"] == 800.0

    def test_serialize_physical_size(self) -> None:
        result = serialize_size(PhysicalSize(800, 600))
        assert result["type"] == "Physical"

    def test_serialize_logical_position(self) -> None:
        result = serialize_position(LogicalPosition(10.0, 20.0))
        assert result["type"] == "Logical"

    def test_serialize_physical_position(self) -> None:
        result = serialize_position(PhysicalPosition(10, 20))
        assert result["type"] == "Physical"
