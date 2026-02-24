"""Tests for frozen-app subprocess detection and command routing."""

from __future__ import annotations

import inspect
import sys
import types

from unittest.mock import patch

import pytest

from pywry._freeze import freeze_support, get_subprocess_command, is_frozen


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
