# Auth Events (auth:*)

The `auth:*` namespace is used by the built-in OAuth2 authentication system.
Events flow in both directions: the frontend can request login/logout, and the
backend notifies the frontend when auth state changes (e.g. after a token
refresh or successful logout).

!!! note "Availability"
    Auth events are only active when `PYWRY_DEPLOY__AUTH_ENABLED=true` and a
    valid `PYWRY_OAUTH2__*` configuration is present. In native mode the full
    flow is handled by `app.login()` / `app.logout()` — these events apply to
    the frontend integration via `window.pywry.auth`.

## Auth Requests (JS → Python)

| Event | Payload | Description |
|-------|---------|-------------|
| `auth:login-request` | `{}` | Frontend requests a login flow (calls `window.pywry.auth.login()`). In native mode the backend opens the provider's authorization URL; in deploy mode it redirects to `/auth/login`. |
| `auth:logout-request` | `{}` | Frontend requests logout (calls `window.pywry.auth.logout()`). The backend revokes tokens, destroys the session, and emits `auth:logout` back. |

## Auth Notifications (Python → JS)

| Event | Payload | Description |
|-------|---------|-------------|
| `auth:state-changed` | `{authenticated, user_id?, roles?, token_type?}` | Auth state changed (login succeeded or session expired). When `authenticated` is `false`, `window.__PYWRY_AUTH__` is cleared. |
| `auth:token-refresh` | `{token_type, expires_in?}` | Access token was refreshed in the background. Updates the current session without requiring re-login. |
| `auth:logout` | `{}` | Server-side logout completed. Clears `window.__PYWRY_AUTH__` and notifies registered `onAuthStateChange` handlers. |

**`auth:state-changed` payload detail:**

```python
{
    "authenticated": True,
    "user_id": "user@example.com",   # sub / id / email from userinfo
    "roles": ["viewer", "editor"],   # from session roles list
    "token_type": "Bearer"           # OAuth2 token type
}
```

When `authenticated` is `false` only the key itself is present:

```python
{"authenticated": False}
```
