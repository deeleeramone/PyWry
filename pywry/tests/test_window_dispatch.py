"""Tests for pywry.window_dispatch module.

These tests verify the dispatch table logic and method routing.
We use minimal stub objects that implement the same interface
as pytauri windows to test the dispatch logic directly.

Note: These are NOT mock tests that just verify "method was called".
They verify that the dispatch logic:
1. Routes to the correct handler
2. Extracts correct return values
3. Raises appropriate errors for unknown properties/methods
4. Handles argument transformation correctly
"""

from __future__ import annotations

import sys

from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock, patch


# Coverage compatibility — ``coverage.Coverage.start()`` evicts ``pywry`` from
# ``sys.modules`` after importing it for path discovery.  ``pywry.__init__``
# sets ``sys._pytauri_standalone = True`` and registers
# ``sys.modules['__pytauri_ext_mod__']``, but the eviction can leave the flag
# set while the module is gone.  Reset the flag so a fresh import re-runs
# ``_setup_pytauri_standalone`` and ``pytauri.ffi`` imports work.
if getattr(sys, "_pytauri_standalone", False) and "__pytauri_ext_mod__" not in sys.modules:
    delattr(sys, "_pytauri_standalone")
from pywry._freeze import _setup_pytauri_standalone


_setup_pytauri_standalone()

import pytest  # noqa: E402

from pywry.window_dispatch import (  # noqa: E402
    APPEARANCE_METHODS,
    BEHAVIOR_METHODS,
    COOKIE_METHODS,
    CURSOR_METHODS,
    PROPERTY_GETTERS,
    PROPERTY_METHODS,
    SIZE_POSITION_METHODS,
    STATE_METHODS,
    VISIBILITY_METHODS,
    WEBVIEW_METHODS,
    _call_appearance_method,
    _call_behavior_method,
    _call_cookie_method,
    _call_cursor_method,
    _call_size_position_method,
    _call_state_method,
    _call_visibility_method,
    _call_webview_method,
    _extract_position,
    _extract_size,
    _serialize_cookie,
    _serialize_monitor,
    _set_background_color,
    _set_badge_count,
    _set_effects,
    _set_icon,
    _set_overlay_icon,
    _set_theme,
    _set_title_bar_style,
    call_window_method,
    get_window_property,
)


# =============================================================================
# Stub Classes - Real objects that behave like pytauri types
# =============================================================================


@dataclass
class StubPosition:
    """Stub for position types."""

    x: int
    y: int


@dataclass
class StubSize:
    """Stub for size types."""

    width: int
    height: int


class StubMonitor:
    """Stub for pytauri Monitor."""

    def __init__(
        self,
        name: str | None = "Test Monitor",
        width: int = 1920,
        height: int = 1080,
        x: int = 0,
        y: int = 0,
        scale: float = 1.0,
    ):
        """Initialize monitor with dimensions and position."""
        self._name = name
        self._size = StubSize(width, height)
        self._position = StubPosition(x, y)
        self._scale = scale

    def name(self) -> str | None:
        """Return monitor name."""
        return self._name

    def size(self) -> StubSize:
        """Return monitor size."""
        return self._size

    def position(self) -> StubPosition:
        """Return monitor position."""
        return self._position

    def scale_factor(self) -> float:
        """Return monitor scale factor."""
        return self._scale


class StubTheme:
    """Stub for pytauri Theme enum."""

    def __init__(self, name: str = "Dark"):
        """Initialize theme with name."""
        self.name = name


@dataclass
class WindowGeometry:
    """Grouped geometry state for StubWindow."""

    inner_pos: StubPosition
    outer_pos: StubPosition
    inner_size: StubSize
    outer_size: StubSize
    scale_factor: float = 2.0


@dataclass
class WindowVisibility:
    """Window visibility and focus state."""

    visible: bool = True
    focused: bool = False
    maximized: bool = False
    minimized: bool = False
    fullscreen: bool = False


@dataclass
class WindowCapabilities:
    """Window capability flags."""

    decorated: bool = True
    resizable: bool = True
    enabled: bool = True
    maximizable: bool = True
    minimizable: bool = True
    closable: bool = True
    always_on_top: bool = False
    always_on_bottom: bool = False
    shadow: bool = True
    content_protected: bool = False


@dataclass
class WindowCursor:
    """Cursor state for window."""

    visible: bool = True
    grab: bool = False
    ignore_events: bool = False


@dataclass
class WindowMonitors:
    """Grouped monitor info for StubWindow."""

    primary: StubMonitor
    current: StubMonitor
    available: list[StubMonitor]


class StubWindow:
    """Stub window that implements pytauri WebviewWindow interface.

    This is a REAL object with REAL state, not a mock.
    Methods actually change state that can be verified.
    Uses composition to group related state.

    Note: The many public methods here mirror the real pytauri interface.
    """

    def __init__(self) -> None:
        """Initialize window with default state."""
        # Basic properties
        self._title = "Default Title"
        self._url = "https://example.com"
        self._theme = StubTheme("Dark")
        self._zoom = 1.0
        self._devtools_open = False

        # Grouped state via composition
        self._geometry = WindowGeometry(
            inner_pos=StubPosition(100, 200),
            outer_pos=StubPosition(95, 175),
            inner_size=StubSize(800, 600),
            outer_size=StubSize(850, 650),
        )
        self._visibility = WindowVisibility()
        self._capabilities = WindowCapabilities()
        self._cursor = WindowCursor()
        primary = StubMonitor("Primary", 2560, 1440)
        current = StubMonitor("Current", 1920, 1080)
        self._monitors = WindowMonitors(
            primary=primary,
            current=current,
            available=[primary, current],
        )

        # Track method calls for verification
        self._calls: list[tuple[str, tuple[Any, ...]]] = []

    def _record(self, method: str, *args: Any) -> None:
        """Record method call for verification."""
        self._calls.append((method, args))

    # Property getters
    def title(self) -> str:
        """Return window title."""
        return self._title

    def url(self) -> str:
        """Return current URL."""
        return self._url

    def theme(self) -> StubTheme:
        """Return current theme."""
        return self._theme

    def scale_factor(self) -> float:
        """Return scale factor."""
        return self._geometry.scale_factor

    def inner_position(self) -> StubPosition:
        """Return inner position."""
        return self._geometry.inner_pos

    def outer_position(self) -> StubPosition:
        """Return outer position."""
        return self._geometry.outer_pos

    def inner_size(self) -> StubSize:
        """Return inner size."""
        return self._geometry.inner_size

    def outer_size(self) -> StubSize:
        """Return outer size."""
        return self._geometry.outer_size

    def current_monitor(self) -> StubMonitor:
        """Return current monitor."""
        return self._monitors.current

    def primary_monitor(self) -> StubMonitor:
        """Return primary monitor."""
        return self._monitors.primary

    def available_monitors(self) -> list[StubMonitor]:
        """Return available monitors."""
        return self._monitors.available

    # Boolean state getters
    def is_visible(self) -> bool:
        """Return visibility state."""
        return self._visibility.visible

    def is_focused(self) -> bool:
        """Return focus state."""
        return self._visibility.focused

    def is_decorated(self) -> bool:
        """Return decoration state."""
        return self._capabilities.decorated

    def is_resizable(self) -> bool:
        """Return resizable state."""
        return self._capabilities.resizable

    def is_enabled(self) -> bool:
        """Return enabled state."""
        return self._capabilities.enabled

    def is_maximizable(self) -> bool:
        """Return maximizable state."""
        return self._capabilities.maximizable

    def is_minimizable(self) -> bool:
        """Return minimizable state."""
        return self._capabilities.minimizable

    def is_closable(self) -> bool:
        """Return closable state."""
        return self._capabilities.closable

    def is_maximized(self) -> bool:
        """Return maximized state."""
        return self._visibility.maximized

    def is_minimized(self) -> bool:
        """Return minimized state."""
        return self._visibility.minimized

    def is_fullscreen(self) -> bool:
        """Return fullscreen state."""
        return self._visibility.fullscreen

    def is_always_on_top(self) -> bool:
        """Return always-on-top state."""
        return self._capabilities.always_on_top

    def is_always_on_bottom(self) -> bool:
        """Return always-on-bottom state."""
        return self._capabilities.always_on_bottom

    def is_devtools_open(self) -> bool:
        """Return devtools open state."""
        return self._devtools_open

    # Visibility methods
    def show(self) -> None:
        """Show the window."""
        self._record("show")
        self._visibility.visible = True

    def hide(self) -> None:
        """Hide the window."""
        self._record("hide")
        self._visibility.visible = False

    def set_focus(self) -> None:
        """Focus the window."""
        self._record("set_focus")
        self._visibility.focused = True

    def close(self) -> None:
        """Close the window."""
        self._record("close")
        self._visibility.visible = False

    def destroy(self) -> None:
        """Destroy the window."""
        self._record("destroy")
        self._visibility.visible = False

    # State methods
    def minimize(self) -> None:
        """Minimize the window."""
        self._record("minimize")
        self._visibility.minimized = True

    def unminimize(self) -> None:
        """Unminimize the window."""
        self._record("unminimize")
        self._visibility.minimized = False

    def maximize(self) -> None:
        """Maximize the window."""
        self._record("maximize")
        self._visibility.maximized = True

    def unmaximize(self) -> None:
        """Unmaximize the window."""
        self._record("unmaximize")
        self._visibility.maximized = False

    def toggle_maximize(self) -> None:
        """Toggle maximize state."""
        self._record("toggle_maximize")
        self._visibility.maximized = not self._visibility.maximized

    def set_fullscreen(self, fullscreen: bool) -> None:
        """Set fullscreen state."""
        self._record("set_fullscreen", fullscreen)
        self._visibility.fullscreen = fullscreen

    def center(self) -> None:
        """Center the window."""
        self._record("center")

    def request_user_attention(self, attention_type: Any) -> None:
        """Request user attention."""
        self._record("request_user_attention", attention_type)

    # Property setters
    def set_title(self, title: str) -> None:
        """Set window title."""
        self._record("set_title", title)
        self._title = title

    def set_enabled(self, enabled: bool) -> None:
        """Set enabled state."""
        self._record("set_enabled", enabled)
        self._capabilities.enabled = enabled

    def set_decorations(self, decorations: bool) -> None:
        """Set decoration state."""
        self._record("set_decorations", decorations)
        self._capabilities.decorated = decorations

    def set_resizable(self, resizable: bool) -> None:
        """Set resizable state."""
        self._record("set_resizable", resizable)
        self._capabilities.resizable = resizable

    def set_maximizable(self, maximizable: bool) -> None:
        """Set maximizable state."""
        self._record("set_maximizable", maximizable)
        self._capabilities.maximizable = maximizable

    def set_minimizable(self, minimizable: bool) -> None:
        """Set minimizable state."""
        self._record("set_minimizable", minimizable)
        self._capabilities.minimizable = minimizable

    def set_closable(self, closable: bool) -> None:
        """Set closable state."""
        self._record("set_closable", closable)
        self._capabilities.closable = closable

    def set_always_on_top(self, always: bool) -> None:
        """Set always-on-top state."""
        self._record("set_always_on_top", always)
        self._capabilities.always_on_top = always

    def set_always_on_bottom(self, always: bool) -> None:
        """Set always-on-bottom state."""
        self._record("set_always_on_bottom", always)
        self._capabilities.always_on_bottom = always

    # Size/position methods
    def set_size(self, size: Any) -> None:
        """Set window size."""
        self._record("set_size", size)
        # Handle pytauri wrapper (has _0) or plain tuple
        if hasattr(size, "_0"):
            w, h = size._0
        else:
            w, h = size[0], size[1]
        self._geometry.inner_size = StubSize(int(w), int(h))

    def set_min_size(self, size: Any) -> None:
        """Set minimum size."""
        self._record("set_min_size", size)

    def set_max_size(self, size: Any) -> None:
        """Set maximum size."""
        self._record("set_max_size", size)

    def set_position(self, pos: Any) -> None:
        """Set window position."""
        self._record("set_position", pos)
        # Handle pytauri wrapper (has _0) or plain tuple
        if hasattr(pos, "_0"):
            x, y = pos._0
        else:
            x, y = pos[0], pos[1]
        self._geometry.inner_pos = StubPosition(int(x), int(y))

    # Appearance methods
    def set_background_color(self, color: tuple[int, ...]) -> None:
        """Set background color."""
        self._record("set_background_color", color)

    def set_theme(self, theme: Any) -> None:
        """Set window theme."""
        self._record("set_theme", theme)
        self._theme = StubTheme(str(theme))

    def set_title_bar_style(self, style: Any) -> None:
        """Set title bar style."""
        self._record("set_title_bar_style", style)

    def set_content_protected(self, protected: bool) -> None:
        """Set content protection."""
        self._record("set_content_protected", protected)
        self._capabilities.content_protected = protected

    def set_shadow(self, shadow: bool) -> None:
        """Set window shadow."""
        self._record("set_shadow", shadow)
        self._capabilities.shadow = shadow

    def set_effects(self, effects: Any) -> None:
        """Set window effects."""
        self._record("set_effects", effects)

    # Cursor methods
    def set_cursor_icon(self, icon: Any) -> None:
        """Set cursor icon."""
        self._record("set_cursor_icon", icon)

    def set_cursor_position(self, pos: Any) -> None:
        """Set cursor position."""
        self._record("set_cursor_position", pos)

    def set_cursor_visible(self, visible: bool) -> None:
        """Set cursor visibility."""
        self._record("set_cursor_visible", visible)
        self._cursor.visible = visible

    def set_cursor_grab(self, grab: bool) -> None:
        """Set cursor grab state."""
        self._record("set_cursor_grab", grab)
        self._cursor.grab = grab

    # Behavior methods
    def set_ignore_cursor_events(self, ignore: bool) -> None:
        """Set ignore cursor events state."""
        self._record("set_ignore_cursor_events", ignore)
        self._cursor.ignore_events = ignore

    def set_progress_bar(self, state: Any) -> None:
        """Set progress bar state."""
        self._record("set_progress_bar", state)

    def set_visible_on_all_workspaces(self, visible: bool) -> None:
        """Set visible on all workspaces."""
        self._record("set_visible_on_all_workspaces", visible)

    def set_traffic_light_position(self, pos: Any) -> None:
        """Set traffic light position."""
        self._record("set_traffic_light_position", pos)

    # Webview methods
    def navigate(self, url: str) -> None:
        """Navigate to URL."""
        self._record("navigate", url)
        self._url = url

    def eval(self, script: str) -> None:
        """Evaluate JavaScript."""
        self._record("eval", script)

    def open_devtools(self) -> None:
        """Open devtools."""
        self._record("open_devtools")
        self._devtools_open = True

    def close_devtools(self) -> None:
        """Close devtools."""
        self._record("close_devtools")
        self._devtools_open = False

    def set_zoom(self, zoom: float) -> None:
        """Set zoom level."""
        self._record("set_zoom", zoom)
        self._zoom = zoom

    def zoom(self, zoom: float) -> None:
        """Set zoom level (alias)."""
        self._record("zoom", zoom)
        self._zoom = zoom

    def clear_all_browsing_data(self) -> None:
        """Clear all browsing data."""
        self._record("clear_all_browsing_data")

    def reload(self) -> None:
        """Reload the page."""
        self._record("reload")

    def print(self) -> None:
        """Print the page."""
        self._record("print")


# =============================================================================
# Tests for get_window_property
# =============================================================================


class TestGetWindowProperty:
    """Test property getter dispatch."""

    def test_title_property(self) -> None:
        """title returns window title."""
        window = StubWindow()
        window._title = "Test Title"

        result = get_window_property(window, "title")
        assert result == "Test Title"

    def test_url_property(self) -> None:
        """url returns current URL."""
        window = StubWindow()
        window._url = "https://test.com"

        result = get_window_property(window, "url")
        assert result == "https://test.com"

    def test_theme_property(self) -> None:
        """theme returns theme name."""
        window = StubWindow()
        window._theme = StubTheme("Light")

        result = get_window_property(window, "theme")
        assert result == "Light"

    def test_scale_factor_property(self) -> None:
        """scale_factor returns numeric value."""
        window = StubWindow()
        window._geometry.scale_factor = 1.5

        result = get_window_property(window, "scale_factor")
        assert result == 1.5

    def test_inner_position_returns_dict(self) -> None:
        """inner_position returns {x, y} dict."""
        window = StubWindow()
        window._geometry.inner_pos = StubPosition(150, 250)

        result = get_window_property(window, "inner_position")
        assert result == {"x": 150, "y": 250}

    def test_outer_position_returns_dict(self) -> None:
        """outer_position returns {x, y} dict."""
        window = StubWindow()
        window._geometry.outer_pos = StubPosition(145, 225)

        result = get_window_property(window, "outer_position")
        assert result == {"x": 145, "y": 225}

    def test_inner_size_returns_dict(self) -> None:
        """inner_size returns {width, height} dict."""
        window = StubWindow()
        window._geometry.inner_size = StubSize(1024, 768)

        result = get_window_property(window, "inner_size")
        assert result == {"width": 1024, "height": 768}

    def test_outer_size_returns_dict(self) -> None:
        """outer_size returns {width, height} dict."""
        window = StubWindow()
        window._geometry.outer_size = StubSize(1050, 800)

        result = get_window_property(window, "outer_size")
        assert result == {"width": 1050, "height": 800}

    def test_current_monitor_returns_serialized(self) -> None:
        """current_monitor returns serialized monitor data."""
        window = StubWindow()

        result = get_window_property(window, "current_monitor")
        assert isinstance(result, dict)
        assert result["name"] == "Current"
        assert result["size"] == {"width": 1920, "height": 1080}
        assert result["position"] == {"x": 0, "y": 0}
        assert result["scale_factor"] == 1.0

    def test_primary_monitor_returns_serialized(self) -> None:
        """primary_monitor returns serialized monitor data."""
        window = StubWindow()

        result = get_window_property(window, "primary_monitor")
        assert isinstance(result, dict)
        assert result["name"] == "Primary"
        assert result["size"] == {"width": 2560, "height": 1440}

    def test_available_monitors_returns_list(self) -> None:
        """available_monitors returns list of serialized monitors."""
        window = StubWindow()

        result = get_window_property(window, "available_monitors")
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["name"] == "Primary"
        assert result[1]["name"] == "Current"

    def test_boolean_properties(self) -> None:
        """Boolean state properties return actual values."""
        window = StubWindow()
        window._visibility.visible = True
        window._visibility.maximized = False
        window._visibility.fullscreen = False
        window._capabilities.decorated = True

        assert get_window_property(window, "is_visible") is True
        assert get_window_property(window, "is_maximized") is False
        assert get_window_property(window, "is_fullscreen") is False
        assert get_window_property(window, "is_decorated") is True

    def test_unknown_property_raises(self) -> None:
        """Unknown property name raises ValueError."""
        window = StubWindow()

        with pytest.raises(ValueError, match="Unknown property"):
            get_window_property(window, "nonexistent_property")

    def test_monitor_from_point_raises(self) -> None:
        """monitor_from_point requires parameters, raises error."""
        window = StubWindow()

        with pytest.raises(ValueError, match="requires x, y parameters"):
            get_window_property(window, "monitor_from_point")


class TestSerializeMonitor:
    """Test monitor serialization helper."""

    def test_none_input(self) -> None:
        """None monitor returns None."""
        result = _serialize_monitor(None)
        assert result is None

    def test_full_monitor(self) -> None:
        """Full monitor is serialized correctly."""
        monitor = StubMonitor("Display 1", 2560, 1440, 100, 50, 2.0)

        result = _serialize_monitor(monitor)
        assert result == {
            "name": "Display 1",
            "position": {"x": 100, "y": 50},
            "size": {"width": 2560, "height": 1440},
            "scale_factor": 2.0,
        }


# =============================================================================
# Tests for call_window_method
# =============================================================================


class TestCallWindowMethodVisibility:
    """Test visibility method dispatch."""

    def test_show(self) -> None:
        """show() makes window visible."""
        window = StubWindow()
        window._visibility.visible = False

        call_window_method(window, "show", {})
        assert window._visibility.visible is True

    def test_hide(self) -> None:
        """hide() hides window."""
        window = StubWindow()
        window._visibility.visible = True

        call_window_method(window, "hide", {})
        assert window._visibility.visible is False

    def test_set_focus(self) -> None:
        """set_focus() sets focus."""
        window = StubWindow()

        call_window_method(window, "set_focus", {})
        assert window._visibility.focused is True

    def test_set_visible_true(self) -> None:
        """set_visible with visible=True calls show."""
        window = StubWindow()
        window._visibility.visible = False

        call_window_method(window, "set_visible", {"visible": True})
        assert window._visibility.visible is True

    def test_set_visible_false(self) -> None:
        """set_visible with visible=False calls hide."""
        window = StubWindow()
        window._visibility.visible = True

        call_window_method(window, "set_visible", {"visible": False})
        assert window._visibility.visible is False


class TestCallWindowMethodState:
    """Test window state method dispatch."""

    def test_minimize(self) -> None:
        """minimize() minimizes window."""
        window = StubWindow()

        call_window_method(window, "minimize", {})
        assert window._visibility.minimized is True

    def test_unminimize(self) -> None:
        """unminimize() restores window."""
        window = StubWindow()
        window._visibility.minimized = True

        call_window_method(window, "unminimize", {})
        assert window._visibility.minimized is False

    def test_maximize(self) -> None:
        """maximize() maximizes window."""
        window = StubWindow()

        call_window_method(window, "maximize", {})
        assert window._visibility.maximized is True

    def test_unmaximize(self) -> None:
        """unmaximize() restores window."""
        window = StubWindow()
        window._visibility.maximized = True

        call_window_method(window, "unmaximize", {})
        assert window._visibility.maximized is False

    def test_toggle_maximize(self) -> None:
        """toggle_maximize() toggles state."""
        window = StubWindow()
        window._visibility.maximized = False

        call_window_method(window, "toggle_maximize", {})
        assert window._visibility.maximized is True

        call_window_method(window, "toggle_maximize", {})
        assert window._visibility.maximized is False

    def test_set_fullscreen(self) -> None:
        """set_fullscreen() sets fullscreen state."""
        window = StubWindow()

        call_window_method(window, "set_fullscreen", {"fullscreen": True})
        assert window._visibility.fullscreen is True

        call_window_method(window, "set_fullscreen", {"fullscreen": False})
        assert window._visibility.fullscreen is False


class TestCallWindowMethodPropertySetters:
    """Test property setter method dispatch."""

    def test_set_title(self) -> None:
        """set_title() changes title."""
        window = StubWindow()

        call_window_method(window, "set_title", {"title": "New Title"})
        assert window._title == "New Title"

    def test_set_decorations(self) -> None:
        """set_decorations() changes decoration state."""
        window = StubWindow()
        window._capabilities.decorated = True

        call_window_method(window, "set_decorations", {"decorations": False})
        assert window._capabilities.decorated is False

    def test_set_resizable(self) -> None:
        """set_resizable() changes resizable state."""
        window = StubWindow()
        window._capabilities.resizable = True

        call_window_method(window, "set_resizable", {"resizable": False})
        assert window._capabilities.resizable is False

    def test_set_always_on_top(self) -> None:
        """set_always_on_top() changes always-on-top state."""
        window = StubWindow()

        call_window_method(window, "set_always_on_top", {"always_on_top": True})
        assert window._capabilities.always_on_top is True


class TestCallWindowMethodSizePosition:
    """Test size/position method dispatch."""

    def test_set_size(self) -> None:
        """set_size() changes window size."""
        window = StubWindow()

        call_window_method(window, "set_size", {"width": 1024, "height": 768})
        assert window._geometry.inner_size.width == 1024
        assert window._geometry.inner_size.height == 768

    def test_set_position(self) -> None:
        """set_position() changes window position."""
        window = StubWindow()

        call_window_method(window, "set_position", {"x": 200, "y": 150})
        assert window._geometry.inner_pos.x == 200
        assert window._geometry.inner_pos.y == 150


class TestCallWindowMethodWebview:
    """Test webview method dispatch."""

    def test_navigate(self) -> None:
        """navigate() changes URL."""
        window = StubWindow()

        call_window_method(window, "navigate", {"url": "https://new.com"})
        assert window._url == "https://new.com"

    def test_eval(self) -> None:
        """eval() executes script."""
        window = StubWindow()

        call_window_method(window, "eval", {"script": "console.log('test')"})
        assert ("eval", ("console.log('test')",)) in window._calls

    def test_open_devtools(self) -> None:
        """open_devtools() opens developer tools."""
        window = StubWindow()

        call_window_method(window, "open_devtools", {})
        assert window._devtools_open is True

    def test_close_devtools(self) -> None:
        """close_devtools() closes developer tools."""
        window = StubWindow()
        window._devtools_open = True

        call_window_method(window, "close_devtools", {})
        assert window._devtools_open is False

    def test_reload(self) -> None:
        """reload() reloads page."""
        window = StubWindow()

        call_window_method(window, "reload", {})
        assert ("reload", ()) in window._calls


class TestCallWindowMethodUnknown:
    """Test error handling for unknown methods."""

    def test_unknown_method_raises(self) -> None:
        """Unknown method name raises ValueError."""
        window = StubWindow()

        with pytest.raises(ValueError, match="Unknown method"):
            call_window_method(window, "nonexistent_method", {})


class TestDispatchTableCompleteness:
    """Verify dispatch tables are complete and well-formed."""

    def test_property_getters_all_callable(self) -> None:
        """All property getters are callable."""
        for prop_name, getter in PROPERTY_GETTERS.items():
            assert callable(getter), f"Getter for {prop_name} is not callable"

    def test_method_categories_non_overlapping(self) -> None:
        """Method categories don't overlap."""
        all_methods = [
            VISIBILITY_METHODS,
            STATE_METHODS,
            PROPERTY_METHODS,
            SIZE_POSITION_METHODS,
            APPEARANCE_METHODS,
            CURSOR_METHODS,
            BEHAVIOR_METHODS,
            WEBVIEW_METHODS,
            COOKIE_METHODS,
        ]

        seen: set[str] = set()
        for category in all_methods:
            for method in category:
                assert method not in seen, f"Method {method} appears in multiple categories"
                seen.add(method)

    def test_method_categories_non_empty(self) -> None:
        """All method categories have at least one method."""
        assert len(VISIBILITY_METHODS) > 0
        assert len(STATE_METHODS) > 0
        assert len(PROPERTY_METHODS) > 0
        assert len(SIZE_POSITION_METHODS) > 0
        assert len(APPEARANCE_METHODS) > 0
        assert len(CURSOR_METHODS) > 0
        assert len(BEHAVIOR_METHODS) > 0
        assert len(WEBVIEW_METHODS) > 0
        assert len(COOKIE_METHODS) > 0


# =============================================================================
# Helper extractor and serializer tests (pure functions)
# =============================================================================


class TestExtractPosition:
    """Tests for the position extractor."""

    def test_none(self) -> None:
        assert _extract_position(None) is None

    def test_pytauri_wrapper_zero_attr(self) -> None:
        """pytauri wraps positions in `_0` tuple attribute."""
        wrapper = MagicMock()
        wrapper._0 = (10, 20)
        assert _extract_position(wrapper) == {"x": 10, "y": 20}

    def test_direct_tuple(self) -> None:
        """Direct tuples are unpacked."""
        assert _extract_position((5, 7)) == {"x": 5, "y": 7}

    def test_object_with_xy_attrs(self) -> None:
        """Objects with .x and .y attributes work too."""

        class P:
            x = 1
            y = 2

        assert _extract_position(P()) == {"x": 1, "y": 2}

    def test_unknown_returns_none(self) -> None:
        """Unknown shape returns None."""

        class Unknown:
            pass

        assert _extract_position(Unknown()) is None


class TestExtractSize:
    """Tests for the size extractor."""

    def test_none(self) -> None:
        assert _extract_size(None) is None

    def test_pytauri_wrapper_zero_attr(self) -> None:
        wrapper = MagicMock()
        wrapper._0 = (640, 480)
        assert _extract_size(wrapper) == {"width": 640, "height": 480}

    def test_direct_tuple(self) -> None:
        assert _extract_size((800, 600)) == {"width": 800, "height": 600}

    def test_object_with_wh_attrs(self) -> None:
        class S:
            width = 1024
            height = 768

        assert _extract_size(S()) == {"width": 1024, "height": 768}

    def test_unknown_returns_none(self) -> None:
        class Unknown:
            pass

        assert _extract_size(Unknown()) is None


class TestSerializeMonitorAttrStyle:
    """Tests for monitor serialization with non-callable attributes."""

    def test_with_attribute_style_monitor(self) -> None:
        """Monitor can have non-callable attributes."""

        class _Pos:
            x = 0
            y = 0

        class _Size:
            width = 1920
            height = 1080

        class StaticMonitor:
            name = "Display 1"
            position = _Pos()
            size = _Size()
            scale_factor = 2.0

        result = _serialize_monitor(StaticMonitor())
        assert result["name"] == "Display 1"
        assert result["position"] == {"x": 0, "y": 0}
        assert result["size"] == {"width": 1920, "height": 1080}
        assert result["scale_factor"] == 2.0


# =============================================================================
# get_window_property - additional branches with mocked window
# =============================================================================


class TestGetWindowPropertyEdgeCases:
    """Branches that need a Mock-style window (None returns, missing attrs)."""

    def test_url_empty_returns_string(self) -> None:
        """url returns empty string when window URL is None."""
        window = MagicMock()
        window.url.return_value = None
        assert get_window_property(window, "url") == ""

    def test_theme_with_str(self) -> None:
        """theme returns str() when theme has no .name attribute."""
        window = MagicMock()
        window.theme.return_value = "Light"
        # str(theme) uses fallback
        assert get_window_property(window, "theme") == "Light"

    def test_inner_position_none(self) -> None:
        """inner_position handles None."""
        window = MagicMock()
        window.inner_position.return_value = None
        assert get_window_property(window, "inner_position") is None

    def test_outer_position_none(self) -> None:
        window = MagicMock()
        window.outer_position.return_value = None
        assert get_window_property(window, "outer_position") is None

    def test_inner_size_none(self) -> None:
        window = MagicMock()
        window.inner_size.return_value = None
        assert get_window_property(window, "inner_size") is None

    def test_outer_size_none(self) -> None:
        window = MagicMock()
        window.outer_size.return_value = None
        assert get_window_property(window, "outer_size") is None

    def test_current_monitor_none(self) -> None:
        window = MagicMock()
        window.current_monitor.return_value = None
        assert get_window_property(window, "current_monitor") is None

    def test_primary_monitor_none(self) -> None:
        window = MagicMock()
        window.primary_monitor.return_value = None
        assert get_window_property(window, "primary_monitor") is None

    def test_available_monitors_empty(self) -> None:
        """Empty list returns empty list."""
        window = MagicMock()
        window.available_monitors.return_value = []
        assert get_window_property(window, "available_monitors") == []

    def test_available_monitors_none(self) -> None:
        """None list returns empty list."""
        window = MagicMock()
        window.available_monitors.return_value = None
        assert get_window_property(window, "available_monitors") == []

    def test_available_monitors_with_valid_entry(self) -> None:
        """Single valid monitor serializes correctly."""
        window = MagicMock()
        m1 = MagicMock()
        m1.name = "M1"
        m1.position = MagicMock(_0=(0, 0))
        m1.size = MagicMock(_0=(800, 600))
        m1.scale_factor = 1.0
        window.available_monitors.return_value = [m1]
        result = get_window_property(window, "available_monitors")
        assert len(result) == 1
        assert result[0]["name"] == "M1"

    def test_is_devtools_open_with_attr(self) -> None:
        """is_devtools_open returns the value."""
        window = MagicMock()
        window.is_devtools_open.return_value = True
        assert get_window_property(window, "is_devtools_open") is True

    def test_is_devtools_open_without_attr(self) -> None:
        """is_devtools_open returns False when attribute is missing."""

        class NoDevtools:
            def title(self) -> str:
                return "x"

            def url(self) -> str:
                return "u"

        assert get_window_property(NoDevtools(), "is_devtools_open") is False

    def test_monitor_from_point_with_args(self) -> None:
        """monitor_from_point requires x/y args."""
        window = MagicMock()
        m = MagicMock()
        m.name = "M"
        m.position = MagicMock(_0=(0, 0))
        m.size = MagicMock(_0=(100, 100))
        m.scale_factor = 1.0
        window.monitor_from_point.return_value = m
        result = get_window_property(window, "monitor_from_point", {"x": 10, "y": 20})
        assert result["name"] == "M"

    def test_monitor_from_point_returns_none(self) -> None:
        """monitor_from_point returning None still serializes."""
        window = MagicMock()
        window.monitor_from_point.return_value = None
        assert get_window_property(window, "monitor_from_point", {"x": 10, "y": 20}) is None

    def test_monitor_from_point_no_attr(self) -> None:
        """monitor_from_point returns None when window doesn't support it."""

        class NoMonitor:
            pass

        assert get_window_property(NoMonitor(), "monitor_from_point", {"x": 10, "y": 20}) is None


# =============================================================================
# Visibility / State / Property setter branches
# =============================================================================


class TestVisibilityDispatch:
    """Visibility method branches reached via _call_visibility_method."""

    def test_close_routes(self) -> None:
        window = MagicMock()
        _call_visibility_method(window, "close", {})
        window.close.assert_called_once()

    def test_destroy_routes(self) -> None:
        window = MagicMock()
        _call_visibility_method(window, "destroy", {})
        window.destroy.assert_called_once()

    def test_set_visible_default_true(self) -> None:
        """set_visible with no args defaults visible=True -> show()."""
        window = MagicMock()
        _call_visibility_method(window, "set_visible", {})
        window.show.assert_called_once()

    def test_start_dragging_routes(self) -> None:
        window = MagicMock()
        _call_visibility_method(window, "start_dragging", {})
        window.start_dragging.assert_called_once()

    def test_start_dragging_missing_attr(self) -> None:
        """start_dragging is a no-op when window lacks the method."""

        class NoDrag:
            pass

        # Should not raise
        _call_visibility_method(NoDrag(), "start_dragging", {})


class TestStateDispatch:
    """State method branches reached via _call_state_method."""

    def test_center_routes(self) -> None:
        window = MagicMock()
        _call_state_method(window, "center", {})
        window.center.assert_called_once()

    def test_request_user_attention_none(self) -> None:
        """attention_type=None calls with None."""
        window = MagicMock()
        _call_state_method(window, "request_user_attention", {})
        window.request_user_attention.assert_called_once_with(None)

    def test_request_user_attention_with_string(self) -> None:
        """String attention_type maps via UserAttentionType enum."""
        attn_mod = MagicMock()
        attn_mod.CRITICAL = "critical_value"
        with patch.dict("sys.modules", {"pytauri": MagicMock(UserAttentionType=attn_mod)}):
            window = MagicMock()
            _call_state_method(
                window,
                "request_user_attention",
                {"attention_type": "CRITICAL"},
            )
            window.request_user_attention.assert_called_once_with("critical_value")

    def test_request_user_attention_with_object(self) -> None:
        """Non-string attention_type passes through unchanged."""
        with patch.dict("sys.modules", {"pytauri": MagicMock()}):
            window = MagicMock()
            obj = object()
            _call_state_method(window, "request_user_attention", {"attention_type": obj})
            window.request_user_attention.assert_called_once_with(obj)


class TestPropertySetterDispatch:
    """Property setters routed through call_window_method."""

    def test_set_enabled(self) -> None:
        window = MagicMock()
        call_window_method(window, "set_enabled", {"enabled": False})
        window.set_enabled.assert_called_once_with(False)

    def test_set_maximizable(self) -> None:
        window = MagicMock()
        call_window_method(window, "set_maximizable", {"maximizable": False})
        window.set_maximizable.assert_called_once_with(False)

    def test_set_minimizable(self) -> None:
        window = MagicMock()
        call_window_method(window, "set_minimizable", {"minimizable": False})
        window.set_minimizable.assert_called_once_with(False)

    def test_set_closable(self) -> None:
        window = MagicMock()
        call_window_method(window, "set_closable", {"closable": False})
        window.set_closable.assert_called_once_with(False)

    def test_set_always_on_bottom(self) -> None:
        window = MagicMock()
        call_window_method(window, "set_always_on_bottom", {"always_on_bottom": True})
        window.set_always_on_bottom.assert_called_once_with(True)

    def test_set_skip_taskbar(self) -> None:
        window = MagicMock()
        call_window_method(window, "set_skip_taskbar", {"skip": True})
        window.set_skip_taskbar.assert_called_once_with(True)


# =============================================================================
# Size/Position helper - uses real pytauri.ffi.Position/Size wrappers
# =============================================================================


class TestSizePositionHelpers:
    """Helper-level tests for _call_size_position_method.

    Uses real pytauri.ffi.Position/Size types — patching ``sys.modules``
    breaks coverage's import handling on this platform, so we let the
    real wrappers run and inspect the ``_0`` tuple that pytauri uses.
    """

    def test_set_size(self) -> None:
        window = MagicMock()
        _call_size_position_method(window, "set_size", {"width": 800, "height": 600})
        called_size = window.set_size.call_args[0][0]
        assert called_size._0 == (800, 600)

    def test_set_size_default(self) -> None:
        """Defaults to 800x600 when no width/height provided."""
        window = MagicMock()
        _call_size_position_method(window, "set_size", {})
        called_size = window.set_size.call_args[0][0]
        assert called_size._0 == (800, 600)

    def test_set_min_size_with_values(self) -> None:
        window = MagicMock()
        _call_size_position_method(window, "set_min_size", {"width": 100, "height": 100})
        called = window.set_min_size.call_args[0][0]
        assert called._0 == (100, 100)

    def test_set_min_size_none(self) -> None:
        """No width/height passes None."""
        window = MagicMock()
        _call_size_position_method(window, "set_min_size", {})
        window.set_min_size.assert_called_once_with(None)

    def test_set_max_size_with_values(self) -> None:
        window = MagicMock()
        _call_size_position_method(window, "set_max_size", {"width": 2000, "height": 2000})
        called = window.set_max_size.call_args[0][0]
        assert called._0 == (2000, 2000)

    def test_set_max_size_none(self) -> None:
        window = MagicMock()
        _call_size_position_method(window, "set_max_size", {})
        window.set_max_size.assert_called_once_with(None)

    def test_set_size_constraints_min_only(self) -> None:
        window = MagicMock()
        _call_size_position_method(
            window,
            "set_size_constraints",
            {"min_size": {"width": 200, "height": 100}},
        )
        window.set_min_size.assert_called_once()
        window.set_max_size.assert_not_called()

    def test_set_size_constraints_max_only(self) -> None:
        window = MagicMock()
        _call_size_position_method(
            window,
            "set_size_constraints",
            {"max_size": {"width": 2000, "height": 1500}},
        )
        window.set_max_size.assert_called_once()
        window.set_min_size.assert_not_called()

    def test_set_size_constraints_both(self) -> None:
        window = MagicMock()
        _call_size_position_method(
            window,
            "set_size_constraints",
            {
                "min_size": {"width": 200, "height": 100},
                "max_size": {"width": 2000, "height": 1500},
            },
        )
        window.set_min_size.assert_called_once()
        window.set_max_size.assert_called_once()

    def test_set_position(self) -> None:
        window = MagicMock()
        _call_size_position_method(window, "set_position", {"x": 100, "y": 200})
        called = window.set_position.call_args[0][0]
        assert called._0 == (100, 200)

    def test_set_position_default(self) -> None:
        window = MagicMock()
        _call_size_position_method(window, "set_position", {})
        called = window.set_position.call_args[0][0]
        assert called._0 == (0, 0)


# =============================================================================
# Appearance helpers
# =============================================================================


class TestAppearanceDispatch:
    """Tests for appearance method handlers."""

    def test_set_background_color_dict(self) -> None:
        """RGBA dict is unpacked correctly."""
        window = MagicMock()
        _set_background_color(window, {"color": {"r": 10, "g": 20, "b": 30, "a": 200}})
        window.set_background_color.assert_called_once_with((10, 20, 30, 200))

    def test_set_background_color_list(self) -> None:
        """List/tuple is converted to tuple."""
        window = MagicMock()
        _set_background_color(window, {"color": [255, 100, 50, 255]})
        window.set_background_color.assert_called_once_with((255, 100, 50, 255))

    def test_set_background_color_unknown_type(self) -> None:
        """Unknown color type defaults to (0,0,0,255)."""
        window = MagicMock()
        _set_background_color(window, {"color": "not-a-color"})
        window.set_background_color.assert_called_once_with((0, 0, 0, 255))

    def test_set_background_color_no_color_key(self) -> None:
        """Falls back to args dict (which is also a dict)."""
        window = MagicMock()
        _set_background_color(window, {"r": 1, "g": 2, "b": 3, "a": 4})
        window.set_background_color.assert_called_once_with((1, 2, 3, 4))

    def test_set_theme_none(self) -> None:
        """No theme key calls set_theme(None)."""
        window = MagicMock()
        _set_theme(window, {})
        window.set_theme.assert_called_once_with(None)

    def test_set_theme_string(self) -> None:
        """String theme is mapped via Theme[...]."""
        fake_theme = MagicMock()
        fake_theme.__getitem__ = MagicMock(return_value="Light_Theme")
        with patch.dict("sys.modules", {"pytauri": MagicMock(Theme=fake_theme)}):
            window = MagicMock()
            _set_theme(window, {"theme": "light"})
            window.set_theme.assert_called_once_with("Light_Theme")

    def test_set_theme_object(self) -> None:
        """Non-string theme passes through unchanged."""
        with patch.dict("sys.modules", {"pytauri": MagicMock()}):
            window = MagicMock()
            obj = object()
            _set_theme(window, {"theme": obj})
            window.set_theme.assert_called_once_with(obj)

    def test_set_title_bar_style_no_attr(self) -> None:
        """If window lacks set_title_bar_style, no-op."""

        class NoTBS:
            pass

        # Should not raise
        _set_title_bar_style(NoTBS(), {"style": "Visible"})

    def test_set_title_bar_style_string(self) -> None:
        """String style is mapped via TitleBarStyle.<name>."""
        window = MagicMock()
        fake_tbs = MagicMock()
        fake_tbs.Visible = "VisibleEnum"
        fake_window_mod = MagicMock(TitleBarStyle=fake_tbs)
        with patch.dict("sys.modules", {"pytauri.window": fake_window_mod}):
            _set_title_bar_style(window, {"style": "Visible"})
        window.set_title_bar_style.assert_called_once_with("VisibleEnum")

    def test_set_title_bar_style_object(self) -> None:
        """Non-string style passes through."""
        window = MagicMock()
        with patch.dict("sys.modules", {"pytauri.window": MagicMock()}):
            obj = object()
            _set_title_bar_style(window, {"style": obj})
        window.set_title_bar_style.assert_called_once_with(obj)

    def test_set_effects_no_attr(self) -> None:
        """If window lacks set_effects, no-op."""

        class NoFx:
            pass

        _set_effects(NoFx(), {"effects": {"effects": [], "state": "Active"}})

    def test_set_effects_no_data(self) -> None:
        """Empty effects_data is no-op."""
        window = MagicMock()
        _set_effects(window, {})
        window.set_effects.assert_not_called()

    def test_set_effects_with_strings(self) -> None:
        """String effects/state mapped via enums."""
        window = MagicMock()

        fake_effect = MagicMock()
        fake_effect.MICA = "mica_val"
        fake_state = MagicMock()
        fake_state.ACTIVE = "active_val"
        fake_effects_class = MagicMock()
        fake_window_mod = MagicMock(
            Effect=fake_effect, EffectState=fake_state, Effects=fake_effects_class
        )
        with patch.dict("sys.modules", {"pytauri.window": fake_window_mod}):
            _set_effects(
                window,
                {
                    "effects": {
                        "effects": ["MICA"],
                        "state": "ACTIVE",
                        "radius": 8.0,
                        "color": [0, 0, 0, 255],
                    }
                },
            )
        window.set_effects.assert_called_once()

    def test_set_effects_with_objects(self) -> None:
        """Non-string effects/state passes through."""
        window = MagicMock()
        fake_window_mod = MagicMock()
        with patch.dict("sys.modules", {"pytauri.window": fake_window_mod}):
            _set_effects(
                window,
                {
                    "effects": {
                        "effects": [object()],
                        "state": object(),
                    }
                },
            )
        window.set_effects.assert_called_once()

    def test_set_icon_with_data(self) -> None:
        """Base64 icon bytes are decoded and passed."""
        import base64

        window = MagicMock()
        raw = b"\x00\x01\x02"
        icon_b64 = base64.b64encode(raw).decode()
        _set_icon(window, {"icon": icon_b64})
        window.set_icon.assert_called_once_with(raw)

    def test_set_icon_no_data_with_attr(self) -> None:
        """No icon and window has set_icon attribute -> calls with None."""
        window = MagicMock()
        _set_icon(window, {})
        window.set_icon.assert_called_once_with(None)

    def test_set_icon_no_data_no_attr(self) -> None:
        """No icon and window lacks set_icon attribute -> no-op."""

        class NoIcon:
            pass

        _set_icon(NoIcon(), {})

    def test_set_icon_with_data_no_attr(self) -> None:
        """Icon data with no set_icon attribute is no-op."""
        import base64

        class NoIcon:
            pass

        b = base64.b64encode(b"x").decode()
        _set_icon(NoIcon(), {"icon": b})

    def test_set_badge_count_with_attr(self) -> None:
        window = MagicMock()
        _set_badge_count(window, {"count": 5})
        window.set_badge_count.assert_called_once_with(5)

    def test_set_badge_count_no_attr(self) -> None:
        class NoBadge:
            pass

        _set_badge_count(NoBadge(), {"count": 5})

    def test_set_overlay_icon_with_data(self) -> None:
        import base64

        window = MagicMock()
        raw = b"\x10\x20"
        icon_b64 = base64.b64encode(raw).decode()
        _set_overlay_icon(window, {"icon": icon_b64})
        window.set_overlay_icon.assert_called_once_with(raw)

    def test_set_overlay_icon_no_data_with_attr(self) -> None:
        window = MagicMock()
        _set_overlay_icon(window, {})
        window.set_overlay_icon.assert_called_once_with(None)

    def test_set_overlay_icon_no_attr_no_data(self) -> None:
        class NoOverlay:
            pass

        _set_overlay_icon(NoOverlay(), {})

    def test_set_overlay_icon_with_data_no_attr(self) -> None:
        """Icon data with no set_overlay_icon attribute is no-op."""
        import base64

        class NoOverlay:
            pass

        b = base64.b64encode(b"x").decode()
        _set_overlay_icon(NoOverlay(), {"icon": b})

    def test_appearance_dispatch_unknown_method(self) -> None:
        """Unknown appearance method is a no-op."""
        window = MagicMock()
        _call_appearance_method(window, "set_unknown", {})

    def test_set_content_protected_via_dispatch(self) -> None:
        """set_content_protected dispatches correctly."""
        window = MagicMock()
        _call_appearance_method(window, "set_content_protected", {"protected": True})
        window.set_content_protected.assert_called_once_with(True)

    def test_set_shadow_via_dispatch(self) -> None:
        window = MagicMock()
        _call_appearance_method(window, "set_shadow", {"shadow": False})
        window.set_shadow.assert_called_once_with(False)


# =============================================================================
# Cursor helpers
# =============================================================================


class TestCursorDispatch:
    """Tests for cursor method handlers."""

    def test_set_cursor_icon_string(self) -> None:
        """String icon mapped via CursorIcon enum."""
        window = MagicMock()
        fake_cursor = MagicMock()
        fake_cursor.Hand = "hand_value"
        with patch.dict("sys.modules", {"pytauri": MagicMock(CursorIcon=fake_cursor)}):
            _call_cursor_method(window, "set_cursor_icon", {"icon": "Hand"})
        window.set_cursor_icon.assert_called_once_with("hand_value")

    def test_set_cursor_icon_object(self) -> None:
        """Non-string icon passes through."""
        window = MagicMock()
        with patch.dict("sys.modules", {"pytauri": MagicMock()}):
            obj = object()
            _call_cursor_method(window, "set_cursor_icon", {"icon": obj})
        window.set_cursor_icon.assert_called_once_with(obj)

    def test_set_cursor_icon_no_attr(self) -> None:
        """If window lacks set_cursor_icon, no-op."""

        class NoCursor:
            pass

        _call_cursor_method(NoCursor(), "set_cursor_icon", {"icon": "Hand"})

    def test_set_cursor_position(self) -> None:
        window = MagicMock()
        _call_cursor_method(window, "set_cursor_position", {"x": 10, "y": 20})
        window.set_cursor_position.assert_called_once_with((10.0, 20.0))

    def test_set_cursor_position_default(self) -> None:
        window = MagicMock()
        _call_cursor_method(window, "set_cursor_position", {})
        window.set_cursor_position.assert_called_once_with((0.0, 0.0))

    def test_set_cursor_position_no_attr(self) -> None:
        class NoCP:
            pass

        _call_cursor_method(NoCP(), "set_cursor_position", {"x": 1, "y": 2})

    def test_set_cursor_visible(self) -> None:
        window = MagicMock()
        _call_cursor_method(window, "set_cursor_visible", {"visible": False})
        window.set_cursor_visible.assert_called_once_with(False)

    def test_set_cursor_visible_no_attr(self) -> None:
        class NoCV:
            pass

        _call_cursor_method(NoCV(), "set_cursor_visible", {"visible": True})

    def test_set_cursor_grab(self) -> None:
        window = MagicMock()
        _call_cursor_method(window, "set_cursor_grab", {"grab": True})
        window.set_cursor_grab.assert_called_once_with(True)

    def test_set_cursor_grab_no_attr(self) -> None:
        class NoCG:
            pass

        _call_cursor_method(NoCG(), "set_cursor_grab", {"grab": False})


# =============================================================================
# Behavior helpers
# =============================================================================


class TestBehaviorDispatch:
    """Tests for behavior methods."""

    def test_set_ignore_cursor_events(self) -> None:
        window = MagicMock()
        _call_behavior_method(window, "set_ignore_cursor_events", {"ignore": True})
        window.set_ignore_cursor_events.assert_called_once_with(True)

    def test_set_ignore_cursor_events_no_attr(self) -> None:
        class NoIgnore:
            pass

        _call_behavior_method(NoIgnore(), "set_ignore_cursor_events", {"ignore": True})

    def test_set_progress_bar_no_attr(self) -> None:
        """If window lacks set_progress_bar, no-op."""

        class NoPB:
            pass

        _call_behavior_method(NoPB(), "set_progress_bar", {"state": {"status": "Normal"}})

    def test_set_progress_bar_no_state(self) -> None:
        """Empty state dict is no-op."""
        window = MagicMock()
        _call_behavior_method(window, "set_progress_bar", {})
        window.set_progress_bar.assert_not_called()

    def test_set_progress_bar_with_string_status(self) -> None:
        """String status mapped via ProgressBarStatus."""
        window = MagicMock()

        fake_status = MagicMock()
        fake_status.Normal = "normal_val"
        fake_state_class = MagicMock()
        fake_window_mod = MagicMock(
            ProgressBarStatus=fake_status, ProgressBarState=fake_state_class
        )
        with patch.dict("sys.modules", {"pytauri.window": fake_window_mod}):
            _call_behavior_method(
                window,
                "set_progress_bar",
                {"state": {"status": "Normal", "progress": 50}},
            )
        window.set_progress_bar.assert_called_once()

    def test_set_progress_bar_with_object_status(self) -> None:
        """Non-string status passes through."""
        window = MagicMock()
        fake_state_class = MagicMock()
        fake_window_mod = MagicMock(ProgressBarState=fake_state_class)
        with patch.dict("sys.modules", {"pytauri.window": fake_window_mod}):
            _call_behavior_method(
                window,
                "set_progress_bar",
                {"state": {"status": object(), "progress": 50}},
            )
        window.set_progress_bar.assert_called_once()

    def test_set_visible_on_all_workspaces(self) -> None:
        window = MagicMock()
        _call_behavior_method(window, "set_visible_on_all_workspaces", {"visible": True})
        window.set_visible_on_all_workspaces.assert_called_once_with(True)

    def test_set_visible_on_all_workspaces_no_attr(self) -> None:
        class NoVOAW:
            pass

        _call_behavior_method(NoVOAW(), "set_visible_on_all_workspaces", {"visible": True})

    def test_set_traffic_light_position(self) -> None:
        window = MagicMock()
        _call_behavior_method(window, "set_traffic_light_position", {"x": 5, "y": 10})
        window.set_traffic_light_position.assert_called_once_with((5.0, 10.0))

    def test_set_traffic_light_position_no_attr(self) -> None:
        class NoTLP:
            pass

        _call_behavior_method(NoTLP(), "set_traffic_light_position", {"x": 1, "y": 2})

    def test_set_traffic_light_position_default(self) -> None:
        window = MagicMock()
        _call_behavior_method(window, "set_traffic_light_position", {})
        window.set_traffic_light_position.assert_called_once_with((0.0, 0.0))


# =============================================================================
# Webview missing branches
# =============================================================================


class TestWebviewDispatchEdgeCases:
    """Webview branches not exercised by the StubWindow integration tests."""

    def test_navigate_no_attr(self) -> None:
        """If window has no .navigate, no-op."""

        class NoNav:
            pass

        _call_webview_method(NoNav(), "navigate", {"url": "about:blank"})

    def test_open_devtools_no_attr(self) -> None:
        class NoDT:
            pass

        _call_webview_method(NoDT(), "open_devtools", {})

    def test_close_devtools_no_attr(self) -> None:
        class NoDT:
            pass

        _call_webview_method(NoDT(), "close_devtools", {})

    def test_is_devtools_open_returns_value(self) -> None:
        window = MagicMock()
        window.is_devtools_open.return_value = True
        assert call_window_method(window, "is_devtools_open", {}) is True

    def test_is_devtools_open_no_attr(self) -> None:
        """Without attr returns False."""

        class NoDT:
            pass

        assert call_window_method(NoDT(), "is_devtools_open", {}) is False

    def test_set_zoom(self) -> None:
        window = MagicMock()
        call_window_method(window, "set_zoom", {"scale": 1.5})
        window.set_zoom.assert_called_once_with(1.5)

    def test_set_zoom_no_attr(self) -> None:
        class NoZoom:
            pass

        call_window_method(NoZoom(), "set_zoom", {"scale": 2.0})

    def test_zoom_returns_value(self) -> None:
        window = MagicMock()
        window.zoom.return_value = 2.0
        assert call_window_method(window, "zoom", {}) == 2.0

    def test_zoom_no_attr(self) -> None:
        class NoZoom:
            pass

        assert call_window_method(NoZoom(), "zoom", {}) == 1.0

    def test_clear_browsing_data(self) -> None:
        window = MagicMock()
        call_window_method(window, "clear_all_browsing_data", {})
        window.clear_all_browsing_data.assert_called_once()

    def test_clear_browsing_data_no_attr(self) -> None:
        class No:
            pass

        call_window_method(No(), "clear_all_browsing_data", {})

    def test_reload_no_attr(self) -> None:
        class No:
            pass

        call_window_method(No(), "reload", {})

    def test_print(self) -> None:
        window = MagicMock()
        call_window_method(window, "print", {})
        window.print.assert_called_once()

    def test_print_no_attr(self) -> None:
        class No:
            pass

        call_window_method(No(), "print", {})

    def test_webview_dispatch_unknown(self) -> None:
        """Unknown method returns None."""
        window = MagicMock()
        assert _call_webview_method(window, "unknown_webview", {}) is None


# =============================================================================
# Cookie helpers
# =============================================================================


class TestCookieDispatch:
    """Tests for cookie helper methods."""

    def test_serialize_cookie_none(self) -> None:
        assert _serialize_cookie(None) == {}

    def test_serialize_cookie_full(self) -> None:
        """Full cookie attributes serialized correctly."""

        class C:
            name = "session"
            value = "abc"
            domain = ".example.com"
            path = "/"
            expires = 1234567
            http_only = True
            secure = True
            same_site = "Strict"

        d = _serialize_cookie(C())
        assert d["name"] == "session"
        assert d["value"] == "abc"
        assert d["domain"] == ".example.com"
        assert d["path"] == "/"
        assert d["http_only"] is True
        assert d["secure"] is True
        assert d["same_site"] == "Strict"

    def test_serialize_cookie_partial(self) -> None:
        """Missing attrs use defaults."""

        class C:
            name = "n"
            value = "v"

        d = _serialize_cookie(C())
        assert d["name"] == "n"
        assert d["value"] == "v"
        assert d["domain"] is None
        assert d["http_only"] is False

    def test_cookie_set(self) -> None:
        window = MagicMock()
        _call_cookie_method(window, "set_cookie", {"cookie": {"name": "n"}})
        window.set_cookie.assert_called_once_with({"name": "n"})

    def test_cookie_set_no_attr(self) -> None:
        class No:
            pass

        assert _call_cookie_method(No(), "set_cookie", {}) is None

    def test_cookie_get_with_cookies(self) -> None:
        """get_cookies returns serialized cookies."""
        window = MagicMock()

        class C:
            name = "n"
            value = "v"

        window.get_cookies.return_value = [C()]
        result = _call_cookie_method(window, "get_cookies", {})
        assert isinstance(result, list)
        assert result[0]["name"] == "n"

    def test_cookie_get_empty(self) -> None:
        """get_cookies returns empty list for None."""
        window = MagicMock()
        window.get_cookies.return_value = None
        assert _call_cookie_method(window, "get_cookies", {}) == []

    def test_cookie_get_no_attr(self) -> None:
        """get_cookies on a window without get_cookies returns []."""

        class No:
            pass

        assert _call_cookie_method(No(), "get_cookies", {}) == []

    def test_cookie_remove(self) -> None:
        window = MagicMock()
        _call_cookie_method(window, "remove_cookie", {"name": "n", "url": "https://x.com"})
        window.remove_cookie.assert_called_once_with("n", "https://x.com")

    def test_cookie_remove_no_attr(self) -> None:
        class No:
            pass

        _call_cookie_method(No(), "remove_cookie", {"name": "n"})

    def test_cookie_remove_all(self) -> None:
        window = MagicMock()
        _call_cookie_method(window, "remove_all_cookies", {})
        window.remove_all_cookies.assert_called_once()

    def test_cookie_remove_all_no_attr(self) -> None:
        class No:
            pass

        _call_cookie_method(No(), "remove_all_cookies", {})

    def test_cookie_dispatch_unknown(self) -> None:
        """Unknown cookie method returns None."""
        window = MagicMock()
        assert _call_cookie_method(window, "unknown_cookie_method", {}) is None
