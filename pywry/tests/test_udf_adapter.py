"""Unit tests for pywry.tvchart.udf (UDF adapter)."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from pywry.tvchart.udf import (
    QuoteData,
    UDFAdapter,
    from_udf_resolution,
    parse_udf_columns,
    to_udf_resolution,
)


# ---------------------------------------------------------------------------
# Resolution mapping
# ---------------------------------------------------------------------------


class TestResolutionMapping:
    """Tests for to_udf_resolution / from_udf_resolution."""

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


# ---------------------------------------------------------------------------
# UDF columnar parsing
# ---------------------------------------------------------------------------


class TestParseUDFColumns:
    """Tests for parse_udf_columns."""

    def test_basic_table(self) -> None:
        data = {
            "t": [100, 200, 300],
            "c": [10.0, 20.0, 30.0],
            "v": [1000, 2000, 3000],
        }
        rows = parse_udf_columns(data)
        assert len(rows) == 3
        assert rows[0] == {"t": 100, "c": 10.0, "v": 1000}
        assert rows[2] == {"t": 300, "c": 30.0, "v": 3000}

    def test_scalar_broadcast(self) -> None:
        data = {
            "symbol": ["AAPL", "MSFT"],
            "exchange": "NASDAQ",
            "pricescale": 100,
        }
        rows = parse_udf_columns(data)
        assert len(rows) == 2
        assert rows[0] == {"symbol": "AAPL", "exchange": "NASDAQ", "pricescale": 100}
        assert rows[1] == {"symbol": "MSFT", "exchange": "NASDAQ", "pricescale": 100}

    def test_empty_data(self) -> None:
        assert parse_udf_columns({}) == []
        assert parse_udf_columns({"scalar": 42}) == []

    def test_explicit_count(self) -> None:
        data = {"val": 99}
        rows = parse_udf_columns(data, count=3)
        assert len(rows) == 3
        assert all(r["val"] == 99 for r in rows)

    def test_mixed_scalar_and_list(self) -> None:
        data = {
            "id": [1, 2],
            "time": [1000, 2000],
            "color": "red",
            "label": ["A", "B"],
        }
        rows = parse_udf_columns(data)
        assert len(rows) == 2
        assert rows[0] == {"id": 1, "time": 1000, "color": "red", "label": "A"}
        assert rows[1] == {"id": 2, "time": 2000, "color": "red", "label": "B"}


# ---------------------------------------------------------------------------
# QuoteData
# ---------------------------------------------------------------------------


class TestQuoteData:
    """Tests for the QuoteData value object."""

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

    def test_format_ticker_html_no_change(self) -> None:
        q = QuoteData(n="X", s="ok", v={"short_name": "X", "lp": 10.0})
        html = q.format_ticker_html(show_change=True)
        assert "10.00" in html
        # No change data → just price, no color spans
        assert "span" not in html

    def test_empty_quote(self) -> None:
        q = QuoteData(n="", s="error", v={}, errmsg="not found")
        assert q.status == "error"
        assert q.error == "not found"
        assert q.last_price is None


# ---------------------------------------------------------------------------
# UDFAdapter — unit tests with mocked HTTP
# ---------------------------------------------------------------------------


class TestUDFAdapterBarParsing:
    """Test the bar-parsing logic in get_bars."""

    @pytest.fixture()
    def adapter(self) -> UDFAdapter:
        return UDFAdapter("https://example.com")

    @pytest.mark.asyncio()
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
        bar0 = result["bars"][0]
        assert bar0["time"] == 1386493512  # Unix seconds (not ms)
        assert bar0["open"] == 41.0
        assert bar0["close"] == 42.1
        assert bar0["volume"] == 12000

    @pytest.mark.asyncio()
    async def test_parse_history_no_data(
        self, adapter: UDFAdapter, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        raw_response = {"s": "no_data", "nextTime": 1428001140000}

        async def mock_get(path: str, params: dict | None = None) -> Any:
            return _MockResponse(200, raw_response)

        monkeypatch.setattr(adapter._client, "get", mock_get)

        result = await adapter.get_bars("AAPL", "1", 100, 200)
        assert result["status"] == "no_data"
        assert result["no_data"] is True
        assert result["next_time"] == 1428001140000

    @pytest.mark.asyncio()
    async def test_parse_history_ok_with_no_data_flag(
        self,
        adapter: UDFAdapter,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """UDF servers can return bars AND noData=true to signal oldest data."""
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
        assert len(result["bars"]) == 1
        assert result["no_data"] is True  # Server's noData flag preserved
        assert result["bars"][0]["time"] == 1386493512

    @pytest.mark.asyncio()
    async def test_parse_history_error(
        self, adapter: UDFAdapter, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        raw_response = {"s": "error", "errmsg": "Invalid symbol"}

        async def mock_get(path: str, params: dict | None = None) -> Any:
            return _MockResponse(200, raw_response)

        monkeypatch.setattr(adapter._client, "get", mock_get)

        result = await adapter.get_bars("INVALID", "D", 100, 200)
        assert result["status"] == "error"
        assert result["error"] == "Invalid symbol"


class TestUDFAdapterConfig:
    """Test config parsing from /config."""

    @pytest.fixture()
    def adapter(self) -> UDFAdapter:
        return UDFAdapter("https://example.com")

    @pytest.mark.asyncio()
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
        assert adapter._supports_marks is True
        assert adapter._supports_timescale_marks is True
        assert adapter._supports_time is True
        assert config["supported_resolutions"] == ["D", "2D", "3D", "W", "3W", "M", "6M"]
        assert len(config["exchanges"]) == 2
        # supports_search and supports_group_request must be forwarded to frontend
        assert config["supports_search"] is True


class TestUDFAdapterResolve:
    """Test symbol resolution and key mapping."""

    @pytest.fixture()
    def adapter(self) -> UDFAdapter:
        return UDFAdapter("https://example.com")

    @pytest.mark.asyncio()
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
        assert info["has_daily"] is True
        assert info["has_weekly_and_monthly"] is True
        assert info["supported_resolutions"] == ["1", "5", "15", "30", "60", "D", "W", "M"]
        assert info["minmov"] == 1


class TestUDFAdapterSearch:
    """Test symbol search."""

    @pytest.fixture()
    def adapter(self) -> UDFAdapter:
        return UDFAdapter("https://example.com")

    @pytest.mark.asyncio()
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


class TestUDFAdapterMarks:
    """Test marks parsing."""

    @pytest.fixture()
    def adapter(self) -> UDFAdapter:
        return UDFAdapter("https://example.com")

    @pytest.mark.asyncio()
    async def test_marks_columnar(
        self, adapter: UDFAdapter, monkeypatch: pytest.MonkeyPatch
    ) -> None:
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

    @pytest.mark.asyncio()
    async def test_marks_array_passthrough(
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


class TestUDFAdapterQuotes:
    """Test quotes endpoint parsing."""

    @pytest.fixture()
    def adapter(self) -> UDFAdapter:
        return UDFAdapter("https://example.com")

    @pytest.mark.asyncio()
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
        assert quotes[0].change == 0.16

    @pytest.mark.asyncio()
    async def test_quotes_error(self, adapter: UDFAdapter, monkeypatch: pytest.MonkeyPatch) -> None:
        raw = {"s": "error", "errmsg": "Bad request"}

        async def mock_get(path: str, params: dict | None = None) -> Any:
            return _MockResponse(200, raw)

        monkeypatch.setattr(adapter._client, "get", mock_get)

        quotes = await adapter._get_quotes(["BAD"])
        assert quotes == []


class TestUDFAdapterLifecycle:
    """Test adapter lifecycle methods."""

    def test_close_idempotent(self) -> None:
        adapter = UDFAdapter("https://example.com")
        adapter.close()
        assert adapter._closed is True
        # Second close should not raise
        adapter.close()

    def test_properties_before_connect(self) -> None:
        adapter = UDFAdapter("https://example.com")
        assert adapter.config is None
        assert adapter.supports_marks is False
        assert adapter.supports_time is False
        assert adapter.supports_search is True


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


class _MockResponse:
    """Minimal mock for httpx.Response."""

    def __init__(self, status_code: int, json_data: Any) -> None:
        self.status_code = status_code
        self._json = json_data
        self.text = str(json_data)

    def json(self) -> Any:
        return self._json

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=httpx.Request("GET", "https://example.com"),
                response=self,  # type: ignore
            )
