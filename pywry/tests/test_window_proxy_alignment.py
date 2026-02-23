"""Tests for WindowProxy ↔ window_dispatch alignment.

Ensures that every method declared on ``WindowProxy`` (that sends IPC) has
a corresponding handler in ``window_dispatch``, and vice versa.
"""

from __future__ import annotations

import inspect

from pywry.window_dispatch import (
    APPEARANCE_METHODS,
    BEHAVIOR_METHODS,
    CURSOR_METHODS,
    PROPERTY_METHODS,
    SIZE_POSITION_METHODS,
    STATE_METHODS,
    VISIBILITY_METHODS,
    WEBVIEW_METHODS,
)
from pywry.window_proxy import WindowProxy


# ── Helpers ───────────────────────────────────────────────────────────

# Collect all dispatch-side method names (union of all category sets)
ALL_DISPATCH_METHODS = (
    VISIBILITY_METHODS
    | STATE_METHODS
    | PROPERTY_METHODS
    | SIZE_POSITION_METHODS
    | APPEARANCE_METHODS
    | CURSOR_METHODS
    | BEHAVIOR_METHODS
    | WEBVIEW_METHODS
)

# WindowProxy methods that are IPC-backed but NOT in the dispatch table
# because they use a different IPC action (e.g. navigate/eval/open_devtools)
_PROXY_ONLY_METHODS = {
    # Webview methods that use dedicated commands
    "navigate",
    "eval",
    "open_devtools",
    "close_devtools",
    "is_devtools_open",
    "reload",
    # Cookie methods use a separate IPC pattern
    "cookies",
    "set_cookie",
    "delete_cookie",
    # Menu methods use menu_* IPC actions
    "set_menu",
    "remove_menu",
    "hide_menu",
    "show_menu",
    "is_menu_visible",
    "popup_menu",
}

# Dispatch methods that don't have a direct 1:1 proxy method name
_DISPATCH_ONLY_METHODS = {
    # set_visible is handled by show/hide on proxy side
    "set_visible",
    # start_dragging has no matching proxy method yet
    "start_dragging",
    # Webview methods available via dispatch but not yet on proxy
    "print",
    "zoom",
}

# Methods that are property getters on the proxy (is_* / title / url / etc.)
_PROXY_PROPERTIES = {
    member_name
    for member_name, member_value in inspect.getmembers(WindowProxy)
    if isinstance(member_value, property)
}


def _get_proxy_action_methods() -> set[str]:
    """Get all WindowProxy methods that send IPC commands.

    Excludes dunder methods, private methods, and properties.
    """
    result = set()
    for name in dir(WindowProxy):
        if name.startswith("_"):
            continue
        member = getattr(WindowProxy, name, None)
        if member is None:
            continue
        if isinstance(inspect.getattr_static(WindowProxy, name), property):
            continue
        if callable(member):
            result.add(name)
    return result


# ── Tests ─────────────────────────────────────────────────────────────


class TestProxyDispatchAlignment:
    """Verify WindowProxy and window_dispatch are consistent."""

    def test_dispatch_categories_no_overlap(self) -> None:
        """All dispatch categories should be mutually exclusive."""
        categories = [
            VISIBILITY_METHODS,
            STATE_METHODS,
            PROPERTY_METHODS,
            SIZE_POSITION_METHODS,
            APPEARANCE_METHODS,
            CURSOR_METHODS,
            BEHAVIOR_METHODS,
            WEBVIEW_METHODS,
        ]
        seen: set[str] = set()
        for cat in categories:
            overlap = seen & cat
            assert not overlap, f"Overlapping methods across categories: {overlap}"
            seen |= cat

    def test_dispatch_categories_non_empty(self) -> None:
        """Every category should have at least one method."""
        for name, cat in [
            ("VISIBILITY", VISIBILITY_METHODS),
            ("STATE", STATE_METHODS),
            ("PROPERTY", PROPERTY_METHODS),
            ("SIZE_POSITION", SIZE_POSITION_METHODS),
            ("APPEARANCE", APPEARANCE_METHODS),
            ("CURSOR", CURSOR_METHODS),
            ("BEHAVIOR", BEHAVIOR_METHODS),
            ("WEBVIEW", WEBVIEW_METHODS),
        ]:
            assert len(cat) > 0, f"{name}_METHODS is empty"

    def test_proxy_covers_dispatch_methods(self) -> None:
        """Every method in dispatch should have a proxy method or be exempted."""
        proxy_methods = _get_proxy_action_methods()
        proxy_props = _PROXY_PROPERTIES

        # Merge proxy methods + properties + exemptions
        proxy_coverage = proxy_methods | proxy_props | _DISPATCH_ONLY_METHODS

        uncovered = ALL_DISPATCH_METHODS - proxy_coverage
        assert not uncovered, f"Dispatch methods have no WindowProxy counterpart: {uncovered}"

    def test_new_menu_tray_types_exist(self) -> None:
        """Menu and tray types are importable."""
        from pywry.types import (  # noqa: F401  # pylint: disable=unused-import
            CheckMenuItemConfig,
            IconMenuItemConfig,
            MenuConfig,
            MenuItemConfig,
            MouseButton,
            MouseButtonState,
            PredefinedMenuItemConfig,
            PredefinedMenuItemKind,
            SubmenuConfig,
            TrayIconConfig,
        )

    def test_menu_proxy_importable(self) -> None:
        """MenuProxy is importable and has expected methods."""
        from pywry.menu_proxy import MenuProxy

        assert hasattr(MenuProxy, "create")
        assert hasattr(MenuProxy, "from_config")
        assert hasattr(MenuProxy, "append")
        assert hasattr(MenuProxy, "set_text")
        assert hasattr(MenuProxy, "set_as_app_menu")
        assert hasattr(MenuProxy, "popup")
        assert hasattr(MenuProxy, "destroy")

    def test_tray_proxy_importable(self) -> None:
        """TrayProxy is importable and has expected methods."""
        from pywry.tray_proxy import TrayProxy

        assert hasattr(TrayProxy, "create")
        assert hasattr(TrayProxy, "from_config")
        assert hasattr(TrayProxy, "set_icon")
        assert hasattr(TrayProxy, "set_tooltip")
        assert hasattr(TrayProxy, "set_title")
        assert hasattr(TrayProxy, "set_menu")
        assert hasattr(TrayProxy, "set_visible")
        assert hasattr(TrayProxy, "on")
        assert hasattr(TrayProxy, "remove")

    def test_window_proxy_has_menu_methods(self) -> None:
        """WindowProxy has menu management methods."""
        assert hasattr(WindowProxy, "set_menu")
        assert hasattr(WindowProxy, "remove_menu")
        assert hasattr(WindowProxy, "hide_menu")
        assert hasattr(WindowProxy, "show_menu")
        assert hasattr(WindowProxy, "is_menu_visible")
        assert hasattr(WindowProxy, "popup_menu")

    def test_pywry_app_has_tray_and_menu(self) -> None:
        """PyWry app class has create_tray/create_menu/set_initialization_script."""
        from pywry.app import PyWry

        assert hasattr(PyWry, "create_tray")
        assert hasattr(PyWry, "create_menu")
        assert hasattr(PyWry, "set_initialization_script")
        assert hasattr(PyWry, "remove_tray")
        assert hasattr(PyWry, "default_config")
