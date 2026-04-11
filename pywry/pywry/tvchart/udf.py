"""UDF (Universal Datafeed) adapter for TradingView charts.

Connects a PyWry TradingView chart to any UDF-compatible HTTP server.
The developer provides a base URL and optional auth headers; the adapter
auto-discovers the server's capabilities via ``GET /config`` and wires
every datafeed event to the corresponding UDF endpoint.

Supported UDF endpoints:

- ``GET /config`` — Datafeed configuration (onReady)
- ``GET /search`` — Symbol search
- ``GET /symbols`` — Symbol resolve
- ``GET /history`` — Historical bars (getBars)
- ``GET /marks`` — Chart marks
- ``GET /timescale_marks`` — Timescale marks
- ``GET /time`` — Server time
- ``GET /quotes`` — Real-time quote snapshots

Usage::

    from pywry import PyWry, ThemeMode
    from pywry.tvchart.udf import UDFAdapter

    app = PyWry(theme=ThemeMode.DARK, title="UDF Chart")
    udf = UDFAdapter("https://demo-feed-data.tradingview.com")
    udf.connect(app, symbol="AAPL", resolution="D")
    app.block()
"""

from __future__ import annotations

import contextlib
import logging
import threading

from typing import TYPE_CHECKING, Any

import httpx

from .datafeed import DatafeedProvider


if TYPE_CHECKING:
    from ..app import PyWry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Resolution mapping: PyWry canonical ↔ UDF wire format
# ---------------------------------------------------------------------------

# UDF uses "1", "5", "60", "D", "W", "M" etc.
# PyWry internally uses "1m", "5m", "1h", "1d", "1w", "1M" etc.
_CANONICAL_TO_UDF: dict[str, str] = {
    "1s": "1S",
    "5s": "5S",
    "10s": "10S",
    "15s": "15S",
    "30s": "30S",
    "1m": "1",
    "3m": "3",
    "5m": "5",
    "10m": "10",
    "15m": "15",
    "30m": "30",
    "45m": "45",
    "1h": "60",
    "2h": "120",
    "3h": "180",
    "4h": "240",
    "1d": "D",
    "1D": "D",
    "2d": "2D",
    "3d": "3D",
    "1w": "W",
    "1W": "W",
    "2w": "2W",
    "3w": "3W",
    "1M": "M",
    "2M": "2M",
    "3M": "3M",
    "6M": "6M",
    "12M": "12M",
}

_UDF_TO_CANONICAL: dict[str, str] = {v: k for k, v in _CANONICAL_TO_UDF.items()}
# Ensure bare letters and prefixed variants map to lowercase canonical
_UDF_TO_CANONICAL.update({"D": "1d", "1D": "1d", "W": "1w", "1W": "1w", "M": "1M"})

# UDF symbol-info keys use hyphens; map them to TVChartSymbolInfo field names
_UDF_SYMBOL_KEY_MAP: dict[str, str] = {
    "has-intraday": "has_intraday",
    "has-daily": "has_daily",
    "has-weekly-and-monthly": "has_weekly_and_monthly",
    "has-seconds": "has_seconds",
    "has-ticks": "has_ticks",
    "has-empty-bars": "has_empty_bars",
    "session-regular": "session",
    "session-holidays": "session_holidays",
    "session-display": "session_display",
    "supported-resolutions": "supported_resolutions",
    "intraday-multipliers": "intraday_multipliers",
    "seconds-multipliers": "seconds_multipliers",
    "visible-plots-set": "visible_plots_set",
    "exchange-listed": "listed_exchange",
    "exchange_listed_name": "listed_exchange",
    "data-status": "data_status",
    "volume-precision": "volume_precision",
    "variable-tick-size": "variable_tick_size",
    "minmovement": "minmov",
    "minmovement2": "minmove2",
}


def to_udf_resolution(canonical: str) -> str:
    """Convert a PyWry canonical resolution to UDF wire format.

    Parameters
    ----------
    canonical : str
        Resolution string like ``"1m"``, ``"5m"``, ``"1h"``, ``"1d"``.

    Returns
    -------
    str
        UDF format like ``"1"``, ``"5"``, ``"60"``, ``"D"``.
    """
    return _CANONICAL_TO_UDF.get(canonical, canonical)


def from_udf_resolution(udf_res: str) -> str:
    """Convert a UDF resolution string to PyWry canonical format.

    Parameters
    ----------
    udf_res : str
        UDF resolution like ``"1"``, ``"5"``, ``"60"``, ``"D"``.

    Returns
    -------
    str
        Canonical format like ``"1m"``, ``"5m"``, ``"1h"``, ``"1d"``.
    """
    return _UDF_TO_CANONICAL.get(udf_res, udf_res)


def parse_udf_columns(data: dict[str, Any], count: int | None = None) -> list[dict[str, Any]]:
    """Parse a UDF "response-as-a-table" columnar object into row dicts.

    In UDF format, each key maps to either a scalar (same for all rows) or
    a list (one value per row).  This function normalises both into a list
    of per-row dicts.

    Parameters
    ----------
    data : dict
        Raw UDF columnar response.
    count : int or None
        Expected row count.  If None, inferred from the first list-valued field.

    Returns
    -------
    list[dict]
        One dict per row.
    """
    if count is None:
        for v in data.values():
            if isinstance(v, list):
                count = len(v)
                break
    if count is None or count == 0:
        return []

    rows: list[dict[str, Any]] = [{} for _ in range(count)]
    for key, val in data.items():
        if isinstance(val, list):
            for i, item in enumerate(val):
                if i < count:
                    rows[i][key] = item
        else:
            for row in rows:
                row[key] = val
    return rows


def _map_symbol_keys(raw: dict[str, Any]) -> dict[str, Any]:
    """Map UDF hyphen-case / legacy keys to TVChartSymbolInfo field names."""
    mapped: dict[str, Any] = {}
    for key, val in raw.items():
        canonical = _UDF_SYMBOL_KEY_MAP.get(key, key.replace("-", "_"))
        mapped[canonical] = val
    return mapped


# ---------------------------------------------------------------------------
# Quote data model
# ---------------------------------------------------------------------------


class QuoteData:
    """Snapshot of a single symbol's quote from the ``/quotes`` endpoint.

    Attributes
    ----------
    symbol : str
        Full symbol name (e.g. ``"NYSE:AA"``).
    status : str
        Per-symbol status (``"ok"`` or ``"error"``).
    error : str
        Error message if ``status`` is ``"error"``.
    short_name : str
        Abbreviated symbol name.
    exchange : str
        Exchange name.
    description : str
        Human-readable description.
    last_price : float | None
        Last traded price.
    change : float | None
        Absolute price change.
    change_percent : float | None
        Percentage price change.
    open_price : float | None
        Opening price.
    high_price : float | None
        High price.
    low_price : float | None
        Low price.
    prev_close_price : float | None
        Previous close price.
    volume : float | None
        Trading volume.
    ask : float | None
        Ask price.
    bid : float | None
        Bid price.
    raw : dict
        The raw ``v`` dict from the UDF response.
    """

    __slots__ = (
        "ask",
        "bid",
        "change",
        "change_percent",
        "description",
        "error",
        "exchange",
        "high_price",
        "last_price",
        "low_price",
        "open_price",
        "prev_close_price",
        "raw",
        "short_name",
        "status",
        "symbol",
        "volume",
    )

    def __init__(self, n: str, s: str, v: dict[str, Any], errmsg: str = "") -> None:
        self.symbol = n
        self.status = s
        self.error = errmsg
        self.raw = v
        self.short_name: str = v.get("short_name", "")
        self.exchange: str = v.get("exchange", "")
        self.description: str = v.get("description", "")
        self.last_price: float | None = v.get("lp")
        self.change: float | None = v.get("ch")
        self.change_percent: float | None = v.get("chp")
        self.open_price: float | None = v.get("open_price")
        self.high_price: float | None = v.get("high_price")
        self.low_price: float | None = v.get("low_price")
        self.prev_close_price: float | None = v.get("prev_close_price")
        self.volume: float | None = v.get("volume")
        self.ask: float | None = v.get("ask")
        self.bid: float | None = v.get("bid")

    def format_ticker_html(self, show_change: bool = True) -> str:
        """Build an HTML snippet suitable for a Marquee ``TickerItem``.

        Parameters
        ----------
        show_change : bool
            Include change / change-percent after the price.

        Returns
        -------
        str
            Ready-to-use HTML string.
        """
        name = self.short_name or self.symbol
        price = f"{self.last_price:.2f}" if self.last_price is not None else "—"
        if not show_change or self.change is None:
            return f"<b>{name}</b>&nbsp;{price}"

        sign = "+" if self.change >= 0 else ""
        chp = self.change_percent or 0.0
        color = (
            "var(--pywry-success, #22c55e)" if self.change >= 0 else "var(--pywry-error, #ef4444)"
        )
        return (
            f"<b>{name}</b>&nbsp;{price}"
            f'&nbsp;<span style="color:{color}">'
            f"{sign}{self.change:.2f}&nbsp;({sign}{chp:.2f}%)</span>"
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Approximate bar duration in seconds for each UDF resolution family.
_RES_SECONDS: dict[str, int] = {
    "S": 1,
    "": 60,  # minutes (bare digits like "1", "5", "60")
    "D": 86400,
    "W": 604800,
    "M": 2592000,  # ~30 days
}


def _estimate_from_ts(udf_res: str, to_ts: int, countback: int) -> int:
    """Compute a reasonable ``from`` timestamp from resolution + countback.

    Used when the charting library sends ``from=0`` on the initial data
    request.  We add a 10 % margin so the server returns enough bars.
    """
    # Determine the letter suffix (D/W/M/S) or "" for minute-based
    suffix = udf_res.lstrip("0123456789")
    multiplier_str = udf_res[: len(udf_res) - len(suffix)] or "1"
    multiplier = int(multiplier_str)
    base = _RES_SECONDS.get(suffix, 60)
    bar_seconds = base * multiplier
    margin = int(countback * bar_seconds * 0.1)
    return max(0, to_ts - countback * bar_seconds - margin)


def _clamp_from_ts(udf_res: str, from_ts: int, to_ts: int, max_bars: int) -> int:
    """Ensure ``from_ts`` doesn't request more than *max_bars* for the resolution.

    When switching resolutions (e.g. daily → 1m), the frontend may send a
    from-to range that covers years — far too many bars at fine granularity.
    """
    suffix = udf_res.lstrip("0123456789")
    multiplier_str = udf_res[: len(udf_res) - len(suffix)] or "1"
    multiplier = int(multiplier_str)
    base = _RES_SECONDS.get(suffix, 60)
    bar_seconds = base * multiplier
    earliest_allowed = to_ts - max_bars * bar_seconds
    return max(from_ts, earliest_allowed)


# ---------------------------------------------------------------------------
# UDFAdapter — extends DatafeedProvider
# ---------------------------------------------------------------------------


class UDFAdapter(DatafeedProvider):
    """Connect a PyWry TradingView chart to a UDF HTTP server.

    Parameters
    ----------
    base_url : str
        Root URL of the UDF server (e.g. ``"https://demo-feed-data.tradingview.com"``).
    headers : dict or None
        Additional HTTP headers (e.g. ``{"Authorization": "Bearer ..."}``)
        sent with every request.
    poll_interval : float or None
        If set, poll ``/history`` every *poll_interval* seconds for the
        latest bar and push updates via ``respond_tvchart_bar_update``.
        Set to ``None`` (default) to disable polling.
    quote_interval : float or None
        If set, poll ``/quotes`` every *quote_interval* seconds and invoke
        the ``on_quote`` callback.  Requires symbols to be registered via
        :meth:`subscribe_quotes`.
    timeout : float
        HTTP request timeout in seconds (default 30).
    """

    def __init__(
        self,
        base_url: str,
        headers: dict[str, str] | None = None,
        poll_interval: float | None = None,
        quote_interval: float | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = headers or {}
        self._poll_interval = poll_interval
        self._quote_interval = quote_interval
        self._timeout = timeout
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers=self._headers,
            timeout=self._timeout,
        )

        # Cached config from /config
        self._config: dict[str, Any] | None = None
        self._supports_search: bool = True
        self._supports_group_request: bool = False
        self._supports_marks: bool = False
        self._supports_timescale_marks: bool = False
        self._supports_time: bool = False

        # Bar-update polling state
        self._subscriptions: dict[str, dict[str, Any]] = {}  # listenerGuid → info
        self._poll_timers: dict[str, threading.Timer] = {}

        # Quote polling state
        self._quote_symbols: set[str] = set()
        self._quote_timer: threading.Timer | None = None
        self._on_quote: Any = None  # callback(list[QuoteData])

        self._app: PyWry | None = None
        self._closed = False

    # ------------------------------------------------------------------
    # DatafeedProvider interface
    # ------------------------------------------------------------------

    async def get_config(self) -> dict[str, Any]:
        """Fetch and cache ``/config`` from the UDF server."""
        if self._config is not None:
            return self._config
        return await self._fetch_config()

    async def search_symbols(
        self,
        query: str,
        symbol_type: str = "",
        exchange: str = "",
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        """Search UDF server for matching symbols."""
        resp = await self._client.get(
            "/search",
            params={
                "query": query,
                "type": symbol_type,
                "exchange": exchange,
                "limit": limit,
            },
        )
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]

    async def resolve_symbol(self, symbol: str) -> dict[str, Any]:
        """Resolve symbol metadata from the UDF server."""
        resp = await self._client.get("/symbols", params={"symbol": symbol})
        resp.raise_for_status()
        raw = resp.json()
        return _map_symbol_keys(raw)

    async def get_bars(
        self,
        symbol: str,
        resolution: str,
        from_ts: int,
        to_ts: int,
        countback: int | None = None,
    ) -> dict[str, Any]:
        """Fetch bars from ``/history`` and convert to the PyWry response format."""
        udf_res = to_udf_resolution(resolution)

        # When from_ts is 0 (initial load), compute a reasonable value from
        # countback so servers that require `from` (e.g. BitMEX) get a valid
        # epoch timestamp instead of 0 (Jan 1 1970).
        if (not from_ts or from_ts <= 0) and countback and to_ts:
            from_ts = _estimate_from_ts(udf_res, to_ts, countback)

        # Clamp the from-to range so it doesn't exceed the server's max_bars
        # worth of data.  When switching from a coarse resolution (e.g. daily)
        # to a fine one (e.g. 1m), the JS may send the same from-to range that
        # covered years of daily bars — far too many bars at 1m granularity.
        if from_ts and to_ts and from_ts < to_ts:
            max_bars = (self._config or {}).get("max_bars", 10000)
            cb = countback or max_bars
            from_ts = _clamp_from_ts(udf_res, from_ts, to_ts, min(cb, max_bars))

        params: dict[str, Any] = {
            "symbol": symbol,
            "resolution": udf_res,
            "from": from_ts,
            "to": to_ts,
        }
        if countback is not None:
            params["countback"] = countback

        resp = await self._client.get("/history", params=params)
        logger.debug("UDF /history request: %s → %s", params, resp.status_code)
        resp.raise_for_status()
        data = resp.json()

        status = data.get("s", "ok")
        if status == "error":
            return {
                "bars": [],
                "status": "error",
                "no_data": True,
                "next_time": None,
                "error": data.get("errmsg", "Unknown error"),
            }
        if status == "no_data":
            next_time = data.get("nextTime")
            return {
                "bars": [],
                "status": "no_data",
                "no_data": True,
                "next_time": next_time,
            }

        # Parse UDF columnar bar data
        timestamps = data.get("t", [])
        closes = data.get("c", [])
        opens = data.get("o", [])
        highs = data.get("h", [])
        lows = data.get("l", [])
        volumes = data.get("v", [])

        bars: list[dict[str, Any]] = []
        for i, ts in enumerate(timestamps):
            bar: dict[str, Any] = {
                "time": ts,  # Both UDF and Lightweight Charts use Unix seconds
                "close": closes[i] if i < len(closes) else 0,
            }
            if opens and i < len(opens):
                bar["open"] = opens[i]
            if highs and i < len(highs):
                bar["high"] = highs[i]
            if lows and i < len(lows):
                bar["low"] = lows[i]
            if volumes and i < len(volumes):
                bar["volume"] = volumes[i]
            bars.append(bar)

        # UDF spec: noData can be true even when bars are returned,
        # signalling "this is the oldest data, don't request further back".
        no_data = data.get("noData", len(bars) == 0)

        return {
            "bars": bars,
            "status": "ok",
            "no_data": no_data,
            "next_time": data.get("nextTime"),
        }

    async def get_marks(
        self,
        symbol: str,
        from_ts: int,
        to_ts: int,
        resolution: str,
    ) -> list[dict[str, Any]]:
        """Fetch chart marks from the UDF ``/marks`` endpoint."""
        resp = await self._client.get(
            "/marks",
            params={
                "symbol": symbol,
                "from": from_ts,
                "to": to_ts,
                "resolution": to_udf_resolution(resolution),
            },
        )
        resp.raise_for_status()
        data = resp.json()

        # Marks can come as columnar (table format) or array of objects
        if isinstance(data, list):
            return data
        # Columnar table format
        count = len(data.get("id", data.get("time", [])))
        return parse_udf_columns(data, count=count)

    async def get_timescale_marks(
        self,
        symbol: str,
        from_ts: int,
        to_ts: int,
        resolution: str,
    ) -> list[dict[str, Any]]:
        """Fetch timescale marks from the UDF ``/timescale_marks`` endpoint."""
        resp = await self._client.get(
            "/timescale_marks",
            params={
                "symbol": symbol,
                "from": from_ts,
                "to": to_ts,
                "resolution": to_udf_resolution(resolution),
            },
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            return data
        count = len(data.get("id", data.get("time", [])))
        return parse_udf_columns(data, count=count)

    async def get_server_time(self) -> int:
        """Fetch server time from the UDF ``/time`` endpoint."""
        resp = await self._client.get("/time")
        resp.raise_for_status()
        return int(resp.text.strip())

    def on_subscribe(
        self,
        listener_guid: str,
        symbol: str,
        resolution: str,
        chart_id: str | None = None,
    ) -> None:
        """Track a bar subscription and start polling if configured."""
        self._subscriptions[listener_guid] = {
            "symbol": symbol,
            "resolution": resolution,
            "chartId": chart_id,
        }
        if self._poll_interval:
            self._start_bar_poll(listener_guid)

    def on_unsubscribe(self, listener_guid: str) -> None:
        """Remove a bar subscription and stop its poll timer."""
        self._subscriptions.pop(listener_guid, None)
        self._stop_bar_poll(listener_guid)

    @property
    def supports_marks(self) -> bool:
        """Whether the UDF server supports chart marks."""
        return self._supports_marks

    @property
    def supports_timescale_marks(self) -> bool:
        """Whether the UDF server supports timescale marks."""
        return self._supports_timescale_marks

    @property
    def supports_time(self) -> bool:
        """Whether the UDF server supports the ``/time`` endpoint."""
        return self._supports_time

    @property
    def supports_search(self) -> bool:
        """Whether the UDF server supports symbol search."""
        return self._supports_search

    # ------------------------------------------------------------------
    # Internal HTTP helpers
    # ------------------------------------------------------------------

    async def _fetch_config(self) -> dict[str, Any]:
        resp = await self._client.get("/config")
        resp.raise_for_status()
        data = resp.json()

        self._supports_search = data.get("supports_search", False)
        self._supports_group_request = data.get("supports_group_request", False)
        self._supports_marks = data.get("supports_marks", False)
        self._supports_timescale_marks = data.get("supports_timescale_marks", False)
        self._supports_time = data.get("supports_time", False)

        config: dict[str, Any] = {}
        for key in (
            "supported_resolutions",
            "exchanges",
            "symbols_types",
            "currency_codes",
            "supports_search",
            "supports_group_request",
            "supports_marks",
            "supports_timescale_marks",
            "supports_time",
            "symbols_grouping",
            "units",
        ):
            if key in data:
                config[key] = data[key]

        self._config = config
        return config

    async def _get_quotes(self, symbols: list[str]) -> list[QuoteData]:
        """Fetch real-time quotes for one or more symbols."""
        resp = await self._client.get(
            "/quotes",
            params={"symbols": ",".join(symbols)},
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("s") == "error":
            logger.warning("UDF /quotes error: %s", data.get("errmsg", ""))
            return []

        return [
            QuoteData(
                n=item.get("n", ""),
                s=item.get("s", "ok"),
                v=item.get("v", {}),
                errmsg=item.get("errmsg", ""),
            )
            for item in data.get("d", [])
        ]

    # ------------------------------------------------------------------
    # Quote subscription helpers
    # ------------------------------------------------------------------

    def subscribe_quotes(
        self,
        symbols: list[str],
        on_quote: Any = None,
    ) -> None:
        """Register symbols for periodic quote polling.

        Parameters
        ----------
        symbols : list[str]
            Symbols to track (e.g. ``["NYSE:AA", "NASDAQ:AAPL"]``).
        on_quote : callable, optional
            ``fn(quotes: list[QuoteData])`` called on each poll cycle.
            If not set, previously registered callback is kept.
        """
        self._quote_symbols.update(symbols)
        if on_quote is not None:
            self._on_quote = on_quote

    def unsubscribe_quotes(self, symbols: list[str] | None = None) -> None:
        """Remove symbols from quote polling.

        Parameters
        ----------
        symbols : list[str] or None
            Symbols to remove. If None, removes all.
        """
        if symbols is None:
            self._quote_symbols.clear()
        else:
            self._quote_symbols -= set(symbols)

    # ------------------------------------------------------------------
    # Connect (main entry point)
    # ------------------------------------------------------------------

    def connect(
        self,
        app: PyWry,
        symbol: str = "AAPL",
        resolution: str = "D",
        **show_kwargs: Any,
    ) -> Any:
        """Wire up all UDF datafeed events and show the chart.

        This is the main entry point.  Call it once; it fetches
        ``/config`` from the UDF server, auto-wires all datafeed
        event handlers via the :class:`DatafeedProvider` protocol,
        and calls ``app.show_tvchart(use_datafeed=True)``.

        Parameters
        ----------
        app : PyWry
            The application instance.
        symbol : str
            Initial symbol to display (default ``"AAPL"``).
        resolution : str
            Initial resolution in UDF format (default ``"D"``).
        **show_kwargs
            Extra keyword arguments forwarded to ``app.show_tvchart()``,
            e.g. ``title``, ``width``, ``height``, ``toolbars``, ``chart_options``.

        Returns
        -------
        NativeWindowHandle or BaseWidget
            The window or widget returned by ``show_tvchart``.
        """
        from ..state.sync_helpers import run_async

        self._app = app

        # Fetch config synchronously before showing the chart
        config = run_async(self._fetch_config(), timeout=self._timeout)

        # Auto-build toolbars from server config when not provided
        if "toolbars" not in show_kwargs:
            from .toolbars import build_tvchart_toolbars

            resolutions = config.get("supported_resolutions", [])
            intervals = [from_udf_resolution(r) for r in resolutions] if resolutions else None
            app_theme = getattr(app, "_theme", "dark")
            theme_str = app_theme.value if hasattr(app_theme, "value") else str(app_theme)
            show_kwargs["toolbars"] = build_tvchart_toolbars(
                intervals=intervals,
                selected_interval=from_udf_resolution(resolution) if intervals else None,
                theme=theme_str,
            )

        # Start quote polling if configured
        if self._quote_interval and self._quote_symbols:
            self._start_quote_polling()

        # Show the chart in datafeed mode — show_tvchart wires the
        # provider handlers AFTER the window is created, ensuring they
        # register on the correct window label.
        return app.show_tvchart(
            provider=self,
            symbol=symbol,
            resolution=from_udf_resolution(resolution),
            **show_kwargs,
        )

    # ------------------------------------------------------------------
    # Bar polling (pseudo real-time)
    # ------------------------------------------------------------------

    def _start_bar_poll(self, listener_guid: str) -> None:
        if self._closed or self._poll_interval is None:
            return

        def _poll() -> None:
            if self._closed or listener_guid not in self._subscriptions:
                return
            sub = self._subscriptions[listener_guid]
            try:
                import time as _time

                from ..state.sync_helpers import run_async

                now = int(_time.time())
                result = run_async(
                    self.get_bars(
                        sub["symbol"],
                        sub["resolution"],
                        now - 86400,  # last 24h
                        now,
                        countback=1,
                    ),
                    timeout=self._timeout,
                )
                bars = result.get("bars", [])
                if bars and self._app:
                    self._app.respond_tvchart_bar_update(
                        listener_guid=listener_guid,
                        bar=bars[-1],
                        chart_id=sub.get("chartId"),
                    )
            except Exception:
                logger.exception("Bar poll failed for %s", listener_guid)

            # Schedule next poll
            if listener_guid in self._subscriptions and not self._closed:
                timer = threading.Timer(self._poll_interval, _poll)  # type: ignore[arg-type]
                timer.daemon = True
                timer.start()
                self._poll_timers[listener_guid] = timer

        timer = threading.Timer(self._poll_interval, _poll)
        timer.daemon = True
        timer.start()
        self._poll_timers[listener_guid] = timer

    def _stop_bar_poll(self, listener_guid: str) -> None:
        timer = self._poll_timers.pop(listener_guid, None)
        if timer:
            timer.cancel()

    # ------------------------------------------------------------------
    # Quote polling
    # ------------------------------------------------------------------

    def _start_quote_polling(self) -> None:
        if self._closed or not self._quote_interval or not self._quote_symbols:
            return

        def _poll_quotes() -> None:
            if self._closed or not self._quote_symbols:
                return
            try:
                from ..state.sync_helpers import run_async

                quotes = run_async(
                    self._get_quotes(list(self._quote_symbols)),
                    timeout=self._timeout,
                )
                if self._on_quote and quotes:
                    self._on_quote(quotes)
            except Exception:
                logger.exception("Quote poll failed")

            # Schedule next poll
            if not self._closed and self._quote_symbols:
                self._quote_timer = threading.Timer(self._quote_interval, _poll_quotes)  # type: ignore[arg-type]
                self._quote_timer.daemon = True
                self._quote_timer.start()

        self._quote_timer = threading.Timer(self._quote_interval, _poll_quotes)
        self._quote_timer.daemon = True
        self._quote_timer.start()

    def _stop_quote_polling(self) -> None:
        if self._quote_timer:
            self._quote_timer.cancel()
            self._quote_timer = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Shut down the adapter: cancel timers and close the HTTP client."""
        self._closed = True
        for guid in list(self._poll_timers):
            self._stop_bar_poll(guid)
        self._stop_quote_polling()
        self._subscriptions.clear()

        from ..state.sync_helpers import run_async

        with contextlib.suppress(Exception):
            run_async(self._client.aclose(), timeout=5.0)

    @property
    def config(self) -> dict[str, Any] | None:
        """The cached UDF server configuration, or None if not yet fetched."""
        return self._config
