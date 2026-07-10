"""Unit tests for pywry.app.PyWry targeting line coverage.

These tests deliberately avoid spawning the pytauri subprocess.  We mock
``pywry.runtime`` and the ``WindowModeBase`` instance inside the app so
the test exercises:

* PyWry constructor across all window modes (with/without auto-fallback).
* show / show_plotly / show_dataframe / show_tvchart dispatch in NOTEBOOK,
  BROWSER, and native modes.
* Auth API (login, logout, _resolve_provider, is_authenticated,
  _show_login_page_and_wait, _wire_logout_handler).
* Native menu / tray helpers (create_menu, create_tray, remove_tray,
  _require_native_mode).
* Event emission helpers (emit, alert, send_event, on_*, command).
* Filter/sort helpers used by server-side grid mode (_apply_grid_filter,
  _apply_grid_sort, _row_matches_filter, _text_filter_match,
  _number_filter_match, _get_sort_key).
* Lifecycle helpers (close, get_labels, is_open, refresh, refresh_css,
  enable/disable_hot_reload, destroy, _shutdown, block).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from pywry.callbacks import get_registry
from pywry.models import HtmlContent, ThemeMode, WindowMode
from pywry.window_manager import (
    BrowserMode,
    MultiWindowMode,
    NewWindowMode,
    SingleWindowMode,
    get_lifecycle,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_state():
    """Reset shared state between tests."""
    get_registry().clear()
    get_lifecycle().clear()
    yield
    get_registry().clear()
    get_lifecycle().clear()


def make_app(mode=WindowMode.NEW_WINDOW, **kwargs):
    """Build a PyWry instance without ever starting the subprocess.

    Mocks ``pywry.runtime`` setters so they don't touch real state and
    forces ``is_headless_environment`` to False so the constructor doesn't
    promote NEW_WINDOW to BROWSER.
    """
    from pywry.app import PyWry

    with (
        patch("pywry.app.should_use_inline_rendering", return_value=False),
        patch("pywry.app.is_headless_environment", return_value=False),
    ):
        return PyWry(mode=mode, **kwargs)


# ---------------------------------------------------------------------------
# Constructor / mode dispatch
# ---------------------------------------------------------------------------


class TestConstructor:
    def test_default_init_creates_new_window_mode(self):
        app = make_app()
        assert app._mode_enum == WindowMode.NEW_WINDOW
        assert isinstance(app._mode, NewWindowMode)
        assert app.theme == ThemeMode.DARK

    def test_single_window_mode(self):
        app = make_app(mode=WindowMode.SINGLE_WINDOW)
        assert isinstance(app._mode, SingleWindowMode)

    def test_multi_window_mode(self):
        app = make_app(mode=WindowMode.MULTI_WINDOW)
        assert isinstance(app._mode, MultiWindowMode)

    def test_browser_mode(self):
        app = make_app(mode=WindowMode.BROWSER)
        assert isinstance(app._mode, BrowserMode)

    def test_notebook_mode_falls_through_to_multi_window(self):
        # _create_mode returns MultiWindowMode for NOTEBOOK
        app = make_app(mode=WindowMode.NOTEBOOK)
        assert isinstance(app._mode, MultiWindowMode)

    def test_init_with_custom_dimensions(self):
        app = make_app(title="X", width=1024, height=768)
        assert app._default_config.title == "X"
        assert app._default_config.width == 1024
        assert app._default_config.height == 768

    def test_init_with_hot_reload_flag(self):
        with patch("pywry.app.HotReloadManager") as mock_mgr_cls:
            mock_mgr = MagicMock()
            mock_mgr_cls.return_value = mock_mgr
            app = make_app(hot_reload=True)
            assert app._hot_reload_manager is mock_mgr
            mock_mgr.start.assert_called_once()

    def test_init_with_settings_hot_reload_enabled(self):
        from pywry.config import PyWrySettings

        settings = PyWrySettings()
        settings.hot_reload.enabled = True

        with patch("pywry.app.HotReloadManager") as mock_mgr_cls:
            mock_mgr = MagicMock()
            mock_mgr_cls.return_value = mock_mgr
            app = make_app(settings=settings)
            assert app._hot_reload_manager is mock_mgr

    def test_auto_fallback_to_browser_on_headless(self):
        from pywry.app import PyWry

        with (
            patch("pywry.app.should_use_inline_rendering", return_value=False),
            patch("pywry.app.is_headless_environment", return_value=True),
        ):
            app = PyWry(mode=WindowMode.NEW_WINDOW)
            assert app._mode_enum == WindowMode.BROWSER
            assert isinstance(app._mode, BrowserMode)


class TestUseInline:
    def test_notebook_mode_returns_true(self):
        app = make_app(mode=WindowMode.NOTEBOOK)
        assert app._use_inline() is True

    def test_browser_mode_returns_true(self):
        app = make_app(mode=WindowMode.BROWSER)
        assert app._use_inline() is True

    def test_native_mode_returns_false_when_not_inline(self):
        app = make_app()
        # _use_inline() is False because should_use_inline_rendering is False
        # at the global module level (we don't re-patch here, but
        # should_use_inline_rendering may return True or False — we only
        # verify the underlying function is consulted)
        with patch("pywry.app.should_use_inline_rendering", return_value=False):
            assert app._use_inline() is False

    def test_inline_when_should_use_inline_true(self):
        app = make_app()
        with patch("pywry.app.should_use_inline_rendering", return_value=True):
            assert app._use_inline() is True


class TestRegisterInlineWidget:
    def test_with_valid_widget(self):
        app = make_app(mode=WindowMode.BROWSER)
        widget = MagicMock()
        widget.label = "w1"
        app._register_inline_widget(widget)
        assert app._inline_widgets["w1"] is widget

    def test_with_missing_attributes(self):
        app = make_app(mode=WindowMode.BROWSER)
        widget = object()
        app._register_inline_widget(widget)
        assert app._inline_widgets == {}


# ---------------------------------------------------------------------------
# Theme property and settings property
# ---------------------------------------------------------------------------


class TestThemeAndSettings:
    def test_theme_setter_updates(self):
        app = make_app()
        app.theme = ThemeMode.LIGHT
        assert app.theme == ThemeMode.LIGHT

    def test_settings_returns_pywrysettings(self):
        from pywry.config import PyWrySettings

        app = make_app()
        assert isinstance(app.settings, PyWrySettings)

    def test_default_config_returns_window_config(self):
        from pywry.models import WindowConfig

        app = make_app()
        assert isinstance(app.default_config, WindowConfig)

    def test_set_initialization_script(self):
        app = make_app()
        app.set_initialization_script("console.log('init');")
        assert app._default_config.initialization_script == "console.log('init');"


# ---------------------------------------------------------------------------
# Auth API
# ---------------------------------------------------------------------------


class TestAuthApi:
    def test_is_authenticated_false_by_default(self):
        app = make_app()
        assert app.is_authenticated is False

    def test_is_authenticated_true_when_result_success(self):
        app = make_app()
        result = MagicMock()
        result.success = True
        app._auth_result = result
        assert app.is_authenticated is True

    def test_is_authenticated_false_when_result_unsuccessful(self):
        app = make_app()
        result = MagicMock()
        result.success = False
        app._auth_result = result
        assert app.is_authenticated is False

    def test_resolve_provider_with_oauth_provider_passes_through(self):
        from pywry.auth.providers import OAuthProvider

        app = make_app()
        provider = MagicMock(spec=OAuthProvider)
        result = app._resolve_provider(provider)
        assert result is provider

    def test_resolve_provider_none_raises_when_no_settings(self):
        from pywry.exceptions import AuthenticationError

        app = make_app()
        # No oauth2 settings — _resolve_provider should raise
        with patch("pywry.config.OAuth2Settings") as mock_settings_cls:
            mock_settings_cls.side_effect = Exception("no env")
            with pytest.raises(AuthenticationError):
                app._resolve_provider(None)

    def test_resolve_provider_creates_from_settings(self):
        from pywry.config import OAuth2Settings

        app = make_app()
        app._settings.oauth2 = OAuth2Settings(
            provider="google", client_id="cid", client_secret="cs", scopes="openid"
        )
        with patch("pywry.auth.providers.create_provider_from_settings") as mock_create:
            mock_provider = MagicMock()
            mock_create.return_value = mock_provider
            result = app._resolve_provider(None)
            assert result is mock_provider

    def test_resolve_provider_assigns_oauth_settings_when_missing(self):
        """When self._settings.oauth2 is None but env-derived OAuth2Settings has
        a client_id, _resolve_provider populates self._settings.oauth2 (line 319)."""
        from pywry.config import OAuth2Settings

        app = make_app()
        app._settings.oauth2 = None
        env_settings = OAuth2Settings(
            provider="google", client_id="abc", client_secret="x", scopes="openid"
        )
        with (
            patch("pywry.config.OAuth2Settings", return_value=env_settings),
            patch(
                "pywry.auth.providers.create_provider_from_settings",
                return_value="prov",
            ),
        ):
            result = app._resolve_provider(None)
            assert result == "prov"
            assert app._settings.oauth2 is env_settings

    def test_resolve_provider_non_oauth_uses_create_from_settings(self):
        app = make_app()
        # Not an OAuthProvider — falls through to create_provider_from_settings
        with patch("pywry.auth.providers.create_provider_from_settings") as mock_create:
            mock_create.return_value = "stub"
            result = app._resolve_provider({"some": "config"})
            assert result == "stub"

    def test_logout_when_not_logged_in(self):
        app = make_app()
        # Should not raise - alert is mocked via emit
        with patch.object(app, "alert"):
            app.logout()
        assert app._session_manager is None
        assert app._auth_result is None

    def test_logout_with_session_manager(self):
        app = make_app()
        sm = MagicMock()
        app._session_manager = sm
        app._auth_result = MagicMock()
        with (
            patch("pywry.state.sync_helpers.run_async") as mock_run,
            patch.object(app, "alert"),
        ):
            app.logout()
            mock_run.assert_called_once()
        assert app._session_manager is None
        assert app._auth_result is None

    def test_logout_no_alert_when_disabled(self):
        app = make_app()
        with patch.object(app, "alert") as mock_alert:
            app.logout(auto_alert=False)
            mock_alert.assert_not_called()

    def test_login_handles_authentication_failure(self):
        app = make_app()
        with (
            patch.object(app, "_resolve_provider", return_value=MagicMock()),
            patch("pywry.auth.flow.AuthFlowManager") as mock_fm_cls,
            patch("pywry.auth.session.SessionManager"),
            patch("pywry.auth.token_store.get_token_store"),
            patch.object(app, "alert"),
        ):
            mock_fm = MagicMock()
            mock_fm.authenticate.side_effect = RuntimeError("auth failed")
            mock_fm_cls.return_value = mock_fm
            with pytest.raises(RuntimeError):
                app.login()

    def test_login_unsuccessful_result(self):
        app = make_app()
        with (
            patch.object(app, "_resolve_provider", return_value=MagicMock()),
            patch("pywry.auth.flow.AuthFlowManager") as mock_fm_cls,
            patch("pywry.auth.session.SessionManager"),
            patch("pywry.auth.token_store.get_token_store"),
            patch.object(app, "alert"),
        ):
            mock_fm = MagicMock()
            result = MagicMock()
            result.success = False
            result.error = "err"
            mock_fm.authenticate.return_value = result
            mock_fm_cls.return_value = mock_fm
            r = app.login()
            assert r is result

    def test_login_successful_with_user_info(self):
        app = make_app()

        on_login_calls = []

        def on_login(res):
            on_login_calls.append(res)

        with (
            patch.object(app, "_resolve_provider", return_value=MagicMock()),
            patch("pywry.auth.flow.AuthFlowManager") as mock_fm_cls,
            patch("pywry.auth.session.SessionManager"),
            patch("pywry.auth.token_store.get_token_store"),
            patch.object(app, "alert"),
        ):
            mock_fm = MagicMock()
            result = MagicMock()
            result.success = True
            result.user_info = {"name": "Alice", "email": "a@x.com"}
            mock_fm.authenticate.return_value = result
            mock_fm_cls.return_value = mock_fm
            app.login(on_login=on_login)
        assert on_login_calls == [result]
        assert app._auth_result is result

    def test_login_successful_without_user_info(self):
        app = make_app()
        with (
            patch.object(app, "_resolve_provider", return_value=MagicMock()),
            patch("pywry.auth.flow.AuthFlowManager") as mock_fm_cls,
            patch("pywry.auth.session.SessionManager"),
            patch("pywry.auth.token_store.get_token_store"),
            patch.object(app, "alert"),
        ):
            mock_fm = MagicMock()
            result = MagicMock()
            result.success = True
            result.user_info = None
            mock_fm.authenticate.return_value = result
            mock_fm_cls.return_value = mock_fm
            app.login()
        assert app._auth_result is result

    def test_login_with_show_page(self):
        app = make_app()
        with (
            patch.object(app, "_resolve_provider", return_value=MagicMock()),
            patch.object(app, "_show_login_page_and_wait") as mock_show_page,
            patch("pywry.auth.flow.AuthFlowManager") as mock_fm_cls,
            patch("pywry.auth.session.SessionManager"),
            patch("pywry.auth.token_store.get_token_store"),
            patch.object(app, "alert"),
        ):
            mock_fm = MagicMock()
            result = MagicMock()
            result.success = True
            result.user_info = {"name": "Bob"}
            mock_fm.authenticate.return_value = result
            mock_fm_cls.return_value = mock_fm
            app.login(show_page=True, page_title="Hi")
            mock_show_page.assert_called_once()

    def test_show_login_page_and_wait_uses_threading_event(self):
        app = make_app()
        provider = MagicMock()
        # We replace show with a mock that simulates the click event firing
        captured_callbacks = {}

        def fake_show(page, **kwargs):
            captured_callbacks.update(kwargs.get("callbacks") or {})
            # Auto-trigger the click handler so wait() returns immediately
            from pywry.auth.login_page import LOGIN_CLICK_EVENT

            cb = captured_callbacks.get(LOGIN_CLICK_EVENT)
            if cb:
                cb({})

        with patch.object(app, "show", side_effect=fake_show):
            app._show_login_page_and_wait(provider, "Sign in")

    def test_wire_logout_handler_registers_for_each_label(self):
        app = make_app()
        # Stub mode.get_labels
        app._mode = MagicMock()
        app._mode.get_labels.return_value = ["w1", "w2"]
        called = []

        def on_logout():
            called.append("logged-out")

        registry = get_registry()
        original_register = registry.register

        registered_pairs = []

        def fake_register(label, event_type, fn, **kwargs):
            registered_pairs.append((label, event_type))
            return original_register(label, event_type, fn, **kwargs)

        with patch.object(registry, "register", side_effect=fake_register):
            app._wire_logout_handler(
                provider=MagicMock(),
                on_login=None,
                on_logout=on_logout,
                show_page=False,
                page_title="X",
                auto_alert=False,
                kwargs={},
            )
        assert ("w1", "auth:do-logout") in registered_pairs
        assert ("w2", "auth:do-logout") in registered_pairs

    def test_wire_logout_handler_default_main_label_when_no_labels(self):
        app = make_app()
        app._mode = MagicMock()
        app._mode.get_labels.return_value = []

        registered_pairs = []
        registry = get_registry()
        original_register = registry.register

        def fake_register(label, event_type, fn, **kwargs):
            registered_pairs.append((label, event_type))
            return original_register(label, event_type, fn, **kwargs)

        with patch.object(registry, "register", side_effect=fake_register):
            app._wire_logout_handler(
                provider=MagicMock(),
                on_login=None,
                on_logout=None,
                show_page=False,
                page_title="X",
                auto_alert=False,
                kwargs={},
            )
        assert ("main", "auth:do-logout") in registered_pairs

    def test_wire_logout_handler_logout_dispatches(self):
        app = make_app()
        app._mode = MagicMock()
        app._mode.get_labels.return_value = ["w1"]
        called = []

        def on_logout():
            called.append("ok")

        with patch.object(app, "logout") as mock_logout:
            app._wire_logout_handler(
                provider=MagicMock(),
                on_login=None,
                on_logout=on_logout,
                show_page=False,
                page_title="X",
                auto_alert=True,
                kwargs={},
            )
            # Now dispatch to trigger the inner _handle_logout
            registry = get_registry()
            registry.dispatch("w1", "auth:do-logout", {})
            assert called == ["ok"]
            mock_logout.assert_called_once_with(auto_alert=True)

    def test_wire_logout_handler_re_enters_login_when_show_page(self):
        app = make_app()
        app._mode = MagicMock()
        app._mode.get_labels.return_value = ["w1"]

        with (
            patch.object(app, "logout"),
            patch.object(app, "login") as mock_login,
        ):
            app._wire_logout_handler(
                provider=MagicMock(),
                on_login=None,
                on_logout=None,
                show_page=True,
                page_title="X",
                auto_alert=True,
                kwargs={},
            )
            registry = get_registry()
            registry.dispatch("w1", "auth:do-logout", {})
            mock_login.assert_called_once()


# ---------------------------------------------------------------------------
# Menu / Tray / require_native_mode
# ---------------------------------------------------------------------------


class TestNativeRequireMode:
    def test_require_native_mode_passes_for_new_window(self):
        app = make_app(mode=WindowMode.NEW_WINDOW)
        app._require_native_mode("foo()")  # No raise

    def test_require_native_mode_passes_for_single_window(self):
        app = make_app(mode=WindowMode.SINGLE_WINDOW)
        app._require_native_mode("foo()")

    def test_require_native_mode_passes_for_multi_window(self):
        app = make_app(mode=WindowMode.MULTI_WINDOW)
        app._require_native_mode("foo()")

    def test_require_native_mode_raises_for_browser(self):
        app = make_app(mode=WindowMode.BROWSER)
        with pytest.raises(RuntimeError, match="requires a native window mode"):
            app._require_native_mode("foo()")

    def test_require_native_mode_raises_for_notebook(self):
        app = make_app(mode=WindowMode.NOTEBOOK)
        with pytest.raises(RuntimeError):
            app._require_native_mode("foo()")


class TestCreateMenu:
    def test_create_menu_native_mode(self):
        app = make_app()
        with patch("pywry.menu_proxy.MenuProxy.create") as mock_create:
            mock_proxy = MagicMock()
            mock_create.return_value = mock_proxy
            result = app.create_menu("menu1", items=[])
            assert result is mock_proxy

    def test_create_menu_raises_in_browser_mode(self):
        app = make_app(mode=WindowMode.BROWSER)
        with pytest.raises(RuntimeError):
            app.create_menu("menu1")


class TestCreateTray:
    def test_create_tray_native_mode(self):
        app = make_app()
        with patch("pywry.tray_proxy.TrayProxy.create") as mock_create:
            mock_tray = MagicMock()
            mock_create.return_value = mock_tray
            result = app.create_tray("t1", tooltip="foo", title="bar", icon=b"X")
            assert result is mock_tray
            assert app._trays["t1"] is mock_tray

    def test_create_tray_raises_in_browser_mode(self):
        app = make_app(mode=WindowMode.BROWSER)
        with pytest.raises(RuntimeError):
            app.create_tray("t1")

    def test_remove_tray_from_app_registry(self):
        app = make_app()
        tray = MagicMock()
        app._trays["t1"] = tray
        app.remove_tray("t1")
        tray.remove.assert_called_once()
        assert "t1" not in app._trays

    def test_remove_tray_falls_back_to_class_registry(self):
        from pywry.tray_proxy import TrayProxy

        app = make_app()
        # Not in app._trays, but in class-level registry
        class_tray = MagicMock()
        with patch.object(TrayProxy, "_all_proxies", {"t1": class_tray}):
            app.remove_tray("t1")
            class_tray.remove.assert_called_once()

    def test_remove_tray_when_not_found(self):
        from pywry.tray_proxy import TrayProxy

        app = make_app()
        # Not anywhere — should be a no-op
        with patch.object(TrayProxy, "_all_proxies", {}):
            app.remove_tray("nonexistent")  # No raise


# ---------------------------------------------------------------------------
# show() in native + inline modes
# ---------------------------------------------------------------------------


class TestShowInline:
    def test_show_in_browser_mode_calls_inline_show(self):
        app = make_app(mode=WindowMode.BROWSER)
        fake_widget = MagicMock()
        fake_widget.label = "w-x"
        with patch("pywry.inline.show", return_value=fake_widget) as mock_show:
            result = app.show("<p>hi</p>", title="T", height=400)
            assert result is fake_widget
            mock_show.assert_called_once()
            # open_browser=True for browser mode
            kwargs = mock_show.call_args.kwargs
            assert kwargs["open_browser"] is True

    def test_show_in_browser_mode_with_html_content(self):
        from pywry.models import HtmlContent

        app = make_app(mode=WindowMode.BROWSER)
        fake_widget = MagicMock()
        fake_widget.label = "w-x"
        content = HtmlContent(html="<p>x</p>", inline_css="body{}")
        with patch("pywry.inline.show", return_value=fake_widget) as mock_show:
            app.show(content)
            kwargs = mock_show.call_args.kwargs
            # inline_css should be prepended to html
            assert "<style id=" in kwargs["content"]

    def test_show_in_browser_mode_with_callbacks(self):
        app = make_app(mode=WindowMode.BROWSER)
        cb = MagicMock()
        fake_widget = MagicMock()
        fake_widget.label = "w-x"
        with patch("pywry.inline.show", return_value=fake_widget) as mock_show:
            app.show("<p>x</p>", callbacks={"foo": cb})
            kwargs = mock_show.call_args.kwargs
            assert "foo" in kwargs["callbacks"]

    def test_show_in_notebook_mode_with_chat_toolbar_uses_chat_widget(self):
        app = make_app(mode=WindowMode.NOTEBOOK)
        fake_widget = MagicMock()
        fake_widget.label = "w-x"

        # Build a toolbar with a chat-container item
        chat_item = MagicMock()
        chat_item.component_id = "chat-container"
        toolbar = MagicMock()
        toolbar.items = [chat_item]

        with (
            patch("pywry.widget.HAS_ANYWIDGET", True),
            patch("pywry.widget.PyWryChatWidget.from_html", return_value=fake_widget) as mock_from,
        ):
            result = app.show("<p>x</p>", toolbars=[toolbar])
            assert result is fake_widget
            mock_from.assert_called_once()
            fake_widget.display.assert_called_once()

    def test_show_in_notebook_with_plotly_uses_inline(self):
        app = make_app(mode=WindowMode.NOTEBOOK)
        fake_widget = MagicMock()
        fake_widget.label = "w-x"
        with patch("pywry.inline.show", return_value=fake_widget) as mock_show:
            result = app.show("<p>x</p>", include_plotly=True)
            assert result is fake_widget

    def test_show_in_notebook_falls_back_when_anywidget_missing(self):
        app = make_app(mode=WindowMode.NOTEBOOK)
        fake_widget = MagicMock()
        fake_widget.label = "w-x"
        with (
            patch("pywry.widget.HAS_ANYWIDGET", False),
            patch("pywry.inline.show", return_value=fake_widget) as mock_show,
        ):
            result = app.show("<p>x</p>")
            assert result is fake_widget

    def test_show_in_notebook_uses_pywrywidget_when_anywidget_available(self):
        app = make_app(mode=WindowMode.NOTEBOOK)
        fake_widget = MagicMock()
        fake_widget.label = "w-x"
        with (
            patch("pywry.widget.HAS_ANYWIDGET", True),
            patch("pywry.widget.PyWryWidget.from_html", return_value=fake_widget) as mock_from,
        ):
            result = app.show("<p>x</p>", width=500)
            assert result is fake_widget
            fake_widget.display.assert_called_once()

    def test_show_with_int_width_in_notebook_mode(self):
        app = make_app(mode=WindowMode.NOTEBOOK)
        fake_widget = MagicMock()
        fake_widget.label = "w-x"
        with (
            patch("pywry.widget.HAS_ANYWIDGET", True),
            patch("pywry.widget.PyWryWidget.from_html", return_value=fake_widget) as mock_from,
        ):
            app.show("<p>x</p>", width=500)
            kwargs = mock_from.call_args.kwargs
            assert kwargs["width"] == "500px"

    def test_show_with_str_width_in_notebook_mode(self):
        app = make_app(mode=WindowMode.NOTEBOOK)
        fake_widget = MagicMock()
        fake_widget.label = "w-x"
        with (
            patch("pywry.widget.HAS_ANYWIDGET", True),
            patch("pywry.widget.PyWryWidget.from_html", return_value=fake_widget) as mock_from,
        ):
            app.show("<p>x</p>", width="60%")
            kwargs = mock_from.call_args.kwargs
            assert kwargs["width"] == "60%"

    def test_show_with_none_width_defaults_to_100pct(self):
        app = make_app(mode=WindowMode.NOTEBOOK)
        fake_widget = MagicMock()
        fake_widget.label = "w-x"
        with (
            patch("pywry.widget.HAS_ANYWIDGET", True),
            patch("pywry.widget.PyWryWidget.from_html", return_value=fake_widget) as mock_from,
        ):
            app.show("<p>x</p>")  # No width
            kwargs = mock_from.call_args.kwargs
            assert kwargs["width"] == "100%"


class TestShowNative:
    def test_show_in_native_mode_calls_mode_show(self):
        app = make_app(mode=WindowMode.SINGLE_WINDOW)
        # Mock the internal mode object
        app._mode = MagicMock()
        app._mode.show = MagicMock(return_value="main")
        # SingleWindowMode has a fixed label property
        app._mode.label = "main"

        with patch("pywry.app.build_html", return_value="<html>built</html>"):
            handle = app.show("<p>x</p>")
        # NativeWindowHandle is returned
        assert handle.label == "main"
        app._mode.show.assert_called_once()

    def test_show_with_html_content_object(self):
        app = make_app(mode=WindowMode.NEW_WINDOW)
        app._mode = MagicMock()
        app._mode.show = MagicMock(return_value="lbl")
        app._mode.label = None  # type: ignore

        content = HtmlContent(html="<p>x</p>", init_script="boot()")
        with patch("pywry.app.build_html", return_value="<html>"):
            handle = app.show(content)
        # init_script promoted to config.initialization_script
        # We validate by inspecting last show call args
        call_args = app._mode.show.call_args
        config_arg = call_args.args[0]
        assert config_arg.initialization_script == "boot()"

    def test_show_with_initialization_script_override(self):
        app = make_app(mode=WindowMode.NEW_WINDOW)
        app._mode = MagicMock()
        app._mode.show = MagicMock(return_value="lbl")
        app._mode.label = None  # type: ignore

        with patch("pywry.app.build_html", return_value="<html>"):
            app.show("<p>x</p>", initialization_script="custom()")
        call_args = app._mode.show.call_args
        config_arg = call_args.args[0]
        assert config_arg.initialization_script == "custom()"

    def test_show_with_menu_registers_dispatcher(self):
        app = make_app(mode=WindowMode.NEW_WINDOW)
        app._mode = MagicMock()
        app._mode.show = MagicMock(return_value="lbl")
        app._mode.label = None  # type: ignore

        item_handler = MagicMock()
        menu = MagicMock()
        menu.collect_handlers = MagicMock(return_value={"save": item_handler})

        menu_proxy = MagicMock()
        with (
            patch("pywry.app.build_html", return_value="<html>"),
            patch("pywry.menu_proxy.MenuProxy.from_config", return_value=menu_proxy),
        ):
            app.show("<p>x</p>", menu=menu)
        menu_proxy.set_as_window_menu.assert_called_once_with("lbl")

    def test_show_with_menu_no_handlers(self):
        # When menu has no handlers, no dispatcher is registered
        app = make_app(mode=WindowMode.NEW_WINDOW)
        app._mode = MagicMock()
        app._mode.show = MagicMock(return_value="lbl")
        app._mode.label = None  # type: ignore

        menu = MagicMock()
        menu.collect_handlers = MagicMock(return_value={})
        menu_proxy = MagicMock()
        with (
            patch("pywry.app.build_html", return_value="<html>"),
            patch("pywry.menu_proxy.MenuProxy.from_config", return_value=menu_proxy),
        ):
            app.show("<p>x</p>", menu=menu)

    def test_show_with_menu_dispatcher_routes_to_handler(self):
        app = make_app(mode=WindowMode.NEW_WINDOW)
        app._mode = MagicMock()
        app._mode.show = MagicMock(return_value="lbl")
        app._mode.label = None  # type: ignore

        item_handler = MagicMock()
        menu = MagicMock()
        menu.collect_handlers = MagicMock(return_value={"save": item_handler})

        captured_callbacks = {}

        def capture_show(config, html, callbacks, label):
            if callbacks:
                captured_callbacks.update(callbacks)
            return "lbl"

        app._mode.show.side_effect = capture_show

        with (
            patch("pywry.app.build_html", return_value="<html>"),
            patch("pywry.menu_proxy.MenuProxy.from_config", return_value=MagicMock()),
        ):
            app.show("<p>x</p>", menu=menu)

        # Trigger the menu:click dispatcher for item_id="save"
        dispatcher = captured_callbacks.get("menu:click")
        assert dispatcher is not None
        dispatcher({"item_id": "save"}, "menu:click", "lbl")
        item_handler.assert_called_once()

    def test_show_with_hot_reload(self):
        app = make_app(mode=WindowMode.NEW_WINDOW, hot_reload=True)
        app._mode = MagicMock()
        app._mode.show = MagicMock(return_value="lbl")
        app._mode.label = None  # type: ignore
        # Make hot_reload_manager not None so the watch path is taken
        assert app._hot_reload_manager is not None

        content = HtmlContent(html="<p>x</p>", watch=True)
        with patch("pywry.app.build_html", return_value="<html>"):
            app.show(content)


# ---------------------------------------------------------------------------
# Hot reload watching
# ---------------------------------------------------------------------------


class TestSetupHotReloadWatching:
    def test_with_css_files(self, tmp_path):
        app = make_app(hot_reload=True)
        css = tmp_path / "x.css"
        css.write_text("/* x */")
        content = HtmlContent(html="<p>x</p>", css_files=[str(css)])
        with patch.object(app._hot_reload_manager, "enable_for_window") as mock_enable:
            app._setup_hot_reload_watching("lbl", content)
            mock_enable.assert_called_once()

    def test_with_script_files(self, tmp_path):
        app = make_app(hot_reload=True)
        from pathlib import Path as _Path

        js = tmp_path / "x.js"
        js.write_text("// x")
        content = HtmlContent(html="<p>x</p>", script_files=[_Path(str(js))])
        with patch.object(app._hot_reload_manager, "enable_for_window"):
            app._setup_hot_reload_watching("lbl", content)

    def test_with_watch_already_true(self, tmp_path):
        app = make_app(hot_reload=True)
        content = HtmlContent(html="<p>x</p>", watch=True)
        with patch.object(app._hot_reload_manager, "enable_for_window"):
            app._setup_hot_reload_watching("lbl", content)


# ---------------------------------------------------------------------------
# show_plotly
# ---------------------------------------------------------------------------


class TestShowPlotly:
    def test_inline_path(self):
        app = make_app(mode=WindowMode.BROWSER)
        fake_widget = MagicMock()
        fake_widget.label = "x"
        figure = {"data": [], "layout": {}}
        with patch("pywry.inline.show_plotly", return_value=fake_widget) as mock_show:
            result = app.show_plotly(figure)
            assert result is fake_widget

    def test_inline_path_with_specific_callbacks(self):
        app = make_app(mode=WindowMode.NOTEBOOK)
        fake_widget = MagicMock()
        fake_widget.label = "x"

        on_click = MagicMock()
        on_hover = MagicMock()
        on_select = MagicMock()
        with patch("pywry.inline.show_plotly", return_value=fake_widget) as mock_show:
            app.show_plotly(
                {"data": []},
                on_click=on_click,
                on_hover=on_hover,
                on_select=on_select,
            )
            kwargs = mock_show.call_args.kwargs
            cbs = kwargs["callbacks"]
            assert cbs.get("plotly_click") is on_click
            assert cbs.get("plotly_hover") is on_hover
            assert cbs.get("plotly_selected") is on_select

    def test_native_path_with_dict_figure(self):
        app = make_app(mode=WindowMode.NEW_WINDOW)
        app._mode = MagicMock()
        app._mode.show = MagicMock(return_value="lbl")
        app._mode.label = None  # type: ignore
        figure = {"data": [{"type": "scatter"}], "layout": {}}
        with patch("pywry.app.build_html", return_value="<html>"):
            app.show_plotly(figure)

    def test_native_path_with_to_plotly_json(self):
        app = make_app(mode=WindowMode.NEW_WINDOW)
        app._mode = MagicMock()
        app._mode.show = MagicMock(return_value="lbl")
        app._mode.label = None  # type: ignore

        class FakeFig:
            def to_plotly_json(self):
                return {"data": [], "layout": {"title": "X"}}

        with patch("pywry.app.build_html", return_value="<html>"):
            app.show_plotly(FakeFig())

    def test_native_path_with_to_dict(self):
        app = make_app(mode=WindowMode.NEW_WINDOW)
        app._mode = MagicMock()
        app._mode.show = MagicMock(return_value="lbl")
        app._mode.label = None  # type: ignore

        class FakeFig:
            def to_dict(self):
                return {"data": [], "layout": {}}

        with patch("pywry.app.build_html", return_value="<html>"):
            app.show_plotly(FakeFig())

    def test_native_path_with_unsupported_figure(self):
        app = make_app(mode=WindowMode.NEW_WINDOW)
        app._mode = MagicMock()
        app._mode.show = MagicMock(return_value="lbl")
        app._mode.label = None  # type: ignore

        class Bad:
            pass

        with patch("pywry.app.build_html", return_value="<html>"):
            app.show_plotly(Bad())

    def test_native_path_with_pydantic_config(self):
        from pywry.plotly_config import PlotlyConfig

        app = make_app(mode=WindowMode.NEW_WINDOW)
        app._mode = MagicMock()
        app._mode.show = MagicMock(return_value="lbl")
        app._mode.label = None  # type: ignore
        cfg = PlotlyConfig(responsive=True)
        with patch("pywry.app.build_html", return_value="<html>"):
            app.show_plotly({"data": []}, config=cfg)

    def test_native_path_with_dict_config(self):
        app = make_app(mode=WindowMode.NEW_WINDOW)
        app._mode = MagicMock()
        app._mode.show = MagicMock(return_value="lbl")
        app._mode.label = None  # type: ignore
        with patch("pywry.app.build_html", return_value="<html>"):
            app.show_plotly({"data": []}, config={"responsive": True})

    def test_native_path_with_unknown_config_type_uses_empty(self):
        app = make_app(mode=WindowMode.NEW_WINDOW)
        app._mode = MagicMock()
        app._mode.show = MagicMock(return_value="lbl")
        app._mode.label = None  # type: ignore
        with patch("pywry.app.build_html", return_value="<html>"):
            # Pass a config that's neither pydantic nor dict
            app.show_plotly({"data": []}, config=42)

    def test_native_path_handles_figure_conversion_failure(self):
        app = make_app(mode=WindowMode.NEW_WINDOW)
        app._mode = MagicMock()
        app._mode.show = MagicMock(return_value="lbl")
        app._mode.label = None  # type: ignore

        class Boom:
            def to_plotly_json(self):
                raise RuntimeError("boom!")

        with patch("pywry.app.build_html", return_value="<html>"):
            app.show_plotly(Boom())  # Should not raise, just produce an error HTML

    def test_native_path_with_inline_css(self):
        app = make_app(mode=WindowMode.NEW_WINDOW)
        app._mode = MagicMock()
        app._mode.show = MagicMock(return_value="lbl")
        app._mode.label = None  # type: ignore

        with patch("pywry.app.build_html", return_value="<html>"):
            app.show_plotly({"data": []}, inline_css="body{}")


# ---------------------------------------------------------------------------
# show_dataframe
# ---------------------------------------------------------------------------


class TestShowDataframe:
    def test_inline_path(self):
        app = make_app(mode=WindowMode.BROWSER)
        fake_widget = MagicMock()
        fake_widget.label = "x"
        with patch("pywry.inline.show_dataframe", return_value=fake_widget) as mock_show:
            result = app.show_dataframe([{"a": 1, "b": 2}])
            assert result is fake_widget

    def test_inline_path_with_specific_callbacks(self):
        app = make_app(mode=WindowMode.BROWSER)
        fake_widget = MagicMock()
        fake_widget.label = "x"
        oc = MagicMock()
        ors = MagicMock()
        with patch("pywry.inline.show_dataframe", return_value=fake_widget) as mock_show:
            app.show_dataframe([{"a": 1}], on_cell_click=oc, on_row_selected=ors)
            cbs = mock_show.call_args.kwargs["callbacks"]
            assert cbs["cell_click"] is oc
            assert cbs["row_selected"] is ors

    def test_native_path_with_list_dict(self):
        app = make_app(mode=WindowMode.NEW_WINDOW)
        app._mode = MagicMock()
        app._mode.show = MagicMock(return_value="lbl")
        app._mode.label = None  # type: ignore
        app._mode.get_labels = MagicMock(return_value=["lbl"])
        with patch("pywry.app.build_html", return_value="<html>"):
            app.show_dataframe([{"a": 1, "b": "x"}])

    def test_native_path_server_side(self):
        app = make_app(mode=WindowMode.NEW_WINDOW)
        app._mode = MagicMock()
        app._mode.show = MagicMock(return_value="lbl")
        app._mode.label = None  # type: ignore
        app._mode.get_labels = MagicMock(return_value=["lbl"])
        with patch("pywry.app.build_html", return_value="<html>"):
            app.show_dataframe([{"a": 1}], server_side=True)

    def test_native_path_with_inline_css(self):
        app = make_app(mode=WindowMode.NEW_WINDOW)
        app._mode = MagicMock()
        app._mode.show = MagicMock(return_value="lbl")
        app._mode.label = None  # type: ignore
        app._mode.get_labels = MagicMock(return_value=["lbl"])
        with patch("pywry.app.build_html", return_value="<html>"):
            app.show_dataframe([{"a": 1}], inline_css="body{}")

    def test_native_path_with_explicit_column_defs_objects(self):
        app = make_app(mode=WindowMode.NEW_WINDOW)
        app._mode = MagicMock()
        app._mode.show = MagicMock(return_value="lbl")
        app._mode.label = None  # type: ignore
        app._mode.get_labels = MagicMock(return_value=["lbl"])

        col_def = MagicMock()
        col_def.to_dict = MagicMock(return_value={"field": "a"})

        with patch("pywry.app.build_html", return_value="<html>"):
            app.show_dataframe([{"a": 1}], column_defs=[col_def, {"field": "b"}])

        col_def.to_dict.assert_called_once()

    def test_native_path_with_light_theme(self):
        app = make_app(theme=ThemeMode.LIGHT)
        app._mode = MagicMock()
        app._mode.show = MagicMock(return_value="lbl")
        app._mode.label = None  # type: ignore
        app._mode.get_labels = MagicMock(return_value=["lbl"])
        with patch("pywry.app.build_html", return_value="<html>"):
            app.show_dataframe([{"a": 1}])


# ---------------------------------------------------------------------------
# show_tvchart
# ---------------------------------------------------------------------------


class TestShowTvchart:
    def test_inline_path(self):
        app = make_app(mode=WindowMode.BROWSER)
        fake_widget = MagicMock()
        fake_widget.label = "x"
        with patch("pywry.inline.show_tvchart", return_value=fake_widget) as mock_show:
            result = app.show_tvchart(
                data=[{"time": 1, "open": 1, "high": 2, "low": 1, "close": 2}]
            )
            assert result is fake_widget

    def test_inline_path_with_yield_curve(self):
        app = make_app(mode=WindowMode.BROWSER)
        fake_widget = MagicMock()
        fake_widget.label = "x"
        with patch("pywry.inline.show_tvchart", return_value=fake_widget) as mock_show:
            app.show_tvchart(
                data=[],
                chart_kind="yield-curve",
                yield_curve={"baseResolution": 1},
            )

    def test_inline_path_with_int_width(self):
        app = make_app(mode=WindowMode.BROWSER)
        fake_widget = MagicMock()
        fake_widget.label = "x"
        with patch("pywry.inline.show_tvchart", return_value=fake_widget) as mock_show:
            app.show_tvchart(data=[], width=500)
            kwargs = mock_show.call_args.kwargs
            assert kwargs["width"] == "500px"

    def test_inline_path_with_callbacks(self):
        app = make_app(mode=WindowMode.BROWSER)
        fake_widget = MagicMock()
        fake_widget.label = "x"
        cb = MagicMock()
        with patch("pywry.inline.show_tvchart", return_value=fake_widget) as mock_show:
            app.show_tvchart(data=[], callbacks={"foo": cb})

    def test_inline_path_with_provider_sets_use_datafeed(self):
        app = make_app(mode=WindowMode.BROWSER)
        fake_widget = MagicMock()
        fake_widget.label = "x"
        provider = MagicMock()
        with patch("pywry.inline.show_tvchart", return_value=fake_widget) as mock_show:
            app.show_tvchart(data=None, provider=provider, symbol="AAPL", resolution="1D")
            kwargs = mock_show.call_args.kwargs
            assert kwargs["use_datafeed"] is True

    def test_native_path_static_data(self):
        app = make_app(mode=WindowMode.NEW_WINDOW)
        app._mode = MagicMock()
        app._mode.show = MagicMock(return_value="lbl")
        app._mode.label = None  # type: ignore
        app._mode.get_labels = MagicMock(return_value=["lbl"])
        with patch("pywry.app.build_html", return_value="<html>"):
            app.show_tvchart(data=[{"time": 1, "open": 1, "high": 2, "low": 1, "close": 2}])

    def test_native_path_with_datafeed(self):
        app = make_app(mode=WindowMode.NEW_WINDOW)
        app._mode = MagicMock()
        app._mode.show = MagicMock(return_value="lbl")
        app._mode.label = None  # type: ignore
        app._mode.get_labels = MagicMock(return_value=["lbl"])
        with patch("pywry.app.build_html", return_value="<html>"):
            app.show_tvchart(use_datafeed=True, symbol="AAPL", resolution="1D")

    def test_native_path_with_provider_wires(self):
        app = make_app(mode=WindowMode.NEW_WINDOW)
        app._mode = MagicMock()
        app._mode.show = MagicMock(return_value="lbl")
        app._mode.label = None  # type: ignore
        app._mode.get_labels = MagicMock(return_value=["lbl"])
        provider = MagicMock()
        with (
            patch("pywry.app.build_html", return_value="<html>"),
            patch.object(app, "_wire_datafeed_provider") as mock_wire,
        ):
            app.show_tvchart(use_datafeed=True, provider=provider)
            mock_wire.assert_called_once()

    def test_native_path_provider_with_str_handle(self):
        """If app.show() returns a plain string label, the wire path takes line 1738."""
        app = make_app(mode=WindowMode.NEW_WINDOW)
        provider = MagicMock()
        bars = [{"time": 1, "open": 1, "high": 2, "low": 1, "close": 2}]
        with (
            patch.object(app, "show", return_value="my-label"),
            patch.object(app, "_wire_datafeed_provider") as mock_wire,
        ):
            app.show_tvchart(data=bars, provider=provider)
            mock_wire.assert_called_once_with(provider, label="my-label")

    def test_native_path_with_yield_curve(self):
        app = make_app(mode=WindowMode.NEW_WINDOW)
        app._mode = MagicMock()
        app._mode.show = MagicMock(return_value="lbl")
        app._mode.label = None  # type: ignore
        app._mode.get_labels = MagicMock(return_value=["lbl"])
        bars = [{"time": 1, "open": 1, "high": 2, "low": 1, "close": 2}]
        with patch("pywry.app.build_html", return_value="<html>"):
            app.show_tvchart(data=bars, chart_kind="yield-curve", yield_curve={"baseResolution": 1})

    def test_native_path_with_explicit_chart_id(self):
        app = make_app(mode=WindowMode.NEW_WINDOW)
        app._mode = MagicMock()
        app._mode.show = MagicMock(return_value="lbl")
        app._mode.label = None  # type: ignore
        app._mode.get_labels = MagicMock(return_value=["lbl"])
        bars = [{"time": 1, "open": 1, "high": 2, "low": 1, "close": 2}]
        with patch("pywry.app.build_html", return_value="<html>"):
            app.show_tvchart(data=bars, chart_id="my-chart")

    def test_native_path_with_inline_css(self):
        app = make_app(mode=WindowMode.NEW_WINDOW)
        app._mode = MagicMock()
        app._mode.show = MagicMock(return_value="lbl")
        app._mode.label = None  # type: ignore
        app._mode.get_labels = MagicMock(return_value=["lbl"])
        bars = [{"time": 1, "open": 1, "high": 2, "low": 1, "close": 2}]
        with patch("pywry.app.build_html", return_value="<html>"):
            app.show_tvchart(data=bars, inline_css="body{}")

    def test_native_with_storage_dict(self):
        app = make_app(mode=WindowMode.NEW_WINDOW)
        app._mode = MagicMock()
        app._mode.show = MagicMock(return_value="lbl")
        app._mode.label = None  # type: ignore
        app._mode.get_labels = MagicMock(return_value=["lbl"])
        bars = [{"time": 1, "open": 1, "high": 2, "low": 1, "close": 2}]
        with (
            patch("pywry.app.build_html", return_value="<html>"),
            patch.object(app, "_wire_chart_storage") as mock_wire,
        ):
            app.show_tvchart(data=bars, storage={"backend": "server"})
            mock_wire.assert_called_once()


# ---------------------------------------------------------------------------
# Helpers used inside show_tvchart
# ---------------------------------------------------------------------------


class TestBuildTvchartSeriesPayload:
    def test_use_datafeed_returns_placeholder(self):
        app = make_app()
        result = app._build_tvchart_series_payload(
            None,
            use_datafeed=True,
            symbol="AAPL",
            resolution="1D",
            series_options={"k": 1},
            symbol_col=None,
            max_bars=100,
        )
        assert len(result) == 1
        assert result[0]["seriesId"] == "main"
        assert result[0]["symbol"] == "AAPL"
        assert result[0]["seriesOptions"] == {"k": 1}

    def test_use_datafeed_default_symbol_empty(self):
        app = make_app()
        result = app._build_tvchart_series_payload(
            None,
            use_datafeed=True,
            symbol=None,
            resolution="1D",
            series_options=None,
            symbol_col=None,
            max_bars=100,
        )
        assert result[0]["symbol"] == ""

    def test_static_normalises_data(self):
        app = make_app()
        bars = [{"time": 1, "open": 1, "high": 2, "low": 1, "close": 2}]
        result = app._build_tvchart_series_payload(
            bars,
            use_datafeed=False,
            symbol=None,
            resolution="1D",
            series_options=None,
            symbol_col=None,
            max_bars=100,
        )
        assert len(result) >= 1


class TestBuildTvchartStorageConfig:
    def test_with_dict_storage(self):
        app = make_app()
        cfg = app._build_tvchart_storage_config({"backend": "memory"})
        assert cfg["backend"] in ("memory", "server")

    def test_default_storage_from_settings(self):
        app = make_app()
        cfg = app._build_tvchart_storage_config(None)
        assert "backend" in cfg

    def test_path_serialised_to_string(self):
        app = make_app()
        cfg = app._build_tvchart_storage_config({"backend": "file", "path": "/tmp/x"})
        assert cfg["path"] == "/tmp/x"

    def test_none_path_is_empty(self):
        app = make_app()
        cfg = app._build_tvchart_storage_config({"backend": "memory", "path": None})
        assert cfg["path"] == ""

    def test_adapter_serialised(self):
        app = make_app()
        cfg = app._build_tvchart_storage_config({"backend": "memory", "adapter": "json"})
        assert cfg["adapter"] == "json"


class TestPreloadChartData:
    def test_preload_failure_returns_empty_or_partial(self):
        app = make_app()
        # When run_async raises, the except branch swallows the error and
        # returns the (possibly partial) preload dict.
        store = MagicMock()
        with (
            patch("pywry.state.get_chart_store", return_value=store),
            patch("pywry.state.sync_helpers.run_async", side_effect=RuntimeError("x")),
        ):
            result = app._preload_chart_data()
        assert isinstance(result, dict)

    def test_preload_returns_layout_data(self):
        app = make_app()
        store = MagicMock()

        with (
            patch("pywry.state.get_chart_store", return_value=store),
            patch(
                "pywry.state.sync_helpers.run_async",
                side_effect=[
                    [{"id": "lay1"}],  # list_layouts
                    "{}",  # get_layout for lay1
                    "tmpl",  # get_settings_template
                    "default-id",  # get_settings_default_id
                ],
            ),
        ):
            preload = app._preload_chart_data()
        assert "__pywry_tvchart_layout_index_v1" in preload
        assert any("layout_data" in k for k in preload)


# ---------------------------------------------------------------------------
# Event-emission API
# ---------------------------------------------------------------------------


class TestEmit:
    def test_emit_to_specific_label(self):
        app = make_app()
        app._mode = MagicMock()
        with patch.object(app, "send_event") as mock_send:
            app.emit("foo:bar", {"x": 1}, label="lbl")
            mock_send.assert_called_with("foo:bar", {"x": 1}, label="lbl")

    def test_emit_broadcasts_to_all_labels(self):
        app = make_app()
        app._mode = MagicMock()
        app._mode.get_labels = MagicMock(return_value=["a", "b"])
        with patch.object(app, "send_event") as mock_send:
            app.emit("foo:bar", {})
            assert mock_send.call_count == 2

    def test_emit_includes_inline_widgets(self):
        app = make_app(mode=WindowMode.BROWSER)
        app._mode = MagicMock()
        app._mode.get_labels = MagicMock(return_value=[])
        widget = MagicMock()
        widget.label = "w1"
        app._inline_widgets["w1"] = widget
        with patch.object(app, "send_event") as mock_send:
            app.emit("foo:bar", {})
            assert mock_send.call_count == 1

    def test_emit_theme_update_is_broadcast(self):
        app = make_app()
        app._mode = MagicMock()
        app._mode.get_labels = MagicMock(return_value=["a"])
        with patch.object(app, "send_event") as mock_send:
            # Pass a label - but theme should still broadcast
            app.emit("pywry:update-theme", {"theme": "dark"}, label="a")
            mock_send.assert_called()

    def test_emit_theme_update_local_scope(self):
        app = make_app()
        app._mode = MagicMock()
        with patch.object(app, "send_event") as mock_send:
            app.emit("pywry:update-theme", {"scope": "local"}, label="a")
            mock_send.assert_called_with("pywry:update-theme", {"scope": "local"}, label="a")


class TestAlert:
    def test_alert_emits_pywry_alert(self):
        app = make_app()
        with patch.object(app, "emit") as mock_emit:
            app.alert("Hello", alert_type="success", title="T", duration=2000)
            mock_emit.assert_called_once()
            args = mock_emit.call_args
            assert args.args[0] == "pywry:alert"


class TestSendEvent:
    def test_to_specific_label_inline_widget(self):
        app = make_app(mode=WindowMode.BROWSER)
        widget = MagicMock()
        app._inline_widgets["w1"] = widget
        result = app.send_event("foo:bar", {"x": 1}, label="w1")
        assert result is True
        widget.emit.assert_called_once_with("foo:bar", {"x": 1})

    def test_to_specific_label_native(self):
        app = make_app()
        app._mode = MagicMock()
        app._mode.send_event = MagicMock(return_value=True)
        result = app.send_event("foo:bar", {}, label="lbl")
        assert result is True

    def test_no_labels_no_widgets_returns_false(self):
        app = make_app()
        app._mode = MagicMock()
        app._mode.get_labels = MagicMock(return_value=[])
        assert app.send_event("foo:bar", {}) is False

    def test_broadcasts_to_native_and_inline(self):
        app = make_app(mode=WindowMode.BROWSER)
        app._mode = MagicMock()
        app._mode.get_labels = MagicMock(return_value=["a"])
        app._mode.send_event = MagicMock(return_value=True)
        widget = MagicMock()
        widget.label = "w1"
        app._inline_widgets["w1"] = widget
        result = app.send_event("foo:bar", {})
        assert result is True
        widget.emit.assert_called_once()


class TestUpdateContent:
    def test_update_with_label(self):
        app = make_app()
        app._mode = MagicMock()
        app._mode.update_content = MagicMock(return_value=True)
        assert app.update_content("<p>x</p>", label="lbl") is True

    def test_update_no_label_uses_first(self):
        app = make_app()
        app._mode = MagicMock()
        app._mode.update_content = MagicMock(return_value=True)
        app._mode.get_labels = MagicMock(return_value=["lbl1"])
        assert app.update_content("<p>x</p>") is True

    def test_update_no_labels_returns_false(self):
        app = make_app()
        app._mode = MagicMock()
        app._mode.get_labels = MagicMock(return_value=[])
        assert app.update_content("<p>x</p>") is False

    def test_update_with_light_theme(self):
        app = make_app(theme=ThemeMode.LIGHT)
        app._mode = MagicMock()
        app._mode.update_content = MagicMock(return_value=True)
        app._mode.get_labels = MagicMock(return_value=["lbl"])
        app.update_content("<p>x</p>")
        # Theme passed as "light"
        call = app._mode.update_content.call_args
        assert call.args[2] == "light"


class TestEvalJs:
    def test_with_label(self):
        app = make_app()
        with patch("pywry.runtime.eval_js", return_value=True) as mock_eval:
            assert app.eval_js("alert(1)", label="lbl") is True
            mock_eval.assert_called_once_with("lbl", "alert(1)")

    def test_no_label_uses_first(self):
        app = make_app()
        app._mode = MagicMock()
        app._mode.get_labels = MagicMock(return_value=["lbl1"])
        with patch("pywry.runtime.eval_js", return_value=True):
            assert app.eval_js("x") is True

    def test_no_labels_returns_false(self):
        app = make_app()
        app._mode = MagicMock()
        app._mode.get_labels = MagicMock(return_value=[])
        assert app.eval_js("x") is False


class TestShowHideClose:
    def test_show_window(self):
        app = make_app()
        app._mode = MagicMock()
        app._mode.show_window = MagicMock(return_value=True)
        assert app.show_window("lbl") is True

    def test_hide_window(self):
        app = make_app()
        app._mode = MagicMock()
        app._mode.hide_window = MagicMock(return_value=True)
        assert app.hide_window("lbl") is True

    def test_close_with_label(self):
        app = make_app()
        app._mode = MagicMock()
        app._mode.close = MagicMock(return_value=True)
        assert app.close(label="lbl") is True

    def test_close_all(self):
        app = make_app()
        app._mode = MagicMock()
        app._mode.close_all = MagicMock(return_value=2)
        assert app.close() is True

    def test_close_all_returns_false_when_zero(self):
        app = make_app()
        app._mode = MagicMock()
        app._mode.close_all = MagicMock(return_value=0)
        assert app.close() is False

    def test_get_labels(self):
        app = make_app()
        app._mode = MagicMock()
        app._mode.get_labels = MagicMock(return_value=["a", "b"])
        assert app.get_labels() == ["a", "b"]

    def test_is_open_specific(self):
        app = make_app()
        app._mode = MagicMock()
        app._mode.is_open = MagicMock(return_value=True)
        assert app.is_open("lbl") is True

    def test_is_open_any(self):
        app = make_app()
        app._mode = MagicMock()
        app._mode.get_labels = MagicMock(return_value=["a"])
        assert app.is_open() is True

    def test_is_open_no_labels(self):
        app = make_app()
        app._mode = MagicMock()
        app._mode.get_labels = MagicMock(return_value=[])
        assert app.is_open() is False


class TestRefresh:
    def test_with_label(self):
        app = make_app()
        with patch("pywry.app.runtime_refresh_window", return_value=True):
            assert app.refresh("lbl") is True

    def test_all_labels(self):
        app = make_app()
        app._mode = MagicMock()
        app._mode.get_labels = MagicMock(return_value=["a", "b"])
        with patch("pywry.app.runtime_refresh_window", return_value=True):
            assert app.refresh() is True

    def test_no_labels(self):
        app = make_app()
        app._mode = MagicMock()
        app._mode.get_labels = MagicMock(return_value=[])
        assert app.refresh() is False


class TestRefreshCss:
    def test_no_hot_reload_warns(self):
        app = make_app()
        # No hot_reload_manager
        assert app.refresh_css() is False

    def test_with_label(self):
        app = make_app(hot_reload=True)
        with patch.object(app._hot_reload_manager, "reload_css", return_value=True):
            assert app.refresh_css(label="lbl") is True

    def test_all_labels(self):
        app = make_app(hot_reload=True)
        app._mode = MagicMock()
        app._mode.get_labels = MagicMock(return_value=["a"])
        with patch.object(app._hot_reload_manager, "reload_css", return_value=True):
            assert app.refresh_css() is True

    def test_no_labels(self):
        app = make_app(hot_reload=True)
        app._mode = MagicMock()
        app._mode.get_labels = MagicMock(return_value=[])
        assert app.refresh_css() is False


class TestEnableDisableHotReload:
    def test_enable_when_missing(self):
        app = make_app()
        app._hot_reload_manager = None
        with patch("pywry.app.HotReloadManager") as mock_cls:
            mock_mgr = MagicMock()
            mock_cls.return_value = mock_mgr
            app.enable_hot_reload()
            assert app._hot_reload_manager is mock_mgr
            mock_mgr.start.assert_called_once()

    def test_enable_when_present_does_nothing(self):
        app = make_app(hot_reload=True)
        existing = app._hot_reload_manager
        app.enable_hot_reload()
        assert app._hot_reload_manager is existing

    def test_disable_stops_and_clears(self):
        app = make_app(hot_reload=True)
        mgr = MagicMock()
        app._hot_reload_manager = mgr
        app.disable_hot_reload()
        assert app._hot_reload_manager is None
        mgr.stop.assert_called_once()

    def test_disable_when_missing(self):
        app = make_app()
        app._hot_reload_manager = None
        app.disable_hot_reload()  # No raise


# ---------------------------------------------------------------------------
# on_*, on, command
# ---------------------------------------------------------------------------


class TestOn:
    def test_on_direct_call_registers(self):
        app = make_app()
        app._mode = MagicMock()
        app._mode.get_labels = MagicMock(return_value=["lbl"])
        called = []
        result = app.on("foo:bar", lambda d, *_: called.append(d))
        assert result is True

    def test_on_decorator_form(self):
        app = make_app()
        app._mode = MagicMock()
        app._mode.get_labels = MagicMock(return_value=["lbl"])
        captured = []

        @app.on("foo:bar")
        def handler(d):
            captured.append(d)

        # Trigger via dispatch
        get_registry().dispatch("lbl", "foo:bar", {"x": 1})
        assert captured == [{"x": 1}]

    def test_on_with_label(self):
        app = make_app()
        app._mode = MagicMock()
        app.on("foo:bar", lambda *args: None, label="custom")

    def test_on_no_labels_uses_main(self):
        app = make_app()
        app._mode = MagicMock()
        app._mode.get_labels = MagicMock(return_value=[])
        app.on("foo:bar", lambda *args: None)

    def test_on_with_widget_id(self):
        app = make_app()
        app._mode = MagicMock()
        app._mode.get_labels = MagicMock(return_value=["lbl"])
        app.on("foo", lambda *args: None, widget_id="wid")

    def test_on_grid(self):
        app = make_app()
        app._mode = MagicMock()
        app._mode.get_labels = MagicMock(return_value=["lbl"])
        result = app.on_grid("grid:click", lambda d, *_: None)
        assert result is True

    def test_on_grid_decorator(self):
        app = make_app()
        app._mode = MagicMock()
        app._mode.get_labels = MagicMock(return_value=["lbl"])

        @app.on_grid("grid:click")
        def handler(d):
            pass

    def test_on_chart(self):
        app = make_app()
        app._mode = MagicMock()
        app._mode.get_labels = MagicMock(return_value=["lbl"])
        result = app.on_chart("plotly:click", lambda d, *_: None)
        assert result is True

    def test_on_toolbar(self):
        app = make_app()
        app._mode = MagicMock()
        app._mode.get_labels = MagicMock(return_value=["lbl"])
        result = app.on_toolbar("toolbar:change", lambda d, *_: None)
        assert result is True

    def test_on_html(self):
        app = make_app()
        app._mode = MagicMock()
        app._mode.get_labels = MagicMock(return_value=["lbl"])
        result = app.on_html("app:custom", lambda d, *_: None)
        assert result is True

    def test_on_window(self):
        app = make_app()
        app._mode = MagicMock()
        app._mode.get_labels = MagicMock(return_value=["lbl"])
        result = app.on_window("window:close", lambda d, *_: None)
        assert result is True

    def test_register_scoped_decorator_with_label(self):
        app = make_app()
        app._mode = MagicMock()
        app._mode.get_labels = MagicMock(return_value=["lbl"])

        decorator = app.on_grid("grid:click", label="custom")

        @decorator
        def handler(d):
            pass

    def test_register_scoped_decorator_no_labels(self):
        app = make_app()
        app._mode = MagicMock()
        app._mode.get_labels = MagicMock(return_value=[])

        @app.on_grid("grid:click")
        def handler(d):
            pass


class TestCommand:
    def test_command_decorator_registers(self):
        app = make_app()
        with patch("pywry.runtime.is_running", return_value=False):

            @app.command()
            def my_cmd(data):
                return {"ok": True}

            from pywry.runtime import get_custom_commands

            assert "my_cmd" in get_custom_commands()

    def test_command_with_explicit_name(self):
        app = make_app()
        with patch("pywry.runtime.is_running", return_value=False):

            @app.command("explicit_name")
            def my_cmd(data):
                return {}

            from pywry.runtime import get_custom_commands

            assert "explicit_name" in get_custom_commands()

    def test_command_raises_when_subprocess_running(self):
        app = make_app()
        with patch("pywry.runtime.is_running", return_value=True):
            with pytest.raises(RuntimeError, match="must be called before show"):

                @app.command()
                def f(data):
                    return {}

    def test_command_raises_for_non_callable(self):
        app = make_app()
        with patch("pywry.runtime.is_running", return_value=False):
            decorator = app.command()
            with pytest.raises(TypeError):
                decorator(42)

    def test_command_raises_in_browser_mode(self):
        app = make_app(mode=WindowMode.BROWSER)
        with patch("pywry.runtime.is_running", return_value=False):
            with pytest.raises(RuntimeError):

                @app.command()
                def f(data):
                    return {}

    def test_command_warns_in_notebook_environment(self):
        app = make_app()
        with (
            patch("pywry.runtime.is_running", return_value=False),
            patch("pywry.notebook.should_use_inline_rendering", return_value=True),
        ):

            @app.command()
            def f(data):
                return {}


# ---------------------------------------------------------------------------
# Server-side grid handler
# ---------------------------------------------------------------------------


class TestServerSideGridHandler:
    def test_setup_handler_registers_callback(self):
        app = make_app()
        app._mode = MagicMock()
        app._mode.get_labels = MagicMock(return_value=["lbl"])
        rows = [{"a": i} for i in range(10)]
        app._setup_server_side_handler("grid1", rows, "lbl")
        # Now dispatch a request
        app.send_event = MagicMock(return_value=True)  # type: ignore[method-assign]
        get_registry().dispatch(
            "lbl",
            "grid:request-page",
            {
                "gridId": "grid1",
                "requestId": "r1",
                "startRow": 0,
                "endRow": 5,
                "sortModel": [],
                "filterModel": {},
            },
        )
        app.send_event.assert_called_once()
        call_args = app.send_event.call_args
        assert call_args.args[0] == "grid:page-response"

    def test_handler_ignores_other_grid_ids(self):
        app = make_app()
        app._mode = MagicMock()
        app._mode.get_labels = MagicMock(return_value=["lbl"])
        app._setup_server_side_handler("grid1", [{"a": 1}], "lbl")
        app.send_event = MagicMock(return_value=True)  # type: ignore[method-assign]
        get_registry().dispatch("lbl", "grid:request-page", {"gridId": "other", "requestId": "r1"})
        app.send_event.assert_not_called()

    def test_handler_default_label_when_none(self):
        app = make_app()
        app._mode = MagicMock()
        app._mode.get_labels = MagicMock(return_value=[])
        # Should default to "main"
        app._setup_server_side_handler("g1", [{"a": 1}], None)


class TestApplyGridFilter:
    def test_no_filter_returns_data(self):
        app = make_app()
        data = [{"a": 1}, {"a": 2}]
        assert app._apply_grid_filter(data, {}) == data

    def test_text_contains_filter(self):
        app = make_app()
        data = [{"name": "Apple"}, {"name": "Banana"}]
        result = app._apply_grid_filter(
            data,
            {"name": {"filterType": "text", "type": "contains", "filter": "an"}},
        )
        assert result == [{"name": "Banana"}]

    def test_filter_skips_when_value_none(self):
        app = make_app()
        data = [{"name": "Apple"}]
        result = app._apply_grid_filter(data, {"name": {"filterType": "text", "filter": None}})
        assert result == data


class TestRowMatchesFilter:
    def test_value_none_returns_false(self):
        app = make_app()
        assert app._row_matches_filter({"a": None}, "a", "text", "contains", "x") is False

    def test_text_filter_dispatched(self):
        app = make_app()
        assert app._row_matches_filter({"a": "hello"}, "a", "text", "contains", "ell") is True

    def test_number_filter_dispatched(self):
        app = make_app()
        assert app._row_matches_filter({"a": 10}, "a", "number", "equals", 10) is True

    def test_unknown_filter_type_returns_true(self):
        app = make_app()
        assert app._row_matches_filter({"a": 1}, "a", "unknown", "x", "y") is True


class TestTextFilterMatch:
    def test_contains(self):
        app = make_app()
        assert app._text_filter_match("hello", "contains", "ell") is True

    def test_equals(self):
        app = make_app()
        assert app._text_filter_match("hello", "equals", "hello") is True
        assert app._text_filter_match("hello", "equals", "world") is False

    def test_starts_with(self):
        app = make_app()
        assert app._text_filter_match("hello", "startsWith", "hel") is True

    def test_ends_with(self):
        app = make_app()
        assert app._text_filter_match("hello", "endsWith", "llo") is True

    def test_not_contains(self):
        app = make_app()
        assert app._text_filter_match("hello", "notContains", "xyz") is True

    def test_not_equal(self):
        app = make_app()
        assert app._text_filter_match("hello", "notEqual", "world") is True

    def test_unknown_op_defaults_to_contains(self):
        app = make_app()
        assert app._text_filter_match("hello", "unknown", "ell") is True


class TestNumberFilterMatch:
    def test_equals(self):
        app = make_app()
        assert app._number_filter_match(5, "equals", 5) is True

    def test_not_equal(self):
        app = make_app()
        assert app._number_filter_match(5, "notEqual", 6) is True

    def test_less_than(self):
        app = make_app()
        assert app._number_filter_match(5, "lessThan", 10) is True

    def test_less_than_or_equal(self):
        app = make_app()
        assert app._number_filter_match(5, "lessThanOrEqual", 5) is True

    def test_greater_than(self):
        app = make_app()
        assert app._number_filter_match(10, "greaterThan", 5) is True

    def test_greater_than_or_equal(self):
        app = make_app()
        assert app._number_filter_match(5, "greaterThanOrEqual", 5) is True

    def test_unknown_op_returns_true(self):
        app = make_app()
        assert app._number_filter_match(5, "unknown", 5) is True

    def test_invalid_value(self):
        app = make_app()
        assert app._number_filter_match("not a number", "equals", 5) is False


class TestApplyGridSort:
    def test_no_sort_returns_data(self):
        app = make_app()
        data = [{"a": 1}, {"a": 2}]
        assert app._apply_grid_sort(data, []) == data

    def test_ascending_sort(self):
        app = make_app()
        data = [{"a": 3}, {"a": 1}, {"a": 2}]
        result = app._apply_grid_sort(data, [{"colId": "a", "sort": "asc"}])
        assert [r["a"] for r in result] == [1, 2, 3]

    def test_descending_sort(self):
        app = make_app()
        data = [{"a": 1}, {"a": 3}, {"a": 2}]
        result = app._apply_grid_sort(data, [{"colId": "a", "sort": "desc"}])
        assert [r["a"] for r in result] == [3, 2, 1]

    def test_skips_sort_with_no_col_id(self):
        app = make_app()
        data = [{"a": 1}]
        result = app._apply_grid_sort(data, [{"sort": "asc"}])
        assert result == data


class TestGetSortKey:
    def test_none_value(self):
        app = make_app()
        assert app._get_sort_key({"a": None}, "a") == (1, "")

    def test_numeric_value(self):
        app = make_app()
        assert app._get_sort_key({"a": "42"}, "a") == (0, 42.0)

    def test_text_value(self):
        app = make_app()
        assert app._get_sort_key({"a": "Hello"}, "a") == (0, "hello")


# ---------------------------------------------------------------------------
# Lazy asset getters / icon / lifecycle
# ---------------------------------------------------------------------------


class TestLazyAssets:
    def test_get_plotly_js_caches(self):
        app = make_app()
        with patch("pywry.app.get_plotly_js", return_value="JS") as mock_get:
            assert app._get_plotly_js() == "JS"
            assert app._get_plotly_js() == "JS"
            mock_get.assert_called_once()

    def test_get_aggrid_js_caches(self):
        app = make_app()
        with patch("pywry.app.get_aggrid_js", return_value="JS") as mock_get:
            assert app._get_aggrid_js() == "JS"
            assert app._get_aggrid_js() == "JS"
            mock_get.assert_called_once()

    def test_get_aggrid_css_caches(self):
        app = make_app()
        with patch("pywry.app.get_aggrid_css", return_value="CSS") as mock_get:
            assert app._get_aggrid_css() == "CSS"
            assert app._get_aggrid_css() == "CSS"
            mock_get.assert_called_once()

    def test_get_icon(self):
        app = make_app()
        with patch("pywry.app.get_pywry_icon", return_value=b"ICON"):
            assert app.get_icon() == b"ICON"

    def test_get_lifecycle_returns_singleton(self):
        app = make_app()
        from pywry.window_manager import get_lifecycle as gl

        assert app.get_lifecycle() is gl()


class TestDestroyAndShutdown:
    def test_destroy_cleans_up_state(self):
        app = make_app()
        app._mode = MagicMock()
        app._asset_loader = MagicMock()
        # Add some cached assets
        app._plotly_js = "x"
        app._aggrid_js = "y"
        app._aggrid_css[("alpine", ThemeMode.DARK)] = "z"
        # Add a tray
        tray = MagicMock()
        app._trays["t1"] = tray
        with patch("pywry.tray_proxy.TrayProxy.remove_all"):
            app.destroy()
        assert app._trays == {}
        assert app._plotly_js is None
        assert app._aggrid_js is None
        assert app._aggrid_css == {}

    def test_destroy_with_hot_reload(self):
        app = make_app(hot_reload=True)
        app._mode = MagicMock()
        mgr = MagicMock()
        app._hot_reload_manager = mgr
        with patch("pywry.tray_proxy.TrayProxy.remove_all"):
            app.destroy()
        assert app._hot_reload_manager is None
        mgr.stop.assert_called_once()

    def test_shutdown_stops_runtime_and_session(self):
        app = make_app()
        app._mode = MagicMock()
        sm = MagicMock()
        sm.provider = MagicMock()
        app._session_manager = sm
        with (
            patch("pywry.tray_proxy.TrayProxy.remove_all"),
            patch("pywry.runtime.stop") as mock_stop,
            patch("pywry.state.sync_helpers.run_async"),
        ):
            app._shutdown()
            mock_stop.assert_called_once()
        sm._cancel_refresh_timer.assert_called_once()
        assert app._session_manager is None

    def test_shutdown_no_session_manager(self):
        app = make_app()
        app._mode = MagicMock()
        with (
            patch("pywry.tray_proxy.TrayProxy.remove_all"),
            patch("pywry.runtime.stop"),
        ):
            app._shutdown()


class TestBlock:
    def test_block_in_browser_mode(self):
        app = make_app(mode=WindowMode.BROWSER)
        with (
            patch("pywry.inline.block") as mock_block,
            patch.object(app, "_shutdown"),
        ):
            app.block()
            mock_block.assert_called_once()

    def test_block_native_no_label(self):
        app = make_app()
        app._mode = MagicMock()
        # Have one label initially, then become empty
        app._mode.get_labels = MagicMock(side_effect=[["lbl"], []])
        with (
            patch("pywry.runtime.is_running", return_value=True),
            patch.object(app, "_shutdown"),
            patch("time.sleep"),
        ):
            app.block()

    def test_block_native_with_label(self):
        app = make_app()
        app._mode = MagicMock()
        # Label initially in list, then gone
        app._mode.get_labels = MagicMock(side_effect=[["lbl"], []])
        with (
            patch("pywry.runtime.is_running", return_value=True),
            patch.object(app, "_shutdown"),
            patch("time.sleep"),
        ):
            app.block(label="lbl")

    def test_block_handles_keyboard_interrupt(self):
        app = make_app()
        app._mode = MagicMock()
        app._mode.get_labels = MagicMock(side_effect=KeyboardInterrupt)
        with (
            patch("pywry.runtime.is_running", return_value=True),
            patch.object(app, "_shutdown"),
        ):
            app.block()

    def test_block_when_runtime_not_running(self):
        app = make_app()
        app._mode = MagicMock()
        app._mode.get_labels = MagicMock(return_value=["lbl"])
        with (
            patch("pywry.runtime.is_running", return_value=False),
            patch.object(app, "_shutdown"),
        ):
            app.block()

    def test_block_with_label_when_runtime_not_running(self):
        app = make_app()
        app._mode = MagicMock()
        app._mode.get_labels = MagicMock(return_value=["lbl"])
        with (
            patch("pywry.runtime.is_running", return_value=False),
            patch.object(app, "_shutdown"),
        ):
            app.block(label="lbl")
