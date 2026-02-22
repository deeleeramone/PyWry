"""PKCE (Proof Key for Code Exchange) implementation.

RFC 7636 - Proof Key for Code Exchange for OAuth 2.0 public clients.
Uses S256 challenge method (SHA-256 hash of the code verifier).
"""

from __future__ import annotations

import hashlib
import secrets

from base64 import urlsafe_b64encode
from dataclasses import dataclass


@dataclass(frozen=True)
class PKCEChallenge:
    """PKCE code verifier and challenge pair.

    Attributes
    ----------
    verifier : str
        The code verifier (high-entropy random string).
    challenge : str
        The code challenge (base64url-encoded SHA-256 hash of verifier).
    method : str
        The challenge method, always "S256".
    """

    verifier: str
    challenge: str
    method: str = "S256"

    @classmethod
    def generate(cls, length: int = 64) -> PKCEChallenge:
        """Generate a new PKCE code verifier and challenge.

        Parameters
        ----------
        length : int
            Number of bytes for the random verifier (default 64).
            RFC 7636 recommends at least 32 bytes.

        Returns
        -------
        PKCEChallenge
            A new PKCE challenge pair.
        """
        verifier = secrets.token_urlsafe(length)
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        challenge = urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        return cls(verifier=verifier, challenge=challenge)
