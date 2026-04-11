"""Demo: Google OAuth2 Sign-In with PyWry.

Demonstrates the library-managed auth lifecycle:

- ``app.login()`` owns the full login/logout cycle
- ``on_login`` middleware for your business logic (DB writes, UI setup)
- ``on_logout`` middleware for cleanup (session invalidation)
- ``show_page=True`` for the built-in themed login page
- ``Toolbar`` with ``Button`` / ``Div`` / ``Spacer`` for the authenticated UI

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

from typing import Any

from pywry import (
    Button,
    Div,
    HtmlContent,
    PyWry,
    ThemeMode,
    Toolbar,
    WindowMode,
)
from pywry.auth import GoogleProvider


# ───────────────────────────────────────────────────────────
# Provider setup
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
# Authenticated home page
# ───────────────────────────────────────────────────────────

HOME_CSS = """\
.hero { text-align: center; padding: 3rem 1.5rem 2rem; }
.hero h1 { font-size: 2rem; margin-bottom: 0.3rem; }
.hero .email { color: var(--pywry-accent); margin-bottom: 0.5rem; }
.hero .tagline { color: var(--pywry-text-secondary); }
.cards {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 1.2rem; max-width: 800px; margin: 0 auto; padding: 0 1.5rem 3rem;
}
.card {
    background: var(--pywry-bg-secondary); border: 1px solid var(--pywry-border-color);
    border-radius: 12px; padding: 1.5rem;
}
.card h3 { margin-bottom: 0.5rem; font-size: 1rem; }
.card p { font-size: 0.85rem; color: var(--pywry-text-secondary); line-height: 1.5; }
"""


def build_home_content(user_info: dict[str, Any]) -> tuple[HtmlContent, list[Toolbar]]:
    """Build the authenticated home screen with a nav toolbar."""
    name = html_mod.escape(
        str(user_info.get("name") or user_info.get("login") or user_info.get("email") or "User")
    )
    email = html_mod.escape(str(user_info.get("email", "")))
    picture = user_info.get("picture", "")

    avatar_html = (
        f'<img src="{html_mod.escape(picture)}" alt="avatar"'
        f' style="width:28px; height:28px; border-radius:50%; vertical-align:middle;" />'
        if picture
        else ""
    )

    nav_toolbar = Toolbar(
        position="top",
        items=[
            Div(content=f"{avatar_html} <strong>{name}</strong>"),
            Div(content="", style="flex: 1;"),
            Button(
                label="Sign out",
                event="auth:do-logout",
                variant="outline",
                size="sm",
            ),
        ],
    )

    home_html = f"""\
<div class="hero">
  <h1>Welcome, {name}!</h1>
  <p class="email">{email}</p>
  <p class="tagline">You are signed in via Google OAuth2.</p>
</div>
<section class="cards">
  <div class="card">
    <h3>Authenticated</h3>
    <p>Your session is active with PKCE-protected tokens stored in memory.</p>
  </div>
  <div class="card">
    <h3>Auto-Refresh</h3>
    <p>Tokens are refreshed automatically before they expire.</p>
  </div>
  <div class="card">
    <h3>Ready to Build</h3>
    <p>Add <code>show_plotly()</code>, <code>show_dataframe()</code>,
       or any HTML widget here.</p>
  </div>
</section>
"""
    return HtmlContent(html=home_html, inline_css=HOME_CSS), [nav_toolbar]


# ───────────────────────────────────────────────────────────
# Developer middleware
# ───────────────────────────────────────────────────────────

app = PyWry(
    mode=WindowMode.SINGLE_WINDOW,
    theme=ThemeMode.DARK,
    title="PyWry - Sign In",
)


def on_login(result: Any) -> None:
    """Called after successful authentication.

    This is where you would write to your user table, set up
    app-specific sessions, etc. Here we just show the home page.
    """
    user_info = result.user_info or {}
    content, toolbars = build_home_content(user_info)
    app.show(
        content,
        title=f"PyWry - {user_info.get('name', 'Home')}",
        width=900,
        height=640,
        toolbars=toolbars,
    )


def on_logout() -> None:
    """Called when the user triggers logout.

    This is where you would invalidate DB sessions, clean up
    app-specific state, etc. Token cleanup is handled by the library.
    """


# ── Launch ────────────────────────────────────────────────

app.login(
    provider=provider,
    on_login=on_login,
    on_logout=on_logout,
    show_page=True,
)
app.block()
