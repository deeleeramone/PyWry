function _tvApplyDrawingInteractionMode(ds) {
    if (!ds || !ds.canvas) return;
    var tool = ds._activeTool || 'cursor';
    if (tool === 'crosshair' || tool === 'cursor') {
        ds.canvas.style.pointerEvents = 'none';
        ds.canvas.style.cursor = tool === 'crosshair' ? 'crosshair' : 'default';
        return;
    }
    ds.canvas.style.pointerEvents = 'auto';
    ds.canvas.style.cursor = 'crosshair';
}

function _tvGetDrawingViewport(chartId) {
    var ds = window.__PYWRY_DRAWINGS__[chartId];
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    var width = ds && ds.canvas ? ds.canvas.clientWidth : 0;
    var height = ds && ds.canvas ? ds.canvas.clientHeight : 0;
    var viewport = { left: 0, top: 0, right: width, bottom: height, width: width, height: height };
    if (!entry || !entry.chart || width <= 0 || height <= 0) return viewport;

    var timeScale = entry.chart.timeScale ? entry.chart.timeScale() : null;
    if (timeScale && typeof timeScale.logicalToCoordinate === 'function' &&
        typeof timeScale.getVisibleLogicalRange === 'function') {
        var range = timeScale.getVisibleLogicalRange();
        if (range && isFinite(range.from) && isFinite(range.to)) {
            var leftCoord = timeScale.logicalToCoordinate(range.from);
            var rightCoord = timeScale.logicalToCoordinate(range.to);
            if (leftCoord !== null && isFinite(leftCoord)) {
                viewport.left = Math.max(0, Math.min(width, leftCoord));
            }
            if (rightCoord !== null && isFinite(rightCoord)) {
                viewport.right = Math.max(viewport.left, Math.min(width, rightCoord));
            }
        }
    }

    if (!isFinite(viewport.right) || viewport.right <= viewport.left + 8 || viewport.right >= width - 2) {
        var placement = entry._chartPrefs && entry._chartPrefs.scalesPlacement
            ? entry._chartPrefs.scalesPlacement
            : 'Auto';
        var labelProbe = 68;
        if (ds && ds.ctx) {
            ds.ctx.save();
            ds.ctx.font = '11px -apple-system,BlinkMacSystemFont,sans-serif';
            labelProbe = Math.ceil(ds.ctx.measureText('000000.00').width) + 18;
            ds.ctx.restore();
        }
        var gutter = Math.max(52, Math.min(96, labelProbe));
        if (placement === 'Left') {
            viewport.left = gutter;
            viewport.right = width;
        } else {
            viewport.left = 0;
            viewport.right = Math.max(0, width - gutter);
        }
    }

    viewport.width = Math.max(0, viewport.right - viewport.left);
    return viewport;
}

// Fibonacci settings (resolved from CSS variables)
var _FIB_LEVELS = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1];
function _getFibColors() {
    var colors = [];
    for (var i = 0; i < 7; i++) {
        colors.push(_cssVar('--pywry-fib-color-' + i));
    }
    return colors;
}

// ---- SVG icon templates for drawing toolbar ----
var _DT_ICONS = {
    pencil: '<svg viewBox="0 0 18 18"><path d="M13.3 1.3a1 1 0 011.4 0l2 2a1 1 0 010 1.4l-10 10a1 1 0 01-.5.3l-3 .7a.5.5 0 01-.6-.6l.7-3a1 1 0 01.3-.5l10-10z"/></svg>',
    bucket: '<svg viewBox="0 0 18 18"><path d="M11 1.5L2.5 10a1 1 0 000 1.4l4.1 4.1a1 1 0 001.4 0L16.5 7m-2 6c0 1.1.9 2.5 2 2.5s2-1.4 2-2.5S17.1 11 16.5 11 14.5 11.9 14.5 13z"/></svg>',
    text: '<svg viewBox="0 0 18 18"><path d="M3 4h12M9 4v11M6 15h6" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>',
    border: '<svg viewBox="0 0 18 18"><rect x="3" y="3" width="12" height="12" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>',
    lineW: '<svg viewBox="0 0 18 18"><rect x="2" y="4" width="14" height="2" rx="1"/><rect x="2" y="8" width="14" height="3" rx="1.5"/><rect x="2" y="13" width="14" height="1" rx=".5"/></svg>',
    settings: '<svg viewBox="0 0 18 18"><circle cx="9" cy="9" r="2.5" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M9 1v2m0 12v2M1 9h2m12 0h2M3.3 3.3l1.4 1.4m8.6 8.6l1.4 1.4M14.7 3.3l-1.4 1.4M4.7 13.3l-1.4 1.4" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg>',
    lock: '<svg viewBox="0 0 18 18"><rect x="4" y="8" width="10" height="8" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M6 8V5.5a3 3 0 016 0V8" fill="none" stroke="currentColor" stroke-width="1.3"/></svg>',
    unlock: '<svg viewBox="0 0 18 18"><rect x="4" y="8" width="10" height="8" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M6 8V5.5a3 3 0 016 0" fill="none" stroke="currentColor" stroke-width="1.3"/></svg>',
    trash: '<svg viewBox="0 0 18 18"><path d="M3 5h12M7 5V3.5A1.5 1.5 0 018.5 2h1A1.5 1.5 0 0111 3.5V5m-6 0l.8 10a1.5 1.5 0 001.5 1.4h3.4a1.5 1.5 0 001.5-1.4L13 5" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg>',
    clone: '<svg viewBox="0 0 18 18"><rect x="5" y="5" width="10" height="10" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.2"/><path d="M3 13V4a1 1 0 011-1h9" fill="none" stroke="currentColor" stroke-width="1.2"/></svg>',
    eye: '<svg viewBox="0 0 18 18"><path d="M1 9s3-5.5 8-5.5S17 9 17 9s-3 5.5-8 5.5S1 9 1 9z" fill="none" stroke="currentColor" stroke-width="1.2"/><circle cx="9" cy="9" r="2.5" fill="none" stroke="currentColor" stroke-width="1.2"/></svg>',
    eyeOff: '<svg viewBox="0 0 18 18"><path d="M1 9s3-5.5 8-5.5S17 9 17 9s-3 5.5-8 5.5S1 9 1 9zM2 16L16 2" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/></svg>',
    more: '<svg viewBox="0 0 18 18"><circle cx="4" cy="9" r="1.3"/><circle cx="9" cy="9" r="1.3"/><circle cx="14" cy="9" r="1.3"/></svg>',
};

// ---- Ensure drawing layer ----
function _tvEnsureDrawingLayer(chartId) {
    if (window.__PYWRY_DRAWINGS__[chartId]) return window.__PYWRY_DRAWINGS__[chartId];

    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (!entry || !entry.container) return null;

    var container = entry.container;
    var pos = window.getComputedStyle(container).position;
    if (pos === 'static') container.style.position = 'relative';

    var canvas = document.createElement('canvas');
    canvas.className = 'pywry-drawing-overlay';
    canvas.style.cssText =
        'position:absolute;top:0;left:0;width:100%;height:100%;' +
        'pointer-events:none;z-index:5;';
    container.appendChild(canvas);

    // UI overlay div (sits above canvas, for floating toolbar / menus)
    var uiLayer = document.createElement('div');
    uiLayer.className = 'pywry-draw-ui-layer';
    uiLayer.style.cssText =
        'position:absolute;top:0;left:0;width:100%;height:100%;' +
        'pointer-events:none;z-index:10;overflow:visible;';
    container.appendChild(uiLayer);

    var ctx = canvas.getContext('2d');
    var state = {
        canvas: canvas,
        ctx: ctx,
        uiLayer: uiLayer,
        chartId: chartId,
        drawings: [],
        priceLines: [],
        _activeTool: 'cursor',
    };
    window.__PYWRY_DRAWINGS__[chartId] = state;
    _tvApplyDrawingInteractionMode(state);

    function resize() {
        var rect = container.getBoundingClientRect();
        var dpr = window.devicePixelRatio || 1;
        canvas.width  = rect.width  * dpr;
        canvas.height = rect.height * dpr;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        _tvRenderDrawings(chartId);
    }
    if (typeof ResizeObserver !== 'undefined') {
        new ResizeObserver(resize).observe(container);
    }
    resize();

    entry.chart.timeScale().subscribeVisibleLogicalRangeChange(function() {
        _tvRenderDrawings(chartId);
        _tvRepositionToolbar(chartId);
    });

    _tvEnableDrawing(chartId);
    return state;
}

// ---- Coordinate helpers ----
function _tvMainSeries(chartId) {
    var e = window.__PYWRY_TVCHARTS__[chartId];
    if (!e) return null;
    var k = Object.keys(e.seriesMap)[0];
    return k ? e.seriesMap[k] : null;
}

function _tvResolveChartId(chartId) {
    if (chartId && window.__PYWRY_TVCHARTS__[chartId]) return chartId;
    var keys = Object.keys(window.__PYWRY_TVCHARTS__);
    return keys.length ? keys[0] : null;
}

function _tvResolveChartEntry(chartId) {
    var resolvedId = _tvResolveChartId(chartId);
    if (!resolvedId) return null;
    return {
        chartId: resolvedId,
        entry: window.__PYWRY_TVCHARTS__[resolvedId],
    };
}

function _tvIsUiScopeNode(node) {
    if (!node || !node.classList) return false;
    return (
        node.classList.contains('pywry-widget') ||
        node.classList.contains('pywry-content') ||
        node.classList.contains('pywry-wrapper-inside') ||
        node.classList.contains('pywry-wrapper-top') ||
        node.classList.contains('pywry-body-scroll') ||
        node.classList.contains('pywry-wrapper-left') ||
        node.classList.contains('pywry-wrapper-header')
    );
}

function _tvResolveUiRootFromElement(element) {
    if (!element || !element.closest) return document;
    var root = element.closest('.pywry-content, .pywry-widget') || element;
    while (root && root.parentElement && _tvIsUiScopeNode(root.parentElement)) {
        root = root.parentElement;
    }
    return root || document;
}

function _tvResolveUiRoot(chartId) {
    var resolved = _tvResolveChartEntry(chartId);
    var entry = resolved ? resolved.entry : null;
    if (!entry) return document;
    if (entry.uiRoot) return entry.uiRoot;
    if (entry.container) {
        entry.uiRoot = _tvResolveUiRootFromElement(entry.container);
        return entry.uiRoot;
    }
    return document;
}

function _tvResolveChartIdFromElement(element) {
    var root = _tvResolveUiRootFromElement(element);
    var ids = Object.keys(window.__PYWRY_TVCHARTS__ || {});
    for (var i = 0; i < ids.length; i++) {
        if (_tvResolveUiRoot(ids[i]) === root) {
            return ids[i];
        }
    }
    return _tvResolveChartId(null);
}

function _tvScopedQuery(scopeOrChartId, selector) {
    var scope = scopeOrChartId;
    if (!scope || typeof scope === 'string') {
        scope = _tvResolveUiRoot(scopeOrChartId);
    }
    if (scope && typeof scope.querySelector === 'function') {
        var scopedNode = scope.querySelector(selector);
        if (scopedNode) return scopedNode;
    }
    return document.querySelector(selector);
}

function _tvScopedQueryAll(scopeOrChartId, selector) {
    var scope = scopeOrChartId;
    if (!scope || typeof scope === 'string') {
        scope = _tvResolveUiRoot(scopeOrChartId);
    }
    if (scope && typeof scope.querySelectorAll === 'function') {
        return scope.querySelectorAll(selector);
    }
    return document.querySelectorAll(selector);
}

function _tvScopedById(scopeOrChartId, id) {
    return _tvScopedQuery(scopeOrChartId, '[id="' + id + '"]');
}

function _tvSetLegendVisible(visible, chartId) {
    if (!chartId) {
        var chartIds = Object.keys(window.__PYWRY_TVCHARTS__ || {});
        if (chartIds.length) {
            for (var i = 0; i < chartIds.length; i++) {
                _tvSetLegendVisible(visible, chartIds[i]);
            }
            return;
        }
    }
    var legend = _tvScopedById(chartId, 'tvchart-legend-box');
    if (!legend) return;
    legend.style.opacity = visible ? '1' : '0';
}

function _tvRefreshLegendVisibility(chartId) {
    if (!chartId) {
        var chartIds = Object.keys(window.__PYWRY_TVCHARTS__ || {});
        if (chartIds.length) {
            for (var i = 0; i < chartIds.length; i++) {
                _tvRefreshLegendVisibility(chartIds[i]);
            }
            return;
        }
    }
    var root = _tvResolveUiRoot(chartId);
    var menuOpen = !!_tvScopedQuery(
        root,
        '.tvchart-save-menu.open, .tvchart-chart-type-menu.open, .tvchart-interval-menu.open'
    );
    _tvSetLegendVisible(!menuOpen, chartId);
}

function _tvRefreshLegendTitle(chartId) {
    var resolved = _tvResolveChartEntry(chartId);
    var entry = resolved ? resolved.entry : null;
    var effectiveChartId = resolved ? resolved.chartId : chartId;
    if (!entry) return;

    var titleEl = _tvScopedById(effectiveChartId, 'tvchart-legend-title');
    if (!titleEl) return;
    var legendBox = _tvScopedById(effectiveChartId, 'tvchart-legend-box');
    var ds = legendBox ? legendBox.dataset : null;

    var base = ds && ds.baseTitle ? String(ds.baseTitle) : '';
    if (!base && entry.payload && entry.payload.useDatafeed && entry.payload.series && entry.payload.series[0] && entry.payload.series[0].symbol) {
        base = String(entry.payload.series[0].symbol);
    }
    if (!base && entry.payload && entry.payload.title) {
        base = String(entry.payload.title);
    }
    if (!base && entry.payload && entry.payload.series && entry.payload.series[0] && entry.payload.series[0].seriesId) {
        var sid = String(entry.payload.series[0].seriesId);
        if (sid && sid !== 'main') base = sid;
    }

    if (ds && ds.showTitle === '0') {
        base = '';
    }
    // Description mode replaces the base title with resolved symbol info
    if (ds && ds.description && ds.description !== 'Off') {
        var descMode = ds.description;
        var symInfo = (entry && entry._resolvedSymbolInfo && entry._resolvedSymbolInfo.main)
            || (entry && entry._mainSymbolInfo) || {};
        var ticker = String(symInfo.ticker || symInfo.displaySymbol || symInfo.symbol || base || '').trim();
        var descText = String(symInfo.description || symInfo.fullName || '').trim();
        if (descMode === 'Description' && descText) {
            base = descText;
        } else if (descMode === 'Ticker and description') {
            base = (ticker && descText) ? (ticker + ' · ' + descText) : (ticker || descText || base);
        }
        // 'Ticker' mode keeps base as-is
    }
    if (ds && base) {
        var intervalText = ds.interval || '';
        // If no explicit interval set, read from toolbar label
        if (!intervalText) {
            var intervalLabel = _tvScopedById(effectiveChartId, 'tvchart-interval-label');
            if (intervalLabel) intervalText = (intervalLabel.textContent || '').trim();
        }
        if (intervalText) {
            base = base + ' · ' + intervalText;
        }
    }

    titleEl.textContent = base;
    titleEl.style.display = base ? 'inline-flex' : 'none';
}

function _tvEmitLegendRefresh(chartId) {
    try {
        if (typeof window.CustomEvent === 'function') {
            window.dispatchEvent(new CustomEvent('pywry:legend-refresh', {
                detail: { chartId: chartId },
            }));
        }
    } catch (e) {}
}

function _tvLegendFormat(v) {
    if (v == null) return '--';
    return Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function _tvLegendFormatVol(v) {
    if (v == null) return '';
    if (v >= 1e9) return (v / 1e9).toFixed(2) + ' B';
    if (v >= 1e6) return (v / 1e6).toFixed(2) + ' M';
    if (v >= 1e3) return (v / 1e3).toFixed(2) + ' K';
    return Number(v).toFixed(0);
}

function _tvLegendColorize(val, ref) {
    var cs = getComputedStyle(document.documentElement);
    var _up = cs.getPropertyValue('--pywry-tvchart-up').trim() || '#089981';
    var _dn = cs.getPropertyValue('--pywry-tvchart-down').trim() || '#f23645';
    var _mt = cs.getPropertyValue('--pywry-tvchart-text-muted').trim() || '#aeb4c2';
    if (val == null || ref == null) return _mt;
    return val >= ref ? _up : _dn;
}

function _tvLegendDataset(chartId) {
    var legendBox = _tvScopedById(chartId, 'tvchart-legend-box');
    return legendBox ? legendBox.dataset : null;
}

function _tvLegendNormalizeTimeValue(value) {
    if (value == null) return null;
    if (typeof value === 'number') return value;
    if (typeof value === 'string') {
        var parsed = Date.parse(value);
        return isFinite(parsed) ? Math.floor(parsed / 1000) : value;
    }
    if (typeof value === 'object') {
        if (typeof value.timestamp === 'number') return value.timestamp;
        if (typeof value.year === 'number' && typeof value.month === 'number' && typeof value.day === 'number') {
            return Date.UTC(value.year, value.month - 1, value.day) / 1000;
        }
    }
    return null;
}

function _tvLegendMainKey(entry) {
    var keys = Object.keys((entry && entry.seriesMap) || {});
    return keys.indexOf('main') >= 0 ? 'main' : (keys[0] || null);
}

function _tvLegendResolvePoint(entry, seriesId, seriesApi, param) {
    var direct = (param && param.seriesData && seriesApi) ? param.seriesData.get(seriesApi) : null;
    if (direct) return direct;

    var rows = entry && entry._seriesRawData ? entry._seriesRawData[seriesId] : null;
    if (!rows || !rows.length) return null;
    if (!param || param.time == null) return rows[rows.length - 1] || null;

    var target = _tvLegendNormalizeTimeValue(param.time);
    if (target == null) return rows[rows.length - 1] || null;

    var best = null;
    var bestTime = null;
    for (var idx = 0; idx < rows.length; idx++) {
        var row = rows[idx];
        var rowTime = _tvLegendNormalizeTimeValue(row && row.time);
        if (rowTime == null) continue;
        if (rowTime === target) return row;
        if (rowTime <= target) {
            best = row;
            bestTime = rowTime;
            continue;
        }
        if (bestTime == null) return row;
        return best;
    }
    return best || rows[rows.length - 1] || null;
}

function _tvLegendSeriesLabel(entry, seriesId) {
    var sid = String(seriesId || 'main');
    if (sid === 'main') {
        var ds = _tvLegendDataset(entry && entry.chartId ? entry.chartId : null) || {};
        var base = ds.baseTitle ? String(ds.baseTitle) : '';
        if (!base && entry && entry.payload && entry.payload.title) base = String(entry.payload.title);
        return base || 'Main';
    }
    if (entry && entry._compareLabels && entry._compareLabels[sid]) return String(entry._compareLabels[sid]);
    if (entry && entry._compareSymbolInfo && entry._compareSymbolInfo[sid]) {
        var info = entry._compareSymbolInfo[sid] || {};
        var display = String(info.displaySymbol || info.ticker || '').trim();
        if (display) return display.toUpperCase();
        var full = String(info.fullName || '').trim();
        if (full) return full;
        var rawInfoSymbol = String(info.symbol || '').trim();
        if (rawInfoSymbol) {
            return rawInfoSymbol.indexOf(':') >= 0 ? rawInfoSymbol.split(':').pop().trim().toUpperCase() : rawInfoSymbol.toUpperCase();
        }
    }
    if (entry && entry._compareSymbols && entry._compareSymbols[sid]) {
        var raw = String(entry._compareSymbols[sid]);
        return raw.indexOf(':') >= 0 ? raw.split(':').pop().trim().toUpperCase() : raw.toUpperCase();
    }
    return sid;
}

function _tvLegendSeriesColor(entry, seriesId, dataPoint, ds) {
    var sid = String(seriesId || 'main');
    if (entry && entry._legendSeriesColors && entry._legendSeriesColors[sid]) {
        return String(entry._legendSeriesColors[sid]);
    }
    if (dataPoint && dataPoint.open !== undefined) {
        return _tvLegendColorize(dataPoint.close, dataPoint.open);
    }
    return (ds && ds.lineColor) ? ds.lineColor : (getComputedStyle(document.documentElement).getPropertyValue('--pywry-tvchart-session-breaks').trim() || '#4c87ff');
}

function _tvRenderLegendSeriesRows(chartId, entry, param) {
    var seriesEl = _tvScopedById(chartId, 'tvchart-legend-series');
    if (!seriesEl || !entry) return;

    var ds = _tvLegendDataset(chartId) || {};
    var currentMainKey = _tvLegendMainKey(entry);
    var keys = Object.keys(entry.seriesMap || {});
    var existing = {};
    var existingRows = seriesEl.querySelectorAll('.tvchart-legend-series-row');
    for (var ri = 0; ri < existingRows.length; ri++) {
        var existingId = existingRows[ri].getAttribute('data-series-id') || '';
        if (existingId) existing[existingId] = existingRows[ri];
    }

    var activeCount = 0;
    for (var i = 0; i < keys.length; i++) {
        var sid = keys[i];
        if (String(sid) === String(currentMainKey) || String(sid) === 'volume' || String(sid).indexOf('ind_') === 0) continue;
        if (entry._indicatorSourceSeries && entry._indicatorSourceSeries[sid]) continue;
        var sApi = entry.seriesMap[sid];
        if (!sApi) continue;

        var d = _tvLegendResolvePoint(entry, sid, sApi, param);
        var value = null;
        if (d && d.open !== undefined) value = Number(d.close);
        else if (d && d.value !== undefined) value = Number(d.value);

        var row = existing[sid] || document.createElement('div');
        if (!existing[sid]) {
            row.className = 'tvchart-legend-row tvchart-legend-series-row';
            row.setAttribute('data-series-id', sid);
            row.innerHTML =
                '<span class="tvchart-legend-series-dot"></span>' +
                '<span class="tvchart-legend-series-name"></span>' +
                '<span class="tvchart-legend-series-value"></span>' +
                '<span class="tvchart-legend-row-actions tvchart-legend-series-actions"></span>';
            seriesEl.appendChild(row);
        }
        delete existing[sid];
        activeCount += 1;

        var dot = row.querySelector('.tvchart-legend-series-dot');
        var name = row.querySelector('.tvchart-legend-series-name');
        var valueEl = row.querySelector('.tvchart-legend-series-value');
        var color = _tvLegendSeriesColor(entry, sid, d, ds);
        if (dot) dot.style.background = color;
        if (name) name.textContent = _tvLegendSeriesLabel(entry, sid);
        if (valueEl) {
            valueEl.textContent = value == null ? '--' : _tvLegendFormat(value);
            valueEl.style.color = color;
        }
    }

    var obsoleteIds = Object.keys(existing);
    for (var oi = 0; oi < obsoleteIds.length; oi++) {
        var obsoleteRow = existing[obsoleteIds[oi]];
        if (obsoleteRow && obsoleteRow.parentNode) obsoleteRow.parentNode.removeChild(obsoleteRow);
    }
    seriesEl.style.display = activeCount ? 'block' : 'none';
}

function _tvRenderHoverLegend(chartId, param) {
    var resolved = _tvResolveChartEntry(chartId);
    var entry = resolved ? resolved.entry : null;
    var effectiveChartId = resolved ? resolved.chartId : chartId;
    if (!entry) return;

    var titleEl = _tvScopedById(effectiveChartId, 'tvchart-legend-title');
    var ohlcEl = _tvScopedById(effectiveChartId, 'tvchart-legend-ohlc');
    var mainRowEl = _tvScopedById(effectiveChartId, 'tvchart-legend-main-row');
    if (!titleEl || !ohlcEl) return;

    var ds = _tvLegendDataset(effectiveChartId) || {};
    _tvRefreshLegendTitle(effectiveChartId);

    var mainKey = _tvLegendMainKey(entry);
    var mainSeries = entry.seriesMap ? entry.seriesMap[mainKey] : null;
    var d = _tvLegendResolvePoint(entry, mainKey, mainSeries, param);
    var legendMainHtml = '';
    var highLowMode = ds.highLowMode || 'Hidden';
    var _csHL = getComputedStyle(document.documentElement);
    var highLowColor = ds.highLowColor || (_csHL.getPropertyValue('--pywry-tvchart-down').trim() || '#f23645');
    var lineColor = ds.lineColor || (_csHL.getPropertyValue('--pywry-tvchart-up').trim() || '#089981');
    var symbolMode = ds.symbolMode || 'Value, line';

    if (d && d.open !== undefined) {
        var chg = Number(d.close) - Number(d.open);
        var chgPct = Number(d.open) !== 0 ? ((chg / Number(d.open)) * 100) : 0;
        var clr = _tvLegendColorize(d.close, d.open);
        var parts = [];
        if (symbolMode !== 'Line only') {
            parts.push('<span style="color:var(--pywry-tvchart-text-dim)">O</span> <span style="color:' + clr + '">' + _tvLegendFormat(d.open) + '</span>');
            if (highLowMode !== 'Hidden') {
                parts.push('<span style="color:' + highLowColor + '">H</span> <span style="color:' + clr + '">' + _tvLegendFormat(d.high) + '</span>');
                parts.push('<span style="color:' + highLowColor + '">L</span> <span style="color:' + clr + '">' + _tvLegendFormat(d.low) + '</span>');
            }
            parts.push('<span style="color:var(--pywry-tvchart-text-dim)">C</span> <span style="color:' + clr + '">' + _tvLegendFormat(d.close) + '</span>');
        } else {
            parts.push('<span style="color:' + lineColor + '">—</span>');
        }
        parts.push('<span style="color:' + clr + '">' + (chg >= 0 ? '+' : '') + _tvLegendFormat(chg) + ' (' + (chg >= 0 ? '+' : '') + chgPct.toFixed(2) + '%)</span>');
        legendMainHtml = parts.join(' ');
    } else if (d && d.value !== undefined) {
        legendMainHtml = symbolMode === 'Line only'
            ? '<span style="color:' + lineColor + '">—</span>'
            : '<span style="color:' + lineColor + '">' + _tvLegendFormat(d.value) + '</span>';
    }

    ohlcEl.innerHTML = legendMainHtml;
    if (mainRowEl) {
        var showMainRow = !!(titleEl.textContent || ohlcEl.textContent || ohlcEl.innerHTML);
        mainRowEl.style.display = showMainRow ? 'flex' : 'none';
    }

    // Volume content and vol row visibility are managed by
    // _tvSetupLegendControls (11-legend.js) — do not touch volEl / volRowEl
    // here to avoid conflicting display changes.

    _tvRenderLegendSeriesRows(effectiveChartId, entry, param);
}

