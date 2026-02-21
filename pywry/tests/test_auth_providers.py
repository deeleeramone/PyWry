"""Unit tests for OAuth2 provider abstractions."""

from __future__ import annotations

import asyncio
import hashlib
import time

from base64 import urlsafe_b64encode
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

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


# ── PKCE Tests ──────────────────────────────────────────────────────


class TestPKCEChallenge:
    """Tests for PKCEChallenge generation."""

    def test_generate_returns_challenge(self) -> None:
        """PKCEChallenge.generate() returns a valid challenge pair."""
        pkce = PKCEChallenge.generate()
        assert pkce.verifier
        assert pkce.challenge
        assert pkce.method == "S256"

    def test_verifier_is_url_safe(self) -> None:
        """Verifier contains only URL-safe characters."""
        pkce = PKCEChallenge.generate()
        # URL-safe base64 chars: A-Z, a-z, 0-9, -, _
        import re

        assert re.match(r"^[A-Za-z0-9_-]+$", pkce.verifier)

    def test_challenge_matches_verifier_sha256(self) -> None:
        """Challenge is the base64url SHA-256 of the verifier."""
        pkce = PKCEChallenge.generate()
        expected_digest = hashlib.sha256(pkce.verifier.encode("ascii")).digest()
        expected_challenge = urlsafe_b64encode(expected_digest).rstrip(b"=").decode("ascii")
        assert pkce.challenge == expected_challenge

    def test_generate_uniqueness(self) -> None:
        """Each generation produces unique values."""
        a = PKCEChallenge.generate()
        b = PKCEChallenge.generate()
        assert a.verifier != b.verifier
        assert a.challenge != b.challenge

    def test_generate_custom_length(self) -> None:
        """Custom length produces different sized verifiers."""
        short = PKCEChallenge.generate(length=32)
        long = PKCEChallenge.generate(length=96)
        # Longer length should generally produce longer verifier
        assert len(short.verifier) < len(long.verifier)

    def test_frozen_dataclass(self) -> None:
        """PKCEChallenge is immutable."""
        pkce = PKCEChallenge.generate()
        with pytest.raises(AttributeError):
            pkce.verifier = "new"  # type: ignore[misc]


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
                asyncio.run(
                    provider.exchange_code("bad_code", "http://localhost/cb")
                )

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
                asyncio.run(
                    provider.exchange_code("bad", "http://localhost/cb")
                )

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

            result = asyncio.run(
                provider.revoke_token("token_to_revoke")
            )

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

            result = asyncio.run(
                provider.revoke_token("token_to_revoke")
            )

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

            result = asyncio.run(
                provider.revoke_token("ghp_abc123")
            )

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

            result = asyncio.run(
                provider.revoke_token("ghp_abc123")
            )

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
