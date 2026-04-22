function _tvShowChartSettings(chartId) {
    _tvHideChartSettings();
    var resolved = _tvResolveChartEntry(chartId);
    if (!resolved || !resolved.entry) return;
    chartId = resolved.chartId;
    var entry = resolved.entry;
    var currentSettings = (entry && entry._chartPrefs && entry._chartPrefs.settings)
        ? entry._chartPrefs.settings
        : _tvBuildCurrentSettings(entry);

    var overlay = document.createElement('div');
    overlay.className = 'tv-settings-overlay';
    _chartSettingsOverlay = overlay;
    _chartSettingsOverlayChartId = chartId;
    _tvSetChartInteractionLocked(chartId, true);
    _tvRefreshLegendVisibility();
    overlay.addEventListener('click', function(e) {
        if (e.target === overlay) _tvHideChartSettings();
    });
    overlay.addEventListener('mousedown', function(e) { e.stopPropagation(); });
    overlay.addEventListener('wheel', function(e) { e.stopPropagation(); });

    var panel = document.createElement('div');
    panel.className = 'tv-settings-panel';
    overlay.appendChild(panel);

    // Header (stays fixed at top)
    var header = document.createElement('div');
    header.className = 'tv-settings-header';
    var title = document.createElement('h3');
    title.textContent = 'Symbol Settings';
    header.appendChild(title);
    var closeBtn = document.createElement('button');
    closeBtn.className = 'tv-settings-close';
    closeBtn.innerHTML = '<svg viewBox="0 0 16 16"><line x1="3" y1="3" x2="13" y2="13"/><line x1="13" y1="3" x2="3" y2="13"/></svg>';
    closeBtn.addEventListener('click', function() { _tvHideChartSettings(); });
    header.appendChild(closeBtn);
    panel.appendChild(header);

    // Sidebar with tabs
    var sidebar = document.createElement('div');
    sidebar.className = 'tv-settings-sidebar';
    panel.appendChild(sidebar);

    var tabDefs = [
        { id: 'symbol', label: 'Symbol', icon: '🔤' },
        { id: 'status', label: 'Status line', icon: '━' },
        { id: 'scales', label: 'Scales and lines', icon: '↕' },
        { id: 'canvas', label: 'Canvas', icon: '⬜' }
    ];

    var tabButtons = {};
    var activeTab = 'symbol';

    for (var ti = 0; ti < tabDefs.length; ti++) {
        var tdef = tabDefs[ti];
        var tBtn = document.createElement('div');
        tBtn.className = 'tv-settings-sidebar-tab' + (ti === 0 ? ' active' : '');
        tBtn.textContent = tdef.label;
        tBtn.setAttribute('data-tab', tdef.id);
        tabButtons[tdef.id] = tBtn;
        
        (function(tabId, btn) {
            btn.addEventListener('click', function() {
                if (activeTab === tabId) return;
                tabButtons[activeTab].classList.remove('active');
                document.getElementById('pane-' + activeTab).classList.remove('active');
                tabButtons[tabId].classList.add('active');
                document.getElementById('pane-' + tabId).classList.add('active');
                activeTab = tabId;
            });
        })(tdef.id, tBtn);
        
        sidebar.appendChild(tBtn);
    }

    // Content area
    var content = document.createElement('div');
    content.className = 'tv-settings-content';
    panel.appendChild(content);

    // Helper functions for controls

    function syncSettingsSwatch(swatch, baseColor, opacityPercent) {
        if (!swatch) return;
        var nextColor = _tvColorToHex(baseColor || swatch.dataset.baseColor || '#aeb4c2', '#aeb4c2');
        var nextOpacity = _tvClamp(_tvToNumber(opacityPercent, swatch.dataset.opacity || 100), 0, 100);
        swatch.dataset.baseColor = nextColor;
        swatch.dataset.opacity = String(nextOpacity);
        swatch.style.background = _tvColorWithOpacity(nextColor, nextOpacity, nextColor);
    }

    function addCheckboxRow(parent, label, checked) {
        var row = document.createElement('div');
        row.className = 'tv-settings-row tv-settings-row-spaced';
        var lbl = document.createElement('label');
        lbl.textContent = label;
        row.appendChild(lbl);
        var cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.className = 'ts-checkbox';
        cb.checked = !!checked;
        cb.setAttribute('data-setting', label);
        var ctrl = document.createElement('div');
        ctrl.className = 'ts-controls';
        ctrl.appendChild(cb);
        row.appendChild(ctrl);
        parent.appendChild(row);
        return cb;
    }

    function addIndentedCheckboxRow(parent, label, checked) {
        var cb = addCheckboxRow(parent, label, checked);
        if (cb && cb.parentNode && cb.parentNode.parentNode) {
            cb.parentNode.parentNode.classList.add('tv-settings-row-indent');
        }
        return cb;
    }

    function addSelectRow(parent, label, options, selected) {
        var row = document.createElement('div');
        row.className = 'tv-settings-row tv-settings-row-spaced';
        var lbl = document.createElement('label');
        lbl.textContent = label;
        row.appendChild(lbl);
        var sel = document.createElement('select');
        sel.className = 'ts-select';
        sel.setAttribute('data-setting', label);
        for (var i = 0; i < options.length; i++) {
            var o = document.createElement('option');
            o.value = options[i];
            o.textContent = options[i];
            if (options[i] === selected) o.selected = true;
            sel.appendChild(o);
        }
        var ctrl = document.createElement('div');
        ctrl.className = 'ts-controls';
        ctrl.appendChild(sel);
        row.appendChild(ctrl);
        parent.appendChild(row);
        return sel;
    }

    function addColorRow(parent, label, checked, color) {
        var row = document.createElement('div');
        row.className = 'tv-settings-row tv-settings-row-spaced';
        var lbl = document.createElement('label');
        lbl.className = 'tv-settings-inline-label';
        lbl.textContent = label;
        row.appendChild(lbl);
        var ctrl = document.createElement('div');
        ctrl.className = 'ts-controls';
        if (checked != null) {
            var cb = document.createElement('input');
            cb.type = 'checkbox';
            cb.className = 'ts-checkbox';
            cb.setAttribute('data-setting', label + '-Enabled');
            cb.checked = !!checked;
            ctrl.appendChild(cb);
        }
        var swatch = document.createElement('div');
        swatch.className = 'ts-swatch';
        swatch.setAttribute('data-setting', label + '-Color');
        swatch.dataset.baseColor = _tvColorToHex(color || '#aeb4c2', '#aeb4c2');
        swatch.dataset.opacity = String(_tvColorOpacityPercent(color, 100));
        swatch.style.background = color || '#aeb4c2';
        ctrl.appendChild(swatch);

        swatch.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            _tvShowColorOpacityPopup(
                swatch,
                swatch.dataset.baseColor || color || '#aeb4c2',
                _tvToNumber(swatch.dataset.opacity, 100),
                overlay,
                function(newColor, newOpacity) {
                    swatch.dataset.baseColor = newColor;
                    swatch.dataset.opacity = String(newOpacity);
                    swatch.style.background = _tvColorWithOpacity(newColor, newOpacity, newColor);
                    scheduleSettingsPreview();
                }
            );
        });

        row.appendChild(ctrl);
        parent.appendChild(row);
        return {
            checkbox: checked !== undefined && checked !== false ? ctrl.querySelector('input[type="checkbox"]') : null,
            swatch: swatch,
        };
    }

    function addDualColorRow(parent, label, checked, upColor, downColor, upSetting, downSetting) {
        var row = document.createElement('div');
        row.className = 'tv-settings-row tv-settings-row-spaced';

        var lbl = document.createElement('label');
        lbl.className = 'tv-settings-inline-label';
        lbl.textContent = label;
        row.appendChild(lbl);

        var ctrl = document.createElement('div');
        ctrl.className = 'ts-controls';

        var cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.className = 'ts-checkbox';
        cb.setAttribute('data-setting', label);
        cb.checked = !!checked;
        ctrl.appendChild(cb);

        function makeSwatch(settingKey, color) {
            var wrap = document.createElement('div');
            wrap.className = 'tv-settings-color-pair';

            var opacityInput = document.createElement('input');
            opacityInput.type = 'hidden';
            var explicitOpacity = currentSettings[settingKey + '-Opacity'];
            var legacyOpacity = currentSettings[label + '-Opacity'];
            opacityInput.value = explicitOpacity != null ? String(explicitOpacity) : (legacyOpacity != null ? String(legacyOpacity) : '100');
            opacityInput.setAttribute('data-setting', settingKey + '-Opacity');
            wrap.appendChild(opacityInput);

            var swatch = document.createElement('div');
            swatch.className = 'ts-swatch';
            swatch.setAttribute('data-setting', settingKey);
            syncSettingsSwatch(swatch, color || '#aeb4c2', opacityInput.value);
            wrap.appendChild(swatch);

            swatch.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                _tvShowColorOpacityPopup(
                    swatch,
                    swatch.dataset.baseColor || color || '#aeb4c2',
                    _tvToNumber(opacityInput.value, 100),
                    overlay,
                    function(newColor, newOpacity) {
                        opacityInput.value = String(newOpacity);
                        syncSettingsSwatch(swatch, newColor, newOpacity);
                        scheduleSettingsPreview();
                    }
                );
            });

            return wrap;
        }

        ctrl.appendChild(makeSwatch(upSetting, upColor));
        ctrl.appendChild(makeSwatch(downSetting, downColor));
        row.appendChild(ctrl);
        parent.appendChild(row);
        return row;
    }

    function addCheckboxSliderRow(parent, label, checked, enabledSetting, sliderValue, sliderSetting) {
        var row = document.createElement('div');
        row.className = 'tv-settings-row tv-settings-row-spaced';

        var lbl = document.createElement('label');
        lbl.textContent = label;
        row.appendChild(lbl);

        var ctrl = document.createElement('div');
        ctrl.className = 'ts-controls ts-controls-slider';

        var cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.className = 'ts-checkbox';
        cb.checked = !!checked;
        cb.setAttribute('data-setting', enabledSetting);
        ctrl.appendChild(cb);

        var slider = document.createElement('input');
        slider.type = 'range';
        slider.min = '0';
        slider.max = '100';
        slider.value = sliderValue != null ? String(sliderValue) : '100';
        slider.className = 'tv-settings-slider';
        slider.setAttribute('data-setting', sliderSetting);
        ctrl.appendChild(slider);

        var output = document.createElement('span');
        output.className = 'tv-settings-slider-value';
        output.textContent = slider.value + '%';
        ctrl.appendChild(output);

        slider.addEventListener('input', function() {
            output.textContent = slider.value + '%';
        });

        row.appendChild(ctrl);
        parent.appendChild(row);
        return { checkbox: cb, slider: slider, output: output };
    }

    function addCheckboxInputRow(parent, label, checked, enabledSetting, inputValue, inputSetting) {
        var row = document.createElement('div');
        row.className = 'tv-settings-row tv-settings-row-spaced tv-settings-row-combo';

        var lbl = document.createElement('label');
        lbl.textContent = '';
        row.appendChild(lbl);

        var ctrl = document.createElement('div');
        ctrl.className = 'ts-controls';

        var cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.className = 'ts-checkbox';
        cb.checked = !!checked;
        cb.setAttribute('data-setting', enabledSetting);
        ctrl.appendChild(cb);

        var textLbl = document.createElement('span');
        textLbl.className = 'tv-settings-inline-gap';
        textLbl.textContent = label;
        ctrl.appendChild(textLbl);

        var inp = document.createElement('input');
        inp.type = 'text';
        inp.className = 'ts-input ts-input-wide';
        inp.setAttribute('data-setting', inputSetting);
        inp.value = inputValue != null ? String(inputValue) : '';
        ctrl.appendChild(inp);

        row.appendChild(ctrl);
        parent.appendChild(row);
        return { checkbox: cb, input: inp };
    }

    function addSelectColorRow(parent, label, options, selected, selectSetting, color, colorSetting) {
        var row = document.createElement('div');
        row.className = 'tv-settings-row tv-settings-row-spaced';

        var lbl = document.createElement('label');
        lbl.textContent = label;
        row.appendChild(lbl);

        var ctrl = document.createElement('div');
        ctrl.className = 'ts-controls';

        var sel = document.createElement('select');
        sel.className = 'ts-select';
        sel.setAttribute('data-setting', selectSetting || label);
        options.forEach(function(opt) {
            var o = document.createElement('option');
            o.value = opt;
            o.textContent = opt;
            if (opt === selected) o.selected = true;
            sel.appendChild(o);
        });
        ctrl.appendChild(sel);

        var swatch = document.createElement('div');
        swatch.className = 'ts-swatch';
        swatch.setAttribute('data-setting', colorSetting || (label + ' color'));
        swatch.dataset.baseColor = _tvColorToHex(color || '#aeb4c2', '#aeb4c2');
        swatch.dataset.opacity = String(_tvColorOpacityPercent(color, 100));
        swatch.style.background = color || '#aeb4c2';
        ctrl.appendChild(swatch);

        swatch.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            _tvShowColorOpacityPopup(
                swatch,
                swatch.dataset.baseColor || color || '#aeb4c2',
                _tvToNumber(swatch.dataset.opacity, 100),
                overlay,
                function(newColor, newOpacity) {
                    swatch.dataset.baseColor = newColor;
                    swatch.dataset.opacity = String(newOpacity);
                    swatch.style.background = _tvColorWithOpacity(newColor, newOpacity, newColor);
                    scheduleSettingsPreview();
                }
            );
        });

        row.appendChild(ctrl);
        parent.appendChild(row);
        return { select: sel, swatch: swatch };
    }

    function addNumberInputRow(parent, label, settingKey, value, min, max, step, unitText, inputClassName) {
        var row = document.createElement('div');
        row.className = 'tv-settings-row tv-settings-row-spaced';

        var lbl = document.createElement('label');
        lbl.textContent = label;
        row.appendChild(lbl);

        var ctrl = document.createElement('div');
        ctrl.className = 'ts-controls';

        var inp = document.createElement('input');
        inp.type = 'number';
        inp.className = inputClassName || 'ts-input';
        inp.setAttribute('data-setting', settingKey || label);
        if (min != null) inp.min = String(min);
        if (max != null) inp.max = String(max);
        if (step != null) inp.step = String(step);
        inp.value = value != null ? String(value) : '';
        ctrl.appendChild(inp);

        if (unitText) {
            var unit = document.createElement('span');
            unit.className = 'tv-settings-unit';
            unit.textContent = unitText;
            ctrl.appendChild(unit);
        }

        row.appendChild(ctrl);
        parent.appendChild(row);
        return inp;
    }

    function addColorSwatchRow(parent, label, color, settingKey) {
        var row = document.createElement('div');
        row.className = 'tv-settings-row tv-settings-row-spaced';

        var lbl = document.createElement('label');
        lbl.textContent = label;
        row.appendChild(lbl);

        var ctrl = document.createElement('div');
        ctrl.className = 'ts-controls';

        var swatch = document.createElement('div');
        swatch.className = 'ts-swatch';
        swatch.setAttribute('data-setting', settingKey || label);
        swatch.dataset.baseColor = _tvColorToHex(color || '#aeb4c2', '#aeb4c2');
        swatch.dataset.opacity = String(_tvColorOpacityPercent(color, 100));
        swatch.style.background = color || '#aeb4c2';
        ctrl.appendChild(swatch);

        swatch.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            _tvShowColorOpacityPopup(
                swatch,
                swatch.dataset.baseColor || color || '#aeb4c2',
                _tvToNumber(swatch.dataset.opacity, 100),
                overlay,
                function(newColor, newOpacity) {
                    swatch.dataset.baseColor = newColor;
                    swatch.dataset.opacity = String(newOpacity);
                    swatch.style.background = _tvColorWithOpacity(newColor, newOpacity, newColor);
                    scheduleSettingsPreview();
                }
            );
        });

        row.appendChild(ctrl);
        parent.appendChild(row);
        return { swatch: swatch };
    }

    // Pane: Symbol
    var paneSymbol = document.createElement('div');
    paneSymbol.id = 'pane-symbol';
    paneSymbol.className = 'tv-settings-content-pane active';
    
    var lineSection = document.createElement('div');
    lineSection.className = 'tv-settings-section-body';
    paneSymbol.appendChild(lineSection);

    var mainSeries = _tvGetMainSeries(entry);
    var seriesType = mainSeries ? _tvGuessSeriesType(mainSeries) : 'Candlestick';

    var symbolTitle = document.createElement('div');
    symbolTitle.className = 'tv-settings-title';

    if (seriesType === 'Candlestick') {
        symbolTitle.textContent = 'CANDLES';
        lineSection.appendChild(symbolTitle);
        addCheckboxRow(lineSection, 'Color bars based on previous close', currentSettings['Color bars based on previous close']);
        addDualColorRow(lineSection, 'Body', currentSettings['Body'], currentSettings['Body-Up Color'], currentSettings['Body-Down Color'], 'Body-Up Color', 'Body-Down Color');
        addDualColorRow(lineSection, 'Borders', currentSettings['Borders'], currentSettings['Borders-Up Color'], currentSettings['Borders-Down Color'], 'Borders-Up Color', 'Borders-Down Color');
        addDualColorRow(lineSection, 'Wick', currentSettings['Wick'], currentSettings['Wick-Up Color'], currentSettings['Wick-Down Color'], 'Wick-Up Color', 'Wick-Down Color');
    } else if (seriesType === 'Bar') {
        symbolTitle.textContent = 'BARS';
        lineSection.appendChild(symbolTitle);
        addCheckboxRow(lineSection, 'Color bars based on previous close', currentSettings['Color bars based on previous close']);
        addColorSwatchRow(lineSection, 'Up color', currentSettings['Bar Up Color'], 'Bar Up Color');
        addColorSwatchRow(lineSection, 'Down color', currentSettings['Bar Down Color'], 'Bar Down Color');
    } else if (seriesType === 'Line') {
        symbolTitle.textContent = 'LINE';
        lineSection.appendChild(symbolTitle);
        addColorSwatchRow(lineSection, 'Color', currentSettings['Line color'], 'Line color');
        addSelectRow(lineSection, 'Line style', ['Solid', 'Dotted', 'Dashed'], currentSettings['Line style']);
        addNumberInputRow(lineSection, 'Line width', 'Line width', currentSettings['Line width'], 1, 4, 1, '', 'ts-input');
    } else if (seriesType === 'Area') {
        symbolTitle.textContent = 'AREA';
        lineSection.appendChild(symbolTitle);
        addColorSwatchRow(lineSection, 'Line color', currentSettings['Line color'], 'Line color');
        addNumberInputRow(lineSection, 'Line width', 'Line width', currentSettings['Line width'], 1, 4, 1, '', 'ts-input');
        addColorSwatchRow(lineSection, 'Fill 1', currentSettings['Area Fill Top'], 'Area Fill Top');
        addColorSwatchRow(lineSection, 'Fill 2', currentSettings['Area Fill Bottom'], 'Area Fill Bottom');
    } else if (seriesType === 'Baseline') {
        symbolTitle.textContent = 'BASELINE';
        lineSection.appendChild(symbolTitle);
        addNumberInputRow(lineSection, 'Base level', 'Baseline Level', currentSettings['Baseline Level'], null, null, null, '', 'ts-input');
        addColorSwatchRow(lineSection, 'Top line color', currentSettings['Baseline Top Line'], 'Baseline Top Line');
        addColorSwatchRow(lineSection, 'Bottom line color', currentSettings['Baseline Bottom Line'], 'Baseline Bottom Line');
        addColorSwatchRow(lineSection, 'Top area 1', currentSettings['Baseline Top Fill 1'], 'Baseline Top Fill 1');
        addColorSwatchRow(lineSection, 'Top area 2', currentSettings['Baseline Top Fill 2'], 'Baseline Top Fill 2');
        addColorSwatchRow(lineSection, 'Bottom area 1', currentSettings['Baseline Bottom Fill 1'], 'Baseline Bottom Fill 1');
        addColorSwatchRow(lineSection, 'Bottom area 2', currentSettings['Baseline Bottom Fill 2'], 'Baseline Bottom Fill 2');
    } else if (seriesType === 'Histogram') {
        symbolTitle.textContent = 'COLUMNS';
        lineSection.appendChild(symbolTitle);
        addCheckboxRow(lineSection, 'Color bars based on previous close', currentSettings['Color bars based on previous close']);
        addColorSwatchRow(lineSection, 'Up color', currentSettings['Bar Up Color'], 'Bar Up Color');
        addColorSwatchRow(lineSection, 'Down color', currentSettings['Bar Down Color'], 'Bar Down Color');
    } else {
        symbolTitle.textContent = seriesType.toUpperCase();
        lineSection.appendChild(symbolTitle);
        addColorSwatchRow(lineSection, 'Color', currentSettings['Line color'], 'Line color');
        addNumberInputRow(lineSection, 'Line width', 'Line width', currentSettings['Line width'], 1, 4, 1, '', 'ts-input');
    }

    var modTitle = document.createElement('div');
    modTitle.className = 'tv-settings-section';
    modTitle.textContent = 'DATA MODIFICATION';
    lineSection.appendChild(modTitle);

    addSelectRow(lineSection, 'Session', ['Regular trading hours', 'Extended trading hours'], currentSettings['Session']);
    addSelectRow(lineSection, 'Precision', ['Default', '0.1', '0.01', '0.001', '0.0001'], currentSettings['Precision']);
    addSelectRow(lineSection, 'Timezone', ['UTC', 'Local'], currentSettings['Timezone']);

    // Ensure the default Symbol tab has visible content.
    content.appendChild(paneSymbol);

    // Pane: Status line
    var paneStatus = document.createElement('div');
    paneStatus.id = 'pane-status';
    paneStatus.className = 'tv-settings-content-pane';
    var statusSection = document.createElement('div');
    statusSection.className = 'tv-settings-section-body';
    paneStatus.appendChild(statusSection);
    var statusTitle = document.createElement('div');
    statusTitle.className = 'tv-settings-title';
    statusTitle.textContent = 'SYMBOL';
    statusSection.appendChild(statusTitle);

    addCheckboxRow(statusSection, 'Logo', currentSettings['Logo']);

    // Title checkbox + inline description-mode dropdown (matches TradingView layout)
    (function() {
        var row = document.createElement('div');
        row.className = 'tv-settings-row tv-settings-row-spaced';
        var lbl = document.createElement('label');
        lbl.textContent = 'Title';
        row.appendChild(lbl);
        var ctrl = document.createElement('div');
        ctrl.className = 'ts-controls';
        var cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.className = 'ts-checkbox';
        cb.checked = currentSettings['Title'] !== false;
        cb.setAttribute('data-setting', 'Title');
        ctrl.appendChild(cb);
        var sel = document.createElement('select');
        sel.className = 'ts-select';
        sel.setAttribute('data-setting', 'Description');
        var descOpts = ['Description', 'Ticker', 'Ticker and description'];
        for (var di = 0; di < descOpts.length; di++) {
            var o = document.createElement('option');
            o.value = descOpts[di];
            o.textContent = descOpts[di];
            if (descOpts[di] === (currentSettings['Description'] || 'Description')) o.selected = true;
            sel.appendChild(o);
        }
        ctrl.appendChild(sel);
        row.appendChild(ctrl);
        statusSection.appendChild(row);
    })();
    addCheckboxRow(statusSection, 'Chart values', currentSettings['Chart values']);
    addCheckboxRow(statusSection, 'Bar change values', currentSettings['Bar change values']);
    addCheckboxRow(statusSection, 'Volume', currentSettings['Volume']);

    var statusIndicTitle = document.createElement('div');
    statusIndicTitle.className = 'tv-settings-section';
    statusIndicTitle.textContent = 'INDICATORS';
    statusSection.appendChild(statusIndicTitle);

    addCheckboxRow(statusSection, 'Titles', currentSettings['Titles']);

    addIndentedCheckboxRow(statusSection, 'Inputs', currentSettings['Inputs']);

    addCheckboxRow(statusSection, 'Values', currentSettings['Values']);
    addCheckboxSliderRow(
        statusSection,
        'Background',
        currentSettings['Background-Enabled'],
        'Background-Enabled',
        currentSettings['Background-Opacity'],
        'Background-Opacity'
    );

    content.appendChild(paneStatus);

    // Pane: Scales and lines - COMPLETE IMPLEMENTATION
    var paneScales = document.createElement('div');
    paneScales.id = 'pane-scales';
    paneScales.className = 'tv-settings-content-pane';
    var scalesSection = document.createElement('div');
    scalesSection.className = 'tv-settings-section-body';
    paneScales.appendChild(scalesSection);

    var scalePriceTitle = document.createElement('div');
    scalePriceTitle.className = 'tv-settings-section';
    scalePriceTitle.textContent = 'PRICE SCALE';
    scalesSection.appendChild(scalePriceTitle);

    addSelectRow(scalesSection, 'Scale modes (A and L)', ['Visible on mouse over', 'Hidden'], currentSettings['Scale modes (A and L)']);

    addCheckboxInputRow(
        scalesSection,
        'Lock price to bar ratio',
        currentSettings['Lock price to bar ratio'],
        'Lock price to bar ratio',
        currentSettings['Lock price to bar ratio (value)'],
        'Lock price to bar ratio (value)'
    );

    addSelectRow(scalesSection, 'Scales placement', ['Auto', 'Left', 'Right'], currentSettings['Scales placement']);

    var scalePriceLabelsTitle = document.createElement('div');
    scalePriceLabelsTitle.className = 'tv-settings-section';
    scalePriceLabelsTitle.textContent = 'PRICE LABELS & LINES';
    scalesSection.appendChild(scalePriceLabelsTitle);

    addCheckboxRow(scalesSection, 'No overlapping labels', currentSettings['No overlapping labels']);
    addCheckboxRow(scalesSection, 'Plus button', currentSettings['Plus button']);
    addCheckboxRow(scalesSection, 'Countdown to bar close', currentSettings['Countdown to bar close']);

    addSelectColorRow(
        scalesSection,
        'Symbol',
        ['Value, line', 'Line', 'Label', 'Hidden'],
        currentSettings['Symbol'],
        'Symbol',
        currentSettings['Symbol color'],
        'Symbol color'
    );

    addSelectRow(
        scalesSection,
        'Value according to scale',
        ['Value according to scale', 'Percent change'],
        currentSettings['Value according to scale'] || currentSettings['Value according to sc...']
    );
    addSelectRow(scalesSection, 'Indicators and financials', ['Value', 'Change', 'Percent change'], currentSettings['Indicators and financials']);

    addSelectColorRow(
        scalesSection,
        'High and low',
        ['Hidden', 'Values only', 'Values and lines'],
        currentSettings['High and low'],
        'High and low',
        currentSettings['High and low color'],
        'High and low color'
    );

    var scaleTimeTitle = document.createElement('div');
    scaleTimeTitle.className = 'tv-settings-section';
    scaleTimeTitle.textContent = 'TIME SCALE';
    scalesSection.appendChild(scaleTimeTitle);

    addCheckboxRow(scalesSection, 'Day of week on labels', currentSettings['Day of week on labels']);
    addSelectRow(scalesSection, 'Date format', ['Mon 29 Sep \'97', 'MM/DD/YY', 'DD/MM/YY', 'YYYY-MM-DD'], currentSettings['Date format']);
    addSelectRow(scalesSection, 'Time hours format', ['24-hours', '12-hours'], currentSettings['Time hours format']);

    content.appendChild(paneScales);

    // Pane: Canvas - COMPLETE IMPLEMENTATION
    var paneCanvas = document.createElement('div');
    paneCanvas.id = 'pane-canvas';
    paneCanvas.className = 'tv-settings-content-pane';
    var canvasSection = document.createElement('div');
    canvasSection.className = 'tv-settings-section-body';
    paneCanvas.appendChild(canvasSection);

    var canvasBasicTitle = document.createElement('div');
    canvasBasicTitle.className = 'tv-settings-section';
    canvasBasicTitle.textContent = 'CHART BASIC STYLES';
    canvasSection.appendChild(canvasBasicTitle);

    addSelectColorRow(canvasSection, 'Background', ['Solid', 'Gradient'], currentSettings['Background'], 'Background', currentSettings['Background-Color'], 'Background-Color');
    addSelectColorRow(canvasSection, 'Grid lines', ['Vert and horz', 'Vert only', 'Horz only', 'Hidden'], currentSettings['Grid lines'], 'Grid lines', currentSettings['Grid-Color'], 'Grid-Color');
    addColorSwatchRow(canvasSection, 'Pane separators', currentSettings['Pane-Separators-Color'], 'Pane-Separators-Color');
    addColorRow(canvasSection, 'Crosshair', currentSettings['Crosshair-Enabled'], currentSettings['Crosshair-Color']);
    addSelectColorRow(canvasSection, 'Watermark', ['Hidden', 'Visible'], currentSettings['Watermark'], 'Watermark', currentSettings['Watermark-Color'], 'Watermark-Color');

    var canvasScalesTitle = document.createElement('div');
    canvasScalesTitle.className = 'tv-settings-section';
    canvasScalesTitle.textContent = 'SCALES';
    canvasSection.appendChild(canvasScalesTitle);

    addColorRow(canvasSection, 'Text', null, currentSettings['Text-Color']);
    addColorRow(canvasSection, 'Lines', null, currentSettings['Lines-Color']);

    var canvasButtonsTitle = document.createElement('div');
    canvasButtonsTitle.className = 'tv-settings-section';
    canvasButtonsTitle.textContent = 'BUTTONS';
    canvasSection.appendChild(canvasButtonsTitle);

    addSelectRow(canvasSection, 'Navigation', ['Visible on mouse over', 'Hidden'], currentSettings['Navigation']);
    addSelectRow(canvasSection, 'Pane', ['Visible on mouse over', 'Hidden'], currentSettings['Pane']);

    var canvasMarginsTitle = document.createElement('div');
    canvasMarginsTitle.className = 'tv-settings-section';
    canvasMarginsTitle.textContent = 'MARGINS';
    canvasSection.appendChild(canvasMarginsTitle);

    addNumberInputRow(canvasSection, 'Top', 'Margin Top', currentSettings['Margin Top'], 0, 100, 1, '%', 'ts-input ts-input-sm');
    addNumberInputRow(canvasSection, 'Bottom', 'Margin Bottom', currentSettings['Margin Bottom'], 0, 100, 1, '%', 'ts-input ts-input-sm');

    content.appendChild(paneCanvas);

    // Footer
    var footer = document.createElement('div');
    footer.className = 'tv-settings-footer';
    var originalSettings = JSON.parse(JSON.stringify(currentSettings || {}));

    function collectSettingsFromPanel() {
        var settings = {};
        var allControls = panel.querySelectorAll('[data-setting]');
        allControls.forEach(function(ctrl) {
            var settingKey = ctrl.getAttribute('data-setting');
            if (!settingKey) return;

            var value;
            if (ctrl.tagName === 'SELECT') {
                value = ctrl.value;
            } else if (ctrl.tagName === 'INPUT') {
                if (ctrl.type === 'checkbox') {
                    value = ctrl.checked;
                } else if (ctrl.type === 'number' || ctrl.type === 'text' || ctrl.type === 'range' || ctrl.type === 'hidden') {
                    value = ctrl.value;
                }
            } else if (ctrl.classList.contains('ts-swatch')) {
                value = ctrl.style.background || ctrl.style.backgroundColor || '#aeb4c2';
            }

            if (value !== undefined) settings[settingKey] = value;
        });

        if (entry && entry._chartPrefs) {
            if (entry._chartPrefs.logScale !== undefined) settings['Log scale'] = !!entry._chartPrefs.logScale;
            if (entry._chartPrefs.autoScale !== undefined) settings['Auto Scale'] = !!entry._chartPrefs.autoScale;
        }
        return settings;
    }

    function syncLegendPreview(settings) {
        var legendBox = _tvScopedById(chartId, 'tvchart-legend-box');
        if (!legendBox) return;
        var titleVisible = settings['Title'] !== false;
        legendBox.style.color = settings['Text-Color'] || '';

        var titleNode = _tvScopedById(chartId, 'tvchart-legend-title');
        if (titleNode) titleNode.style.display = titleVisible ? 'inline-flex' : 'none';
    }

    function scheduleSettingsPreview() {
        if (!entry || !panel) return;
        try {
            var previewSettings = collectSettingsFromPanel();
            _tvApplySettingsToChart(chartId, entry, previewSettings);
            syncLegendPreview(previewSettings);
        } catch (previewErr) {
            console.warn('Settings preview error:', previewErr);
        }
    }

    function persistSettings(settings) {
        if (!entry._chartPrefs) entry._chartPrefs = {};
        entry._chartPrefs.settings = settings;
        entry._chartPrefs.colorBarsBasedOnPrevClose = !!settings['Color bars based on previous close'];
        entry._chartPrefs.bodyVisible = settings['Body'] !== false;
        entry._chartPrefs.bodyUpColor = settings['Body-Up Color'] || _cssVar('--pywry-tvchart-up', '');
        entry._chartPrefs.bodyDownColor = settings['Body-Down Color'] || _cssVar('--pywry-tvchart-down', '');
        entry._chartPrefs.bodyUpOpacity = _tvToNumber(settings['Body-Up Color-Opacity'], _tvToNumber(settings['Body-Opacity'], 100));
        entry._chartPrefs.bodyDownOpacity = _tvToNumber(settings['Body-Down Color-Opacity'], _tvToNumber(settings['Body-Opacity'], 100));
        entry._chartPrefs.bodyOpacity = _tvToNumber(settings['Body-Opacity'], 100);
        entry._chartPrefs.bordersVisible = settings['Borders'] !== false;
        entry._chartPrefs.borderUpColor = settings['Borders-Up Color'] || _cssVar('--pywry-tvchart-border-up', '');
        entry._chartPrefs.borderDownColor = settings['Borders-Down Color'] || _cssVar('--pywry-tvchart-border-down', '');
        entry._chartPrefs.borderUpOpacity = _tvToNumber(settings['Borders-Up Color-Opacity'], _tvToNumber(settings['Borders-Opacity'], 100));
        entry._chartPrefs.borderDownOpacity = _tvToNumber(settings['Borders-Down Color-Opacity'], _tvToNumber(settings['Borders-Opacity'], 100));
        entry._chartPrefs.borderOpacity = _tvToNumber(settings['Borders-Opacity'], 100);
        entry._chartPrefs.wickVisible = settings['Wick'] !== false;
        entry._chartPrefs.wickUpColor = settings['Wick-Up Color'] || _cssVar('--pywry-tvchart-wick-up', '');
        entry._chartPrefs.wickDownColor = settings['Wick-Down Color'] || _cssVar('--pywry-tvchart-wick-down', '');
        entry._chartPrefs.wickUpOpacity = _tvToNumber(settings['Wick-Up Color-Opacity'], _tvToNumber(settings['Wick-Opacity'], 100));
        entry._chartPrefs.wickDownOpacity = _tvToNumber(settings['Wick-Down Color-Opacity'], _tvToNumber(settings['Wick-Opacity'], 100));
        entry._chartPrefs.wickOpacity = _tvToNumber(settings['Wick-Opacity'], 100);
        // Bar-specific
        entry._chartPrefs.barUpColor = settings['Bar Up Color'] || '';
        entry._chartPrefs.barDownColor = settings['Bar Down Color'] || '';
        // Area-specific
        entry._chartPrefs.areaFillTop = settings['Area Fill Top'] || '';
        entry._chartPrefs.areaFillBottom = settings['Area Fill Bottom'] || '';
        // Baseline-specific
        entry._chartPrefs.baselineLevel = _tvToNumber(settings['Baseline Level'], 0);
        entry._chartPrefs.baselineTopLine = settings['Baseline Top Line'] || '';
        entry._chartPrefs.baselineBottomLine = settings['Baseline Bottom Line'] || '';
        entry._chartPrefs.baselineTopFill1 = settings['Baseline Top Fill 1'] || '';
        entry._chartPrefs.baselineTopFill2 = settings['Baseline Top Fill 2'] || '';
        entry._chartPrefs.baselineBottomFill1 = settings['Baseline Bottom Fill 1'] || '';
        entry._chartPrefs.baselineBottomFill2 = settings['Baseline Bottom Fill 2'] || '';
        entry._chartPrefs.session = settings['Session'] || 'Regular trading hours';
        entry._chartPrefs.precision = settings['Precision'] || 'Default';
        entry._chartPrefs.timezone = settings['Timezone'] || 'UTC';
        entry._chartPrefs.description = settings['Description'] || 'Description';
        entry._chartPrefs.showLogo = settings['Logo'] !== false;
        entry._chartPrefs.showTitle = settings['Title'] !== false;
        entry._chartPrefs.showChartValues = settings['Chart values'] !== false;
        entry._chartPrefs.showBarChange = settings['Bar change values'] !== false;
        entry._chartPrefs.showVolume = settings['Volume'] !== false;
        entry._chartPrefs.showIndicatorTitles = settings['Titles'] !== false;
        entry._chartPrefs.showIndicatorInputs = settings['Inputs'] !== false;
        entry._chartPrefs.showIndicatorValues = settings['Values'] !== false;
        if (settings['Log scale'] !== undefined) entry._chartPrefs.logScale = !!settings['Log scale'];
        if (settings['Auto Scale'] !== undefined) entry._chartPrefs.autoScale = !!settings['Auto Scale'];
        entry._chartPrefs.backgroundEnabled = settings['Background-Enabled'] !== false;
        entry._chartPrefs.backgroundOpacity = _tvToNumber(settings['Background-Opacity'], 50);
        entry._chartPrefs.lineColor = settings['Line color'] || _cssVar('--pywry-tvchart-up', '');
        entry._chartPrefs.scaleModesVisibility = settings['Scale modes (A and L)'] || 'Visible on mouse over';
        entry._chartPrefs.lockPriceToBarRatio = !!settings['Lock price to bar ratio'];
        entry._chartPrefs.lockPriceToBarRatioValue = _tvToNumber(settings['Lock price to bar ratio (value)'], 0.018734);
        entry._chartPrefs.scalesPlacement = settings['Scales placement'] || 'Auto';
        entry._chartPrefs.noOverlappingLabels = settings['No overlapping labels'] !== false;
        entry._chartPrefs.plusButton = !!settings['Plus button'];
        entry._chartPrefs.countdownToBarClose = !!settings['Countdown to bar close'];
        entry._chartPrefs.symbolMode = settings['Symbol'] || 'Value, line';
        entry._chartPrefs.symbolColor = settings['Symbol color'] || _cssVar('--pywry-tvchart-up', '');
        entry._chartPrefs.valueAccordingToScale = settings['Value according to scale'] || settings['Value according to sc...'] || 'Value according to scale';
        entry._chartPrefs.indicatorsAndFinancials = settings['Indicators and financials'] || 'Value';
        entry._chartPrefs.highAndLow = settings['High and low'] || 'Hidden';
        entry._chartPrefs.highAndLowColor = settings['High and low color'] || _cssVar('--pywry-tvchart-down');
        entry._chartPrefs.dayOfWeekOnLabels = settings['Day of week on labels'] !== false;
        entry._chartPrefs.dateFormat = settings['Date format'] || 'Mon 29 Sep \'97';
        entry._chartPrefs.timeHoursFormat = settings['Time hours format'] || '24-hours';
        entry._chartPrefs.gridVisible = settings['Grid lines'] !== 'Hidden';
        entry._chartPrefs.gridMode = settings['Grid lines'] || 'Vert and horz';
        entry._chartPrefs.gridColor = settings['Grid-Color'] || _cssVar('--pywry-tvchart-grid');
        entry._chartPrefs.paneSeparatorsColor = settings['Pane-Separators-Color'] || _cssVar('--pywry-tvchart-grid');
        entry._chartPrefs.backgroundColor = settings['Background-Color'] || _cssVar('--pywry-tvchart-bg');
        entry._chartPrefs.crosshairEnabled = settings['Crosshair-Enabled'] === true;
        entry._chartPrefs.crosshairColor = settings['Crosshair-Color'] || _cssVar('--pywry-tvchart-crosshair-color');
        entry._chartPrefs.watermarkVisible = settings['Watermark'] === 'Visible';
        entry._chartPrefs.watermarkColor = settings['Watermark-Color'] || 'rgba(255,255,255,0.08)';
        entry._chartPrefs.textColor = settings['Text-Color'] || _cssVar('--pywry-tvchart-text');
        entry._chartPrefs.linesColor = settings['Lines-Color'] || _cssVar('--pywry-tvchart-grid');
        entry._chartPrefs.navigation = settings['Navigation'] || 'Visible on mouse over';
        entry._chartPrefs.pane = settings['Pane'] || 'Visible on mouse over';
        entry._chartPrefs.marginTop = _tvToNumber(settings['Margin Top'], 10);
        entry._chartPrefs.marginBottom = _tvToNumber(settings['Margin Bottom'], 8);
    }

    function applySettingsToPanel(nextSettings) {
        if (!panel || !nextSettings || typeof nextSettings !== 'object') return;

        var allControls = panel.querySelectorAll('[data-setting]');
        allControls.forEach(function(ctrl) {
            var key = ctrl.getAttribute('data-setting');
            if (!key || nextSettings[key] === undefined) return;
            var value = nextSettings[key];
            if (ctrl.tagName === 'SELECT') {
                ctrl.value = String(value);
            } else if (ctrl.tagName === 'INPUT') {
                if (ctrl.type === 'checkbox') {
                    ctrl.checked = !!value;
                } else {
                    ctrl.value = String(value);
                }
            }
        });

        var swatches = panel.querySelectorAll('.ts-swatch[data-setting]');
        swatches.forEach(function(swatch) {
            var key = swatch.getAttribute('data-setting');
            if (!key || nextSettings[key] === undefined) return;
            var colorVal = nextSettings[key];
            var opacityKey = key + '-Opacity';
            if (nextSettings[opacityKey] !== undefined) {
                syncSettingsSwatch(swatch, colorVal, nextSettings[opacityKey]);
            } else {
                var nextHex = _tvColorToHex(colorVal || swatch.style.background || '#aeb4c2', '#aeb4c2');
                swatch.dataset.baseColor = nextHex;
                swatch.style.background = nextHex;
            }

            var swParent = swatch.parentNode;
            if (swParent && swParent.querySelector) {
                var colorInput = swParent.querySelector('input.ts-hidden-color-input[type="color"]');
                if (colorInput) {
                    colorInput.value = _tvColorToHex(swatch.dataset.baseColor || swatch.style.background, '#aeb4c2');
                }
            }
        });

        var sliders = panel.querySelectorAll('.tv-settings-slider');
        sliders.forEach(function(slider) {
            var out = slider.parentNode && slider.parentNode.querySelector('.tv-settings-slider-value');
            if (out) out.textContent = slider.value + '%';
        });

        scheduleSettingsPreview();
    }

    var factoryTemplate = _tvBuildCurrentSettings({
        chartId: chartId,
        theme: entry && entry.theme,
        _chartPrefs: {},
        volumeMap: (entry && entry.volumeMap && entry.volumeMap.main) ? { main: {} } : {},
        seriesMap: {},
    });

    function cloneSettings(settingsObj) {
        try {
            return JSON.parse(JSON.stringify(settingsObj || {}));
        } catch (e) {
            return {};
        }
    }

    function getResolvedTemplateId() {
        var preferred = _tvLoadSettingsDefaultTemplateId(chartId);
        if (preferred === 'custom' && !_tvLoadCustomSettingsTemplate(chartId)) {
            _tvSaveSettingsDefaultTemplateId('factory', chartId);
            return 'factory';
        }
        return preferred;
    }
    
    var templateWrap = document.createElement('div');
    templateWrap.className = 'tv-settings-template-wrap';
    var templateBtn = document.createElement('button');
    templateBtn.className = 'ts-btn-template';
    templateBtn.type = 'button';
    templateBtn.textContent = 'Template';
    templateWrap.appendChild(templateBtn);

    var templateMenu = null;

    function closeTemplateMenu() {
        if (templateMenu && templateMenu.parentNode) {
            templateMenu.parentNode.removeChild(templateMenu);
        }
        templateMenu = null;
    }

    function updateTemplateDefaultBadges(menuEl) {
        if (!menuEl) return;
        var activeId = getResolvedTemplateId();
        var defaultItems = menuEl.querySelectorAll('.tv-settings-template-item[data-template-default]');
        defaultItems.forEach(function(item) {
            var itemId = item.getAttribute('data-template-default');
            var isActive = itemId === activeId;
            item.classList.toggle('active-default', isActive);
            var badge = item.querySelector('.tv-settings-template-badge');
            if (badge) badge.style.visibility = isActive ? 'visible' : 'hidden';
        });
    }

    function openTemplateMenu() {
        closeTemplateMenu();
        var customTemplate = _tvLoadCustomSettingsTemplate(chartId);
        var activeDefaultId = getResolvedTemplateId();

        var menu = document.createElement('div');
        menu.className = 'tv-settings-template-menu';

        var applyItem = document.createElement('button');
        applyItem.type = 'button';
        applyItem.className = 'tv-settings-template-item';
        applyItem.textContent = 'Apply default template';
        applyItem.addEventListener('click', function() {
            var resolvedDefault = getResolvedTemplateId();
            var chosen = resolvedDefault === 'custom' ? (_tvLoadCustomSettingsTemplate(chartId) || factoryTemplate) : factoryTemplate;
            applySettingsToPanel(cloneSettings(chosen));
            _tvNotify('success', 'Template applied.', 'Settings', chartId);
            closeTemplateMenu();
        });
        menu.appendChild(applyItem);

        var sep = document.createElement('div');
        sep.className = 'tv-settings-template-sep';
        menu.appendChild(sep);

        function makeDefaultItem(label, templateId, disabled) {
            var item = document.createElement('button');
            item.type = 'button';
            item.className = 'tv-settings-template-item';
            item.setAttribute('data-template-default', templateId);
            if (disabled) item.disabled = true;
            var text = document.createElement('span');
            text.textContent = label;
            item.appendChild(text);
            var badge = document.createElement('span');
            badge.className = 'tv-settings-template-badge';
            badge.textContent = 'default';
            badge.style.visibility = templateId === activeDefaultId ? 'visible' : 'hidden';
            item.appendChild(badge);
            item.addEventListener('click', function() {
                _tvSaveSettingsDefaultTemplateId(templateId, chartId);
                updateTemplateDefaultBadges(menu);
            });
            return item;
        }

        menu.appendChild(makeDefaultItem('Use TradingView defaults', 'factory', false));
        menu.appendChild(makeDefaultItem('Use saved custom default', 'custom', !customTemplate));

        var saveCurrent = document.createElement('button');
        saveCurrent.type = 'button';
        saveCurrent.className = 'tv-settings-template-item';
        saveCurrent.textContent = 'Save current as custom default';
        saveCurrent.addEventListener('click', function() {
            var settings = collectSettingsFromPanel();
            _tvSaveCustomSettingsTemplate(cloneSettings(settings), chartId);
            _tvSaveSettingsDefaultTemplateId('custom', chartId);
            updateTemplateDefaultBadges(menu);
            var customDefaultRow = menu.querySelector('[data-template-default="custom"]');
            if (customDefaultRow) customDefaultRow.disabled = false;
            _tvNotify('success', 'Saved custom default template.', 'Settings', chartId);
        });
        menu.appendChild(saveCurrent);

        var clearCustom = document.createElement('button');
        clearCustom.type = 'button';
        clearCustom.className = 'tv-settings-template-item';
        clearCustom.textContent = 'Clear custom default';
        clearCustom.disabled = !customTemplate;
        clearCustom.addEventListener('click', function() {
            _tvClearCustomSettingsTemplate(chartId);
            if (_tvLoadSettingsDefaultTemplateId(chartId) === 'custom') {
                _tvSaveSettingsDefaultTemplateId('factory', chartId);
            }
            var customDefaultRow = menu.querySelector('[data-template-default="custom"]');
            if (customDefaultRow) customDefaultRow.disabled = true;
            clearCustom.disabled = true;
            updateTemplateDefaultBadges(menu);
            _tvNotify('success', 'Cleared custom default template.', 'Settings', chartId);
        });
        menu.appendChild(clearCustom);

        templateMenu = menu;
        templateWrap.appendChild(menu);
        updateTemplateDefaultBadges(menu);
    }

    templateBtn.addEventListener('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        if (templateMenu) {
            closeTemplateMenu();
        } else {
            openTemplateMenu();
        }
    });

    overlay.addEventListener('mousedown', function(e) {
        if (templateMenu && templateWrap && !templateWrap.contains(e.target)) {
            closeTemplateMenu();
        }
    });

    footer.appendChild(templateWrap);

    var cancelBtn = document.createElement('button');
    cancelBtn.className = 'ts-btn-cancel';
    cancelBtn.addEventListener('click', function() {
        closeTemplateMenu();
        _tvApplySettingsToChart(chartId, entry, originalSettings);
        syncLegendPreview(originalSettings);
        _tvHideChartSettings();
    });
    cancelBtn.textContent = 'Cancel';
    footer.appendChild(cancelBtn);

    var okBtn = document.createElement('button');
    okBtn.className = 'ts-btn-ok';
    okBtn.addEventListener('click', function() {
        if (!entry || !panel) return;
        try {
            closeTemplateMenu();
            var settings = collectSettingsFromPanel();
            persistSettings(settings);
            _tvApplySettingsToChart(chartId, entry, settings);
            syncLegendPreview(settings);

            // Sync session mode from chart settings to bottom bar
            var sessionSetting = settings['Session'] || 'Extended trading hours';
            var newMode = sessionSetting.indexOf('Regular') >= 0 ? 'RTH' : 'ETH';
            if (entry._sessionMode !== newMode) {
                entry._sessionMode = newMode;
                var sBtn = document.getElementById('tvchart-session-btn');
                if (sBtn) {
                    var sLbl = sBtn.querySelector('.tvchart-bottom-btn-label');
                    if (sLbl) sLbl.textContent = newMode;
                    sBtn.classList.toggle('active', newMode === 'RTH');
                }
            }

            // Re-apply bottom bar timezone (takes precedence over chart settings' UTC/Local)
            if (typeof _tvGetActiveTimezone === 'function' && typeof _tvApplyTimezoneToChart === 'function') {
                var activeTz = _tvGetActiveTimezone();
                if (entry._selectedTimezone && entry._selectedTimezone !== 'exchange') {
                    _tvApplyTimezoneToChart(entry, activeTz);
                }
            }

            console.log('Chart settings applied:', settings);
        } catch(err) {
            console.warn('Settings apply error:', err);
        }
        _tvHideChartSettings();
    });
    okBtn.textContent = 'Ok';
    footer.appendChild(okBtn);

    panel.appendChild(footer);
    panel.addEventListener('input', function(e) {
        var target = e.target;
        if (!target) return;
        if (target.tagName === 'INPUT' || target.tagName === 'SELECT') scheduleSettingsPreview();
    });
    panel.addEventListener('change', function(e) {
        var target = e.target;
        if (!target) return;
        if (target.tagName === 'INPUT' || target.tagName === 'SELECT') scheduleSettingsPreview();
    });

    _tvOverlayContainer(chartId).appendChild(overlay);
}

// ---------------------------------------------------------------------------
// Normalize a raw symbol item (from search/resolve) into a consistent shape.
// Shared by compare panel and indicator symbol picker.
// ---------------------------------------------------------------------------
function _tvNormalizeSymbolInfo(item) {
    if (!item || typeof item !== 'object') return null;
    var symbol = String(item.symbol || item.ticker || '').trim();
    if (!symbol) return null;
    var ticker = String(item.ticker || '').trim().toUpperCase();
    if (!ticker) {
        ticker = symbol.indexOf(':') >= 0 ? symbol.split(':').pop().trim().toUpperCase() : symbol.toUpperCase();
    }
    var fullName = String(item.fullName || item.full_name || '').trim();
    var description = String(item.description || '').trim();
    var exchange = String(item.exchange || item.listedExchange || item.listed_exchange || '').trim();
    var symbolType = String(item.type || item.symbolType || item.symbol_type || '').trim();
    var currency = String(item.currency || item.currencyCode || item.currency_code || '').trim();
    return {
        symbol: symbol,
        ticker: ticker,
        displaySymbol: ticker || symbol,
        requestSymbol: ticker || symbol,
        fullName: fullName,
        description: description,
        exchange: exchange,
        type: symbolType,
        currency: currency,
        pricescale: item.pricescale,
        minmov: item.minmov,
        timezone: item.timezone,
        session: item.session,
    };
}

