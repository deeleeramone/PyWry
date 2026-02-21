"""Ephemeral localhost HTTP server for OAuth2 redirect capture.

Used in native window mode to intercept the OAuth2 callback
on a randomly assigned port. Serves a success/error HTML page
and extracts authorization code + state from query parameters.

Uses only stdlib (http.server, threading, urllib.parse) — zero
additional dependencies.
"""

# pylint: disable=logging-too-many-args

# pylint: disable=C0103,W0212

from __future__ import annotations

import html
import logging
import threading

from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse


logger = logging.getLogger("pywry.auth")

_SUCCESS_HTML = """<!DOCTYPE html>
<html>
<head><title>Authentication Complete</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
         display: flex; align-items: center; justify-content: center;
         height: 100vh; margin: 0; background: #f0f2f5; color: #1a1a2e; }
  .card { text-align: center; padding: 2rem 3rem; background: white;
          border-radius: 12px; box-shadow: 0 2px 12px rgba(0,0,0,.08); }
  h1 { font-size: 1.5rem; margin-bottom: 0.5rem; }
  p { color: #666; }
</style></head>
<body><div class="card">
  <h1>&#x2705; Authentication Complete</h1>
  <p>You can close this window.</p>
</div></body></html>"""

_ERROR_HTML = """<!DOCTYPE html>
<html>
<head><title>Authentication Error</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
         display: flex; align-items: center; justify-content: center;
         height: 100vh; margin: 0; background: #f0f2f5; color: #1a1a2e; }}
  .card {{ text-align: center; padding: 2rem 3rem; background: white;
          border-radius: 12px; box-shadow: 0 2px 12px rgba(0,0,0,.08); }}
  h1 {{ font-size: 1.5rem; margin-bottom: 0.5rem; color: #cc0000; }}
  p {{ color: #666; }}
</style></head>
<body><div class="card">
  <h1>&#x274C; Authentication Failed</h1>
  <p>{error}</p>
</div></body></html>"""

_WAITING_HTML = """<!DOCTYPE html>
<html>
<head><title>Waiting for Authentication</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
         display: flex; align-items: center; justify-content: center;
         height: 100vh; margin: 0; background: #f0f2f5; color: #1a1a2e; }
  .card { text-align: center; padding: 2rem 3rem; background: white;
          border-radius: 12px; box-shadow: 0 2px 12px rgba(0,0,0,.08); }
</style></head>
<body><div class="card">
  <h1>Waiting for authentication&hellip;</h1>
  <p>Please complete the login in the browser window.</p>
</div></body></html>"""


class OAuthCallbackServer:
    """Ephemeral localhost HTTP server for capturing OAuth2 redirects.

    Parameters
    ----------
    host : str
        Bind address (default ``"127.0.0.1"``).
    port : int
        Port number (``0`` for auto-assign).
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 0) -> None:
        """Initialize the callback server."""
        self._host = host
        self._port = port
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._result: dict[str, Any] | None = None
        self._result_event = threading.Event()
        self._actual_port: int = 0

    @property
    def redirect_uri(self) -> str:
        """Get the redirect URI for this callback server.

        Returns
        -------
        str
            The full redirect URI (e.g. ``http://127.0.0.1:54321/callback``).
        """
        return f"http://{self._host}:{self._actual_port}/callback"

    def start(self) -> str:
        """Start the callback server on a daemon thread.

        Returns
        -------
        str
            The redirect URI to use with the OAuth2 provider.
        """
        server_ref = self

        class _CallbackHandler(BaseHTTPRequestHandler):
            """HTTP request handler for OAuth2 callbacks."""

            def do_GET(self) -> None:
                """Handle GET requests."""
                parsed = urlparse(self.path)

                if parsed.path == "/callback":
                    params = parse_qs(parsed.query)
                    result: dict[str, Any] = {
                        "code": params.get("code", [None])[0],
                        "state": params.get("state", [None])[0],
                        "error": params.get("error", [None])[0],
                        "error_description": params.get("error_description", [None])[0],
                    }

                    # Only capture the first callback
                    if not server_ref._result_event.is_set():
                        server_ref._result = result

                        if result.get("error"):
                            error_msg = result.get("error_description") or result["error"]
                            safe_msg = html.escape(str(error_msg), quote=True)
                            error_html = _ERROR_HTML.format(error=safe_msg)
                            self._send_html(error_html)
                        else:
                            self._send_html(_SUCCESS_HTML)

                        server_ref._result_event.set()
                        # Schedule shutdown on a background thread to avoid deadlock
                        threading.Thread(target=self._shutdown_server, daemon=True).start()
                    else:
                        self._send_html(_SUCCESS_HTML)

                elif parsed.path == "/":
                    self._send_html(_WAITING_HTML)
                else:
                    self.send_error(404)

            def _send_html(self, html_content: str) -> None:
                """Send an HTML response with security headers."""
                encoded = html_content.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(encoded)))
                self.send_header("Cache-Control", "no-store")
                self.send_header(
                    "Content-Security-Policy",
                    "default-src 'none'; style-src 'unsafe-inline'",
                )
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                self.wfile.write(encoded)

            def _shutdown_server(self) -> None:
                """Shut down the HTTP server."""
                if server_ref._server:
                    server_ref._server.shutdown()

            def log_message(self, *args: Any) -> None:
                """Redirect HTTP server logging to the pywry logger."""
                if args:
                    logger.debug("OAuth callback server: %s", args[0] % args[1:])

        self._server = HTTPServer((self._host, self._port), _CallbackHandler)
        self._actual_port = self._server.server_address[1]

        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

        logger.debug("OAuth callback server started on %s", self.redirect_uri)
        return self.redirect_uri

    def wait_for_callback(self, timeout: float = 120.0) -> dict[str, Any] | None:
        """Block until the callback is received or timeout expires.

        Parameters
        ----------
        timeout : float
            Maximum seconds to wait (default 120).

        Returns
        -------
        dict or None
            Callback parameters (``code``, ``state``, ``error``, ``error_description``)
            or ``None`` if timeout expired.
        """
        received = self._result_event.wait(timeout=timeout)
        if received:
            return self._result
        return None

    def stop(self) -> None:
        """Force-shutdown the callback server."""
        if self._server:
            self._server.shutdown()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._server = None
        self._thread = None
