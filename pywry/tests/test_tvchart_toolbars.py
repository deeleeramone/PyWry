"""Tests for ``pywry/tvchart/toolbars.py``.

``build_tvchart_toolbars`` is the high-level factory the
``show_tvchart`` API calls when the caller doesn't supply custom
toolbars.  The factory must produce the four standard TradingView-style
toolbars (header, drawing tools, time-range presets, OHLC legend
overlay) wired with the right component IDs and intervals.

Time-range presets are picked from a candidates list that depends on
the finest interval the dev exposes — these tests lock down the
preset choices for the common cases (daily-only, weekly-only,
quarterly-only, intraday-mix) plus the fallback paths.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from pywry.tvchart.toolbars import (
    _resolve_time_range_interval,
    _time_range_presets,
    build_tvchart_toolbars,
)


# =============================================================================
# build_tvchart_toolbars — structural contracts
# =============================================================================


class TestToolbarsStructure:
    """The factory always returns four toolbars in fixed positions."""

    @pytest.fixture()
    def toolbars(self) -> list:
        return build_tvchart_toolbars()

    def test_returns_four_toolbars(self, toolbars: list) -> None:
        assert len(toolbars) == 4

    def test_positions(self, toolbars: list) -> None:
        positions = [tb.position for tb in toolbars]
        assert sorted(positions) == ["bottom", "inside", "left", "top"]

    def test_header_has_chart_type_selector(self, toolbars: list) -> None:
        header = next(tb for tb in toolbars if tb.position == "top")
        ids = [item.component_id for item in header.items]
        assert "wrap-tvchart-chart-type" in ids

    def test_header_has_save_button(self, toolbars: list) -> None:
        header = next(tb for tb in toolbars if tb.position == "top")
        ids = [item.component_id for item in header.items]
        assert "wrap-tvchart-save-split" in ids

    def test_header_has_indicators_button(self, toolbars: list) -> None:
        header = next(tb for tb in toolbars if tb.position == "top")
        ids = [item.component_id for item in header.items]
        assert "wrap-tvchart-indicators" in ids

    def test_left_has_drawing_tools(self, toolbars: list) -> None:
        left = next(tb for tb in toolbars if tb.position == "left")
        ids = [item.component_id for item in left.items]
        # Pointer + crosshair + line tools + channel tools + eraser are
        # the bare-minimum drawing set.
        assert "wrap-tvchart-tool-crosshair" in ids
        assert "wrap-tvchart-group-lines" in ids
        assert "wrap-tvchart-group-channels" in ids
        assert "wrap-tvchart-tool-eraser" in ids

    def test_bottom_has_time_range_tabs(self, toolbars: list) -> None:
        bottom = next(tb for tb in toolbars if tb.position == "bottom")
        ids = [item.component_id for item in bottom.items]
        assert "tvchart-time-range" in ids
        assert "wrap-tvchart-date-range" in ids

    def test_inside_legend_div_has_no_inline_script(self, toolbars: list) -> None:
        """Legend script is loaded via 11-legend.js — never as inline
        on the Div component."""
        inside = next(tb for tb in toolbars if tb.position == "inside")
        legend = inside.items[0]
        assert legend.script is None or legend.script == ""


# =============================================================================
# Theme propagation to the dark-mode toggle
# =============================================================================


class TestThemeToggle:
    def test_light_theme_toggle_off(self) -> None:
        toolbars = build_tvchart_toolbars(theme="light")
        header = next(tb for tb in toolbars if tb.position == "top")
        toggle = next(item for item in header.items if item.component_id == "tvchart-dark-mode")
        assert toggle.value is False

    def test_dark_theme_toggle_on(self) -> None:
        toolbars = build_tvchart_toolbars(theme="dark")
        header = next(tb for tb in toolbars if tb.position == "top")
        toggle = next(item for item in header.items if item.component_id == "tvchart-dark-mode")
        assert toggle.value is True

    def test_default_theme_is_dark(self) -> None:
        toolbars = build_tvchart_toolbars()
        header = next(tb for tb in toolbars if tb.position == "top")
        toggle = next(item for item in header.items if item.component_id == "tvchart-dark-mode")
        assert toggle.value is True


# =============================================================================
# Interval selector in the header
# =============================================================================


class TestIntervalSelector:
    def test_intervals_omitted_when_none(self) -> None:
        toolbars = build_tvchart_toolbars(intervals=None)
        header = next(tb for tb in toolbars if tb.position == "top")
        ids = [item.component_id for item in header.items]
        assert "wrap-tvchart-interval-btn" not in ids

    def test_intervals_show_selector(self) -> None:
        toolbars = build_tvchart_toolbars(intervals=["1m", "5m", "1h"], selected_interval="5m")
        header = next(tb for tb in toolbars if tb.position == "top")
        ids = [item.component_id for item in header.items]
        assert "wrap-tvchart-interval-btn" in ids


# =============================================================================
# Time-range presets — preset choice depends on finest interval
# =============================================================================


def _bottom_time_range(toolbars: list):
    bottom = next(tb for tb in toolbars if tb.position == "bottom")
    return next(item for item in bottom.items if item.component_id == "tvchart-time-range")


class TestTimeRangePresetSelection:
    def test_daily_only_uses_year_presets(self) -> None:
        toolbars = build_tvchart_toolbars(intervals=["1d", "1w", "1M"], selected_interval="1d")
        time_range = _bottom_time_range(toolbars)

        assert [opt.value for opt in time_range.options] == [
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
        assert [opt.data_attrs["target-interval"] for opt in time_range.options] == [
            "1d",
            "1M",
            "1w",
            "1d",
            "1d",
            "1d",
            "1d",
            "1d",
        ]

    def test_weekly_only_uses_longer_ranges(self) -> None:
        toolbars = build_tvchart_toolbars(intervals=["1w", "1M"], selected_interval="1w")
        time_range = _bottom_time_range(toolbars)

        assert [opt.value for opt in time_range.options] == [
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
        assert [opt.data_attrs["target-interval"] for opt in time_range.options] == [
            "1w",
            "1M",
            "1w",
            "1w",
            "1w",
            "1w",
            "1w",
            "1w",
        ]

    def test_quarterly_only_uses_multi_year_presets(self) -> None:
        toolbars = build_tvchart_toolbars(intervals=["3M", "12M"], selected_interval="3M")
        time_range = _bottom_time_range(toolbars)

        assert [opt.value for opt in time_range.options] == [
            "all",
            "20y",
            "10y",
            "5y",
            "3y",
            "ytd",
        ]
        assert time_range.selected == "ytd"
        assert [opt.data_attrs["target-interval"] for opt in time_range.options] == [
            "3M",
            "3M",
            "3M",
            "3M",
            "3M",
            "3M",
        ]

    def test_intraday_mix_target_intervals_and_tooltips(self) -> None:
        toolbars = build_tvchart_toolbars(
            intervals=["1m", "3m", "5m", "15m", "30m", "45m", "1h", "2h", "4h", "1d", "1w", "1M"],
            selected_interval="1d",
        )
        time_range = _bottom_time_range(toolbars)
        options = {opt.value: opt for opt in time_range.options}

        assert options["1d"].data_attrs["target-interval"] == "1m"
        assert options["5d"].data_attrs["target-interval"] == "5m"
        assert options["1m"].data_attrs["target-interval"] == "30m"
        assert options["3m"].data_attrs["target-interval"] == "1h"
        assert options["6m"].data_attrs["target-interval"] == "2h"
        assert options["ytd"].data_attrs["target-interval"] == "1d"
        assert options["all"].data_attrs["target-interval"] == "1d"

        # Descriptions
        assert options["1d"].description == "1 day"
        assert options["5d"].description == "5 days"
        assert options["1m"].description == "1 month"
        assert options["3m"].description == "3 months"
        assert options["6m"].description == "6 months"
        assert options["ytd"].description == "Year to date"
        assert options["all"].description == "All"

        # Labels for the renamed buttons
        assert options["10y"].label == "10y"
        assert options["ytd"].label == "YTD"
        assert options["all"].label == "Max"


# =============================================================================
# _resolve_time_range_interval — fallback behaviour
# =============================================================================


class TestResolveTimeRangeInterval:
    def test_unknown_intervals_for_large_range_returns_coarsest(self) -> None:
        # span_days for "all" is 365*50 → >= 30, so we fall to max()
        result = _resolve_time_range_interval("all", intervals=["xx", "yy"])
        assert result in {"xx", "yy"}

    def test_unknown_intervals_for_small_range_returns_finest(self) -> None:
        result = _resolve_time_range_interval("1d", intervals=["xx", "yy"])
        assert result in {"xx", "yy"}


# =============================================================================
# _time_range_presets — direct invocation for edge cases
# =============================================================================


class TestTimeRangePresetsHelper:
    def test_default_intervals_yields_options(self) -> None:
        options, selected = _time_range_presets(["1d"])
        assert options
        assert selected

    def test_minute_intervals_yield_options(self) -> None:
        options, selected = _time_range_presets(["1m"])
        assert options
        assert selected

    def test_none_intervals_uses_default(self) -> None:
        options, _ = _time_range_presets(None)
        assert options

    def test_relaxed_filter_when_strict_yields_few(self) -> None:
        # Inject a custom huge unit; ratios for everything drop below the
        # strict >=8 threshold, the relaxed >=3 path fires.
        from pywry.tvchart import toolbars as toolbars_mod

        with patch.dict(toolbars_mod._INTERVAL_DAYS, {"hugeunit": 100_000.0}):
            options, _ = toolbars_mod._time_range_presets(["hugeunit"])
        assert options
