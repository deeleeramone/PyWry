"""PyWry exception hierarchy.

All PyWry-specific exceptions inherit from PyWryException, enabling
catch-all handling while supporting specific error types.
"""

from __future__ import annotations

from typing import Any


class PyWryException(Exception):
    """Base exception for all PyWry errors."""

    def __init__(self, message: str, **context: Any) -> None:
        """Initialize PyWry exception.

        Parameters
        ----------
        message : str
            Human-readable error message.
        **context : Any
            Additional context (label, method, request_id, etc.).
        """
        super().__init__(message)
        self.message = message
        self.context = context

    def __str__(self) -> str:
        """Format exception with context."""
        if self.context:
            ctx = ", ".join(f"{k}={v!r}" for k, v in self.context.items())
            return f"{self.message} ({ctx})"
        return self.message


class WindowError(PyWryException):
    """Window operation failed.

    Raised when a window is not found, already destroyed,
    or an operation cannot be performed on it.
    """

    def __init__(self, message: str, label: str | None = None, **context: Any) -> None:
        """Initialize window error.

        Parameters
        ----------
        message : str
            Human-readable error message.
        label : str, optional
            The window label that caused the error.
        **context : Any
            Additional context.
        """
        super().__init__(message, label=label, **context)
        self.label = label


class IPCError(PyWryException):
    """IPC communication failed.

    Raised when communication with the subprocess fails,
    including encoding/decoding errors and pipe failures.
    """

    def __init__(
        self,
        message: str,
        action: str | None = None,
        label: str | None = None,
        **context: Any,
    ) -> None:
        """Initialize IPC error.

        Parameters
        ----------
        message : str
            Human-readable error message.
        action : str, optional
            The IPC action that failed.
        label : str, optional
            The window label involved.
        **context : Any
            Additional context.
        """
        super().__init__(message, action=action, label=label, **context)
        self.action = action
        self.label = label


class IPCTimeoutError(IPCError):
    """IPC response timeout.

    Raised when waiting for a subprocess response exceeds
    the configured timeout.
    """

    def __init__(
        self,
        message: str,
        timeout: float,
        action: str | None = None,
        label: str | None = None,
        **context: Any,
    ) -> None:
        """Initialize timeout error.

        Parameters
        ----------
        message : str
            Human-readable error message.
        timeout : float
            The timeout value in seconds.
        action : str, optional
            The IPC action that timed out.
        label : str, optional
            The window label involved.
        **context : Any
            Additional context.
        """
        super().__init__(message, action=action, label=label, timeout=timeout, **context)
        self.timeout = timeout


class PropertyError(PyWryException):
    """Failed to get or set a window property.

    Raised when a property access or modification fails,
    typically due to the property not existing or being read-only.
    """

    def __init__(
        self,
        message: str,
        property_name: str,
        label: str | None = None,
        **context: Any,
    ) -> None:
        """Initialize property error.

        Parameters
        ----------
        message : str
            Human-readable error message.
        property_name : str
            The property that caused the error.
        label : str, optional
            The window label involved.
        **context : Any
            Additional context.
        """
        super().__init__(message, property_name=property_name, label=label, **context)
        self.property_name = property_name
        self.label = label


class SubprocessError(PyWryException):
    """Subprocess-related error.

    Raised when the pytauri subprocess fails to start,
    crashes unexpectedly, or returns an error.
    """

    def __init__(self, message: str, exit_code: int | None = None, **context: Any) -> None:
        """Initialize subprocess error.

        Parameters
        ----------
        message : str
            Human-readable error message.
        exit_code : int, optional
            The subprocess exit code if available.
        **context : Any
            Additional context.
        """
        super().__init__(message, exit_code=exit_code, **context)
        self.exit_code = exit_code


class AuthenticationError(PyWryException):
    """Base exception for all authentication failures.

    Raised when an authentication operation fails, including
    OAuth2 flows, token validation, or session management.
    """

    def __init__(
        self,
        message: str,
        provider: str | None = None,
        flow_id: str | None = None,
        **context: Any,
    ) -> None:
        """Initialize authentication error.

        Parameters
        ----------
        message : str
            Human-readable error message.
        provider : str, optional
            The OAuth2 provider name (e.g., "google", "github").
        flow_id : str, optional
            The unique identifier of the auth flow that failed.
        **context : Any
            Additional context.
        """
        super().__init__(message, provider=provider, flow_id=flow_id, **context)
        self.provider = provider
        self.flow_id = flow_id


class AuthFlowCancelled(AuthenticationError):
    """Authentication flow was cancelled.

    Raised when the user closes the authentication window
    or explicitly aborts the login flow.
    """


class AuthFlowTimeout(AuthenticationError):
    """Authentication flow timed out.

    Raised when the blocking wait for OAuth2 callback
    exceeds the configured timeout.
    """

    def __init__(
        self,
        message: str,
        timeout: float,
        provider: str | None = None,
        flow_id: str | None = None,
        **context: Any,
    ) -> None:
        """Initialize timeout error.

        Parameters
        ----------
        message : str
            Human-readable error message.
        timeout : float
            The timeout value in seconds.
        provider : str, optional
            The OAuth2 provider name.
        flow_id : str, optional
            The unique identifier of the auth flow.
        **context : Any
            Additional context.
        """
        super().__init__(message, provider=provider, flow_id=flow_id, timeout=timeout, **context)
        self.timeout = timeout


class TokenError(AuthenticationError):
    """Base exception for token-related failures.

    Raised when token operations (validation, refresh, exchange) fail.
    """


class TokenExpiredError(TokenError):
    """Token has expired.

    Raised when an access or refresh token is past its expiry time.
    """


class TokenRefreshError(TokenError):
    """Token refresh failed.

    Raised when attempting to refresh an expired access token
    using a refresh token fails.
    """
