# pylint: disable=invalid-name
"""PyInstaller hook for pywry.

Automatically applied when ``pywry`` is used as a dependency in a
PyInstaller build.  Handles:

- **Data files** — frontend assets (HTML, JS, CSS, gzipped libraries,
  icons), Tauri configuration (``Tauri.toml``), capability manifests,
  and MCP skill markdown files.
- **Hidden imports** — dynamically imported modules that PyInstaller's
  static analysis cannot trace (subprocess entry point, pytauri plugins,
  vendored native bindings, IPC command handlers, entry-point-loaded
  native extensions).
- **Native binaries** — the vendored ``pytauri_wheel`` shared library
  (``.pyd`` on Windows, ``.so`` on Linux, ``.dylib`` on macOS).
"""

from __future__ import annotations

import contextlib

from PyInstaller.utils.hooks import (  # type: ignore[import-untyped]  # pylint: disable=import-error
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
    copy_metadata,
)


# ── Data files ────────────────────────────────────────────────────────
# collect_data_files finds every non-.py file inside the package tree.
# This captures frontend/, Tauri.toml, capabilities/*.toml, mcp/skills/*.md,
# frontend/assets/*.gz, icons, CSS, JS — everything context_factory() and
# the asset loaders need at runtime.
datas = collect_data_files("pywry")

# Bundle package metadata (.dist-info) so that importlib.metadata.entry_points()
# can discover the pytauri native extension at runtime if needed.
# pytauri's _ext_mod._load_ext_mod() uses entry_points(group="pytauri",
# name="ext_mod") to find pytauri_wheel.ext_mod.  Without the dist-info
# this lookup fails.
# Belt-and-suspenders: _freeze._setup_pytauri_standalone() also bypasses
# entry-point discovery via sys._pytauri_standalone, but keeping metadata
# makes importlib.metadata introspection work in general.
for _pkg in ("pytauri_wheel", "pytauri", "pytauri_plugins"):
    with contextlib.suppress(Exception):
        datas += copy_metadata(_pkg)

# ── Hidden imports ────────────────────────────────────────────────────
# These modules are imported dynamically (inside functions, try/except
# blocks, importlib.import_module, entry-point lookups, or string-based
# references) and are invisible to PyInstaller's static import graph.
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
    # collect_submodules captures __init__, lib, AND the native ext_mod .pyd
    *collect_submodules("pywry._vendor.pytauri_wheel"),
    # Non-vendored fallback (editable / dev installs)
    # collect_submodules captures pytauri_wheel.ext_mod (the native .pyd)
    # which is loaded at runtime via entry_points(group="pytauri")
    *collect_submodules("pytauri_wheel"),
    # pytauri and all its plugins — loaded dynamically by _load_plugins()
    *collect_submodules("pytauri"),
    *collect_submodules("pytauri_plugins"),
    # importlib_metadata — used by pytauri.ffi._ext_mod to discover the
    # native extension via entry_points(); it's a backport package that
    # PyInstaller may not trace from the dynamic lookup code
    "importlib_metadata",
    # anyio backend — selected by name string at runtime
    "anyio._backends._asyncio",
    # setproctitle — optional, guarded import
    "setproctitle",
]

# ── Native binaries ───────────────────────────────────────────────────
# collect_dynamic_libs finds .dll / .so / .dylib files (NOT .pyd extension
# modules — those are handled via hiddenimports above).
# This catches any non-Python shared libraries that pytauri_wheel may
# depend on (e.g., C runtime libraries bundled alongside the extension).
binaries = collect_dynamic_libs("pywry._vendor.pytauri_wheel")
if not binaries:
    binaries = collect_dynamic_libs("pytauri_wheel")
