"""PyWry TradingView Chart Demo — live data via yFinance datafeed.

This example implements the full TradingView Datafeed API using yfinance
as the data backend.  It supports:

- Symbol search via ``yf.Search`` (fetches quotes from Yahoo Finance)
- Symbol resolution via ``Ticker.get_history_metadata()`` (session times,
  timezone, pricescale — all derived from live metadata, nothing hardcoded)
- Historical bars for multiple resolutions (1m → 1M)
- Real-time bar streaming via ``yf.WebSocket``

All history is fetched once per (symbol, resolution) and cached.  Interval
switches and symbol changes always serve the full cached dataset.

Usage::

    pip install yfinance
    python pywry_demo_tvchart_yfinance.py          # opens AAPL 1D chart
    python pywry_demo_tvchart_yfinance.py MSFT      # opens MSFT 1D chart
"""

from __future__ import annotations

import contextlib
import sys
import threading
import time

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import yfinance as yf

from yfinance.data import YfData

from pywry import PyWry, ThemeMode
from pywry.toolbar import Marquee, TickerItem, Toolbar
from pywry.tvchart import build_tvchart_toolbars


# ---------------------------------------------------------------------------
# Number formatting helpers
# ---------------------------------------------------------------------------


def _fmt_number(value: float | int, decimals: int = 2) -> str:
    """Format a number with thousand separators and fixed decimals."""
    if abs(value) >= 1e12:
        return f"{value / 1e12:,.{decimals}f}T"
    if abs(value) >= 1e9:
        return f"{value / 1e9:,.{decimals}f}B"
    if abs(value) >= 1e6:
        return f"{value / 1e6:,.{decimals}f}M"
    return f"{value:,.{decimals}f}"


def _fmt_volume(value: float | int) -> str:
    """Format volume with K/M/B suffix."""
    if abs(value) >= 1e9:
        return f"{value / 1e9:,.2f}B"
    if abs(value) >= 1e6:
        return f"{value / 1e6:,.2f}M"
    if abs(value) >= 1e3:
        return f"{value / 1e3:,.1f}K"
    return f"{value:,.0f}"


# ---------------------------------------------------------------------------
# Exchange timezone & delay caches — populated during symbol resolution
# ---------------------------------------------------------------------------
_tz_cache: dict[str, str] = {}
_delay_cache: dict[str, int] = {}  # symbol → exchangeDataDelayedBy (minutes)
_info_cache: dict[str, dict] = {}  # symbol → yf.Ticker.info snapshot
_reg_close_cache: dict[str, float] = {}  # symbol → regular session close price

# Session boundaries per symbol stored as minutes-since-midnight in
# exchange-local time: (pre_start, reg_start, reg_end, post_end).
# For US equities this is typically (240, 570, 960, 1200) → 4:00–20:00 ET.
# Populated during symbol resolution from ``currentTradingPeriod``.
_session_bounds_cache: dict[str, tuple[int, int, int, int]] = {}


def _is_overnight(epoch: int, symbol: str) -> bool:
    """Return True if *epoch* falls outside the pre→post session window.

    Overnight bars (e.g. Blue Ocean ATS 20:00–04:00 ET) are extremely
    sparse and create ugly gaps on the chart.  This helper lets both the
    historical fetch and the streaming handler skip them.
    """
    bounds = _session_bounds_cache.get(symbol.upper())
    if bounds is None:
        return False  # unknown symbol — let it through
    pre_start_m, _, _, post_end_m = bounds
    if pre_start_m == post_end_m:
        return False  # 24/7 market (crypto) — no overnight
    tz_name = _tz_cache.get(symbol.upper(), "America/New_York")
    dt = datetime.fromtimestamp(epoch, tz=ZoneInfo(tz_name))
    hm = dt.hour * 60 + dt.minute
    return hm >= post_end_m or hm < pre_start_m


def _current_session_label(symbol: str) -> tuple[str, str]:
    """Return the current (label, color) for the market session badge.

    Uses the cached session boundaries and the current clock to
    determine the session — never relies on the WebSocket or REST API
    ``market_hours`` / ``marketState`` fields, which can be stale or
    missing (proto3 omits default values).

    Session windows for US equities (exchange-local time):

    - **Pre-Market**: 4:00 AM – 9:30 AM ET
    - **Market Open**: 9:30 AM – 4:00 PM ET
    - **After Hours**: 4:00 PM – 8:00 PM ET
    - **Overnight**: 8:00 PM – 4:00 AM ET (Blue Ocean ATS)
    """
    bounds = _session_bounds_cache.get(symbol.upper())
    if bounds is None:
        return ("—", "#787b86")
    pre_start_m, reg_start_m, reg_end_m, post_end_m = bounds
    if pre_start_m == post_end_m:
        return ("Market Open", "#26a69a")  # 24/7 (crypto)
    tz_name = _tz_cache.get(symbol.upper(), "America/New_York")
    now = datetime.now(tz=ZoneInfo(tz_name))
    hm = now.hour * 60 + now.minute
    if reg_start_m <= hm < reg_end_m:
        return ("Market Open", "#26a69a")
    if pre_start_m <= hm < reg_start_m:
        return ("Pre-Market", "#ffa726")
    if reg_end_m <= hm < post_end_m:
        return ("After Hours", "#ffa726")
    if hm >= post_end_m or hm < pre_start_m:
        return ("Overnight", "#64b5f6")
    return ("Closed", "#787b86")


def _is_extended_session(symbol: str) -> bool:
    """Return True if the current time is outside the regular session."""
    bounds = _session_bounds_cache.get(symbol.upper())
    if bounds is None:
        return False
    _, reg_start_m, reg_end_m, _ = bounds
    tz_name = _tz_cache.get(symbol.upper(), "America/New_York")
    now = datetime.now(tz=ZoneInfo(tz_name))
    hm = now.hour * 60 + now.minute
    return hm < reg_start_m or hm >= reg_end_m


# ---------------------------------------------------------------------------
# Resolution mapping
# ---------------------------------------------------------------------------

# Map interval codes (as emitted by the toolbar UI) to yfinance params.
# The toolbar uses lowercase like "1m", "5m", "1d"; we normalize incoming
# resolutions via _normalize_resolution() before lookup.
_RESOLUTION_MAP: dict[str, dict[str, str]] = {
    "1m": {"interval": "1m", "period": "7d"},
    "5m": {"interval": "5m", "period": "60d"},
    "15m": {"interval": "15m", "period": "60d"},
    "30m": {"interval": "30m", "period": "60d"},
    "1h": {"interval": "1h", "period": "730d"},
    "1d": {"interval": "1d", "period": "max"},
    "1w": {"interval": "1wk", "period": "max"},
    "1M": {"interval": "1mo", "period": "max"},
}

# Derived resolutions: aggregate bars from a native (source) resolution.
_DERIVED_RESOLUTIONS: dict[str, dict[str, Any]] = {
    "3m": {"source": "1m", "factor": 3},
    "45m": {"source": "15m", "factor": 3},
    "2h": {"source": "1h", "factor": 2},
    "3h": {"source": "1h", "factor": 3},
    "4h": {"source": "1h", "factor": 4},
    "3M": {"source": "1M", "factor": 3},
    "6M": {"source": "1M", "factor": 6},
    "12M": {"source": "1M", "factor": 12},
}

# Alias map: TradingView datafeed uses bare numbers for minute resolutions
# and "1D"/"1W" for daily/weekly.  Normalize everything.
_RESOLUTION_ALIASES: dict[str, str] = {
    "1": "1m",
    "3": "3m",
    "5": "5m",
    "15": "15m",
    "30": "30m",
    "45": "45m",
    "60": "1h",
    "120": "2h",
    "180": "3h",
    "240": "4h",
    "1D": "1d",
    "D": "1d",
    "1W": "1w",
    "W": "1w",
}

# Seconds per bar for each resolution — used to bucket streaming ticks.
_RESOLUTION_SECONDS: dict[str, int] = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "45m": 2700,
    "1h": 3600,
    "2h": 7200,
    "3h": 10800,
    "4h": 14400,
    "1d": 86400,
    "1w": 604800,
    "1M": 2592000,
    "3M": 7776000,
    "6M": 15552000,
    "12M": 31104000,
}

SUPPORTED_RESOLUTIONS = [
    "1m",
    "3m",
    "5m",
    "15m",
    "30m",
    "45m",
    "1h",
    "2h",
    "3h",
    "4h",
    "1d",
    "1w",
    "1M",
    "3M",
    "6M",
    "12M",
]


def _normalize_resolution(res: str) -> str:
    """Normalize a resolution string to the canonical key used by ``_RESOLUTION_MAP``."""
    if res in _RESOLUTION_MAP or res in _DERIVED_RESOLUTIONS:
        return res
    if res in _RESOLUTION_ALIASES:
        return _RESOLUTION_ALIASES[res]
    # Fallback: try lowercase
    low = res.lower()
    if low in _RESOLUTION_MAP or low in _DERIVED_RESOLUTIONS:
        return low
    return "1d"


# ---------------------------------------------------------------------------
# Display label mappings
# ---------------------------------------------------------------------------

_TYPE_LABELS: dict[str, str] = {
    "equity": "Stock",
    "etf": "ETF",
    "index": "Index",
    "mutualfund": "Mutual Fund",
    "cryptocurrency": "Crypto",
    "currency": "Currency",
    "future": "Futures",
    "option": "Option",
}

_EXCHANGE_LABELS: dict[str, str] = {
    "NMS": "NASDAQ",
    "NGM": "NASDAQ",
    "NCM": "NASDAQ",
    "NasdaqGS": "NASDAQ",
    "NasdaqGM": "NASDAQ",
    "NasdaqCM": "NASDAQ",
    "NYQ": "NYSE",
    "NYSE": "NYSE",
    "NYSEArca": "NYSE ARCA",
    "NYSEARCA": "NYSE ARCA",
    "PCX": "NYSE ARCA",
    "NYSEAMERICAN": "NYSE AMEX",
    "ASE": "NYSE AMEX",
    "BTS": "CBOE BZX",
    "CBO": "CBOE",
    "OPR": "OTC",
    "PNK": "OTC Markets",
    "LSE": "LSE",
    "TSE": "TSE",
    "TSX": "TSX",
}

# Shared YfData instance for Lookup API calls.
_yf_data = YfData()

# ---------------------------------------------------------------------------
# yFinance helpers
# ---------------------------------------------------------------------------


def _df_to_bars(df: Any) -> list[dict[str, Any]]:
    """Convert a yfinance DataFrame to a list of bar dicts."""
    bars: list[dict[str, Any]] = []
    for ts, row in df.iterrows():
        bars.append(
            {
                "time": int(ts.timestamp()),
                "open": round(float(row["Open"]), 6),
                "high": round(float(row["High"]), 6),
                "low": round(float(row["Low"]), 6),
                "close": round(float(row["Close"]), 6),
                "volume": int(float(row["Volume"])),
            }
        )
    return bars


def _yf_fetch_full_history(symbol: str, resolution: str) -> list[dict[str, Any]]:
    """Fetch the maximum available history from yfinance for *symbol* at *resolution*.

    Always uses ``period=`` to get the full dataset — never a date range.
    """
    res = _normalize_resolution(resolution)
    mapping = _RESOLUTION_MAP.get(res, _RESOLUTION_MAP["1d"])
    yf_interval = mapping["interval"]
    yf_period = mapping["period"]

    ticker = yf.Ticker(symbol)
    try:
        df = ticker.history(interval=yf_interval, period=yf_period, prepost=True)
    except Exception:
        return []

    if df is None or df.empty:
        return []

    bars = _df_to_bars(df)

    # Strip overnight bars (e.g. Blue Ocean ATS 20:00–04:00 ET) for intraday
    # resolutions.  They are extremely sparse and create ugly gaps.
    if yf_interval not in ("1d", "5d", "1wk", "1mo", "3mo"):
        bars = [b for b in bars if not _is_overnight(b["time"], symbol)]

    return bars


def _aggregate_bars(bars: list[dict[str, Any]], factor: int) -> list[dict[str, Any]]:
    """Aggregate *bars* by grouping every *factor* consecutive bars into one."""
    out: list[dict[str, Any]] = []
    for i in range(0, len(bars), factor):
        group = bars[i : i + factor]
        if not group:
            break
        out.append(
            {
                "time": group[0]["time"],
                "open": group[0]["open"],
                "high": max(b["high"] for b in group),
                "low": min(b["low"] for b in group),
                "close": group[-1]["close"],
                "volume": sum(b["volume"] for b in group),
            }
        )
    return out


# ---------------------------------------------------------------------------
# Bar cache — (symbol, resolution) → bars, fetched once
# ---------------------------------------------------------------------------


class BarCache:
    """Thread-safe cache of bar data keyed by ``(symbol, resolution)``."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cache: dict[tuple[str, str], list[dict[str, Any]]] = {}

    def get(self, symbol: str, resolution: str) -> list[dict[str, Any]]:
        """Return cached bars, fetching from yfinance if not yet cached."""
        res = _normalize_resolution(resolution)
        key = (symbol.upper(), res)
        with self._lock:
            if key in self._cache:
                return list(self._cache[key])

        # Derived resolution: fetch source bars and aggregate
        if res in _DERIVED_RESOLUTIONS:
            derived = _DERIVED_RESOLUTIONS[res]
            source_bars = self.get(symbol, derived["source"])
            bars = _aggregate_bars(source_bars, derived["factor"])
        else:
            bars = _yf_fetch_full_history(symbol, resolution)
        with self._lock:
            self._cache[key] = bars
        return list(bars)

    def refresh(self, symbol: str, resolution: str) -> list[dict[str, Any]]:
        """Force re-fetch and return fresh bars."""
        res = _normalize_resolution(resolution)
        if res in _DERIVED_RESOLUTIONS:
            derived = _DERIVED_RESOLUTIONS[res]
            source_bars = self.refresh(symbol, derived["source"])
            bars = _aggregate_bars(source_bars, derived["factor"])
        else:
            bars = _yf_fetch_full_history(symbol, res)
        key = (symbol.upper(), res)
        with self._lock:
            self._cache[key] = bars
        return list(bars)

    def append_bar(self, symbol: str, resolution: str, bar: dict[str, Any]) -> None:
        """Merge a streaming bar into the cache (update last or append)."""
        res = _normalize_resolution(resolution)
        key = (symbol.upper(), res)
        with self._lock:
            bars = self._cache.get(key)
            if bars is None:
                return
            if bars and bars[-1]["time"] == bar["time"]:
                bars[-1] = bar
            elif not bars or bar["time"] > bars[-1]["time"]:
                bars.append(bar)

    def last_bar_time(self, symbol: str, resolution: str) -> int:
        """Return the epoch timestamp of the last cached bar, or 0."""
        res = _normalize_resolution(resolution)
        key = (symbol.upper(), res)
        with self._lock:
            bars = self._cache.get(key, [])
            return bars[-1]["time"] if bars else 0

    def invalidate(self, symbol: str, resolution: str | None = None) -> None:
        """Remove cached data for *symbol* (optionally only one resolution)."""
        with self._lock:
            if resolution:
                self._cache.pop((symbol.upper(), resolution), None)
            else:
                keys = [k for k in self._cache if k[0] == symbol.upper()]
                for k in keys:
                    del self._cache[k]


# Yahoo Lookup API type values (map our internal types to Yahoo's).
_LOOKUP_TYPE_MAP: dict[str, str] = {
    "equity": "equity",
    "etf": "etf",
    "index": "index",
    "mutualfund": "mutualfund",
    "cryptocurrency": "cryptocurrency",
    "currency": "currency",
    "future": "future",
}


def _yf_lookup(
    query: str,
    yahoo_type: str,
    count: int,
    region: str,
) -> list[dict]:
    """Single Yahoo Lookup API call."""
    url = "https://query2.finance.yahoo.com/v1/finance/lookup"
    params = {
        "query": query,
        "type": yahoo_type,
        "start": 0,
        "count": count,
        "formatted": False,
        "fetchPricingData": True,
        "lang": "en-US",
        "region": region,
    }
    resp = _yf_data.get(url=url, params=params, timeout=15)
    data = resp.json()
    result = data.get("finance", {}).get("result")
    if not result:
        return []
    return result[0].get("documents", [])


# Types to query when no specific type is requested.
_LOOKUP_ALL_TYPES = ["equity", "etf", "index", "mutualfund", "future", "currency", "cryptocurrency"]


def _yf_search(
    query: str,
    limit: int = 30,
    symbol_type: str = "",
) -> list[dict[str, Any]]:
    """Search for symbols via Yahoo Finance Lookup API.

    Queries multiple asset types in parallel when no specific type is requested,
    then deduplicates and returns up to *limit* results.
    """
    try:
        # Determine which type(s) to query.
        if symbol_type:
            yahoo_type = _LOOKUP_TYPE_MAP.get(symbol_type.lower(), "equity")
            types_to_query = [yahoo_type]
        else:
            types_to_query = _LOOKUP_ALL_TYPES

        fetch_per_type = max(limit * 2, 100) if len(types_to_query) == 1 else max(limit * 2, 50)

        # Collect docs from all type queries.
        all_docs: list[dict] = []
        seen_symbols: set[str] = set()
        for t in types_to_query:
            docs = _yf_lookup(query, t, fetch_per_type, "US")
            for doc in docs:
                sym = doc.get("symbol", "")
                if sym and sym not in seen_symbols:
                    seen_symbols.add(sym)
                    all_docs.append(doc)

        items: list[dict[str, Any]] = []
        for doc in all_docs:
            exch_code = (doc.get("exchange") or "").upper()
            items.append(
                {
                    "symbol": doc.get("symbol", ""),
                    "full_name": doc.get("longName") or doc.get("shortName", ""),
                    "description": doc.get("shortName", ""),
                    "exchange": _EXCHANGE_LABELS.get(exch_code, doc.get("exchange", "")),
                    "type": (doc.get("quoteType") or "equity").lower(),
                }
            )
            if len(items) >= limit:
                break

    except Exception as exc:
        print(f"[yfinance] Search error: {exc}")
        return []
    else:
        return items


def _build_session_string(metadata: dict[str, Any]) -> tuple[str, str, str, str, dict | None]:
    """Derive TradingView session strings from Yahoo metadata.

    Returns ``(full, premarket, regular, postmarket, schedule)`` where
    the first four are ``HHMM-HHMM`` strings and *schedule* is an
    optional per-day dict ``{"SUN": "1800-2359", ...}`` for instruments
    that don't trade every day (e.g. futures).
    """
    ctp = metadata.get("currentTradingPeriod", {})
    reg = ctp.get("regular", {})
    pre_period = ctp.get("pre", {})
    post_period = ctp.get("post", {})

    reg_start = reg.get("start", 0)
    reg_end = reg.get("end", 0)

    instrument = (metadata.get("instrumentType") or "").upper()

    # Detect ~24-hour markets by the actual span of the regular session
    if reg_start and reg_end and (reg_end - reg_start) >= 82800:  # >= 23 h
        # Futures with ~24h span are NOT 24/7 — they have a 1h daily break
        # and don't trade on Saturday.  Derive actual days from tradingPeriods.
        if instrument == "FUTURE":
            return _build_futures_session(metadata)
        # True 24/7 markets (crypto)
        return "24x7", "", "24x7", "", None

    tz_name = metadata.get("exchangeTimezoneName", "UTC")
    zi = ZoneInfo(tz_name)

    def _fmt(ts_start: int, ts_end: int) -> str:
        if not ts_start or not ts_end or ts_end <= ts_start:
            return ""
        s = datetime.fromtimestamp(ts_start, tz=zi)
        e = datetime.fromtimestamp(ts_end, tz=zi)
        return f"{s:%H%M}-{e:%H%M}"

    pre_str = _fmt(pre_period.get("start", 0), pre_period.get("end", 0))
    reg_str = _fmt(reg_start, reg_end)
    post_str = _fmt(post_period.get("start", 0), post_period.get("end", 0))

    windows = [w for w in [pre_str, reg_str, post_str] if w]
    full = ",".join(windows) if windows else "0930-1600"

    return full, pre_str, reg_str, post_str, None


def _build_futures_session(
    metadata: dict[str, Any],
) -> tuple[str, str, str, str, dict]:
    """Build session data for futures that trade ~24h Sun-Fri with a 1h break.

    CME/COMEX/NYMEX futures typically trade 18:00-17:00 ET (23h) with a
    daily maintenance break from 17:00-18:00.  Saturday is closed.

    yfinance ``tradingPeriods`` reports Sun–Thu in ET (the days each session
    **opens** at 18:00).  Thursday's session carries over into Friday until
    17:00, so the actual trading calendar is Sun–Fri in ET.

    Returns ``(full, pre, regular, post, schedule)`` where *schedule* maps
    day abbreviations to their ``HHMM-HHMM`` windows.
    """
    # Determine which calendar days have trading from tradingPeriods
    active_days: set[str] = set()
    try:
        import pandas as pd

        tp = metadata.get("tradingPeriods")
        if isinstance(tp, pd.DataFrame) and not tp.empty:
            for idx in tp.index:
                if hasattr(idx, "strftime"):
                    active_days.add(idx.strftime("%a").upper()[:3])
    except Exception:
        pass

    # Fallback: assume Sun-Fri if we couldn't read tradingPeriods
    if not active_days:
        active_days = {"SUN", "MON", "TUE", "WED", "THU", "FRI"}

    # yfinance only reports days where a session *opens* (Sun-Thu for CME).
    # Thursday's 18:00 ET session carries into Friday 17:00 ET, so Friday
    # is always a trading day when Thursday is present.
    if "THU" in active_days:
        active_days.add("FRI")

    # Build per-day schedule:
    # Sunday  → 1800-2359 (market opens Sunday evening)
    # Mon-Thu → 0000-1700, 1800-2359 (with 1h break)
    # Friday  → 0000-1700 (last session closes Friday afternoon)
    _DAY_NAMES = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]
    schedule: dict[str, str] = {}
    for day in _DAY_NAMES:
        if day not in active_days:
            continue
        if day == "SUN":
            schedule["SUN"] = "1800-2359"
        elif day == "FRI":
            schedule["FRI"] = "0000-1700"
        else:
            schedule[day] = "0000-1700,1800-2359"

    # The combined session string for the regular session field
    reg_str = "0000-1700,1800-2359"
    full = reg_str

    return full, "", reg_str, "", schedule


def _pricescale_from_hint(price_hint: int | None) -> int:
    """Convert Yahoo's ``priceHint`` (decimal places) to LWC ``pricescale``.

    ``priceHint=2`` → ``100``, ``priceHint=4`` → ``10000``, etc.
    """
    if price_hint is None or price_hint < 0:
        return 100
    return 10**price_hint


def _yf_symbol_info(symbol: str) -> dict[str, Any] | None:
    """Build TradingView ``symbolInfo`` from yfinance metadata.

    All fields are derived from ``Ticker.get_history_metadata()`` and
    ``Ticker.info`` — no hardcoded session times or timezones.
    Capabilities like intraday support, volume, and supported resolutions
    are determined per-ticker from the actual metadata.
    """
    try:
        ticker = yf.Ticker(symbol)
        md = ticker.get_history_metadata()
    except Exception as exc:
        print(f"[yfinance] Metadata error for {symbol}: {exc}")
        return None

    if not md:
        return None

    exchange_tz = md.get("exchangeTimezoneName", "UTC")
    # Cache the timezone so _yf_bars uses exchange-local day boundaries
    _tz_cache[symbol.upper()] = exchange_tz

    # Cache session boundaries as minutes-since-midnight (exchange-local)
    # for overnight filtering and time-based session badge.
    ctp = md.get("currentTradingPeriod", {})
    pre_ts = (ctp.get("pre") or {}).get("start", 0)
    reg_start_ts = (ctp.get("regular") or {}).get("start", 0)
    reg_end_ts = (ctp.get("regular") or {}).get("end", 0)
    post_ts = (ctp.get("post") or {}).get("end", 0)
    if pre_ts and reg_start_ts and reg_end_ts and post_ts:
        zi = ZoneInfo(exchange_tz)

        def _to_minutes(ts: int) -> int:
            dt = datetime.fromtimestamp(ts, tz=zi)
            return dt.hour * 60 + dt.minute

        _session_bounds_cache[symbol.upper()] = (
            _to_minutes(pre_ts),
            _to_minutes(reg_start_ts),
            _to_minutes(reg_end_ts),
            _to_minutes(post_ts),
        )
    else:
        _session_bounds_cache[symbol.upper()] = (240, 570, 960, 1200)  # 4:00,9:30,16:00,20:00
    raw_exchange = md.get("fullExchangeName") or md.get("exchangeName", "")
    exchange = _EXCHANGE_LABELS.get(raw_exchange, raw_exchange)
    name = md.get("shortName") or md.get("longName", symbol)
    instrument = (md.get("instrumentType") or "EQUITY").lower()
    type_label = _TYPE_LABELS.get(instrument, instrument.title())
    session_full, session_pre, session_reg, session_post, session_schedule = _build_session_string(
        md
    )
    pricescale = _pricescale_from_hint(md.get("priceHint"))
    currency = md.get("currency", "USD")

    # Fetch sector/industry and delay info from the detailed info endpoint
    sector = ""
    industry = ""
    delay_minutes = 0
    try:
        info = ticker.info
        sector = info.get("sector", "") or ""
        industry = info.get("industry", "") or ""
        delay_minutes = int(info.get("exchangeDataDelayedBy", 0) or 0)
        _info_cache[symbol.upper()] = info
    except Exception:
        pass

    _delay_cache[symbol.upper()] = delay_minutes

    # -- Derive capabilities from actual metadata --

    # validRanges tells us what date ranges Yahoo supports for this ticker.
    # Short ranges like "1d"/"5d" imply intraday granularity is available.
    valid_ranges = set(md.get("validRanges") or [])
    has_short_range = bool(valid_ranges & {"1d", "5d"})
    data_gran = (md.get("dataGranularity") or "1d").lower()

    # Intraday: available if short ranges exist and granularity isn't daily-only.
    has_intraday = has_short_range and data_gran != "1d"

    # Weekly/monthly: available if long ranges exist (almost always true).
    has_weekly_monthly = bool(valid_ranges & {"1y", "2y", "5y", "max"})

    # Volume: absent when regularMarketVolume is None or 0.
    raw_vol = md.get("regularMarketVolume")
    has_no_volume = raw_vol is None or raw_vol == 0

    # Build supported resolutions based on actual capabilities.
    if has_intraday:
        supported = list(SUPPORTED_RESOLUTIONS)
    else:
        # Daily and above only
        supported = [r for r in SUPPORTED_RESOLUTIONS if r in ("1d", "1w", "1M", "3M", "6M", "12M")]

    return {
        "name": name,
        "symbol": symbol.upper(),
        "ticker": symbol.upper(),
        "description": md.get("longName") or name,
        "exchange": exchange,
        "listed_exchange": exchange,
        "type": type_label,
        "session": session_full,
        "session_premarket": session_pre,
        "session_regular": session_reg,
        "session_postmarket": session_post,
        "timezone": exchange_tz,
        "sector": sector,
        "industry": industry,
        "minmov": 1,
        "pricescale": pricescale,
        "has_intraday": has_intraday,
        "has_daily": True,
        "has_weekly_and_monthly": has_weekly_monthly,
        "supported_resolutions": supported,
        "volume_precision": 0,
        "data_status": "delayed_streaming" if delay_minutes > 0 else "streaming",
        "delay": delay_minutes * 60 if delay_minutes > 0 else 0,
        "currency_code": currency,
        "has_empty_bars": False,
        "has_no_volume": has_no_volume,
        **({"session_schedule": session_schedule} if session_schedule else {}),
    }


# ---------------------------------------------------------------------------
# Real-time streaming via yfinance WebSocket
# ---------------------------------------------------------------------------


class RealtimeStreamer:
    """Background thread that uses ``yf.WebSocket`` for live price updates.

    Only pushes bar updates to subscribers at 1-minute resolution.
    Longer intervals (5m, 15m, 1h, 1D, 1W, 1M) do NOT receive streaming
    updates — their bars are complete on initial fetch and new bars form
    over much longer periods than WebSocket tick frequency.
    """

    # Only these resolutions are eligible for real-time streaming.
    _STREAMABLE = frozenset({"1m"})

    def __init__(self, app: PyWry, cache: BarCache) -> None:
        self._app = app
        self._cache = cache
        # guid → {symbol, resolution}
        self._subs: dict[str, dict[str, str]] = {}
        # symbol → latest aggregated bar (for current minute)
        self._latest: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._ws: yf.WebSocket | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        # symbol → delay in minutes (from exchangeDataDelayedBy)
        self._delay: dict[str, int] = {}
        # Periodic backfill timers (symbol → Timer)
        self._backfill_timers: dict[str, threading.Timer] = {}

    def subscribe(self, guid: str, symbol: str, resolution: str, delay_minutes: int = 0) -> None:  # noqa: D102
        # Track delay for this symbol
        if delay_minutes > 0:
            self._delay[symbol.upper()] = delay_minutes

        # Refresh cache and backfill any gap bars to the chart
        if resolution in self._STREAMABLE:
            threading.Thread(
                target=self._backfill_gap,
                args=(guid, symbol, resolution),
                daemon=True,
            ).start()
            # For delayed data sources, schedule periodic re-fetches
            if delay_minutes > 0:
                self._start_periodic_backfill(symbol, resolution, delay_minutes)

        with self._lock:
            self._subs[guid] = {"symbol": symbol, "resolution": resolution}
            symbols = list({s["symbol"] for s in self._subs.values()})

        if self._ws is None:
            self._ws = yf.WebSocket(verbose=False)
            self._ws.subscribe(symbols)
            self._stop.clear()
            self._thread = threading.Thread(target=self._listen_loop, daemon=True)
            self._thread.start()
        else:
            self._ws.subscribe([symbol])

    def unsubscribe(self, guid: str) -> None:  # noqa: D102
        with self._lock:
            info = self._subs.pop(guid, None)
            remaining_symbols = {s["symbol"] for s in self._subs.values()}

        if info and self._ws and info["symbol"] not in remaining_symbols:
            with contextlib.suppress(Exception):
                self._ws.unsubscribe([info["symbol"]])
            # Cancel periodic backfill if no more subscribers for this symbol
            key = info["symbol"].upper()
            timer = self._backfill_timers.pop(key, None)
            if timer:
                timer.cancel()

    def stop(self) -> None:  # noqa: D102
        self._stop.set()
        # Cancel all periodic backfill timers
        for timer in self._backfill_timers.values():
            timer.cancel()
        self._backfill_timers.clear()
        if self._ws:
            with contextlib.suppress(Exception):
                self._ws.close()

    def _backfill_gap(self, guid: str, symbol: str, resolution: str) -> None:
        """Refresh cache and push any newer bars to fill the gap."""
        old_last = self._cache.last_bar_time(symbol, resolution)
        new_bars = self._cache.refresh(symbol, resolution)
        gap_bars = [b for b in new_bars if b["time"] > old_last]
        if gap_bars:
            print(f"[streamer] backfilling {len(gap_bars)} gap bar(s) for {symbol}")
            for bar in gap_bars:
                self._app.respond_tvchart_bar_update(
                    listener_guid=guid,
                    bar=bar,
                )

    def _start_periodic_backfill(self, symbol: str, resolution: str, delay_minutes: int) -> None:
        """Schedule periodic cache refreshes for delayed data sources.

        Runs every 60 seconds for ``delay_minutes`` cycles to gradually
        close the gap as delayed bars become available from Yahoo.
        """
        key = symbol.upper()
        remaining = delay_minutes

        def _tick() -> None:
            nonlocal remaining
            if self._stop.is_set() or remaining <= 0:
                self._backfill_timers.pop(key, None)
                return

            old_last = self._cache.last_bar_time(symbol, resolution)
            new_bars = self._cache.refresh(symbol, resolution)
            gap_bars = [b for b in new_bars if b["time"] > old_last]

            if gap_bars:
                with self._lock:
                    guids = [
                        g
                        for g, s in self._subs.items()
                        if s["symbol"] == symbol and s["resolution"] in self._STREAMABLE
                    ]
                for guid in guids:
                    for bar in gap_bars:
                        self._app.respond_tvchart_bar_update(
                            listener_guid=guid,
                            bar=bar,
                        )
                print(f"[streamer] periodic backfill: {len(gap_bars)} bar(s) for {symbol}")

            remaining -= 1
            if remaining > 0 and not self._stop.is_set():
                t = threading.Timer(60.0, _tick)
                t.daemon = True
                self._backfill_timers[key] = t
                t.start()
            else:
                self._backfill_timers.pop(key, None)

        # First tick after 60 seconds
        t = threading.Timer(60.0, _tick)
        t.daemon = True
        self._backfill_timers[key] = t
        t.start()

    def _listen_loop(self) -> None:
        """Run the WebSocket listener in a background thread."""
        try:
            self._ws.listen(self._on_message)
        except Exception as exc:
            if not self._stop.is_set():
                print(f"[websocket] Connection closed: {exc}")

    def _on_message(self, msg: dict[str, Any]) -> None:
        """Handle a WebSocket tick message from Yahoo Finance.

        Ticks are bucketed into 1-minute bars and only pushed to
        subscribers at 1-minute resolution.
        """
        symbol = msg.get("id", "")
        price = msg.get("price")
        if not symbol or price is None:
            return

        epoch = msg.get("time")
        if not isinstance(epoch, int):
            epoch = int(time.time())

        # Bucket to the start of the current minute
        bar_time = (epoch // 60) * 60
        price = float(price)

        with self._lock:
            prev = self._latest.get(symbol)
            if prev and prev["time"] == bar_time:
                prev["high"] = max(prev["high"], price)
                prev["low"] = min(prev["low"], price)
                prev["close"] = price
                if "day_volume" in msg:
                    prev["volume"] = int(msg["day_volume"])
                bar = dict(prev)
            else:
                bar = {
                    "time": bar_time,
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                    "volume": int(msg.get("day_volume", 0)),
                }
                self._latest[symbol] = dict(bar)

            # Only push to 1-minute subscribers — skip overnight bars
            # so the chart never shows sparse Blue Ocean ATS data.
            if not _is_overnight(bar_time, symbol):
                market_hours = msg.get("market_hours")
                for guid, sub in self._subs.items():
                    if sub["symbol"] == symbol and sub["resolution"] in self._STREAMABLE:
                        push_bar = (
                            bar if market_hours is None else {**bar, "market_hours": market_hours}
                        )
                        self._app.respond_tvchart_bar_update(
                            listener_guid=guid,
                            bar=push_bar,
                        )

            # Keep cache in sync so on_data_request returns fresh data
            # (exclude overnight so refreshed history stays clean too)
            if not _is_overnight(bar_time, symbol):
                self._cache.append_bar(symbol, "1m", bar)

        # Push live fields to the marquee ticker strip
        self._update_marquee(symbol, msg)

    def _update_marquee(self, symbol: str, msg: dict[str, Any]) -> None:
        """Emit marquee-set-item events for each live data field."""
        price = msg.get("price")

        def _emit(
            ticker: str,
            text: str,
            styles: dict | None = None,
            *,
            is_html: bool = False,
        ) -> None:
            payload: dict[str, Any] = {"ticker": ticker}
            payload["html" if is_html else "text"] = text
            if styles:
                payload["styles"] = styles
            self._app.emit("toolbar:marquee-set-item", payload)

        extended = _is_extended_session(symbol)
        reg_close = _reg_close_cache.get(symbol.upper())

        if extended and reg_close is not None and price is not None:
            # Primary slots: regular session close (static)
            reg_change = msg.get("change")
            reg_pct = msg.get("change_percent")
            # The WS change/change_percent is vs previous close, not today's
            # regular close.  Recalculate from cached regular close.
            info = _info_cache.get(symbol.upper(), {})
            reg_change = info.get("regularMarketChange")
            reg_pct = info.get("regularMarketChangePercent")
            if reg_change is not None and reg_pct is not None:
                is_pos = float(reg_change) >= 0
                rc = "#26a69a" if is_pos else "#ef5350"
                arrow = "▲" if is_pos else "▼"
                sign = "+" if is_pos else ""
                _emit("ws-price", f"{reg_close:,.2f}", {"color": rc})
                _emit(
                    "ws-change",
                    f"{arrow} {sign}{float(reg_change):,.2f} ({sign}{float(reg_pct):.2f}%)",
                    {"color": rc},
                )

            # Extended-hours slots: live price + change from regular close
            ext_price = float(price)
            ext_chg = ext_price - reg_close
            ext_pct = (ext_chg / reg_close) * 100 if reg_close else 0
            ext_pos = ext_chg >= 0
            ext_color = "#26a69a" if ext_pos else "#ef5350"
            ext_arrow = "▲" if ext_pos else "▼"
            ext_sign = "+" if ext_pos else ""
            _emit("ws-ext-price", f"{ext_price:,.2f}", {"color": ext_color})
            _emit(
                "ws-ext-change",
                f"{ext_arrow} {ext_sign}{ext_chg:,.2f} ({ext_sign}{ext_pct:.2f}%)",
                {"color": ext_color},
            )
        else:
            # Regular session: update primary slots with live data
            change = msg.get("change")
            change_pct = msg.get("change_percent")
            is_positive = (change or 0) >= 0
            color = "#26a69a" if is_positive else "#ef5350"
            arrow = "▲" if is_positive else "▼"

            if price is not None:
                _emit("ws-price", f"{float(price):,.2f}", {"color": color})
                # Cache as regular close for when session ends
                _reg_close_cache[symbol.upper()] = float(price)

            if change is not None and change_pct is not None:
                sign = "+" if is_positive else ""
                _emit(
                    "ws-change",
                    f"{arrow} {sign}{float(change):,.2f} ({sign}{float(change_pct):.2f}%)",
                    {"color": color},
                )

            # Clear extended-hours slots
            _emit("ws-ext-price", "")
            _emit("ws-ext-change", "")

        if "open_price" in msg:
            _emit("ws-open", f"{float(msg['open_price']):,.2f}")

        if "day_high" in msg:
            _emit("ws-high", f"{float(msg['day_high']):,.2f}")

        if "day_low" in msg:
            _emit("ws-low", f"{float(msg['day_low']):,.2f}")

        if "day_volume" in msg:
            _emit("ws-volume", _fmt_volume(float(msg["day_volume"])))

        if "market_cap" in msg:
            _emit("ws-mktcap", _fmt_number(float(msg["market_cap"]), 2))

        if "vol_24hr" in msg:
            _emit(
                "ws-vol24",
                f'<span class="ws-label">24h Vol</span> {_fmt_volume(float(msg["vol_24hr"]))}',
                is_html=True,
            )

        # Update the symbol label if needed (first message)
        _emit("ws-symbol", symbol.upper())

        # Market session status — always derived from current clock
        label, clr = _current_session_label(symbol)
        _emit("ws-session", label, {"color": clr})


def _seed_marquee(app: PyWry, symbol: str) -> None:
    """Populate the marquee with initial data from the cached ticker.info."""
    info = _info_cache.get(symbol.upper())
    if not info:
        return

    def _emit(
        ticker: str,
        text: str,
        styles: dict | None = None,
        *,
        is_html: bool = False,
    ) -> None:
        payload: dict[str, Any] = {"ticker": ticker}
        payload["html" if is_html else "text"] = text
        if styles:
            payload["styles"] = styles
        app.emit("toolbar:marquee-set-item", payload)

    # Always show regular session close in the primary slots.
    reg_price = info.get("regularMarketPrice")
    reg_change = info.get("regularMarketChange")
    reg_pct = info.get("regularMarketChangePercent")

    # Cache the regular close for streaming ext-hours calculation
    if reg_price is not None:
        _reg_close_cache[symbol.upper()] = float(reg_price)

    is_positive = (reg_change or 0) >= 0
    color = "#26a69a" if is_positive else "#ef5350"
    arrow = "▲" if is_positive else "▼"

    if reg_price is not None:
        _emit("ws-price", f"{float(reg_price):,.2f}", {"color": color})

    if reg_change is not None and reg_pct is not None:
        sign = "+" if is_positive else ""
        _emit(
            "ws-change",
            f"{arrow} {sign}{float(reg_change):,.2f} ({sign}{float(reg_pct):.2f}%)",
            {"color": color},
        )

    # Extended-hours: show ext price + change from regular close
    ms = (info.get("marketState") or "").upper()
    ext_price = None
    if ms in ("POST", "POSTPOST"):
        ext_price = info.get("postMarketPrice")
    elif ms in ("PRE", "PREPRE"):
        ext_price = info.get("preMarketPrice")

    if ext_price is not None and reg_price is not None:
        ext_chg = float(ext_price) - float(reg_price)
        ext_pct = (ext_chg / float(reg_price)) * 100 if reg_price else 0
        ext_pos = ext_chg >= 0
        ext_color = "#26a69a" if ext_pos else "#ef5350"
        ext_arrow = "▲" if ext_pos else "▼"
        ext_sign = "+" if ext_pos else ""
        _emit("ws-ext-price", f"{float(ext_price):,.2f}", {"color": ext_color})
        _emit(
            "ws-ext-change",
            f"{ext_arrow} {ext_sign}{ext_chg:,.2f} ({ext_sign}{ext_pct:.2f}%)",
            {"color": ext_color},
        )
    else:
        _emit("ws-ext-price", "")
        _emit("ws-ext-change", "")

    # OHLV fields
    open_price = info.get("regularMarketOpen") or info.get("open")
    if open_price is not None:
        _emit("ws-open", f"{float(open_price):,.2f}")

    high = info.get("regularMarketDayHigh") or info.get("dayHigh")
    if high is not None:
        _emit("ws-high", f"{float(high):,.2f}")

    low = info.get("regularMarketDayLow") or info.get("dayLow")
    if low is not None:
        _emit("ws-low", f"{float(low):,.2f}")

    volume = info.get("regularMarketVolume") or info.get("volume")
    if volume is not None:
        _emit("ws-volume", _fmt_volume(float(volume)))

    mkt_cap = info.get("marketCap")
    if mkt_cap is not None:
        _emit("ws-mktcap", _fmt_number(float(mkt_cap), 2))

    # Crypto-specific 24h volume
    is_crypto = (info.get("quoteType") or "").lower() == "cryptocurrency"
    if is_crypto:
        vol_24 = info.get("volume24Hr")
        if vol_24 is not None:
            _emit(
                "ws-vol24",
                f'<span class="ws-label">24h Vol</span> {_fmt_volume(float(vol_24))}',
                is_html=True,
            )
    else:
        _emit("ws-vol24", "")

    _emit("ws-symbol", symbol.upper())

    # Market session status — always derived from current clock
    label, clr = _current_session_label(symbol)
    _emit("ws-session", label, {"color": clr})


# ---------------------------------------------------------------------------
# Datafeed callbacks
# ---------------------------------------------------------------------------


def make_callbacks(
    app: PyWry,
    streamer: RealtimeStreamer,
    cache: BarCache,
) -> dict[str, Any]:
    """Build the callback dict that implements the TV Datafeed protocol."""

    def on_config(data: dict[str, Any]) -> None:
        """Respond to ``onReady`` with datafeed configuration."""
        request_id = data.get("requestId", "")
        chart_id = data.get("chartId")
        print(f"[datafeed] config-request  id={request_id}")
        app.respond_tvchart_datafeed_config(
            request_id=request_id,
            chart_id=chart_id,
            config={
                "supported_resolutions": list(SUPPORTED_RESOLUTIONS),
                "exchanges": [],
                "symbols_types": [
                    {"name": "All Types", "value": ""},
                    {"name": "Stock", "value": "equity"},
                    {"name": "ETF", "value": "etf"},
                    {"name": "Index", "value": "index"},
                    {"name": "Mutual Fund", "value": "mutualfund"},
                    {"name": "Futures", "value": "future"},
                    {"name": "Crypto", "value": "cryptocurrency"},
                    {"name": "Currency", "value": "currency"},
                ],
                "supports_marks": False,
                "supports_time": True,
                "supports_timescale_marks": False,
            },
        )

    def on_search(data: dict[str, Any]) -> None:
        """Respond to ``searchSymbols`` with matching tickers."""
        request_id = data.get("requestId", "")
        query = data.get("query", "")
        symbol_type = data.get("symbolType", "")
        limit = data.get("limit", 30)
        chart_id = data.get("chartId")
        print(
            f"[datafeed] search  q={query!r} type={symbol_type!r}  id={request_id}",
        )
        items = _yf_search(query, limit=limit, symbol_type=symbol_type)
        app.respond_tvchart_symbol_search(
            request_id=request_id,
            items=items,
            chart_id=chart_id,
            query=query,
        )

    def on_resolve(data: dict[str, Any]) -> None:
        """Respond to ``resolveSymbol`` with full symbol metadata."""
        request_id = data.get("requestId", "")
        symbol = data.get("symbol", "")
        chart_id = data.get("chartId")
        print(f"[datafeed] resolve  sym={symbol!r}  id={request_id}")
        info = _yf_symbol_info(symbol)
        if info is None:
            app.respond_tvchart_symbol_resolve(
                request_id=request_id,
                symbol_info=None,
                chart_id=chart_id,
                error=f"Could not resolve symbol: {symbol}",
            )
        else:
            app.respond_tvchart_symbol_resolve(
                request_id=request_id,
                symbol_info=info,
                chart_id=chart_id,
            )
            # Seed the marquee with snapshot data from ticker.info
            _seed_marquee(app, symbol)

    def on_history(data: dict[str, Any]) -> None:
        """Respond to ``getBars`` with full cached history."""
        request_id = data.get("requestId", "")
        symbol = data.get("symbol", "")
        resolution = _normalize_resolution(data.get("resolution", "1d"))
        chart_id = data.get("chartId")
        first = data.get("firstDataRequest", False)
        print(
            f"[datafeed] history  sym={symbol!r} res={resolution} first={first}  id={request_id}",
        )

        bars = cache.get(symbol, resolution)
        if not bars:
            app.respond_tvchart_history(
                request_id=request_id,
                bars=[],
                status="no_data",
                no_data=True,
                chart_id=chart_id,
            )
        else:
            app.respond_tvchart_history(
                request_id=request_id,
                bars=bars,
                status="ok",
                chart_id=chart_id,
            )

    def on_subscribe(data: dict[str, Any]) -> None:
        """Handle ``subscribeBars`` — start real-time WebSocket streaming."""
        guid = data.get("listenerGuid", "")
        symbol = data.get("symbol", "")
        resolution = data.get("resolution", "1D")
        delay = _delay_cache.get(symbol.upper(), 0)
        print(f"[datafeed] subscribe  sym={symbol!r} res={resolution} guid={guid} delay={delay}m")
        streamer.subscribe(guid, symbol, resolution, delay_minutes=delay)

    def on_unsubscribe(data: dict[str, Any]) -> None:
        """Handle ``unsubscribeBars`` — stop streaming for this listener."""
        guid = data.get("listenerGuid", "")
        print(f"[datafeed] unsubscribe  guid={guid}")
        streamer.unsubscribe(guid)

    def on_server_time(data: dict[str, Any]) -> None:
        """Respond to ``getServerTime`` with current epoch seconds."""
        request_id = data.get("requestId", "")
        chart_id = data.get("chartId")
        app.respond_tvchart_server_time(
            request_id=request_id,
            time=int(time.time()),
            chart_id=chart_id,
        )

    def on_data_request(data: dict[str, Any], _et: str = "", _lb: str = "") -> None:
        """Unified data handler for interval changes, symbol changes, etc.

        Always serves the entire cached history for the requested
        (symbol, resolution) pair.
        """
        chart_id = data.get("chartId", "main")
        series_id = data.get("seriesId", "main")
        symbol = data.get("symbol", "")
        raw_res = str(data.get("resolution", data.get("interval", "1d")))
        resolution = _normalize_resolution(raw_res)
        print(f"[data-request] sym={symbol!r} res={resolution} series={series_id}")
        if not symbol:
            return
        bars = cache.get(symbol, resolution)
        print(f"[data-request] serving {len(bars)} cached bars for {symbol} @ {resolution}")
        app.emit(
            "tvchart:data-response",
            {
                "chartId": chart_id,
                "seriesId": series_id,
                "bars": bars,
                "fitContent": True,
                "interval": resolution,
            },
        )

    return {
        "tvchart:datafeed-config-request": on_config,
        "tvchart:datafeed-search-request": on_search,
        "tvchart:datafeed-resolve-request": on_resolve,
        "tvchart:datafeed-history-request": on_history,
        "tvchart:datafeed-subscribe": on_subscribe,
        "tvchart:datafeed-unsubscribe": on_unsubscribe,
        "tvchart:datafeed-server-time-request": on_server_time,
        "tvchart:data-request": on_data_request,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Launch the yFinance-powered TradingView chart."""
    symbol = sys.argv[1].upper() if len(sys.argv) > 1 else "AAPL"

    app = PyWry(theme=ThemeMode.DARK)
    cache = BarCache()
    streamer = RealtimeStreamer(app, cache)

    callbacks = make_callbacks(app, streamer, cache)

    # Keep Python-side theme in sync when the toggle fires
    def on_theme_change(data: dict[str, Any]) -> None:
        theme_str = (data.get("theme") or "dark").lower()
        app.theme = ThemeMode.LIGHT if theme_str == "light" else ThemeMode.DARK

    callbacks["pywry:update-theme"] = on_theme_change

    toolbars = build_tvchart_toolbars(
        intervals=SUPPORTED_RESOLUTIONS,
        selected_interval="1d",
    )

    # -- Live data marquee (non-scrolling ticker strip above the header) -----
    ticker_items = [
        TickerItem(
            ticker="ws-symbol",
            html=f'<span class="ws-sym">{symbol}</span>',
        ),
        TickerItem(
            ticker="ws-price",
            html='<span class="ws-val">—</span>',
            class_name="ws-price",
        ),
        TickerItem(
            ticker="ws-change",
            html='<span class="ws-val ws-muted">— (—%)</span>',
            class_name="ws-change",
        ),
        TickerItem(
            ticker="ws-session",
            html='<span class="ws-val ws-muted">—</span>',
            class_name="ws-session",
        ),
        TickerItem(
            ticker="ws-ext-price",
            html="",
            class_name="ws-ext-price",
        ),
        TickerItem(
            ticker="ws-ext-change",
            html="",
            class_name="ws-ext-change",
        ),
        TickerItem(
            ticker="ws-open",
            html='<span class="ws-val ws-muted">—</span>',
            class_name="ws-field",
        ),
        TickerItem(
            ticker="ws-high",
            html='<span class="ws-val ws-muted">—</span>',
            class_name="ws-field",
        ),
        TickerItem(
            ticker="ws-low",
            html='<span class="ws-val ws-muted">—</span>',
            class_name="ws-field",
        ),
        TickerItem(
            ticker="ws-volume",
            html='<span class="ws-val ws-muted">—</span>',
            class_name="ws-field",
        ),
        TickerItem(
            ticker="ws-mktcap",
            html='<span class="ws-val ws-muted">—</span>',
            class_name="ws-field",
        ),
        TickerItem(
            ticker="ws-vol24",
            html="",
            class_name="ws-field",
        ),
    ]

    # Build HTML: label + value pairs laid out in a flex row
    labels = ["", "", "", "", "", "", "O", "H", "L", "Vol", "Mkt Cap", ""]
    parts: list[str] = []
    for label, item in zip(labels, ticker_items, strict=False):
        if label:
            parts.append(f'<span class="ws-label">{label}</span>{item.build_html()}')
        else:
            parts.append(item.build_html())

    marquee_html = "  ".join(parts)

    marquee_toolbar = Toolbar(
        position="header",
        class_name="yf-marquee-strip",
        items=[
            Marquee(
                component_id="yf-live-marquee",
                text=marquee_html,
                behavior="static",
                event="toolbar:noop",
                style="width: 100%;",
            ),
        ],
    )
    toolbars.insert(0, marquee_toolbar)

    # -- Custom CSS for the marquee strip -----------------------------------
    marquee_css = """
    .yf-marquee-strip {
        border-bottom: 1px solid var(--pywry-border-color, #333) !important;
        background: var(--pywry-bg-primary, #1e1e1e) !important;
        padding: 0 !important;
        min-height: 0 !important;
    }
    .yf-marquee-strip .pywry-toolbar-content {
        padding: 0 !important;
    }
    .yf-marquee-strip .pywry-marquee {
        width: 100%;
    }
    .yf-marquee-strip .pywry-marquee-content {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 4px 10px;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        font-size: 11.5px;
        letter-spacing: 0.01em;
        white-space: nowrap;
    }
    .ws-sym {
        font-weight: 700;
        font-size: 13px;
        color: var(--pywry-text-primary, #e0e0e0);
        letter-spacing: 0.04em;
    }
    .ws-price .pywry-ticker-item,
    .ws-price {
        font-weight: 600;
        font-size: 13px;
        font-variant-numeric: tabular-nums;
    }
    .ws-change .pywry-ticker-item,
    .ws-change {
        font-weight: 500;
        font-size: 11.5px;
        font-variant-numeric: tabular-nums;
    }
    .ws-label {
        color: var(--pywry-text-secondary, #787b86);
        font-size: 10.5px;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin-right: 2px;
    }
    .ws-field {
        font-variant-numeric: tabular-nums;
        color: var(--pywry-text-primary, #e0e0e0);
        font-size: 11px;
    }
    .ws-val {
        font-variant-numeric: tabular-nums;
    }
    .ws-muted {
        color: var(--pywry-text-secondary, #787b86);
    }
    .ws-session .pywry-ticker-item,
    .ws-session {
        font-weight: 600;
        font-size: 10.5px;
        letter-spacing: 0.03em;
        padding: 1px 6px;
        border-radius: 3px;
        background: rgba(255, 255, 255, 0.06);
    }
    .ws-ext-price .pywry-ticker-item,
    .ws-ext-price {
        font-weight: 600;
        font-size: 13px;
        font-variant-numeric: tabular-nums;
    }
    .ws-ext-change .pywry-ticker-item,
    .ws-ext-change {
        font-weight: 500;
        font-size: 11.5px;
        font-variant-numeric: tabular-nums;
    }
    """

    app.show_tvchart(
        use_datafeed=True,
        symbol=symbol,
        resolution="1d",
        title="PyWry - TradingView Lightweight Chart with yFinance Datafeed",
        width=1280,
        height=800,
        chart_options={
            "timeScale": {"secondsVisible": False},
        },
        toolbars=toolbars,
        callbacks=callbacks,
        inline_css=marquee_css,
    )

    print(f"\n  Chart opened for {symbol}.  Close the window to exit.\n")
    try:
        app.block()
    finally:
        streamer.stop()


if __name__ == "__main__":
    main()
