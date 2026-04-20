function _tvShowIndicatorSettings(seriesId) {
    var info = _activeIndicators[seriesId];
    if (!info) return;
    var chartId = info.chartId;
    var ds = window.__PYWRY_DRAWINGS__[info.chartId] || _tvEnsureDrawingLayer(info.chartId);
    if (!ds || !ds.uiLayer) return;

    var type = info.type || info.name;
    var baseName = info.name.replace(/\s*\(\d+\)\s*$/, '');
    var isBB = !!(info.group && type === 'bollinger-bands');
    var isRSI = baseName === 'RSI';
    var isATR = baseName === 'ATR';
    var isVWAP = baseName === 'VWAP';
    var isVolSMA = baseName === 'Volume SMA';
    var isVP = type === 'volume-profile-fixed' || type === 'volume-profile-visible';
    var isMACD = type === 'macd';
    var isStoch = type === 'stochastic';
    var isAroon = type === 'aroon';
    var isADX = type === 'adx';
    var isKC = type === 'keltner-channels';
    var isIchimoku = type === 'ichimoku';
    var isCCI = baseName === 'CCI';
    var isWilliamsR = baseName === 'Williams %R';
    var isHV = baseName === 'Historical Volatility';
    var isPSAR = type === 'parabolic-sar';
    var isLightweight = type === 'moving-average-ex' || type === 'momentum' || type === 'correlation'
        || type === 'percent-change' || type === 'average-price' || type === 'median-price'
        || type === 'weighted-close' || type === 'spread' || type === 'ratio'
        || type === 'sum' || type === 'product';
    var isBinary = type === 'spread' || type === 'ratio' || type === 'sum' || type === 'product' || type === 'correlation';

    // Source options
    var _SRC_OPTS = [
        { v: 'close', l: 'Close' }, { v: 'open', l: 'Open' },
        { v: 'high', l: 'High' }, { v: 'low', l: 'Low' },
        { v: 'hl2', l: 'HL2' }, { v: 'hlc3', l: 'HLC3' }, { v: 'ohlc4', l: 'OHLC4' },
    ];

    // Collect all series in this group for multi-plot style controls
    var groupSids = [];
    if (info.group) {
        var allK = Object.keys(_activeIndicators);
        for (var gk = 0; gk < allK.length; gk++) {
            if (_activeIndicators[allK[gk]].group === info.group) groupSids.push(allK[gk]);
        }
    } else {
        groupSids = [seriesId];
    }

    var draft = {
        period: info.period,
        color: info.color || '#e6b32c',
        lineWidth: info.lineWidth || 2,
        lineStyle: info.lineStyle || 0,
        multiplier: info.multiplier || 2,
        source: info.source || 'close',
        method: info.method || 'SMA',
        maType: info.maType || 'SMA',
        offset: info.offset || 0,
        primarySource: info.primarySource || 'close',
        secondarySource: info.secondarySource || 'close',
        // Volume Profile-specific draft
        vpRowsLayout: info.rowsLayout || 'rows',          // 'rows' | 'ticks'
        vpRowSize: info.rowSize != null
            ? info.rowSize
            : (info.rowsLayout === 'ticks' ? 1 : (info.bucketCount || info.period || 24)),
        vpVolumeMode: info.volumeMode || 'updown',         // 'updown' | 'total' | 'delta'
        vpPlacement: info.placement || 'right',
        vpWidthPercent: info.widthPercent != null ? info.widthPercent : 15,
        vpValueAreaPct: info.valueAreaPct != null ? Math.round(info.valueAreaPct * 100) : 70,
        vpShowPOC: info.showPOC !== false,
        vpShowValueArea: info.showValueArea !== false,
        vpShowDevelopingPOC: info.showDevelopingPOC === true,
        vpShowDevelopingVA: info.showDevelopingVA === true,
        vpLabelsOnPriceScale: info.labelsOnPriceScale !== false,
        vpValuesInStatusLine: info.valuesInStatusLine !== false,
        vpInputsInStatusLine: info.inputsInStatusLine !== false,
        vpUpColor: info.upColor || _cssVar('--pywry-tvchart-vp-up'),
        vpDownColor: info.downColor || _cssVar('--pywry-tvchart-vp-down'),
        vpVAUpColor: info.vaUpColor || _cssVar('--pywry-tvchart-vp-va-up'),
        vpVADownColor: info.vaDownColor || _cssVar('--pywry-tvchart-vp-va-down'),
        vpPOCColor: info.pocColor || _cssVar('--pywry-tvchart-vp-poc'),
        vpDevelopingPOCColor: info.developingPOCColor || _cssVar('--pywry-tvchart-ind-tertiary'),
        vpDevelopingVAColor: info.developingVAColor || _cssVar('--pywry-tvchart-vp-va-up'),
        // BB-specific fill settings
        showBandFill: info.showBandFill !== undefined ? info.showBandFill : true,
        bandFillColor: info.bandFillColor || '#2196f3',
        bandFillOpacity: info.bandFillOpacity !== undefined ? info.bandFillOpacity : 100,
        // RSI-specific
        smoothingLine: info.smoothingLine || 'SMA',
        smoothingLength: info.smoothingLength || 14,
        // MACD
        fast: info.fast || 12,
        slow: info.slow || 26,
        signal: info.signal || 9,
        macdSource: info.macdSource || info.source || 'close',
        oscMaType: info.oscMaType || 'EMA',
        signalMaType: info.signalMaType || 'EMA',
        // Stochastic — TradingView's "%K Length / %K Smoothing / %D Smoothing"
        kPeriod: info.kPeriod || info.period || 14,
        kSmoothing: info.kSmoothing || 1,
        dPeriod: info.dPeriod || 3,
        // ADX — TradingView splits "ADX Smoothing / DI Length"
        adxSmoothing: info.adxSmoothing || info.period || 14,
        diLength: info.diLength || info.period || 14,
        // Ichimoku — TradingView field names
        conversionPeriod: info.conversionPeriod || info.tenkan || 9,
        basePeriod: info.basePeriod || info.kijun || info.period || 26,
        leadingSpanPeriod: info.leadingSpanPeriod || info.senkouB || 52,
        laggingPeriod: info.laggingPeriod || 26,
        leadingShiftPeriod: info.leadingShiftPeriod || 26,
        // Parabolic SAR
        step: info.step || 0.02,
        maxStep: info.maxStep || 0.2,
        // Historical Volatility
        annualization: info.annualization || 252,
        showUpperLimit: info.showUpperLimit !== false,
        showLowerLimit: info.showLowerLimit !== false,
        showMiddleLimit: info.showMiddleLimit !== undefined ? info.showMiddleLimit : false,
        upperLimitValue: info.upperLimitValue || 70,
        lowerLimitValue: info.lowerLimitValue || 30,
        middleLimitValue: info.middleLimitValue || 50,
        upperLimitColor: info.upperLimitColor || '#787b86',
        lowerLimitColor: info.lowerLimitColor || '#787b86',
        middleLimitColor: info.middleLimitColor || '#787b86',
        showBackground: info.showBackground !== undefined ? info.showBackground : true,
        bgColor: info.bgColor || '#7b1fa2',
        bgOpacity: info.bgOpacity !== undefined ? info.bgOpacity : 0.05,
        // Binary indicator fill/output settings
        showPositiveFill: info.showPositiveFill !== undefined ? info.showPositiveFill : true,
        positiveFillColor: info.positiveFillColor || '#26a69a',
        positiveFillOpacity: info.positiveFillOpacity !== undefined ? info.positiveFillOpacity : 100,
        showNegativeFill: info.showNegativeFill !== undefined ? info.showNegativeFill : true,
        negativeFillColor: info.negativeFillColor || '#ef5350',
        negativeFillOpacity: info.negativeFillOpacity !== undefined ? info.negativeFillOpacity : 100,
        precision: info.precision || 'default',
        labelsOnPriceScale: info.labelsOnPriceScale !== false,
        valuesInStatusLine: info.valuesInStatusLine !== false,
        inputsInStatusLine: info.inputsInStatusLine !== false,
        // Per-plot visibility/style
        plotStyles: {},
    };
    // Initialize per-plot style drafts
    for (var pi = 0; pi < groupSids.length; pi++) {
        var pInfo = _activeIndicators[groupSids[pi]];
        draft.plotStyles[groupSids[pi]] = {
            visible: pInfo.visible !== false,
            color: pInfo.color || '#e6b32c',
            lineWidth: pInfo.lineWidth || 2,
            lineStyle: pInfo.lineStyle || 0,
        };
    }

    var activeTab = 'inputs';

    var overlay = document.createElement('div');
    overlay.className = 'tv-settings-overlay';
    _tvSetChartInteractionLocked(info.chartId, true);
    function closeOverlay() {
        _tvSetChartInteractionLocked(info.chartId, false);
        if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
    }
    overlay.addEventListener('click', function(e) { if (e.target === overlay) closeOverlay(); });
    overlay.addEventListener('mousedown', function(e) { e.stopPropagation(); });
    overlay.addEventListener('wheel', function(e) { e.stopPropagation(); });

    var panel = document.createElement('div');
    panel.className = 'tv-settings-panel';
    // Wider panel (matches TradingView) so the Visibility tab's
    // checkbox + min + slider + max + sep + max-input row fits without
    // a horizontal scrollbar.
    panel.style.cssText = 'width:560px;max-width:90vw;flex-direction:column;max-height:75vh;position:relative;overflow:hidden;';
    overlay.appendChild(panel);

    var header = document.createElement('div');
    header.className = 'tv-settings-header';
    header.style.cssText = 'position:relative;flex-direction:column;align-items:stretch;padding-bottom:0;';
    var hdrRow = document.createElement('div');
    hdrRow.style.cssText = 'display:flex;align-items:center;gap:8px;';
    var titleEl = document.createElement('h3');
    // Title uses the short canonical name TradingView shows in its
    // own dialog (e.g. "Ichimoku" not "Ichimoku Cloud Settings", and
    // collapsed for grouped indicators that span multiple lines).
    var titleText;
    if (isBB) titleText = 'Bollinger Bands';
    else if (isIchimoku) titleText = 'Ichimoku';
    else if (isMACD) titleText = 'MACD';
    else if (isStoch) titleText = 'Stoch';
    else if (isADX) titleText = 'ADX';
    else if (isAroon) titleText = 'Aroon';
    else if (isKC) titleText = 'Keltner Channels';
    else if (isPSAR) titleText = 'SAR';
    else titleText = info.name;
    titleEl.textContent = titleText + ' Settings';
    hdrRow.appendChild(titleEl);
    var closeBtn = document.createElement('button');
    closeBtn.className = 'tv-settings-close';
    closeBtn.innerHTML = '<svg viewBox="0 0 16 16"><line x1="3" y1="3" x2="13" y2="13"/><line x1="13" y1="3" x2="3" y2="13"/></svg>';
    closeBtn.addEventListener('click', closeOverlay);
    hdrRow.appendChild(closeBtn);
    header.appendChild(hdrRow);

    // Tab bar: Inputs | Style | Visibility
    var tabBar = document.createElement('div');
    tabBar.className = 'tv-ind-settings-tabs';
    var tabs = ['Inputs', 'Style', 'Visibility'];
    var tabEls = {};
    tabs.forEach(function(t) {
        var te = document.createElement('div');
        te.className = 'tv-ind-settings-tab' + (t.toLowerCase() === activeTab ? ' active' : '');
        te.textContent = t;
        te.addEventListener('click', function() {
            activeTab = t.toLowerCase();
            tabs.forEach(function(tn) { tabEls[tn].classList.toggle('active', tn.toLowerCase() === activeTab); });
            renderBody();
        });
        tabEls[t] = te;
        tabBar.appendChild(te);
    });
    header.appendChild(tabBar);
    panel.appendChild(header);

    var body = document.createElement('div');
    body.className = 'tv-settings-body';
    body.style.cssText = 'flex:1;overflow-y:auto;overflow-x:hidden;min-height:80px;';
    panel.appendChild(body);

    var foot = document.createElement('div');
    foot.className = 'tv-settings-footer';
    foot.style.cssText = 'position:relative;display:flex;align-items:center;gap:8px;';

    // Defaults dropdown (TradingView pattern) — left side of footer.
    // Snapshot the original draft so "Reset Settings" restores the
    // values the dialog opened with.
    var _draftSnapshot = JSON.parse(JSON.stringify(draft));

    // Live preview: push every draft edit straight to the chart so the
    // user sees their change the moment they make it.  Apply is cheap
    // (single setData + applyOptions), so debounce is unnecessary — but
    // coalesce with rAF so a burst of number-spinner ticks still render
    // as one frame.
    var _livePreviewScheduled = false;
    function _livePreview() {
        if (_livePreviewScheduled) return;
        _livePreviewScheduled = true;
        var schedule = typeof requestAnimationFrame === 'function'
            ? requestAnimationFrame
            : function(cb) { return setTimeout(cb, 0); };
        schedule(function() {
            _livePreviewScheduled = false;
            try { _tvApplyIndicatorSettings(seriesId, draft); } catch (_e) {}
        });
    }
    var defaultsWrap = document.createElement('div');
    defaultsWrap.style.cssText = 'position:relative;margin-right:auto;';
    var defaultsBtn = document.createElement('button');
    defaultsBtn.className = 'ts-btn-cancel';
    defaultsBtn.textContent = 'Defaults  \u25BE';
    defaultsBtn.style.cssText = 'min-width:104px;text-align:left;';
    defaultsWrap.appendChild(defaultsBtn);
    var defaultsMenu = document.createElement('div');
    defaultsMenu.style.cssText = 'position:absolute;left:0;bottom:calc(100% + 4px);min-width:200px;background:var(--pywry-tvchart-panel-bg,#1c1f26);border:1px solid var(--pywry-tvchart-border,#2a2e39);border-radius:4px;padding:4px 0;display:none;z-index:10;box-shadow:0 4px 12px var(--pywry-tvchart-shadow,rgba(0,0,0,0.45));';
    function defaultsItem(label, onClick) {
        var item = document.createElement('div');
        item.textContent = label;
        item.style.cssText = 'padding:8px 12px;font-size:13px;color:var(--pywry-tvchart-text);cursor:pointer;';
        item.addEventListener('mouseenter', function() { item.style.background = 'var(--pywry-tvchart-hover,#262a33)'; });
        item.addEventListener('mouseleave', function() { item.style.background = ''; });
        item.addEventListener('click', function(e) {
            e.stopPropagation();
            defaultsMenu.style.display = 'none';
            onClick();
        });
        return item;
    }
    defaultsMenu.appendChild(defaultsItem('Reset Settings', function() {
        Object.keys(_draftSnapshot).forEach(function(k) { draft[k] = JSON.parse(JSON.stringify(_draftSnapshot[k])); });
        renderBody();
        _tvApplyIndicatorSettings(seriesId, draft);
    }));
    defaultsWrap.appendChild(defaultsMenu);
    defaultsBtn.addEventListener('click', function(e) {
        e.stopPropagation();
        defaultsMenu.style.display = defaultsMenu.style.display === 'block' ? 'none' : 'block';
    });
    document.addEventListener('click', function() { defaultsMenu.style.display = 'none'; });
    foot.appendChild(defaultsWrap);

    var cancelBtn = document.createElement('button');
    cancelBtn.className = 'ts-btn-cancel';
    cancelBtn.textContent = 'Cancel';
    cancelBtn.addEventListener('click', closeOverlay);
    foot.appendChild(cancelBtn);
    var okBtn = document.createElement('button');
    okBtn.className = 'ts-btn-ok';
    okBtn.textContent = 'Ok';
    okBtn.addEventListener('click', function() {
        closeOverlay();
        _tvApplyIndicatorSettings(seriesId, draft);
    });
    foot.appendChild(okBtn);
    panel.appendChild(foot);

    // ---- Row builder helpers ----
    function addSection(parent, text) {
        var sec = document.createElement('div');
        sec.className = 'tv-settings-section';
        sec.textContent = text;
        parent.appendChild(sec);
    }
    function addColorRow(parent, label, val, onChange) {
        var row = document.createElement('div');
        row.className = 'tv-settings-row tv-settings-row-spaced';
        var lbl = document.createElement('label'); lbl.textContent = label; row.appendChild(lbl);
        var ctrl = document.createElement('div'); ctrl.className = 'ts-controls'; ctrl.style.position = 'relative';
        var swatch = document.createElement('div'); swatch.className = 'ts-swatch';
        swatch.dataset.baseColor = _tvColorToHex(val || '#e6b32c', '#e6b32c');
        swatch.dataset.opacity = String(_tvColorOpacityPercent(val, 100));
        swatch.style.background = val;
        swatch.addEventListener('click', function(e) {
            e.preventDefault(); e.stopPropagation();
            _tvShowColorOpacityPopup(
                swatch,
                swatch.dataset.baseColor,
                _tvToNumber(swatch.dataset.opacity, 100),
                overlay,
                function(newColor, newOpacity) {
                    swatch.dataset.baseColor = newColor;
                    swatch.dataset.opacity = String(newOpacity);
                    swatch.style.background = _tvColorWithOpacity(newColor, newOpacity, newColor);
                    onChange(newColor, newOpacity);
                    _livePreview();
                }
            );
        });
        ctrl.appendChild(swatch); row.appendChild(ctrl); parent.appendChild(row);
    }
    function addSelectRow(parent, label, opts, val, onChange) {
        var row = document.createElement('div');
        row.className = 'tv-settings-row tv-settings-row-spaced';
        var lbl = document.createElement('label'); lbl.textContent = label; row.appendChild(lbl);
        var sel = document.createElement('select'); sel.className = 'ts-select';
        opts.forEach(function(o) {
            var opt = document.createElement('option'); opt.value = o.v; opt.textContent = o.l;
            if (String(o.v) === String(val)) opt.selected = true; sel.appendChild(opt);
        });
        sel.addEventListener('change', function() { onChange(sel.value); _livePreview(); });
        row.appendChild(sel); parent.appendChild(row);
    }
    function addNumberRow(parent, label, min, max, step, val, onChange) {
        var row = document.createElement('div');
        row.className = 'tv-settings-row tv-settings-row-spaced';
        var lbl = document.createElement('label'); lbl.textContent = label; row.appendChild(lbl);
        var inp = document.createElement('input'); inp.type = 'number'; inp.className = 'ts-input';
        inp.min = min; inp.max = max; inp.step = step; inp.value = val;
        inp.addEventListener('keydown', function(e) { e.stopPropagation(); });
        inp.addEventListener('input', function() {
            var v = parseFloat(inp.value);
            if (!isNaN(v) && v >= parseFloat(min)) { onChange(v); _livePreview(); }
        });
        row.appendChild(inp); parent.appendChild(row);
    }
    function addCheckRow(parent, label, val, onChange) {
        var row = document.createElement('div');
        row.className = 'tv-settings-row tv-settings-row-spaced';
        var lbl = document.createElement('label'); lbl.textContent = label; row.appendChild(lbl);
        var cb = document.createElement('input'); cb.type = 'checkbox'; cb.className = 'ts-checkbox';
        cb.checked = !!val;
        cb.addEventListener('change', function() { onChange(cb.checked); _livePreview(); });
        row.appendChild(cb); parent.appendChild(row);
    }

    // Plot-style row: checkbox + color swatch + line style selector
    function addPlotStyleRow(parent, label, plotDraft) {
        var row = document.createElement('div');
        row.className = 'tv-settings-row tv-settings-row-spaced';
        row.style.cssText = 'display:flex;align-items:center;gap:8px;';
        var cb = document.createElement('input'); cb.type = 'checkbox'; cb.className = 'ts-checkbox';
        cb.checked = plotDraft.visible !== false;
        cb.addEventListener('change', function() { plotDraft.visible = cb.checked; _livePreview(); });
        row.appendChild(cb);
        var lbl = document.createElement('label'); lbl.textContent = label; lbl.style.flex = '1'; row.appendChild(lbl);
        var swatch = document.createElement('div'); swatch.className = 'ts-swatch';
        swatch.dataset.baseColor = _tvColorToHex(plotDraft.color || '#e6b32c', '#e6b32c');
        swatch.dataset.opacity = String(_tvColorOpacityPercent(plotDraft.color, 100));
        swatch.style.background = plotDraft.color;
        swatch.addEventListener('click', function(e) {
            e.preventDefault(); e.stopPropagation();
            _tvShowColorOpacityPopup(
                swatch,
                swatch.dataset.baseColor,
                _tvToNumber(swatch.dataset.opacity, 100),
                overlay,
                function(newColor, newOpacity) {
                    swatch.dataset.baseColor = newColor;
                    swatch.dataset.opacity = String(newOpacity);
                    swatch.style.background = _tvColorWithOpacity(newColor, newOpacity, newColor);
                    plotDraft.color = _tvColorWithOpacity(newColor, newOpacity, newColor);
                    _livePreview();
                }
            );
        });
        row.appendChild(swatch);
        var wSel = document.createElement('select'); wSel.className = 'ts-select'; wSel.style.width = '60px';
        [{v:1,l:'1px'},{v:2,l:'2px'},{v:3,l:'3px'},{v:4,l:'4px'}].forEach(function(o) {
            var opt = document.createElement('option'); opt.value = o.v; opt.textContent = o.l;
            if (Number(o.v) === Number(plotDraft.lineWidth)) opt.selected = true; wSel.appendChild(opt);
        });
        wSel.addEventListener('change', function() { plotDraft.lineWidth = Number(wSel.value); _livePreview(); });
        row.appendChild(wSel);
        // Line style selector
        var lsSel = document.createElement('select'); lsSel.className = 'ts-select'; lsSel.style.width = '80px';
        [{v:0,l:'Solid'},{v:1,l:'Dashed'},{v:2,l:'Dotted'},{v:3,l:'Lg Dash'}].forEach(function(o) {
            var opt = document.createElement('option'); opt.value = o.v; opt.textContent = o.l;
            if (Number(o.v) === Number(plotDraft.lineStyle || 0)) opt.selected = true; lsSel.appendChild(opt);
        });
        lsSel.addEventListener('change', function() { plotDraft.lineStyle = Number(lsSel.value); _livePreview(); });
        row.appendChild(lsSel);
        parent.appendChild(row);
    }

    // Horizontal-limit row: checkbox + color + value input
    function addHlimitRow(parent, label, show, color, value, onShow, onColor, onValue) {
        var row = document.createElement('div');
        row.className = 'tv-settings-row tv-settings-row-spaced';
        row.style.cssText = 'display:flex;align-items:center;gap:8px;';
        var cb = document.createElement('input'); cb.type = 'checkbox'; cb.className = 'ts-checkbox';
        cb.checked = !!show;
        cb.addEventListener('change', function() { onShow(cb.checked); });
        row.appendChild(cb);
        var lbl = document.createElement('label'); lbl.textContent = label; lbl.style.flex = '1'; row.appendChild(lbl);
        var swatch = document.createElement('div'); swatch.className = 'ts-swatch';
        swatch.dataset.baseColor = _tvColorToHex(color || '#787b86', '#787b86');
        swatch.dataset.opacity = String(_tvColorOpacityPercent(color, 100));
        swatch.style.background = color;
        swatch.addEventListener('click', function(e) {
            e.preventDefault(); e.stopPropagation();
            _tvShowColorOpacityPopup(
                swatch,
                swatch.dataset.baseColor,
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
        row.appendChild(swatch);
        var inp = document.createElement('input'); inp.type = 'number'; inp.className = 'ts-input';
        inp.style.width = '54px'; inp.value = value; inp.step = 'any';
        inp.addEventListener('keydown', function(e) { e.stopPropagation(); });
        inp.addEventListener('input', function() { var v = parseFloat(inp.value); if (!isNaN(v)) onValue(v); });
        row.appendChild(inp);
        parent.appendChild(row);
    }

    function renderBody() {
        body.innerHTML = '';

        // ===================== INPUTS TAB =====================
        if (activeTab === 'inputs') {
            var hasInputs = false;

            // Period / Length
            // Indicators that expose their own period-like fields below
            // (MACD = Fast/Slow/Signal, Stochastic = %K/%D, Ichimoku = Tenkan/Kijun/Senkou B,
            // Parabolic SAR = Step/Max Step) skip the generic Period row.
            var skipGenericPeriod = isMACD || isStoch || isIchimoku || isPSAR;
            if (info.period > 0 && !skipGenericPeriod) {
                var isLengthType = isBB || (isLightweight && (type === 'moving-average-ex' || type === 'momentum' || type === 'correlation'));
                addNumberRow(body, isLengthType ? 'Length' : 'Period', '1', '500', '1', draft.period, function(v) { draft.period = v; });
                hasInputs = true;
            }

            // RSI inputs
            if (isRSI) {
                addSelectRow(body, 'Source', _SRC_OPTS, draft.source, function(v) { draft.source = v; });
                addSelectRow(body, 'Smoothing Line', [
                    { v: 'SMA', l: 'SMA' }, { v: 'EMA', l: 'EMA' }, { v: 'WMA', l: 'WMA' },
                ], draft.smoothingLine, function(v) { draft.smoothingLine = v; });
                addNumberRow(body, 'Smoothing Length', '1', '200', '1', draft.smoothingLength, function(v) { draft.smoothingLength = v; });
                hasInputs = true;
            }

            // Bollinger Bands inputs
            if (isBB) {
                addSelectRow(body, 'Source', _SRC_OPTS, draft.source, function(v) { draft.source = v; });
                addNumberRow(body, 'Mult', '0.1', '10', '0.1', draft.multiplier, function(v) { draft.multiplier = v; });
                addNumberRow(body, 'Offset', '-500', '500', '1', draft.offset, function(v) { draft.offset = v; });
                addSelectRow(body, 'MA Type', [
                    { v: 'SMA', l: 'SMA' }, { v: 'EMA', l: 'EMA' }, { v: 'WMA', l: 'WMA' },
                ], draft.maType, function(v) { draft.maType = v; });
                hasInputs = true;
            }

            // ATR inputs
            if (isATR) {
                addSelectRow(body, 'Source', _SRC_OPTS.slice(0, 4), draft.source, function(v) { draft.source = v; });
                hasInputs = true;
            }

            // Lightweight examples
            if (isLightweight) {
                if (type === 'moving-average-ex') {
                    // Single "Moving Average" surface — Type covers
                    // every MA family the renderer supports.
                    addSelectRow(body, 'Source', _SRC_OPTS, draft.source, function(v) { draft.source = v; });
                    addSelectRow(body, 'Type', [
                        { v: 'SMA',  l: 'Simple (SMA)' },
                        { v: 'EMA',  l: 'Exponential (EMA)' },
                        { v: 'WMA',  l: 'Weighted (WMA)' },
                        { v: 'HMA',  l: 'Hull (HMA)' },
                        { v: 'VWMA', l: 'Volume-Weighted (VWMA)' },
                    ], draft.method, function(v) { draft.method = v; });
                    hasInputs = true;
                } else if (type === 'momentum' || type === 'percent-change') {
                    addSelectRow(body, 'Source', _SRC_OPTS, draft.source, function(v) { draft.source = v; });
                    hasInputs = true;
                } else if (type === 'correlation' || type === 'spread' || type === 'ratio' || type === 'sum' || type === 'product') {
                    // Single Source dropdown (applies to both primary and secondary)
                    addSelectRow(body, 'Source', _SRC_OPTS, draft.primarySource, function(v) {
                        draft.primarySource = v;
                        draft.secondarySource = v;
                    });
                    // Symbol field showing secondary symbol with edit / refresh buttons
                    var secEntry = window.__PYWRY_TVCHARTS__[info.chartId];
                    var secSymText = (secEntry && secEntry._compareSymbols && secEntry._compareSymbols[info.secondarySeriesId]) || info.secondarySeriesId || '';
                    var symRow = document.createElement('div');
                    symRow.className = 'tv-settings-row tv-settings-row-spaced';
                    var symLbl = document.createElement('label'); symLbl.textContent = 'Symbol'; symRow.appendChild(symLbl);
                    var symCtrl = document.createElement('div'); symCtrl.style.cssText = 'display:flex;align-items:center;gap:6px;flex:1;justify-content:flex-end;';
                    var symVal = document.createElement('span');
                    symVal.style.cssText = 'font-size:13px;color:var(--pywry-tvchart-text,#d1d4dc);direction:rtl;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:180px;';
                    symVal.textContent = secSymText;
                    symCtrl.appendChild(symVal);
                    // Edit (pencil) button
                    var editBtn = document.createElement('button');
                    editBtn.className = 'tv-settings-icon-btn';
                    editBtn.title = 'Change symbol';
                    editBtn.innerHTML = '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M11.3 2.3a1.4 1.4 0 012 2L5.7 11.9 2 13l1.1-3.7z"/></svg>';
                    editBtn.addEventListener('click', function() {
                        closeOverlay();
                        // Mark that this new indicator should replace the existing one
                        var editEntry = window.__PYWRY_TVCHARTS__[info.chartId];
                        if (editEntry) editEntry._pendingReplaceIndicator = seriesId;
                        _tvShowIndicatorSymbolPicker(info.chartId, {
                            name: info.name,
                            key: type,
                            requiresSecondary: true,
                            _primarySource: draft.primarySource,
                            _secondarySource: draft.secondarySource,
                        });
                    });
                    symCtrl.appendChild(editBtn);
                    // Refresh button
                    var refreshBtn = document.createElement('button');
                    refreshBtn.className = 'tv-settings-icon-btn';
                    refreshBtn.title = 'Refresh data';
                    refreshBtn.innerHTML = '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M13 8a5 5 0 01-9.3 2.5"/><path d="M3 8a5 5 0 019.3-2.5"/><path d="M13 3v3h-3"/><path d="M3 13v-3h3"/></svg>';
                    refreshBtn.addEventListener('click', function() {
                        closeOverlay();
                        _tvApplyIndicatorSettings(seriesId, draft);
                    });
                    symCtrl.appendChild(refreshBtn);
                    symRow.appendChild(symCtrl);
                    body.appendChild(symRow);
                    hasInputs = true;
                }
            }

            // Volume SMA
            if (isVolSMA) {
                addSelectRow(body, 'Source', [{ v: 'volume', l: 'Volume' }], 'volume', function() {});
                hasInputs = true;
            }

            // MACD — TradingView's exact field labels
            if (isMACD) {
                addNumberRow(body, 'Fast Length', '1', '500', '1', draft.fast, function(v) { draft.fast = v; });
                addNumberRow(body, 'Slow Length', '1', '500', '1', draft.slow, function(v) { draft.slow = v; });
                addSelectRow(body, 'Source', _SRC_OPTS, draft.macdSource, function(v) { draft.macdSource = v; });
                addNumberRow(body, 'Signal Smoothing', '1', '500', '1', draft.signal, function(v) { draft.signal = v; });
                addSelectRow(body, 'Oscillator MA Type', [
                    { v: 'SMA', l: 'SMA' }, { v: 'EMA', l: 'EMA' }, { v: 'WMA', l: 'WMA' },
                ], draft.oscMaType, function(v) { draft.oscMaType = v; });
                addSelectRow(body, 'Signal Line MA Type', [
                    { v: 'SMA', l: 'SMA' }, { v: 'EMA', l: 'EMA' }, { v: 'WMA', l: 'WMA' },
                ], draft.signalMaType, function(v) { draft.signalMaType = v; });
                hasInputs = true;
            }

            // Stochastic — TradingView's three lengths
            if (isStoch) {
                addNumberRow(body, '%K Length', '1', '500', '1', draft.kPeriod, function(v) { draft.kPeriod = v; draft.period = v; });
                addNumberRow(body, '%K Smoothing', '1', '500', '1', draft.kSmoothing, function(v) { draft.kSmoothing = v; });
                addNumberRow(body, '%D Smoothing', '1', '500', '1', draft.dPeriod, function(v) { draft.dPeriod = v; });
                hasInputs = true;
            }

            // ADX — TradingView "ADX Smoothing" + "DI Length"
            if (isADX) {
                addNumberRow(body, 'ADX Smoothing', '1', '500', '1', draft.adxSmoothing, function(v) { draft.adxSmoothing = v; draft.period = v; });
                addNumberRow(body, 'DI Length',     '1', '500', '1', draft.diLength,     function(v) { draft.diLength = v; });
                hasInputs = true;
            }

            // CCI / Williams %R — Length (above) + Source dropdown
            if (isCCI || isWilliamsR) {
                addSelectRow(body, 'Source', _SRC_OPTS, draft.source, function(v) { draft.source = v; });
                hasInputs = true;
            }

            // Historical Volatility — Length (above) + Annualization
            if (isHV) {
                addNumberRow(body, 'Annualization', '1', '10000', '1', draft.annualization, function(v) { draft.annualization = v; });
                hasInputs = true;
            }

            // Parabolic SAR — TradingView labels: Start, Increment, Maximum
            // (TV's "Start" and "Increment" are the same value in stock SAR;
            // exposing both for clarity and future tweaks.)
            if (isPSAR) {
                addNumberRow(body, 'Start',     '0.001', '1', '0.001', draft.step,    function(v) { draft.step = v; });
                addNumberRow(body, 'Increment', '0.001', '1', '0.001', draft.step,    function(v) { draft.step = v; });
                addNumberRow(body, 'Maximum',   '0.001', '1', '0.001', draft.maxStep, function(v) { draft.maxStep = v; });
                hasInputs = true;
            }

            // Keltner Channels — TradingView fields:
            //   Length / Source / Use Exponential MA / Bands Style / ATR Length / Multiplier
            if (isKC) {
                addSelectRow(body, 'Source', _SRC_OPTS, draft.source, function(v) { draft.source = v; });
                addCheckRow(body, 'Use Exponential MA', draft.maType !== 'SMA', function(v) {
                    draft.maType = v ? 'EMA' : 'SMA';
                });
                addNumberRow(body, 'Multiplier', '0.1', '20', '0.1', draft.multiplier, function(v) { draft.multiplier = v; });
                hasInputs = true;
            }

            // Ichimoku Cloud — TradingView's exact field labels
            if (isIchimoku) {
                addNumberRow(body, 'Conversion Line Periods', '1', '500', '1', draft.conversionPeriod, function(v) { draft.conversionPeriod = v; });
                addNumberRow(body, 'Base Line Periods',       '1', '500', '1', draft.basePeriod,       function(v) { draft.basePeriod = v; draft.period = v; });
                addNumberRow(body, 'Leading Span Periods',    '1', '500', '1', draft.leadingSpanPeriod, function(v) { draft.leadingSpanPeriod = v; });
                addNumberRow(body, 'Lagging Span Periods',    '1', '500', '1', draft.laggingPeriod,    function(v) { draft.laggingPeriod = v; });
                addNumberRow(body, 'Leading Shift Periods',   '1', '500', '1', draft.leadingShiftPeriod, function(v) { draft.leadingShiftPeriod = v; });
                hasInputs = true;
            }

            // Volume Profile inputs (VPVR / VPFR)
            if (isVP) {
                addSelectRow(body, 'Rows Layout', [
                    { v: 'rows', l: 'Number Of Rows' },
                    { v: 'ticks', l: 'Ticks Per Row' },
                ], draft.vpRowsLayout, function(v) {
                    draft.vpRowsLayout = v;
                    if (v === 'ticks') {
                        if (!draft.vpRowSize || draft.vpRowSize > 100) draft.vpRowSize = 1;
                    } else {
                        if (!draft.vpRowSize || draft.vpRowSize < 4) draft.vpRowSize = 24;
                    }
                    _tvApplyVPDraftLive(seriesId, draft);
                    renderBody();
                });
                addNumberRow(
                    body,
                    'Row Size',
                    draft.vpRowsLayout === 'ticks' ? '1' : '4',
                    draft.vpRowsLayout === 'ticks' ? '1000' : '500',
                    draft.vpRowsLayout === 'ticks' ? '0.0001' : '1',
                    draft.vpRowSize,
                    function(v) { draft.vpRowSize = v; _tvApplyVPDraftLive(seriesId, draft); }
                );
                addSelectRow(body, 'Volume', [
                    { v: 'updown', l: 'Up/Down' },
                    { v: 'total', l: 'Total' },
                    { v: 'delta', l: 'Delta' },
                ], draft.vpVolumeMode, function(v) {
                    draft.vpVolumeMode = v;
                    _tvApplyVPDraftLive(seriesId, draft);
                });
                addNumberRow(body, 'Value Area Volume', '10', '95', '1', draft.vpValueAreaPct, function(v) {
                    draft.vpValueAreaPct = v;
                    _tvApplyVPDraftLive(seriesId, draft);
                });
                hasInputs = true;
            }

            if (!hasInputs) {
                var noRow = document.createElement('div');
                noRow.className = 'tv-settings-row';
                noRow.style.cssText = 'color:var(--pywry-tvchart-text-muted,#787b86);font-size:12px;';
                noRow.textContent = 'No configurable inputs.';
                body.appendChild(noRow);
            }

        // ===================== STYLE TAB =====================
        } else if (activeTab === 'style') {
            // Volume Profile style — full custom panel (skip the generic plot rows)
            if (isVP) {
                function liveVP() { _tvApplyVPDraftLive(seriesId, draft); }
                addSection(body, 'VOLUME PROFILE');
                addNumberRow(body, 'Width (% of pane)', '2', '60', '1', draft.vpWidthPercent, function(v) { draft.vpWidthPercent = v; liveVP(); });
                addSelectRow(body, 'Placement', [
                    { v: 'right', l: 'Right' },
                    { v: 'left', l: 'Left' },
                ], draft.vpPlacement, function(v) { draft.vpPlacement = v; liveVP(); });
                addColorRow(body, 'Up Volume', draft.vpUpColor, function(v, op) { draft.vpUpColor = _tvColorWithOpacity(v, op, v); liveVP(); });
                addColorRow(body, 'Down Volume', draft.vpDownColor, function(v, op) { draft.vpDownColor = _tvColorWithOpacity(v, op, v); liveVP(); });
                addColorRow(body, 'Value Area Up', draft.vpVAUpColor, function(v, op) { draft.vpVAUpColor = _tvColorWithOpacity(v, op, v); liveVP(); });
                addColorRow(body, 'Value Area Down', draft.vpVADownColor, function(v, op) { draft.vpVADownColor = _tvColorWithOpacity(v, op, v); liveVP(); });

                addSection(body, 'POC');
                addCheckRow(body, 'Show POC', draft.vpShowPOC, function(v) { draft.vpShowPOC = v; liveVP(); });
                addColorRow(body, 'POC Color', draft.vpPOCColor, function(v, op) { draft.vpPOCColor = _tvColorWithOpacity(v, op, v); liveVP(); });

                addSection(body, 'DEVELOPING POC');
                addCheckRow(body, 'Show Developing POC', draft.vpShowDevelopingPOC, function(v) { draft.vpShowDevelopingPOC = v; liveVP(); });
                addColorRow(body, 'Developing POC Color', draft.vpDevelopingPOCColor, function(v, op) { draft.vpDevelopingPOCColor = _tvColorWithOpacity(v, op, v); liveVP(); });

                addSection(body, 'VALUE AREA');
                addCheckRow(body, 'Highlight Value Area', draft.vpShowValueArea, function(v) { draft.vpShowValueArea = v; liveVP(); });
                addCheckRow(body, 'Show Developing VA', draft.vpShowDevelopingVA, function(v) { draft.vpShowDevelopingVA = v; liveVP(); });
                addColorRow(body, 'Developing VA Color', draft.vpDevelopingVAColor, function(v, op) { draft.vpDevelopingVAColor = _tvColorWithOpacity(v, op, v); liveVP(); });

                addSection(body, 'OUTPUT VALUES');
                addCheckRow(body, 'Labels on price scale', draft.vpLabelsOnPriceScale, function(v) { draft.vpLabelsOnPriceScale = v; });
                addCheckRow(body, 'Values in status line', draft.vpValuesInStatusLine, function(v) { draft.vpValuesInStatusLine = v; });
                addSection(body, 'INPUT VALUES');
                addCheckRow(body, 'Inputs in status line', draft.vpInputsInStatusLine, function(v) { draft.vpInputsInStatusLine = v; });
                return;
            }

            addSection(body, 'PLOTS');

            // Multi-plot indicators (Bollinger Bands)
            if (groupSids.length > 1) {
                for (var gi = 0; gi < groupSids.length; gi++) {
                    var gInfo = _activeIndicators[groupSids[gi]];
                    var plotLabel = gInfo ? gInfo.name : groupSids[gi];
                    if (draft.plotStyles[groupSids[gi]]) {
                        addPlotStyleRow(body, plotLabel, draft.plotStyles[groupSids[gi]]);
                    }
                }
            } else {
                // Single-plot indicator
                addPlotStyleRow(body, info.name, draft.plotStyles[seriesId] || { visible: true, color: draft.color, lineWidth: draft.lineWidth, lineStyle: draft.lineStyle });
            }

            // RSI-specific: horizontal limits + background
            if (isRSI) {
                addSection(body, 'LEVELS');
                addHlimitRow(body, 'Upper Limit', draft.showUpperLimit, draft.upperLimitColor, draft.upperLimitValue,
                    function(v) { draft.showUpperLimit = v; }, function(v) { draft.upperLimitColor = v; }, function(v) { draft.upperLimitValue = v; });
                addHlimitRow(body, 'Middle Limit', draft.showMiddleLimit, draft.middleLimitColor, draft.middleLimitValue,
                    function(v) { draft.showMiddleLimit = v; }, function(v) { draft.middleLimitColor = v; }, function(v) { draft.middleLimitValue = v; });
                addHlimitRow(body, 'Lower Limit', draft.showLowerLimit, draft.lowerLimitColor, draft.lowerLimitValue,
                    function(v) { draft.showLowerLimit = v; }, function(v) { draft.lowerLimitColor = v; }, function(v) { draft.lowerLimitValue = v; });
                addSection(body, 'FILLS');
                addCheckRow(body, 'Background', draft.showBackground, function(v) { draft.showBackground = v; });
                if (draft.showBackground) {
                    addColorRow(body, 'Fill Color', draft.bgColor, function(v, op) { draft.bgColor = _tvColorWithOpacity(v, op, v); });
                }
            }

            // Binary indicator fills + output/input values
            if (isBinary) {
                addSection(body, 'FILLS');
                // Positive fill: checkbox + color
                var posFillRow = document.createElement('div');
                posFillRow.className = 'tv-settings-row tv-settings-row-spaced';
                posFillRow.style.cssText = 'display:flex;align-items:center;gap:8px;';
                var posCb = document.createElement('input'); posCb.type = 'checkbox'; posCb.className = 'ts-checkbox';
                posCb.checked = !!draft.showPositiveFill;
                posCb.addEventListener('change', function() { draft.showPositiveFill = posCb.checked; });
                posFillRow.appendChild(posCb);
                var posLbl = document.createElement('label'); posLbl.textContent = 'Positive fill'; posLbl.style.flex = '1'; posFillRow.appendChild(posLbl);
                var posSwatch = document.createElement('div'); posSwatch.className = 'ts-swatch';
                posSwatch.dataset.baseColor = _tvColorToHex(draft.positiveFillColor || '#26a69a', '#26a69a');
                posSwatch.dataset.opacity = String(_tvColorOpacityPercent(draft.positiveFillColor, 100));
                posSwatch.style.background = draft.positiveFillColor;
                posSwatch.addEventListener('click', function(e) {
                    e.preventDefault(); e.stopPropagation();
                    _tvShowColorOpacityPopup(
                        posSwatch,
                        posSwatch.dataset.baseColor,
                        _tvToNumber(posSwatch.dataset.opacity, 100),
                        overlay,
                        function(newColor, newOpacity) {
                            posSwatch.dataset.baseColor = newColor;
                            posSwatch.dataset.opacity = String(newOpacity);
                            posSwatch.style.background = _tvColorWithOpacity(newColor, newOpacity, newColor);
                            draft.positiveFillColor = newColor;
                            draft.positiveFillOpacity = newOpacity;
                        }
                    );
                });
                posFillRow.appendChild(posSwatch);
                body.appendChild(posFillRow);
                // Negative fill: checkbox + color
                var negFillRow = document.createElement('div');
                negFillRow.className = 'tv-settings-row tv-settings-row-spaced';
                negFillRow.style.cssText = 'display:flex;align-items:center;gap:8px;';
                var negCb = document.createElement('input'); negCb.type = 'checkbox'; negCb.className = 'ts-checkbox';
                negCb.checked = !!draft.showNegativeFill;
                negCb.addEventListener('change', function() { draft.showNegativeFill = negCb.checked; });
                negFillRow.appendChild(negCb);
                var negLbl = document.createElement('label'); negLbl.textContent = 'Negative fill'; negLbl.style.flex = '1'; negFillRow.appendChild(negLbl);
                var negSwatch = document.createElement('div'); negSwatch.className = 'ts-swatch';
                negSwatch.dataset.baseColor = _tvColorToHex(draft.negativeFillColor || '#ef5350', '#ef5350');
                negSwatch.dataset.opacity = String(_tvColorOpacityPercent(draft.negativeFillColor, 100));
                negSwatch.style.background = draft.negativeFillColor;
                negSwatch.addEventListener('click', function(e) {
                    e.preventDefault(); e.stopPropagation();
                    _tvShowColorOpacityPopup(
                        negSwatch,
                        negSwatch.dataset.baseColor,
                        _tvToNumber(negSwatch.dataset.opacity, 100),
                        overlay,
                        function(newColor, newOpacity) {
                            negSwatch.dataset.baseColor = newColor;
                            negSwatch.dataset.opacity = String(newOpacity);
                            negSwatch.style.background = _tvColorWithOpacity(newColor, newOpacity, newColor);
                            draft.negativeFillColor = newColor;
                            draft.negativeFillOpacity = newOpacity;
                        }
                    );
                });
                negFillRow.appendChild(negSwatch);
                body.appendChild(negFillRow);

                addSection(body, 'OUTPUT VALUES');
                addSelectRow(body, 'Precision', [
                    { v: 'default', l: 'Default' }, { v: '0', l: '0' }, { v: '1', l: '1' },
                    { v: '2', l: '2' }, { v: '3', l: '3' }, { v: '4', l: '4' },
                    { v: '5', l: '5' }, { v: '6', l: '6' }, { v: '7', l: '7' }, { v: '8', l: '8' },
                ], draft.precision, function(v) { draft.precision = v; });
                addCheckRow(body, 'Labels on price scale', draft.labelsOnPriceScale, function(v) { draft.labelsOnPriceScale = v; });
                addCheckRow(body, 'Values in status line', draft.valuesInStatusLine, function(v) { draft.valuesInStatusLine = v; });

                addSection(body, 'INPUT VALUES');
                addCheckRow(body, 'Inputs in status line', draft.inputsInStatusLine, function(v) { draft.inputsInStatusLine = v; });
            }

            // Bollinger Bands: band fill + output/input values
            if (isBB) {
                addSection(body, 'FILLS');
                addCheckRow(body, 'Plots Background', draft.showBandFill, function(v) { draft.showBandFill = v; renderBody(); });
                if (draft.showBandFill) {
                    addColorRow(body, 'Fill Color', draft.bandFillColor, function(v, op) { draft.bandFillColor = v; draft.bandFillOpacity = op; });
                }

                addSection(body, 'OUTPUT VALUES');
                addSelectRow(body, 'Precision', [
                    { v: 'default', l: 'Default' }, { v: '0', l: '0' }, { v: '1', l: '1' },
                    { v: '2', l: '2' }, { v: '3', l: '3' }, { v: '4', l: '4' },
                    { v: '5', l: '5' }, { v: '6', l: '6' }, { v: '7', l: '7' }, { v: '8', l: '8' },
                ], draft.precision, function(v) { draft.precision = v; });
                addCheckRow(body, 'Labels on price scale', draft.labelsOnPriceScale, function(v) { draft.labelsOnPriceScale = v; });
                addCheckRow(body, 'Values in status line', draft.valuesInStatusLine, function(v) { draft.valuesInStatusLine = v; });

                addSection(body, 'INPUT VALUES');
                addCheckRow(body, 'Inputs in status line', draft.inputsInStatusLine, function(v) { draft.inputsInStatusLine = v; });
            }

            // Universal OUTPUT VALUES + INPUT VALUES sections — TradingView
            // shows these on every indicator's Style tab.  Skip when an
            // indicator already rendered them above (RSI / BB / binary).
            if (!isRSI && !isBB && !isBinary) {
                addSection(body, 'OUTPUT VALUES');
                addSelectRow(body, 'Precision', [
                    { v: 'default', l: 'Default' }, { v: '0', l: '0' }, { v: '1', l: '1' },
                    { v: '2', l: '2' }, { v: '3', l: '3' }, { v: '4', l: '4' },
                    { v: '5', l: '5' }, { v: '6', l: '6' }, { v: '7', l: '7' }, { v: '8', l: '8' },
                ], draft.precision, function(v) { draft.precision = v; });
                addCheckRow(body, 'Labels on price scale', draft.labelsOnPriceScale, function(v) { draft.labelsOnPriceScale = v; });
                addCheckRow(body, 'Values in status line', draft.valuesInStatusLine, function(v) { draft.valuesInStatusLine = v; });
                addSection(body, 'INPUT VALUES');
                addCheckRow(body, 'Inputs in status line', draft.inputsInStatusLine, function(v) { draft.inputsInStatusLine = v; });
            }

        // ===================== VISIBILITY TAB =====================
        } else if (activeTab === 'visibility') {
            addSection(body, 'TIMEFRAME VISIBILITY');
            // { key, label, min, max } — bounds match TradingView's
            // per-interval ranges (Seconds 1-59, Minutes 1-59, Hours 1-24,
            // Days 1-366, Weeks 1-52, Months 1-12).
            var intervals = [
                { key: 'seconds', label: 'Seconds', min: 1, max: 59 },
                { key: 'minutes', label: 'Minutes', min: 1, max: 59 },
                { key: 'hours',   label: 'Hours',   min: 1, max: 24 },
                { key: 'days',    label: 'Days',    min: 1, max: 366 },
                { key: 'weeks',   label: 'Weeks',   min: 1, max: 52 },
                { key: 'months',  label: 'Months',  min: 1, max: 12 },
            ];
            if (!draft.visibility) draft.visibility = {};
            intervals.forEach(function(iv) {
                if (!draft.visibility[iv.key] || typeof draft.visibility[iv.key] !== 'object') {
                    draft.visibility[iv.key] = { enabled: true, min: iv.min, max: iv.max };
                }
            });

            intervals.forEach(function(iv) {
                var v = draft.visibility[iv.key];
                if (v.min == null) v.min = iv.min;
                if (v.max == null) v.max = iv.max;

                var row = document.createElement('div');
                row.className = 'tv-settings-row';
                // checkbox | label | min input | slider (flex) | – | max input
                row.style.cssText = 'display:grid;grid-template-columns:24px 64px 56px 1fr 12px 56px;align-items:center;gap:6px;padding:6px 0;';

                var cb = document.createElement('input');
                cb.type = 'checkbox';
                cb.className = 'ts-checkbox';
                cb.checked = v.enabled !== false;
                row.appendChild(cb);

                var lbl = document.createElement('label');
                lbl.textContent = iv.label;
                lbl.style.cssText = 'font-size:13px;';
                row.appendChild(lbl);

                var minInp = document.createElement('input');
                minInp.type = 'number';
                minInp.className = 'ts-input';
                minInp.min = String(iv.min);
                minInp.max = String(iv.max);
                minInp.step = '1';
                minInp.value = String(v.min);
                minInp.style.cssText = 'width:100%;min-width:0;';
                row.appendChild(minInp);

                // Two-thumb range via twin overlapping <input type="range">.
                var rangeWrap = document.createElement('div');
                rangeWrap.style.cssText = 'position:relative;height:24px;display:flex;align-items:center;';
                var track = document.createElement('div');
                track.style.cssText = 'position:absolute;left:0;right:0;height:4px;border-radius:2px;background:var(--pywry-tvchart-separator,#2a2e39);pointer-events:none;';
                rangeWrap.appendChild(track);
                var fill = document.createElement('div');
                fill.style.cssText = 'position:absolute;height:4px;border-radius:2px;background:var(--pywry-tvchart-active-text,#2962ff);pointer-events:none;';
                rangeWrap.appendChild(fill);
                var minSlider = document.createElement('input');
                minSlider.type = 'range';
                minSlider.min = String(iv.min);
                minSlider.max = String(iv.max);
                minSlider.step = '1';
                minSlider.value = String(v.min);
                minSlider.style.cssText = 'position:absolute;left:0;right:0;width:100%;height:24px;background:transparent;pointer-events:auto;-webkit-appearance:none;appearance:none;';
                rangeWrap.appendChild(minSlider);
                var maxSlider = document.createElement('input');
                maxSlider.type = 'range';
                maxSlider.min = String(iv.min);
                maxSlider.max = String(iv.max);
                maxSlider.step = '1';
                maxSlider.value = String(v.max);
                maxSlider.style.cssText = 'position:absolute;left:0;right:0;width:100%;height:24px;background:transparent;pointer-events:auto;-webkit-appearance:none;appearance:none;';
                rangeWrap.appendChild(maxSlider);
                row.appendChild(rangeWrap);

                var sep = document.createElement('span');
                sep.textContent = '\u2013';
                sep.style.cssText = 'color:var(--pywry-tvchart-text-muted,#787b86);font-size:13px;text-align:center;';
                row.appendChild(sep);

                var maxInp = document.createElement('input');
                maxInp.type = 'number';
                maxInp.className = 'ts-input';
                maxInp.min = String(iv.min);
                maxInp.max = String(iv.max);
                maxInp.step = '1';
                maxInp.value = String(v.max);
                maxInp.style.cssText = 'width:100%;min-width:0;';
                row.appendChild(maxInp);

                body.appendChild(row);

                function updateFill() {
                    var span = iv.max - iv.min;
                    if (span <= 0) return;
                    var lo = (Number(v.min) - iv.min) / span * 100;
                    var hi = (Number(v.max) - iv.min) / span * 100;
                    fill.style.left = lo + '%';
                    fill.style.right = (100 - hi) + '%';
                }
                updateFill();

                cb.addEventListener('change', function() { v.enabled = cb.checked; });
                function clamp(n) { return Math.max(iv.min, Math.min(iv.max, n)); }
                minInp.addEventListener('input', function() {
                    var n = clamp(parseInt(minInp.value, 10) || iv.min);
                    if (n > Number(v.max)) n = Number(v.max);
                    v.min = n; minSlider.value = String(n); updateFill();
                });
                maxInp.addEventListener('input', function() {
                    var n = clamp(parseInt(maxInp.value, 10) || iv.max);
                    if (n < Number(v.min)) n = Number(v.min);
                    v.max = n; maxSlider.value = String(n); updateFill();
                });
                minSlider.addEventListener('input', function() {
                    var n = parseInt(minSlider.value, 10);
                    if (n > Number(v.max)) n = Number(v.max);
                    v.min = n; minInp.value = String(n); updateFill();
                });
                maxSlider.addEventListener('input', function() {
                    var n = parseInt(maxSlider.value, 10);
                    if (n < Number(v.min)) n = Number(v.min);
                    v.max = n; maxInp.value = String(n); updateFill();
                });
                [minInp, maxInp].forEach(function(el) {
                    el.addEventListener('keydown', function(e) { e.stopPropagation(); });
                });
            });
        }
    }

    renderBody();
    _tvAppendOverlay(chartId, overlay);
}

