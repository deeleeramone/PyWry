"""JavaScript bridge scripts for PyWry.

All JavaScript is loaded from dedicated files in ``frontend/src/``.
No inline JS is defined in this module.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from .assets import get_toast_notifications_js


_SRC_DIR = Path(__file__).parent / "frontend" / "src"


def _load_js(filename: str) -> str:
    """Load a JavaScript file from the frontend/src/ directory.

    Parameters
    ----------
    filename : str
        Name of the JS file to load.

    Returns
    -------
    str
        File contents, or empty string if not found.
    """
    path = _SRC_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


@lru_cache(maxsize=1)
def _get_tooltip_manager_js() -> str:
    """Load the tooltip manager JavaScript from the single source file."""
    return _load_js("tooltip-manager.js")


@lru_cache(maxsize=1)
def _get_bridge_js() -> str:
    """Load the PyWry bridge (emit, on, result, etc.)."""
    return _load_js("bridge.js")


@lru_cache(maxsize=1)
def _get_system_events_js() -> str:
    """Load system event handlers (CSS injection, downloads, etc.)."""
    return _load_js("system-events.js")


@lru_cache(maxsize=1)
def _get_theme_manager_js() -> str:
    """Load the theme manager (dark/light switching, Plotly/AG Grid sync)."""
    return _load_js("theme-manager.js")


@lru_cache(maxsize=1)
def _get_event_bridge_js() -> str:
    """Load the Tauri event bridge."""
    return _load_js("event-bridge.js")


@lru_cache(maxsize=1)
def _get_toolbar_bridge_js() -> str:
    """Load the toolbar state management bridge."""
    return _load_js("toolbar-bridge.js")


@lru_cache(maxsize=1)
def _get_cleanup_js() -> str:
    """Load cleanup handlers (secret clearing, resource release)."""
    return _load_js("cleanup.js")


@lru_cache(maxsize=1)
def _get_hot_reload_js() -> str:
    """Load the hot reload bridge (scroll preservation)."""
    return _load_js("hot-reload.js")


def build_init_script(
    window_label: str,
    enable_hot_reload: bool = False,
) -> str:
    """Build the core initialization script for a window.

    Loads all bridge scripts from ``frontend/src/`` and concatenates
    them with the window label assignment.

    Parameters
    ----------
    window_label : str
        The label for this window.
    enable_hot_reload : bool, optional
        Whether to include hot reload functionality.

    Returns
    -------
    str
        The combined JavaScript initialization script.
    """
    scripts = [
        f"window.__PYWRY_LABEL__ = '{window_label}';",
        _get_bridge_js(),
        _get_system_events_js(),
        get_toast_notifications_js(),
        _get_tooltip_manager_js(),
        _get_theme_manager_js(),
        _get_event_bridge_js(),
        _get_toolbar_bridge_js(),
        _get_cleanup_js(),
    ]

    if enable_hot_reload:
        scripts.append(_get_hot_reload_js())

    return "\n".join(scripts)
