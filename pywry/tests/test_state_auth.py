"""Tests for the state.auth module."""

from __future__ import annotations

import time

from unittest.mock import AsyncMock, MagicMock

import pytest

from pywry.state.auth import (
    DEFAULT_ROLE_PERMISSIONS,
    AuthConfig,
    AuthMiddleware,
    check_widget_permission,
    generate_session_token,
    generate_widget_token,
    get_role_permissions,
    get_session_from_request,
    has_permission,
    is_admin,
    validate_session_token,
    validate_widget_token,
)
from pywry.state.memory import MemorySessionStore
from pywry.state.types import UserSession


class TestAuthConfig:
    """Tests for the AuthConfig dataclass."""

    def test_default_values(self) -> None:
        cfg = AuthConfig()
        assert cfg.enabled is False
        assert cfg.session_cookie == "pywry_session"
        assert cfg.auth_header == "Authorization"
        assert cfg.session_ttl == 86400
        assert cfg.require_auth_for_widgets is False
        # Token secret auto-generated
        assert cfg.token_secret != ""
        assert len(cfg.token_secret) > 0

    def test_explicit_token_secret_preserved(self) -> None:
        cfg = AuthConfig(token_secret="my-secret")
        assert cfg.token_secret == "my-secret"

    def test_empty_token_secret_generated(self) -> None:
        cfg = AuthConfig(token_secret="")
        assert cfg.token_secret != ""


class TestSessionTokenGeneration:
    """Tests for session token generation/validation."""

    def test_generate_and_validate(self) -> None:
        token = generate_session_token("user1", "secret")
        is_valid, user_id, error = validate_session_token(token, "secret")
        assert is_valid is True
        assert user_id == "user1"
        assert error is None

    def test_validate_with_expiry(self) -> None:
        future_expiry = time.time() + 3600
        token = generate_session_token("user1", "secret", expires_at=future_expiry)
        is_valid, user_id, _ = validate_session_token(token, "secret")
        assert is_valid is True
        assert user_id == "user1"

    def test_expired_token(self) -> None:
        past_expiry = time.time() - 100  # already expired
        token = generate_session_token("user1", "secret", expires_at=past_expiry)
        is_valid, user_id, error = validate_session_token(token, "secret")
        assert is_valid is False
        assert user_id is None
        assert "expired" in error.lower()

    def test_invalid_signature(self) -> None:
        token = generate_session_token("user1", "secret")
        is_valid, user_id, error = validate_session_token(token, "different-secret")
        assert is_valid is False
        assert user_id is None
        assert "signature" in error.lower()

    def test_invalid_format_too_few_parts(self) -> None:
        is_valid, _user_id, error = validate_session_token("a:b:c", "secret")
        assert is_valid is False
        assert "format" in error.lower()

    def test_invalid_format_too_many_parts(self) -> None:
        is_valid, _user_id, error = validate_session_token("a:b:c:d:e", "secret")
        assert is_valid is False
        assert "format" in error.lower()

    def test_non_integer_timestamp(self) -> None:
        # Build a malformed token with non-int timestamp
        token = "user1:notanint:0:badsig"
        is_valid, _user_id, error = validate_session_token(token, "secret")
        assert is_valid is False
        # Either parse error or signature failure
        assert error is not None


class TestWidgetToken:
    """Tests for widget token generation/validation."""

    def test_generate_and_validate(self) -> None:
        token = generate_widget_token("widget-1", "secret", ttl=300)
        assert validate_widget_token(token, "widget-1", "secret") is True

    def test_wrong_widget_id_rejects(self) -> None:
        token = generate_widget_token("widget-1", "secret")
        assert validate_widget_token(token, "widget-2", "secret") is False

    def test_wrong_secret_rejects(self) -> None:
        token = generate_widget_token("widget-1", "secret")
        assert validate_widget_token(token, "widget-1", "other-secret") is False


class TestRolePermissions:
    """Tests for role permissions helpers."""

    def test_admin_has_all_permissions(self) -> None:
        perms = get_role_permissions("admin")
        assert "read" in perms
        assert "write" in perms
        assert "admin" in perms

    def test_viewer_has_only_read(self) -> None:
        perms = get_role_permissions("viewer")
        assert perms == {"read"}

    def test_editor_has_read_and_write(self) -> None:
        perms = get_role_permissions("editor")
        assert perms == {"read", "write"}

    def test_anonymous_has_nothing(self) -> None:
        perms = get_role_permissions("anonymous")
        assert perms == set()

    def test_unknown_role_returns_empty(self) -> None:
        perms = get_role_permissions("unknown-role")
        assert perms == set()

    def test_default_role_permissions_constant(self) -> None:
        assert "admin" in DEFAULT_ROLE_PERMISSIONS
        assert "viewer" in DEFAULT_ROLE_PERMISSIONS


class TestHasPermission:
    """Tests for has_permission function."""

    def test_session_with_admin_has_admin_perm(self) -> None:
        session = UserSession(session_id="s1", user_id="u1", roles=["admin"])
        assert has_permission(session, "admin") is True

    def test_session_with_viewer_has_read(self) -> None:
        session = UserSession(session_id="s1", user_id="u1", roles=["viewer"])
        assert has_permission(session, "read") is True
        assert has_permission(session, "write") is False

    def test_none_session_denies(self) -> None:
        assert has_permission(None, "read") is False

    def test_multiple_roles_combine(self) -> None:
        session = UserSession(session_id="s1", user_id="u1", roles=["viewer", "editor"])
        assert has_permission(session, "read") is True
        assert has_permission(session, "write") is True


class TestIsAdmin:
    """Tests for is_admin."""

    def test_admin_user(self) -> None:
        session = UserSession(session_id="s1", user_id="u1", roles=["admin"])
        assert is_admin(session) is True

    def test_non_admin_user(self) -> None:
        session = UserSession(session_id="s1", user_id="u1", roles=["viewer"])
        assert is_admin(session) is False

    def test_none_session(self) -> None:
        assert is_admin(None) is False


class TestGetSessionFromRequest:
    """Tests for get_session_from_request."""

    @pytest.fixture
    def session_store(self) -> MemorySessionStore:
        return MemorySessionStore()

    @pytest.fixture
    def auth_config(self) -> AuthConfig:
        return AuthConfig(enabled=True, token_secret="test-secret")

    async def test_extract_via_cookie(
        self, session_store: MemorySessionStore, auth_config: AuthConfig
    ) -> None:
        await session_store.create_session("session1", "user1", roles=["admin"])

        request = MagicMock()
        request.cookies = {"pywry_session": "session1"}
        request.headers = {}
        request.query_params = {}

        result = await get_session_from_request(request, session_store, auth_config)
        assert result is not None
        assert result.user_id == "user1"

    async def test_extract_via_query_params(
        self, session_store: MemorySessionStore, auth_config: AuthConfig
    ) -> None:
        await session_store.create_session("session1", "user1")

        request = MagicMock()
        request.cookies = {}
        request.headers = {}
        request.query_params = {"session": "session1"}

        result = await get_session_from_request(request, session_store, auth_config)
        assert result is not None
        assert result.user_id == "user1"

    async def test_extract_via_bearer_token(
        self, session_store: MemorySessionStore, auth_config: AuthConfig
    ) -> None:
        await session_store.create_session("session1", "user1")

        token = generate_session_token("user1", auth_config.token_secret)
        request = MagicMock()
        request.cookies = {}
        request.headers = {"Authorization": f"Bearer {token}"}
        request.query_params = {}

        result = await get_session_from_request(request, session_store, auth_config)
        assert result is not None
        assert result.user_id == "user1"

    async def test_bearer_token_no_session(
        self, session_store: MemorySessionStore, auth_config: AuthConfig
    ) -> None:
        # Valid token, but no session for user
        token = generate_session_token("ghost-user", auth_config.token_secret)
        request = MagicMock()
        request.cookies = {}
        request.headers = {"Authorization": f"Bearer {token}"}
        request.query_params = {}

        result = await get_session_from_request(request, session_store, auth_config)
        assert result is None

    async def test_bearer_token_invalid(
        self, session_store: MemorySessionStore, auth_config: AuthConfig
    ) -> None:
        request = MagicMock()
        request.cookies = {}
        request.headers = {"Authorization": "Bearer invalid-token"}
        request.query_params = {}

        result = await get_session_from_request(request, session_store, auth_config)
        # Falls through to query params - returns None
        assert result is None

    async def test_no_auth_returns_none(
        self, session_store: MemorySessionStore, auth_config: AuthConfig
    ) -> None:
        request = MagicMock()
        request.cookies = {}
        request.headers = {}
        request.query_params = {}

        result = await get_session_from_request(request, session_store, auth_config)
        assert result is None

    async def test_request_without_cookies_attribute(
        self, session_store: MemorySessionStore, auth_config: AuthConfig
    ) -> None:
        await session_store.create_session("session1", "user1")

        # Build a wrapper class that lacks `cookies` attribute
        class StripRequest:
            headers: dict = {}
            query_params: dict = {"session": "session1"}

        result = await get_session_from_request(
            StripRequest(),  # type: ignore
            session_store,
            auth_config,
        )
        assert result is not None
        assert result.user_id == "user1"


class TestCheckWidgetPermission:
    """Tests for check_widget_permission."""

    @pytest.fixture
    def session_store(self) -> MemorySessionStore:
        return MemorySessionStore()

    async def test_no_session_denies(self, session_store: MemorySessionStore) -> None:
        result = await check_widget_permission(None, "w1", "read", session_store)
        assert result is False

    async def test_admin_session_allowed(self, session_store: MemorySessionStore) -> None:
        session = await session_store.create_session("s1", "user1", roles=["admin"])
        result = await check_widget_permission(session, "w1", "admin", session_store)
        assert result is True

    async def test_viewer_can_read(self, session_store: MemorySessionStore) -> None:
        session = await session_store.create_session("s1", "user1", roles=["viewer"])
        result = await check_widget_permission(session, "w1", "read", session_store)
        assert result is True

    async def test_viewer_cannot_write(self, session_store: MemorySessionStore) -> None:
        session = await session_store.create_session("s1", "user1", roles=["viewer"])
        result = await check_widget_permission(session, "w1", "write", session_store)
        assert result is False


class TestAuthMiddleware:
    """Tests for AuthMiddleware ASGI middleware."""

    @pytest.fixture
    def session_store(self) -> MemorySessionStore:
        return MemorySessionStore()

    @pytest.fixture
    def auth_config(self) -> AuthConfig:
        return AuthConfig(enabled=True, token_secret="test-secret")

    async def test_non_http_passes_through(
        self, session_store: MemorySessionStore, auth_config: AuthConfig
    ) -> None:
        app = AsyncMock()
        middleware = AuthMiddleware(app, session_store, auth_config)
        scope = {"type": "lifespan"}
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)
        app.assert_awaited_once_with(scope, receive, send)

    async def test_public_path_passes_through(
        self, session_store: MemorySessionStore, auth_config: AuthConfig
    ) -> None:
        app = AsyncMock()
        middleware = AuthMiddleware(app, session_store, auth_config, public_paths={"/auth/"})
        scope = {"type": "http", "path": "/auth/login", "headers": [], "query_string": b""}
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)
        app.assert_awaited_once()

    async def test_disabled_auth_skips_session_extraction(
        self, session_store: MemorySessionStore
    ) -> None:
        config = AuthConfig(enabled=False)
        app = AsyncMock()
        middleware = AuthMiddleware(app, session_store, config)
        scope = {"type": "http", "path": "/api", "headers": [], "query_string": b""}
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)
        # session is None when auth is disabled
        assert scope["session"] is None
        app.assert_awaited_once()

    async def test_with_cookie(
        self, session_store: MemorySessionStore, auth_config: AuthConfig
    ) -> None:
        await session_store.create_session("session1", "user1", roles=["admin"])

        app = AsyncMock()
        middleware = AuthMiddleware(app, session_store, auth_config)
        cookie = b"pywry_session=session1; other=value"
        scope = {
            "type": "http",
            "path": "/api",
            "headers": [(b"cookie", cookie)],
            "query_string": b"",
        }
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)
        assert scope["session"] is not None
        assert scope["session"].user_id == "user1"

    async def test_with_query_params(
        self, session_store: MemorySessionStore, auth_config: AuthConfig
    ) -> None:
        await session_store.create_session("session1", "user1")

        app = AsyncMock()
        middleware = AuthMiddleware(app, session_store, auth_config)
        scope = {
            "type": "http",
            "path": "/api",
            "headers": [],
            "query_string": b"session=session1&other=foo",
        }
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)
        assert scope["session"] is not None

    async def test_no_session_data(
        self, session_store: MemorySessionStore, auth_config: AuthConfig
    ) -> None:
        app = AsyncMock()
        middleware = AuthMiddleware(app, session_store, auth_config)
        scope = {
            "type": "http",
            "path": "/api",
            "headers": [],
            "query_string": b"",
        }
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)
        assert scope["session"] is None

    async def test_websocket_supported(
        self, session_store: MemorySessionStore, auth_config: AuthConfig
    ) -> None:
        await session_store.create_session("session1", "user1")

        app = AsyncMock()
        middleware = AuthMiddleware(app, session_store, auth_config)
        scope = {
            "type": "websocket",
            "path": "/ws",
            "headers": [],
            "query_string": b"session=session1",
        }
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)
        assert scope["session"] is not None
