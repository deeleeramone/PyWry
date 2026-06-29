"""Tests for the callback chat provider.

Source: ``pywry/chat/providers/callback.py``.

The callback provider takes a user-supplied function and adapts its return
value (sync/async, str/iterable/SessionUpdate) into the ACP streaming
shape.  Tests cover every return-value shape.
"""

from __future__ import annotations

import asyncio

import pytest

from pywry.chat.models import GenerationCancelledError, TextPart
from pywry.chat.providers.callback import CallbackProvider
from pywry.chat.session import ClientCapabilities
from pywry.chat.updates import AgentMessageUpdate


@pytest.fixture
async def empty_provider():
    """Provider with no prompt_fn — yields the default 'no callback' message."""
    provider = CallbackProvider()
    sid = await provider.new_session("/tmp")
    return provider, sid


class TestCallbackProvider:
    async def test_initialize_returns_default_caps(self):
        provider = CallbackProvider()
        caps = await provider.initialize(ClientCapabilities())
        assert caps.prompt_capabilities is None

    async def test_new_session_returns_id_with_prefix(self):
        provider = CallbackProvider()
        sid = await provider.new_session("/tmp")
        assert sid.startswith("cb_")

    async def test_no_callback_returns_default_message(self, empty_provider):
        provider, sid = empty_provider
        updates = []
        async for u in provider.prompt(sid, [TextPart(text="hi")]):
            updates.append(u)
        assert len(updates) == 1
        assert "No prompt callback configured." in updates[0].text

    async def test_sync_str_callback(self):
        def fn(_sid, _content, _cancel):
            return "hello-world"

        provider = CallbackProvider(prompt_fn=fn)
        sid = await provider.new_session("/tmp")
        updates = []
        async for u in provider.prompt(sid, [TextPart(text="hi")]):
            updates.append(u)
        assert len(updates) == 1
        assert updates[0].text == "hello-world"

    async def test_async_str_callback(self):
        async def fn(_sid, _content, _cancel):
            return "async-result"

        provider = CallbackProvider(prompt_fn=fn)
        sid = await provider.new_session("/tmp")
        updates = []
        async for u in provider.prompt(sid, [TextPart(text="hi")]):
            updates.append(u)
        assert updates[0].text == "async-result"

    async def test_sync_generator_callback(self):
        def fn(_sid, _content, _cancel):
            yield "a"
            yield "b"

        provider = CallbackProvider(prompt_fn=fn)
        sid = await provider.new_session("/tmp")
        updates = []
        async for u in provider.prompt(sid, [TextPart(text="hi")]):
            updates.append(u)
        assert [u.text for u in updates] == ["a", "b"]

    async def test_async_generator_callback(self):
        async def fn(_sid, _content, _cancel):
            for x in ["x", "y"]:
                yield x

        provider = CallbackProvider(prompt_fn=fn)
        sid = await provider.new_session("/tmp")
        updates = []
        async for u in provider.prompt(sid, [TextPart(text="hi")]):
            updates.append(u)
        assert [u.text for u in updates] == ["x", "y"]

    async def test_callback_yielding_session_updates(self):
        def fn(_sid, _content, _cancel):
            yield AgentMessageUpdate(text="from-update")

        provider = CallbackProvider(prompt_fn=fn)
        sid = await provider.new_session("/tmp")
        updates = []
        async for u in provider.prompt(sid, [TextPart(text="hi")]):
            updates.append(u)
        assert isinstance(updates[0], AgentMessageUpdate)
        assert updates[0].text == "from-update"

    async def test_non_string_non_iterable_result_stringified(self):
        def fn(_sid, _content, _cancel):
            return 42  # type: ignore[return-value]

        provider = CallbackProvider(prompt_fn=fn)
        sid = await provider.new_session("/tmp")
        updates = []
        async for u in provider.prompt(sid, [TextPart(text="hi")]):
            updates.append(u)
        assert updates[0].text == "42"

    async def test_iterable_object_with_aiter(self):
        class _AIter:
            def __init__(self, items):
                self._items = items

            def __aiter__(self):
                async def _gen():
                    for x in self._items:
                        yield x

                return _gen()

        def fn(_sid, _content, _cancel):
            return _AIter(["a", "b"])

        provider = CallbackProvider(prompt_fn=fn)
        sid = await provider.new_session("/tmp")
        updates = []
        async for u in provider.prompt(sid, [TextPart(text="hi")]):
            updates.append(u)
        assert [u.text for u in updates] == ["a", "b"]

    async def test_iterable_object_sync(self):
        def fn(_sid, _content, _cancel):
            return iter(["c", "d"])

        provider = CallbackProvider(prompt_fn=fn)
        sid = await provider.new_session("/tmp")
        updates = []
        async for u in provider.prompt(sid, [TextPart(text="hi")]):
            updates.append(u)
        assert [u.text for u in updates] == ["c", "d"]

    async def test_async_generator_cancel_raises(self):
        async def fn(_sid, _content, _cancel):
            for x in range(10):
                yield str(x)

        provider = CallbackProvider(prompt_fn=fn)
        sid = await provider.new_session("/tmp")
        cancel = asyncio.Event()
        cancel.set()
        with pytest.raises(GenerationCancelledError):
            async for _ in provider.prompt(sid, [TextPart(text="hi")], cancel_event=cancel):
                pass

    async def test_sync_generator_cancel_raises(self):
        def fn(_sid, _content, _cancel):
            yield "a"
            yield "b"

        provider = CallbackProvider(prompt_fn=fn)
        sid = await provider.new_session("/tmp")
        cancel = asyncio.Event()
        cancel.set()
        with pytest.raises(GenerationCancelledError):
            async for _ in provider.prompt(sid, [TextPart(text="hi")], cancel_event=cancel):
                pass

    async def test_cancel_is_noop(self):
        provider = CallbackProvider()
        assert await provider.cancel("any") is None
