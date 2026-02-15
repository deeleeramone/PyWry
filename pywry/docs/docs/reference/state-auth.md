# pywry.state.auth

Authentication, session management, and role-based access control (RBAC).

---

## Configuration

::: pywry.state.auth.AuthConfig
    options:
      show_root_heading: true
      heading_level: 2

---

## Session Tokens

::: pywry.state.auth.generate_session_token
    options:
      show_root_heading: true
      heading_level: 2

::: pywry.state.auth.validate_session_token
    options:
      show_root_heading: true
      heading_level: 2

---

## Widget Tokens

::: pywry.state.auth.generate_widget_token
    options:
      show_root_heading: true
      heading_level: 2

::: pywry.state.auth.validate_widget_token
    options:
      show_root_heading: true
      heading_level: 2

---

## RBAC

::: pywry.state.auth.get_role_permissions
    options:
      show_root_heading: true
      heading_level: 2

::: pywry.state.auth.has_permission
    options:
      show_root_heading: true
      heading_level: 2

::: pywry.state.auth.is_admin
    options:
      show_root_heading: true
      heading_level: 2

---

## Middleware

::: pywry.state.auth.AuthMiddleware
    options:
      show_root_heading: true
      heading_level: 2
      members_order: source
