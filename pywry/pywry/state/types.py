"""Type definitions for PyWry state management.

Shared types used across state store implementations.
"""

from __future__ import annotations

import time

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal


class StateBackend(str, Enum):
    """Available state storage backends."""

    MEMORY = "memory"
    REDIS = "redis"


@dataclass
class WidgetData:
    """Widget data stored in the state store.

    Attributes
    ----------
    widget_id : str
        Unique identifier for the widget.
    html : str
        The HTML content of the widget.
    token : str or None
        Optional per-widget authentication token.
    created_at : float
        Unix timestamp when the widget was created.
    owner_worker_id : str or None
        ID of the worker that created/owns this widget's callbacks.
    metadata : dict[str, Any]
        Additional metadata (title, theme, etc.).
    """

    widget_id: str
    html: str
    token: str | None = None
    created_at: float = 0.0
    owner_worker_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConnectionInfo:
    """Information about a WebSocket connection.

    Attributes
    ----------
    widget_id : str
        The widget this connection is for.
    worker_id : str
        The worker ID that owns this connection.
    connected_at : float
        Unix timestamp when the connection was established.
    last_heartbeat : float
        Unix timestamp of the last heartbeat/activity.
    user_id : str or None
        Optional user ID for RBAC.
    session_id : str or None
        Optional session ID for tracking.
    """

    widget_id: str
    worker_id: str
    connected_at: float = 0.0
    last_heartbeat: float = 0.0
    user_id: str | None = None
    session_id: str | None = None


@dataclass
class EventMessage:
    """Event message for cross-worker communication.

    Attributes
    ----------
    event_type : str
        The type of event (e.g., "click", "cellValueChanged").
    widget_id : str
        The target widget ID.
    data : dict[str, Any]
        The event payload.
    source_worker_id : str
        The worker that sent this event.
    target_worker_id : str or None
        The specific worker to receive this event (None for broadcast).
    timestamp : float
        Unix timestamp when the event was created.
    message_id : str
        Unique identifier for this message.
    """

    event_type: str
    widget_id: str
    data: dict[str, Any]
    source_worker_id: str
    target_worker_id: str | None = None
    timestamp: float = 0.0
    message_id: str = ""


@dataclass
class UserSession:
    """User session information for RBAC support.

    Attributes
    ----------
    session_id : str
        Unique session identifier.
    user_id : str
        User identifier.
    roles : list[str]
        User roles for access control.
    created_at : float
        Unix timestamp when the session was created.
    expires_at : float or None
        Unix timestamp when the session expires (None for no expiry).
    metadata : dict[str, Any]
        Additional session metadata.
    """

    session_id: str
    user_id: str
    roles: list[str] = field(default_factory=list)
    created_at: float = 0.0
    expires_at: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# Type aliases for clarity
WidgetId = str
WorkerId = str
SessionId = str
UserId = str
EventType = str
CallbackResult = Any

# Access control permission types
Permission = Literal["read", "write", "admin"]
ResourceType = Literal["widget", "session", "user", "system"]


@dataclass
class OAuthTokenSet:
    """OAuth2 token set returned by a provider.

    Attributes
    ----------
    access_token : str
        The access token for API requests.
    token_type : str
        Token type, typically "Bearer".
    refresh_token : str or None
        Optional refresh token for obtaining new access tokens.
    expires_in : int or None
        Token lifetime in seconds from issuance.
    id_token : str or None
        Optional OIDC ID token (JWT).
    scope : str
        Space-separated list of granted scopes.
    raw : dict[str, Any]
        The raw token response from the provider.
    issued_at : float
        Unix timestamp when the token was issued.
    """

    access_token: str
    token_type: str = "Bearer"  # noqa: S105
    refresh_token: str | None = None
    expires_in: int | None = None
    id_token: str | None = None
    scope: str = ""
    raw: dict[str, Any] = field(default_factory=dict)
    issued_at: float = field(default_factory=time.time)

    @property
    def is_expired(self) -> bool:
        """Check if the access token has expired."""
        if self.expires_in is None:
            return False
        return time.time() > (self.issued_at + self.expires_in)

    @property
    def expires_at(self) -> float | None:
        """Get the expiry timestamp, or None if no expiry."""
        if self.expires_in is None:
            return None
        return self.issued_at + self.expires_in


@dataclass
class AuthFlowResult:
    """Result of an OAuth2 authentication flow.

    Attributes
    ----------
    success : bool
        Whether authentication completed successfully.
    tokens : OAuthTokenSet or None
        The token set if authentication succeeded.
    error : str or None
        Error message if authentication failed.
    user_info : dict[str, Any] or None
        User profile information from the provider.
    """

    success: bool
    tokens: OAuthTokenSet | None = None
    error: str | None = None
    user_info: dict[str, Any] | None = None


class AuthFlowState(str, Enum):
    """State of an OAuth2 authentication flow."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
