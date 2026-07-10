"""Tests for ``pywry/tvchart/datafeed.py``.

The :class:`DatafeedProvider` abstract base class supplies default
implementations for the optional hooks (``get_marks``,
``get_timescale_marks``, ``get_server_time``, ``on_subscribe``,
``on_unsubscribe``, ``close``) and feature-flag properties.  These
defaults are what subclasses inherit when they only implement the four
required abstract methods, so they must behave as documented.
"""

from __future__ import annotations

import time as _time

from typing import Any

import pytest

from pywry.tvchart.datafeed import DatafeedProvider


class _MinimalDatafeedProvider(DatafeedProvider):
    """Bare-bones provider that only implements the required abstract methods."""

    async def get_config(self) -> dict[str, Any]:
        return {}

    async def search_symbols(
        self,
        query: str,
        symbol_type: str = "",
        exchange: str = "",
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        return []

    async def resolve_symbol(self, symbol: str) -> dict[str, Any]:
        return {"name": symbol}

    async def get_bars(
        self,
        symbol: str,
        resolution: str,
        from_ts: int,
        to_ts: int,
        countback: int | None = None,
    ) -> dict[str, Any]:
        return {"bars": [], "status": "ok"}


@pytest.fixture()
def provider() -> _MinimalDatafeedProvider:
    return _MinimalDatafeedProvider()


# =============================================================================
# Required abstract methods on the minimal subclass
# =============================================================================


class TestRequiredMethodsAreCalled:
    """Sanity-check that a minimal subclass actually returns its values."""

    async def test_get_config_returns_empty_dict(self, provider: _MinimalDatafeedProvider) -> None:
        assert await provider.get_config() == {}

    async def test_search_returns_empty_list(self, provider: _MinimalDatafeedProvider) -> None:
        assert await provider.search_symbols("AAPL") == []

    async def test_resolve_echoes_symbol(self, provider: _MinimalDatafeedProvider) -> None:
        info = await provider.resolve_symbol("AAPL")
        assert info == {"name": "AAPL"}

    async def test_get_bars_returns_ok_empty(self, provider: _MinimalDatafeedProvider) -> None:
        result = await provider.get_bars("AAPL", "1D", 0, 1_700_000_000)
        assert result == {"bars": [], "status": "ok"}


# =============================================================================
# Default optional method behaviour
# =============================================================================


class TestOptionalDefaults:
    """The optional methods have no-op defaults — verify the documented values."""

    async def test_get_marks_default_empty(self, provider: _MinimalDatafeedProvider) -> None:
        assert await provider.get_marks("AAPL", 0, 100, "D") == []

    async def test_get_timescale_marks_default_empty(
        self, provider: _MinimalDatafeedProvider
    ) -> None:
        assert await provider.get_timescale_marks("AAPL", 0, 100, "D") == []

    async def test_get_server_time_returns_current_time(
        self, provider: _MinimalDatafeedProvider
    ) -> None:
        before = int(_time.time())
        ts = await provider.get_server_time()
        after = int(_time.time())
        assert isinstance(ts, int)
        assert before <= ts <= after

    def test_on_subscribe_is_noop(self, provider: _MinimalDatafeedProvider) -> None:
        # Default impl just returns None and doesn't raise.
        assert (
            provider.on_subscribe(listener_guid="g1", symbol="AAPL", resolution="D", chart_id=None)
            is None
        )

    def test_on_unsubscribe_is_noop(self, provider: _MinimalDatafeedProvider) -> None:
        assert provider.on_unsubscribe("g1") is None

    def test_close_is_noop(self, provider: _MinimalDatafeedProvider) -> None:
        assert provider.close() is None


class TestFeatureFlagDefaults:
    """The base class's feature flags advertise capabilities to the wiring code."""

    def test_supports_marks_default_false(self, provider: _MinimalDatafeedProvider) -> None:
        assert provider.supports_marks is False

    def test_supports_timescale_marks_default_false(
        self, provider: _MinimalDatafeedProvider
    ) -> None:
        assert provider.supports_timescale_marks is False

    def test_supports_time_default_false(self, provider: _MinimalDatafeedProvider) -> None:
        assert provider.supports_time is False

    def test_supports_search_default_true(self, provider: _MinimalDatafeedProvider) -> None:
        # Search is the most common UDF capability, so it defaults on.
        assert provider.supports_search is True


# =============================================================================
# Subclasses can override the feature flags
# =============================================================================


class TestSubclassOverridesFlags:
    """Subclasses set flags by overriding the property."""

    def test_override_supports_marks(self) -> None:
        class _WithMarks(_MinimalDatafeedProvider):
            @property
            def supports_marks(self) -> bool:
                return True

        assert _WithMarks().supports_marks is True

    def test_override_supports_time(self) -> None:
        class _WithTime(_MinimalDatafeedProvider):
            @property
            def supports_time(self) -> bool:
                return True

        assert _WithTime().supports_time is True


# =============================================================================
# Abstract-method enforcement
# =============================================================================


class TestAbstractMethodEnforcement:
    """You cannot instantiate :class:`DatafeedProvider` directly — Python's
    ABCMeta protects all four abstract methods."""

    def test_cannot_instantiate_directly(self) -> None:
        with pytest.raises(TypeError, match="abstract"):
            DatafeedProvider()  # type: ignore[abstract]
