"""FastAPI routes for OAuth2 authentication in deploy mode.

Provides login, callback, refresh, logout, userinfo, and status
endpoints that integrate with the existing session store and auth middleware.
"""

# pylint: disable=logging-too-many-args,too-many-statements

from __future__ import annotations

import asyncio
import collections
import contextlib
import logging
import secrets
import threading
import time

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse

from ..state.auth import AuthConfig, generate_session_token
from ..state.types import UserSession
from .pkce import PKCEChallenge


if TYPE_CHECKING:
    from ..config import DeploySettings
    from ..state.base import SessionStore
    from .providers import OAuthProvider
    from .token_store import TokenStore


logger = logging.getLogger("pywry.auth")


# ── CSRF Origin Verification ────────────────────────────────────────


def _verify_csrf_origin(request: Request, *, trusted_origins: list[str] | None = None) -> bool:
    """Verify that POST requests originate from a trusted origin.

    Checks the ``Origin`` header first, then falls back to ``Referer``.
    Returns ``True`` if the origin is trusted, ``False`` otherwise.

    Parameters
    ----------
    request : Request
        The incoming request.
    trusted_origins : list[str] | None
        Allowed origins (e.g. ``["https://myapp.example.com"]``).
        If ``None`` or empty, allows same-origin requests only.
    """
    origin = request.headers.get("origin")
    referer = request.headers.get("referer")

    # Determine the source origin
    source_origin: str | None = None
    if origin and origin != "null":
        source_origin = origin.rstrip("/")
    elif referer:
        # Extract scheme + host from Referer
        from urllib.parse import urlparse

        parsed = urlparse(referer)
        if parsed.scheme and parsed.netloc:
            source_origin = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")

    if source_origin is None:
        # No Origin/Referer — could be a same-origin navigation (browser omits for same-origin GET)
        # For POST requests we reject (fail-closed)
        return False

    # If specific trusted origins are provided, check against them
    if trusted_origins:
        return source_origin in [o.rstrip("/") for o in trusted_origins]

    # Same-origin check: compare against the request's own host
    request_origin = f"{request.url.scheme}://{request.url.netloc}".rstrip("/")
    return source_origin == request_origin


# ── Login Rate Limiter ───────────────────────────────────────────────


class LoginRateLimiter:
    """Simple in-process sliding-window rate limiter for login requests.

    Limits by client IP address with a configurable window and max requests.

    Parameters
    ----------
    max_requests : int
        Maximum number of requests allowed per window.
    window_seconds : float
        Time window in seconds.
    """

    def __init__(self, max_requests: int = 10, window_seconds: float = 60.0) -> None:
        self._max_requests = max_requests
        self._window = window_seconds
        self._requests: dict[str, collections.deque] = {}
        self._lock = threading.Lock()

    def is_allowed(self, client_ip: str) -> bool:
        """Check if a request from *client_ip* is allowed."""
        now = time.monotonic()
        with self._lock:
            if client_ip not in self._requests:
                self._requests[client_ip] = collections.deque()

            dq = self._requests[client_ip]
            # Evict old entries outside the window
            while dq and dq[0] < now - self._window:
                dq.popleft()

            if len(dq) >= self._max_requests:
                return False

            dq.append(now)
            return True

    def reset(self) -> None:
        """Clear all rate limit state (for testing)."""
        with self._lock:
            self._requests.clear()


_login_rate_limiter = LoginRateLimiter()


# ── Bounded Auth State Store ─────────────────────────────────────────


class AuthStateStore:
    """Bounded, TTL-enforced store for pending OAuth2 CSRF state.

    Thread-safe via ``asyncio.Lock``. Evicts expired entries on every
    write and enforces a hard capacity limit to prevent memory exhaustion.

    Parameters
    ----------
    max_pending : int
        Maximum number of concurrent pending auth states.
    max_age : float
        Maximum age of a pending state in seconds before auto-eviction.
    """

    def __init__(self, max_pending: int = 1000, max_age: float = 600.0) -> None:
        self._store: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        self._max_pending = max_pending
        self._max_age = max_age

    async def put(self, state: str, data: dict[str, Any]) -> None:
        """Store a pending auth state."""
        async with self._lock:
            self._evict_expired()
            if len(self._store) >= self._max_pending:
                # Evict oldest entry when at capacity
                oldest_key = min(self._store, key=lambda k: self._store[k].get("created_at", 0))
                del self._store[oldest_key]
            self._store[state] = data

    async def pop(self, state: str) -> dict[str, Any] | None:
        """Retrieve and remove a pending auth state (single-use)."""
        async with self._lock:
            self._evict_expired()
            return self._store.pop(state, None)

    async def contains(self, state: str) -> bool:
        """Check if a state exists."""
        async with self._lock:
            self._evict_expired()
            return state in self._store

    def _evict_expired(self) -> None:
        """Remove all expired entries (caller must hold lock)."""
        now = time.time()
        expired = [
            k for k, v in self._store.items() if now - v.get("created_at", 0) > self._max_age
        ]
        for k in expired:
            del self._store[k]

    async def cleanup(self) -> int:
        """Explicitly clean up expired states. Returns count removed."""
        async with self._lock:
            before = len(self._store)
            self._evict_expired()
            return before - len(self._store)

    async def size(self) -> int:
        """Return current number of pending states."""
        async with self._lock:
            return len(self._store)

    def _get_store_for_testing(self) -> dict[str, dict[str, Any]]:
        """Expose internal store for testing only."""
        return self._store


# Global instance — shared across routes in this process.
# For multi-worker deploy, this should be replaced with a Redis-backed store.
_auth_state_store = AuthStateStore()

# Legacy alias kept for test compatibility
_pending_auth_states = _auth_state_store._get_store_for_testing()


def create_auth_router(  # noqa: C901, PLR0915
    provider: OAuthProvider,
    session_store: SessionStore,
    token_store: TokenStore,
    deploy_settings: DeploySettings,
    auth_config: AuthConfig,
    use_pkce: bool = True,
) -> APIRouter:
    """Create a FastAPI router with OAuth2 authentication routes.

    Parameters
    ----------
    provider : OAuthProvider
        The configured OAuth2 provider.
    session_store : SessionStore
        Session store for creating/managing sessions.
    token_store : TokenStore
        Token store for persisting OAuth2 tokens.
    deploy_settings : DeploySettings
        Deploy configuration (cookie name, default roles, etc.).
    auth_config : AuthConfig
        Auth configuration (secret, session TTL, etc.).
    use_pkce : bool
        Whether to use PKCE (default True).

    Returns
    -------
    APIRouter
        Router with ``/auth/*`` routes.
    """
    router = APIRouter(prefix="/auth", tags=["authentication"])

    @router.get("/login")
    async def auth_login(request: Request) -> Response:
        """Initiate OAuth2 login flow.

        Generates PKCE challenge, state nonce, and OIDC nonce,
        then redirects the user to the provider's authorization page.

        Rate limited to prevent abuse.
        """
        # Rate limit login attempts by client IP
        client_ip = request.client.host if request.client else "unknown"
        if not _login_rate_limiter.is_allowed(client_ip):
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limited",
                    "error_description": "Too many login attempts. Please try again later.",
                },
            )

        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)

        pkce: PKCEChallenge | None = None
        if use_pkce:
            pkce = PKCEChallenge.generate()

        # Determine redirect URI: use configured value or derive from request
        configured_uri = getattr(deploy_settings, "auth_redirect_uri", "")
        redirect_uri = configured_uri or str(request.url_for("auth_callback"))

        # Enforce HTTPS for redirect URIs in deploy mode (unless localhost dev)
        force_https = getattr(deploy_settings, "force_https", False)
        if force_https and redirect_uri.startswith("http://"):
            _host = redirect_uri.split("://", 1)[1].split("/")[0].split(":")[0]
            if _host not in ("localhost", "127.0.0.1", "[::1]"):
                redirect_uri = "https://" + redirect_uri[len("http://") :]

        # Store state for CSRF validation
        await _auth_state_store.put(
            state,
            {
                "pkce_verifier": pkce.verifier if pkce else None,
                "redirect_uri": redirect_uri,
                "nonce": nonce,
                "created_at": time.time(),
            },
        )

        authorize_url = provider.build_authorize_url(
            redirect_uri=redirect_uri,
            state=state,
            pkce=pkce,
            extra_params={"nonce": nonce},
        )

        return RedirectResponse(url=authorize_url, status_code=302)

    @router.get("/callback")
    async def auth_callback(
        request: Request,  # pylint: disable=unused-argument
        code: str | None = None,
        state: str | None = None,
        error: str | None = None,
        error_description: str | None = None,
    ) -> Response:
        """Handle OAuth2 callback from the provider.

        Validates the state parameter, exchanges the authorization code
        for tokens, creates a session, and redirects to the application.
        """
        if error:
            return JSONResponse(
                status_code=400,
                content={
                    "error": error,
                    "error_description": error_description or "Authentication failed",
                },
            )

        if not state or not await _auth_state_store.contains(state):
            return JSONResponse(
                status_code=400,
                content={
                    "error": "invalid_state",
                    "error_description": "Invalid or expired state parameter",
                },
            )

        if not code:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "missing_code",
                    "error_description": "Authorization code not provided",
                },
            )

        # Retrieve and remove pending state (single-use)
        auth_state = await _auth_state_store.pop(state)
        if auth_state is None:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "invalid_state",
                    "error_description": "State already consumed or expired",
                },
            )
        redirect_uri = auth_state["redirect_uri"]
        pkce_verifier = auth_state.get("pkce_verifier")
        nonce = auth_state.get("nonce")

        # Exchange code for tokens
        try:
            tokens = await provider.exchange_code(
                code=code,
                redirect_uri=redirect_uri,
                pkce_verifier=pkce_verifier,
                nonce=nonce,
            )
        except Exception:
            logger.exception("Token exchange failed")
            return JSONResponse(
                status_code=500,
                content={
                    "error": "token_exchange_failed",
                    "error_description": "An internal error occurred",
                },
            )

        # Fetch user info
        user_info: dict[str, Any] = {}
        try:
            user_info = await provider.get_userinfo(tokens.access_token)
        except Exception as exc:
            logger.warning("Failed to fetch user info: %s", exc)

        # Determine user ID from user info or token
        user_id = (
            user_info.get("sub")
            or user_info.get("id")
            or user_info.get("login")
            or user_info.get("email")
            or "unknown"
        )

        # Create session
        session_ttl = auth_config.session_ttl
        expires_at = time.time() + session_ttl

        session_token = generate_session_token(
            user_id=str(user_id),
            secret=auth_config.token_secret,
            expires_at=expires_at,
        )

        session = UserSession(
            session_id=session_token,
            user_id=str(user_id),
            roles=list(deploy_settings.default_roles),
            created_at=time.time(),
            expires_at=expires_at,
            metadata={
                "provider": provider.__class__.__name__,
                "user_info": user_info,
            },
        )

        # Check if the user is an admin
        admin_users = getattr(deploy_settings, "admin_users", [])
        if (
            str(user_id) in admin_users or user_info.get("email") in admin_users
        ) and "admin" not in session.roles:
            session.roles.append("admin")

        await session_store.create_session(
            session_id=session.session_id,
            user_id=session.user_id,
            roles=session.roles,
            ttl=int(auth_config.session_ttl),
            metadata=session.metadata,
        )

        # Store OAuth tokens keyed by session_id for isolation
        await token_store.save(session_token, tokens)

        # Set session cookie and redirect to app
        cookie_name = deploy_settings.auth_session_cookie
        response = RedirectResponse(url="/", status_code=302)

        # Determine cookie security based on request scheme and config
        force_https = getattr(deploy_settings, "force_https", False)
        request_is_https = str(request.url).startswith("https://")
        cookie_secure = force_https or request_is_https

        response.set_cookie(
            key=cookie_name,
            value=session_token,
            httponly=True,
            secure=cookie_secure,
            samesite="lax",
            max_age=session_ttl,
        )

        logger.info("User %s authenticated via %s", user_id, provider.__class__.__name__)
        return response

    @router.post("/refresh")
    async def auth_refresh(request: Request) -> JSONResponse:
        """Refresh the OAuth2 access token using the refresh token."""
        # CSRF origin verification for state-changing POST
        if not _verify_csrf_origin(request):
            return JSONResponse(
                status_code=403,
                content={
                    "error": "csrf_failed",
                    "error_description": "Origin verification failed",
                },
            )

        session: UserSession | None = getattr(request.state, "session", None)
        if not session:
            return JSONResponse(status_code=401, content={"error": "not_authenticated"})

        existing_tokens = await token_store.load(session.session_id)
        if not existing_tokens or not existing_tokens.refresh_token:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "no_refresh_token",
                    "error_description": "No refresh token available",
                },
            )

        try:
            new_tokens = await provider.refresh_tokens(existing_tokens.refresh_token)
            await token_store.save(session.session_id, new_tokens)
            return JSONResponse(
                content={
                    "success": True,
                    "expires_in": new_tokens.expires_in,
                    "token_type": new_tokens.token_type,
                }
            )
        except Exception:
            logger.exception("Token refresh failed for user %s", session.user_id)
            return JSONResponse(
                status_code=500,
                content={
                    "error": "refresh_failed",
                    "error_description": "An internal error occurred",
                },
            )

    @router.post("/logout")
    async def auth_logout(request: Request) -> Response:
        """Log out the current user.

        Deletes the session, clears stored tokens, and removes the cookie.
        """
        # CSRF origin verification for state-changing POST
        if not _verify_csrf_origin(request):
            return JSONResponse(
                status_code=403,
                content={
                    "error": "csrf_failed",
                    "error_description": "Origin verification failed",
                },
            )

        session: UserSession | None = getattr(request.state, "session", None)

        if session:
            # Revoke tokens at provider if supported
            existing_tokens = await token_store.load(session.session_id)
            if existing_tokens:
                with contextlib.suppress(Exception):
                    await provider.revoke_token(existing_tokens.access_token)

            # Clean up
            await session_store.delete_session(session.session_id)
            await token_store.delete(session.session_id)

        cookie_name = deploy_settings.auth_session_cookie
        response = JSONResponse(content={"success": True, "message": "Logged out"})
        response.delete_cookie(key=cookie_name)
        return response

    @router.get("/userinfo")
    async def auth_userinfo(request: Request) -> JSONResponse:
        """Return the current user's profile information."""
        session: UserSession | None = getattr(request.state, "session", None)
        if not session:
            return JSONResponse(status_code=401, content={"error": "not_authenticated"})

        user_info = session.metadata.get("user_info", {})
        return JSONResponse(
            content={
                "user_id": session.user_id,
                "roles": session.roles,
                "user_info": user_info,
            }
        )

    @router.get("/status")
    async def auth_status(request: Request) -> JSONResponse:
        """Return the current authentication status."""
        session: UserSession | None = getattr(request.state, "session", None)
        if not session:
            return JSONResponse(
                content={
                    "authenticated": False,
                }
            )

        return JSONResponse(
            content={
                "authenticated": True,
                "user_id": session.user_id,
                "roles": session.roles,
                "expires_at": session.expires_at,
            }
        )

    return router


def cleanup_expired_states(max_age: float = 600.0) -> int:
    """Remove expired pending auth states (synchronous wrapper).

    Parameters
    ----------
    max_age : float
        Maximum age in seconds before a state is considered expired.

    Returns
    -------
    int
        Number of expired states removed.
    """
    now = time.time()
    store = _auth_state_store._get_store_for_testing()
    expired = [k for k, v in store.items() if now - v.get("created_at", 0) > max_age]
    for k in expired:
        del store[k]
    return len(expired)
