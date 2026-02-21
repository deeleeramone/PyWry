"""OAuth2 authentication system for PyWry.

Provides OAuth2 provider abstractions, token storage, session management,
and auth flow orchestration for both native window and deploy modes.
"""

from __future__ import annotations

from .flow import AuthFlowManager
from .pkce import PKCEChallenge
from .providers import (
    GenericOIDCProvider,
    GitHubProvider,
    GoogleProvider,
    MicrosoftProvider,
    OAuthProvider,
    create_provider_from_settings,
)
from .session import SessionManager
from .token_store import (
    MemoryTokenStore,
    RedisTokenStore,
    TokenStore,
    get_token_store,
    reset_token_store,
)


__all__ = [
    "AuthFlowManager",
    "GenericOIDCProvider",
    "GitHubProvider",
    "GoogleProvider",
    "MemoryTokenStore",
    "MicrosoftProvider",
    "OAuthProvider",
    "PKCEChallenge",
    "RedisTokenStore",
    "SessionManager",
    "TokenStore",
    "create_provider_from_settings",
    "get_token_store",
    "reset_token_store",
]
