# pylint: disable=missing-function-docstring,redefined-outer-name,unsubscriptable-object
"""E2E tests for TradingView charts with real UDF datafeed.

Uses a real UDFAdapter connected to the BitMEX public UDF server to test
every layer -- Python datafeed wiring, IPC transport, and JavaScript DOM
state -- across native, inline, and browser rendering paths.

Architecture:
  ONE chart opens.  It STAYS OPEN.  Every test in ``TestTVChartFullLifecycle``
  runs against that same live window in definition order:

      open -> verify data -> interval change -> chart types -> indicators ->
      indicator settings -> overlays -> pane swap -> drawing tools ->
      drawing settings -> undo/redo -> scale modes -> time scale ->
      markers & price lines -> theme switch -> streaming -> state export ->
      cleanup -> destroy

  Inline / browser / Redis / RBAC tests follow in their own classes.
"""

from __future__ import annotations

import os
import socket
import time
import urllib.error
import urllib.request

from typing import Any

import pytest

from tests.conftest import (
    ReadyWaiter,
    _clear_registries,
    _stop_runtime_sync,
    wait_for_result,
)
from tests.constants import SHORT_TIMEOUT


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

UDF_URL = "https://www.bitmex.com/api/udf"
UDF_SYMBOL = "XBTUSD"
UDF_RESOLUTION = "D"

CHART_RENDER_WAIT = 5.0
WINDOW_TIMEOUT = 30.0


# ---------------------------------------------------------------------------
# JS helpers
# ---------------------------------------------------------------------------

_FULL_STATE_JS = """
(function() {
    var reg = window.__PYWRY_TVCHARTS__ || {};
    var ids = Object.keys(reg);
    var cid = ids.length > 0 ? ids[0] : null;
    var entry = cid ? reg[cid] : null;
    var container = entry ? entry.container : null;
    var raw = (entry && entry._seriesRawData)
        ? entry._seriesRawData['main'] : null;

    pywry.result({
        hasLWC: typeof LightweightCharts !== 'undefined',
        hasRegistry: !!window.__PYWRY_TVCHARTS__,
        chartCount: ids.length,
        hasChart: !!entry,
        seriesIds: entry ? Object.keys(entry.seriesMap || {}) : [],
        volumeIds: entry ? Object.keys(entry.volumeMap || {}) : [],
        containerHasChildren: container ? container.children.length > 0 : false,
        theme: entry ? (entry.theme || '') : '',
        barCount: raw ? raw.length : 0,
        hasGlobals: (
            typeof window.PYWRY_TVCHART_CREATE === 'function' &&
            typeof window.PYWRY_TVCHART_STREAM === 'function' &&
            typeof window.PYWRY_TVCHART_DESTROY === 'function'
        ),
        chartDisplayStyle: entry ? (entry._chartDisplayStyle || null) : null,
    });
})();
"""


def _full_state(label: str) -> dict[str, Any]:
    result = wait_for_result(label, _FULL_STATE_JS)
    assert result is not None, "No response from chart window!"
    return result


def _js(label: str, script: str, timeout: float = SHORT_TIMEOUT) -> dict[str, Any]:
    """Shorthand: execute JS and return result dict, asserting non-None."""
    result = wait_for_result(label, script, timeout=timeout)
    assert result is not None, f"JS returned None for:\n{script[:120]}"
    return result


def _cid() -> str:
    """Standard JS preamble to resolve chartId + entry."""
    return (
        "var cid = Object.keys(window.__PYWRY_TVCHARTS__)[0];"
        "var entry = window.__PYWRY_TVCHARTS__[cid];"
    )


# JS helpers for driving the REAL drawing pipeline (tool-selection + a
# synthetic ``click`` MouseEvent dispatched on the overlay canvas, not
# a direct ``ds.drawings.push``).  The click handler computes the
# time/price from the click pixel via ``_tvFromPixel``, pushes the
# drawing itself, and calls ``_tvRenderDrawings`` — so the canvas
# actually ends up with drawing pixels and the tests exercise the same
# code the user would hit with a mouse.
_DRAW_PIXEL_JS = (
    "function _dispatchDrawClick(ds, fx, fy) {"
    "  var rect = ds.canvas.getBoundingClientRect();"
    "  var mx = rect.left + rect.width * fx;"
    "  var my = rect.top + rect.height * fy;"
    "  var ev = new MouseEvent('click', {"
    "    bubbles: true, cancelable: true, view: window,"
    "    clientX: mx, clientY: my, button: 0,"
    "  });"
    "  ds.canvas.dispatchEvent(ev);"
    "}"
    "function _canvasHasPixels(ds) {"
    "  try {"
    "    var w = ds.canvas.width, h = ds.canvas.height;"
    "    if (!w || !h) return false;"
    "    var data = ds.ctx.getImageData(0, 0, w, h).data;"
    "    for (var i = 3; i < data.length; i += 4) if (data[i] !== 0) return true;"
    "    return false;"
    "  } catch (e) { return null; }"
    "}"
)


def _draw_hline_script() -> str:
    return (
        _DRAW_PIXEL_JS
        + "_tvSetDrawTool(cid, 'hline');"
        + "var ds = window.__PYWRY_DRAWINGS__[cid];"
        + "if (!ds) { pywry.result({error:'no drawing state'}); return; }"
        + "var before = ds.drawings.length;"
        + "_dispatchDrawClick(ds, 0.5, 0.5);"
        + "var rendered = _canvasHasPixels(ds);"
        + "_tvSetDrawTool(cid, 'cursor');"
        + "pywry.result({"
        + "  count: ds.drawings.length,"
        + "  added: ds.drawings.length - before,"
        + "  type: ds.drawings.length ? ds.drawings[ds.drawings.length - 1].type : null,"
        + "  rendered: rendered,"
        + "});"
    )


def _draw_two_point_script(tool: str) -> str:
    return (
        _DRAW_PIXEL_JS
        + "_tvSetDrawTool(cid, '"
        + tool
        + "');"
        + "var ds = window.__PYWRY_DRAWINGS__[cid];"
        + "if (!ds) { pywry.result({error:'no drawing state'}); return; }"
        + "var before = ds.drawings.length;"
        + "_dispatchDrawClick(ds, 0.3, 0.4);"
        + "_dispatchDrawClick(ds, 0.7, 0.6);"
        + "_tvSetDrawTool(cid, 'cursor');"
        + "pywry.result({"
        + "  count: ds.drawings.length,"
        + "  added: ds.drawings.length - before,"
        + "  type: ds.drawings.length ? ds.drawings[ds.drawings.length - 1].type : null,"
        + "});"
    )


def _draw_single_point_script(tool: str) -> str:
    # The ``text`` tool's canvas-click handler auto-opens
    # ``_tvShowDrawingSettings`` (so the user can name the label
    # immediately).  That flips ``entry._interactionLocked`` to
    # true.  Leaving the overlay up leaks locked state into every
    # subsequent test in the class-scoped fixture — test 39's
    # ``assert lockedBefore is False`` then fails.  Close the
    # drawing-settings overlay and any floating toolbar, then
    # clear the lock flag defensively so the idle-chart contract
    # holds.
    return (
        _DRAW_PIXEL_JS
        + "_tvSetDrawTool(cid, '"
        + tool
        + "');"
        + "var ds = window.__PYWRY_DRAWINGS__[cid];"
        + "if (!ds) { pywry.result({error:'no drawing state'}); return; }"
        + "var before = ds.drawings.length;"
        + "_dispatchDrawClick(ds, 0.4, 0.5);"
        + "if (typeof _tvHideDrawingSettings === 'function') _tvHideDrawingSettings();"
        + "if (typeof _tvHideFloatingToolbar === 'function') _tvHideFloatingToolbar();"
        + "_tvSetDrawTool(cid, 'cursor');"
        + "if (entry) entry._interactionLocked = false;"
        + "pywry.result({"
        + "  count: ds.drawings.length,"
        + "  added: ds.drawings.length - before,"
        + "  type: ds.drawings.length ? ds.drawings[ds.drawings.length - 1].type : null,"
        + "});"
    )


# ============================================================================
# Fixture -- ONE chart for the entire class
# ============================================================================


@pytest.fixture(scope="class")
def chart(request) -> dict[str, Any]:
    """Class-scoped UDF chart shared by ALL tests in TestTVChartFullLifecycle."""
    from pywry.app import PyWry
    from pywry.models import ThemeMode
    from pywry.tvchart.udf import UDFAdapter

    _stop_runtime_sync()
    _clear_registries()

    if request.cls is not None:
        request.cls._pywry_class_scoped = True

    app = PyWry(theme=ThemeMode.DARK)
    udf = UDFAdapter(UDF_URL, poll_interval=60)

    waiter = ReadyWaiter(timeout=WINDOW_TIMEOUT)

    widget = udf.connect(
        app,
        symbol=UDF_SYMBOL,
        resolution=UDF_RESOLUTION,
        title="TradingView E2E",
        width=1200,
        height=700,
        callbacks={"pywry:ready": waiter.on_ready},
    )
    label = widget.label if hasattr(widget, "label") else str(widget)

    if not waiter.wait():
        ping = wait_for_result(
            label,
            "pywry.result({ state: document.readyState, hasBody: !!document.body });",
            timeout=SHORT_TIMEOUT,
            retries=1,
        )
        if not (isinstance(ping, dict) and ping.get("hasBody")):
            # Clean up before skipping so the finalizer doesn't error
            udf.close()
            app.close()
            _stop_runtime_sync()
            _clear_registries()
            pytest.skip(
                f"UDF chart window '{label}' did not become ready within {WINDOW_TIMEOUT}s"
                " (native runtime unavailable)"
            )

    time.sleep(CHART_RENDER_WAIT)

    yield {"app": app, "udf": udf, "label": label}

    udf.close()
    app.close()
    _stop_runtime_sync()
    _clear_registries()


# ============================================================================
# THE TEST CLASS -- one chart, stays open, tests everything in order
# ============================================================================


class TestTVChartFullLifecycle:
    """Open one chart.  Keep it open.  Test *everything*."""

    # ------------------------------------------------------------------
    # 1. Foundation -- chart loaded with real data
    # ------------------------------------------------------------------

    def test_01_chart_loaded_with_data(self, chart: dict[str, Any]) -> None:
        """LWC loaded, registry populated, real BitMEX bars present."""
        s = _full_state(chart["label"])
        assert s["hasLWC"], "LightweightCharts library not loaded"
        assert s["hasRegistry"], "__PYWRY_TVCHARTS__ registry missing"
        assert s["hasChart"], "No chart entry in registry"
        assert s["hasGlobals"], "Global tvchart functions missing"
        assert s["barCount"] > 0, "No bars loaded from BitMEX"
        assert s["containerHasChildren"], "Container has no DOM children"
        assert "main" in s["seriesIds"]
        assert len(s["volumeIds"]) > 0, "Volume histogram missing"

    def test_02_udf_config_fetched(self, chart: dict[str, Any]) -> None:
        udf = chart["udf"]
        assert udf.config is not None, "UDF config was never fetched"
        assert "supported_resolutions" in udf.config
        assert len(udf.config["supported_resolutions"]) > 0

    def test_03_subscription_active(self, chart: dict[str, Any]) -> None:
        assert len(chart["udf"]._subscriptions) > 0

    def test_04_dark_theme_active(self, chart: dict[str, Any]) -> None:
        """Theme is 'dark' and chart bg is dark (low-luminance)."""
        r = _js(
            chart["label"],
            "(function() {" + _cid() + "var opts = entry.chart.options();"
            "var bg = opts.layout.background.color || '';"
            "pywry.result({"
            "  theme: entry.theme,"
            "  bg: bg,"
            "  isWhite: bg.indexOf('255') >= 0 && bg.indexOf('255') === bg.lastIndexOf('255') ? false : bg === '#ffffff' || bg.indexOf('255, 255, 255') >= 0,"
            "});"
            "})();",
        )
        assert r["theme"] == "dark"
        assert r["isWhite"] is not True, f"Dark theme should not have white bg: {r['bg']}"

    # ------------------------------------------------------------------
    # 2. Interval change
    # ------------------------------------------------------------------

    def test_05_interval_change_emits_data_request(self, chart: dict[str, Any]) -> None:
        """Changing interval emits tvchart:data-request to Python."""
        r = _js(
            chart["label"],
            "(function() {"
            "var emitted = [];"
            "var orig = window.pywry.emit;"
            "window.pywry.emit = function(t, d) {"
            "  if (t === 'tvchart:data-request') emitted.push(d);"
            "  return orig.apply(this, arguments);"
            "};"
            "window.pywry._trigger('tvchart:interval-change', {value: '1h'});"
            "window.pywry.emit = orig;"
            "pywry.result({"
            "  count: emitted.length,"
            "  hasInterval: emitted.length > 0"
            "    ? !!(emitted[0].interval || emitted[0].resolution) : false,"
            "});"
            "})();",
        )
        assert r["count"] >= 1, "interval-change should emit data-request"

    # ------------------------------------------------------------------
    # 3. Chart type cycling
    # ------------------------------------------------------------------

    def test_06_chart_type_to_line(self, chart: dict[str, Any]) -> None:
        r = _js(
            chart["label"],
            "(function() {" + _cid() + "window.pywry._trigger('tvchart:chart-type-change',"
            "  {value: 'Line', chartId: cid});"
            "pywry.result({style: entry._chartDisplayStyle});"
            "})();",
        )
        assert r["style"] == "Line"

    def test_07_chart_type_cycle_all(self, chart: dict[str, Any]) -> None:
        """Cycle: Area -> Baseline -> Bars -> HLC Area -> Candles."""
        r = _js(
            chart["label"],
            "(function() {" + _cid() + "var styles = [];"
            "var types = ['Area', 'Baseline', 'Bars', 'HLC Area', 'Candles'];"
            "for (var i = 0; i < types.length; i++) {"
            "  window.pywry._trigger('tvchart:chart-type-change',"
            "    {value: types[i], chartId: cid});"
            "  styles.push(entry._chartDisplayStyle || 'UNSET');"
            "}"
            "pywry.result({styles: styles});"
            "})();",
        )
        assert r["styles"] == ["Area", "Baseline", "Bars", "HLC Area", "Candles"]

    # ------------------------------------------------------------------
    # 4. Indicators -- add, verify, keep open
    # ------------------------------------------------------------------

    def test_08_add_sma_20(self, chart: dict[str, Any]) -> None:
        """Add an SMA(20) overlay via the unified Moving Average entry."""
        r = _js(
            chart["label"],
            "(function() {" + _cid() + "var before = Object.keys(entry.seriesMap).length;"
            "_tvAddIndicator("
            "  {name: 'Moving Average', key: 'moving-average-ex',"
            "   fullName: 'Moving Average', category: 'Moving Averages',"
            "   defaultPeriod: 20, _method: 'SMA'},"
            "  cid"
            ");"
            "var after = Object.keys(entry.seriesMap).length;"
            "var indKey = Object.keys(_activeIndicators).filter("
            "  function(k) {"
            "    var ai = _activeIndicators[k];"
            "    return ai.type === 'moving-average-ex' && ai.method === 'SMA';"
            "  }"
            ")[0];"
            "var info = indKey ? _activeIndicators[indKey] : null;"
            "pywry.result({"
            "  before: before, after: after,"
            "  name: info ? info.name : null,"
            "  method: info ? info.method : null,"
            "  period: info ? info.period : null,"
            "  isSubplot: info ? !!info.isSubplot : null,"
            "  seriesId: indKey || null,"
            "});"
            "})();",
        )
        assert r["after"] > r["before"], "Moving Average should add a new series"
        assert r["name"] == "Moving Average"
        assert r["method"] == "SMA"
        assert r["period"] == 20
        assert r["isSubplot"] is False

    def test_09_sma_has_computed_data(self, chart: dict[str, Any]) -> None:
        """SMA line contains non-null values after period warm-up."""
        r = _js(
            chart["label"],
            "(function() {" + _cid() + "var indKey = Object.keys(_activeIndicators).filter("
            "  function(k) {"
            "    var ai = _activeIndicators[k];"
            "    return ai.type === 'moving-average-ex' && ai.method === 'SMA';"
            "  }"
            ")[0];"
            "var series = indKey ? entry.seriesMap[indKey] : null;"
            "var data = [];"
            "if (series && typeof series.data === 'function') data = series.data();"
            "var nonNull = 0;"
            "for (var i = 0; i < data.length; i++) {"
            "  if (data[i].value !== undefined && data[i].value !== null) nonNull++;"
            "}"
            "pywry.result({total: data.length, nonNull: nonNull});"
            "})();",
        )
        assert r["nonNull"] > 0, "SMA should have computed values"

    # ------------------------------------------------------------------
    # 5. Indicator settings -- change period + color, keep open
    # ------------------------------------------------------------------

    def test_10_change_sma_period_to_50(self, chart: dict[str, Any]) -> None:
        r = _js(
            chart["label"],
            "(function() {" + _cid() + "var indKey = Object.keys(_activeIndicators).filter("
            "  function(k) {"
            "    var ai = _activeIndicators[k];"
            "    return ai.type === 'moving-average-ex' && ai.method === 'SMA';"
            "  }"
            ")[0];"
            "_tvApplyIndicatorSettings(indKey, {period: 50});"
            "var info = _activeIndicators[indKey];"
            "pywry.result({period: info ? info.period : null});"
            "})();",
        )
        assert r["period"] == 50

    def test_11_change_sma_color(self, chart: dict[str, Any]) -> None:
        r = _js(
            chart["label"],
            "(function() {" + _cid() + "var indKey = Object.keys(_activeIndicators).filter("
            "  function(k) {"
            "    var ai = _activeIndicators[k];"
            "    return ai.type === 'moving-average-ex' && ai.method === 'SMA';"
            "  }"
            ")[0];"
            "_tvApplyIndicatorSettings(indKey, {color: '#ff6600'});"
            "var info = _activeIndicators[indKey];"
            "pywry.result({color: info ? info.color : null});"
            "})();",
        )
        assert r["color"] == "#ff6600"

    def test_12_add_ema_overlay(self, chart: dict[str, Any]) -> None:
        """Add an EMA(12) -- now two overlay indicators active."""
        r = _js(
            chart["label"],
            "(function() {" + _cid() + "_tvAddIndicator("
            "  {name: 'Moving Average', key: 'moving-average-ex',"
            "   fullName: 'Moving Average', category: 'Moving Averages',"
            "   defaultPeriod: 12, _method: 'EMA'},"
            "  cid"
            ");"
            "var indKeys = Object.keys(_activeIndicators);"
            "var overlays = indKeys.filter(function(k) {"
            "  return !_activeIndicators[k].isSubplot;"
            "});"
            "pywry.result({"
            "  totalIndicators: indKeys.length,"
            "  overlayCount: overlays.length,"
            "});"
            "})();",
        )
        assert r["totalIndicators"] >= 2
        assert r["overlayCount"] >= 2

    # ------------------------------------------------------------------
    # 6. RSI subplot -- separate pane
    # ------------------------------------------------------------------

    def test_13_add_rsi_subplot(self, chart: dict[str, Any]) -> None:
        r = _js(
            chart["label"],
            "(function() {" + _cid() + "_tvAddIndicator("
            "  {name: 'RSI', key: 'rsi', fullName: 'Relative Strength Index',"
            "   category: 'Momentum', defaultPeriod: 14},"
            "  cid"
            ");"
            "var rsiKey = Object.keys(_activeIndicators).filter("
            "  function(k) { return _activeIndicators[k].name === 'RSI'; }"
            ")[0];"
            "var info = rsiKey ? _activeIndicators[rsiKey] : null;"
            "pywry.result({"
            "  hasRSI: !!rsiKey,"
            "  isSubplot: info ? !!info.isSubplot : null,"
            "  paneIndex: info ? info.paneIndex : null,"
            "  period: info ? info.period : null,"
            "});"
            "})();",
        )
        assert r["hasRSI"]
        assert r["isSubplot"] is True, "RSI should be in a subplot pane"
        assert r["paneIndex"] is not None and r["paneIndex"] > 0
        assert r["period"] == 14

    def test_14_rsi_has_computed_values(self, chart: dict[str, Any]) -> None:
        r = _js(
            chart["label"],
            "(function() {" + _cid() + "var rsiKey = Object.keys(_activeIndicators).filter("
            "  function(k) { return _activeIndicators[k].name === 'RSI'; }"
            ")[0];"
            "var series = rsiKey ? entry.seriesMap[rsiKey] : null;"
            "var data = [];"
            "if (series && typeof series.data === 'function') data = series.data();"
            "var nonNull = 0;"
            "for (var i = 0; i < data.length; i++) {"
            "  if (data[i].value !== undefined && data[i].value !== null) nonNull++;"
            "}"
            "pywry.result({total: data.length, nonNull: nonNull});"
            "})();",
        )
        assert r["nonNull"] > 0

    def test_15_change_rsi_period(self, chart: dict[str, Any]) -> None:
        r = _js(
            chart["label"],
            "(function() {"
            "var rsiKey = Object.keys(_activeIndicators).filter("
            "  function(k) { return _activeIndicators[k].name === 'RSI'; }"
            ")[0];"
            "_tvApplyIndicatorSettings(rsiKey, {period: 7});"
            "var info = _activeIndicators[rsiKey];"
            "pywry.result({period: info ? info.period : null});"
            "})();",
        )
        assert r["period"] == 7

    # ------------------------------------------------------------------
    # 7. Bollinger Bands -- grouped multi-series indicator
    # ------------------------------------------------------------------

    def test_16_add_bollinger_bands(self, chart: dict[str, Any]) -> None:
        """BB adds 3 grouped series (upper / middle / lower)."""
        r = _js(
            chart["label"],
            "(function() {" + _cid() + "var beforeKeys = Object.keys(_activeIndicators);"
            "_tvAddIndicator("
            "  {name: 'Bollinger Bands', fullName: 'Bollinger Bands',"
            "   category: 'Volatility', defaultPeriod: 20},"
            "  cid"
            ");"
            "var afterKeys = Object.keys(_activeIndicators);"
            "var newKeys = afterKeys.filter(function(k) {"
            "  return beforeKeys.indexOf(k) === -1;"
            "});"
            "var groups = {};"
            "for (var i = 0; i < newKeys.length; i++) {"
            "  var g = _activeIndicators[newKeys[i]].group || 'none';"
            "  groups[g] = (groups[g] || 0) + 1;"
            "}"
            "pywry.result({newCount: newKeys.length, groups: groups});"
            "})();",
        )
        assert r["newCount"] >= 3, f"BB should add 3+ series, got {r['newCount']}"
        group_counts = list(r["groups"].values())
        assert any(c >= 3 for c in group_counts)

    def test_17_indicator_count_correct(self, chart: dict[str, Any]) -> None:
        """MA(SMA) + MA(EMA) + RSI + BB(3) = at least 6 indicator series."""
        r = _js(
            chart["label"],
            "(function() {pywry.result({count: Object.keys(_activeIndicators).length});})();",
        )
        assert r["count"] >= 6

    # ------------------------------------------------------------------
    # 8. Overlay vs pane
    # ------------------------------------------------------------------

    def test_18_sma_overlay_rsi_subplot(self, chart: dict[str, Any]) -> None:
        r = _js(
            chart["label"],
            "(function() {"
            "var smaKey = Object.keys(_activeIndicators).filter("
            "  function(k) {"
            "    var ai = _activeIndicators[k];"
            "    return ai.type === 'moving-average-ex' && ai.method === 'SMA';"
            "  }"
            ")[0];"
            "var rsiKey = Object.keys(_activeIndicators).filter("
            "  function(k) { return _activeIndicators[k].name === 'RSI'; }"
            ")[0];"
            "var sma = smaKey ? _activeIndicators[smaKey] : null;"
            "var rsi = rsiKey ? _activeIndicators[rsiKey] : null;"
            "pywry.result({"
            "  smaSubplot: sma ? !!sma.isSubplot : null,"
            "  smaPane: sma ? (sma.paneIndex || 0) : null,"
            "  rsiSubplot: rsi ? !!rsi.isSubplot : null,"
            "  rsiPane: rsi ? rsi.paneIndex : null,"
            "});"
            "})();",
        )
        assert r["smaSubplot"] is False
        assert r["rsiSubplot"] is True
        assert (r["rsiPane"] or 0) > (r["smaPane"] or 0)

    # ------------------------------------------------------------------
    # 9. Pane swap
    # ------------------------------------------------------------------

    def test_19_swap_rsi_pane(self, chart: dict[str, Any]) -> None:
        """Swap RSI pane up -- pane index decreases."""
        r = _js(
            chart["label"],
            "(function() {" + _cid() + "var rsiKey = Object.keys(_activeIndicators).filter("
            "  function(k) { return _activeIndicators[k].name === 'RSI'; }"
            ")[0];"
            "var before = _activeIndicators[rsiKey]"
            "  ? _activeIndicators[rsiKey].paneIndex : -1;"
            "_tvSwapIndicatorPane(cid, rsiKey, -1);"
            "var after = _activeIndicators[rsiKey]"
            "  ? _activeIndicators[rsiKey].paneIndex : -1;"
            "pywry.result({before: before, after: after,"
            "  moved: after < before});"
            "})();",
        )
        assert r["moved"] is True, (
            f"Pane swap up should decrease index: {r['before']} -> {r['after']}"
        )

    # ------------------------------------------------------------------
    # 10. Drawing tools -- draw shapes, verify persistence
    # ------------------------------------------------------------------

    def test_20_draw_hline(self, chart: dict[str, Any]) -> None:
        # Drive the real drawing pipeline: select the tool (which flips
        # the overlay canvas into ``pointer-events: auto``), dispatch a
        # synthetic click, and let the click handler compute the price,
        # push the drawing, call ``_tvRenderDrawings``, and create the
        # native ``priceLine``.  No direct ``ds.drawings.push`` here.
        r = _js(
            chart["label"],
            "(function() {" + _cid() + _draw_hline_script() + "})();",
        )
        assert r.get("error") is None, r.get("error")
        assert r["count"] >= 1
        assert r["type"] == "hline"
        assert r["rendered"] is True, "Canvas had no drawing pixels after click"

    def test_21_draw_trendline(self, chart: dict[str, Any]) -> None:
        # Two-point tool: first click sets p1, second click commits.
        r = _js(
            chart["label"],
            "(function() {" + _cid() + _draw_two_point_script("trendline") + "})();",
        )
        assert r.get("error") is None, r.get("error")
        assert r["count"] >= 2
        assert r["type"] == "trendline"

    def test_22_draw_rect(self, chart: dict[str, Any]) -> None:
        r = _js(
            chart["label"],
            "(function() {" + _cid() + _draw_two_point_script("rect") + "})();",
        )
        assert r.get("error") is None, r.get("error")
        assert r["count"] >= 3
        assert r["type"] == "rect"

    def test_23_draw_text_annotation(self, chart: dict[str, Any]) -> None:
        # ``text`` is a single-click tool.
        r = _js(
            chart["label"],
            "(function() {" + _cid() + _draw_single_point_script("text") + "})();",
        )
        assert r.get("error") is None, r.get("error")
        assert r["count"] >= 4
        assert r["type"] == "text"

    def test_24_draw_fibonacci(self, chart: dict[str, Any]) -> None:
        r = _js(
            chart["label"],
            "(function() {" + _cid() + _draw_two_point_script("fibonacci") + "})();",
        )
        assert r.get("error") is None, r.get("error")
        assert r["count"] >= 5
        assert r["type"] == "fibonacci"

    def test_25_drawing_count_correct(self, chart: dict[str, Any]) -> None:
        """hline + trendline + rect + text + fib = 5."""
        r = _js(
            chart["label"],
            "(function() {" + _cid() + "var ds = window.__PYWRY_DRAWINGS__[cid];"
            "var types = [];"
            "for (var i = 0; i < ds.drawings.length; i++)"
            "  types.push(ds.drawings[i].type);"
            "pywry.result({count: ds.drawings.length, types: types});"
            "})();",
        )
        assert r["count"] == 5, f"Expected 5, got {r['count']}: {r['types']}"
        for t in ["hline", "trendline", "rect", "text", "fibonacci"]:
            assert t in r["types"], f"Missing drawing type: {t}"

    # ------------------------------------------------------------------
    # 11. Drawing settings -- change properties
    # ------------------------------------------------------------------

    def test_26_change_hline_color(self, chart: dict[str, Any]) -> None:
        r = _js(
            chart["label"],
            "(function() {" + _cid() + "var ds = window.__PYWRY_DRAWINGS__[cid];"
            "var hline = null;"
            "for (var i = 0; i < ds.drawings.length; i++)"
            "  if (ds.drawings[i].type === 'hline') { hline = ds.drawings[i]; break; }"
            "if (!hline) { pywry.result({error:'no hline'}); return; }"
            "hline.color = '#00ff00';"
            "hline.lineWidth = 3;"
            "pywry.result({color: hline.color, lineWidth: hline.lineWidth});"
            "})();",
        )
        assert r.get("error") is None, r.get("error")
        assert r["color"] == "#00ff00"
        assert r["lineWidth"] == 3

    def test_27_change_trendline_style(self, chart: dict[str, Any]) -> None:
        r = _js(
            chart["label"],
            "(function() {" + _cid() + "var ds = window.__PYWRY_DRAWINGS__[cid];"
            "var tl = null;"
            "for (var i = 0; i < ds.drawings.length; i++)"
            "  if (ds.drawings[i].type === 'trendline') { tl = ds.drawings[i]; break; }"
            "if (!tl) { pywry.result({error:'no trendline'}); return; }"
            "tl.lineStyle = 1;"
            "tl.color = '#f23645';"
            "pywry.result({lineStyle: tl.lineStyle, color: tl.color});"
            "})();",
        )
        assert r.get("error") is None
        assert r["lineStyle"] == 1
        assert r["color"] == "#f23645"

    # ------------------------------------------------------------------
    # 12. Drawing visibility and lock
    # ------------------------------------------------------------------

    def test_28_drawing_visibility_toggle(self, chart: dict[str, Any]) -> None:
        r = _js(
            chart["label"],
            "(function() {" + _cid() + "var ds = window.__PYWRY_DRAWINGS__[cid];"
            "if (!ds || !ds.canvas) {"
            "  pywry.result({error:'no canvas'}); return;"
            "}"
            "window.pywry._trigger('tvchart:tool-visibility', {});"
            "var hidden = ds.canvas.style.display === 'none';"
            "window.pywry._trigger('tvchart:tool-visibility', {});"
            "var visible = ds.canvas.style.display !== 'none';"
            "pywry.result({hidden: hidden, visible: visible});"
            "})();",
        )
        assert r.get("error") is None, r.get("error")
        assert r["hidden"] is True
        assert r["visible"] is True

    def test_29_drawing_lock_toggle(self, chart: dict[str, Any]) -> None:
        r = _js(
            chart["label"],
            "(function() {" + _cid() + "var ds = window.__PYWRY_DRAWINGS__[cid];"
            "var before = !!ds._locked;"
            "window.pywry._trigger('tvchart:tool-lock', {});"
            "var locked = !!ds._locked;"
            "window.pywry._trigger('tvchart:tool-lock', {});"
            "var unlocked = !!ds._locked;"
            "pywry.result({before: before, locked: locked, unlocked: unlocked});"
            "})();",
        )
        assert r["before"] is False
        assert r["locked"] is True
        assert r["unlocked"] is False

    # ------------------------------------------------------------------
    # 13. Undo / redo
    # ------------------------------------------------------------------

    def test_30_undo_removes_last_drawing(self, chart: dict[str, Any]) -> None:
        r = _js(
            chart["label"],
            "(function() {" + _cid() + "var ds = window.__PYWRY_DRAWINGS__[cid];"
            "var before = ds.drawings.length;"
            "window.pywry._trigger('tvchart:undo', {});"
            "var after = ds.drawings.length;"
            "pywry.result({before: before, after: after});"
            "})();",
        )
        assert r["after"] == r["before"] - 1

    def test_31_redo_restores_drawing(self, chart: dict[str, Any]) -> None:
        r = _js(
            chart["label"],
            "(function() {" + _cid() + "var ds = window.__PYWRY_DRAWINGS__[cid];"
            "var before = ds.drawings.length;"
            "window.pywry._trigger('tvchart:redo', {});"
            "var after = ds.drawings.length;"
            "var lastType = ds.drawings.length > 0"
            "  ? ds.drawings[ds.drawings.length-1].type : null;"
            "pywry.result({before: before, after: after, lastType: lastType});"
            "})();",
        )
        assert r["after"] == r["before"] + 1
        assert r["lastType"] == "fibonacci"

    # ------------------------------------------------------------------
    # 14. Eraser
    # ------------------------------------------------------------------

    def test_32_eraser_clears_all(self, chart: dict[str, Any]) -> None:
        r = _js(
            chart["label"],
            "(function() {" + _cid() + "var ds = window.__PYWRY_DRAWINGS__[cid];"
            "var before = ds.drawings.length;"
            "window.pywry._trigger('tvchart:tool-eraser', {});"
            "var after = ds.drawings.length;"
            "pywry.result({before: before, after: after});"
            "})();",
        )
        assert r["before"] > 0
        assert r["after"] == 0

    # ------------------------------------------------------------------
    # 15. Scale modes
    # ------------------------------------------------------------------

    def test_33_log_scale_on_off(self, chart: dict[str, Any]) -> None:
        r = _js(
            chart["label"],
            "(function() {" + _cid() + "window.pywry._trigger('tvchart:log-scale', {value: true});"
            "var logOn = entry._chartPrefs ? entry._chartPrefs.logScale : null;"
            "window.pywry._trigger('tvchart:log-scale', {value: false});"
            "var logOff = entry._chartPrefs ? entry._chartPrefs.logScale : null;"
            "pywry.result({logOn: logOn, logOff: logOff});"
            "})();",
        )
        assert r["logOn"] is True
        assert r["logOff"] is False

    def test_34_auto_scale_toggle(self, chart: dict[str, Any]) -> None:
        r = _js(
            chart["label"],
            "(function() {"
            + _cid()
            + "window.pywry._trigger('tvchart:auto-scale', {value: false});"
            "var off = entry._chartPrefs ? entry._chartPrefs.autoScale : null;"
            "window.pywry._trigger('tvchart:auto-scale', {value: true});"
            "var on = entry._chartPrefs ? entry._chartPrefs.autoScale : null;"
            "pywry.result({off: off, on: on});"
            "})();",
        )
        assert r["off"] is False
        assert r["on"] is True

    # ------------------------------------------------------------------
    # 16. Time scale
    # ------------------------------------------------------------------

    def test_35_time_scale_fit_content(self, chart: dict[str, Any]) -> None:
        r = _js(
            chart["label"],
            "(function() {" + _cid() + "var ts = entry.chart.timeScale();"
            "ts.setVisibleLogicalRange({from: 5, to: 10});"
            "setTimeout(function() {"
            "  var narrow = ts.getVisibleLogicalRange();"
            "  var narrowSpan = narrow ? Math.round(narrow.to - narrow.from) : 0;"
            "  window.pywry._trigger('tvchart:time-scale', {"
            "    chartId: cid, fitContent: true"
            "  });"
            "  setTimeout(function() {"
            "    var fit = ts.getVisibleLogicalRange();"
            "    var fitSpan = fit ? Math.round(fit.to - fit.from) : 0;"
            "    pywry.result({"
            "      narrowSpan: narrowSpan, fitSpan: fitSpan,"
            "      fitWider: fitSpan > narrowSpan,"
            "    });"
            "  }, 200);"
            "}, 200);"
            "})();",
        )
        assert r["fitWider"] is True

    # ------------------------------------------------------------------
    # 17. Markers and price lines
    # ------------------------------------------------------------------

    def test_36_add_markers_sorted(self, chart: dict[str, Any]) -> None:
        r = _js(
            chart["label"],
            "(function() {" + _cid() + "try {"
            "  window.pywry._trigger('tvchart:add-markers', {"
            "    chartId: cid, seriesId: 'main',"
            "    markers: ["
            "      {time:1700432000,position:'belowBar',color:'#0f0',"
            "       shape:'arrowUp',text:'Buy'},"
            "      {time:1700172800,position:'aboveBar',color:'#f00',"
            "       shape:'arrowDown',text:'Sell'},"
            "    ]"
            "  });"
            "  pywry.result({ok: true});"
            "} catch(e) { pywry.result({ok: false, error: e.message}); }"
            "})();",
        )
        assert r["ok"] is True, r.get("error")

    def test_37_add_price_line(self, chart: dict[str, Any]) -> None:
        r = _js(
            chart["label"],
            "(function() {" + _cid() + "var error = null;"
            "try {"
            "  window.pywry._trigger('tvchart:add-price-line', {"
            "    chartId:cid,seriesId:'main',"
            "    price:50000.0,color:'#2196f3',title:'Target',"
            "  });"
            "} catch(e) { error = e.message; }"
            "pywry.result({error: error});"
            "})();",
        )
        assert r["error"] is None

    # ------------------------------------------------------------------
    # 18. Legend
    # ------------------------------------------------------------------

    def test_38_legend_present(self, chart: dict[str, Any]) -> None:
        r = _js(
            chart["label"],
            "(function() {" + _cid() + "pywry.result({"
            "  hasContainer: !!document.querySelector('.tvchart-legend-container'),"
            "  hasRow: !!document.querySelector('.tvchart-legend-row'),"
            "  hasUiState: !!entry._legendUiState,"
            "});"
            "})();",
        )
        assert r["hasContainer"]
        assert r["hasRow"]

    # ------------------------------------------------------------------
    # 19. Settings modal
    # ------------------------------------------------------------------

    def test_39_settings_modal_opens(self, chart: dict[str, Any]) -> None:
        r = _js(
            chart["label"],
            "(function() {" + _cid() + "var lockedBefore = !!entry._interactionLocked;"
            "window.pywry._trigger('tvchart:show-settings', {chartId: cid});"
            "setTimeout(function() {"
            "  var lockedAfter = !!entry._interactionLocked;"
            "  var hasOverlay = !!document.querySelector("
            "    '.tv-chart-settings-overlay, .tv-settings-overlay'"
            "  );"
            "  var overlay = document.querySelector("
            "    '.tv-chart-settings-overlay, .tv-settings-overlay'"
            "  );"
            "  if (overlay) overlay.click();"
            "  setTimeout(function() {"
            "    pywry.result({"
            "      lockedBefore: lockedBefore,"
            "      lockedAfter: lockedAfter,"
            "      hasOverlay: hasOverlay,"
            "    });"
            "  }, 200);"
            "}, 300);"
            "})();",
        )
        assert r["lockedBefore"] is False
        assert r["lockedAfter"] is True
        assert r["hasOverlay"] is True

    # ------------------------------------------------------------------
    # 20. Theme switch -- dark <-> light with visual verification
    # ------------------------------------------------------------------

    def test_40_switch_to_light_theme(self, chart: dict[str, Any]) -> None:
        """Switch to light and verify chart bg is light."""
        r = _js(
            chart["label"],
            "(function() {"
            "window.pywry._trigger('pywry:update-theme', {theme: 'light'});"
            "setTimeout(function() {" + _cid() + "  var opts = entry.chart.options();"
            "  var cssBg = getComputedStyle(document.documentElement)"
            "    .getPropertyValue('--pywry-tvchart-bg').trim();"
            "  pywry.result({"
            "    theme: entry.theme,"
            "    chartBg: opts.layout.background.color,"
            "    cssBg: cssBg,"
            "    htmlClass: document.documentElement.className,"
            "  });"
            "}, 500);"
            "})();",
        )
        assert r["theme"] == "light"
        assert r["cssBg"] == "#ffffff"

    def test_41_light_theme_text_color(self, chart: dict[str, Any]) -> None:
        r = _js(
            chart["label"],
            "(function() {" + _cid() + "var opts = entry.chart.options();"
            "pywry.result({"
            "  textColor: opts.layout.textColor,"
            "  cssText: getComputedStyle(document.documentElement)"
            "    .getPropertyValue('--pywry-tvchart-text').trim(),"
            "});"
            "})();",
        )
        assert r["textColor"] == r["cssText"]
        assert r["textColor"] != "#d1d4dc"

    def test_42_switch_back_to_dark(self, chart: dict[str, Any]) -> None:
        r = _js(
            chart["label"],
            "(function() {"
            "window.pywry._trigger('pywry:update-theme', {theme: 'dark'});"
            "setTimeout(function() {" + _cid() + "  pywry.result({theme: entry.theme});"
            "}, 500);"
            "})();",
        )
        assert r["theme"] == "dark"

    # ------------------------------------------------------------------
    # 21. Streaming
    # ------------------------------------------------------------------

    def test_43_stream_appends_new_bar(self, chart: dict[str, Any]) -> None:
        initial = _full_state(chart["label"])["barCount"]
        future_ts = str(2000000000)
        r = _js(
            chart["label"],
            "(function() {"
            "  window.pywry._trigger('tvchart:stream', {"
            "    bar:{time:" + future_ts + ",open:50000,high:51000,low:49000,close:50500},"
            "    seriesId:'main'"
            "  });"
            "  setTimeout(function() {"
            "    var e = window.__PYWRY_TVCHARTS__["
            "      Object.keys(window.__PYWRY_TVCHARTS__)[0]];"
            "    var r = e._seriesRawData['main'];"
            "    pywry.result({barCount: r ? r.length : -1});"
            "  }, 500);"
            "})();",
        )
        assert r["barCount"] == initial + 1

    def test_44_stream_updates_in_place(self, chart: dict[str, Any]) -> None:
        count = _full_state(chart["label"])["barCount"]
        future_ts = str(2000000000)
        r = _js(
            chart["label"],
            "(function() {"
            "  window.pywry._trigger('tvchart:stream', {"
            "    bar:{time:" + future_ts + ",open:50000,high:55000,low:48000,close:54000},"
            "    seriesId:'main'"
            "  });"
            "  setTimeout(function() {"
            "    var e = window.__PYWRY_TVCHARTS__["
            "      Object.keys(window.__PYWRY_TVCHARTS__)[0]];"
            "    var r = e._seriesRawData['main'];"
            "    var last = r[r.length-1];"
            "    pywry.result({barCount: r.length, lastHigh: last.high});"
            "  }, 500);"
            "})();",
        )
        assert r["barCount"] == count
        assert r["lastHigh"] == 55000

    # ------------------------------------------------------------------
    # 22. State export
    # ------------------------------------------------------------------

    def test_45_state_export_has_content(self, chart: dict[str, Any]) -> None:
        r = _js(
            chart["label"],
            "(function() {"
            "var captured = null;"
            "var orig = window.pywry.emit;"
            "window.pywry.emit = function(t, d) {"
            "  if (t === 'tvchart:state-response') captured = d;"
            "  return orig.apply(this, arguments);"
            "};"
            "window.pywry._trigger('tvchart:request-state', {});"
            "setTimeout(function() {"
            "  window.pywry.emit = orig;"
            "  pywry.result({"
            "    captured: !!captured,"
            "    hasChartId: captured ? !!captured.chartId : false,"
            "    keys: captured ? Object.keys(captured) : [],"
            "  });"
            "}, 500);"
            "})();",
        )
        assert r["captured"], "State response was not emitted"
        assert r["hasChartId"], "State response missing chartId"

    # ------------------------------------------------------------------
    # 23. Remove indicators
    # ------------------------------------------------------------------

    def test_46_remove_sma(self, chart: dict[str, Any]) -> None:
        r = _js(
            chart["label"],
            "(function() {"
            "var before = Object.keys(_activeIndicators).length;"
            "var smaKey = Object.keys(_activeIndicators).filter("
            "  function(k) {"
            "    var ai = _activeIndicators[k];"
            "    return ai.type === 'moving-average-ex' && ai.method === 'SMA';"
            "  }"
            ")[0];"
            "if (smaKey) _tvRemoveIndicator(smaKey);"
            "var after = Object.keys(_activeIndicators).length;"
            "pywry.result({before: before, after: after, removed: !!smaKey});"
            "})();",
        )
        assert r["removed"] is True
        assert r["after"] < r["before"]

    def test_47_remove_all_indicators(self, chart: dict[str, Any]) -> None:
        r = _js(
            chart["label"],
            "(function() {"
            "var keys = Object.keys(_activeIndicators).slice();"
            "for (var i = 0; i < keys.length; i++)"
            "  _tvRemoveIndicator(keys[i]);"
            "var remaining = Object.keys(_activeIndicators).length;"
            "pywry.result({removed: keys.length, remaining: remaining});"
            "})();",
        )
        assert r["remaining"] == 0

    # ------------------------------------------------------------------
    # 24. Destroy
    # ------------------------------------------------------------------

    def test_48_destroy_cleans_up(self, chart: dict[str, Any]) -> None:
        r = _js(
            chart["label"],
            "(function() {" + _cid() + "window.pywry._trigger('tvchart:destroy', {chartId: cid});"
            "setTimeout(function() {"
            "  pywry.result({destroyed: !window.__PYWRY_TVCHARTS__[cid]});"
            "}, 500);"
            "})();",
        )
        assert r["destroyed"] is True


# ============================================================================
# Light theme -- separate chart verifying visual correctness
# ============================================================================


@pytest.fixture(scope="class")
def light_chart(request) -> dict[str, Any]:
    """Class-scoped UDF chart with LIGHT theme."""
    from pywry.app import PyWry
    from pywry.models import ThemeMode
    from pywry.tvchart.udf import UDFAdapter

    _stop_runtime_sync()
    _clear_registries()

    if request.cls is not None:
        request.cls._pywry_class_scoped = True

    app = PyWry(theme=ThemeMode.LIGHT)
    udf = UDFAdapter(UDF_URL, poll_interval=60)

    waiter = ReadyWaiter(timeout=WINDOW_TIMEOUT)

    widget = udf.connect(
        app,
        symbol=UDF_SYMBOL,
        resolution=UDF_RESOLUTION,
        title="TradingView E2E -- Light",
        width=1200,
        height=700,
        callbacks={"pywry:ready": waiter.on_ready},
    )
    label = widget.label if hasattr(widget, "label") else str(widget)

    if not waiter.wait():
        ping = wait_for_result(
            label,
            "pywry.result({ state: document.readyState, hasBody: !!document.body });",
            timeout=SHORT_TIMEOUT,
            retries=1,
        )
        if not (isinstance(ping, dict) and ping.get("hasBody")):
            udf.close()
            app.close()
            _stop_runtime_sync()
            _clear_registries()
            pytest.skip(
                f"Light chart '{label}' did not become ready within {WINDOW_TIMEOUT}s"
                " (native runtime unavailable)"
            )

    time.sleep(CHART_RENDER_WAIT)

    yield {"app": app, "udf": udf, "label": label}

    udf.close()
    app.close()
    _stop_runtime_sync()
    _clear_registries()


class TestTVChartLightTheme:
    """Verify light theme renders with correct visual colors."""

    def test_01_light_bg_is_white(self, light_chart: dict[str, Any]) -> None:
        r = _js(
            light_chart["label"],
            "(function() {" + _cid() + "var opts = entry.chart.options();"
            "var cssBg = getComputedStyle(document.documentElement)"
            "  .getPropertyValue('--pywry-tvchart-bg').trim();"
            "pywry.result({"
            "  theme: entry.theme,"
            "  chartBg: opts.layout.background.color,"
            "  cssBg: cssBg,"
            "  htmlClass: document.documentElement.className,"
            "});"
            "})();",
        )
        assert r["theme"] == "light"
        assert r["cssBg"] == "#ffffff", f"CSS bg should be #ffffff, got {r['cssBg']}"
        assert "pywry-theme-light" in r["htmlClass"]
        # With the fix, chart options bg must NOT be dark
        bg = (r.get("chartBg") or "").lower()
        assert "13, 17, 23" not in bg, f"Chart bg still has hardcoded dark color: {bg}"

    def test_02_light_text_is_dark(self, light_chart: dict[str, Any]) -> None:
        r = _js(
            light_chart["label"],
            "(function() {" + _cid() + "pywry.result({"
            "  cssText: getComputedStyle(document.documentElement)"
            "    .getPropertyValue('--pywry-tvchart-text').trim(),"
            "});"
            "})();",
        )
        # CSS var should resolve to a dark text colour for light theme
        assert r["cssText"] != "#d1d4dc", (
            f"Light theme text CSS should not be dark-theme default, got {r['cssText']}"
        )

    def test_03_light_grid_colors(self, light_chart: dict[str, Any]) -> None:
        r = _js(
            light_chart["label"],
            "(function() {" + _cid() + "pywry.result({"
            "  cssVert: getComputedStyle(document.documentElement)"
            "    .getPropertyValue('--pywry-tvchart-grid-vert').trim(),"
            "});"
            "})();",
        )
        # Light theme grid should NOT be the dark-theme default
        assert "255, 255, 255" not in (r["cssVert"] or "")

    def test_04_light_chart_has_data(self, light_chart: dict[str, Any]) -> None:
        s = _full_state(light_chart["label"])
        assert s["barCount"] > 0
        assert "main" in s["seriesIds"]


# ============================================================================
# Storage -- server backend
# ============================================================================


@pytest.fixture(scope="class")
def server_storage_chart(request) -> dict[str, Any]:
    """Class-scoped UDF chart with server storage backend."""
    from pywry.app import PyWry
    from pywry.models import ThemeMode
    from pywry.tvchart.udf import UDFAdapter

    _stop_runtime_sync()
    _clear_registries()

    if request.cls is not None:
        request.cls._pywry_class_scoped = True

    app = PyWry(theme=ThemeMode.DARK)
    udf = UDFAdapter(UDF_URL, poll_interval=60)

    waiter = ReadyWaiter(timeout=WINDOW_TIMEOUT)

    widget = udf.connect(
        app,
        symbol=UDF_SYMBOL,
        resolution=UDF_RESOLUTION,
        title="TradingView E2E -- Server Storage",
        width=1200,
        height=700,
        callbacks={"pywry:ready": waiter.on_ready},
        storage={"backend": "server"},
    )
    label = widget.label if hasattr(widget, "label") else str(widget)

    if not waiter.wait():
        ping = wait_for_result(
            label,
            "pywry.result({ state: document.readyState, hasBody: !!document.body });",
            timeout=SHORT_TIMEOUT,
            retries=1,
        )
        if not (isinstance(ping, dict) and ping.get("hasBody")):
            udf.close()
            app.close()
            _stop_runtime_sync()
            _clear_registries()
            pytest.skip(
                f"Storage chart '{label}' did not become ready within {WINDOW_TIMEOUT}s"
                " (native runtime unavailable)"
            )

    time.sleep(CHART_RENDER_WAIT)

    yield {"app": app, "udf": udf, "label": label}

    udf.close()
    app.close()
    _stop_runtime_sync()
    _clear_registries()


class TestTVChartStorage:
    """Storage adapter: localStorage + server-backend event pipeline."""

    def test_01_set_and_get(self, server_storage_chart: dict[str, Any]) -> None:
        r = _js(
            server_storage_chart["label"],
            "(function() {" + _cid() + "var adapter = _tvStorageAdapter(cid);"
            "adapter.setItem('__test_key', 'test_value_123');"
            "var got = adapter.getItem('__test_key');"
            "pywry.result({got: got});"
            "})();",
        )
        assert r["got"] == "test_value_123"

    def test_02_remove(self, server_storage_chart: dict[str, Any]) -> None:
        r = _js(
            server_storage_chart["label"],
            "(function() {" + _cid() + "var adapter = _tvStorageAdapter(cid);"
            "adapter.setItem('__rm', 'gone');"
            "adapter.removeItem('__rm');"
            "pywry.result({got: adapter.getItem('__rm')});"
            "})();",
        )
        assert r["got"] is None

    def test_03_server_backend_configured(self, server_storage_chart: dict[str, Any]) -> None:
        r = _js(
            server_storage_chart["label"],
            "(function() {" + _cid() + "var cfg = _tvStorageConfig(cid);"
            "pywry.result({backend: cfg.backend});"
            "})();",
        )
        assert r["backend"] == "server"

    def test_04_server_set_emits_event(self, server_storage_chart: dict[str, Any]) -> None:
        r = _js(
            server_storage_chart["label"],
            "(function() {"
            "var emitted = [];"
            "var orig = window.pywry.emit;"
            "window.pywry.emit = function(t, d) {"
            "  if (t === 'tvchart:storage-set') emitted.push(d);"
            "  return orig.apply(this, arguments);"
            "};" + _cid() + "var adapter = _tvStorageAdapter(cid);"
            "adapter.setItem('__emit_test', 'emit_value');"
            "window.pywry.emit = orig;"
            "pywry.result({"
            "  count: emitted.length,"
            "  key: emitted.length > 0 ? emitted[0].key : null,"
            "  value: emitted.length > 0 ? emitted[0].value : null,"
            "});"
            "})();",
        )
        assert r["count"] >= 1
        assert r["key"] == "__emit_test"
        assert r["value"] == "emit_value"

    def test_05_server_remove_emits_event(self, server_storage_chart: dict[str, Any]) -> None:
        r = _js(
            server_storage_chart["label"],
            "(function() {"
            "var emitted = [];"
            "var orig = window.pywry.emit;"
            "window.pywry.emit = function(t, d) {"
            "  if (t === 'tvchart:storage-remove') emitted.push(d);"
            "  return orig.apply(this, arguments);"
            "};" + _cid() + "var adapter = _tvStorageAdapter(cid);"
            "adapter.setItem('__rm_emit', 'val');"
            "adapter.removeItem('__rm_emit');"
            "window.pywry.emit = orig;"
            "pywry.result({"
            "  count: emitted.length,"
            "  key: emitted.length > 0 ? emitted[0].key : null,"
            "});"
            "})();",
        )
        assert r["count"] >= 1
        assert r["key"] == "__rm_emit"


# ============================================================================
# Inline Mode (synthetic data, no UDF)
# ============================================================================

try:
    from pywry.inline import HAS_FASTAPI
except ImportError:
    HAS_FASTAPI = False


def _http_get(url: str, timeout: float = 5.0) -> str:
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


@pytest.mark.skipif(not HAS_FASTAPI, reason="FastAPI not installed")
class TestTVChartInline:
    """Inline rendering path."""

    @pytest.fixture(autouse=True)
    def _clean_inline_state(self):
        from pywry.config import clear_settings
        from pywry.inline import _state, stop_server

        for key in list(os.environ.keys()):
            if key.startswith("PYWRY_DEPLOY"):
                del os.environ[key]
        os.environ.pop("PYWRY_HEADLESS", None)
        stop_server()
        _state.widgets.clear()
        clear_settings()
        yield
        stop_server()
        _state.widgets.clear()
        clear_settings()
        for key in list(os.environ.keys()):
            if key.startswith("PYWRY_"):
                del os.environ[key]

    def test_01_widget_registered(self) -> None:
        from pywry.inline import InlineWidget, _state

        html = '<html><body><div id="tc" class="pywry-tvchart-container"></div></body></html>'
        widget = InlineWidget(html, browser_only=True)
        assert widget.widget_id in _state.widgets

    def test_02_serves_html(self) -> None:
        from pywry.inline import InlineWidget, _state

        html = '<html><body><div class="pywry-tvchart-container">tvchart-marker</div></body></html>'
        widget = InlineWidget(html, browser_only=True)
        time.sleep(0.5)
        port = _state.port
        assert port is not None, "Server did not start"
        url = f"http://127.0.0.1:{port}/widget/{widget.widget_id}"
        content = _http_get(url)
        assert "tvchart-marker" in content


# ============================================================================
# Browser Mode
# ============================================================================


def _wait_for_port_release(port: int, timeout: float = 5.0) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("127.0.0.1", port))
                return True
        except OSError:
            time.sleep(0.1)
    return False


@pytest.mark.skipif(not HAS_FASTAPI, reason="FastAPI not installed")
class TestTVChartBrowser:
    """Browser mode rendering path."""

    @pytest.fixture(autouse=True)
    def _clean_browser_state(self):
        from pywry.config import clear_settings
        from pywry.inline import _state, stop_server

        old_port = _state.port
        stop_server(timeout=5.0)
        _state.widgets.clear()
        clear_settings()
        if old_port is not None:
            _wait_for_port_release(old_port, timeout=3.0)
        yield
        old_port = _state.port
        stop_server(timeout=5.0)
        _state.widgets.clear()
        clear_settings()
        if old_port is not None:
            _wait_for_port_release(old_port)
        for key in list(os.environ.keys()):
            if key.startswith("PYWRY_"):
                del os.environ[key]

    def test_01_serves_tvchart_html(self) -> None:
        from pywry.inline import InlineWidget, _state

        html = (
            "<html><body>"
            '<div class="pywry-tvchart-container">'
            "browser-tvchart-content</div>"
            "</body></html>"
        )
        widget = InlineWidget(html, browser_only=True)
        time.sleep(0.5)
        port = _state.port
        assert port is not None
        url = f"http://127.0.0.1:{port}/widget/{widget.widget_id}"
        content = _http_get(url)
        assert "browser-tvchart-content" in content


# ============================================================================
# Redis Storage Backend
# ============================================================================


@pytest.mark.container
@pytest.mark.redis
class TestTVChartRedisStorage:
    """Redis chart store CRUD."""

    @pytest.fixture()
    def chart_store(self, redis_container: str):
        from pywry.state.redis import RedisChartStore

        prefix = f"test:tvchart:{time.monotonic_ns()}:"
        store = RedisChartStore(redis_url=redis_container, prefix=prefix)
        yield store

    def test_01_save_and_load(self, chart_store) -> None:
        from pywry.state.sync_helpers import run_async

        run_async(
            chart_store.save_layout(
                user_id="user1",
                layout_id="layout_a",
                name="My Layout",
                data_json='{"drawings": [], "indicators": []}',
                summary="Test layout",
            ),
            timeout=5.0,
        )
        data = run_async(chart_store.get_layout("user1", "layout_a"), timeout=5.0)
        assert data is not None
        assert "drawings" in data

    def test_02_list_layouts(self, chart_store) -> None:
        from pywry.state.sync_helpers import run_async

        for i in range(3):
            run_async(
                chart_store.save_layout(
                    user_id="user1",
                    layout_id=f"layout_{i}",
                    name=f"Layout {i}",
                    data_json=f'{{"index": {i}}}',
                ),
                timeout=5.0,
            )
            time.sleep(0.05)
        layouts = run_async(chart_store.list_layouts("user1"), timeout=5.0)
        assert len(layouts) == 3
        assert layouts[0]["name"] == "Layout 2"

    def test_03_delete_layout(self, chart_store) -> None:
        from pywry.state.sync_helpers import run_async

        run_async(
            chart_store.save_layout(
                user_id="user1",
                layout_id="to_delete",
                name="Delete Me",
                data_json="{}",
            ),
            timeout=5.0,
        )
        deleted = run_async(chart_store.delete_layout("user1", "to_delete"), timeout=5.0)
        assert deleted is True
        data = run_async(chart_store.get_layout("user1", "to_delete"), timeout=5.0)
        assert data is None

    def test_04_settings_template(self, chart_store) -> None:
        from pywry.state.sync_helpers import run_async

        tpl = '{"background": "#1a1a2e", "gridLines": false}'
        run_async(chart_store.save_settings_template("user1", tpl), timeout=5.0)
        loaded = run_async(chart_store.get_settings_template("user1"), timeout=5.0)
        assert loaded is not None
        assert "background" in loaded


# ============================================================================
# RBAC Storage Scoping
# ============================================================================


@pytest.mark.container
@pytest.mark.redis
class TestTVChartRBACStorage:
    """User-scoped layout isolation."""

    @pytest.fixture()
    def chart_store(self, redis_container: str):
        from pywry.state.redis import RedisChartStore

        prefix = f"test:rbac:{time.monotonic_ns()}:"
        store = RedisChartStore(redis_url=redis_container, prefix=prefix)
        yield store

    def test_01_user_scoping(self, chart_store) -> None:
        from pywry.state.sync_helpers import run_async

        run_async(
            chart_store.save_layout(
                user_id="alice",
                layout_id="private",
                name="Alice Layout",
                data_json='{"owner": "alice"}',
            ),
            timeout=5.0,
        )
        alice = run_async(chart_store.list_layouts("alice"), timeout=5.0)
        assert len(alice) == 1
        bob = run_async(chart_store.list_layouts("bob"), timeout=5.0)
        assert len(bob) == 0
        data = run_async(chart_store.get_layout("bob", "private"), timeout=5.0)
        assert data is None

    def test_02_admin_full_access(self, chart_store) -> None:
        from pywry.state.sync_helpers import run_async

        run_async(
            chart_store.save_layout(
                user_id="admin",
                layout_id="admin_layout",
                name="Admin Layout",
                data_json='{"admin": true}',
            ),
            timeout=5.0,
        )
        data = run_async(chart_store.get_layout("admin", "admin_layout"), timeout=5.0)
        assert data is not None
        deleted = run_async(chart_store.delete_layout("admin", "admin_layout"), timeout=5.0)
        assert deleted is True
        after = run_async(chart_store.list_layouts("admin"), timeout=5.0)
        assert len(after) == 0

    def test_03_settings_per_user(self, chart_store) -> None:
        from pywry.state.sync_helpers import run_async

        run_async(
            chart_store.save_settings_template("user_x", '{"theme": "custom_x"}'),
            timeout=5.0,
        )
        run_async(
            chart_store.save_settings_template("user_y", '{"theme": "custom_y"}'),
            timeout=5.0,
        )
        tpl_x = run_async(chart_store.get_settings_template("user_x"), timeout=5.0)
        tpl_y = run_async(chart_store.get_settings_template("user_y"), timeout=5.0)
        assert tpl_x is not None and "custom_x" in tpl_x
        assert tpl_y is not None and "custom_y" in tpl_y
