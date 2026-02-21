"""Demo: Google OAuth2 Sign-In with PyWry.

Demonstrates the documented auth patterns:

- ``GoogleProvider`` for explicit provider configuration
- ``HtmlContent`` for structured content (html / css / init_script)
- ``app.login(provider=provider)`` as the core auth API
- ``app.logout()`` for session teardown

Setup
-----
1. Create a Google OAuth2 client at https://console.cloud.google.com/apis/credentials
2. Set the authorized redirect URI to ``http://127.0.0.1:0/callback``
   (for native / loopback flows any port is matched).
3. Export the credentials::

       # PowerShell
       $env:PYWRY_OAUTH2__CLIENT_ID = "your-client-id.apps.googleusercontent.com"
       $env:PYWRY_OAUTH2__CLIENT_SECRET = "your-client-secret"

       # Bash
       export PYWRY_OAUTH2__CLIENT_ID="your-client-id.apps.googleusercontent.com"
       export PYWRY_OAUTH2__CLIENT_SECRET="your-client-secret"

4. Run::

       python examples/pywry_demo_oauth2.py
"""

from __future__ import annotations

import html as html_mod
import os
import sys
import threading

from typing import Any

from pywry import HtmlContent, PyWry, WindowMode
from pywry.auth import GoogleProvider


# ───────────────────────────────────────────────────────────
# Provider setup (documented pattern)
# ───────────────────────────────────────────────────────────

CLIENT_ID = os.environ.get(
    "PYWRY_OAUTH2__CLIENT_ID",
    "***.apps.googleusercontent.com",
)
CLIENT_SECRET = os.environ.get("PYWRY_OAUTH2__CLIENT_SECRET", "GOCSPX-your-client-secret")

if not CLIENT_ID or "your-client-id" in CLIENT_ID:
    print(
        "\n"
        "╔══════════════════════════════════════════════════════════════╗\n"
        "║  ERROR: Real Google OAuth2 credentials are required.         ║\n"
        "╚══════════════════════════════════════════════════════════════╝\n"
        "\n"
        "  1. Go to https://console.cloud.google.com/apis/credentials\n"
        "  2. Create an OAuth 2.0 Client ID (type: Desktop app)\n"
        "  3. Set the env vars:\n"
        "\n"
        "     PowerShell:\n"
        '       $env:PYWRY_OAUTH2__CLIENT_ID = "YOUR_REAL_ID.apps.googleusercontent.com"\n'
        '       $env:PYWRY_OAUTH2__CLIENT_SECRET = "GOCSPX-your-real-secret"\n'
        "\n"
        "     Then run:  python examples/pywry_demo_oauth2.py\n"
    )
    sys.exit(1)


provider = GoogleProvider(client_id=CLIENT_ID, client_secret=CLIENT_SECRET)


# ───────────────────────────────────────────────────────────
# Login page
# ───────────────────────────────────────────────────────────

LOGIN_CSS = """\
* { margin: 0; padding: 0; box-sizing: border-box; }
body, html { height: 100%; }
#login-root {
    height: 100vh; display: flex; align-items: center; justify-content: center;
    background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    color: #e0e0e0;
}
.login-card {
    background: rgba(255,255,255,0.06); backdrop-filter: blur(12px);
    border: 1px solid rgba(255,255,255,0.12); border-radius: 16px;
    padding: 3rem 2.5rem; text-align: center; width: 380px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.3);
}
.logo { font-size: 3rem; margin-bottom: 0.5rem; }
h1 { font-size: 1.6rem; margin-bottom: 0.25rem; font-weight: 600; }
.subtitle { color: #aaa; margin-bottom: 2rem; }
.btn-google {
    display: inline-flex; align-items: center; justify-content: center;
    width: 100%; padding: 0.75rem 1.5rem;
    background: #fff; color: #444; border: none; border-radius: 8px;
    font-size: 1rem; font-weight: 500; cursor: pointer;
    transition: box-shadow 0.2s, transform 0.1s;
}
.btn-google:hover { box-shadow: 0 2px 12px rgba(66,133,244,0.4); transform: translateY(-1px); }
.btn-google:active { transform: translateY(0); }
.btn-google:disabled { opacity: 0.6; cursor: default; transform: none; box-shadow: none; }
.hint { margin-top: 1.5rem; font-size: 0.75rem; color: #777; }
code {
    background: rgba(255,255,255,0.1); padding: 2px 5px;
    border-radius: 4px; font-size: 0.7rem;
}
"""

LOGIN_HTML = """\
<div id="login-root">
  <div class="login-card">
    <div class="logo">🔐</div>
    <h1>Welcome to PyWry</h1>
    <p class="subtitle">Sign in to continue</p>
    <button id="btn-google" class="btn-google">
      <svg width="18" height="18" viewBox="0 0 48 48" style="margin-right:10px;">
        <path fill="#EA4335"
          d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0
             14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
        <path fill="#4285F4"
          d="M46.98 24.55c0-1.57-.14-3.09-.41-4.55H24v9.02h12.94
             c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6
             c4.51-4.18 7.09-10.36 7.09-17.65z"/>
        <path fill="#FBBC05"
          d="M10.53 28.59a14.5 14.5 0 0 1 0-9.18l-7.98-6.19
             a24.07 24.07 0 0 0 0 21.56l7.98-6.19z"/>
        <path fill="#34A853"
          d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6
             c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91
             l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
      </svg>
      Sign in with Google
    </button>
    <p class="hint">
      Requires <code>PYWRY_OAUTH2__CLIENT_ID</code> and
      <code>PYWRY_OAUTH2__CLIENT_SECRET</code> env vars.
    </p>
  </div>
</div>
"""

LOGIN_INIT_SCRIPT = """\
document.getElementById("btn-google").addEventListener("click", function() {
    this.textContent = "Signing in\\u2026";
    this.disabled = true;
    window.pywry.emit("auth:login", {});
});
"""

LOGIN_CONTENT = HtmlContent(
    html=LOGIN_HTML,
    inline_css=LOGIN_CSS,
    init_script=LOGIN_INIT_SCRIPT,
)

# ── Home page ─────────────────────────────────────────────

HOME_CSS = """\
* { margin: 0; padding: 0; box-sizing: border-box; }
body, html { height: 100%; }
#home-root {
    min-height: 100vh;
    background: linear-gradient(160deg, #0f0c29, #1a1a3e);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    color: #e0e0e0;
}
nav {
    display: flex; align-items: center; justify-content: space-between;
    padding: 0.75rem 1.5rem;
    background: rgba(255,255,255,0.05);
    border-bottom: 1px solid rgba(255,255,255,0.08);
}
.brand { font-weight: 700; font-size: 1.1rem; color: #8b5cf6; }
.nav-user { display: flex; align-items: center; gap: 0.6rem; }
.avatar { width: 32px; height: 32px; border-radius: 50%; }
.avatar-placeholder {
    width: 32px; height: 32px; border-radius: 50%;
    background: rgba(255,255,255,0.1); display: flex;
    align-items: center; justify-content: center; font-size: 1.1rem;
}
.nav-name { font-size: 0.85rem; }
.btn-logout {
    background: transparent; border: 1px solid rgba(255,255,255,0.2);
    color: #ccc; padding: 0.3rem 0.8rem; border-radius: 6px;
    font-size: 0.8rem; cursor: pointer; transition: background 0.2s;
}
.btn-logout:hover { background: rgba(255,255,255,0.1); }
main { max-width: 800px; margin: 0 auto; padding: 3rem 1.5rem; }
.hero { text-align: center; margin-bottom: 3rem; }
.hero h1 { font-size: 2rem; margin-bottom: 0.3rem; }
.email { color: #8b5cf6; margin-bottom: 0.5rem; }
.tagline { color: #888; }
.cards {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 1.2rem;
}
.card {
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px; padding: 1.5rem;
}
.card h3 { margin-bottom: 0.5rem; font-size: 1rem; }
.card p { font-size: 0.85rem; color: #aaa; line-height: 1.5; }
code {
    background: rgba(255,255,255,0.1); padding: 2px 5px;
    border-radius: 4px; font-size: 0.8rem;
}
"""

HOME_INIT_SCRIPT = """\
document.getElementById("btn-logout").addEventListener("click", function() {
    window.pywry.emit("auth:do-logout", {});
});
"""


def build_home_content(user_info: dict[str, Any]) -> HtmlContent:
    """Build an ``HtmlContent`` for the authenticated home screen."""
    name = html_mod.escape(
        str(user_info.get("name") or user_info.get("login") or user_info.get("email") or "User")
    )
    email = html_mod.escape(str(user_info.get("email", "")))
    picture = user_info.get("picture", "")

    avatar = (
        f'<img class="avatar" src="{html_mod.escape(picture)}" alt="avatar" />'
        if picture
        else '<div class="avatar-placeholder">👤</div>'
    )

    home_html = f"""\
<div id="home-root">
  <nav>
    <span class="brand">PyWry</span>
    <div class="nav-user">
      {avatar}
      <span class="nav-name">{name}</span>
      <button id="btn-logout" class="btn-logout">Sign out</button>
    </div>
  </nav>

  <main>
    <div class="hero">
      <h1>Welcome, {name}!</h1>
      <p class="email">{email}</p>
      <p class="tagline">You are signed in via Google OAuth2.</p>
    </div>

    <section class="cards">
      <div class="card">
        <h3>🔒 Authenticated</h3>
        <p>Your session is active with PKCE-protected tokens stored in memory.</p>
      </div>
      <div class="card">
        <h3>🔄 Auto-Refresh</h3>
        <p>Tokens are refreshed automatically before they expire.</p>
      </div>
      <div class="card">
        <h3>🚀 Ready to Build</h3>
        <p>Add <code>show_plotly()</code>, <code>show_dataframe()</code>,
           or any HTML widget here.</p>
      </div>
    </section>
  </main>
</div>
"""
    return HtmlContent(html=home_html, inline_css=HOME_CSS, init_script=HOME_INIT_SCRIPT)


# ───────────────────────────────────────────────────────────
# App & callbacks
# ───────────────────────────────────────────────────────────

app = PyWry(
    mode=WindowMode.SINGLE_WINDOW,
    title="PyWry - Sign In",
    width=460,
    height=560,
)


def on_login(_data: dict[str, Any], _event_type: str, _label: str) -> None:
    """Handle *Sign in with Google* button click.

    The blocking OAuth2 flow runs in a background thread so the IPC
    reader thread stays free to process ``set_content`` commands.
    """

    def _do_login() -> None:
        try:
            # Documented pattern:  result = app.login(provider=provider)
            result = app.login(provider=provider)
            if result.success:
                user_info = result.user_info or {}
                app.show(
                    build_home_content(user_info),
                    title=f"PyWry - {user_info.get('name', 'Home')}",
                    width=900,
                    height=640,
                    callbacks={"auth:do-logout": on_logout},
                )
        except Exception as exc:
            print(f"Authentication failed: {exc}")
            app.show(
                LOGIN_CONTENT,
                title="PyWry - Sign In",
                callbacks={"auth:login": on_login},
            )

    threading.Thread(target=_do_login, daemon=True).start()


def on_logout(_data: dict[str, Any], _event_type: str, _label: str) -> None:
    """Sign out: clear tokens and return to login."""
    app.logout()
    app.show(
        LOGIN_CONTENT,
        title="PyWry - Sign In",
        width=460,
        height=560,
        callbacks={"auth:login": on_login},
    )


# ── Launch ────────────────────────────────────────────────

app.show(
    LOGIN_CONTENT,
    title="PyWry - Sign In",
    callbacks={"auth:login": on_login},
)

app.block()
