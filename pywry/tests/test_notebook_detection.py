"""Tests for notebook environment detection and the WindowMode.NOTEBOOK override.

Covers two related fixes:

* Cloud-managed notebooks (Colab, Kaggle, Azure, Databricks, …) are detected
  via env-var / import signals even when their IPython shell is not a vanilla
  ``ZMQInteractiveShell`` from the ``ipykernel`` module.
* ``WindowMode.NOTEBOOK`` is honoured as an explicit override in
  ``PyWry.show*()``, regardless of what auto-detection returns.
"""

from __future__ import annotations

import sys
import types

from unittest.mock import MagicMock, patch

import pytest

from pywry.config import clear_settings
from pywry.models import WindowMode
from pywry.notebook import (
    NotebookEnvironment,
    clear_environment_cache,
    detect_notebook_environment,
    should_use_inline_rendering,
)


@pytest.fixture(autouse=True)
def _reset_detection_cache():
    clear_environment_cache()
    clear_settings()
    yield
    clear_environment_cache()
    clear_settings()


def _make_fake_ipython(class_name: str, module: str = "ipykernel.zmqshell") -> object:
    """Return an instance of a synthetic class with the given ``__name__`` / ``__module__``."""
    fake_class = type(class_name, (), {})
    fake_class.__module__ = module
    return fake_class()


def _make_zmq_shell_instance() -> object:
    """Return an instance of ZMQInteractiveShell (or skip if ipykernel missing)."""
    try:
        from ipykernel.zmqshell import ZMQInteractiveShell
    except ImportError:
        pytest.skip("ipykernel not installed")

    # ZMQInteractiveShell.__init__ does heavy setup (kernel session, etc.).
    # Bypass it — we only need an instance whose isinstance() and class
    # attributes match. A subclass with a no-op __init__ is enough.
    class _FakeShell(ZMQInteractiveShell):  # type: ignore[misc, valid-type]
        def __init__(self) -> None:  # noqa: D401 - intentional no-op
            pass

    return _FakeShell()


# ---------------------------------------------------------------------------
# Cloud-managed environments
# ---------------------------------------------------------------------------


class TestColabDetection:
    """Colab is detected via env vars even when its shell is google.colab._shell.Shell."""

    def test_colab_detected_via_release_tag_env_var(self, monkeypatch):
        # Simulate a real Colab kernel: subclass of ZMQInteractiveShell, but in the
        # google.colab._shell module — this used to misfire on the strict checks.
        try:
            from ipykernel.zmqshell import ZMQInteractiveShell
        except ImportError:
            pytest.skip("ipykernel not installed")

        class _ColabShell(ZMQInteractiveShell):  # type: ignore[misc, valid-type]
            def __init__(self) -> None:
                pass

        _ColabShell.__module__ = "google.colab._shell"
        fake_shell = _ColabShell()

        monkeypatch.setenv("COLAB_RELEASE_TAG", "release-colab-foo")
        with patch("IPython.get_ipython", return_value=fake_shell):
            assert detect_notebook_environment() == NotebookEnvironment.COLAB
            assert should_use_inline_rendering() is True

    def test_colab_detected_via_notebook_id_env_var(self, monkeypatch):
        monkeypatch.delenv("COLAB_RELEASE_TAG", raising=False)
        monkeypatch.setenv("COLAB_NOTEBOOK_ID", "1abc")
        fake_shell = _make_zmq_shell_instance()
        with patch("IPython.get_ipython", return_value=fake_shell):
            assert detect_notebook_environment() == NotebookEnvironment.COLAB

    def test_colab_detected_via_google_colab_import(self, monkeypatch):
        monkeypatch.delenv("COLAB_RELEASE_TAG", raising=False)
        monkeypatch.delenv("COLAB_NOTEBOOK_ID", raising=False)

        # Inject a fake `google.colab` module so the import-fallback branch fires.
        google_pkg = types.ModuleType("google")
        google_pkg.__path__ = []  # type: ignore[attr-defined]
        colab_mod = types.ModuleType("google.colab")
        monkeypatch.setitem(sys.modules, "google", google_pkg)
        monkeypatch.setitem(sys.modules, "google.colab", colab_mod)

        fake_shell = _make_zmq_shell_instance()
        with patch("IPython.get_ipython", return_value=fake_shell):
            assert detect_notebook_environment() == NotebookEnvironment.COLAB


class TestEnvVarManagedNotebooks:
    """Other env-var-driven environments still work after the reorder."""

    def _patch_zmq_shell(self):
        return patch("IPython.get_ipython", return_value=_make_zmq_shell_instance())

    @staticmethod
    def _clear_managed_env(monkeypatch):
        for var in (
            "COLAB_RELEASE_TAG",
            "COLAB_NOTEBOOK_ID",
            "AZURE_NOTEBOOKS_HOST",
            "VSCODE_PID",
            "NTERACT_EXE",
            "COCALC_PROJECT_ID",
            "DATABRICKS_RUNTIME_VERSION",
            "JUPYTER_SERVER_ROOT",
            "JUPYTERHUB_USER",
            "JUPYTERLAB_WORKSPACES_DIR",
        ):
            monkeypatch.delenv(var, raising=False)

    def test_kaggle_detected(self, monkeypatch):
        self._clear_managed_env(monkeypatch)
        # _check_kaggle uses Path("/kaggle/input").exists(). We can't write there
        # in tests, so patch the entry in _CHECKERS directly.
        with (
            patch.dict(
                "pywry.notebook._CHECKERS",
                {"_check_kaggle": lambda: True},
            ),
            self._patch_zmq_shell(),
        ):
            assert detect_notebook_environment() == NotebookEnvironment.KAGGLE

    def test_databricks_detected(self, monkeypatch):
        self._clear_managed_env(monkeypatch)
        monkeypatch.setenv("DATABRICKS_RUNTIME_VERSION", "13.3")
        with self._patch_zmq_shell():
            assert detect_notebook_environment() == NotebookEnvironment.DATABRICKS


# ---------------------------------------------------------------------------
# Plain Jupyter / terminal / no-IPython baselines
# ---------------------------------------------------------------------------


class TestNonManagedEnvironments:
    """Detection still distinguishes plain Jupyter, terminal IPython, and scripts."""

    def test_terminal_ipython_returns_terminal(self):
        fake = _make_fake_ipython(
            "TerminalInteractiveShell", module="IPython.terminal.interactiveshell"
        )
        with patch("IPython.get_ipython", return_value=fake):
            assert detect_notebook_environment() == NotebookEnvironment.IPYTHON_TERMINAL
            assert should_use_inline_rendering() is False

    def test_plain_jupyter_returns_jupyter_notebook(self, monkeypatch):
        # Clear any cloud-env vars that the test runner may have set.
        for var in (
            "COLAB_RELEASE_TAG",
            "COLAB_NOTEBOOK_ID",
            "AZURE_NOTEBOOKS_HOST",
            "VSCODE_PID",
            "NTERACT_EXE",
            "COCALC_PROJECT_ID",
            "DATABRICKS_RUNTIME_VERSION",
            "JUPYTER_SERVER_ROOT",
            "JUPYTERHUB_USER",
            "JUPYTERLAB_WORKSPACES_DIR",
        ):
            monkeypatch.delenv(var, raising=False)

        fake_shell = _make_zmq_shell_instance()
        with patch("IPython.get_ipython", return_value=fake_shell):
            assert detect_notebook_environment() == NotebookEnvironment.JUPYTER_NOTEBOOK

    def test_no_ipython_returns_none(self):
        with patch("IPython.get_ipython", return_value=None):
            assert detect_notebook_environment() == NotebookEnvironment.NONE
            assert should_use_inline_rendering() is False

    def test_vscode_terminal_without_ipython_is_not_a_notebook(self, monkeypatch):
        # VSCODE_PID is set whenever a process runs under VS Code's terminal.
        # Without IPython, that's a plain script, not a notebook.
        monkeypatch.setenv("VSCODE_PID", "1234")
        with patch("IPython.get_ipython", return_value=None):
            assert detect_notebook_environment() == NotebookEnvironment.NONE


# ---------------------------------------------------------------------------
# WindowMode.NOTEBOOK explicit override
# ---------------------------------------------------------------------------


class TestWindowModeNotebookOverride:
    """``WindowMode.NOTEBOOK`` forces inline rendering regardless of detection."""

    def test_use_inline_true_with_notebook_mode(self):
        from pywry.app import PyWry

        with (
            patch("pywry.app.should_use_inline_rendering", return_value=False),
            patch("pywry.app.is_headless_environment", return_value=False),
        ):
            app = PyWry(mode=WindowMode.NOTEBOOK)
            assert app._use_inline() is True

    def test_use_inline_false_for_native_modes_outside_notebook(self):
        from pywry.app import PyWry

        # is_headless must be False so the constructor doesn't promote NEW_WINDOW
        # to BROWSER on a headless CI runner.
        with (
            patch("pywry.app.should_use_inline_rendering", return_value=False),
            patch("pywry.app.is_headless_environment", return_value=False),
        ):
            app = PyWry(mode=WindowMode.NEW_WINDOW)
            assert app._use_inline() is False

    def test_use_inline_true_for_browser_mode(self):
        from pywry.app import PyWry

        with (
            patch("pywry.app.should_use_inline_rendering", return_value=False),
            patch("pywry.app.is_headless_environment", return_value=False),
        ):
            app = PyWry(mode=WindowMode.BROWSER)
            assert app._use_inline() is True

    def test_show_with_notebook_mode_skips_subprocess(self):
        """``app.show()`` with ``WindowMode.NOTEBOOK`` takes the inline branch
        without spawning the pytauri subprocess, even when auto-detection
        would otherwise return NONE.

        The widget produced depends on whether ``anywidget`` is installed in
        the test environment — we don't care which one, only that the
        subprocess is never started and the result is not a native handle.
        """
        from pywry import runtime
        from pywry.app import PyWry
        from pywry.widget_protocol import NativeWindowHandle

        # Stub the inline widget factories so the test doesn't depend on
        # anywidget/IPython actually being installed/usable.
        fake_widget = MagicMock()
        fake_widget.label = "test-widget"

        with (
            patch("pywry.app.should_use_inline_rendering", return_value=False),
            patch("pywry.app.is_headless_environment", return_value=False),
            patch.object(runtime, "start") as mock_start,
            patch("pywry.widget.PyWryWidget.from_html", return_value=fake_widget),
            patch("pywry.inline.show", return_value=fake_widget),
        ):
            app = PyWry(mode=WindowMode.NOTEBOOK)
            result = app.show("<p>hello</p>")

            assert not isinstance(result, NativeWindowHandle)
            mock_start.assert_not_called()


# ---------------------------------------------------------------------------
# Headless VM auto-fallback to BROWSER mode
# ---------------------------------------------------------------------------


class TestHeadlessEnvironmentDetection:
    """``is_headless_environment()`` reflects whether a display is available."""

    def test_no_display_on_linux_is_headless(self, monkeypatch):
        from pywry.notebook import is_headless_environment

        monkeypatch.setattr("sys.platform", "linux")
        monkeypatch.delenv("DISPLAY", raising=False)
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        assert is_headless_environment() is True

    def test_x11_display_set_is_not_headless(self, monkeypatch):
        from pywry.notebook import is_headless_environment

        monkeypatch.setattr("sys.platform", "linux")
        monkeypatch.setenv("DISPLAY", ":0")
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        assert is_headless_environment() is False

    def test_wayland_display_set_is_not_headless(self, monkeypatch):
        from pywry.notebook import is_headless_environment

        monkeypatch.setattr("sys.platform", "linux")
        monkeypatch.delenv("DISPLAY", raising=False)
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
        assert is_headless_environment() is False

    def test_macos_is_never_headless(self, monkeypatch):
        from pywry.notebook import is_headless_environment

        monkeypatch.setattr("sys.platform", "darwin")
        monkeypatch.delenv("DISPLAY", raising=False)
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        assert is_headless_environment() is False

    def test_windows_is_never_headless(self, monkeypatch):
        from pywry.notebook import is_headless_environment

        monkeypatch.setattr("sys.platform", "win32")
        monkeypatch.delenv("DISPLAY", raising=False)
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        assert is_headless_environment() is False


class TestHeadlessVMAutoFallbackToBrowser:
    """When a native mode is requested on a headless VM (no notebook UI),
    PyWry transparently falls back to ``BROWSER`` mode."""

    def test_native_mode_on_headless_promotes_to_browser(self):
        from pywry.app import PyWry
        from pywry.window_manager import BrowserMode

        with (
            patch("pywry.app.should_use_inline_rendering", return_value=False),
            patch("pywry.app.is_headless_environment", return_value=True),
        ):
            app = PyWry(mode=WindowMode.NEW_WINDOW)
            assert app._mode_enum == WindowMode.BROWSER
            assert isinstance(app._mode, BrowserMode)
            assert app._use_inline() is True

    def test_native_mode_with_display_stays_native(self):
        from pywry.app import PyWry
        from pywry.window_manager import NewWindowMode

        with (
            patch("pywry.app.should_use_inline_rendering", return_value=False),
            patch("pywry.app.is_headless_environment", return_value=False),
        ):
            app = PyWry(mode=WindowMode.NEW_WINDOW)
            assert app._mode_enum == WindowMode.NEW_WINDOW
            assert isinstance(app._mode, NewWindowMode)
            assert app._use_inline() is False

    def test_notebook_env_takes_precedence_over_headless(self):
        """On Colab/Jupyter (headless AND a notebook UI), keep the requested
        native mode — _use_inline() at show*() time renders inline anywidget,
        which is what users expect inside a notebook."""
        from pywry.app import PyWry
        from pywry.window_manager import NewWindowMode

        with (
            patch("pywry.app.should_use_inline_rendering", return_value=True),
            patch("pywry.app.is_headless_environment", return_value=True),
        ):
            app = PyWry(mode=WindowMode.NEW_WINDOW)
            # Mode is NOT promoted to BROWSER — anywidget rendering inside the
            # notebook UI is preferred over a server URL.
            assert app._mode_enum == WindowMode.NEW_WINDOW
            assert isinstance(app._mode, NewWindowMode)
            # _use_inline() still returns True (via should_use_inline_rendering).
            assert app._use_inline() is True

    def test_explicit_notebook_mode_not_demoted_on_headless(self):
        """``WindowMode.NOTEBOOK`` is the user's explicit choice and must not
        be silently flipped to BROWSER even on a headless host."""
        from pywry.app import PyWry

        with (
            patch("pywry.app.should_use_inline_rendering", return_value=False),
            patch("pywry.app.is_headless_environment", return_value=True),
        ):
            app = PyWry(mode=WindowMode.NOTEBOOK)
            assert app._mode_enum == WindowMode.NOTEBOOK
