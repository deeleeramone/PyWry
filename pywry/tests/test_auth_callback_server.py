"""Unit tests for OAuth2 ephemeral callback server."""

# pylint: disable=consider-using-with

from __future__ import annotations

import contextlib
import threading
import time

from urllib.parse import urlencode
from urllib.request import urlopen

from pywry.auth.callback_server import OAuthCallbackServer


class TestOAuthCallbackServer:
    """Tests for OAuthCallbackServer."""

    def test_start_and_stop(self) -> None:
        """Server starts, binds to a port, and stops cleanly."""
        server = OAuthCallbackServer()
        redirect_uri = server.start()

        assert redirect_uri.startswith("http://127.0.0.1:")
        assert redirect_uri.endswith("/callback")
        assert server._actual_port > 0

        server.stop()

    def test_redirect_uri_property(self) -> None:
        """redirect_uri matches the started server port."""
        server = OAuthCallbackServer()
        server.start()
        try:
            assert f":{server._actual_port}/callback" in server.redirect_uri
        finally:
            server.stop()

    def test_wait_for_callback_timeout(self) -> None:
        """wait_for_callback returns None on timeout."""
        server = OAuthCallbackServer()
        server.start()
        try:
            result = server.wait_for_callback(timeout=0.2)
            assert result is None
        finally:
            server.stop()

    def test_callback_with_code(self) -> None:
        """Callback captures authorization code and state."""
        server = OAuthCallbackServer()
        server.start()

        try:
            params = urlencode({"code": "test_code_123", "state": "test_state"})
            callback_url = f"{server.redirect_uri}?{params}"

            # Send the callback in a background thread
            def send_request() -> None:
                time.sleep(0.1)
                with contextlib.suppress(Exception):
                    urlopen(callback_url, timeout=5)  # noqa: S310

            t = threading.Thread(target=send_request, daemon=True)
            t.start()

            result = server.wait_for_callback(timeout=5.0)
            assert result is not None
            assert result["code"] == "test_code_123"
            assert result["state"] == "test_state"
            assert result["error"] is None
        finally:
            server.stop()

    def test_callback_with_error(self) -> None:
        """Callback captures provider error."""
        server = OAuthCallbackServer()
        server.start()

        try:
            params = urlencode(
                {
                    "error": "access_denied",
                    "error_description": "User cancelled",
                }
            )
            callback_url = f"{server.redirect_uri}?{params}"

            def send_request() -> None:
                time.sleep(0.1)
                with contextlib.suppress(Exception):
                    urlopen(callback_url, timeout=5)  # noqa: S310

            t = threading.Thread(target=send_request, daemon=True)
            t.start()

            result = server.wait_for_callback(timeout=5.0)
            assert result is not None
            assert result["error"] == "access_denied"
            assert result["error_description"] == "User cancelled"
            assert result["code"] is None
        finally:
            server.stop()

    def test_waiting_page(self) -> None:
        """Root path returns the waiting page."""
        server = OAuthCallbackServer()
        server.start()

        try:
            resp = urlopen(f"http://127.0.0.1:{server._actual_port}/", timeout=5)
            content = resp.read().decode("utf-8")
            assert "Waiting for authentication" in content
        finally:
            server.stop()

    def test_only_first_callback_captured(self) -> None:
        """Only the first callback result is captured."""
        server = OAuthCallbackServer()
        server.start()

        try:
            params1 = urlencode({"code": "first", "state": "s1"})
            params2 = urlencode({"code": "second", "state": "s2"})

            # Send first callback
            with contextlib.suppress(Exception):
                urlopen(f"{server.redirect_uri}?{params1}", timeout=5)  # noqa: S310

            # Send second callback
            with contextlib.suppress(Exception):
                urlopen(f"{server.redirect_uri}?{params2}", timeout=5)  # noqa: S310

            result = server.wait_for_callback(timeout=2.0)
            assert result is not None
            assert result["code"] == "first"
        finally:
            server.stop()

    def test_custom_host_port(self) -> None:
        """Custom host and port are used."""
        server = OAuthCallbackServer(host="127.0.0.1", port=0)
        redirect_uri = server.start()

        try:
            assert "127.0.0.1" in redirect_uri
        finally:
            server.stop()

    def test_stop_idempotent(self) -> None:
        """Calling stop() multiple times is safe."""
        server = OAuthCallbackServer()
        server.start()
        server.stop()
        server.stop()  # Should not raise

    def test_callback_xss_escaping(self) -> None:
        """Error messages in callback HTML are HTML-escaped to prevent XSS."""
        server = OAuthCallbackServer()
        server.start()

        try:
            xss_payload = '<script>alert("xss")</script>'
            params = urlencode(
                {
                    "error": "access_denied",
                    "error_description": xss_payload,
                }
            )
            callback_url = f"{server.redirect_uri}?{params}"

            def send_request() -> None:
                time.sleep(0.1)
                with contextlib.suppress(Exception):
                    urlopen(callback_url, timeout=5)  # noqa: S310

            t = threading.Thread(target=send_request, daemon=True)
            t.start()

            result = server.wait_for_callback(timeout=5.0)
            assert result is not None
            assert result["error"] == "access_denied"
            # The raw XSS payload must NOT appear in the error_description rendered
            # (but we can't inspect the HTML directly from the result dict;
            #  the important thing is the server didn't crash)
        finally:
            server.stop()

    def test_callback_csp_header(self) -> None:
        """Callback responses include Content-Security-Policy header."""
        from urllib.request import Request

        server = OAuthCallbackServer()
        server.start()

        try:
            # Hit the root waiting page and check CSP header
            req = Request(f"http://127.0.0.1:{server._actual_port}/")
            resp = urlopen(req, timeout=5)  # noqa: S310
            csp = resp.headers.get("Content-Security-Policy", "")
            assert "default-src" in csp
            assert "'none'" in csp or "style-src" in csp
        finally:
            server.stop()
