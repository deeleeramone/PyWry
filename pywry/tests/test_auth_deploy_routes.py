"""Integration tests for OAuth2 deploy mode FastAPI routes."""

from __future__ import annotations

import asyncio
import time

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from pywry.auth.deploy_routes import (
    AuthStateStore,
    LoginRateLimiter,
    _login_rate_limiter,
    _pending_auth_states,
    _verify_csrf_origin,
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


def _make_mock_deploy_settings(
    *,
    admin_users: list[str] | None = None,
    force_https: bool = False,
    auth_redirect_uri: str = "",
) -> MagicMock:
    """Create a mock DeploySettings."""
    settings = MagicMock()
    settings.auth_session_cookie = "pywry_session"
    settings.default_roles = ["viewer"]
    settings.admin_users = ["admin@test.com"] if admin_users is None else admin_users
    settings.force_https = force_https
    settings.auth_redirect_uri = auth_redirect_uri
    return settings


def _make_mock_session_store() -> MagicMock:
    """Create a mock SessionStore."""
    store = MagicMock()
    store.create_session = AsyncMock()
    store.get_session = AsyncMock(return_value=None)
    store.delete_session = AsyncMock()
    return store


def _build_app(
    *,
    provider: MagicMock | None = None,
    session_store: MagicMock | None = None,
    token_store: MemoryTokenStore | None = None,
    deploy_settings: MagicMock | None = None,
    auth_config: AuthConfig | None = None,
    inject_session: Any | None = None,
) -> tuple[FastAPI, dict[str, Any]]:
    """Create a FastAPI app with the auth router mounted.

    Returns ``(app, deps)`` where ``deps`` exposes the wiring dependencies for
    post-call assertions. If ``inject_session`` is provided, a middleware
    attaches it to ``request.state.session`` to simulate the auth middleware.
    """
    app = FastAPI()
    deps: dict[str, Any] = {
        "provider": provider or _make_mock_provider(),
        "session_store": session_store or _make_mock_session_store(),
        "token_store": token_store or MemoryTokenStore(),
        "deploy_settings": deploy_settings or _make_mock_deploy_settings(),
        "auth_config": auth_config
        or AuthConfig(
            enabled=True,
            token_secret="test-secret-key-for-testing",
            session_ttl=3600,
        ),
    }

    if inject_session is not None:

        @app.middleware("http")
        async def add_session(request, call_next):
            request.state.session = inject_session
            return await call_next(request)

    router = create_auth_router(**deps)
    app.include_router(router)
    return app, deps


def _create_test_app(
    provider: MagicMock | None = None,
    session_store: MagicMock | None = None,
    token_store: MemoryTokenStore | None = None,
    deploy_settings: MagicMock | None = None,
    auth_config: AuthConfig | None = None,
) -> FastAPI:
    """Compat shim that returns just the FastAPI app (without deps)."""
    app, _ = _build_app(
        provider=provider,
        session_store=session_store,
        token_store=token_store,
        deploy_settings=deploy_settings,
        auth_config=auth_config,
    )
    return app


def _run(coro: Any) -> Any:
    """Synchronously drive a coroutine to completion."""
    return asyncio.run(coro)


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


# ── Unit tests: _verify_csrf_origin ─────────────────────────────────


def _make_csrf_request(
    *,
    origin: str | None,
    referer: str | None,
    scheme: str = "http",
    host: str = "testserver",
) -> MagicMock:
    """Build a mock Request for _verify_csrf_origin coverage."""
    request = MagicMock()
    headers_dict: dict[str, str] = {}
    if origin is not None:
        headers_dict["origin"] = origin
    if referer is not None:
        headers_dict["referer"] = referer

    request.headers = MagicMock()
    request.headers.get = lambda key, default=None: headers_dict.get(key, default)
    request.url.scheme = scheme
    request.url.netloc = host
    return request


class TestVerifyCSRFOrigin:
    """Cover branches in _verify_csrf_origin()."""

    def test_referer_used_when_no_origin(self) -> None:
        """Referer is used as fallback when Origin is absent."""
        request = _make_csrf_request(
            origin=None,
            referer="http://testserver/some/path",
        )
        assert _verify_csrf_origin(request) is True

    def test_referer_with_invalid_url(self) -> None:
        """Invalid Referer (no scheme/netloc) is rejected."""
        request = _make_csrf_request(origin=None, referer="/relative/path")
        assert _verify_csrf_origin(request) is False

    def test_origin_null_falls_back_to_referer(self) -> None:
        """Origin='null' is treated as missing and falls back to Referer."""
        request = _make_csrf_request(
            origin="null",
            referer="http://testserver/foo",
        )
        assert _verify_csrf_origin(request) is True

    def test_origin_null_no_referer_rejected(self) -> None:
        """Origin='null' with no Referer is rejected."""
        request = _make_csrf_request(origin="null", referer=None)
        assert _verify_csrf_origin(request) is False

    def test_trusted_origins_allowed(self) -> None:
        """Origin in trusted_origins is accepted."""
        request = _make_csrf_request(
            origin="https://approved.example.com",
            referer=None,
        )
        assert (
            _verify_csrf_origin(
                request,
                trusted_origins=["https://approved.example.com/"],
            )
            is True
        )

    def test_trusted_origins_rejected(self) -> None:
        """Origin not in trusted_origins is rejected."""
        request = _make_csrf_request(
            origin="https://unknown.example.com",
            referer=None,
        )
        assert (
            _verify_csrf_origin(
                request,
                trusted_origins=["https://approved.example.com"],
            )
            is False
        )


# ── Unit tests: LoginRateLimiter ────────────────────────────────────


class TestLoginRateLimiterEviction:
    """Cover the eviction branch in LoginRateLimiter."""

    def test_old_entries_evicted(self) -> None:
        """Old entries fall outside the window and are popped, freeing the slot."""
        limiter = LoginRateLimiter(max_requests=2, window_seconds=0.05)
        assert limiter.is_allowed("1.1.1.1") is True
        assert limiter.is_allowed("1.1.1.1") is True
        # Now exhausted
        assert limiter.is_allowed("1.1.1.1") is False
        # Wait for window to pass
        time.sleep(0.1)
        # Old entries should be evicted
        assert limiter.is_allowed("1.1.1.1") is True


# ── Unit tests: AuthStateStore ──────────────────────────────────────


class TestAuthStateStoreInternals:
    """Cover internal AuthStateStore branches."""

    def test_eviction_on_capacity(self) -> None:
        """When at capacity, oldest entry is evicted on put()."""
        store = AuthStateStore(max_pending=2, max_age=600.0)
        now = time.time()
        _run(store.put("a", {"created_at": now - 10, "value": "A"}))
        _run(store.put("b", {"created_at": now - 5, "value": "B"}))
        # Adding a third should evict 'a' (oldest)
        _run(store.put("c", {"created_at": now, "value": "C"}))
        assert _run(store.contains("a")) is False
        assert _run(store.contains("b")) is True
        assert _run(store.contains("c")) is True

    def test_evict_expired_internal(self) -> None:
        """_evict_expired removes entries older than max_age."""
        store = AuthStateStore(max_pending=10, max_age=1.0)
        store._store["old"] = {"created_at": time.time() - 100}
        store._store["fresh"] = {"created_at": time.time()}
        store._evict_expired()
        assert "old" not in store._store
        assert "fresh" in store._store

    def test_cleanup_returns_count(self) -> None:
        """cleanup() returns the number of expired entries removed."""
        store = AuthStateStore(max_pending=10, max_age=1.0)
        # Pre-populate manually because put() itself runs _evict_expired.
        store._store["expired1"] = {"created_at": time.time() - 100}
        store._store["expired2"] = {"created_at": time.time() - 100}
        store._store["fresh"] = {"created_at": time.time()}
        removed = _run(store.cleanup())
        assert removed == 2

    def test_size_returns_count(self) -> None:
        """size() returns the current number of pending states."""
        store = AuthStateStore(max_pending=10, max_age=600.0)
        assert _run(store.size()) == 0
        _run(store.put("a", {"created_at": time.time()}))
        assert _run(store.size()) == 1


# ── /auth/login extra branches ──────────────────────────────────────


class TestLoginRedirectConfiguration:
    """Test /auth/login with configured URI and force_https."""

    def test_login_uses_configured_redirect_uri(self) -> None:
        """If auth_redirect_uri is configured, it overrides the request-derived URI."""
        _login_rate_limiter.reset()
        _pending_auth_states.clear()
        deploy = _make_mock_deploy_settings(
            auth_redirect_uri="https://my-app.example.com/auth/callback"
        )
        app, deps = _build_app(deploy_settings=deploy)
        client = TestClient(app, follow_redirects=False)
        resp = client.get("/auth/login")
        assert resp.status_code == 302
        deps["provider"].build_authorize_url.assert_called_once()
        call_kwargs = deps["provider"].build_authorize_url.call_args[1]
        assert call_kwargs["redirect_uri"] == "https://my-app.example.com/auth/callback"
        _login_rate_limiter.reset()

    def test_login_force_https_rewrites_uri(self) -> None:
        """force_https rewrites http:// to https:// for non-localhost hosts."""
        _login_rate_limiter.reset()
        _pending_auth_states.clear()
        deploy = _make_mock_deploy_settings(
            force_https=True,
            auth_redirect_uri="http://example.com/auth/callback",
        )
        app, deps = _build_app(deploy_settings=deploy)
        client = TestClient(app, follow_redirects=False)
        resp = client.get("/auth/login")
        assert resp.status_code == 302
        call_kwargs = deps["provider"].build_authorize_url.call_args[1]
        assert call_kwargs["redirect_uri"].startswith("https://example.com/")
        _login_rate_limiter.reset()

    def test_login_force_https_skips_localhost(self) -> None:
        """force_https leaves localhost http:// untouched."""
        _login_rate_limiter.reset()
        _pending_auth_states.clear()
        deploy = _make_mock_deploy_settings(
            force_https=True,
            auth_redirect_uri="http://localhost:8080/auth/callback",
        )
        app, deps = _build_app(deploy_settings=deploy)
        client = TestClient(app, follow_redirects=False)
        resp = client.get("/auth/login")
        assert resp.status_code == 302
        call_kwargs = deps["provider"].build_authorize_url.call_args[1]
        assert call_kwargs["redirect_uri"].startswith("http://localhost")
        _login_rate_limiter.reset()


# ── /auth/callback extra branches ───────────────────────────────────


class TestCallbackPopBranch:
    """Cover the auth_state pop returning None branch."""

    def test_callback_pop_returns_none(self) -> None:
        """If auth state is removed between contains() and pop(), 400 returned."""
        _pending_auth_states.clear()
        _pending_auth_states["state1"] = {
            "pkce_verifier": None,
            "redirect_uri": "http://testserver/auth/callback",
            "nonce": "nonce",
            "created_at": time.time(),
        }
        # Patch AuthStateStore.pop to return None even though contains() returns True
        from pywry.auth import deploy_routes as dr

        original_pop = dr._auth_state_store.pop

        async def patched_pop(_state: str) -> dict | None:
            return None

        dr._auth_state_store.pop = patched_pop  # type: ignore[assignment]
        try:
            app = _create_test_app()
            client = TestClient(app, follow_redirects=False)
            resp = client.get("/auth/callback?code=c&state=state1")
            assert resp.status_code == 400
            assert resp.json()["error"] == "invalid_state"
            assert "consumed" in resp.json()["error_description"]
        finally:
            dr._auth_state_store.pop = original_pop  # type: ignore[assignment]


class TestCallbackUserInfoFailure:
    """Cover the get_userinfo exception path in callback handler."""

    def test_user_info_failure_continues(self) -> None:
        """If get_userinfo raises, callback still creates session with 'unknown' id."""
        _pending_auth_states.clear()
        _pending_auth_states["s1"] = {
            "pkce_verifier": None,
            "redirect_uri": "http://testserver/auth/callback",
            "nonce": "nonce",
            "created_at": time.time(),
        }

        provider = _make_mock_provider()
        provider.get_userinfo = AsyncMock(side_effect=RuntimeError("downstream fail"))

        session_store = _make_mock_session_store()
        app = _create_test_app(provider=provider, session_store=session_store)
        client = TestClient(app, follow_redirects=False)
        resp = client.get("/auth/callback?code=c&state=s1")

        assert resp.status_code == 302
        # Session was created with 'unknown' user_id since get_userinfo failed
        session_store.create_session.assert_called_once()
        call_kwargs = session_store.create_session.call_args[1]
        assert call_kwargs["user_id"] == "unknown"


class TestCallbackHTTPSCookie:
    """Cover the cookie_secure branches in /auth/callback."""

    def test_cookie_secure_when_force_https(self) -> None:
        """force_https forces Secure=True on the session cookie."""
        _pending_auth_states.clear()
        _pending_auth_states["s1"] = {
            "pkce_verifier": None,
            "redirect_uri": "https://example.com/auth/callback",
            "nonce": "n",
            "created_at": time.time(),
        }
        deploy = _make_mock_deploy_settings(force_https=True)
        app = _create_test_app(deploy_settings=deploy)
        client = TestClient(app, follow_redirects=False)
        resp = client.get("/auth/callback?code=c&state=s1")
        assert resp.status_code == 302
        cookie_header = resp.headers.get("set-cookie", "")
        assert "Secure" in cookie_header


# ── /auth/refresh authenticated body ────────────────────────────────


def _mock_session(session_id: str = "sess_xyz") -> MagicMock:
    """Build a mock UserSession with sensible defaults."""
    return MagicMock(session_id=session_id, user_id="u1", roles=["viewer"])


class TestRefreshAuthenticated:
    """Cover the body of /auth/refresh when authenticated."""

    def test_refresh_no_existing_tokens(self) -> None:
        """No stored tokens for the session → 400 no_refresh_token."""
        token_store = MemoryTokenStore()
        app, _ = _build_app(token_store=token_store, inject_session=_mock_session())
        client = TestClient(app)
        resp = client.post(
            "/auth/refresh",
            headers={"origin": "http://testserver"},
        )
        assert resp.status_code == 400
        assert resp.json()["error"] == "no_refresh_token"

    def test_refresh_no_refresh_token_field(self) -> None:
        """Stored tokens but no refresh_token → 400 no_refresh_token."""
        token_store = MemoryTokenStore()
        _run(
            token_store.save(
                "sess_xyz",
                OAuthTokenSet(access_token="at", refresh_token=None, expires_in=3600),
            )
        )
        app, _ = _build_app(token_store=token_store, inject_session=_mock_session())
        client = TestClient(app)
        resp = client.post(
            "/auth/refresh",
            headers={"origin": "http://testserver"},
        )
        assert resp.status_code == 400

    def test_refresh_success(self) -> None:
        """Valid refresh returns new token info."""
        token_store = MemoryTokenStore()
        _run(
            token_store.save(
                "sess_xyz",
                OAuthTokenSet(
                    access_token="at_old",
                    refresh_token="rt_old",
                    expires_in=3600,
                ),
            )
        )
        app, _ = _build_app(token_store=token_store, inject_session=_mock_session())
        client = TestClient(app)
        resp = client.post(
            "/auth/refresh",
            headers={"origin": "http://testserver"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["expires_in"] == 3600

    def test_refresh_provider_failure(self) -> None:
        """Provider refresh failure → 500 with sanitised error message."""
        token_store = MemoryTokenStore()
        _run(
            token_store.save(
                "sess_xyz",
                OAuthTokenSet(
                    access_token="at_old",
                    refresh_token="rt_old",
                    expires_in=3600,
                ),
            )
        )
        provider = _make_mock_provider()
        provider.refresh_tokens = AsyncMock(side_effect=RuntimeError("broken"))

        app, _ = _build_app(
            provider=provider,
            token_store=token_store,
            inject_session=_mock_session(),
        )
        client = TestClient(app)
        resp = client.post(
            "/auth/refresh",
            headers={"origin": "http://testserver"},
        )
        assert resp.status_code == 500
        assert resp.json()["error"] == "refresh_failed"


# ── /auth/logout authenticated body ─────────────────────────────────


class TestLogoutAuthenticated:
    """Cover the body of /auth/logout when authenticated."""

    def test_logout_with_session_revokes(self) -> None:
        """Logout with active session revokes tokens and clears state."""
        token_store = MemoryTokenStore()
        _run(
            token_store.save(
                "sess_xyz",
                OAuthTokenSet(access_token="at", refresh_token="rt", expires_in=3600),
            )
        )
        provider = _make_mock_provider()
        session_store = _make_mock_session_store()

        app, _ = _build_app(
            provider=provider,
            token_store=token_store,
            session_store=session_store,
            inject_session=_mock_session(),
        )
        client = TestClient(app)
        resp = client.post(
            "/auth/logout",
            headers={"origin": "http://testserver"},
        )
        assert resp.status_code == 200
        provider.revoke_token.assert_awaited_once()
        session_store.delete_session.assert_awaited_once_with("sess_xyz")
        # The session-scoped tokens should be gone after logout
        assert _run(token_store.load("sess_xyz")) is None

    def test_logout_revoke_swallows_exception(self) -> None:
        """If revoke_token raises, logout still succeeds."""
        token_store = MemoryTokenStore()
        _run(
            token_store.save(
                "sess_xyz",
                OAuthTokenSet(access_token="at", refresh_token="rt", expires_in=3600),
            )
        )
        provider = _make_mock_provider()
        provider.revoke_token = AsyncMock(side_effect=RuntimeError("boom"))
        session_store = _make_mock_session_store()

        app, _ = _build_app(
            provider=provider,
            token_store=token_store,
            session_store=session_store,
            inject_session=_mock_session(),
        )
        client = TestClient(app)
        resp = client.post(
            "/auth/logout",
            headers={"origin": "http://testserver"},
        )
        # Logout still returns success despite revoke failure
        assert resp.status_code == 200


# ── /auth/userinfo and /auth/status authenticated bodies ────────────


class TestUserinfoAuthenticated:
    """Cover the userinfo body when authenticated."""

    def test_userinfo_authenticated(self) -> None:
        """Authenticated userinfo returns session details from the session metadata."""
        session = MagicMock(
            session_id="s1",
            user_id="u1",
            roles=["editor"],
            metadata={"user_info": {"name": "Tester"}},
        )
        app, _ = _build_app(inject_session=session)
        client = TestClient(app)
        resp = client.get("/auth/userinfo")
        assert resp.status_code == 200
        body = resp.json()
        assert body["user_id"] == "u1"
        assert body["roles"] == ["editor"]
        assert body["user_info"] == {"name": "Tester"}


class TestStatusAuthenticated:
    """Cover the status body when authenticated."""

    def test_status_authenticated(self) -> None:
        """Authenticated status returns expires_at + roles + authenticated=True."""
        now = time.time()
        session = MagicMock(
            session_id="s1",
            user_id="u1",
            roles=["viewer"],
            expires_at=now + 3600,
        )
        app, _ = _build_app(inject_session=session)
        client = TestClient(app)
        resp = client.get("/auth/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["authenticated"] is True
        assert body["user_id"] == "u1"
        assert body["expires_at"] == pytest.approx(now + 3600, abs=1)
