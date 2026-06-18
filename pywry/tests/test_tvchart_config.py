"""Tests for ``pywry/tvchart/config.py``.

Covers the Pydantic configuration models that mirror the Lightweight
Charts API — enum values, camelCase aliasing, defaults, JSON
round-trips, and the serialization helpers on :class:`TVChartConfig`
(``to_chart_options``, ``to_payload``, ``to_series_options``).
"""

from __future__ import annotations

import json

import pydantic
import pytest

from pywry.tvchart.config import (
    ChartTemplate,
    ChartTheme,
    CrosshairConfig,
    CrosshairMode,
    DrawingCoordinate,
    DrawingState,
    DrawingToolConfig,
    DrawingToolType,
    GridConfig,
    IndicatorConfig,
    IndicatorPreset,
    LayoutConfig,
    LineStyle,
    LineWidth,
    PriceScaleConfig,
    PriceScaleMode,
    SavedChart,
    SeriesConfig,
    SeriesType,
    TimeScaleConfig,
    TVChartConfig,
    WatermarkConfig,
)


# =============================================================================
# Enum values
# =============================================================================


class TestEnums:
    """Verify the enum value contracts (these are the strings/ints LWC reads)."""

    def test_series_type_values(self) -> None:
        assert SeriesType.CANDLESTICK.value == "Candlestick"
        assert SeriesType.LINE.value == "Line"
        assert SeriesType.BAR.value == "Bar"
        assert SeriesType.AREA.value == "Area"
        assert SeriesType.BASELINE.value == "Baseline"
        assert SeriesType.HISTOGRAM.value == "Histogram"

    def test_price_scale_mode_values(self) -> None:
        assert PriceScaleMode.NORMAL == 0
        assert PriceScaleMode.LOGARITHMIC == 1
        assert PriceScaleMode.PERCENTAGE == 2
        assert PriceScaleMode.INDEXED_TO_100 == 3

    def test_crosshair_mode_values(self) -> None:
        assert CrosshairMode.NORMAL == 0
        assert CrosshairMode.MAGNET == 1

    def test_line_style_values(self) -> None:
        assert LineStyle.SOLID == 0
        assert LineStyle.DOTTED == 1
        assert LineStyle.DASHED == 2
        assert LineStyle.LARGE_DASHED == 3
        assert LineStyle.SPARSE_DOTTED == 4

    def test_line_width_values(self) -> None:
        assert LineWidth.ONE == 1
        assert LineWidth.FOUR == 4

    def test_drawing_tool_type_has_core_tools(self) -> None:
        # A few representative tools — the enum has 40+ values.
        assert DrawingToolType.TREND_LINE.value == "trendline"
        assert DrawingToolType.HORIZONTAL_LINE.value == "hline"
        assert DrawingToolType.FIB_RETRACEMENT.value == "fib_retracement"
        assert DrawingToolType.RECTANGLE.value == "rect"


# =============================================================================
# Sub-config serialization (snake_case → camelCase)
# =============================================================================


class TestSubConfigSerialization:
    """The Pydantic alias_generator must rewrite every snake_case field
    into camelCase so the JS frontend gets the expected key names."""

    def test_series_config_camel_case(self) -> None:
        cfg = SeriesConfig(
            series_type=SeriesType.LINE,
            price_scale_id="left",
            up_color="#00ff00",
            down_color="#ff0000",
        )
        d = cfg.model_dump(by_alias=True, exclude_none=True)
        assert d["seriesType"] == "Line"
        assert d["priceScaleId"] == "left"
        assert d["upColor"] == "#00ff00"
        assert d["downColor"] == "#ff0000"
        # No snake_case keys when by_alias=True
        assert "series_type" not in d
        assert "price_scale_id" not in d

    def test_price_scale_config_defaults(self) -> None:
        cfg = PriceScaleConfig()
        d = cfg.model_dump(by_alias=True, exclude_none=True)
        assert d["autoScale"] is True
        assert d["mode"] == PriceScaleMode.NORMAL.value
        assert d["visible"] is True

    def test_time_scale_config_defaults(self) -> None:
        cfg = TimeScaleConfig()
        d = cfg.model_dump(by_alias=True, exclude_none=True)
        assert d["rightOffset"] == 5
        assert d["barSpacing"] == 6.0
        assert d["timeVisible"] is True

    def test_crosshair_config_defaults(self) -> None:
        cfg = CrosshairConfig()
        d = cfg.model_dump(by_alias=True, exclude_none=True)
        assert d["mode"] == CrosshairMode.MAGNET.value

    def test_layout_config_camel_case(self) -> None:
        cfg = LayoutConfig(text_color="#fff", font_size=14, font_family="Arial")
        d = cfg.model_dump(by_alias=True, exclude_none=True)
        assert d["textColor"] == "#fff"
        assert d["fontSize"] == 14
        assert d["fontFamily"] == "Arial"
        assert "text_color" not in d

    def test_watermark_config_camel_case(self) -> None:
        cfg = WatermarkConfig(visible=True, text="AAPL", font_size=64)
        d = cfg.model_dump(by_alias=True, exclude_none=True)
        assert d["visible"] is True
        assert d["fontSize"] == 64
        assert d["horzAlign"] == "center"
        assert d["vertAlign"] == "center"

    def test_grid_config_camel_case(self) -> None:
        cfg = GridConfig(
            vert_lines={"visible": True, "color": "#222"},
            horz_lines={"visible": False},
        )
        d = cfg.model_dump(by_alias=True, exclude_none=True)
        assert d["vertLines"] == {"visible": True, "color": "#222"}
        assert d["horzLines"] == {"visible": False}


# =============================================================================
# Drawing / indicator / theme / template models
# =============================================================================


class TestDrawingModels:
    """Drawing state models used for persisting tool annotations."""

    def test_drawing_coordinate(self) -> None:
        c = DrawingCoordinate(time=1700000000, price=42.5)
        assert c.time == 1700000000
        assert c.price == 42.5

    def test_drawing_tool_config_defaults(self) -> None:
        cfg = DrawingToolConfig(tool_type=DrawingToolType.TREND_LINE)
        d = cfg.model_dump(by_alias=True, exclude_none=True)
        assert d["toolType"] == "trendline"
        assert d["color"] == "#2196F3"
        assert d["lineStyle"] == LineStyle.SOLID.value
        assert d["snapToCandle"] is True

    def test_drawing_state_roundtrip(self) -> None:
        d = DrawingState(
            drawing_id="d1",
            tool_type=DrawingToolType.TREND_LINE,
            coordinates=[
                DrawingCoordinate(time=1, price=100.0),
                DrawingCoordinate(time=2, price=110.0),
            ],
            config=DrawingToolConfig(tool_type=DrawingToolType.TREND_LINE),
            z_order=5,
            locked=True,
        )
        dumped = d.model_dump(by_alias=True, exclude_none=True)
        assert dumped["drawingId"] == "d1"
        assert dumped["zOrder"] == 5
        assert dumped["locked"] is True
        assert len(dumped["coordinates"]) == 2


class TestIndicatorModels:
    """Indicator config + preset models."""

    def test_indicator_config_defaults(self) -> None:
        cfg = IndicatorConfig(indicator_type="sma")
        d = cfg.model_dump(by_alias=True, exclude_none=True)
        assert d["indicatorType"] == "sma"
        assert d["params"] == {}
        assert d["paneIndex"] == 0
        assert d["visible"] is True

    def test_indicator_preset_with_params(self) -> None:
        p = IndicatorPreset(
            name="Fast SMA",
            indicator_type="sma",
            params={"period": 20, "source": "close"},
            description="Short trend",
        )
        d = p.model_dump(by_alias=True, exclude_none=True)
        assert d["name"] == "Fast SMA"
        assert d["indicatorType"] == "sma"
        assert d["params"]["period"] == 20


class TestThemeAndTemplate:
    """Theme + template + saved-chart models."""

    def test_chart_theme_defaults(self) -> None:
        t = ChartTheme(name="custom")
        d = t.model_dump(by_alias=True, exclude_none=True)
        assert d["name"] == "custom"
        assert d["backgroundColor"] == "#0a0a0d"
        assert d["upColor"] == "#089981"
        assert d["downColor"] == "#f23645"

    def test_chart_template_with_indicators(self) -> None:
        tpl = ChartTemplate(
            name="trend",
            indicators=[IndicatorConfig(indicator_type="sma", params={"period": 50})],
            series_config=SeriesConfig(),
            layout=LayoutConfig(),
        )
        d = tpl.model_dump(by_alias=True, exclude_none=True)
        assert d["name"] == "trend"
        assert len(d["indicators"]) == 1
        assert d["indicators"][0]["indicatorType"] == "sma"

    def test_saved_chart_full_state(self) -> None:
        sc = SavedChart(
            name="trend-watch",
            symbol="AAPL",
            timeframe="1H",
            indicators=[IndicatorConfig(indicator_type="rsi")],
            compare_symbols=["MSFT", "GOOG"],
            visible_range={"from": 1, "to": 1000},
        )
        d = sc.model_dump(by_alias=True, exclude_none=True)
        assert d["name"] == "trend-watch"
        assert d["symbol"] == "AAPL"
        assert d["timeframe"] == "1H"
        assert d["compareSymbols"] == ["MSFT", "GOOG"]
        assert d["visibleRange"] == {"from": 1, "to": 1000}


# =============================================================================
# TVChartConfig top-level model + serialization helpers
# =============================================================================


class TestTVChartConfigNested:
    """TVChartConfig holds the sub-configs; nested camelCase must work too."""

    def test_nested_serialization(self) -> None:
        cfg = TVChartConfig(
            time_scale=TimeScaleConfig(right_offset=10),
            crosshair=CrosshairConfig(mode=CrosshairMode.NORMAL),
        )
        d = cfg.model_dump(by_alias=True, exclude_none=True)
        assert d["timeScale"]["rightOffset"] == 10
        assert d["crosshair"]["mode"] == CrosshairMode.NORMAL.value

    def test_json_roundtrip_preserves_camel_case(self) -> None:
        cfg = TVChartConfig(
            time_scale=TimeScaleConfig(right_offset=10),
            layout=LayoutConfig(text_color="#ccc"),
        )
        parsed = json.loads(cfg.model_dump_json(by_alias=True, exclude_none=True))
        assert "timeScale" in parsed
        assert parsed["layout"]["textColor"] == "#ccc"


class TestTVChartConfigToChartOptions:
    """Cover every conditional branch in :meth:`TVChartConfig.to_chart_options`."""

    def test_empty_config_only_emits_auto_size(self) -> None:
        opts = TVChartConfig().to_chart_options()
        assert opts == {"autoSize": True}

    def test_layout_block(self) -> None:
        opts = TVChartConfig(layout=LayoutConfig()).to_chart_options()
        assert isinstance(opts["layout"], dict)

    def test_grid_block(self) -> None:
        opts = TVChartConfig(grid=GridConfig()).to_chart_options()
        assert "grid" in opts

    def test_crosshair_block(self) -> None:
        opts = TVChartConfig(crosshair=CrosshairConfig()).to_chart_options()
        assert "crosshair" in opts

    def test_watermark_block(self) -> None:
        opts = TVChartConfig(watermark=WatermarkConfig(visible=True, text="x")).to_chart_options()
        assert opts["watermark"]["text"] == "x"

    def test_right_price_scale_block(self) -> None:
        opts = TVChartConfig(right_price_scale=PriceScaleConfig()).to_chart_options()
        assert "rightPriceScale" in opts

    def test_left_price_scale_block(self) -> None:
        opts = TVChartConfig(left_price_scale=PriceScaleConfig()).to_chart_options()
        assert "leftPriceScale" in opts

    def test_time_scale_block(self) -> None:
        opts = TVChartConfig(time_scale=TimeScaleConfig()).to_chart_options()
        assert "timeScale" in opts

    def test_locale_block(self) -> None:
        opts = TVChartConfig(locale="fr-FR").to_chart_options()
        assert opts["locale"] == "fr-FR"

    def test_yield_curve_block(self) -> None:
        opts = TVChartConfig(
            yield_curve={"baseResolution": 1, "minimumTimeRange": 4}
        ).to_chart_options()
        assert opts["yieldCurve"] == {"baseResolution": 1, "minimumTimeRange": 4}

    def test_yield_curve_unset_omitted(self) -> None:
        """``yield_curve`` is optional — without an explicit dict don't ship an empty block
        that the frontend would treat as a wipe of the LWC defaults."""
        opts = TVChartConfig(chart_kind="yield-curve").to_chart_options()
        assert "yieldCurve" not in opts

    def test_all_branches(self) -> None:
        cfg = TVChartConfig(
            layout=LayoutConfig(),
            grid=GridConfig(),
            crosshair=CrosshairConfig(),
            watermark=WatermarkConfig(visible=True, text="x"),
            right_price_scale=PriceScaleConfig(),
            left_price_scale=PriceScaleConfig(),
            time_scale=TimeScaleConfig(),
            locale="en-US",
            yield_curve={"a": 1},
        )
        opts = cfg.to_chart_options()
        for key in (
            "layout",
            "grid",
            "crosshair",
            "watermark",
            "rightPriceScale",
            "leftPriceScale",
            "timeScale",
            "locale",
            "yieldCurve",
            "autoSize",
        ):
            assert key in opts


class TestTVChartConfigToPayload:
    """``to_payload`` packages ``chartKind`` + ``chartOptions`` for the frontend."""

    def test_default_payload_carries_chart_kind(self) -> None:
        payload = TVChartConfig().to_payload()
        assert payload["chartKind"] == "default"
        assert isinstance(payload["chartOptions"], dict)

    def test_price_kind_payload(self) -> None:
        payload = TVChartConfig(chart_kind="price").to_payload()
        assert payload["chartKind"] == "price"

    def test_yield_curve_payload_forwards_options(self) -> None:
        payload = TVChartConfig(
            chart_kind="yield-curve",
            yield_curve={"baseResolution": 1, "minimumTimeRange": 360},
        ).to_payload()
        assert payload["chartKind"] == "yield-curve"
        assert payload["chartOptions"]["yieldCurve"]["minimumTimeRange"] == 360


class TestTVChartConfigToSeriesOptions:
    def test_series_options_camel_case(self) -> None:
        cfg = TVChartConfig(series=SeriesConfig(price_scale_id="left"))
        opts = cfg.to_series_options()
        assert opts["priceScaleId"] == "left"


class TestTVChartConfigChartKind:
    """Lock down the ``chart_kind`` literal selector."""

    def test_default_is_time_axis(self) -> None:
        cfg = TVChartConfig()
        assert cfg.chart_kind == "default"
        assert cfg.yield_curve is None

    def test_accepts_price_kind(self) -> None:
        assert TVChartConfig(chart_kind="price").chart_kind == "price"

    def test_accepts_yield_curve_kind(self) -> None:
        assert TVChartConfig(chart_kind="yield-curve").chart_kind == "yield-curve"

    def test_rejects_unknown_kind(self) -> None:
        with pytest.raises(pydantic.ValidationError):
            TVChartConfig(chart_kind="candlestick")  # type: ignore[arg-type]
