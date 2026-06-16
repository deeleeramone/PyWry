"""Unit tests for the PKCE (RFC 7636) implementation."""

from __future__ import annotations

import hashlib
import re

from base64 import urlsafe_b64encode

import pytest

from pywry.auth.pkce import PKCEChallenge


class TestPKCEChallenge:
    """Tests for PKCEChallenge generation."""

    def test_generate_returns_challenge(self) -> None:
        """PKCEChallenge.generate() returns a valid challenge pair."""
        pkce = PKCEChallenge.generate()
        assert pkce.verifier
        assert pkce.challenge
        assert pkce.method == "S256"

    def test_verifier_is_url_safe(self) -> None:
        """Verifier contains only URL-safe characters."""
        pkce = PKCEChallenge.generate()
        # URL-safe base64 chars: A-Z, a-z, 0-9, -, _
        assert re.match(r"^[A-Za-z0-9_-]+$", pkce.verifier)

    def test_challenge_matches_verifier_sha256(self) -> None:
        """Challenge is the base64url SHA-256 of the verifier."""
        pkce = PKCEChallenge.generate()
        expected_digest = hashlib.sha256(pkce.verifier.encode("ascii")).digest()
        expected_challenge = urlsafe_b64encode(expected_digest).rstrip(b"=").decode("ascii")
        assert pkce.challenge == expected_challenge

    def test_generate_uniqueness(self) -> None:
        """Each generation produces unique values."""
        a = PKCEChallenge.generate()
        b = PKCEChallenge.generate()
        assert a.verifier != b.verifier
        assert a.challenge != b.challenge

    def test_generate_custom_length(self) -> None:
        """Custom length produces different sized verifiers."""
        short = PKCEChallenge.generate(length=32)
        long = PKCEChallenge.generate(length=96)
        # Longer length should generally produce longer verifier
        assert len(short.verifier) < len(long.verifier)

    def test_frozen_dataclass(self) -> None:
        """PKCEChallenge is immutable."""
        pkce = PKCEChallenge.generate()
        with pytest.raises(AttributeError):
            pkce.verifier = "new"  # type: ignore
