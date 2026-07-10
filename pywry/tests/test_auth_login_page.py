"""Tests for pywry.auth.login_page."""

from __future__ import annotations

from pywry.auth.login_page import LOGIN_CLICK_EVENT, build_login_page
from pywry.models import HtmlContent


class TestBuildLoginPage:
    """Tests for build_login_page()."""

    def test_returns_html_content(self):
        """build_login_page returns an HtmlContent instance."""
        result = build_login_page("Google")
        assert isinstance(result, HtmlContent)

    def test_includes_provider_name(self):
        """Provider name is rendered in the HTML body."""
        result = build_login_page("GitHub")
        assert "GitHub" in result.html

    def test_default_title(self):
        """Default title is 'Sign In'."""
        result = build_login_page("Google")
        assert "Sign In" in result.html

    def test_custom_title(self):
        """Custom title is rendered in the HTML body."""
        result = build_login_page("GitHub", title="Welcome Back")
        assert "Welcome Back" in result.html

    def test_default_subtitle(self):
        """Default subtitle is 'Sign in to continue'."""
        result = build_login_page("Google")
        assert "Sign in to continue" in result.html

    def test_custom_subtitle(self):
        """Custom subtitle is rendered in the HTML body."""
        result = build_login_page("Google", subtitle="Use your work account")
        assert "Use your work account" in result.html

    def test_includes_login_button_id(self):
        """Login button has the well-known id used by the init script."""
        result = build_login_page("Google")
        assert 'id="pywry-login-btn"' in result.html

    def test_inline_css_present(self):
        """Inline CSS includes the login card class."""
        result = build_login_page("Google")
        assert result.inline_css is not None
        assert ".pywry-login-card" in result.inline_css

    def test_init_script_present(self):
        """Init script wires the login button to the auth-login-click event."""
        result = build_login_page("Google")
        assert result.init_script is not None
        assert "pywry:auth-login-click" in result.init_script

    def test_login_click_event_constant(self):
        """LOGIN_CLICK_EVENT matches the documented event name."""
        assert LOGIN_CLICK_EVENT == "pywry:auth-login-click"
