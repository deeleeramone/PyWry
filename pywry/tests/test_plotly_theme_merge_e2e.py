"""E2E tests for Plotly theme merge in REAL PyWry windows.

These tests launch actual GUI windows, render Plotly charts with
template_dark / template_light overrides, and read back the RENDERED
chart colors from the live DOM to prove the deep-merge actually works
in the frontend.

What this proves that unit tests cannot:
- The full pipeline from PlotlyConfig → show_plotly → WebView2 → Plotly.js → DOM
- __pywryDeepMerge and __pywryMergeThemeTemplate execute correctly in a real browser
- User template overrides are actually applied to the rendered chart
- Base theme values survive where the user didn't override
"""

# pylint: disable=unsubscriptable-object

from __future__ import annotations

import time

from pywry.plotly_config import PlotlyConfig
from tests.conftest import (
    show_plotly_and_wait_ready,
    wait_for_result,
)


# Custom colors that are unmistakably NOT from any built-in Plotly template.
# If these show up in the rendered chart, the merge definitely worked.
CUSTOM_DARK_PAPER_BG = "#1a1a2e"
CUSTOM_DARK_PLOT_BG = "#16213e"
CUSTOM_DARK_FONT_COLOR = "#e0e0e0"
CUSTOM_LIGHT_PAPER_BG = "#fafafa"
CUSTOM_LIGHT_PLOT_BG = "#eaeaea"
CUSTOM_LIGHT_FONT_COLOR = "#222222"


def _read_chart_template_state(label: str) -> dict | None:
    """Read the rendered Plotly chart's template state from the live DOM.

    Returns a dict with:
    - hasMergeFunction: bool - whether __pywryMergeThemeTemplate is available
    - hasDeepMerge: bool - whether __pywryDeepMerge is available
    - hasPlotly: bool - whether a Plotly chart div exists
    - svgCount: int - number of SVG elements (chart is drawn if > 0)
    - paperBg: str - the actual rendered paper_bgcolor
    - plotBg: str - the actual rendered plot_bgcolor
    - fontColor: str - the actual rendered font color
    - fontFamily: str - the rendered font family (if set)
    - storedDark: bool - whether __pywry_user_template_dark__ is on the div
    - storedLight: bool - whether __pywry_user_template_light__ is on the div
    - storedLegacy: bool - whether __pywry_user_template__ is on the div
    - baseDarkPaperBg: str - the base plotly_dark template's paper_bgcolor
    - baseLightPaperBg: str - the base plotly_white template's paper_bgcolor
    """
    return wait_for_result(
        label,
        """
        (function() {
            var plotDiv = document.querySelector('.js-plotly-plot')
                       || document.querySelector('[data-pywry-chart]');
            var templates = window.PYWRY_PLOTLY_TEMPLATES || {};

            pywry.result({
                hasMergeFunction: typeof window.__pywryMergeThemeTemplate === 'function',
                hasDeepMerge: typeof window.__pywryDeepMerge === 'function',
                hasPlotly: !!plotDiv,
                svgCount: plotDiv ? plotDiv.querySelectorAll('svg').length : 0,
                paperBg: plotDiv && plotDiv._fullLayout ? plotDiv._fullLayout.paper_bgcolor : null,
                plotBg: plotDiv && plotDiv._fullLayout ? plotDiv._fullLayout.plot_bgcolor : null,
                fontColor: plotDiv && plotDiv._fullLayout ? plotDiv._fullLayout.font.color : null,
                fontFamily: plotDiv && plotDiv._fullLayout ? (plotDiv._fullLayout.font.family || null) : null,
                storedDark: plotDiv ? !!plotDiv.__pywry_user_template_dark__ : false,
                storedLight: plotDiv ? !!plotDiv.__pywry_user_template_light__ : false,
                storedLegacy: plotDiv ? !!plotDiv.__pywry_user_template__ : false,
                baseDarkPaperBg: templates.plotly_dark ? templates.plotly_dark.layout.paper_bgcolor : null,
                baseLightPaperBg: templates.plotly_white ? templates.plotly_white.layout.paper_bgcolor : null
            });
        })();
        """,
    )


SIMPLE_FIGURE = {"data": [{"x": [1, 2, 3], "y": [10, 15, 13], "type": "scatter"}]}


class TestDarkThemeMergeE2E:
    """DARK window: user template_dark overrides are merged on top of plotly_dark base.

    Proves that custom colors actually appear in the rendered chart.
    """

    def test_custom_dark_colors_applied(self, dark_app) -> None:
        """User's dark template overrides actually render in the chart."""
        config = PlotlyConfig(
            template_dark={
                "layout": {
                    "paper_bgcolor": CUSTOM_DARK_PAPER_BG,
                    "plot_bgcolor": CUSTOM_DARK_PLOT_BG,
                    "font": {"color": CUSTOM_DARK_FONT_COLOR},
                }
            },
            template_light={
                "layout": {
                    "paper_bgcolor": CUSTOM_LIGHT_PAPER_BG,
                    "plot_bgcolor": CUSTOM_LIGHT_PLOT_BG,
                    "font": {"color": CUSTOM_LIGHT_FONT_COLOR},
                }
            },
        )

        label = show_plotly_and_wait_ready(
            dark_app,
            SIMPLE_FIGURE,
            title="Dark Merge E2E",
            config=config,
            timeout=20.0,
        )
        time.sleep(2.0)  # Plotly renders asynchronously

        result = _read_chart_template_state(label)
        assert result is not None, "No response from window!"
        assert result["hasPlotly"], "Plotly chart div not found!"
        assert result["svgCount"] > 0, "No SVG elements — chart not drawn!"

        # The merge functions must be loaded in the page
        assert result["hasMergeFunction"], "__pywryMergeThemeTemplate not found in window!"
        assert result["hasDeepMerge"], "__pywryDeepMerge not found in window!"

        # The CUSTOM colors must be rendered — NOT the base plotly_dark values
        assert result["paperBg"] == CUSTOM_DARK_PAPER_BG, (
            f"paper_bgcolor should be custom dark '{CUSTOM_DARK_PAPER_BG}', "
            f"got '{result['paperBg']}' (base dark is '{result['baseDarkPaperBg']}')"
        )
        assert result["plotBg"] == CUSTOM_DARK_PLOT_BG, (
            f"plot_bgcolor should be custom dark '{CUSTOM_DARK_PLOT_BG}', got '{result['plotBg']}'"
        )
        assert result["fontColor"] == CUSTOM_DARK_FONT_COLOR, (
            f"font color should be '{CUSTOM_DARK_FONT_COLOR}', got '{result['fontColor']}'"
        )

    def test_dual_templates_stored_on_dom(self, dark_app) -> None:
        """Both dark and light user templates are stored on the plot div for theme switching."""
        config = PlotlyConfig(
            template_dark={"layout": {"paper_bgcolor": CUSTOM_DARK_PAPER_BG}},
            template_light={"layout": {"paper_bgcolor": CUSTOM_LIGHT_PAPER_BG}},
        )

        label = show_plotly_and_wait_ready(
            dark_app,
            SIMPLE_FIGURE,
            title="Stored Templates E2E",
            config=config,
            timeout=20.0,
        )
        time.sleep(2.0)

        result = _read_chart_template_state(label)
        assert result is not None, "No response from window!"

        # Both templates must be persisted on the DOM element
        assert result["storedDark"], "template_dark not stored on plot div!"
        assert result["storedLight"], "template_light not stored on plot div!"
        # Legacy single template should NOT be stored when dual templates are used
        assert not result["storedLegacy"], (
            "Legacy template should NOT be stored when dual templates given!"
        )

    def test_base_theme_values_kept_where_not_overridden(self, dark_app) -> None:
        """Base plotly_dark values are preserved for keys the user didn't override."""
        # Only override paper_bgcolor — everything else should come from plotly_dark base
        config = PlotlyConfig(
            template_dark={"layout": {"paper_bgcolor": CUSTOM_DARK_PAPER_BG}},
        )

        label = show_plotly_and_wait_ready(
            dark_app,
            SIMPLE_FIGURE,
            title="Partial Override E2E",
            config=config,
            timeout=20.0,
        )
        time.sleep(2.0)

        result = _read_chart_template_state(label)
        assert result is not None, "No response from window!"
        assert result["hasPlotly"], "Plotly chart div not found!"

        # paper_bgcolor is overridden
        assert result["paperBg"] == CUSTOM_DARK_PAPER_BG, (
            f"paper_bgcolor should be custom '{CUSTOM_DARK_PAPER_BG}', got '{result['paperBg']}'"
        )

        # plot_bgcolor should be the base dark value (NOT custom), because we didn't override it
        # We can't hardcode what plotly_dark's plot_bgcolor is, but it should NOT be our custom value
        # and it should NOT be the light custom value
        assert result["plotBg"] != CUSTOM_DARK_PLOT_BG, (
            "plot_bgcolor should NOT be custom — it wasn't overridden!"
        )
        assert result["plotBg"] != CUSTOM_LIGHT_PLOT_BG, (
            "plot_bgcolor should NOT be the light custom value!"
        )

    def test_no_templates_uses_base_dark(self, dark_app) -> None:
        """Without any user templates, the base plotly_dark template is applied."""
        # No template_dark / template_light — just a plain config
        config = PlotlyConfig(responsive=True)

        label = show_plotly_and_wait_ready(
            dark_app,
            SIMPLE_FIGURE,
            title="No Override E2E",
            config=config,
            timeout=20.0,
        )
        time.sleep(2.0)

        result = _read_chart_template_state(label)
        assert result is not None, "No response from window!"
        assert result["hasPlotly"], "Plotly chart div not found!"

        # paper_bgcolor should be the base plotly_dark template value
        assert result["paperBg"] == result["baseDarkPaperBg"], (
            f"Without overrides, paper_bgcolor should be base dark '{result['baseDarkPaperBg']}', "
            f"got '{result['paperBg']}'"
        )


class TestLightThemeMergeE2E:
    """LIGHT window: user template_light overrides are merged on top of plotly_white base."""

    def test_custom_light_colors_applied(self, light_app) -> None:
        """User's light template overrides actually render in the chart."""
        config = PlotlyConfig(
            template_dark={
                "layout": {
                    "paper_bgcolor": CUSTOM_DARK_PAPER_BG,
                    "plot_bgcolor": CUSTOM_DARK_PLOT_BG,
                }
            },
            template_light={
                "layout": {
                    "paper_bgcolor": CUSTOM_LIGHT_PAPER_BG,
                    "plot_bgcolor": CUSTOM_LIGHT_PLOT_BG,
                    "font": {"color": CUSTOM_LIGHT_FONT_COLOR},
                }
            },
        )

        label = show_plotly_and_wait_ready(
            light_app,
            SIMPLE_FIGURE,
            title="Light Merge E2E",
            config=config,
            timeout=20.0,
        )
        time.sleep(2.0)

        result = _read_chart_template_state(label)
        assert result is not None, "No response from window!"
        assert result["hasPlotly"], "Plotly chart div not found!"
        assert result["svgCount"] > 0, "No SVG elements — chart not drawn!"

        # Light custom colors should be rendered — NOT base plotly_white and NOT dark overrides
        assert result["paperBg"] == CUSTOM_LIGHT_PAPER_BG, (
            f"paper_bgcolor should be custom light '{CUSTOM_LIGHT_PAPER_BG}', "
            f"got '{result['paperBg']}' (base light is '{result['baseLightPaperBg']}')"
        )
        assert result["plotBg"] == CUSTOM_LIGHT_PLOT_BG, (
            f"plot_bgcolor should be custom light '{CUSTOM_LIGHT_PLOT_BG}', got '{result['plotBg']}'"
        )
        assert result["fontColor"] == CUSTOM_LIGHT_FONT_COLOR, (
            f"font color should be '{CUSTOM_LIGHT_FONT_COLOR}', got '{result['fontColor']}'"
        )

        # Must NOT have dark overrides applied
        assert result["paperBg"] != CUSTOM_DARK_PAPER_BG, "Dark override leaked into light mode!"
        assert result["plotBg"] != CUSTOM_DARK_PLOT_BG, "Dark override leaked into light mode!"

    def test_no_templates_uses_base_light(self, light_app) -> None:
        """Without any user templates, the base plotly_white template is applied."""
        config = PlotlyConfig(responsive=True)

        label = show_plotly_and_wait_ready(
            light_app,
            SIMPLE_FIGURE,
            title="No Override Light E2E",
            config=config,
            timeout=20.0,
        )
        time.sleep(2.0)

        result = _read_chart_template_state(label)
        assert result is not None, "No response from window!"
        assert result["hasPlotly"], "Plotly chart div not found!"

        # paper_bgcolor should be the base plotly_white template value
        assert result["paperBg"] == result["baseLightPaperBg"], (
            f"Without overrides, paper_bgcolor should be base light '{result['baseLightPaperBg']}', "
            f"got '{result['paperBg']}'"
        )


class TestThemeSwitchViaEventE2E:
    """Verify the REAL pywry:update-theme event handler toggles templates correctly.

    These tests fire app.emit('pywry:update-theme', ...) from Python, which goes
    through the full IPC path → JS window.pywry.on('pywry:update-theme') handler →
    __pywryMergeThemeTemplate → Plotly.relayout. This is the ACTUAL code
    path that runs when a user toggles the theme.
    """

    def test_emit_toggle_dark_to_light(self, dark_app) -> None:
        """app.emit('pywry:update-theme') dark→light switches to light user template."""
        config = PlotlyConfig(
            template_dark={"layout": {"paper_bgcolor": CUSTOM_DARK_PAPER_BG}},
            template_light={"layout": {"paper_bgcolor": CUSTOM_LIGHT_PAPER_BG}},
        )

        label = show_plotly_and_wait_ready(
            dark_app,
            SIMPLE_FIGURE,
            title="Emit Toggle D→L",
            config=config,
            timeout=20.0,
        )
        time.sleep(2.0)

        # Verify initial dark state
        result = _read_chart_template_state(label)
        assert result is not None and result["paperBg"] == CUSTOM_DARK_PAPER_BG, (
            f"Initial dark paper_bgcolor wrong: {result}"
        )

        # Fire the REAL event through the full Python → IPC → JS handler chain
        dark_app.emit("pywry:update-theme", {"theme": "plotly_white"}, label=label)

        # Wait for the handler + Plotly.relayout to complete
        time.sleep(2.5)

        # Read back the rendered chart state
        after = _read_chart_template_state(label)
        assert after is not None, "No response after theme toggle!"
        assert after["paperBg"] == CUSTOM_LIGHT_PAPER_BG, (
            f"After emit toggle to light, paper_bgcolor should be '{CUSTOM_LIGHT_PAPER_BG}', "
            f"got '{after['paperBg']}'"
        )

    def test_emit_toggle_light_to_dark(self, light_app) -> None:
        """app.emit('pywry:update-theme') light→dark switches to dark user template."""
        config = PlotlyConfig(
            template_dark={"layout": {"paper_bgcolor": CUSTOM_DARK_PAPER_BG}},
            template_light={"layout": {"paper_bgcolor": CUSTOM_LIGHT_PAPER_BG}},
        )

        label = show_plotly_and_wait_ready(
            light_app,
            SIMPLE_FIGURE,
            title="Emit Toggle L→D",
            config=config,
            timeout=20.0,
        )
        time.sleep(2.0)

        # Verify initial light state
        result = _read_chart_template_state(label)
        assert result is not None and result["paperBg"] == CUSTOM_LIGHT_PAPER_BG, (
            f"Initial light paper_bgcolor wrong: {result}"
        )

        # Fire the REAL event
        light_app.emit("pywry:update-theme", {"theme": "plotly_dark"}, label=label)
        time.sleep(2.5)

        after = _read_chart_template_state(label)
        assert after is not None, "No response after theme toggle!"
        assert after["paperBg"] == CUSTOM_DARK_PAPER_BG, (
            f"After emit toggle to dark, paper_bgcolor should be '{CUSTOM_DARK_PAPER_BG}', "
            f"got '{after['paperBg']}'"
        )

    def test_emit_round_trip_dark_light_dark(self, dark_app) -> None:
        """Full round-trip via real events: dark → light → dark. Templates persist."""
        config = PlotlyConfig(
            template_dark={
                "layout": {
                    "paper_bgcolor": CUSTOM_DARK_PAPER_BG,
                    "plot_bgcolor": CUSTOM_DARK_PLOT_BG,
                }
            },
            template_light={
                "layout": {
                    "paper_bgcolor": CUSTOM_LIGHT_PAPER_BG,
                    "plot_bgcolor": CUSTOM_LIGHT_PLOT_BG,
                }
            },
        )

        label = show_plotly_and_wait_ready(
            dark_app,
            SIMPLE_FIGURE,
            title="Emit Round Trip",
            config=config,
            timeout=20.0,
        )
        time.sleep(2.0)

        # Step 1: Verify initial dark
        r1 = _read_chart_template_state(label)
        assert r1 is not None and r1["paperBg"] == CUSTOM_DARK_PAPER_BG
        assert r1["plotBg"] == CUSTOM_DARK_PLOT_BG

        # Step 2: Toggle to light via real event
        dark_app.emit("pywry:update-theme", {"theme": "plotly_white"}, label=label)
        time.sleep(2.5)

        r2 = _read_chart_template_state(label)
        assert r2 is not None, "No response after toggle to light!"
        assert r2["paperBg"] == CUSTOM_LIGHT_PAPER_BG, (
            f"After light toggle, expected '{CUSTOM_LIGHT_PAPER_BG}', got '{r2['paperBg']}'"
        )
        assert r2["plotBg"] == CUSTOM_LIGHT_PLOT_BG, (
            f"After light toggle, expected '{CUSTOM_LIGHT_PLOT_BG}', got '{r2['plotBg']}'"
        )

        # Step 3: Toggle BACK to dark via real event
        dark_app.emit("pywry:update-theme", {"theme": "plotly_dark"}, label=label)
        time.sleep(2.5)

        r3 = _read_chart_template_state(label)
        assert r3 is not None, "No response after toggle back to dark!"
        assert r3["paperBg"] == CUSTOM_DARK_PAPER_BG, (
            f"After round-trip back to dark, expected '{CUSTOM_DARK_PAPER_BG}', got '{r3['paperBg']}'"
        )
        assert r3["plotBg"] == CUSTOM_DARK_PLOT_BG, (
            f"After round-trip back to dark, expected '{CUSTOM_DARK_PLOT_BG}', got '{r3['plotBg']}'"
        )

    def test_emit_toggle_preserves_stored_templates_on_dom(self, dark_app) -> None:
        """After real event toggle, the stored templates are still on the DOM element."""
        config = PlotlyConfig(
            template_dark={"layout": {"paper_bgcolor": CUSTOM_DARK_PAPER_BG}},
            template_light={"layout": {"paper_bgcolor": CUSTOM_LIGHT_PAPER_BG}},
        )

        label = show_plotly_and_wait_ready(
            dark_app,
            SIMPLE_FIGURE,
            title="Emit Persist E2E",
            config=config,
            timeout=20.0,
        )
        time.sleep(2.0)

        # Toggle to light via real event
        dark_app.emit("pywry:update-theme", {"theme": "plotly_white"}, label=label)
        time.sleep(2.5)

        # The handler calls Plotly.relayout which preserves the DOM element.
        # Verify the stored templates survived the re-render.
        after = _read_chart_template_state(label)
        assert after is not None, "No response after toggle!"
        assert after["storedDark"], "template_dark lost after real event toggle + Plotly.relayout!"
        assert after["storedLight"], (
            "template_light lost after real event toggle + Plotly.relayout!"
        )

    def test_font_colors_update_on_theme_switch(self, dark_app) -> None:
        """Switching from light→dark must NOT leave black text on a dark background.

        This is the core regression test: font.color, paper_bgcolor, and
        plot_bgcolor should all come from the NEW template after a toggle,
        not be carried over from the old one.
        """
        label = show_plotly_and_wait_ready(
            dark_app,
            SIMPLE_FIGURE,
            title="Font Color Switch",
            timeout=20.0,
        )
        time.sleep(2.0)

        # Read initial dark state — font should be light
        dark_state = _read_chart_template_state(label)
        assert dark_state is not None and dark_state["fontColor"] is not None

        # Toggle to light
        dark_app.emit("pywry:update-theme", {"theme": "plotly_white"}, label=label)
        time.sleep(2.5)
        light_state = _read_chart_template_state(label)
        assert light_state is not None, "No response after toggle to light"

        # Toggle back to dark
        dark_app.emit("pywry:update-theme", {"theme": "plotly_dark"}, label=label)
        time.sleep(2.5)
        back_dark = _read_chart_template_state(label)
        assert back_dark is not None, "No response after toggle back to dark"

        # Font color after round-trip must match the original dark font color,
        # NOT the light theme's font color.
        assert back_dark["fontColor"] == dark_state["fontColor"], (
            f"Font color after light→dark round-trip is '{back_dark['fontColor']}' but "
            f"should be '{dark_state['fontColor']}'. "
            "Dark text on a dark background!"
        )
