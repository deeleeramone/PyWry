"""Frozen-app (distributable executable) support for PyWry.

When a developer builds their PyWry application as a standalone executable
using PyInstaller, Nuitka, or cx_Freeze, the Tauri subprocess can no longer
be launched with ``python -m pywry`` because ``sys.executable`` points to
the developer's bundled ``.exe``, not a Python interpreter.

This module solves that by:

1. Detecting frozen environments (``sys.frozen`` is set by all major freezers).
2. Providing ``get_subprocess_command()`` so ``runtime.start()`` spawns the
   frozen executable *itself* with ``PYWRY_IS_SUBPROCESS=1`` in the env.
3. Providing ``freeze_support()`` which, when called at import time from
   ``pywry/__init__.py``, intercepts the child process and routes it directly
   to the Tauri event loop — preventing the developer's application code
   from executing a second time in the subprocess.

Developers do **not** need to call anything from this module directly.
The interception happens automatically on ``import pywry``.  For maximum
safety (ensuring no developer code runs before the interception), they can
optionally call ``freeze_support()`` at the very top of their entry point::

    if __name__ == "__main__":
        from pywry import freeze_support

        freeze_support()

        # ... rest of application ...
"""

from __future__ import annotations

import os
import sys


def is_frozen() -> bool:
    """Return ``True`` if running inside a frozen executable.

    PyInstaller, Nuitka (standalone), and cx_Freeze all set
    ``sys.frozen = True``.
    """
    return bool(getattr(sys, "frozen", False))


def get_subprocess_command() -> list[str]:
    """Return the command to spawn the PyWry Tauri subprocess.

    Normal install::

        [sys.executable, "-u", "-m", "pywry"]

    Frozen executable::

        [sys.executable]

    In frozen mode the ``PYWRY_IS_SUBPROCESS=1`` environment variable
    (set by ``runtime.start()``) tells the child to enter the Tauri
    event loop instead of running the developer's application.  The
    ``-u`` flag is replaced by ``PYTHONUNBUFFERED=1`` in the env.
    """
    if is_frozen():
        return [sys.executable]
    return [sys.executable, "-u", "-m", "pywry"]


def freeze_support() -> None:
    """Handle subprocess re-entry in frozen executables.

    Called automatically at the top of ``pywry/__init__.py``.  When all
    of the following are true the function enters the Tauri event loop
    and calls ``sys.exit()`` — the developer's application code never
    executes in the child process:

    1. ``sys.frozen`` is truthy  (we are inside a frozen executable).
    2. ``PYWRY_IS_SUBPROCESS`` environment variable is ``"1"``
       (we were spawned by ``runtime.start()`` as the Tauri subprocess).

    In every other situation (normal Python, frozen parent process, etc.)
    this function is a no-op and returns immediately.
    """
    if not is_frozen():
        return

    if os.environ.get("PYWRY_IS_SUBPROCESS") != "1":
        return

    # We are the frozen child process.  Import the Tauri entry point
    # and run it, then hard-exit so the developer's code never executes.
    from pywry.__main__ import main

    sys.exit(main())
