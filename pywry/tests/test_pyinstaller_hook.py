"""Tests for the pyinstaller hook helpers."""

from __future__ import annotations

from pathlib import Path

import pytest


pytest.importorskip("PyInstaller")


from pywry._pyinstaller_hook import get_hook_dirs


class TestGetHookDirs:
    def test_returns_one_dir(self):
        dirs = get_hook_dirs()
        assert len(dirs) == 1

    def test_returned_path_is_a_directory(self):
        dirs = get_hook_dirs()
        path = Path(dirs[0])
        assert path.is_dir()

    def test_hook_file_present(self):
        dirs = get_hook_dirs()
        path = Path(dirs[0]) / "hook-pywry.py"
        assert path.is_file()


def test_hook_module_executes_with_collected_state():
    """Run hook-pywry.py top-to-bottom and verify the resulting attributes.

    Use importlib so coverage tracks the executed lines under the
    package-relative module name.
    """
    import importlib.util

    hook_path = Path(get_hook_dirs()[0]) / "hook-pywry.py"
    spec = importlib.util.spec_from_file_location(
        "pywry._pyinstaller_hook.hook-pywry",
        str(hook_path),
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]

    assert isinstance(module.datas, list)
    assert "pywry.__main__" in module.hiddenimports
    assert "pywry._freeze" in module.hiddenimports
    assert "pywry.commands" in module.hiddenimports
    assert isinstance(module.binaries, list)
