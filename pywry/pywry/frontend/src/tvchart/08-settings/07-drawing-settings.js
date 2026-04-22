function _tvShowDrawingSettings(chartId, drawIdx) {
    _tvHideDrawingSettings();
    var ds = window.__PYWRY_DRAWINGS__[chartId];
    if (!ds || drawIdx < 0 || drawIdx >= ds.drawings.length) return;
    var d = ds.drawings[drawIdx];
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (!entry) return;

    // Clone properties for cancel support
    var draft = Object.assign({}, d);

    var overlay = document.createElement('div');
    overlay.className = 'tv-settings-overlay';
    _settingsOverlay = overlay;
    _settingsOverlayChartId = chartId;
    _tvSetChartInteractionLocked(chartId, true);
    overlay.addEventListener('click', function(e) {
        if (e.target === overlay) _tvHideDrawingSettings();
    });
    overlay.addEventListener('mousedown', function(e) { e.stopPropagation(); });
    overlay.addEventListener('wheel', function(e) { e.stopPropagation(); });

    var panel = document.createElement('div');
    panel.className = 'tv-settings-panel';
    panel.style.flexDirection = 'column';
    panel.style.width = '560px';
    overlay.appendChild(panel);

    // Header
    var header = document.createElement('div');
    header.className = 'tv-settings-header';
    header.style.cssText = 'position:relative;flex-direction:column;align-items:stretch;padding-bottom:0;';
    var hdrRow = document.createElement('div');
    hdrRow.style.cssText = 'display:flex;align-items:center;gap:8px;';
    var title = document.createElement('h3');
    title.textContent = _DRAW_TYPE_NAMES[d.type] || d.type;
    hdrRow.appendChild(title);
    var closeBtn = document.createElement('button');
    closeBtn.className = 'tv-settings-close';
    closeBtn.innerHTML = '<svg viewBox="0 0 16 16"><line x1="3" y1="3" x2="13" y2="13"/><line x1="13" y1="3" x2="3" y2="13"/></svg>';
    closeBtn.addEventListener('click', function() { _tvHideDrawingSettings(); });
    hdrRow.appendChild(closeBtn);
    header.appendChild(hdrRow);

    // Tabs — Text tab for text drawing type and line tools
    // Build tab list per drawing type (matching TradingView layout)
    var tabs = [];
    var _inputsTools = ['regression_channel', 'fibonacci', 'trendline',
        'fib_extension', 'fib_channel', 'fib_timezone', 'fib_fan',
        'fib_arc', 'fib_circle', 'fib_wedge', 'pitchfan',
        'fib_time', 'gann_box', 'gann_square_fixed', 'gann_square', 'gann_fan',
        'long_position', 'short_position', 'forecast'];
    if (_inputsTools.indexOf(d.type) !== -1) tabs.push('Inputs');
    tabs.push('Style');
    var _textTabTools = ['text', 'trendline', 'ray', 'extended_line', 'arrow_marker', 'arrow', 'arrow_mark_up', 'arrow_mark_down', 'arrow_mark_left', 'arrow_mark_right', 'anchored_text', 'note', 'price_note', 'pin', 'callout', 'comment', 'price_label', 'signpost', 'flag_mark'];
    if (_textTabTools.indexOf(d.type) !== -1) tabs.push('Text');
    tabs.push('Coordinates', 'Visibility');
    var activeTab = tabs[0];

    var tabBar = document.createElement('div');
    tabBar.className = 'tv-settings-tabs';
    header.appendChild(tabBar);
    panel.appendChild(header);

    var body = document.createElement('div');
    body.className = 'tv-settings-body';
    body.style.cssText = 'flex:1;overflow-y:auto;';
    panel.appendChild(body);

    function renderTabs() {
        tabBar.innerHTML = '';
        for (var ti = 0; ti < tabs.length; ti++) {
            (function(tname) {
                var tab = document.createElement('div');
                tab.className = 'tv-settings-tab' + (tname === activeTab ? ' active' : '');
                tab.textContent = tname;
                tab.addEventListener('click', function() {
                    activeTab = tname;
                    renderTabs();
                    renderBody();
                });
                tabBar.appendChild(tab);
            })(tabs[ti]);
        }
    }

    function makeRow(labelText) {
        var row = document.createElement('div');
        row.className = 'tv-settings-row';
        var lbl = document.createElement('label');
        lbl.textContent = labelText;
        row.appendChild(lbl);
        var ctrl = document.createElement('div');
        ctrl.className = 'ts-controls';
        row.appendChild(ctrl);
        return { row: row, ctrl: ctrl };
    }

    function makeColorSwatch(color, onChange) {
        var sw = document.createElement('div');
        sw.className = 'ts-swatch';
        sw.dataset.baseColor = _tvColorToHex(color || '#aeb4c2', '#aeb4c2');
        sw.dataset.opacity = String(_tvColorOpacityPercent(color, 100));
        sw.style.background = color;
        sw.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            _tvShowColorOpacityPopup(
                sw,
                sw.dataset.baseColor || color,
                _tvToNumber(sw.dataset.opacity, 100),
                overlay,
                function(newColor, newOpacity) {
                    sw.dataset.baseColor = newColor;
                    sw.dataset.opacity = String(newOpacity);
                    sw.style.background = _tvColorWithOpacity(newColor, newOpacity, newColor);
                    color = newColor;
                    onChange(_tvColorWithOpacity(newColor, newOpacity, newColor), newOpacity);
                }
            );
        });
        return sw;
    }

    function makeSelect(options, current, onChange) {
        var sel = document.createElement('select');
        sel.className = 'ts-select';
        for (var si = 0; si < options.length; si++) {
            var opt = document.createElement('option');
            opt.value = options[si].value !== undefined ? options[si].value : options[si];
            opt.textContent = options[si].label || options[si];
            if (String(opt.value) === String(current)) opt.selected = true;
            sel.appendChild(opt);
        }
        sel.addEventListener('change', function() { onChange(sel.value); });
        return sel;
    }

    function makeCheckbox(checked, onChange) {
        var cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.className = 'ts-checkbox';
        cb.checked = !!checked;
        cb.addEventListener('change', function() { onChange(cb.checked); });
        return cb;
    }

    function makeTextInput(val, onChange) {
        var inp = document.createElement('input');
        inp.type = 'text';
        inp.className = 'ts-input ts-input-full';
        inp.value = val || '';
        inp.addEventListener('input', function() { onChange(inp.value); });
        inp.addEventListener('keydown', function(e) { e.stopPropagation(); });
        return inp;
    }

    function makeNumberInput(val, onChange) {
        var inp = document.createElement('input');
        inp.type = 'number';
        inp.className = 'ts-input';
        inp.value = val;
        inp.step = 'any';
        inp.addEventListener('input', function() { onChange(parseFloat(inp.value)); });
        inp.addEventListener('keydown', function(e) { e.stopPropagation(); });
        return inp;
    }

    function makeOpacityInput(val, onChange) {
        var wrap = document.createElement('div');
        wrap.style.cssText = 'display:flex;align-items:center;gap:6px;';
        var slider = document.createElement('input');
        slider.type = 'range';
        slider.className = 'tv-settings-slider';
        slider.min = '0'; slider.max = '100';
        slider.value = String(Math.round((val !== undefined ? val : 0.15) * 100));
        var numBox = document.createElement('input');
        numBox.type = 'number';
        numBox.className = 'ts-input ts-input-sm';
        numBox.min = '0'; numBox.max = '100';
        numBox.value = slider.value;
        numBox.addEventListener('keydown', function(e) { e.stopPropagation(); });
        slider.addEventListener('input', function() {
            numBox.value = slider.value;
            onChange(parseInt(slider.value) / 100);
        });
        numBox.addEventListener('input', function() {
            slider.value = numBox.value;
            onChange(parseInt(numBox.value) / 100);
        });
        var pct = document.createElement('span');
        pct.className = 'tv-settings-unit';
        pct.textContent = '%';
        wrap.appendChild(slider); wrap.appendChild(numBox); wrap.appendChild(pct);
        return wrap;
    }

    function addSectionHeading(text) {
        var sec = document.createElement('div');
        sec.className = 'tv-settings-section';
        sec.textContent = text;
        body.appendChild(sec);
    }

    // Shared: Line row with color swatch + style toggle buttons
    function addLineRow(container) {
        var cRow = makeRow('Line');
        var lineSwatch = makeColorSwatch(draft.color || _drawDefaults.color, function(c) { draft.color = c; });
        cRow.ctrl.appendChild(lineSwatch);
        var styleGroup = document.createElement('div');
        styleGroup.className = 'ts-line-style-group';
        var styleOpts = [
            { val: 0, svg: '<svg width="28" height="14"><line x1="2" y1="7" x2="26" y2="7" stroke="currentColor" stroke-width="2"/></svg>' },
            { val: 1, svg: '<svg width="28" height="14"><line x1="2" y1="7" x2="26" y2="7" stroke="currentColor" stroke-width="2" stroke-dasharray="6,3"/></svg>' },
            { val: 2, svg: '<svg width="28" height="14"><line x1="2" y1="7" x2="26" y2="7" stroke="currentColor" stroke-width="2" stroke-dasharray="2,3"/></svg>' },
        ];
        var styleBtns = [];
        styleOpts.forEach(function(so) {
            var btn = document.createElement('button');
            btn.className = 'ts-line-style-btn' + (parseInt(draft.lineStyle || 0) === so.val ? ' active' : '');
            btn.innerHTML = so.svg;
            btn.addEventListener('click', function() {
                draft.lineStyle = so.val;
                styleBtns.forEach(function(b) { b.classList.remove('active'); });
                btn.classList.add('active');
            });
            styleBtns.push(btn);
            styleGroup.appendChild(btn);
        });
        cRow.ctrl.appendChild(styleGroup);
        container.appendChild(cRow.row);
    }

    // Shared: Width row
    function addWidthRow(container) {
        var wRow = makeRow('Width');
        wRow.ctrl.appendChild(makeSelect([{value:1,label:'1px'},{value:2,label:'2px'},{value:3,label:'3px'},{value:4,label:'4px'},{value:5,label:'5px'}], draft.lineWidth || 2, function(v) { draft.lineWidth = parseInt(v); }));
        container.appendChild(wRow.row);
    }

    // Shared: TV-style compound line control (checkbox + color + line-style buttons)
    // opts: { label, showKey, colorKey, styleKey, widthKey, defaultColor, defaultStyle, defaultShow }
    function addCompoundLineRow(container, opts) {
        var row = makeRow(opts.label);
        // Checkbox
        row.ctrl.appendChild(makeCheckbox(draft[opts.showKey] !== false, function(v) { draft[opts.showKey] = v; }));
        // Color swatch
        row.ctrl.appendChild(makeColorSwatch(draft[opts.colorKey] || opts.defaultColor || draft.color || _drawDefaults.color, function(c) { draft[opts.colorKey] = c; }));
        // Line style selector
        var styleGroup = document.createElement('div');
        styleGroup.className = 'ts-line-style-group';
        var styleOpts = [
            { val: 0, svg: '<svg width="28" height="14"><line x1="2" y1="7" x2="26" y2="7" stroke="currentColor" stroke-width="2"/></svg>' },
            { val: 1, svg: '<svg width="28" height="14"><line x1="2" y1="7" x2="26" y2="7" stroke="currentColor" stroke-width="2" stroke-dasharray="6,3"/></svg>' },
            { val: 2, svg: '<svg width="28" height="14"><line x1="2" y1="7" x2="26" y2="7" stroke="currentColor" stroke-width="2" stroke-dasharray="2,3"/></svg>' },
        ];
        var curStyle = draft[opts.styleKey] !== undefined ? draft[opts.styleKey] : (opts.defaultStyle || 0);
        var styleBtns = [];
        styleOpts.forEach(function(so) {
            var btn = document.createElement('button');
            btn.className = 'ts-line-style-btn' + (parseInt(curStyle) === so.val ? ' active' : '');
            btn.innerHTML = so.svg;
            btn.addEventListener('click', function() {
                draft[opts.styleKey] = so.val;
                styleBtns.forEach(function(b) { b.classList.remove('active'); });
                btn.classList.add('active');
            });
            styleBtns.push(btn);
            styleGroup.appendChild(btn);
        });
        row.ctrl.appendChild(styleGroup);
        container.appendChild(row.row);
    }

    // Shared: TV-style visibility time interval section
    function addVisibilityIntervals(container) {
        var intervals = [
            { key: 'seconds', label: 'Seconds', defFrom: 1, defTo: 59 },
            { key: 'minutes', label: 'Minutes', defFrom: 1, defTo: 59 },
            { key: 'hours', label: 'Hours', defFrom: 1, defTo: 24 },
            { key: 'days', label: 'Days', defFrom: 1, defTo: 365 },
            { key: 'weeks', label: 'Weeks', defFrom: 1, defTo: 52 },
            { key: 'months', label: 'Months', defFrom: 1, defTo: 12 },
        ];
        if (!draft.visibility) draft.visibility = {};
        for (var vi = 0; vi < intervals.length; vi++) {
            (function(itv) {
                if (!draft.visibility[itv.key]) {
                    draft.visibility[itv.key] = { enabled: true, from: itv.defFrom, to: itv.defTo };
                }
                var vis = draft.visibility[itv.key];
                var row = makeRow(itv.label);
                // Checkbox
                row.ctrl.appendChild(makeCheckbox(vis.enabled !== false, function(v) { vis.enabled = v; }));
                // From
                var fromInp = document.createElement('input');
                fromInp.type = 'number'; fromInp.className = 'ts-input ts-input-sm';
                fromInp.min = String(itv.defFrom); fromInp.max = String(itv.defTo);
                fromInp.value = String(vis.from || itv.defFrom);
                fromInp.addEventListener('input', function() { vis.from = parseInt(fromInp.value) || itv.defFrom; slider.value = String(vis.from); });
                fromInp.addEventListener('keydown', function(e) { e.stopPropagation(); });
                row.ctrl.appendChild(fromInp);
                // Slider
                var slider = document.createElement('input');
                slider.type = 'range'; slider.className = 'tv-settings-slider';
                slider.min = String(itv.defFrom); slider.max = String(itv.defTo);
                slider.value = String(vis.from || itv.defFrom);
                slider.addEventListener('input', function() { vis.from = parseInt(slider.value); fromInp.value = slider.value; });
                row.ctrl.appendChild(slider);
                // To
                var toInp = document.createElement('input');
                toInp.type = 'number'; toInp.className = 'ts-input ts-input-sm';
                toInp.min = String(itv.defFrom); toInp.max = String(itv.defTo);
                toInp.value = String(vis.to || itv.defTo);
                toInp.addEventListener('input', function() { vis.to = parseInt(toInp.value) || itv.defTo; });
                toInp.addEventListener('keydown', function(e) { e.stopPropagation(); });
                row.ctrl.appendChild(toInp);
                container.appendChild(row.row);
            })(intervals[vi]);
        }
    }

    function renderBody() {
        body.innerHTML = '';

        if (activeTab === 'Inputs') {
            // ---- INPUTS TAB ----
            if (d.type === 'regression_channel') {
                addSectionHeading('DEVIATION');
                var udRow = makeRow('Upper deviation');
                udRow.ctrl.appendChild(makeNumberInput(draft.upperDeviation !== undefined ? draft.upperDeviation : 2.0, function(v) { draft.upperDeviation = v; }));
                body.appendChild(udRow.row);
                var ldRow = makeRow('Lower deviation');
                ldRow.ctrl.appendChild(makeNumberInput(draft.lowerDeviation !== undefined ? draft.lowerDeviation : 2.0, function(v) { draft.lowerDeviation = v; }));
                body.appendChild(ldRow.row);
                var uuRow = makeRow('Use upper deviation');
                uuRow.ctrl.appendChild(makeCheckbox(draft.useUpperDeviation !== false, function(v) { draft.useUpperDeviation = v; }));
                body.appendChild(uuRow.row);
                var ulRow = makeRow('Use lower deviation');
                ulRow.ctrl.appendChild(makeCheckbox(draft.useLowerDeviation !== false, function(v) { draft.useLowerDeviation = v; }));
                body.appendChild(ulRow.row);
                addSectionHeading('SOURCE');
                var srcRow = makeRow('Source');
                srcRow.ctrl.appendChild(makeSelect([
                    {value:'close',label:'Close'},{value:'open',label:'Open'},
                    {value:'high',label:'High'},{value:'low',label:'Low'},
                    {value:'hl2',label:'(H+L)/2'},{value:'hlc3',label:'(H+L+C)/3'},
                    {value:'ohlc4',label:'(O+H+L+C)/4'}
                ], draft.source || 'close', function(v) { draft.source = v; }));
                body.appendChild(srcRow.row);

            } else if (d.type === 'fibonacci') {
                addSectionHeading('LEVELS');
                var revRow = makeRow('Reverse');
                revRow.ctrl.appendChild(makeCheckbox(!!draft.reverse, function(v) { draft.reverse = v; }));
                body.appendChild(revRow.row);
                var showLabRow = makeRow('Show labels');
                showLabRow.ctrl.appendChild(makeCheckbox(draft.showLabels !== false, function(v) { draft.showLabels = v; }));
                body.appendChild(showLabRow.row);
                var showPrRow = makeRow('Show prices');
                showPrRow.ctrl.appendChild(makeCheckbox(draft.showPrices !== false, function(v) { draft.showPrices = v; }));
                body.appendChild(showPrRow.row);
                var showLevRow = makeRow('Levels based on');
                showLevRow.ctrl.appendChild(makeSelect([
                    {value:'percent',label:'Percent'},{value:'price',label:'Price'}
                ], draft.levelsBasis || 'percent', function(v) { draft.levelsBasis = v; }));
                body.appendChild(showLevRow.row);

            } else if (d.type === 'fib_extension') {
                addSectionHeading('LEVELS');
                var revRow = makeRow('Reverse');
                revRow.ctrl.appendChild(makeCheckbox(!!draft.reverse, function(v) { draft.reverse = v; }));
                body.appendChild(revRow.row);
                var showLabRow = makeRow('Show labels');
                showLabRow.ctrl.appendChild(makeCheckbox(draft.showLabels !== false, function(v) { draft.showLabels = v; }));
                body.appendChild(showLabRow.row);
                var showPrRow = makeRow('Show prices');
                showPrRow.ctrl.appendChild(makeCheckbox(draft.showPrices !== false, function(v) { draft.showPrices = v; }));
                body.appendChild(showPrRow.row);
                var showLevRow = makeRow('Levels based on');
                showLevRow.ctrl.appendChild(makeSelect([
                    {value:'percent',label:'Percent'},{value:'price',label:'Price'}
                ], draft.levelsBasis || 'percent', function(v) { draft.levelsBasis = v; }));
                body.appendChild(showLevRow.row);

            } else if (d.type === 'fib_channel' || d.type === 'fib_fan' || d.type === 'fib_arc' ||
                       d.type === 'fib_circle' || d.type === 'fib_wedge') {
                addSectionHeading('LEVELS');
                var revRow = makeRow('Reverse');
                revRow.ctrl.appendChild(makeCheckbox(!!draft.reverse, function(v) { draft.reverse = v; }));
                body.appendChild(revRow.row);
                var showLabRow = makeRow('Show labels');
                showLabRow.ctrl.appendChild(makeCheckbox(draft.showLabels !== false, function(v) { draft.showLabels = v; }));
                body.appendChild(showLabRow.row);
                var showPrRow = makeRow('Show prices');
                showPrRow.ctrl.appendChild(makeCheckbox(draft.showPrices !== false, function(v) { draft.showPrices = v; }));
                body.appendChild(showPrRow.row);

            } else if (d.type === 'pitchfan') {
                addSectionHeading('OPTIONS');
                var showLabRow = makeRow('Show labels');
                showLabRow.ctrl.appendChild(makeCheckbox(draft.showLabels !== false, function(v) { draft.showLabels = v; }));
                body.appendChild(showLabRow.row);
                var showPrRow = makeRow('Show prices');
                showPrRow.ctrl.appendChild(makeCheckbox(draft.showPrices !== false, function(v) { draft.showPrices = v; }));
                body.appendChild(showPrRow.row);

            } else if (d.type === 'fib_timezone') {
                addSectionHeading('OPTIONS');
                var showLabRow = makeRow('Show labels');
                showLabRow.ctrl.appendChild(makeCheckbox(draft.showLabels !== false, function(v) { draft.showLabels = v; }));
                body.appendChild(showLabRow.row);

            } else if (d.type === 'fib_time') {
                addSectionHeading('OPTIONS');
                var showLabRow = makeRow('Show labels');
                showLabRow.ctrl.appendChild(makeCheckbox(draft.showLabels !== false, function(v) { draft.showLabels = v; }));
                body.appendChild(showLabRow.row);
                var revRow = makeRow('Reverse');
                revRow.ctrl.appendChild(makeCheckbox(!!draft.reverse, function(v) { draft.reverse = v; }));
                body.appendChild(revRow.row);

            } else if (d.type === 'gann_box' || d.type === 'gann_square_fixed' || d.type === 'gann_square') {
                addSectionHeading('OPTIONS');
                var revRow = makeRow('Reverse');
                revRow.ctrl.appendChild(makeCheckbox(!!draft.reverse, function(v) { draft.reverse = v; }));
                body.appendChild(revRow.row);
                var showLabRow = makeRow('Show labels');
                showLabRow.ctrl.appendChild(makeCheckbox(draft.showLabels !== false, function(v) { draft.showLabels = v; }));
                body.appendChild(showLabRow.row);

            } else if (d.type === 'gann_fan') {
                addSectionHeading('OPTIONS');
                var showLabRow = makeRow('Show labels');
                showLabRow.ctrl.appendChild(makeCheckbox(draft.showLabels !== false, function(v) { draft.showLabels = v; }));
                body.appendChild(showLabRow.row);

            } else if (d.type === 'trendline') {
                addSectionHeading('OPTIONS');
                var extRow = makeRow('Extend');
                extRow.ctrl.appendChild(makeSelect(["Don't extend", 'Left', 'Right', 'Both'], draft.extend || "Don't extend", function(v) { draft.extend = v; }));
                body.appendChild(extRow.row);
                var mpRow = makeRow('Middle point');
                mpRow.ctrl.appendChild(makeCheckbox(!!draft.showMiddlePoint, function(v) { draft.showMiddlePoint = v; }));
                body.appendChild(mpRow.row);
                var plRow = makeRow('Price labels');
                plRow.ctrl.appendChild(makeCheckbox(!!draft.showPriceLabels, function(v) { draft.showPriceLabels = v; }));
                body.appendChild(plRow.row);
                addSectionHeading('STATS');
                var statsRow = makeRow('Stats');
                statsRow.ctrl.appendChild(makeSelect([{value:'hidden',label:'Hidden'},{value:'compact',label:'Compact'},{value:'values',label:'Values'}], draft.stats || 'hidden', function(v) { draft.stats = v; }));
                body.appendChild(statsRow.row);
                var spRow = makeRow('Stats position');
                spRow.ctrl.appendChild(makeSelect([{value:'left',label:'Left'},{value:'right',label:'Right'}], draft.statsPosition || 'right', function(v) { draft.statsPosition = v; }));
                body.appendChild(spRow.row);
                var asRow = makeRow('Always show stats');
                asRow.ctrl.appendChild(makeCheckbox(!!draft.alwaysShowStats, function(v) { draft.alwaysShowStats = v; }));
                body.appendChild(asRow.row);

            } else if (d.type === 'long_position' || d.type === 'short_position') {
                addSectionHeading('RISK/REWARD');
                var rrRow = makeRow('Risk/Reward ratio');
                rrRow.ctrl.appendChild(makeNumberInput(draft.riskReward !== undefined ? draft.riskReward : 2.0, function(v) { draft.riskReward = v; }));
                body.appendChild(rrRow.row);
                var lotRow = makeRow('Lot size');
                lotRow.ctrl.appendChild(makeNumberInput(draft.lotSize !== undefined ? draft.lotSize : 1, function(v) { draft.lotSize = v; }));
                body.appendChild(lotRow.row);
                var accRow = makeRow('Account size');
                accRow.ctrl.appendChild(makeNumberInput(draft.accountSize !== undefined ? draft.accountSize : 10000, function(v) { draft.accountSize = v; }));
                body.appendChild(accRow.row);
                var showLblRow = makeRow('Show labels');
                showLblRow.ctrl.appendChild(makeCheckbox(draft.showLabels !== false, function(v) { draft.showLabels = v; }));
                body.appendChild(showLblRow.row);

            } else if (d.type === 'forecast') {
                addSectionHeading('OPTIONS');
                var srcRow = makeRow('Source');
                srcRow.ctrl.appendChild(makeSelect([
                    {value:'close',label:'Close'},{value:'open',label:'Open'},
                    {value:'high',label:'High'},{value:'low',label:'Low'}
                ], draft.source || 'close', function(v) { draft.source = v; }));
                body.appendChild(srcRow.row);
            }

        } else if (activeTab === 'Style') {

            // ---- HLINE ----
            if (d.type === 'hline') {
                addSectionHeading('LINE');
                addLineRow(body);
                addWidthRow(body);
                var extRow = makeRow('Extend');
                extRow.ctrl.appendChild(makeSelect(["Don't extend", 'Left', 'Right', 'Both'], draft.extend || "Don't extend", function(v) { draft.extend = v; }));
                body.appendChild(extRow.row);
                addSectionHeading('PRICE LABEL');
                var plRow = makeRow('Price label');
                plRow.ctrl.appendChild(makeCheckbox(draft.showPriceLabel !== false, function(v) { draft.showPriceLabel = v; }));
                body.appendChild(plRow.row);
                var plColorRow = makeRow('Label color');
                plColorRow.ctrl.appendChild(makeColorSwatch(draft.labelColor || draft.color || _drawDefaults.color, function(c) { draft.labelColor = c; }));
                body.appendChild(plColorRow.row);
                var plTitleRow = makeRow('Label text');
                plTitleRow.ctrl.appendChild(makeTextInput(draft.title || '', function(v) { draft.title = v; }));
                body.appendChild(plTitleRow.row);

            // ---- TRENDLINE / RAY / EXTENDED_LINE ----
            } else if (d.type === 'trendline' || d.type === 'ray' || d.type === 'extended_line') {
                addSectionHeading('LINE');
                addLineRow(body);
                addWidthRow(body);

            // ---- HRAY ----
            } else if (d.type === 'hray') {
                addSectionHeading('LINE');
                addLineRow(body);
                addWidthRow(body);
                addSectionHeading('PRICE LABEL');
                var plRow = makeRow('Price label');
                plRow.ctrl.appendChild(makeCheckbox(draft.showPriceLabel !== false, function(v) { draft.showPriceLabel = v; }));
                body.appendChild(plRow.row);

            // ---- VLINE ----
            } else if (d.type === 'vline') {
                addSectionHeading('LINE');
                addLineRow(body);
                addWidthRow(body);

            // ---- CROSSLINE ----
            } else if (d.type === 'crossline') {
                addSectionHeading('LINE');
                addLineRow(body);
                addWidthRow(body);

            // ---- RECT ----
            } else if (d.type === 'rect') {
                addSectionHeading('BORDER');
                addLineRow(body);
                addWidthRow(body);
                addSectionHeading('BACKGROUND');
                var bgEnRow = makeRow('Background');
                bgEnRow.ctrl.appendChild(makeCheckbox(draft.fillEnabled !== false, function(v) { draft.fillEnabled = v; }));
                bgEnRow.ctrl.appendChild(makeColorSwatch(draft.fillColor || draft.color || _drawDefaults.color, function(c) { draft.fillColor = c; }));
                body.appendChild(bgEnRow.row);
                var bgOpRow = makeRow('Opacity');
                bgOpRow.ctrl.appendChild(makeOpacityInput(draft.fillOpacity !== undefined ? draft.fillOpacity : 0.15, function(v) { draft.fillOpacity = v; }));
                body.appendChild(bgOpRow.row);

            // ---- CHANNEL ----
            } else if (d.type === 'channel') {
                addSectionHeading('LINES');
                addLineRow(body);
                addWidthRow(body);
                var midRow = makeRow('Middle line');
                midRow.ctrl.appendChild(makeCheckbox(draft.showMiddleLine !== false, function(v) { draft.showMiddleLine = v; }));
                body.appendChild(midRow.row);
                var extRow = makeRow('Extend');
                extRow.ctrl.appendChild(makeSelect(["Don't extend", 'Left', 'Right', 'Both'], draft.extend || "Don't extend", function(v) { draft.extend = v; }));
                body.appendChild(extRow.row);
                addSectionHeading('BACKGROUND');
                var bgEnRow = makeRow('Background');
                bgEnRow.ctrl.appendChild(makeCheckbox(draft.fillEnabled !== false, function(v) { draft.fillEnabled = v; }));
                bgEnRow.ctrl.appendChild(makeColorSwatch(draft.fillColor || draft.color || _drawDefaults.color, function(c) { draft.fillColor = c; }));
                body.appendChild(bgEnRow.row);
                var bgOpRow = makeRow('Opacity');
                bgOpRow.ctrl.appendChild(makeOpacityInput(draft.fillOpacity !== undefined ? draft.fillOpacity : 0.08, function(v) { draft.fillOpacity = v; }));
                body.appendChild(bgOpRow.row);

            // ---- REGRESSION_CHANNEL (TV-style: Base/Up/Down lines) ----
            } else if (d.type === 'regression_channel') {
                addCompoundLineRow(body, {
                    label: 'Base', showKey: 'showBaseLine', colorKey: 'baseColor',
                    styleKey: 'baseLineStyle', defaultColor: draft.color || _drawDefaults.color, defaultStyle: 0
                });
                addCompoundLineRow(body, {
                    label: 'Up', showKey: 'showUpLine', colorKey: 'upColor',
                    styleKey: 'upLineStyle', defaultColor: draft.upColor || '#26a69a', defaultStyle: 1
                });
                addCompoundLineRow(body, {
                    label: 'Down', showKey: 'showDownLine', colorKey: 'downColor',
                    styleKey: 'downLineStyle', defaultColor: draft.downColor || '#ef5350', defaultStyle: 1
                });
                var extLnRow = makeRow('Extend lines');
                extLnRow.ctrl.appendChild(makeCheckbox(!!draft.extendLines, function(v) { draft.extendLines = v; }));
                body.appendChild(extLnRow.row);
                var prRow = makeRow("Pearson's R");
                prRow.ctrl.appendChild(makeCheckbox(!!draft.showPearsonsR, function(v) { draft.showPearsonsR = v; }));
                body.appendChild(prRow.row);
                addSectionHeading('BACKGROUND');
                var bgEnRow = makeRow('Background');
                bgEnRow.ctrl.appendChild(makeCheckbox(draft.fillEnabled !== false, function(v) { draft.fillEnabled = v; }));
                bgEnRow.ctrl.appendChild(makeColorSwatch(draft.fillColor || draft.color || _drawDefaults.color, function(c) { draft.fillColor = c; }));
                body.appendChild(bgEnRow.row);
                var bgOpRow = makeRow('Opacity');
                bgOpRow.ctrl.appendChild(makeOpacityInput(draft.fillOpacity !== undefined ? draft.fillOpacity : 0.05, function(v) { draft.fillOpacity = v; }));
                body.appendChild(bgOpRow.row);

            // ---- FLAT_CHANNEL ----
            } else if (d.type === 'flat_channel') {
                addSectionHeading('LINES');
                addLineRow(body);
                addWidthRow(body);
                addSectionHeading('BACKGROUND');
                var bgEnRow = makeRow('Background');
                bgEnRow.ctrl.appendChild(makeCheckbox(draft.fillEnabled !== false, function(v) { draft.fillEnabled = v; }));
                bgEnRow.ctrl.appendChild(makeColorSwatch(draft.fillColor || draft.color || _drawDefaults.color, function(c) { draft.fillColor = c; }));
                body.appendChild(bgEnRow.row);
                var bgOpRow = makeRow('Opacity');
                bgOpRow.ctrl.appendChild(makeOpacityInput(draft.fillOpacity !== undefined ? draft.fillOpacity : 0.08, function(v) { draft.fillOpacity = v; }));
                body.appendChild(bgOpRow.row);

            // ---- FIBONACCI ----
            } else if (d.type === 'fibonacci') {
                addSectionHeading('TREND LINE');
                addLineRow(body);
                addWidthRow(body);
                var extRow = makeRow('Extend');
                extRow.ctrl.appendChild(makeSelect(["Don't extend", 'Left', 'Right', 'Both'], draft.extend || "Don't extend", function(v) { draft.extend = v; }));
                body.appendChild(extRow.row);
                addSectionHeading('LEVELS');
                var fibLevels = draft.fibLevelValues || _FIB_LEVELS.slice();
                var fibColors = (draft.fibColors && draft.fibColors.length) ? draft.fibColors : _getFibColors();
                var fibEnabled = draft.fibEnabled || [];
                for (var fi = 0; fi < fibLevels.length; fi++) {
                    (function(idx) {
                        var fRow = makeRow('');
                        var enCb = makeCheckbox(fibEnabled[idx] !== false, function(v) {
                            if (!draft.fibEnabled) draft.fibEnabled = fibLevels.map(function() { return true; });
                            draft.fibEnabled[idx] = v;
                        });
                        fRow.ctrl.appendChild(enCb);
                        var levelInp = document.createElement('input');
                        levelInp.type = 'number'; levelInp.step = '0.001';
                        levelInp.className = 'ts-input ts-input-sm';
                        levelInp.value = fibLevels[idx].toFixed(3);
                        levelInp.addEventListener('input', function() {
                            if (!draft.fibLevelValues) draft.fibLevelValues = fibLevels.slice();
                            draft.fibLevelValues[idx] = parseFloat(levelInp.value) || 0;
                        });
                        levelInp.addEventListener('keydown', function(e) { e.stopPropagation(); });
                        fRow.ctrl.appendChild(levelInp);
                        fRow.ctrl.appendChild(makeColorSwatch(fibColors[idx] || _drawDefaults.color, function(c) {
                            if (!draft.fibColors) draft.fibColors = fibColors.slice();
                            draft.fibColors[idx] = c;
                        }));
                        body.appendChild(fRow.row);
                    })(fi);
                }

            // ---- FIB EXTENSION ----
            } else if (d.type === 'fib_extension') {
                addSectionHeading('TREND LINE');
                addLineRow(body);
                addWidthRow(body);
                var extRow = makeRow('Extend');
                extRow.ctrl.appendChild(makeSelect(["Don't extend", 'Left', 'Right', 'Both'], draft.extend || "Don't extend", function(v) { draft.extend = v; }));
                body.appendChild(extRow.row);
                addSectionHeading('LEVELS');
                var extDefLevels = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1, 1.618, 2.618, 4.236];
                var fibLevels = (draft.fibLevelValues && draft.fibLevelValues.length) ? draft.fibLevelValues : extDefLevels;
                var fibColors = (draft.fibColors && draft.fibColors.length) ? draft.fibColors : _getFibColors();
                var fibEnabled = draft.fibEnabled || [];
                for (var fi = 0; fi < fibLevels.length; fi++) {
                    (function(idx) {
                        var fRow = makeRow('');
                        var enCb = makeCheckbox(fibEnabled[idx] !== false, function(v) {
                            if (!draft.fibEnabled) draft.fibEnabled = fibLevels.map(function() { return true; });
                            draft.fibEnabled[idx] = v;
                        });
                        fRow.ctrl.appendChild(enCb);
                        var levelInp = document.createElement('input');
                        levelInp.type = 'number'; levelInp.step = '0.001';
                        levelInp.className = 'ts-input ts-input-sm';
                        levelInp.value = fibLevels[idx].toFixed(3);
                        levelInp.addEventListener('input', function() {
                            if (!draft.fibLevelValues) draft.fibLevelValues = fibLevels.slice();
                            draft.fibLevelValues[idx] = parseFloat(levelInp.value) || 0;
                        });
                        levelInp.addEventListener('keydown', function(e) { e.stopPropagation(); });
                        fRow.ctrl.appendChild(levelInp);
                        fRow.ctrl.appendChild(makeColorSwatch(fibColors[idx % fibColors.length] || _drawDefaults.color, function(c) {
                            if (!draft.fibColors) draft.fibColors = fibColors.slice();
                            while (draft.fibColors.length <= idx) draft.fibColors.push(_drawDefaults.color);
                            draft.fibColors[idx] = c;
                        }));
                        body.appendChild(fRow.row);
                    })(fi);
                }
                addSectionHeading('BACKGROUND');
                var bgEnRow = makeRow('Background');
                bgEnRow.ctrl.appendChild(makeCheckbox(draft.fillEnabled !== false, function(v) { draft.fillEnabled = v; }));
                bgEnRow.ctrl.appendChild(makeColorSwatch(draft.fillColor || draft.color || _drawDefaults.color, function(c) { draft.fillColor = c; }));
                body.appendChild(bgEnRow.row);
                var bgOpRow = makeRow('Opacity');
                bgOpRow.ctrl.appendChild(makeOpacityInput(draft.fillOpacity !== undefined ? draft.fillOpacity : 0.06, function(v) { draft.fillOpacity = v; }));
                body.appendChild(bgOpRow.row);

            // ---- FIB CHANNEL ----
            } else if (d.type === 'fib_channel') {
                addSectionHeading('BORDER');
                addLineRow(body);
                addWidthRow(body);
                var extRow = makeRow('Extend');
                extRow.ctrl.appendChild(makeSelect(["Don't extend", 'Left', 'Right', 'Both'], draft.extend || "Don't extend", function(v) { draft.extend = v; }));
                body.appendChild(extRow.row);
                addSectionHeading('LEVELS');
                var fibLevels = draft.fibLevelValues || _FIB_LEVELS.slice();
                var fibColors = (draft.fibColors && draft.fibColors.length) ? draft.fibColors : _getFibColors();
                var fibEnabled = draft.fibEnabled || [];
                for (var fi = 0; fi < fibLevels.length; fi++) {
                    (function(idx) {
                        var fRow = makeRow('');
                        fRow.ctrl.appendChild(makeCheckbox(fibEnabled[idx] !== false, function(v) {
                            if (!draft.fibEnabled) draft.fibEnabled = fibLevels.map(function() { return true; });
                            draft.fibEnabled[idx] = v;
                        }));
                        var levelInp = document.createElement('input');
                        levelInp.type = 'number'; levelInp.step = '0.001';
                        levelInp.className = 'ts-input ts-input-sm';
                        levelInp.value = fibLevels[idx].toFixed(3);
                        levelInp.addEventListener('input', function() {
                            if (!draft.fibLevelValues) draft.fibLevelValues = fibLevels.slice();
                            draft.fibLevelValues[idx] = parseFloat(levelInp.value) || 0;
                        });
                        levelInp.addEventListener('keydown', function(e) { e.stopPropagation(); });
                        fRow.ctrl.appendChild(levelInp);
                        fRow.ctrl.appendChild(makeColorSwatch(fibColors[idx] || _drawDefaults.color, function(c) {
                            if (!draft.fibColors) draft.fibColors = fibColors.slice();
                            draft.fibColors[idx] = c;
                        }));
                        body.appendChild(fRow.row);
                    })(fi);
                }
                addSectionHeading('BACKGROUND');
                var bgEnRow = makeRow('Background');
                bgEnRow.ctrl.appendChild(makeCheckbox(draft.fillEnabled !== false, function(v) { draft.fillEnabled = v; }));
                bgEnRow.ctrl.appendChild(makeColorSwatch(draft.fillColor || draft.color || _drawDefaults.color, function(c) { draft.fillColor = c; }));
                body.appendChild(bgEnRow.row);
                var bgOpRow = makeRow('Opacity');
                bgOpRow.ctrl.appendChild(makeOpacityInput(draft.fillOpacity !== undefined ? draft.fillOpacity : 0.04, function(v) { draft.fillOpacity = v; }));
                body.appendChild(bgOpRow.row);

            // ---- FIB FAN ----
            } else if (d.type === 'fib_fan') {
                addSectionHeading('TREND LINE');
                addLineRow(body);
                addWidthRow(body);
                addSectionHeading('LEVELS');
                var fibLevels = draft.fibLevelValues || _FIB_LEVELS.slice();
                var fibColors = (draft.fibColors && draft.fibColors.length) ? draft.fibColors : _getFibColors();
                var fibEnabled = draft.fibEnabled || [];
                for (var fi = 0; fi < fibLevels.length; fi++) {
                    (function(idx) {
                        var fRow = makeRow('');
                        fRow.ctrl.appendChild(makeCheckbox(fibEnabled[idx] !== false, function(v) {
                            if (!draft.fibEnabled) draft.fibEnabled = fibLevels.map(function() { return true; });
                            draft.fibEnabled[idx] = v;
                        }));
                        var levelInp = document.createElement('input');
                        levelInp.type = 'number'; levelInp.step = '0.001';
                        levelInp.className = 'ts-input ts-input-sm';
                        levelInp.value = fibLevels[idx].toFixed(3);
                        levelInp.addEventListener('input', function() {
                            if (!draft.fibLevelValues) draft.fibLevelValues = fibLevels.slice();
                            draft.fibLevelValues[idx] = parseFloat(levelInp.value) || 0;
                        });
                        levelInp.addEventListener('keydown', function(e) { e.stopPropagation(); });
                        fRow.ctrl.appendChild(levelInp);
                        fRow.ctrl.appendChild(makeColorSwatch(fibColors[idx] || _drawDefaults.color, function(c) {
                            if (!draft.fibColors) draft.fibColors = fibColors.slice();
                            draft.fibColors[idx] = c;
                        }));
                        body.appendChild(fRow.row);
                    })(fi);
                }
                addSectionHeading('BACKGROUND');
                var bgEnRow = makeRow('Fill between fan lines');
                bgEnRow.ctrl.appendChild(makeCheckbox(draft.fillEnabled !== false, function(v) { draft.fillEnabled = v; }));
                body.appendChild(bgEnRow.row);
                var bgColRow = makeRow('Color');
                bgColRow.ctrl.appendChild(makeColorSwatch(draft.fillColor || draft.color || _drawDefaults.color, function(c) { draft.fillColor = c; }));
                body.appendChild(bgColRow.row);
                var bgOpRow = makeRow('Opacity');
                bgOpRow.ctrl.appendChild(makeOpacityInput(draft.fillOpacity !== undefined ? draft.fillOpacity : 0.03, function(v) { draft.fillOpacity = v; }));
                body.appendChild(bgOpRow.row);

            // ---- FIB ARC ----
            } else if (d.type === 'fib_arc') {
                addSectionHeading('TREND LINE');
                addLineRow(body);
                addWidthRow(body);
                var tlRow = makeRow('Show trend line');
                tlRow.ctrl.appendChild(makeCheckbox(draft.showTrendLine !== false, function(v) { draft.showTrendLine = v; }));
                body.appendChild(tlRow.row);
                addSectionHeading('LEVELS');
                var fibLevels = draft.fibLevelValues || _FIB_LEVELS.slice();
                var fibColors = (draft.fibColors && draft.fibColors.length) ? draft.fibColors : _getFibColors();
                var fibEnabled = draft.fibEnabled || [];
                for (var fi = 0; fi < fibLevels.length; fi++) {
                    (function(idx) {
                        var fRow = makeRow('');
                        fRow.ctrl.appendChild(makeCheckbox(fibEnabled[idx] !== false, function(v) {
                            if (!draft.fibEnabled) draft.fibEnabled = fibLevels.map(function() { return true; });
                            draft.fibEnabled[idx] = v;
                        }));
                        var levelInp = document.createElement('input');
                        levelInp.type = 'number'; levelInp.step = '0.001';
                        levelInp.className = 'ts-input ts-input-sm';
                        levelInp.value = fibLevels[idx].toFixed(3);
                        levelInp.addEventListener('input', function() {
                            if (!draft.fibLevelValues) draft.fibLevelValues = fibLevels.slice();
                            draft.fibLevelValues[idx] = parseFloat(levelInp.value) || 0;
                        });
                        levelInp.addEventListener('keydown', function(e) { e.stopPropagation(); });
                        fRow.ctrl.appendChild(levelInp);
                        fRow.ctrl.appendChild(makeColorSwatch(fibColors[idx] || _drawDefaults.color, function(c) {
                            if (!draft.fibColors) draft.fibColors = fibColors.slice();
                            draft.fibColors[idx] = c;
                        }));
                        body.appendChild(fRow.row);
                    })(fi);
                }

            // ---- FIB CIRCLE ----
            } else if (d.type === 'fib_circle') {
                addSectionHeading('TREND LINE');
                addLineRow(body);
                addWidthRow(body);
                var tlRow = makeRow('Show trend line');
                tlRow.ctrl.appendChild(makeCheckbox(draft.showTrendLine !== false, function(v) { draft.showTrendLine = v; }));
                body.appendChild(tlRow.row);
                addSectionHeading('LEVELS');
                var fibLevels = draft.fibLevelValues || _FIB_LEVELS.slice();
                var fibColors = (draft.fibColors && draft.fibColors.length) ? draft.fibColors : _getFibColors();
                var fibEnabled = draft.fibEnabled || [];
                for (var fi = 0; fi < fibLevels.length; fi++) {
                    (function(idx) {
                        var fRow = makeRow('');
                        fRow.ctrl.appendChild(makeCheckbox(fibEnabled[idx] !== false, function(v) {
                            if (!draft.fibEnabled) draft.fibEnabled = fibLevels.map(function() { return true; });
                            draft.fibEnabled[idx] = v;
                        }));
                        var levelInp = document.createElement('input');
                        levelInp.type = 'number'; levelInp.step = '0.001';
                        levelInp.className = 'ts-input ts-input-sm';
                        levelInp.value = fibLevels[idx].toFixed(3);
                        levelInp.addEventListener('input', function() {
                            if (!draft.fibLevelValues) draft.fibLevelValues = fibLevels.slice();
                            draft.fibLevelValues[idx] = parseFloat(levelInp.value) || 0;
                        });
                        levelInp.addEventListener('keydown', function(e) { e.stopPropagation(); });
                        fRow.ctrl.appendChild(levelInp);
                        fRow.ctrl.appendChild(makeColorSwatch(fibColors[idx] || _drawDefaults.color, function(c) {
                            if (!draft.fibColors) draft.fibColors = fibColors.slice();
                            draft.fibColors[idx] = c;
                        }));
                        body.appendChild(fRow.row);
                    })(fi);
                }

            // ---- FIB WEDGE ----
            } else if (d.type === 'fib_wedge') {
                addSectionHeading('LINE');
                addLineRow(body);
                addWidthRow(body);
                addSectionHeading('LEVELS');
                var fibLevels = draft.fibLevelValues || _FIB_LEVELS.slice();
                var fibColors = (draft.fibColors && draft.fibColors.length) ? draft.fibColors : _getFibColors();
                var fibEnabled = draft.fibEnabled || [];
                for (var fi = 0; fi < fibLevels.length; fi++) {
                    (function(idx) {
                        var fRow = makeRow('');
                        fRow.ctrl.appendChild(makeCheckbox(fibEnabled[idx] !== false, function(v) {
                            if (!draft.fibEnabled) draft.fibEnabled = fibLevels.map(function() { return true; });
                            draft.fibEnabled[idx] = v;
                        }));
                        var levelInp = document.createElement('input');
                        levelInp.type = 'number'; levelInp.step = '0.001';
                        levelInp.className = 'ts-input ts-input-sm';
                        levelInp.value = fibLevels[idx].toFixed(3);
                        levelInp.addEventListener('input', function() {
                            if (!draft.fibLevelValues) draft.fibLevelValues = fibLevels.slice();
                            draft.fibLevelValues[idx] = parseFloat(levelInp.value) || 0;
                        });
                        levelInp.addEventListener('keydown', function(e) { e.stopPropagation(); });
                        fRow.ctrl.appendChild(levelInp);
                        fRow.ctrl.appendChild(makeColorSwatch(fibColors[idx] || _drawDefaults.color, function(c) {
                            if (!draft.fibColors) draft.fibColors = fibColors.slice();
                            draft.fibColors[idx] = c;
                        }));
                        body.appendChild(fRow.row);
                    })(fi);
                }
                addSectionHeading('BACKGROUND');
                var bgEnRow = makeRow('Background');
                bgEnRow.ctrl.appendChild(makeCheckbox(draft.fillEnabled !== false, function(v) { draft.fillEnabled = v; }));
                bgEnRow.ctrl.appendChild(makeColorSwatch(draft.fillColor || draft.color || _drawDefaults.color, function(c) { draft.fillColor = c; }));
                body.appendChild(bgEnRow.row);
                var bgOpRow = makeRow('Opacity');
                bgOpRow.ctrl.appendChild(makeOpacityInput(draft.fillOpacity !== undefined ? draft.fillOpacity : 0.04, function(v) { draft.fillOpacity = v; }));
                body.appendChild(bgOpRow.row);

            // ---- PITCHFAN ----
            } else if (d.type === 'pitchfan') {
                addSectionHeading('LINES');
                addLineRow(body);
                addWidthRow(body);
                addSectionHeading('MEDIAN');
                var medRow = makeRow('Show median');
                medRow.ctrl.appendChild(makeCheckbox(draft.showMedian !== false, function(v) { draft.showMedian = v; }));
                body.appendChild(medRow.row);
                var medColorRow = makeRow('Median color');
                medColorRow.ctrl.appendChild(makeColorSwatch(draft.medianColor || draft.color || _drawDefaults.color, function(c) { draft.medianColor = c; }));
                body.appendChild(medColorRow.row);
                addSectionHeading('FAN LEVELS');
                var pfLevels = [0.236, 0.382, 0.5, 0.618, 0.786];
                var fibLevels = (draft.fibLevelValues && draft.fibLevelValues.length) ? draft.fibLevelValues : pfLevels;
                var fibColors = (draft.fibColors && draft.fibColors.length) ? draft.fibColors : _getFibColors();
                var fibEnabled = draft.fibEnabled || [];
                for (var fi = 0; fi < fibLevels.length; fi++) {
                    (function(idx) {
                        var fRow = makeRow('');
                        fRow.ctrl.appendChild(makeCheckbox(fibEnabled[idx] !== false, function(v) {
                            if (!draft.fibEnabled) draft.fibEnabled = fibLevels.map(function() { return true; });
                            draft.fibEnabled[idx] = v;
                        }));
                        var levelInp = document.createElement('input');
                        levelInp.type = 'number'; levelInp.step = '0.001';
                        levelInp.className = 'ts-input ts-input-sm';
                        levelInp.value = fibLevels[idx].toFixed(3);
                        levelInp.addEventListener('input', function() {
                            if (!draft.fibLevelValues) draft.fibLevelValues = fibLevels.slice();
                            draft.fibLevelValues[idx] = parseFloat(levelInp.value) || 0;
                        });
                        levelInp.addEventListener('keydown', function(e) { e.stopPropagation(); });
                        fRow.ctrl.appendChild(levelInp);
                        fRow.ctrl.appendChild(makeColorSwatch(fibColors[idx] || _drawDefaults.color, function(c) {
                            if (!draft.fibColors) draft.fibColors = fibColors.slice();
                            draft.fibColors[idx] = c;
                        }));
                        body.appendChild(fRow.row);
                    })(fi);
                }

            // ---- FIB TIME ZONE ----
            } else if (d.type === 'fib_timezone') {
                addSectionHeading('TREND LINE');
                addLineRow(body);
                addWidthRow(body);
                var tlRow = makeRow('Show trend line');
                tlRow.ctrl.appendChild(makeCheckbox(draft.showTrendLine !== false, function(v) { draft.showTrendLine = v; }));
                body.appendChild(tlRow.row);
                addSectionHeading('TIME ZONE LINES');
                var tzNums = [0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144];
                var tzColors = (draft.fibColors && draft.fibColors.length) ? draft.fibColors : _getFibColors();
                var tzEnabled = draft.fibEnabled || [];
                for (var fi = 0; fi < tzNums.length; fi++) {
                    (function(idx) {
                        var fRow = makeRow(String(tzNums[idx]));
                        fRow.ctrl.appendChild(makeCheckbox(tzEnabled[idx] !== false, function(v) {
                            if (!draft.fibEnabled) draft.fibEnabled = tzNums.map(function() { return true; });
                            draft.fibEnabled[idx] = v;
                        }));
                        fRow.ctrl.appendChild(makeColorSwatch(tzColors[idx % tzColors.length] || _drawDefaults.color, function(c) {
                            if (!draft.fibColors) {
                                draft.fibColors = [];
                                for (var ci = 0; ci < tzNums.length; ci++) draft.fibColors.push(tzColors[ci % tzColors.length] || _drawDefaults.color);
                            }
                            draft.fibColors[idx] = c;
                        }));
                        body.appendChild(fRow.row);
                    })(fi);
                }

            // ---- MEASURE ----
            } else if (d.type === 'fib_time') {
                addSectionHeading('TREND LINE');
                addLineRow(body);
                addWidthRow(body);
                addSectionHeading('LEVELS');
                var ftDefLevels = [0, 0.382, 0.5, 0.618, 1, 1.382, 1.618, 2, 2.618, 4.236];
                var ftLevels = (draft.fibLevelValues && draft.fibLevelValues.length) ? draft.fibLevelValues : ftDefLevels;
                var ftColors = (draft.fibColors && draft.fibColors.length) ? draft.fibColors : _getFibColors();
                var ftEnabled = draft.fibEnabled || [];
                for (var fi = 0; fi < ftLevels.length; fi++) {
                    (function(idx) {
                        var fRow = makeRow(ftLevels[idx].toFixed(3));
                        fRow.ctrl.appendChild(makeCheckbox(ftEnabled[idx] !== false, function(v) {
                            if (!draft.fibEnabled) draft.fibEnabled = ftLevels.map(function() { return true; });
                            draft.fibEnabled[idx] = v;
                        }));
                        fRow.ctrl.appendChild(makeColorSwatch(ftColors[idx % ftColors.length] || _drawDefaults.color, function(c) {
                            if (!draft.fibColors) {
                                draft.fibColors = [];
                                for (var ci = 0; ci < ftLevels.length; ci++) draft.fibColors.push(ftColors[ci % ftColors.length] || _drawDefaults.color);
                            }
                            draft.fibColors[idx] = c;
                        }));
                        body.appendChild(fRow.row);
                    })(fi);
                }

            // ---- FIB SPIRAL ----
            } else if (d.type === 'fib_spiral') {
                addSectionHeading('LINE');
                addLineRow(body);
                addWidthRow(body);

            // ---- GANN BOX ----
            } else if (d.type === 'gann_box') {
                addSectionHeading('BORDER');
                addLineRow(body);
                addWidthRow(body);
                addSectionHeading('LEVELS');
                var gbDefLevels = [0.25, 0.5, 0.75];
                var gbLevels = draft.gannLevels || gbDefLevels;
                var gbColors = (draft.fibColors && draft.fibColors.length) ? draft.fibColors : [];
                var gbEnabled = draft.fibEnabled || [];
                for (var gi = 0; gi < gbLevels.length; gi++) {
                    (function(idx) {
                        var gRow = makeRow(gbLevels[idx].toFixed(3));
                        gRow.ctrl.appendChild(makeCheckbox(gbEnabled[idx] !== false, function(v) {
                            if (!draft.fibEnabled) draft.fibEnabled = gbLevels.map(function() { return true; });
                            draft.fibEnabled[idx] = v;
                        }));
                        gRow.ctrl.appendChild(makeColorSwatch(gbColors[idx] || _drawDefaults.color, function(c) {
                            if (!draft.fibColors) { draft.fibColors = []; for (var ci = 0; ci < gbLevels.length; ci++) draft.fibColors.push(_drawDefaults.color); }
                            draft.fibColors[idx] = c;
                        }));
                        body.appendChild(gRow.row);
                    })(gi);
                }
                addSectionHeading('BACKGROUND');
                var fillRow = makeRow('Fill');
                fillRow.ctrl.appendChild(makeCheckbox(draft.fillEnabled !== false, function(v) { draft.fillEnabled = v; }));
                body.appendChild(fillRow.row);
                var bgColRow = makeRow('Color');
                bgColRow.ctrl.appendChild(makeColorSwatch(draft.fillColor || draft.color || _drawDefaults.color, function(c) { draft.fillColor = c; }));
                body.appendChild(bgColRow.row);
                var opRow = makeRow('Opacity');
                opRow.ctrl.appendChild(makeOpacityInput(draft.fillOpacity !== undefined ? draft.fillOpacity : 0.03, function(v) { draft.fillOpacity = v; }));
                body.appendChild(opRow.row);

            // ---- GANN SQUARE FIXED ----
            } else if (d.type === 'gann_square_fixed') {
                addSectionHeading('BORDER');
                addLineRow(body);
                addWidthRow(body);
                addSectionHeading('LEVELS');
                var gsfDefLevels = [0.25, 0.5, 0.75];
                var gsfLevels = draft.gannLevels || gsfDefLevels;
                var gsfColors = (draft.fibColors && draft.fibColors.length) ? draft.fibColors : [];
                var gsfEnabled = draft.fibEnabled || [];
                for (var gi = 0; gi < gsfLevels.length; gi++) {
                    (function(idx) {
                        var gRow = makeRow(gsfLevels[idx].toFixed(3));
                        gRow.ctrl.appendChild(makeCheckbox(gsfEnabled[idx] !== false, function(v) {
                            if (!draft.fibEnabled) draft.fibEnabled = gsfLevels.map(function() { return true; });
                            draft.fibEnabled[idx] = v;
                        }));
                        gRow.ctrl.appendChild(makeColorSwatch(gsfColors[idx] || _drawDefaults.color, function(c) {
                            if (!draft.fibColors) { draft.fibColors = []; for (var ci = 0; ci < gsfLevels.length; ci++) draft.fibColors.push(_drawDefaults.color); }
                            draft.fibColors[idx] = c;
                        }));
                        body.appendChild(gRow.row);
                    })(gi);
                }
                addSectionHeading('BACKGROUND');
                var fillRow = makeRow('Fill');
                fillRow.ctrl.appendChild(makeCheckbox(draft.fillEnabled !== false, function(v) { draft.fillEnabled = v; }));
                body.appendChild(fillRow.row);
                var bgColRow = makeRow('Color');
                bgColRow.ctrl.appendChild(makeColorSwatch(draft.fillColor || draft.color || _drawDefaults.color, function(c) { draft.fillColor = c; }));
                body.appendChild(bgColRow.row);
                var opRow = makeRow('Opacity');
                opRow.ctrl.appendChild(makeOpacityInput(draft.fillOpacity !== undefined ? draft.fillOpacity : 0.03, function(v) { draft.fillOpacity = v; }));
                body.appendChild(opRow.row);

            // ---- GANN SQUARE ----
            } else if (d.type === 'gann_square') {
                addSectionHeading('BORDER');
                addLineRow(body);
                addWidthRow(body);
                addSectionHeading('LEVELS');
                var gsDefLevels = [0.25, 0.5, 0.75];
                var gsLevels = draft.gannLevels || gsDefLevels;
                var gsColors = (draft.fibColors && draft.fibColors.length) ? draft.fibColors : [];
                var gsEnabled = draft.fibEnabled || [];
                for (var gi = 0; gi < gsLevels.length; gi++) {
                    (function(idx) {
                        var gRow = makeRow(gsLevels[idx].toFixed(3));
                        gRow.ctrl.appendChild(makeCheckbox(gsEnabled[idx] !== false, function(v) {
                            if (!draft.fibEnabled) draft.fibEnabled = gsLevels.map(function() { return true; });
                            draft.fibEnabled[idx] = v;
                        }));
                        gRow.ctrl.appendChild(makeColorSwatch(gsColors[idx] || _drawDefaults.color, function(c) {
                            if (!draft.fibColors) { draft.fibColors = []; for (var ci = 0; ci < gsLevels.length; ci++) draft.fibColors.push(_drawDefaults.color); }
                            draft.fibColors[idx] = c;
                        }));
                        body.appendChild(gRow.row);
                    })(gi);
                }
                addSectionHeading('BACKGROUND');
                var fillRow = makeRow('Fill');
                fillRow.ctrl.appendChild(makeCheckbox(draft.fillEnabled !== false, function(v) { draft.fillEnabled = v; }));
                body.appendChild(fillRow.row);
                var bgColRow = makeRow('Color');
                bgColRow.ctrl.appendChild(makeColorSwatch(draft.fillColor || draft.color || _drawDefaults.color, function(c) { draft.fillColor = c; }));
                body.appendChild(bgColRow.row);
                var opRow = makeRow('Opacity');
                opRow.ctrl.appendChild(makeOpacityInput(draft.fillOpacity !== undefined ? draft.fillOpacity : 0.03, function(v) { draft.fillOpacity = v; }));
                body.appendChild(opRow.row);

            // ---- GANN FAN ----
            } else if (d.type === 'gann_fan') {
                addSectionHeading('LINES');
                addLineRow(body);
                addWidthRow(body);
                addSectionHeading('FAN LEVELS');
                var gfAngleNames = ['1\u00d78', '1\u00d74', '1\u00d73', '1\u00d72', '1\u00d71', '2\u00d71', '3\u00d71', '4\u00d71', '8\u00d71'];
                var gfColors = (draft.fibColors && draft.fibColors.length) ? draft.fibColors : [];
                var gfEnabled = draft.fibEnabled || [];
                for (var gi = 0; gi < gfAngleNames.length; gi++) {
                    (function(idx) {
                        var gRow = makeRow(gfAngleNames[idx]);
                        gRow.ctrl.appendChild(makeCheckbox(gfEnabled[idx] !== false, function(v) {
                            if (!draft.fibEnabled) draft.fibEnabled = gfAngleNames.map(function() { return true; });
                            draft.fibEnabled[idx] = v;
                        }));
                        gRow.ctrl.appendChild(makeColorSwatch(gfColors[idx] || _drawDefaults.color, function(c) {
                            if (!draft.fibColors) { draft.fibColors = []; for (var ci = 0; ci < gfAngleNames.length; ci++) draft.fibColors.push(_drawDefaults.color); }
                            draft.fibColors[idx] = c;
                        }));
                        body.appendChild(gRow.row);
                    })(gi);
                }

            // ---- MEASURE ----
            } else if (d.type === 'measure') {
                addSectionHeading('COLORS');
                var upRow = makeRow('Up color');
                upRow.ctrl.appendChild(makeColorSwatch(draft.colorUp || _cssVar('--pywry-draw-measure-up', '#26a69a'), function(c) { draft.colorUp = c; }));
                body.appendChild(upRow.row);
                var dnRow = makeRow('Down color');
                dnRow.ctrl.appendChild(makeColorSwatch(draft.colorDown || _cssVar('--pywry-draw-measure-down', '#ef5350'), function(c) { draft.colorDown = c; }));
                body.appendChild(dnRow.row);
                var bgOpRow = makeRow('Opacity');
                bgOpRow.ctrl.appendChild(makeOpacityInput(draft.fillOpacity !== undefined ? draft.fillOpacity : 0.08, function(v) { draft.fillOpacity = v; }));
                body.appendChild(bgOpRow.row);
                addSectionHeading('LABEL');
                var mFsRow = makeRow('Font size');
                mFsRow.ctrl.appendChild(makeSelect([{value:10,label:'10'},{value:11,label:'11'},{value:12,label:'12'},{value:13,label:'13'},{value:14,label:'14'},{value:16,label:'16'}], draft.fontSize || 12, function(v) { draft.fontSize = parseInt(v); }));
                body.appendChild(mFsRow.row);

            // ---- TEXT ----
            } else if (d.type === 'text') {
                addSectionHeading('TEXT');
                var tColorRow = makeRow('Color');
                tColorRow.ctrl.appendChild(makeColorSwatch(draft.color || _drawDefaults.color, function(c) { draft.color = c; }));
                body.appendChild(tColorRow.row);
                var fsRow = makeRow('Font size');
                fsRow.ctrl.appendChild(makeSelect([{value:10,label:'10'},{value:12,label:'12'},{value:14,label:'14'},{value:16,label:'16'},{value:18,label:'18'},{value:20,label:'20'},{value:24,label:'24'},{value:28,label:'28'}], draft.fontSize || 14, function(v) { draft.fontSize = parseInt(v); }));
                body.appendChild(fsRow.row);
                var boldRow = makeRow('Bold');
                boldRow.ctrl.appendChild(makeCheckbox(!!draft.bold, function(v) { draft.bold = v; }));
                body.appendChild(boldRow.row);
                var italicRow = makeRow('Italic');
                italicRow.ctrl.appendChild(makeCheckbox(!!draft.italic, function(v) { draft.italic = v; }));
                body.appendChild(italicRow.row);
                addSectionHeading('BACKGROUND');
                var bgEnRow = makeRow('Background');
                bgEnRow.ctrl.appendChild(makeCheckbox(!!draft.bgEnabled, function(v) { draft.bgEnabled = v; }));
                bgEnRow.ctrl.appendChild(makeColorSwatch(draft.bgColor || '#2a2e39', function(c) { draft.bgColor = c; }));
                body.appendChild(bgEnRow.row);
                var bgOpRow = makeRow('Opacity');
                bgOpRow.ctrl.appendChild(makeOpacityInput(draft.bgOpacity !== undefined ? draft.bgOpacity : 0.7, function(v) { draft.bgOpacity = v; }));
                body.appendChild(bgOpRow.row);

            // ---- BRUSH ----
            } else if (d.type === 'brush') {
                addSectionHeading('BRUSH');
                var cRow = makeRow('Color');
                cRow.ctrl.appendChild(makeColorSwatch(draft.color || _drawDefaults.color, function(c) { draft.color = c; }));
                body.appendChild(cRow.row);
                var wRow = makeRow('Width');
                wRow.ctrl.appendChild(makeSelect([{value:1,label:'1px'},{value:2,label:'2px'},{value:3,label:'3px'},{value:4,label:'4px'},{value:5,label:'5px'},{value:8,label:'8px'},{value:12,label:'12px'}], draft.lineWidth || 2, function(v) { draft.lineWidth = parseInt(v); }));
                body.appendChild(wRow.row);
                var opRow = makeRow('Opacity');
                opRow.ctrl.appendChild(makeOpacityInput(draft.opacity !== undefined ? draft.opacity : 1.0, function(v) { draft.opacity = v; }));
                body.appendChild(opRow.row);

            // ---- HIGHLIGHTER ----
            } else if (d.type === 'highlighter') {
                addSectionHeading('HIGHLIGHTER');
                var cRow = makeRow('Color');
                cRow.ctrl.appendChild(makeColorSwatch(draft.color || '#FFEB3B', function(c) { draft.color = c; }));
                body.appendChild(cRow.row);
                var wRow = makeRow('Width');
                wRow.ctrl.appendChild(makeSelect([{value:5,label:'5px'},{value:8,label:'8px'},{value:10,label:'10px'},{value:15,label:'15px'},{value:20,label:'20px'}], draft.lineWidth || 10, function(v) { draft.lineWidth = parseInt(v); }));
                body.appendChild(wRow.row);
                var opRow = makeRow('Opacity');
                opRow.ctrl.appendChild(makeOpacityInput(draft.opacity !== undefined ? draft.opacity : 0.4, function(v) { draft.opacity = v; }));
                body.appendChild(opRow.row);

            // ---- ARROW MARKER (filled shape) ----
            } else if (d.type === 'arrow_marker') {
                addSectionHeading('FILL');
                var fRow = makeRow('Fill color');
                fRow.ctrl.appendChild(makeColorSwatch(draft.fillColor || draft.color || _drawDefaults.color, function(c) { draft.fillColor = c; }));
                body.appendChild(fRow.row);
                addSectionHeading('BORDER');
                var brdRow = makeRow('Border color');
                brdRow.ctrl.appendChild(makeColorSwatch(draft.borderColor || draft.color || _drawDefaults.color, function(c) { draft.borderColor = c; }));
                body.appendChild(brdRow.row);
                addSectionHeading('TEXT');
                var tcRow = makeRow('Text color');
                tcRow.ctrl.appendChild(makeColorSwatch(draft.textColor || draft.color || _drawDefaults.color, function(c) { draft.textColor = c; }));
                body.appendChild(tcRow.row);
                var fsRow = makeRow('Font size');
                fsRow.ctrl.appendChild(makeSelect([{value:10,label:'10'},{value:12,label:'12'},{value:14,label:'14'},{value:16,label:'16'},{value:18,label:'18'},{value:20,label:'20'},{value:24,label:'24'},{value:30,label:'30'}], draft.fontSize || 16, function(v) { draft.fontSize = parseInt(v); }));
                body.appendChild(fsRow.row);
                var bRow = makeRow('Bold');
                bRow.ctrl.appendChild(makeCheckbox(!!draft.bold, function(v) { draft.bold = v; }));
                body.appendChild(bRow.row);
                var iRow = makeRow('Italic');
                iRow.ctrl.appendChild(makeCheckbox(!!draft.italic, function(v) { draft.italic = v; }));
                body.appendChild(iRow.row);

            // ---- ARROW (line with arrowhead) ----
            } else if (d.type === 'arrow') {
                addSectionHeading('LINE');
                addLineRow(body);
                addWidthRow(body);
                var styRow = makeRow('Line style');
                styRow.ctrl.appendChild(makeSelect([{value:0,label:'Solid'},{value:1,label:'Dashed'},{value:2,label:'Dotted'}], draft.lineStyle || 0, function(v) { draft.lineStyle = parseInt(v); }));
                body.appendChild(styRow.row);

            // ---- ARROW MARKS (up/down/left/right) ----
            } else if (d.type === 'arrow_mark_up' || d.type === 'arrow_mark_down' || d.type === 'arrow_mark_left' || d.type === 'arrow_mark_right') {
                addSectionHeading('FILL');
                var fRow = makeRow('Fill color');
                fRow.ctrl.appendChild(makeColorSwatch(draft.fillColor || draft.color || _drawDefaults.color, function(c) { draft.fillColor = c; }));
                body.appendChild(fRow.row);
                addSectionHeading('BORDER');
                var brdRow = makeRow('Border color');
                brdRow.ctrl.appendChild(makeColorSwatch(draft.borderColor || draft.color || _drawDefaults.color, function(c) { draft.borderColor = c; }));
                body.appendChild(brdRow.row);
                addSectionHeading('TEXT');
                var tcRow = makeRow('Text color');
                tcRow.ctrl.appendChild(makeColorSwatch(draft.textColor || draft.color || _drawDefaults.color, function(c) { draft.textColor = c; }));
                body.appendChild(tcRow.row);
                var fsRow = makeRow('Font size');
                fsRow.ctrl.appendChild(makeSelect([{value:10,label:'10'},{value:12,label:'12'},{value:14,label:'14'},{value:16,label:'16'},{value:18,label:'18'},{value:20,label:'20'},{value:24,label:'24'},{value:30,label:'30'}], draft.fontSize || 16, function(v) { draft.fontSize = parseInt(v); }));
                body.appendChild(fsRow.row);
                var bRow = makeRow('Bold');
                bRow.ctrl.appendChild(makeCheckbox(!!draft.bold, function(v) { draft.bold = v; }));
                body.appendChild(bRow.row);
                var iRow = makeRow('Italic');
                iRow.ctrl.appendChild(makeCheckbox(!!draft.italic, function(v) { draft.italic = v; }));
                body.appendChild(iRow.row);

            // ---- TEXT/NOTES TOOLS (anchored_text, note, price_note, pin, callout, comment, price_label, signpost, flag_mark) ----
            } else if (['anchored_text', 'note', 'price_note', 'pin', 'callout', 'comment', 'price_label', 'signpost', 'flag_mark'].indexOf(d.type) !== -1) {
                // Pin, flag_mark, signpost: Style tab has only the marker color
                // Other text tools: Style tab has color, font, bold, italic, bg, border
                var _hoverTextTools = ['pin', 'flag_mark', 'signpost'];
                if (_hoverTextTools.indexOf(d.type) !== -1) {
                    addSectionHeading('MARKER');
                    var cRow = makeRow('Color');
                    cRow.ctrl.appendChild(makeColorSwatch(draft.markerColor || draft.color || _drawDefaults.color, function(c) { draft.markerColor = c; }));
                    body.appendChild(cRow.row);
                } else {
                    addSectionHeading('STYLE');
                    var cRow = makeRow('Color');
                    cRow.ctrl.appendChild(makeColorSwatch(draft.color || _drawDefaults.color, function(c) { draft.color = c; }));
                    body.appendChild(cRow.row);
                    var fsRow = makeRow('Font size');
                    fsRow.ctrl.appendChild(makeSelect([{value:10,label:'10'},{value:12,label:'12'},{value:14,label:'14'},{value:16,label:'16'},{value:18,label:'18'},{value:20,label:'20'},{value:24,label:'24'},{value:28,label:'28'}], draft.fontSize || 14, function(v) { draft.fontSize = parseInt(v); }));
                    body.appendChild(fsRow.row);
                    var bRow = makeRow('Bold');
                    bRow.ctrl.appendChild(makeCheckbox(!!draft.bold, function(v) { draft.bold = v; }));
                    body.appendChild(bRow.row);
                    var iRow = makeRow('Italic');
                    iRow.ctrl.appendChild(makeCheckbox(!!draft.italic, function(v) { draft.italic = v; }));
                    body.appendChild(iRow.row);
                    addSectionHeading('BACKGROUND');
                    var bgRow = makeRow('Background');
                    bgRow.ctrl.appendChild(makeCheckbox(draft.bgEnabled !== false, function(v) { draft.bgEnabled = v; }));
                    bgRow.ctrl.appendChild(makeColorSwatch(draft.bgColor || '#2a2e39', function(c) { draft.bgColor = c; }));
                    body.appendChild(bgRow.row);
                    var bdRow = makeRow('Border');
                    bdRow.ctrl.appendChild(makeCheckbox(!!draft.borderEnabled, function(v) { draft.borderEnabled = v; }));
                    bdRow.ctrl.appendChild(makeColorSwatch(draft.borderColor || draft.color || _drawDefaults.color, function(c) { draft.borderColor = c; }));
                    body.appendChild(bdRow.row);
                }

            // ---- CIRCLE / ELLIPSE ----
            } else if (d.type === 'circle' || d.type === 'ellipse') {
                addSectionHeading('BORDER');
                addLineRow(body);
                addWidthRow(body);
                addSectionHeading('BACKGROUND');
                var fillRow = makeRow('Fill');
                fillRow.ctrl.appendChild(makeCheckbox(!!draft.fillColor, function(v) { draft.fillColor = v ? (draft.fillColor || 'rgba(41,98,255,0.2)') : ''; }));
                fillRow.ctrl.appendChild(makeColorSwatch(draft.fillColor || 'rgba(41,98,255,0.2)', function(c) { draft.fillColor = c; }));
                body.appendChild(fillRow.row);

            // ---- TRIANGLE / ROTATED RECT ----
            } else if (d.type === 'triangle' || d.type === 'rotated_rect') {
                addSectionHeading('BORDER');
                addLineRow(body);
                addWidthRow(body);
                addSectionHeading('BACKGROUND');
                var fillRow = makeRow('Fill');
                fillRow.ctrl.appendChild(makeCheckbox(!!draft.fillColor, function(v) { draft.fillColor = v ? (draft.fillColor || 'rgba(41,98,255,0.2)') : ''; }));
                fillRow.ctrl.appendChild(makeColorSwatch(draft.fillColor || 'rgba(41,98,255,0.2)', function(c) { draft.fillColor = c; }));
                body.appendChild(fillRow.row);

            // ---- PATH / POLYLINE ----
            } else if (d.type === 'path' || d.type === 'polyline') {
                addSectionHeading('LINE');
                addLineRow(body);
                addWidthRow(body);
                if (d.type === 'path') {
                    addSectionHeading('BACKGROUND');
                    var fillRow = makeRow('Fill');
                    fillRow.ctrl.appendChild(makeCheckbox(!!draft.fillColor, function(v) { draft.fillColor = v ? (draft.fillColor || 'rgba(41,98,255,0.2)') : ''; }));
                    fillRow.ctrl.appendChild(makeColorSwatch(draft.fillColor || 'rgba(41,98,255,0.2)', function(c) { draft.fillColor = c; }));
                    body.appendChild(fillRow.row);
                }

            // ---- ARC / CURVE / DOUBLE CURVE ----
            } else if (d.type === 'shape_arc' || d.type === 'curve' || d.type === 'double_curve') {
                addSectionHeading('LINE');
                addLineRow(body);
                addWidthRow(body);

            // ---- LONG / SHORT POSITION ----
            } else if (d.type === 'long_position' || d.type === 'short_position') {
                addSectionHeading('COLORS');
                var profRow = makeRow('Profit color');
                profRow.ctrl.appendChild(makeColorSwatch(draft.profitColor || '#26a69a', function(c) { draft.profitColor = c; }));
                body.appendChild(profRow.row);
                var lossRow = makeRow('Stop color');
                lossRow.ctrl.appendChild(makeColorSwatch(draft.stopColor || '#ef5350', function(c) { draft.stopColor = c; }));
                body.appendChild(lossRow.row);
                addSectionHeading('LINE');
                addLineRow(body);
                addWidthRow(body);

            // ---- FORECAST / GHOST FEED ----
            } else if (d.type === 'forecast' || d.type === 'ghost_feed') {
                addSectionHeading('LINE');
                addLineRow(body);
                addWidthRow(body);

            // ---- BARS PATTERN / PROJECTION ----
            } else if (d.type === 'bars_pattern' || d.type === 'projection') {
                addSectionHeading('LINE');
                addLineRow(body);
                addWidthRow(body);

            // ---- ANCHORED VWAP ----
            } else if (d.type === 'anchored_vwap') {
                addSectionHeading('LINE');
                addLineRow(body);
                addWidthRow(body);

            // ---- FIXED RANGE VOLUME ----
            } else if (d.type === 'fixed_range_vol') {
                addSectionHeading('LINE');
                addLineRow(body);
                addWidthRow(body);

            // ---- PRICE RANGE / DATE RANGE / DATE+PRICE RANGE ----
            } else if (d.type === 'price_range' || d.type === 'date_range' || d.type === 'date_price_range') {
                addSectionHeading('LINE');
                addLineRow(body);
                addWidthRow(body);
                if (d.type === 'date_price_range') {
                    addSectionHeading('BACKGROUND');
                    var fillRow = makeRow('Fill');
                    fillRow.ctrl.appendChild(makeColorSwatch(draft.fillColor || 'rgba(41,98,255,0.1)', function(c) { draft.fillColor = c; }));
                    body.appendChild(fillRow.row);
                }

            // ---- FALLBACK (any unknown type) ----
            } else {
                addSectionHeading('LINE');
                addLineRow(body);
                addWidthRow(body);
            }

        } else if (activeTab === 'Text' && d.type === 'text') {
            addSectionHeading('CONTENT');
            var tRow = makeRow('Text');
            tRow.ctrl.appendChild(makeTextInput(draft.text || '', function(v) { draft.text = v; }));
            body.appendChild(tRow.row);

        } else if (activeTab === 'Text' && (d.type === 'trendline' || d.type === 'ray' || d.type === 'extended_line')) {
            addSectionHeading('TEXT');
            var tRow = makeRow('Text');
            tRow.ctrl.appendChild(makeTextInput(draft.text || '', function(v) { draft.text = v; }));
            body.appendChild(tRow.row);
            var tColorRow = makeRow('Text color');
            tColorRow.ctrl.appendChild(makeColorSwatch(draft.textColor || draft.color || _drawDefaults.color, function(c) { draft.textColor = c; }));
            body.appendChild(tColorRow.row);
            var tSizeRow = makeRow('Font size');
            tSizeRow.ctrl.appendChild(makeSelect([{value:10,label:'10'},{value:12,label:'12'},{value:14,label:'14'},{value:16,label:'16'},{value:18,label:'18'},{value:20,label:'20'},{value:24,label:'24'}], draft.textFontSize || 12, function(v) { draft.textFontSize = parseInt(v); }));
            body.appendChild(tSizeRow.row);
            var tBoldRow = makeRow('Bold');
            tBoldRow.ctrl.appendChild(makeCheckbox(!!draft.textBold, function(v) { draft.textBold = v; }));
            body.appendChild(tBoldRow.row);
            var tItalicRow = makeRow('Italic');
            tItalicRow.ctrl.appendChild(makeCheckbox(!!draft.textItalic, function(v) { draft.textItalic = v; }));
            body.appendChild(tItalicRow.row);

        } else if (activeTab === 'Text' && (d.type === 'arrow_marker' || d.type === 'arrow' || d.type === 'arrow_mark_up' || d.type === 'arrow_mark_down' || d.type === 'arrow_mark_left' || d.type === 'arrow_mark_right')) {
            addSectionHeading('TEXT');
            var tRow = makeRow('Text');
            tRow.ctrl.appendChild(makeTextInput(draft.text || '', function(v) { draft.text = v; }));
            body.appendChild(tRow.row);

        } else if (activeTab === 'Text' && ['anchored_text', 'note', 'price_note', 'pin', 'callout', 'comment', 'price_label', 'signpost', 'flag_mark'].indexOf(d.type) !== -1) {
            var _hoverTextTools2 = ['pin', 'flag_mark', 'signpost'];
            if (_hoverTextTools2.indexOf(d.type) !== -1) {
                // TV-style Text tab: font row, textarea, background, border
                var fontRow = document.createElement('div');
                fontRow.style.cssText = 'display:flex;align-items:center;gap:8px;padding:8px 16px;';
                fontRow.appendChild(makeColorSwatch(draft.color || _drawDefaults.color, function(c) { draft.color = c; }));
                fontRow.appendChild(makeSelect([{value:10,label:'10'},{value:12,label:'12'},{value:14,label:'14'},{value:16,label:'16'},{value:18,label:'18'},{value:20,label:'20'},{value:24,label:'24'},{value:28,label:'28'}], draft.fontSize || 14, function(v) { draft.fontSize = parseInt(v); }));
                var boldBtn = document.createElement('button');
                boldBtn.textContent = 'B';
                boldBtn.className = 'ts-btn' + (draft.bold ? ' active' : '');
                boldBtn.style.cssText = 'font-weight:bold;min-width:28px;height:28px;border:1px solid rgba(255,255,255,0.2);border-radius:4px;background:' + (draft.bold ? 'rgba(255,255,255,0.15)' : 'transparent') + ';color:inherit;cursor:pointer;';
                boldBtn.addEventListener('click', function() {
                    draft.bold = !draft.bold;
                    boldBtn.style.background = draft.bold ? 'rgba(255,255,255,0.15)' : 'transparent';
                });
                fontRow.appendChild(boldBtn);
                var italicBtn = document.createElement('button');
                italicBtn.textContent = 'I';
                italicBtn.className = 'ts-btn' + (draft.italic ? ' active' : '');
                italicBtn.style.cssText = 'font-style:italic;min-width:28px;height:28px;border:1px solid rgba(255,255,255,0.2);border-radius:4px;background:' + (draft.italic ? 'rgba(255,255,255,0.15)' : 'transparent') + ';color:inherit;cursor:pointer;';
                italicBtn.addEventListener('click', function() {
                    draft.italic = !draft.italic;
                    italicBtn.style.background = draft.italic ? 'rgba(255,255,255,0.15)' : 'transparent';
                });
                fontRow.appendChild(italicBtn);
                body.appendChild(fontRow);

                var ta = document.createElement('textarea');
                ta.className = 'ts-input ts-input-full tv-settings-textarea';
                ta.style.cssText = 'margin:8px 16px;min-height:80px;resize:vertical;border:2px solid #2962ff;border-radius:4px;background:#1e222d;color:inherit;padding:8px;font-family:inherit;font-size:14px;';
                ta.placeholder = 'Add text';
                ta.value = draft.text || '';
                ta.addEventListener('input', function() { draft.text = ta.value; });
                ta.addEventListener('keydown', function(e) { e.stopPropagation(); });
                body.appendChild(ta);

                var bgRow2 = makeRow('Background');
                bgRow2.ctrl.appendChild(makeCheckbox(draft.bgEnabled !== false, function(v) { draft.bgEnabled = v; }));
                bgRow2.ctrl.appendChild(makeColorSwatch(draft.bgColor || '#2a2e39', function(c) { draft.bgColor = c; }));
                body.appendChild(bgRow2.row);
                var bdRow2 = makeRow('Border');
                bdRow2.ctrl.appendChild(makeCheckbox(!!draft.borderEnabled, function(v) { draft.borderEnabled = v; }));
                bdRow2.ctrl.appendChild(makeColorSwatch(draft.borderColor || draft.color || _drawDefaults.color, function(c) { draft.borderColor = c; }));
                body.appendChild(bdRow2.row);
            } else {
                addSectionHeading('TEXT');
                var tRow = makeRow('Text');
                tRow.ctrl.appendChild(makeTextInput(draft.text || '', function(v) { draft.text = v; }));
                body.appendChild(tRow.row);
            }

        } else if (activeTab === 'Coordinates') {
            // Helper: make a bar index input from a time value
            function makeBarInput(tKey) {
                var entry = window.__PYWRY_TVCHARTS__ && window.__PYWRY_TVCHARTS__[chartId];
                var data = entry && entry.series && typeof entry.series.data === 'function' ? entry.series.data() : null;
                var barIdx = 0;
                if (data && data.length && draft[tKey]) {
                    for (var bi = 0; bi < data.length; bi++) {
                        if (data[bi].time >= draft[tKey]) { barIdx = bi; break; }
                    }
                    if (barIdx === 0 && data[data.length - 1].time < draft[tKey]) barIdx = data.length - 1;
                }
                var inp = document.createElement('input');
                inp.type = 'number';
                inp.className = 'ts-input';
                inp.value = barIdx;
                inp.min = '0';
                inp.max = data ? String(data.length - 1) : '0';
                inp.step = '1';
                inp.addEventListener('input', function() {
                    if (!data || !data.length) return;
                    var idx = Math.max(0, Math.min(parseInt(inp.value) || 0, data.length - 1));
                    draft[tKey] = data[idx].time;
                });
                inp.addEventListener('keydown', function(e) { e.stopPropagation(); });
                return inp;
            }

            if (d.type === 'hline') {
                addSectionHeading('PRICE');
                var pRow = makeRow('Price');
                pRow.ctrl.appendChild(makeNumberInput(draft.price || draft.p1 || 0, function(v) {
                    draft.price = v; draft.p1 = v;
                }));
                body.appendChild(pRow.row);
            } else if (d.type === 'trendline' || d.type === 'ray' || d.type === 'extended_line' || d.type === 'fibonacci' || d.type === 'measure' ||
                       d.type === 'fib_timezone' || d.type === 'fib_fan' || d.type === 'fib_arc' || d.type === 'fib_circle' ||
                       d.type === 'fib_spiral' || d.type === 'gann_box' || d.type === 'gann_square_fixed' || d.type === 'gann_square' || d.type === 'gann_fan' ||
                       d.type === 'arrow_marker' || d.type === 'arrow' || d.type === 'circle' || d.type === 'ellipse' || d.type === 'curve' ||
                       d.type === 'long_position' || d.type === 'short_position' || d.type === 'forecast' ||
                       d.type === 'bars_pattern' || d.type === 'ghost_feed' || d.type === 'projection' || d.type === 'fixed_range_vol' ||
                       d.type === 'price_range' || d.type === 'date_range' || d.type === 'date_price_range') {
                addSectionHeading('#1');
                var b1Row = makeRow('Bar');
                b1Row.ctrl.appendChild(makeBarInput('t1'));
                body.appendChild(b1Row.row);
                var p1Row = makeRow('Price');
                p1Row.ctrl.appendChild(makeNumberInput(draft.p1 || 0, function(v) { draft.p1 = v; }));
                body.appendChild(p1Row.row);
                addSectionHeading('#2');
                var b2Row = makeRow('Bar');
                b2Row.ctrl.appendChild(makeBarInput('t2'));
                body.appendChild(b2Row.row);
                var p2Row = makeRow('Price');
                p2Row.ctrl.appendChild(makeNumberInput(draft.p2 || 0, function(v) { draft.p2 = v; }));
                body.appendChild(p2Row.row);
            } else if (d.type === 'fib_extension' || d.type === 'fib_channel' || d.type === 'fib_wedge' || d.type === 'pitchfan' || d.type === 'fib_time' ||
                       d.type === 'rotated_rect' || d.type === 'triangle' || d.type === 'shape_arc' || d.type === 'double_curve') {
                addSectionHeading('#1');
                var b1Row = makeRow('Bar');
                b1Row.ctrl.appendChild(makeBarInput('t1'));
                body.appendChild(b1Row.row);
                var p1Row = makeRow('Price');
                p1Row.ctrl.appendChild(makeNumberInput(draft.p1 || 0, function(v) { draft.p1 = v; }));
                body.appendChild(p1Row.row);
                addSectionHeading('#2');
                var b2Row = makeRow('Bar');
                b2Row.ctrl.appendChild(makeBarInput('t2'));
                body.appendChild(b2Row.row);
                var p2Row = makeRow('Price');
                p2Row.ctrl.appendChild(makeNumberInput(draft.p2 || 0, function(v) { draft.p2 = v; }));
                body.appendChild(p2Row.row);
                addSectionHeading('#3');
                var b3Row = makeRow('Bar');
                b3Row.ctrl.appendChild(makeBarInput('t3'));
                body.appendChild(b3Row.row);
                var p3Row = makeRow('Price');
                p3Row.ctrl.appendChild(makeNumberInput(draft.p3 || 0, function(v) { draft.p3 = v; }));
                body.appendChild(p3Row.row);
            } else if (d.type === 'vline') {
                addSectionHeading('TIME');
                var vbRow = makeRow('Bar');
                vbRow.ctrl.appendChild(makeBarInput('t1'));
                body.appendChild(vbRow.row);
            } else if (d.type === 'crossline') {
                addSectionHeading('POSITION');
                var cbRow = makeRow('Bar');
                cbRow.ctrl.appendChild(makeBarInput('t1'));
                body.appendChild(cbRow.row);
                var pRow = makeRow('Price');
                pRow.ctrl.appendChild(makeNumberInput(draft.p1 || 0, function(v) { draft.p1 = v; }));
                body.appendChild(pRow.row);
            } else if (d.type === 'hray') {
                addSectionHeading('POSITION');
                var hbRow = makeRow('Bar');
                hbRow.ctrl.appendChild(makeBarInput('t1'));
                body.appendChild(hbRow.row);
                var pRow = makeRow('Price');
                pRow.ctrl.appendChild(makeNumberInput(draft.p1 || 0, function(v) { draft.p1 = v; }));
                body.appendChild(pRow.row);
            } else if (d.type === 'flat_channel') {
                addSectionHeading('LEVELS');
                var p1Row = makeRow('Upper level');
                p1Row.ctrl.appendChild(makeNumberInput(draft.p1 || 0, function(v) { draft.p1 = v; }));
                body.appendChild(p1Row.row);
                var p2Row = makeRow('Lower level');
                p2Row.ctrl.appendChild(makeNumberInput(draft.p2 || 0, function(v) { draft.p2 = v; }));
                body.appendChild(p2Row.row);
            } else if (d.type === 'regression_channel') {
                addSectionHeading('#1');
                var rb1 = makeRow('Bar');
                rb1.ctrl.appendChild(makeBarInput('t1'));
                body.appendChild(rb1.row);
                var rp1 = makeRow('Price');
                rp1.ctrl.appendChild(makeNumberInput(draft.p1 || 0, function(v) { draft.p1 = v; }));
                body.appendChild(rp1.row);
                addSectionHeading('#2');
                var rb2 = makeRow('Bar');
                rb2.ctrl.appendChild(makeBarInput('t2'));
                body.appendChild(rb2.row);
                var rp2 = makeRow('Price');
                rp2.ctrl.appendChild(makeNumberInput(draft.p2 || 0, function(v) { draft.p2 = v; }));
                body.appendChild(rp2.row);
            } else if (d.type === 'rect') {
                addSectionHeading('TOP-LEFT');
                var rb1 = makeRow('Bar');
                rb1.ctrl.appendChild(makeBarInput('t1'));
                body.appendChild(rb1.row);
                var p1Row = makeRow('Price');
                p1Row.ctrl.appendChild(makeNumberInput(draft.p1 || 0, function(v) { draft.p1 = v; }));
                body.appendChild(p1Row.row);
                addSectionHeading('BOTTOM-RIGHT');
                var rb2 = makeRow('Bar');
                rb2.ctrl.appendChild(makeBarInput('t2'));
                body.appendChild(rb2.row);
                var p2Row = makeRow('Price');
                p2Row.ctrl.appendChild(makeNumberInput(draft.p2 || 0, function(v) { draft.p2 = v; }));
                body.appendChild(p2Row.row);
            } else if (d.type === 'channel') {
                addSectionHeading('#1');
                var cb1 = makeRow('Bar');
                cb1.ctrl.appendChild(makeBarInput('t1'));
                body.appendChild(cb1.row);
                var cp1 = makeRow('Price');
                cp1.ctrl.appendChild(makeNumberInput(draft.p1 || 0, function(v) { draft.p1 = v; }));
                body.appendChild(cp1.row);
                addSectionHeading('#2');
                var cb2 = makeRow('Bar');
                cb2.ctrl.appendChild(makeBarInput('t2'));
                body.appendChild(cb2.row);
                var cp2 = makeRow('Price');
                cp2.ctrl.appendChild(makeNumberInput(draft.p2 || 0, function(v) { draft.p2 = v; }));
                body.appendChild(cp2.row);
                addSectionHeading('CHANNEL');
                var offRow = makeRow('Offset (px)');
                offRow.ctrl.appendChild(makeNumberInput(draft.offset || 30, function(v) { draft.offset = v; }));
                body.appendChild(offRow.row);
            } else if (d.type === 'brush' || d.type === 'highlighter' || d.type === 'path' || d.type === 'polyline') {
                addSectionHeading('POSITION');
                var noRow = document.createElement('div');
                noRow.className = 'tv-settings-row';
                noRow.style.cssText = 'color:var(--pywry-tvchart-text-muted,#787b86);font-size:12px;';
                noRow.textContent = 'Freeform drawing \u2014 drag to reposition.';
                body.appendChild(noRow);
            } else if (d.type === 'arrow_mark_up' || d.type === 'arrow_mark_down' || d.type === 'arrow_mark_left' || d.type === 'arrow_mark_right' || d.type === 'anchored_vwap') {
                addSectionHeading('POSITION');
                var abRow = makeRow('Bar');
                abRow.ctrl.appendChild(makeBarInput('t1'));
                body.appendChild(abRow.row);
                var apRow = makeRow('Price');
                apRow.ctrl.appendChild(makeNumberInput(draft.p1 || 0, function(v) { draft.p1 = v; }));
                body.appendChild(apRow.row);
            } else if (d.type === 'text') {
                addSectionHeading('POSITION');
                var tbRow = makeRow('Bar');
                tbRow.ctrl.appendChild(makeBarInput('t1'));
                body.appendChild(tbRow.row);
                var tpRow = makeRow('Price');
                tpRow.ctrl.appendChild(makeNumberInput(draft.p1 || 0, function(v) { draft.p1 = v; }));
                body.appendChild(tpRow.row);
            } else {
                if (draft.p1 !== undefined) {
                    var p1Row = makeRow('Price 1');
                    p1Row.ctrl.appendChild(makeNumberInput(draft.p1, function(v) { draft.p1 = v; }));
                    body.appendChild(p1Row.row);
                }
                if (draft.p2 !== undefined) {
                    var p2Row = makeRow('Price 2');
                    p2Row.ctrl.appendChild(makeNumberInput(draft.p2, function(v) { draft.p2 = v; }));
                    body.appendChild(p2Row.row);
                }
            }

        } else if (activeTab === 'Visibility') {
            addSectionHeading('TIME INTERVALS');
            addVisibilityIntervals(body);
            addSectionHeading('DRAWING');
            var hRow = makeRow('Hidden');
            hRow.ctrl.appendChild(makeCheckbox(!!draft.hidden, function(v) { draft.hidden = v; }));
            body.appendChild(hRow.row);
            var lkRow = makeRow('Locked');
            lkRow.ctrl.appendChild(makeCheckbox(!!draft.locked, function(v) { draft.locked = v; }));
            body.appendChild(lkRow.row);
        }
    }

    // Footer
    var footer = document.createElement('div');
    footer.className = 'tv-settings-footer';
    footer.style.cssText = 'position:relative;bottom:auto;left:auto;right:auto;';
    var cancelBtn = document.createElement('button');
    cancelBtn.className = 'ts-btn-cancel';
    cancelBtn.textContent = 'Cancel';
    cancelBtn.addEventListener('click', function() { _tvHideDrawingSettings(); });
    footer.appendChild(cancelBtn);
    var okBtn = document.createElement('button');
    okBtn.className = 'ts-btn-ok';
    okBtn.textContent = 'Ok';
    okBtn.addEventListener('click', function() {
        // Apply draft onto original drawing
        Object.assign(d, draft);
        // Sync native price line for hline
        if (d.type === 'hline') {
            _tvSyncPriceLineColor(chartId, drawIdx, d.color || _drawDefaults.color);
            _tvSyncPriceLinePrice(chartId, drawIdx, d.price || d.p1);
        }
        _tvRenderDrawings(chartId);
        if (_floatingToolbar) {
            _tvHideFloatingToolbar();
            _tvShowFloatingToolbar(chartId, drawIdx);
        }
        _tvHideDrawingSettings();
    });
    footer.appendChild(okBtn);
    panel.appendChild(footer);

    renderTabs();
    renderBody();
    ds.uiLayer.appendChild(overlay);
}

