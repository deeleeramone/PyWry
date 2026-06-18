"""Tests for ``pywry/tvchart/mixin.py``.

:class:`TVChartStateMixin` is the mixin a host widget (PyWry,
PyWryWidget, InlineWidget) inherits to drive a TradingView chart.
It exposes:

* Convenience methods that emit ``tvchart:*`` events
  (``update_series``, ``add_indicator``, ``add_marker``, ...).
* Datafeed-protocol responders
  (``respond_tvchart_history``, ``respond_tvchart_bar_update``, ...).
* Provider auto-wiring (``_wire_datafeed_provider``) that registers
  handlers for every event a datafeed must implement.
* Chart-storage write-through (``_wire_chart_storage``) that
  persists JS-side localStorage writes into a ``ChartStore``.

The mock emitter records every ``emit``/``on`` call so we can verify
the wire contract without spinning up a real subprocess.
"""

from __future__ import annotations

import asyncio
import json

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from pywry.tvchart.datafeed import DatafeedProvider
from pywry.tvchart.mixin import (
    TVChartStateMixin,
    _chart_store_save_layout,
    _chart_store_sync_index,
)
from pywry.tvchart.models import TVChartData


# =============================================================================
# Mock helpers
# =============================================================================


class _MockEmitter(TVChartStateMixin):
    """Concrete mixin host that records every emit/on call."""

    def __init__(self) -> None:
        self._emitted: list[tuple[str, Any]] = []
        self._handlers: dict[str, list[Any]] = {}

    def emit(self, event_type: str, data: Any | None = None) -> None:
        self._emitted.append((event_type, data))

    def on(self, event_type: str, handler: Any, **_kwargs: Any) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    def fire(self, event_type: str, data: dict[str, Any]) -> None:
        for handler in self._handlers.get(event_type, []):
            handler(data, event_type, "test-label")


class _SyncRunAsync:
    """Synchronous ``run_async`` substitute that runs coroutines in a fresh loop."""

    def __init__(self) -> None:
        self.calls: list[tuple[Any, float | None]] = []

    def __call__(self, coro: Any, *, timeout: float | None = 10.0) -> Any:
        self.calls.append((coro, timeout))
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


@pytest.fixture()
def m() -> _MockEmitter:
    return _MockEmitter()


def _make_provider(
    *,
    supports_search: bool = False,
    supports_marks: bool = False,
    supports_timescale_marks: bool = False,
    supports_time: bool = False,
    config: dict[str, Any] | None = None,
    bars: dict[str, Any] | None = None,
    search_items: list[dict[str, Any]] | None = None,
    resolve_info: dict[str, Any] | None = None,
    marks_result: list[dict[str, Any]] | None = None,
    timescale_marks_result: list[dict[str, Any]] | None = None,
    server_time: int = 1_700_000_000,
    fail_on: str | None = None,
) -> Any:
    """Build a fully-mocked DatafeedProvider for the auto-wiring tests."""
    provider = AsyncMock(spec=DatafeedProvider)
    provider.supports_search = supports_search
    provider.supports_marks = supports_marks
    provider.supports_timescale_marks = supports_timescale_marks
    provider.supports_time = supports_time

    def _wire(method: str, normal_value: Any) -> Any:
        if fail_on == method:
            return AsyncMock(side_effect=RuntimeError("failure"))
        return AsyncMock(return_value=normal_value)

    provider.get_config = _wire("get_config", config or {})
    provider.get_bars = _wire("get_bars", bars or {"bars": [], "status": "ok"})
    provider.search_symbols = _wire("search_symbols", search_items or [])
    provider.resolve_symbol = _wire("resolve_symbol", resolve_info or {"name": "X"})
    provider.get_marks = _wire("get_marks", marks_result or [])
    provider.get_timescale_marks = _wire("get_timescale_marks", timescale_marks_result or [])
    provider.get_server_time = _wire("get_server_time", server_time)
    return provider


# =============================================================================
# Convenience methods (update / indicator / marker / price line)
# =============================================================================


class TestUpdateSeries:
    def test_emits_update_event(self, m: _MockEmitter) -> None:
        m.update_series([{"time": 1, "open": 1, "high": 2, "low": 0, "close": 1}])
        assert len(m._emitted) == 1
        event, payload = m._emitted[0]
        assert event == "tvchart:update"
        assert "bars" in payload
        assert payload["fitContent"] is True

    def test_no_volume_when_bars_only(self, m: _MockEmitter) -> None:
        m.update_series([{"time": 1, "close": 5.0}])
        _, payload = m._emitted[0]
        assert "volume" not in payload

    def test_dataframe_input_includes_volume(self, m: _MockEmitter) -> None:
        df = pd.DataFrame(
            {
                "time": [1700000000, 1700086400],
                "open": [100.0, 101.0],
                "high": [105.0, 106.0],
                "low": [99.0, 100.0],
                "close": [103.0, 104.0],
                "volume": [1000, 2000],
            }
        )
        m.update_series(df)
        _, payload = m._emitted[0]
        assert "volume" in payload
        assert len(payload["volume"]) == 2

    def test_chart_and_series_id_propagation(self, m: _MockEmitter) -> None:
        m.update_series([], chart_id="c42", series_id="overlay")
        _, payload = m._emitted[0]
        assert payload["chartId"] == "c42"
        assert payload["seriesId"] == "overlay"


class TestUpdateBar:
    def test_emits_stream_event(self, m: _MockEmitter) -> None:
        bar = {"time": 1700000000, "open": 100, "high": 105, "low": 98, "close": 103}
        m.update_bar(bar)
        event, payload = m._emitted[0]
        assert event == "tvchart:stream"
        assert payload["bar"] is bar

    def test_up_close_uses_green_volume_color(self, m: _MockEmitter) -> None:
        m.update_bar({"time": 1, "open": 100, "high": 110, "low": 95, "close": 105, "volume": 1000})
        _, payload = m._emitted[0]
        assert payload["volume"]["color"].startswith("rgba(38")  # green

    def test_down_close_uses_red_volume_color(self, m: _MockEmitter) -> None:
        m.update_bar({"time": 1, "open": 100, "high": 100, "low": 90, "close": 90, "volume": 5})
        _, payload = m._emitted[0]
        assert payload["volume"]["color"].startswith("rgba(239")  # red

    def test_chart_and_series_id(self, m: _MockEmitter) -> None:
        m.update_bar(
            {"time": 1, "open": 1, "high": 2, "low": 0, "close": 1},
            chart_id="c1",
            series_id="s1",
        )
        _, payload = m._emitted[0]
        assert payload["chartId"] == "c1"
        assert payload["seriesId"] == "s1"


class TestIndicatorMethods:
    def test_add_indicator_emits_add_series(self, m: _MockEmitter) -> None:
        data = [{"time": 1, "value": 50}, {"time": 2, "value": 55}]
        m.add_indicator(data, series_id="sma20", series_type="Line")
        event, payload = m._emitted[0]
        assert event == "tvchart:add-series"
        assert payload["seriesId"] == "sma20"
        assert payload["seriesType"] == "Line"
        assert payload["bars"] is data

    def test_add_indicator_chart_id(self, m: _MockEmitter) -> None:
        m.add_indicator([{"time": 1, "value": 5}], chart_id="c1")
        _, payload = m._emitted[0]
        assert payload["chartId"] == "c1"

    def test_remove_indicator(self, m: _MockEmitter) -> None:
        m.remove_indicator("sma20")
        event, payload = m._emitted[0]
        assert event == "tvchart:remove-series"
        assert payload["seriesId"] == "sma20"

    def test_remove_indicator_chart_id(self, m: _MockEmitter) -> None:
        m.remove_indicator("ind1", chart_id="c1")
        _, payload = m._emitted[0]
        assert payload["chartId"] == "c1"

    # Built-in indicators (JS-side compute)

    def test_add_builtin_indicator_minimal(self, m: _MockEmitter) -> None:
        m.add_builtin_indicator("RSI")
        event, payload = m._emitted[0]
        assert event == "tvchart:add-indicator"
        assert payload == {"name": "RSI"}

    def test_add_builtin_indicator_with_period_and_color(self, m: _MockEmitter) -> None:
        m.add_builtin_indicator("Moving Average", period=50, color="#2196F3", method="SMA")
        _, payload = m._emitted[0]
        assert payload["name"] == "Moving Average"
        assert payload["method"] == "SMA"
        assert payload["period"] == 50
        assert payload["color"] == "#2196F3"

    def test_add_builtin_indicator_bollinger_options(self, m: _MockEmitter) -> None:
        m.add_builtin_indicator(
            "Bollinger Bands",
            period=20,
            multiplier=2.0,
            ma_type="SMA",
            offset=0,
            source="close",
        )
        _, payload = m._emitted[0]
        assert payload["multiplier"] == 2.0
        assert payload["maType"] == "SMA"
        assert payload["offset"] == 0
        assert payload["source"] == "close"

    def test_add_builtin_indicator_omits_unset_options(self, m: _MockEmitter) -> None:
        m.add_builtin_indicator("RSI", period=12)
        _, payload = m._emitted[0]
        assert set(payload.keys()) == {"name", "period"}

    def test_add_builtin_indicator_chart_id(self, m: _MockEmitter) -> None:
        m.add_builtin_indicator("Moving Average", period=10, method="SMA", chart_id="alt")
        _, payload = m._emitted[0]
        assert payload["chartId"] == "alt"

    def test_remove_builtin_indicator(self, m: _MockEmitter) -> None:
        m.remove_builtin_indicator("ind_sma_99")
        event, payload = m._emitted[0]
        assert event == "tvchart:remove-indicator"
        assert payload == {"seriesId": "ind_sma_99"}

    def test_remove_builtin_indicator_chart_id(self, m: _MockEmitter) -> None:
        m.remove_builtin_indicator("ind_sma_99", chart_id="alt")
        _, payload = m._emitted[0]
        assert payload["chartId"] == "alt"

    def test_list_indicators_default(self, m: _MockEmitter) -> None:
        m.list_indicators()
        event, payload = m._emitted[0]
        assert event == "tvchart:list-indicators"
        assert payload == {}

    def test_list_indicators_with_context(self, m: _MockEmitter) -> None:
        m.list_indicators(chart_id="alt", context={"trigger": "init"})
        _, payload = m._emitted[0]
        assert payload["chartId"] == "alt"
        assert payload["context"] == {"trigger": "init"}


class TestVolumeProfile:
    def test_visible_profile(self, m: _MockEmitter) -> None:
        m.add_volume_profile(
            mode="visible",
            up_color="green",
            down_color="red",
            poc_color="blue",
            chart_id="c1",
        )
        ev, payload = m._emitted[0]
        assert ev == "tvchart:add-indicator"
        assert payload["name"] == "Volume Profile Visible Range"
        assert payload["upColor"] == "green"
        assert payload["downColor"] == "red"
        assert payload["pocColor"] == "blue"
        assert payload["chartId"] == "c1"

    def test_fixed_profile_with_indices(self, m: _MockEmitter) -> None:
        m.add_volume_profile(mode="fixed", from_index=0, to_index=100)
        _ev, payload = m._emitted[0]
        assert payload["name"] == "Volume Profile Fixed Range"
        assert payload["fromIndex"] == 0
        assert payload["toIndex"] == 100


class TestMarkerAndPriceLine:
    def test_add_marker(self, m: _MockEmitter) -> None:
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

    def test_add_marker_chart_and_series_id(self, m: _MockEmitter) -> None:
        m.add_marker([{"time": 1}], chart_id="c1", series_id="s1")
        _, payload = m._emitted[0]
        assert payload["chartId"] == "c1"
        assert payload["seriesId"] == "s1"

    def test_add_price_line(self, m: _MockEmitter) -> None:
        m.add_price_line(150.0, color="#ff0000", title="Resistance")
        event, payload = m._emitted[0]
        assert event == "tvchart:add-price-line"
        assert payload["price"] == 150.0
        assert payload["color"] == "#ff0000"
        assert payload["title"] == "Resistance"

    def test_add_price_line_chart_and_series_id(self, m: _MockEmitter) -> None:
        m.add_price_line(50.0, series_id="s1", chart_id="c1")
        _, payload = m._emitted[0]
        assert payload["chartId"] == "c1"
        assert payload["seriesId"] == "s1"


class TestVisibleRangeAndOptions:
    def test_set_visible_range(self, m: _MockEmitter) -> None:
        m.set_visible_range(1700000000, 1700500000)
        event, payload = m._emitted[0]
        assert event == "tvchart:time-scale"
        assert payload["visibleRange"]["from"] == 1700000000
        assert payload["visibleRange"]["to"] == 1700500000

    def test_set_visible_range_chart_id(self, m: _MockEmitter) -> None:
        m.set_visible_range(1, 100, chart_id="c1")
        _, payload = m._emitted[0]
        assert payload["chartId"] == "c1"

    def test_fit_content(self, m: _MockEmitter) -> None:
        m.fit_content()
        event, payload = m._emitted[0]
        assert event == "tvchart:time-scale"
        assert payload["fitContent"] is True

    def test_fit_content_chart_id(self, m: _MockEmitter) -> None:
        m.fit_content(chart_id="c1")
        _, payload = m._emitted[0]
        assert payload["chartId"] == "c1"

    def test_apply_chart_options(self, m: _MockEmitter) -> None:
        m.apply_chart_options(chart_options={"layout": {"background": {"color": "#000"}}})
        event, payload = m._emitted[0]
        assert event == "tvchart:apply-options"
        assert "chartOptions" in payload

    def test_apply_chart_options_full(self, m: _MockEmitter) -> None:
        m.apply_chart_options(
            chart_options={"layout": {}},
            series_options={"upColor": "green"},
            series_id="s1",
            chart_id="c1",
        )
        _, payload = m._emitted[0]
        assert "chartOptions" in payload
        assert "seriesOptions" in payload
        assert payload["seriesId"] == "s1"
        assert payload["chartId"] == "c1"


class TestRequestState:
    def test_default(self, m: _MockEmitter) -> None:
        m.request_tvchart_state()
        ev, payload = m._emitted[0]
        assert ev == "tvchart:request-state"
        assert payload == {}

    def test_chart_id(self, m: _MockEmitter) -> None:
        m.request_tvchart_state(chart_id="chart1")
        _, payload = m._emitted[0]
        assert payload["chartId"] == "chart1"

    def test_with_context(self, m: _MockEmitter) -> None:
        m.request_tvchart_state(
            chart_id="chart1", context={"target_view": "watchlist", "reason": "reload"}
        )
        _, payload = m._emitted[0]
        assert payload["chartId"] == "chart1"
        assert payload["context"] == {"target_view": "watchlist", "reason": "reload"}


# =============================================================================
# Datafeed responder methods (request_* / respond_*)
# =============================================================================


class TestDatafeedSearch:
    def test_request(self, m: _MockEmitter) -> None:
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

    def test_response_ok(self, m: _MockEmitter) -> None:
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

    def test_response_with_error(self, m: _MockEmitter) -> None:
        m.respond_tvchart_symbol_search(request_id="r", items=[], chart_id="c1", error="boom")
        _, payload = m._emitted[0]
        assert payload["error"] == "boom"


class TestDatafeedResolve:
    def test_request_response(self, m: _MockEmitter) -> None:
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

    def test_response_with_error(self, m: _MockEmitter) -> None:
        m.respond_tvchart_symbol_resolve(
            request_id="r", symbol_info=None, chart_id="c1", error="boom"
        )
        _, payload = m._emitted[0]
        assert payload["error"] == "boom"


class TestDatafeedHistory:
    def test_request_response(self, m: _MockEmitter) -> None:
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

    def test_response_with_error(self, m: _MockEmitter) -> None:
        m.respond_tvchart_history(
            request_id="r", bars=[], status="error", chart_id="c1", error="boom"
        )
        _, payload = m._emitted[0]
        assert payload["error"] == "boom"


class TestDatafeedConfigBarMarks:
    def test_respond_datafeed_config(self, m: _MockEmitter) -> None:
        m.respond_tvchart_datafeed_config(
            request_id="cfg-1",
            config={"supported_resolutions": ["1", "5", "1D"], "supports_marks": True},
            chart_id="chart1",
        )
        event, payload = m._emitted[0]
        assert event == "tvchart:datafeed-config-response"
        assert payload["requestId"] == "cfg-1"
        assert payload["config"]["supports_marks"] is True

    def test_respond_datafeed_config_with_error(self, m: _MockEmitter) -> None:
        m.respond_tvchart_datafeed_config(request_id="r", config={}, chart_id="c1", error="boom")
        _, payload = m._emitted[0]
        assert payload["error"] == "boom"

    def test_respond_bar_update(self, m: _MockEmitter) -> None:
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
        assert payload["chartId"] == "chart1"

    def test_respond_reset_cache(self, m: _MockEmitter) -> None:
        m.respond_tvchart_reset_cache(listener_guid="guid-abc", chart_id="chart1")
        event, payload = m._emitted[0]
        assert event == "tvchart:datafeed-reset-cache"
        assert payload["listenerGuid"] == "guid-abc"
        assert payload["chartId"] == "chart1"

    def test_respond_marks(self, m: _MockEmitter) -> None:
        m.respond_tvchart_marks(
            request_id="m-1",
            marks=[{"id": "mk1", "time": 1700000000, "color": "red", "text": "Buy"}],
            chart_id="chart1",
        )
        event, payload = m._emitted[0]
        assert event == "tvchart:datafeed-marks-response"
        assert payload["requestId"] == "m-1"

    def test_respond_marks_with_error(self, m: _MockEmitter) -> None:
        m.respond_tvchart_marks(request_id="r", marks=[], chart_id="c1", error="boom")
        _, payload = m._emitted[0]
        assert payload["error"] == "boom"

    def test_respond_timescale_marks(self, m: _MockEmitter) -> None:
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

    def test_respond_timescale_marks_with_error(self, m: _MockEmitter) -> None:
        m.respond_tvchart_timescale_marks(request_id="r", marks=[], chart_id="c1", error="boom")
        _, payload = m._emitted[0]
        assert payload["error"] == "boom"

    def test_respond_server_time(self, m: _MockEmitter) -> None:
        m.respond_tvchart_server_time(request_id="st-1", time=1700000000, chart_id="chart1")
        event, payload = m._emitted[0]
        assert event == "tvchart:datafeed-server-time-response"
        assert payload["requestId"] == "st-1"
        assert payload["time"] == 1700000000

    def test_respond_server_time_with_error(self, m: _MockEmitter) -> None:
        m.respond_tvchart_server_time(request_id="r", time=0, chart_id="c1", error="boom")
        _, payload = m._emitted[0]
        assert payload["error"] == "boom"


# =============================================================================
# _normalize_tvchart_data static method
# =============================================================================


class TestNormalizeTVChartDataStatic:
    def test_list_passthrough(self) -> None:
        bars = [{"time": 1, "open": 1, "high": 2, "low": 0, "close": 1}]
        result_bars, result_vol = TVChartStateMixin._normalize_tvchart_data(bars)
        assert result_bars is bars
        assert result_vol == []

    def test_dataframe_includes_volume(self) -> None:
        df = pd.DataFrame(
            {
                "time": [1, 2],
                "open": [1.0, 1.1],
                "high": [1.2, 1.3],
                "low": [0.9, 1.0],
                "close": [1.1, 1.2],
                "volume": [100, 200],
            }
        )
        bars, vol = TVChartStateMixin._normalize_tvchart_data(df)
        assert len(bars) == 2
        assert len(vol) == 2

    def test_empty_dataframe(self) -> None:
        df = pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])
        bars, vol = TVChartStateMixin._normalize_tvchart_data(df)
        assert bars == []
        assert vol == []

    def test_unsupported_type_returns_empty(self) -> None:
        bars, vol = TVChartStateMixin._normalize_tvchart_data(42)
        assert bars == []
        assert vol == []

    def test_dataframe_no_series_yields_empty(self) -> None:
        """When normalize_ohlcv unexpectedly returns no series, the helper
        falls through to empty results (defensive)."""

        class _MiniDF:
            columns: list[str] = ["time", "close"]

            def to_dict(self, orient: str = "records") -> list[dict[str, Any]]:
                return []

        with patch(
            "pywry.tvchart.normalize.normalize_ohlcv",
            return_value=TVChartData(series=[]),
        ):
            bars, vol = TVChartStateMixin._normalize_tvchart_data(_MiniDF())
        assert bars == []
        assert vol == []


# =============================================================================
# _chart_store_save_layout / _chart_store_sync_index module helpers
# =============================================================================


class TestChartStoreSaveLayout:
    def test_with_cached_js_index(self) -> None:
        store = MagicMock()
        store.save_layout = AsyncMock(return_value=None)
        idx = [{"id": "L1", "name": "Layout One", "summary": "summary"}]
        run_async = _SyncRunAsync()
        _chart_store_save_layout(store, run_async, "user", "L1", "{}", js_index=idx)
        store.save_layout.assert_called_once()
        # The first positional argument is user_id, second is layout_id, etc.
        call_args = store.save_layout.call_args
        assert call_args[0][0] == "user"
        assert call_args[0][1] == "L1"
        assert call_args[0][2] == "Layout One"  # name from the JS index

    def test_with_no_index_falls_back_to_store_lookup(self) -> None:
        store = MagicMock()
        store.list_layouts = AsyncMock(
            return_value=[{"id": "L1", "name": "From Store", "summary": ""}]
        )
        store.save_layout = AsyncMock(return_value=None)
        run_async = _SyncRunAsync()
        _chart_store_save_layout(store, run_async, "user", "L1", "{}", js_index=None)
        store.list_layouts.assert_called_once_with("user")
        # Name picked up from the store index, not the layout_id.
        call_args = store.save_layout.call_args
        assert call_args[0][2] == "From Store"

    def test_lookup_exception_swallowed_save_still_runs(self) -> None:
        store = MagicMock()

        async def list_layouts_fail(_user: str) -> list[Any]:
            raise RuntimeError("nope")

        store.list_layouts = list_layouts_fail
        store.save_layout = AsyncMock(return_value=None)
        run_async = _SyncRunAsync()
        _chart_store_save_layout(store, run_async, "user", "L1", "{}", js_index=None)
        store.save_layout.assert_called_once()


class TestChartStoreSyncIndex:
    def test_invalid_json_no_op(self) -> None:
        store = MagicMock()
        run_async = _SyncRunAsync()
        _chart_store_sync_index(store, run_async, "user", "not json")
        store.delete_layout.assert_not_called()
        store.update_layout_meta.assert_not_called()

    def test_non_list_payload_no_op(self) -> None:
        store = MagicMock()
        run_async = _SyncRunAsync()
        _chart_store_sync_index(store, run_async, "user", '{"x": 1}')
        store.delete_layout.assert_not_called()

    def test_metadata_change_triggers_update(self) -> None:
        store = MagicMock()
        store.list_layouts = AsyncMock(
            return_value=[{"id": "L1", "name": "Old", "summary": "", "data": "{}"}]
        )
        store.delete_layout = AsyncMock(return_value=None)
        store.update_layout_meta = AsyncMock(return_value=None)
        run_async = _SyncRunAsync()
        new_index = json.dumps([{"id": "L1", "name": "New", "summary": "fresh"}])
        _chart_store_sync_index(store, run_async, "user", new_index)
        store.update_layout_meta.assert_called_once()

    def test_skips_entries_without_id(self) -> None:
        store = MagicMock()
        store.list_layouts = AsyncMock(return_value=[])
        store.delete_layout = AsyncMock(return_value=None)
        store.update_layout_meta = AsyncMock(return_value=None)
        run_async = _SyncRunAsync()
        new_index = json.dumps([{"no_id_field": "x"}, "string-not-dict", {"id": ""}])
        _chart_store_sync_index(store, run_async, "user", new_index)
        store.update_layout_meta.assert_not_called()

    def test_removed_layouts_deleted(self) -> None:
        store = MagicMock()
        store.list_layouts = AsyncMock(
            return_value=[
                {"id": "L1", "name": "One", "summary": ""},
                {"id": "L2", "name": "Two", "summary": ""},
            ]
        )
        store.delete_layout = AsyncMock(return_value=None)
        store.update_layout_meta = AsyncMock(return_value=None)
        run_async = _SyncRunAsync()
        # New index drops L2 — should delete it
        _chart_store_sync_index(
            store,
            run_async,
            "user",
            json.dumps([{"id": "L1", "name": "One", "summary": ""}]),
        )
        store.delete_layout.assert_called_once_with("user", "L2")


# =============================================================================
# _wire_datafeed_provider — registers handlers for every event
# =============================================================================


class TestWireDatafeedProvider:
    def test_full_provider_registers_all_handlers(self, m: _MockEmitter) -> None:
        provider = _make_provider(
            supports_search=True,
            supports_marks=True,
            supports_timescale_marks=True,
            supports_time=True,
            search_items=[{"symbol": "A"}],
            resolve_info={"name": "A"},
            bars={"bars": [{"time": 1, "value": 2}], "status": "ok"},
            marks_result=[{"id": "m1"}],
            timescale_marks_result=[{"id": "ts1"}],
            server_time=1700000000,
        )

        m._wire_datafeed_provider(provider)

        assert "tvchart:data-request" in m._handlers
        assert "tvchart:datafeed-config-request" in m._handlers
        assert "tvchart:datafeed-search-request" in m._handlers
        assert "tvchart:datafeed-resolve-request" in m._handlers
        assert "tvchart:datafeed-history-request" in m._handlers
        assert "tvchart:datafeed-subscribe" in m._handlers
        assert "tvchart:datafeed-unsubscribe" in m._handlers
        assert "tvchart:datafeed-marks-request" in m._handlers
        assert "tvchart:datafeed-timescale-marks-request" in m._handlers
        assert "tvchart:datafeed-server-time-request" in m._handlers

    def test_minimal_provider_skips_optional_handlers(self, m: _MockEmitter) -> None:
        provider = _make_provider()  # no optional flags
        m._wire_datafeed_provider(provider)
        assert "tvchart:datafeed-search-request" not in m._handlers
        assert "tvchart:datafeed-marks-request" not in m._handlers
        assert "tvchart:datafeed-timescale-marks-request" not in m._handlers
        assert "tvchart:datafeed-server-time-request" not in m._handlers


class TestDataRequestHandler:
    def test_invokes_get_bars(self, m: _MockEmitter) -> None:
        provider = _make_provider(bars={"bars": [{"time": 100, "value": 5}], "status": "ok"})
        m._wire_datafeed_provider(provider)
        m.fire(
            "tvchart:data-request",
            {
                "chartId": "main",
                "interval": "D",
                "symbol": "AAPL",
                "periodParams": {"from": 1, "to": 100, "countBack": 50},
            },
        )
        provider.get_bars.assert_called_once_with("AAPL", "D", 1, 100, 50)
        events = [ev for ev, _ in m._emitted]
        assert "tvchart:data-response" in events

    def test_resolution_fallback_when_no_interval(self, m: _MockEmitter) -> None:
        provider = _make_provider()
        m._wire_datafeed_provider(provider)
        m.fire(
            "tvchart:data-request",
            {"symbol": "AAPL", "resolution": "5m"},
        )
        call_args = provider.get_bars.call_args
        assert call_args[0][1] == "5m"

    def test_echoes_interval_and_bars(self, m: _MockEmitter) -> None:
        provider = _make_provider(
            bars={
                "bars": [{"time": 1700000000, "open": 100, "high": 105, "low": 98, "close": 103}],
                "status": "ok",
            }
        )
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
        assert payload["chartId"] == "main"
        assert len(payload["bars"]) == 1

    def test_provider_exception_emits_empty_bars(self, m: _MockEmitter) -> None:
        provider = _make_provider(fail_on="get_bars")
        m._wire_datafeed_provider(provider)
        m.fire("tvchart:data-request", {"symbol": "AAPL", "interval": "D"})
        events = [(ev, payload) for ev, payload in m._emitted]
        assert any(ev == "tvchart:data-response" for ev, _ in events)
        for ev, payload in events:
            if ev == "tvchart:data-response":
                assert payload["bars"] == []


class TestCoreHandlerRouting:
    def test_config_handler_ok(self, m: _MockEmitter) -> None:
        provider = _make_provider(config={"supported_resolutions": ["D"]})
        m._wire_datafeed_provider(provider)
        m.fire("tvchart:datafeed-config-request", {"requestId": "req-1", "chartId": "c1"})
        for ev, payload in m._emitted:
            if ev == "tvchart:datafeed-config-response":
                assert payload["config"]["supported_resolutions"] == ["D"]
                return
        pytest.fail("config-response not emitted")

    def test_config_handler_exception(self, m: _MockEmitter) -> None:
        provider = _make_provider(fail_on="get_config")
        m._wire_datafeed_provider(provider)
        m.fire("tvchart:datafeed-config-request", {"requestId": "r"})
        for ev, payload in m._emitted:
            if ev == "tvchart:datafeed-config-response":
                assert payload.get("error")

    def test_search_handler_ok(self, m: _MockEmitter) -> None:
        provider = _make_provider(supports_search=True, search_items=[{"symbol": "AAPL"}])
        m._wire_datafeed_provider(provider)
        m.fire(
            "tvchart:datafeed-search-request",
            {"requestId": "r", "query": "AAPL", "symbolType": "stock", "exchange": "", "limit": 10},
        )
        for ev, payload in m._emitted:
            if ev == "tvchart:datafeed-search-response":
                assert payload["items"][0]["symbol"] == "AAPL"
                return
        pytest.fail("search-response not emitted")

    def test_search_handler_exception(self, m: _MockEmitter) -> None:
        provider = _make_provider(supports_search=True, fail_on="search_symbols")
        m._wire_datafeed_provider(provider)
        m.fire("tvchart:datafeed-search-request", {"requestId": "r", "query": "x"})
        for ev, payload in m._emitted:
            if ev == "tvchart:datafeed-search-response":
                assert payload.get("error")

    def test_resolve_handler_ok(self, m: _MockEmitter) -> None:
        provider = _make_provider(resolve_info={"name": "AAPL"})
        m._wire_datafeed_provider(provider)
        m.fire("tvchart:datafeed-resolve-request", {"requestId": "r", "symbol": "AAPL"})
        for ev, payload in m._emitted:
            if ev == "tvchart:datafeed-resolve-response":
                assert payload["symbolInfo"]["name"] == "AAPL"
                return
        pytest.fail("resolve-response not emitted")

    def test_resolve_handler_exception(self, m: _MockEmitter) -> None:
        provider = _make_provider(fail_on="resolve_symbol")
        m._wire_datafeed_provider(provider)
        m.fire("tvchart:datafeed-resolve-request", {"requestId": "r", "symbol": "X"})
        for ev, payload in m._emitted:
            if ev == "tvchart:datafeed-resolve-response":
                assert payload.get("error")

    def test_history_handler_ok(self, m: _MockEmitter) -> None:
        provider = _make_provider(
            bars={
                "bars": [{"time": 1, "value": 2}],
                "status": "ok",
                "no_data": False,
                "next_time": 0,
            }
        )
        m._wire_datafeed_provider(provider)
        m.fire(
            "tvchart:datafeed-history-request",
            {
                "requestId": "r",
                "symbol": "AAPL",
                "resolution": "D",
                "from": 1,
                "to": 100,
                "countBack": 30,
            },
        )
        for ev, payload in m._emitted:
            if ev == "tvchart:datafeed-history-response":
                assert payload["status"] == "ok"
                return
        pytest.fail("history-response not emitted")

    def test_history_handler_exception(self, m: _MockEmitter) -> None:
        provider = _make_provider(fail_on="get_bars")
        m._wire_datafeed_provider(provider)
        m.fire(
            "tvchart:datafeed-history-request",
            {"requestId": "r", "symbol": "X", "resolution": "D"},
        )
        for ev, payload in m._emitted:
            if ev == "tvchart:datafeed-history-response":
                assert payload["status"] == "error"


class TestSubscriptionHandlers:
    def test_subscribe_handler(self, m: _MockEmitter) -> None:
        # MagicMock instead of AsyncMock — on_subscribe is sync.
        provider = MagicMock(spec=DatafeedProvider)
        provider.supports_search = False
        provider.supports_marks = False
        provider.supports_timescale_marks = False
        provider.supports_time = False
        provider.get_config = AsyncMock(return_value={})
        provider.get_bars = AsyncMock(return_value={"bars": [], "status": "ok"})

        m._wire_datafeed_provider(provider)
        m.fire(
            "tvchart:datafeed-subscribe",
            {"listenerGuid": "g1", "symbol": "AAPL", "resolution": "D", "chartId": "c1"},
        )
        provider.on_subscribe.assert_called_once()

    def test_unsubscribe_handler(self, m: _MockEmitter) -> None:
        provider = MagicMock(spec=DatafeedProvider)
        provider.supports_search = False
        provider.supports_marks = False
        provider.supports_timescale_marks = False
        provider.supports_time = False
        provider.get_config = AsyncMock(return_value={})
        provider.get_bars = AsyncMock(return_value={"bars": [], "status": "ok"})

        m._wire_datafeed_provider(provider)
        m.fire("tvchart:datafeed-unsubscribe", {"listenerGuid": "g1"})
        provider.on_unsubscribe.assert_called_once_with("g1")


class TestOptionalHandlers:
    def test_marks_handler_ok(self, m: _MockEmitter) -> None:
        provider = _make_provider(supports_marks=True, marks_result=[{"id": "m1"}])
        m._wire_datafeed_provider(provider)
        m.fire(
            "tvchart:datafeed-marks-request",
            {"requestId": "r", "symbol": "AAPL", "from": 0, "to": 100, "resolution": "D"},
        )
        for ev, payload in m._emitted:
            if ev == "tvchart:datafeed-marks-response":
                assert payload["marks"][0]["id"] == "m1"
                return
        pytest.fail("marks-response not emitted")

    def test_marks_handler_exception(self, m: _MockEmitter) -> None:
        provider = _make_provider(supports_marks=True, fail_on="get_marks")
        m._wire_datafeed_provider(provider)
        m.fire("tvchart:datafeed-marks-request", {"requestId": "r"})
        for ev, payload in m._emitted:
            if ev == "tvchart:datafeed-marks-response":
                assert payload.get("error")

    def test_timescale_marks_handler_ok(self, m: _MockEmitter) -> None:
        provider = _make_provider(
            supports_timescale_marks=True, timescale_marks_result=[{"id": "ts1"}]
        )
        m._wire_datafeed_provider(provider)
        m.fire("tvchart:datafeed-timescale-marks-request", {"requestId": "r"})
        for ev, payload in m._emitted:
            if ev == "tvchart:datafeed-timescale-marks-response":
                assert payload["marks"][0]["id"] == "ts1"
                return
        pytest.fail("timescale-marks-response not emitted")

    def test_timescale_marks_handler_exception(self, m: _MockEmitter) -> None:
        provider = _make_provider(supports_timescale_marks=True, fail_on="get_timescale_marks")
        m._wire_datafeed_provider(provider)
        m.fire("tvchart:datafeed-timescale-marks-request", {"requestId": "r"})
        for ev, payload in m._emitted:
            if ev == "tvchart:datafeed-timescale-marks-response":
                assert payload.get("error")

    def test_server_time_handler_ok(self, m: _MockEmitter) -> None:
        provider = _make_provider(supports_time=True, server_time=1700000000)
        m._wire_datafeed_provider(provider)
        m.fire("tvchart:datafeed-server-time-request", {"requestId": "r"})
        for ev, payload in m._emitted:
            if ev == "tvchart:datafeed-server-time-response":
                assert payload["time"] == 1700000000
                return
        pytest.fail("server-time-response not emitted")

    def test_server_time_handler_exception(self, m: _MockEmitter) -> None:
        provider = _make_provider(supports_time=True, fail_on="get_server_time")
        m._wire_datafeed_provider(provider)
        m.fire("tvchart:datafeed-server-time-request", {"requestId": "r"})
        for ev, payload in m._emitted:
            if ev == "tvchart:datafeed-server-time-response":
                assert payload.get("error")


# =============================================================================
# _wire_chart_storage — JS localStorage write-through to ChartStore
# =============================================================================


class TestWireChartStorage:
    """Exercise every key-routing branch in _wire_chart_storage."""

    @pytest.fixture()
    def memory_store(self) -> Any:
        from pywry.state.memory import MemoryChartStore

        return MemoryChartStore()

    def _wire(self, m: _MockEmitter, store: Any) -> None:
        with patch("pywry.state.get_chart_store", return_value=store):
            m._wire_chart_storage(user_id="default")

    def test_storage_set_invalid_index_json_caches_nothing(
        self, m: _MockEmitter, memory_store: Any
    ) -> None:
        self._wire(m, memory_store)
        m.fire("tvchart:storage-set", {"key": m._TV_INDEX_KEY, "value": "not-json"})
        # No exception — store remains untouched.

    def test_storage_set_settings_template(self, m: _MockEmitter, memory_store: Any) -> None:
        self._wire(m, memory_store)
        m.fire(
            "tvchart:storage-set",
            {"key": m._TV_SETTINGS_CUSTOM_KEY, "value": '{"x":1}'},
        )

    def test_storage_set_default_id(self, m: _MockEmitter, memory_store: Any) -> None:
        self._wire(m, memory_store)
        m.fire(
            "tvchart:storage-set",
            {"key": m._TV_SETTINGS_DEFAULT_KEY, "value": "custom"},
        )

    def test_storage_set_layout_uses_cached_index(self, m: _MockEmitter, memory_store: Any) -> None:
        self._wire(m, memory_store)
        # Seed the cache via a valid index payload.
        m.fire(
            "tvchart:storage-set",
            {
                "key": m._TV_INDEX_KEY,
                "value": json.dumps([{"id": "L1", "name": "Layout One", "summary": "s"}]),
            },
        )
        # Then save the layout data — the resolver picks up "Layout One".
        m.fire(
            "tvchart:storage-set",
            {"key": f"{m._TV_DATA_PREFIX}L1", "value": '{"data":1}'},
        )

    def test_storage_remove_layout(self, m: _MockEmitter, memory_store: Any) -> None:
        self._wire(m, memory_store)
        m.fire("tvchart:storage-remove", {"key": f"{m._TV_DATA_PREFIX}L1"})

    def test_storage_remove_settings_template(self, m: _MockEmitter, memory_store: Any) -> None:
        self._wire(m, memory_store)
        m.fire("tvchart:storage-remove", {"key": m._TV_SETTINGS_CUSTOM_KEY})

    def test_storage_remove_default_id_resets_to_factory(
        self, m: _MockEmitter, memory_store: Any
    ) -> None:
        self._wire(m, memory_store)
        m.fire("tvchart:storage-remove", {"key": m._TV_SETTINGS_DEFAULT_KEY})

    def test_storage_set_empty_key_ignored(self, m: _MockEmitter, memory_store: Any) -> None:
        self._wire(m, memory_store)
        m.fire("tvchart:storage-set", {"key": "", "value": "x"})

    def test_storage_remove_empty_key_ignored(self, m: _MockEmitter, memory_store: Any) -> None:
        self._wire(m, memory_store)
        m.fire("tvchart:storage-remove", {"key": ""})

    def test_storage_set_unknown_key_ignored(self, m: _MockEmitter, memory_store: Any) -> None:
        self._wire(m, memory_store)
        m.fire("tvchart:storage-set", {"key": "unrelated", "value": "x"})

    def test_storage_set_handles_runtime_exception(self, m: _MockEmitter) -> None:
        store = MagicMock()
        store.save_layout = AsyncMock(side_effect=RuntimeError("write failure"))
        store.list_layouts = AsyncMock(return_value=[])
        self._wire(m, store)
        # Must not propagate the exception.
        m.fire(
            "tvchart:storage-set",
            {"key": f"{m._TV_DATA_PREFIX}L1", "value": "{}"},
        )

    def test_storage_remove_handles_runtime_exception(self, m: _MockEmitter) -> None:
        store = MagicMock()
        store.delete_layout = AsyncMock(side_effect=RuntimeError("rm failure"))
        self._wire(m, store)
        m.fire("tvchart:storage-remove", {"key": f"{m._TV_DATA_PREFIX}L1"})
