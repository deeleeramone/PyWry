"""Tests for ``pywry/tvchart/udf.py``.

The :class:`UDFAdapter` connects a PyWry TradingView chart to any
TradingView UDF-compatible HTTP server.  Tests cover:

* Pure helper functions (resolution mapping, columnar parsing,
  bar aggregation, decomposition).
* :class:`QuoteData` ticker formatting.
* :class:`UDFAdapter` HTTP endpoint parsing
  (``/config``, ``/symbols``, ``/search``, ``/history``, ``/marks``,
  ``/timescale_marks``, ``/time``, ``/quotes``).
* Subscription / polling lifecycle (bar + quote pollers driven via
  fake timers so no wall-clock waiting happens in tests).
* :meth:`UDFAdapter.connect` integration with a mocked ``PyWry`` app.

HTTP responses are produced by a tiny ``_MockResponse`` helper that
mirrors the subset of :class:`httpx.Response` actually used by the
adapter.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from pywry.tvchart.udf import (
    _RES_SECONDS,
    QuoteData,
    UDFAdapter,
    _aggregate_bars,
    _clamp_from_ts,
    _decompose_resolution,
    _estimate_from_ts,
    _map_symbol_keys,
    _parse_udf_history,
    from_udf_resolution,
    parse_udf_columns,
    to_udf_resolution,
)


# =============================================================================
# Shared fixtures / mock helpers
# =============================================================================


class _MockResponse:
    """Minimal mock of :class:`httpx.Response`."""

    def __init__(
        self,
        status_code: int,
        json_data: Any,
        *,
        raise_on_json: bool = False,
    ) -> None:
        self.status_code = status_code
        self._json = json_data
        self.text = str(json_data) if not isinstance(json_data, str) else json_data
        self._raise_on_json = raise_on_json

    def json(self) -> Any:
        if self._raise_on_json:
            raise ValueError("Bad JSON")
        return self._json

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=httpx.Request("GET", "https://example.com"),
                response=self,  # type: ignore[arg-type]
            )


class _FakeTimer:
    """Replacement for :class:`threading.Timer` that captures ``fn``
    without scheduling.  Used to drive the inner poll callbacks
    deterministically."""

    instances: list[_FakeTimer] = []  # noqa: RUF012 — collected across tests

    def __init__(self, interval: float, fn: Any) -> None:
        self.interval = interval
        self.fn = fn
        self.daemon = False
        self.started = False
        self.cancelled = False
        type(self).instances.append(self)

    def start(self) -> None:
        self.started = True

    def cancel(self) -> None:
        self.cancelled = True


@pytest.fixture()
def adapter() -> UDFAdapter:
    return UDFAdapter("https://example.com")


# =============================================================================
# Resolution mapping
# =============================================================================


class TestResolutionMapping:
    @pytest.mark.parametrize(
        ("canonical", "udf"),
        [
            ("1m", "1"),
            ("5m", "5"),
            ("15m", "15"),
            ("30m", "30"),
            ("1h", "60"),
            ("2h", "120"),
            ("4h", "240"),
            ("1d", "D"),
            ("1D", "D"),
            ("1w", "W"),
            ("1W", "W"),
            ("1M", "M"),
            ("3M", "3M"),
        ],
    )
    def test_canonical_to_udf(self, canonical: str, udf: str) -> None:
        assert to_udf_resolution(canonical) == udf

    @pytest.mark.parametrize(
        ("udf", "canonical"),
        [
            ("1", "1m"),
            ("5", "5m"),
            ("60", "1h"),
            ("D", "1d"),
            ("1D", "1d"),
            ("W", "1w"),
            ("M", "1M"),
            ("1M", "1M"),
        ],
    )
    def test_udf_to_canonical(self, udf: str, canonical: str) -> None:
        assert from_udf_resolution(udf) == canonical

    def test_passthrough_unknown(self) -> None:
        assert to_udf_resolution("UNKNOWN") == "UNKNOWN"
        assert from_udf_resolution("UNKNOWN") == "UNKNOWN"


# =============================================================================
# UDF columnar table → row dicts
# =============================================================================


class TestParseUDFColumns:
    def test_basic_table(self) -> None:
        rows = parse_udf_columns({"t": [100, 200, 300], "c": [10.0, 20.0, 30.0]})
        assert len(rows) == 3
        assert rows[0] == {"t": 100, "c": 10.0}
        assert rows[2] == {"t": 300, "c": 30.0}

    def test_scalar_broadcast(self) -> None:
        rows = parse_udf_columns(
            {"symbol": ["AAPL", "MSFT"], "exchange": "NASDAQ", "pricescale": 100}
        )
        assert rows[0] == {"symbol": "AAPL", "exchange": "NASDAQ", "pricescale": 100}
        assert rows[1] == {"symbol": "MSFT", "exchange": "NASDAQ", "pricescale": 100}

    def test_empty_data(self) -> None:
        assert parse_udf_columns({}) == []
        assert parse_udf_columns({"scalar": 42}) == []

    def test_explicit_count(self) -> None:
        rows = parse_udf_columns({"val": 99}, count=3)
        assert len(rows) == 3
        assert all(r["val"] == 99 for r in rows)

    def test_explicit_count_zero(self) -> None:
        assert parse_udf_columns({"a": [1, 2]}, count=0) == []

    def test_mixed_scalar_and_list(self) -> None:
        rows = parse_udf_columns(
            {"id": [1, 2], "time": [1000, 2000], "color": "red", "label": ["A", "B"]}
        )
        assert rows[0] == {"id": 1, "time": 1000, "color": "red", "label": "A"}
        assert rows[1] == {"id": 2, "time": 2000, "color": "red", "label": "B"}


# =============================================================================
# Internal helpers
# =============================================================================


class TestSymbolKeyMapping:
    def test_hyphen_to_underscore(self) -> None:
        result = _map_symbol_keys({"has-intraday": True, "name": "AAPL", "extra-foo": 1})
        assert result["has_intraday"] is True
        assert result["name"] == "AAPL"
        assert result["extra_foo"] == 1


class TestEstimateFromTs:
    def test_minutes(self) -> None:
        # "1" → minute resolution, 1 multiplier
        result = _estimate_from_ts("1", to_ts=1_700_000_000, countback=100)
        assert 0 < result < 1_700_000_000

    def test_hours(self) -> None:
        # "60" → minute base, 60 multiplier
        result = _estimate_from_ts("60", to_ts=1_700_000_000, countback=10)
        assert result > 0

    def test_days(self) -> None:
        result = _estimate_from_ts("D", to_ts=1_700_000_000, countback=5)
        assert result > 0

    def test_clamped_to_zero(self) -> None:
        result = _estimate_from_ts("D", to_ts=100, countback=10_000_000)
        assert result == 0


class TestClampFromTs:
    def test_within_range_returned_unchanged(self) -> None:
        result = _clamp_from_ts("D", from_ts=1_699_999_900, to_ts=1_700_000_000, max_bars=10)
        assert result == 1_699_999_900

    def test_pushed_forward_when_too_old(self) -> None:
        # earliest_allowed = 1_700_000_000 - 10*60 = 1_699_999_400
        result = _clamp_from_ts("1", from_ts=0, to_ts=1_700_000_000, max_bars=10)
        assert result == 1_699_999_400


class TestDecomposeResolution:
    def test_weekly(self) -> None:
        assert _decompose_resolution("W") == ("D", 7)
        assert _decompose_resolution("3W") == ("D", 21)

    def test_daily_multi(self) -> None:
        assert _decompose_resolution("3D") == ("D", 3)

    def test_daily_single(self) -> None:
        assert _decompose_resolution("D") == ("D", 1)

    def test_hour_aligned(self) -> None:
        assert _decompose_resolution("120") == ("60", 2)

    def test_minutes(self) -> None:
        assert _decompose_resolution("15") == ("1", 15)

    def test_unrecognised(self) -> None:
        assert _decompose_resolution("3M") == ("3M", 1)


class TestAggregateBars:
    def test_no_op_for_n_one(self) -> None:
        bars = [{"time": 1, "open": 1, "high": 2, "low": 0, "close": 1}]
        assert _aggregate_bars(bars, 1) == bars

    def test_empty(self) -> None:
        assert _aggregate_bars([], 5) == []

    def test_aggregate_chunks(self) -> None:
        bars = [
            {"time": 1, "open": 1, "high": 2, "low": 0, "close": 1, "volume": 100},
            {"time": 2, "open": 1, "high": 3, "low": 0.5, "close": 2, "volume": 200},
            {"time": 3, "open": 2, "high": 4, "low": 1, "close": 3, "volume": 300},
            {"time": 4, "open": 3, "high": 5, "low": 2, "close": 4, "volume": 400},
        ]
        result = _aggregate_bars(bars, 2)
        assert len(result) == 2
        assert result[0]["time"] == 1
        assert result[0]["open"] == 1  # first open in chunk
        assert result[0]["close"] == 2  # last close in chunk
        assert result[0]["high"] == 3  # max
        assert result[0]["low"] == 0  # min
        assert result[0]["volume"] == 300  # sum

    def test_partial_fields(self) -> None:
        bars = [
            {"time": 1, "open": 1, "close": 1},
            {"time": 2, "open": 1, "close": 2},
        ]
        result = _aggregate_bars(bars, 2)
        assert len(result) == 1
        assert "high" not in result[0]
        assert "low" not in result[0]
        assert "volume" not in result[0]


class TestParseUDFHistory:
    def test_with_volume(self) -> None:
        result = _parse_udf_history(
            {
                "t": [100, 200],
                "c": [10.0, 11.0],
                "o": [9.0, 10.0],
                "h": [11.0, 12.0],
                "l": [8.0, 9.0],
                "v": [1000, 2000],
            }
        )
        assert result["status"] == "ok"
        assert len(result["bars"]) == 2
        assert result["bars"][0]["volume"] == 1000

    def test_close_only(self) -> None:
        result = _parse_udf_history({"t": [100], "c": [10.0]})
        assert result["bars"][0]["close"] == 10.0
        assert "open" not in result["bars"][0]


class TestResSecondsConstants:
    def test_known_units(self) -> None:
        assert _RES_SECONDS["S"] == 1
        assert _RES_SECONDS[""] == 60  # minute family
        assert _RES_SECONDS["D"] == 86400


# =============================================================================
# QuoteData
# =============================================================================


class TestQuoteData:
    def test_basic_fields(self) -> None:
        q = QuoteData(
            n="NYSE:AA",
            s="ok",
            v={
                "ch": 0.16,
                "chp": 0.98,
                "short_name": "AA",
                "exchange": "NYSE",
                "description": "Alcoa Inc.",
                "lp": 16.57,
                "ask": 16.58,
                "bid": 16.57,
                "open_price": 16.25,
                "high_price": 16.60,
                "low_price": 16.25,
                "prev_close_price": 16.41,
                "volume": 4029041,
            },
        )
        assert q.symbol == "NYSE:AA"
        assert q.status == "ok"
        assert q.last_price == 16.57
        assert q.change == 0.16
        assert q.change_percent == 0.98
        assert q.short_name == "AA"
        assert q.volume == 4029041

    def test_error_quote(self) -> None:
        q = QuoteData(n="", s="error", v={}, errmsg="not found")
        assert q.status == "error"
        assert q.error == "not found"
        assert q.last_price is None

    def test_format_ticker_html_positive(self) -> None:
        q = QuoteData(
            n="AAPL",
            s="ok",
            v={"short_name": "AAPL", "lp": 186.25, "ch": 1.50, "chp": 0.81},
        )
        html = q.format_ticker_html()
        assert "<b>AAPL</b>" in html
        assert "186.25" in html
        assert "+1.50" in html
        assert "+0.81%" in html
        assert "pywry-success" in html

    def test_format_ticker_html_negative(self) -> None:
        q = QuoteData(
            n="MSFT",
            s="ok",
            v={"short_name": "MSFT", "lp": 415.00, "ch": -2.50, "chp": -0.60},
        )
        html = q.format_ticker_html()
        assert "MSFT" in html
        assert "-2.50" in html
        assert "pywry-error" in html

    def test_format_ticker_html_zero_change_treated_as_positive(self) -> None:
        q = QuoteData(n="X", s="ok", v={"lp": 100.0, "ch": 0.0, "chp": 0.0})
        html = q.format_ticker_html()
        assert "pywry-success" in html

    def test_format_ticker_html_no_change_data(self) -> None:
        q = QuoteData(n="X", s="ok", v={})
        html = q.format_ticker_html()
        assert "—" in html  # placeholder when no price

    def test_format_ticker_html_show_change_false(self) -> None:
        q = QuoteData(n="X", s="ok", v={"lp": 100.0, "ch": 1.0, "chp": 1.0})
        html = q.format_ticker_html(show_change=False)
        assert "+1.00" not in html

    def test_format_ticker_html_no_short_name_uses_symbol(self) -> None:
        q = QuoteData(n="AAPL", s="ok", v={"lp": 100.0, "ch": 1.0, "chp": 1.0})
        html = q.format_ticker_html()
        assert "<b>AAPL</b>" in html

    def test_format_ticker_html_no_change_when_present_price(self) -> None:
        q = QuoteData(n="X", s="ok", v={"short_name": "X", "lp": 10.0})
        html = q.format_ticker_html(show_change=True)
        assert "10.00" in html
        # No change data → just price, no color spans.
        assert "span" not in html


# =============================================================================
# UDFAdapter endpoint parsing
# =============================================================================


class TestUDFAdapterConfig:
    async def test_parse_config(self, adapter: UDFAdapter, monkeypatch: pytest.MonkeyPatch) -> None:
        raw_config = {
            "supports_search": True,
            "supports_group_request": False,
            "supports_marks": True,
            "supports_timescale_marks": True,
            "supports_time": True,
            "exchanges": [
                {"value": "", "name": "All Exchanges", "desc": ""},
                {"value": "XETRA", "name": "XETRA", "desc": "XETRA"},
            ],
            "symbols_types": [{"name": "All types", "value": ""}],
            "supported_resolutions": ["D", "2D", "3D", "W", "3W", "M", "6M"],
        }

        async def mock_get(path: str, params: dict | None = None) -> Any:
            return _MockResponse(200, raw_config)

        monkeypatch.setattr(adapter._client, "get", mock_get)

        config = await adapter._fetch_config()
        assert adapter._supports_search is True
        assert adapter.supports_marks is True
        assert adapter.supports_timescale_marks is True
        assert adapter.supports_time is True
        assert config["supported_resolutions"] == ["D", "2D", "3D", "W", "3W", "M", "6M"]
        assert len(config["exchanges"]) == 2

    async def test_get_config_uses_cache(self, adapter: UDFAdapter) -> None:
        adapter._config = {"foo": "bar"}
        assert await adapter.get_config() == {"foo": "bar"}

    async def test_get_config_without_cache_calls_fetch(self, adapter: UDFAdapter) -> None:
        adapter._config = None

        async def fake_fetch() -> dict[str, Any]:
            adapter._config = {"x": 1}
            return adapter._config

        adapter._fetch_config = fake_fetch  # type: ignore[method-assign]
        assert await adapter.get_config() == {"x": 1}


class TestUDFAdapterResolve:
    async def test_resolve_maps_hyphen_keys(
        self, adapter: UDFAdapter, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        raw_symbol = {
            "name": "AAPL",
            "description": "Apple Inc",
            "exchange": "NASDAQ",
            "type": "stock",
            "session-regular": "0930-1600",
            "has-intraday": True,
            "has-daily": True,
            "has-weekly-and-monthly": True,
            "supported-resolutions": ["1", "5", "15", "30", "60", "D", "W", "M"],
            "minmovement": 1,
            "pricescale": 100,
            "timezone": "America/New_York",
        }

        async def mock_get(path: str, params: dict | None = None) -> Any:
            return _MockResponse(200, raw_symbol)

        monkeypatch.setattr(adapter._client, "get", mock_get)
        info = await adapter.resolve_symbol("AAPL")
        assert info["name"] == "AAPL"
        assert info["session"] == "0930-1600"
        assert info["has_intraday"] is True
        assert info["supported_resolutions"] == ["1", "5", "15", "30", "60", "D", "W", "M"]
        assert info["minmov"] == 1


class TestUDFAdapterSearch:
    async def test_search_returns_items(
        self, adapter: UDFAdapter, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        raw_results = [
            {
                "symbol": "AAPL",
                "full_name": "NASDAQ:AAPL",
                "description": "Apple Inc",
                "exchange": "NASDAQ",
                "type": "stock",
            },
            {
                "symbol": "AA",
                "full_name": "NYSE:AA",
                "description": "Alcoa",
                "exchange": "NYSE",
                "type": "stock",
            },
        ]

        async def mock_get(path: str = "", params: dict | None = None) -> Any:
            return _MockResponse(200, raw_results)

        monkeypatch.setattr(adapter._client, "get", mock_get)
        items = await adapter.search_symbols("AA", limit=10)
        assert len(items) == 2
        assert items[0]["symbol"] == "AAPL"


class TestUDFAdapterHistory:
    async def test_parse_history_ok(
        self, adapter: UDFAdapter, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        raw_response = {
            "s": "ok",
            "t": [1386493512, 1386493572],
            "c": [42.1, 43.4],
            "o": [41.0, 42.9],
            "h": [43.0, 44.1],
            "l": [40.4, 42.1],
            "v": [12000, 18500],
        }

        async def mock_get(path: str, params: dict | None = None) -> Any:
            return _MockResponse(200, raw_response)

        monkeypatch.setattr(adapter._client, "get", mock_get)
        result = await adapter.get_bars("AAPL", "D", 1386493512, 1386493999)
        assert result["status"] == "ok"
        assert len(result["bars"]) == 2
        assert result["bars"][0]["time"] == 1386493512
        assert result["bars"][0]["open"] == 41.0
        assert result["bars"][0]["volume"] == 12000

    async def test_parse_history_no_data(
        self, adapter: UDFAdapter, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def mock_get(path: str, params: dict | None = None) -> Any:
            return _MockResponse(200, {"s": "no_data", "nextTime": 1428001140000})

        monkeypatch.setattr(adapter._client, "get", mock_get)
        result = await adapter.get_bars("AAPL", "1", 100, 200)
        assert result["status"] == "no_data"
        assert result["no_data"] is True
        assert result["next_time"] == 1428001140000

    async def test_parse_history_ok_with_no_data_flag(
        self, adapter: UDFAdapter, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """UDF servers can return bars AND noData=true to signal the oldest bar."""
        raw_response = {
            "s": "ok",
            "t": [1386493512],
            "c": [42.1],
            "o": [41.0],
            "h": [43.0],
            "l": [40.4],
            "v": [12000],
            "noData": True,
        }

        async def mock_get(path: str, params: dict | None = None) -> Any:
            return _MockResponse(200, raw_response)

        monkeypatch.setattr(adapter._client, "get", mock_get)
        result = await adapter.get_bars("AAPL", "D", 1386493512, 1386493999)
        assert result["status"] == "ok"
        assert result["no_data"] is True

    async def test_parse_history_error(
        self, adapter: UDFAdapter, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def mock_get(path: str, params: dict | None = None) -> Any:
            return _MockResponse(200, {"s": "error", "errmsg": "Invalid symbol"})

        monkeypatch.setattr(adapter._client, "get", mock_get)
        result = await adapter.get_bars("INVALID", "D", 100, 200)
        assert result["status"] == "error"
        assert result["error"] == "Invalid symbol"

    async def test_resolution_rejection_aggregates_base(
        self, adapter: UDFAdapter, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When the server rejects a fine resolution, the adapter must retry
        with the decomposed base resolution and aggregate client-side."""
        call_count = {"n": 0}

        async def mock_get(path: str, params: dict | None = None) -> Any:
            call_count["n"] += 1
            if call_count["n"] == 1:
                return _MockResponse(200, {"s": "error", "errmsg": "Unsupported resolution"})
            return _MockResponse(
                200,
                {
                    "s": "ok",
                    "t": [100, 200, 300, 400],
                    "c": [10.0, 11.0, 12.0, 13.0],
                    "o": [9.0, 10.0, 11.0, 12.0],
                    "h": [11.0, 12.0, 13.0, 14.0],
                    "l": [8.0, 9.0, 10.0, 11.0],
                    "v": [100, 200, 300, 400],
                },
            )

        monkeypatch.setattr(adapter._client, "get", mock_get)
        result = await adapter.get_bars("AAPL", "3m", 100, 1000)
        assert call_count["n"] == 2
        assert result["status"] == "ok"
        # 4 bars / 3 = 2 chunks
        assert len(result["bars"]) >= 1

    async def test_resolution_error_no_multiplier_no_retry(
        self, adapter: UDFAdapter, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def mock_get(path: str, params: dict | None = None) -> Any:
            return _MockResponse(200, {"s": "error", "errmsg": "Unsupported resolution"})

        monkeypatch.setattr(adapter._client, "get", mock_get)
        # "D" decomposes to ("D", 1) — multiplier 1 means no retry.
        result = await adapter.get_bars("AAPL", "1d", 100, 1000)
        assert result["status"] == "error"

    async def test_uses_max_bars_from_config(
        self, adapter: UDFAdapter, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        adapter._config = {"max_bars": 500}

        async def mock_get(path: str, params: dict | None = None) -> Any:
            return _MockResponse(
                200, {"s": "ok", "t": [], "c": [], "o": [], "h": [], "l": [], "v": []}
            )

        monkeypatch.setattr(adapter._client, "get", mock_get)
        await adapter.get_bars("AAPL", "1d", 100, 1000, countback=1000)

    async def test_from_ts_zero_uses_estimate(
        self, adapter: UDFAdapter, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, Any] = {}

        async def mock_get(path: str, params: dict | None = None) -> Any:
            captured.update(params or {})
            return _MockResponse(
                200, {"s": "ok", "t": [], "c": [], "o": [], "h": [], "l": [], "v": []}
            )

        monkeypatch.setattr(adapter._client, "get", mock_get)
        await adapter.get_bars("AAPL", "1d", 0, 1_700_000_000, countback=10)
        # from_ts started at 0; _estimate_from_ts should bump it.
        assert captured.get("from", 0) > 0


class TestUDFAdapterHistoryHTTPErrors:
    async def test_4xx_with_json_error_body(
        self, adapter: UDFAdapter, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def mock_get(path: str, params: dict | None = None) -> Any:
            return _MockResponse(400, {"s": "error", "errmsg": "Bad request"})

        monkeypatch.setattr(adapter._client, "get", mock_get)
        result = await adapter.get_bars("AAPL", "1d", 100, 200)
        assert result["status"] == "error"

    async def test_5xx_with_unparseable_body_raises(
        self, adapter: UDFAdapter, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def mock_get(path: str, params: dict | None = None) -> Any:
            return _MockResponse(500, "not-json", raise_on_json=True)

        monkeypatch.setattr(adapter._client, "get", mock_get)
        with pytest.raises(httpx.HTTPStatusError):
            await adapter.get_bars("AAPL", "1d", 100, 200)

    async def test_4xx_ok_status_raises_on_status(
        self, adapter: UDFAdapter, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def mock_get(path: str, params: dict | None = None) -> Any:
            return _MockResponse(
                400, {"s": "ok", "t": [], "c": [], "o": [], "h": [], "l": [], "v": []}
            )

        monkeypatch.setattr(adapter._client, "get", mock_get)
        with pytest.raises(httpx.HTTPStatusError):
            await adapter.get_bars("AAPL", "1d", 100, 200)

    async def test_200_with_unparseable_body_returns_bad_response(
        self, adapter: UDFAdapter, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def mock_get(path: str, params: dict | None = None) -> Any:
            return _MockResponse(200, "garbage", raise_on_json=True)

        monkeypatch.setattr(adapter._client, "get", mock_get)
        result = await adapter.get_bars("AAPL", "1d", 100, 200)
        assert result["status"] == "error"
        assert result["error"] == "Bad response"


class TestUDFAdapterMarks:
    async def test_columnar(self, adapter: UDFAdapter, monkeypatch: pytest.MonkeyPatch) -> None:
        raw_marks = {
            "id": [1, 2],
            "time": [1000, 2000],
            "color": "red",
            "text": ["Mark 1", "Mark 2"],
            "label": ["A", "B"],
            "labelFontColor": "white",
            "minSize": 14,
        }

        async def mock_get(path: str = "", params: dict | None = None) -> Any:
            return _MockResponse(200, raw_marks)

        monkeypatch.setattr(adapter._client, "get", mock_get)
        marks = await adapter.get_marks("AAPL", 0, 9999, "D")
        assert len(marks) == 2
        assert marks[0]["id"] == 1
        assert marks[0]["color"] == "red"
        assert marks[1]["text"] == "Mark 2"

    async def test_array_passthrough(
        self, adapter: UDFAdapter, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        raw_marks = [
            {"id": 1, "time": 1000, "color": "blue", "text": "A"},
            {"id": 2, "time": 2000, "color": "green", "text": "B"},
        ]

        async def mock_get(path: str = "", params: dict | None = None) -> Any:
            return _MockResponse(200, raw_marks)

        monkeypatch.setattr(adapter._client, "get", mock_get)
        marks = await adapter.get_marks("AAPL", 0, 9999, "D")
        assert len(marks) == 2
        assert marks[0]["color"] == "blue"


class TestUDFAdapterTimescaleMarks:
    async def test_columnar(self, adapter: UDFAdapter, monkeypatch: pytest.MonkeyPatch) -> None:
        raw = {
            "id": [1, 2],
            "time": [1000, 2000],
            "color": "red",
            "label": ["A", "B"],
            "tooltip": [["Tip 1"], ["Tip 2"]],
        }

        async def mock_get(path: str = "", params: dict | None = None) -> Any:
            return _MockResponse(200, raw)

        monkeypatch.setattr(adapter._client, "get", mock_get)
        marks = await adapter.get_timescale_marks("AAPL", 0, 9999, "D")
        assert len(marks) == 2

    async def test_array(self, adapter: UDFAdapter, monkeypatch: pytest.MonkeyPatch) -> None:
        async def mock_get(path: str = "", params: dict | None = None) -> Any:
            return _MockResponse(200, [{"id": 1, "time": 1000, "color": "blue", "label": "A"}])

        monkeypatch.setattr(adapter._client, "get", mock_get)
        marks = await adapter.get_timescale_marks("AAPL", 0, 9999, "D")
        assert len(marks) == 1


class TestUDFAdapterServerTime:
    async def test_get_server_time(
        self, adapter: UDFAdapter, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class _TextResp:
            status_code = 200
            text = "1700000000\n"

            def raise_for_status(self) -> None:
                pass

        async def mock_get(path: str) -> Any:
            return _TextResp()

        monkeypatch.setattr(adapter._client, "get", mock_get)
        ts = await adapter.get_server_time()
        assert ts == 1700000000


class TestUDFAdapterQuotes:
    async def test_quotes_ok(self, adapter: UDFAdapter, monkeypatch: pytest.MonkeyPatch) -> None:
        raw = {
            "s": "ok",
            "d": [
                {
                    "s": "ok",
                    "n": "NYSE:AA",
                    "v": {
                        "ch": 0.16,
                        "chp": 0.98,
                        "short_name": "AA",
                        "exchange": "NYSE",
                        "description": "Alcoa Inc.",
                        "lp": 16.57,
                        "volume": 4029041,
                    },
                },
            ],
        }

        async def mock_get(path: str, params: dict | None = None) -> Any:
            return _MockResponse(200, raw)

        monkeypatch.setattr(adapter._client, "get", mock_get)
        quotes = await adapter._get_quotes(["NYSE:AA"])
        assert len(quotes) == 1
        assert quotes[0].symbol == "NYSE:AA"
        assert quotes[0].last_price == 16.57

    async def test_quotes_error(self, adapter: UDFAdapter, monkeypatch: pytest.MonkeyPatch) -> None:
        async def mock_get(path: str, params: dict | None = None) -> Any:
            return _MockResponse(200, {"s": "error", "errmsg": "Bad request"})

        monkeypatch.setattr(adapter._client, "get", mock_get)
        assert await adapter._get_quotes(["BAD"]) == []


# =============================================================================
# Subscription / quote lifecycle (no actual polling — fake Timer)
# =============================================================================


class TestSubscriptionLifecycle:
    def test_on_subscribe_no_polling_when_interval_none(self) -> None:
        adapter = UDFAdapter("https://example.com", poll_interval=None)
        adapter.on_subscribe(listener_guid="g1", symbol="AAPL", resolution="D", chart_id="c1")
        assert adapter._subscriptions["g1"]["symbol"] == "AAPL"
        assert "g1" not in adapter._poll_timers

    def test_on_subscribe_with_poll_interval_starts_poll(self) -> None:
        adapter = UDFAdapter("https://example.com", poll_interval=10.0)

        with patch.object(adapter, "_start_bar_poll") as mock_start:
            adapter.on_subscribe(listener_guid="g1", symbol="AAPL", resolution="D", chart_id=None)
        mock_start.assert_called_once_with("g1")

    def test_on_unsubscribe_clears(self, adapter: UDFAdapter) -> None:
        adapter.on_subscribe(listener_guid="g1", symbol="AAPL", resolution="D", chart_id=None)
        adapter.on_unsubscribe("g1")
        assert "g1" not in adapter._subscriptions

    def test_on_unsubscribe_unknown_id_no_op(self, adapter: UDFAdapter) -> None:
        adapter.on_unsubscribe("nonexistent")  # no error

    def test_subscribe_quotes_register(self, adapter: UDFAdapter) -> None:
        cb = MagicMock()
        adapter.subscribe_quotes(["AAPL", "MSFT"], on_quote=cb)
        assert "AAPL" in adapter._quote_symbols
        assert adapter._on_quote is cb

    def test_subscribe_quotes_preserves_existing_callback(self, adapter: UDFAdapter) -> None:
        cb = MagicMock()
        adapter.subscribe_quotes(["AAPL"], on_quote=cb)
        adapter.subscribe_quotes(["MSFT"])  # no callback supplied
        assert adapter._on_quote is cb

    def test_unsubscribe_quotes_specific(self, adapter: UDFAdapter) -> None:
        adapter.subscribe_quotes(["AAPL", "MSFT"])
        adapter.unsubscribe_quotes(["AAPL"])
        assert "AAPL" not in adapter._quote_symbols
        assert "MSFT" in adapter._quote_symbols

    def test_unsubscribe_quotes_all(self, adapter: UDFAdapter) -> None:
        adapter.subscribe_quotes(["AAPL", "MSFT"])
        adapter.unsubscribe_quotes(None)
        assert not adapter._quote_symbols


class TestStartBarPoll:
    def test_no_op_when_closed(self) -> None:
        adapter = UDFAdapter("https://example.com", poll_interval=1.0)
        adapter._closed = True
        adapter._subscriptions["g1"] = {"symbol": "AAPL", "resolution": "D", "chartId": None}
        adapter._start_bar_poll("g1")
        assert "g1" not in adapter._poll_timers

    def test_no_op_when_no_interval(self) -> None:
        adapter = UDFAdapter("https://example.com", poll_interval=None)
        adapter._subscriptions["g1"] = {"symbol": "AAPL", "resolution": "D", "chartId": None}
        adapter._start_bar_poll("g1")
        assert "g1" not in adapter._poll_timers

    def test_schedules_timer(self) -> None:
        adapter = UDFAdapter("https://example.com", poll_interval=10.0)
        adapter._subscriptions["g1"] = {"symbol": "AAPL", "resolution": "D", "chartId": None}

        _FakeTimer.instances.clear()
        with patch("pywry.tvchart.udf.threading.Timer", _FakeTimer):
            adapter._start_bar_poll("g1")
        assert "g1" in adapter._poll_timers

    def test_stop_bar_poll_cancels_timer(self, adapter: UDFAdapter) -> None:
        timer = MagicMock()
        adapter._poll_timers["g1"] = timer
        adapter._stop_bar_poll("g1")
        timer.cancel.assert_called_once()

    def test_stop_bar_poll_unknown_id_no_op(self, adapter: UDFAdapter) -> None:
        adapter._stop_bar_poll("nonexistent")


class TestBarPollCallback:
    """Drive the inner ``_poll`` closure captured by the fake Timer."""

    def test_emits_bar_update(self) -> None:
        adapter = UDFAdapter("https://example.com", poll_interval=10.0)
        adapter._subscriptions["g1"] = {
            "symbol": "AAPL",
            "resolution": "D",
            "chartId": "c1",
        }

        async def mock_get_bars(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
            return {"bars": [{"time": 1, "close": 5.0}], "status": "ok"}

        adapter.get_bars = mock_get_bars  # type: ignore[method-assign]
        app = MagicMock()
        adapter._app = app

        _FakeTimer.instances.clear()
        with patch("pywry.tvchart.udf.threading.Timer", _FakeTimer):
            adapter._start_bar_poll("g1")
        # The first FakeTimer captures the inner _poll function.
        _FakeTimer.instances[0].fn()
        app.respond_tvchart_bar_update.assert_called_once()

    def test_returns_early_when_subscription_removed(self) -> None:
        adapter = UDFAdapter("https://example.com", poll_interval=10.0)
        adapter._subscriptions["g1"] = {
            "symbol": "AAPL",
            "resolution": "D",
            "chartId": None,
        }

        _FakeTimer.instances.clear()
        with patch("pywry.tvchart.udf.threading.Timer", _FakeTimer):
            adapter._start_bar_poll("g1")
        adapter._subscriptions.pop("g1")
        # Should be a no-op; no exception.
        _FakeTimer.instances[0].fn()

    def test_swallows_get_bars_exception(self) -> None:
        adapter = UDFAdapter("https://example.com", poll_interval=10.0)
        adapter._subscriptions["g1"] = {
            "symbol": "AAPL",
            "resolution": "D",
            "chartId": None,
        }

        async def failing_get_bars(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
            raise RuntimeError("boom")

        adapter.get_bars = failing_get_bars  # type: ignore[method-assign]

        _FakeTimer.instances.clear()
        with patch("pywry.tvchart.udf.threading.Timer", _FakeTimer):
            adapter._start_bar_poll("g1")
        _FakeTimer.instances[0].fn()  # exception swallowed


class TestStartQuotePolling:
    def test_no_op_when_closed(self) -> None:
        adapter = UDFAdapter("https://example.com", quote_interval=1.0)
        adapter._closed = True
        adapter._quote_symbols.add("AAPL")
        adapter._start_quote_polling()
        assert adapter._quote_timer is None

    def test_no_op_without_interval(self) -> None:
        adapter = UDFAdapter("https://example.com", quote_interval=None)
        adapter._quote_symbols.add("AAPL")
        adapter._start_quote_polling()
        assert adapter._quote_timer is None

    def test_no_op_without_symbols(self) -> None:
        adapter = UDFAdapter("https://example.com", quote_interval=1.0)
        adapter._start_quote_polling()
        assert adapter._quote_timer is None

    def test_schedules_timer(self) -> None:
        adapter = UDFAdapter("https://example.com", quote_interval=60.0)
        adapter._quote_symbols.add("AAPL")

        _FakeTimer.instances.clear()
        with patch("pywry.tvchart.udf.threading.Timer", _FakeTimer):
            adapter._start_quote_polling()
        assert adapter._quote_timer is not None

    def test_stop_quote_polling(self) -> None:
        adapter = UDFAdapter("https://example.com")
        timer = MagicMock()
        adapter._quote_timer = timer
        adapter._stop_quote_polling()
        timer.cancel.assert_called_once()
        assert adapter._quote_timer is None

    def test_stop_quote_polling_no_op_when_none(self) -> None:
        adapter = UDFAdapter("https://example.com")
        adapter._quote_timer = None
        adapter._stop_quote_polling()


class TestQuotePollCallback:
    def test_invokes_callback(self) -> None:
        adapter = UDFAdapter("https://example.com", quote_interval=60.0)
        adapter._quote_symbols.add("AAPL")

        async def mock_get_quotes(symbols: list[str]) -> list[QuoteData]:
            return [QuoteData(n="AAPL", s="ok", v={"lp": 100.0})]

        adapter._get_quotes = mock_get_quotes  # type: ignore[method-assign]
        captured: list[Any] = []
        adapter._on_quote = lambda qs: captured.extend(qs)

        _FakeTimer.instances.clear()
        with patch("pywry.tvchart.udf.threading.Timer", _FakeTimer):
            adapter._start_quote_polling()
        _FakeTimer.instances[0].fn()
        assert len(captured) == 1
        assert captured[0].symbol == "AAPL"

    def test_swallows_exception(self) -> None:
        adapter = UDFAdapter("https://example.com", quote_interval=60.0)
        adapter._quote_symbols.add("AAPL")

        async def failing_get_quotes(_symbols: list[str]) -> list[QuoteData]:
            raise RuntimeError("err")

        adapter._get_quotes = failing_get_quotes  # type: ignore[method-assign]

        _FakeTimer.instances.clear()
        with patch("pywry.tvchart.udf.threading.Timer", _FakeTimer):
            adapter._start_quote_polling()
        _FakeTimer.instances[0].fn()  # no exception

    def test_returns_when_closed(self) -> None:
        adapter = UDFAdapter("https://example.com", quote_interval=60.0)
        adapter._quote_symbols.add("AAPL")

        _FakeTimer.instances.clear()
        with patch("pywry.tvchart.udf.threading.Timer", _FakeTimer):
            adapter._start_quote_polling()
        adapter._closed = True
        _FakeTimer.instances[0].fn()  # returns early


# =============================================================================
# Close + connect
# =============================================================================


class TestUDFAdapterClose:
    def test_close_cancels_timers_and_clears_state(self) -> None:
        adapter = UDFAdapter("https://example.com")
        timer = MagicMock()
        adapter._poll_timers["g1"] = timer
        adapter._subscriptions["g1"] = {"symbol": "AAPL", "resolution": "D", "chartId": None}
        adapter._quote_timer = MagicMock()

        adapter.close()
        timer.cancel.assert_called_once()
        assert adapter._closed is True
        assert not adapter._subscriptions

    def test_close_idempotent(self) -> None:
        adapter = UDFAdapter("https://example.com")
        adapter.close()
        adapter.close()  # no error

    def test_properties_before_connect(self) -> None:
        adapter = UDFAdapter("https://example.com")
        assert adapter.config is None
        assert adapter.supports_marks is False
        assert adapter.supports_time is False
        assert adapter.supports_search is True


class TestUDFAdapterConnect:
    def test_invokes_show_tvchart(self) -> None:
        from pywry.models import ThemeMode

        adapter = UDFAdapter("https://example.com")

        async def fake_fetch() -> dict[str, Any]:
            adapter._config = {"supported_resolutions": ["1", "5", "60", "D"]}
            adapter._supports_search = True
            return adapter._config

        adapter._fetch_config = fake_fetch  # type: ignore[method-assign]

        app = MagicMock()
        app._theme = ThemeMode.DARK
        app.show_tvchart = MagicMock(return_value="window-handle")

        result = adapter.connect(app, symbol="AAPL", resolution="D")
        assert result == "window-handle"
        app.show_tvchart.assert_called_once()
        kwargs = app.show_tvchart.call_args.kwargs
        assert kwargs["provider"] is adapter
        assert kwargs["symbol"] == "AAPL"
        assert kwargs["resolution"] == "1d"  # UDF "D" → canonical "1d"
        assert "toolbars" in kwargs

    def test_keeps_explicit_toolbars(self) -> None:
        from pywry.models import ThemeMode

        adapter = UDFAdapter("https://example.com")

        async def fake_fetch() -> dict[str, Any]:
            adapter._config = {}
            return adapter._config

        adapter._fetch_config = fake_fetch  # type: ignore[method-assign]

        app = MagicMock()
        app._theme = ThemeMode.LIGHT
        app.show_tvchart = MagicMock(return_value="x")

        adapter.connect(app, symbol="AAPL", resolution="D", toolbars=["mine"])
        kwargs = app.show_tvchart.call_args.kwargs
        assert kwargs["toolbars"] == ["mine"]

    def test_starts_quote_polling_when_configured(self) -> None:
        from pywry.models import ThemeMode

        adapter = UDFAdapter("https://example.com", quote_interval=60.0)
        adapter._quote_symbols = {"AAPL"}

        async def fake_fetch() -> dict[str, Any]:
            adapter._config = {}
            return adapter._config

        adapter._fetch_config = fake_fetch  # type: ignore[method-assign]

        app = MagicMock()
        app._theme = ThemeMode.DARK
        app.show_tvchart = MagicMock(return_value="x")

        with patch.object(adapter, "_start_quote_polling") as mock_start:
            adapter.connect(app, symbol="AAPL", resolution="D")
        mock_start.assert_called_once()

    def test_app_theme_string_accepted(self) -> None:
        adapter = UDFAdapter("https://example.com")

        async def fake_fetch() -> dict[str, Any]:
            adapter._config = {"supported_resolutions": ["D"]}
            return adapter._config

        adapter._fetch_config = fake_fetch  # type: ignore[method-assign]

        app = MagicMock()
        app._theme = "light"  # plain string, no .value
        app.show_tvchart = MagicMock(return_value="x")

        adapter.connect(app, symbol="X", resolution="D")
        # Should not raise.
