"""Abstract base for TradingView datafeed providers.

Any class that implements :class:`DatafeedProvider` can be passed to
:pymethod:`TVChartStateMixin._wire_datafeed_provider` (or directly to
``show_tvchart(provider=...)``) and all IPC event wiring happens
automatically — no per-adapter boilerplate needed.
"""

from __future__ import annotations

import time as _time

from abc import ABC, abstractmethod
from typing import Any


class DatafeedProvider(ABC):
    """Interface that every TradingView datafeed adapter must implement.

    Subclasses must implement four required methods and may override
    optional methods for marks, timescale marks, server time, and
    real-time subscriptions.

    Required Methods
    ----------------
    get_config
        Return the datafeed configuration dict.
    search_symbols
        Search for symbols matching a query string.
    resolve_symbol
        Resolve a symbol name to full symbol metadata.
    get_bars
        Fetch historical OHLCV bars for a symbol and resolution.

    Optional Methods
    ----------------
    get_marks
        Return chart marks (default: empty list).
    get_timescale_marks
        Return timescale marks (default: empty list).
    get_server_time
        Return server time as Unix seconds (default: local clock).
    on_subscribe
        Called when the chart subscribes to real-time bar updates.
    on_unsubscribe
        Called when the chart unsubscribes from bar updates.
    close
        Release resources held by the provider.

    Feature Flags
    -------------
    Set these properties to ``True`` to enable optional handler wiring:
    ``supports_marks``, ``supports_timescale_marks``, ``supports_time``,
    ``supports_search``.
    """

    # ------------------------------------------------------------------
    # Required — subclasses must implement
    # ------------------------------------------------------------------

    @abstractmethod
    async def get_config(self) -> dict[str, Any]:
        """Return the datafeed configuration (``onReady`` response).

        Returns
        -------
        dict
            Keys such as ``supported_resolutions``, ``exchanges``,
            ``symbols_types``, ``supports_marks``, etc.
        """

    @abstractmethod
    async def search_symbols(
        self,
        query: str,
        symbol_type: str = "",
        exchange: str = "",
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        """Search for symbols matching *query*.

        Parameters
        ----------
        query : str
            User-entered search text.
        symbol_type : str
            Filter by symbol type (e.g. ``"crypto"``).
        exchange : str
            Filter by exchange name.
        limit : int
            Maximum number of results to return.

        Returns
        -------
        list[dict]
            Each dict should have ``symbol``, ``full_name``,
            ``description``, ``exchange``, ``type`` keys.
        """

    @abstractmethod
    async def resolve_symbol(self, symbol: str) -> dict[str, Any]:
        """Resolve a symbol name to full symbol metadata.

        Parameters
        ----------
        symbol : str
            Symbol name or ticker to resolve.

        Returns
        -------
        dict
            A ``TVChartSymbolInfo``-compatible dict.
        """

    @abstractmethod
    async def get_bars(
        self,
        symbol: str,
        resolution: str,
        from_ts: int,
        to_ts: int,
        countback: int | None = None,
    ) -> dict[str, Any]:
        """Fetch historical OHLCV bars.

        Parameters
        ----------
        symbol : str
            Symbol name or ticker.
        resolution : str
            Bar resolution (e.g. ``"1"``, ``"60"``, ``"D"``, ``"W"``).
        from_ts : int
            Start of requested range (Unix epoch seconds).
        to_ts : int
            End of requested range (Unix epoch seconds).
        countback : int or None
            Number of bars to return (optional, used by some servers).

        Returns
        -------
        dict
            Must include ``bars`` (list[dict]), ``status`` (``"ok"``
            | ``"no_data"`` | ``"error"``).  May include ``no_data``
            (bool), ``next_time`` (int), ``error`` (str).
        """

    # ------------------------------------------------------------------
    # Optional — override when the server supports these
    # ------------------------------------------------------------------

    async def get_marks(
        self,
        symbol: str,
        from_ts: int,
        to_ts: int,
        resolution: str,
    ) -> list[dict[str, Any]]:
        """Return chart marks (default: empty)."""
        return []

    async def get_timescale_marks(
        self,
        symbol: str,
        from_ts: int,
        to_ts: int,
        resolution: str,
    ) -> list[dict[str, Any]]:
        """Return timescale marks (default: empty)."""
        return []

    async def get_server_time(self) -> int:
        """Return server time as unix seconds (default: local clock)."""
        return int(_time.time())

    def on_subscribe(  # noqa: B027
        self,
        listener_guid: str,
        symbol: str,
        resolution: str,
        chart_id: str | None = None,
    ) -> None:
        """Called when the chart subscribes to real-time bar updates."""

    def on_unsubscribe(self, listener_guid: str) -> None:  # noqa: B027
        """Called when the chart unsubscribes from bar updates."""

    def close(self) -> None:  # noqa: B027
        """Release resources held by the provider."""

    # ------------------------------------------------------------------
    # Feature-flag properties
    # ------------------------------------------------------------------

    @property
    def supports_marks(self) -> bool:
        """Whether this provider supplies chart marks."""
        return False

    @property
    def supports_timescale_marks(self) -> bool:
        """Whether this provider supplies timescale marks."""
        return False

    @property
    def supports_time(self) -> bool:
        """Whether this provider supplies a server-time endpoint."""
        return False

    @property
    def supports_search(self) -> bool:
        """Whether this provider supports symbol search."""
        return True
