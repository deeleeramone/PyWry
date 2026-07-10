"""Tests for the ``pywry.notebook`` module.

Covers:
- Notebook environment detection (Colab, Kaggle, Databricks, plain Jupyter,
  terminal IPython, no-IPython, headless VM).
- ``WindowMode.NOTEBOOK`` as an explicit override in ``PyWry.show*()``.
- ``is_headless_environment`` per-platform logic.
- ``is_anywidget_available`` / ``is_cloud_environment`` helpers.
- Toolbar wrappers (``_wrap_content_with_toolbar`` /
  ``_wrap_content_with_toolbars``).
- Widget factories (``create_plotly_widget``, ``create_dataframe_widget``,
  ``create_tvchart_widget``) for both anywidget and InlineWidget code paths.
- Grid CSV export handler.
"""

from __future__ import annotations

import sys
import types

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import pywry.notebook as notebook_mod

from pywry.config import clear_settings
from pywry.models import WindowMode
from pywry.notebook import (
    NotebookEnvironment,
    _make_grid_export_handler,
    _wrap_content_with_toolbar,
    _wrap_content_with_toolbars,
    clear_environment_cache,
    create_dataframe_widget,
    create_plotly_widget,
    create_tvchart_widget,
    detect_notebook_environment,
    is_anywidget_available,
    is_cloud_environment,
    is_headless_environment,
    should_use_inline_rendering,
)


# =============================================================================
# Module-level helpers and fixtures
# =============================================================================


_MANAGED_ENV_VARS = (
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
)


@pytest.fixture(autouse=True)
def _reset_detection_cache():
    """Clear detection cache + config singleton around every test."""
    clear_environment_cache()
    clear_settings()
    yield
    clear_environment_cache()
    clear_settings()


@pytest.fixture
def clear_managed_env(monkeypatch):
    """Clear all environment variables that select a managed-notebook backend."""
    for var in _MANAGED_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


def _make_fake_ipython(class_name: str, module: str = "ipykernel.zmqshell") -> object:
    """Return an instance of a synthetic class with the given name/module."""
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
    # Subclass with a no-op __init__ to get a usable isinstance() target.
    class _FakeShell(ZMQInteractiveShell):  # type: ignore[misc, valid-type]
        def __init__(self) -> None:
            pass

    return _FakeShell()


def _builtin_import():
    """Return the real builtins.__import__ regardless of dict/module shape."""
    return __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__


# ---------------------------------------------------------------------------
# Cloud-managed environment detection
# ---------------------------------------------------------------------------


class TestColabDetection:
    """Colab is detected via env vars even when its shell is google.colab._shell.Shell."""

    def test_colab_detected_via_release_tag_env_var(self, monkeypatch):
        # A real Colab kernel is a ZMQInteractiveShell subclass in
        # google.colab._shell — strict checks used to misfire here.
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

    def test_kaggle_detected(self, clear_managed_env):
        # _check_kaggle uses Path("/kaggle/input").exists(), which we can't fake
        # on Windows, so patch the entry in _CHECKERS directly.
        with (
            patch.dict(
                "pywry.notebook._CHECKERS",
                {"_check_kaggle": lambda: True},
            ),
            self._patch_zmq_shell(),
        ):
            assert detect_notebook_environment() == NotebookEnvironment.KAGGLE

    def test_databricks_detected(self, clear_managed_env):
        clear_managed_env.setenv("DATABRICKS_RUNTIME_VERSION", "13.3")
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

    def test_plain_jupyter_returns_jupyter_notebook(self, clear_managed_env):
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


class TestDetectImportErrors:
    """ImportError fallback paths in _detect_environment_impl."""

    def test_no_ipython_module_returns_none(self):
        """When IPython itself isn't importable, detection returns NONE."""
        original_modules = dict(sys.modules)

        for key in list(sys.modules.keys()):
            if key.startswith("IPython"):
                del sys.modules[key]

        real_import = _builtin_import()

        def import_blocker(name, *args, **kwargs):
            if name == "IPython" or name.startswith("IPython."):
                raise ImportError(f"blocked import of {name}")
            return real_import(name, *args, **kwargs)

        try:
            with patch("builtins.__import__", side_effect=import_blocker):
                clear_environment_cache()
                assert detect_notebook_environment() == NotebookEnvironment.NONE
        finally:
            sys.modules.update(original_modules)

    def test_no_ipykernel_module_returns_none(self, clear_managed_env):
        """When ipykernel isn't importable but IPython is, returns NONE if no
        env-var checks match.
        """
        # An IPython instance that is NOT a TerminalInteractiveShell, so the
        # function reaches the ipykernel import.
        fake_shell = MagicMock()
        fake_shell.__class__.__name__ = "GenericShell"

        real_import = _builtin_import()

        def import_blocker(name, *args, **kwargs):
            if name in {"ipykernel.zmqshell", "ipykernel"}:
                raise ImportError(f"blocked: {name}")
            return real_import(name, *args, **kwargs)

        with (
            patch("IPython.get_ipython", return_value=fake_shell),
            patch.dict(
                notebook_mod._CHECKERS,
                {
                    "_check_colab": lambda: False,
                    "_check_kaggle": lambda: False,
                    "_check_azure": lambda: False,
                    "_check_vscode": lambda: False,
                    "_check_nteract": lambda: False,
                    "_check_cocalc": lambda: False,
                    "_check_databricks": lambda: False,
                    "_check_remote_jupyter": lambda: False,
                    "_check_jupyterlab": lambda: False,
                },
            ),
            patch("builtins.__import__", side_effect=import_blocker),
        ):
            clear_environment_cache()
            assert detect_notebook_environment() == NotebookEnvironment.NONE


# ---------------------------------------------------------------------------
# should_use_inline_rendering forced-override
# ---------------------------------------------------------------------------


class TestShouldUseInlineRenderingForceNotebook:
    """force_notebook=True returns True regardless of env detection."""

    def test_force_notebook_overrides_detection(self):
        fake_settings = MagicMock()
        fake_settings.server.force_notebook = True

        with patch("pywry.config.get_settings", return_value=fake_settings):
            assert should_use_inline_rendering() is True


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

        # is_headless must be False so the constructor doesn't promote
        # NEW_WINDOW to BROWSER on a headless CI runner.
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
        """
        from pywry import runtime
        from pywry.app import PyWry
        from pywry.widget_protocol import NativeWindowHandle

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
        monkeypatch.setattr("sys.platform", "linux")
        monkeypatch.delenv("DISPLAY", raising=False)
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        assert is_headless_environment() is True

    def test_x11_display_set_is_not_headless(self, monkeypatch):
        monkeypatch.setattr("sys.platform", "linux")
        monkeypatch.setenv("DISPLAY", ":0")
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        assert is_headless_environment() is False

    def test_wayland_display_set_is_not_headless(self, monkeypatch):
        monkeypatch.setattr("sys.platform", "linux")
        monkeypatch.delenv("DISPLAY", raising=False)
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
        assert is_headless_environment() is False

    def test_macos_is_never_headless(self, monkeypatch):
        monkeypatch.setattr("sys.platform", "darwin")
        monkeypatch.delenv("DISPLAY", raising=False)
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        assert is_headless_environment() is False

    def test_windows_is_never_headless(self, monkeypatch):
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


# ---------------------------------------------------------------------------
# is_anywidget_available
# ---------------------------------------------------------------------------


class TestIsAnywidgetAvailable:
    """All branches of is_anywidget_available."""

    def test_anywidget_not_installed_returns_false(self):
        real_import = _builtin_import()

        def import_blocker(name, *args, **kwargs):
            if name == "anywidget":
                raise ImportError("anywidget not installed")
            return real_import(name, *args, **kwargs)

        cached = sys.modules.pop("anywidget", None)
        try:
            with patch("builtins.__import__", side_effect=import_blocker):
                assert is_anywidget_available() is False
        finally:
            if cached is not None:
                sys.modules["anywidget"] = cached

    def test_anywidget_old_version_returns_false(self):
        """Version 0.8.x is rejected; we need >= 0.9.0."""
        fake = MagicMock()
        fake.__version__ = "0.8.5"
        with patch.dict(sys.modules, {"anywidget": fake}):
            assert is_anywidget_available() is False

    def test_anywidget_exactly_0_9_returns_true(self):
        fake = MagicMock()
        fake.__version__ = "0.9.0"
        with patch.dict(sys.modules, {"anywidget": fake}):
            assert is_anywidget_available() is True

    def test_anywidget_major_version_1_returns_true(self):
        fake = MagicMock()
        fake.__version__ = "1.0.0"
        with patch.dict(sys.modules, {"anywidget": fake}):
            assert is_anywidget_available() is True

    def test_anywidget_no_minor_version_returns_true(self):
        """Version string with only major component (e.g. '1')."""
        fake = MagicMock()
        fake.__version__ = "1"
        with patch.dict(sys.modules, {"anywidget": fake}):
            assert is_anywidget_available() is True

    def test_anywidget_no_version_attr_returns_false(self):
        """Without __version__, getattr default '0.0.0' triggers the rejection."""

        class FakeMod:
            pass

        with patch.dict(sys.modules, {"anywidget": FakeMod()}):
            assert is_anywidget_available() is False


# ---------------------------------------------------------------------------
# is_cloud_environment
# ---------------------------------------------------------------------------


class TestIsCloudEnvironment:
    """is_cloud_environment classifies cloud vs local notebook backends."""

    @pytest.mark.parametrize(
        "env",
        [
            NotebookEnvironment.COLAB,
            NotebookEnvironment.KAGGLE,
            NotebookEnvironment.AZURE,
            NotebookEnvironment.DATABRICKS,
        ],
    )
    def test_cloud_environments_classified_true(self, env: NotebookEnvironment):
        with patch("pywry.notebook.detect_notebook_environment", return_value=env):
            assert is_cloud_environment() is True

    @pytest.mark.parametrize(
        "env",
        [NotebookEnvironment.JUPYTER_NOTEBOOK, NotebookEnvironment.NONE],
    )
    def test_local_environments_classified_false(self, env: NotebookEnvironment):
        with patch("pywry.notebook.detect_notebook_environment", return_value=env):
            assert is_cloud_environment() is False


# ---------------------------------------------------------------------------
# Toolbar wrappers
# ---------------------------------------------------------------------------


class TestWrapContentWithToolbar:
    """_wrap_content_with_toolbar covers each position branch."""

    def test_empty_toolbar_returns_content_unchanged(self):
        out = _wrap_content_with_toolbar("<div>main</div>", "", "top")
        assert out == "<div>main</div>"

    def test_top_position(self):
        out = _wrap_content_with_toolbar("<div>x</div>", "<T>", "top")
        assert "pywry-wrapper-top" in out
        assert out.index("<T>") < out.index("<div>x</div>")

    def test_bottom_position(self):
        out = _wrap_content_with_toolbar("<div>x</div>", "<T>", "bottom")
        assert "pywry-wrapper-bottom" in out
        assert out.index("<div>x</div>") < out.index("<T>")

    def test_left_position(self):
        out = _wrap_content_with_toolbar("<div>x</div>", "<T>", "left")
        assert "pywry-wrapper-left" in out

    def test_right_position(self):
        out = _wrap_content_with_toolbar("<div>x</div>", "<T>", "right")
        assert "pywry-wrapper-right" in out

    def test_inside_position(self):
        out = _wrap_content_with_toolbar("<div>x</div>", "<T>", "inside")
        assert "pywry-wrapper-inside" in out

    def test_unknown_position_falls_back_to_content(self):
        # wrappers.get(position, content) falls back to bare content
        out = _wrap_content_with_toolbar("<div>x</div>", "<T>", "diagonal")
        assert out == "<div>x</div>"


class TestWrapContentWithToolbars:
    """_wrap_content_with_toolbars delegates to toolbar.wrap_content_with_toolbars."""

    def test_delegates_to_toolbar_module(self):
        with patch(
            "pywry.toolbar.wrap_content_with_toolbars",
            return_value="<wrapped>",
        ) as mock_fn:
            out = _wrap_content_with_toolbars("<content>", [{"position": "top"}])
            assert out == "<wrapped>"
            mock_fn.assert_called_once()

    def test_with_none_toolbars_passes_through(self):
        # When toolbars is None, the real function returns content unchanged
        out = _wrap_content_with_toolbars("<content>", None)
        assert "<content>" in out


# ---------------------------------------------------------------------------
# create_plotly_widget
# ---------------------------------------------------------------------------


class TestCreatePlotlyWidget:
    """Both anywidget and InlineWidget paths of create_plotly_widget."""

    def test_anywidget_path_with_toolbars_and_modals(self):
        """HAS_ANYWIDGET=True + not headless + not force_iframe → PyWryPlotlyWidget."""
        fake_widget = MagicMock(name="PyWryPlotlyWidget")

        with (
            patch("pywry.runtime.is_headless", return_value=False),
            patch("pywry.widget.HAS_ANYWIDGET", True),
            patch("pywry.widget.PyWryPlotlyWidget", return_value=fake_widget),
            patch("pywry.inline._generate_widget_token", return_value="tok123"),
            patch("pywry.inline.generate_plotly_html", return_value="<html-content>"),
            patch(
                "pywry.modal.wrap_content_with_modals",
                return_value=("<modal-html>", "<modal-scripts>"),
            ),
        ):
            result = create_plotly_widget(
                figure_json='{"data": []}',
                widget_id="w1",
                title="Plot",
                theme="dark",
                width="100%",
                height=400,
                toolbars=[{"position": "top"}],
                modals=[{"component_id": "m1"}],
                force_iframe=False,
            )
            assert result is fake_widget

    def test_anywidget_path_no_toolbars_no_modals(self):
        """The simpler anywidget path with no modals and no toolbars."""
        fake_widget = MagicMock(name="PyWryPlotlyWidget")
        with (
            patch("pywry.runtime.is_headless", return_value=False),
            patch("pywry.widget.HAS_ANYWIDGET", True),
            patch("pywry.widget.PyWryPlotlyWidget", return_value=fake_widget),
            patch("pywry.inline._generate_widget_token", return_value="t"),
            patch("pywry.inline.generate_plotly_html", return_value="<h>"),
        ):
            result = create_plotly_widget(figure_json='{"data": []}', widget_id="w1")
            assert result is fake_widget

    def test_inline_widget_path_when_force_iframe(self):
        """force_iframe=True selects the InlineWidget path."""
        fake_iw = MagicMock(name="InlineWidget")
        with (
            patch("pywry.runtime.is_headless", return_value=False),
            patch("pywry.widget.HAS_ANYWIDGET", True),
            patch("pywry.inline._generate_widget_token", return_value="tok"),
            patch("pywry.inline.generate_plotly_html", return_value="<h>"),
            patch("pywry.inline.InlineWidget", return_value=fake_iw),
        ):
            result = create_plotly_widget(
                figure_json='{"data": []}',
                widget_id="w1",
                force_iframe=True,
            )
            assert result is fake_iw

    def test_inline_widget_path_when_headless(self):
        """is_headless=True selects the InlineWidget path."""
        fake_iw = MagicMock(name="InlineWidget")
        with (
            patch("pywry.runtime.is_headless", return_value=True),
            patch("pywry.widget.HAS_ANYWIDGET", True),
            patch("pywry.inline._generate_widget_token", return_value="tok"),
            patch("pywry.inline.generate_plotly_html", return_value="<h>"),
            patch("pywry.inline.InlineWidget", return_value=fake_iw),
        ):
            result = create_plotly_widget(
                figure_json='{"data": []}',
                widget_id="w1",
                port=9000,
            )
            assert result is fake_iw

    def test_inline_widget_path_when_no_anywidget(self):
        fake_iw = MagicMock(name="InlineWidget")
        with (
            patch("pywry.runtime.is_headless", return_value=False),
            patch("pywry.widget.HAS_ANYWIDGET", False),
            patch("pywry.inline._generate_widget_token", return_value="tok"),
            patch("pywry.inline.generate_plotly_html", return_value="<h>"),
            patch("pywry.inline.InlineWidget", return_value=fake_iw),
        ):
            result = create_plotly_widget(figure_json='{"data": []}', widget_id="w1")
            assert result is fake_iw

    def test_inline_widget_path_with_modals(self):
        fake_iw = MagicMock(name="InlineWidget")
        with (
            patch("pywry.runtime.is_headless", return_value=False),
            patch("pywry.widget.HAS_ANYWIDGET", False),
            patch("pywry.inline._generate_widget_token", return_value="tok"),
            patch("pywry.inline.generate_plotly_html", return_value="<h>"),
            patch("pywry.inline.InlineWidget", return_value=fake_iw),
            patch(
                "pywry.modal.wrap_content_with_modals",
                return_value=("<m>", "<s>"),
            ),
        ):
            result = create_plotly_widget(
                figure_json='{"data": []}',
                widget_id="w1",
                modals=[{"component_id": "m1"}],
            )
            assert result is fake_iw


# ---------------------------------------------------------------------------
# _make_grid_export_handler
# ---------------------------------------------------------------------------


class TestMakeGridExportHandler:
    """The handler that writes CSV files and emits notifications."""

    def test_export_writes_file_and_emits_notification(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        widget = MagicMock()
        handler = _make_grid_export_handler(widget)

        data = {
            "csvContent": "a,b\r\n1,2\r\n",
            "fileName": "data.csv",
            "exportType": "manual",
        }
        handler(data, "grid:export-csv", "label1")

        # A file matching pattern data_*.csv should have been written
        files = list(tmp_path.glob("data_*.csv"))
        assert len(files) == 1
        # Line endings normalised to \n
        body = files[0].read_text(encoding="utf-8")
        assert "\r" not in body
        assert body == "a,b\n1,2\n"

        # Notification emitted
        widget.emit.assert_called_once()
        emit_args = widget.emit.call_args
        assert emit_args[0][0] == "pywry:show-notification"
        assert "Saved" in emit_args[0][1]["message"]

    def test_export_failure_emits_error_notification(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        widget = MagicMock()
        handler = _make_grid_export_handler(widget)

        with patch.object(Path, "write_text", side_effect=OSError("disk full")):
            handler(
                {
                    "csvContent": "a,b\n1,2\n",
                    "fileName": "boom.csv",
                    "exportType": "auto",
                },
                "grid:export-csv",
                "labelX",
            )

        widget.emit.assert_called_once()
        emit_args = widget.emit.call_args
        assert emit_args[0][0] == "pywry:show-notification"
        assert "Export failed" in emit_args[0][1]["message"]

    def test_export_default_filename(self, tmp_path: Path, monkeypatch):
        """When fileName is missing, the handler defaults to 'export.csv'."""
        monkeypatch.chdir(tmp_path)
        widget = MagicMock()
        handler = _make_grid_export_handler(widget)

        # Empty dict triggers all defaults
        handler({}, "grid:export-csv", "lbl")

        files = list(tmp_path.glob("export_*.csv"))
        assert len(files) == 1


# ---------------------------------------------------------------------------
# create_dataframe_widget
# ---------------------------------------------------------------------------


class TestCreateDataframeWidget:
    """Both anywidget and InlineWidget paths of create_dataframe_widget."""

    def test_anywidget_path_with_toolbars(self):
        fake_widget = MagicMock(name="PyWryAgGridWidget")
        fake_config = MagicMock()
        with (
            patch("pywry.runtime.is_headless", return_value=False),
            patch("pywry.widget.HAS_ANYWIDGET", True),
            patch("pywry.widget.PyWryAgGridWidget", return_value=fake_widget),
            patch("pywry.grid.to_js_grid_config", return_value={"some": "config"}),
            patch(
                "pywry.modal.wrap_content_with_modals",
                return_value=("<modal-html>", "<modal-scripts>"),
            ),
        ):
            result = create_dataframe_widget(
                config=fake_config,
                widget_id="w1",
                title="Data",
                theme="dark",
                aggrid_theme="alpine",
                width="100%",
                height=500,
                toolbars=[{"position": "top"}],
                modals=[{"component_id": "m1"}],
            )
            assert result is fake_widget

    def test_anywidget_path_with_header_html_no_toolbars(self):
        """header_html present and no toolbars - wraps content with header."""
        fake_widget = MagicMock(name="PyWryAgGridWidget")
        fake_config = MagicMock()
        with (
            patch("pywry.runtime.is_headless", return_value=False),
            patch("pywry.widget.HAS_ANYWIDGET", True),
            patch("pywry.widget.PyWryAgGridWidget", return_value=fake_widget),
            patch("pywry.grid.to_js_grid_config", return_value={"k": "v"}),
        ):
            result = create_dataframe_widget(
                config=fake_config,
                widget_id="w1",
                header_html="<h1>Header</h1>",
                toolbars=None,
            )
            assert result is fake_widget

    def test_anywidget_path_string_height_passes_through(self):
        """When height is already a string, don't append 'px'."""
        fake_widget = MagicMock(name="PyWryAgGridWidget")
        fake_config = MagicMock()
        with (
            patch("pywry.runtime.is_headless", return_value=False),
            patch("pywry.widget.HAS_ANYWIDGET", True),
            patch("pywry.widget.PyWryAgGridWidget", return_value=fake_widget),
            patch("pywry.grid.to_js_grid_config", return_value={}),
        ):
            result = create_dataframe_widget(
                config=fake_config,
                widget_id="w1",
                height="800px",
            )
            assert result is fake_widget

    def test_inline_widget_path_force_iframe_registers_export_handler(self):
        """force_iframe=True takes the InlineWidget path and registers the export handler."""
        fake_iw = MagicMock(name="InlineWidget")
        fake_iw.on = MagicMock()
        fake_config = MagicMock()

        with (
            patch("pywry.runtime.is_headless", return_value=False),
            patch("pywry.widget.HAS_ANYWIDGET", True),
            patch("pywry.inline._generate_widget_token", return_value="tok"),
            patch(
                "pywry.inline.generate_dataframe_html_from_config",
                return_value="<grid-html>",
            ),
            patch("pywry.inline.InlineWidget", return_value=fake_iw),
        ):
            result = create_dataframe_widget(
                config=fake_config,
                widget_id="w1",
                force_iframe=True,
            )
            assert result is fake_iw
            fake_iw.on.assert_called_once()
            assert fake_iw.on.call_args[0][0] == "grid:export-csv"

    def test_inline_widget_path_when_headless(self):
        fake_iw = MagicMock(name="InlineWidget")
        fake_iw.on = MagicMock()
        fake_config = MagicMock()

        with (
            patch("pywry.runtime.is_headless", return_value=True),
            patch("pywry.widget.HAS_ANYWIDGET", True),
            patch("pywry.inline._generate_widget_token", return_value="tok"),
            patch(
                "pywry.inline.generate_dataframe_html_from_config",
                return_value="<grid-html>",
            ),
            patch("pywry.inline.InlineWidget", return_value=fake_iw),
        ):
            result = create_dataframe_widget(
                config=fake_config,
                widget_id="w1",
                port=8080,
            )
            assert result is fake_iw
            fake_iw.on.assert_called_once()

    def test_inline_widget_path_with_modals(self):
        fake_iw = MagicMock(name="InlineWidget")
        fake_iw.on = MagicMock()
        fake_config = MagicMock()

        with (
            patch("pywry.runtime.is_headless", return_value=False),
            patch("pywry.widget.HAS_ANYWIDGET", False),
            patch("pywry.inline._generate_widget_token", return_value="tok"),
            patch(
                "pywry.inline.generate_dataframe_html_from_config",
                return_value="<grid-html>",
            ),
            patch("pywry.inline.InlineWidget", return_value=fake_iw),
            patch(
                "pywry.modal.wrap_content_with_modals",
                return_value=("<m>", "<s>"),
            ),
        ):
            result = create_dataframe_widget(
                config=fake_config,
                widget_id="w1",
                modals=[{"component_id": "m1"}],
            )
            assert result is fake_iw


# ---------------------------------------------------------------------------
# create_tvchart_widget
# ---------------------------------------------------------------------------


class TestCreateTVChartWidget:
    """Both anywidget and InlineWidget paths of create_tvchart_widget."""

    def test_anywidget_path(self):
        fake_widget = MagicMock()
        with (
            patch("pywry.runtime.is_headless", return_value=False),
            patch("pywry.widget.HAS_ANYWIDGET", True),
            patch("pywry.widget.PyWryTVChartWidget", return_value=fake_widget) as mock_widget,
        ):
            result = create_tvchart_widget(
                chart_html='<div id="c"></div>',
                config_payload='{"chartOptions":{}}',
                chart_id="c",
                widget_id="w1",
            )
        assert result is fake_widget
        mock_widget.assert_called_once()

    def test_anywidget_with_modals(self):
        fake_widget = MagicMock()
        with (
            patch("pywry.runtime.is_headless", return_value=False),
            patch("pywry.widget.HAS_ANYWIDGET", True),
            patch("pywry.widget.PyWryTVChartWidget", return_value=fake_widget),
            patch(
                "pywry.modal.wrap_content_with_modals",
                return_value=("<m>", "<s>"),
            ),
        ):
            result = create_tvchart_widget(
                chart_html='<div id="c"></div>',
                config_payload='{"chartOptions":{}}',
                chart_id="c",
                widget_id="w1",
                modals=[{"component_id": "m1"}],
            )
        assert result is fake_widget

    def test_iframe_path_via_force_iframe(self):
        fake_iw = MagicMock()
        with (
            patch("pywry.runtime.is_headless", return_value=False),
            patch("pywry.widget.HAS_ANYWIDGET", True),
            patch("pywry.inline._generate_widget_token", return_value="tok"),
            patch("pywry.inline.generate_tvchart_html", return_value="<html/>"),
            patch("pywry.inline.InlineWidget", return_value=fake_iw),
        ):
            result = create_tvchart_widget(
                chart_html='<div id="c"></div>',
                config_payload='{"chartOptions":{}}',
                chart_id="c",
                widget_id="w1",
                force_iframe=True,
            )
        assert result is fake_iw

    def test_iframe_path_via_headless(self):
        fake_iw = MagicMock()
        with (
            patch("pywry.runtime.is_headless", return_value=True),
            patch("pywry.widget.HAS_ANYWIDGET", True),
            patch("pywry.inline._generate_widget_token", return_value="tok"),
            patch("pywry.inline.generate_tvchart_html", return_value="<html/>"),
            patch("pywry.inline.InlineWidget", return_value=fake_iw),
        ):
            result = create_tvchart_widget(
                chart_html='<div id="c"></div>',
                config_payload='{"chartOptions":{}}',
                chart_id="c",
                widget_id="w1",
            )
        assert result is fake_iw

    def test_iframe_path_no_anywidget(self):
        fake_iw = MagicMock()
        with (
            patch("pywry.runtime.is_headless", return_value=False),
            patch("pywry.widget.HAS_ANYWIDGET", False),
            patch("pywry.inline._generate_widget_token", return_value="tok"),
            patch("pywry.inline.generate_tvchart_html", return_value="<html/>"),
            patch("pywry.inline.InlineWidget", return_value=fake_iw),
        ):
            result = create_tvchart_widget(
                chart_html='<div id="c"></div>',
                config_payload='{"chartOptions":{}}',
                chart_id="c",
                widget_id="w1",
            )
        assert result is fake_iw

    def test_string_height_passed_through(self):
        fake_widget = MagicMock()
        with (
            patch("pywry.runtime.is_headless", return_value=False),
            patch("pywry.widget.HAS_ANYWIDGET", True),
            patch("pywry.widget.PyWryTVChartWidget", return_value=fake_widget) as mock_widget,
        ):
            create_tvchart_widget(
                chart_html='<div id="c"></div>',
                config_payload='{"chartOptions":{}}',
                chart_id="c",
                widget_id="w1",
                height="800px",
            )
        kwargs = mock_widget.call_args.kwargs
        assert kwargs["height"] == "800px"
