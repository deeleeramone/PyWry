"""Tests for the Anthropic chat provider.

Source: ``pywry/chat/providers/anthropic.py``.

The Anthropic client is mocked via ``unittest.mock`` so tests run without
network or an installed ``anthropic`` package.
"""

from __future__ import annotations

import asyncio
import builtins
import sys

from unittest.mock import MagicMock

import pytest

from pywry.chat.models import GenerationCancelledError, TextPart
from pywry.chat.session import ClientCapabilities
from pywry.chat.updates import AgentMessageUpdate


# =============================================================================
# Anthropic client surrogate
# =============================================================================


class _FakeAnthStream:
    """Async-context-manager + async-iterable text stream surrogate."""

    def __init__(self, chunks: list[str]):
        self._chunks = chunks

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    @property
    def text_stream(self):
        async def _gen():
            for c in self._chunks:
                yield c

        return _gen()


def _make_anthropic_client(chunks: list[str]) -> MagicMock:
    """Build a fake AsyncAnthropic whose ``.messages.stream`` returns a context-manager."""
    client = MagicMock()
    stream_obj = _FakeAnthStream(chunks)

    def _stream(**_kwargs):
        return stream_obj

    client.messages.stream = MagicMock(side_effect=_stream)
    return client


@pytest.fixture
def anthropic_module(monkeypatch):
    """Install a fake ``anthropic`` module whose AsyncAnthropic returns an
    empty MagicMock — useful for tests that exercise paths that don't drive
    the client."""
    fake_module = MagicMock()
    fake_module.AsyncAnthropic = lambda **_kwargs: MagicMock()
    monkeypatch.setitem(sys.modules, "anthropic", fake_module)
    return fake_module


# =============================================================================
# Tests
# =============================================================================


class TestAnthropicProvider:
    def test_import_error_when_anthropic_missing(self, monkeypatch):
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "anthropic":
                raise ImportError("no anthropic")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        from pywry.chat.providers.anthropic import AnthropicProvider

        with pytest.raises(ImportError, match="pywry\\[anthropic\\]"):
            AnthropicProvider(api_key="x")

    def test_constructor_creates_client(self, monkeypatch):
        fake_client = MagicMock()
        fake_module = MagicMock()
        fake_module.AsyncAnthropic = lambda **_kwargs: fake_client
        monkeypatch.setitem(sys.modules, "anthropic", fake_module)
        from pywry.chat.providers.anthropic import AnthropicProvider

        provider = AnthropicProvider(api_key="sk-test")
        assert provider._client is fake_client
        assert provider._sessions == {}

    async def test_initialize_returns_image_capabilities(self, anthropic_module):
        from pywry.chat.providers.anthropic import AnthropicProvider

        provider = AnthropicProvider()
        caps = await provider.initialize(ClientCapabilities())
        assert caps.prompt_capabilities is not None
        assert caps.prompt_capabilities.image is True

    async def test_new_session_returns_id_with_prefix(self, anthropic_module):
        from pywry.chat.providers.anthropic import AnthropicProvider

        provider = AnthropicProvider()
        sid = await provider.new_session("/tmp")
        assert sid.startswith("ant_")
        assert provider._sessions[sid]["model"] == "claude-sonnet-4-20250514"

    async def test_prompt_yields_agent_message_updates(self, monkeypatch):
        client = _make_anthropic_client(["Hello", " world"])
        fake_module = MagicMock()
        fake_module.AsyncAnthropic = lambda **_kwargs: client
        monkeypatch.setitem(sys.modules, "anthropic", fake_module)
        from pywry.chat.providers.anthropic import AnthropicProvider

        provider = AnthropicProvider()
        sid = await provider.new_session("/tmp")
        updates = []
        async for u in provider.prompt(sid, [TextPart(text="hi")]):
            updates.append(u)
        assert [u.text for u in updates] == ["Hello", " world"]
        assert all(isinstance(u, AgentMessageUpdate) for u in updates)

    async def test_prompt_respects_cancel_event(self, monkeypatch):
        client = _make_anthropic_client(["a", "b", "c"])
        fake_module = MagicMock()
        fake_module.AsyncAnthropic = lambda **_kwargs: client
        monkeypatch.setitem(sys.modules, "anthropic", fake_module)
        from pywry.chat.providers.anthropic import AnthropicProvider

        provider = AnthropicProvider()
        sid = await provider.new_session("/tmp")
        cancel = asyncio.Event()
        cancel.set()

        with pytest.raises(GenerationCancelledError):
            async for _ in provider.prompt(sid, [TextPart(text="hi")], cancel_event=cancel):
                pass

    async def test_cancel_is_noop(self, anthropic_module):
        from pywry.chat.providers.anthropic import AnthropicProvider

        provider = AnthropicProvider()
        assert await provider.cancel("any-session") is None
