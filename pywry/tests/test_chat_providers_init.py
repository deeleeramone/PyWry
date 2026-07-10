"""Tests for the ChatProvider ABC and ``get_provider`` factory.

Source: ``pywry/chat/providers/__init__.py``.
"""

from __future__ import annotations

import pytest

from pywry.chat.providers import ChatProvider, get_provider


# =============================================================================
# ABC default implementations
# =============================================================================


class _MinProvider(ChatProvider):
    """Concrete provider implementing only the abstract methods so the
    ABC's default helpers can be exercised."""

    async def initialize(self, capabilities):  # type: ignore[override]
        from pywry.chat.session import AgentCapabilities

        return AgentCapabilities()

    async def new_session(self, cwd, mcp_servers=None):  # type: ignore[override]
        return "min_session"

    async def prompt(self, session_id, content, cancel_event=None):  # type: ignore[override]
        if False:
            yield None  # pragma: no cover

    async def cancel(self, session_id):  # type: ignore[override]
        return None


class TestChatProviderDefaults:
    async def test_load_session_default_raises_not_implemented(self):
        provider = _MinProvider()
        with pytest.raises(NotImplementedError, match="does not support session loading"):
            await provider.load_session("sid", "/cwd")

    async def test_set_config_option_default_returns_empty_list(self):
        provider = _MinProvider()
        assert await provider.set_config_option("sid", "k", "v") == []

    async def test_set_mode_default_returns_none(self):
        provider = _MinProvider()
        assert await provider.set_mode("sid", "mode_x") is None

    async def test_abstract_prompt_body_raises_not_implemented(self):
        """The ``prompt`` ABC body is reachable when a subclass calls
        ``super().prompt(...)``."""

        class _SubCallingSuper(ChatProvider):
            async def initialize(self, _caps):
                from pywry.chat.session import AgentCapabilities

                return AgentCapabilities()

            async def new_session(self, _cwd, mcp_servers=None):
                return "x"

            def prompt(self, sid, content, cancel_event=None):
                return ChatProvider.prompt(self, sid, content, cancel_event)

            async def cancel(self, _sid):
                return None

        provider = _SubCallingSuper()
        with pytest.raises(NotImplementedError):
            provider.prompt("sid", [])


# =============================================================================
# get_provider factory
# =============================================================================


class TestGetProviderFactory:
    def test_unknown_provider_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            get_provider("nonexistent")

    def test_unknown_provider_lists_available(self):
        with pytest.raises(ValueError, match="openai|anthropic|callback|magentic|stdio"):
            get_provider("totally-bogus")

    def test_known_provider_callback(self):
        from pywry.chat.providers.callback import CallbackProvider

        assert isinstance(get_provider("callback"), CallbackProvider)

    def test_known_provider_callback_with_kwargs(self):
        from pywry.chat.providers.callback import CallbackProvider

        def fn(_sid, _content, _cancel):
            yield "hi"

        assert isinstance(get_provider("callback", prompt_fn=fn), CallbackProvider)
