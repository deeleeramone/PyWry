"""RBAC permission mappings for ACP operations.

Maps each ACP operation to the minimum permission level required on the
widget resource. Integrates with the existing ``check_widget_permission``
infrastructure in ``pywry.state.auth``.
"""

from __future__ import annotations

from typing import Any


ACP_PERMISSION_MAP: dict[str, str] = {
    # Session lifecycle
    "session/new": "write",
    "session/load": "write",
    "session/prompt": "write",
    "session/cancel": "write",
    "session/set_config_option": "write",
    "session/set_mode": "write",
    # Tool permission approval
    "session/request_permission": "write",
    # File system (agent → client)
    "fs/read_text_file": "read",
    "fs/write_text_file": "admin",
    # Terminal (agent → client)
    "terminal/create": "admin",
    "terminal/output": "admin",
    "terminal/kill": "admin",
    "terminal/wait_for_exit": "admin",
    "terminal/release": "admin",
}
"""Maps ACP operation names to required RBAC permission levels.

Operations not listed here default to ``"admin"`` as a safe fallback.
"""


async def check_acp_permission(
    user_session: Any,
    widget_id: str,
    operation: str,
    session_store: Any,
) -> bool:
    """Check RBAC permission for an ACP operation.

    Parameters
    ----------
    user_session : UserSession | None
        Current user session. ``None`` means auth is disabled — all
        operations are permitted.
    widget_id : str
        Widget scope for the permission check.
    operation : str
        ACP operation name (e.g. ``"session/prompt"``).
    session_store : SessionStore
        Store for permission lookups.

    Returns
    -------
    bool
        Whether the operation is permitted.
    """
    if user_session is None:
        return True

    permission = ACP_PERMISSION_MAP.get(operation, "admin")

    try:
        from ..state.auth import check_widget_permission

        return await check_widget_permission(
            user_session,
            widget_id,
            permission,
            session_store,
        )
    except ImportError:
        # Auth module not available — allow all
        return True
