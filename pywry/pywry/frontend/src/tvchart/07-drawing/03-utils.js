function _tvClamp(v, min, max) {
    if (v < min) return min;
    if (v > max) return max;
    return v;
}

function _tvToNumber(v, fallback) {
    var n = Number(v);
    return isFinite(n) ? n : fallback;
}

function _tvColorToHex(color, fallback) {
    if (!color || typeof color !== 'string') return fallback || '#aeb4c2';
    var c = color.trim();
    if (/^#[0-9a-f]{6}$/i.test(c)) return c;
    if (/^#[0-9a-f]{3}$/i.test(c)) {
        return '#' + c[1] + c[1] + c[2] + c[2] + c[3] + c[3];
    }
    var m = c.match(/rgba?\s*\(([^)]+)\)/i);
    if (!m) return fallback || '#aeb4c2';
    var parts = m[1].split(',');
    if (parts.length < 3) return fallback || '#aeb4c2';
    var r = _tvClamp(Math.round(_tvToNumber(parts[0], 0)), 0, 255);
    var g = _tvClamp(Math.round(_tvToNumber(parts[1], 0)), 0, 255);
    var b = _tvClamp(Math.round(_tvToNumber(parts[2], 0)), 0, 255);
    var hex = '#';
    var vals = [r, g, b];
    for (var i = 0; i < vals.length; i++) {
        var h = vals[i].toString(16);
        if (h.length < 2) h = '0' + h;
        hex += h;
    }
    return hex;
}

function _tvColorOpacityPercent(color, fallback) {
    if (!color || typeof color !== 'string') return fallback != null ? fallback : 100;
    var m = color.trim().match(/rgba\s*\(([^)]+)\)/i);
    if (!m) return fallback != null ? fallback : 100;
    var parts = m[1].split(',');
    if (parts.length < 4) return fallback != null ? fallback : 100;
    var alpha = _tvClamp(_tvToNumber(parts[3], 1), 0, 1);
    return Math.round(alpha * 100);
}

function _tvColorWithOpacity(color, opacityPercent, fallback) {
    var baseHex = _tvColorToHex(color, fallback || '#aeb4c2');
    var rgb = _hexToRgb(baseHex);
    var alpha = _tvClamp(_tvToNumber(opacityPercent, 100), 0, 100) / 100;
    return 'rgba(' + rgb[0] + ', ' + rgb[1] + ', ' + rgb[2] + ', ' + alpha.toFixed(2) + ')';
}

function _tvHexToRgba(color, alpha) {
    var hex = _tvColorToHex(color, '#aeb4c2');
    var rgb = _hexToRgb(hex);
    var a = typeof alpha === 'number' ? alpha : 1;
    return 'rgba(' + rgb[0] + ', ' + rgb[1] + ', ' + rgb[2] + ', ' + a.toFixed(2) + ')';
}

function _tvLineStyleFromName(name) {
    if (name === 'Dashed') return 2;
    if (name === 'Dotted') return 1;
    return 0;
}

function _tvGetMainSeries(entry) {
    if (!entry || !entry.seriesMap) return null;
    var keys = Object.keys(entry.seriesMap);
    if (!keys.length) return null;
    return entry.seriesMap[keys[0]];
}

function _tvBuildCurrentSettings(entry) {
    var mainSeries = _tvGetMainSeries(entry);
    var mainOpts = {};
    try {
        if (mainSeries && typeof mainSeries.options === 'function') {
            mainOpts = mainSeries.options() || {};
        }
    } catch (e) {
        mainOpts = {};
    }

    var prefs = entry && entry._chartPrefs ? entry._chartPrefs : {};
    var intervalEl = _tvScopedById(entry && entry.chartId ? entry.chartId : null, 'tvchart-interval-label');
    var hasVolume = !!(entry && entry.volumeMap && entry.volumeMap.main);
    // In datafeed mode, volume loads asynchronously — default to true
    if (!hasVolume && entry && entry.payload && entry.payload.useDatafeed) {
        hasVolume = true;
    }
    var palette = TVCHART_THEMES._get((entry && entry.theme) || _tvDetectTheme());

    return {
        'Color bars based on previous close': !!prefs.colorBarsBasedOnPrevClose,
        'Body': prefs.bodyVisible !== false,
        'Body-Up Color': prefs.bodyUpColor || mainOpts.upColor || palette.upColor,
        'Body-Down Color': prefs.bodyDownColor || mainOpts.downColor || palette.downColor,
        'Body-Up Color-Opacity': prefs.bodyUpOpacity != null ? String(prefs.bodyUpOpacity) : String(_tvColorOpacityPercent(mainOpts.upColor || palette.upColor, prefs.bodyOpacity != null ? prefs.bodyOpacity : 100)),
        'Body-Down Color-Opacity': prefs.bodyDownOpacity != null ? String(prefs.bodyDownOpacity) : String(_tvColorOpacityPercent(mainOpts.downColor || palette.downColor, prefs.bodyOpacity != null ? prefs.bodyOpacity : 100)),
        'Body-Opacity': prefs.bodyOpacity != null ? String(prefs.bodyOpacity) : String(_tvColorOpacityPercent(mainOpts.upColor || palette.upColor, 100)),
        'Borders': prefs.bordersVisible !== false,
        'Borders-Up Color': prefs.borderUpColor || mainOpts.borderUpColor || palette.borderUpColor,
        'Borders-Down Color': prefs.borderDownColor || mainOpts.borderDownColor || palette.borderDownColor,
        'Borders-Up Color-Opacity': prefs.borderUpOpacity != null ? String(prefs.borderUpOpacity) : String(_tvColorOpacityPercent(mainOpts.borderUpColor || palette.borderUpColor, prefs.borderOpacity != null ? prefs.borderOpacity : 100)),
        'Borders-Down Color-Opacity': prefs.borderDownOpacity != null ? String(prefs.borderDownOpacity) : String(_tvColorOpacityPercent(mainOpts.borderDownColor || palette.borderDownColor, prefs.borderOpacity != null ? prefs.borderOpacity : 100)),
        'Borders-Opacity': prefs.borderOpacity != null ? String(prefs.borderOpacity) : String(_tvColorOpacityPercent(mainOpts.borderUpColor || palette.borderUpColor, 100)),
        'Wick': prefs.wickVisible !== false,
        'Wick-Up Color': prefs.wickUpColor || mainOpts.wickUpColor || palette.wickUpColor,
        'Wick-Down Color': prefs.wickDownColor || mainOpts.wickDownColor || palette.wickDownColor,
        'Wick-Up Color-Opacity': prefs.wickUpOpacity != null ? String(prefs.wickUpOpacity) : String(_tvColorOpacityPercent(mainOpts.wickUpColor || palette.wickUpColor, prefs.wickOpacity != null ? prefs.wickOpacity : 100)),
        'Wick-Down Color-Opacity': prefs.wickDownOpacity != null ? String(prefs.wickDownOpacity) : String(_tvColorOpacityPercent(mainOpts.wickDownColor || palette.wickDownColor, prefs.wickOpacity != null ? prefs.wickOpacity : 100)),
        'Wick-Opacity': prefs.wickOpacity != null ? String(prefs.wickOpacity) : String(_tvColorOpacityPercent(mainOpts.wickUpColor || palette.wickUpColor, 100)),
        // Bar-specific
        'Bar Up Color': prefs.barUpColor || mainOpts.upColor || palette.upColor,
        'Bar Down Color': prefs.barDownColor || mainOpts.downColor || palette.downColor,
        // Area-specific
        'Area Fill Top': prefs.areaFillTop || mainOpts.topColor || 'rgba(38, 166, 154, 0.4)',
        'Area Fill Bottom': prefs.areaFillBottom || mainOpts.bottomColor || 'rgba(38, 166, 154, 0)',
        // Baseline-specific
        'Baseline Level': prefs.baselineLevel != null ? String(prefs.baselineLevel) : String((mainOpts.baseValue && mainOpts.baseValue.price) || 0),
        'Baseline Top Line': prefs.baselineTopLine || mainOpts.topLineColor || palette.upColor,
        'Baseline Bottom Line': prefs.baselineBottomLine || mainOpts.bottomLineColor || palette.downColor,
        'Baseline Top Fill 1': prefs.baselineTopFill1 || mainOpts.topFillColor1 || 'rgba(38, 166, 154, 0.28)',
        'Baseline Top Fill 2': prefs.baselineTopFill2 || mainOpts.topFillColor2 || 'rgba(38, 166, 154, 0.05)',
        'Baseline Bottom Fill 1': prefs.baselineBottomFill1 || mainOpts.bottomFillColor1 || 'rgba(239, 83, 80, 0.05)',
        'Baseline Bottom Fill 2': prefs.baselineBottomFill2 || mainOpts.bottomFillColor2 || 'rgba(239, 83, 80, 0.28)',
        'Session': prefs.session || 'Regular trading hours',
        'Precision': prefs.precision || 'Default',
        'Timezone': prefs.timezone || 'UTC',
        'Logo': prefs.showLogo !== undefined ? prefs.showLogo : false,
        'Title': prefs.showTitle !== undefined ? prefs.showTitle : true,
        'Description': prefs.description || 'Description',
        'Chart values': prefs.showChartValues !== undefined ? prefs.showChartValues : true,
        'Bar change values': prefs.showBarChange !== undefined ? prefs.showBarChange : true,
        'Volume': prefs.showVolume !== undefined ? prefs.showVolume : hasVolume,
        'Titles': prefs.showIndicatorTitles !== undefined ? prefs.showIndicatorTitles : true,
        'Inputs': prefs.showIndicatorInputs !== undefined ? prefs.showIndicatorInputs : true,
        'Values': prefs.showIndicatorValues !== undefined ? prefs.showIndicatorValues : true,
        'Background-Enabled': prefs.backgroundEnabled !== false,
        'Background-Opacity': prefs.backgroundOpacity != null ? String(prefs.backgroundOpacity) : '50',
        'Line style': mainOpts.lineStyle === 2 ? 'Dashed' : (mainOpts.lineStyle === 1 ? 'Dotted' : 'Solid'),
        'Line width': String(mainOpts.lineWidth || 1),
        'Line color': mainOpts.color || mainOpts.lineColor || prefs.lineColor || _cssVar('--pywry-tvchart-up', ''),
        'Scale modes (A and L)': prefs.scaleModesVisibility || 'Visible on mouse over',
        'Lock price to bar ratio': !!prefs.lockPriceToBarRatio,
        'Lock price to bar ratio (value)': prefs.lockPriceToBarRatioValue != null ? String(prefs.lockPriceToBarRatioValue) : '0.018734',
        'Scales placement': prefs.scalesPlacement || 'Auto',
        'No overlapping labels': prefs.noOverlappingLabels !== false,
        'Plus button': !!prefs.plusButton,
        'Countdown to bar close': !!prefs.countdownToBarClose,
        'Symbol': prefs.symbolMode || (function() {
            var pv = mainOpts.priceLineVisible !== false;
            var lv = mainOpts.lastValueVisible !== false;
            if (pv && lv) return 'Value, line';
            if (pv && !lv) return 'Line';
            if (!pv && lv) return 'Label';
            return 'Hidden';
        })(),
        'Symbol color': prefs.symbolColor || mainOpts.color || mainOpts.lineColor || _cssVar('--pywry-tvchart-up', ''),
        'Value according to scale': prefs.valueAccordingToScale || 'Value according to scale',
        'Value according to sc...': prefs.valueAccordingToScale || 'Value according to scale',
        'Indicators and financials': prefs.indicatorsAndFinancials || 'Value',
        'High and low': prefs.highAndLow || 'Hidden',
        'High and low color': prefs.highAndLowColor || _cssVar('--pywry-tvchart-down', ''),
        'Day of week on labels': prefs.dayOfWeekOnLabels !== false,
        'Date format': prefs.dateFormat || 'Mon 29 Sep \'97',
        'Time hours format': prefs.timeHoursFormat || '24-hours',
        'Background': 'Solid',
        'Background-Color': prefs.backgroundColor || palette.background,
        'Grid lines': prefs.gridVisible === false ? 'Hidden' : (prefs.gridMode || 'Vert and horz'),
        'Grid-Color': prefs.gridColor || _cssVar('--pywry-tvchart-grid'),
        'Pane-Separators-Color': prefs.paneSeparatorsColor || _cssVar('--pywry-tvchart-grid'),
        'Crosshair-Enabled': prefs.crosshairEnabled === true,
        'Crosshair-Color': prefs.crosshairColor || _cssVar('--pywry-tvchart-crosshair-color'),
        'Watermark': prefs.watermarkVisible ? 'Visible' : 'Hidden',
        'Watermark-Color': prefs.watermarkColor || 'rgba(255,255,255,0.08)',
        'Text-Color': prefs.textColor || _cssVar('--pywry-tvchart-text'),
        'Lines-Color': prefs.linesColor || _cssVar('--pywry-tvchart-grid'),
        'Navigation': prefs.navigation || 'Visible on mouse over',
        'Pane': prefs.pane || 'Visible on mouse over',
        'Margin Top': prefs.marginTop != null ? String(prefs.marginTop) : '10',
        'Margin Bottom': prefs.marginBottom != null ? String(prefs.marginBottom) : '8',
        'Interval': intervalEl ? (intervalEl.textContent || '').trim() : '',
    };
}

