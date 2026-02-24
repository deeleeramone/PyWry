"""PyInstaller hook registration for pywry.

PyInstaller discovers this via the ``pyinstaller40`` entry point in
``pyproject.toml``.  When a developer runs ``pyinstaller myapp.py``,
PyInstaller automatically applies the hook in ``hook-pywry.py`` without
any manual ``.spec`` file configuration.
"""

from __future__ import annotations

from pathlib import Path


def get_hook_dirs() -> list[str]:
    """Return the directory containing PyInstaller hooks for pywry."""
    return [str(Path(__file__).parent)]
