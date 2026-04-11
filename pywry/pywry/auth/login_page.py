"""Built-in login page for OAuth2 authentication.

Provides a themed login page that uses PyWry CSS variables for automatic
dark/light theme support. Used internally by ``PyWry.login(show_page=True)``.
"""

from __future__ import annotations

from ..models import HtmlContent


# Internal event emitted by the login button — not part of the public API.
LOGIN_CLICK_EVENT = "pywry:auth-login-click"

_LOGIN_CSS = """\
.pywry-login-center {
    height: 100vh; display: flex; align-items: center; justify-content: center;
    font-family: var(--pywry-font-family, -apple-system, BlinkMacSystemFont,
        "Segoe UI", Roboto, sans-serif);
    color: var(--pywry-text-primary, #ebebed);
}
.pywry-login-card {
    background: var(--pywry-bg-secondary, #151518);
    border: 1px solid var(--pywry-border-color, #333);
    border-radius: 16px;
    padding: 3rem 2.5rem; text-align: center; width: 380px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}
.pywry-login-card .pywry-login-logo {
    font-size: 3rem; margin-bottom: 0.5rem;
}
.pywry-login-card h1 {
    font-size: 1.6rem; margin-bottom: 0.25rem;
    font-weight: var(--pywry-font-weight-medium, 500);
}
.pywry-login-card .pywry-login-subtitle {
    color: var(--pywry-text-secondary, #a0a0a0); margin-bottom: 2rem;
}
.pywry-login-btn {
    display: inline-flex; align-items: center; justify-content: center;
    width: 100%; padding: 0.75rem 1.5rem;
    background: var(--pywry-btn-primary-bg, #e2e2e2);
    color: var(--pywry-btn-primary-text, #151518);
    border: none; border-radius: var(--pywry-radius-lg, 6px);
    font-size: 1rem; font-weight: var(--pywry-font-weight-medium, 500);
    cursor: pointer;
    transition: background var(--pywry-transition-normal, 0.2s ease),
                transform 0.1s;
}
.pywry-login-btn:hover {
    background: var(--pywry-btn-primary-hover, #cccccc);
    transform: translateY(-1px);
}
.pywry-login-btn:active { transform: translateY(0); }
.pywry-login-btn:disabled {
    opacity: 0.6; cursor: default; transform: none;
}
.pywry-login-hint {
    display: none; margin-top: 1.25rem;
    color: var(--pywry-text-secondary, #a0a0a0);
    font-size: 0.875rem; line-height: 1.4;
}
"""

_LOGIN_INIT_SCRIPT = """\
document.getElementById("pywry-login-btn").addEventListener("click", function() {
    this.textContent = "Signing in\\u2026";
    this.disabled = true;
    var hint = document.getElementById("pywry-login-hint");
    if (hint) hint.style.display = "block";
    window.pywry.emit("pywry:auth-login-click", {});
});
"""


def build_login_page(
    provider_name: str,
    title: str = "Sign In",
    subtitle: str = "Sign in to continue",
) -> HtmlContent:
    """Build a themed login page for OAuth2 authentication.

    Parameters
    ----------
    provider_name : str
        Display name of the provider (e.g., "Google", "GitHub").
    title : str
        Page heading text.
    subtitle : str
        Subheading text below the title.

    Returns
    -------
    HtmlContent
        Ready-to-render login page content.
    """
    html = f"""\
<div class="pywry-login-center">
  <div class="pywry-login-card">
    <div class="pywry-login-logo">&#x1f512;</div>
    <h1>{title}</h1>
    <p class="pywry-login-subtitle">{subtitle}</p>
    <button id="pywry-login-btn" class="pywry-login-btn">
      Sign in with {provider_name}
    </button>
    <p id="pywry-login-hint" class="pywry-login-hint">
      Complete sign-in in your browser, then return here.
    </p>
  </div>
</div>
"""
    return HtmlContent(
        html=html,
        inline_css=_LOGIN_CSS,
        init_script=_LOGIN_INIT_SCRIPT,
    )
