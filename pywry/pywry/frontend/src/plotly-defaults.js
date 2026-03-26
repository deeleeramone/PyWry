/* PyWry Plotly Defaults & Registry */

// Registry for all Plotly charts on the page
if (!window.__PYWRY_CHARTS__) {
    window.__PYWRY_CHARTS__ = {};
}

// Unified component registry — any component can register with getData()
if (!window.__PYWRY_COMPONENTS__) {
    window.__PYWRY_COMPONENTS__ = {};
}

/**
 * Deep-merge two plain objects. Values in `overrides` win on conflict.
 * Arrays are NOT deep-merged — the override array replaces the base.
 * Used to layer user template customizations on top of a theme template.
 */
window.__pywryDeepMerge = function deepMerge(base, overrides) {
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
};

/**
 * Build a merged Plotly template: theme base + user overrides (user always wins).
 * Supports dual templates (separate dark/light overrides) — on theme toggle, the
 * correct per-theme user override is deep-merged on top of the built-in base.
 *
 * User overrides are persisted on the plot div so they survive theme switches.
 *
 * @param {HTMLElement} plotDiv - The Plotly chart DOM element.
 * @param {string} themeTemplateName - 'plotly_dark' or 'plotly_white'.
 * @param {object|null} userTemplate - Single user template to store (legacy / layout.template).
 * @param {object|null} userTemplateDark - User overrides specific to dark mode.
 * @param {object|null} userTemplateLight - User overrides specific to light mode.
 * @returns {object} The merged template.
 */
window.__pywryMergeThemeTemplate = function(plotDiv, themeTemplateName, userTemplate, userTemplateDark, userTemplateLight) {
    var templates = window.PYWRY_PLOTLY_TEMPLATES || {};
    var baseTemplate = templates[themeTemplateName] || {};

    // Store dual templates if provided (first call / figure update)
    if (userTemplateDark && typeof userTemplateDark === 'object' && Object.keys(userTemplateDark).length > 0) {
        plotDiv.__pywry_user_template_dark__ = JSON.parse(JSON.stringify(userTemplateDark));
    }
    if (userTemplateLight && typeof userTemplateLight === 'object' && Object.keys(userTemplateLight).length > 0) {
        plotDiv.__pywry_user_template_light__ = JSON.parse(JSON.stringify(userTemplateLight));
    }

    // Store single/legacy template if no dual templates given
    if (userTemplate && typeof userTemplate === 'object' && Object.keys(userTemplate).length > 0
        && !userTemplateDark && !userTemplateLight) {
        plotDiv.__pywry_user_template__ = JSON.parse(JSON.stringify(userTemplate));
    }

    // Pick the right user override for this theme mode
    var isDark = themeTemplateName.indexOf('dark') !== -1;
    var overrides = null;
    if (isDark && plotDiv.__pywry_user_template_dark__) {
        overrides = plotDiv.__pywry_user_template_dark__;
    } else if (!isDark && plotDiv.__pywry_user_template_light__) {
        overrides = plotDiv.__pywry_user_template_light__;
    } else {
        // Fallback to single/legacy template (applies to both modes)
        overrides = plotDiv.__pywry_user_template__;
    }

    if (!overrides) return JSON.parse(JSON.stringify(baseTemplate));

    // Deep-merge: base theme first, then user overrides on top (user wins)
    return window.__pywryDeepMerge(baseTemplate, overrides);
};

/**
 * Remove theme-sensitive colour properties from the explicit (input) layout
 * so that a subsequent Plotly.relayout({template:…}) can actually take
 * effect.  In Plotly.js, explicit layout values ALWAYS beat template
 * defaults, so colours set during the initial Plotly.newPlot (or injected
 * by Plotly Express) will survive a template swap unless we delete them
 * from gd.layout first.
 *
 * We only touch the known theme-sensitive keys — everything else
 * (margin, title text, annotations, traces …) is left untouched.
 *
 * @param {HTMLElement} plotDiv - The Plotly graph div.
 */
window.__pywryStripThemeColors = function(plotDiv) {
    var layout = plotDiv.layout;
    if (!layout) return;

    // Top-level colour properties provided by every Plotly theme template
    delete layout.paper_bgcolor;
    delete layout.plot_bgcolor;
    delete layout.colorway;

    // Font colour
    if (layout.font) {
        delete layout.font.color;
        if (Object.keys(layout.font).length === 0) delete layout.font;
    }

    // Axis colour properties (xaxis, yaxis, xaxis2, yaxis2, …)
    var axisRe = /^[xyz]axis\d*$/;
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
};

/**
 * Register a Plotly chart instance with PyWry.
 * @param {string} chartId - The unique ID for this chart.
 * @param {object} plotDiv - The DOM element containing the Plotly chart.
 * @param {object} bridge - The PyWry event bridge (optional, will look for window.pywry).
 */
function registerPyWryChart(chartId, plotDiv, bridge) {
    window.__PYWRY_CHARTS__[chartId] = plotDiv;

    // Register in unified component registry
    window.__PYWRY_COMPONENTS__[chartId] = {
        getData: function () {
            try {
                var traces = plotDiv.data.map(function (t) {
                    return { name: t.name || '', x: t.x, y: t.y, type: t.type };
                });
                return JSON.stringify(traces, null, 2);
            } catch (e) { return ''; }
        }
    };

    const pywry = bridge || window.pywry;
    if (!pywry) {
        console.warn('[PyWry Plotly] No bridge found for chart:', chartId);
        return;
    }

    // Attach basic event handlers
    if (plotDiv.on) {
        // Click
        plotDiv.on('plotly_click', (data) => {
            const points = data.points || [];
            pywry.emit('plotly:click', {
                widget_type: 'chart',
                chartId: chartId,
                points: points.map(p => ({
                    curveNumber: p.curveNumber,
                    pointNumber: p.pointNumber,
                    pointIndex: p.pointIndex,
                    x: p.x,
                    y: p.y,
                    z: p.z,
                    text: p.text,
                    customdata: p.customdata,
                    data: p.data,
                    trace_name: p.data ? p.data.name : null
                })),
                point_indices: points.map(p => p.pointNumber),
                curve_number: points.length > 0 ? points[0].curveNumber : null,
                event: data.event
            });
        });

        // Hover
        plotDiv.on('plotly_hover', (data) => {
            const points = data.points || [];
            pywry.emit('plotly:hover', {
                widget_type: 'chart',
                chartId: chartId,
                points: points.map(p => ({
                    curveNumber: p.curveNumber,
                    pointNumber: p.pointNumber,
                    pointIndex: p.pointIndex,
                    x: p.x,
                    y: p.y,
                    z: p.z,
                    text: p.text,
                    customdata: p.customdata,
                    data: p.data,
                    trace_name: p.data ? p.data.name : null
                })),
                point_indices: points.map(p => p.pointNumber),
                curve_number: points.length > 0 ? points[0].curveNumber : null
            });
        });

        // Selected
        plotDiv.on('plotly_selected', (data) => {
            if (!data) {
                pywry.emit('plotly:selected', { widget_type: 'chart', chartId: chartId, points: [], point_indices: [], range: null, lassoPoints: null });
                return;
            }
            const points = data.points || [];
            pywry.emit('plotly:selected', {
                widget_type: 'chart',
                chartId: chartId,
                points: points.map(p => ({
                    curveNumber: p.curveNumber,
                    pointNumber: p.pointNumber,
                    pointIndex: p.pointIndex,
                    x: p.x,
                    y: p.y,
                    z: p.z,
                    text: p.text,
                    customdata: p.customdata,
                    data: p.data,
                    trace_name: p.data ? p.data.name : null
                })),
                point_indices: points.map(p => p.pointNumber),
                range: data.range || null,
                lassoPoints: data.lassoPoints || null
            });
        });

        // Relayout
        plotDiv.on('plotly_relayout', (data) => {
            pywry.emit('plotly:relayout', {
                widget_type: 'chart',
                chartId: chartId,
                relayout_data: data
            });
        });
    }
}

// Expose globally
window.registerPyWryChart = registerPyWryChart;

(function() {
    // Helper to find chart container - look for Plotly div
    function findPlotDiv(chartId) {
        // If specific chartId provided, try to find in registry
        if (chartId && window.__PYWRY_CHARTS__ && window.__PYWRY_CHARTS__[chartId]) {
            return window.__PYWRY_CHARTS__[chartId];
        }
        // Use the most recently created chart's graph div object (set by Plotly.newPlot callback)
        if (window.__PYWRY_PLOTLY_DIV__) {
            return window.__PYWRY_PLOTLY_DIV__;
        }
        // Final fallback - querySelector (may not work for relayout without internal state)
        return document.querySelector('.js-plotly-plot');
    }

    // Helper function to process config - converts icon names to objects and event props to click handlers
    function processPlotlyConfig(config) {
        if (!config) return config;

        if (config.modeBarButtonsToAdd && Array.isArray(config.modeBarButtonsToAdd)) {
            config.modeBarButtonsToAdd = config.modeBarButtonsToAdd.map(function(btn, idx) {
                // Handle icon - could be string (Plotly icon name) or object (custom SVG)
                if (typeof btn.icon === 'string') {
                    var iconName = btn.icon;
                    if (window.Plotly && window.Plotly.Icons && window.Plotly.Icons[iconName]) {
                        btn.icon = window.Plotly.Icons[iconName];
                    } else {
                        console.warn('[PyWry Plotly] Unknown icon:', iconName, '- using fallback');
                        if (window.Plotly && window.Plotly.Icons && window.Plotly.Icons.question) {
                            btn.icon = window.Plotly.Icons.question;
                        }
                    }
                } else if (btn.icon && typeof btn.icon === 'object') {
                    if (!btn.icon.width) btn.icon.width = 1000;
                    if (!btn.icon.height) btn.icon.height = 1000;
                }

                // Convert 'event' property to 'click' function
                if (btn.event) {
                    var eventName = btn.event;
                    var eventData = btn.data || {};
                    btn.click = function(gd) {
                        if (window.pywry && window.pywry.emit) {
                            window.pywry.emit(eventName, eventData);
                        }
                    };
                    delete btn.event;
                    delete btn.data;
                }

                return btn;
            });
        }

        return config;
    }

    // Wait for pywry bridge to be ready
    function setupHandlers() {
        if (!window.pywry || !window.pywry.on) {
            setTimeout(setupHandlers, 50);
            return;
        }

        // plotly:update-figure - Full figure update
        window.pywry.on('plotly:update-figure', function(data) {
            var plotDiv = findPlotDiv(data && data.chartId);
            if (plotDiv && window.Plotly) {
                var figData = data.figure ? data.figure.data : data.data;
                var figLayout = data.figure ? data.figure.layout : data.layout;
                var rawConfig = data.config || {};

                // Extract per-theme templates before passing config to Plotly
                var userTemplateDark = rawConfig.templateDark || null;
                var userTemplateLight = rawConfig.templateLight || null;
                delete rawConfig.templateDark;
                delete rawConfig.templateLight;

                var config = Object.assign({displaylogo: false}, processPlotlyConfig(rawConfig));
                if (figData) {
                    // Merge user template with theme base (user always wins)
                    var userTemplate = null;
                    if (figLayout && figLayout.template && typeof figLayout.template === 'object') {
                        userTemplate = figLayout.template;
                        figLayout.template = null;
                    }
                    var themeName = plotDiv.__pywry_theme_template__ || 'plotly_dark';
                    if (userTemplate || userTemplateDark || userTemplateLight) {
                        figLayout = figLayout || {};
                        figLayout.template = window.__pywryMergeThemeTemplate(plotDiv, themeName, userTemplate, userTemplateDark, userTemplateLight);
                    }
                    window.Plotly.react(plotDiv, figData, figLayout || {}, config);
                }
            } else {
                console.warn('[PyWry Plotly] plotly:update-figure - no plotDiv or Plotly found');
            }
        });

        // plotly:update-layout - Partial layout update
        window.pywry.on('plotly:update-layout', function(data) {
            var plotDiv = findPlotDiv(data && data.chartId);
            if (plotDiv && window.Plotly && data && data.layout) {
                // Build update object using Plotly's dot notation for proper merging
                var layoutUpdate = {};

                Object.keys(data.layout).forEach(function(key) {
                    var value = data.layout[key];
                    // Handle title specially - use dot notation for template compatibility
                    if (key === 'title' && typeof value === 'string') {
                        layoutUpdate['title.text'] = value;
                    } else if (key === 'title' && typeof value === 'object' && value !== null) {
                        // Flatten title object to dot notation
                        Object.keys(value).forEach(function(titleKey) {
                            layoutUpdate['title.' + titleKey] = value[titleKey];
                        });
                    } else {
                        layoutUpdate[key] = value;
                    }
                });

                window.Plotly.relayout(plotDiv, layoutUpdate);
            } else {
                console.warn('[PyWry Plotly] plotly:update-layout - missing requirements', {plotDiv: !!plotDiv, Plotly: !!window.Plotly, data: data});
            }
        });

        // plotly:update-traces - Update trace data
        window.pywry.on('plotly:update-traces', function(data) {
            var plotDiv = findPlotDiv(data && data.chartId);
            if (plotDiv && window.Plotly && data && data.update) {
                window.Plotly.restyle(plotDiv, data.update, data.indices);
            } else {
                console.warn('[PyWry Plotly] plotly:update-traces - no plotDiv, Plotly, or update data');
            }
        });

        // plotly:reset-zoom - Reset chart zoom to autorange
        window.pywry.on('plotly:reset-zoom', function(data) {
            var plotDiv = findPlotDiv(data && data.chartId);
            if (plotDiv && window.Plotly) {
                window.Plotly.relayout(plotDiv, {
                    'xaxis.autorange': true,
                    'yaxis.autorange': true
                });
            } else {
                console.warn('[PyWry Plotly] plotly:reset-zoom - no plotDiv or Plotly found');
            }
        });

        // plotly:request-state - Return current chart state to Python
        window.pywry.on('plotly:request-state', function(data) {
            var chartId = data && data.chartId;
            var plotDiv = findPlotDiv(chartId);
            if (plotDiv && window.Plotly && window.pywry.emit) {
                window.pywry.emit('plotly:state-response', {
                    layout: plotDiv.layout,
                    data: plotDiv.data,
                    chartId: chartId || 'default'
                });
            } else {
                console.warn('[PyWry Plotly] plotly:request-state - cannot respond');
            }
        });

        // plotly:export-data - Trigger data export
        window.pywry.on('plotly:export-data', function(data) {
            var plotDiv = findPlotDiv(data && data.chartId);
            if (plotDiv && window.pywry.emit) {
                var exportData = [];
                if (plotDiv.data && Array.isArray(plotDiv.data)) {
                    plotDiv.data.forEach(function(trace, idx) {
                        exportData.push({
                            traceIndex: idx,
                            name: trace.name || 'trace' + idx,
                            x: trace.x,
                            y: trace.y,
                            type: trace.type
                        });
                    });
                }
                window.pywry.emit('plotly:export-response', { data: exportData });
            }
        });

        // pywry:update-theme - Theme switching
        window.pywry.on('pywry:update-theme', function(data) {
            if (data && data.theme) {
                var isDark = data.theme.includes('dark');

                // Update container classes
                var container = document.querySelector('.pywry-widget');
                if (container) {
                    container.classList.remove('pywry-theme-dark', 'pywry-theme-light');
                    container.classList.add(isDark ? 'pywry-theme-dark' : 'pywry-theme-light');
                }

                // Update chart template (theme base + user overrides)
                // Use relayout — NOT newPlot — so Plotly re-derives all
                // template defaults (font colors, backgrounds, axis colours)
                // without carrying stale values from the old layout.
                var plotDiv = findPlotDiv();
                if (plotDiv && window.Plotly && plotDiv.data && window.PYWRY_PLOTLY_TEMPLATES) {
                    var templateName = isDark ? 'plotly_dark' : 'plotly_white';
                    var mergedTemplate = window.__pywryMergeThemeTemplate(plotDiv, templateName);
                    if (window.__pywryStripThemeColors) window.__pywryStripThemeColors(plotDiv);
                    window.Plotly.relayout(plotDiv, { template: mergedTemplate });
                }
            }
        });
    }

    // Start setup when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', setupHandlers);
    } else {
        setupHandlers();
    }
})();
