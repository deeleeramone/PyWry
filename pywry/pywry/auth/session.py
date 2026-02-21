"""OAuth2 session manager with automatic token refresh.

Manages the lifecycle of OAuth2 tokens including persistence,
validation, and background refresh scheduling. Uses threading.Timer
for refresh scheduling to match the thread-based auth flow pattern.
"""

# pylint: disable=logging-too-many-args

from __future__ import annotations

import contextlib
import logging
import threading

from typing import TYPE_CHECKING

from ..exceptions import TokenExpiredError, TokenRefreshError
from ..state.sync_helpers import run_async


if TYPE_CHECKING:
    from collections.abc import Callable

    from ..state.base import SessionStore
    from ..state.types import OAuthTokenSet
    from .providers import OAuthProvider
    from .token_store import TokenStore


logger = logging.getLogger("pywry.auth")


class SessionManager:
    """Manages OAuth2 token lifecycle with automatic refresh.

    Parameters
    ----------
    provider : OAuthProvider
        The OAuth2 provider for token refresh.
    token_store : TokenStore
        Store for persisting tokens.
    session_key : str
        Key used to identify stored tokens (e.g., user ID).
    session_store : SessionStore, optional
        Session store for internal session management.
    refresh_buffer_seconds : int
        Seconds before token expiry to trigger refresh (default ``60``).
    on_reauth_required : callable, optional
        Callback invoked when refresh fails and re-authentication is needed.
        Signature: ``on_reauth_required() -> None``.
    """

    def __init__(
        self,
        provider: OAuthProvider,
        token_store: TokenStore,
        session_key: str = "default",
        session_store: SessionStore | None = None,
        refresh_buffer_seconds: int = 60,
        on_reauth_required: Callable[[], None] | None = None,
    ) -> None:
        """Initialize the session manager."""
        self.provider = provider
        self.token_store = token_store
        self.session_key = session_key
        self.session_store = session_store
        self.refresh_buffer_seconds = refresh_buffer_seconds
        self.on_reauth_required = on_reauth_required

        self._refresh_timer: threading.Timer | None = None
        self._lock = threading.Lock()
        self._current_tokens: OAuthTokenSet | None = None

    async def initialize(self) -> OAuthTokenSet | None:
        """Load existing tokens from store and validate.

        Returns
        -------
        OAuthTokenSet or None
            The stored tokens if valid, or None if no tokens
            are stored or they have expired.
        """
        tokens = await self.token_store.load(self.session_key)
        if tokens is None:
            return None

        if tokens.is_expired:
            # Try to refresh
            if tokens.refresh_token:
                try:
                    tokens = await self.provider.refresh_tokens(tokens.refresh_token)
                    await self.token_store.save(self.session_key, tokens)
                    self._current_tokens = tokens
                    self._schedule_refresh(tokens)
                except Exception as exc:
                    logger.warning("Token refresh on init failed: %s", exc)
                    return None
                return tokens
            return None

        self._current_tokens = tokens
        self._schedule_refresh(tokens)
        return tokens

    async def save_tokens(self, tokens: OAuthTokenSet) -> None:
        """Persist tokens and schedule background refresh.

        Parameters
        ----------
        tokens : OAuthTokenSet
            The token set to save.
        """
        await self.token_store.save(self.session_key, tokens)
        with self._lock:
            self._current_tokens = tokens
        self._schedule_refresh(tokens)
        logger.debug("Tokens saved for session %s", self.session_key)

    async def get_access_token(self) -> str:
        """Get a valid access token, refreshing if near expiry.

        Returns
        -------
        str
            A valid access token.

        Raises
        ------
        TokenExpiredError
            If the token is expired and cannot be refreshed.
        """
        with self._lock:
            tokens = self._current_tokens

        if tokens is None:
            tokens = await self.token_store.load(self.session_key)

        if tokens is None:
            msg = "No tokens available"
            raise TokenExpiredError(msg)

        if tokens.is_expired:
            tokens = await self.refresh()

        return tokens.access_token

    async def refresh(self) -> OAuthTokenSet:
        """Refresh the access token.

        Uses the stored refresh token to obtain a new access token.
        Falls back to ``on_reauth_required`` if refresh fails.

        Returns
        -------
        OAuthTokenSet
            A new token set.

        Raises
        ------
        TokenRefreshError
            If refresh fails and no re-auth callback is set.
        """
        with self._lock:
            tokens = self._current_tokens

        if tokens is None:
            tokens = await self.token_store.load(self.session_key)

        if tokens is None or not tokens.refresh_token:
            if self.on_reauth_required:
                self.on_reauth_required()
                msg = "Re-authentication required"
            else:
                msg = "No refresh token available"
            raise TokenRefreshError(msg)

        try:
            new_tokens = await self.provider.refresh_tokens(tokens.refresh_token)
            await self.token_store.save(self.session_key, new_tokens)
            with self._lock:
                self._current_tokens = new_tokens
            self._schedule_refresh(new_tokens)
            logger.info("Tokens refreshed for session %s", self.session_key)
        except Exception as exc:
            logger.exception("Token refresh failed")
            if self.on_reauth_required:
                self.on_reauth_required()
            raise TokenRefreshError(
                f"Token refresh failed: {exc}",
                provider=self.provider.__class__.__name__,
            ) from exc

        return new_tokens

    async def logout(self) -> None:
        """Clear all tokens and cancel scheduled refresh.

        Optionally revokes the token at the provider.
        """
        self._cancel_refresh_timer()

        with self._lock:
            tokens = self._current_tokens
            self._current_tokens = None

        # Best-effort token revocation
        if tokens and tokens.access_token:
            with contextlib.suppress(Exception):
                await self.provider.revoke_token(tokens.access_token)

        await self.token_store.delete(self.session_key)
        logger.info("Session %s logged out", self.session_key)

    def _schedule_refresh(self, tokens: OAuthTokenSet) -> None:
        """Schedule a background token refresh before expiry.

        Parameters
        ----------
        tokens : OAuthTokenSet
            The current tokens (used to calculate refresh timing).
        """
        self._cancel_refresh_timer()

        if tokens.expires_at is None:
            return  # No expiry, no need to refresh

        import time

        delay = tokens.expires_at - time.time() - self.refresh_buffer_seconds
        if delay <= 0:
            # Already near/past expiry — refresh immediately
            delay = 1.0

        logger.debug(
            "Scheduling token refresh in %.0fs for session %s",
            delay,
            self.session_key,
        )

        self._refresh_timer = threading.Timer(delay, self._do_background_refresh)
        self._refresh_timer.daemon = True
        self._refresh_timer.start()

    def _do_background_refresh(self) -> None:
        """Execute a background token refresh (runs on Timer thread)."""
        try:
            run_async(self.refresh(), timeout=30.0)
        except Exception:
            logger.exception("Background token refresh failed")
            if self.on_reauth_required:
                self.on_reauth_required()

    def _cancel_refresh_timer(self) -> None:
        """Cancel any pending refresh timer."""
        if self._refresh_timer is not None:
            self._refresh_timer.cancel()
            self._refresh_timer = None
