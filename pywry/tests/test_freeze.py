"""Tests for frozen-app subprocess detection and command routing."""

from __future__ import annotations

import inspect
import sys
import types

from pathlib import Path
from unittest.mock import patch

import pytest

from pywry._freeze import (
    _setup_pytauri_standalone,
    freeze_support,
    get_subprocess_command,
    is_frozen,
)


def _make_fake_main_module(return_code: int = 0) -> types.ModuleType:
    """Create a fake ``pywry.__main__`` module with a mock ``main()``.

    Avoids importing the real ``pywry.__main__`` which reconfigures
    ``sys.stdin``/``sys.stdout``/``sys.stderr`` on Windows and breaks
    pytest's capture system.
    """
    mod = types.ModuleType("pywry.__main__")
    mod.main = lambda: return_code  # type: ignore[attr-defined]
    return mod


# ── is_frozen() ───────────────────────────────────────────────────────


class TestIsFrozen:
    """Tests for is_frozen() detection."""

    def test_false_in_normal_python(self) -> None:
        """Normal interpreter should not be detected as frozen."""
        assert not is_frozen()

    def test_true_when_sys_frozen_set(self) -> None:
        """PyInstaller / Nuitka / cx_Freeze set sys.frozen = True."""
        with patch.object(sys, "frozen", True, create=True):
            assert is_frozen()

    def test_false_when_sys_frozen_false(self) -> None:
        """Explicitly False should not trigger."""
        with patch.object(sys, "frozen", False, create=True):
            assert not is_frozen()


# ── get_subprocess_command() ──────────────────────────────────────────


class TestGetSubprocessCommand:
    """Tests for subprocess command generation."""

    def test_normal_mode_uses_module_flag(self) -> None:
        """Normal Python: [python, -u, -m, pywry]."""
        cmd = get_subprocess_command()
        assert cmd == [sys.executable, "-u", "-m", "pywry"]

    def test_frozen_mode_uses_bare_executable(self) -> None:
        """Frozen: [sys.executable] — no -u, -m, or pywry args."""
        with patch.object(sys, "frozen", True, create=True):
            cmd = get_subprocess_command()
        assert cmd == [sys.executable]

    def test_frozen_command_has_no_python_flags(self) -> None:
        """Frozen executable is not a Python interpreter — no -u or -m."""
        with patch.object(sys, "frozen", True, create=True):
            cmd = get_subprocess_command()
        assert "-u" not in cmd
        assert "-m" not in cmd
        assert "pywry" not in cmd


# ── freeze_support() ─────────────────────────────────────────────────


class TestFreezeSupport:
    """Tests for the freeze_support() interception function."""

    def test_noop_when_not_frozen(self) -> None:
        """Normal Python — should return immediately without side effects."""
        # Must not raise or call sys.exit
        freeze_support()

    def test_noop_when_frozen_but_no_env_var(self) -> None:
        """Frozen parent process — PYWRY_IS_SUBPROCESS not set → no-op."""
        with (
            patch.object(sys, "frozen", True, create=True),
            patch.dict("os.environ", {}, clear=True),
        ):
            freeze_support()  # must not raise or exit

    def test_noop_when_env_var_but_not_frozen(self) -> None:
        """Non-frozen process with env var set — should be ignored."""
        with patch.dict("os.environ", {"PYWRY_IS_SUBPROCESS": "1"}):
            freeze_support()  # must not raise or exit

    def test_exits_when_frozen_with_env_var(self) -> None:
        """Frozen subprocess with PYWRY_IS_SUBPROCESS=1 → calls main() and exits."""
        fake_mod = _make_fake_main_module(return_code=0)
        with (
            patch.object(sys, "frozen", True, create=True),
            patch.dict("os.environ", {"PYWRY_IS_SUBPROCESS": "1"}),
            patch.dict("sys.modules", {"pywry.__main__": fake_mod}),
            pytest.raises(SystemExit) as exc_info,
        ):
            freeze_support()
        assert exc_info.value.code == 0

    def test_exit_propagates_nonzero_return(self) -> None:
        """Non-zero return from main() propagates through sys.exit."""
        fake_mod = _make_fake_main_module(return_code=1)
        with (
            patch.object(sys, "frozen", True, create=True),
            patch.dict("os.environ", {"PYWRY_IS_SUBPROCESS": "1"}),
            patch.dict("sys.modules", {"pywry.__main__": fake_mod}),
            pytest.raises(SystemExit) as exc_info,
        ):
            freeze_support()
        assert exc_info.value.code == 1


# ── runtime.start() integration ──────────────────────────────────────


class TestRuntimeIntegration:
    """Verify that runtime.start() uses get_subprocess_command()."""

    def test_start_uses_get_subprocess_command(self) -> None:
        """runtime.start() must delegate to get_subprocess_command()."""
        from pywry import runtime

        source = inspect.getsource(runtime.start)
        assert "get_subprocess_command" in source

    def test_start_no_longer_hardcodes_python_m_pywry(self) -> None:
        """The old hardcoded [python, -m, pywry] pattern must be gone."""
        from pywry import runtime

        source = inspect.getsource(runtime.start)
        assert '"-m", "pywry"' not in source

    def test_start_sets_pywry_is_subprocess_for_frozen(self) -> None:
        """In frozen mode, PYWRY_IS_SUBPROCESS=1 must be set in env."""
        from pywry import runtime

        source = inspect.getsource(runtime.start)
        assert "PYWRY_IS_SUBPROCESS" in source


# ── pytauri standalone setup ──────────────────────────────────────────


class TestPytauriStandaloneSetup:
    """Verify that _setup_pytauri_standalone bypasses entry-point discovery."""

    def test_registers_ext_mod_in_sys_modules(self) -> None:
        """Must place the native module in sys.modules['__pytauri_ext_mod__']."""
        # Clean up any previous state
        old_standalone = getattr(sys, "_pytauri_standalone", None)
        old_mod = sys.modules.pop("__pytauri_ext_mod__", None)
        try:
            if hasattr(sys, "_pytauri_standalone"):
                del sys._pytauri_standalone
            _setup_pytauri_standalone()
            assert getattr(sys, "_pytauri_standalone", False) is True
            assert "__pytauri_ext_mod__" in sys.modules
        finally:
            # Restore original state
            if old_standalone is not None:
                sys._pytauri_standalone = old_standalone  # type: ignore[attr-defined]
            elif hasattr(sys, "_pytauri_standalone"):
                del sys._pytauri_standalone
            if old_mod is not None:
                sys.modules["__pytauri_ext_mod__"] = old_mod
            else:
                sys.modules.pop("__pytauri_ext_mod__", None)

    def test_idempotent(self) -> None:
        """Calling _setup_pytauri_standalone twice must not fail."""
        old_standalone = getattr(sys, "_pytauri_standalone", None)
        old_mod = sys.modules.pop("__pytauri_ext_mod__", None)
        try:
            if hasattr(sys, "_pytauri_standalone"):
                del sys._pytauri_standalone
            _setup_pytauri_standalone()
            _setup_pytauri_standalone()  # second call should be idempotent
            assert getattr(sys, "_pytauri_standalone", False) is True
        finally:
            if old_standalone is not None:
                sys._pytauri_standalone = old_standalone  # type: ignore[attr-defined]
            elif hasattr(sys, "_pytauri_standalone"):
                del sys._pytauri_standalone
            if old_mod is not None:
                sys.modules["__pytauri_ext_mod__"] = old_mod
            else:
                sys.modules.pop("__pytauri_ext_mod__", None)

    def test_freeze_support_calls_setup_in_frozen_mode(self) -> None:
        """freeze_support() must call _setup_pytauri_standalone when frozen."""
        source = inspect.getsource(freeze_support)
        assert "_setup_pytauri_standalone" in source


# ── PyInstaller hook validation ───────────────────────────────────────


class TestPyInstallerHook:
    """Verify that the PyInstaller hook captures all required assets."""

    def test_hook_dirs_returns_valid_path(self) -> None:
        """get_hook_dirs() must return a list with the hook directory."""
        from pywry._pyinstaller_hook import get_hook_dirs

        dirs = get_hook_dirs()
        assert len(dirs) == 1
        hook_dir = Path(dirs[0])
        assert hook_dir.is_dir()
        assert (hook_dir / "hook-pywry.py").is_file()

    def test_hook_collects_data_files(self) -> None:
        """The hook must collect Tauri.toml, frontend/, capabilities/."""
        from PyInstaller.utils.hooks import collect_data_files

        datas = collect_data_files("pywry")
        src_files = {src for src, _ in datas}
        # Must include Tauri.toml and index.html at minimum
        assert any("Tauri.toml" in f for f in src_files)
        assert any("index.html" in f for f in src_files)
        assert any("default.toml" in f for f in src_files)

    def test_hook_includes_native_ext_mod(self) -> None:
        """hiddenimports must include pytauri_wheel.ext_mod (the .pyd)."""
        from PyInstaller.utils.hooks import collect_submodules

        # The hook uses collect_submodules which should find ext_mod
        submodules = collect_submodules("pytauri_wheel")
        assert "pytauri_wheel.ext_mod" in submodules

    def test_hook_includes_importlib_metadata(self) -> None:
        """importlib_metadata must be a hidden import (used by pytauri)."""
        # Read the hook source and verify importlib_metadata is listed
        hook_path = Path(__file__).parent.parent / "pywry" / "_pyinstaller_hook" / "hook-pywry.py"
        source = hook_path.read_text(encoding="utf-8")
        assert "importlib_metadata" in source
