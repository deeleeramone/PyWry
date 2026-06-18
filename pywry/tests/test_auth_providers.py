"""Unit tests for OAuth2 provider abstractions."""

from __future__ import annotations

import asyncio
import sys
import time

from collections import UserDict
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from pywry.auth.pkce import PKCEChallenge
from pywry.auth.providers import (
    GenericOIDCProvider,
    GitHubProvider,
    GoogleProvider,
    MicrosoftProvider,
    create_provider_from_settings,
)
from pywry.exceptions import AuthenticationError, TokenError, TokenRefreshError
from pywry.state.types import OAuthTokenSet


# ── Test helpers ────────────────────────────────────────────────────


def _run(coro: Any) -> Any:
    """Synchronously drive a coroutine to completion."""
    return asyncio.run(coro)


def _mock_async_client(mock_instance: AsyncMock) -> AsyncMock:
    """Make AsyncMock work as a context-manager friendly httpx.AsyncClient."""
    mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
    mock_instance.__aexit__ = AsyncMock(return_value=False)
    mock_instance.is_closed = False
    mock_instance.aclose = AsyncMock()
    return mock_instance


def _make_resp(payload: dict) -> MagicMock:
    """Build a mocked httpx response that yields *payload* from .json()."""
    resp = MagicMock()
    resp.json.return_value = payload
    resp.raise_for_status = MagicMock()
    return resp


# ── Provider URL Building ───────────────────────────────────────────


class TestOAuthProviderURLBuilding:
    """Tests for OAuthProvider.build_authorize_url()."""

    def test_build_url_basic(self) -> None:
        """Basic URL building with required params."""
        provider = GoogleProvider(client_id="test-id", client_secret="test-secret")
        url = provider.build_authorize_url(
            redirect_uri="http://localhost:8080/callback",
            state="test-state",
        )
        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        assert parsed.scheme == "https"
        assert "accounts.google.com" in parsed.netloc
        assert params["client_id"] == ["test-id"]
        assert params["redirect_uri"] == ["http://localhost:8080/callback"]
        assert params["state"] == ["test-state"]
        assert params["response_type"] == ["code"]

    def test_build_url_with_pkce(self) -> None:
        """URL includes PKCE challenge when provided."""
        provider = GoogleProvider(client_id="test-id")
        pkce = PKCEChallenge.generate()
        url = provider.build_authorize_url(
            redirect_uri="http://localhost/cb",
            state="s",
            pkce=pkce,
        )
        params = parse_qs(urlparse(url).query)
        assert params["code_challenge"] == [pkce.challenge]
        assert params["code_challenge_method"] == ["S256"]

    def test_build_url_with_scopes(self) -> None:
        """URL includes scopes."""
        provider = GenericOIDCProvider(
            client_id="c",
            scopes=["openid", "email"],
            authorize_url="https://idp.example.com/authorize",
        )
        url = provider.build_authorize_url(redirect_uri="http://localhost/cb", state="s")
        params = parse_qs(urlparse(url).query)
        assert params["scope"] == ["openid email"]

    def test_google_includes_access_type(self) -> None:
        """Google provider adds access_type=offline."""
        provider = GoogleProvider(client_id="test-id")
        url = provider.build_authorize_url(redirect_uri="http://localhost/cb", state="s")
        params = parse_qs(urlparse(url).query)
        assert params["access_type"] == ["offline"]
        assert params["prompt"] == ["consent"]

    def test_extra_params(self) -> None:
        """Extra params are included."""
        provider = GitHubProvider(client_id="test-id")
        url = provider.build_authorize_url(
            redirect_uri="http://localhost/cb",
            state="s",
            extra_params={"login": "user@example.com"},
        )
        params = parse_qs(urlparse(url).query)
        assert params["login"] == ["user@example.com"]


# ── Provider Preset URLs ────────────────────────────────────────────


class TestProviderPresets:
    """Tests for preset provider URLs."""

    def test_google_urls(self) -> None:
        """Google provider has correct preset URLs."""
        g = GoogleProvider(client_id="c")
        assert "accounts.google.com" in g.authorize_url
        assert "googleapis.com/token" in g.token_url
        assert "googleapis.com" in g.userinfo_url

    def test_github_urls(self) -> None:
        """GitHub provider has correct preset URLs."""
        gh = GitHubProvider(client_id="c")
        assert "github.com/login/oauth/authorize" in gh.authorize_url
        assert "github.com/login/oauth/access_token" in gh.token_url
        assert "api.github.com/user" in gh.userinfo_url

    def test_microsoft_urls(self) -> None:
        """Microsoft provider has correct preset URLs."""
        ms = MicrosoftProvider(client_id="c", tenant_id="my-tenant")
        assert "my-tenant" in ms.authorize_url
        assert "my-tenant" in ms.token_url
        assert "graph.microsoft.com" in ms.userinfo_url
        assert ms.tenant_id == "my-tenant"

    def test_microsoft_default_tenant(self) -> None:
        """Microsoft defaults to 'common' tenant."""
        ms = MicrosoftProvider(client_id="c")
        assert "common" in ms.authorize_url

    def test_github_scopes(self) -> None:
        """GitHub has correct default scopes."""
        gh = GitHubProvider(client_id="c")
        assert "read:user" in gh.scopes
        assert "user:email" in gh.scopes

    def test_google_scopes(self) -> None:
        """Google has correct default scopes."""
        g = GoogleProvider(client_id="c")
        assert "openid" in g.scopes
        assert "email" in g.scopes


# ── Token Exchange (Mocked) ─────────────────────────────────────────


class TestTokenExchange:
    """Tests for OAuthProvider.exchange_code() with mocked HTTP."""

    @pytest.fixture()
    def mock_response(self) -> dict:
        """Standard token response."""
        return {
            "access_token": "at_test123",
            "token_type": "Bearer",
            "refresh_token": "rt_test123",
            "expires_in": 3600,
            "scope": "openid email",
            "id_token": "eyJhbGci...",
        }

    def test_exchange_code_success(self, mock_response: dict) -> None:
        """Successful code exchange returns OAuthTokenSet."""
        provider = GenericOIDCProvider(
            client_id="c",
            client_secret="s",
            token_url="https://idp.example.com/token",
            require_id_token_validation=False,
        )

        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_resp
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            tokens = asyncio.run(
                provider.exchange_code("code123", "http://localhost/cb", "verifier")
            )

        assert tokens.access_token == "at_test123"
        assert tokens.refresh_token == "rt_test123"
        assert tokens.expires_in == 3600
        assert tokens.token_type == "Bearer"

    def test_exchange_code_error(self) -> None:
        """Failed code exchange raises TokenError."""
        provider = GenericOIDCProvider(
            client_id="c",
            token_url="https://idp.example.com/token",
        )

        import httpx

        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Bad Request", request=MagicMock(), response=mock_resp
        )

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_resp
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            with pytest.raises(TokenError):
                asyncio.run(provider.exchange_code("bad_code", "http://localhost/cb"))

    def test_github_exchange_code_with_error_response(self) -> None:
        """GitHub returns error in JSON body, not HTTP status."""
        provider = GitHubProvider(client_id="c", client_secret="s")

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "error": "bad_verification_code",
            "error_description": "The code passed is incorrect or expired.",
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_resp
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            with pytest.raises(TokenError, match="expired"):
                asyncio.run(provider.exchange_code("bad", "http://localhost/cb"))

    def test_refresh_tokens_success(self, mock_response: dict) -> None:
        """Successful token refresh."""
        provider = GenericOIDCProvider(
            client_id="c",
            client_secret="s",
            token_url="https://idp.example.com/token",
        )

        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_resp
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            tokens = asyncio.run(provider.refresh_tokens("rt_old"))

        assert tokens.access_token == "at_test123"

    def test_refresh_tokens_failure(self) -> None:
        """Failed token refresh raises TokenRefreshError."""
        provider = GenericOIDCProvider(
            client_id="c",
            token_url="https://idp.example.com/token",
        )

        import httpx

        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Unauthorized", request=MagicMock(), response=mock_resp
        )

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_resp
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            with pytest.raises(TokenRefreshError):
                asyncio.run(provider.refresh_tokens("rt_bad"))


# ── Token Revocation ────────────────────────────────────────────────


class TestTokenRevocation:
    """Tests for OAuthProvider.revoke_token() implementations."""

    def test_base_revoke_no_url(self) -> None:
        """Base provider without revocation_url returns False."""
        provider = GenericOIDCProvider(
            client_id="c",
            token_url="https://idp.example.com/token",
        )
        result = asyncio.run(provider.revoke_token("some_token"))
        assert result is False

    def test_base_revoke_with_url_success(self) -> None:
        """Provider with revocation_url posts to it and returns True."""
        provider = GenericOIDCProvider(
            client_id="c",
            token_url="https://idp.example.com/token",
            revocation_url="https://idp.example.com/revoke",
        )

        mock_resp = MagicMock()
        mock_resp.is_success = True

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_resp
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            result = asyncio.run(provider.revoke_token("token_to_revoke"))

        assert result is True
        mock_instance.post.assert_called_once()
        call_kwargs = mock_instance.post.call_args
        assert call_kwargs[1]["data"]["token"] == "token_to_revoke"
        assert call_kwargs[1]["data"]["client_id"] == "c"

    def test_base_revoke_http_error(self) -> None:
        """Provider returns False when revocation request fails."""
        import httpx

        provider = GenericOIDCProvider(
            client_id="c",
            token_url="https://idp.example.com/token",
            revocation_url="https://idp.example.com/revoke",
        )

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.side_effect = httpx.HTTPError("connection failed")
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            result = asyncio.run(provider.revoke_token("token_to_revoke"))

        assert result is False

    def test_google_revoke_uses_correct_url(self) -> None:
        """Google provider has revocation_url preconfigured."""
        provider = GoogleProvider(client_id="c", client_secret="s")
        assert provider.revocation_url == "https://oauth2.googleapis.com/revoke"

    def test_oidc_revoke_triggers_discovery(self) -> None:
        """OIDC revoke_token calls _discover() before revoking."""
        provider = GenericOIDCProvider(
            client_id="c",
            issuer_url="https://idp.example.com",
            token_url="https://idp.example.com/token",
        )

        with patch.object(provider, "_discover", new_callable=AsyncMock) as mock_disc:
            result = asyncio.run(provider.revoke_token("tok"))

        mock_disc.assert_awaited_once()
        # No revocation_url discovered (mocked), so returns False
        assert result is False

    def test_github_revoke_success(self) -> None:
        """GitHub revoke_token uses DELETE /applications/{id}/token."""
        provider = GitHubProvider(client_id="gh_id", client_secret="gh_secret")

        mock_resp = MagicMock()
        mock_resp.status_code = 204

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.request.return_value = mock_resp
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            result = asyncio.run(provider.revoke_token("ghp_abc123"))

        assert result is True
        call_args = mock_instance.request.call_args
        assert call_args[0][0] == "DELETE"
        assert "applications/gh_id/token" in call_args[0][1]
        assert call_args[1]["json"]["access_token"] == "ghp_abc123"
        assert call_args[1]["auth"] == ("gh_id", "gh_secret")

    def test_github_revoke_no_secret(self) -> None:
        """GitHub revoke returns False without client_secret."""
        provider = GitHubProvider(client_id="gh_id")
        result = asyncio.run(provider.revoke_token("ghp_abc123"))
        assert result is False

    def test_github_revoke_failure(self) -> None:
        """GitHub revoke returns False on non-204 status."""
        provider = GitHubProvider(client_id="gh_id", client_secret="gh_secret")

        mock_resp = MagicMock()
        mock_resp.status_code = 404

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.request.return_value = mock_resp
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            result = asyncio.run(provider.revoke_token("ghp_abc123"))

        assert result is False

    def test_microsoft_no_revocation(self) -> None:
        """Microsoft provider has no revocation endpoint."""
        provider = MicrosoftProvider(client_id="c", client_secret="s")
        assert provider.revocation_url == ""
        result = asyncio.run(provider.revoke_token("tok"))
        assert result is False


# ── Provider Factory ────────────────────────────────────────────────


class TestCreateProviderFromSettings:
    """Tests for create_provider_from_settings()."""

    def _make_settings(self, **kwargs: object) -> MagicMock:
        """Create a mock settings object."""
        defaults = {
            "provider": "custom",
            "client_id": "test-id",
            "client_secret": "test-secret",
            "scopes": "openid email",
            "authorize_url": "https://example.com/authorize",
            "token_url": "https://example.com/token",
            "userinfo_url": "",
            "issuer_url": "",
            "tenant_id": "common",
        }
        defaults.update(kwargs)
        mock = MagicMock()
        for k, v in defaults.items():
            setattr(mock, k, v)
        return mock

    def test_google_provider(self) -> None:
        """Factory creates GoogleProvider."""
        settings = self._make_settings(provider="google")
        provider = create_provider_from_settings(settings)
        assert isinstance(provider, GoogleProvider)

    def test_github_provider(self) -> None:
        """Factory creates GitHubProvider."""
        settings = self._make_settings(provider="github")
        provider = create_provider_from_settings(settings)
        assert isinstance(provider, GitHubProvider)

    def test_microsoft_provider(self) -> None:
        """Factory creates MicrosoftProvider."""
        settings = self._make_settings(provider="microsoft", tenant_id="my-tenant")
        provider = create_provider_from_settings(settings)
        assert isinstance(provider, MicrosoftProvider)
        assert provider.tenant_id == "my-tenant"

    def test_oidc_provider(self) -> None:
        """Factory creates GenericOIDCProvider for 'oidc'."""
        settings = self._make_settings(
            provider="oidc",
            issuer_url="https://accounts.google.com",
        )
        provider = create_provider_from_settings(settings)
        assert isinstance(provider, GenericOIDCProvider)

    def test_custom_provider(self) -> None:
        """Factory creates GenericOIDCProvider for 'custom'."""
        settings = self._make_settings(provider="custom")
        provider = create_provider_from_settings(settings)
        assert isinstance(provider, GenericOIDCProvider)

    def test_custom_requires_urls(self) -> None:
        """Custom provider without URLs raises AuthenticationError."""
        settings = self._make_settings(
            provider="custom",
            authorize_url="",
            token_url="",
        )
        with pytest.raises(AuthenticationError, match="requires"):
            create_provider_from_settings(settings)

    def test_unknown_provider(self) -> None:
        """Unknown provider raises AuthenticationError."""
        settings = self._make_settings(provider="unknown")
        with pytest.raises(AuthenticationError, match="Unknown"):
            create_provider_from_settings(settings)


# ── Provider lifecycle (close / get_userinfo) ───────────────────────


class TestProviderClose:
    """Cover OAuthProvider.close() lifecycle."""

    def test_close_when_no_client(self) -> None:
        """close() is safe when no client has been created."""
        provider = GenericOIDCProvider(client_id="c", token_url="https://x/token")
        # _http_client is None; close() should be a no-op
        _run(provider.close())
        assert provider._http_client is None

    def test_close_with_open_client(self) -> None:
        """close() awaits aclose() on the client and resets state."""
        provider = GenericOIDCProvider(client_id="c", token_url="https://x/token")
        fake = MagicMock()
        fake.is_closed = False
        fake.aclose = AsyncMock()
        provider._http_client = fake
        _run(provider.close())
        fake.aclose.assert_awaited_once()
        assert provider._http_client is None

    def test_close_already_closed(self) -> None:
        """close() does nothing when client is already closed."""
        provider = GenericOIDCProvider(client_id="c", token_url="https://x/token")
        fake = MagicMock()
        fake.is_closed = True
        fake.aclose = AsyncMock()
        provider._http_client = fake
        _run(provider.close())
        fake.aclose.assert_not_called()


class TestGetUserInfo:
    """Cover OAuthProvider.get_userinfo()."""

    def test_no_userinfo_url_returns_empty(self) -> None:
        """Provider without userinfo_url returns empty dict."""
        provider = GenericOIDCProvider(
            client_id="c",
            token_url="https://x/token",
            userinfo_url="",
        )
        # Force discovery so it doesn't try to discover with no issuer
        provider._discovered = True
        result = _run(provider.get_userinfo("at_test"))
        assert result == {}

    def test_userinfo_success(self) -> None:
        """get_userinfo returns user data and sends Bearer auth header."""
        provider = GenericOIDCProvider(
            client_id="c",
            token_url="https://x/token",
            userinfo_url="https://x/userinfo",
        )
        provider._discovered = True

        mock_resp = _make_resp({"sub": "user-1", "email": "u@x.com"})

        with patch("httpx.AsyncClient") as mock_client:
            inst = AsyncMock()
            inst.get = AsyncMock(return_value=mock_resp)
            _mock_async_client(inst)
            mock_client.return_value = inst

            data = _run(provider.get_userinfo("at_test"))

        assert data["sub"] == "user-1"
        # Verify Authorization header was sent
        call_kwargs = inst.get.call_args[1]
        assert call_kwargs["headers"]["Authorization"] == "Bearer at_test"


# ── OIDC discovery / JWKS / ID-token validation ─────────────────────


class TestOIDCDiscovery:
    """Cover GenericOIDCProvider._discover()."""

    def test_discover_skips_when_no_issuer(self) -> None:
        """No issuer_url → discovery short-circuits."""
        provider = GenericOIDCProvider(client_id="c", token_url="https://x/token")
        _run(provider._discover())
        assert provider._discovered is False

    def test_discover_skips_when_already_discovered(self) -> None:
        """Already discovered → short-circuits."""
        provider = GenericOIDCProvider(
            client_id="c",
            issuer_url="https://idp.example.com",
            token_url="https://x/token",
        )
        provider._discovered = True
        with patch("httpx.AsyncClient") as mock_client:
            _run(provider._discover())
            mock_client.assert_not_called()

    def test_discover_success_populates_endpoints(self) -> None:
        """Discovery populates endpoints from well-known config."""
        provider = GenericOIDCProvider(
            client_id="c",
            issuer_url="https://idp.example.com",
        )

        config_resp = _make_resp(
            {
                "issuer": "https://idp.example.com",
                "authorization_endpoint": "https://idp.example.com/authorize",
                "token_endpoint": "https://idp.example.com/token",
                "userinfo_endpoint": "https://idp.example.com/userinfo",
                "revocation_endpoint": "https://idp.example.com/revoke",
                "jwks_uri": "https://idp.example.com/jwks",
            }
        )

        with patch("httpx.AsyncClient") as mock_client:
            inst = AsyncMock()
            inst.get = AsyncMock(return_value=config_resp)
            _mock_async_client(inst)
            mock_client.return_value = inst
            _run(provider._discover())

        assert provider._discovered
        assert provider.authorize_url == "https://idp.example.com/authorize"
        assert provider.token_url == "https://idp.example.com/token"
        assert provider.userinfo_url == "https://idp.example.com/userinfo"
        assert provider.revocation_url == "https://idp.example.com/revoke"
        assert provider._jwks_uri == "https://idp.example.com/jwks"

    def test_discover_issuer_mismatch(self) -> None:
        """Issuer mismatch raises AuthenticationError."""
        provider = GenericOIDCProvider(
            client_id="c",
            issuer_url="https://idp.example.com",
        )
        config_resp = _make_resp({"issuer": "https://wrong-idp.com"})

        with patch("httpx.AsyncClient") as mock_client:
            inst = AsyncMock()
            inst.get = AsyncMock(return_value=config_resp)
            _mock_async_client(inst)
            mock_client.return_value = inst

            with pytest.raises(AuthenticationError, match="issuer mismatch"):
                _run(provider._discover())

    def test_discover_http_error_logs_warning(self) -> None:
        """HTTP error during discovery is logged but not raised."""
        provider = GenericOIDCProvider(
            client_id="c",
            issuer_url="https://idp.example.com",
        )

        with patch("httpx.AsyncClient") as mock_client:
            inst = AsyncMock()
            inst.get = AsyncMock(side_effect=httpx.HTTPError("network down"))
            _mock_async_client(inst)
            mock_client.return_value = inst

            _run(provider._discover())

        assert not provider._discovered


class TestJWKSFetch:
    """Cover GenericOIDCProvider._fetch_jwks()."""

    def test_fetch_jwks_no_uri(self) -> None:
        """No JWKS URI raises TokenError."""
        provider = GenericOIDCProvider(client_id="c", token_url="https://x/token")
        with pytest.raises(TokenError, match="JWKS URI"):
            _run(provider._fetch_jwks())

    def test_fetch_jwks_returns_cached(self) -> None:
        """Cached JWKS is returned without HTTP call."""
        provider = GenericOIDCProvider(client_id="c", token_url="https://x/token")
        provider._jwks_data = {"keys": [{"kty": "RSA"}]}
        result = _run(provider._fetch_jwks())
        assert result == {"keys": [{"kty": "RSA"}]}

    def test_fetch_jwks_http_success(self) -> None:
        """Fresh JWKS fetch makes HTTP request and caches the result."""
        provider = GenericOIDCProvider(client_id="c", token_url="https://x/token")
        provider._jwks_uri = "https://idp.example.com/jwks"

        mock_resp = _make_resp({"keys": [{"kty": "RSA", "kid": "k1"}]})

        with patch("httpx.AsyncClient") as mock_client:
            inst = AsyncMock()
            inst.get = AsyncMock(return_value=mock_resp)
            _mock_async_client(inst)
            mock_client.return_value = inst
            result = _run(provider._fetch_jwks())

        assert result["keys"][0]["kid"] == "k1"
        # Cached for next call
        assert provider._jwks_data is not None


class TestValidateIDToken:
    """Cover GenericOIDCProvider.validate_id_token()."""

    def test_no_authlib_raises(self) -> None:
        """Missing authlib raises TokenError."""
        provider = GenericOIDCProvider(client_id="c", token_url="https://x/token")
        with (
            patch("pywry.auth.providers._HAS_AUTHLIB", False),
            pytest.raises(TokenError, match="authlib"),
        ):
            _run(provider.validate_id_token("dummy.token"))

    def test_validation_failure_wrapped_as_token_error(self) -> None:
        """Failed validation wraps exception in TokenError."""
        provider = GenericOIDCProvider(
            client_id="c",
            issuer_url="https://idp.example.com",
            token_url="https://idp.example.com/token",
        )
        provider._discovered = True
        provider._jwks_data = {"keys": []}

        # JWT decode will fail because token is gibberish
        with pytest.raises(TokenError, match="ID token validation failed"):
            _run(provider.validate_id_token("not.a.real.jwt"))

    def test_validation_with_nonce_option(self) -> None:
        """Nonce parameter is wired into claims_options."""
        provider = GenericOIDCProvider(
            client_id="c",
            issuer_url="https://idp.example.com",
            token_url="https://idp.example.com/token",
        )
        provider._discovered = True
        provider._jwks_data = {"keys": []}

        # Should fail validation but not before processing nonce
        with pytest.raises(TokenError):
            _run(provider.validate_id_token("invalid.token.value", nonce="my-nonce"))

    def test_validation_success_returns_claims(self) -> None:
        """Successful validation returns the dict of claims."""
        provider = GenericOIDCProvider(
            client_id="test-client",
            issuer_url="https://idp.example.com",
            token_url="https://idp.example.com/token",
        )
        provider._discovered = True
        provider._jwks_data = {"keys": []}

        class _FakeClaims(UserDict):
            def validate(self) -> None:
                """No-op validate to mimic authlib's claims object."""

        fake_claims_obj = _FakeClaims({"sub": "u1", "iss": "https://idp.example.com"})

        with (
            patch("pywry.auth.providers.JsonWebToken") as mock_jwt_cls,
            patch("pywry.auth.providers.JsonWebKey") as mock_jwk,
        ):
            mock_jwt = MagicMock()
            mock_jwt.decode.return_value = fake_claims_obj
            mock_jwt_cls.return_value = mock_jwt
            mock_jwk.import_key_set = MagicMock(return_value={})
            claims = _run(provider.validate_id_token("hdr.payload.sig"))
        assert claims["sub"] == "u1"


# ── exchange_code / refresh_tokens error paths ──────────────────────


class TestExchangeCodeErrors:
    """Cover error paths in GenericOIDCProvider.exchange_code()."""

    def test_no_token_url_raises(self) -> None:
        """No token_url after discovery raises TokenError."""
        provider = GenericOIDCProvider(client_id="c", token_url="")
        provider._discovered = True
        with pytest.raises(TokenError, match="Token URL not configured"):
            _run(provider.exchange_code("code", "http://localhost/cb"))

    def test_http_error_raises_token_error(self) -> None:
        """Non-status HTTP error raises TokenError."""
        provider = GenericOIDCProvider(
            client_id="c",
            client_secret="s",
            token_url="https://idp.example.com/token",
        )
        provider._discovered = True

        with patch("httpx.AsyncClient") as mock_client:
            inst = AsyncMock()
            inst.post = AsyncMock(side_effect=httpx.HTTPError("connection refused"))
            _mock_async_client(inst)
            mock_client.return_value = inst

            with pytest.raises(TokenError, match="Token exchange request failed"):
                _run(provider.exchange_code("code", "http://localhost/cb"))

    def test_id_token_validation_invoked(self) -> None:
        """ID token validation is called when require_id_token_validation."""
        provider = GenericOIDCProvider(
            client_id="c",
            client_secret="s",
            token_url="https://idp.example.com/token",
            require_id_token_validation=True,
        )
        provider._discovered = True

        mock_resp = _make_resp(
            {
                "access_token": "at",
                "id_token": "header.payload.signature",
                "expires_in": 3600,
            }
        )

        with patch("httpx.AsyncClient") as mock_client:
            inst = AsyncMock()
            inst.post = AsyncMock(return_value=mock_resp)
            _mock_async_client(inst)
            mock_client.return_value = inst

            with patch.object(
                provider, "validate_id_token", new_callable=AsyncMock
            ) as mock_validate:
                tokens = _run(provider.exchange_code("code", "http://localhost/cb"))

        mock_validate.assert_awaited_once_with("header.payload.signature", nonce=None)
        assert tokens.id_token == "header.payload.signature"


class TestRefreshTokensErrors:
    """Cover error paths in GenericOIDCProvider.refresh_tokens()."""

    def test_no_token_url_raises(self) -> None:
        """No token_url after discovery raises TokenRefreshError."""
        provider = GenericOIDCProvider(client_id="c", token_url="")
        provider._discovered = True
        with pytest.raises(TokenRefreshError, match="Token URL not configured"):
            _run(provider.refresh_tokens("rt_x"))

    def test_http_error_raises_refresh_error(self) -> None:
        """Generic HTTP error raises TokenRefreshError."""
        provider = GenericOIDCProvider(
            client_id="c",
            token_url="https://idp.example.com/token",
        )
        provider._discovered = True

        with patch("httpx.AsyncClient") as mock_client:
            inst = AsyncMock()
            inst.post = AsyncMock(side_effect=httpx.HTTPError("dns failure"))
            _mock_async_client(inst)
            mock_client.return_value = inst

            with pytest.raises(TokenRefreshError, match="Token refresh request failed"):
                _run(provider.refresh_tokens("rt_x"))


# ── GoogleProvider — build_authorize_url ────────────────────────────


class TestGoogleAuthorize:
    """Cover GoogleProvider.build_authorize_url() merge of extra_params."""

    def test_extra_params_merged(self) -> None:
        """Google merges custom extra_params with default access_type/prompt."""
        provider = GoogleProvider(client_id="c")
        url = provider.build_authorize_url(
            redirect_uri="http://localhost/cb",
            state="s",
            extra_params={"login_hint": "user@example.com"},
        )
        # Both default and custom params present
        assert "access_type=offline" in url
        assert "prompt=consent" in url
        assert "login_hint=user%40example.com" in url


# ── GitHubProvider — exchange / refresh / revoke error paths ────────


class TestGitHubExchangeErrors:
    """Cover error paths in GitHubProvider.exchange_code()."""

    def test_status_error(self) -> None:
        """HTTPStatusError yields TokenError with status code."""
        provider = GitHubProvider(client_id="c", client_secret="s")
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Bad Request", request=MagicMock(), response=mock_resp
        )

        with patch("httpx.AsyncClient") as mock_client:
            inst = AsyncMock()
            inst.post = AsyncMock(return_value=mock_resp)
            _mock_async_client(inst)
            mock_client.return_value = inst

            with pytest.raises(TokenError, match="GitHub token exchange failed"):
                _run(provider.exchange_code("code", "http://localhost/cb"))

    def test_http_error(self) -> None:
        """Generic HTTPError yields TokenError."""
        provider = GitHubProvider(client_id="c", client_secret="s")

        with patch("httpx.AsyncClient") as mock_client:
            inst = AsyncMock()
            inst.post = AsyncMock(side_effect=httpx.HTTPError("dns"))
            _mock_async_client(inst)
            mock_client.return_value = inst

            with pytest.raises(TokenError, match="GitHub token exchange request failed"):
                _run(provider.exchange_code("code", "http://localhost/cb"))

    def test_success(self) -> None:
        """Successful GitHub exchange returns OAuthTokenSet with all fields."""
        provider = GitHubProvider(client_id="c", client_secret="s")

        mock_resp = _make_resp(
            {
                "access_token": "ghp_abc123",
                "token_type": "bearer",
                "scope": "read:user,user:email",
                "expires_in": 28800,
                "refresh_token": "ghr_xyz",
            }
        )

        with patch("httpx.AsyncClient") as mock_client:
            inst = AsyncMock()
            inst.post = AsyncMock(return_value=mock_resp)
            _mock_async_client(inst)
            mock_client.return_value = inst

            tokens = _run(provider.exchange_code("code", "http://localhost/cb"))

        assert tokens.access_token == "ghp_abc123"
        assert tokens.refresh_token == "ghr_xyz"
        assert tokens.expires_in == 28800
        assert tokens.token_type == "bearer"


class TestGitHubRefreshTokens:
    """Cover GitHubProvider.refresh_tokens()."""

    def test_success(self) -> None:
        """Successful GitHub refresh returns new tokens with all fields."""
        provider = GitHubProvider(client_id="c", client_secret="s")

        mock_resp = _make_resp(
            {
                "access_token": "at_refreshed",
                "refresh_token": "rt_new",
                "token_type": "bearer",
                "expires_in": 7200,
                "scope": "read:user",
            }
        )

        with patch("httpx.AsyncClient") as mock_client:
            inst = AsyncMock()
            inst.post = AsyncMock(return_value=mock_resp)
            _mock_async_client(inst)
            mock_client.return_value = inst

            tokens = _run(provider.refresh_tokens("rt_old"))

        assert tokens.access_token == "at_refreshed"
        assert tokens.refresh_token == "rt_new"
        assert tokens.expires_in == 7200

    def test_http_error(self) -> None:
        """HTTP error during GitHub refresh raises TokenRefreshError."""
        provider = GitHubProvider(client_id="c", client_secret="s")

        with patch("httpx.AsyncClient") as mock_client:
            inst = AsyncMock()
            inst.post = AsyncMock(side_effect=httpx.HTTPError("connect"))
            _mock_async_client(inst)
            mock_client.return_value = inst

            with pytest.raises(TokenRefreshError, match="GitHub token refresh failed"):
                _run(provider.refresh_tokens("rt_x"))

    def test_error_in_body(self) -> None:
        """GitHub returns error in JSON body during refresh."""
        provider = GitHubProvider(client_id="c", client_secret="s")

        mock_resp = _make_resp({"error": "bad_refresh_token", "error_description": "invalid token"})

        with patch("httpx.AsyncClient") as mock_client:
            inst = AsyncMock()
            inst.post = AsyncMock(return_value=mock_resp)
            _mock_async_client(inst)
            mock_client.return_value = inst

            with pytest.raises(TokenRefreshError, match="invalid token"):
                _run(provider.refresh_tokens("rt_x"))


class TestGitHubRevokeError:
    """Cover GitHubProvider.revoke_token() exception path."""

    def test_revoke_http_error(self) -> None:
        """HTTPError during revoke returns False."""
        provider = GitHubProvider(client_id="gh_id", client_secret="gh_sec")
        with patch("httpx.AsyncClient") as mock_client:
            inst = AsyncMock()
            inst.request = AsyncMock(side_effect=httpx.HTTPError("conn"))
            _mock_async_client(inst)
            mock_client.return_value = inst
            result = _run(provider.revoke_token("ghp_x"))
        assert result is False


# ── MicrosoftProvider — _discover branches ──────────────────────────


class TestMicrosoftDiscover:
    """Cover MicrosoftProvider._discover() variations."""

    def test_discover_skips_when_already_discovered(self) -> None:
        """Already discovered MS provider short-circuits."""
        provider = MicrosoftProvider(client_id="c", tenant_id="my-tenant")
        provider._discovered = True
        with patch("httpx.AsyncClient") as mock_client:
            _run(provider._discover())
            mock_client.assert_not_called()

    def test_discover_skips_when_no_issuer(self) -> None:
        """MS provider with empty issuer_url short-circuits."""
        provider = MicrosoftProvider(client_id="c")
        provider.issuer_url = ""
        with patch("httpx.AsyncClient") as mock_client:
            _run(provider._discover())
            mock_client.assert_not_called()

    def test_discover_with_tenantid_placeholder(self) -> None:
        """MS issuer with `{tenantid}` placeholder is normalized."""
        provider = MicrosoftProvider(client_id="c", tenant_id="my-tenant")
        # Don't set explicit URLs - allow discovery to populate them
        provider.authorize_url = ""
        provider.token_url = ""
        provider.userinfo_url = ""
        provider.revocation_url = ""

        config_resp = _make_resp(
            {
                # Microsoft uses {tenantid} placeholder
                "issuer": "https://login.microsoftonline.com/{tenantid}/v2.0",
                "authorization_endpoint": (
                    "https://login.microsoftonline.com/my-tenant/oauth2/v2.0/authorize"
                ),
                "token_endpoint": ("https://login.microsoftonline.com/my-tenant/oauth2/v2.0/token"),
                "userinfo_endpoint": "https://graph.microsoft.com/oidc/userinfo",
                "revocation_endpoint": "",
                "jwks_uri": ("https://login.microsoftonline.com/my-tenant/discovery/v2.0/keys"),
            }
        )

        with patch("httpx.AsyncClient") as mock_client:
            inst = AsyncMock()
            inst.get = AsyncMock(return_value=config_resp)
            _mock_async_client(inst)
            mock_client.return_value = inst
            _run(provider._discover())

        assert provider._discovered
        assert "/authorize" in provider.authorize_url
        assert "/token" in provider.token_url
        assert provider.userinfo_url == "https://graph.microsoft.com/oidc/userinfo"
        assert provider._jwks_uri.endswith("/discovery/v2.0/keys")

    def test_discover_real_issuer_mismatch_raises(self) -> None:
        """A non-matching MS issuer (after normalization) still raises."""
        provider = MicrosoftProvider(client_id="c", tenant_id="my-tenant")
        config_resp = _make_resp({"issuer": "https://login.microsoftonline.com/wrong-tenant/v2.0"})

        with patch("httpx.AsyncClient") as mock_client:
            inst = AsyncMock()
            inst.get = AsyncMock(return_value=config_resp)
            _mock_async_client(inst)
            mock_client.return_value = inst

            with pytest.raises(AuthenticationError, match="issuer mismatch"):
                _run(provider._discover())

    def test_discover_http_error_logs_warning(self) -> None:
        """HTTP error during MS discovery is logged but not raised."""
        provider = MicrosoftProvider(client_id="c", tenant_id="my-tenant")

        with patch("httpx.AsyncClient") as mock_client:
            inst = AsyncMock()
            inst.get = AsyncMock(side_effect=httpx.HTTPError("network down"))
            _mock_async_client(inst)
            mock_client.return_value = inst
            _run(provider._discover())

        assert not provider._discovered


# ── Module-level — authlib import fallback ──────────────────────────


class TestAuthlibImportFallback:
    """Cover the ImportError fallback when authlib is missing."""

    def test_reimport_with_missing_authlib(self) -> None:
        """When authlib import fails at module load, _HAS_AUTHLIB becomes False."""
        import importlib

        # Save the existing module
        original = sys.modules.get("pywry.auth.providers")

        # Remove authlib + jose modules to force ImportError
        authlib_modules = [k for k in list(sys.modules) if k.startswith("authlib")]
        saved = {k: sys.modules[k] for k in authlib_modules}
        for k in authlib_modules:
            sys.modules[k] = None  # type: ignore[assignment]

        try:
            sys.modules.pop("pywry.auth.providers", None)
            # Re-import — should trigger the ImportError fallback path
            reimported = importlib.import_module("pywry.auth.providers")
            assert reimported._HAS_AUTHLIB is False
        finally:
            # Restore authlib modules
            for k, v in saved.items():
                sys.modules[k] = v
            # Restore the original providers module
            if original is not None:
                sys.modules["pywry.auth.providers"] = original
            else:
                sys.modules.pop("pywry.auth.providers", None)
                importlib.import_module("pywry.auth.providers")


# ── OAuthTokenSet ────────────────────────────────────────────────────


class TestOAuthTokenSet:
    """Tests for OAuthTokenSet dataclass."""

    def test_is_expired_false(self) -> None:
        """Token with future expiry is not expired."""
        tokens = OAuthTokenSet(
            access_token="at",
            expires_in=3600,
            issued_at=time.time(),
        )
        assert not tokens.is_expired

    def test_is_expired_true(self) -> None:
        """Token with past expiry is expired."""
        tokens = OAuthTokenSet(
            access_token="at",
            expires_in=3600,
            issued_at=time.time() - 7200,  # 2 hours ago
        )
        assert tokens.is_expired

    def test_is_expired_no_expiry(self) -> None:
        """Token without expires_in is never expired."""
        tokens = OAuthTokenSet(access_token="at", expires_in=None)
        assert not tokens.is_expired

    def test_expires_at(self) -> None:
        """expires_at returns correct timestamp."""
        now = time.time()
        tokens = OAuthTokenSet(access_token="at", expires_in=3600, issued_at=now)
        assert tokens.expires_at == pytest.approx(now + 3600, abs=1)

    def test_expires_at_none(self) -> None:
        """expires_at returns None when no expiry."""
        tokens = OAuthTokenSet(access_token="at", expires_in=None)
        assert tokens.expires_at is None
