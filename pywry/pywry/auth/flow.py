"""OAuth2 authentication flow orchestrator.

Provides AuthFlowManager that coordinates the complete OAuth2 flow
in both native window mode (ephemeral callback server) and deploy
mode (server-side routes). Uses threading.Event for blocking
synchronization between the main thread and auth callbacks.
"""

# pylint: disable=logging-too-many-args,too-many-branches,too-many-statements

from __future__ import annotations

import contextlib
import logging
import secrets
import threading

from typing import TYPE_CHECKING, Any

from ..exceptions import (
    AuthenticationError,
    AuthFlowCancelled,
    AuthFlowTimeout,
)
from ..state.sync_helpers import run_async
from ..state.types import AuthFlowResult, AuthFlowState
from .callback_server import OAuthCallbackServer
from .pkce import PKCEChallenge


if TYPE_CHECKING:
    from .providers import OAuthProvider
    from .session import SessionManager
    from .token_store import TokenStore


logger = logging.getLogger("pywry.auth")


class AuthFlowManager:
    """Orchestrates OAuth2 authentication flows.

    Supports two modes:

    - **Native mode**: Opens a dedicated auth window pointing at the
      provider's authorize URL, captures the redirect on an ephemeral
      localhost HTTP server, and exchanges the code for tokens.

    - **Deploy mode**: Returns the ``/auth/login`` URL for the frontend
      to navigate to. The server-side routes handle the actual flow.

    Parameters
    ----------
    provider : OAuthProvider
        The configured OAuth2 provider.
    token_store : TokenStore, optional
        Store for persisting tokens after successful auth.
    session_manager : SessionManager, optional
        Session manager for token lifecycle.
    use_pkce : bool
        Whether to use PKCE (default ``True``).
    auth_timeout : float
        Seconds to wait for the auth callback (default ``120``).
    """

    def __init__(
        self,
        provider: OAuthProvider,
        token_store: TokenStore | None = None,
        session_manager: SessionManager | None = None,
        use_pkce: bool = True,
        auth_timeout: float = 120.0,
    ) -> None:
        """Initialize the auth flow manager."""
        self.provider = provider
        self.token_store = token_store
        self.session_manager = session_manager
        self.use_pkce = use_pkce
        self.auth_timeout = auth_timeout

        self._flow_state = AuthFlowState.PENDING
        self._flow_id: str | None = None
        self._cancellation_event = threading.Event()
        self._callback_server: OAuthCallbackServer | None = None

    @property
    def flow_state(self) -> AuthFlowState:
        """Current state of the auth flow."""
        return self._flow_state

    def run_native(  # noqa: C901, PLR0912, PLR0915
        self,
        show_window: Any | None = None,
        close_window: Any | None = None,
        window_config: dict[str, Any] | None = None,
    ) -> AuthFlowResult:
        """Run the OAuth2 flow in native window mode.

        This method blocks until authentication completes, times out,
        or is cancelled.

        Parameters
        ----------
        show_window : callable, optional
            Function to open the auth window. Signature:
            ``show_window(url: str, config: dict) -> str`` (returns label).
            If None, the URL is logged for manual navigation.
        close_window : callable, optional
            Function to close the auth window. Signature:
            ``close_window(label: str) -> None``.
        window_config : dict, optional
            Additional window configuration (title, width, height).

        Returns
        -------
        AuthFlowResult
            The result of the authentication flow.

        Raises
        ------
        AuthFlowTimeout
            If the callback is not received within the timeout.
        AuthFlowCancelled
            If the user closes the auth window or aborts.
        AuthenticationError
            If the provider returns an error.
        """
        self._flow_id = secrets.token_urlsafe(16)
        self._flow_state = AuthFlowState.IN_PROGRESS
        self._cancellation_event.clear()

        provider_name = self.provider.__class__.__name__

        # 1. Start callback server
        self._callback_server = OAuthCallbackServer()
        redirect_uri = self._callback_server.start()
        logger.info("Auth flow %s: callback server at %s", self._flow_id, redirect_uri)

        auth_window_label: str | None = None

        try:
            # 2. Generate PKCE + state
            pkce: PKCEChallenge | None = None
            if self.use_pkce:
                pkce = PKCEChallenge.generate()

            state = secrets.token_urlsafe(32)

            # 3. Build authorize URL
            authorize_url = self.provider.build_authorize_url(
                redirect_uri=redirect_uri,
                state=state,
                pkce=pkce,
            )

            # 4. Open auth window (or log URL)
            config = {
                "title": "Sign In",
                "width": 500,
                "height": 700,
                "center": True,
                "resizable": True,
                **(window_config or {}),
            }

            if show_window is not None:
                auth_window_label = show_window(authorize_url, config)
                logger.debug("Auth window opened: %s", auth_window_label)
            else:
                logger.info("Open this URL to authenticate: %s", authorize_url)

            # 5. Wait for callback with cancellation polling
            result = self._wait_for_callback_with_cancellation()

            if result is None:
                # Timeout
                self._flow_state = AuthFlowState.TIMED_OUT
                msg = f"Authentication timed out after {self.auth_timeout}s"
                raise AuthFlowTimeout(  # noqa: TRY301
                    msg,
                    timeout=self.auth_timeout,
                    provider=provider_name,
                    flow_id=self._flow_id,
                )

            # Check for errors from provider
            if result.get("error"):
                self._flow_state = AuthFlowState.FAILED
                error_desc = result.get("error_description") or result["error"]
                msg = f"Provider returned error: {error_desc}"
                raise AuthenticationError(msg, provider=provider_name, flow_id=self._flow_id)  # noqa: TRY301

            # Validate state
            if result.get("state") != state:
                self._flow_state = AuthFlowState.FAILED
                msg = "State parameter mismatch (possible CSRF attack)"
                raise AuthenticationError(msg, provider=provider_name, flow_id=self._flow_id)  # noqa: TRY301

            code = result.get("code")
            if not code:
                self._flow_state = AuthFlowState.FAILED
                msg = "No authorization code in callback"
                raise AuthenticationError(msg, provider=provider_name, flow_id=self._flow_id)  # noqa: TRY301

            # 6. Exchange code for tokens
            tokens = run_async(
                self.provider.exchange_code(
                    code=code,
                    redirect_uri=redirect_uri,
                    pkce_verifier=pkce.verifier if pkce else None,
                ),
                timeout=30.0,
            )

            # 7. Fetch user info
            user_info: dict[str, Any] = {}
            try:
                user_info = run_async(
                    self.provider.get_userinfo(tokens.access_token),
                    timeout=10.0,
                )
            except Exception as exc:
                logger.warning("Failed to fetch user info: %s", exc)

            # 8. Store tokens if token_store is available
            if self.token_store:
                user_id = (
                    user_info.get("sub")
                    or user_info.get("id")
                    or user_info.get("email")
                    or "default"
                )
                run_async(self.token_store.save(str(user_id), tokens))

            # 9. Initialize session manager if available
            if self.session_manager:
                run_async(self.session_manager.save_tokens(tokens))

            self._flow_state = AuthFlowState.COMPLETED
            logger.info("Auth flow %s completed successfully", self._flow_id)

            return AuthFlowResult(
                success=True,
                tokens=tokens,
                user_info=user_info,
            )

        except (AuthFlowTimeout, AuthFlowCancelled):
            raise
        except AuthenticationError:
            raise
        except Exception as exc:
            self._flow_state = AuthFlowState.FAILED
            msg = f"Authentication flow failed: {exc}"
            raise AuthenticationError(msg, provider=provider_name, flow_id=self._flow_id) from exc
        finally:
            # Clean up
            if self._callback_server:
                self._callback_server.stop()
                self._callback_server = None
            if auth_window_label and close_window is not None:
                with contextlib.suppress(Exception):
                    close_window(auth_window_label)

    def run_deploy(self, base_url: str = "") -> str:
        """Get the login URL for deploy mode.

        In deploy mode, the actual OAuth2 flow is handled server-side
        by the routes in ``deploy_routes.py``. This method simply
        returns the URL that the frontend should navigate to.

        Parameters
        ----------
        base_url : str
            The base URL of the deploy server (e.g. ``http://localhost:8080``).

        Returns
        -------
        str
            The ``/auth/login`` URL.
        """
        return f"{base_url}/auth/login"

    def authenticate(
        self,
        app: Any,
        show_window: Any | None = None,
        close_window: Any | None = None,
        window_config: dict[str, Any] | None = None,
    ) -> AuthFlowResult:
        """Unified authentication entry point.

        Detects the app mode and runs the appropriate flow.

        Parameters
        ----------
        app : PyWry
            The PyWry application instance.
        show_window : callable, optional
            Window opener for native mode.
        close_window : callable, optional
            Window closer for native mode.
        window_config : dict, optional
            Window configuration for native mode.

        Returns
        -------
        AuthFlowResult
            The authentication result.
        """
        mode_enum = getattr(app, "_mode_enum", None)

        # Check if we're in browser/deploy mode
        if mode_enum is not None:
            try:
                from ..models import WindowMode

                if mode_enum == WindowMode.BROWSER:
                    login_url = self.run_deploy()
                    return AuthFlowResult(
                        success=False,
                        error=f"Navigate to {login_url} to authenticate (deploy mode)",
                    )
            except ImportError:
                pass

        # Native mode — provide a default show_window that opens the system browser
        if show_window is None:
            import webbrowser

            def _open_browser(url: str, _config: dict[str, Any]) -> str:
                webbrowser.open(url)
                return "__browser__"

            show_window = _open_browser
            # No close needed for system browser
            close_window = close_window or (lambda _label: None)

        return self.run_native(
            show_window=show_window,
            close_window=close_window,
            window_config=window_config,
        )

    def cancel(self) -> None:
        """Cancel the current authentication flow.

        Sets the cancellation event which unblocks ``_wait_for_callback_with_cancellation``.
        """
        self._flow_state = AuthFlowState.CANCELLED
        self._cancellation_event.set()
        if self._callback_server:
            self._callback_server.stop()

    def _wait_for_callback_with_cancellation(self) -> dict[str, Any] | None:
        """Wait for the callback with cancellation support.

        Polls both the callback server result and the cancellation event
        every 100ms. Returns the callback result, or raises
        ``AuthFlowCancelled`` if cancelled, or returns ``None`` on timeout.
        """
        deadline = threading.Event()
        elapsed = 0.0
        poll_interval = 0.1

        while elapsed < self.auth_timeout:
            # Check cancellation
            if self._cancellation_event.is_set():
                self._flow_state = AuthFlowState.CANCELLED
                provider_name = self.provider.__class__.__name__
                msg = "Authentication flow was cancelled"
                raise AuthFlowCancelled(msg, provider=provider_name, flow_id=self._flow_id)

            # Check callback server
            if self._callback_server and self._callback_server._result_event.is_set():
                return self._callback_server._result

            deadline.wait(timeout=poll_interval)
            elapsed += poll_interval

        return None
