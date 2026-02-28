# Authentication & OAuth2

> Add OAuth2 authentication to PyWry apps — Google, GitHub, Microsoft, or any OIDC provider.

## Two Modes

### Native Mode (Desktop)
Opens a dedicated auth window → user logs in at provider → callback captured on ephemeral localhost server → tokens returned.

```python
from pywry import PyWry

app = PyWry()
result = app.login()  # Blocks until auth completes

if result.success:
    app.show("<h1>Welcome!</h1>")
    app.block()
```

### Deploy Mode (Production)
Auth routes mounted automatically when `auth_enabled=True` and `oauth2` settings are configured.

```bash
PYWRY_DEPLOY__AUTH_ENABLED=true
PYWRY_OAUTH2__PROVIDER=google
PYWRY_OAUTH2__CLIENT_ID=your-id
PYWRY_OAUTH2__CLIENT_SECRET=your-secret
```

Routes: `GET /auth/login`, `GET /auth/callback`, `POST /auth/refresh`, `POST /auth/logout`, `GET /auth/status`, `GET /auth/userinfo`

## Configuration

### Environment Variables

```bash
# Provider: google, github, microsoft, oidc, custom
PYWRY_OAUTH2__PROVIDER=google

# Credentials
PYWRY_OAUTH2__CLIENT_ID=your-client-id
PYWRY_OAUTH2__CLIENT_SECRET=your-client-secret

# Scopes (space-separated)
PYWRY_OAUTH2__SCOPES=openid email profile

# PKCE (recommended for public clients)
PYWRY_OAUTH2__USE_PKCE=true

# Token storage: memory (default), keyring (native), redis (deploy)
PYWRY_OAUTH2__TOKEN_STORE_BACKEND=memory

# Custom provider endpoints
PYWRY_OAUTH2__AUTHORIZE_URL=https://provider.com/authorize
PYWRY_OAUTH2__TOKEN_URL=https://provider.com/token

# OIDC auto-discovery
PYWRY_OAUTH2__ISSUER_URL=https://accounts.google.com
```

### TOML Configuration

```toml
[tool.pywry.oauth2]
provider = "github"
client_id = "your-id"
scopes = "read:user user:email"
use_pkce = true
token_store_backend = "memory"
```

## Provider Setup

### Google
```python
from pywry.auth import GoogleProvider
provider = GoogleProvider(client_id="...", client_secret="...")
result = app.login(provider=provider)
```

### GitHub
```python
from pywry.auth import GitHubProvider
provider = GitHubProvider(client_id="...", client_secret="...")
result = app.login(provider=provider)
```

### Microsoft (Azure AD)
```python
from pywry.auth import MicrosoftProvider
provider = MicrosoftProvider(client_id="...", tenant_id="your-tenant")
result = app.login(provider=provider)
```

### Custom OIDC
```python
from pywry.auth import GenericOIDCProvider
provider = GenericOIDCProvider(
    client_id="...",
    issuer_url="https://your-idp.com",  # Auto-discovers endpoints
)
result = app.login(provider=provider)
```

## Frontend Auth State

When authenticated, `window.__PYWRY_AUTH__` is set with `{ user_id, roles, token_type }`.

```javascript
// Check auth
window.pywry.auth.isAuthenticated()

// Get state
window.pywry.auth.getState()  // { authenticated, user_id, roles, token_type }

// React to changes
window.pywry.auth.onAuthStateChange((state) => {
    console.log('Auth changed:', state);
});
```

## Token Storage Backends

| Backend | Use Case | Persistence |
|---------|----------|-------------|
| `memory` | Development, single-process | None (lost on restart) |
| `keyring` | Native desktop apps | OS credential manager |
| `redis` | Deploy mode, multi-worker | Redis with TTL |

Install keyring support: `pip install pywry[auth]`

## Security Notes

- PKCE is enabled by default (public client best practice)
- CSRF protection via `state` parameter validation
- Tokens are never injected into HTML — passed via secure cookies or IPC
- Session cookies are `HttpOnly`, `Secure`, `SameSite=Lax`
- Background token refresh happens automatically before expiry
