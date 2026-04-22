function _tvSetToolbarVisibility(settings, chartId) {
    var leftToolbar = _tvScopedQuery(chartId, '.tvchart-left');
    var bottomToolbar = _tvScopedQuery(chartId, '.tvchart-bottom');
    if (leftToolbar) {
        leftToolbar.style.display = settings['Navigation'] === 'Hidden' ? 'none' : '';
    }
    if (bottomToolbar) {
        bottomToolbar.style.display = settings['Pane'] === 'Hidden' ? 'none' : '';
    }

    var autoScaleEl = _tvScopedQuery(chartId, '[data-component-id="tvchart-auto-scale"]');
    var logScaleEl = _tvScopedQuery(chartId, '[data-component-id="tvchart-log-scale"]');
    var pctScaleEl = _tvScopedQuery(chartId, '[data-component-id="tvchart-pct-scale"]');
    var showScaleButtons = settings['Scale modes (A and L)'] !== 'Hidden';
    if (autoScaleEl) autoScaleEl.style.display = showScaleButtons ? '' : 'none';
    if (logScaleEl) logScaleEl.style.display = showScaleButtons ? '' : 'none';
    if (pctScaleEl) pctScaleEl.style.display = showScaleButtons ? '' : 'none';
}

function _tvApplySettingsToChart(chartId, entry, settings, opts) {
    if (!entry || !entry.chart) return;
    opts = opts || {};

    var chartOptions = {};
    var rightPriceScale = {};
    var leftPriceScale = {};
    var timeScale = {};
    var localization = {};

    // Canvas: grid visibility
    var gridMode = settings['Grid lines'] || 'Vert and horz';
    var gridColor = settings['Grid-Color'] || settings['Lines-Color'] || undefined;
    chartOptions.grid = {
        vertLines: {
            visible: gridMode === 'Vert and horz' || gridMode === 'Vert only',
            color: gridColor,
        },
        horzLines: {
            visible: gridMode === 'Vert and horz' || gridMode === 'Horz only',
            color: gridColor,
        },
    };

    // Canvas: background + text + crosshair
    var bgOpacity = _tvClamp(_tvToNumber(settings['Background-Opacity'], 50), 0, 100) / 100;
    var bgEnabled = settings['Background-Enabled'] !== false;
    var _bgPalette = TVCHART_THEMES._get((entry && entry.theme) || _tvDetectTheme());
    var bgColor = settings['Background-Color'] || _bgPalette.background;
    // Apply opacity to background color
    var bgHex = _tvColorToHex(bgColor, _bgPalette.background);
    var bgFinal = bgEnabled ? _tvColorWithOpacity(bgHex, bgOpacity * 100, bgHex) : 'transparent';
    chartOptions.layout = {
        attributionLogo: false,
        textColor: settings['Text-Color'] || undefined,
        background: {
            type: 'solid',
            color: bgFinal,
        },
    };

    var _chEn = settings['Crosshair-Enabled'] === true;
    chartOptions.crosshair = {
        mode: LightweightCharts.CrosshairMode.Normal,
        vertLine: {
            color: settings['Crosshair-Color'] || undefined,
            visible: _chEn,
            labelVisible: true,
            style: 2,
            width: 1,
        },
        horzLine: {
            color: settings['Crosshair-Color'] || undefined,
            visible: _chEn,
            labelVisible: _chEn,
            style: 2,
            width: 1,
        },
    };

    // Status/scales — apply same config to both sides
    var scaleAutoScale = settings['Auto Scale'] !== false;
    var scaleMode = settings['Log scale'] === true ? 1 : 0;
    var scaleAlignLabels = settings['No overlapping labels'] !== false;
    var scaleTextColor = settings['Text-Color'] || undefined;
    var scaleBorderColor = settings['Lines-Color'] || undefined;

    rightPriceScale.autoScale = scaleAutoScale;
    rightPriceScale.mode = scaleMode;
    rightPriceScale.alignLabels = scaleAlignLabels;
    rightPriceScale.textColor = scaleTextColor;
    rightPriceScale.borderColor = scaleBorderColor;

    leftPriceScale.autoScale = scaleAutoScale;
    leftPriceScale.mode = scaleMode;
    leftPriceScale.alignLabels = scaleAlignLabels;
    leftPriceScale.textColor = scaleTextColor;
    leftPriceScale.borderColor = scaleBorderColor;

    var topMargin = _tvClamp(_tvToNumber(settings['Margin Top'], 10), 0, 90) / 100;
    var bottomMargin = _tvClamp(_tvToNumber(settings['Margin Bottom'], 8), 0, 90) / 100;
    if (entry.volumeMap && entry.volumeMap.main) {
        bottomMargin = Math.max(bottomMargin, 0.14);
    }
    rightPriceScale.scaleMargins = { top: topMargin, bottom: bottomMargin };
    leftPriceScale.scaleMargins = { top: topMargin, bottom: bottomMargin };

    if (settings['Lock price to bar ratio']) {
        var ratio = _tvClamp(_tvToNumber(settings['Lock price to bar ratio (value)'], 0.018734), 0.001, 0.95);
        var lockedMargins = {
            top: _tvClamp(ratio, 0.0, 0.9),
            bottom: _tvClamp(1 - ratio - 0.05, 0.0, 0.9),
        };
        rightPriceScale.autoScale = false;
        rightPriceScale.scaleMargins = lockedMargins;
        leftPriceScale.autoScale = false;
        leftPriceScale.scaleMargins = lockedMargins;
    }

    var placement = settings['Scales placement'] || 'Auto';
    if (placement === 'Left') {
        leftPriceScale.visible = true;
        rightPriceScale.visible = false;
    } else if (placement === 'Right') {
        leftPriceScale.visible = false;
        rightPriceScale.visible = true;
    } else {
        leftPriceScale.visible = false;
        rightPriceScale.visible = true;
    }

    timeScale.borderColor = settings['Lines-Color'] || undefined;
    timeScale.secondsVisible = false;
    // Daily+ charts should never show time on the x-axis
    var _resIsDaily = (function() {
        var r = entry._currentResolution || '';
        return /^[1-9]?[DWM]$/.test(r) || /^\d+[DWM]$/.test(r);
    })();

    // Skip timeVisible and localization overrides when the datafeed already
    // set timezone-aware formatters (deferred re-apply after series creation).
    if (!opts.skipLocalization) {
        timeScale.timeVisible = !_resIsDaily;

        var showDOW = settings['Day of week on labels'] !== false;
        var use24h = (settings['Time hours format'] || '24-hours') === '24-hours';
        var dateFmt = settings['Date format'] || 'Mon 29 Sep \'97';
        var useUTC = (settings['Timezone'] || 'UTC') === 'UTC';
        localization.timeFormatter = function(t) {
        var d;
        if (typeof t === 'number') {
            d = new Date(t * 1000);
        } else if (t && typeof t.year === 'number') {
            d = useUTC
                ? new Date(Date.UTC(t.year, (t.month || 1) - 1, t.day || 1))
                : new Date(t.year, (t.month || 1) - 1, t.day || 1);
        } else {
            return '';
        }
        var days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
        var monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        var month = useUTC ? d.getUTCMonth() : d.getMonth();
        var day = useUTC ? d.getUTCDate() : d.getDate();
        var year = useUTC ? d.getUTCFullYear() : d.getFullYear();
        var hour = useUTC ? d.getUTCHours() : d.getHours();
        var minute = useUTC ? d.getUTCMinutes() : d.getMinutes();
        var weekDay = useUTC ? d.getUTCDay() : d.getDay();
        var mm = String(month + 1);
        var dd = String(day);
        var yyyy = String(year);
        var yy = yyyy.slice(-2);
        var hours = use24h ? hour : ((hour % 12) || 12);
        var mins = String(minute).padStart(2, '0');
        var ampm = hour >= 12 ? ' PM' : ' AM';
        var time = use24h ? String(hours).padStart(2, '0') + ':' + mins : String(hours) + ':' + mins + ampm;
        var datePart;
        if (dateFmt === 'MM/DD/YY') {
            datePart = mm.padStart(2, '0') + '/' + dd.padStart(2, '0') + '/' + yy;
        } else if (dateFmt === 'DD/MM/YY') {
            datePart = dd.padStart(2, '0') + '/' + mm.padStart(2, '0') + '/' + yy;
        } else {
            datePart = dd.padStart(2, '0') + ' ' + monthNames[month] + " '" + yy;
        }
        if (_resIsDaily) {
            return (showDOW ? (days[weekDay] + ' ') : '') + datePart;
        }
        return (showDOW ? (days[weekDay] + ' ') : '') + datePart + ' ' + time;
    };
    } // end skipLocalization guard
    chartOptions.rightPriceScale = rightPriceScale;
    chartOptions.leftPriceScale = leftPriceScale;
    chartOptions.timeScale = timeScale;
    chartOptions.localization = localization;
    chartOptions = _tvMerge(chartOptions, _tvInteractiveNavigationOptions());

    // Watermark
    var wmColor = settings['Watermark-Color'] || 'rgba(255,255,255,0.08)';
    chartOptions.watermark = {
        visible: settings['Watermark'] === 'Visible',
        text: settings['Title'] === false ? '' : 'OHLCV Demo',
        color: wmColor,
        fontSize: 24,
    };

    entry.chart.applyOptions(chartOptions);
    _tvEnsureInteractiveNavigation(entry);
    _tvApplyHoverReadoutMode(entry);

    // Move main series to the correct price scale side
    var targetScaleId = placement === 'Left' ? 'left' : 'right';
    var mainSeries = _tvGetMainSeries(entry);
    if (mainSeries) {
        try { mainSeries.applyOptions({ priceScaleId: targetScaleId }); } catch (e) {}
    }

    _tvApplyCustomScaleSide(entry, targetScaleId, {
        alignLabels: settings['No overlapping labels'] !== false,
        textColor: settings['Text-Color'] || undefined,
        borderColor: settings['Lines-Color'] || undefined,
    });

    // Apply main-series options (price labels and line from Symbol mode)
    if (!mainSeries) mainSeries = _tvGetMainSeries(entry);
    if (mainSeries) {
        var stype = _tvGuessSeriesType(mainSeries);
        var lineColor = settings['Line color'] || settings['Symbol color'] || undefined;
        var lw = _tvClamp(_tvToNumber(settings['Line width'], 1), 1, 4);
        var ls = _tvLineStyleFromName(settings['Line style']);
        // Derive price line/label visibility from Symbol dropdown (Scales & Lines tab)
        var symbolMode = settings['Symbol'] || 'Value, line';
        var showPriceLabel = symbolMode === 'Value, line' || symbolMode === 'Label';
        var showPriceLine = symbolMode === 'Value, line' || symbolMode === 'Line';
        var symbolColor = settings['Symbol color'] || _cssVar('--pywry-tvchart-up', '#26a69a');
        var sOpts = {
            lastValueVisible: showPriceLabel,
            priceLineVisible: showPriceLine,
            priceLineColor: symbolColor,
        };
        if (stype === 'Line' || stype === 'Area' || stype === 'Baseline' || stype === 'Histogram') {
            sOpts.lineStyle = ls;
            sOpts.lineWidth = lw;
            sOpts.color = lineColor;
            sOpts.lineColor = lineColor;
        }
        if (stype === 'Area') {
            if (settings['Area Fill Top']) sOpts.topColor = settings['Area Fill Top'];
            if (settings['Area Fill Bottom']) sOpts.bottomColor = settings['Area Fill Bottom'];
        }
        if (stype === 'Baseline') {
            var bLevel = _tvToNumber(settings['Baseline Level'], 0);
            sOpts.baseValue = { price: bLevel, type: 'price' };
            if (settings['Baseline Top Line']) sOpts.topLineColor = settings['Baseline Top Line'];
            if (settings['Baseline Bottom Line']) sOpts.bottomLineColor = settings['Baseline Bottom Line'];
            if (settings['Baseline Top Fill 1']) sOpts.topFillColor1 = settings['Baseline Top Fill 1'];
            if (settings['Baseline Top Fill 2']) sOpts.topFillColor2 = settings['Baseline Top Fill 2'];
            if (settings['Baseline Bottom Fill 1']) sOpts.bottomFillColor1 = settings['Baseline Bottom Fill 1'];
            if (settings['Baseline Bottom Fill 2']) sOpts.bottomFillColor2 = settings['Baseline Bottom Fill 2'];
        }
        if (stype === 'Bar') {
            if (settings['Bar Up Color']) sOpts.upColor = settings['Bar Up Color'];
            if (settings['Bar Down Color']) sOpts.downColor = settings['Bar Down Color'];
        }
        if (stype === 'Candlestick' || stype === 'Bar') {
            var bodyVisible = settings['Body'] !== false;
            var bodyUpOpacity = _tvClamp(_tvToNumber(settings['Body-Up Color-Opacity'], settings['Body-Opacity']), 0, 100);
            var bodyDownOpacity = _tvClamp(_tvToNumber(settings['Body-Down Color-Opacity'], settings['Body-Opacity']), 0, 100);
            var borderUpOpacity = _tvClamp(_tvToNumber(settings['Borders-Up Color-Opacity'], settings['Borders-Opacity']), 0, 100);
            var borderDownOpacity = _tvClamp(_tvToNumber(settings['Borders-Down Color-Opacity'], settings['Borders-Opacity']), 0, 100);
            var wickUpOpacity = _tvClamp(_tvToNumber(settings['Wick-Up Color-Opacity'], settings['Wick-Opacity']), 0, 100);
            var wickDownOpacity = _tvClamp(_tvToNumber(settings['Wick-Down Color-Opacity'], settings['Wick-Opacity']), 0, 100);
            var bodyHidden = _cssVar('--pywry-tvchart-hidden') || 'rgba(0, 0, 0, 0)';
            sOpts.upColor = bodyVisible ? _tvColorWithOpacity(settings['Body-Up Color'], bodyUpOpacity, _cssVar('--pywry-tvchart-up', '#26a69a')) : bodyHidden;
            sOpts.downColor = bodyVisible ? _tvColorWithOpacity(settings['Body-Down Color'], bodyDownOpacity, _cssVar('--pywry-tvchart-down', '#ef5350')) : bodyHidden;
            sOpts.borderVisible = settings['Borders'] !== false;
            sOpts.borderUpColor = _tvColorWithOpacity(settings['Borders-Up Color'], borderUpOpacity, _cssVar('--pywry-tvchart-border-up', '#26a69a'));
            sOpts.borderDownColor = _tvColorWithOpacity(settings['Borders-Down Color'], borderDownOpacity, _cssVar('--pywry-tvchart-border-down', '#ef5350'));
            sOpts.wickVisible = settings['Wick'] !== false;
            sOpts.wickUpColor = _tvColorWithOpacity(settings['Wick-Up Color'], wickUpOpacity, _cssVar('--pywry-tvchart-wick-up', '#26a69a'));
            sOpts.wickDownColor = _tvColorWithOpacity(settings['Wick-Down Color'], wickDownOpacity, _cssVar('--pywry-tvchart-wick-down', '#ef5350'));
        }
        if (settings['Precision'] && settings['Precision'] !== 'Default') {
            var minMove = Number(settings['Precision']);
            if (isFinite(minMove) && minMove > 0) {
                var decimals = String(settings['Precision']).indexOf('.') >= 0
                    ? String(settings['Precision']).split('.')[1].length
                    : 0;
                sOpts.priceFormat = { type: 'price', precision: decimals, minMove: minMove };
            }
        }
        mainSeries.applyOptions(sOpts);
    }

    // Volume label visibility in the status line / legend.
    // This does NOT create or destroy the volume subplot — it only controls
    // whether the "Volume 31.29 M" text appears in the legend header.
    // The legend updater reads legendBox.dataset.showVolume below.

    _tvSetToolbarVisibility(settings, chartId);

    // Persist legend and scale behavior flags for the legend updater script.
    var legendBox = _tvScopedById(chartId, 'tvchart-legend-box');
    if (legendBox) {
        var baseTitle = 'Symbol';
        if (entry.payload && entry.payload.useDatafeed && entry.payload.series && entry.payload.series[0] && entry.payload.series[0].symbol) {
            baseTitle = String(entry.payload.series[0].symbol);
        } else if (entry.payload && entry.payload.title) {
            baseTitle = String(entry.payload.title);
        } else if (entry.payload && entry.payload.series && entry.payload.series[0] && entry.payload.series[0].seriesId) {
            var sid = String(entry.payload.series[0].seriesId);
            if (sid && sid !== 'main') baseTitle = sid;
        }
        var intervalEl = _tvScopedById(chartId, 'tvchart-interval-label');

        legendBox.dataset.baseTitle = baseTitle;
        legendBox.dataset.interval = intervalEl ? (intervalEl.textContent || '').trim() : '';
        legendBox.dataset.showLogo = settings['Logo'] === false ? '0' : '1';
        legendBox.dataset.showTitle = settings['Title'] === false ? '0' : '1';
        legendBox.dataset.description = settings['Description'] || 'Description';
        legendBox.dataset.showChartValues = settings['Chart values'] === false ? '0' : '1';
        legendBox.dataset.showBarChange = settings['Bar change values'] === false ? '0' : '1';
        legendBox.dataset.showVolume = settings['Volume'] !== false ? '1' : '0';
        legendBox.dataset.showIndicatorTitles = settings['Titles'] === false ? '0' : '1';
        legendBox.dataset.showIndicatorInputs = settings['Inputs'] === false ? '0' : '1';
        legendBox.dataset.showIndicatorValues = settings['Values'] === false ? '0' : '1';
        legendBox.dataset.showStatusValues = settings['Chart values'] === false ? '0' : '1';
        legendBox.dataset.symbolMode = settings['Symbol'] || 'Value, line';
        legendBox.dataset.valueMode = settings['Value according to scale'] || settings['Value according to sc...'] || 'Value according to scale';
        legendBox.dataset.financialsMode = settings['Indicators and financials'] || 'Value';
        legendBox.dataset.highLowMode = settings['High and low'] || 'Hidden';
        legendBox.dataset.symbolColor = settings['Symbol color'] || '';
        legendBox.dataset.highLowColor = settings['High and low color'] || '';
        legendBox.dataset.lineColor = settings['Line color'] || '';
        legendBox.dataset.textColor = settings['Text-Color'] || '';
    }

    // Plus button mock on right scale edge.
    var container = entry.container || (entry.chart && entry.chart._container) || null;
    if (container) {
        var plusId = 'tvchart-plus-button-' + chartId;
        var plusEl = document.getElementById(plusId);
        if (!plusEl) {
            plusEl = document.createElement('div');
            plusEl.id = plusId;
            plusEl.className = 'pywry-tvchart-plus-button';
            plusEl.textContent = '+';
            container.appendChild(plusEl);
        }
        plusEl.style.display = settings['Plus button'] ? 'block' : 'none';

        var cdId = 'tvchart-countdown-label-' + chartId;
        var cdEl = document.getElementById(cdId);
        if (!cdEl) {
            cdEl = document.createElement('div');
            cdEl.id = cdId;
            cdEl.className = 'pywry-tvchart-countdown';
            container.appendChild(cdEl);
        }
        if (settings['Countdown to bar close']) {
            cdEl.style.display = 'block';
            cdEl.textContent = 'CLOSE TIMER';
        } else {
            cdEl.style.display = 'none';
        }
    }

    // Notify legend to re-render with updated dataset flags
    try {
        window.dispatchEvent(new CustomEvent('pywry:legend-refresh', { detail: { chartId: chartId } }));
    } catch (_e) {}

}

function _tvToPixel(chartId, time, price) {
    var e = window.__PYWRY_TVCHARTS__[chartId];
    if (!e || !e.chart) return null;
    var s = _tvMainSeries(chartId);
    var x = e.chart.timeScale().timeToCoordinate(time);
    var y = s ? s.priceToCoordinate(price) : null;
    if (x === null || y === null) return null;
    return { x: x, y: y };
}

function _tvFromPixel(chartId, x, y) {
    var e = window.__PYWRY_TVCHARTS__[chartId];
    if (!e || !e.chart) return null;
    var s = _tvMainSeries(chartId);
    var time  = e.chart.timeScale().coordinateToTime(x);
    var price = s ? s.coordinateToPrice(y) : null;
    return { time: time, price: price };
}

// ---- Get drawing anchor points in pixel coords ----
