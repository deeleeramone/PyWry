function _tvShowVolumeSettings(chartId) {
    _tvHideVolumeSettings();
    var resolved = _tvResolveChartEntry(chartId);
    if (!resolved || !resolved.entry) return;
    chartId = resolved.chartId;
    var entry = resolved.entry;
    var volSeries = entry.volumeMap && entry.volumeMap.main;
    if (!volSeries) return;

    var currentOpts = {};
    try { currentOpts = volSeries.options() || {}; } catch (e) {}
    var palette = TVCHART_THEMES._get(entry.theme || _tvDetectTheme());

    // Read persisted volume prefs or derive from current state
    var prefs = entry._volumeColorPrefs || {};
    var draft = {
        upColor: _tvColorToHex(prefs.upColor || palette.volumeUp, palette.volumeUp),
        downColor: _tvColorToHex(prefs.downColor || palette.volumeDown || palette.volumeUp, palette.volumeDown || palette.volumeUp),
        // Inputs
        maLength: prefs.maLength || 20,
        volumeMA: prefs.volumeMA || 'SMA',
        colorBasedOnPrevClose: !!prefs.colorBasedOnPrevClose,
        smoothingLine: prefs.smoothingLine || 'SMA',
        smoothingLength: prefs.smoothingLength || 9,
        // Style
        showVolume: prefs.showVolumePlot !== false,
        showVolumeMA: !!prefs.showVolumeMA,
        volumeMAColor: prefs.volumeMAColor || '#2196f3',
        showSmoothedMA: !!prefs.showSmoothedMA,
        smoothedMAColor: prefs.smoothedMAColor || '#ff6d00',
        precision: prefs.precision || 'Default',
        labelsOnPriceScale: prefs.labelsOnPriceScale !== false,
        valuesInStatusLine: prefs.valuesInStatusLine !== false,
        inputsInStatusLine: prefs.inputsInStatusLine !== false,
        priceLine: !!prefs.priceLine,
        // Visibility
        visibility: prefs.visibility || null,
    };

    // Snapshot original state for cancel/revert
    var snapshot = JSON.parse(JSON.stringify(draft));

    // --- Live preview helper: recolour volume bars immediately ---
    function applyVolumeLive() {
        var rawBars = entry._rawData;
        if (!rawBars || !Array.isArray(rawBars) || rawBars.length === 0 || !volSeries) return;
        var newVolData = [];
        for (var i = 0; i < rawBars.length; i++) {
            var b = rawBars[i];
            var v = b.volume != null ? b.volume : (b.Volume != null ? b.Volume : b.vol);
            if (v == null || isNaN(v)) continue;
            var isUp;
            if (draft.colorBasedOnPrevClose) {
                var prevClose = (i > 0) ? (rawBars[i - 1].close != null ? rawBars[i - 1].close : rawBars[i - 1].Close) : null;
                isUp = (prevClose != null && b.close != null) ? b.close >= prevClose : true;
            } else {
                isUp = (b.close != null && b.open != null) ? b.close >= b.open : true;
            }
            newVolData.push({
                time: b.time,
                value: +v,
                color: isUp ? draft.upColor : draft.downColor,
            });
        }
        if (newVolData.length > 0) volSeries.setData(newVolData);
    }

    var overlay = document.createElement('div');
    overlay.className = 'tv-settings-overlay';
    _volumeSettingsOverlay = overlay;
    _volumeSettingsOverlayChartId = chartId;
    _tvSetChartInteractionLocked(chartId, true);
    _tvRefreshLegendVisibility();
    overlay.addEventListener('click', function(e) {
        if (e.target === overlay) {
            // Revert on backdrop click
            draft = JSON.parse(JSON.stringify(snapshot));
            applyVolumeLive();
            _tvHideVolumeSettings();
        }
    });
    overlay.addEventListener('mousedown', function(e) { e.stopPropagation(); });
    overlay.addEventListener('wheel', function(e) { e.stopPropagation(); });

    var panel = document.createElement('div');
    panel.className = 'tv-settings-panel';
    panel.style.cssText = 'width:460px;max-width:calc(100% - 32px);max-height:70vh;display:flex;flex-direction:column;';
    overlay.appendChild(panel);

    // Header
    var header = document.createElement('div');
    header.className = 'tv-settings-header';
    header.style.cssText = 'position:relative;flex-direction:column;align-items:stretch;padding-bottom:0;';
    var hdrRow = document.createElement('div');
    hdrRow.style.cssText = 'display:flex;align-items:center;gap:8px;';
    var titleEl = document.createElement('h3');
    titleEl.textContent = 'Volume';
    hdrRow.appendChild(titleEl);
    var closeBtn = document.createElement('button');
    closeBtn.className = 'tv-settings-close';
    closeBtn.innerHTML = '<svg viewBox="0 0 16 16"><line x1="3" y1="3" x2="13" y2="13"/><line x1="13" y1="3" x2="3" y2="13"/></svg>';
    closeBtn.addEventListener('click', function() {
        draft = JSON.parse(JSON.stringify(snapshot));
        applyVolumeLive();
        _tvHideVolumeSettings();
    });
    hdrRow.appendChild(closeBtn);
    header.appendChild(hdrRow);

    // Tab bar
    var activeTab = 'inputs';
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

    // Body
    var body = document.createElement('div');
    body.className = 'tv-settings-body';
    body.style.cssText = 'flex:1;overflow-y:auto;min-height:80px;padding:16px 20px;';
    panel.appendChild(body);

    // --- Row builder helpers ---
    function addSection(parent, text) {
        var sec = document.createElement('div');
        sec.className = 'tv-settings-section';
        sec.textContent = text;
        parent.appendChild(sec);
    }
    function makeRow(labelText) {
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
    function makeColorSwatch(color, onChange) {
        var swatch = document.createElement('div');
        swatch.className = 'ts-swatch';
        swatch.dataset.baseColor = _tvColorToHex(color, '#aeb4c2');
        swatch.dataset.opacity = String(_tvColorOpacityPercent(color, 100));
        swatch.style.background = color;
        swatch.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            _tvShowColorOpacityPopup(
                swatch,
                swatch.dataset.baseColor || color,
                _tvToNumber(swatch.dataset.opacity, 100),
                overlay,
                function(newColor, newOpacity) {
                    swatch.dataset.baseColor = newColor;
                    swatch.dataset.opacity = String(newOpacity);
                    var display = _tvColorWithOpacity(newColor, newOpacity, newColor);
                    swatch.style.background = display;
                    onChange(display, newColor, newOpacity);
                }
            );
        });
        return swatch;
    }
    function addCheckRow(parent, label, val, onChange) {
        var row = document.createElement('div');
        row.className = 'tv-settings-row tv-settings-row-spaced';
        var lbl = document.createElement('label'); lbl.textContent = label; row.appendChild(lbl);
        var cb = document.createElement('input'); cb.type = 'checkbox'; cb.className = 'ts-checkbox';
        cb.checked = !!val;
        cb.addEventListener('change', function() { onChange(cb.checked); });
        row.appendChild(cb); parent.appendChild(row);
    }
    function addSelectRow(parent, label, opts, val, onChange) {
        var row = document.createElement('div');
        row.className = 'tv-settings-row tv-settings-row-spaced';
        var lbl = document.createElement('label'); lbl.textContent = label; row.appendChild(lbl);
        var sel = document.createElement('select'); sel.className = 'ts-select';
        opts.forEach(function(o) {
            var opt = document.createElement('option');
            opt.value = typeof o === 'string' ? o : o.v;
            opt.textContent = typeof o === 'string' ? o : o.l;
            if (String(opt.value) === String(val)) opt.selected = true;
            sel.appendChild(opt);
        });
        sel.addEventListener('change', function() { onChange(sel.value); });
        row.appendChild(sel); parent.appendChild(row);
    }
    function addNumberRow(parent, label, min, max, step, val, onChange) {
        var row = document.createElement('div');
        row.className = 'tv-settings-row tv-settings-row-spaced';
        var lbl = document.createElement('label'); lbl.textContent = label; row.appendChild(lbl);
        var inp = document.createElement('input'); inp.type = 'number'; inp.className = 'ts-input';
        inp.min = min; inp.max = max; inp.step = step; inp.value = val;
        inp.addEventListener('keydown', function(e) { e.stopPropagation(); });
        inp.addEventListener('input', function() { var v = parseFloat(inp.value); if (!isNaN(v) && v >= parseFloat(min)) onChange(v); });
        row.appendChild(inp); parent.appendChild(row);
    }

    function renderBody() {
        body.innerHTML = '';

        // ===================== INPUTS TAB =====================
        if (activeTab === 'inputs') {
            // Symbol source radio buttons (separate section, no tv-settings-row label sizing)
            var symSection = document.createElement('div');
            symSection.style.cssText = 'display:flex;flex-direction:column;gap:10px;padding-bottom:12px;border-bottom:1px solid var(--pywry-tvchart-divider,rgba(128,128,128,0.15));margin-bottom:12px;';

            var r1 = document.createElement('label');
            r1.style.cssText = 'display:flex;align-items:center;gap:8px;cursor:pointer;font-size:12px;color:var(--pywry-tvchart-text);';
            var rb1 = document.createElement('input'); rb1.type = 'radio'; rb1.name = 'vol-sym-src'; rb1.value = 'main'; rb1.checked = true;
            rb1.style.cssText = 'margin:0;';
            r1.appendChild(rb1);
            r1.appendChild(document.createTextNode('Main chart symbol'));
            symSection.appendChild(r1);

            var r2 = document.createElement('label');
            r2.style.cssText = 'display:flex;align-items:center;gap:8px;cursor:default;font-size:12px;color:var(--pywry-tvchart-text-muted,#787b86);opacity:0.5;';
            var rb2 = document.createElement('input'); rb2.type = 'radio'; rb2.name = 'vol-sym-src'; rb2.value = 'other'; rb2.disabled = true;
            rb2.style.cssText = 'margin:0;';
            r2.appendChild(rb2);
            r2.appendChild(document.createTextNode('Another symbol'));
            // Pencil icon (disabled)
            var pencilSvg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
            pencilSvg.setAttribute('viewBox', '0 0 18 18');
            pencilSvg.setAttribute('width', '14');
            pencilSvg.setAttribute('height', '14');
            pencilSvg.style.cssText = 'opacity:0.4;flex-shrink:0;';
            pencilSvg.innerHTML = '<path d="M2.5 13.5l-.5 2 2-.5L14.5 4.5l-1.5-1.5z" fill="none" stroke="currentColor" stroke-width="1.2"/>';
            r2.appendChild(pencilSvg);
            symSection.appendChild(r2);

            body.appendChild(symSection);

            // Remaining input fields
            addNumberRow(body, 'MA Length', '1', '500', '1', draft.maLength, function(v) { draft.maLength = v; });
            addSelectRow(body, 'Volume MA', [
                { v: 'SMA', l: 'SMA' }, { v: 'EMA', l: 'EMA' }, { v: 'WMA', l: 'WMA' },
            ], draft.volumeMA, function(v) { draft.volumeMA = v; });
            addCheckRow(body, 'Color based on previous close', draft.colorBasedOnPrevClose, function(v) {
                draft.colorBasedOnPrevClose = v;
                applyVolumeLive();
            });
            addSelectRow(body, 'Smoothing Line', [
                { v: 'SMA', l: 'SMA' }, { v: 'EMA', l: 'EMA' }, { v: 'WMA', l: 'WMA' },
            ], draft.smoothingLine, function(v) { draft.smoothingLine = v; });
            addNumberRow(body, 'Smoothing Length', '1', '200', '1', draft.smoothingLength, function(v) { draft.smoothingLength = v; });

        // ===================== STYLE TAB =====================
        } else if (activeTab === 'style') {
            // Volume row: checkbox + "Volume" label ... Falling swatch  Growing swatch
            var volRow = document.createElement('div');
            volRow.style.cssText = 'display:flex;align-items:center;gap:8px;margin-bottom:2px;';
            var volCb = document.createElement('input'); volCb.type = 'checkbox'; volCb.className = 'ts-checkbox';
            volCb.checked = draft.showVolume;
            volCb.addEventListener('change', function() { draft.showVolume = volCb.checked; });
            volRow.appendChild(volCb);
            var volLbl = document.createElement('span');
            volLbl.textContent = 'Volume';
            volLbl.style.cssText = 'font-size:12px;color:var(--pywry-tvchart-text);flex:1;';
            volRow.appendChild(volLbl);

            // Falling color group (down)
            var fallGroup = document.createElement('div');
            fallGroup.style.cssText = 'display:flex;flex-direction:column;align-items:center;gap:3px;';
            var downSwatch = makeColorSwatch(draft.downColor, function(display) {
                draft.downColor = display;
                applyVolumeLive();
            });
            fallGroup.appendChild(downSwatch);
            var fallLbl = document.createElement('span');
            fallLbl.textContent = 'Falling';
            fallLbl.style.cssText = 'font-size:10px;color:var(--pywry-tvchart-text-muted,#787b86);';
            fallGroup.appendChild(fallLbl);
            volRow.appendChild(fallGroup);

            // Growing color group (up)
            var growGroup = document.createElement('div');
            growGroup.style.cssText = 'display:flex;flex-direction:column;align-items:center;gap:3px;';
            var upSwatch = makeColorSwatch(draft.upColor, function(display) {
                draft.upColor = display;
                applyVolumeLive();
            });
            growGroup.appendChild(upSwatch);
            var growLbl = document.createElement('span');
            growLbl.textContent = 'Growing';
            growLbl.style.cssText = 'font-size:10px;color:var(--pywry-tvchart-text-muted,#787b86);';
            growGroup.appendChild(growLbl);
            volRow.appendChild(growGroup);

            body.appendChild(volRow);

            // Separator
            var sep1 = document.createElement('div');
            sep1.style.cssText = 'border-bottom:1px solid var(--pywry-tvchart-divider,rgba(128,128,128,0.15));margin:10px 0;';
            body.appendChild(sep1);

            // Price line toggle
            addCheckRow(body, 'Price line', draft.priceLine, function(v) { draft.priceLine = v; });

            // Separator
            var sep2 = document.createElement('div');
            sep2.style.cssText = 'border-bottom:1px solid var(--pywry-tvchart-divider,rgba(128,128,128,0.15));margin:10px 0;';
            body.appendChild(sep2);

            // Volume MA row: checkbox + label + color
            var maRow = document.createElement('div');
            maRow.style.cssText = 'display:flex;align-items:center;gap:8px;margin-bottom:8px;';
            var maCb = document.createElement('input'); maCb.type = 'checkbox'; maCb.className = 'ts-checkbox';
            maCb.checked = draft.showVolumeMA;
            maCb.addEventListener('change', function() { draft.showVolumeMA = maCb.checked; });
            maRow.appendChild(maCb);
            var maLbl = document.createElement('span');
            maLbl.textContent = 'Volume MA';
            maLbl.style.cssText = 'font-size:12px;color:var(--pywry-tvchart-text);flex:1;';
            maRow.appendChild(maLbl);
            maRow.appendChild(makeColorSwatch(draft.volumeMAColor, function(display) { draft.volumeMAColor = display; }));
            body.appendChild(maRow);

            // Smoothed MA row: checkbox + label + color
            var smRow = document.createElement('div');
            smRow.style.cssText = 'display:flex;align-items:center;gap:8px;margin-bottom:8px;';
            var smCb = document.createElement('input'); smCb.type = 'checkbox'; smCb.className = 'ts-checkbox';
            smCb.checked = draft.showSmoothedMA;
            smCb.addEventListener('change', function() { draft.showSmoothedMA = smCb.checked; });
            smRow.appendChild(smCb);
            var smLbl = document.createElement('span');
            smLbl.textContent = 'Smoothed MA';
            smLbl.style.cssText = 'font-size:12px;color:var(--pywry-tvchart-text);flex:1;';
            smRow.appendChild(smLbl);
            smRow.appendChild(makeColorSwatch(draft.smoothedMAColor, function(display) { draft.smoothedMAColor = display; }));
            body.appendChild(smRow);

            // Separator
            var sep3 = document.createElement('div');
            sep3.style.cssText = 'border-bottom:1px solid var(--pywry-tvchart-divider,rgba(128,128,128,0.15));margin:10px 0;';
            body.appendChild(sep3);

            // OUTPUT VALUES section
            addSection(body, 'OUTPUT VALUES');
            addSelectRow(body, 'Precision', [
                { v: 'Default', l: 'Default' }, { v: '0', l: '0' }, { v: '1', l: '1' },
                { v: '2', l: '2' }, { v: '3', l: '3' }, { v: '4', l: '4' },
            ], draft.precision, function(v) { draft.precision = v; });
            addCheckRow(body, 'Labels on price scale', draft.labelsOnPriceScale, function(v) { draft.labelsOnPriceScale = v; });
            addCheckRow(body, 'Values in status line', draft.valuesInStatusLine, function(v) { draft.valuesInStatusLine = v; });

            // INPUT VALUES section
            addSection(body, 'INPUT VALUES');
            addCheckRow(body, 'Inputs in status line', draft.inputsInStatusLine, function(v) { draft.inputsInStatusLine = v; });

        // ===================== VISIBILITY TAB =====================
        } else if (activeTab === 'visibility') {
            addSection(body, 'TIMEFRAME VISIBILITY');
            var intervals = [
                { key: 'seconds', label: 'Seconds', rangeLabel: '1s \u2013 59s' },
                { key: 'minutes', label: 'Minutes', rangeLabel: '1m \u2013 59m' },
                { key: 'hours', label: 'Hours', rangeLabel: '1H \u2013 24H' },
                { key: 'days', label: 'Days', rangeLabel: '1D \u2013 1Y' },
                { key: 'weeks', label: 'Weeks', rangeLabel: '1W \u2013 52W' },
                { key: 'months', label: 'Months', rangeLabel: '1M \u2013 12M' },
            ];
            if (!draft.visibility) {
                draft.visibility = {};
                intervals.forEach(function(iv) { draft.visibility[iv.key] = true; });
            }
            intervals.forEach(function(iv) {
                var row = document.createElement('div');
                row.className = 'tv-settings-row tv-settings-row-spaced';
                row.style.cssText = 'display:flex;align-items:center;gap:8px;';
                var cb = document.createElement('input'); cb.type = 'checkbox'; cb.className = 'ts-checkbox';
                cb.checked = draft.visibility[iv.key] !== false;
                cb.addEventListener('change', function() { draft.visibility[iv.key] = cb.checked; });
                row.appendChild(cb);
                var lbl = document.createElement('label'); lbl.style.flex = '1';
                lbl.textContent = iv.label;
                row.appendChild(lbl);
                var range = document.createElement('span');
                range.style.cssText = 'color:var(--pywry-tvchart-text-muted,#787b86);font-size:11px;';
                range.textContent = iv.rangeLabel;
                row.appendChild(range);
                body.appendChild(row);
            });
        }
    }

    renderBody();

    // Footer with Defaults dropdown, Cancel, Ok
    var footer = document.createElement('div');
    footer.className = 'tv-settings-footer';
    footer.style.cssText = 'position:relative;bottom:auto;left:auto;right:auto;';

    var cancelBtn = document.createElement('button');
    cancelBtn.className = 'ts-btn-cancel';
    cancelBtn.textContent = 'Cancel';
    cancelBtn.addEventListener('click', function() {
        draft = JSON.parse(JSON.stringify(snapshot));
        applyVolumeLive();
        _tvHideVolumeSettings();
    });
    footer.appendChild(cancelBtn);

    var okBtn = document.createElement('button');
    okBtn.className = 'ts-btn-ok';
    okBtn.textContent = 'Ok';
    okBtn.addEventListener('click', function() {
        // Persist all volume prefs
        if (!entry._volumeColorPrefs) entry._volumeColorPrefs = {};
        entry._volumeColorPrefs.upColor = draft.upColor;
        entry._volumeColorPrefs.downColor = draft.downColor;
        entry._volumeColorPrefs.maLength = draft.maLength;
        entry._volumeColorPrefs.volumeMA = draft.volumeMA;
        entry._volumeColorPrefs.colorBasedOnPrevClose = draft.colorBasedOnPrevClose;
        entry._volumeColorPrefs.smoothingLine = draft.smoothingLine;
        entry._volumeColorPrefs.smoothingLength = draft.smoothingLength;
        entry._volumeColorPrefs.showVolumePlot = draft.showVolume;
        entry._volumeColorPrefs.showVolumeMA = draft.showVolumeMA;
        entry._volumeColorPrefs.volumeMAColor = draft.volumeMAColor;
        entry._volumeColorPrefs.showSmoothedMA = draft.showSmoothedMA;
        entry._volumeColorPrefs.smoothedMAColor = draft.smoothedMAColor;
        entry._volumeColorPrefs.precision = draft.precision;
        entry._volumeColorPrefs.labelsOnPriceScale = draft.labelsOnPriceScale;
        entry._volumeColorPrefs.valuesInStatusLine = draft.valuesInStatusLine;
        entry._volumeColorPrefs.inputsInStatusLine = draft.inputsInStatusLine;
        entry._volumeColorPrefs.priceLine = draft.priceLine;
        entry._volumeColorPrefs.visibility = draft.visibility;

        // Apply live colour change (already previewed) and update series options
        applyVolumeLive();
        if (volSeries) {
            try {
                volSeries.applyOptions({
                    lastValueVisible: draft.priceLine,
                    priceLineVisible: draft.priceLine,
                });
            } catch (e) {}
        }

        _tvHideVolumeSettings();
    });
    footer.appendChild(okBtn);
    panel.appendChild(footer);

    _tvOverlayContainer(chartId).appendChild(overlay);
}

