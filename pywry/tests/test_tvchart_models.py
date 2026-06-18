"""Tests for ``pywry/tvchart/models.py``.

The data models live in two groups:

* Chart-data containers (``TVChartSeriesData``, ``TVChartData``) used by
  ``normalize_ohlcv`` and the mixin's series-update helpers.
* Datafeed protocol models (``TVChartSymbolInfo``,
  ``TVChartDatafeed*``) that mirror the TradingView Datafeed JSON
  wire contract.

Both sets need to round-trip cleanly through ``model_dump`` so the JS
frontend gets exactly the keys it expects.
"""

from __future__ import annotations

import pytest

from pywry.tvchart.config import SeriesType
from pywry.tvchart.models import (
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
    TVChartSymbolInfo,
    TVChartSymbolInfoPriceSource,
    TVChartTimescaleMark,
)


# =============================================================================
# TVChartSeriesData + TVChartData container properties
# =============================================================================


class TestTVChartSeriesData:
    """Defaults and field validation for the per-series container."""

    def test_defaults(self) -> None:
        s = TVChartSeriesData(series_id="main")
        assert s.series_id == "main"
        assert s.bars == []
        assert s.volume == []
        assert s.series_type == SeriesType.CANDLESTICK
        assert s.has_volume is False
        assert s.total_rows == 0
        assert s.truncated_rows == 0

    def test_explicit_fields(self) -> None:
        s = TVChartSeriesData(
            series_id="AAPL",
            bars=[{"time": 1, "open": 1, "high": 2, "low": 0, "close": 1}],
            volume=[{"time": 1, "value": 1000}],
            series_type=SeriesType.LINE,
            has_volume=True,
            total_rows=1,
            truncated_rows=0,
        )
        assert s.has_volume is True
        assert s.total_rows == 1
        assert s.series_type == SeriesType.LINE


class TestTVChartDataProperties:
    """:class:`TVChartData` exposes shortcuts that fan out across series."""

    def test_bars_property_reads_first_series(self) -> None:
        s = TVChartSeriesData(series_id="main", bars=[{"time": 1, "value": 2}], total_rows=1)
        data = TVChartData(series=[s])
        assert data.bars == [{"time": 1, "value": 2}]

    def test_volume_property_reads_first_series(self) -> None:
        s = TVChartSeriesData(
            series_id="main",
            bars=[{"time": 1, "value": 2}],
            volume=[{"time": 1, "value": 1000}],
            total_rows=1,
        )
        data = TVChartData(series=[s])
        assert data.volume == [{"time": 1, "value": 1000}]

    def test_series_ids_property(self) -> None:
        data = TVChartData(
            series=[
                TVChartSeriesData(series_id="AAPL", bars=[], total_rows=0),
                TVChartSeriesData(series_id="MSFT", bars=[], total_rows=0),
            ]
        )
        assert data.series_ids == ["AAPL", "MSFT"]

    def test_total_rows_sums_all_series(self) -> None:
        data = TVChartData(
            series=[
                TVChartSeriesData(series_id="a", bars=[], total_rows=100),
                TVChartSeriesData(series_id="b", bars=[], total_rows=200),
            ]
        )
        assert data.total_rows == 300

    def test_empty_series_yields_empty_shortcuts(self) -> None:
        data = TVChartData(series=[])
        assert data.bars == []
        assert data.volume == []
        assert data.series_ids == []
        assert data.total_rows == 0

    def test_defaults_for_meta_fields(self) -> None:
        data = TVChartData()
        assert data.columns == []
        assert data.time_column == "time"
        assert data.symbol_column is None
        assert data.is_multi_series is False
        assert data.source_format == "single"
        assert data.column_types == {}


# =============================================================================
# TVChartSymbolInfo (LibrarySymbolInfo mirror)
# =============================================================================


class TestTVChartSymbolInfo:
    """Verifies every optional field is excluded when unset (so the JSON
    wire format stays minimal) and that documented values land where
    expected."""

    def test_required_defaults(self) -> None:
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

    def test_full_fields_round_trip(self) -> None:
        info = TVChartSymbolInfo(
            name="AAPL",
            ticker="AAPL",
            full_name="Apple Inc.",
            description="Apple common stock",
            exchange="NASDAQ",
            listed_exchange="NASDAQ",
            type="stock",
            session="0930-1600",
            timezone="America/New_York",
            currency_code="USD",
            has_intraday=True,
            has_daily=True,
            has_weekly_and_monthly=True,
            supported_resolutions=["1", "5", "15", "60", "1D"],
            intraday_multipliers=["1", "5", "15", "60"],
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
        assert dumped["has_intraday"] is True
        assert dumped["supported_resolutions"] == ["1", "5", "15", "60", "1D"]
        assert dumped["sector"] == "Technology"

    def test_optional_fields_excluded_when_unset(self) -> None:
        info = TVChartSymbolInfo(name="X", description="Test", exchange="NYSE")
        dumped = info.model_dump(exclude_none=True)
        assert "ticker" not in dumped
        assert "has_seconds" not in dumped
        assert "expired" not in dumped
        assert "subsessions" not in dumped

    def test_fractional_format(self) -> None:
        info = TVChartSymbolInfo(
            name="ZBM2023",
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

    def test_subsessions_for_extended_hours(self) -> None:
        info = TVChartSymbolInfo(
            name="ES",
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

    def test_price_sources(self) -> None:
        info = TVChartSymbolInfo(
            name="AAPL",
            price_sources=[
                TVChartSymbolInfoPriceSource(id="1", name="Spot Price"),
                TVChartSymbolInfoPriceSource(id="2", name="Bid"),
            ],
            price_source_id="1",
        )
        dumped = info.model_dump(exclude_none=True)
        assert len(dumped["price_sources"]) == 2
        assert dumped["price_source_id"] == "1"

    def test_symbol_type_alias_field(self) -> None:
        info = TVChartSymbolInfo(name="X", symbol_type="futures")
        dumped = info.model_dump(exclude_none=True)
        assert dumped["symbol_type"] == "futures"


# =============================================================================
# Exchange / symbol-type / configuration models
# =============================================================================


class TestExchangeAndSymbolType:
    def test_exchange_with_desc(self) -> None:
        ex = TVChartExchange(value="NYSE", name="New York Stock Exchange", desc="US equities")
        assert ex.value == "NYSE"
        assert ex.desc == "US equities"

    def test_exchange_default_desc(self) -> None:
        ex = TVChartExchange(value="NYSE", name="NYSE")
        assert ex.desc == ""

    def test_symbol_type_round_trip(self) -> None:
        st = TVChartDatafeedSymbolType(name="Stock", value="stock")
        assert st.name == "Stock"
        assert st.value == "stock"


class TestDatafeedConfiguration:
    def test_full_config(self) -> None:
        cfg = TVChartDatafeedConfiguration(
            exchanges=[TVChartExchange(value="NYSE", name="NYSE")],
            symbols_types=[TVChartDatafeedSymbolType(name="Stock", value="stock")],
            supported_resolutions=["1", "5", "15", "60", "1D", "1W", "1M"],
            supports_marks=True,
            supports_timescale_marks=True,
            supports_time=True,
            currency_codes=["USD", "EUR"],
        )
        dumped = cfg.model_dump(exclude_none=True)
        assert dumped["exchanges"][0]["value"] == "NYSE"
        assert dumped["supports_marks"] is True
        assert "1D" in dumped["supported_resolutions"]

    def test_empty_config_excluded(self) -> None:
        dumped = TVChartDatafeedConfiguration().model_dump(exclude_none=True)
        assert dumped == {}


class TestSearchSymbolResultItem:
    def test_full_item(self) -> None:
        item = TVChartSearchSymbolResultItem(
            symbol="AAPL",
            description="Apple Inc.",
            exchange="NasdaqNM",
            type="stock",
            ticker="AAPL",
        )
        dumped = item.model_dump(exclude_none=True)
        assert dumped["symbol"] == "AAPL"
        assert dumped["ticker"] == "AAPL"

    def test_required_field_validation(self) -> None:
        # ``symbol`` is the only required field.
        with pytest.raises(Exception):
            TVChartSearchSymbolResultItem()  # type: ignore[call-arg]


# =============================================================================
# Bar / Mark / TimescaleMark
# =============================================================================


class TestBarMarkModels:
    def test_bar_with_volume(self) -> None:
        bar = TVChartBar(
            time=1700000000000, open=100.0, high=105.0, low=99.0, close=103.0, volume=1_000_000.0
        )
        dumped = bar.model_dump()
        assert dumped["time"] == 1700000000000
        assert dumped["volume"] == 1_000_000.0

    def test_bar_without_volume_excludes_key(self) -> None:
        bar = TVChartBar(time=1700000000000, open=100.0, high=105.0, low=99.0, close=103.0)
        dumped = bar.model_dump(exclude_none=True)
        assert "volume" not in dumped

    def test_mark_full_fields(self) -> None:
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
        assert dumped["min_size"] == 24

    def test_timescale_mark(self) -> None:
        mark = TVChartTimescaleMark(
            id="ts1",
            time=1700000000,
            color="blue",
            label="D",
            tooltip=["Dividend", "$0.25/share"],
        )
        dumped = mark.model_dump(exclude_none=True)
        assert dumped["tooltip"] == ["Dividend", "$0.25/share"]

    def test_timescale_mark_shape_literal(self) -> None:
        # ``shape`` accepts a known set of strings only.
        mark = TVChartTimescaleMark(
            id="ts2",
            time=1700000000,
            color="green",
            shape="earningUp",
        )
        assert mark.shape == "earningUp"


# =============================================================================
# Datafeed request / response pairs
# =============================================================================


class TestConfigRequestResponse:
    def test_request_fields(self) -> None:
        req = TVChartDatafeedConfigRequest(request_id="cfg-1", chart_id="main")
        assert req.request_id == "cfg-1"
        assert req.chart_id == "main"

    def test_response_carries_config(self) -> None:
        resp = TVChartDatafeedConfigResponse(
            request_id="cfg-1",
            config=TVChartDatafeedConfiguration(supports_marks=True),
        )
        dumped = resp.model_dump(exclude_none=True)
        assert dumped["config"]["supports_marks"] is True

    def test_response_with_error(self) -> None:
        resp = TVChartDatafeedConfigResponse(request_id="cfg-1", error="boom")
        dumped = resp.model_dump(exclude_none=True)
        assert dumped["error"] == "boom"


class TestSearchRequestResponse:
    def test_request_round_trip(self) -> None:
        req = TVChartDatafeedSearchRequest(
            request_id="req-1",
            query="aapl",
            chart_id="main",
            limit=15,
            exchange="NASDAQ",
            symbol_type="stock",
        )
        dumped = req.model_dump()
        assert dumped["query"] == "aapl"
        assert dumped["exchange"] == "NASDAQ"
        assert dumped["limit"] == 15

    def test_response_round_trip(self) -> None:
        resp = TVChartDatafeedSearchResponse(
            request_id="req-1",
            query="aapl",
            items=[
                TVChartSearchSymbolResultItem(
                    symbol="AAPL", description="Apple Inc.", exchange="NASDAQ"
                )
            ],
        )
        dumped = resp.model_dump(exclude_none=True)
        assert dumped["items"][0]["symbol"] == "AAPL"


class TestResolveRequestResponse:
    def test_request_round_trip(self) -> None:
        req = TVChartDatafeedResolveRequest(
            request_id="req-2", symbol="NASDAQ:AAPL", chart_id="main"
        )
        dumped = req.model_dump()
        assert dumped["symbol"] == "NASDAQ:AAPL"

    def test_response_carries_symbol_info(self) -> None:
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
        dumped = resp.model_dump(exclude_none=True)
        assert dumped["symbol_info"]["ticker"] == "AAPL"
        assert dumped["symbol_info"]["pricescale"] == 100


class TestHistoryRequestResponse:
    def test_request_round_trip(self) -> None:
        req = TVChartDatafeedHistoryRequest(
            request_id="req-3",
            symbol="NASDAQ:AAPL",
            resolution="1D",
            from_time=1_700_000_000,
            to_time=1_700_086_400,
            count_back=300,
            first_data_request=True,
        )
        dumped = req.model_dump()
        assert dumped["resolution"] == "1D"
        assert dumped["count_back"] == 300
        assert dumped["first_data_request"] is True

    def test_response_ok(self) -> None:
        resp = TVChartDatafeedHistoryResponse(
            request_id="req-3",
            status="ok",
            bars=[{"time": 1_700_000_000, "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5}],
        )
        dumped = resp.model_dump()
        assert dumped["status"] == "ok"
        assert len(dumped["bars"]) == 1

    def test_response_no_data(self) -> None:
        resp = TVChartDatafeedHistoryResponse(
            request_id="req-4",
            status="no_data",
            bars=[],
            no_data=True,
            next_time=1_699_900_000_000,
        )
        dumped = resp.model_dump(exclude_none=True)
        assert dumped["status"] == "no_data"
        assert dumped["no_data"] is True
        assert dumped["next_time"] == 1_699_900_000_000


class TestSubscribeUnsubscribe:
    def test_subscribe_request(self) -> None:
        req = TVChartDatafeedSubscribeRequest(
            request_id="sub-1",
            symbol="AAPL",
            resolution="1",
            listener_guid="guid-abc-123",
            chart_id="main",
        )
        assert req.listener_guid == "guid-abc-123"
        assert req.resolution == "1"

    def test_unsubscribe_request(self) -> None:
        req = TVChartDatafeedUnsubscribeRequest(
            listener_guid="guid-abc-123",
            chart_id="main",
        )
        assert req.listener_guid == "guid-abc-123"

    def test_bar_update(self) -> None:
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


class TestMarksRequestResponse:
    def test_marks_round_trip(self) -> None:
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

    def test_timescale_marks_round_trip(self) -> None:
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
                    "tooltip": ["Div"],
                }
            ],
        )
        dumped = resp.model_dump(exclude_none=True)
        assert len(dumped["marks"]) == 1


class TestServerTime:
    def test_request_response(self) -> None:
        req = TVChartDatafeedServerTimeRequest(request_id="st-1", chart_id="main")
        assert req.request_id == "st-1"

        resp = TVChartDatafeedServerTimeResponse(request_id="st-1", time=1700000000)
        dumped = resp.model_dump(exclude_none=True)
        assert dumped["time"] == 1700000000
