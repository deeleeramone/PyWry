# pylint: disable=invalid-name
"""PyInstaller hook for pywry.

Automatically applied when ``pywry`` is used as a dependency in a
PyInstaller build.  Handles:

- **Data files** — frontend assets (HTML, JS, CSS, gzipped libraries,
  icons), Tauri configuration (``Tauri.toml``), capability manifests,
  and MCP skill markdown files.
- **Hidden imports** — dynamically imported modules that PyInstaller's
  static analysis cannot trace (subprocess entry point, pytauri plugins,
  vendored native bindings, IPC command handlers).
- **Native binaries** — the vendored ``pytauri_wheel`` shared library
  (``.pyd`` on Windows, ``.so`` on Linux, ``.dylib`` on macOS).
"""

from __future__ import annotations

from PyInstaller.utils.hooks import (  # type: ignore[import-untyped]  # pylint: disable=import-error
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)


# ── Data files ────────────────────────────────────────────────────────
# collect_data_files finds every non-.py file inside the package tree.
# This captures frontend/, Tauri.toml, capabilities/*.toml, mcp/skills/*.md,
# frontend/assets/*.gz, icons, CSS, JS — everything context_factory() and
# the asset loaders need at runtime.
datas = collect_data_files("pywry")

# ── Hidden imports ────────────────────────────────────────────────────
# These modules are imported dynamically (inside functions, try/except
# blocks, importlib.import_module, or string-based references) and are
# invisible to PyInstaller's static import graph.
hiddenimports: list[str] = [
    # Subprocess entry point — spawned at runtime, never imported statically
    "pywry.__main__",
    # Freeze detection — imported inside guards
    "pywry._freeze",
    # IPC command handlers — registered at runtime in __main__.main()
    "pywry.commands",
    "pywry.commands.window_commands",
    "pywry.window_dispatch",
    # Vendored Tauri runtime — imported inside try/except in __main__
    "pywry._vendor.pytauri_wheel",
    "pywry._vendor.pytauri_wheel.lib",
    # Non-vendored fallback (editable / dev installs)
    "pytauri_wheel",
    "pytauri_wheel.lib",
    # pytauri and all its plugins — loaded dynamically by _load_plugins()
    *collect_submodules("pytauri"),
    *collect_submodules("pytauri_plugins"),
    # anyio backend — selected by name string at runtime
    "anyio._backends._asyncio",
    # setproctitle — optional, guarded import
    "setproctitle",
]

# ── Native binaries ───────────────────────────────────────────────────
# collect_dynamic_libs finds .pyd / .so / .dylib files and adds them to
# the binaries list so PyInstaller links them correctly (rather than
# treating them as opaque data files).
# Try vendored location first; fall back to system-installed package.
binaries = collect_dynamic_libs("pywry._vendor.pytauri_wheel")
if not binaries:
    binaries = collect_dynamic_libs("pytauri_wheel")
