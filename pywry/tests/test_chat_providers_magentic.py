"""Tests for the Magentic chat provider.

Source: ``pywry/chat/providers/magentic.py``.

Mocks the entire ``magentic`` module hierarchy via ``sys.modules`` so the
provider can be tested without installing the package.
"""

from __future__ import annotations

import asyncio
import builtins
import sys

from unittest.mock import MagicMock

import pytest

from pywry.chat.models import GenerationCancelledError, TextPart
from pywry.chat.session import ClientCapabilities


# =============================================================================
# Magentic module surrogate
# =============================================================================


def _install_fake_magentic(monkeypatch, *, chat_chunks=None):
    """Install a fake ``magentic`` module hierarchy into sys.modules."""

    class _FakeChatModel:
        """Stand-in for ``magentic.chat_model.base.ChatModel``."""

    class _FakeOpenaiChatModel(_FakeChatModel):
        def __init__(self, model_name, **_kwargs):
            self.model_name = model_name

    class _AsyncStrIter:
        def __init__(self, items):
            self._items = items

        def __aiter__(self):
            async def _gen():
                for x in self._items:
                    yield x

            return _gen()

    class _FakeChat:
        def __init__(self, **_kwargs):
            self.last_message = MagicMock()
            self.last_message.content = _AsyncStrIter(chat_chunks or [])

        async def asubmit(self):
            return self

    fake_top = MagicMock()
    fake_top.Chat = _FakeChat
    fake_top.SystemMessage = MagicMock()
    fake_top.UserMessage = MagicMock()
    fake_top.OpenaiChatModel = _FakeOpenaiChatModel

    fake_chat_model = MagicMock()
    fake_chat_model_base = MagicMock()
    fake_chat_model_base.ChatModel = _FakeChatModel
    fake_chat_model.base = fake_chat_model_base

    fake_streaming = MagicMock()
    fake_streaming.AsyncStreamedStr = MagicMock()

    monkeypatch.setitem(sys.modules, "magentic", fake_top)
    monkeypatch.setitem(sys.modules, "magentic.chat_model", fake_chat_model)
    monkeypatch.setitem(sys.modules, "magentic.chat_model.base", fake_chat_model_base)
    monkeypatch.setitem(sys.modules, "magentic.streaming", fake_streaming)
    return _FakeChatModel


@pytest.fixture
def magentic_module(monkeypatch):
    """Install a fake magentic hierarchy with no chat chunks — for tests
    that don't drive the streaming output."""
    return _install_fake_magentic(monkeypatch)


# =============================================================================
# Tests
# =============================================================================


class TestMagenticProvider:
    def test_import_error_when_magentic_missing(self, monkeypatch):
        for mod in list(sys.modules):
            if mod == "magentic" or mod.startswith("magentic."):
                monkeypatch.delitem(sys.modules, mod, raising=False)

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "magentic" or name.startswith("magentic."):
                raise ImportError("no magentic")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        from pywry.chat.providers.magentic import MagenticProvider

        with pytest.raises(ImportError, match="pywry\\[magentic\\]"):
            MagenticProvider(model="gpt-4")

    def test_type_error_when_model_is_neither_str_nor_chatmodel(self, magentic_module):
        from pywry.chat.providers.magentic import MagenticProvider

        with pytest.raises(TypeError, match="Expected ChatModel or model name string"):
            MagenticProvider(model=12345)  # int — not a ChatModel

    def test_constructor_with_string_model(self, magentic_module):
        from pywry.chat.providers.magentic import MagenticProvider

        provider = MagenticProvider(model="gpt-4o-mini")
        assert provider._model is not None
        assert provider._sessions == {}
        # Should be a fake OpenaiChatModel instance
        assert provider._model.model_name == "gpt-4o-mini"

    def test_constructor_with_chatmodel_instance(self, monkeypatch):
        chat_model_cls = _install_fake_magentic(monkeypatch)
        from pywry.chat.providers.magentic import MagenticProvider

        stub = chat_model_cls()
        provider = MagenticProvider(model=stub)
        assert provider._model is stub

    async def test_initialize_returns_default_caps(self, magentic_module):
        from pywry.chat.providers.magentic import MagenticProvider

        provider = MagenticProvider(model="gpt-4o-mini")
        caps = await provider.initialize(ClientCapabilities())
        assert caps.prompt_capabilities is None

    async def test_new_session_returns_id_with_prefix(self, magentic_module):
        from pywry.chat.providers.magentic import MagenticProvider

        provider = MagenticProvider(model="gpt-4o-mini")
        sid = await provider.new_session("/tmp")
        assert sid.startswith("mag_")

    async def test_prompt_yields_chunks(self, monkeypatch):
        _install_fake_magentic(monkeypatch, chat_chunks=["foo", "bar"])
        from pywry.chat.providers.magentic import MagenticProvider

        provider = MagenticProvider(model="gpt-4o-mini")
        sid = await provider.new_session("/tmp")
        provider._sessions[sid]["system_prompt"] = "Be helpful."
        updates = []
        async for u in provider.prompt(sid, [TextPart(text="hi")]):
            updates.append(u)
        assert [u.text for u in updates] == ["foo", "bar"]

    async def test_prompt_yields_default_message_when_magentic_missing(self, monkeypatch):
        _install_fake_magentic(monkeypatch, chat_chunks=["x"])
        from pywry.chat.providers.magentic import MagenticProvider

        provider = MagenticProvider(model="gpt-4o-mini")
        sid = await provider.new_session("/tmp")

        # Strip magentic from sys.modules and force re-import to fail
        for mod in list(sys.modules):
            if mod == "magentic" or mod.startswith("magentic."):
                monkeypatch.delitem(sys.modules, mod, raising=False)

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "magentic" or name.startswith("magentic."):
                raise ImportError("no magentic")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        updates = []
        async for u in provider.prompt(sid, [TextPart(text="hi")]):
            updates.append(u)
        assert len(updates) == 1
        assert "magentic is not installed" in updates[0].text

    async def test_prompt_cancel_event(self, monkeypatch):
        _install_fake_magentic(monkeypatch, chat_chunks=["a", "b", "c"])
        from pywry.chat.providers.magentic import MagenticProvider

        provider = MagenticProvider(model="gpt-4o-mini")
        sid = await provider.new_session("/tmp")
        cancel = asyncio.Event()
        cancel.set()
        with pytest.raises(GenerationCancelledError):
            async for _ in provider.prompt(sid, [TextPart(text="hi")], cancel_event=cancel):
                pass

    async def test_cancel_is_noop(self, magentic_module):
        from pywry.chat.providers.magentic import MagenticProvider

        provider = MagenticProvider(model="gpt-4o-mini")
        assert await provider.cancel("any") is None
