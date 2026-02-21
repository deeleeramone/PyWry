# pywry.auth

OAuth2 authentication system — providers, token storage, session management, and flow orchestration.

---

## Package Exports

::: pywry.auth
    options:
      show_root_heading: false
      heading_level: 2
      members:
        - AuthFlowManager
        - OAuthProvider
        - GenericOIDCProvider
        - GoogleProvider
        - GitHubProvider
        - MicrosoftProvider
        - SessionManager
        - TokenStore
        - MemoryTokenStore
        - RedisTokenStore
        - PKCEChallenge
        - create_provider_from_settings
        - get_token_store
      show_if_no_docstring: false
      show_source: false
      show_docstring_description: true
      show_docstring_parameters: false
      show_docstring_returns: false

---

## Submodules

| Module | Description |
|:---|:---|
| [Providers](auth-providers.md) | `OAuthProvider` ABC and concrete implementations (Google, GitHub, Microsoft, OIDC) |
| [Token Store](auth-token-store.md) | Pluggable token storage backends (memory, keyring, Redis) |
| [Flow](auth-flow.md) | `AuthFlowManager` — orchestrates the full OAuth2 authorization code flow |
| [Session](auth-session.md) | `SessionManager` — token lifecycle with automatic background refresh |
| [Deploy Routes](auth-deploy-routes.md) | FastAPI router for server-side OAuth2 in deploy mode |
| [Callback Server](auth-callback-server.md) | Ephemeral localhost server for capturing OAuth2 redirects |
| [PKCE](auth-pkce.md) | RFC 7636 PKCE code challenge generation |
