"""OAuth2 provider abstractions.

Defines the OAuthProvider ABC and concrete implementations for
Google, GitHub, Microsoft, and generic OIDC providers.
"""

# pylint: disable=logging-too-many-args

from __future__ import annotations

import logging
import time

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

import httpx

from ..exceptions import AuthenticationError, TokenError, TokenRefreshError
from ..state.types import OAuthTokenSet


try:
    from authlib.jose import JsonWebKey, JsonWebToken  # type: ignore[import-untyped]

    _HAS_AUTHLIB = True
except ImportError:
    _HAS_AUTHLIB = False


if TYPE_CHECKING:
    from .pkce import PKCEChallenge

logger = logging.getLogger("pywry.auth")


class OAuthProvider(ABC):
    """Abstract base class for OAuth2 providers.

    Parameters
    ----------
    client_id : str
        The OAuth2 client ID.
    client_secret : str
        The OAuth2 client secret (empty string for public clients).
    scopes : list[str]
        Requested OAuth2 scopes.
    authorize_url : str
        The provider's authorization endpoint.
    token_url : str
        The provider's token exchange endpoint.
    userinfo_url : str
        The provider's userinfo endpoint (optional for non-OIDC).
    revocation_url : str
        The provider's token revocation endpoint (RFC 7009).
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str = "",
        scopes: list[str] | None = None,
        authorize_url: str = "",
        token_url: str = "",
        userinfo_url: str = "",
        revocation_url: str = "",
    ) -> None:
        """Initialize OAuth provider."""
        self.client_id = client_id
        self.client_secret = client_secret
        self.scopes = scopes or []
        self.authorize_url = authorize_url
        self.token_url = token_url
        self.userinfo_url = userinfo_url
        self.revocation_url = revocation_url
        self._http_client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the shared HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client

    async def close(self) -> None:
        """Close the shared HTTP client. Call from app shutdown lifecycle."""
        if self._http_client is not None and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None

    def build_authorize_url(
        self,
        redirect_uri: str,
        state: str,
        pkce: PKCEChallenge | None = None,
        extra_params: dict[str, str] | None = None,
    ) -> str:
        """Build the full authorization URL.

        Parameters
        ----------
        redirect_uri : str
            The callback URL to redirect to after authorization.
        state : str
            CSRF protection nonce.
        pkce : PKCEChallenge, optional
            PKCE challenge for public clients.
        extra_params : dict, optional
            Additional query parameters.

        Returns
        -------
        str
            The full authorization URL.
        """
        params: dict[str, str] = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": " ".join(self.scopes),
        }
        if pkce:
            params["code_challenge"] = pkce.challenge
            params["code_challenge_method"] = pkce.method
        if extra_params:
            params.update(extra_params)
        return f"{self.authorize_url}?{urlencode(params)}"

    @abstractmethod
    async def exchange_code(
        self,
        code: str,
        redirect_uri: str,
        pkce_verifier: str | None = None,
        nonce: str | None = None,
    ) -> OAuthTokenSet:
        """Exchange authorization code for tokens.

        Parameters
        ----------
        code : str
            The authorization code from the callback.
        redirect_uri : str
            The redirect URI used in the authorization request.
        pkce_verifier : str, optional
            The PKCE code verifier if PKCE was used.
        nonce : str, optional
            The nonce sent in the authorize request (for ID token validation).

        Returns
        -------
        OAuthTokenSet
            The token set from the provider.

        Raises
        ------
        TokenError
            If the code exchange fails.
        """

    @abstractmethod
    async def refresh_tokens(self, refresh_token: str) -> OAuthTokenSet:
        """Refresh an expired access token.

        Parameters
        ----------
        refresh_token : str
            The refresh token.

        Returns
        -------
        OAuthTokenSet
            A new token set with a fresh access token.

        Raises
        ------
        TokenRefreshError
            If the refresh fails.
        """

    async def get_userinfo(self, access_token: str) -> dict[str, Any]:
        """Fetch user profile information from the provider.

        Parameters
        ----------
        access_token : str
            A valid access token.

        Returns
        -------
        dict[str, Any]
            User profile data from the provider.
        """
        if not self.userinfo_url:
            return {}
        client = await self._get_client()
        resp = await client.get(
            self.userinfo_url,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]

    async def revoke_token(self, token: str) -> bool:
        """Revoke a token at the provider (RFC 7009).

        Posts to the ``revocation_url`` if one is configured.
        Subclasses with non-standard revocation APIs should override.

        Parameters
        ----------
        token : str
            The token to revoke (access or refresh).

        Returns
        -------
        bool
            True if revocation succeeded, False if no endpoint
            is configured or the request failed.
        """
        if not self.revocation_url:
            return False
        try:
            client = await self._get_client()
            resp = await client.post(
                self.revocation_url,
                data={"token": token, "client_id": self.client_id},
                timeout=10.0,
            )
        except httpx.HTTPError:
            return False
        return resp.is_success


class GenericOIDCProvider(OAuthProvider):
    """Generic OpenID Connect provider.

    Supports auto-discovery from ``/.well-known/openid-configuration``
    if an ``issuer_url`` is provided.

    Parameters
    ----------
    client_id : str
        The OAuth2 client ID.
    client_secret : str
        The OAuth2 client secret.
    issuer_url : str
        The OIDC issuer URL (used for auto-discovery).
    scopes : list[str], optional
        Requested scopes (defaults to ``["openid", "email", "profile"]``).
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str = "",
        issuer_url: str = "",
        scopes: list[str] | None = None,
        authorize_url: str = "",
        token_url: str = "",
        userinfo_url: str = "",
        revocation_url: str = "",
        *,
        require_id_token_validation: bool = True,
    ) -> None:
        """Initialize OIDC provider."""
        super().__init__(
            client_id=client_id,
            client_secret=client_secret,
            scopes=scopes or ["openid", "email", "profile"],
            authorize_url=authorize_url,
            token_url=token_url,
            userinfo_url=userinfo_url,
            revocation_url=revocation_url,
        )
        self.issuer_url = issuer_url
        self.require_id_token_validation = require_id_token_validation
        self._discovered = False
        self._jwks_uri: str = ""
        self._jwks_data: dict[str, Any] | None = None

    async def _discover(self) -> None:
        """Auto-discover OIDC endpoints from the well-known configuration."""
        if self._discovered or not self.issuer_url:
            return
        url = f"{self.issuer_url.rstrip('/')}/.well-known/openid-configuration"
        try:
            client = await self._get_client()
            resp = await client.get(url, timeout=10.0)
            resp.raise_for_status()
            config = resp.json()
            # Validate issuer exactly matches configured issuer
            discovered_issuer = config.get("issuer", "")
            expected = self.issuer_url.rstrip("/")
            if discovered_issuer.rstrip("/") != expected:
                msg = f"OIDC issuer mismatch: expected '{expected}', got '{discovered_issuer}'"
                raise AuthenticationError(msg, provider=self.__class__.__name__)
            if not self.authorize_url:
                self.authorize_url = config.get("authorization_endpoint", "")
            if not self.token_url:
                self.token_url = config.get("token_endpoint", "")
            if not self.userinfo_url:
                self.userinfo_url = config.get("userinfo_endpoint", "")
            if not self.revocation_url:
                self.revocation_url = config.get("revocation_endpoint", "")
            self._jwks_uri = config.get("jwks_uri", "")
            self._discovered = True
        except httpx.HTTPError as exc:
            logger.warning("OIDC discovery failed for %s: %s", self.issuer_url, exc)

    async def _fetch_jwks(self) -> dict[str, Any]:
        """Fetch the JWKS key set from the provider."""
        if self._jwks_data is not None:
            return self._jwks_data
        if not self._jwks_uri:
            msg = "JWKS URI not available (run discovery first)"
            raise TokenError(msg, provider=self.__class__.__name__)
        client = await self._get_client()
        resp = await client.get(self._jwks_uri, timeout=10.0)
        resp.raise_for_status()
        self._jwks_data = resp.json()
        return self._jwks_data

    async def validate_id_token(
        self,
        id_token: str,
        nonce: str | None = None,
    ) -> dict[str, Any]:
        """Validate an OIDC ID token.

        Checks signature (via JWKS), issuer, audience, expiry, and nonce.

        Parameters
        ----------
        id_token : str
            The raw ID token JWT string.
        nonce : str, optional
            Expected nonce value (if one was sent in the authorize request).

        Returns
        -------
        dict[str, Any]
            The validated claims from the ID token.

        Raises
        ------
        TokenError
            If validation fails for any reason.
        """
        if not _HAS_AUTHLIB:
            msg = (
                "authlib is required for OIDC ID token validation. "
                "Install with: pip install authlib"
            )
            raise TokenError(msg, provider=self.__class__.__name__)

        await self._discover()
        jwks_data = await self._fetch_jwks()

        jwt = JsonWebToken(["RS256", "RS384", "RS512", "ES256", "ES384", "ES512"])

        claims_options: dict[str, Any] = {
            "iss": {"essential": True, "value": self.issuer_url.rstrip("/")},
            "aud": {"essential": True, "value": self.client_id},
            "exp": {"essential": True},
        }
        if nonce:
            claims_options["nonce"] = {"essential": True, "value": nonce}

        try:
            key_set = JsonWebKey.import_key_set(jwks_data)
            claims = jwt.decode(
                id_token,
                key_set,
                claims_options=claims_options,
            )
            claims.validate()
        except Exception as exc:
            msg = f"ID token validation failed: {exc}"
            raise TokenError(msg, provider=self.__class__.__name__) from exc

        return dict(claims)

    async def exchange_code(
        self,
        code: str,
        redirect_uri: str,
        pkce_verifier: str | None = None,
        nonce: str | None = None,
    ) -> OAuthTokenSet:
        """Exchange authorization code for tokens via OIDC token endpoint.

        Parameters
        ----------
        code : str
            The authorization code from the callback.
        redirect_uri : str
            The redirect URI used in the authorization request.
        pkce_verifier : str, optional
            The PKCE code verifier if PKCE was used.
        nonce : str, optional
            The nonce sent in the authorize request (for ID token validation).
        """
        await self._discover()
        if not self.token_url:
            msg = "Token URL not configured and discovery failed"
            raise TokenError(msg, provider=self.__class__.__name__)

        data: dict[str, str] = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": self.client_id,
        }
        if self.client_secret:
            data["client_secret"] = self.client_secret
        if pkce_verifier:
            data["code_verifier"] = pkce_verifier

        try:
            client = await self._get_client()
            resp = await client.post(
                self.token_url,
                data=data,
                headers={"Accept": "application/json"},
                timeout=30.0,
            )
            resp.raise_for_status()
            raw = resp.json()
        except httpx.HTTPStatusError as exc:
            msg = f"Token exchange failed: {exc.response.status_code}"
            raise TokenError(msg, provider=self.__class__.__name__) from exc
        except httpx.HTTPError as exc:
            msg = f"Token exchange request failed: {exc}"
            raise TokenError(msg, provider=self.__class__.__name__) from exc

        # Validate ID token if present and validation is required
        id_token_raw = raw.get("id_token")
        if id_token_raw and self.require_id_token_validation:
            await self.validate_id_token(id_token_raw, nonce=nonce)

        return OAuthTokenSet(
            access_token=raw["access_token"],
            token_type=raw.get("token_type", "Bearer"),
            refresh_token=raw.get("refresh_token"),
            expires_in=raw.get("expires_in"),
            id_token=id_token_raw,
            scope=raw.get("scope", ""),
            raw=raw,
            issued_at=time.time(),
        )

    async def refresh_tokens(self, refresh_token: str) -> OAuthTokenSet:
        """Refresh tokens via OIDC token endpoint."""
        await self._discover()
        if not self.token_url:
            msg = "Token URL not configured and discovery failed"
            raise TokenRefreshError(msg, provider=self.__class__.__name__)

        data: dict[str, str] = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.client_id,
        }
        if self.client_secret:
            data["client_secret"] = self.client_secret

        try:
            client = await self._get_client()
            resp = await client.post(
                self.token_url,
                data=data,
                headers={"Accept": "application/json"},
                timeout=30.0,
            )
            resp.raise_for_status()
            raw = resp.json()
        except httpx.HTTPStatusError as exc:
            msg = f"Token refresh failed: {exc.response.status_code}"
            raise TokenRefreshError(msg, provider=self.__class__.__name__) from exc
        except httpx.HTTPError as exc:
            msg = f"Token refresh request failed: {exc}"
            raise TokenRefreshError(msg, provider=self.__class__.__name__) from exc

        return OAuthTokenSet(
            access_token=raw["access_token"],
            token_type=raw.get("token_type", "Bearer"),
            refresh_token=raw.get("refresh_token", refresh_token),
            expires_in=raw.get("expires_in"),
            id_token=raw.get("id_token"),
            scope=raw.get("scope", ""),
            raw=raw,
            issued_at=time.time(),
        )

    async def revoke_token(self, token: str) -> bool:
        """Revoke a token via the OIDC revocation endpoint.

        Triggers endpoint auto-discovery before delegating to the
        base implementation.
        """
        await self._discover()
        return await super().revoke_token(token)


class GoogleProvider(GenericOIDCProvider):
    """Google OAuth2 provider with preset endpoints.

    Parameters
    ----------
    client_id : str
        Google OAuth2 client ID.
    client_secret : str
        Google OAuth2 client secret.
    scopes : list[str], optional
        Requested scopes (defaults to openid, email, profile).
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str = "",
        scopes: list[str] | None = None,
    ) -> None:
        """Initialize Google provider."""
        super().__init__(
            client_id=client_id,
            client_secret=client_secret,
            scopes=scopes or ["openid", "email", "profile"],
            authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
            token_url="https://oauth2.googleapis.com/token",  # noqa: S106
            userinfo_url="https://openidconnect.googleapis.com/v1/userinfo",
            revocation_url="https://oauth2.googleapis.com/revoke",
        )

    def build_authorize_url(
        self,
        redirect_uri: str,
        state: str,
        pkce: PKCEChallenge | None = None,
        extra_params: dict[str, str] | None = None,
    ) -> str:
        """Build Google authorization URL with access_type=offline."""
        params = {"access_type": "offline", "prompt": "consent"}
        if extra_params:
            params.update(extra_params)
        return super().build_authorize_url(redirect_uri, state, pkce, params)


class GitHubProvider(OAuthProvider):
    """GitHub OAuth2 provider.

    GitHub uses a non-standard token exchange (no OIDC) and
    a separate API endpoint for user info.

    Parameters
    ----------
    client_id : str
        GitHub OAuth2 client ID.
    client_secret : str
        GitHub OAuth2 client secret.
    scopes : list[str], optional
        Requested scopes (defaults to ``["read:user", "user:email"]``).
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str = "",
        scopes: list[str] | None = None,
    ) -> None:
        """Initialize GitHub provider."""
        super().__init__(
            client_id=client_id,
            client_secret=client_secret,
            scopes=scopes or ["read:user", "user:email"],
            authorize_url="https://github.com/login/oauth/authorize",
            token_url="https://github.com/login/oauth/access_token",  # noqa: S106
            userinfo_url="https://api.github.com/user",
        )

    async def exchange_code(
        self,
        code: str,
        redirect_uri: str,
        pkce_verifier: str | None = None,
        nonce: str | None = None,
    ) -> OAuthTokenSet:
        """Exchange authorization code for a GitHub access token."""
        data: dict[str, str] = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        }

        try:
            client = await self._get_client()
            resp = await client.post(
                self.token_url,
                data=data,
                headers={"Accept": "application/json"},
                timeout=30.0,
            )
            resp.raise_for_status()
            raw = resp.json()
        except httpx.HTTPStatusError as exc:
            msg = f"GitHub token exchange failed: {exc.response.status_code}"
            raise TokenError(msg, provider="github") from exc
        except httpx.HTTPError as exc:
            msg = f"GitHub token exchange request failed: {exc}"
            raise TokenError(msg, provider="github") from exc

        if "error" in raw:
            msg = f"GitHub token error: {raw.get('error_description', raw['error'])}"
            raise TokenError(msg, provider="github")

        return OAuthTokenSet(
            access_token=raw["access_token"],
            token_type=raw.get("token_type", "bearer"),
            refresh_token=raw.get("refresh_token"),
            expires_in=raw.get("expires_in"),
            scope=raw.get("scope", ""),
            raw=raw,
            issued_at=time.time(),
        )

    async def refresh_tokens(self, refresh_token: str) -> OAuthTokenSet:
        """Refresh GitHub tokens (GitHub uses token rotation)."""
        data: dict[str, str] = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }

        try:
            client = await self._get_client()
            resp = await client.post(
                self.token_url,
                data=data,
                headers={"Accept": "application/json"},
                timeout=30.0,
            )
            resp.raise_for_status()
            raw = resp.json()
        except httpx.HTTPError as exc:
            msg = f"GitHub token refresh failed: {exc}"
            raise TokenRefreshError(msg, provider="github") from exc

        if "error" in raw:
            msg = f"GitHub refresh error: {raw.get('error_description', raw['error'])}"
            raise TokenRefreshError(msg, provider="github")

        return OAuthTokenSet(
            access_token=raw["access_token"],
            token_type=raw.get("token_type", "bearer"),
            refresh_token=raw.get("refresh_token"),
            expires_in=raw.get("expires_in"),
            scope=raw.get("scope", ""),
            raw=raw,
            issued_at=time.time(),
        )

    async def revoke_token(self, token: str) -> bool:
        """Revoke a GitHub token via the Applications API.

        Uses ``DELETE /applications/{client_id}/token`` with HTTP
        Basic authentication (client_id / client_secret).

        Parameters
        ----------
        token : str
            The access token to revoke.

        Returns
        -------
        bool
            True if GitHub accepted the revocation.
        """
        if not self.client_secret:
            logger.warning("GitHub token revocation requires a client_secret")
            return False
        url = f"https://api.github.com/applications/{self.client_id}/token"
        try:
            client = await self._get_client()
            resp = await client.request(
                "DELETE",
                url,
                auth=(self.client_id, self.client_secret),
                json={"access_token": token},
                timeout=10.0,
            )
        except httpx.HTTPError:
            return False
        # GitHub returns 204 No Content on success
        return resp.status_code == 204


class MicrosoftProvider(GenericOIDCProvider):
    """Microsoft / Azure AD OAuth2 provider.

    Parameters
    ----------
    client_id : str
        Azure AD application (client) ID.
    client_secret : str
        Azure AD client secret.
    tenant_id : str
        Azure AD tenant ID (default "common" for multi-tenant).
    scopes : list[str], optional
        Requested scopes.
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str = "",
        tenant_id: str = "common",
        scopes: list[str] | None = None,
    ) -> None:
        """Initialize Microsoft provider."""
        base = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0"
        super().__init__(
            client_id=client_id,
            client_secret=client_secret,
            scopes=scopes or ["openid", "email", "profile", "offline_access"],
            authorize_url=f"{base}/authorize",
            token_url=f"{base}/token",
            userinfo_url="https://graph.microsoft.com/oidc/userinfo",
            revocation_url="",  # Microsoft doesn't support standard revocation
        )
        self.tenant_id = tenant_id


def create_provider_from_settings(settings: Any) -> OAuthProvider:
    """Create an OAuthProvider instance from OAuth2Settings.

    Parameters
    ----------
    settings : OAuth2Settings
        The OAuth2 configuration settings.

    Returns
    -------
    OAuthProvider
        A configured provider instance.

    Raises
    ------
    AuthenticationError
        If the provider type is unknown or settings are invalid.
    """
    provider_type = getattr(settings, "provider", "custom")
    client_id = getattr(settings, "client_id", "")
    client_secret = getattr(settings, "client_secret", "")
    scopes_str = getattr(settings, "scopes", "")
    scopes = [s.strip() for s in scopes_str.split() if s.strip()] if scopes_str else None

    if provider_type == "google":
        return GoogleProvider(
            client_id=client_id,
            client_secret=client_secret,
            scopes=scopes,
        )
    if provider_type == "github":
        return GitHubProvider(
            client_id=client_id,
            client_secret=client_secret,
            scopes=scopes,
        )
    if provider_type == "microsoft":
        tenant_id = getattr(settings, "tenant_id", "common")
        return MicrosoftProvider(
            client_id=client_id,
            client_secret=client_secret,
            tenant_id=tenant_id,
            scopes=scopes,
        )
    if provider_type == "oidc":
        issuer_url = getattr(settings, "issuer_url", "")
        return GenericOIDCProvider(
            client_id=client_id,
            client_secret=client_secret,
            issuer_url=issuer_url,
            scopes=scopes,
            authorize_url=getattr(settings, "authorize_url", ""),
            token_url=getattr(settings, "token_url", ""),
            userinfo_url=getattr(settings, "userinfo_url", ""),
        )
    if provider_type == "custom":
        authorize_url = getattr(settings, "authorize_url", "")
        token_url = getattr(settings, "token_url", "")
        if not authorize_url or not token_url:
            msg = "Custom provider requires authorize_url and token_url"
            raise AuthenticationError(msg, provider="custom")
        return GenericOIDCProvider(
            client_id=client_id,
            client_secret=client_secret,
            scopes=scopes,
            authorize_url=authorize_url,
            token_url=token_url,
            userinfo_url=getattr(settings, "userinfo_url", ""),
        )

    msg = f"Unknown OAuth2 provider type: {provider_type}"
    raise AuthenticationError(msg, provider=provider_type)
