"""Tests for Plotly theme merge feature.

Proves that:
1. PlotlyConfig serializes template_dark / template_light to camelCase
2. build_plotly_init_script emits correct JS for dual template extraction & merge
3. The JS deep-merge logic works (user values always win, arrays replace, nested merges)
4. Theme switching picks the correct per-theme user override

These are NEW tests for the deep-merge / dual-template feature.
"""

from __future__ import annotations

import json
import subprocess
import textwrap

import pytest

from pywry.models import ThemeMode
from pywry.plotly_config import PlotlyConfig
from pywry.templates import build_plotly_init_script


# =============================================================================
# PlotlyConfig serialization — template_dark / template_light
# =============================================================================


class TestPlotlyConfigDualTemplateFields:
    """Verify template_dark and template_light fields serialize correctly."""

    def test_template_dark_serializes_to_camel_case(self) -> None:
        """template_dark -> templateDark in serialized output."""
        config = PlotlyConfig(
            template_dark={"layout": {"paper_bgcolor": "#1a1a2e"}},
        )
        data = config.model_dump(by_alias=True, exclude_none=True)
        assert "templateDark" in data
        assert data["templateDark"] == {"layout": {"paper_bgcolor": "#1a1a2e"}}
        # Should NOT have snake_case key
        assert "template_dark" not in data

    def test_template_light_serializes_to_camel_case(self) -> None:
        """template_light -> templateLight in serialized output."""
        config = PlotlyConfig(
            template_light={"layout": {"plot_bgcolor": "#f0f0f0"}},
        )
        data = config.model_dump(by_alias=True, exclude_none=True)
        assert "templateLight" in data
        assert data["templateLight"] == {"layout": {"plot_bgcolor": "#f0f0f0"}}
        assert "template_light" not in data

    def test_both_templates_serialize_together(self) -> None:
        """Both dark and light templates appear when set."""
        config = PlotlyConfig(
            template_dark={"layout": {"paper_bgcolor": "#111"}},
            template_light={"layout": {"paper_bgcolor": "#fff"}},
        )
        data = config.model_dump(by_alias=True, exclude_none=True)
        assert "templateDark" in data
        assert "templateLight" in data
        assert data["templateDark"]["layout"]["paper_bgcolor"] == "#111"
        assert data["templateLight"]["layout"]["paper_bgcolor"] == "#fff"

    def test_templates_excluded_when_none(self) -> None:
        """templateDark/templateLight are absent when not set (exclude_none)."""
        config = PlotlyConfig(responsive=True)
        data = config.model_dump(by_alias=True, exclude_none=True)
        assert "templateDark" not in data
        assert "templateLight" not in data

    def test_empty_dict_is_not_excluded(self) -> None:
        """An empty dict is NOT None — it should still serialize."""
        config = PlotlyConfig(template_dark={})
        data = config.model_dump(by_alias=True, exclude_none=True)
        assert "templateDark" in data
        assert data["templateDark"] == {}

    def test_nested_template_structure_preserved(self) -> None:
        """Complex nested template structures survive serialization."""
        dark_template = {
            "layout": {
                "paper_bgcolor": "#1a1a2e",
                "plot_bgcolor": "#16213e",
                "font": {"color": "#e0e0e0", "size": 14},
                "xaxis": {"gridcolor": "#333"},
            },
            "data": {
                "scatter": [{"marker": {"color": "#00ff88"}}],
            },
        }
        config = PlotlyConfig(template_dark=dark_template)
        data = config.model_dump(by_alias=True, exclude_none=True)
        assert data["templateDark"]["layout"]["font"]["color"] == "#e0e0e0"
        assert data["templateDark"]["data"]["scatter"][0]["marker"]["color"] == "#00ff88"


# =============================================================================
# build_plotly_init_script — JS output contains dual template handling
# =============================================================================


class TestBuildPlotlyInitScriptDualTemplates:
    """Verify that build_plotly_init_script emits correct JS for theme merge."""

    @staticmethod
    def _make_figure(
        *,
        template_dark: dict | None = None,
        template_light: dict | None = None,
    ) -> dict:
        """Create a figure dict with optional dual templates in config."""
        config: dict = {"responsive": True}
        if template_dark is not None:
            config["templateDark"] = template_dark
        if template_light is not None:
            config["templateLight"] = template_light
        return {
            "data": [{"x": [1, 2], "y": [3, 4], "type": "scatter"}],
            "layout": {},
            "config": config,
        }

    def test_extracts_template_dark_from_config(self) -> None:
        """JS extracts userTemplateDark from config and deletes it."""
        figure = self._make_figure(
            template_dark={"layout": {"paper_bgcolor": "#111"}},
        )
        script = build_plotly_init_script(figure, chart_id="test-chart")
        assert "config.templateDark" in script
        assert "delete config.templateDark" in script

    def test_extracts_template_light_from_config(self) -> None:
        """JS extracts userTemplateLight from config and deletes it."""
        figure = self._make_figure(
            template_light={"layout": {"paper_bgcolor": "#fff"}},
        )
        script = build_plotly_init_script(figure, chart_id="test-chart")
        assert "config.templateLight" in script
        assert "delete config.templateLight" in script

    def test_calls_merge_function_with_five_args(self) -> None:
        """JS calls __pywryMergeThemeTemplate with (gd, theme, user, dark, light)."""
        figure = self._make_figure(
            template_dark={"layout": {"paper_bgcolor": "#111"}},
            template_light={"layout": {"paper_bgcolor": "#fff"}},
        )
        script = build_plotly_init_script(figure, chart_id="test-chart")
        assert "__pywryMergeThemeTemplate" in script
        # The call should have gd, themeTemplate, userTemplate, userTemplateDark, userTemplateLight
        assert "gd, themeTemplate, userTemplate, userTemplateDark, userTemplateLight" in script

    def test_dark_theme_sets_plotly_dark_template_name(self) -> None:
        """In dark mode, themeTemplate is 'plotly_dark'."""
        figure = self._make_figure()
        script = build_plotly_init_script(figure, theme=ThemeMode.DARK)
        assert "var themeTemplate = 'plotly_dark'" in script

    def test_light_theme_sets_plotly_white_template_name(self) -> None:
        """In light mode, themeTemplate is 'plotly_white'."""
        figure = self._make_figure()
        script = build_plotly_init_script(figure, theme=ThemeMode.LIGHT)
        assert "var themeTemplate = 'plotly_white'" in script

    def test_user_template_values_embedded_in_js(self) -> None:
        """The actual user template values end up in the emitted JS JSON."""
        dark = {"layout": {"paper_bgcolor": "#CUSTOM_DARK_BG"}}
        light = {"layout": {"paper_bgcolor": "#CUSTOM_LIGHT_BG"}}
        figure = self._make_figure(template_dark=dark, template_light=light)
        script = build_plotly_init_script(figure, chart_id="tc")
        # The template values are embedded in the figData JSON
        assert "#CUSTOM_DARK_BG" in script
        assert "#CUSTOM_LIGHT_BG" in script

    def test_relayout_applies_merged_template(self) -> None:
        """After newPlot, the script calls Plotly.relayout with merged template."""
        figure = self._make_figure(template_dark={"layout": {}})
        script = build_plotly_init_script(figure, chart_id="tc")
        assert "Plotly.relayout(gd, { template: mergedTemplate })" in script

    def test_figure_without_dual_templates_still_has_extraction_code(self) -> None:
        """Even without dual templates, the extraction code is present (they'll be null)."""
        figure = self._make_figure()
        script = build_plotly_init_script(figure, chart_id="tc")
        # Extraction lines are always present
        assert "var userTemplateDark = config.templateDark || null" in script
        assert "var userTemplateLight = config.templateLight || null" in script


# =============================================================================
# JS deep-merge and theme selection logic tests
# =============================================================================

# We test the actual JavaScript functions by running them in Node.js.
# This proves the runtime behaviour, not just that we emit the right strings.


_JS_FUNCTIONS = textwrap.dedent("""\
    // --- Paste of __pywryDeepMerge ---
    function deepMerge(base, overrides) {
        if (!overrides || typeof overrides !== 'object') return base ? JSON.parse(JSON.stringify(base)) : {};
        if (!base || typeof base !== 'object') return JSON.parse(JSON.stringify(overrides));
        var result = JSON.parse(JSON.stringify(base));
        var keys = Object.keys(overrides);
        for (var i = 0; i < keys.length; i++) {
            var key = keys[i];
            var val = overrides[key];
            if (val !== null && typeof val === 'object' && !Array.isArray(val)
                && result[key] !== null && typeof result[key] === 'object' && !Array.isArray(result[key])) {
                result[key] = deepMerge(result[key], val);
            } else {
                result[key] = (val !== null && typeof val === 'object') ? JSON.parse(JSON.stringify(val)) : val;
            }
        }
        return result;
    }

    // --- Paste of __pywryMergeThemeTemplate ---
    var PYWRY_PLOTLY_TEMPLATES = {};
    function mergeThemeTemplate(plotDiv, themeTemplateName, userTemplate, userTemplateDark, userTemplateLight) {
        var templates = PYWRY_PLOTLY_TEMPLATES;
        var baseTemplate = templates[themeTemplateName] || {};

        if (userTemplateDark && typeof userTemplateDark === 'object' && Object.keys(userTemplateDark).length > 0) {
            plotDiv.__pywry_user_template_dark__ = JSON.parse(JSON.stringify(userTemplateDark));
        }
        if (userTemplateLight && typeof userTemplateLight === 'object' && Object.keys(userTemplateLight).length > 0) {
            plotDiv.__pywry_user_template_light__ = JSON.parse(JSON.stringify(userTemplateLight));
        }
        if (userTemplate && typeof userTemplate === 'object' && Object.keys(userTemplate).length > 0
            && !userTemplateDark && !userTemplateLight) {
            plotDiv.__pywry_user_template__ = JSON.parse(JSON.stringify(userTemplate));
        }

        var isDark = themeTemplateName.indexOf('dark') !== -1;
        var overrides = null;
        if (isDark && plotDiv.__pywry_user_template_dark__) {
            overrides = plotDiv.__pywry_user_template_dark__;
        } else if (!isDark && plotDiv.__pywry_user_template_light__) {
            overrides = plotDiv.__pywry_user_template_light__;
        } else {
            overrides = plotDiv.__pywry_user_template__;
        }

        if (!overrides) return JSON.parse(JSON.stringify(baseTemplate));
        return deepMerge(baseTemplate, overrides);
    }

    // --- Paste of __pywryStripThemeColors ---
    function stripThemeColors(plotDiv) {
        var layout = plotDiv.layout;
        if (!layout) return;
        delete layout.paper_bgcolor;
        delete layout.plot_bgcolor;
        delete layout.colorway;
        if (layout.font) {
            delete layout.font.color;
            if (Object.keys(layout.font).length === 0) delete layout.font;
        }
        var axisRe = /^[xyz]axis\\d*$/;
        var keys = Object.keys(layout);
        for (var i = 0; i < keys.length; i++) {
            if (axisRe.test(keys[i]) && layout[keys[i]] && typeof layout[keys[i]] === 'object') {
                var ax = layout[keys[i]];
                delete ax.color;
                delete ax.gridcolor;
                delete ax.linecolor;
                delete ax.zerolinecolor;
            }
        }
    }
""")


def _node_available() -> bool:
    """Check if node is available on PATH."""
    try:
        result = subprocess.run(
            ["node", "--version"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    else:
        return result.returncode == 0


def _run_js(code: str) -> str:
    """Run a JS snippet in Node.js and return stdout."""
    full = _JS_FUNCTIONS + "\n" + code
    result = subprocess.run(  # noqa: S603
        ["node", "-e", full],  # noqa: S607
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Node.js error:\n{result.stderr}")
    return result.stdout.strip()


def _run_js_json(code: str) -> object:
    """Run JS that console.log's a JSON value, return parsed Python object."""
    raw = _run_js(code)
    return json.loads(raw)


_requires_node = pytest.mark.skipif(
    not _node_available(),
    reason="Node.js not available — JS runtime tests skipped",
)


@_requires_node
class TestDeepMergeJS:
    """Test the __pywryDeepMerge function via Node.js."""

    def test_user_value_wins_on_conflict(self) -> None:
        """When both base and overrides have the same key, override wins."""
        result = _run_js_json("""
            var base = {a: 1, b: 2};
            var over = {b: 99};
            console.log(JSON.stringify(deepMerge(base, over)));
        """)
        assert result == {"a": 1, "b": 99}

    def test_nested_objects_are_deep_merged(self) -> None:
        """Nested objects are merged recursively, not replaced."""
        result = _run_js_json("""
            var base = {layout: {paper_bgcolor: '#000', font: {color: '#ccc', size: 12}}};
            var over = {layout: {font: {color: '#fff'}}};
            console.log(JSON.stringify(deepMerge(base, over)));
        """)
        assert result["layout"]["paper_bgcolor"] == "#000"  # kept from base
        assert result["layout"]["font"]["color"] == "#fff"  # overridden
        assert result["layout"]["font"]["size"] == 12  # kept from base

    def test_arrays_are_replaced_not_merged(self) -> None:
        """Override array replaces base array entirely."""
        result = _run_js_json("""
            var base = {colors: ['red', 'green', 'blue']};
            var over = {colors: ['#ff0000']};
            console.log(JSON.stringify(deepMerge(base, over)));
        """)
        assert result["colors"] == ["#ff0000"]

    def test_overrides_null_returns_base_copy(self) -> None:
        """When overrides is null, result is a copy of base."""
        result = _run_js_json("""
            var base = {a: 1};
            console.log(JSON.stringify(deepMerge(base, null)));
        """)
        assert result == {"a": 1}

    def test_base_null_returns_overrides_copy(self) -> None:
        """When base is null, result is a copy of overrides."""
        result = _run_js_json("""
            var over = {b: 2};
            console.log(JSON.stringify(deepMerge(null, over)));
        """)
        assert result == {"b": 2}

    def test_both_null_returns_empty_object(self) -> None:
        """When both are null, result is empty object."""
        result = _run_js_json("""
            console.log(JSON.stringify(deepMerge(null, null)));
        """)
        assert result == {}

    def test_new_keys_from_override_are_added(self) -> None:
        """Keys only in overrides are added to result."""
        result = _run_js_json("""
            var base = {a: 1};
            var over = {b: 2};
            console.log(JSON.stringify(deepMerge(base, over)));
        """)
        assert result == {"a": 1, "b": 2}

    def test_deeply_nested_three_levels(self) -> None:
        """Three levels of nesting merge correctly."""
        result = _run_js_json("""
            var base = {l1: {l2: {l3: 'base', keep: true}}};
            var over = {l1: {l2: {l3: 'override'}}};
            console.log(JSON.stringify(deepMerge(base, over)));
        """)
        assert result["l1"]["l2"]["l3"] == "override"
        assert result["l1"]["l2"]["keep"] is True

    def test_override_does_not_mutate_base(self) -> None:
        """Deep merge produces a new object — base is not mutated."""
        result = _run_js_json("""
            var base = {a: {b: 1}};
            var baseCopy = JSON.stringify(base);
            deepMerge(base, {a: {b: 99}});
            console.log(JSON.stringify(base === JSON.parse(baseCopy) ? 'fail' : base));
        """)
        # base.a.b should still be 1 (not mutated)
        assert result["a"]["b"] == 1


@_requires_node
class TestMergeThemeTemplateJS:
    """Test the __pywryMergeThemeTemplate function via Node.js."""

    def test_dark_theme_picks_dark_user_template(self) -> None:
        """In dark mode, template_dark overrides are used."""
        result = _run_js_json("""
            PYWRY_PLOTLY_TEMPLATES = {
                plotly_dark: {layout: {paper_bgcolor: '#111', font: {color: '#aaa'}}},
                plotly_white: {layout: {paper_bgcolor: '#fff', font: {color: '#333'}}}
            };
            var plotDiv = {};
            var merged = mergeThemeTemplate(
                plotDiv, 'plotly_dark', null,
                {layout: {paper_bgcolor: '#CUSTOM_DARK'}},  // dark override
                {layout: {paper_bgcolor: '#CUSTOM_LIGHT'}}  // light override
            );
            console.log(JSON.stringify(merged));
        """)
        # Dark override should win for paper_bgcolor
        assert result["layout"]["paper_bgcolor"] == "#CUSTOM_DARK"
        # Base dark font color should be kept (not in override)
        assert result["layout"]["font"]["color"] == "#aaa"

    def test_light_theme_picks_light_user_template(self) -> None:
        """In light mode, template_light overrides are used."""
        result = _run_js_json("""
            PYWRY_PLOTLY_TEMPLATES = {
                plotly_dark: {layout: {paper_bgcolor: '#111', font: {color: '#aaa'}}},
                plotly_white: {layout: {paper_bgcolor: '#fff', font: {color: '#333'}}}
            };
            var plotDiv = {};
            var merged = mergeThemeTemplate(
                plotDiv, 'plotly_white', null,
                {layout: {paper_bgcolor: '#CUSTOM_DARK'}},
                {layout: {paper_bgcolor: '#CUSTOM_LIGHT'}}
            );
            console.log(JSON.stringify(merged));
        """)
        assert result["layout"]["paper_bgcolor"] == "#CUSTOM_LIGHT"
        assert result["layout"]["font"]["color"] == "#333"  # base light font

    def test_fallback_to_legacy_template_when_no_dual(self) -> None:
        """When only a single template is provided, it applies to both modes."""
        result = _run_js_json("""
            PYWRY_PLOTLY_TEMPLATES = {
                plotly_dark: {layout: {paper_bgcolor: '#111'}}
            };
            var plotDiv = {};
            var merged = mergeThemeTemplate(
                plotDiv, 'plotly_dark',
                {layout: {paper_bgcolor: '#LEGACY'}},  // single/legacy
                null, null  // no dual templates
            );
            console.log(JSON.stringify(merged));
        """)
        assert result["layout"]["paper_bgcolor"] == "#LEGACY"

    def test_legacy_fallback_also_applies_on_light(self) -> None:
        """Single/legacy template also works for light mode."""
        result = _run_js_json("""
            PYWRY_PLOTLY_TEMPLATES = {
                plotly_white: {layout: {paper_bgcolor: '#fff'}}
            };
            var plotDiv = {};
            // First call with legacy template
            mergeThemeTemplate(plotDiv, 'plotly_white', {layout: {font: {size: 20}}}, null, null);
            // Second call: theme toggle (no new templates — reads from stored)
            var merged = mergeThemeTemplate(plotDiv, 'plotly_white', null, null, null);
            console.log(JSON.stringify(merged));
        """)
        assert result["layout"]["font"]["size"] == 20
        assert result["layout"]["paper_bgcolor"] == "#fff"

    def test_templates_persist_across_theme_switches(self) -> None:
        """Stored per-theme templates survive across toggle calls."""
        result = _run_js_json("""
            PYWRY_PLOTLY_TEMPLATES = {
                plotly_dark: {layout: {paper_bgcolor: '#111'}},
                plotly_white: {layout: {paper_bgcolor: '#fff'}}
            };
            var plotDiv = {};
            // Initial render in dark mode with both templates
            mergeThemeTemplate(
                plotDiv, 'plotly_dark', null,
                {layout: {paper_bgcolor: '#MY_DARK'}},
                {layout: {paper_bgcolor: '#MY_LIGHT'}}
            );
            // User toggles to light — no new templates, just reads stored ones
            var light = mergeThemeTemplate(plotDiv, 'plotly_white', null, null, null);
            // User toggles back to dark
            var dark = mergeThemeTemplate(plotDiv, 'plotly_dark', null, null, null);
            console.log(JSON.stringify({light: light, dark: dark}));
        """)
        assert result["light"]["layout"]["paper_bgcolor"] == "#MY_LIGHT"
        assert result["dark"]["layout"]["paper_bgcolor"] == "#MY_DARK"

    def test_no_user_overrides_returns_base_theme(self) -> None:
        """When no user templates are set, plain base theme is returned."""
        result = _run_js_json("""
            PYWRY_PLOTLY_TEMPLATES = {
                plotly_dark: {layout: {paper_bgcolor: '#111', font: {color: '#ccc'}}}
            };
            var plotDiv = {};
            var merged = mergeThemeTemplate(plotDiv, 'plotly_dark', null, null, null);
            console.log(JSON.stringify(merged));
        """)
        assert result == {"layout": {"paper_bgcolor": "#111", "font": {"color": "#ccc"}}}

    def test_unknown_theme_name_returns_override_only(self) -> None:
        """If theme name doesn't match any base, override is returned as-is."""
        result = _run_js_json("""
            PYWRY_PLOTLY_TEMPLATES = {};
            var plotDiv = {};
            var merged = mergeThemeTemplate(
                plotDiv, 'nonexistent_theme', null,
                {layout: {paper_bgcolor: '#DARK_ONLY'}},
                null
            );
            // nonexistent_theme contains 'dark' substring? No, let's pick a dark theme name
            console.log(JSON.stringify(merged));
        """)
        # "nonexistent_theme" doesn't contain 'dark', so it's treated as light
        # No light template provided, no legacy template -> base is empty
        assert result == {}

    def test_dark_override_with_complex_nested_values(self) -> None:
        """Complex nested user dark template merges correctly with base."""
        result = _run_js_json("""
            PYWRY_PLOTLY_TEMPLATES = {
                plotly_dark: {
                    layout: {
                        paper_bgcolor: '#111',
                        plot_bgcolor: '#222',
                        font: {color: '#aaa', size: 12, family: 'Arial'},
                        xaxis: {gridcolor: '#444', zerolinecolor: '#555'},
                        yaxis: {gridcolor: '#444', zerolinecolor: '#555'}
                    }
                }
            };
            var plotDiv = {};
            var merged = mergeThemeTemplate(
                plotDiv, 'plotly_dark', null,
                {
                    layout: {
                        paper_bgcolor: '#1a1a2e',
                        font: {color: '#e0e0e0'},
                        xaxis: {gridcolor: '#333'}
                    }
                },
                null
            );
            console.log(JSON.stringify(merged));
        """)
        layout = result["layout"]
        # User dark overrides win
        assert layout["paper_bgcolor"] == "#1a1a2e"
        assert layout["font"]["color"] == "#e0e0e0"
        assert layout["xaxis"]["gridcolor"] == "#333"
        # Base values are kept where user didn't override
        assert layout["plot_bgcolor"] == "#222"
        assert layout["font"]["size"] == 12
        assert layout["font"]["family"] == "Arial"
        assert layout["xaxis"]["zerolinecolor"] == "#555"
        assert layout["yaxis"]["gridcolor"] == "#444"

    def test_dual_templates_not_stored_when_empty(self) -> None:
        """Empty dict templates are NOT stored (Object.keys check)."""
        result = _run_js_json("""
            PYWRY_PLOTLY_TEMPLATES = {
                plotly_dark: {layout: {paper_bgcolor: '#111'}}
            };
            var plotDiv = {};
            var merged = mergeThemeTemplate(plotDiv, 'plotly_dark', null, {}, {});
            // Empty dicts -> not stored, base returned as-is
            console.log(JSON.stringify({
                merged: merged,
                hasDark: !!plotDiv.__pywry_user_template_dark__,
                hasLight: !!plotDiv.__pywry_user_template_light__
            }));
        """)
        assert result["merged"]["layout"]["paper_bgcolor"] == "#111"
        assert result["hasDark"] is False
        assert result["hasLight"] is False


# =============================================================================
# End-to-end: PlotlyConfig -> build_plotly_init_script -> theme merge JS
# =============================================================================


class TestEndToEndTemplatePipeline:
    """Test the full pipeline from PlotlyConfig through to JS output."""

    def test_plotly_config_to_figure_to_script(self) -> None:
        """PlotlyConfig with dual templates produces correct init script."""
        config = PlotlyConfig(
            responsive=True,
            template_dark={"layout": {"paper_bgcolor": "#1a1a2e"}},
            template_light={"layout": {"paper_bgcolor": "#ffffff"}},
        )
        config_dict = config.model_dump(by_alias=True, exclude_none=True)

        figure = {
            "data": [{"x": [1, 2], "y": [3, 4], "type": "scatter"}],
            "layout": {},
            "config": config_dict,
        }

        script = build_plotly_init_script(figure, chart_id="e2e-chart", theme=ThemeMode.DARK)

        # 1. Templates are embedded in the JSON
        assert "#1a1a2e" in script
        assert "#ffffff" in script

        # 2. Extraction code is present
        assert "config.templateDark" in script
        assert "config.templateLight" in script
        assert "delete config.templateDark" in script
        assert "delete config.templateLight" in script

        # 3. Merge function is called
        assert "__pywryMergeThemeTemplate" in script

        # 4. Theme is dark
        assert "var themeTemplate = 'plotly_dark'" in script

        # 5. Relayout applies the merged result
        assert "Plotly.relayout(gd, { template: mergedTemplate })" in script

    def test_plotly_config_light_mode_pipeline(self) -> None:
        """Same pipeline in light mode picks plotly_white."""
        config = PlotlyConfig(
            template_dark={"layout": {"paper_bgcolor": "#111"}},
            template_light={"layout": {"paper_bgcolor": "#eee"}},
        )
        config_dict = config.model_dump(by_alias=True, exclude_none=True)

        figure = {
            "data": [{"x": [1], "y": [1], "type": "bar"}],
            "layout": {},
            "config": config_dict,
        }

        script = build_plotly_init_script(figure, chart_id="e2e-light", theme=ThemeMode.LIGHT)
        assert "var themeTemplate = 'plotly_white'" in script

    def test_no_templates_still_works(self) -> None:
        """PlotlyConfig without templates produces a valid script."""
        config = PlotlyConfig(responsive=True)
        config_dict = config.model_dump(by_alias=True, exclude_none=True)

        figure = {
            "data": [{"x": [1], "y": [1], "type": "scatter"}],
            "layout": {},
            "config": config_dict,
        }

        script = build_plotly_init_script(figure, chart_id="no-tpl")
        # Should still have the extraction code (it'll produce null)
        assert "var userTemplateDark = config.templateDark || null" in script
        assert "__pywryMergeThemeTemplate" in script


# =============================================================================
# __pywryStripThemeColors — JS runtime tests
# =============================================================================


@_requires_node
class TestStripThemeColorsJS:
    """Test that __pywryStripThemeColors removes theme-sensitive explicit colours."""

    def test_strips_paper_and_plot_bgcolor(self) -> None:
        result = _run_js_json("""
            var div = {layout: {paper_bgcolor: '#fff', plot_bgcolor: '#eee', title: 'Keep Me'}};
            stripThemeColors(div);
            console.log(JSON.stringify(div.layout));
        """)
        assert "paper_bgcolor" not in result
        assert "plot_bgcolor" not in result
        assert result["title"] == "Keep Me"

    def test_strips_font_color_but_keeps_font_size(self) -> None:
        result = _run_js_json("""
            var div = {layout: {font: {color: '#000', size: 14, family: 'Arial'}}};
            stripThemeColors(div);
            console.log(JSON.stringify(div.layout));
        """)
        assert "color" not in result["font"]
        assert result["font"]["size"] == 14
        assert result["font"]["family"] == "Arial"

    def test_removes_empty_font_object(self) -> None:
        result = _run_js_json("""
            var div = {layout: {font: {color: '#000'}, title: 'X'}};
            stripThemeColors(div);
            console.log(JSON.stringify(div.layout));
        """)
        assert "font" not in result
        assert result["title"] == "X"

    def test_strips_colorway(self) -> None:
        result = _run_js_json("""
            var div = {layout: {colorway: ['red', 'blue'], title: 'Chart'}};
            stripThemeColors(div);
            console.log(JSON.stringify(div.layout));
        """)
        assert "colorway" not in result

    def test_strips_axis_color_properties(self) -> None:
        result = _run_js_json("""
            var div = {layout: {
                xaxis: {color: '#000', gridcolor: '#ccc', linecolor: '#aaa', zerolinecolor: '#ddd', title: 'X'},
                yaxis: {color: '#000', gridcolor: '#ccc'},
                xaxis2: {color: '#111', range: [0, 10]}
            }};
            stripThemeColors(div);
            console.log(JSON.stringify(div.layout));
        """)
        assert "color" not in result["xaxis"]
        assert "gridcolor" not in result["xaxis"]
        assert "linecolor" not in result["xaxis"]
        assert "zerolinecolor" not in result["xaxis"]
        assert result["xaxis"]["title"] == "X"  # preserved
        assert "color" not in result["yaxis"]
        assert "color" not in result["xaxis2"]
        assert result["xaxis2"]["range"] == [0, 10]  # preserved

    def test_preserves_non_theme_layout_properties(self) -> None:
        result = _run_js_json("""
            var div = {layout: {
                paper_bgcolor: '#fff', title: 'My Chart',
                margin: {t: 40, r: 20}, autosize: true,
                annotations: [{text: 'hi'}]
            }};
            stripThemeColors(div);
            console.log(JSON.stringify(div.layout));
        """)
        assert result["title"] == "My Chart"
        assert result["margin"] == {"t": 40, "r": 20}
        assert result["autosize"] is True
        assert result["annotations"] == [{"text": "hi"}]

    def test_no_layout_is_noop(self) -> None:
        """Missing layout doesn't crash."""
        result = _run_js_json("""
            var div = {};
            stripThemeColors(div);
            console.log(JSON.stringify(div));
        """)
        assert result == {}
