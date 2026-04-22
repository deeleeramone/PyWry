"""Tests for TradingView Lightweight Charts integration.

Tests:
- TVChartConfig and sub-model serialization (snake_case to camelCase)
- normalize_ohlcv() for list-of-dicts, dict-of-lists, edge cases
- TVChartData properties (bars, volume, series_ids, total_rows)
- _serialize_timestamp() and _serialize_ohlcv_value() helpers
- _resolve_ohlcv_columns() alias resolution
- build_tvchart_toolbars() factory validation
- TVChartStateMixin event emission
- PyWryTVChartWidget class shape
- show_tvchart function signature and basic wiring
- Public API imports from pywry.__init__
"""

# pylint: disable=missing-function-docstring,redefined-outer-name,disallowed-name

from __future__ import annotations

import json

from datetime import datetime, timezone
from typing import Any

import pytest

from pywry.tvchart import (
    TVChartBar,
    TVChartData,
    TVChartDatafeedBarUpdate,
    TVChartDatafeedConfigRequest,
    TVChartDatafeedConfigResponse,
    TVChartDatafeedConfiguration,
    TVChartDatafeedHistoryRequest,
    TVChartDatafeedHistoryResponse,
    TVChartDatafeedMarksRequest,
    TVChartDatafeedMarksResponse,
    TVChartDatafeedResolveRequest,
    TVChartDatafeedResolveResponse,
    TVChartDatafeedSearchRequest,
    TVChartDatafeedSearchResponse,
    TVChartDatafeedServerTimeRequest,
    TVChartDatafeedServerTimeResponse,
    TVChartDatafeedSubscribeRequest,
    TVChartDatafeedSymbolType,
    TVChartDatafeedTimescaleMarksRequest,
    TVChartDatafeedTimescaleMarksResponse,
    TVChartDatafeedUnsubscribeRequest,
    TVChartExchange,
    TVChartLibrarySubsessionInfo,
    TVChartMark,
    TVChartSearchSymbolResultItem,
    TVChartSeriesData,
    TVChartStateMixin,
    TVChartSymbolInfo,
    TVChartSymbolInfoPriceSource,
    TVChartTimescaleMark,
    build_tvchart_toolbars,
    normalize_ohlcv,
)
from pywry.tvchart.config import (
    CrosshairConfig,
    CrosshairMode,
    LayoutConfig,
    PriceScaleConfig,
    PriceScaleMode,
    SeriesConfig,
    SeriesType,
    TimeScaleConfig,
    TVChartConfig,
    WatermarkConfig,
)
from pywry.tvchart.normalize import (
    _resolve_ohlcv_columns,
    _serialize_bar,
    _serialize_ohlcv_value,
    _serialize_series_from_rows,
    _serialize_timestamp,
)


# =============================================================================
# Fixtures
# =============================================================================


def _make_ohlcv_rows(n: int = 5) -> list[dict[str, Any]]:
    """Generate synthetic OHLCV rows with Unix timestamps."""
    base_time = 1_700_000_000
    return [
        {
            "time": base_time + i * 86400,
            "open": 100.0 + i,
            "high": 105.0 + i,
            "low": 98.0 + i,
            "close": 103.0 + i,
            "volume": 1_000_000 + i * 10_000,
        }
        for i in range(n)
    ]


# =============================================================================
# TVChartConfig serialization tests
# =============================================================================


class TestTVChartConfigSerialization:
    """Verify Pydantic models serialize snake_case to camelCase."""

    def test_series_type_enum_values(self):
        assert SeriesType.CANDLESTICK.value == "Candlestick"
        assert SeriesType.LINE.value == "Line"
        assert SeriesType.AREA.value == "Area"
        assert SeriesType.HISTOGRAM.value == "Histogram"

    def test_series_config_camel_case(self):
        cfg = SeriesConfig(
            series_type=SeriesType.LINE,
            price_scale_id="left",
            up_color="#00ff00",
            down_color="#ff0000",
        )
        d = cfg.model_dump(by_alias=True, exclude_none=True)
        assert "seriesType" in d
        assert d["seriesType"] == "Line"
        assert "priceScaleId" in d
        assert d["priceScaleId"] == "left"
        assert "upColor" in d
        assert "downColor" in d
        # No snake_case keys
        assert "series_type" not in d
        assert "price_scale_id" not in d

    def test_price_scale_config_defaults(self):
        cfg = PriceScaleConfig()
        d = cfg.model_dump(by_alias=True, exclude_none=True)
        assert d["autoScale"] is True
        assert d["mode"] == PriceScaleMode.NORMAL.value

    def test_time_scale_config_defaults(self):
        cfg = TimeScaleConfig()
        d = cfg.model_dump(by_alias=True, exclude_none=True)
        assert d["rightOffset"] == 5
        assert d["barSpacing"] == 6.0
        assert d["timeVisible"] is True

    def test_crosshair_config_defaults(self):
        cfg = CrosshairConfig()
        d = cfg.model_dump(by_alias=True, exclude_none=True)
        assert d["mode"] == CrosshairMode.MAGNET.value

    def test_layout_config_camel_case(self):
        cfg = LayoutConfig(text_color="#fff", font_size=14, font_family="Arial")
        d = cfg.model_dump(by_alias=True, exclude_none=True)
        assert "textColor" in d
        assert "fontSize" in d
        assert "fontFamily" in d
        assert "text_color" not in d

    def test_watermark_config_camel_case(self):
        cfg = WatermarkConfig(visible=True, text="AAPL", font_size=64)
        d = cfg.model_dump(by_alias=True, exclude_none=True)
        assert d["visible"] is True
        assert d["fontSize"] == 64
        assert "horzAlign" in d
        assert "vertAlign" in d

    def test_tvchart_config_nested(self):
        cfg = TVChartConfig(
            time_scale=TimeScaleConfig(right_offset=10),
            crosshair=CrosshairConfig(mode=CrosshairMode.NORMAL),
        )
        d = cfg.model_dump(by_alias=True, exclude_none=True)
        assert "timeScale" in d
        assert d["timeScale"]["rightOffset"] == 10
        assert "crosshair" in d
        assert d["crosshair"]["mode"] == CrosshairMode.NORMAL.value

    def test_tvchart_config_json_roundtrip(self):
        cfg = TVChartConfig(
            time_scale=TimeScaleConfig(right_offset=10),
            layout=LayoutConfig(text_color="#ccc"),
        )
        json_str = cfg.model_dump_json(by_alias=True, exclude_none=True)
        parsed = json.loads(json_str)
        assert "timeScale" in parsed
        assert parsed["layout"]["textColor"] == "#ccc"


# =============================================================================
# Timestamp serialization tests
# =============================================================================


class TestSerializeTimestamp:
    """Test the _serialize_timestamp helper function."""

    def test_int(self):
        assert _serialize_timestamp(1_700_000_000) == 1_700_000_000

    def test_float(self):
        assert _serialize_timestamp(1_700_000_000.5) == 1_700_000_000

    def test_nan_returns_none(self):
        assert _serialize_timestamp(float("nan")) is None

    def test_inf_returns_none(self):
        assert _serialize_timestamp(float("inf")) is None

    def test_none_returns_none(self):
        assert _serialize_timestamp(None) is None

    def test_datetime_utc(self):
        dt = datetime(2023, 11, 15, 0, 0, 0, tzinfo=timezone.utc)
        result = _serialize_timestamp(dt)
        assert result == int(dt.timestamp())

    def test_datetime_naive(self):
        dt = datetime(2023, 11, 15, 0, 0, 0)
        result = _serialize_timestamp(dt)
        assert result == int(dt.replace(tzinfo=timezone.utc).timestamp())

    def test_iso_string(self):
        result = _serialize_timestamp("2023-11-15T00:00:00")
        expected = int(datetime(2023, 11, 15, tzinfo=timezone.utc).timestamp())
        assert result == expected


# =============================================================================
# OHLCV value serialization tests
# =============================================================================


class TestSerializeOHLCVValue:
    """Test the _serialize_ohlcv_value helper function."""

    def test_float(self):
        assert _serialize_ohlcv_value(100.5) == 100.5

    def test_int(self):
        assert _serialize_ohlcv_value(100) == 100.0

    def test_nan_returns_none(self):
        assert _serialize_ohlcv_value(float("nan")) is None

    def test_inf_returns_none(self):
        assert _serialize_ohlcv_value(float("inf")) is None

    def test_none_returns_none(self):
        assert _serialize_ohlcv_value(None) is None

    def test_string_number(self):
        assert _serialize_ohlcv_value("42.5") == 42.5

    def test_invalid_string_returns_none(self):
        assert _serialize_ohlcv_value("not_a_number") is None


# =============================================================================
# Column alias resolution tests
# =============================================================================


class TestResolveOHLCVColumns:
    """Test column name alias resolution."""

    def test_standard_lowercase(self):
        cols = ["time", "open", "high", "low", "close", "volume"]
        result = _resolve_ohlcv_columns(cols)
        assert result["time"] == "time"
        assert result["open"] == "open"
        assert result["high"] == "high"
        assert result["low"] == "low"
        assert result["close"] == "close"
        assert result["volume"] == "volume"

    def test_capitalized(self):
        cols = ["Date", "Open", "High", "Low", "Close", "Volume"]
        result = _resolve_ohlcv_columns(cols)
        assert result["time"] == "Date"
        assert result["open"] == "Open"
        assert result["close"] == "Close"
        assert result["volume"] == "Volume"

    def test_single_letter(self):
        cols = ["t", "o", "h", "l", "c", "v"]
        result = _resolve_ohlcv_columns(cols)
        assert result["time"] == "t"
        assert result["open"] == "o"
        assert result["close"] == "c"

    def test_adj_close_alias(self):
        cols = ["time", "adj_close"]
        result = _resolve_ohlcv_columns(cols)
        assert result["close"] == "adj_close"

    def test_missing_columns_are_none(self):
        cols = ["time", "close"]
        result = _resolve_ohlcv_columns(cols)
        assert result["open"] is None
        assert result["high"] is None
        assert result["low"] is None
        assert result["volume"] is None

    def test_timestamp_alias(self):
        cols = ["Timestamp", "close"]
        result = _resolve_ohlcv_columns(cols)
        assert result["time"] == "Timestamp"


# =============================================================================
# _serialize_bar tests
# =============================================================================


class TestSerializeBar:
    """Test single-row bar serialization."""

    def test_full_ohlcv_bar(self):
        row = {
            "time": 1700000000,
            "open": 100,
            "high": 105,
            "low": 98,
            "close": 103,
            "volume": 1000000,
        }
        ohlcv_map = {
            "time": "time",
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "volume": "volume",
        }
        bar, vol = _serialize_bar(row, ohlcv_map)
        assert bar is not None
        assert bar["time"] == 1700000000
        assert bar["open"] == 100.0
        assert bar["high"] == 105.0
        assert bar["low"] == 98.0
        assert bar["close"] == 103.0
        assert vol is not None
        assert vol["time"] == 1700000000
        assert vol["value"] == 1000000.0

    def test_line_bar_close_only(self):
        row = {"time": 1700000000, "close": 103}
        ohlcv_map = {
            "time": "time",
            "open": None,
            "high": None,
            "low": None,
            "close": "close",
            "volume": None,
        }
        bar, vol = _serialize_bar(row, ohlcv_map)
        assert bar is not None
        assert "value" in bar
        assert bar["value"] == 103.0
        assert "open" not in bar
        assert vol is None

    def test_missing_time_returns_none(self):
        row = {"close": 103}
        ohlcv_map = {
            "time": "time",
            "open": None,
            "high": None,
            "low": None,
            "close": "close",
            "volume": None,
        }
        bar, vol = _serialize_bar(row, ohlcv_map)
        assert bar is None
        assert vol is None


# =============================================================================
# normalize_ohlcv tests
# =============================================================================


class TestNormalizeOhlcv:
    """Test the main normalization entry point."""

    def test_list_of_dicts_ohlcv(self):
        rows = _make_ohlcv_rows(5)
        result = normalize_ohlcv(rows)
        assert isinstance(result, TVChartData)
        assert len(result.series) == 1
        assert result.series[0].series_id == "main"
        assert len(result.bars) == 5
        assert result.series[0].has_volume is True
        assert len(result.volume) == 5
        assert result.series[0].series_type == SeriesType.CANDLESTICK

    def test_list_of_dicts_line_data(self):
        rows = [{"time": 1700000000 + i * 86400, "close": 100.0 + i} for i in range(3)]
        result = normalize_ohlcv(rows)
        assert len(result.bars) == 3
        assert "value" in result.bars[0]
        assert result.series[0].series_type == SeriesType.LINE

    def test_dict_of_lists(self):
        data = {
            "time": [1700000000, 1700086400],
            "close": [100.0, 101.0],
        }
        result = normalize_ohlcv(data)
        assert len(result.bars) == 2

    def test_empty_list(self):
        result = normalize_ohlcv([])
        assert len(result.series) == 1
        assert result.series[0].series_id == "main"
        assert len(result.bars) == 0

    def test_passthrough_tvchart_data(self):
        """normalize_ohlcv returns TVChartData unchanged."""
        original = TVChartData(
            series=[
                TVChartSeriesData(series_id="test", bars=[{"time": 1, "value": 2}], total_rows=1)
            ],
        )
        result = normalize_ohlcv(original)
        assert result is original

    def test_raises_on_unsupported_type(self):
        with pytest.raises(TypeError, match="Unsupported data type"):
            normalize_ohlcv("not_valid_data")

    def test_raises_on_missing_time_column(self):
        rows = [{"price": 100}]
        with pytest.raises(ValueError, match="Could not resolve time column"):
            normalize_ohlcv(rows)

    def test_raises_on_missing_close_column(self):
        rows = [{"time": 1700000000, "foo": 100}]
        with pytest.raises(ValueError, match="Could not resolve close/value column"):
            normalize_ohlcv(rows)

    def test_max_bars_truncation(self):
        rows = _make_ohlcv_rows(20)
        result = normalize_ohlcv(rows, max_bars=5)
        assert len(result.bars) == 5
        assert result.series[0].truncated_rows == 15
        assert result.series[0].total_rows == 20

    def test_capitalized_columns(self):
        rows = [
            {"Date": 1700000000, "Open": 100, "High": 105, "Low": 98, "Close": 103, "Volume": 1000}
        ]
        result = normalize_ohlcv(rows)
        assert len(result.bars) == 1
        assert result.bars[0]["open"] == 100.0


# =============================================================================
# TVChartData property tests
# =============================================================================


class TestTVChartDataProperties:
    """Test TVChartData computed properties."""

    def test_bars_property(self):
        s = TVChartSeriesData(series_id="main", bars=[{"time": 1, "value": 2}], total_rows=1)
        data = TVChartData(series=[s])
        assert data.bars == [{"time": 1, "value": 2}]

    def test_volume_property(self):
        s = TVChartSeriesData(
            series_id="main",
            bars=[{"time": 1, "value": 2}],
            volume=[{"time": 1, "value": 1000}],
            total_rows=1,
        )
        data = TVChartData(series=[s])
        assert data.volume == [{"time": 1, "value": 1000}]

    def test_series_ids_property(self):
        data = TVChartData(
            series=[
                TVChartSeriesData(series_id="AAPL", bars=[], total_rows=0),
                TVChartSeriesData(series_id="MSFT", bars=[], total_rows=0),
            ]
        )
        assert data.series_ids == ["AAPL", "MSFT"]

    def test_total_rows_property(self):
        data = TVChartData(
            series=[
                TVChartSeriesData(series_id="a", bars=[], total_rows=100),
                TVChartSeriesData(series_id="b", bars=[], total_rows=200),
            ]
        )
        assert data.total_rows == 300

    def test_empty_series_properties(self):
        data = TVChartData(series=[])
        assert data.bars == []
        assert data.volume == []
        assert data.series_ids == []
        assert data.total_rows == 0


class TestTVChartDatafeedModels:
    """Verify datafeed protocol model shape and serialization."""

    # --- TVChartSymbolInfo (full LibrarySymbolInfo) ---

    def test_symbol_info_required_fields(self):
        info = TVChartSymbolInfo()
        dumped = info.model_dump(exclude_none=True)
        assert dumped["name"] == ""
        assert dumped["description"] == ""
        assert dumped["exchange"] == ""
        assert dumped["listed_exchange"] == ""
        assert dumped["type"] == "stock"
        assert dumped["session"] == "24x7"
        assert dumped["timezone"] == "Etc/UTC"
        assert dumped["minmov"] == 1
        assert dumped["pricescale"] == 100
        assert dumped["format"] == "price"

    def test_symbol_info_full_fields(self):
        info = TVChartSymbolInfo(
            name="AAPL",
            symbol="NASDAQ:AAPL",
            ticker="AAPL",
            full_name="Apple Inc.",
            description="Apple common stock",
            exchange="NASDAQ",
            listed_exchange="NASDAQ",
            type="stock",
            session="0930-1600",
            timezone="America/New_York",
            currency_code="USD",
            minmov=1,
            pricescale=100,
            format="price",
            has_intraday=True,
            has_daily=True,
            has_weekly_and_monthly=True,
            supported_resolutions=["1", "5", "15", "60", "1D", "1W", "1M"],
            intraday_multipliers=["1", "5", "15", "60"],
            daily_multipliers=["1"],
            weekly_multipliers=["1"],
            monthly_multipliers=["1"],
            visible_plots_set="ohlcv",
            volume_precision=0,
            data_status="streaming",
            sector="Technology",
            industry="Consumer Electronics",
            logo_urls=["https://example.com/aapl.svg"],
        )
        dumped = info.model_dump(exclude_none=True)
        assert dumped["name"] == "AAPL"
        assert dumped["ticker"] == "AAPL"
        assert dumped["full_name"] == "Apple Inc."
        assert dumped["has_intraday"] is True
        assert dumped["has_daily"] is True
        assert dumped["visible_plots_set"] == "ohlcv"
        assert dumped["sector"] == "Technology"
        assert dumped["supported_resolutions"] == ["1", "5", "15", "60", "1D", "1W", "1M"]

    def test_symbol_info_optional_fields_excluded(self):
        info = TVChartSymbolInfo(
            name="X", description="Test", exchange="NYSE", listed_exchange="NYSE"
        )
        dumped = info.model_dump(exclude_none=True)
        assert "ticker" not in dumped
        assert "has_seconds" not in dumped
        assert "expired" not in dumped
        assert "subsessions" not in dumped

    def test_symbol_info_fractional_format(self):
        info = TVChartSymbolInfo(
            name="ZBM2023",
            description="T-Bond Futures",
            exchange="CME",
            listed_exchange="CME",
            type="futures",
            minmov=1,
            pricescale=128,
            minmove2=4,
            fractional=True,
        )
        dumped = info.model_dump(exclude_none=True)
        assert dumped["fractional"] is True
        assert dumped["minmove2"] == 4
        assert dumped["pricescale"] == 128

    def test_symbol_info_subsessions(self):
        info = TVChartSymbolInfo(
            name="ES",
            description="E-Mini S&P",
            exchange="CME",
            listed_exchange="CME",
            session="0930-1600",
            subsession_id="regular",
            subsessions=[
                TVChartLibrarySubsessionInfo(
                    id="regular", description="Regular", session="0930-1600"
                ),
                TVChartLibrarySubsessionInfo(
                    id="extended", description="Extended", session="0400-2000"
                ),
            ],
        )
        dumped = info.model_dump(exclude_none=True)
        assert len(dumped["subsessions"]) == 2
        assert dumped["subsessions"][0]["id"] == "regular"

    def test_symbol_info_price_sources(self):
        info = TVChartSymbolInfo(
            name="AAPL",
            description="Apple",
            exchange="NASDAQ",
            listed_exchange="NASDAQ",
            price_sources=[
                TVChartSymbolInfoPriceSource(id="1", name="Spot Price"),
                TVChartSymbolInfoPriceSource(id="2", name="Bid"),
            ],
            price_source_id="1",
        )
        dumped = info.model_dump(exclude_none=True)
        assert len(dumped["price_sources"]) == 2
        assert dumped["price_source_id"] == "1"

    def test_symbol_info_alias(self):
        info = TVChartSymbolInfo(
            name="X", description="", exchange="", listed_exchange="", symbol_type="futures"
        )
        dumped = info.model_dump(exclude_none=True)
        assert dumped["symbol_type"] == "futures"

    # --- TVChartDatafeedConfiguration ---

    def test_datafeed_configuration_model(self):
        cfg = TVChartDatafeedConfiguration(
            exchanges=[TVChartExchange(value="NYSE", name="New York Stock Exchange", desc="")],
            symbols_types=[TVChartDatafeedSymbolType(name="Stock", value="stock")],
            supported_resolutions=["1", "5", "15", "60", "1D", "1W", "1M"],
            supports_marks=True,
            supports_timescale_marks=True,
            supports_time=True,
            currency_codes=["USD", "EUR"],
        )
        dumped = cfg.model_dump(exclude_none=True)
        assert len(dumped["exchanges"]) == 1
        assert dumped["exchanges"][0]["value"] == "NYSE"
        assert dumped["supports_marks"] is True
        assert dumped["supports_time"] is True
        assert "1D" in dumped["supported_resolutions"]

    def test_datafeed_configuration_empty(self):
        cfg = TVChartDatafeedConfiguration()
        dumped = cfg.model_dump(exclude_none=True)
        assert dumped == {}

    # --- TVChartSearchSymbolResultItem ---

    def test_search_symbol_result_item(self):
        item = TVChartSearchSymbolResultItem(
            symbol="AAPL",
            description="Apple Inc.",
            exchange="NasdaqNM",
            type="stock",
            ticker="AAPL",
        )
        dumped = item.model_dump(exclude_none=True)
        assert dumped["symbol"] == "AAPL"
        assert dumped["type"] == "stock"

    # --- TVChartBar ---

    def test_bar_model(self):
        bar = TVChartBar(
            time=1700000000000, open=100.0, high=105.0, low=99.0, close=103.0, volume=1000000.0
        )
        dumped = bar.model_dump()
        assert dumped["time"] == 1700000000000
        assert dumped["open"] == 100.0
        assert dumped["volume"] == 1000000.0

    def test_bar_model_no_volume(self):
        bar = TVChartBar(time=1700000000000, open=100.0, high=105.0, low=99.0, close=103.0)
        dumped = bar.model_dump(exclude_none=True)
        assert "volume" not in dumped

    # --- TVChartMark ---

    def test_mark_model(self):
        mark = TVChartMark(
            id="m1",
            time=1700000000,
            color="red",
            text="Earnings",
            label="E",
            label_font_color="white",
            min_size=24,
        )
        dumped = mark.model_dump(exclude_none=True)
        assert dumped["id"] == "m1"
        assert dumped["color"] == "red"
        assert dumped["label"] == "E"

    # --- TVChartTimescaleMark ---

    def test_timescale_mark_model(self):
        mark = TVChartTimescaleMark(
            id="ts1",
            time=1700000000,
            color="blue",
            label="D",
            tooltip=["Dividend", "$0.25/share"],
        )
        dumped = mark.model_dump(exclude_none=True)
        assert dumped["id"] == "ts1"
        assert dumped["tooltip"] == ["Dividend", "$0.25/share"]

    # --- Config request/response ---

    def test_config_request_response(self):
        req = TVChartDatafeedConfigRequest(request_id="cfg-1", chart_id="main")
        assert req.request_id == "cfg-1"

        resp = TVChartDatafeedConfigResponse(
            request_id="cfg-1",
            config=TVChartDatafeedConfiguration(supports_marks=True),
        )
        dumped = resp.model_dump(exclude_none=True)
        assert dumped["config"]["supports_marks"] is True

    # --- Search request/response ---

    def test_search_request_and_response_models(self):
        req = TVChartDatafeedSearchRequest(
            request_id="req-1",
            query="aapl",
            chart_id="main",
            limit=15,
            exchange="NASDAQ",
            symbol_type="stock",
        )
        req_dump = req.model_dump()
        assert req_dump["request_id"] == "req-1"
        assert req_dump["query"] == "aapl"
        assert req_dump["exchange"] == "NASDAQ"
        assert req_dump["limit"] == 15

        resp = TVChartDatafeedSearchResponse(
            request_id="req-1",
            query="aapl",
            items=[
                TVChartSearchSymbolResultItem(
                    symbol="AAPL", description="Apple Inc.", exchange="NASDAQ"
                )
            ],
        )
        resp_dump = resp.model_dump(exclude_none=True)
        assert resp_dump["request_id"] == "req-1"
        assert resp_dump["items"][0]["symbol"] == "AAPL"

    # --- Resolve request/response ---

    def test_resolve_request_and_response_models(self):
        req = TVChartDatafeedResolveRequest(
            request_id="req-2", symbol="NASDAQ:AAPL", chart_id="main"
        )
        req_dump = req.model_dump()
        assert req_dump["request_id"] == "req-2"
        assert req_dump["symbol"] == "NASDAQ:AAPL"

        resp = TVChartDatafeedResolveResponse(
            request_id="req-2",
            symbol_info=TVChartSymbolInfo(
                name="AAPL",
                ticker="AAPL",
                description="Apple",
                exchange="NASDAQ",
                listed_exchange="NASDAQ",
                pricescale=100,
            ),
        )
        resp_dump = resp.model_dump(exclude_none=True)
        assert resp_dump["request_id"] == "req-2"
        assert resp_dump["symbol_info"]["ticker"] == "AAPL"
        assert resp_dump["symbol_info"]["pricescale"] == 100

    # --- History request/response ---

    def test_history_request_and_response_models(self):
        req = TVChartDatafeedHistoryRequest(
            request_id="req-3",
            symbol="NASDAQ:AAPL",
            resolution="1D",
            from_time=1_700_000_000,
            to_time=1_700_086_400,
            count_back=300,
            first_data_request=True,
        )
        req_dump = req.model_dump()
        assert req_dump["resolution"] == "1D"
        assert req_dump["count_back"] == 300
        assert req_dump["first_data_request"] is True

        resp = TVChartDatafeedHistoryResponse(
            request_id="req-3",
            status="ok",
            bars=[{"time": 1_700_000_000, "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5}],
        )
        resp_dump = resp.model_dump()
        assert resp_dump["request_id"] == "req-3"
        assert resp_dump["status"] == "ok"
        assert len(resp_dump["bars"]) == 1

    def test_history_response_no_data(self):
        resp = TVChartDatafeedHistoryResponse(
            request_id="req-4",
            status="no_data",
            bars=[],
            no_data=True,
            next_time=1_699_900_000_000,
        )
        dumped = resp.model_dump(exclude_none=True)
        assert dumped["no_data"] is True
        assert dumped["next_time"] == 1_699_900_000_000
        assert dumped["status"] == "no_data"

    # --- Subscribe/Unsubscribe ---

    def test_subscribe_request(self):
        req = TVChartDatafeedSubscribeRequest(
            request_id="sub-1",
            symbol="AAPL",
            resolution="1",
            listener_guid="guid-abc-123",
            chart_id="main",
        )
        assert req.listener_guid == "guid-abc-123"
        assert req.resolution == "1"

    def test_unsubscribe_request(self):
        req = TVChartDatafeedUnsubscribeRequest(
            listener_guid="guid-abc-123",
            chart_id="main",
        )
        assert req.listener_guid == "guid-abc-123"

    def test_bar_update(self):
        update = TVChartDatafeedBarUpdate(
            listener_guid="guid-abc-123",
            bar={
                "time": 1700000000000,
                "open": 100,
                "high": 105,
                "low": 99,
                "close": 103,
                "volume": 50000,
            },
        )
        dumped = update.model_dump()
        assert dumped["listener_guid"] == "guid-abc-123"
        assert dumped["bar"]["close"] == 103

    # --- Marks request/response ---

    def test_marks_request_response(self):
        req = TVChartDatafeedMarksRequest(
            request_id="m-1",
            symbol="AAPL",
            from_time=1700000000,
            to_time=1700086400,
            resolution="1D",
        )
        assert req.from_time == 1700000000

        resp = TVChartDatafeedMarksResponse(
            request_id="m-1",
            marks=[
                {
                    "id": "mk1",
                    "time": 1700000000,
                    "color": "red",
                    "text": "Buy",
                    "label": "B",
                    "labelFontColor": "#fff",
                    "minSize": 20,
                }
            ],
        )
        dumped = resp.model_dump(exclude_none=True)
        assert len(dumped["marks"]) == 1

    # --- TimescaleMarks request/response ---

    def test_timescale_marks_request_response(self):
        req = TVChartDatafeedTimescaleMarksRequest(
            request_id="ts-1",
            symbol="AAPL",
            from_time=1700000000,
            to_time=1700086400,
            resolution="1D",
        )
        assert req.resolution == "1D"

        resp = TVChartDatafeedTimescaleMarksResponse(
            request_id="ts-1",
            marks=[
                {
                    "id": "tsm1",
                    "time": 1700000000,
                    "color": "blue",
                    "label": "D",
                    "tooltip": ["Dividend"],
                }
            ],
        )
        dumped = resp.model_dump(exclude_none=True)
        assert len(dumped["marks"]) == 1

    # --- ServerTime request/response ---

    def test_server_time_request_response(self):
        req = TVChartDatafeedServerTimeRequest(request_id="st-1", chart_id="main")
        assert req.request_id == "st-1"

        resp = TVChartDatafeedServerTimeResponse(
            request_id="st-1",
            time=1700000000,
        )
        dumped = resp.model_dump(exclude_none=True)
        assert dumped["time"] == 1700000000


# =============================================================================
# _serialize_series_from_rows tests
# =============================================================================


class TestSerializeSeriesFromRows:
    """Test bulk row serialization into TVChartSeriesData."""

    def test_basic_ohlcv(self):
        rows = _make_ohlcv_rows(3)
        ohlcv_map = _resolve_ohlcv_columns(list(rows[0].keys()))
        result = _serialize_series_from_rows(rows, ohlcv_map, "test")
        assert result.series_id == "test"
        assert len(result.bars) == 3
        assert result.series_type == SeriesType.CANDLESTICK
        assert result.has_volume is True
        assert result.total_rows == 3
        assert result.truncated_rows == 0

    def test_truncation(self):
        rows = _make_ohlcv_rows(10)
        ohlcv_map = _resolve_ohlcv_columns(list(rows[0].keys()))
        result = _serialize_series_from_rows(rows, ohlcv_map, "test", max_bars=3)
        assert len(result.bars) == 3
        assert result.total_rows == 10
        assert result.truncated_rows == 7


# =============================================================================
# build_tvchart_toolbars tests
# =============================================================================


class TestBuildTVChartToolbars:
    """Test the toolbar factory function."""

    def test_returns_four_toolbars(self):
        toolbars = build_tvchart_toolbars()
        assert len(toolbars) == 4

    def test_toolbar_positions(self):
        toolbars = build_tvchart_toolbars()
        positions = [tb.position for tb in toolbars]
        assert "top" in positions
        assert "left" in positions
        assert "bottom" in positions
        assert "inside" in positions

    def test_header_has_chart_type_select(self):
        toolbars = build_tvchart_toolbars()
        header = next(tb for tb in toolbars if tb.position == "top")
        ids = [item.component_id for item in header.items]
        assert "wrap-tvchart-chart-type" in ids

    def test_left_has_drawing_tools(self):
        toolbars = build_tvchart_toolbars()
        left = next(tb for tb in toolbars if tb.position == "left")
        ids = [item.component_id for item in left.items]
        assert "wrap-tvchart-tool-crosshair" in ids
        assert "wrap-tvchart-group-lines" in ids
        assert "wrap-tvchart-group-channels" in ids
        assert "wrap-tvchart-tool-eraser" in ids

    def test_bottom_has_time_range_tabs(self):
        toolbars = build_tvchart_toolbars()
        bottom = next(tb for tb in toolbars if tb.position == "bottom")
        ids = [item.component_id for item in bottom.items]
        assert "tvchart-time-range" in ids
        assert "wrap-tvchart-date-range" in ids

    def test_bottom_uses_daily_practical_ranges_when_intraday_is_unavailable(self):
        toolbars = build_tvchart_toolbars(intervals=["1d", "1w", "1M"], selected_interval="1d")
        bottom = next(tb for tb in toolbars if tb.position == "bottom")
        time_range = next(
            item for item in bottom.items if item.component_id == "tvchart-time-range"
        )

        assert [option.value for option in time_range.options] == [
            "all",
            "10y",
            "5y",
            "1y",
            "ytd",
            "6m",
            "3m",
            "1m",
        ]
        assert time_range.selected == "1y"
        assert [option.data_attrs["target-interval"] for option in time_range.options] == [
            "1d",
            "1M",
            "1w",
            "1d",
            "1d",
            "1d",
            "1d",
            "1d",
        ]

    def test_bottom_uses_longer_ranges_for_weekly_only_data(self):
        toolbars = build_tvchart_toolbars(intervals=["1w", "1M"], selected_interval="1w")
        bottom = next(tb for tb in toolbars if tb.position == "bottom")
        time_range = next(
            item for item in bottom.items if item.component_id == "tvchart-time-range"
        )

        assert [option.value for option in time_range.options] == [
            "all",
            "10y",
            "5y",
            "3y",
            "1y",
            "ytd",
            "6m",
            "3m",
        ]
        assert time_range.selected == "1y"
        assert [option.data_attrs["target-interval"] for option in time_range.options] == [
            "1w",
            "1M",
            "1w",
            "1w",
            "1w",
            "1w",
            "1w",
            "1w",
        ]

    def test_bottom_uses_multi_year_ranges_for_quarterly_data(self):
        toolbars = build_tvchart_toolbars(intervals=["3M", "12M"], selected_interval="3M")
        bottom = next(tb for tb in toolbars if tb.position == "bottom")
        time_range = next(
            item for item in bottom.items if item.component_id == "tvchart-time-range"
        )

        assert [option.value for option in time_range.options] == [
            "all",
            "20y",
            "10y",
            "5y",
            "3y",
            "ytd",
        ]
        assert time_range.selected == "ytd"
        assert [option.data_attrs["target-interval"] for option in time_range.options] == [
            "3M",
            "3M",
            "3M",
            "3M",
            "3M",
            "3M",
        ]

    def test_bottom_intraday_ranges_expose_expected_target_intervals_and_tooltips(self):
        toolbars = build_tvchart_toolbars(
            intervals=["1m", "3m", "5m", "15m", "30m", "45m", "1h", "2h", "4h", "1d", "1w", "1M"],
            selected_interval="1d",
        )
        bottom = next(tb for tb in toolbars if tb.position == "bottom")
        time_range = next(
            item for item in bottom.items if item.component_id == "tvchart-time-range"
        )
        options = {option.value: option for option in time_range.options}

        assert options["1d"].data_attrs["target-interval"] == "1m"
        assert options["5d"].data_attrs["target-interval"] == "5m"
        assert options["1m"].data_attrs["target-interval"] == "30m"
        assert options["3m"].data_attrs["target-interval"] == "1h"
        assert options["6m"].data_attrs["target-interval"] == "2h"
        assert options["ytd"].data_attrs["target-interval"] == "1d"
        assert options["all"].data_attrs["target-interval"] == "1d"
        assert options["1d"].description == "1 day"
        assert options["5d"].description == "5 days"
        assert options["1m"].description == "1 month"
        assert options["3m"].description == "3 months"
        assert options["6m"].description == "6 months"
        assert options["ytd"].description == "Year to date"
        assert options["all"].description == "All"
        assert options["10y"].label == "10y"
        assert options["ytd"].label == "YTD"
        assert options["all"].label == "Max"

    def test_header_has_save_button(self):
        toolbars = build_tvchart_toolbars()
        header = next(tb for tb in toolbars if tb.position == "top")
        ids = [item.component_id for item in header.items]
        assert "wrap-tvchart-save-split" in ids

    def test_inside_toolbar_legend_div_has_no_inline_script(self):
        """Legend script is loaded via 11-legend.js, not inline on the Div."""
        toolbars = build_tvchart_toolbars()
        inside = next(tb for tb in toolbars if tb.position == "inside")
        legend = inside.items[0]
        assert legend.script is None or legend.script == ""


class TestTVChartFrontendStateContracts:
    """Validate structural and behavioural contracts in the JS frontend source.

    Each test scopes its assertions to a specific function or handler body,
    verifying that the tested property lives in the correct execution context
    rather than just checking for string presence anywhere in ~12 000 lines.
    """

    @pytest.fixture
    def tvchart_defaults_js(self) -> str:
        from pywry.assets import get_tvchart_defaults_js

        return get_tvchart_defaults_js()

    # ------------------------------------------------------------------
    # Helpers: scope extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _skip_comment(src: str, i: int, n: int) -> int | None:
        """If *i* points to the start of a JS comment, return the index past it."""
        if i + 1 >= n:
            return None
        nxt = src[i + 1]
        if nxt == "/":
            nl = src.find("\n", i)
            return (nl + 1) if nl != -1 else n
        if nxt == "*":
            end = src.find("*/", i + 2)
            return (end + 2) if end != -1 else n
        return None

    @staticmethod
    def _extract_braced(src: str, search_from: int) -> str:
        """Return text from *search_from* through the matching closing brace.

        Handles string literals (single, double, backtick) and comments
        (// and /* */) so braces inside them are not counted.
        """
        i = src.index("{", search_from)
        depth = 0
        in_string: str | None = None
        escaped = False
        n = len(src)
        while i < n:
            ch = src[i]
            if escaped:
                escaped = False
                i += 1
                continue
            if ch == "\\":
                escaped = True
                i += 1
                continue
            if in_string:
                if ch == in_string:
                    in_string = None
                i += 1
                continue
            if ch in ("'", '"', "`"):
                in_string = ch
            elif ch == "/":
                skip = TestTVChartFrontendStateContracts._skip_comment(src, i, n)
                if skip is not None:
                    i = skip
                    continue
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return src[search_from : i + 1]
            i += 1
        return src[search_from:]

    def _fn(self, src: str, name: str) -> str:
        """Extract the full body of ``function <name>(...)``."""
        return self._extract_braced(src, src.index(f"function {name}("))

    def _handler(self, src: str, event: str) -> str:
        """Extract the body of an event listener for ``<event>``.

        Accepts both ``window.pywry.on('<event>', ...)`` and
        ``bridge.on('<event>', ...)`` — the tvchart event handlers are
        registered against a local ``bridge`` reference that defaults to
        ``window.pywry``.
        """
        candidates = (
            f"window.pywry.on('{event}'",
            f"bridge.on('{event}'",
        )
        for candidate in candidates:
            idx = src.find(candidate)
            if idx != -1:
                return self._extract_braced(src, idx)
        raise ValueError(f"No handler registration found for event '{event}'")

    def _create_body(self, src: str) -> str:
        """Extract the PYWRY_TVCHART_CREATE function body."""
        start = src.index("window.PYWRY_TVCHART_CREATE = function")
        end = src.index("window.PYWRY_TVCHART_UPDATE", start)
        return src[start:end]

    # ------------------------------------------------------------------
    # State export & request
    # ------------------------------------------------------------------

    def test_state_export_returns_all_survival_fields(self, tvchart_defaults_js: str):
        """_tvExportState must return rawData, drawings, and indicators so a
        chart can be fully reconstructed after a page reload."""
        body = self._fn(tvchart_defaults_js, "_tvExportState")
        # The return object must include each survival-critical field
        for field in ("rawData", "drawings", "indicators"):
            assert f"{field}: {field}" in body, (
                f"_tvExportState return object must include '{field}'"
            )
        # Also verify visibleRange is captured (for state, not layout)
        assert "getVisibleLogicalRange()" in body

    def test_state_response_echoes_request_context(self, tvchart_defaults_js: str):
        """The request-state handler must attach data.context to the response
        so the caller can correlate responses to requests."""
        body = self._handler(tvchart_defaults_js, "tvchart:request-state")
        # Must call the export function
        assert "_tvExportState(" in body
        # Must propagate context
        assert "data.context" in body
        assert "Object.assign" in body
        # Must emit the response event
        assert "tvchart:state-response" in body

    # ------------------------------------------------------------------
    # Legend scoping & controls
    # ------------------------------------------------------------------

    def test_legend_setup_is_scoped_to_chart_instance(self, tvchart_defaults_js: str):
        """_tvSetupLegendControls must accept chartId and use scoped DOM
        queries — never reference hardcoded chart IDs or global singletons."""
        body = self._fn(tvchart_defaults_js, "_tvSetupLegendControls")
        # Scoped lookup pattern
        assert "_tvResolveChartEntry(chartId)" in body
        assert "_tvScopedById(chartId" in body
        # Uses local scopedById helper for DOM queries
        assert "function scopedById(id)" in body
        # Never hardcodes the first chart
        assert "chartIds[0]" not in body

    def test_legend_has_per_series_action_buttons(self, tvchart_defaults_js: str):
        """Each legend series row must have hide, settings, remove, and more actions."""
        body = self._fn(tvchart_defaults_js, "_tvSetupLegendControls")
        required_actions = ["hide", "settings", "remove", "more"]
        for action in required_actions:
            assert f'data-action="{action}"' in body, (
                f"Legend row must have a '{action}' action button"
            )

    def test_legend_listens_for_external_refresh_events(self, tvchart_defaults_js: str):
        """Legend must subscribe to pywry:legend-refresh for external updates
        (compare add/remove, indicator changes)."""
        body = self._fn(tvchart_defaults_js, "_tvSetupLegendControls")
        assert "pywry:legend-refresh" in body

    # ------------------------------------------------------------------
    # Volume subplot
    # ------------------------------------------------------------------

    def test_volume_reserve_called_in_both_lifecycle_paths(self, tvchart_defaults_js: str):
        """_tvReserveVolumePane must be called in both the static-data (CREATE)
        and datafeed-mode code paths to ensure volume always gets a subplot."""
        create = self._create_body(tvchart_defaults_js)
        # Static lifecycle must call reserve
        assert "_tvReserveVolumePane(entry," in create, (
            "PYWRY_TVCHART_CREATE must call _tvReserveVolumePane for static data"
        )
        # The reserve function itself must accept (entry, seriesId)
        reserve_fn = self._fn(tvchart_defaults_js, "_tvReserveVolumePane")
        assert "entry._volumePaneBySeries" in reserve_fn
        # Main volume always gets pane index 1
        assert "paneIndex = 1" in reserve_fn

    def test_volume_pane_height_is_clamped_proportionally(self, tvchart_defaults_js: str):
        """_tvApplyDefaultVolumePaneHeight must clamp the height to a reasonable
        fraction of the container, not use a fixed pixel value. The formula
        prevents the volume pane from being too small or too large."""
        body = self._fn(tvchart_defaults_js, "_tvApplyDefaultVolumePaneHeight")
        # Must reference container height for proportional sizing
        assert "containerHeight" in body
        # Clamp formula: min 64, max 132, 12% of container
        assert "Math.max(64" in body
        assert "Math.min(132" in body
        assert "0.12" in body
        # Actually sets the height on the pane
        assert "setHeight(desiredHeight)" in body

    def test_volume_options(self, tvchart_defaults_js: str):
        """Volume series uses the right-side price scale of its own pane,
        keeps the latest-value label visible, and suppresses the price line."""
        body = self._fn(tvchart_defaults_js, "_tvBuildVolumeOptions")
        assert "lastValueVisible: true" in body, (
            "Volume needs the latest-value label so the right axis renders ticks"
        )
        assert "priceLineVisible: false" in body, (
            "Volume must hide priceLineVisible to avoid horizontal-line clutter"
        )
        # Volume series binds to the standard 'right' price scale of its
        # own pane (visible by default), not a hidden custom 'volume' scale.
        assert "priceScaleId: 'right'" in body

    def test_volume_auto_enables_in_create(self, tvchart_defaults_js: str):
        """PYWRY_TVCHART_CREATE enables volume by default when enableVolume is
        not explicitly false, and applies the default pane height."""
        create = self._create_body(tvchart_defaults_js)
        assert "enableVolume !== false" in create
        assert "_tvApplyDefaultVolumePaneHeight(" in create

    # ------------------------------------------------------------------
    # Time range (zoom-only, no interval switching)
    # ------------------------------------------------------------------

    def test_time_range_handler_is_zoom_only(self, tvchart_defaults_js: str):
        """The tvchart:time-range handler must apply zoom via
        _tvApplyTimeRangeSelection and must NOT switch the interval.
        Interval authority belongs exclusively to the interval dropdown."""
        body = self._handler(tvchart_defaults_js, "tvchart:time-range")
        assert "_tvApplyTimeRangeSelection(" in body, (
            "time-range handler must call _tvApplyTimeRangeSelection"
        )
        # Must not contain interval-switching patterns
        assert "_pendingTimeRange" not in body, (
            "time-range handler must not defer to interval change"
        )
        assert "targetInterval" not in body, "time-range handler must not switch the interval"
        assert "tvchart:interval-change" not in body, (
            "time-range handler must not emit interval-change events"
        )

    def test_time_range_selection_handles_all_and_ytd(self, tvchart_defaults_js: str):
        """_tvApplyTimeRangeSelection must have explicit branches for 'all'
        (fit all data) and 'ytd' (year-to-date), plus use _tvResolveRangeSpanDays
        for named presets like '1y', '3m', etc.  For absolute date-range
        requests it must delegate to _tvApplyAbsoluteDateRange."""
        body = self._fn(tvchart_defaults_js, "_tvApplyTimeRangeSelection")
        assert "range === 'all'" in body
        assert "fitContent()" in body
        assert "range === 'ytd'" in body
        assert "_tvResolveRangeSpanDays(" in body
        # Absolute date-range requests are handled by a separate helper.
        assert "function _tvApplyAbsoluteDateRange" in tvchart_defaults_js

    def test_range_span_resolver_covers_standard_presets(self, tvchart_defaults_js: str):
        """_tvResolveRangeSpanDays must define time spans for all standard presets."""
        body = self._fn(tvchart_defaults_js, "_tvResolveRangeSpanDays")
        for preset in ("'1d'", "'5d'", "'1m'", "'3m'", "'6m'", "'1y'", "'5y'"):
            assert preset in body, f"Range resolver must cover preset {preset}"

    # No anti-pattern
    def test_no_pending_time_range_state(self, tvchart_defaults_js: str):
        """_pendingTimeRange was an old pattern that coupled range to interval.
        It must not exist anywhere in the codebase."""
        assert "_pendingTimeRange" not in tvchart_defaults_js

    # ------------------------------------------------------------------
    # Legend hover & crosshair
    # ------------------------------------------------------------------

    def test_legend_hover_falls_back_to_cached_data(self, tvchart_defaults_js: str):
        """_legendResolveHoveredPoint must try live seriesData first, then
        fall back to cached _seriesRawData for cases where seriesData is
        unavailable (e.g. compare series, synthetic indicators)."""
        body = self._fn(tvchart_defaults_js, "_legendResolveHoveredPoint")
        # Try live data first via param.seriesData.get()
        assert "param.seriesData" in body
        # Fall back to cached raw data
        assert "_seriesRawData" in body
        # Must handle null/missing time
        assert "param.time" in body

    def test_legend_hover_refresh_functions_exist_and_are_called(self, tvchart_defaults_js: str):
        """_tvRefreshLegendTitle, _tvEmitLegendRefresh, and _tvRenderHoverLegend
        must exist and be called after compare series changes (add/remove)."""
        # Functions must exist
        for fn in ("_tvRefreshLegendTitle", "_tvEmitLegendRefresh", "_tvRenderHoverLegend"):
            assert f"function {fn}(" in tvchart_defaults_js, f"{fn} must be defined"

        # They must each be called from more than just their definition
        # (at least 2 occurrences = definition + call site)
        for fn in ("_tvRefreshLegendTitle(", "_tvEmitLegendRefresh(", "_tvRenderHoverLegend("):
            count = tvchart_defaults_js.count(fn)
            assert count >= 2, (
                f"{fn} found {count} time(s) — must be defined AND called from at least one site"
            )

    def test_crosshair_mode_controlled_by_prefs(self, tvchart_defaults_js: str):
        """Crosshair visibility must be driven by prefs.crosshairEnabled so
        user can toggle it, and default to disabled."""
        body = self._fn(tvchart_defaults_js, "_tvCrosshairLinesVisible")
        assert "crosshairEnabled" in body
        # _tvApplyHoverReadoutMode must exist to sync crosshair mode to chart
        assert "function _tvApplyHoverReadoutMode(" in tvchart_defaults_js

    # ------------------------------------------------------------------
    # Volume divider clearance & scale placement
    # ------------------------------------------------------------------

    def test_divider_clearance_conditionally_expands_bottom_margin(self, tvchart_defaults_js: str):
        """_tvEnforceMainScaleDividerClearance must increase the bottom margin
        only when a volume pane exists, so the lowest price label does not
        overlay the pane divider."""
        body = self._fn(tvchart_defaults_js, "_tvEnforceMainScaleDividerClearance")
        # Check for volume pane existence
        assert "volumeMap" in body
        # Conditional increase
        assert "Math.max(bottom" in body
        # Must apply via priceScale().applyOptions
        assert "scaleMargins" in body
        # Must resolve the scale side dynamically
        assert "_tvResolveScalePlacement(entry)" in body

    def test_scale_placement_resolver_is_used_at_series_creation(self, tvchart_defaults_js: str):
        """_tvResolveScalePlacement must be called wherever series are created
        or scale options are applied, so scale-side is never hardcoded."""
        # Function must exist
        assert "function _tvResolveScalePlacement(entry)" in tvchart_defaults_js
        # Must be called at multiple sites (not just defined)
        call_count = tvchart_defaults_js.count("_tvResolveScalePlacement(entry)")
        assert call_count >= 3, (
            f"_tvResolveScalePlacement called {call_count} time(s); expected >= 3 "
            "(definition + series creation + divider clearance)"
        )

    # ------------------------------------------------------------------
    # Layout save/open (client-side persistence)
    # ------------------------------------------------------------------

    def test_layout_persist_builds_summary_from_contents(self, tvchart_defaults_js: str):
        """_tvLayoutPersist must build a summary from indicator/drawing names
        for the index entry, not store symbol/timeframe (layouts are portable)."""
        body = self._fn(tvchart_defaults_js, "_tvLayoutPersist")
        # Builds summary from indicators
        assert "indNames" in body or "summary" in body
        # Stores to local storage via adapter
        assert "_tvStorageSet(" in body
        # Index entry has summary field
        assert "summary:" in body
        # Must NOT store symbol or timeframe
        assert "symbol:" not in body
        assert "timeframe:" not in body

    def test_layout_apply_restores_drawings_and_indicators(self, tvchart_defaults_js: str):
        """_tvApplyLayout must restore drawings and indicators, handle grouped
        indicators (Bollinger Bands deduplication), and NOT restore
        visibleRange (layouts are portable across charts)."""
        body = self._fn(tvchart_defaults_js, "_tvApplyLayout")
        # Restores drawings
        assert "_tvRenderDrawings(" in body
        # Removes old indicators before adding saved ones
        assert "_tvRemoveIndicator(" in body
        assert "_tvAddIndicator(" in body
        # Grouped indicator deduplication
        assert "restoredGroups" in body
        # Must NOT restore visibleRange
        assert (
            "setVisibleLogicalRange" not in body
            and "visibleRange" not in body.split("// visibleRange")[0]
        ), "Layout apply must not restore visibleRange (portability contract)"
        # Restores settings
        assert "_tvApplySettingsToChart(" in body

    def test_layout_meta_label_shows_summary_not_symbol(self, tvchart_defaults_js: str):
        """_tvLayoutMetaLabel should show summary + date, not symbol/timeframe."""
        body = self._fn(tvchart_defaults_js, "_tvLayoutMetaLabel")
        assert "summary" in body
        assert "savedAt" in body or "Date" in body
        # Must NOT reference symbol or timeframe
        assert "symbol" not in body.lower()
        assert "timeframe" not in body.lower()

    def test_no_alert_in_layout_flow(self, tvchart_defaults_js: str):
        """Layout save/open must use toast notifications, never window.alert."""
        assert "window.alert(" not in tvchart_defaults_js

    # ------------------------------------------------------------------
    # Candle settings: opacity & colour controls
    # ------------------------------------------------------------------

    def test_candle_colours_use_opacity_popup_not_separate_rows(self, tvchart_defaults_js: str):
        """Candle body/border/wick colour controls must use the unified
        color-opacity popup. Separate addOpacityRow calls for these must
        NOT exist (they create redundant UI rows)."""
        # The unified popup must exist
        assert "function _tvShowColorOpacityPopup(" in tvchart_defaults_js
        # Old per-element opacity rows must NOT be used for candle parts
        for part in ("Body", "Borders", "Wick"):
            assert f"addOpacityRow(lineSection, '{part}'" not in tvchart_defaults_js, (
                f"Candle {part} must use color-opacity popup, not a separate opacity row"
            )
        # Combined opacity keys must exist for all candle parts
        for part in ("Body", "Borders", "Wick"):
            assert f"'{part}-Opacity'" in tvchart_defaults_js

    def test_candle_colour_with_opacity_applied_for_all_parts(self, tvchart_defaults_js: str):
        """All six candle colour keys (Body/Borders/Wick x Up/Down) must be
        passed through _tvColorWithOpacity so opacity is actually applied."""
        parts = [
            "Body-Up Color",
            "Body-Down Color",
            "Borders-Up Color",
            "Borders-Down Color",
            "Wick-Up Color",
            "Wick-Down Color",
        ]
        for part in parts:
            assert f"_tvColorWithOpacity(settings['{part}']" in tvchart_defaults_js, (
                f"Missing _tvColorWithOpacity call for '{part}'"
            )

    def test_settings_collect_hidden_inputs_for_opacity(self, tvchart_defaults_js: str):
        """collectSettingsFromPanel must read hidden inputs (used for opacity
        sliders) in addition to number/text/range controls."""
        assert (
            "ctrl.type === 'number' || ctrl.type === 'text' || ctrl.type === 'range' || ctrl.type === 'hidden'"
            in tvchart_defaults_js
        )

    # ------------------------------------------------------------------
    # Status-line and scales settings
    # ------------------------------------------------------------------

    def test_settings_row_helpers_exist(self, tvchart_defaults_js: str):
        """Shared settings row builders must be defined so all settings tabs
        have consistent layout and control alignment."""
        helpers = [
            "addIndentedCheckboxRow(parent, label, checked)",
            "addCheckboxSliderRow(parent, label, checked, enabledSetting, sliderValue, sliderSetting)",
            "addNumberInputRow(parent, label, settingKey, value, min, max, step, unitText, inputClassName)",
            "addColorSwatchRow(parent, label, color, settingKey)",
            "addCheckboxInputRow(parent, label, checked, enabledSetting, inputValue, inputSetting)",
            "addSelectColorRow(parent, label, options, selected, selectSetting, color, colorSetting)",
        ]
        for sig in helpers:
            assert f"function {sig}" in tvchart_defaults_js, (
                f"Settings helper 'function {sig}' must be defined"
            )

    def test_scales_settings_uses_full_value_label(self, tvchart_defaults_js: str):
        """The scales tab must use the full 'Value according to scale' label.
        A truncated 'Value according to sc...' label broke the settings key
        mapping.  Fallback for the truncated key must also exist."""
        assert "'Value according to scale'" in tvchart_defaults_js
        # The truncated key must NOT be used in addSelectRow calls
        assert "addSelectRow(scalesSection, 'Value according to sc...'" not in tvchart_defaults_js
        # Fallback for layouts saved with the truncated key
        assert "'Value according to sc...'" in tvchart_defaults_js

    # ------------------------------------------------------------------
    # Settings preview & cancel
    # ------------------------------------------------------------------

    def test_settings_preview_pipeline(self, tvchart_defaults_js: str):
        """Settings must clone originals for revert, schedule a preview on
        input/change events, and revert to originals on cancel."""
        # Original settings cloned for cancel-revert
        assert "JSON.parse(JSON.stringify(currentSettings" in tvchart_defaults_js
        # Preview functions exist
        for fn_name in ("collectSettingsFromPanel", "scheduleSettingsPreview", "persistSettings"):
            assert f"function {fn_name}(" in tvchart_defaults_js, (
                f"Settings preview pipeline requires '{fn_name}'"
            )
        # Cancel reverts to original
        assert "_tvApplySettingsToChart(chartId, entry, originalSettings)" in tvchart_defaults_js
        # Preview triggered on user input
        assert "addEventListener('input'" in tvchart_defaults_js
        assert "addEventListener('change'" in tvchart_defaults_js

    # ------------------------------------------------------------------
    # Chart navigation (scroll/zoom always enabled)
    # ------------------------------------------------------------------

    def test_navigation_disable_restore_symmetry(self, tvchart_defaults_js: str):
        """Drawing drag temporarily disables chart navigation. Every disable
        call must have a matching restore call — an imbalance would leave
        the chart in a broken non-interactive state."""
        disable_count = tvchart_defaults_js.count(
            "entry.chart.applyOptions({ handleScroll: false, handleScale: false })"
        )
        restore_count = tvchart_defaults_js.count(
            "entry.chart.applyOptions({ handleScroll: true, handleScale: true })"
        )
        assert disable_count >= 1, "At least one navigation disable expected for drawing drag"
        assert disable_count == restore_count, (
            f"Disable ({disable_count}) and restore ({restore_count}) must be symmetric"
        )

    def test_ensure_interactive_navigation_exists_and_is_called(self, tvchart_defaults_js: str):
        """_tvEnsureInteractiveNavigation must exist (restores navigation after
        overlays close) and be called from at least one site."""
        body = self._fn(tvchart_defaults_js, "_tvEnsureInteractiveNavigation")
        # Must re-enable both scroll and scale options
        assert "handleScroll" in body or "applyOptions" in body
        # Must be called from other code (not just defined)
        all_calls = tvchart_defaults_js.count("_tvEnsureInteractiveNavigation(entry)")
        assert all_calls >= 2, (
            f"_tvEnsureInteractiveNavigation called {all_calls} time(s); expected >= 2 "
            "(definition + at least one call site)"
        )

    def test_interactive_navigation_options_enable_all_inputs(self, tvchart_defaults_js: str):
        """_tvInteractiveNavigationOptions must enable mouse wheel, pressed
        mouse move (pan), and pinch zoom."""
        body = self._fn(tvchart_defaults_js, "_tvInteractiveNavigationOptions")
        for opt in ("mouseWheel: true", "pressedMouseMove: true", "pinch: true"):
            assert opt in body, f"Interactive navigation must have {opt}"

    # ------------------------------------------------------------------
    # Chart-type change: ordering & scoping
    # ------------------------------------------------------------------

    def test_chart_type_change_adds_new_series_before_removing_old(self, tvchart_defaults_js: str):
        """Chart-type switching must add the replacement series BEFORE removing
        the old one.  If the old (sole) series in a pane is removed first the
        pane is destroyed and renumbered by Lightweight Charts, causing the new
        series to land in the wrong pane."""
        handler = self._handler(tvchart_defaults_js, "tvchart:chart-type-change")
        add_pos = handler.index("_tvAddSeriesCompat(entry.chart,")
        remove_pos = handler.index("entry.chart.removeSeries(oldSeries)")
        assert add_pos < remove_pos, (
            "chart-type-change handler must call _tvAddSeriesCompat BEFORE "
            "removeSeries to prevent pane collapse"
        )

    def test_settings_rebuild_adds_new_series_before_removing_old(self, tvchart_defaults_js: str):
        """Series-settings OK handler must also add-then-remove to keep the
        pane alive while replacing the series object."""
        anchor = "_tvAddSeriesCompat(entry.chart, targetType, rebuiltOptions"
        settings_start = tvchart_defaults_js.index(anchor)
        region = tvchart_defaults_js[max(0, settings_start - 600) : settings_start + 600]
        add_pos = region.index(anchor)
        remove_pos = region.index("entry.chart.removeSeries(oldSeries)")
        assert add_pos < remove_pos, (
            "series-settings rebuild must call _tvAddSeriesCompat BEFORE "
            "removeSeries to prevent pane collapse"
        )

    def test_chart_type_change_handler_scoped_to_single_chart(self, tvchart_defaults_js: str):
        """Chart-type changes must target a single resolved chart entry, never
        iterate over all charts globally."""
        handler = self._handler(tvchart_defaults_js, "tvchart:chart-type-change")
        assert "_tvResolveChartEntry(" in handler, (
            "handler must use _tvResolveChartEntry to scope to one chart"
        )
        assert "Object.keys(window.__PYWRY_TVCHARTS__)" not in handler, (
            "handler must NOT iterate over all charts"
        )

    # ------------------------------------------------------------------
    # Baseline series & chart creation
    # ------------------------------------------------------------------

    def test_baseline_series_computes_base_value_in_both_paths(self, tvchart_defaults_js: str):
        """Baseline series must compute baseValue from data in both the
        chart-type-change handler AND the initial CREATE path.  Without this,
        baseValue defaults to 0 and all data renders above the baseline."""
        assert "function _tvComputeBaselineValue(bars, pct)" in tvchart_defaults_js

        handler = self._handler(tvchart_defaults_js, "tvchart:chart-type-change")
        assert "_tvComputeBaselineValue(" in handler, (
            "chart-type-change must compute baseValue for Baseline type"
        )

        create = self._create_body(tvchart_defaults_js)
        assert "_tvComputeBaselineValue(" in create, (
            "PYWRY_TVCHART_CREATE must compute baseValue for Baseline type"
        )

    def test_create_branches_on_datafeed_mode(self, tvchart_defaults_js: str):
        """PYWRY_TVCHART_CREATE must branch on payload.useDatafeed to select
        between static-data and streaming-datafeed initialisation."""
        create = self._create_body(tvchart_defaults_js)
        assert "payload.useDatafeed" in create
        assert "_tvInitDatafeedMode(" in create

    def test_datafeed_init_orchestrates_full_protocol(self, tvchart_defaults_js: str):
        """_tvInitDatafeedMode must create a datafeed and call all required
        TradingView Datafeed API methods (onReady, resolveSymbol, getBars,
        subscribeBars) to establish the streaming connection."""
        body = self._fn(tvchart_defaults_js, "_tvInitDatafeedMode")
        assert "_tvCreateDatafeed(" in body
        for method in ("onReady", "resolveSymbol", "getBars", "subscribeBars"):
            assert f"datafeed.{method}(" in body, (
                f"_tvInitDatafeedMode must call datafeed.{method}()"
            )

    # ------------------------------------------------------------------
    # Layout export (no raw data, portable)
    # ------------------------------------------------------------------

    def test_layout_export_excludes_raw_data_and_visible_range(self, tvchart_defaults_js: str):
        """_tvExportLayout must export indicators, drawings, and settings
        but NOT rawData or visibleRange (layouts are portable)."""
        body = self._fn(tvchart_defaults_js, "_tvExportLayout")
        # Must export these
        assert "indicators" in body
        assert "drawings" in body
        assert "settings" in body or "_tvBuildCurrentSettings" in body
        # Must NOT include raw bar data (that's for state, not layout)
        assert "rawData:" not in body
        # Must NOT include visibleRange
        assert "visibleRange:" not in body

    def test_layout_export_preserves_grouped_indicator_metadata(self, tvchart_defaults_js: str):
        """_tvExportLayout must preserve group-specific metadata like multiplier,
        maType, offset, and source so grouped indicators (e.g. Bollinger Bands)
        can be faithfully restored."""
        body = self._fn(tvchart_defaults_js, "_tvExportLayout")
        for field in ("multiplier", "maType", "offset", "source"):
            assert field in body, f"_tvExportLayout must preserve '{field}' for grouped indicators"


# =============================================================================
# TVChartStateMixin tests
# =============================================================================


class _MockEmitter(TVChartStateMixin):
    """Concrete class for testing the mixin."""

    def __init__(self):
        self._emitted: list[tuple[str, Any]] = []

    def emit(self, event_type: str, data: dict[str, Any] | None = None) -> None:
        self._emitted.append((event_type, data))


class TestTVChartStateMixin:
    """Test TVChartStateMixin methods emit correct events."""

    def test_update_series(self):
        m = _MockEmitter()
        m.update_series([{"time": 1, "open": 1, "high": 2, "low": 0, "close": 1}])
        assert len(m._emitted) == 1
        event, payload = m._emitted[0]
        assert event == "tvchart:update"
        assert "bars" in payload
        assert payload["fitContent"] is True

    def test_update_bar(self):
        m = _MockEmitter()
        bar = {"time": 1700000000, "open": 100, "high": 105, "low": 98, "close": 103}
        m.update_bar(bar)
        assert len(m._emitted) == 1
        event, payload = m._emitted[0]
        assert event == "tvchart:stream"
        assert payload["bar"] is bar

    def test_update_bar_with_volume(self):
        m = _MockEmitter()
        bar = {
            "time": 1700000000,
            "open": 100,
            "high": 105,
            "low": 98,
            "close": 103,
            "volume": 5000,
        }
        m.update_bar(bar)
        _event, payload = m._emitted[0]
        assert "volume" in payload
        assert payload["volume"]["value"] == 5000

    def test_add_indicator(self):
        m = _MockEmitter()
        indicator_data = [{"time": 1, "value": 50}, {"time": 2, "value": 55}]
        m.add_indicator(indicator_data, series_id="sma20", series_type="Line")
        event, payload = m._emitted[0]
        assert event == "tvchart:add-series"
        assert payload["seriesId"] == "sma20"
        assert payload["seriesType"] == "Line"
        assert payload["bars"] is indicator_data

    def test_remove_indicator(self):
        m = _MockEmitter()
        m.remove_indicator("sma20")
        event, payload = m._emitted[0]
        assert event == "tvchart:remove-series"
        assert payload["seriesId"] == "sma20"

    # -------- built-in indicator engine (JS-side compute) ---------------

    def test_add_builtin_indicator_minimal(self):
        m = _MockEmitter()
        m.add_builtin_indicator("RSI")
        event, payload = m._emitted[0]
        assert event == "tvchart:add-indicator"
        assert payload == {"name": "RSI"}

    def test_add_builtin_indicator_with_period_and_color(self):
        m = _MockEmitter()
        m.add_builtin_indicator("Moving Average", period=50, color="#2196F3", method="SMA")
        event, payload = m._emitted[0]
        assert event == "tvchart:add-indicator"
        assert payload["name"] == "Moving Average"
        assert payload["method"] == "SMA"
        assert payload["period"] == 50
        assert payload["color"] == "#2196F3"

    def test_add_builtin_indicator_passes_bollinger_options(self):
        m = _MockEmitter()
        m.add_builtin_indicator(
            "Bollinger Bands",
            period=20,
            multiplier=2.0,
            ma_type="SMA",
            offset=0,
            source="close",
        )
        _event, payload = m._emitted[0]
        # Note: ma_type → maType in payload (per the wire contract)
        assert payload["multiplier"] == 2.0
        assert payload["maType"] == "SMA"
        assert payload["offset"] == 0
        assert payload["source"] == "close"

    def test_add_builtin_indicator_omits_unset_options(self):
        m = _MockEmitter()
        m.add_builtin_indicator("RSI", period=12)
        _event, payload = m._emitted[0]
        # Only the explicit fields land in the payload
        assert set(payload.keys()) == {"name", "period"}

    def test_add_builtin_indicator_chart_id(self):
        m = _MockEmitter()
        m.add_builtin_indicator("Moving Average", period=10, method="SMA", chart_id="alt")
        _event, payload = m._emitted[0]
        assert payload["chartId"] == "alt"

    def test_add_builtin_indicator_with_method(self):
        m = _MockEmitter()
        m.add_builtin_indicator("Moving Average", period=14, method="EMA")
        _event, payload = m._emitted[0]
        assert payload["method"] == "EMA"

    def test_remove_builtin_indicator(self):
        m = _MockEmitter()
        m.remove_builtin_indicator("ind_sma_99")
        event, payload = m._emitted[0]
        assert event == "tvchart:remove-indicator"
        assert payload == {"seriesId": "ind_sma_99"}

    def test_remove_builtin_indicator_with_chart_id(self):
        m = _MockEmitter()
        m.remove_builtin_indicator("ind_sma_99", chart_id="alt")
        _event, payload = m._emitted[0]
        assert payload["chartId"] == "alt"

    def test_list_indicators_default(self):
        m = _MockEmitter()
        m.list_indicators()
        event, payload = m._emitted[0]
        assert event == "tvchart:list-indicators"
        assert payload == {}

    def test_list_indicators_with_context(self):
        m = _MockEmitter()
        m.list_indicators(chart_id="alt", context={"trigger": "init"})
        _event, payload = m._emitted[0]
        assert payload["chartId"] == "alt"
        assert payload["context"] == {"trigger": "init"}

    def test_add_marker(self):
        m = _MockEmitter()
        markers = [
            {
                "time": 1,
                "position": "aboveBar",
                "shape": "arrowDown",
                "color": "red",
                "text": "Sell",
            }
        ]
        m.add_marker(markers)
        event, payload = m._emitted[0]
        assert event == "tvchart:add-markers"
        assert payload["markers"] is markers

    def test_add_price_line(self):
        m = _MockEmitter()
        m.add_price_line(150.0, color="#ff0000", title="Resistance")
        event, payload = m._emitted[0]
        assert event == "tvchart:add-price-line"
        assert payload["price"] == 150.0
        assert payload["color"] == "#ff0000"
        assert payload["title"] == "Resistance"

    def test_set_visible_range(self):
        m = _MockEmitter()
        m.set_visible_range(1700000000, 1700500000)
        event, payload = m._emitted[0]
        assert event == "tvchart:time-scale"
        assert payload["visibleRange"]["from"] == 1700000000
        assert payload["visibleRange"]["to"] == 1700500000

    def test_fit_content(self):
        m = _MockEmitter()
        m.fit_content()
        event, payload = m._emitted[0]
        assert event == "tvchart:time-scale"
        assert payload["fitContent"] is True

    def test_apply_chart_options(self):
        m = _MockEmitter()
        m.apply_chart_options(chart_options={"layout": {"background": {"color": "#000"}}})
        event, payload = m._emitted[0]
        assert event == "tvchart:apply-options"
        assert "chartOptions" in payload

    def test_request_tvchart_state(self):
        m = _MockEmitter()
        m.request_tvchart_state(chart_id="chart1")
        event, payload = m._emitted[0]
        assert event == "tvchart:request-state"
        assert payload["chartId"] == "chart1"

    def test_request_tvchart_state_with_context(self):
        m = _MockEmitter()
        m.request_tvchart_state(
            chart_id="chart1", context={"target_view": "watchlist", "reason": "reload"}
        )
        event, payload = m._emitted[0]
        assert event == "tvchart:request-state"
        assert payload["chartId"] == "chart1"
        assert payload["context"] == {"target_view": "watchlist", "reason": "reload"}

    def test_chart_id_propagation(self):
        m = _MockEmitter()
        m.update_series([], chart_id="chart42")
        _, payload = m._emitted[0]
        assert payload["chartId"] == "chart42"

    def test_series_id_propagation(self):
        m = _MockEmitter()
        m.update_series([], series_id="overlay")
        _, payload = m._emitted[0]
        assert payload["seriesId"] == "overlay"

    def test_request_tvchart_symbol_search(self):
        m = _MockEmitter()
        m.request_tvchart_symbol_search(
            "aapl",
            request_id="req-s-1",
            chart_id="chart1",
            limit=7,
            exchange="NASDAQ",
            symbol_type="stock",
        )
        event, payload = m._emitted[0]
        assert event == "tvchart:datafeed-search-request"
        assert payload["query"] == "aapl"
        assert payload["requestId"] == "req-s-1"
        assert payload["chartId"] == "chart1"
        assert payload["limit"] == 7
        assert payload["exchange"] == "NASDAQ"
        assert payload["symbolType"] == "stock"

    def test_respond_tvchart_symbol_search(self):
        m = _MockEmitter()
        m.respond_tvchart_symbol_search(
            request_id="req-s-2",
            items=[{"symbol": "NASDAQ:AAPL", "fullName": "Apple Inc."}],
            chart_id="chart1",
            query="app",
        )
        event, payload = m._emitted[0]
        assert event == "tvchart:datafeed-search-response"
        assert payload["requestId"] == "req-s-2"
        assert payload["items"][0]["symbol"] == "NASDAQ:AAPL"
        assert payload["chartId"] == "chart1"
        assert payload["query"] == "app"

    def test_request_and_respond_tvchart_symbol_resolve(self):
        m = _MockEmitter()
        m.request_tvchart_symbol_resolve("NASDAQ:AAPL", request_id="req-r-1", chart_id="chart1")
        event, payload = m._emitted[0]
        assert event == "tvchart:datafeed-resolve-request"
        assert payload["symbol"] == "NASDAQ:AAPL"
        assert payload["requestId"] == "req-r-1"

        m.respond_tvchart_symbol_resolve(
            request_id="req-r-1",
            symbol_info={"symbol": "NASDAQ:AAPL", "fullName": "Apple Inc."},
            chart_id="chart1",
        )
        event, payload = m._emitted[1]
        assert event == "tvchart:datafeed-resolve-response"
        assert payload["requestId"] == "req-r-1"
        assert payload["symbolInfo"]["symbol"] == "NASDAQ:AAPL"

    def test_request_and_respond_tvchart_history(self):
        m = _MockEmitter()
        m.request_tvchart_history(
            symbol="NASDAQ:AAPL",
            resolution="1D",
            from_time=1_700_000_000,
            to_time=1_700_086_400,
            request_id="req-h-1",
            chart_id="chart1",
            count_back=300,
            first_data_request=True,
        )
        event, payload = m._emitted[0]
        assert event == "tvchart:datafeed-history-request"
        assert payload["symbol"] == "NASDAQ:AAPL"
        assert payload["resolution"] == "1D"
        assert payload["from"] == 1_700_000_000
        assert payload["to"] == 1_700_086_400
        assert payload["countBack"] == 300
        assert payload["firstDataRequest"] is True

        m.respond_tvchart_history(
            request_id="req-h-1",
            bars=[{"time": 1_700_000_000, "value": 123.4}],
            status="ok",
            chart_id="chart1",
            no_data=False,
            next_time=1_699_900_000,
        )
        event, payload = m._emitted[1]
        assert event == "tvchart:datafeed-history-response"
        assert payload["requestId"] == "req-h-1"
        assert payload["status"] == "ok"
        assert payload["bars"][0]["value"] == 123.4
        assert payload["noData"] is False
        assert payload["nextTime"] == 1_699_900_000

    def test_respond_tvchart_datafeed_config(self):
        m = _MockEmitter()
        m.respond_tvchart_datafeed_config(
            request_id="cfg-1",
            config={"supported_resolutions": ["1", "5", "1D"], "supports_marks": True},
            chart_id="chart1",
        )
        event, payload = m._emitted[0]
        assert event == "tvchart:datafeed-config-response"
        assert payload["requestId"] == "cfg-1"
        assert payload["config"]["supports_marks"] is True

    def test_respond_tvchart_bar_update(self):
        m = _MockEmitter()
        m.respond_tvchart_bar_update(
            listener_guid="guid-abc",
            bar={
                "time": 1700000000000,
                "open": 100,
                "high": 105,
                "low": 99,
                "close": 103,
                "volume": 50000,
            },
            chart_id="chart1",
        )
        event, payload = m._emitted[0]
        assert event == "tvchart:datafeed-bar-update"
        assert payload["listenerGuid"] == "guid-abc"
        assert payload["bar"]["close"] == 103

    def test_respond_tvchart_reset_cache(self):
        m = _MockEmitter()
        m.respond_tvchart_reset_cache(listener_guid="guid-abc", chart_id="chart1")
        event, payload = m._emitted[0]
        assert event == "tvchart:datafeed-reset-cache"
        assert payload["listenerGuid"] == "guid-abc"

    def test_respond_tvchart_marks(self):
        m = _MockEmitter()
        m.respond_tvchart_marks(
            request_id="m-1",
            marks=[{"id": "mk1", "time": 1700000000, "color": "red", "text": "Buy"}],
            chart_id="chart1",
        )
        event, payload = m._emitted[0]
        assert event == "tvchart:datafeed-marks-response"
        assert payload["requestId"] == "m-1"


class _WirableEmitter(_MockEmitter):
    """Mock emitter with on() support for wiring tests."""

    def __init__(self):
        super().__init__()
        self._handlers: dict[str, list] = {}

    def on(self, event: str, callback, label=None):
        self._handlers.setdefault(event, []).append(callback)

    def fire(self, event: str, data: dict):
        for cb in self._handlers.get(event, []):
            cb(data, event, "test-label")


class TestDatafeedDataRequestWiring:
    """Verify that _wire_datafeed_provider registers a data-request handler."""

    def test_data_request_handler_registered(self):
        from unittest.mock import AsyncMock

        from pywry.tvchart.datafeed import DatafeedProvider

        provider = AsyncMock(spec=DatafeedProvider)
        provider.supports_search = False
        provider.get_config = AsyncMock(return_value={})

        m = _WirableEmitter()
        m._wire_datafeed_provider(provider)

        assert "tvchart:data-request" in m._handlers

    def test_data_request_echoes_interval(self):
        from unittest.mock import AsyncMock

        from pywry.tvchart.datafeed import DatafeedProvider

        provider = AsyncMock(spec=DatafeedProvider)
        provider.supports_search = False
        provider.get_config = AsyncMock(return_value={})
        provider.get_bars = AsyncMock(
            return_value={
                "bars": [{"time": 1700000000, "open": 100, "high": 105, "low": 98, "close": 103}],
                "status": "ok",
            }
        )

        m = _WirableEmitter()
        m._wire_datafeed_provider(provider)

        m.fire(
            "tvchart:data-request",
            {
                "chartId": "main",
                "interval": "6M",
                "symbol": "AAPL",
                "periodParams": {"from": 0, "to": 1700000000, "countBack": 300},
            },
        )

        assert len(m._emitted) == 1
        event, payload = m._emitted[0]
        assert event == "tvchart:data-response"
        assert payload["interval"] == "6M"
        assert len(payload["bars"]) == 1
        assert payload["chartId"] == "main"
        # Verify provider.get_bars was called with correct args
        provider.get_bars.assert_called_once_with("AAPL", "6M", 0, 1700000000, 300)


class TestTVChartStateMixinResponders:
    """Remaining responder tests (continued from TestTVChartStateMixin)."""

    def test_respond_tvchart_timescale_marks(self):
        m = _MockEmitter()
        m.respond_tvchart_timescale_marks(
            request_id="ts-1",
            marks=[
                {"id": "ts1", "time": 1700000000, "color": "blue", "label": "D", "tooltip": ["Div"]}
            ],
            chart_id="chart1",
        )
        event, payload = m._emitted[0]
        assert event == "tvchart:datafeed-timescale-marks-response"
        assert payload["requestId"] == "ts-1"
        assert len(payload["marks"]) == 1

    def test_respond_tvchart_server_time(self):
        m = _MockEmitter()
        m.respond_tvchart_server_time(
            request_id="st-1",
            time=1700000000,
            chart_id="chart1",
        )
        event, payload = m._emitted[0]
        assert event == "tvchart:datafeed-server-time-response"
        assert payload["requestId"] == "st-1"
        assert payload["time"] == 1700000000

    def test_normalize_tvchart_data_list(self):
        bars = [{"time": 1, "open": 1, "high": 2, "low": 0, "close": 1}]
        result_bars, result_vol = TVChartStateMixin._normalize_tvchart_data(bars)
        assert result_bars is bars
        assert result_vol == []


# =============================================================================
# Widget class shape tests
# =============================================================================


class TestPyWryTVChartWidgetShape:
    """Verify the TVChart widget class exists with expected attributes."""

    def test_class_exists(self):
        from pywry.widget import PyWryTVChartWidget

        assert PyWryTVChartWidget is not None

    def test_fallback_instantiation(self):
        """The widget can be instantiated (at minimum as fallback)."""
        from pywry.widget import PyWryTVChartWidget

        w = PyWryTVChartWidget(content="<div>test</div>")
        assert hasattr(w, "content")

    def test_has_emit_method(self):
        from pywry.widget import PyWryTVChartWidget

        w = PyWryTVChartWidget(content="")
        assert callable(getattr(w, "emit", None))

    def test_has_on_method(self):
        from pywry.widget import PyWryTVChartWidget

        w = PyWryTVChartWidget(content="")
        assert callable(getattr(w, "on", None))


# =============================================================================
# Public API import tests
# =============================================================================


class TestPublicAPIImports:
    """Verify all new symbols are exported from pywry.__init__."""

    def test_import_tvchart_config(self):
        from pywry import TVChartConfig as PublicTVChartConfig

        assert PublicTVChartConfig is not None

    def test_import_tvchart_data(self):
        from pywry import TVChartData as PublicTVChartData

        assert PublicTVChartData is not None

    def test_import_tvchart_datafeed_models(self):
        from pywry import (
            TVChartBar,
            TVChartDatafeedBarUpdate,
            TVChartDatafeedConfigRequest,
            TVChartDatafeedConfigResponse,
            TVChartDatafeedConfiguration,
            TVChartDatafeedHistoryRequest,
            TVChartDatafeedHistoryResponse,
            TVChartDatafeedMarksRequest,
            TVChartDatafeedMarksResponse,
            TVChartDatafeedResolveRequest,
            TVChartDatafeedResolveResponse,
            TVChartDatafeedSearchRequest,
            TVChartDatafeedSearchResponse,
            TVChartDatafeedServerTimeRequest,
            TVChartDatafeedServerTimeResponse,
            TVChartDatafeedSubscribeRequest,
            TVChartDatafeedSymbolType,
            TVChartDatafeedTimescaleMarksRequest,
            TVChartDatafeedTimescaleMarksResponse,
            TVChartDatafeedUnsubscribeRequest,
            TVChartExchange,
            TVChartLibrarySubsessionInfo,
            TVChartMark,
            TVChartSearchSymbolResultItem,
            TVChartSymbolInfo,
            TVChartSymbolInfoPriceSource,
            TVChartTimescaleMark,
        )

        assert TVChartBar is not None
        assert TVChartDatafeedBarUpdate is not None
        assert TVChartDatafeedConfigRequest is not None
        assert TVChartDatafeedConfigResponse is not None
        assert TVChartDatafeedConfiguration is not None
        assert TVChartDatafeedHistoryRequest is not None
        assert TVChartDatafeedHistoryResponse is not None
        assert TVChartDatafeedMarksRequest is not None
        assert TVChartDatafeedMarksResponse is not None
        assert TVChartDatafeedResolveRequest is not None
        assert TVChartDatafeedResolveResponse is not None
        assert TVChartDatafeedSearchRequest is not None
        assert TVChartDatafeedSearchResponse is not None
        assert TVChartDatafeedServerTimeRequest is not None
        assert TVChartDatafeedServerTimeResponse is not None
        assert TVChartDatafeedSubscribeRequest is not None
        assert TVChartDatafeedSymbolType is not None
        assert TVChartDatafeedTimescaleMarksRequest is not None
        assert TVChartDatafeedTimescaleMarksResponse is not None
        assert TVChartDatafeedUnsubscribeRequest is not None
        assert TVChartExchange is not None
        assert TVChartLibrarySubsessionInfo is not None
        assert TVChartMark is not None
        assert TVChartSearchSymbolResultItem is not None
        assert TVChartSymbolInfo is not None
        assert TVChartSymbolInfoPriceSource is not None
        assert TVChartTimescaleMark is not None

    def test_import_tvchart_state_mixin(self):
        from pywry import TVChartStateMixin

        assert TVChartStateMixin is not None

    def test_import_pywry_tvchart_widget(self):
        from pywry import PyWryTVChartWidget

        assert PyWryTVChartWidget is not None

    def test_import_show_tvchart(self):
        from pywry import show_tvchart

        assert callable(show_tvchart)

    def test_import_build_tvchart_toolbars(self):
        from pywry import build_tvchart_toolbars

        assert callable(build_tvchart_toolbars)

    def test_all_in_dunder_all(self):
        import pywry

        all_names = pywry.__all__
        for name in [
            "TVChartBar",
            "TVChartConfig",
            "TVChartData",
            "TVChartDatafeedBarUpdate",
            "TVChartDatafeedConfigRequest",
            "TVChartDatafeedConfigResponse",
            "TVChartDatafeedConfiguration",
            "TVChartDatafeedHistoryRequest",
            "TVChartDatafeedHistoryResponse",
            "TVChartDatafeedMarksRequest",
            "TVChartDatafeedMarksResponse",
            "TVChartDatafeedResolveRequest",
            "TVChartDatafeedResolveResponse",
            "TVChartDatafeedSearchRequest",
            "TVChartDatafeedSearchResponse",
            "TVChartDatafeedServerTimeRequest",
            "TVChartDatafeedServerTimeResponse",
            "TVChartDatafeedSubscribeRequest",
            "TVChartDatafeedSymbolType",
            "TVChartDatafeedTimescaleMarksRequest",
            "TVChartDatafeedTimescaleMarksResponse",
            "TVChartDatafeedUnsubscribeRequest",
            "TVChartExchange",
            "TVChartLibrarySubsessionInfo",
            "TVChartMark",
            "TVChartSearchSymbolResultItem",
            "TVChartSymbolInfo",
            "TVChartSymbolInfoPriceSource",
            "TVChartTimescaleMark",
            "TVChartStateMixin",
            "PyWryTVChartWidget",
            "show_tvchart",
            "build_tvchart_toolbars",
        ]:
            assert name in all_names, f"{name} not in __all__"


# =============================================================================
# show_tvchart wiring tests
# =============================================================================


class TestShowTVChartSignature:
    """Test that show_tvchart has the expected signature."""

    def test_signature_params(self):
        import inspect

        from pywry.inline import show_tvchart

        sig = inspect.signature(show_tvchart)
        params = list(sig.parameters.keys())
        assert "data" in params
        assert "callbacks" in params
        assert "title" in params
        assert "width" in params
        assert "height" in params
        assert "theme" in params
        assert "chart_options" in params
        assert "series_options" in params
        assert "symbol_col" in params
        assert "max_bars" in params
        assert "toolbars" in params
        assert "use_datafeed" in params
        assert "symbol" in params
        assert "resolution" in params

    def test_data_defaults_to_none(self):
        import inspect

        from pywry.inline import show_tvchart

        sig = inspect.signature(show_tvchart)
        assert sig.parameters["data"].default is None

    def test_use_datafeed_defaults_to_false(self):
        import inspect

        from pywry.inline import show_tvchart

        sig = inspect.signature(show_tvchart)
        assert sig.parameters["use_datafeed"].default is False

    def test_resolution_defaults_to_1d(self):
        import inspect

        from pywry.inline import show_tvchart

        sig = inspect.signature(show_tvchart)
        assert sig.parameters["resolution"].default == "1D"


# =============================================================================
# Indicator catalog + compute + recompute coverage
# =============================================================================


class TestTVChartIndicatorCatalog:
    """Every indicator advertised by the catalog must have:

    * a compute function present in the bundled JS,
    * an add-indicator branch that creates its series, and
    * a recompute branch in ``_tvRecomputeIndicatorSeries`` so it refreshes
      when underlying bars change (otherwise indicators silently freeze at
      their initial snapshot when the datafeed replaces bars — exactly the
      bug that made VWAP show 9.99 on a $270 stock).
    """

    @pytest.fixture
    def js(self) -> str:
        from pywry.assets import get_tvchart_defaults_js

        return get_tvchart_defaults_js()

    # ------------------------------------------------------------------
    # Catalog entries
    # ------------------------------------------------------------------

    EXPECTED_CATALOG_NAMES = (
        "Moving Average",
        "Ichimoku Cloud",
        "Bollinger Bands",
        "Keltner Channels",
        "ATR",
        "Historical Volatility",
        "Parabolic SAR",
        "RSI",
        "MACD",
        "Stochastic",
        "Williams %R",
        "CCI",
        "ADX",
        "Aroon",
        "VWAP",
        "Volume SMA",
        "Accumulation/Distribution",
        "Volume Profile Fixed Range",
        "Volume Profile Visible Range",
    )

    @pytest.mark.parametrize("name", EXPECTED_CATALOG_NAMES)
    def test_catalog_contains_indicator(self, js: str, name: str) -> None:
        cat_start = js.index("_INDICATOR_CATALOG = [")
        cat_end = js.index("];", cat_start)
        catalog_src = js[cat_start:cat_end]
        assert f"name: '{name}'" in catalog_src, f"Indicator catalog missing entry for '{name}'"

    def test_volume_profile_entries_are_primitive(self, js: str) -> None:
        cat_start = js.index("_INDICATOR_CATALOG = [")
        cat_end = js.index("];", cat_start)
        catalog_src = js[cat_start:cat_end]
        for key in ("'volume-profile-fixed'", "'volume-profile-visible'"):
            block = catalog_src[catalog_src.index(key) :]
            first_close = block.index("}")
            entry = block[:first_close]
            assert "primitive: true" in entry, f"Expected VP entry {key} to have primitive: true"

    # ------------------------------------------------------------------
    # Compute functions
    # ------------------------------------------------------------------

    EXPECTED_COMPUTE_FNS = (
        "_computeSMA",
        "_computeEMA",
        "_computeWMA",
        "_computeHMA",
        "_computeVWMA",
        "_computeRSI",
        "_computeATR",
        "_computeBollingerBands",
        "_computeKeltnerChannels",
        "_computeVWAP",
        "_computeMACD",
        "_computeStochastic",
        "_computeAroon",
        "_computeADX",
        "_computeCCI",
        "_computeWilliamsR",
        "_computeAccumulationDistribution",
        "_computeHistoricalVolatility",
        "_computeIchimoku",
        "_computeParabolicSAR",
    )

    @pytest.mark.parametrize("fn_name", EXPECTED_COMPUTE_FNS)
    def test_compute_function_defined(self, js: str, fn_name: str) -> None:
        assert f"function {fn_name}(" in js, f"Missing compute function {fn_name} in bundled JS"

    # ------------------------------------------------------------------
    # Add-indicator branches
    # ------------------------------------------------------------------

    ADD_BRANCHES = (
        ("name === 'VWAP'", "_computeVWAP"),
        ("name === 'MACD'", "_computeMACD"),
        ("name === 'Stochastic'", "_computeStochastic"),
        ("name === 'Aroon'", "_computeAroon"),
        ("name === 'ADX'", "_computeADX"),
        ("name === 'CCI'", "_computeCCI"),
        ("name === 'Williams %R'", "_computeWilliamsR"),
        ("name === 'Accumulation/Distribution'", "_computeAccumulationDistribution"),
        ("name === 'Historical Volatility'", "_computeHistoricalVolatility"),
        ("name === 'Keltner Channels'", "_computeKeltnerChannels"),
        ("name === 'Ichimoku Cloud'", "_computeIchimoku"),
        ("name === 'Parabolic SAR'", "_computeParabolicSAR"),
    )

    @pytest.mark.parametrize("branch,fn", ADD_BRANCHES)
    def test_add_branch_wires_compute(self, js: str, branch: str, fn: str) -> None:
        assert branch in js, f"Missing add-indicator branch '{branch}' in 04-series.js"
        # Narrow the search: compute call must appear after the branch and
        # before the next `} else if (name ===` marker.
        branch_idx = js.index(branch)
        next_branch = js.find("} else if (name ===", branch_idx + 1)
        if next_branch < 0:
            next_branch = js.find("_tvAddIndicator fallthrough", branch_idx + 1)
        segment = js[branch_idx : next_branch if next_branch > 0 else branch_idx + 2000]
        assert fn in segment, (
            f"Branch for '{branch}' should call {fn}() but didn't within 2000 chars"
        )

    # ------------------------------------------------------------------
    # Recompute branches (THIS is the bug that caused VWAP=9.99)
    # ------------------------------------------------------------------

    @pytest.fixture
    def recompute_body(self, js: str) -> str:
        start = js.index("function _tvRecomputeIndicatorSeries(")
        # Find matching close brace for the function
        depth = 0
        i = js.index("{", start)
        n = len(js)
        while i < n:
            ch = js[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return js[start : i + 1]
            i += 1
        raise RuntimeError("Could not find end of _tvRecomputeIndicatorSeries")

    RECOMPUTE_BRANCHES = (
        ("info.name === 'VWAP'", "_computeVWAP"),
        ("info.name === 'CCI'", "_computeCCI"),
        ("info.name === 'Williams %R'", "_computeWilliamsR"),
        ("info.name === 'Accumulation/Distribution'", "_computeAccumulationDistribution"),
        ("info.name === 'Historical Volatility'", "_computeHistoricalVolatility"),
        ("type === 'parabolic-sar'", "_computeParabolicSAR"),
        ("type === 'macd'", "_computeMACD"),
        ("type === 'stochastic'", "_computeStochastic"),
        ("type === 'aroon'", "_computeAroon"),
        ("type === 'adx'", "_computeADX"),
        ("type === 'keltner-channels'", "_computeKeltnerChannels"),
        ("type === 'ichimoku'", "_computeIchimoku"),
    )

    @pytest.mark.parametrize("branch,fn", RECOMPUTE_BRANCHES)
    def test_recompute_branch_refreshes_series(
        self, recompute_body: str, branch: str, fn: str
    ) -> None:
        assert branch in recompute_body, (
            f"_tvRecomputeIndicatorSeries missing branch for {branch!r}. "
            "Without this branch, the indicator won't refresh when bars "
            "change (e.g., via datafeed scrollback or interval switch) "
            "and will stay frozen at its initial snapshot."
        )
        idx = recompute_body.index(branch)
        tail = recompute_body[idx : idx + 2500]
        assert fn in tail, (
            f"Recompute branch {branch!r} found but never calls {fn}() "
            "within the following 2500 chars — did the branch get broken?"
        )

    def test_recompute_branch_for_volume_profile(self, recompute_body: str) -> None:
        """Visible-range volume profiles must recompute when the bar set
        changes — otherwise scrolling into new data leaves their right-pinned
        rows reflecting the old range."""
        assert "type === 'volume-profile-visible'" in recompute_body
        assert "_tvRefreshVisibleVolumeProfiles" in recompute_body


# =============================================================================
# Volume Profile compute contract
# =============================================================================


class TestTVChartVolumeProfile:
    """Tests for _tvComputeVolumeProfile — the pure function behind VPVR."""

    @pytest.fixture
    def js(self) -> str:
        from pywry.assets import get_tvchart_defaults_js

        return get_tvchart_defaults_js()

    def test_vp_compute_function_signature(self, js: str) -> None:
        assert "function _tvComputeVolumeProfile(bars, fromIdx, toIdx, opts)" in js

    def test_vp_result_returns_profile_and_metadata(self, js: str) -> None:
        fn_start = js.index("function _tvComputeVolumeProfile(")
        fn_end = js.index("\nfunction ", fn_start + 1)
        body = js[fn_start:fn_end]
        for key in ("profile", "minPrice", "maxPrice", "step", "totalVolume"):
            assert key in body, f"VP compute result missing expected field '{key}'"

    def test_vp_splits_up_down_volume(self, js: str) -> None:
        fn_start = js.index("function _tvComputeVolumeProfile(")
        fn_end = js.index("\nfunction ", fn_start + 1)
        body = js[fn_start:fn_end]
        # Up/down split is what differentiates VPVR from a flat histogram.
        assert "upVol" in body and "downVol" in body, (
            "VP compute must split each row into up vs down volume"
        )

    def test_vp_exposes_poc_value_area_helper(self, js: str) -> None:
        """A separate helper derives POC and Value Area from the computed profile."""
        assert "function _tvComputePOCAndValueArea(" in js
        fn_start = js.index("function _tvComputePOCAndValueArea(")
        fn_end = js.index("\nfunction ", fn_start + 1)
        body = js[fn_start:fn_end]
        for key in ("pocIdx", "vaLowIdx", "vaHighIdx"):
            assert key in body, f"POC/VA helper must expose '{key}' so renderer can draw lines"

    def test_vp_refresh_visible_exposed(self, js: str) -> None:
        """Visible-range refresh must exist for the recompute path to call it."""
        assert "function _tvRefreshVisibleVolumeProfiles(chartId)" in js


# =============================================================================
# Legend volume removal actually destroys the series + pane
# =============================================================================


class TestTVChartLegendVolumeRemoval:
    """Removing volume from the legend must actually remove it from the chart
    (issue: previously, clicking Remove only set a legend dataset flag but
    left the histogram series and its pane on the chart)."""

    @pytest.fixture
    def js(self) -> str:
        from pywry.assets import get_tvchart_defaults_js

        return get_tvchart_defaults_js()

    def _fn_or_nested(self, js: str, name: str) -> str:
        """Extract a function body — works for nested ``function X()`` too."""
        idx = js.index(f"function {name}(")
        depth = 0
        i = js.index("{", idx)
        n = len(js)
        while i < n:
            ch = js[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return js[idx : i + 1]
            i += 1
        raise RuntimeError(f"Could not find end of {name}")

    def test_disable_volume_removes_series(self, js: str) -> None:
        body = self._fn_or_nested(js, "_legendDisableVolume")
        assert "entry.chart.removeSeries(volSeries)" in body, (
            "Remove-volume must actually call chart.removeSeries"
        )
        assert "delete entry.volumeMap.main" in body, "Remove-volume must clear the volumeMap entry"

    def test_disable_volume_removes_pane(self, js: str) -> None:
        body = self._fn_or_nested(js, "_legendDisableVolume")
        assert "chart.removePane(removedPane)" in body, (
            "Remove-volume must collapse the now-empty pane, not leave dead space"
        )

    def test_disable_volume_reindexes_panes(self, js: str) -> None:
        body = self._fn_or_nested(js, "_legendDisableVolume")
        # When pane N is removed, LWC reindexes panes > N down by 1. We must
        # mirror that for our bookkeeping on _activeIndicators and _volumePaneBySeries.
        assert ".paneIndex -= 1" in body
        assert "_volumePaneBySeries" in body

    def test_enable_volume_rebuilds_series(self, js: str) -> None:
        body = self._fn_or_nested(js, "_legendEnableVolume")
        assert "_tvAddSeriesCompat(entry.chart, 'Histogram'" in body, (
            "Restore-volume must rebuild the histogram series via the same "
            "path used for initial creation"
        )
        assert "_tvExtractVolumeFromBars" in body, (
            "Restore-volume must re-extract volume from the stored raw bars"
        )


# =============================================================================
# Theme CSS variables — every new VP / indicator color var is defined
# =============================================================================


class TestTVChartThemeVariables:
    """The tvchart.css stylesheet must define every CSS variable that the
    frontend JS consumes, in both dark and light themes (otherwise colors
    silently fall back to whatever the browser decides)."""

    @pytest.fixture
    def css(self) -> str:
        from pathlib import Path

        import pywry

        return (
            Path(pywry.__file__).parent / "frontend" / "style" / "tvchart.css"
        ).read_text(encoding="utf-8")

    VP_VARS = (
        "--pywry-tvchart-vp-up",
        "--pywry-tvchart-vp-down",
        "--pywry-tvchart-vp-va-up",
        "--pywry-tvchart-vp-va-down",
        "--pywry-tvchart-vp-poc",
    )

    INDICATOR_PALETTE_VARS = (
        "--pywry-tvchart-ind-primary",
        "--pywry-tvchart-ind-secondary",
        "--pywry-tvchart-ind-tertiary",
        "--pywry-tvchart-ind-positive",
        "--pywry-tvchart-ind-negative",
        "--pywry-tvchart-ind-positive-dim",
        "--pywry-tvchart-ind-negative-dim",
    )

    @pytest.mark.parametrize("var", VP_VARS + INDICATOR_PALETTE_VARS)
    def test_var_defined_at_least_twice(self, css: str, var: str) -> None:
        """Each var must appear in both the dark (root) and light theme blocks."""
        count = css.count(var + ":")
        assert count >= 2, (
            f"CSS var {var} defined only {count} time(s); expected at least 2 "
            "(one for dark theme, one for light)."
        )


# =============================================================================
# MCP tool definition tests
# =============================================================================


class TestMCPToolDefinition:
    """Verify show_tvchart MCP tool is registered."""

    def test_tool_schema_exists(self):
        from pywry.mcp.tools import get_tools

        names = [t.name for t in get_tools()]
        assert "show_tvchart" in names

    def test_tool_schema_has_data_json(self):
        from pywry.mcp.tools import get_tools

        tool = next(t for t in get_tools() if t.name == "show_tvchart")
        props = tool.inputSchema["properties"]
        assert "data_json" in props

    def test_handler_registered(self):
        from pywry.mcp.handlers import _HANDLERS

        assert "show_tvchart" in _HANDLERS


# ---------------------------------------------------------------------------
# Alternative chart factories: createOptionsChart + createYieldCurveChart
# ---------------------------------------------------------------------------


class TestTVChartSpecialtyChartKinds:
    """Contract checks for the two non-temporal LWC chart factories.

    Lightweight Charts 5.x exposes three factories:
      * createChart              — time X axis (default)
      * createOptionsChart       — numeric price / strike X axis
      * createYieldCurveChart    — tenor-in-months X axis

    PyWry routes these via ``payload.chartKind`` in
    ``PYWRY_TVCHART_CREATE``.  These tests lock down both the dispatch
    logic AND the option builders so future refactors can't silently
    break either branch.
    """

    @pytest.fixture
    def tvchart_defaults_js(self) -> str:
        from pywry.assets import get_tvchart_defaults_js

        return get_tvchart_defaults_js()

    def test_bundle_ships_all_three_builders(self, tvchart_defaults_js: str):
        assert "function _tvBuildChartOptions(" in tvchart_defaults_js
        assert "function _tvBuildPriceChartOptions(" in tvchart_defaults_js
        assert "function _tvBuildYieldCurveChartOptions(" in tvchart_defaults_js

    def test_price_builder_inherits_base_defaults(self, tvchart_defaults_js: str):
        src = tvchart_defaults_js
        start = src.index("function _tvBuildPriceChartOptions(")
        body = TestTVChartFrontendStateContracts._extract_braced(src, start)
        assert "_tvBuildChartOptions(null, theme)" in body, (
            "price chart options must inherit the base PyWry defaults so "
            "palette / interaction / scales stay consistent across factories"
        )

    def test_yield_curve_builder_seeds_yield_curve_options(self, tvchart_defaults_js: str):
        src = tvchart_defaults_js
        start = src.index("function _tvBuildYieldCurveChartOptions(")
        body = TestTVChartFrontendStateContracts._extract_braced(src, start)
        assert "_tvBuildChartOptions(null, theme)" in body
        assert "yieldCurve" in body
        assert "baseResolution" in body
        assert "minimumTimeRange" in body
        assert "startTimeRange" in body

    def test_yield_curve_builder_ignores_whitespace_indices(self, tvchart_defaults_js: str):
        """The crosshair must snap to real tenors — a yield curve has
        irregular whitespace between 2Y and 5Y, 5Y and 10Y, etc."""
        src = tvchart_defaults_js
        start = src.index("function _tvBuildYieldCurveChartOptions(")
        body = TestTVChartFrontendStateContracts._extract_braced(src, start)
        assert "ignoreWhitespaceIndices = true" in body

    def test_create_dispatches_to_price_factory(self, tvchart_defaults_js: str):
        body = TestTVChartFrontendStateContracts()._create_body(tvchart_defaults_js)
        assert "LightweightCharts.createOptionsChart(container, chartOptions)" in body
        assert "chartKind === 'price'" in body

    def test_create_dispatches_to_yield_curve_factory(self, tvchart_defaults_js: str):
        body = TestTVChartFrontendStateContracts()._create_body(tvchart_defaults_js)
        assert "LightweightCharts.createYieldCurveChart(container, chartOptions)" in body
        assert "yield-curve" in body

    def test_create_default_falls_back_to_create_chart(self, tvchart_defaults_js: str):
        body = TestTVChartFrontendStateContracts()._create_body(tvchart_defaults_js)
        assert "LightweightCharts.createChart(container, chartOptions)" in body

    def test_volume_auto_enable_gated_on_default_chart_kind(self, tvchart_defaults_js: str):
        """Auto-volume on price / yield-curve charts would histogram
        by strike / tenor which is meaningless — gate it off."""
        body = TestTVChartFrontendStateContracts()._create_body(tvchart_defaults_js)
        assert "enableVolume !== false && chartKind === 'default'" in body

    def test_time_range_tabs_gated_on_default_chart_kind(self, tvchart_defaults_js: str):
        """'1D / 5D / 1Y / ...' tabs only make sense for time-axis
        charts.  Skip the lookup on specialty kinds."""
        body = TestTVChartFrontendStateContracts()._create_body(tvchart_defaults_js)
        # Guard is an inline `if (chartKind === 'default')` ahead of the
        # `.pywry-tab-active[data-target-interval]` query.
        idx_guard = body.find("chartKind === 'default'")
        idx_tab_query = body.find(".pywry-tab-active[data-target-interval]")
        assert idx_guard != -1 and idx_tab_query != -1
        assert idx_guard < idx_tab_query, (
            "the chartKind guard must appear BEFORE the time-range tab "
            "lookup so non-default charts skip the whole block"
        )


class TestTVChartChartKindConfig:
    """Python typed surface for the chartKind selector.

    Locks in the TVChartConfig literal + the to_payload shape that the
    frontend consumes.
    """

    def test_config_default_is_time_axis(self):
        from pywry.tvchart.config import TVChartConfig

        cfg = TVChartConfig()
        assert cfg.chart_kind == "default"
        assert cfg.yield_curve is None

    def test_config_accepts_price_kind(self):
        from pywry.tvchart.config import TVChartConfig

        cfg = TVChartConfig(chart_kind="price")
        assert cfg.chart_kind == "price"

    def test_config_accepts_yield_curve_kind(self):
        from pywry.tvchart.config import TVChartConfig

        cfg = TVChartConfig(chart_kind="yield-curve")
        assert cfg.chart_kind == "yield-curve"

    def test_config_rejects_unknown_kind(self):
        import pydantic

        from pywry.tvchart.config import TVChartConfig

        with pytest.raises(pydantic.ValidationError):
            TVChartConfig(chart_kind="candlestick")  # type: ignore[arg-type]

    def test_to_payload_exposes_chart_kind_alongside_options(self):
        from pywry.tvchart.config import TVChartConfig

        cfg = TVChartConfig(chart_kind="price")
        payload = cfg.to_payload()
        assert payload["chartKind"] == "price"
        assert isinstance(payload["chartOptions"], dict)

    def test_to_payload_forwards_yield_curve_options(self):
        from pywry.tvchart.config import TVChartConfig

        cfg = TVChartConfig(
            chart_kind="yield-curve",
            yield_curve={
                "baseResolution": 1,
                "minimumTimeRange": 360,
                "startTimeRange": 0,
            },
        )
        payload = cfg.to_payload()
        assert payload["chartKind"] == "yield-curve"
        assert payload["chartOptions"]["yieldCurve"]["minimumTimeRange"] == 360

    def test_to_chart_options_skips_yield_curve_when_unset(self):
        from pywry.tvchart.config import TVChartConfig

        cfg = TVChartConfig(chart_kind="yield-curve")
        opts = cfg.to_chart_options()
        assert "yieldCurve" not in opts, (
            "yield_curve is optional — don't ship an empty block that the "
            "frontend would treat as a wipe of the LWC defaults"
        )


class TestTVChartSpecialtyInlinePayload:
    """The inline (notebook) path must carry chart_kind into the JSON
    payload that gets dumped into the PyWryTVChartWidget's chart_config
    traitlet — that's the only channel the frontend reads."""

    def test_inline_payload_carries_chart_kind(self):
        import inspect

        from pywry import inline as pywry_inline

        src = inspect.getsource(pywry_inline.show_tvchart)
        assert '"chartKind": chart_kind' in src, (
            "chart_kind must land in the JSON config_payload so the "
            "frontend can route to createOptionsChart / "
            "createYieldCurveChart"
        )

    def test_inline_show_tvchart_accepts_chart_kind(self):
        import inspect

        from pywry import inline as pywry_inline

        sig = inspect.signature(pywry_inline.show_tvchart)
        assert "chart_kind" in sig.parameters
        assert sig.parameters["chart_kind"].default == "default"

    def test_app_show_tvchart_accepts_chart_kind(self):
        import inspect

        from pywry.app import PyWry

        sig = inspect.signature(PyWry.show_tvchart)
        assert "chart_kind" in sig.parameters
        assert "yield_curve" in sig.parameters
        assert sig.parameters["chart_kind"].default == "default"

    def test_specialty_demo_cells_in_notebook(self):
        """The TVChart demo notebook must include runnable cells for
        both alternative chart kinds — keeps the documented example in
        sync with the public chart_kind / yield_curve API surface."""
        import ast
        import json

        from pathlib import Path

        nb_path = Path(__file__).resolve().parent.parent / "examples" / "pywry_demo_tvchart.ipynb"
        if not nb_path.exists():
            pytest.skip("demo notebook not bundled in this source tree")
        nb = json.loads(nb_path.read_text(encoding="utf-8"))
        code_cells = [
            "".join(c.get("source", []))
            for c in nb.get("cells", [])
            if c.get("cell_type") == "code"
        ]
        assert any(
            'chart_kind="yield-curve"' in src and "yield_curve" in src for src in code_cells
        ), "notebook missing a yield-curve chart cell"
        assert any('chart_kind="price"' in src for src in code_cells), (
            "notebook missing a price-axis (options payoff) chart cell"
        )
        # Every code cell must still parse as valid Python so stale
        # snippets break this test loudly instead of silently rotting.
        for src in code_cells:
            ast.parse(src)
