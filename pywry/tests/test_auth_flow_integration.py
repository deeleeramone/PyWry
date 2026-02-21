"""Integration tests for OAuth2 flow manager."""

# pylint: disable=consider-using-with

from __future__ import annotations

import asyncio
import contextlib
import threading
import time

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import urlencode
from urllib.request import urlopen

import pytest

from pywry.auth.callback_server import OAuthCallbackServer
from pywry.auth.flow import AuthFlowManager
from pywry.auth.token_store import MemoryTokenStore
from pywry.exceptions import (
    AuthenticationError,
    AuthFlowCancelled,
    AuthFlowTimeout,
)
from pywry.state.types import AuthFlowState, OAuthTokenSet


# ── Helpers ──────────────────────────────────────────────────────────


def _make_mock_provider(**kwargs: Any) -> MagicMock:
    """Create a mock OAuthProvider."""
    provider = MagicMock()
    provider.__class__.__name__ = "MockProvider"
    provider.build_authorize_url.return_value = "https://mock.idp/authorize?state=test"

    tokens = OAuthTokenSet(
        access_token="at_mock",
        token_type="Bearer",
        refresh_token="rt_mock",
        expires_in=3600,
        issued_at=time.time(),
    )
    provider.exchange_code = AsyncMock(return_value=tokens)
    provider.get_userinfo = AsyncMock(return_value={"sub": "user123", "email": "test@example.com"})
    provider.refresh_tokens = AsyncMock(return_value=tokens)
    provider.revoke_token = AsyncMock()

    for k, v in kwargs.items():
        setattr(provider, k, v)

    return provider


def _send_callback_to_server(
    port: int, code: str = "test_code", state: str = "test_state", delay: float = 0.3
) -> None:
    """Send a simulated OAuth callback to the server."""

    def _send() -> None:
        time.sleep(delay)
        params = urlencode({"code": code, "state": state})
        url = f"http://127.0.0.1:{port}/callback?{params}"
        with contextlib.suppress(Exception):
            urlopen(url, timeout=5)  # noqa: S310

    t = threading.Thread(target=_send, daemon=True)
    t.start()


# ── Tests ────────────────────────────────────────────────────────────


class TestAuthFlowManagerNative:
    """Tests for native mode auth flow."""

    def test_initial_state(self) -> None:
        """Flow starts in PENDING state."""
        provider = _make_mock_provider()
        flow = AuthFlowManager(provider=provider)
        assert flow.flow_state == AuthFlowState.PENDING

    def test_run_native_timeout(self) -> None:
        """Flow times out if no callback received."""
        provider = _make_mock_provider()
        flow = AuthFlowManager(provider=provider, auth_timeout=0.5)

        with pytest.raises(AuthFlowTimeout):
            flow.run_native()

        assert flow.flow_state == AuthFlowState.TIMED_OUT

    def test_cancel_flow(self) -> None:
        """Cancelling flow raises AuthFlowCancelled."""
        provider = _make_mock_provider()
        flow = AuthFlowManager(provider=provider, auth_timeout=5.0)

        # Cancel after a brief delay
        def cancel_soon() -> None:
            time.sleep(0.3)
            flow.cancel()

        t = threading.Thread(target=cancel_soon, daemon=True)
        t.start()

        with pytest.raises(AuthFlowCancelled):
            flow.run_native()

        assert flow.flow_state == AuthFlowState.CANCELLED

    def test_run_native_success(self) -> None:
        """Successful native flow returns tokens and user_info."""
        provider = _make_mock_provider()
        flow = AuthFlowManager(provider=provider, auth_timeout=10.0, use_pkce=True)

        # We need to intercept the callback server to send the response
        original_start = OAuthCallbackServer.start

        def patched_start(self_server: OAuthCallbackServer) -> str:  # pylint: disable=unused-variable
            uri = original_start(self_server)
            # Now we know the port — send callback with correct state
            # The state is generated inside run_native, so we need to
            # grab it from the authorize URL
            return uri

        # Instead of patching start, we'll intercept build_authorize_url
        # to capture the state, then send the callback with that state
        captured_state: list[str] = []

        def capture_authorize_url(
            redirect_uri: str,  # pylint: disable=unused-argument
            state: str,
            pkce: Any = None,  # pylint: disable=unused-argument
            extra_params: Any = None,  # pylint: disable=unused-argument
        ) -> str:
            captured_state.append(state)
            return f"https://mock.idp/authorize?state={state}&redirect_uri={redirect_uri}"

        provider.build_authorize_url.side_effect = capture_authorize_url

        def send_callback_later() -> None:
            """Wait for the server to start, then send callback."""
            time.sleep(0.5)
            # Find the port from the flow's callback server
            if flow._callback_server and flow._callback_server._actual_port:
                port = flow._callback_server._actual_port
                state = captured_state[0] if captured_state else "unknown"
                _send_callback_to_server(port, code="auth_code", state=state, delay=0.0)

        t = threading.Thread(target=send_callback_later, daemon=True)
        t.start()

        result = flow.run_native()

        assert result.success is True
        assert result.tokens is not None
        assert result.tokens.access_token == "at_mock"
        assert result.user_info.get("sub") == "user123"
        assert flow.flow_state == AuthFlowState.COMPLETED

    def test_run_native_stores_tokens(self) -> None:
        """Native flow stores tokens when token_store is provided."""
        provider = _make_mock_provider()
        token_store = MemoryTokenStore()
        flow = AuthFlowManager(
            provider=provider,
            token_store=token_store,
            auth_timeout=10.0,
        )

        captured_state: list[str] = []

        def capture_authorize_url(
            redirect_uri: str,  # pylint: disable=unused-argument
            state: str,
            **kwargs: Any,  # pylint: disable=unused-argument
        ) -> str:
            captured_state.append(state)
            return f"https://mock.idp/authorize?state={state}"

        provider.build_authorize_url.side_effect = capture_authorize_url

        def send_callback_later() -> None:
            time.sleep(0.5)
            if flow._callback_server and flow._callback_server._actual_port:
                port = flow._callback_server._actual_port
                state = captured_state[0] if captured_state else ""
                _send_callback_to_server(port, code="code", state=state, delay=0.0)

        t = threading.Thread(target=send_callback_later, daemon=True)
        t.start()

        result = flow.run_native()
        assert result.success

        # Verify tokens were stored
        stored = asyncio.get_event_loop().run_until_complete(token_store.load("user123"))
        assert stored is not None
        assert stored.access_token == "at_mock"

    def test_run_native_provider_error(self) -> None:
        """Provider error in callback raises AuthenticationError."""
        provider = _make_mock_provider()
        flow = AuthFlowManager(provider=provider, auth_timeout=10.0)

        def send_error_callback() -> None:
            time.sleep(0.5)
            if flow._callback_server and flow._callback_server._actual_port:
                port = flow._callback_server._actual_port
                params = urlencode({"error": "access_denied", "error_description": "User denied"})
                with contextlib.suppress(Exception):
                    urlopen(f"http://127.0.0.1:{port}/callback?{params}", timeout=5)

        t = threading.Thread(target=send_error_callback, daemon=True)
        t.start()

        with pytest.raises(AuthenticationError, match=r"access_denied|User denied"):
            flow.run_native()

        assert flow.flow_state == AuthFlowState.FAILED

    def test_run_native_state_mismatch(self) -> None:
        """State mismatch raises AuthenticationError."""
        provider = _make_mock_provider()
        flow = AuthFlowManager(provider=provider, auth_timeout=10.0)

        def send_wrong_state() -> None:
            time.sleep(0.5)
            if flow._callback_server and flow._callback_server._actual_port:
                port = flow._callback_server._actual_port
                _send_callback_to_server(port, code="code", state="wrong_state", delay=0.0)

        t = threading.Thread(target=send_wrong_state, daemon=True)
        t.start()

        with pytest.raises(AuthenticationError, match=r"[Ss]tate"):
            flow.run_native()

    def test_show_window_called(self) -> None:
        """show_window callback is called with authorize URL."""
        provider = _make_mock_provider()
        flow = AuthFlowManager(provider=provider, auth_timeout=0.5)

        show_window = MagicMock(return_value="auth-window")
        close_window = MagicMock()

        with pytest.raises(AuthFlowTimeout):
            flow.run_native(
                show_window=show_window,
                close_window=close_window,
            )

        show_window.assert_called_once()
        args = show_window.call_args
        assert "https://mock.idp" in args[0][0]  # URL
        assert isinstance(args[0][1], dict)  # config

        # close_window should be called in finally block
        close_window.assert_called_once_with("auth-window")


class TestAuthFlowManagerDeploy:
    """Tests for deploy mode auth flow."""

    def test_run_deploy(self) -> None:
        """Deploy mode returns /auth/login URL."""
        provider = _make_mock_provider()
        flow = AuthFlowManager(provider=provider)
        url = flow.run_deploy(base_url="http://localhost:8080")
        assert url == "http://localhost:8080/auth/login"

    def test_run_deploy_no_base(self) -> None:
        """Deploy mode with empty base returns relative URL."""
        provider = _make_mock_provider()
        flow = AuthFlowManager(provider=provider)
        url = flow.run_deploy()
        assert url == "/auth/login"
