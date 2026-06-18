"""Tests for the bundled TVChart frontend (JS + CSS) and the public
``show_tvchart`` API surface.

These tests don't target a Python module in ``pywry/tvchart/`` —
they target the bundled JavaScript (``pywry/frontend/...``) loaded via
``pywry.assets.get_tvchart_defaults_js`` and the public API exposed
from :mod:`pywry`.  They live in their own file because they assert
behaviour of the bundled assets rather than any single source module.

Structure
---------

* **TestTVChartFrontendStateContracts** — JS bundle scoping / state /
  layout / navigation / chart-type-change contracts.
* **TestTVChartIndicatorCatalog** — catalogue, compute, and recompute
  contracts for every supported indicator.
* **TestTVChartVolumeProfile** — VPVR compute & helpers.
* **TestTVChartLegendVolumeRemoval** — remove/restore volume contract.
* **TestTVChartThemeVariables** — CSS variable parity across themes.
* **TestTVChartSpecialtyChartKinds** — three LWC chart factories
  (default, price, yield-curve).
* **TestTVChartSpecialtyInlinePayload** — inline / app surface for
  ``chart_kind``.
* **TestShowTVChartSignature** — public ``show_tvchart`` signature.
* **TestPyWryTVChartWidgetShape** — widget class smoke tests.
* **TestPublicAPIImports** — tvchart symbols re-exported on
  :mod:`pywry`.
* **TestMCPToolDefinition** — MCP tool registry for ``show_tvchart``.
"""

from __future__ import annotations

import ast
import json

from pathlib import Path

import pytest


# =============================================================================
# Shared fixture for the bundled JS source
# =============================================================================


@pytest.fixture(scope="module")
def tvchart_defaults_js() -> str:
    from pywry.assets import get_tvchart_defaults_js

    return get_tvchart_defaults_js()


@pytest.fixture(scope="module")
def tvchart_css() -> str:
    import pywry

    return (Path(pywry.__file__).parent / "frontend" / "style" / "tvchart.css").read_text(
        encoding="utf-8"
    )


# =============================================================================
# Helpers — scope-aware JS extraction
# =============================================================================


def _skip_comment(src: str, i: int, n: int) -> int | None:
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


def _extract_braced(src: str, search_from: int) -> str:
    """Return text from *search_from* through the matching closing brace.
    Handles string literals and comments so braces inside them are not
    counted."""
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
            skip = _skip_comment(src, i, n)
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


def _fn(src: str, name: str) -> str:
    """Extract the body of ``function <name>(...)``."""
    return _extract_braced(src, src.index(f"function {name}("))


def _handler(src: str, event: str) -> str:
    """Extract the body of an event listener for ``<event>``."""
    candidates = (f"window.pywry.on('{event}'", f"bridge.on('{event}'")
    for candidate in candidates:
        idx = src.find(candidate)
        if idx != -1:
            return _extract_braced(src, idx)
    raise ValueError(f"No handler registration found for event '{event}'")


def _create_body(src: str) -> str:
    """Extract the PYWRY_TVCHART_CREATE function body."""
    start = src.index("window.PYWRY_TVCHART_CREATE = function")
    end = src.index("window.PYWRY_TVCHART_UPDATE", start)
    return src[start:end]


def _fn_or_nested(src: str, name: str) -> str:
    """Extract a function body — works for nested ``function X()`` too."""
    idx = src.index(f"function {name}(")
    depth = 0
    i = src.index("{", idx)
    n = len(src)
    while i < n:
        ch = src[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return src[idx : i + 1]
        i += 1
    raise RuntimeError(f"Could not find end of {name}")


# =============================================================================
# JS bundle: state export / request, legend, volume, time range
# =============================================================================


class TestTVChartFrontendStateContracts:
    """Validate structural and behavioural contracts in the JS frontend source.

    Each test scopes its assertions to a specific function or handler body,
    verifying that the tested property lives in the correct execution context
    rather than just checking for string presence anywhere in ~12,000 lines.
    """

    # -- State export & request --

    def test_state_export_returns_all_survival_fields(self, tvchart_defaults_js: str) -> None:
        body = _fn(tvchart_defaults_js, "_tvExportState")
        for field in ("rawData", "drawings", "indicators"):
            assert f"{field}: {field}" in body, (
                f"_tvExportState return object must include '{field}'"
            )
        assert "getVisibleLogicalRange()" in body

    def test_state_response_echoes_request_context(self, tvchart_defaults_js: str) -> None:
        body = _handler(tvchart_defaults_js, "tvchart:request-state")
        assert "_tvExportState(" in body
        assert "data.context" in body
        assert "Object.assign" in body
        assert "tvchart:state-response" in body

    # -- Legend scoping & controls --

    def test_legend_setup_is_scoped_to_chart_instance(self, tvchart_defaults_js: str) -> None:
        body = _fn(tvchart_defaults_js, "_tvSetupLegendControls")
        assert "_tvResolveChartEntry(chartId)" in body
        assert "_tvScopedById(chartId" in body
        assert "function scopedById(id)" in body
        assert "chartIds[0]" not in body

    def test_legend_has_per_series_action_buttons(self, tvchart_defaults_js: str) -> None:
        body = _fn(tvchart_defaults_js, "_tvSetupLegendControls")
        for action in ("hide", "settings", "remove", "more"):
            assert f'data-action="{action}"' in body, (
                f"Legend row must have a '{action}' action button"
            )

    def test_legend_listens_for_external_refresh_events(self, tvchart_defaults_js: str) -> None:
        body = _fn(tvchart_defaults_js, "_tvSetupLegendControls")
        assert "pywry:legend-refresh" in body

    # -- Volume subplot --

    def test_volume_reserve_called_in_both_lifecycle_paths(self, tvchart_defaults_js: str) -> None:
        create = _create_body(tvchart_defaults_js)
        assert "_tvReserveVolumePane(entry," in create
        reserve_fn = _fn(tvchart_defaults_js, "_tvReserveVolumePane")
        assert "entry._volumePaneBySeries" in reserve_fn
        assert "paneIndex = 1" in reserve_fn

    def test_volume_pane_height_is_clamped_proportionally(self, tvchart_defaults_js: str) -> None:
        body = _fn(tvchart_defaults_js, "_tvApplyDefaultVolumePaneHeight")
        assert "containerHeight" in body
        assert "Math.max(64" in body
        assert "Math.min(132" in body
        assert "0.12" in body
        assert "setHeight(desiredHeight)" in body

    def test_volume_options(self, tvchart_defaults_js: str) -> None:
        body = _fn(tvchart_defaults_js, "_tvBuildVolumeOptions")
        assert "lastValueVisible: true" in body
        assert "priceLineVisible: false" in body
        assert "priceScaleId: 'right'" in body

    def test_volume_auto_enables_in_create(self, tvchart_defaults_js: str) -> None:
        create = _create_body(tvchart_defaults_js)
        assert "enableVolume !== false" in create
        assert "_tvApplyDefaultVolumePaneHeight(" in create

    # -- Time range (zoom-only, no interval switching) --

    def test_time_range_handler_is_zoom_only(self, tvchart_defaults_js: str) -> None:
        body = _handler(tvchart_defaults_js, "tvchart:time-range")
        assert "_tvApplyTimeRangeSelection(" in body
        assert "_pendingTimeRange" not in body
        assert "targetInterval" not in body
        assert "tvchart:interval-change" not in body

    def test_time_range_selection_handles_all_and_ytd(self, tvchart_defaults_js: str) -> None:
        body = _fn(tvchart_defaults_js, "_tvApplyTimeRangeSelection")
        assert "range === 'all'" in body
        assert "fitContent()" in body
        assert "range === 'ytd'" in body
        assert "_tvResolveRangeSpanDays(" in body
        assert "function _tvApplyAbsoluteDateRange" in tvchart_defaults_js

    def test_range_span_resolver_covers_standard_presets(self, tvchart_defaults_js: str) -> None:
        body = _fn(tvchart_defaults_js, "_tvResolveRangeSpanDays")
        for preset in ("'1d'", "'5d'", "'1m'", "'3m'", "'6m'", "'1y'", "'5y'"):
            assert preset in body, f"Range resolver must cover preset {preset}"

    def test_no_pending_time_range_state(self, tvchart_defaults_js: str) -> None:
        assert "_pendingTimeRange" not in tvchart_defaults_js

    # -- Legend hover & crosshair --

    def test_legend_hover_falls_back_to_cached_data(self, tvchart_defaults_js: str) -> None:
        body = _fn(tvchart_defaults_js, "_legendResolveHoveredPoint")
        assert "param.seriesData" in body
        assert "_seriesRawData" in body
        assert "param.time" in body

    def test_legend_hover_refresh_functions_exist_and_are_called(
        self, tvchart_defaults_js: str
    ) -> None:
        for fn in ("_tvRefreshLegendTitle", "_tvEmitLegendRefresh", "_tvRenderHoverLegend"):
            assert f"function {fn}(" in tvchart_defaults_js, f"{fn} must be defined"
        for fn in ("_tvRefreshLegendTitle(", "_tvEmitLegendRefresh(", "_tvRenderHoverLegend("):
            count = tvchart_defaults_js.count(fn)
            assert count >= 2, (
                f"{fn} found {count} time(s) — must be defined AND called from at least one site"
            )

    def test_crosshair_mode_controlled_by_prefs(self, tvchart_defaults_js: str) -> None:
        body = _fn(tvchart_defaults_js, "_tvCrosshairLinesVisible")
        assert "crosshairEnabled" in body
        assert "function _tvApplyHoverReadoutMode(" in tvchart_defaults_js

    # -- Volume divider clearance & scale placement --

    def test_divider_clearance_conditionally_expands_bottom_margin(
        self, tvchart_defaults_js: str
    ) -> None:
        body = _fn(tvchart_defaults_js, "_tvEnforceMainScaleDividerClearance")
        assert "volumeMap" in body
        assert "Math.max(bottom" in body
        assert "scaleMargins" in body
        assert "_tvResolveScalePlacement(entry)" in body

    def test_scale_placement_resolver_used_at_series_creation(
        self, tvchart_defaults_js: str
    ) -> None:
        assert "function _tvResolveScalePlacement(entry)" in tvchart_defaults_js
        call_count = tvchart_defaults_js.count("_tvResolveScalePlacement(entry)")
        assert call_count >= 3, (
            f"_tvResolveScalePlacement called {call_count} time(s); expected >= 3 "
            "(definition + series creation + divider clearance)"
        )

    # -- Layout save/open --

    def test_layout_persist_builds_summary_from_contents(self, tvchart_defaults_js: str) -> None:
        body = _fn(tvchart_defaults_js, "_tvLayoutPersist")
        assert "indNames" in body or "summary" in body
        assert "_tvStorageSet(" in body
        assert "summary:" in body
        assert "symbol:" not in body
        assert "timeframe:" not in body

    def test_layout_apply_restores_drawings_and_indicators(self, tvchart_defaults_js: str) -> None:
        body = _fn(tvchart_defaults_js, "_tvApplyLayout")
        assert "_tvRenderDrawings(" in body
        assert "_tvRemoveIndicator(" in body
        assert "_tvAddIndicator(" in body
        assert "restoredGroups" in body
        assert (
            "setVisibleLogicalRange" not in body
            and "visibleRange" not in body.split("// visibleRange")[0]
        ), "Layout apply must not restore visibleRange (portability contract)"
        assert "_tvApplySettingsToChart(" in body

    def test_layout_meta_label_shows_summary_not_symbol(self, tvchart_defaults_js: str) -> None:
        body = _fn(tvchart_defaults_js, "_tvLayoutMetaLabel")
        assert "summary" in body
        assert "savedAt" in body or "Date" in body
        assert "symbol" not in body.lower()
        assert "timeframe" not in body.lower()

    def test_no_alert_in_layout_flow(self, tvchart_defaults_js: str) -> None:
        assert "window.alert(" not in tvchart_defaults_js

    # -- Candle settings & opacity controls --

    def test_candle_colours_use_opacity_popup(self, tvchart_defaults_js: str) -> None:
        assert "function _tvShowColorOpacityPopup(" in tvchart_defaults_js
        for part in ("Body", "Borders", "Wick"):
            assert f"addOpacityRow(lineSection, '{part}'" not in tvchart_defaults_js
            assert f"'{part}-Opacity'" in tvchart_defaults_js

    def test_candle_colour_with_opacity_applied(self, tvchart_defaults_js: str) -> None:
        parts = [
            "Body-Up Color",
            "Body-Down Color",
            "Borders-Up Color",
            "Borders-Down Color",
            "Wick-Up Color",
            "Wick-Down Color",
        ]
        for part in parts:
            assert f"_tvColorWithOpacity(settings['{part}']" in tvchart_defaults_js

    def test_settings_collect_hidden_inputs_for_opacity(self, tvchart_defaults_js: str) -> None:
        assert (
            "ctrl.type === 'number' || ctrl.type === 'text' || ctrl.type === 'range' || ctrl.type === 'hidden'"
            in tvchart_defaults_js
        )

    # -- Settings tabs --

    def test_settings_row_helpers_exist(self, tvchart_defaults_js: str) -> None:
        helpers = [
            "addIndentedCheckboxRow(parent, label, checked)",
            "addCheckboxSliderRow(parent, label, checked, enabledSetting, sliderValue, sliderSetting)",
            "addNumberInputRow(parent, label, settingKey, value, min, max, step, unitText, inputClassName)",
            "addColorSwatchRow(parent, label, color, settingKey)",
            "addCheckboxInputRow(parent, label, checked, enabledSetting, inputValue, inputSetting)",
            "addSelectColorRow(parent, label, options, selected, selectSetting, color, colorSetting)",
        ]
        for sig in helpers:
            assert f"function {sig}" in tvchart_defaults_js

    def test_scales_settings_uses_full_value_label(self, tvchart_defaults_js: str) -> None:
        assert "'Value according to scale'" in tvchart_defaults_js
        assert "addSelectRow(scalesSection, 'Value according to sc...'" not in tvchart_defaults_js
        assert "'Value according to sc...'" in tvchart_defaults_js

    def test_settings_preview_pipeline(self, tvchart_defaults_js: str) -> None:
        assert "JSON.parse(JSON.stringify(currentSettings" in tvchart_defaults_js
        for fn_name in ("collectSettingsFromPanel", "scheduleSettingsPreview", "persistSettings"):
            assert f"function {fn_name}(" in tvchart_defaults_js
        assert "_tvApplySettingsToChart(chartId, entry, originalSettings)" in tvchart_defaults_js
        assert "addEventListener('input'" in tvchart_defaults_js
        assert "addEventListener('change'" in tvchart_defaults_js

    # -- Navigation symmetry --

    def test_navigation_disable_restore_symmetry(self, tvchart_defaults_js: str) -> None:
        disable_count = tvchart_defaults_js.count(
            "entry.chart.applyOptions({ handleScroll: false, handleScale: false })"
        )
        restore_count = tvchart_defaults_js.count(
            "entry.chart.applyOptions({ handleScroll: true, handleScale: true })"
        )
        assert disable_count >= 1
        assert disable_count == restore_count

    def test_ensure_interactive_navigation_exists(self, tvchart_defaults_js: str) -> None:
        body = _fn(tvchart_defaults_js, "_tvEnsureInteractiveNavigation")
        assert "handleScroll" in body or "applyOptions" in body
        all_calls = tvchart_defaults_js.count("_tvEnsureInteractiveNavigation(entry)")
        assert all_calls >= 2

    def test_interactive_navigation_options_enable_all_inputs(
        self, tvchart_defaults_js: str
    ) -> None:
        body = _fn(tvchart_defaults_js, "_tvInteractiveNavigationOptions")
        for opt in ("mouseWheel: true", "pressedMouseMove: true", "pinch: true"):
            assert opt in body

    # -- Chart-type change (add-then-remove ordering) --

    def test_chart_type_change_adds_new_before_removing_old(self, tvchart_defaults_js: str) -> None:
        handler = _handler(tvchart_defaults_js, "tvchart:chart-type-change")
        add_pos = handler.index("_tvAddSeriesCompat(entry.chart,")
        remove_pos = handler.index("entry.chart.removeSeries(oldSeries)")
        assert add_pos < remove_pos

    def test_settings_rebuild_adds_new_before_removing_old(self, tvchart_defaults_js: str) -> None:
        anchor = "_tvAddSeriesCompat(entry.chart, targetType, rebuiltOptions"
        settings_start = tvchart_defaults_js.index(anchor)
        region = tvchart_defaults_js[max(0, settings_start - 600) : settings_start + 600]
        add_pos = region.index(anchor)
        remove_pos = region.index("entry.chart.removeSeries(oldSeries)")
        assert add_pos < remove_pos

    def test_chart_type_change_handler_scoped_to_single_chart(
        self, tvchart_defaults_js: str
    ) -> None:
        handler = _handler(tvchart_defaults_js, "tvchart:chart-type-change")
        assert "_tvResolveChartEntry(" in handler
        assert "Object.keys(window.__PYWRY_TVCHARTS__)" not in handler

    # -- Baseline series & chart creation --

    def test_baseline_series_computes_base_value_in_both_paths(
        self, tvchart_defaults_js: str
    ) -> None:
        assert "function _tvComputeBaselineValue(bars, pct)" in tvchart_defaults_js
        handler = _handler(tvchart_defaults_js, "tvchart:chart-type-change")
        assert "_tvComputeBaselineValue(" in handler
        create = _create_body(tvchart_defaults_js)
        assert "_tvComputeBaselineValue(" in create

    def test_create_branches_on_datafeed_mode(self, tvchart_defaults_js: str) -> None:
        create = _create_body(tvchart_defaults_js)
        assert "payload.useDatafeed" in create
        assert "_tvInitDatafeedMode(" in create

    def test_datafeed_init_orchestrates_full_protocol(self, tvchart_defaults_js: str) -> None:
        body = _fn(tvchart_defaults_js, "_tvInitDatafeedMode")
        assert "_tvCreateDatafeed(" in body
        for method in ("onReady", "resolveSymbol", "getBars", "subscribeBars"):
            assert f"datafeed.{method}(" in body

    # -- Layout export (no raw data, portable) --

    def test_layout_export_excludes_raw_data_and_visible_range(
        self, tvchart_defaults_js: str
    ) -> None:
        body = _fn(tvchart_defaults_js, "_tvExportLayout")
        assert "indicators" in body
        assert "drawings" in body
        assert "settings" in body or "_tvBuildCurrentSettings" in body
        assert "rawData:" not in body
        assert "visibleRange:" not in body

    def test_layout_export_preserves_grouped_indicator_metadata(
        self, tvchart_defaults_js: str
    ) -> None:
        body = _fn(tvchart_defaults_js, "_tvExportLayout")
        for field in ("multiplier", "maType", "offset", "source"):
            assert field in body


# =============================================================================
# Indicator catalogue + compute + recompute
# =============================================================================


class TestTVChartIndicatorCatalog:
    """Every indicator advertised by the catalog must have:

    * a compute function present in the bundled JS,
    * an add-indicator branch that creates its series, and
    * a recompute branch in ``_tvRecomputeIndicatorSeries`` so it refreshes
      when underlying bars change (otherwise indicators silently freeze at
      their initial snapshot when the datafeed replaces bars).
    """

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
    def test_catalog_contains_indicator(self, tvchart_defaults_js: str, name: str) -> None:
        cat_start = tvchart_defaults_js.index("_INDICATOR_CATALOG = [")
        cat_end = tvchart_defaults_js.index("];", cat_start)
        catalog_src = tvchart_defaults_js[cat_start:cat_end]
        assert f"name: '{name}'" in catalog_src

    def test_volume_profile_entries_are_primitive(self, tvchart_defaults_js: str) -> None:
        cat_start = tvchart_defaults_js.index("_INDICATOR_CATALOG = [")
        cat_end = tvchart_defaults_js.index("];", cat_start)
        catalog_src = tvchart_defaults_js[cat_start:cat_end]
        for key in ("'volume-profile-fixed'", "'volume-profile-visible'"):
            block = catalog_src[catalog_src.index(key) :]
            first_close = block.index("}")
            entry = block[:first_close]
            assert "primitive: true" in entry

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
    def test_compute_function_defined(self, tvchart_defaults_js: str, fn_name: str) -> None:
        assert f"function {fn_name}(" in tvchart_defaults_js

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
    def test_add_branch_wires_compute(self, tvchart_defaults_js: str, branch: str, fn: str) -> None:
        assert branch in tvchart_defaults_js
        branch_idx = tvchart_defaults_js.index(branch)
        next_branch = tvchart_defaults_js.find("} else if (name ===", branch_idx + 1)
        if next_branch < 0:
            next_branch = tvchart_defaults_js.find("_tvAddIndicator fallthrough", branch_idx + 1)
        segment = tvchart_defaults_js[
            branch_idx : next_branch if next_branch > 0 else branch_idx + 2000
        ]
        assert fn in segment

    @pytest.fixture()
    def recompute_body(self, tvchart_defaults_js: str) -> str:
        start = tvchart_defaults_js.index("function _tvRecomputeIndicatorSeries(")
        depth = 0
        i = tvchart_defaults_js.index("{", start)
        n = len(tvchart_defaults_js)
        while i < n:
            ch = tvchart_defaults_js[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return tvchart_defaults_js[start : i + 1]
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
        assert branch in recompute_body
        idx = recompute_body.index(branch)
        tail = recompute_body[idx : idx + 2500]
        assert fn in tail

    def test_recompute_branch_for_volume_profile(self, recompute_body: str) -> None:
        assert "type === 'volume-profile-visible'" in recompute_body
        assert "_tvRefreshVisibleVolumeProfiles" in recompute_body


# =============================================================================
# Volume Profile compute contract
# =============================================================================


class TestTVChartVolumeProfile:
    def test_vp_compute_function_signature(self, tvchart_defaults_js: str) -> None:
        assert "function _tvComputeVolumeProfile(bars, fromIdx, toIdx, opts)" in tvchart_defaults_js

    def test_vp_result_returns_profile_and_metadata(self, tvchart_defaults_js: str) -> None:
        fn_start = tvchart_defaults_js.index("function _tvComputeVolumeProfile(")
        fn_end = tvchart_defaults_js.index("\nfunction ", fn_start + 1)
        body = tvchart_defaults_js[fn_start:fn_end]
        for key in ("profile", "minPrice", "maxPrice", "step", "totalVolume"):
            assert key in body

    def test_vp_splits_up_down_volume(self, tvchart_defaults_js: str) -> None:
        fn_start = tvchart_defaults_js.index("function _tvComputeVolumeProfile(")
        fn_end = tvchart_defaults_js.index("\nfunction ", fn_start + 1)
        body = tvchart_defaults_js[fn_start:fn_end]
        assert "upVol" in body and "downVol" in body

    def test_vp_exposes_poc_value_area_helper(self, tvchart_defaults_js: str) -> None:
        assert "function _tvComputePOCAndValueArea(" in tvchart_defaults_js
        fn_start = tvchart_defaults_js.index("function _tvComputePOCAndValueArea(")
        fn_end = tvchart_defaults_js.index("\nfunction ", fn_start + 1)
        body = tvchart_defaults_js[fn_start:fn_end]
        for key in ("pocIdx", "vaLowIdx", "vaHighIdx"):
            assert key in body

    def test_vp_refresh_visible_exposed(self, tvchart_defaults_js: str) -> None:
        assert "function _tvRefreshVisibleVolumeProfiles(chartId)" in tvchart_defaults_js


# =============================================================================
# Legend volume removal actually destroys the series + pane
# =============================================================================


class TestTVChartLegendVolumeRemoval:
    """Removing volume from the legend must actually remove it from the
    chart (issue: previously, clicking Remove only set a legend dataset
    flag but left the histogram series and its pane on the chart)."""

    def test_disable_volume_removes_series(self, tvchart_defaults_js: str) -> None:
        body = _fn_or_nested(tvchart_defaults_js, "_legendDisableVolume")
        assert "entry.chart.removeSeries(volSeries)" in body
        assert "delete entry.volumeMap.main" in body

    def test_disable_volume_removes_pane(self, tvchart_defaults_js: str) -> None:
        body = _fn_or_nested(tvchart_defaults_js, "_legendDisableVolume")
        assert "chart.removePane(removedPane)" in body

    def test_disable_volume_reindexes_panes(self, tvchart_defaults_js: str) -> None:
        body = _fn_or_nested(tvchart_defaults_js, "_legendDisableVolume")
        assert ".paneIndex -= 1" in body
        assert "_volumePaneBySeries" in body

    def test_enable_volume_rebuilds_series(self, tvchart_defaults_js: str) -> None:
        body = _fn_or_nested(tvchart_defaults_js, "_legendEnableVolume")
        assert "_tvAddSeriesCompat(entry.chart, 'Histogram'" in body
        assert "_tvExtractVolumeFromBars" in body


# =============================================================================
# Theme CSS variables — parity across dark + light themes
# =============================================================================


class TestTVChartThemeVariables:
    """The tvchart.css stylesheet must define every CSS variable that the
    frontend JS consumes, in both dark and light themes."""

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
    def test_var_defined_at_least_twice(self, tvchart_css: str, var: str) -> None:
        count = tvchart_css.count(var + ":")
        assert count >= 2, (
            f"CSS var {var} defined only {count} time(s); expected at least 2 "
            "(one for dark theme, one for light)."
        )


# =============================================================================
# Specialty chart factories: createOptionsChart + createYieldCurveChart
# =============================================================================


class TestTVChartSpecialtyChartKinds:
    """Lightweight Charts 5.x exposes three factories:
      * createChart              — time X axis (default)
      * createOptionsChart       — numeric price / strike X axis
      * createYieldCurveChart    — tenor-in-months X axis

    PyWry routes these via ``payload.chartKind`` in
    ``PYWRY_TVCHART_CREATE``."""

    def test_bundle_ships_all_three_builders(self, tvchart_defaults_js: str) -> None:
        assert "function _tvBuildChartOptions(" in tvchart_defaults_js
        assert "function _tvBuildPriceChartOptions(" in tvchart_defaults_js
        assert "function _tvBuildYieldCurveChartOptions(" in tvchart_defaults_js

    def test_price_builder_inherits_base_defaults(self, tvchart_defaults_js: str) -> None:
        start = tvchart_defaults_js.index("function _tvBuildPriceChartOptions(")
        body = _extract_braced(tvchart_defaults_js, start)
        assert "_tvBuildChartOptions(null, theme)" in body

    def test_yield_curve_builder_seeds_yield_curve_options(self, tvchart_defaults_js: str) -> None:
        start = tvchart_defaults_js.index("function _tvBuildYieldCurveChartOptions(")
        body = _extract_braced(tvchart_defaults_js, start)
        assert "_tvBuildChartOptions(null, theme)" in body
        assert "yieldCurve" in body
        assert "baseResolution" in body
        assert "minimumTimeRange" in body
        assert "startTimeRange" in body

    def test_yield_curve_builder_ignores_whitespace_indices(self, tvchart_defaults_js: str) -> None:
        start = tvchart_defaults_js.index("function _tvBuildYieldCurveChartOptions(")
        body = _extract_braced(tvchart_defaults_js, start)
        assert "ignoreWhitespaceIndices = true" in body

    def test_create_dispatches_to_price_factory(self, tvchart_defaults_js: str) -> None:
        body = _create_body(tvchart_defaults_js)
        assert "LightweightCharts.createOptionsChart(container, chartOptions)" in body
        assert "chartKind === 'price'" in body

    def test_create_dispatches_to_yield_curve_factory(self, tvchart_defaults_js: str) -> None:
        body = _create_body(tvchart_defaults_js)
        assert "LightweightCharts.createYieldCurveChart(container, chartOptions)" in body
        assert "yield-curve" in body

    def test_create_default_falls_back_to_create_chart(self, tvchart_defaults_js: str) -> None:
        body = _create_body(tvchart_defaults_js)
        assert "LightweightCharts.createChart(container, chartOptions)" in body

    def test_volume_auto_enable_gated_on_default_chart_kind(self, tvchart_defaults_js: str) -> None:
        body = _create_body(tvchart_defaults_js)
        assert "enableVolume !== false && chartKind === 'default'" in body

    def test_time_range_tabs_gated_on_default_chart_kind(self, tvchart_defaults_js: str) -> None:
        body = _create_body(tvchart_defaults_js)
        idx_guard = body.find("chartKind === 'default'")
        idx_tab_query = body.find(".pywry-tab-active[data-target-interval]")
        assert idx_guard != -1 and idx_tab_query != -1
        assert idx_guard < idx_tab_query


# =============================================================================
# Inline / app payload carries chart_kind
# =============================================================================


class TestTVChartSpecialtyInlinePayload:
    def test_inline_payload_carries_chart_kind(self) -> None:
        import inspect

        from pywry import inline as pywry_inline

        src = inspect.getsource(pywry_inline.show_tvchart)
        assert '"chartKind": chart_kind' in src

    def test_inline_show_tvchart_accepts_chart_kind(self) -> None:
        import inspect

        from pywry import inline as pywry_inline

        sig = inspect.signature(pywry_inline.show_tvchart)
        assert "chart_kind" in sig.parameters
        assert sig.parameters["chart_kind"].default == "default"

    def test_app_show_tvchart_accepts_chart_kind(self) -> None:
        import inspect

        from pywry.app import PyWry

        sig = inspect.signature(PyWry.show_tvchart)
        assert "chart_kind" in sig.parameters
        assert "yield_curve" in sig.parameters
        assert sig.parameters["chart_kind"].default == "default"

    def test_specialty_demo_cells_in_notebook(self) -> None:
        nb_path = Path(__file__).resolve().parent.parent / "examples" / "pywry_demo_tvchart.ipynb"
        if not nb_path.exists():
            pytest.skip("demo notebook not bundled in this source tree")
        nb = json.loads(nb_path.read_text(encoding="utf-8"))
        code_cells = [
            "".join(c.get("source", []))
            for c in nb.get("cells", [])
            if c.get("cell_type") == "code"
        ]
        assert any('chart_kind="yield-curve"' in src and "yield_curve" in src for src in code_cells)
        assert any('chart_kind="price"' in src for src in code_cells)
        # Every code cell still parses as valid Python.
        for src in code_cells:
            ast.parse(src)


# =============================================================================
# show_tvchart public API signature
# =============================================================================


class TestShowTVChartSignature:
    """``show_tvchart`` has many keyword arguments — lock the signature
    against accidental removal."""

    def test_signature_params(self) -> None:
        import inspect

        from pywry.inline import show_tvchart

        params = list(inspect.signature(show_tvchart).parameters.keys())
        for required in (
            "data",
            "callbacks",
            "title",
            "width",
            "height",
            "theme",
            "chart_options",
            "series_options",
            "symbol_col",
            "max_bars",
            "toolbars",
            "use_datafeed",
            "symbol",
            "resolution",
        ):
            assert required in params, f"show_tvchart missing param {required!r}"

    def test_data_defaults_to_none(self) -> None:
        import inspect

        from pywry.inline import show_tvchart

        assert inspect.signature(show_tvchart).parameters["data"].default is None

    def test_use_datafeed_defaults_to_false(self) -> None:
        import inspect

        from pywry.inline import show_tvchart

        assert inspect.signature(show_tvchart).parameters["use_datafeed"].default is False

    def test_resolution_defaults_to_1d(self) -> None:
        import inspect

        from pywry.inline import show_tvchart

        assert inspect.signature(show_tvchart).parameters["resolution"].default == "1D"


# =============================================================================
# PyWryTVChartWidget shape
# =============================================================================


class TestPyWryTVChartWidgetShape:
    def test_class_exists(self) -> None:
        from pywry.widget import PyWryTVChartWidget

        assert PyWryTVChartWidget is not None

    def test_fallback_instantiation(self) -> None:
        from pywry.widget import PyWryTVChartWidget

        w = PyWryTVChartWidget(content="<div>test</div>")
        assert hasattr(w, "content")

    def test_has_emit_method(self) -> None:
        from pywry.widget import PyWryTVChartWidget

        w = PyWryTVChartWidget(content="")
        assert callable(getattr(w, "emit", None))

    def test_has_on_method(self) -> None:
        from pywry.widget import PyWryTVChartWidget

        w = PyWryTVChartWidget(content="")
        assert callable(getattr(w, "on", None))


# =============================================================================
# Public API imports — every TVChart symbol re-exported on `pywry`
# =============================================================================


class TestPublicAPIImports:
    """The TVChart symbols must be importable from the top-level
    :mod:`pywry` package as well as from :mod:`pywry.tvchart`."""

    EXPECTED_TVCHART_SYMBOLS = (
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
    )

    @pytest.mark.parametrize("name", EXPECTED_TVCHART_SYMBOLS)
    def test_symbol_in_pywry_all(self, name: str) -> None:
        import pywry

        assert name in pywry.__all__, f"{name} not in pywry.__all__"

    @pytest.mark.parametrize("name", EXPECTED_TVCHART_SYMBOLS)
    def test_symbol_importable_from_pywry(self, name: str) -> None:
        import pywry

        assert getattr(pywry, name, None) is not None, f"pywry.{name} resolves to None"


# =============================================================================
# MCP show_tvchart tool registration
# =============================================================================


class TestMCPToolDefinition:
    def test_tool_schema_exists(self) -> None:
        from pywry.mcp.tools import get_tools

        names = [t.name for t in get_tools()]
        assert "show_tvchart" in names

    def test_tool_schema_has_data_json(self) -> None:
        from pywry.mcp.tools import get_tools

        tool = next(t for t in get_tools() if t.name == "show_tvchart")
        assert "data_json" in tool.inputSchema["properties"]

    def test_handler_registered(self) -> None:
        from pywry.mcp.handlers import _HANDLERS

        assert "show_tvchart" in _HANDLERS
