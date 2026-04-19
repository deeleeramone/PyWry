// ---------------------------------------------------------------------------
// Series type map: type name → LightweightCharts series constructor (v5 API)
// ---------------------------------------------------------------------------

var SERIES_TYPES = {
    'Candlestick': 'CandlestickSeries',
    'Line':        'LineSeries',
    'Area':        'AreaSeries',
    'Bar':         'BarSeries',
    'Baseline':    'BaselineSeries',
    'Histogram':   'HistogramSeries',
};

var LEGACY_ADD_SERIES_METHODS = {
    'Candlestick': 'addCandlestickSeries',
    'Line': 'addLineSeries',
    'Area': 'addAreaSeries',
    'Bar': 'addBarSeries',
    'Baseline': 'addBaselineSeries',
    'Histogram': 'addHistogramSeries',
};

function _tvAddSeriesCompat(chart, seriesType, seriesOptions, paneIndex) {
    var constructorName = SERIES_TYPES[seriesType] || 'LineSeries';
    var seriesCtor = LightweightCharts[constructorName];
    var hasPaneIndex = typeof paneIndex === 'number' && isFinite(paneIndex);
    var created;

    // Preferred v5 API path (series definition object)
    if (seriesCtor) {
        created = hasPaneIndex
            ? chart.addSeries(seriesCtor, seriesOptions, paneIndex)
            : chart.addSeries(seriesCtor, seriesOptions);
        if (hasPaneIndex && paneIndex > 0 && created && typeof created.moveToPane === 'function') {
            try { created.moveToPane(paneIndex); } catch (e) {}
        }
        return created;
    }

    // Fallback for older/alternate builds exposing dedicated add*Series APIs
    var methodName = LEGACY_ADD_SERIES_METHODS[seriesType] || 'addLineSeries';
    if (typeof chart[methodName] === 'function') {
        created = chart[methodName](seriesOptions);
        if (hasPaneIndex && paneIndex > 0 && created && typeof created.moveToPane === 'function') {
            try { created.moveToPane(paneIndex); } catch (e2) {}
        }
        return created;
    }

    throw new Error(
        '[pywry:tvchart] Unsupported series API for type ' + seriesType +
        ' (missing constructor ' + constructorName + ' and method ' + methodName + ')'
    );
}

function _tvReserveVolumePane(entry, seriesId) {
    if (!entry._volumePaneBySeries) entry._volumePaneBySeries = {};
    var sid = seriesId || 'main';
    if (entry._volumePaneBySeries[sid] !== undefined) {
        return entry._volumePaneBySeries[sid];
    }

    var paneIndex;
    if (sid === 'main') {
        // Keep the first subplot consistently dedicated to main volume.
        paneIndex = 1;
    } else {
        if (!entry._nextPane || entry._nextPane < 2) entry._nextPane = 2;
        paneIndex = entry._nextPane;
        entry._nextPane += 1;
    }

    entry._volumePaneBySeries[sid] = paneIndex;
    if (!entry._nextPane || entry._nextPane <= paneIndex) {
        entry._nextPane = paneIndex + 1;
    }
    return paneIndex;
}

function _tvApplyDefaultVolumePaneHeight(entry, paneIndex) {
    if (!entry || !entry.chart) return;
    var targetPane = typeof paneIndex === 'number' ? paneIndex : _tvReserveVolumePane(entry, 'main');
    var containerHeight = entry.container ? (entry.container.clientHeight || 0) : 0;
    // Keep volume visible but smaller so divider/axis labels stay readable.
    var desiredHeight = Math.round(Math.max(64, Math.min(132, containerHeight * 0.12)));
    try {
        if (typeof entry.chart.panes === 'function') {
            var panes = entry.chart.panes();
            if (panes && panes[targetPane] && typeof panes[targetPane].setHeight === 'function') {
                panes[targetPane].setHeight(desiredHeight);
            }
        }
    } catch (e) {}
}

function _tvEnforceMainScaleDividerClearance(entry, preferredTop, preferredBottom) {
    if (!entry || !entry.chart) return;
    var hasVolumePane = !!(entry.volumeMap && entry.volumeMap.main);
    var side = _tvResolveScalePlacement(entry);
    var top = isFinite(preferredTop) ? preferredTop : 0.1;
    var bottom = isFinite(preferredBottom) ? preferredBottom : 0.08;
    if (hasVolumePane) {
        // Reserve extra room above the pane divider for the lowest price label.
        bottom = Math.max(bottom, 0.14);
    }
    try {
        entry.chart.priceScale(side).applyOptions({
            scaleMargins: { top: top, bottom: bottom },
        });
    } catch (e) {}
}

// ---------------------------------------------------------------------------
// Core: create / update / destroy chart
// ---------------------------------------------------------------------------

/**
 * Create a Lightweight Chart inside the given container.
 *
 * @param {string} chartId - Unique chart identifier
 * @param {HTMLElement} container - DOM element to render into
 * @param {Object} payload - { chartOptions, series, volume, seriesType, seriesOptions, volumeOptions }
 *   - series: [ { bars: [...], volume: [...], seriesType, seriesId } , ... ]
 *     OR legacy flat: { chartOptions, bars, volume, seriesType, ... }
 */
window.PYWRY_TVCHART_CREATE = function(chartId, container, payload) {
    try {
    // Destroy previous chart if exists
    if (window.__PYWRY_TVCHARTS__[chartId] && window.__PYWRY_TVCHARTS__[chartId].chart) {
        window.__PYWRY_TVCHARTS__[chartId].chart.remove();
    }

    var theme = _tvDetectTheme();
    var chartOptions = _tvBuildChartOptions(payload.chartOptions || null, theme);
    var measured = _tvMeasureContainerSize(container);

    // Prefer auto-size unless explicit dimensions are provided.
    if (chartOptions.width || chartOptions.height) {
        chartOptions.autoSize = false;
        if (!chartOptions.width || chartOptions.width <= 0) {
            chartOptions.width = measured.width;
        }
        if (!chartOptions.height || chartOptions.height <= 0) {
            chartOptions.height = measured.height;
        }
    } else {
        // WebView layout timing can report 0x0 at first paint; fallback to
        // explicit dimensions in that case so the series remains visible.
        if ((container.clientWidth || 0) <= 0 || (container.clientHeight || 0) <= 0) {
            chartOptions.autoSize = false;
            chartOptions.width = measured.width;
            chartOptions.height = measured.height;
        } else {
            chartOptions.autoSize = true;
        }
    }

    var chart = LightweightCharts.createChart(container, chartOptions);
    var crect = container.getBoundingClientRect();
    if (crect.width > 0 && crect.height > 0 && typeof chart.resize === 'function') {
        chart.resize(Math.floor(crect.width), Math.floor(crect.height));
    }

    var entry = {
        chart: chart,
        container: container,
        chartId: chartId,
        uiRoot: _tvResolveUiRootFromElement(container),
        seriesMap: {},       // seriesId → ISeriesApi
        volumeMap: {},       // seriesId → ISeriesApi (volume histogram)
        _legendSeriesColors: {},
        _seriesRawData: {},  // seriesId -> normalized bars
        _seriesDisplayData: {}, // seriesId -> currently displayed bars (may be filtered)
        _seriesCanonicalRawData: {}, // seriesId -> canonical source bars (prefer OHLC)
        payload: payload,    // stash for theme-switch rebuild
        theme: theme,
        _volumePaneBySeries: {},
        _customPriceScaleIds: {},
        _chartPrefs: {
            logScale: false,
            autoScale: true,
            gridVisible: true,
            crosshairEnabled: false,
        },
        // One-shot callbacks that fire once seriesMap contains a main
        // series (registered via entry.whenMainSeriesReady).  Needed
        // because the destroy-recreate flow has to chain post-CREATE
        // work (re-apply display style, etc.) but datafeed mode adds
        // the series inside an async resolveSymbol callback — polling
        // for seriesMap.main would be a race-condition workaround.
        _mainSeriesReadyCallbacks: [],
    };
    entry.whenMainSeriesReady = function(cb) {
        if (typeof cb !== 'function') return;
        if (entry.seriesMap && (entry.seriesMap.main || entry.seriesMap['series-0'])) {
            try { cb(); } catch (e) {}
            return;
        }
        entry._mainSeriesReadyCallbacks.push(cb);
    };

    // Normalise: support both multi-series array and legacy flat format
    var seriesList = payload.series;
    if (!seriesList || !Array.isArray(seriesList)) {
        // Legacy flat format → wrap into single series
        seriesList = [{
            seriesId: 'main',
            bars: payload.bars || [],
            volume: payload.volume || [],
            seriesType: payload.seriesType || 'Candlestick',
            seriesOptions: payload.seriesOptions || {},
        }];
    }

    // ---- Register entry early so event handlers can find it ----
    window.__PYWRY_TVCHARTS__[chartId] = entry;

    // Store bridge reference for per-widget isolation in notebooks.
    // Each anywidget stores its bridge on the .pywry-widget container.
    var _widgetEl = container.closest && container.closest('.pywry-widget');
    entry.bridge = (_widgetEl && _widgetEl._pywryInstance) ? _widgetEl._pywryInstance : (window.pywry || null);

    if (payload.useDatafeed) {
        // Datafeed mode — series populated asynchronously via the Datafeed API
        _tvInitDatafeedMode(entry, seriesList, theme);
    } else {
        // Static data mode — bars provided inline in the payload
        for (var i = 0; i < seriesList.length; i++) {
            var s = seriesList[i];
            var sType = s.seriesType || 'Candlestick';
            var sOptions = _tvBuildSeriesOptions(s.seriesOptions || {}, sType, theme);

            // For overlay/compare series (not first), use a separate price scale
            if (i > 0) {
                sOptions.priceScaleId = s.seriesId || ('overlay-' + i);
                _tvRegisterCustomPriceScaleId(entry, sOptions.priceScaleId);
                if (!sOptions.priceFormat) {
                    sOptions.priceFormat = { type: 'price', precision: 2, minMove: 0.01 };
                }
            }

            // For Baseline, compute a baseValue at the 50% level of the data range.
            if (sType === 'Baseline' && !sOptions.baseValue) {
                var bBars = Array.isArray(s.bars) ? s.bars : [];
                sOptions.baseValue = { type: 'price', price: _tvComputeBaselineValue(bBars, 50), _level: 50 };
            }

            var series = _tvAddSeriesCompat(chart, sType, sOptions);
            var sourceBars = Array.isArray(s.bars) ? s.bars : [];
            var normalizedBars = _tvNormalizeBarsForSeriesType(sourceBars, sType);
            series.setData(normalizedBars);
            var sid = s.seriesId || ('series-' + i);
            entry.seriesMap[sid] = series;
            entry._seriesRawData[sid] = normalizedBars;
            if (_tvIsMainSeriesId(sid) && series && typeof series.moveToPane === 'function') {
                try { series.moveToPane(0); } catch (e) {}
            }
            if (_tvIsMainSeriesId(sid) || sid === 'series-0') {
                _tvFireMainSeriesReady(entry);
            }
            if (_tvLooksLikeOhlcBars(sourceBars)) {
                entry._seriesCanonicalRawData[sid] = sourceBars;
            }
            entry._legendSeriesColors[sid] = (
                sOptions.color ||
                sOptions.lineColor ||
                sOptions.upColor ||
                sOptions.borderUpColor ||
                '#4c87ff'
            );

            // Store raw data for indicator computation (first / main series)
            if (i === 0 && sourceBars.length > 0) {
                entry._rawData = _tvLooksLikeOhlcBars(sourceBars) ? sourceBars : normalizedBars;
            }

            // Auto-enable volume unless caller explicitly disables it.
            // Accept an explicit volume array, or extract from bars' volume field.
            if (payload && payload.enableVolume !== false) {
                var volData = (s.volume && s.volume.length > 0) ? s.volume : _tvExtractVolumeFromBars(sourceBars, theme, entry);
                if (volData && volData.length > 0) {
                    var volOptions = _tvBuildVolumeOptions(s, theme);
                    _tvRegisterCustomPriceScaleId(entry, volOptions.priceScaleId);
                    var vSid = s.seriesId || ('series-' + i);
                    var vPaneIndex = _tvReserveVolumePane(entry, vSid);
                    var volSeries = _tvAddSeriesCompat(chart, 'Histogram', volOptions, vPaneIndex);
                    volSeries.setData(volData);
                    entry.volumeMap[vSid] = volSeries;
                    if (vSid === 'main') {
                        _tvApplyDefaultVolumePaneHeight(entry, vPaneIndex);
                        _tvEnforceMainScaleDividerClearance(entry, 0.1, 0.08);
                    }
                }
            }
        }

        // Apply the default time-range from the selected bottom tab, or fitContent.
        // Deferred: bottom toolbar HTML is rendered AFTER chart content in the DOM,
        // so the tab elements don't exist yet when this script executes synchronously.
        // Runs at setTimeout(150) to execute AFTER _tvScheduleVisibilityRecovery
        // (which resizes the chart at 0ms, double-rAF, and 120ms).
        (function(e, c) {
            function applyDefault() {
                // Destroy-recreate flows (interval-change / symbol-change)
                // hand us a pre-destroy zoom to restore — honour it instead
                // of falling through to fitContent, which would wipe the
                // user's zoom every time the data interval changes.
                var preserved = e._preservedVisibleTimeRange;
                if (preserved && preserved.from != null && preserved.to != null) {
                    try {
                        c.timeScale().setVisibleRange({
                            from: preserved.from,
                            to: preserved.to,
                        });
                        delete e._preservedVisibleTimeRange;
                        return;
                    } catch (err) {
                        delete e._preservedVisibleTimeRange;
                    }
                }
                var sel = document.querySelector('.pywry-tab.pywry-tab-active[data-target-interval]');
                if (sel) {
                    var range = sel.getAttribute('data-value');
                    if (range && range !== 'all') {
                        _tvApplyTimeRangeSelection(e, range);
                        return;
                    }
                }
                c.timeScale().fitContent();
            }
            // Check if a non-all time range tab exists.  Set the flag early
            // so _tvScheduleVisibilityRecovery skips fitContent.
            var earlyTab = document.querySelector('.pywry-tab.pywry-tab-active[data-target-interval]');
            if (!earlyTab) {
                // Tab not in DOM yet (still parsing) — will exist after DOMContentLoaded.
                // Peek at the HTML to decide if we should suppress fitContent.
                e._initialRangeApplied = true;
            } else {
                var earlyRange = earlyTab.getAttribute('data-value');
                if (earlyRange && earlyRange !== 'all') {
                    e._initialRangeApplied = true;
                }
            }
            // Run after visibility recovery (which fires at 0, ~32, and 120ms).
            setTimeout(applyDefault, 150);
        })(entry, chart);
    }

    // (entry already stored above)
    _tvApplyHoverReadoutMode(entry);
    _tvScheduleVisibilityRecovery(entry);

    // Provision the drawing overlay up front so the canvas element is
    // part of every live chart, not lazy-created on first tool
    // selection.  Tools that toggle drawing visibility / lock / state
    // export rely on the overlay existing; requiring a prior draw
    // action to instantiate it left those paths broken whenever the
    // user / caller hadn't drawn yet.
    if (typeof _tvEnsureDrawingLayer === "function") {
        try { _tvEnsureDrawingLayer(chartId); } catch (e) { /* best-effort */ }
    }

    // Register with unified component registry
    window.__PYWRY_COMPONENTS__[chartId] = {
        type: 'tvchart',
        getData: function() {
            return _tvExportState(chartId);
        },
    };

    // Wire up user interaction events → Python
    _tvSetupEventBridge(chartId, chart);

        // Crosshair/mousemove → legend values (no Python round-trip needed)
        chart.subscribeCrosshairMove(function(param) {
            _tvUpdateIndicatorLegendValues(chartId, param);
            _tvRenderHoverLegend(chartId, param || null);
        });
        _tvRenderHoverLegend(chartId, null);

    // Setup legend controls (context menus, eye/settings/remove buttons,
    // compare-series rows, crosshair legend updater, etc.)
    if (typeof _tvSetupLegendControls === 'function') {
        _tvSetupLegendControls(chartId);
    }

    // Apply persisted settings on initial load (description mode, crosshair, grid, etc.)
    // First, check if there's a persisted custom default template to seed initial settings.
    if (typeof _tvBuildCurrentSettings === 'function' && typeof _tvApplySettingsToChart === 'function') {
        var initSettings = _tvBuildCurrentSettings(entry);
        // If user has a custom default template saved, use that as the initial settings
        if (typeof _tvLoadSettingsDefaultTemplateId === 'function' &&
            typeof _tvLoadCustomSettingsTemplate === 'function') {
            var templateId = _tvLoadSettingsDefaultTemplateId(chartId);
            if (templateId === 'custom') {
                var customTemplate = _tvLoadCustomSettingsTemplate(chartId);
                if (customTemplate) {
                    // Merge custom template over defaults so all keys are present
                    var tKeys = Object.keys(customTemplate);
                    for (var ti = 0; ti < tKeys.length; ti++) {
                        initSettings[tKeys[ti]] = customTemplate[tKeys[ti]];
                    }
                }
            }
        }
        _tvApplySettingsToChart(chartId, entry, initSettings);
        // _tvApplySettingsToChart applies a default 50% opacity to the background
        // colour, which breaks themes (especially light where 50% white looks grey).
        // For fresh charts with no user-customised bg from a saved template,
        // restore the theme palette background at full opacity — identical to what
        // _tvApplyThemeToAll does when switching themes at runtime.
        var _hasCustomTemplateBg = !!(customTemplate && customTemplate['Background-Color']);
        if (!_hasCustomTemplateBg) {
            // Restore full theme palette — _tvApplySettingsToChart mangles
            // background with 50% opacity and may pick up stale text/grid
            // colors.  This mirrors what _tvApplyThemeToAll does at runtime.
            var _createPalette = TVCHART_THEMES._get(entry.theme || 'dark');
            entry.chart.applyOptions({
                layout: {
                    background: { type: LightweightCharts.ColorType.Solid, color: _createPalette.background },
                    textColor: _createPalette.textColor,
                },
                grid: _createPalette.grid,
                rightPriceScale: { borderColor: _createPalette.grid.vertLines.color },
                timeScale: { borderColor: _createPalette.grid.vertLines.color },
            });
        }
        // In datafeed mode the main series doesn't exist yet (created async),
        // so stash the settings for deferred application after series creation.
        if (payload && payload.useDatafeed) {
            entry._pendingCustomDefaults = initSettings;
        }
        // Persist loaded settings into _chartPrefs so settings panel shows correct values
        if (entry._chartPrefs) {
            var _s = initSettings;
            entry._chartPrefs.colorBarsBasedOnPrevClose = !!_s['Color bars based on previous close'];
            entry._chartPrefs.bodyVisible = _s['Body'] !== false;
            entry._chartPrefs.bodyUpColor = _s['Body-Up Color'] || entry._chartPrefs.bodyUpColor;
            entry._chartPrefs.bodyDownColor = _s['Body-Down Color'] || entry._chartPrefs.bodyDownColor;
            entry._chartPrefs.bordersVisible = _s['Borders'] !== false;
            entry._chartPrefs.bordersUpColor = _s['Borders-Up Color'] || entry._chartPrefs.bordersUpColor;
            entry._chartPrefs.bordersDownColor = _s['Borders-Down Color'] || entry._chartPrefs.bordersDownColor;
            entry._chartPrefs.wickVisible = _s['Wick'] !== false;
            entry._chartPrefs.wickUpColor = _s['Wick-Up Color'] || entry._chartPrefs.wickUpColor;
            entry._chartPrefs.wickDownColor = _s['Wick-Down Color'] || entry._chartPrefs.wickDownColor;
            entry._chartPrefs.crosshairEnabled = _s['Crosshair-Enabled'] === true;
            entry._chartPrefs.crosshairColor = _s['Crosshair-Color'] || entry._chartPrefs.crosshairColor;
            entry._chartPrefs.gridVisible = _s['Grid lines'] !== 'Hidden';
            entry._chartPrefs.gridMode = _s['Grid lines'] || 'Vert and horz';
            entry._chartPrefs.gridColor = _s['Grid-Color'] || entry._chartPrefs.gridColor;
            entry._chartPrefs.backgroundColor = _hasCustomTemplateBg ? _s['Background-Color'] : '';
            entry._chartPrefs.textColor = _s['Text-Color'] || entry._chartPrefs.textColor;
            entry._chartPrefs.linesColor = _s['Lines-Color'] || entry._chartPrefs.linesColor;
            entry._chartPrefs.dayOfWeekOnLabels = _s['Day of week on labels'] !== false;
            entry._chartPrefs.dateFormat = _s['Date format'] || entry._chartPrefs.dateFormat;
            entry._chartPrefs.timeHoursFormat = _s['Time hours format'] || entry._chartPrefs.timeHoursFormat;
            entry._chartPrefs.paneSeparatorsColor = _s['Pane-Separators-Color'] || entry._chartPrefs.paneSeparatorsColor;
            entry._chartPrefs.symbolMode = _s['Symbol'] || entry._chartPrefs.symbolMode;
            entry._chartPrefs.symbolColor = _s['Symbol color'] || entry._chartPrefs.symbolColor;
            entry._chartPrefs.settings = _s;
        }
    }

    // Defer drawing-layer initialization until a drawing tool is actually used.
    // This avoids an extra overlay canvas covering the chart in some webview paths.
    } catch (err) {
        console.error('[pywry:tvchart] create failed:', err);
        if (container) {
            container.innerHTML =
                '<div style="padding:12px;color:#ef5350;font:12px monospace;white-space:pre-wrap;">' +
                'TVChart create failed:\n' +
                String(err && (err.stack || err.message || err)) +
                '</div>';
        }
    }
};

window.PYWRY_TVCHART_RENDER = function(chartId, container, payload) {
    if (!container) return;

    function createFallback() {
        var copied = _tvMerge(payload || {}, {
            chartOptions: {
                autoSize: false,
                width: Math.max(container.clientWidth || 0, 300),
                height: Math.max(container.clientHeight || 0, 420),
            },
        });
        window.PYWRY_TVCHART_CREATE(chartId, container, copied);
    }

    window.PYWRY_TVCHART_CREATE(chartId, container, payload);

    // If no chart canvas appears, force a sized fallback render.
    setTimeout(function() {
        if (!container.querySelector('canvas')) {
            container.innerHTML = '';
            createFallback();
        }
    }, 200);
};

/**
 * Build volume histogram series options.
 */
function _tvBuildVolumeOptions(seriesEntry, theme) {
    var palette = TVCHART_THEMES._get(theme || 'dark');
    return _tvMerge({
        priceFormat: { type: 'volume' },
        priceScaleId: 'volume',
        scaleMargins: { top: 0.8, bottom: 0 },
        color: palette.volumeUp,
        lastValueVisible: false,
        priceLineVisible: false,
    }, seriesEntry.volumeOptions || {});
}

/**
 * Extract volume histogram data from OHLCV bars.
 *
 * Bars are expected to carry a numeric `volume` field.  The function
 * produces the `{time, value, color}` array that the Histogram series
 * needs, colouring each bar up/down from the theme palette.
 */
function _tvExtractVolumeFromBars(bars, theme, entry) {
    if (!Array.isArray(bars) || bars.length === 0) return null;
    // Quick check: first bar must have a numeric volume
    var first = bars[0];
    if (first.volume == null && first.Volume == null && first.vol == null) return null;
    var palette = TVCHART_THEMES._get(theme || 'dark');
    var prefs = (entry && entry._volumeColorPrefs) || {};
    var upColor = prefs.upColor || palette.volumeUp;
    var downColor = prefs.downColor || palette.volumeDown || upColor;
    var usePrevClose = !!prefs.colorBasedOnPrevClose;
    var result = [];
    for (var i = 0; i < bars.length; i++) {
        var b = bars[i];
        var v = b.volume != null ? b.volume : (b.Volume != null ? b.Volume : b.vol);
        if (v == null || isNaN(v)) continue;
        var isUp;
        if (usePrevClose && i > 0) {
            var pc = bars[i - 1].close != null ? bars[i - 1].close : bars[i - 1].Close;
            isUp = (pc != null && b.close != null) ? b.close >= pc : true;
        } else {
            isUp = (b.close != null && b.open != null) ? b.close >= b.open : true;
        }
        result.push({ time: b.time, value: +v, color: isUp ? upColor : downColor });
    }
    return result.length > 0 ? result : null;
}

/**
 * Update bar data for an existing chart.
 *
 * @param {string} chartId
 * @param {Object} payload - { seriesId, bars, volume } or { bars, volume } for main series
 */
window.PYWRY_TVCHART_UPDATE = function(chartId, payload) {
    var resolved = _tvResolveChartEntry(chartId);
    var entry = resolved ? resolved.entry : null;
    if (!entry) {
        console.warn('[pywry:tvchart] update: chart not found:', chartId);
        return;
    }

    var seriesId = payload.seriesId || 'main';
    var series = entry.seriesMap[seriesId];
    if (series && payload.bars) {
        var seriesType = _tvGuessSeriesType(series);
        if (!entry._seriesCanonicalRawData) entry._seriesCanonicalRawData = {};
        var incomingBars = Array.isArray(payload.bars) ? payload.bars : [];
        if (_tvLooksLikeOhlcBars(incomingBars)) {
            entry._seriesCanonicalRawData[seriesId] = incomingBars;
        }
        var canonicalBars = entry._seriesCanonicalRawData[seriesId];
        var sourceBars = (Array.isArray(canonicalBars) && canonicalBars.length) ? canonicalBars : incomingBars;
        var bars = _tvNormalizeBarsForSeriesType(sourceBars, seriesType);
        series.setData(bars);
        entry._seriesRawData[seriesId] = bars;
        _tvUpsertPayloadSeries(entry, seriesId, { bars: sourceBars, seriesType: seriesType });

        if (seriesId === 'main') {
            entry._rawData = sourceBars;
            if (entry.payload) {
                if (payload.interval) {
                    entry.payload.interval = payload.interval;
                    _tvSetIntervalUi(resolved ? resolved.chartId : chartId, payload.interval);
                }
                if (entry.payload.series && Array.isArray(entry.payload.series) && entry.payload.series[0]) {
                    entry.payload.series[0].bars = sourceBars;
                } else {
                    entry.payload.bars = sourceBars;
                }
            }
        }


    if (seriesId === 'main' && payload.interval && entry.payload) {
        entry.payload.interval = payload.interval;
        _tvSetIntervalUi(resolved ? resolved.chartId : chartId, payload.interval);
    }
        _tvRecomputeIndicatorsForChart(resolved ? resolved.chartId : chartId, seriesId);
    }

    var volSeries = entry.volumeMap[seriesId];
    if (volSeries) {
        var volData = (payload.volume && payload.volume.length > 0)
            ? payload.volume
            : _tvExtractVolumeFromBars(payload.bars, entry.theme, entry);
        if (volData && volData.length > 0) {
            volSeries.setData(volData);
            _tvUpsertPayloadSeries(entry, seriesId, { volume: volData });
            if (seriesId === 'main' && entry.payload) {
                if (entry.payload.series && Array.isArray(entry.payload.series) && entry.payload.series[0]) {
                    entry.payload.series[0].volume = volData;
                } else {
                    entry.payload.volume = volData;
                }
            }
        }
    }

    if (payload.fitContent !== false) {
        entry.chart.timeScale().fitContent();
    }
    _tvRenderHoverLegend(resolved ? resolved.chartId : chartId, null);
};

/**
 * Stream a single bar update (real-time).
 *
 * @param {string} chartId
 * @param {Object} payload - { seriesId, bar, volume }
 */
window.PYWRY_TVCHART_STREAM = function(chartId, payload) {
    var resolved = _tvResolveChartEntry(chartId);
    var entry = resolved ? resolved.entry : null;
    if (!entry) return;

    var seriesId = payload.seriesId || 'main';
    var series = entry.seriesMap[seriesId];
    if (series && payload.bar) {
        var currentType = _tvGuessSeriesType(series);
        if (!entry._seriesCanonicalRawData) entry._seriesCanonicalRawData = {};
        var canonical = entry._seriesCanonicalRawData[seriesId];
        if (!Array.isArray(canonical)) canonical = [];
        var pbar = payload.bar || {};

        if (pbar.open !== undefined && pbar.high !== undefined && pbar.low !== undefined && pbar.close !== undefined) {
            if (canonical.length > 0 && canonical[canonical.length - 1] && canonical[canonical.length - 1].time === pbar.time) {
                canonical[canonical.length - 1] = pbar;
            } else {
                canonical.push(pbar);
            }
            entry._seriesCanonicalRawData[seriesId] = canonical;
        }

        var streamSource = (Array.isArray(entry._seriesCanonicalRawData[seriesId]) && entry._seriesCanonicalRawData[seriesId].length)
            ? entry._seriesCanonicalRawData[seriesId][entry._seriesCanonicalRawData[seriesId].length - 1]
            : pbar;
        var normalizedBar = _tvNormalizeSingleBarForSeriesType(streamSource, currentType);
        if (!normalizedBar) return;
        series.update(normalizedBar);

        if (!entry._seriesRawData[seriesId]) entry._seriesRawData[seriesId] = [];
        var arr = entry._seriesRawData[seriesId];
        if (arr.length > 0 && arr[arr.length - 1] && arr[arr.length - 1].time === normalizedBar.time) {
            arr[arr.length - 1] = normalizedBar;
        } else {
            arr.push(normalizedBar);
        }
        if (seriesId === 'main') {
            entry._rawData = (entry._seriesCanonicalRawData[seriesId] && entry._seriesCanonicalRawData[seriesId].length)
                ? entry._seriesCanonicalRawData[seriesId]
                : arr;
        }
        _tvUpsertPayloadSeries(entry, seriesId, {
            bars: (entry._seriesCanonicalRawData[seriesId] && entry._seriesCanonicalRawData[seriesId].length)
                ? entry._seriesCanonicalRawData[seriesId]
                : arr,
            seriesType: _tvGuessSeriesType(series),
        });
        _tvRecomputeIndicatorsForChart(resolved ? resolved.chartId : chartId, seriesId);
        _tvRenderHoverLegend(resolved ? resolved.chartId : chartId, null);
    }

    var volSeries = entry.volumeMap[seriesId];
    if (volSeries && payload.volume) {
        volSeries.update(payload.volume);
    }
};

/**
 * Destroy a chart instance and clean up.
 */
window.PYWRY_TVCHART_DESTROY = function(chartId) {
    var resolved = _tvResolveChartEntry(chartId);
    var entry = resolved ? resolved.entry : null;
    if (!entry) return;

    // Unsubscribe all active datafeed bar subscriptions
    if (entry._datafeedSubscriptions) {
        var subKeys = Object.keys(entry._datafeedSubscriptions);
        for (var i = 0; i < subKeys.length; i++) {
            var guid = entry._datafeedSubscriptions[subKeys[i]];
            if (guid) _tvDatafeedUnsubscribeBars(guid);
        }
    }

    // Stop exchange clock interval
    if (entry._clockInterval) {
        clearInterval(entry._clockInterval);
        entry._clockInterval = null;
    }

    try { entry.chart.remove(); } catch (e) { /* already removed */ }
    delete window.__PYWRY_TVCHARTS__[chartId];
    delete window.__PYWRY_COMPONENTS__[chartId];
};

// ---------------------------------------------------------------------------
// Theme switching
// ---------------------------------------------------------------------------

/**
 * Re-apply theme to all TV charts (called on pywry:update-theme).
 */
function _tvApplyThemeToChart(chartId, newTheme) {
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (!entry || !entry.chart) return;

    entry.theme = newTheme;
    var palette = TVCHART_THEMES._get(newTheme || 'dark');

    // Update chart layout, grid, and scale borders
    // Crosshair mode stays Normal (hover readout always active);
    // only lines visibility respects the user setting.
    var _chPrefs = (entry._chartPrefs && entry._chartPrefs.settings) || {};
    var _chEnabled = _chPrefs['Crosshair-Enabled'] === true;
    var _chColor = palette.crosshair.vertLine ? palette.crosshair.vertLine.color : undefined;
    entry.chart.applyOptions({
        layout: {
            background: { type: LightweightCharts.ColorType.Solid, color: palette.background },
            textColor: palette.textColor,
        },
        grid: palette.grid,
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
            vertLine: { color: _chColor, visible: _chEnabled, labelVisible: true, style: 2, width: 1 },
            horzLine: { color: _chColor, visible: _chEnabled, labelVisible: _chEnabled, style: 2, width: 1 },
        },
        rightPriceScale: { borderColor: palette.grid.vertLines.color },
        timeScale: { borderColor: palette.grid.vertLines.color },
    });

    // Update main/compare series with theme colours (skip indicator series)
    var sKeys = Object.keys(entry.seriesMap);
    for (var j = 0; j < sKeys.length; j++) {
        var sid = sKeys[j];
        // Indicator series have their own colours — don't override them
        if (typeof _activeIndicators !== 'undefined' && _activeIndicators[sid]) continue;
        var sType = _tvGuessSeriesType(entry.seriesMap[sid]);
        var sOpts = _tvBuildSeriesOptions({}, sType, newTheme);
        entry.seriesMap[sid].applyOptions(sOpts);
    }

    // Update volume series colours — reset custom color prefs to new theme defaults
    // but preserve non-color settings (colorBasedOnPrevClose, MA settings, etc.)
    if (entry._volumeColorPrefs) {
        delete entry._volumeColorPrefs.upColor;
        delete entry._volumeColorPrefs.downColor;
        delete entry._volumeColorPrefs.volumeMAColor;
        delete entry._volumeColorPrefs.smoothedMAColor;
    }
    var vKeys = Object.keys(entry.volumeMap);
    for (var k = 0; k < vKeys.length; k++) {
        entry.volumeMap[vKeys[k]].applyOptions({ color: palette.volumeUp });
    }
    // Re-colour volume bar data so up/down bars use new theme palette
    if (entry._rawData && Array.isArray(entry._rawData) && entry._rawData.length > 0) {
        var volUpC = palette.volumeUp;
        var volDownC = palette.volumeDown || volUpC;
        for (var vk = 0; vk < vKeys.length; vk++) {
            var volS = entry.volumeMap[vKeys[vk]];
            var volBars = [];
            for (var vi = 0; vi < entry._rawData.length; vi++) {
                var vb = entry._rawData[vi];
                var vv = vb.volume != null ? vb.volume : (vb.Volume != null ? vb.Volume : vb.vol);
                if (vv == null || isNaN(vv)) continue;
                var vIsUp = (vb.close != null && vb.open != null) ? vb.close >= vb.open : true;
                volBars.push({ time: vb.time, value: +vv, color: vIsUp ? volUpC : volDownC });
            }
            if (volBars.length > 0) volS.setData(volBars);
        }
    }
}

function _tvApplyThemeToAll(newTheme) {
    var ids = Object.keys(window.__PYWRY_TVCHARTS__);
    for (var i = 0; i < ids.length; i++) {
        _tvApplyThemeToChart(ids[i], newTheme);
    }
}

/**
 * Best-effort type detection from series API options.
 */
function _tvGuessSeriesType(seriesApi) {
    try {
        var opts = seriesApi.options();
        if (opts.upColor !== undefined && opts.wickUpColor !== undefined) return 'Candlestick';
        if (opts.upColor !== undefined) return 'Bar';
        if (opts.topColor !== undefined) return 'Area';
        if (opts.topLineColor !== undefined) return 'Baseline';
        if (opts.color !== undefined && opts.base !== undefined) return 'Histogram';
    } catch (e) { /* ignore */ }
    return 'Line';
}

// ---------------------------------------------------------------------------
// Event bridge: chart interactions → Python
// ---------------------------------------------------------------------------

function _tvSetupEventBridge(chartId, chart) {
    var bridge = _tvGetBridge(chartId);
    if (!bridge) return;

    // Crosshair move (throttled)
    var lastCrosshairEmit = 0;
    chart.subscribeCrosshairMove(function(param) {
        var now = Date.now();
        if (now - lastCrosshairEmit < 100) return; // 10 fps throttle
        lastCrosshairEmit = now;

        if (!param.time) return;

        var prices = {};
        var seriesKeys = Object.keys(window.__PYWRY_TVCHARTS__[chartId].seriesMap);
        for (var i = 0; i < seriesKeys.length; i++) {
            var s = window.__PYWRY_TVCHARTS__[chartId].seriesMap[seriesKeys[i]];
            var data = param.seriesData ? param.seriesData.get(s) : null;
            if (data) {
                prices[seriesKeys[i]] = data;
            }
        }

        bridge.emit('tvchart:crosshair-move', {
            chartId: chartId,
            time: param.time,
            point: param.point,
            prices: prices,
        });
    });

    // Click
    chart.subscribeClick(function(param) {
        if (!param.time) return;
        bridge.emit('tvchart:click', {
            chartId: chartId,
            time: param.time,
            point: param.point,
        });
    });

    // Visible range change
    chart.timeScale().subscribeVisibleLogicalRangeChange(function(range) {
        if (!range) return;
        bridge.emit('tvchart:visible-range-change', {
            chartId: chartId,
            from: range.from,
            to: range.to,
        });
    });
}

// ---------------------------------------------------------------------------
// State export
// ---------------------------------------------------------------------------

function _tvExportState(chartId) {
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (!entry) return null;

    var seriesData = {};
    var sKeys = Object.keys(entry.seriesMap);
    for (var i = 0; i < sKeys.length; i++) {
        seriesData[sKeys[i]] = {
            type: _tvGuessSeriesType(entry.seriesMap[sKeys[i]]),
        };
    }

    var logicalRange;
    var timeRange;
    try { logicalRange = entry.chart.timeScale().getVisibleLogicalRange(); } catch (e) { logicalRange = null; }
    try { timeRange = entry.chart.timeScale().getVisibleRange(); } catch (e) { timeRange = null; }

    // Collect raw bar data if stored
    var rawData = entry._rawData ? entry._rawData.slice() : null;

    // Main symbol and interval (from the stored payload)
    var mainSymbol = '';
    if (entry.payload && entry.payload.series && entry.payload.series[0] && entry.payload.series[0].symbol) {
        mainSymbol = String(entry.payload.series[0].symbol);
    } else if (entry._resolvedSymbolInfo && entry._resolvedSymbolInfo.main) {
        mainSymbol = String(entry._resolvedSymbolInfo.main.symbol || entry._resolvedSymbolInfo.main.ticker || '');
    }
    var interval = (entry.payload && entry.payload.interval) ? String(entry.payload.interval) : '';
    var chartType = entry._chartDisplayStyle || 'Candles';

    // Split compare-series entries into two buckets: user-facing
    // compares (what the user added via the Compare dialog) vs.
    // indicator-source compares (the secondary ticker that drives a
    // Spread/Ratio/Sum/Product/Correlation indicator — hidden from
    // the Compare panel, but still in the compare map because that's
    // where the bar data lives).
    var compareSymbols = {};
    var indicatorSourceSymbols = {};
    if (entry._compareSymbols) {
        var csKeys = Object.keys(entry._compareSymbols);
        for (var cs = 0; cs < csKeys.length; cs++) {
            var sid = csKeys[cs];
            var sym = String(entry._compareSymbols[sid]);
            if (entry._indicatorSourceSeries && entry._indicatorSourceSeries[sid]) {
                indicatorSourceSymbols[sid] = sym;
            } else {
                compareSymbols[sid] = sym;
            }
        }
    }

    // Collect drawings
    var ds = window.__PYWRY_DRAWINGS__[chartId];
    var drawings = [];
    if (ds && ds.drawings) {
        for (var d = 0; d < ds.drawings.length; d++) {
            drawings.push(Object.assign({}, ds.drawings[d]));
        }
    }

    // Collect active indicators for this chart.  Binary indicators
    // (Spread, Ratio, Sum, Product, Correlation) carry their secondary
    // series id — resolve it back to the ticker symbol so agents
    // describing the chart know *what* is being spread/ratioed without
    // having to cross-reference seriesId maps themselves.
    var indicators = [];
    var aiKeys = Object.keys(_activeIndicators);
    for (var a = 0; a < aiKeys.length; a++) {
        var ai = _activeIndicators[aiKeys[a]];
        if (ai.chartId !== chartId) continue;
        var entryOut = {
            seriesId: aiKeys[a],
            name: ai.name,
            type: ai.type || null,
            period: ai.period,
            color: ai.color || null,
            group: ai.group || null,
            sourceSeriesId: ai.sourceSeriesId || null,
            secondarySeriesId: ai.secondarySeriesId || null,
            isSubplot: !!ai.isSubplot,
            primarySource: ai.primarySource || null,
            secondarySource: ai.secondarySource || null,
        };
        if (ai.secondarySeriesId) {
            var secSym = (entry._compareSymbols && entry._compareSymbols[ai.secondarySeriesId]) || null;
            entryOut.secondarySymbol = secSym ? String(secSym) : null;
        }
        indicators.push(entryOut);
    }

    return {
        chartId: chartId,
        theme: entry.theme,
        symbol: mainSymbol,
        interval: interval,
        chartType: chartType,
        compareSymbols: compareSymbols,
        indicatorSourceSymbols: indicatorSourceSymbols,
        series: seriesData,
        visibleRange: timeRange,
        visibleLogicalRange: logicalRange,
        rawData: rawData,
        drawings: drawings,
        indicators: indicators,
    };
}

/**
 * Export layout only (annotations + indicators setup, NO raw data).
 * Maps to ChartTemplate model on Python side.
 */
function _tvExportLayout(chartId) {
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (!entry) return null;

    // Series types (but no data)
    var seriesConfig = {};
    var sKeys = Object.keys(entry.seriesMap);
    for (var i = 0; i < sKeys.length; i++) {
        seriesConfig[sKeys[i]] = {
            type: _tvGuessSeriesType(entry.seriesMap[sKeys[i]]),
        };
    }

    // Drawings
    var ds = window.__PYWRY_DRAWINGS__[chartId];
    var drawings = [];
    if (ds && ds.drawings) {
        for (var d = 0; d < ds.drawings.length; d++) {
            drawings.push(Object.assign({}, ds.drawings[d]));
        }
    }

    // Indicators
    var indicators = [];
    var aiKeys = Object.keys(_activeIndicators);
    for (var a = 0; a < aiKeys.length; a++) {
        var ai = _activeIndicators[aiKeys[a]];
        if (ai.chartId === chartId) {
            var indEntry = {
                seriesId: aiKeys[a],
                name: ai.name,
                period: ai.period,
                color: ai.color || null,
                group: ai.group || null,
                type: ai.type || null,
            };
            // Preserve group-specific metadata (BB multiplier, MA type, etc.)
            if (ai.multiplier != null) indEntry.multiplier = ai.multiplier;
            if (ai.maType) indEntry.maType = ai.maType;
            if (ai.offset != null) indEntry.offset = ai.offset;
            if (ai.source) indEntry.source = ai.source;
            indicators.push(indEntry);
        }
    }

    return {
        chartId: chartId,
        theme: entry.theme,
        seriesConfig: seriesConfig,
        drawings: drawings,
        indicators: indicators,
        settings: (typeof _tvBuildCurrentSettings === 'function') ? _tvBuildCurrentSettings(entry) : null,
    };
}

