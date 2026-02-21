"""Integration tests for OAuth2 deploy mode FastAPI routes."""

from __future__ import annotations

import time

from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from pywry.auth.deploy_routes import (
    _login_rate_limiter,
    _pending_auth_states,
    cleanup_expired_states,
    create_auth_router,
)
from pywry.auth.token_store import MemoryTokenStore
from pywry.state.auth import AuthConfig
from pywry.state.types import OAuthTokenSet


# ── Helpers ──────────────────────────────────────────────────────────


def _make_mock_provider() -> MagicMock:
    """Create a mock OAuthProvider."""
    provider = MagicMock()
    provider.__class__.__name__ = "MockProvider"

    tokens = OAuthTokenSet(
        access_token="at_deploy_test",
        token_type="Bearer",
        refresh_token="rt_deploy_test",
        expires_in=3600,
        issued_at=time.time(),
    )
    provider.exchange_code = AsyncMock(return_value=tokens)
    provider.get_userinfo = AsyncMock(return_value={"sub": "user1", "email": "user@test.com"})
    provider.refresh_tokens = AsyncMock(
        return_value=OAuthTokenSet(
            access_token="at_refreshed",
            token_type="Bearer",
            refresh_token="rt_new",
            expires_in=3600,
            issued_at=time.time(),
        )
    )
    provider.revoke_token = AsyncMock()
    provider.build_authorize_url.return_value = "https://mock.idp/authorize?state=test"
    return provider


def _make_mock_deploy_settings() -> MagicMock:
    """Create a mock DeploySettings."""
    settings = MagicMock()
    settings.auth_session_cookie = "pywry_session"
    settings.default_roles = ["viewer"]
    settings.admin_users = ["admin@test.com"]
    return settings


def _make_mock_session_store() -> MagicMock:
    """Create a mock SessionStore."""
    store = MagicMock()
    store.create_session = AsyncMock()
    store.get_session = AsyncMock(return_value=None)
    store.delete_session = AsyncMock()
    return store


def _create_test_app(
    provider: MagicMock | None = None,
    session_store: MagicMock | None = None,
    token_store: MemoryTokenStore | None = None,
    deploy_settings: MagicMock | None = None,
    auth_config: AuthConfig | None = None,
) -> FastAPI:
    """Create a FastAPI app with the auth router mounted."""
    app = FastAPI()
    provider = provider or _make_mock_provider()
    session_store = session_store or _make_mock_session_store()
    token_store = token_store or MemoryTokenStore()
    deploy_settings = deploy_settings or _make_mock_deploy_settings()
    auth_config = auth_config or AuthConfig(
        enabled=True,
        token_secret="test-secret-key-for-testing",
        session_ttl=3600,
    )

    router = create_auth_router(
        provider=provider,
        session_store=session_store,
        token_store=token_store,
        deploy_settings=deploy_settings,
        auth_config=auth_config,
    )
    app.include_router(router)
    return app


# ── Tests ────────────────────────────────────────────────────────────


class TestLoginRoute:
    """Tests for GET /auth/login."""

    def test_login_redirects(self) -> None:
        """Login endpoint redirects to provider."""
        app = _create_test_app()
        client = TestClient(app, follow_redirects=False)
        resp = client.get("/auth/login")
        assert resp.status_code == 302
        assert "mock.idp" in resp.headers["location"]

    def test_login_stores_pending_state(self) -> None:
        """Login endpoint stores pending auth state."""
        _pending_auth_states.clear()
        app = _create_test_app()
        client = TestClient(app, follow_redirects=False)
        client.get("/auth/login")
        assert len(_pending_auth_states) >= 1


class TestCallbackRoute:
    """Tests for GET /auth/callback."""

    def test_callback_missing_state(self) -> None:
        """Callback without state returns 400."""
        app = _create_test_app()
        client = TestClient(app)
        resp = client.get("/auth/callback?code=test_code")
        assert resp.status_code == 400
        assert resp.json()["error"] == "invalid_state"

    def test_callback_invalid_state(self) -> None:
        """Callback with unknown state returns 400."""
        app = _create_test_app()
        client = TestClient(app)
        resp = client.get("/auth/callback?code=test_code&state=bogus")
        assert resp.status_code == 400
        assert resp.json()["error"] == "invalid_state"

    def test_callback_provider_error(self) -> None:
        """Callback with error param returns 400."""
        app = _create_test_app()
        client = TestClient(app)
        resp = client.get("/auth/callback?error=access_denied&error_description=User+denied")
        assert resp.status_code == 400
        data = resp.json()
        assert data["error"] == "access_denied"

    def test_callback_missing_code(self) -> None:
        """Callback without code returns 400."""
        _pending_auth_states.clear()
        _pending_auth_states["valid_state"] = {
            "pkce_verifier": None,
            "redirect_uri": "http://testserver/auth/callback",
            "nonce": "test_nonce",
            "created_at": time.time(),
        }
        app = _create_test_app()
        client = TestClient(app)
        resp = client.get("/auth/callback?state=valid_state")
        assert resp.status_code == 400
        assert resp.json()["error"] == "missing_code"

    def test_callback_success(self) -> None:
        """Successful callback creates session and redirects."""
        _pending_auth_states.clear()
        _pending_auth_states["good_state"] = {
            "pkce_verifier": "verifier123",
            "redirect_uri": "http://testserver/auth/callback",
            "nonce": "test_nonce",
            "created_at": time.time(),
        }

        session_store = _make_mock_session_store()
        token_store = MemoryTokenStore()
        app = _create_test_app(
            session_store=session_store,
            token_store=token_store,
        )
        client = TestClient(app, follow_redirects=False)
        resp = client.get("/auth/callback?code=auth_code_123&state=good_state")

        assert resp.status_code == 302
        assert resp.headers["location"] == "/"
        assert "pywry_session" in resp.headers.get("set-cookie", "")

        # Verify session was created
        session_store.create_session.assert_called_once()

    def test_callback_exchange_failure(self) -> None:
        """Token exchange failure returns 500 with generic error (no exception leak)."""
        _pending_auth_states.clear()
        _pending_auth_states["fail_state"] = {
            "pkce_verifier": None,
            "redirect_uri": "http://testserver/auth/callback",
            "nonce": "test_nonce",
            "created_at": time.time(),
        }

        provider = _make_mock_provider()
        provider.exchange_code = AsyncMock(side_effect=Exception("Network error"))

        app = _create_test_app(provider=provider)
        client = TestClient(app)
        resp = client.get("/auth/callback?code=bad_code&state=fail_state")
        assert resp.status_code == 500
        data = resp.json()
        assert data["error"] == "token_exchange_failed"
        # Must NOT leak internal exception message
        assert "Network error" not in data.get("error_description", "")
        assert data["error_description"] == "An internal error occurred"

    def test_callback_consumes_state(self) -> None:
        """State is single-use (removed after callback)."""
        _pending_auth_states.clear()
        _pending_auth_states["once_state"] = {
            "pkce_verifier": None,
            "redirect_uri": "http://testserver/auth/callback",
            "nonce": "test_nonce",
            "created_at": time.time(),
        }

        app = _create_test_app()
        client = TestClient(app, follow_redirects=False)
        # First call succeeds
        resp1 = client.get("/auth/callback?code=code1&state=once_state")
        assert resp1.status_code == 302

        # Second call fails
        resp2 = client.get("/auth/callback?code=code2&state=once_state")
        assert resp2.status_code == 400


class TestAuthenticatedRoutes:
    """Tests for routes requiring authentication."""

    def _make_authenticated_app(self) -> tuple[FastAPI, MagicMock, MemoryTokenStore]:
        """Create an app with session middleware that injects a mock session."""
        provider = _make_mock_provider()
        session_store = _make_mock_session_store()
        token_store = MemoryTokenStore()
        deploy_settings = _make_mock_deploy_settings()
        auth_config = AuthConfig(
            enabled=True,
            token_secret="test-secret",
            session_ttl=3600,
        )

        app = FastAPI()
        router = create_auth_router(
            provider=provider,
            session_store=session_store,
            token_store=token_store,
            deploy_settings=deploy_settings,
            auth_config=auth_config,
        )
        app.include_router(router)

        return app, provider, token_store

    def test_status_unauthenticated(self) -> None:
        """Status returns authenticated=false when no session."""
        app, _, _ = self._make_authenticated_app()
        client = TestClient(app)
        resp = client.get("/auth/status")
        assert resp.status_code == 200
        assert resp.json()["authenticated"] is False

    def test_userinfo_unauthenticated(self) -> None:
        """Userinfo returns 401 when no session."""
        app, _, _ = self._make_authenticated_app()
        client = TestClient(app)
        resp = client.get("/auth/userinfo")
        assert resp.status_code == 401

    def test_refresh_unauthenticated(self) -> None:
        """Refresh returns 401 when no session."""
        app, _, _ = self._make_authenticated_app()
        client = TestClient(app)
        resp = client.post("/auth/refresh", headers={"origin": "http://testserver"})
        assert resp.status_code == 401

    def test_logout_no_session(self) -> None:
        """Logout without session still returns success."""
        app, _, _ = self._make_authenticated_app()
        client = TestClient(app)
        resp = client.post("/auth/logout", headers={"origin": "http://testserver"})
        assert resp.status_code == 200
        assert resp.json()["success"] is True


class TestCleanupExpiredStates:
    """Tests for cleanup_expired_states utility."""

    def test_cleanup_removes_old_states(self) -> None:
        """Expired states are removed."""
        _pending_auth_states.clear()
        _pending_auth_states["old"] = {"created_at": time.time() - 700}
        _pending_auth_states["fresh"] = {"created_at": time.time()}

        removed = cleanup_expired_states(max_age=600.0)
        assert removed == 1
        assert "old" not in _pending_auth_states
        assert "fresh" in _pending_auth_states

    def test_cleanup_empty(self) -> None:
        """No-op when no states exist."""
        _pending_auth_states.clear()
        removed = cleanup_expired_states()
        assert removed == 0

    def test_admin_role_for_admin_user(self) -> None:
        """Admin users get admin role in session."""
        _pending_auth_states.clear()
        _pending_auth_states["admin_state"] = {
            "pkce_verifier": None,
            "redirect_uri": "http://testserver/auth/callback",
            "nonce": "test_nonce",
            "created_at": time.time(),
        }

        provider = _make_mock_provider()
        provider.get_userinfo = AsyncMock(return_value={"sub": "admin1", "email": "admin@test.com"})

        session_store = _make_mock_session_store()
        deploy_settings = _make_mock_deploy_settings()

        app = _create_test_app(
            provider=provider,
            session_store=session_store,
            deploy_settings=deploy_settings,
        )
        client = TestClient(app, follow_redirects=False)
        resp = client.get("/auth/callback?code=admin_code&state=admin_state")
        assert resp.status_code == 302

        # Verify the created session has admin role
        session_store.create_session.assert_called_once()
        call_kwargs = session_store.create_session.call_args[1]
        assert "admin" in call_kwargs["roles"]


class TestCSRFOriginVerification:
    """Tests for CSRF origin verification on POST routes."""

    def _make_app(self):
        return _create_test_app()

    def test_refresh_rejects_missing_origin(self) -> None:
        """POST /auth/refresh without Origin header returns 403."""
        app = self._make_app()
        client = TestClient(app)
        resp = client.post("/auth/refresh")
        assert resp.status_code == 403
        assert resp.json()["error"] == "csrf_failed"

    def test_logout_rejects_missing_origin(self) -> None:
        """POST /auth/logout without Origin header returns 403."""
        app = self._make_app()
        client = TestClient(app)
        resp = client.post("/auth/logout")
        assert resp.status_code == 403
        assert resp.json()["error"] == "csrf_failed"

    def test_refresh_rejects_cross_origin(self) -> None:
        """POST /auth/refresh with cross-origin Origin returns 403."""
        app = self._make_app()
        client = TestClient(app)
        resp = client.post(
            "/auth/refresh",
            headers={"origin": "https://evil.example.com"},
        )
        assert resp.status_code == 403

    def test_logout_accepts_same_origin(self) -> None:
        """POST /auth/logout with matching Origin is accepted (passes CSRF)."""
        app = self._make_app()
        client = TestClient(app)
        # testserver base URL is http://testserver
        resp = client.post(
            "/auth/logout",
            headers={"origin": "http://testserver"},
        )
        # Should pass CSRF and reach logout logic (200 success, no session)
        assert resp.status_code == 200
        assert resp.json()["success"] is True


class TestLoginRateLimiting:
    """Tests for rate limiting on /auth/login."""

    def test_login_rate_limit_exceeded(self) -> None:
        """Login returns 429 after too many attempts."""
        _login_rate_limiter.reset()
        app = _create_test_app()
        client = TestClient(app, follow_redirects=False)

        # Exhaust the rate limit (default 10 per 60s)
        for _ in range(10):
            resp = client.get("/auth/login")
            assert resp.status_code == 302

        # 11th request should be rate limited
        resp = client.get("/auth/login")
        assert resp.status_code == 429
        assert resp.json()["error"] == "rate_limited"

        _login_rate_limiter.reset()

    def test_login_within_limit(self) -> None:
        """Login succeeds within rate limit."""
        _login_rate_limiter.reset()
        app = _create_test_app()
        client = TestClient(app, follow_redirects=False)

        resp = client.get("/auth/login")
        assert resp.status_code == 302

        _login_rate_limiter.reset()
