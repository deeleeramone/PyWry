function _tvHideSeriesSettings() {
    _tvHideColorOpacityPopup();
    if (_seriesSettingsOverlay && _seriesSettingsOverlay.parentNode) {
        _seriesSettingsOverlay.parentNode.removeChild(_seriesSettingsOverlay);
    }
    if (_seriesSettingsOverlayChartId) _tvSetChartInteractionLocked(_seriesSettingsOverlayChartId, false);
    _seriesSettingsOverlay = null;
    _seriesSettingsOverlayChartId = null;
    _seriesSettingsOverlaySeriesId = null;
    _tvRefreshLegendVisibility();
}

function _tvShowSeriesSettings(chartId, seriesId) {
    _tvHideSeriesSettings();
    var resolved = _tvResolveChartEntry(chartId);
    if (!resolved || !resolved.entry) return;
    chartId = resolved.chartId;
    var entry = resolved.entry;
    var seriesApi = entry.seriesMap ? entry.seriesMap[seriesId] : null;
    if (!seriesApi) return;

    var currentType = _tvGuessSeriesType(seriesApi);
    var currentOpts = {};
    try { currentOpts = seriesApi.options() || {}; } catch (e) {}
    var persistedVisibility = (entry._seriesVisibilityIntervals && entry._seriesVisibilityIntervals[seriesId])
        ? entry._seriesVisibilityIntervals[seriesId]
        : null;
    var defaultVisibilityIntervals = {
        seconds: { enabled: true, min: 1, max: 59 },
        minutes: { enabled: true, min: 1, max: 59 },
        hours:   { enabled: true, min: 1, max: 24 },
        days:    { enabled: true, min: 1, max: 366 },
        weeks:   { enabled: true, min: 1, max: 52 },
        months:  { enabled: true, min: 1, max: 12 },
    };
    var persistedStylePrefs = (entry._seriesStylePrefs && entry._seriesStylePrefs[seriesId])
        ? entry._seriesStylePrefs[seriesId]
        : null;
    var initialStyle = (persistedStylePrefs && persistedStylePrefs.style)
        ? persistedStylePrefs.style
        : _ssTypeToStyleName(currentType || 'Line');
    var auxStyle = (entry._seriesStyleAux && entry._seriesStyleAux[seriesId]) ? entry._seriesStyleAux[seriesId] : {};

    // Theme-aware defaults — all pulled from CSS vars so swapping themes
    // (or overriding them via CSS) recolors the settings-dialog "Reset"
    // state.  Fallback literals match the dark-theme palette for the case
    // where _cssVar resolves to empty (e.g. running outside the chart's
    // themed container).
    var themeUp = _cssVar('--pywry-tvchart-up') || '#26a69a';
    var themeDown = _cssVar('--pywry-tvchart-down') || '#ef5350';
    var themeBorderUp = _cssVar('--pywry-tvchart-border-up') || themeUp;
    var themeBorderDown = _cssVar('--pywry-tvchart-border-down') || themeDown;
    var themeWickUp = _cssVar('--pywry-tvchart-wick-up') || themeUp;
    var themeWickDown = _cssVar('--pywry-tvchart-wick-down') || themeDown;
    var themeLineColor = _cssVar('--pywry-tvchart-line-default') || '#4c87ff';
    var themeAreaTop = _cssVar('--pywry-tvchart-area-top-default') || themeLineColor;
    var themeAreaBottom = _cssVar('--pywry-tvchart-area-bottom-default') || '#10223f';
    var themeBaselineTopFill1 = _cssVar('--pywry-tvchart-baseline-top-fill1') || themeUp;
    var themeBaselineTopFill2 = _cssVar('--pywry-tvchart-baseline-top-fill2') || themeUp;
    var themeBaselineBottomFill1 = _cssVar('--pywry-tvchart-baseline-bottom-fill1') || themeDown;
    var themeBaselineBottomFill2 = _cssVar('--pywry-tvchart-baseline-bottom-fill2') || themeDown;

    var initialState = {
        style: initialStyle,
        priceSource: 'close',
        color: _tvColorToHex(
            currentOpts.color || currentOpts.lineColor || (entry._legendSeriesColors && entry._legendSeriesColors[seriesId]) || themeLineColor,
            themeLineColor
        ),
        lineWidth: _tvClamp(_tvToNumber(currentOpts.lineWidth || currentOpts.width, 2), 1, 4),
        markersVisible: currentOpts.pointMarkersVisible === true,
        areaTopColor: _tvColorToHex(currentOpts.topColor || themeAreaTop, themeAreaTop),
        areaBottomColor: _tvColorToHex(currentOpts.bottomColor || themeAreaBottom, themeAreaBottom),
        baselineTopLineColor: _tvColorToHex(currentOpts.topLineColor || themeUp, themeUp),
        baselineBottomLineColor: _tvColorToHex(currentOpts.bottomLineColor || themeDown, themeDown),
        baselineTopFillColor1: _tvColorToHex(currentOpts.topFillColor1 || themeBaselineTopFill1, themeUp),
        baselineTopFillColor2: _tvColorToHex(currentOpts.topFillColor2 || themeBaselineTopFill2, themeUp),
        baselineBottomFillColor1: _tvColorToHex(currentOpts.bottomFillColor1 || themeBaselineBottomFill1, themeDown),
        baselineBottomFillColor2: _tvColorToHex(currentOpts.bottomFillColor2 || themeBaselineBottomFill2, themeDown),
        baselineBaseLevel: _tvToNumber((currentOpts.baseValue && currentOpts.baseValue._level), 50),
        columnsUpColor: _tvColorToHex(currentOpts.upColor || currentOpts.color || themeUp, themeUp),
        columnsDownColor: _tvColorToHex(currentOpts.downColor || currentOpts.color || themeDown, themeDown),
        barsUpColor: _tvColorToHex(currentOpts.upColor || themeUp, themeUp),
        barsDownColor: _tvColorToHex(currentOpts.downColor || themeDown, themeDown),
        barsOpenVisible: currentOpts.openVisible !== false,
        priceLineVisible: currentOpts.priceLineVisible !== false,
        overrideMinTick: 'Default',
        visible: currentOpts.visible !== false,
        bodyVisible: true,
        bordersVisible: true,
        wickVisible: true,
        bodyUpColor: _tvColorToHex(currentOpts.upColor || currentOpts.color || themeUp, themeUp),
        bodyDownColor: _tvColorToHex(currentOpts.downColor || themeDown, themeDown),
        borderUpColor: _tvColorToHex(currentOpts.borderUpColor || currentOpts.upColor || themeBorderUp, themeBorderUp),
        borderDownColor: _tvColorToHex(currentOpts.borderDownColor || currentOpts.downColor || themeBorderDown, themeBorderDown),
        wickUpColor: _tvColorToHex(currentOpts.wickUpColor || currentOpts.upColor || themeWickUp, themeWickUp),
        wickDownColor: _tvColorToHex(currentOpts.wickDownColor || currentOpts.downColor || themeWickDown, themeWickDown),
        hlcHighVisible: auxStyle.highVisible !== false,
        hlcLowVisible: auxStyle.lowVisible !== false,
        hlcCloseVisible: auxStyle.closeVisible !== false,
        hlcHighColor: _tvColorToHex(auxStyle.highColor || _cssVar('--pywry-tvchart-hlcarea-high') || '#089981', '#089981'),
        hlcLowColor: _tvColorToHex(auxStyle.lowColor || _cssVar('--pywry-tvchart-hlcarea-low') || '#f23645', '#f23645'),
        hlcCloseColor: _tvColorToHex(auxStyle.closeColor || (currentOpts.lineColor || currentOpts.color || _cssVar('--pywry-tvchart-hlcarea-close') || '#2962ff'), '#2962ff'),
        hlcFillTopColor: auxStyle.fillTopColor || _cssVar('--pywry-tvchart-hlcarea-fill-up') || 'rgba(8, 153, 129, 0.28)',
        hlcFillBottomColor: auxStyle.fillBottomColor || _cssVar('--pywry-tvchart-hlcarea-fill-down') || 'rgba(242, 54, 69, 0.28)',
        visibilityIntervals: _tvMerge(defaultVisibilityIntervals, persistedVisibility || {}),
    };
    if (persistedStylePrefs) {
        var persistedKeys = Object.keys(initialState);
        for (var pk = 0; pk < persistedKeys.length; pk++) {
            var pkey = persistedKeys[pk];
            if (persistedStylePrefs[pkey] !== undefined) initialState[pkey] = persistedStylePrefs[pkey];
        }
    }
    var draft = _tvMerge({}, initialState);
    var label = _tvLegendSeriesLabel(entry, seriesId);
    var activeTab = 'style';

    var overlay = document.createElement('div');
    overlay.className = 'tv-settings-overlay';
    _seriesSettingsOverlay = overlay;
    _seriesSettingsOverlayChartId = chartId;
    _seriesSettingsOverlaySeriesId = seriesId;
    _tvSetChartInteractionLocked(chartId, true);
    _tvRefreshLegendVisibility();
    overlay.addEventListener('click', function(e) {
        if (e.target === overlay) _tvHideSeriesSettings();
    });
    overlay.addEventListener('mousedown', function(e) { e.stopPropagation(); });
    overlay.addEventListener('wheel', function(e) { e.stopPropagation(); });

    var panel = document.createElement('div');
    panel.className = 'tv-settings-panel';
    panel.style.cssText = 'width:620px;max-width:calc(100% - 32px);max-height:72vh;display:flex;flex-direction:column;';
    overlay.appendChild(panel);

    var header = document.createElement('div');
    header.className = 'tv-settings-header';
    header.style.cssText = 'position:relative;flex-direction:column;align-items:stretch;padding-bottom:0;';

    var hdrRow = document.createElement('div');
    hdrRow.style.cssText = 'display:flex;align-items:center;gap:8px;';
    var titleEl = document.createElement('h3');
    titleEl.textContent = label || seriesId;
    hdrRow.appendChild(titleEl);
    var closeBtn = document.createElement('button');
    closeBtn.className = 'tv-settings-close';
    closeBtn.innerHTML = '<svg viewBox="0 0 16 16"><line x1="3" y1="3" x2="13" y2="13"/><line x1="13" y1="3" x2="3" y2="13"/></svg>';
    closeBtn.addEventListener('click', function() { _tvHideSeriesSettings(); });
    hdrRow.appendChild(closeBtn);
    header.appendChild(hdrRow);

    var tabBar = document.createElement('div');
    tabBar.className = 'tv-ind-settings-tabs';
    var styleTab = document.createElement('div');
    styleTab.className = 'tv-ind-settings-tab active';
    styleTab.textContent = 'Style';
    var visTab = document.createElement('div');
    visTab.className = 'tv-ind-settings-tab';
    visTab.textContent = 'Visibility';
    tabBar.appendChild(styleTab);
    tabBar.appendChild(visTab);
    header.appendChild(tabBar);
    panel.appendChild(header);

    var body = document.createElement('div');
    body.className = 'tv-settings-body';
    body.style.cssText = 'flex:1;overflow-y:auto;min-height:80px;';
    panel.appendChild(body);

    function _ssRow(labelText) {
        var row = document.createElement('div');
        row.className = 'tv-settings-row tv-settings-row-spaced';
        var lbl = document.createElement('label');
        lbl.textContent = labelText;
        row.appendChild(lbl);
        var ctrl = document.createElement('div');
        ctrl.className = 'ts-controls';
        row.appendChild(ctrl);
        return { row: row, ctrl: ctrl };
    }

    function _ssSelect(opts, value, onChange) {
        var sel = document.createElement('select');
        sel.className = 'ts-select';
        for (var i = 0; i < opts.length; i++) {
            var opt = document.createElement('option');
            opt.value = opts[i].v;
            opt.textContent = opts[i].l;
            if (String(opts[i].v) === String(value)) opt.selected = true;
            sel.appendChild(opt);
        }
        sel.addEventListener('change', function() { onChange(sel.value); });
        return sel;
    }

    function _ssCheckbox(value, onChange) {
        var cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.className = 'ts-checkbox';
        cb.checked = !!value;
        cb.addEventListener('change', function() { onChange(cb.checked); });
        return cb;
    }

    function _ssColorLineControl(value, widthValue, onColor, onWidth) {
        var wrap = document.createElement('div');
        wrap.style.cssText = 'display:flex;align-items:center;gap:8px;';
        var swatch = document.createElement('div');
        swatch.className = 'ts-swatch';
        swatch.dataset.baseColor = _tvColorToHex(value || '#4c87ff', '#4c87ff');
        swatch.dataset.opacity = String(_tvColorOpacityPercent(value, 100));
        swatch.style.background = value;
        swatch.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            _tvShowColorOpacityPopup(
                swatch,
                swatch.dataset.baseColor || value,
                _tvToNumber(swatch.dataset.opacity, 100),
                overlay,
                function(newColor, newOpacity) {
                    swatch.dataset.baseColor = newColor;
                    swatch.dataset.opacity = String(newOpacity);
                    swatch.style.background = _tvColorWithOpacity(newColor, newOpacity, newColor);
                    linePreview.style.background = _tvColorWithOpacity(newColor, newOpacity, newColor);
                    onColor(_tvColorWithOpacity(newColor, newOpacity, newColor));
                }
            );
        });
        var linePreview = document.createElement('div');
        linePreview.style.cssText = 'width:44px;height:2px;background:' + value + ';border-radius:2px;';
        function syncWidth(w) { linePreview.style.height = String(_tvClamp(_tvToNumber(w, 2), 1, 4)) + 'px'; }
        syncWidth(widthValue);
        onWidth(syncWidth);
        wrap.appendChild(swatch);
        wrap.appendChild(linePreview);
        return wrap;
    }

    function _ssDualColorControl(upValue, downValue, onUp, onDown) {
        var wrap = document.createElement('div');
        wrap.style.cssText = 'display:flex;align-items:center;gap:8px;';
        function makeSwatch(initial, onChange) {
            var sw = document.createElement('div');
            sw.className = 'ts-swatch';
            sw.dataset.baseColor = _tvColorToHex(initial || '#4c87ff', '#4c87ff');
            sw.dataset.opacity = String(_tvColorOpacityPercent(initial, 100));
            sw.style.background = initial;
            sw.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                _tvShowColorOpacityPopup(
                    sw,
                    sw.dataset.baseColor || initial,
                    _tvToNumber(sw.dataset.opacity, 100),
                    overlay,
                    function(newColor, newOpacity) {
                        sw.dataset.baseColor = newColor;
                        sw.dataset.opacity = String(newOpacity);
                        sw.style.background = _tvColorWithOpacity(newColor, newOpacity, newColor);
                        onChange(_tvColorWithOpacity(newColor, newOpacity, newColor));
                    }
                );
            });
            wrap.appendChild(sw);
        }
        makeSwatch(upValue, onUp);
        makeSwatch(downValue, onDown);
        return wrap;
    }

    function _ssColorControl(value, onColor) {
        var wrap = document.createElement('div');
        wrap.style.cssText = 'display:flex;align-items:center;gap:8px;';
        var swatch = document.createElement('div');
        swatch.className = 'ts-swatch';
        swatch.dataset.baseColor = _tvColorToHex(value || '#4c87ff', '#4c87ff');
        swatch.dataset.opacity = String(_tvColorOpacityPercent(value, 100));
        swatch.style.background = value;
        swatch.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            _tvShowColorOpacityPopup(
                swatch,
                swatch.dataset.baseColor || value,
                _tvToNumber(swatch.dataset.opacity, 100),
                overlay,
                function(newColor, newOpacity) {
                    swatch.dataset.baseColor = newColor;
                    swatch.dataset.opacity = String(newOpacity);
                    swatch.style.background = _tvColorWithOpacity(newColor, newOpacity, newColor);
                    onColor(_tvColorWithOpacity(newColor, newOpacity, newColor));
                }
            );
        });
        wrap.appendChild(swatch);
        return wrap;
    }

    function _ssIsCandleStyle(styleName) {
        var s = String(styleName || '');
        return s === 'Candles' || s === 'Hollow candles';
    }

    function _ssIsHlcAreaStyle(styleName) {
        return String(styleName || '') === 'HLC area';
    }

    function _ssIsLineLikeStyle(styleName) {
        var s = String(styleName || '');
        return s === 'Line' || s === 'Line with markers' || s === 'Step line';
    }

    function _ssPriceFormatFromTick(value) {
        var v = String(value || 'Default');
        if (v === 'Default') return null;
        if (v === 'Integer') {
            return { type: 'price', precision: 0, minMove: 1 };
        }
        var decMatch = v.match(/^(\d+)\s+decimals?$/i);
        if (decMatch) {
            var precision = _tvClamp(parseInt(decMatch[1], 10) || 0, 0, 15);
            return { type: 'price', precision: precision, minMove: Math.pow(10, -precision) };
        }
        if (v.indexOf('1/') === 0) {
            var denom = parseInt(v.slice(2), 10);
            if (isFinite(denom) && denom > 0) {
                var minMove = 1 / denom;
                var text = String(minMove);
                var precisionFromText = (text.indexOf('.') >= 0) ? (text.split('.')[1] || '').length : 0;
                var precision = _tvClamp(precisionFromText, 1, 8);
                return { type: 'price', precision: precision, minMove: minMove };
            }
        }
        return null;
    }

    function _ssTypeToStyleName(lwcType) {
        var t = String(lwcType || 'Line');
        if (t === 'Candlestick') return 'Candles';
        if (t === 'Bar') return 'Bars';
        if (t === 'Histogram') return 'Columns';
        return t; // Line, Area, Baseline map 1:1
    }

    function _ssStyleConfig(styleName) {
        var s = String(styleName || 'Line');
        if (s === 'Bars') return { seriesType: 'Bar', source: 'close', optionPatch: {} };
        if (s === 'Candles') return { seriesType: 'Candlestick', source: 'close', optionPatch: {} };
        if (s === 'Hollow candles') {
            return {
                seriesType: 'Candlestick',
                source: 'close',
                optionPatch: {
                    upColor: _cssVar('--pywry-tvchart-hollow-up-body') || 'rgba(0, 0, 0, 0)',
                    priceLineColor: _cssVar('--pywry-tvchart-price-line') || _cssVar('--pywry-tvchart-up') || '#26a69a',
                },
            };
        }
        if (s === 'Columns') return { seriesType: 'Histogram', source: 'close', optionPatch: {} };
        if (s === 'Line') return { seriesType: 'Line', source: 'close', optionPatch: {} };
        if (s === 'Line with markers') {
            return {
                seriesType: 'Line',
                source: 'close',
                optionPatch: {
                    pointMarkersVisible: true,
                },
            };
        }
        if (s === 'Step line') {
            return {
                seriesType: 'Line',
                source: 'close',
                optionPatch: {
                    lineType: 1,
                },
            };
        }
        if (s === 'Area') return { seriesType: 'Area', source: 'close', optionPatch: {} };
        if (s === 'HLC area') return { seriesType: 'Area', source: 'close', optionPatch: {}, composite: 'hlcArea' };
        if (s === 'Baseline') return { seriesType: 'Baseline', source: 'close', optionPatch: {} };
        if (s === 'HLC bars') return { seriesType: 'Bar', source: 'hlc3', optionPatch: {} };
        if (s === 'High-low') return { seriesType: 'Bar', source: 'close', optionPatch: {} };
        return { seriesType: 'Line', source: 'close', optionPatch: {} };
    }

    function _ssToNumber(v, fallback) {
        var n = Number(v);
        return isFinite(n) ? n : fallback;
    }

    function _ssSourceValue(row, source) {
        var r = row || {};
        var o = _ssToNumber(r.open, _ssToNumber(r.value, null));
        var h = _ssToNumber(r.high, o);
        var l = _ssToNumber(r.low, o);
        var c = _ssToNumber(r.close, _ssToNumber(r.value, o));
        if (source === 'open') return o;
        if (source === 'high') return h;
        if (source === 'low') return l;
        if (source === 'hl2') return (h + l) / 2;
        if (source === 'hlc3') return (h + l + c) / 3;
        if (source === 'ohlc4') return (o + h + l + c) / 4;
        return c;
    }

    function _ssBuildBarsForStyle(rawBars, styleName, seriesType, source) {
        var src = Array.isArray(rawBars) ? rawBars : [];
        if (!src.length) return [];

        var out = [];
        var prevClose = null;
        for (var i = 0; i < src.length; i++) {
            var row = src[i] || {};
            if (row.time == null) continue;

            if (seriesType === 'Line' || seriesType === 'Area' || seriesType === 'Baseline' || seriesType === 'Histogram') {
                out.push({
                    time: row.time,
                    value: _ssSourceValue(row, source),
                });
                continue;
            }

            var base = _ssSourceValue(row, source);
            var open = _ssToNumber(row.open, _ssToNumber(row.value, base));
            var high = _ssToNumber(row.high, Math.max(open, base));
            var low = _ssToNumber(row.low, Math.min(open, base));
            var close = _ssToNumber(row.close, _ssToNumber(row.value, base));

            if (styleName === 'HLC bars') {
                var hlc = _ssSourceValue(row, 'hlc3');
                var o = (prevClose == null) ? hlc : prevClose;
                var c = hlc;
                open = o;
                close = c;
                high = Math.max(o, c);
                low = Math.min(o, c);
                prevClose = c;
            } else if (styleName === 'High-low') {
                var hh = _ssToNumber(row.high, base);
                var ll = _ssToNumber(row.low, base);
                open = ll;
                close = hh;
                high = hh;
                low = ll;
                prevClose = close;
            } else {
                prevClose = close;
            }

            out.push({
                time: row.time,
                open: open,
                high: high,
                low: low,
                close: close,
            });
        }
        return out;
    }

    function _ssLooksLikeOhlcBars(rows) {
        if (!Array.isArray(rows) || !rows.length) return false;
        for (var i = 0; i < rows.length; i++) {
            var r = rows[i] || {};
            if (r.open !== undefined && r.high !== undefined && r.low !== undefined && r.close !== undefined) {
                return true;
            }
        }
        return false;
    }

    function renderBody() {
        body.innerHTML = '';
        if (activeTab === 'style') {
            var styleRow = _ssRow('Style');
            styleRow.ctrl.appendChild(_ssSelect([
                { v: 'Bars', l: 'Bars' },
                { v: 'Candles', l: 'Candles' },
                { v: 'Hollow candles', l: 'Hollow candles' },
                { v: 'Columns', l: 'Columns' },
                { v: 'Line', l: 'Line' },
                { v: 'Line with markers', l: 'Line with markers' },
                { v: 'Step line', l: 'Step line' },
                { v: 'Area', l: 'Area' },
                { v: 'HLC area', l: 'HLC area' },
                { v: 'Baseline', l: 'Baseline' },
                { v: 'HLC bars', l: 'HLC bars' },
                { v: 'High-low', l: 'High-low' },
            ], draft.style, function(v) {
                draft.style = v;
                renderBody();
            }));
            body.appendChild(styleRow.row);

            var selectedStyle = String(draft.style || 'Line');
            if (_ssIsCandleStyle(selectedStyle)) {
                var bodyRow = _ssRow('Body');
                var bodyWrap = document.createElement('div');
                bodyWrap.style.cssText = 'display:flex;align-items:center;gap:10px;';
                bodyWrap.appendChild(_ssCheckbox(draft.bodyVisible !== false, function(v) { draft.bodyVisible = v; }));
                bodyWrap.appendChild(_ssDualColorControl(
                    draft.bodyUpColor,
                    draft.bodyDownColor,
                    function(v) { draft.bodyUpColor = v; },
                    function(v) { draft.bodyDownColor = v; }
                ));
                bodyRow.ctrl.appendChild(bodyWrap);
                body.appendChild(bodyRow.row);

                var borderRow = _ssRow('Borders');
                var borderWrap = document.createElement('div');
                borderWrap.style.cssText = 'display:flex;align-items:center;gap:10px;';
                borderWrap.appendChild(_ssCheckbox(draft.bordersVisible !== false, function(v) { draft.bordersVisible = v; }));
                borderWrap.appendChild(_ssDualColorControl(
                    draft.borderUpColor,
                    draft.borderDownColor,
                    function(v) { draft.borderUpColor = v; },
                    function(v) { draft.borderDownColor = v; }
                ));
                borderRow.ctrl.appendChild(borderWrap);
                body.appendChild(borderRow.row);

                var wickRow = _ssRow('Wick');
                var wickWrap = document.createElement('div');
                wickWrap.style.cssText = 'display:flex;align-items:center;gap:10px;';
                wickWrap.appendChild(_ssCheckbox(draft.wickVisible !== false, function(v) { draft.wickVisible = v; }));
                wickWrap.appendChild(_ssDualColorControl(
                    draft.wickUpColor,
                    draft.wickDownColor,
                    function(v) { draft.wickUpColor = v; },
                    function(v) { draft.wickDownColor = v; }
                ));
                wickRow.ctrl.appendChild(wickWrap);
                body.appendChild(wickRow.row);
            } else if (_ssIsHlcAreaStyle(selectedStyle)) {
                var highRow = _ssRow('High line');
                var highWrap = document.createElement('div');
                highWrap.style.cssText = 'display:flex;align-items:center;gap:10px;';
                highWrap.appendChild(_ssCheckbox(draft.hlcHighVisible !== false, function(v) { draft.hlcHighVisible = v; }));
                highWrap.appendChild(_ssColorLineControl(draft.hlcHighColor, draft.lineWidth, function(v) { draft.hlcHighColor = v; }, function() {}));
                highRow.ctrl.appendChild(highWrap);
                body.appendChild(highRow.row);

                var lowRow = _ssRow('Low line');
                var lowWrap = document.createElement('div');
                lowWrap.style.cssText = 'display:flex;align-items:center;gap:10px;';
                lowWrap.appendChild(_ssCheckbox(draft.hlcLowVisible !== false, function(v) { draft.hlcLowVisible = v; }));
                lowWrap.appendChild(_ssColorLineControl(draft.hlcLowColor, draft.lineWidth, function(v) { draft.hlcLowColor = v; }, function() {}));
                lowRow.ctrl.appendChild(lowWrap);
                body.appendChild(lowRow.row);

                var closeLineRow = _ssRow('Close line');
                closeLineRow.ctrl.appendChild(_ssColorLineControl(draft.hlcCloseColor, draft.lineWidth, function(v) { draft.hlcCloseColor = v; }, function() {}));
                body.appendChild(closeLineRow.row);

                var fillRow = _ssRow('Fill');
                fillRow.ctrl.appendChild(_ssDualColorControl(
                    draft.hlcFillTopColor,
                    draft.hlcFillBottomColor,
                    function(v) { draft.hlcFillTopColor = v; },
                    function(v) { draft.hlcFillBottomColor = v; }
                ));
                body.appendChild(fillRow.row);
            } else if (selectedStyle === 'Area') {
                var areaSourceRow = _ssRow('Price source');
                areaSourceRow.ctrl.appendChild(_ssSelect([
                    { v: 'open', l: 'Open' },
                    { v: 'high', l: 'High' },
                    { v: 'low', l: 'Low' },
                    { v: 'close', l: 'Close' },
                    { v: 'hl2', l: '(H + L)/2' },
                    { v: 'hlc3', l: '(H + L + C)/3' },
                    { v: 'ohlc4', l: '(O + H + L + C)/4' },
                ], draft.priceSource, function(v) { draft.priceSource = v; }));
                body.appendChild(areaSourceRow.row);

                var areaLineRow = _ssRow('Line');
                var areaWidthSync = function() {};
                areaLineRow.ctrl.appendChild(_ssColorLineControl(
                    draft.color,
                    draft.lineWidth,
                    function(v) { draft.color = v; },
                    function(sync) { areaWidthSync = sync; }
                ));
                body.appendChild(areaLineRow.row);

                var areaWidthRow = _ssRow('Line width');
                areaWidthRow.ctrl.appendChild(_ssSelect([
                    { v: 1, l: '1px' },
                    { v: 2, l: '2px' },
                    { v: 3, l: '3px' },
                    { v: 4, l: '4px' },
                ], draft.lineWidth, function(v) {
                    draft.lineWidth = _tvClamp(_tvToNumber(v, 2), 1, 4);
                    areaWidthSync(draft.lineWidth);
                }));
                body.appendChild(areaWidthRow.row);

                var areaFillRow = _ssRow('Fill');
                areaFillRow.ctrl.appendChild(_ssDualColorControl(
                    draft.areaTopColor,
                    draft.areaBottomColor,
                    function(v) { draft.areaTopColor = v; },
                    function(v) { draft.areaBottomColor = v; }
                ));
                body.appendChild(areaFillRow.row);
            } else if (selectedStyle === 'Baseline') {
                var baseSourceRow = _ssRow('Price source');
                baseSourceRow.ctrl.appendChild(_ssSelect([
                    { v: 'open', l: 'Open' },
                    { v: 'high', l: 'High' },
                    { v: 'low', l: 'Low' },
                    { v: 'close', l: 'Close' },
                    { v: 'hl2', l: '(H + L)/2' },
                    { v: 'hlc3', l: '(H + L + C)/3' },
                    { v: 'ohlc4', l: '(O + H + L + C)/4' },
                ], draft.priceSource, function(v) { draft.priceSource = v; }));
                body.appendChild(baseSourceRow.row);

                var topLineRow = _ssRow('Top line');
                topLineRow.ctrl.appendChild(_ssColorControl(draft.baselineTopLineColor, function(v) { draft.baselineTopLineColor = v; }));
                body.appendChild(topLineRow.row);

                var bottomLineRow = _ssRow('Bottom line');
                bottomLineRow.ctrl.appendChild(_ssColorControl(draft.baselineBottomLineColor, function(v) { draft.baselineBottomLineColor = v; }));
                body.appendChild(bottomLineRow.row);

                var topFillRow = _ssRow('Top fill');
                topFillRow.ctrl.appendChild(_ssDualColorControl(
                    draft.baselineTopFillColor1,
                    draft.baselineTopFillColor2,
                    function(v) { draft.baselineTopFillColor1 = v; },
                    function(v) { draft.baselineTopFillColor2 = v; }
                ));
                body.appendChild(topFillRow.row);

                var bottomFillRow = _ssRow('Bottom fill');
                bottomFillRow.ctrl.appendChild(_ssDualColorControl(
                    draft.baselineBottomFillColor1,
                    draft.baselineBottomFillColor2,
                    function(v) { draft.baselineBottomFillColor1 = v; },
                    function(v) { draft.baselineBottomFillColor2 = v; }
                ));
                body.appendChild(bottomFillRow.row);

                var baseValueRow = _ssRow('Base level');
                var baseLevelWrap = document.createElement('span');
                baseLevelWrap.style.display = 'inline-flex';
                baseLevelWrap.style.alignItems = 'center';
                baseLevelWrap.style.gap = '4px';
                var baseValueInput = document.createElement('input');
                baseValueInput.type = 'number';
                baseValueInput.className = 'ts-input';
                baseValueInput.style.width = '80px';
                baseValueInput.min = '0';
                baseValueInput.max = '100';
                baseValueInput.value = String(_tvToNumber(draft.baselineBaseLevel, 50));
                baseValueInput.addEventListener('input', function() {
                    draft.baselineBaseLevel = _tvClamp(_tvToNumber(baseValueInput.value, 50), 0, 100);
                });
                var pctLabel = document.createElement('span');
                pctLabel.textContent = '%';
                pctLabel.style.opacity = '0.6';
                baseLevelWrap.appendChild(baseValueInput);
                baseLevelWrap.appendChild(pctLabel);
                baseValueRow.ctrl.appendChild(baseLevelWrap);
                body.appendChild(baseValueRow.row);
            } else if (selectedStyle === 'Columns') {
                var columnsSourceRow = _ssRow('Price source');
                columnsSourceRow.ctrl.appendChild(_ssSelect([
                    { v: 'open', l: 'Open' },
                    { v: 'high', l: 'High' },
                    { v: 'low', l: 'Low' },
                    { v: 'close', l: 'Close' },
                    { v: 'hl2', l: '(H + L)/2' },
                    { v: 'hlc3', l: '(H + L + C)/3' },
                    { v: 'ohlc4', l: '(O + H + L + C)/4' },
                ], draft.priceSource, function(v) { draft.priceSource = v; }));
                body.appendChild(columnsSourceRow.row);

                var columnsColorRow = _ssRow('Columns');
                columnsColorRow.ctrl.appendChild(_ssDualColorControl(
                    draft.columnsUpColor,
                    draft.columnsDownColor,
                    function(v) { draft.columnsUpColor = v; },
                    function(v) { draft.columnsDownColor = v; }
                ));
                body.appendChild(columnsColorRow.row);
            } else if (selectedStyle === 'Bars' || selectedStyle === 'HLC bars' || selectedStyle === 'High-low') {
                if (selectedStyle === 'Bars') {
                    var barsSourceRow = _ssRow('Price source');
                    barsSourceRow.ctrl.appendChild(_ssSelect([
                        { v: 'open', l: 'Open' },
                        { v: 'high', l: 'High' },
                        { v: 'low', l: 'Low' },
                        { v: 'close', l: 'Close' },
                        { v: 'hl2', l: '(H + L)/2' },
                        { v: 'hlc3', l: '(H + L + C)/3' },
                        { v: 'ohlc4', l: '(O + H + L + C)/4' },
                    ], draft.priceSource, function(v) { draft.priceSource = v; }));
                    body.appendChild(barsSourceRow.row);
                }

                var barsColorRow = _ssRow('Up/Down colors');
                barsColorRow.ctrl.appendChild(_ssDualColorControl(
                    draft.barsUpColor,
                    draft.barsDownColor,
                    function(v) { draft.barsUpColor = v; },
                    function(v) { draft.barsDownColor = v; }
                ));
                body.appendChild(barsColorRow.row);

                var openTickRow = _ssRow('Open tick');
                openTickRow.ctrl.appendChild(_ssCheckbox(draft.barsOpenVisible !== false, function(v) { draft.barsOpenVisible = v; }));
                body.appendChild(openTickRow.row);
            } else {
                var sourceRow = _ssRow('Price source');
                sourceRow.ctrl.appendChild(_ssSelect([
                    { v: 'open', l: 'Open' },
                    { v: 'high', l: 'High' },
                    { v: 'low', l: 'Low' },
                    { v: 'close', l: 'Close' },
                    { v: 'hl2', l: '(H + L)/2' },
                    { v: 'hlc3', l: '(H + L + C)/3' },
                    { v: 'ohlc4', l: '(O + H + L + C)/4' },
                ], draft.priceSource, function(v) { draft.priceSource = v; }));
                body.appendChild(sourceRow.row);

                var lineRow = _ssRow('Line');
                var widthSync = function() {};
                var lineCtrl = _ssColorLineControl(draft.color, draft.lineWidth, function(v) { draft.color = v; }, function(sync) { widthSync = sync; });
                lineRow.ctrl.appendChild(lineCtrl);
                body.appendChild(lineRow.row);

                var widthRow = _ssRow('Line width');
                widthRow.ctrl.appendChild(_ssSelect([
                    { v: 1, l: '1px' },
                    { v: 2, l: '2px' },
                    { v: 3, l: '3px' },
                    { v: 4, l: '4px' },
                ], draft.lineWidth, function(v) {
                    draft.lineWidth = _tvClamp(_tvToNumber(v, 2), 1, 4);
                    widthSync(draft.lineWidth);
                }));
                body.appendChild(widthRow.row);

                if (selectedStyle === 'Line with markers') {
                    var markersRow = _ssRow('Markers');
                    markersRow.ctrl.appendChild(_ssCheckbox(draft.markersVisible !== false, function(v) {
                        draft.markersVisible = v;
                    }));
                    body.appendChild(markersRow.row);
                }
            }

            var priceLineRow = _ssRow('Price line');
            priceLineRow.ctrl.appendChild(_ssCheckbox(draft.priceLineVisible, function(v) { draft.priceLineVisible = v; }));
            body.appendChild(priceLineRow.row);

            var tickRow = _ssRow('Override min tick');
            tickRow.ctrl.appendChild(_ssSelect([
                { v: 'Default', l: 'Default' },
                { v: 'Integer', l: 'Integer' },
                { v: '1 decimals', l: '1 decimal' },
                { v: '2 decimals', l: '2 decimals' },
                { v: '3 decimals', l: '3 decimals' },
                { v: '4 decimals', l: '4 decimals' },
                { v: '5 decimals', l: '5 decimals' },
                { v: '6 decimals', l: '6 decimals' },
                { v: '7 decimals', l: '7 decimals' },
                { v: '8 decimals', l: '8 decimals' },
                { v: '9 decimals', l: '9 decimals' },
                { v: '10 decimals', l: '10 decimals' },
                { v: '11 decimals', l: '11 decimals' },
                { v: '12 decimals', l: '12 decimals' },
                { v: '13 decimals', l: '13 decimals' },
                { v: '14 decimals', l: '14 decimals' },
                { v: '15 decimals', l: '15 decimals' },
                { v: '1/2', l: '1/2' },
                { v: '1/4', l: '1/4' },
                { v: '1/8', l: '1/8' },
                { v: '1/16', l: '1/16' },
                { v: '1/32', l: '1/32' },
                { v: '1/64', l: '1/64' },
                { v: '1/128', l: '1/128' },
                { v: '1/320', l: '1/320' },
            ], draft.overrideMinTick, function(v) { draft.overrideMinTick = v; }));
            body.appendChild(tickRow.row);
        } else {
            var visibilityDefs = [
                { key: 'seconds', label: 'Seconds', max: 59 },
                { key: 'minutes', label: 'Minutes', max: 59 },
                { key: 'hours', label: 'Hours', max: 24 },
                { key: 'days', label: 'Days', max: 366 },
                { key: 'weeks', label: 'Weeks', max: 52 },
                { key: 'months', label: 'Months', max: 12 },
            ];
            for (var vi = 0; vi < visibilityDefs.length; vi++) {
                (function(def) {
                    var cfg = draft.visibilityIntervals[def.key] || { enabled: true, min: 1, max: def.max };
                    var row = document.createElement('div');
                    row.className = 'tv-settings-row tv-settings-row-spaced';
                    row.style.alignItems = 'center';

                    var lhs = document.createElement('div');
                    lhs.style.cssText = 'display:flex;align-items:center;gap:10px;min-width:120px;';
                    var cb = _ssCheckbox(cfg.enabled !== false, function(v) {
                        cfg.enabled = !!v;
                        draft.visibilityIntervals[def.key] = cfg;
                    });
                    lhs.appendChild(cb);
                    var lbl = document.createElement('span');
                    lbl.textContent = def.label;
                    lbl.style.color = 'var(--pywry-tvchart-text)';
                    lhs.appendChild(lbl);
                    row.appendChild(lhs);

                    var minInput = document.createElement('input');
                    minInput.type = 'number';
                    minInput.className = 'ts-input';
                    minInput.style.width = '74px';
                    minInput.min = '1';
                    minInput.max = String(def.max);
                    minInput.value = String(_tvClamp(_tvToNumber(cfg.min, 1), 1, def.max));
                    row.appendChild(minInput);

                    var track = document.createElement('div');
                    track.style.cssText = 'position:relative;flex:1;min-width:130px;max-width:190px;height:14px;';
                    var rail = document.createElement('div');
                    rail.style.cssText = 'position:absolute;left:0;right:0;top:6px;height:3px;border-radius:3px;background:var(--pywry-tvchart-border-strong);';
                    var leftKnob = document.createElement('span');
                    var rightKnob = document.createElement('span');
                    leftKnob.style.cssText = 'position:absolute;top:1px;width:12px;height:12px;border-radius:50%;background:var(--pywry-tvchart-panel-bg);border:2px solid #fff;box-sizing:border-box;';
                    rightKnob.style.cssText = 'position:absolute;top:1px;width:12px;height:12px;border-radius:50%;background:var(--pywry-tvchart-panel-bg);border:2px solid #fff;box-sizing:border-box;';
                    track.appendChild(rail);
                    track.appendChild(leftKnob);
                    track.appendChild(rightKnob);
                    row.appendChild(track);

                    var maxInput = document.createElement('input');
                    maxInput.type = 'number';
                    maxInput.className = 'ts-input';
                    maxInput.style.width = '74px';
                    maxInput.min = '1';
                    maxInput.max = String(def.max);
                    maxInput.value = String(_tvClamp(_tvToNumber(cfg.max, def.max), 1, def.max));
                    row.appendChild(maxInput);

                    function syncKnobs() {
                        var minVal = _tvClamp(_tvToNumber(minInput.value, 1), 1, def.max);
                        var maxVal = _tvClamp(_tvToNumber(maxInput.value, def.max), 1, def.max);
                        if (minVal > maxVal) {
                            if (document.activeElement === minInput) maxVal = minVal;
                            else minVal = maxVal;
                        }
                        minInput.value = String(minVal);
                        maxInput.value = String(maxVal);
                        cfg.min = minVal;
                        cfg.max = maxVal;
                        draft.visibilityIntervals[def.key] = cfg;
                        var lp = ((minVal - 1) / Math.max(def.max - 1, 1)) * 100;
                        var rp = ((maxVal - 1) / Math.max(def.max - 1, 1)) * 100;
                        leftKnob.style.left = 'calc(' + lp + '% - 6px)';
                        rightKnob.style.left = 'calc(' + rp + '% - 6px)';
                    }

                    minInput.addEventListener('input', syncKnobs);
                    maxInput.addEventListener('input', syncKnobs);
                    syncKnobs();
                    body.appendChild(row);
                })(visibilityDefs[vi]);
            }
        }
    }

    styleTab.addEventListener('click', function() {
        activeTab = 'style';
        styleTab.classList.add('active');
        visTab.classList.remove('active');
        renderBody();
    });
    visTab.addEventListener('click', function() {
        activeTab = 'visibility';
        visTab.classList.add('active');
        styleTab.classList.remove('active');
        renderBody();
    });

    var footer = document.createElement('div');
    footer.className = 'tv-settings-footer';
    footer.style.position = 'relative';

    var defaultsWrap = document.createElement('div');
    defaultsWrap.className = 'tv-settings-template-wrap';
    var defaultsBtn = document.createElement('button');
    defaultsBtn.className = 'ts-btn-template';
    defaultsBtn.textContent = 'Defaults';
    defaultsWrap.appendChild(defaultsBtn);
    var defaultsMenu = null;
    function closeDefaultsMenu() {
        if (defaultsMenu && defaultsMenu.parentNode) defaultsMenu.parentNode.removeChild(defaultsMenu);
        defaultsMenu = null;
        defaultsBtn.classList.remove('open');
    }
    defaultsBtn.addEventListener('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        if (defaultsMenu) {
            closeDefaultsMenu();
            return;
        }
        defaultsMenu = document.createElement('div');
        defaultsMenu.className = 'tv-settings-template-menu';
        var resetBtn = document.createElement('button');
        resetBtn.className = 'tv-settings-template-item';
        resetBtn.textContent = 'Reset settings';
        resetBtn.addEventListener('click', function() {
            draft = _tvMerge({}, initialState);
            renderBody();
            closeDefaultsMenu();
        });
        defaultsMenu.appendChild(resetBtn);
        var saveBtn = document.createElement('button');
        saveBtn.className = 'tv-settings-template-item';
        saveBtn.textContent = 'Save as default';
        saveBtn.addEventListener('click', function() { closeDefaultsMenu(); });
        defaultsMenu.appendChild(saveBtn);
        defaultsWrap.appendChild(defaultsMenu);
        defaultsBtn.classList.add('open');
    });
    overlay.addEventListener('mousedown', function(e) {
        if (defaultsMenu && defaultsWrap && !defaultsWrap.contains(e.target)) closeDefaultsMenu();
    });
    footer.appendChild(defaultsWrap);

    var cancelBtn = document.createElement('button');
    cancelBtn.className = 'ts-btn-cancel';
    cancelBtn.textContent = 'Cancel';
    cancelBtn.addEventListener('click', function() { _tvHideSeriesSettings(); });
    footer.appendChild(cancelBtn);

    var okBtn = document.createElement('button');
    okBtn.className = 'ts-btn-ok';
    okBtn.textContent = 'Ok';
    okBtn.addEventListener('click', function() {
        var selectedStyle = String(draft.style || 'Line');
        var cfg = _ssStyleConfig(selectedStyle);
        var targetType = cfg.seriesType;

        // Fast path: series type unchanged — just applyOptions, never recreate.
        var oldSeries = entry.seriesMap ? entry.seriesMap[seriesId] : null;
        var oldType = oldSeries ? _tvGuessSeriesType(oldSeries) : null;
        if (oldSeries && oldType === targetType
            && selectedStyle !== 'Columns' && !_ssIsHlcAreaStyle(selectedStyle)) {
            var patchOpts = {};

            if (_ssIsCandleStyle(selectedStyle)) {
                var hidden = _cssVar('--pywry-tvchart-hidden') || 'rgba(0, 0, 0, 0)';
                var hollowBody = _cssVar('--pywry-tvchart-hollow-up-body') || hidden;
                patchOpts.upColor = (draft.bodyVisible !== false) ? draft.bodyUpColor : hidden;
                patchOpts.downColor = (draft.bodyVisible !== false) ? draft.bodyDownColor : hidden;
                patchOpts.borderUpColor = (draft.bordersVisible !== false) ? draft.borderUpColor : hidden;
                patchOpts.borderDownColor = (draft.bordersVisible !== false) ? draft.borderDownColor : hidden;
                patchOpts.wickUpColor = (draft.wickVisible !== false) ? draft.wickUpColor : hidden;
                patchOpts.wickDownColor = (draft.wickVisible !== false) ? draft.wickDownColor : hidden;
                if (selectedStyle === 'Hollow candles') patchOpts.upColor = hollowBody;
            } else if (_ssIsLineLikeStyle(selectedStyle)) {
                patchOpts.color = draft.color;
                patchOpts.lineColor = draft.color;
                patchOpts.lineWidth = _tvClamp(_tvToNumber(draft.lineWidth, 2), 1, 4);
                patchOpts.pointMarkersVisible = selectedStyle === 'Line with markers' ? (draft.markersVisible !== false) : false;
                patchOpts.lineType = selectedStyle === 'Step line' ? 1 : 0;
            } else if (selectedStyle === 'Area') {
                patchOpts.lineColor = draft.color;
                patchOpts.topColor = draft.areaTopColor;
                patchOpts.bottomColor = draft.areaBottomColor;
                patchOpts.lineWidth = _tvClamp(_tvToNumber(draft.lineWidth, 2), 1, 4);
            } else if (selectedStyle === 'Baseline') {
                patchOpts.topLineColor = draft.baselineTopLineColor;
                patchOpts.bottomLineColor = draft.baselineBottomLineColor;
                patchOpts.topFillColor1 = draft.baselineTopFillColor1;
                patchOpts.topFillColor2 = draft.baselineTopFillColor2;
                patchOpts.bottomFillColor1 = draft.baselineBottomFillColor1;
                patchOpts.bottomFillColor2 = draft.baselineBottomFillColor2;
                patchOpts.lineWidth = _tvClamp(_tvToNumber(draft.lineWidth, 2), 1, 4);
            } else if (selectedStyle === 'Bars' || selectedStyle === 'HLC bars' || selectedStyle === 'High-low') {
                patchOpts.upColor = draft.barsUpColor;
                patchOpts.downColor = draft.barsDownColor;
                patchOpts.openVisible = draft.barsOpenVisible !== false;
            }

            var tickPriceFormat = _ssPriceFormatFromTick(draft.overrideMinTick);
            if (tickPriceFormat) patchOpts.priceFormat = tickPriceFormat;

            try { oldSeries.applyOptions(patchOpts); } catch (e) {}

            // Persist preferences
            if (!entry._seriesStylePrefs) entry._seriesStylePrefs = {};
            entry._seriesStylePrefs[seriesId] = {
                style: draft.style,
                priceSource: draft.priceSource,
                color: draft.color,
                lineWidth: draft.lineWidth,
                markersVisible: draft.markersVisible,
                areaTopColor: draft.areaTopColor,
                areaBottomColor: draft.areaBottomColor,
                baselineTopLineColor: draft.baselineTopLineColor,
                baselineBottomLineColor: draft.baselineBottomLineColor,
                baselineTopFillColor1: draft.baselineTopFillColor1,
                baselineTopFillColor2: draft.baselineTopFillColor2,
                baselineBottomFillColor1: draft.baselineBottomFillColor1,
                baselineBottomFillColor2: draft.baselineBottomFillColor2,
                baselineBaseLevel: draft.baselineBaseLevel,
                columnsUpColor: draft.columnsUpColor,
                columnsDownColor: draft.columnsDownColor,
                barsUpColor: draft.barsUpColor,
                barsDownColor: draft.barsDownColor,
                barsOpenVisible: draft.barsOpenVisible,
                bodyVisible: draft.bodyVisible,
                bordersVisible: draft.bordersVisible,
                wickVisible: draft.wickVisible,
                bodyUpColor: draft.bodyUpColor,
                bodyDownColor: draft.bodyDownColor,
                borderUpColor: draft.borderUpColor,
                borderDownColor: draft.borderDownColor,
                wickUpColor: draft.wickUpColor,
                wickDownColor: draft.wickDownColor,
                priceLineVisible: draft.priceLineVisible,
                overrideMinTick: draft.overrideMinTick,
                hlcHighVisible: draft.hlcHighVisible,
                hlcLowVisible: draft.hlcLowVisible,
                hlcCloseVisible: draft.hlcCloseVisible,
                hlcHighColor: draft.hlcHighColor,
                hlcLowColor: draft.hlcLowColor,
                hlcCloseColor: draft.hlcCloseColor,
                hlcFillTopColor: draft.hlcFillTopColor,
                hlcFillBottomColor: draft.hlcFillBottomColor,
            };
            if (!entry._seriesVisibilityIntervals) entry._seriesVisibilityIntervals = {};
            entry._seriesVisibilityIntervals[seriesId] = _tvMerge({}, draft.visibilityIntervals || {});

            // Update legend color
            var legendColor = draft.color;
            if (_ssIsCandleStyle(selectedStyle)) legendColor = draft.bodyUpColor;
            if (selectedStyle === 'Columns') legendColor = draft.columnsUpColor;
            if (selectedStyle === 'Bars' || selectedStyle === 'HLC bars' || selectedStyle === 'High-low') legendColor = draft.barsUpColor;
            if (selectedStyle === 'Area') legendColor = draft.color;
            if (selectedStyle === 'Baseline') legendColor = draft.baselineTopLineColor;
            if (!entry._legendSeriesColors) entry._legendSeriesColors = {};
            entry._legendSeriesColors[seriesId] = legendColor;

            _tvHideSeriesSettings();
            _tvRenderHoverLegend(chartId, null);
            return;
        }

        // Full rebuild path — style changed, need to destroy and recreate series
        var sourceForStyle = cfg.source || draft.priceSource || 'close';
        var payloadSeries = _tvFindPayloadSeries(entry, seriesId);
        if (!entry._seriesCanonicalRawData) entry._seriesCanonicalRawData = {};
        var canonicalBars = entry._seriesCanonicalRawData[seriesId];
        var payloadBars = (payloadSeries && Array.isArray(payloadSeries.bars)) ? payloadSeries.bars : [];
        var fallbackBars = (entry._seriesRawData && entry._seriesRawData[seriesId]) ? entry._seriesRawData[seriesId] : [];
        if (!Array.isArray(canonicalBars) || !canonicalBars.length) {
            if (_ssLooksLikeOhlcBars(payloadBars)) {
                canonicalBars = payloadBars;
            } else if (_ssLooksLikeOhlcBars(fallbackBars)) {
                canonicalBars = fallbackBars;
            }
            if (Array.isArray(canonicalBars) && canonicalBars.length) {
                entry._seriesCanonicalRawData[seriesId] = canonicalBars;
            }
        }
        var rawBars = (Array.isArray(canonicalBars) && canonicalBars.length)
            ? canonicalBars
            : (payloadBars.length ? payloadBars : fallbackBars);
        var transformedRawBars = _ssBuildBarsForStyle(rawBars, String(draft.style || ''), targetType, sourceForStyle);
        var normalizedBars = _tvNormalizeBarsForSeriesType(transformedRawBars, targetType);

        if (selectedStyle === 'Columns') {
            var histogramBars = [];
            var prevValue = null;
            for (var ci = 0; ci < rawBars.length; ci++) {
                var crow = rawBars[ci] || {};
                if (crow.time == null) continue;
                var cval = _ssSourceValue(crow, sourceForStyle);
                var isUp = (prevValue == null) ? true : (cval >= prevValue);
                histogramBars.push({
                    time: crow.time,
                    value: cval,
                    color: isUp ? draft.columnsUpColor : draft.columnsDownColor,
                });
                prevValue = cval;
            }
            normalizedBars = histogramBars;
            transformedRawBars = histogramBars;
        }

        var oldSeries = entry.seriesMap ? entry.seriesMap[seriesId] : null;
        var paneIndex = 0;
        if (!_tvIsMainSeriesId(seriesId) && entry._comparePaneBySeries && entry._comparePaneBySeries[seriesId] !== undefined) {
            paneIndex = entry._comparePaneBySeries[seriesId];
        }

        var baseSeriesOptions = _tvBuildSeriesOptions(
            (payloadSeries && payloadSeries.seriesOptions) ? payloadSeries.seriesOptions : {},
            targetType,
            entry.theme
        );

        var rebuiltOptions = _tvMerge(baseSeriesOptions, {
            priceLineVisible: !!draft.priceLineVisible,
            lastValueVisible: !!draft.priceLineVisible,
            visible: draft.visible !== false,
        });

        if (_tvIsMainSeriesId(seriesId)) {
            rebuiltOptions.priceScaleId = _tvResolveScalePlacement(entry);
            if (entry._comparePaneBySeries && entry._comparePaneBySeries.main !== undefined) {
                delete entry._comparePaneBySeries.main;
            }
        }

        if (_ssIsLineLikeStyle(selectedStyle)) {
            rebuiltOptions.color = draft.color;
            rebuiltOptions.lineColor = draft.color;
            rebuiltOptions.lineWidth = _tvClamp(_tvToNumber(draft.lineWidth, 2), 1, 4);
            rebuiltOptions.pointMarkersVisible = selectedStyle === 'Line with markers' ? (draft.markersVisible !== false) : false;
            rebuiltOptions.lineType = selectedStyle === 'Step line' ? 1 : 0;
        } else if (selectedStyle === 'Area') {
            rebuiltOptions.lineColor = draft.color;
            rebuiltOptions.topColor = draft.areaTopColor;
            rebuiltOptions.bottomColor = draft.areaBottomColor;
            rebuiltOptions.lineWidth = _tvClamp(_tvToNumber(draft.lineWidth, 2), 1, 4);
        } else if (selectedStyle === 'Baseline') {
            rebuiltOptions.topLineColor = draft.baselineTopLineColor;
            rebuiltOptions.bottomLineColor = draft.baselineBottomLineColor;
            rebuiltOptions.topFillColor1 = draft.baselineTopFillColor1;
            rebuiltOptions.topFillColor2 = draft.baselineTopFillColor2;
            rebuiltOptions.bottomFillColor1 = draft.baselineBottomFillColor1;
            rebuiltOptions.bottomFillColor2 = draft.baselineBottomFillColor2;
            rebuiltOptions.lineWidth = _tvClamp(_tvToNumber(draft.lineWidth, 2), 1, 4);
            var baseLevel = _tvClamp(_tvToNumber(draft.baselineBaseLevel, 50), 0, 100);
            var basePrice = _tvComputeBaselineValue(rawBars, baseLevel);
            rebuiltOptions.baseValue = { type: 'price', price: basePrice, _level: baseLevel };
        } else if (selectedStyle === 'Columns') {
            rebuiltOptions.color = draft.columnsUpColor;
        } else if (selectedStyle === 'Bars' || selectedStyle === 'HLC bars' || selectedStyle === 'High-low') {
            rebuiltOptions.upColor = draft.barsUpColor;
            rebuiltOptions.downColor = draft.barsDownColor;
            rebuiltOptions.openVisible = draft.barsOpenVisible !== false;
        }

        if (_ssIsCandleStyle(selectedStyle)) {
            var hidden = _cssVar('--pywry-tvchart-hidden') || 'rgba(0, 0, 0, 0)';
            rebuiltOptions.upColor = (draft.bodyVisible !== false) ? draft.bodyUpColor : hidden;
            rebuiltOptions.downColor = (draft.bodyVisible !== false) ? draft.bodyDownColor : hidden;
            rebuiltOptions.borderUpColor = (draft.bordersVisible !== false) ? draft.borderUpColor : hidden;
            rebuiltOptions.borderDownColor = (draft.bordersVisible !== false) ? draft.borderDownColor : hidden;
            rebuiltOptions.wickUpColor = (draft.wickVisible !== false) ? draft.wickUpColor : hidden;
            rebuiltOptions.wickDownColor = (draft.wickVisible !== false) ? draft.wickDownColor : hidden;
        }

        function _ssClearStyleAux() {
            if (!entry._seriesStyleAux || !entry._seriesStyleAux[seriesId]) return;
            var aux = entry._seriesStyleAux[seriesId] || {};
            var keys = Object.keys(aux);
            for (var ai = 0; ai < keys.length; ai++) {
                var key = keys[ai];
                if (key.indexOf('series_') === 0 && aux[key] && entry.chart && typeof entry.chart.removeSeries === 'function') {
                    try { entry.chart.removeSeries(aux[key]); } catch (e) {}
                }
            }
            delete entry._seriesStyleAux[seriesId];
        }

        _ssClearStyleAux();
        rebuiltOptions = _tvMerge(rebuiltOptions, cfg.optionPatch || {});

        // Preserve current scale placement for this series
        try {
            var existingOpts = oldSeries && oldSeries.options ? oldSeries.options() : null;
            if (!_tvIsMainSeriesId(seriesId) && existingOpts && existingOpts.priceScaleId !== undefined) {
                rebuiltOptions.priceScaleId = existingOpts.priceScaleId;
            }
        } catch (e) {}

        var tickPriceFormat = _ssPriceFormatFromTick(draft.overrideMinTick);
        if (tickPriceFormat) rebuiltOptions.priceFormat = tickPriceFormat;

        // Add new series FIRST so the pane is never empty (removing the
        // last series in a pane destroys it and renumbers the rest).
        var newSeries = _tvAddSeriesCompat(entry.chart, targetType, rebuiltOptions, paneIndex);
        try { newSeries.setData(normalizedBars); } catch (e) {}
        if (oldSeries && entry.chart && typeof entry.chart.removeSeries === 'function') {
            try { entry.chart.removeSeries(oldSeries); } catch (e) {}
        }
        entry.seriesMap[seriesId] = newSeries;
        if (!entry._seriesRawData) entry._seriesRawData = {};
        entry._seriesRawData[seriesId] = normalizedBars;

        _tvUpsertPayloadSeries(entry, seriesId, {
            seriesType: targetType,
            bars: transformedRawBars,
            seriesOptions: _tvMerge((payloadSeries && payloadSeries.seriesOptions) ? payloadSeries.seriesOptions : {}, rebuiltOptions),
        });

        var legendColor = draft.color;
        if (selectedStyle === 'Columns') legendColor = draft.columnsUpColor;
        if (selectedStyle === 'Bars' || selectedStyle === 'HLC bars' || selectedStyle === 'High-low') legendColor = draft.barsUpColor;
        if (selectedStyle === 'Area') legendColor = draft.color;
        if (selectedStyle === 'Baseline') legendColor = draft.baselineTopLineColor;

        if (_ssIsHlcAreaStyle(selectedStyle)) {
            var sourceBars = Array.isArray(rawBars) ? rawBars : [];
            var highBars = [];
            var lowBars = [];
            var closeBars = [];
            for (var hi = 0; hi < sourceBars.length; hi++) {
                var r = sourceBars[hi] || {};
                if (r.time == null) continue;
                var h = _ssToNumber(r.high, _ssSourceValue(r, 'close'));
                var l = _ssToNumber(r.low, _ssSourceValue(r, 'close'));
                var c = _ssToNumber(r.close, _ssSourceValue(r, 'close'));
                highBars.push({ time: r.time, value: h });
                lowBars.push({ time: r.time, value: l });
                closeBars.push({ time: r.time, value: c });
            }
            var aux = {
                highVisible: draft.hlcHighVisible !== false,
                lowVisible: draft.hlcLowVisible !== false,
                closeVisible: draft.hlcCloseVisible !== false,
                highColor: draft.hlcHighColor,
                lowColor: draft.hlcLowColor,
                closeColor: draft.hlcCloseColor,
                fillTopColor: draft.hlcFillTopColor,
                fillBottomColor: draft.hlcFillBottomColor,
            };

            var hlcBgColor = _cssVar('--pywry-tvchart-bg');
            var hlcLineW = _tvClamp(_tvToNumber(draft.lineWidth, 1), 1, 4);
            var hlcAuxBase = {
                crosshairMarkerVisible: false,
                lastValueVisible: false,
                priceLineVisible: false,
                priceScaleId: rebuiltOptions.priceScaleId,
            };

            // Main series is the close Area (layer 3) — apply close color + fill-down
            try {
                newSeries.applyOptions({
                    topColor: draft.hlcFillBottomColor,
                    bottomColor: draft.hlcFillBottomColor,
                    lineColor: draft.hlcCloseColor,
                    lineWidth: 2,
                    visible: draft.hlcCloseVisible !== false,
                });
            } catch (e) {}

            // Layer 1: High area (fill-up color from high line down)
            var highSeries = _tvAddSeriesCompat(entry.chart, 'Area', _tvMerge(hlcAuxBase, {
                topColor: draft.hlcFillTopColor,
                bottomColor: draft.hlcFillTopColor,
                lineColor: draft.hlcHighColor,
                lineWidth: hlcLineW,
                visible: draft.hlcHighVisible !== false,
            }), paneIndex);

            // Layer 2: Close mask (opaque background erases fill-up below close)
            var closeMaskSeries = _tvAddSeriesCompat(entry.chart, 'Area', _tvMerge(hlcAuxBase, {
                topColor: hlcBgColor,
                bottomColor: hlcBgColor,
                lineColor: 'transparent',
                lineWidth: 0,
            }), paneIndex);

            // Layer 4: Low mask (opaque background erases fill-down below low + low line)
            var lowMaskSeries = _tvAddSeriesCompat(entry.chart, 'Area', _tvMerge(hlcAuxBase, {
                topColor: hlcBgColor,
                bottomColor: hlcBgColor,
                lineColor: draft.hlcLowColor,
                lineWidth: hlcLineW,
                visible: draft.hlcLowVisible !== false,
            }), paneIndex);

            try { highSeries.setData(highBars); } catch (e) {}
            try { closeMaskSeries.setData(closeBars); } catch (e) {}
            try { lowMaskSeries.setData(lowBars); } catch (e) {}

            aux.series_high = highSeries;
            aux.series_closeMask = closeMaskSeries;
            aux.series_lowMask = lowMaskSeries;
            if (!entry._seriesStyleAux) entry._seriesStyleAux = {};
            entry._seriesStyleAux[seriesId] = aux;
            if (!entry._seriesAuxRawData) entry._seriesAuxRawData = {};
            entry._seriesAuxRawData[seriesId] = { high: highBars, low: lowBars };
            legendColor = draft.hlcCloseColor;
        }

        if (!entry._seriesStylePrefs) entry._seriesStylePrefs = {};
        entry._seriesStylePrefs[seriesId] = {
            style: draft.style,
            priceSource: draft.priceSource,
            color: draft.color,
            lineWidth: draft.lineWidth,
            markersVisible: draft.markersVisible,
            areaTopColor: draft.areaTopColor,
            areaBottomColor: draft.areaBottomColor,
            baselineTopLineColor: draft.baselineTopLineColor,
            baselineBottomLineColor: draft.baselineBottomLineColor,
            baselineTopFillColor1: draft.baselineTopFillColor1,
            baselineTopFillColor2: draft.baselineTopFillColor2,
            baselineBottomFillColor1: draft.baselineBottomFillColor1,
            baselineBottomFillColor2: draft.baselineBottomFillColor2,
            baselineBaseLevel: draft.baselineBaseLevel,
            columnsUpColor: draft.columnsUpColor,
            columnsDownColor: draft.columnsDownColor,
            barsUpColor: draft.barsUpColor,
            barsDownColor: draft.barsDownColor,
            barsOpenVisible: draft.barsOpenVisible,
            bodyVisible: draft.bodyVisible,
            bordersVisible: draft.bordersVisible,
            wickVisible: draft.wickVisible,
            bodyUpColor: draft.bodyUpColor,
            bodyDownColor: draft.bodyDownColor,
            borderUpColor: draft.borderUpColor,
            borderDownColor: draft.borderDownColor,
            wickUpColor: draft.wickUpColor,
            wickDownColor: draft.wickDownColor,
            priceLineVisible: draft.priceLineVisible,
            overrideMinTick: draft.overrideMinTick,
            hlcHighVisible: draft.hlcHighVisible,
            hlcLowVisible: draft.hlcLowVisible,
            hlcCloseVisible: draft.hlcCloseVisible,
            hlcHighColor: draft.hlcHighColor,
            hlcLowColor: draft.hlcLowColor,
            hlcCloseColor: draft.hlcCloseColor,
            hlcFillTopColor: draft.hlcFillTopColor,
            hlcFillBottomColor: draft.hlcFillBottomColor,
        };
        if (!entry._legendSeriesColors) entry._legendSeriesColors = {};
        entry._legendSeriesColors[seriesId] = legendColor;
        if (!entry._seriesVisibilityIntervals) entry._seriesVisibilityIntervals = {};
        entry._seriesVisibilityIntervals[seriesId] = _tvMerge({}, draft.visibilityIntervals || {});
        _tvHideSeriesSettings();
        _tvRenderHoverLegend(chartId, null);
    });
    footer.appendChild(okBtn);
    panel.appendChild(footer);

    renderBody();
    _tvOverlayContainer(chartId).appendChild(overlay);
}

