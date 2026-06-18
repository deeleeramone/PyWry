"""Tests for the OpenAI chat provider.

Source: ``pywry/chat/providers/openai.py``.
"""

from __future__ import annotations

import asyncio
import builtins
import sys

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from pywry.chat.models import GenerationCancelledError, TextPart
from pywry.chat.session import ClientCapabilities


# =============================================================================
# OpenAI client surrogate
# =============================================================================


class _FakeOaiDelta:
    def __init__(self, content: str):
        self.content = content


class _FakeOaiChoice:
    def __init__(self, content: str | None):
        self.delta = _FakeOaiDelta(content) if content is not None else None


class _FakeOaiChunk:
    def __init__(self, content: str | None = None, no_choices: bool = False):
        self.choices = [] if no_choices else [_FakeOaiChoice(content)]


class _FakeOaiResponse:
    """Simulates the OpenAI streaming response object with ``.response.aclose()``."""

    def __init__(self, chunks: list[Any]):
        self._chunks = chunks
        self.response = MagicMock()
        self.response.aclose = AsyncMock()

    def __aiter__(self):
        async def _gen():
            for c in self._chunks:
                yield c

        return _gen()


def _make_openai_client(chunks: list[Any]) -> MagicMock:
    client = MagicMock()
    response = _FakeOaiResponse(chunks)
    client.chat.completions.create = AsyncMock(return_value=response)
    return client


@pytest.fixture
def openai_module(monkeypatch):
    """Install a fake ``openai`` module whose AsyncOpenAI returns an empty
    MagicMock — for tests that don't drive the client."""
    fake_module = MagicMock()
    fake_module.AsyncOpenAI = lambda **_kwargs: MagicMock()
    monkeypatch.setitem(sys.modules, "openai", fake_module)
    return fake_module


# =============================================================================
# Tests
# =============================================================================


class TestOpenAIProvider:
    def test_import_error_when_openai_missing(self, monkeypatch):
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "openai":
                raise ImportError("no openai")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        from pywry.chat.providers.openai import OpenAIProvider

        with pytest.raises(ImportError, match="pywry\\[openai\\]"):
            OpenAIProvider(api_key="x")

    def test_constructor_creates_client(self, monkeypatch):
        fake_client = MagicMock()
        fake_module = MagicMock()
        fake_module.AsyncOpenAI = lambda **_kwargs: fake_client
        monkeypatch.setitem(sys.modules, "openai", fake_module)
        from pywry.chat.providers.openai import OpenAIProvider

        provider = OpenAIProvider(api_key="sk-test")
        assert provider._client is fake_client

    async def test_initialize_returns_image_capabilities(self, openai_module):
        from pywry.chat.providers.openai import OpenAIProvider

        provider = OpenAIProvider()
        caps = await provider.initialize(ClientCapabilities())
        assert caps.prompt_capabilities is not None
        assert caps.prompt_capabilities.image is True

    async def test_new_session_returns_id_with_prefix(self, openai_module):
        from pywry.chat.providers.openai import OpenAIProvider

        provider = OpenAIProvider()
        sid = await provider.new_session("/tmp")
        assert sid.startswith("oai_")
        assert provider._sessions[sid]["model"] == "gpt-4"

    async def test_prompt_streams_chunks(self, monkeypatch):
        client = _make_openai_client(
            [_FakeOaiChunk("Hello"), _FakeOaiChunk(" world"), _FakeOaiChunk(None)]
        )
        fake_module = MagicMock()
        fake_module.AsyncOpenAI = lambda **_kwargs: client
        monkeypatch.setitem(sys.modules, "openai", fake_module)
        from pywry.chat.providers.openai import OpenAIProvider

        provider = OpenAIProvider()
        sid = await provider.new_session("/tmp")
        updates = []
        async for u in provider.prompt(sid, [TextPart(text="hi")]):
            updates.append(u)
        # Only chunks with content yield updates
        assert [u.text for u in updates] == ["Hello", " world"]

    async def test_prompt_skips_chunks_without_choices(self, monkeypatch):
        client = _make_openai_client([_FakeOaiChunk(no_choices=True), _FakeOaiChunk("ok")])
        fake_module = MagicMock()
        fake_module.AsyncOpenAI = lambda **_kwargs: client
        monkeypatch.setitem(sys.modules, "openai", fake_module)
        from pywry.chat.providers.openai import OpenAIProvider

        provider = OpenAIProvider()
        sid = await provider.new_session("/tmp")
        updates = []
        async for u in provider.prompt(sid, [TextPart(text="hi")]):
            updates.append(u)
        assert [u.text for u in updates] == ["ok"]

    async def test_prompt_with_system_prompt_added_to_messages(self, monkeypatch):
        captured: dict = {}

        async def _create(**kwargs):
            captured.update(kwargs)
            return _FakeOaiResponse([_FakeOaiChunk("ok")])

        client = MagicMock()
        client.chat.completions.create = _create
        fake_module = MagicMock()
        fake_module.AsyncOpenAI = lambda **_kwargs: client
        monkeypatch.setitem(sys.modules, "openai", fake_module)
        from pywry.chat.providers.openai import OpenAIProvider

        provider = OpenAIProvider()
        sid = await provider.new_session("/tmp")
        provider._sessions[sid]["system_prompt"] = "You are X."

        async for _ in provider.prompt(sid, [TextPart(text="hi")]):
            pass
        msgs = captured["messages"]
        assert msgs[0]["role"] == "system"
        assert msgs[0]["content"] == "You are X."
        assert msgs[1]["role"] == "user"

    async def test_prompt_cancel_event(self, monkeypatch):
        client = _make_openai_client([_FakeOaiChunk("a"), _FakeOaiChunk("b")])
        fake_module = MagicMock()
        fake_module.AsyncOpenAI = lambda **_kwargs: client
        monkeypatch.setitem(sys.modules, "openai", fake_module)
        from pywry.chat.providers.openai import OpenAIProvider

        provider = OpenAIProvider()
        sid = await provider.new_session("/tmp")
        cancel = asyncio.Event()
        cancel.set()
        with pytest.raises(GenerationCancelledError):
            async for _ in provider.prompt(sid, [TextPart(text="hi")], cancel_event=cancel):
                pass

    async def test_cancel_is_noop(self, openai_module):
        from pywry.chat.providers.openai import OpenAIProvider

        provider = OpenAIProvider()
        assert await provider.cancel("any") is None
