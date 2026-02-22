# OAuth2 Authentication

PyWry includes a full OAuth2 authentication system for both **native mode** (desktop apps) and **deploy mode** (multi-user web servers). It supports Google, GitHub, Microsoft, and any OpenID Connect provider out of the box.

This guide uses two perspectives throughout:

- **Developer** — the person writing the PyWry application
- **User** — the person running the app and logging in

---

## How it works (overview)

=== "Native mode"

    The developer calls `app.login()`. PyWry starts an ephemeral HTTP server on a
    random `localhost` port, opens the provider's login page in the user's system
    browser, waits for the OAuth2 redirect to land on that server, exchanges the
    authorization code for tokens, and hands the result back to the developer's code.

    The user never interacts with PyWry directly — they log in at the provider's
    own website (Google, GitHub, etc.) and are then redirected back automatically.

=== "Deploy mode"

    The developer mounts a FastAPI router (`/auth/*`) on the server. The user
    navigates to `/auth/login`, gets redirected to the provider, authenticates,
    and lands back at `/auth/callback` where PyWry creates a server session and
    sets a cookie. The user is then redirected to the application root (`/`).

---

## Developer: one-time provider setup

Before writing any code, register an OAuth2 application with your chosen provider.
Each provider's developer console will give you a **client ID** and **client secret**.
You must also register the **redirect URI** that PyWry will use.

| Mode | Redirect URI to register |
|:---|:---|
| Native | `http://127.0.0.1` (any port, or use a wildcard if the provider supports it) |
| Deploy | `https://your-domain.com/auth/callback` |

!!! warning "Keep your client secret private"
    Never commit `client_secret` to version control. Use environment variables or
    a secrets manager.

Provider registration links:

- **Google**: [console.cloud.google.com](https://console.cloud.google.com/) → APIs & Services → Credentials
- **GitHub**: [github.com/settings/developers](https://github.com/settings/developers) → OAuth Apps
- **Microsoft**: [portal.azure.com](https://portal.azure.com/) → Azure Active Directory → App registrations

---

## Developer: configure the provider

Set credentials via environment variables (recommended) or construct the provider
in code. PyWry reads `PYWRY_OAUTH2__*` variables automatically when
`PYWRY_OAUTH2__CLIENT_ID` is present.

=== "Environment variables"

    ```bash
    # Choose one of: google, github, microsoft, oidc, custom
    export PYWRY_OAUTH2__PROVIDER=github
    export PYWRY_OAUTH2__CLIENT_ID=your-client-id
    export PYWRY_OAUTH2__CLIENT_SECRET=your-client-secret
    ```

    Other available variables:

    | Variable | Default | Description |
    |:---|:---|:---|
    | `PYWRY_OAUTH2__SCOPES` | `openid email profile` | Space-separated scopes |
    | `PYWRY_OAUTH2__USE_PKCE` | `true` | Enable PKCE (recommended) |
    | `PYWRY_OAUTH2__TOKEN_STORE_BACKEND` | `memory` | `memory`, `keyring`, or `redis` |
    | `PYWRY_OAUTH2__AUTH_TIMEOUT_SECONDS` | `120` | Seconds to wait for user callback |
    | `PYWRY_OAUTH2__REFRESH_BUFFER_SECONDS` | `60` | Seconds before expiry to refresh |
    | `PYWRY_OAUTH2__ISSUER_URL` | *(empty)* | OIDC discovery URL (oidc provider) |
    | `PYWRY_OAUTH2__TENANT_ID` | `common` | Azure AD tenant (microsoft provider) |
    | `PYWRY_OAUTH2__AUTHORIZE_URL` | *(empty)* | Required for `custom` provider |
    | `PYWRY_OAUTH2__TOKEN_URL` | *(empty)* | Required for `custom` provider |

=== "Google"

    ```python
    from pywry.auth import GoogleProvider

    provider = GoogleProvider(
        client_id="…",
        client_secret="…",
        # Default scopes: openid email profile
        # Always adds access_type=offline and prompt=consent
        # so a refresh token is returned.
    )
    ```

=== "GitHub"

    ```python
    from pywry.auth import GitHubProvider

    provider = GitHubProvider(
        client_id="…",
        client_secret="…",
        # Default scopes: read:user user:email
        # client_secret is required for token revocation.
    )
    ```

    GitHub is not a standard OIDC provider. Userinfo comes from
    `https://api.github.com/user`. Token revocation uses
    `DELETE /applications/{client_id}/token` with HTTP Basic auth.

=== "Microsoft / Azure AD"

    ```python
    from pywry.auth import MicrosoftProvider

    provider = MicrosoftProvider(
        client_id="…",
        client_secret="…",
        tenant_id="common",  # or your specific tenant GUID
        # Default scopes: openid email profile offline_access
    )
    ```

    Use `tenant_id="common"` for multi-tenant apps. Microsoft does not implement
    RFC 7009, so `revoke_token()` always returns `False`.

=== "Generic OIDC"

    ```python
    from pywry.auth import GenericOIDCProvider

    provider = GenericOIDCProvider(
        client_id="…",
        client_secret="…",
        issuer_url="https://auth.example.com",
        # Fetches /.well-known/openid-configuration on first use.
        # Explicit URLs take precedence over discovered ones.
        scopes=["openid", "profile"],
    )
    ```

=== "From settings"

    When settings are loaded from config or env vars:

    ```python
    from pywry.auth import create_provider_from_settings
    from pywry.config import get_settings

    provider = create_provider_from_settings(get_settings().oauth2)
    # Returns GoogleProvider, GitHubProvider, MicrosoftProvider,
    # or GenericOIDCProvider based on the 'provider' field.
    # Raises AuthenticationError for unknown types or missing URLs.
    ```

---

## Native mode

### Developer: call `app.login()`

`PyWry.login()` is the single entry point for native mode. It constructs the
provider, token store, session manager, and flow manager from settings, runs the
OAuth2 flow, and returns when the user has finished authenticating (or fails).

```python
from pywry import PyWry
from pywry.exceptions import AuthFlowTimeout, AuthFlowCancelled, AuthenticationError

app = PyWry()

try:
    result = app.login()  # blocks — see "User experience" below
except AuthFlowTimeout:
    print("User took too long to authenticate")
except AuthFlowCancelled:
    print("User closed the login window")
except AuthenticationError as e:
    print(f"Authentication failed: {e}")
```

After a successful login:

```python
if result.success:
    user_id   = result.user_info.get("sub") or result.user_info.get("login")
    email     = result.user_info.get("email")
    token     = result.tokens.access_token  # valid access token
    expires   = result.tokens.expires_at    # float timestamp, or None

app.is_authenticated  # True after a successful login()
app.logout()          # revokes token at provider, clears store
```

`result.user_info` is the raw dict returned by the provider's userinfo endpoint.
The keys vary by provider:

| Provider | Common keys |
|:---|:---|
| Google | `sub`, `email`, `name`, `picture` |
| GitHub | `id`, `login`, `email`, `name`, `avatar_url` |
| Microsoft | `sub`, `email`, `name` |

### Developer: configure token persistence

By default, tokens are stored in memory and lost when the process exits. For
desktop apps that should remember the user across restarts, use the keyring backend:

```python
result = app.login(
    # Pass a custom token store via the flow manager if needed,
    # or set via environment variable:
    # PYWRY_OAUTH2__TOKEN_STORE_BACKEND=keyring
)
```

```bash
export PYWRY_OAUTH2__TOKEN_STORE_BACKEND=keyring
pip install pywry[auth]  # installs the keyring package
```

See [Token Storage](#token-storage) below for all backends.

### Developer: keep the access token fresh

`SessionManager` runs a background `threading.Timer` that refreshes the token
before it expires, so `app.login()` does not need to be called again after the
initial authentication:

```python
# Constructed automatically inside app.login() using settings:
# PYWRY_OAUTH2__REFRESH_BUFFER_SECONDS=60

# To access the token at any point after login:
token = await app._session_manager.get_access_token()
# Automatically refreshes if the token is within 60s of expiry.
```

When the refresh token itself expires (i.e. the user has been away too long),
re-authentication is needed. Wire `on_reauth_required` to prompt the user:

```python
from pywry.auth import SessionManager

mgr = SessionManager(
    provider=provider,
    token_store=store,
    session_key="user@example.com",
    refresh_buffer_seconds=60,
    on_reauth_required=lambda: app.login(),  # re-authenticate automatically
)
```

### User experience (native mode)

1. The developer's app calls `app.login()`.
2. The user's **system browser opens** to the provider's login page (e.g.
   accounts.google.com, github.com/login). PyWry does not host or render this page.
3. The user enters their credentials at the provider's site and approves the
   requested scopes.
4. The provider redirects the browser to `http://127.0.0.1:{port}/callback`.
   PyWry's ephemeral callback server responds with a plain HTML page:
   > ✅ **Authentication Complete** — You can close this window.
5. Control returns to the developer's code with `AuthFlowResult`.

The user never sees PyWry UI during login. If the provider is slow or the user
takes too long, `AuthFlowTimeout` is raised after `auth_timeout_seconds` (default
120 s).

---

## Deploy mode

### Developer: register the OAuth2 app

Register `https://your-domain.com/auth/callback` as the redirect URI with the
provider (not a `localhost` URL).

### Developer: configure environment variables

```bash
# OAuth2 provider
PYWRY_OAUTH2__PROVIDER=google
PYWRY_OAUTH2__CLIENT_ID=…
PYWRY_OAUTH2__CLIENT_SECRET=…

# Auth middleware
PYWRY_DEPLOY__AUTH_ENABLED=true
PYWRY_DEPLOY__AUTH_SESSION_COOKIE=pywry_session
PYWRY_DEPLOY__DEFAULT_ROLES=viewer
PYWRY_DEPLOY__ADMIN_USERS=admin@example.com

# Session / state backend
PYWRY_DEPLOY__STATE_BACKEND=redis
PYWRY_DEPLOY__REDIS_URL=redis://localhost:6379/0
```

Any user whose ID or email matches `ADMIN_USERS` gets `"admin"` added to their
session roles automatically when they log in.

### Developer: mount the auth router

```python
from pywry.auth import create_provider_from_settings, get_token_store
from pywry.auth.deploy_routes import create_auth_router
from pywry.state import get_session_store
from pywry.state.auth import AuthConfig

provider = create_provider_from_settings(settings.oauth2)

auth_router = create_auth_router(
    provider=provider,
    session_store=get_session_store(),
    token_store=get_token_store("redis", redis_url="redis://localhost:6379/0"),
    deploy_settings=settings.deploy,
    auth_config=AuthConfig(
        enabled=True,
        token_secret="your-secret-key",
        session_ttl=86400,  # 24 hours
    ),
    use_pkce=True,
)

fastapi_app.include_router(auth_router)
```

This exposes six endpoints:

| Route | Method | Description |
|:---|:---|:---|
| `/auth/login` | `GET` | Redirects the user to the provider's login page |
| `/auth/callback` | `GET` | Receives the redirect, creates a session, sets a cookie |
| `/auth/refresh` | `POST` | Refreshes the access token (called by frontend JS) |
| `/auth/logout` | `POST` | Revokes the token, deletes the session, clears the cookie |
| `/auth/userinfo` | `GET` | Returns `user_id`, `roles`, and `user_info` for the session |
| `/auth/status` | `GET` | Returns `{authenticated, user_id, roles, expires_at}` |

### Developer: protect routes

Check the session on each request using the auth middleware. The session is
populated by the `pywry_session` cookie set at `/auth/callback`:

```python
from fastapi import Request

@fastapi_app.get("/dashboard")
async def dashboard(request: Request):
    session = getattr(request.state, "session", None)
    if not session:
        return RedirectResponse("/auth/login")
    return {"user": session.user_id, "roles": session.roles}
```

### Developer: prune stale CSRF nonces

`/auth/login` stores a one-time state nonce server-side. Nonces older than
`max_age` seconds can be pruned periodically (e.g. from a background task):

```python
from pywry.auth.deploy_routes import cleanup_expired_states

removed = cleanup_expired_states(max_age=600.0)  # default 10 min
```

### User experience (deploy mode)

1. The user navigates to `/auth/login` (e.g. by clicking a "Sign in" button in the
   frontend).
2. The server generates a PKCE challenge and a CSRF state nonce, then
   **redirects the browser** to the provider's login page.
3. The user logs in at the provider's site and approves the scopes.
4. The provider redirects the browser to `/auth/callback?code=…&state=…`.
5. PyWry validates the state nonce, exchanges the code for tokens, creates a
   session, and sets an `HttpOnly Secure SameSite=Lax` cookie.
6. The browser is **redirected to `/`** — the user lands in the application,
   already authenticated.

To check authentication status from frontend JavaScript:

```javascript
const res = await fetch('/auth/status');
const { authenticated, user_id, roles, expires_at } = await res.json();
```

---

## Token Storage

All backends implement the same async interface (`save`, `load`, `delete`, `exists`,
`list_keys`). Select one with `get_token_store()`:

```python
from pywry.auth import get_token_store

store = get_token_store("memory")                                       # default
store = get_token_store("keyring", service_name="my-app")              # pip install pywry[auth]
store = get_token_store("redis", redis_url="redis://localhost:6379/0") # pip install redis
```

`get_token_store` is `@lru_cache(maxsize=1)` — the same `backend` argument always
returns the same instance.

| Backend | Persistence | Best for |
|:---|:---|:---|
| `memory` | Process lifetime | Development, single-process apps |
| `keyring` | OS credential store | Desktop apps that remember the user |
| `redis` | Redis TTL | Multi-worker deploy mode |

For `redis`, the TTL is `expires_in + 300` seconds (5-minute buffer for refresh).
Keys are namespaced as `{prefix}:oauth:tokens:{key}`.

---

## PKCE

PKCE (Proof Key for Code Exchange, RFC 7636) is enabled by default and recommended
for all clients, especially desktop apps where the OAuth2 redirect goes to
`localhost`. It prevents authorization code interception attacks.

`AuthFlowManager` and `create_auth_router` both handle PKCE automatically.
`PKCEChallenge` is only needed if building a custom flow:

```python
from pywry.auth import PKCEChallenge

pkce = PKCEChallenge.generate(length=64)
pkce.verifier   # sent during token exchange (code_verifier)
pkce.challenge  # sent during authorize (base64url SHA-256 of verifier)
pkce.method     # always "S256"
```

---

## Error Handling

```python
from pywry.exceptions import (
    AuthenticationError,  # general auth failure or bad configuration
    AuthFlowTimeout,      # user did not complete login within auth_timeout_seconds
    AuthFlowCancelled,    # flow.cancel() was called (e.g. user closed the window)
    TokenExpiredError,    # token is expired and no refresh token is available
    TokenRefreshError,    # provider rejected the refresh token
    TokenError,           # token exchange with provider failed
)
```

All exceptions carry contextual fields (`provider`, `flow_id`, `timeout`) where
applicable.

---

## Integration with State & RBAC

OAuth2 authentication integrates with the PyWry session and RBAC system:

1. **OAuth2 tokens** are stored in `TokenStore`, keyed by the user's ID from
   `user_info` (`sub`, `id`, `login`, or `email` — first non-empty).
2. **Sessions** are created in `SessionStore` with `auth_config.session_ttl` as TTL.
3. **Roles** default to `deploy_settings.default_roles` (`viewer` by default).
4. **Admin promotion**: if the user's ID or email appears in
   `deploy_settings.admin_users`, `"admin"` is appended to their roles.
5. **`user_info`** from the provider is stored in `session.metadata["user_info"]`
   and returned verbatim from `/auth/userinfo`.

For details on sessions, RBAC, and the session store, see
[State, Redis & RBAC](state-and-auth.md).

---

## Next Steps

- **[State, Redis & RBAC](state-and-auth.md)** — Session store, roles, and permissions
- **[Deploy Mode](deploy-mode.md)** — Running PyWry as a production web server
- **[Configuration](configuration.md)** — Full settings reference including `OAuth2Settings`
- **[API Reference: Auth](../reference/auth.md)** — Full API docs for the auth package

