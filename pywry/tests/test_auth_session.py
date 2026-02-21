"""Tests for OAuth2 session manager."""

# pylint: disable=redefined-outer-name

from __future__ import annotations

import asyncio
import time

from unittest.mock import AsyncMock, MagicMock

import pytest

from pywry.auth.session import SessionManager
from pywry.auth.token_store import MemoryTokenStore
from pywry.exceptions import TokenExpiredError, TokenRefreshError
from pywry.state.types import OAuthTokenSet


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture()
def mock_provider() -> MagicMock:
    """Create a mock OAuth provider."""
    provider = MagicMock()
    provider.__class__.__name__ = "MockProvider"
    provider.revoke_token = AsyncMock()
    provider.refresh_tokens = AsyncMock(
        return_value=OAuthTokenSet(
            access_token="at_refreshed",
            token_type="Bearer",
            refresh_token="rt_new",
            expires_in=3600,
            issued_at=time.time(),
        )
    )
    return provider


@pytest.fixture()
def token_store() -> MemoryTokenStore:
    """Create a memory token store."""
    return MemoryTokenStore()


@pytest.fixture()
def valid_tokens() -> OAuthTokenSet:
    """Create a valid (non-expired) token set."""
    return OAuthTokenSet(
        access_token="at_valid",
        token_type="Bearer",
        refresh_token="rt_valid",
        expires_in=3600,
        issued_at=time.time(),
    )


@pytest.fixture()
def expired_tokens() -> OAuthTokenSet:
    """Create an expired token set."""
    return OAuthTokenSet(
        access_token="at_expired",
        token_type="Bearer",
        refresh_token="rt_for_refresh",
        expires_in=3600,
        issued_at=time.time() - 7200,  # 2 hours ago
    )


def _run(coro):
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)


# ── Tests ────────────────────────────────────────────────────────────


class TestSessionManagerInit:
    """Tests for SessionManager initialization."""

    def test_initialize_no_stored_tokens(
        self,
        mock_provider: MagicMock,
        token_store: MemoryTokenStore,
    ) -> None:
        """Initialize with empty store returns None."""
        mgr = SessionManager(mock_provider, token_store)
        result = _run(mgr.initialize())
        assert result is None

    def test_initialize_with_valid_tokens(
        self,
        mock_provider: MagicMock,
        token_store: MemoryTokenStore,
        valid_tokens: OAuthTokenSet,
    ) -> None:
        """Initialize with valid stored tokens returns them."""
        _run(token_store.save("default", valid_tokens))
        mgr = SessionManager(mock_provider, token_store)
        result = _run(mgr.initialize())
        assert result is not None
        assert result.access_token == "at_valid"

    def test_initialize_with_expired_tokens_refreshes(
        self,
        mock_provider: MagicMock,
        token_store: MemoryTokenStore,
        expired_tokens: OAuthTokenSet,
    ) -> None:
        """Initialize with expired tokens tries to refresh."""
        _run(token_store.save("default", expired_tokens))
        mgr = SessionManager(mock_provider, token_store)
        result = _run(mgr.initialize())
        assert result is not None
        assert result.access_token == "at_refreshed"
        mock_provider.refresh_tokens.assert_called_once_with("rt_for_refresh")

    def test_initialize_expired_no_refresh_token(
        self,
        mock_provider: MagicMock,
        token_store: MemoryTokenStore,
    ) -> None:
        """Initialize with expired tokens and no refresh token returns None."""
        no_refresh = OAuthTokenSet(
            access_token="at_old",
            expires_in=3600,
            issued_at=time.time() - 7200,
        )
        _run(token_store.save("default", no_refresh))
        mgr = SessionManager(mock_provider, token_store)
        result = _run(mgr.initialize())
        assert result is None


class TestSessionManagerTokenAccess:
    """Tests for get_access_token and refresh."""

    def test_get_access_token_valid(
        self,
        mock_provider: MagicMock,
        token_store: MemoryTokenStore,
        valid_tokens: OAuthTokenSet,
    ) -> None:
        """get_access_token returns token when valid."""
        mgr = SessionManager(mock_provider, token_store)
        _run(mgr.save_tokens(valid_tokens))
        token = _run(mgr.get_access_token())
        assert token == "at_valid"

    def test_get_access_token_no_tokens(
        self,
        mock_provider: MagicMock,
        token_store: MemoryTokenStore,
    ) -> None:
        """get_access_token raises when no tokens available."""
        mgr = SessionManager(mock_provider, token_store)
        with pytest.raises(TokenExpiredError, match="No tokens"):
            _run(mgr.get_access_token())

    def test_refresh_success(
        self,
        mock_provider: MagicMock,
        token_store: MemoryTokenStore,
        valid_tokens: OAuthTokenSet,
    ) -> None:
        """Explicit refresh returns new tokens."""
        mgr = SessionManager(mock_provider, token_store)
        _run(mgr.save_tokens(valid_tokens))
        new_tokens = _run(mgr.refresh())
        assert new_tokens.access_token == "at_refreshed"

        # Verify tokens were persisted
        stored = _run(token_store.load("default"))
        assert stored is not None
        assert stored.access_token == "at_refreshed"

    def test_refresh_no_refresh_token(
        self,
        mock_provider: MagicMock,
        token_store: MemoryTokenStore,
    ) -> None:
        """Refresh without refresh_token raises TokenRefreshError."""
        no_refresh = OAuthTokenSet(
            access_token="at_no_refresh",
            expires_in=3600,
            issued_at=time.time(),
        )
        mgr = SessionManager(mock_provider, token_store)
        _run(mgr.save_tokens(no_refresh))

        with pytest.raises(TokenRefreshError, match="No refresh token"):
            _run(mgr.refresh())

    def test_refresh_calls_reauth_callback(
        self,
        mock_provider: MagicMock,
        token_store: MemoryTokenStore,
    ) -> None:
        """Refresh failure triggers on_reauth_required callback."""
        no_refresh = OAuthTokenSet(
            access_token="at",
            expires_in=3600,
            issued_at=time.time(),
        )

        reauth_called = []
        mgr = SessionManager(
            mock_provider,
            token_store,
            on_reauth_required=lambda: reauth_called.append(True),
        )
        _run(mgr.save_tokens(no_refresh))

        with pytest.raises(TokenRefreshError):
            _run(mgr.refresh())

        assert reauth_called


class TestSessionManagerLogout:
    """Tests for session logout."""

    def test_logout_clears_tokens(
        self,
        mock_provider: MagicMock,
        token_store: MemoryTokenStore,
        valid_tokens: OAuthTokenSet,
    ) -> None:
        """Logout deletes stored tokens."""
        mgr = SessionManager(mock_provider, token_store)
        _run(mgr.save_tokens(valid_tokens))
        _run(mgr.logout())

        assert not _run(token_store.exists("default"))
        assert mgr._current_tokens is None

    def test_logout_revokes_token(
        self,
        mock_provider: MagicMock,
        token_store: MemoryTokenStore,
        valid_tokens: OAuthTokenSet,
    ) -> None:
        """Logout attempts token revocation."""
        mgr = SessionManager(mock_provider, token_store)
        _run(mgr.save_tokens(valid_tokens))
        _run(mgr.logout())
        mock_provider.revoke_token.assert_called_once()

    def test_logout_empty_is_safe(
        self,
        mock_provider: MagicMock,
        token_store: MemoryTokenStore,
    ) -> None:
        """Logout with no tokens does not raise."""
        mgr = SessionManager(mock_provider, token_store)
        _run(mgr.logout())  # Should not raise


class TestSessionManagerRefreshScheduling:
    """Tests for background refresh scheduling."""

    def test_schedule_refresh_timer(
        self,
        mock_provider: MagicMock,
        token_store: MemoryTokenStore,
        valid_tokens: OAuthTokenSet,
    ) -> None:
        """Saving tokens schedules a refresh timer."""
        mgr = SessionManager(mock_provider, token_store, refresh_buffer_seconds=60)
        _run(mgr.save_tokens(valid_tokens))
        assert mgr._refresh_timer is not None
        assert mgr._refresh_timer.is_alive()
        mgr._cancel_refresh_timer()

    def test_no_timer_without_expiry(
        self,
        mock_provider: MagicMock,
        token_store: MemoryTokenStore,
    ) -> None:
        """Tokens without expires_in don't schedule a timer."""
        no_expiry = OAuthTokenSet(
            access_token="at_forever",
            expires_in=None,
            issued_at=time.time(),
        )
        mgr = SessionManager(mock_provider, token_store)
        _run(mgr.save_tokens(no_expiry))
        assert mgr._refresh_timer is None

    def test_cancel_refresh_timer(
        self,
        mock_provider: MagicMock,
        token_store: MemoryTokenStore,
        valid_tokens: OAuthTokenSet,
    ) -> None:
        """_cancel_refresh_timer stops the timer."""
        mgr = SessionManager(mock_provider, token_store)
        _run(mgr.save_tokens(valid_tokens))
        mgr._cancel_refresh_timer()
        assert mgr._refresh_timer is None
