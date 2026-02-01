"""Global state for MCP server.

This module holds the shared state for the MCP server, including
the PyWry app instance and widget tracking.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from pywry import PyWry

# Global PyWry app instance for MCP server (mutable singleton, not a constant)
_app: PyWry | None = None  # pylint: disable=invalid-name

# Active widgets by ID
_widgets: dict[str, Any] = {}

# Widget configurations for export
_widget_configs: dict[str, dict[str, Any]] = {}


def get_app() -> PyWry:
    """Get or create the global PyWry app instance.

    Adapts to the rendering environment:
    - Desktop (PYWRY_HEADLESS=0 or unset): Native windows via WindowMode.NEW_WINDOW
    - Headless (PYWRY_HEADLESS=1): Inline widgets via WindowMode.BROWSER

    Returns
    -------
    PyWry
        The global PyWry application instance.
    """
    import os

    global _app  # noqa: PLW0603
    if _app is None:
        from pywry import PyWry, WindowMode

        headless = os.environ.get("PYWRY_HEADLESS", "0") == "1"
        mode = WindowMode.BROWSER if headless else WindowMode.NEW_WINDOW
        _app = PyWry(mode=mode)
    return _app


def register_widget(widget_id: str, widget: Any) -> None:
    """Register a widget.

    Parameters
    ----------
    widget_id : str
        Unique identifier for the widget.
    widget : Any
        The widget instance.
    """
    _widgets[widget_id] = widget


def store_widget_config(widget_id: str, config: dict[str, Any]) -> None:
    """Store widget configuration for export.

    Parameters
    ----------
    widget_id : str
        The widget identifier.
    config : dict[str, Any]
        The widget configuration.
    """
    _widget_configs[widget_id] = config


def get_widgets() -> dict[str, Any]:
    """Get all widgets.

    Returns
    -------
    dict[str, Any]
        Dictionary of widget IDs to widget instances.
    """
    return _widgets


def get_widget(widget_id: str) -> Any | None:
    """Get a widget by ID.

    Parameters
    ----------
    widget_id : str
        The widget identifier.

    Returns
    -------
    Any or None
        The widget instance or None if not found.
    """
    return _widgets.get(widget_id)


def get_widget_config(widget_id: str) -> dict[str, Any] | None:
    """Get widget configuration by ID.

    Parameters
    ----------
    widget_id : str
        The widget identifier.

    Returns
    -------
    dict or None
        The widget configuration or None if not found.
    """
    return _widget_configs.get(widget_id)


def list_widget_ids() -> list[str]:
    """List all active widget IDs.

    Returns
    -------
    list of str
        List of widget identifiers.
    """
    return list(_widgets.keys())


def remove_widget(widget_id: str) -> bool:
    """Remove a widget.

    Parameters
    ----------
    widget_id : str
        The widget identifier.

    Returns
    -------
    bool
        True if widget was removed, False if not found.
    """
    if widget_id in _widgets:
        del _widgets[widget_id]
        _widget_configs.pop(widget_id, None)
        return True
    return False
