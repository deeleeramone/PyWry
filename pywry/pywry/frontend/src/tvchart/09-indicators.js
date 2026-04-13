// Helper: sync hline price after coordinate edit
function _tvSyncPriceLinePrice(chartId, drawIdx, newPrice) {
    var ds = window.__PYWRY_DRAWINGS__[chartId];
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (!ds || !entry) return;
    var d = ds.drawings[drawIdx];
    if (!d || d.type !== 'hline') return;
    // Remove old native price line and recreate
    if (ds.priceLines[drawIdx]) {
        var pl = ds.priceLines[drawIdx];
        var ser = entry.seriesMap[pl.seriesId];
        if (ser) try { ser.removePriceLine(pl.priceLine); } catch(e) {}
    }
    var mainKey = Object.keys(entry.seriesMap)[0];
    if (mainKey && entry.seriesMap[mainKey]) {
        var newPl = entry.seriesMap[mainKey].createPriceLine({
            price: newPrice, color: d.color || _drawDefaults.color,
            lineWidth: d.lineWidth || 2, lineStyle: d.lineStyle || 0,
            axisLabelVisible: d.showPriceLabel !== false,
            title: d.title || '',
        });
        ds.priceLines[drawIdx] = { seriesId: mainKey, priceLine: newPl };
    }
}

// ---------------------------------------------------------------------------
// Indicators Panel
// ---------------------------------------------------------------------------
var _indicatorsOverlay = null;
var _indicatorsOverlayChartId = null;
var _activeIndicators = {};  // { seriesId: { name, period, chartId } }

var _INDICATOR_CATALOG = [
    { key: 'average-price', name: 'Average Price', fullName: 'Average Price', category: 'Lightweight Examples', defaultPeriod: 0 },
    { key: 'correlation', name: 'Correlation', fullName: 'Correlation', category: 'Lightweight Examples', defaultPeriod: 20, requiresSecondary: true, subplot: true },
    { key: 'median-price', name: 'Median Price', fullName: 'Median Price', category: 'Lightweight Examples', defaultPeriod: 0 },
    { key: 'momentum', name: 'Momentum', fullName: 'Momentum', category: 'Lightweight Examples', defaultPeriod: 10, subplot: true },
    { key: 'moving-average-ex', name: 'Moving Average', fullName: 'Moving Average', category: 'Lightweight Examples', defaultPeriod: 10 },
    { key: 'percent-change', name: 'Percent Change', fullName: 'Percent Change', category: 'Lightweight Examples', defaultPeriod: 0, subplot: true },
    { key: 'product', name: 'Product', fullName: 'Product', category: 'Lightweight Examples', defaultPeriod: 0, requiresSecondary: true, subplot: true },
    { key: 'ratio', name: 'Ratio', fullName: 'Ratio', category: 'Lightweight Examples', defaultPeriod: 0, requiresSecondary: true, subplot: true },
    { key: 'spread', name: 'Spread', fullName: 'Spread', category: 'Lightweight Examples', defaultPeriod: 0, requiresSecondary: true, subplot: true },
    { key: 'sum', name: 'Sum', fullName: 'Sum', category: 'Lightweight Examples', defaultPeriod: 0, requiresSecondary: true, subplot: true },
    { key: 'weighted-close', name: 'Weighted Close', fullName: 'Weighted Close', category: 'Lightweight Examples', defaultPeriod: 0 },

    { name: 'SMA', fullName: 'Simple Moving Average', category: 'Moving Averages', defaultPeriod: 20 },
    { name: 'EMA', fullName: 'Exponential Moving Average', category: 'Moving Averages', defaultPeriod: 20 },
    { name: 'WMA', fullName: 'Weighted Moving Average', category: 'Moving Averages', defaultPeriod: 20 },
    { name: 'SMA (50)', fullName: 'Simple Moving Average (50)', category: 'Moving Averages', defaultPeriod: 50 },
    { name: 'SMA (200)', fullName: 'Simple Moving Average (200)', category: 'Moving Averages', defaultPeriod: 200 },
    { name: 'EMA (12)', fullName: 'Exponential Moving Average (12)', category: 'Moving Averages', defaultPeriod: 12 },
    { name: 'EMA (26)', fullName: 'Exponential Moving Average (26)', category: 'Moving Averages', defaultPeriod: 26 },
    { name: 'Bollinger Bands', fullName: 'Bollinger Bands', category: 'Volatility', defaultPeriod: 20 },
    { name: 'RSI', fullName: 'Relative Strength Index', category: 'Momentum', defaultPeriod: 14 },
    { name: 'ATR', fullName: 'Average True Range', category: 'Volatility', defaultPeriod: 14 },
    { name: 'VWAP', fullName: 'Volume Weighted Average Price', category: 'Volume', defaultPeriod: 0 },
    { name: 'Volume SMA', fullName: 'Volume Simple Moving Average', category: 'Volume', defaultPeriod: 20 },
];

// ---- Indicator computation functions ----
function _computeSMA(data, period, field) {
    field = field || 'close';
    var result = [];
    for (var i = 0; i < data.length; i++) {
        if (i < period - 1) { result.push({ time: data[i].time }); continue; }
        var sum = 0;
        for (var j = i - period + 1; j <= i; j++) sum += (data[j][field] !== undefined ? data[j][field] : data[j].value || 0);
        result.push({ time: data[i].time, value: sum / period });
    }
    return result;
}

function _computeEMA(data, period, field) {
    field = field || 'close';
    var result = [];
    var k = 2 / (period + 1);
    var ema = null;
    for (var i = 0; i < data.length; i++) {
        var val = data[i][field] !== undefined ? data[i][field] : data[i].value || 0;
        if (i < period - 1) { result.push({ time: data[i].time }); continue; }
        if (ema === null) {
            var sum = 0;
            for (var j = i - period + 1; j <= i; j++) sum += (data[j][field] !== undefined ? data[j][field] : data[j].value || 0);
            ema = sum / period;
        } else {
            ema = val * k + ema * (1 - k);
        }
        result.push({ time: data[i].time, value: ema });
    }
    return result;
}

function _computeWMA(data, period, field) {
    field = field || 'close';
    var result = [];
    for (var i = 0; i < data.length; i++) {
        if (i < period - 1) { result.push({ time: data[i].time }); continue; }
        var sum = 0, wsum = 0;
        for (var j = 0; j < period; j++) {
            var w = j + 1;
            var val = data[i - period + 1 + j][field] !== undefined ? data[i - period + 1 + j][field] : 0;
            sum += val * w;
            wsum += w;
        }
        result.push({ time: data[i].time, value: sum / wsum });
    }
    return result;
}

function _computeRSI(data, period) {
    var result = [];
    var gains = 0, losses = 0;
    for (var i = 0; i < data.length; i++) {
        if (i === 0) { result.push({ time: data[i].time }); continue; }
        var prev = data[i - 1].close !== undefined ? data[i - 1].close : data[i - 1].value || 0;
        var cur = data[i].close !== undefined ? data[i].close : data[i].value || 0;
        var diff = cur - prev;
        if (i <= period) {
            if (diff > 0) gains += diff; else losses -= diff;
            if (i === period) {
                gains /= period; losses /= period;
                var rs = losses === 0 ? 100 : gains / losses;
                result.push({ time: data[i].time, value: 100 - 100 / (1 + rs) });
            } else {
                result.push({ time: data[i].time });
            }
        } else {
            var g = diff > 0 ? diff : 0, l = diff < 0 ? -diff : 0;
            gains = (gains * (period - 1) + g) / period;
            losses = (losses * (period - 1) + l) / period;
            var rs2 = losses === 0 ? 100 : gains / losses;
            result.push({ time: data[i].time, value: 100 - 100 / (1 + rs2) });
        }
    }
    return result;
}

function _computeATR(data, period) {
    var result = [];
    var atr = null;
    for (var i = 0; i < data.length; i++) {
        if (i === 0) { result.push({ time: data[i].time }); continue; }
        var h = data[i].high || data[i].close || data[i].value || 0;
        var l = data[i].low || data[i].close || data[i].value || 0;
        var pc = data[i - 1].close !== undefined ? data[i - 1].close : data[i - 1].value || 0;
        var tr = Math.max(h - l, Math.abs(h - pc), Math.abs(l - pc));
        if (i < period) { result.push({ time: data[i].time }); if (i === period - 1) { var s = 0; for (var j = 1; j <= i; j++) { var dh = data[j].high || data[j].close || 0; var dl = data[j].low || data[j].close || 0; var dpc = data[j-1].close || 0; s += Math.max(dh-dl, Math.abs(dh-dpc), Math.abs(dl-dpc)); } atr = (s + tr) / period; result[result.length - 1].value = atr; } continue; }
        atr = (atr * (period - 1) + tr) / period;
        result.push({ time: data[i].time, value: atr });
    }
    return result;
}

function _computeBollingerBands(data, period, mult, maType, offset) {
    mult = mult || 2;
    maType = maType || 'SMA';
    offset = offset || 0;
    var maFn = maType === 'EMA' ? _computeEMA : (maType === 'WMA' ? _computeWMA : _computeSMA);
    var ma = maFn(data, period);
    var upper = [], lower = [];
    for (var i = 0; i < data.length; i++) {
        if (!ma[i].value) { upper.push({ time: data[i].time }); lower.push({ time: data[i].time }); continue; }
        var sum = 0;
        for (var j = i - period + 1; j <= i; j++) {
            var v = data[j].close !== undefined ? data[j].close : data[j].value || 0;
            sum += (v - ma[i].value) * (v - ma[i].value);
        }
        var std = Math.sqrt(sum / period);
        upper.push({ time: data[i].time, value: ma[i].value + mult * std });
        lower.push({ time: data[i].time, value: ma[i].value - mult * std });
    }
    // Apply offset (shift data points forward/backward by offset bars)
    if (offset !== 0) {
        ma = _tvApplyOffset(ma, offset, data);
        upper = _tvApplyOffset(upper, offset, data);
        lower = _tvApplyOffset(lower, offset, data);
    }
    return { middle: ma, upper: upper, lower: lower };
}

function _tvApplyOffset(series, offset, refData) {
    if (!offset || !series.length) return series;
    var result = [];
    for (var i = 0; i < series.length; i++) {
        var srcIdx = i - offset;
        if (srcIdx >= 0 && srcIdx < series.length) {
            result.push({ time: series[i].time, value: series[srcIdx].value });
        } else {
            result.push({ time: series[i].time });
        }
    }
    return result;
}

// ---------------------------------------------------------------------------
// Bollinger Bands fill rendering (LWC series primitive — auto-clipped to pane)
// ---------------------------------------------------------------------------
var _bbFillPrimitives = {};  // { chartId: { primitive, seriesId } }

/** Draw BB band fills into a media-coordinate canvas context (called from primitive renderer). */
function _tvDrawBBFill(chartId, ctx, mediaSize) {
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (!entry || !entry.chart) return;
    var w = mediaSize.width;
    var h = mediaSize.height;

    // Find all BB groups on this chart that have fill enabled
    var groups = {};
    var keys = Object.keys(_activeIndicators);
    for (var i = 0; i < keys.length; i++) {
        var ind = _activeIndicators[keys[i]];
        if (ind.chartId !== chartId || ind.type !== 'bollinger-bands' || !ind.group) continue;
        if (!ind.showBandFill) continue;
        if (!groups[ind.group]) groups[ind.group] = { upper: null, lower: null, color: ind.bandFillColor || '#2196f3', opacity: ind.bandFillOpacity !== undefined ? ind.bandFillOpacity : 100 };
        if (keys[i].indexOf('upper') >= 0) groups[ind.group].upper = keys[i];
        else if (keys[i].indexOf('lower') >= 0) groups[ind.group].lower = keys[i];
    }

    var timeScale = entry.chart.timeScale();

    var groupKeys = Object.keys(groups);
    for (var gi = 0; gi < groupKeys.length; gi++) {
        var g = groups[groupKeys[gi]];
        if (!g.upper || !g.lower) continue;
        var upperSeries = entry.seriesMap[g.upper];
        var lowerSeries = entry.seriesMap[g.lower];
        if (!upperSeries || !lowerSeries) continue;

        var upperData = upperSeries.data();
        var lowerData = lowerSeries.data();
        if (!upperData.length || !lowerData.length) continue;

        // Build time→value map for lower band
        var lowerMap = {};
        for (var li = 0; li < lowerData.length; li++) {
            if (lowerData[li].value !== undefined) {
                lowerMap[String(lowerData[li].time)] = lowerData[li].value;
            }
        }

        // Iterate upper data, pair with lower, convert to pixel coords
        var upperPts = [];
        var lowerPts = [];
        var margin = 20;
        for (var di = 0; di < upperData.length; di++) {
            var uPt = upperData[di];
            if (uPt.value === undefined) continue;
            var lVal = lowerMap[String(uPt.time)];
            if (lVal === undefined) continue;

            var x = timeScale.timeToCoordinate(uPt.time);
            if (x === null || x === undefined) continue;
            if (x < -margin || x > w + margin) continue;

            // Use same series for both conversions to ensure consistent scaling
            var yU = upperSeries.priceToCoordinate(uPt.value);
            var yL = upperSeries.priceToCoordinate(lVal);
            if (yU === null || yL === null) continue;

            upperPts.push({ x: x, y: yU });
            lowerPts.push({ x: x, y: yL });
        }

        if (upperPts.length < 2) continue;

        // Draw filled polygon: upper line forward, lower line backward
        ctx.beginPath();
        ctx.moveTo(upperPts[0].x, upperPts[0].y);
        for (var pi = 1; pi < upperPts.length; pi++) {
            ctx.lineTo(upperPts[pi].x, upperPts[pi].y);
        }
        for (var pi2 = lowerPts.length - 1; pi2 >= 0; pi2--) {
            ctx.lineTo(lowerPts[pi2].x, lowerPts[pi2].y);
        }
        ctx.closePath();

        var fillColor = g.color || '#2196f3';
        var fillOp = _tvClamp(_tvToNumber(g.opacity, 100), 0, 100) / 100;
        ctx.fillStyle = _tvHexToRgba(fillColor, 0.15 * fillOp);
        ctx.fill();
    }
}

function _tvEnsureBBFillPrimitive(chartId) {
    if (_bbFillPrimitives[chartId]) return;
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (!entry || !entry.chart) return;

    // Find an upper BB series to attach the primitive to
    var upperSeriesId = null;
    var allKeys = Object.keys(_activeIndicators);
    for (var i = 0; i < allKeys.length; i++) {
        var ind = _activeIndicators[allKeys[i]];
        if (ind.chartId === chartId && ind.type === 'bollinger-bands' && allKeys[i].indexOf('upper') >= 0) {
            upperSeriesId = allKeys[i];
            break;
        }
    }
    if (!upperSeriesId || !entry.seriesMap[upperSeriesId]) return;

    var _requestUpdate = null;
    var theRenderer = {
        draw: function(target) {
            target.useMediaCoordinateSpace(function(scope) {
                _tvDrawBBFill(chartId, scope.context, scope.mediaSize);
            });
        }
    };
    var theView = {
        zOrder: function() { return 'bottom'; },
        renderer: function() { return theRenderer; }
    };
    var primitive = {
        attached: function(params) { _requestUpdate = params.requestUpdate; },
        detached: function() { _requestUpdate = null; },
        updateAllViews: function() {},
        paneViews: function() { return [theView]; },
        triggerUpdate: function() { if (_requestUpdate) _requestUpdate(); }
    };

    entry.seriesMap[upperSeriesId].attachPrimitive(primitive);
    _bbFillPrimitives[chartId] = { primitive: primitive, seriesId: upperSeriesId };
}

function _tvRemoveBBFillPrimitive(chartId) {
    var bp = _bbFillPrimitives[chartId];
    if (!bp) return;
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (entry && entry.seriesMap[bp.seriesId]) {
        try { entry.seriesMap[bp.seriesId].detachPrimitive(bp.primitive); } catch (e) {}
    }
    delete _bbFillPrimitives[chartId];
}

function _tvUpdateBBFill(chartId) {
    var bp = _bbFillPrimitives[chartId];
    if (bp && bp.primitive && bp.primitive.triggerUpdate) {
        bp.primitive.triggerUpdate();
    }
}

function _computeVWAP(data) {
    var result = [];
    var cumVol = 0, cumTP = 0;
    for (var i = 0; i < data.length; i++) {
        var h = data[i].high || data[i].close || data[i].value || 0;
        var l = data[i].low || data[i].close || data[i].value || 0;
        var c = data[i].close !== undefined ? data[i].close : data[i].value || 0;
        var v = data[i].volume || 1;
        var tp = (h + l + c) / 3;
        cumTP += tp * v;
        cumVol += v;
        result.push({ time: data[i].time, value: cumVol > 0 ? cumTP / cumVol : tp });
    }
    return result;
}

function _tvIndicatorValue(point, source) {
    var src = source || 'close';
    if (src === 'hl2') {
        var h2 = point.high !== undefined ? point.high : (point.value || 0);
        var l2 = point.low !== undefined ? point.low : (point.value || 0);
        return (h2 + l2) / 2;
    }
    if (src === 'ohlc4') {
        var o4 = point.open !== undefined ? point.open : (point.value || 0);
        var h4 = point.high !== undefined ? point.high : (point.value || 0);
        var l4 = point.low !== undefined ? point.low : (point.value || 0);
        var c4 = point.close !== undefined ? point.close : (point.value || 0);
        return (o4 + h4 + l4 + c4) / 4;
    }
    if (src === 'hlc3') {
        var h3 = point.high !== undefined ? point.high : (point.value || 0);
        var l3 = point.low !== undefined ? point.low : (point.value || 0);
        var c3 = point.close !== undefined ? point.close : (point.value || 0);
        return (h3 + l3 + c3) / 3;
    }
    if (point[src] !== undefined) return point[src];
    if (point.close !== undefined) return point.close;
    if (point.value !== undefined) return point.value;
    return 0;
}

function _tvShiftIndicatorData(data, offsetBars) {
    var offset = Number(offsetBars || 0);
    if (!offset) return data;
    var out = [];
    for (var i = 0; i < data.length; i++) {
        var srcIdx = i - offset;
        if (srcIdx >= 0 && srcIdx < data.length && data[srcIdx].value !== undefined) {
            out.push({ time: data[i].time, value: data[srcIdx].value });
        } else {
            out.push({ time: data[i].time });
        }
    }
    return out;
}

function _tvComputeAveragePrice(data) {
    var out = [];
    for (var i = 0; i < data.length; i++) {
        var p = data[i] || {};
        var sum = 0;
        var count = 0;
        if (p.open !== undefined) { sum += p.open; count++; }
        if (p.high !== undefined) { sum += p.high; count++; }
        if (p.low !== undefined) { sum += p.low; count++; }
        if (p.close !== undefined) { sum += p.close; count++; }
        if (!count && p.value !== undefined) { sum += p.value; count = 1; }
        out.push({ time: p.time, value: count ? (sum / count) : undefined });
    }
    return out;
}

function _tvComputeMedianPrice(data) {
    var out = [];
    for (var i = 0; i < data.length; i++) {
        var p = data[i] || {};
        var h = p.high !== undefined ? p.high : (p.value !== undefined ? p.value : undefined);
        var l = p.low !== undefined ? p.low : (p.value !== undefined ? p.value : undefined);
        out.push({ time: p.time, value: (h !== undefined && l !== undefined) ? (h + l) / 2 : undefined });
    }
    return out;
}

function _tvComputeWeightedClose(data) {
    var out = [];
    for (var i = 0; i < data.length; i++) {
        var p = data[i] || {};
        var h = p.high !== undefined ? p.high : (p.value || 0);
        var l = p.low !== undefined ? p.low : (p.value || 0);
        var c = p.close !== undefined ? p.close : (p.value || 0);
        out.push({ time: p.time, value: (h + l + 2 * c) / 4 });
    }
    return out;
}

function _tvComputeMomentum(data, length, source) {
    var out = [];
    for (var i = 0; i < data.length; i++) {
        if (i < length) { out.push({ time: data[i].time }); continue; }
        var cur = _tvIndicatorValue(data[i], source);
        var prv = _tvIndicatorValue(data[i - length], source);
        out.push({ time: data[i].time, value: cur - prv });
    }
    return out;
}

function _tvComputePercentChange(data, source) {
    var out = [];
    var base = null;
    for (var i = 0; i < data.length; i++) {
        var v = _tvIndicatorValue(data[i], source);
        if (base === null && isFinite(v) && v !== 0) base = v;
        if (base === null || !isFinite(v)) {
            out.push({ time: data[i].time });
        } else {
            out.push({ time: data[i].time, value: ((v / base) - 1) * 100 });
        }
    }
    return out;
}

function _tvAlignTwoSeries(primary, secondary, primarySource, secondarySource) {
    var secMap = {};
    for (var j = 0; j < secondary.length; j++) {
        secMap[String(secondary[j].time)] = _tvIndicatorValue(secondary[j], secondarySource);
    }
    var out = [];
    for (var i = 0; i < primary.length; i++) {
        var t = String(primary[i].time);
        if (secMap[t] === undefined) continue;
        out.push({ time: primary[i].time, a: _tvIndicatorValue(primary[i], primarySource), b: secMap[t] });
    }
    return out;
}

function _tvComputeBinary(primary, secondary, primarySource, secondarySource, op) {
    var aligned = _tvAlignTwoSeries(primary, secondary, primarySource, secondarySource);
    var out = [];
    for (var i = 0; i < aligned.length; i++) {
        var p = aligned[i];
        var val;
        if (op === 'spread') val = p.a - p.b;
        else if (op === 'ratio') val = p.b === 0 ? undefined : p.a / p.b;
        else if (op === 'sum') val = p.a + p.b;
        else if (op === 'product') val = p.a * p.b;
        out.push({ time: p.time, value: val });
    }
    return out;
}

function _tvComputeCorrelation(primary, secondary, length, primarySource, secondarySource) {
    var aligned = _tvAlignTwoSeries(primary, secondary, primarySource, secondarySource);
    var out = [];
    for (var i = 0; i < aligned.length; i++) {
        if (i + 1 < length) {
            out.push({ time: aligned[i].time });
            continue;
        }
        var sx = 0, sy = 0;
        for (var j = i - length + 1; j <= i; j++) {
            sx += aligned[j].a;
            sy += aligned[j].b;
        }
        var mx = sx / length;
        var my = sy / length;
        var cov = 0, vx = 0, vy = 0;
        for (var k = i - length + 1; k <= i; k++) {
            var dx = aligned[k].a - mx;
            var dy = aligned[k].b - my;
            cov += dx * dy;
            vx += dx * dx;
            vy += dy * dy;
        }
        var den = Math.sqrt(vx * vy);
        out.push({ time: aligned[i].time, value: den > 0 ? (cov / den) : 0 });
    }
    return out;
}

// Assign distinct colors to indicators
var _INDICATOR_COLORS = [
    '#ff9800', '#e91e63', '#9c27b0', '#00bcd4', '#8bc34a',
    '#ff5722', '#3f51b5', '#009688', '#ffc107', '#607d8b'
];
var _indicatorColorIdx = 0;

function _getNextIndicatorColor() {
    var c = _cssVar('--pywry-preset-' + ((_indicatorColorIdx % 10) + 3), _INDICATOR_COLORS[_indicatorColorIdx % _INDICATOR_COLORS.length]);
    _indicatorColorIdx++;
    return c;
}

function _tvRemoveIndicator(seriesId) {
    var info = _activeIndicators[seriesId];
    if (!info) return;
    var chartId = info.chartId;
    var entry = window.__PYWRY_TVCHARTS__[chartId];

    // Push undo entry before removing (skip during layout restore)
    if (!window.__PYWRY_UNDO_SUPPRESS__) {
        var _undoDef = {
            name: info.name, key: info.type,
            defaultPeriod: info.period || 0,
            _color: info.color,
            _multiplier: info.multiplier,
            _maType: info.maType,
            _offset: info.offset,
            _source: info.source,
        };
        var _undoCid = chartId;
        _tvPushUndo({
            label: 'Remove ' + (info.name || 'indicator'),
            undo: function() {
                _tvAddIndicator(_undoDef, _undoCid);
            },
            redo: function() {
                // Find the indicator by type+period after re-add (seriesIds change)
                var keys = Object.keys(_activeIndicators);
                for (var i = keys.length - 1; i >= 0; i--) {
                    var ai = _activeIndicators[keys[i]];
                    if (ai && ai.chartId === _undoCid && ai.type === _undoDef.key) {
                        _tvRemoveIndicator(keys[i]);
                        break;
                    }
                }
            },
        });
    }

    // Remove requested series and grouped siblings in a single pass.
    var toRemove = [seriesId];
    if (info.group) {
        var gKeys = Object.keys(_activeIndicators);
        for (var gi = 0; gi < gKeys.length; gi++) {
            var gk = gKeys[gi];
            if (gk !== seriesId && _activeIndicators[gk] && _activeIndicators[gk].group === info.group) {
                toRemove.push(gk);
            }
        }
    }

    var removedPanes = {};
    for (var i = 0; i < toRemove.length; i++) {
        var sid = toRemove[i];
        var sinfo = _activeIndicators[sid];
        if (!sinfo) continue;
        var sEntry = window.__PYWRY_TVCHARTS__[sinfo.chartId];
        if (sEntry && sEntry.seriesMap[sid]) {
            try { sEntry.chart.removeSeries(sEntry.seriesMap[sid]); } catch(e) {}
            delete sEntry.seriesMap[sid];
        }
        // Clean up hidden indicator source series (secondary symbol used for binary indicators)
        if (sinfo.secondarySeriesId && sEntry && sEntry._indicatorSourceSeries && sEntry._indicatorSourceSeries[sinfo.secondarySeriesId]) {
            var secId = sinfo.secondarySeriesId;
            if (sEntry.seriesMap[secId]) {
                try { sEntry.chart.removeSeries(sEntry.seriesMap[secId]); } catch(e) {}
                delete sEntry.seriesMap[secId];
            }
            delete sEntry._indicatorSourceSeries[secId];
            if (sEntry._compareSymbols) delete sEntry._compareSymbols[secId];
            if (sEntry._compareLabels) delete sEntry._compareLabels[secId];
            if (sEntry._compareSymbolInfo) delete sEntry._compareSymbolInfo[secId];
            if (sEntry._seriesRawData) delete sEntry._seriesRawData[secId];
            if (sEntry._seriesCanonicalRawData) delete sEntry._seriesCanonicalRawData[secId];
        }
        if (sinfo.chartId === chartId && sinfo.isSubplot && sinfo.paneIndex > 0) {
            removedPanes[sinfo.paneIndex] = true;
        }
        delete _activeIndicators[sid];
    }

    // Remove empty subplot containers and keep pane indexes in sync.
    if (entry && entry.chart && typeof entry.chart.removePane === 'function') {
        var paneKeys = Object.keys(removedPanes)
            .map(function(v) { return Number(v); })
            .sort(function(a, b) { return b - a; });
        for (var pi = 0; pi < paneKeys.length; pi++) {
            var removedPane = paneKeys[pi];
            var paneStillUsed = false;
            var remaining = Object.keys(_activeIndicators);
            for (var ri = 0; ri < remaining.length; ri++) {
                var ai = _activeIndicators[remaining[ri]];
                if (ai && ai.chartId === chartId && ai.isSubplot && ai.paneIndex === removedPane) {
                    paneStillUsed = true;
                    break;
                }
            }
            if (paneStillUsed) continue;
            var paneRemoved = false;
            try {
                entry.chart.removePane(removedPane);
                paneRemoved = true;
            } catch(e2) {
                try {
                    if (typeof entry.chart.panes === 'function') {
                        var paneObj = entry.chart.panes()[removedPane];
                        if (paneObj) {
                            entry.chart.removePane(paneObj);
                            paneRemoved = true;
                        }
                    }
                } catch(e3) {}
            }
            if (paneRemoved) {
                // Lightweight Charts reindexes panes after removal.
                for (var uj = 0; uj < remaining.length; uj++) {
                    var uid = remaining[uj];
                    var uai = _activeIndicators[uid];
                    if (uai && uai.chartId === chartId && uai.isSubplot && uai.paneIndex > removedPane) {
                        uai.paneIndex -= 1;
                    }
                }
            }
        }
    }

    // Keep next pane index compact after removals.
    if (entry) {
        var maxPane = 0;
        var keys = Object.keys(_activeIndicators);
        for (var k = 0; k < keys.length; k++) {
            var ii = _activeIndicators[keys[k]];
            if (ii && ii.chartId === chartId && ii.isSubplot && ii.paneIndex > maxPane) {
                maxPane = ii.paneIndex;
            }
        }
        entry._nextPane = maxPane + 1;
    }

    // Reset maximize/collapse state — pane layout changed
    if (entry) { entry._paneState = { mode: 'normal', pane: -1 }; delete entry._savedPaneHeights; }

    _tvRebuildIndicatorLegend(chartId);

    // Clean up BB fill canvas if no BB indicators remain on this chart
    if (info.type === 'bollinger-bands') {
        var hasBB = false;
        var remKeys = Object.keys(_activeIndicators);
        for (var bi = 0; bi < remKeys.length; bi++) {
            if (_activeIndicators[remKeys[bi]].chartId === chartId && _activeIndicators[remKeys[bi]].type === 'bollinger-bands') { hasBB = true; break; }
        }
        if (!hasBB) {
            _tvRemoveBBFillPrimitive(chartId);
        } else {
            _tvUpdateBBFill(chartId);
        }
    }
}

// ---------------------------------------------------------------------------
// Indicator legend helpers
// ---------------------------------------------------------------------------

function _tvLegendActionButton(title, iconHtml, onClick) {
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'tvchart-legend-btn';
    btn.setAttribute('data-tooltip', title);
    btn.setAttribute('aria-label', title);
    btn.innerHTML = iconHtml;
    btn.addEventListener('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        if (onClick) onClick(btn, e);
    });
    return btn;
}

function _tvOpenLegendItemMenu(anchorEl, actions) {
    if (!anchorEl || !actions || !actions.length) return;
    var old = document.querySelector('.tvchart-legend-menu');
    if (old && old.parentNode) old.parentNode.removeChild(old);
    var menu = document.createElement('div');
    menu.className = 'tvchart-legend-menu';
    for (var i = 0; i < actions.length; i++) {
        (function(action) {
            if (action.separator) {
                var sep = document.createElement('div');
                sep.className = 'tvchart-legend-menu-sep';
                menu.appendChild(sep);
                return;
            }
            var item = document.createElement('button');
            item.type = 'button';
            item.className = 'tvchart-legend-menu-item';
            if (action.disabled) {
                item.disabled = true;
                item.classList.add('is-disabled');
            }
            if (action.tooltip) {
                item.setAttribute('data-tooltip', action.tooltip);
            }
            var icon = document.createElement('span');
            icon.className = 'tvchart-legend-menu-item-icon';
            icon.innerHTML = action.icon || '';
            item.appendChild(icon);
            var label = document.createElement('span');
            label.className = 'tvchart-legend-menu-item-label';
            label.textContent = action.label;
            item.appendChild(label);
            if (action.meta) {
                var meta = document.createElement('span');
                meta.className = 'tvchart-legend-menu-item-meta';
                meta.textContent = action.meta;
                item.appendChild(meta);
            }
            item.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                if (action.disabled) return;
                if (menu.parentNode) menu.parentNode.removeChild(menu);
                action.run();
            });
            menu.appendChild(item);
        })(actions[i]);
    }
    menu.addEventListener('click', function(e) { e.stopPropagation(); });
    var _oc = _tvAppendOverlay(anchorEl, menu);
    var _cs = _tvContainerSize(_oc);
    var rect = _tvContainerRect(_oc, anchorEl.getBoundingClientRect());
    var menuRect = menu.getBoundingClientRect();
    var left = Math.max(6, Math.min(_cs.width - menuRect.width - 6, rect.right - menuRect.width));
    var top = Math.max(6, Math.min(_cs.height - menuRect.height - 6, rect.bottom + 4));
    menu.style.left = left + 'px';
    menu.style.top = top + 'px';
    setTimeout(function() {
        document.addEventListener('click', function closeMenu() {
            if (menu.parentNode) menu.parentNode.removeChild(menu);
        }, { once: true });
    }, 0);
}

function _tvSetIndicatorVisibility(chartId, seriesId, visible) {
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (!entry || !entry.chart) return;
    var target = _activeIndicators[seriesId];
    if (!target) return;
    var keys = Object.keys(_activeIndicators);
    for (var i = 0; i < keys.length; i++) {
        var sid = keys[i];
        var info = _activeIndicators[sid];
        if (!info || info.chartId !== chartId) continue;
        if (target.group && info.group !== target.group) continue;
        if (!target.group && sid !== seriesId) continue;
        var s = entry.seriesMap[sid];
        if (s && typeof s.applyOptions === 'function') {
            try { s.applyOptions({ visible: !!visible }); } catch (e) {}
        }
        info.hidden = !visible;
    }
}

function _tvLegendCopyToClipboard(text) {
    var value = String(text || '').trim();
    if (!value) return;
    try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(value);
        }
    } catch (e) {}
}

// ---------------------------------------------------------------------------
// Pane move up/down for subplot indicators
// ---------------------------------------------------------------------------

function _tvSwapIndicatorPane(chartId, seriesId, direction) {
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (!entry || !entry.chart) return;
    var info = _activeIndicators[seriesId];
    if (!info || !info.isSubplot) return;

    // Restore panes to normal before swapping so heights are sane
    var pState = _tvGetPaneState(chartId);
    if (pState.mode !== 'normal') {
        _tvRestorePanes(chartId);
    }

    var targetPane = info.paneIndex + direction;
    if (targetPane < 0) return; // Can't move above the first pane

    // Count the total number of panes via LWC API
    var totalPanes = 0;
    try {
        if (typeof entry.chart.panes === 'function') {
            totalPanes = entry.chart.panes().length;
        }
    } catch (e) {}
    if (totalPanes <= 0) {
        // Fallback: count from tracked indicators + volume
        var allKeys = Object.keys(_activeIndicators);
        for (var i = 0; i < allKeys.length; i++) {
            var ai = _activeIndicators[allKeys[i]];
            if (ai && ai.chartId === chartId && ai.paneIndex > totalPanes) {
                totalPanes = ai.paneIndex;
            }
        }
        totalPanes += 1; // convert max index to count
    }
    if (targetPane >= totalPanes) return; // Can't move below last pane

    // Use LWC v5 swapPanes API
    try {
        if (typeof entry.chart.swapPanes === 'function') {
            entry.chart.swapPanes(info.paneIndex, targetPane);
        } else {
            return; // API not available
        }
    } catch (e) {
        return;
    }

    var oldPane = info.paneIndex;

    // Update paneIndex tracking for all affected indicators
    var allKeys2 = Object.keys(_activeIndicators);
    for (var j = 0; j < allKeys2.length; j++) {
        var aj = _activeIndicators[allKeys2[j]];
        if (!aj || aj.chartId !== chartId) continue;
        if (aj.paneIndex === oldPane) {
            aj.paneIndex = targetPane;
        } else if (aj.paneIndex === targetPane) {
            aj.paneIndex = oldPane;
        }
    }

    // Update volume pane tracking if swap involved a volume pane
    if (entry._volumePaneBySeries) {
        var volKeys = Object.keys(entry._volumePaneBySeries);
        for (var vi = 0; vi < volKeys.length; vi++) {
            var vk = volKeys[vi];
            if (entry._volumePaneBySeries[vk] === oldPane) {
                entry._volumePaneBySeries[vk] = targetPane;
            } else if (entry._volumePaneBySeries[vk] === targetPane) {
                entry._volumePaneBySeries[vk] = oldPane;
            }
        }
    }

    // Reposition the main chart legend to follow the pane it now lives in.
    // Deferred so the swap DOM changes are settled.
    requestAnimationFrame(function() {
        _tvRepositionMainLegend(entry, chartId);
    });

    _tvRebuildIndicatorLegend(chartId);
}

/**
 * Find which pane index the main chart series currently lives in.
 * Returns 0 if unknown.
 */
function _tvFindMainChartPane(entry) {
    if (!entry || !entry.chart) return 0;
    try {
        var panes = typeof entry.chart.panes === 'function' ? entry.chart.panes() : null;
        if (!panes) return 0;
        // The main chart series is the first entry in seriesMap
        var mainKey = Object.keys(entry.seriesMap)[0];
        var mainSeries = mainKey ? entry.seriesMap[mainKey] : null;
        if (!mainSeries) return 0;
        for (var pi = 0; pi < panes.length; pi++) {
            var pSeries = typeof panes[pi].getSeries === 'function' ? panes[pi].getSeries() : [];
            for (var si = 0; si < pSeries.length; si++) {
                if (pSeries[si] === mainSeries) return pi;
            }
        }
    } catch (e) {}
    return 0;
}

/**
 * Reposition the main legend box (OHLC, Volume text, indicators-in-main)
 * so it sits at the top of whichever pane the main chart series is in.
 * When the main chart is in pane 0 (default), top stays at 8px.
 * When it's been swapped to another pane, offset the legend accordingly.
 */
function _tvRepositionMainLegend(entry, chartId) {
    if (!entry || !entry.chart) return;
    var legendBox = _tvScopedById(chartId, 'tvchart-legend-box');
    if (!legendBox) return;

    var mainPane = _tvFindMainChartPane(entry);
    if (mainPane === 0) {
        // Default position
        legendBox.style.top = '8px';
        return;
    }

    try {
        var panes = typeof entry.chart.panes === 'function' ? entry.chart.panes() : null;
        if (!panes || !panes[mainPane]) { legendBox.style.top = '8px'; return; }
        var paneHtml = typeof panes[mainPane].getHTMLElement === 'function'
            ? panes[mainPane].getHTMLElement() : null;
        if (!paneHtml) { legendBox.style.top = '8px'; return; }
        // The legend box is positioned relative to the inside toolbar overlay
        // which matches the chart container bounds exactly.
        var containerRect = entry.container.getBoundingClientRect();
        var paneRect = paneHtml.getBoundingClientRect();
        var offset = paneRect.top - containerRect.top;
        legendBox.style.top = (offset + 8) + 'px';
    } catch (e) {
        legendBox.style.top = '8px';
    }
}

/**
 * Get the current state of a pane: 'normal', 'maximized', or 'collapsed'.
 */
function _tvGetPaneState(chartId) {
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (!entry) return { mode: 'normal', pane: -1 };
    if (!entry._paneState) entry._paneState = { mode: 'normal', pane: -1 };
    return entry._paneState;
}

/**
 * Save the current pane heights before maximize/collapse so we can
 * restore them later.
 */
function _tvSavePaneHeights(entry) {
    if (!entry || !entry.chart) return;
    try {
        var panes = entry.chart.panes();
        if (!panes) return;
        entry._savedPaneHeights = [];
        for (var i = 0; i < panes.length; i++) {
            var el = typeof panes[i].getHTMLElement === 'function'
                ? panes[i].getHTMLElement() : null;
            entry._savedPaneHeights.push(el ? el.clientHeight : 0);
        }
    } catch (e) {}
}

/**
 * Hide or show LWC pane HTML elements and separator bars.
 * LWC renders panes as table-row elements inside a table; separators
 * are sibling rows.  We walk the parent and hide everything except the
 * target pane's row.
 */
function _tvSetPaneVisibility(panes, visibleIndex, hidden) {
    for (var k = 0; k < panes.length; k++) {
        var el = typeof panes[k].getHTMLElement === 'function'
            ? panes[k].getHTMLElement() : null;
        if (!el) continue;
        if (hidden && k !== visibleIndex) {
            el.style.display = 'none';
            // Also hide the separator bar above (previous sibling of the pane)
            var sep = el.previousElementSibling;
            if (sep && sep !== el.parentElement.firstElementChild) {
                sep.style.display = 'none';
            }
        } else {
            el.style.display = '';
            var sep2 = el.previousElementSibling;
            if (sep2 && sep2 !== el.parentElement.firstElementChild) {
                sep2.style.display = '';
            }
        }
    }
}

/**
 * Show or hide the legend boxes to match which panes are visible.
 *   mode='normal'    — show everything
 *   mode='maximized' — show only the legend for `pane`, hide others
 *   mode='collapsed' — hide the legend for `pane`, show others
 */
function _tvSyncLegendVisibility(chartId, mode, pane) {
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (!entry) return;

    // Main legend box (OHLC, Volume, indicators-in-main-pane)
    var legendBox = _tvScopedById(chartId, 'tvchart-legend-box');
    var mainPane = _tvFindMainChartPane(entry);

    if (mode === 'normal') {
        // Show everything
        if (legendBox) legendBox.style.display = '';
        if (entry._paneLegendEls) {
            var pKeys = Object.keys(entry._paneLegendEls);
            for (var i = 0; i < pKeys.length; i++) {
                entry._paneLegendEls[pKeys[i]].style.display = '';
            }
        }
    } else if (mode === 'maximized') {
        // Hide main legend if main chart pane is not the maximized one
        if (legendBox) legendBox.style.display = (mainPane === pane) ? '' : 'none';
        // Hide all pane overlays except for the maximized pane
        if (entry._paneLegendEls) {
            var mKeys = Object.keys(entry._paneLegendEls);
            for (var m = 0; m < mKeys.length; m++) {
                var idx = Number(mKeys[m]);
                entry._paneLegendEls[mKeys[m]].style.display = (idx === pane) ? '' : 'none';
            }
        }
    } else if (mode === 'collapsed') {
        // Show all legends — the collapsed pane still shows its legend in the thin strip
        if (legendBox) legendBox.style.display = '';
        if (entry._paneLegendEls) {
            var cKeys = Object.keys(entry._paneLegendEls);
            for (var c = 0; c < cKeys.length; c++) {
                entry._paneLegendEls[cKeys[c]].style.display = '';
            }
        }
    }
}

/**
 * Maximize a pane: hide every other pane so it fills the entire chart area.
 */
function _tvMaximizePane(chartId, paneIndex) {
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (!entry || !entry.chart) return;
    try {
        if (typeof entry.chart.panes !== 'function') return;
        var panes = entry.chart.panes();
        if (!panes || !panes[paneIndex]) return;
        var state = _tvGetPaneState(chartId);

        // If already maximized on this pane, restore instead
        if (state.mode === 'maximized' && state.pane === paneIndex) {
            _tvRestorePanes(chartId);
            return;
        }

        // If currently in another mode, restore first
        if (state.mode !== 'normal') {
            _tvSetPaneVisibility(panes, -1, false); // unhide all
        }

        // Save heights only from normal state
        if (state.mode === 'normal') {
            _tvSavePaneHeights(entry);
        }

        // Hide all panes except the target
        _tvSetPaneVisibility(panes, paneIndex, true);

        // Force the target pane to fill the full container height
        var containerH = entry.container ? entry.container.clientHeight : 600;
        if (typeof panes[paneIndex].setHeight === 'function') {
            panes[paneIndex].setHeight(containerH);
        }

        entry._paneState = { mode: 'maximized', pane: paneIndex };
        _tvSyncLegendVisibility(chartId, 'maximized', paneIndex);
        _tvUpdatePaneControlButtons(chartId);
        requestAnimationFrame(function() {
            _tvRepositionPaneLegends(chartId);
        });
    } catch (e) {}
}

/**
 * Collapse a pane: shrink it to a thin strip showing only the legend text.
 * The pane stays visible but its chart content is clipped.
 */
function _tvCollapsePane(chartId, paneIndex) {
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (!entry || !entry.chart) return;
    try {
        if (typeof entry.chart.panes !== 'function') return;
        var panes = entry.chart.panes();
        if (!panes || !panes[paneIndex]) return;
        var state = _tvGetPaneState(chartId);

        // If already collapsed on this pane, restore instead
        if (state.mode === 'collapsed' && state.pane === paneIndex) {
            _tvRestorePanes(chartId);
            return;
        }

        // If currently in another mode, restore first
        if (state.mode !== 'normal') {
            _tvSetPaneVisibility(panes, -1, false);
            _tvShowPaneContent(panes, -1); // unhide any hidden canvases
        }

        // Save heights only from normal state
        if (state.mode === 'normal') {
            _tvSavePaneHeights(entry);
        }

        // Shrink pane to minimal via LWC API, then hide all canvas/content
        // children so only the empty strip remains for the legend overlay.
        if (typeof panes[paneIndex].setHeight === 'function') {
            panes[paneIndex].setHeight(1);
        }
        _tvHidePaneContent(panes[paneIndex]);

        entry._paneState = { mode: 'collapsed', pane: paneIndex };
        _tvSyncLegendVisibility(chartId, 'collapsed', paneIndex);
        _tvUpdatePaneControlButtons(chartId);
        requestAnimationFrame(function() {
            _tvRepositionPaneLegends(chartId);
        });
    } catch (e) {}
}

/**
 * Hide all visual content (canvases, child elements) inside a pane,
 * leaving the pane element itself visible at whatever height LWC gives it.
 */
function _tvHidePaneContent(pane) {
    var el = typeof pane.getHTMLElement === 'function' ? pane.getHTMLElement() : null;
    if (!el) return;
    // Hide every child element inside the pane (canvas, scale elements, etc.)
    var children = el.querySelectorAll('*');
    for (var i = 0; i < children.length; i++) {
        children[i].style.visibility = 'hidden';
    }
}

/**
 * Restore visibility to pane content.
 * If paneIndex is -1, restores all panes.
 */
function _tvShowPaneContent(panes, paneIndex) {
    for (var k = 0; k < panes.length; k++) {
        if (paneIndex >= 0 && k !== paneIndex) continue;
        var el = typeof panes[k].getHTMLElement === 'function'
            ? panes[k].getHTMLElement() : null;
        if (!el) continue;
        var children = el.querySelectorAll('*');
        for (var j = 0; j < children.length; j++) {
            children[j].style.visibility = '';
        }
    }
}

/**
 * Restore all panes to their saved heights (before maximize/collapse).
 */
function _tvRestorePanes(chartId) {
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (!entry || !entry.chart) return;
    try {
        if (typeof entry.chart.panes !== 'function') return;
        var panes = entry.chart.panes();
        if (!panes) return;

        // Unhide all panes (from maximize) and restore content (from collapse)
        _tvSetPaneVisibility(panes, -1, false);
        _tvShowPaneContent(panes, -1);

        var saved = entry._savedPaneHeights;
        if (saved && saved.length === panes.length) {
            for (var i = 0; i < panes.length; i++) {
                if (typeof panes[i].setHeight === 'function' && saved[i] > 0) {
                    panes[i].setHeight(saved[i]);
                }
            }
        } else {
            // Fallback: equal distribution
            var containerH = entry.container ? entry.container.clientHeight : 600;
            for (var j = 0; j < panes.length; j++) {
                if (typeof panes[j].setHeight === 'function') {
                    panes[j].setHeight(Math.round(containerH / panes.length));
                }
            }
        }
        entry._paneState = { mode: 'normal', pane: -1 };
        delete entry._savedPaneHeights;
        _tvSyncLegendVisibility(chartId, 'normal', -1);
        _tvUpdatePaneControlButtons(chartId);
        requestAnimationFrame(function() {
            _tvRepositionPaneLegends(chartId);
        });
    } catch (e) {}
}

/**
 * Update the maximize/collapse/restore button icon and tooltip for every
 * subplot indicator in the given chart, reflecting the current pane state.
 */
function _tvUpdatePaneControlButtons(chartId) {
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (!entry) return;
    var state = _tvGetPaneState(chartId);
    var restoreSvg = '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="display:block"><rect x="1.5" y="4.5" width="9" height="9" rx="1.5"/><path d="M5.5 4.5V3a1.5 1.5 0 011.5-1.5h6A1.5 1.5 0 0114.5 3v6a1.5 1.5 0 01-1.5 1.5h-1.5"/></svg>';
    var maximizeSvg = '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="display:block"><rect x="2.5" y="2.5" width="11" height="11" rx="1.5"/></svg>';
    var collapseSvg = '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" style="display:block"><line x1="3" y1="8" x2="13" y2="8"/></svg>';

    var keys = Object.keys(_activeIndicators);
    for (var i = 0; i < keys.length; i++) {
        var info = _activeIndicators[keys[i]];
        if (!info || info.chartId !== chartId || !info.isSubplot) continue;
        var isThisPane = state.pane === info.paneIndex;

        // Update maximize button
        var btn = document.getElementById('tvchart-pane-ctrl-' + keys[i]);
        if (btn) {
            if (state.mode === 'maximized' && isThisPane) {
                btn.innerHTML = restoreSvg;
                btn.setAttribute('data-tooltip', 'Restore pane');
                btn.setAttribute('aria-label', 'Restore pane');
            } else {
                btn.innerHTML = maximizeSvg;
                btn.setAttribute('data-tooltip', 'Maximize pane');
                btn.setAttribute('aria-label', 'Maximize pane');
            }
        }

        // Update collapse button
        var cBtn = document.getElementById('tvchart-pane-collapse-' + keys[i]);
        if (cBtn) {
            if (state.mode === 'collapsed' && isThisPane) {
                cBtn.innerHTML = restoreSvg;
                cBtn.setAttribute('data-tooltip', 'Restore pane');
                cBtn.setAttribute('aria-label', 'Restore pane');
            } else {
                cBtn.innerHTML = collapseSvg;
                cBtn.setAttribute('data-tooltip', 'Collapse pane');
                cBtn.setAttribute('aria-label', 'Collapse pane');
            }
        }
    }
}

/**
 * Get or create a legend overlay for a specific pane, positioned absolutely
 * inside entry.container (the chart wrapper div).
 */
function _tvGetPaneLegendContainer(entry, paneIndex) {
    if (!entry._paneLegendEls) entry._paneLegendEls = {};
    if (entry._paneLegendEls[paneIndex]) return entry._paneLegendEls[paneIndex];

    var container = entry.container;
    if (!container || !entry.chart) return null;

    try {
        if (typeof entry.chart.panes !== 'function') return null;
        var panes = entry.chart.panes();
        if (!panes || !panes[paneIndex]) return null;

        // Compute the top offset and height of this pane relative to the container
        var top = 0;
        var paneHeight = 0;
        var paneHtml = typeof panes[paneIndex].getHTMLElement === 'function'
            ? panes[paneIndex].getHTMLElement() : null;
        if (paneHtml) {
            var paneRect = paneHtml.getBoundingClientRect();
            var containerRect = container.getBoundingClientRect();
            top = paneRect.top - containerRect.top;
            paneHeight = paneRect.height;
        } else {
            // Fallback: sum preceding pane heights + 1px separators
            for (var i = 0; i < paneIndex; i++) {
                var ps = typeof entry.chart.paneSize === 'function'
                    ? entry.chart.paneSize(i) : null;
                top += (ps ? ps.height : 0) + 1;
            }
            var curPs = typeof entry.chart.paneSize === 'function'
                ? entry.chart.paneSize(paneIndex) : null;
            paneHeight = curPs ? curPs.height : 0;
        }

        var overlay = document.createElement('div');
        overlay.className = 'tvchart-pane-legend';
        overlay.style.top = (top + 4) + 'px';
        if (paneHeight > 0) {
            overlay.style.maxHeight = (paneHeight - 8) + 'px';
            overlay.style.overflow = 'hidden';
        }
        container.appendChild(overlay);
        entry._paneLegendEls[paneIndex] = overlay;
        return overlay;
    } catch (e) {
        return null;
    }
}

/**
 * Reposition existing per-pane legend overlays (e.g. after pane resize via divider drag).
 */
function _tvRepositionPaneLegends(chartId) {
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (!entry || !entry._paneLegendEls || !entry.chart || !entry.container) return;
    var container = entry.container;
    var panes;
    try { panes = typeof entry.chart.panes === 'function' ? entry.chart.panes() : null; } catch (e) { return; }
    if (!panes) return;

    for (var pi in entry._paneLegendEls) {
        var overlay = entry._paneLegendEls[pi];
        if (!overlay) continue;
        var idx = Number(pi);
        var paneHtml = panes[idx] && typeof panes[idx].getHTMLElement === 'function'
            ? panes[idx].getHTMLElement() : null;
        if (paneHtml) {
            var paneRect = paneHtml.getBoundingClientRect();
            var containerRect = container.getBoundingClientRect();
            overlay.style.top = (paneRect.top - containerRect.top + 4) + 'px';
            if (paneRect.height > 0) {
                overlay.style.maxHeight = (paneRect.height - 8) + 'px';
            }
        }
    }

    // Also keep the main legend box tracking its pane (after swaps)
    _tvRepositionMainLegend(entry, chartId);
}

function _tvRebuildIndicatorLegend(chartId) {
    var indBox = _tvScopedById(chartId, 'tvchart-legend-indicators');
    if (!indBox) return;
    indBox.innerHTML = '';

    // Clean up previous per-pane legend overlays
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (entry && entry._paneLegendEls) {
        for (var pi in entry._paneLegendEls) {
            if (entry._paneLegendEls[pi] && entry._paneLegendEls[pi].parentNode) {
                entry._paneLegendEls[pi].parentNode.removeChild(entry._paneLegendEls[pi]);
            }
        }
    }
    if (entry) entry._paneLegendEls = {};

    // Compute total pane count for directional button logic
    var totalPanes = 0;
    if (entry && entry.chart && typeof entry.chart.panes === 'function') {
        try { totalPanes = entry.chart.panes().length; } catch (e) {}
    }

    var keys = Object.keys(_activeIndicators);
    var shown = {};
    for (var i = 0; i < keys.length; i++) {
        var sid = keys[i];
        var ai = _activeIndicators[sid];
        if (ai.chartId !== chartId) continue;
        if (ai.group && shown[ai.group]) continue;
        if (ai.group) shown[ai.group] = true;
        (function(seriesId, info) {
            var row = document.createElement('div');
            row.className = 'tvchart-legend-row tvchart-ind-row';
            row.id = 'tvchart-ind-row-' + seriesId;
            row.dataset.hidden = info.hidden ? '1' : '0';
            var dot = document.createElement('span');
            dot.className = 'tvchart-ind-dot';
            dot.style.background = info.color;
            row.appendChild(dot);
            var nameSp = document.createElement('span');
            nameSp.className = 'tvchart-ind-name';
            nameSp.style.color = info.color;
            // Extract base name (remove any trailing period in parentheses from the stored name)
            var baseName = info.group ? 'BB' : (info.name || '').replace(/\s*\(\d+\)\s*$/, '');
            var indLabel;
            if (info.group && info.type === 'bollinger-bands') {
                // TradingView format: "BB 20 2 0 SMA"
                indLabel = 'BB ' + (info.period || 20) + ' ' + (info.multiplier || 2) + ' ' + (info.offset || 0) + ' ' + (info.maType || 'SMA');
            } else {
                indLabel = baseName + (info.period ? ' ' + info.period : '');
            }
            // Binary indicators: show "Indicator source PrimarySymbol / SecondarySymbol"
            if (info.secondarySeriesId) {
                var indEntry = window.__PYWRY_TVCHARTS__[info.chartId];
                var priSym = '';
                var secSym = '';
                if (indEntry) {
                    // Primary symbol from chart title / symbolInfo
                    priSym = (indEntry._resolvedSymbolInfo && indEntry._resolvedSymbolInfo.main && indEntry._resolvedSymbolInfo.main.ticker)
                        || (indEntry.payload && indEntry.payload.title)
                        || '';
                    // Secondary symbol from compare tracking
                    secSym = (indEntry._compareSymbols && indEntry._compareSymbols[info.secondarySeriesId]) || '';
                }
                var srcLabel = info.primarySource || 'close';
                indLabel = baseName + ' ' + srcLabel + ' ' + priSym + ' / ' + secSym;
            }
            nameSp.textContent = indLabel;
            row.appendChild(nameSp);
            // For grouped indicators (BB), add a value span per group member
            if (info.group) {
                var gKeys = Object.keys(_activeIndicators);
                for (var gvi = 0; gvi < gKeys.length; gvi++) {
                    if (_activeIndicators[gKeys[gvi]].group === info.group) {
                        var gValSp = document.createElement('span');
                        gValSp.className = 'tvchart-ind-val';
                        gValSp.id = 'tvchart-ind-val-' + gKeys[gvi];
                        gValSp.style.color = _activeIndicators[gKeys[gvi]].color;
                        row.appendChild(gValSp);
                    }
                }
            } else {
                var valSp = document.createElement('span');
                valSp.className = 'tvchart-ind-val';
                valSp.id = 'tvchart-ind-val-' + seriesId;
                row.appendChild(valSp);
            }
            var ctrl = document.createElement('span');
            ctrl.className = 'tvchart-legend-row-actions tvchart-ind-ctrl';
            var upArrowSvg = '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" style="display:block"><path d="M8 13V3"/><path d="M3 7l5-5 5 5"/></svg>';
            var downArrowSvg = '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" style="display:block"><path d="M8 3v10"/><path d="M3 9l5 5 5-5"/></svg>';
            var maximizeSvg = '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="display:block"><rect x="2.5" y="2.5" width="11" height="11" rx="1.5"/></svg>';
            var hideSvg = '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" style="display:block"><path d="M1.8 8s2.2-3.8 6.2-3.8S14.2 8 14.2 8s-2.2 3.8-6.2 3.8S1.8 8 1.8 8z"/><circle cx="8" cy="8" r="1.9"/></svg>';
            var showSvg = '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" style="display:block"><path d="M1.8 8s2.2-3.8 6.2-3.8S14.2 8 14.2 8s-2.2 3.8-6.2 3.8S1.8 8 1.8 8z"/><circle cx="8" cy="8" r="1.9"/><line x1="3" y1="13" x2="13" y2="3" stroke-width="1.6"/></svg>';
            var settingsSvg = '<svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor" style="display:block"><path d="M8 10.2a2.2 2.2 0 100-4.4 2.2 2.2 0 000 4.4zm4.8-2.7a.5.5 0 01.3-.46l.46-.27a.5.5 0 00.18-.68l-.54-.94a.5.5 0 00-.68-.18l-.46.27a.5.5 0 01-.53-.05 4.4 4.4 0 00-.55-.32.5.5 0 01-.3-.45V3.9A.5.5 0 0010.19 3.5H9.12a.5.5 0 00-.5.46v.51a.5.5 0 01-.3.45 4.4 4.4 0 00-.55.32.5.5 0 01-.53.05l-.46-.27a.5.5 0 00-.68.18l-.54.94a.5.5 0 00.18.68l.46.27a.5.5 0 01.3.46v.02a.5.5 0 01-.3.46l-.46.27a.5.5 0 00-.18.68l.54.94a.5.5 0 00.68.18l.46-.27a.5.5 0 01.53.05c.17.12.35.22.55.32a.5.5 0 01.3.45v.51A.5.5 0 0010.19 12.5H9.12a.5.5 0 01-.5-.46v-.51a.5.5 0 00-.3-.45 4.4 4.4 0 01-.55-.32.5.5 0 00-.53.05l-.46.27a.5.5 0 01-.68-.18l-.54-.94a.5.5 0 01.18-.68l.46-.27a.5.5 0 00.3-.46v-.02z"/></svg>';
            var removeSvg = '<svg viewBox="0 0 16 16" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none" style="display:block"><line x1="4" y1="4" x2="12" y2="12"/><line x1="12" y1="4" x2="4" y2="12"/></svg>';
            var menuSvg = '<svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor" style="display:block"><circle cx="3.5" cy="8" r="1.2"/><circle cx="8" cy="8" r="1.2"/><circle cx="12.5" cy="8" r="1.2"/></svg>';
            var copySvg = '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" style="display:block"><rect x="5.2" y="3.6" width="7.2" height="8.6" rx="1.4"/><path d="M3.6 10.4V5.1c0-.9.7-1.6 1.6-1.6h4.4"/></svg>';

            // Pane move buttons for subplot indicators
            if (info.isSubplot) {
                var canMoveUp = info.paneIndex > 0;
                var canMoveDown = totalPanes > 0 && info.paneIndex < totalPanes - 1;
                if (canMoveUp) {
                    ctrl.appendChild(_tvLegendActionButton('Move pane up', upArrowSvg, function() {
                        _tvSwapIndicatorPane(chartId, seriesId, -1);
                    }));
                }
                if (canMoveDown) {
                    ctrl.appendChild(_tvLegendActionButton('Move pane down', downArrowSvg, function() {
                        _tvSwapIndicatorPane(chartId, seriesId, 1);
                    }));
                }
                // Maximize pane button
                var paneBtn = _tvLegendActionButton('Maximize pane', maximizeSvg, function() {
                    var pState = _tvGetPaneState(chartId);
                    var isThisPane = pState.pane === info.paneIndex;
                    if (pState.mode === 'maximized' && isThisPane) {
                        _tvRestorePanes(chartId);
                    } else {
                        _tvMaximizePane(chartId, info.paneIndex);
                    }
                });
                paneBtn.id = 'tvchart-pane-ctrl-' + seriesId;
                ctrl.appendChild(paneBtn);
                // Collapse pane button (minimize icon — horizontal line)
                var collapseSvg = '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" style="display:block"><line x1="3" y1="8" x2="13" y2="8"/></svg>';
                var collapseBtn = _tvLegendActionButton('Collapse pane', collapseSvg, function() {
                    var pState = _tvGetPaneState(chartId);
                    var isThisPane = pState.pane === info.paneIndex;
                    if (pState.mode === 'collapsed' && isThisPane) {
                        _tvRestorePanes(chartId);
                    } else {
                        _tvCollapsePane(chartId, info.paneIndex);
                    }
                });
                collapseBtn.id = 'tvchart-pane-collapse-' + seriesId;
                ctrl.appendChild(collapseBtn);
            }
            var eyeBtn = _tvLegendActionButton(info.hidden ? 'Show' : 'Hide', info.hidden ? showSvg : hideSvg, function(btn) {
                var hidden = !info.hidden;
                _tvSetIndicatorVisibility(chartId, seriesId, !hidden);
                row.dataset.hidden = hidden ? '1' : '0';
                btn.setAttribute('data-tooltip', hidden ? 'Show' : 'Hide');
                btn.setAttribute('aria-label', hidden ? 'Show' : 'Hide');
                btn.innerHTML = hidden ? showSvg : hideSvg;
            });
            eyeBtn.id = 'tvchart-eye-' + seriesId;
            ctrl.appendChild(eyeBtn);
            ctrl.appendChild(_tvLegendActionButton('Settings', settingsSvg, function() {
                _tvShowIndicatorSettings(seriesId);
            }));
            ctrl.appendChild(_tvLegendActionButton('Remove', removeSvg, function() {
                _tvRemoveIndicator(seriesId);
            }));
            ctrl.appendChild(_tvLegendActionButton('More', menuSvg, function(btn) {
                var fullName = (info.name || '').trim();
                var groupName = info.group ? 'Indicator group' : 'Single indicator';
                _tvOpenLegendItemMenu(btn, [
                    {
                        label: info.hidden ? 'Show' : 'Hide',
                        icon: info.hidden ? showSvg : hideSvg,
                        run: function() {
                            var hidden = !info.hidden;
                            _tvSetIndicatorVisibility(chartId, seriesId, !hidden);
                            row.dataset.hidden = hidden ? '1' : '0';
                            var eb = document.getElementById('tvchart-eye-' + seriesId);
                            if (eb) {
                                eb.setAttribute('data-tooltip', hidden ? 'Show' : 'Hide');
                                eb.setAttribute('aria-label', hidden ? 'Show' : 'Hide');
                                eb.innerHTML = hidden ? showSvg : hideSvg;
                            }
                        },
                    },
                    {
                        label: 'Settings',
                        icon: settingsSvg,
                        run: function() { _tvShowIndicatorSettings(seriesId); },
                    },
                    {
                        label: 'Remove',
                        icon: removeSvg,
                        run: function() { _tvRemoveIndicator(seriesId); },
                    },
                    { separator: true },
                    {
                        label: 'Copy Name',
                        icon: copySvg,
                        meta: fullName || groupName,
                        disabled: !fullName,
                        tooltip: fullName || 'Indicator name unavailable',
                        run: function() { _tvLegendCopyToClipboard(fullName); },
                    },
                    {
                        label: 'Reset Visibility',
                        icon: hideSvg,
                        meta: groupName,
                        run: function() {
                            _tvSetIndicatorVisibility(chartId, seriesId, true);
                            row.dataset.hidden = '0';
                            var eb = document.getElementById('tvchart-eye-' + seriesId);
                            if (eb) {
                                eb.setAttribute('data-tooltip', 'Hide');
                                eb.setAttribute('aria-label', 'Hide');
                                eb.innerHTML = hideSvg;
                            }
                        },
                    },
                ]);
            }));
            row.appendChild(ctrl);

            // Route subplot indicators to per-pane legend overlays.
            // Always append to indBox first; a deferred pass will relocate
            // subplot rows into their pane overlays once the DOM is laid out.
            indBox.appendChild(row);
        })(sid, ai);
    }

    // Deferred: move subplot indicator rows into per-pane overlays once
    // LWC has finished laying out pane DOM elements (getBoundingClientRect
    // returns zeros when called synchronously after addSeries).
    if (entry && entry.chart) {
        requestAnimationFrame(function() {
            _tvRelocateSubplotLegends(chartId);
            _tvUpdatePaneControlButtons(chartId);
        });
    }
}

/**
 * Move subplot indicator legend rows from the main indBox into per-pane
 * overlay containers.  Called after a rAF so LWC pane DOM is laid out.
 */
function _tvRelocateSubplotLegends(chartId) {
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (!entry || !entry.chart) return;
    var mainPane = _tvFindMainChartPane(entry);
    var keys = Object.keys(_activeIndicators);
    var shown = {};
    for (var i = 0; i < keys.length; i++) {
        var sid = keys[i];
        var ai = _activeIndicators[sid];
        if (ai.chartId !== chartId) continue;
        if (ai.group && shown[ai.group]) continue;
        if (ai.group) shown[ai.group] = true;
        // Keep non-subplot and indicators in the main chart pane in indBox
        if (!ai.isSubplot || ai.paneIndex === mainPane) continue;
        var row = document.getElementById('tvchart-ind-row-' + sid);
        if (!row) continue;
        var paneEl = _tvGetPaneLegendContainer(entry, ai.paneIndex);
        if (paneEl) {
            paneEl.appendChild(row); // moves the node out of indBox
        }
    }
}

function _tvUpdateIndicatorLegendValues(chartId, param) {
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (!entry) return;
    // Reposition pane legends (handles pane divider drag)
    _tvRepositionPaneLegends(chartId);
    var keys = Object.keys(_activeIndicators);
    for (var i = 0; i < keys.length; i++) {
        var sid = keys[i];
        var info = _activeIndicators[sid];
        if (info.chartId !== chartId) continue;
        var valSp = _tvScopedById(chartId, 'tvchart-ind-val-' + sid);
        if (!valSp) continue;
        var series = entry.seriesMap[sid];
        if (!series) continue;
        var d = param && param.seriesData ? param.seriesData.get(series) : null;
        if (d && d.value !== undefined) {
            valSp.textContent = '\u00a0' + Number(d.value).toFixed(2);
        }
    }
}

function _tvShowIndicatorSettings(seriesId) {
    var info = _activeIndicators[seriesId];
    if (!info) return;
    var ds = window.__PYWRY_DRAWINGS__[info.chartId] || _tvEnsureDrawingLayer(info.chartId);
    if (!ds || !ds.uiLayer) return;

    var type = info.type || info.name;
    var baseName = info.name.replace(/\s*\(\d+\)\s*$/, '');
    var isBB = !!(info.group && type === 'bollinger-bands');
    var isRSI = baseName === 'RSI';
    var isATR = baseName === 'ATR';
    var isVWAP = baseName === 'VWAP';
    var isVolSMA = baseName === 'Volume SMA';
    var isMA = baseName === 'SMA' || baseName === 'EMA' || baseName === 'WMA';
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
        // BB-specific fill settings
        showBandFill: info.showBandFill !== undefined ? info.showBandFill : true,
        bandFillColor: info.bandFillColor || '#2196f3',
        bandFillOpacity: info.bandFillOpacity !== undefined ? info.bandFillOpacity : 100,
        // RSI-specific
        smoothingLine: info.smoothingLine || 'SMA',
        smoothingLength: info.smoothingLength || 14,
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
    panel.style.cssText = 'width:400px;flex-direction:column;max-height:75vh;position:relative;';
    overlay.appendChild(panel);

    var header = document.createElement('div');
    header.className = 'tv-settings-header';
    header.style.cssText = 'position:relative;flex-direction:column;align-items:stretch;padding-bottom:0;';
    var hdrRow = document.createElement('div');
    hdrRow.style.cssText = 'display:flex;align-items:center;gap:8px;';
    var titleEl = document.createElement('h3');
    titleEl.textContent = (isBB ? 'Bollinger Bands' : info.name) + ' Settings';
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
    body.style.cssText = 'flex:1;overflow-y:auto;min-height:80px;';
    panel.appendChild(body);

    var foot = document.createElement('div');
    foot.className = 'tv-settings-footer';
    foot.style.position = 'relative';
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
    function addCheckRow(parent, label, val, onChange) {
        var row = document.createElement('div');
        row.className = 'tv-settings-row tv-settings-row-spaced';
        var lbl = document.createElement('label'); lbl.textContent = label; row.appendChild(lbl);
        var cb = document.createElement('input'); cb.type = 'checkbox'; cb.className = 'ts-checkbox';
        cb.checked = !!val;
        cb.addEventListener('change', function() { onChange(cb.checked); });
        row.appendChild(cb); parent.appendChild(row);
    }

    // Plot-style row: checkbox + color swatch + line style selector
    function addPlotStyleRow(parent, label, plotDraft) {
        var row = document.createElement('div');
        row.className = 'tv-settings-row tv-settings-row-spaced';
        row.style.cssText = 'display:flex;align-items:center;gap:8px;';
        var cb = document.createElement('input'); cb.type = 'checkbox'; cb.className = 'ts-checkbox';
        cb.checked = plotDraft.visible !== false;
        cb.addEventListener('change', function() { plotDraft.visible = cb.checked; });
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
                }
            );
        });
        row.appendChild(swatch);
        var wSel = document.createElement('select'); wSel.className = 'ts-select'; wSel.style.width = '60px';
        [{v:1,l:'1px'},{v:2,l:'2px'},{v:3,l:'3px'},{v:4,l:'4px'}].forEach(function(o) {
            var opt = document.createElement('option'); opt.value = o.v; opt.textContent = o.l;
            if (Number(o.v) === Number(plotDraft.lineWidth)) opt.selected = true; wSel.appendChild(opt);
        });
        wSel.addEventListener('change', function() { plotDraft.lineWidth = Number(wSel.value); });
        row.appendChild(wSel);
        // Line style selector
        var lsSel = document.createElement('select'); lsSel.className = 'ts-select'; lsSel.style.width = '80px';
        [{v:0,l:'Solid'},{v:1,l:'Dashed'},{v:2,l:'Dotted'},{v:3,l:'Lg Dash'}].forEach(function(o) {
            var opt = document.createElement('option'); opt.value = o.v; opt.textContent = o.l;
            if (Number(o.v) === Number(plotDraft.lineStyle || 0)) opt.selected = true; lsSel.appendChild(opt);
        });
        lsSel.addEventListener('change', function() { plotDraft.lineStyle = Number(lsSel.value); });
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
            if (info.period > 0) {
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

            // SMA / EMA / WMA inputs
            if (isMA) {
                addSelectRow(body, 'Source', _SRC_OPTS, draft.source, function(v) { draft.source = v; });
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
                    addSelectRow(body, 'Source', _SRC_OPTS, draft.source, function(v) { draft.source = v; });
                    addSelectRow(body, 'Method', [
                        { v: 'SMA', l: 'SMA' }, { v: 'EMA', l: 'EMA' }, { v: 'WMA', l: 'WMA' },
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

            if (!hasInputs) {
                var noRow = document.createElement('div');
                noRow.className = 'tv-settings-row';
                noRow.style.cssText = 'color:var(--pywry-tvchart-text-muted,#787b86);font-size:12px;';
                noRow.textContent = 'No configurable inputs.';
                body.appendChild(noRow);
            }

        // ===================== STYLE TAB =====================
        } else if (activeTab === 'style') {
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

            // ATR / generic single-series: just color + width already covered above

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
    _tvAppendOverlay(chartId, overlay);
}

function _tvApplyIndicatorSettings(seriesId, newSettings) {
    var info = _activeIndicators[seriesId];
    if (!info) return;
    var entry = window.__PYWRY_TVCHARTS__[info.chartId];
    if (!entry) return;
    var rawData = _tvSeriesRawData(entry, info.sourceSeriesId || 'main');
    var periodChanged = !!(newSettings.period && info.period > 0 && newSettings.period !== info.period);
    var multChanged = !!(info.group && newSettings.multiplier !== (info.multiplier || 2));
    var sourceChanged = !!(newSettings.source && newSettings.source !== info.source);
    var methodChanged = !!(newSettings.method && newSettings.method !== info.method);
    var maTypeChanged = !!(newSettings.maType && newSettings.maType !== (info.maType || 'SMA'));
    var offsetChanged = (newSettings.offset !== undefined && newSettings.offset !== (info.offset || 0));
    var primarySourceChanged = !!(newSettings.primarySource && newSettings.primarySource !== info.primarySource);
    var secondarySourceChanged = !!(newSettings.secondarySource && newSettings.secondarySource !== info.secondarySource);
    var type = info.type || info.name;

    // Apply per-plot styles
    var styleSids = [];
    if (info.group) {
        var allKeys = Object.keys(_activeIndicators);
        for (var k = 0; k < allKeys.length; k++) { if (_activeIndicators[allKeys[k]].group === info.group) styleSids.push(allKeys[k]); }
    } else { styleSids = [seriesId]; }
    for (var si = 0; si < styleSids.length; si++) {
        var ss = entry.seriesMap[styleSids[si]];
        var plotDraft = newSettings.plotStyles && newSettings.plotStyles[styleSids[si]];
        var isBaselineSeries = !!(_activeIndicators[styleSids[si]] && _activeIndicators[styleSids[si]].isBaseline);
        if (plotDraft) {
            var opts;
            if (isBaselineSeries) {
                opts = { topLineColor: plotDraft.color, bottomLineColor: plotDraft.color, lineWidth: plotDraft.lineWidth, lineStyle: plotDraft.lineStyle || 0 };
            } else {
                opts = { color: plotDraft.color, lineWidth: plotDraft.lineWidth, lineStyle: plotDraft.lineStyle || 0 };
            }
            if (plotDraft.visible === false) opts.visible = false;
            else opts.visible = true;
            if (ss) { try { ss.applyOptions(opts); } catch(e) {} }
            if (_activeIndicators[styleSids[si]]) {
                _activeIndicators[styleSids[si]].color = plotDraft.color;
                _activeIndicators[styleSids[si]].lineWidth = plotDraft.lineWidth;
                _activeIndicators[styleSids[si]].lineStyle = plotDraft.lineStyle;
                _activeIndicators[styleSids[si]].visible = plotDraft.visible;
            }
        } else {
            // Fallback to draft top-level color/lineWidth
            if (isBaselineSeries) {
                if (ss) { try { ss.applyOptions({ topLineColor: newSettings.color, bottomLineColor: newSettings.color, lineWidth: newSettings.lineWidth }); } catch(e) {} }
            } else {
                if (ss) { try { ss.applyOptions({ color: newSettings.color, lineWidth: newSettings.lineWidth }); } catch(e) {} }
            }
            if (_activeIndicators[styleSids[si]]) { _activeIndicators[styleSids[si]].color = newSettings.color; _activeIndicators[styleSids[si]].lineWidth = newSettings.lineWidth; }
        }
    }

    // Apply baseline fill settings for binary indicators
    if (info.isBaseline) {
        var bSeries = entry.seriesMap[seriesId];
        if (bSeries) {
            var fillOpts = {};
            if (newSettings.showPositiveFill) {
                var pc = newSettings.positiveFillColor || '#26a69a';
                var pOp = _tvClamp(_tvToNumber(newSettings.positiveFillOpacity, 100), 0, 100) / 100;
                fillOpts.topFillColor1 = _tvHexToRgba(pc, 0.28 * pOp);
                fillOpts.topFillColor2 = _tvHexToRgba(pc, 0.05 * pOp);
            } else {
                fillOpts.topFillColor1 = 'transparent';
                fillOpts.topFillColor2 = 'transparent';
            }
            if (newSettings.showNegativeFill) {
                var nc = newSettings.negativeFillColor || '#ef5350';
                var nOp = _tvClamp(_tvToNumber(newSettings.negativeFillOpacity, 100), 0, 100) / 100;
                fillOpts.bottomFillColor1 = _tvHexToRgba(nc, 0.05 * nOp);
                fillOpts.bottomFillColor2 = _tvHexToRgba(nc, 0.28 * nOp);
            } else {
                fillOpts.bottomFillColor1 = 'transparent';
                fillOpts.bottomFillColor2 = 'transparent';
            }
            try { bSeries.applyOptions(fillOpts); } catch(e) {}
        }
        info.showPositiveFill = newSettings.showPositiveFill;
        info.positiveFillColor = newSettings.positiveFillColor;
        info.positiveFillOpacity = newSettings.positiveFillOpacity;
        info.showNegativeFill = newSettings.showNegativeFill;
        info.negativeFillColor = newSettings.negativeFillColor;
        info.negativeFillOpacity = newSettings.negativeFillOpacity;
        info.precision = newSettings.precision;
        info.labelsOnPriceScale = newSettings.labelsOnPriceScale;
        info.valuesInStatusLine = newSettings.valuesInStatusLine;
        info.inputsInStatusLine = newSettings.inputsInStatusLine;
        // Apply precision
        if (bSeries && newSettings.precision && newSettings.precision !== 'default') {
            try { bSeries.applyOptions({ priceFormat: { type: 'price', precision: Number(newSettings.precision), minMove: Math.pow(10, -Number(newSettings.precision)) } }); } catch(e) {}
        }
        // Apply labels on price scale
        if (bSeries) {
            try { bSeries.applyOptions({ lastValueVisible: newSettings.labelsOnPriceScale !== false }); } catch(e) {}
        }
    }

    // Store RSI-specific settings
    if (newSettings.showUpperLimit !== undefined) {
        info.showUpperLimit = newSettings.showUpperLimit;
        info.upperLimitValue = newSettings.upperLimitValue;
        info.upperLimitColor = newSettings.upperLimitColor;
        info.showLowerLimit = newSettings.showLowerLimit;
        info.lowerLimitValue = newSettings.lowerLimitValue;
        info.lowerLimitColor = newSettings.lowerLimitColor;
        info.showMiddleLimit = newSettings.showMiddleLimit;
        info.middleLimitValue = newSettings.middleLimitValue;
        info.middleLimitColor = newSettings.middleLimitColor;
        info.showBackground = newSettings.showBackground;
        info.bgColor = newSettings.bgColor;
        info.bgOpacity = newSettings.bgOpacity;
    }
    // Store smoothing settings
    if (newSettings.smoothingLine !== undefined) info.smoothingLine = newSettings.smoothingLine;
    if (newSettings.smoothingLength !== undefined) info.smoothingLength = newSettings.smoothingLength;
    // Store BB-specific settings (propagate to all group members)
    if (type === 'bollinger-bands' && info.group) {
        var bbKeys = Object.keys(_activeIndicators);
        for (var bk = 0; bk < bbKeys.length; bk++) {
            if (_activeIndicators[bbKeys[bk]].group !== info.group) continue;
            _activeIndicators[bbKeys[bk]].showBandFill = newSettings.showBandFill;
            _activeIndicators[bbKeys[bk]].bandFillColor = newSettings.bandFillColor;
            _activeIndicators[bbKeys[bk]].bandFillOpacity = newSettings.bandFillOpacity;
            _activeIndicators[bbKeys[bk]].precision = newSettings.precision;
            _activeIndicators[bbKeys[bk]].labelsOnPriceScale = newSettings.labelsOnPriceScale;
            _activeIndicators[bbKeys[bk]].valuesInStatusLine = newSettings.valuesInStatusLine;
            _activeIndicators[bbKeys[bk]].inputsInStatusLine = newSettings.inputsInStatusLine;
        }
    }
    // Store visibility
    if (newSettings.visibility) info.visibility = newSettings.visibility;

    // Recompute if period / multiplier / source / method / maType / offset changed
    if ((periodChanged || multChanged || sourceChanged || methodChanged || maTypeChanged || offsetChanged || primarySourceChanged || secondarySourceChanged) && rawData) {
        var baseName = info.name.replace(/\s*\(\d+\)\s*$/, '');
        var newPeriod = newSettings.period || info.period;
        var newMult = newSettings.multiplier || info.multiplier || 2;

        if (type === 'moving-average-ex') {
            var maSource = newSettings.source || info.source || 'close';
            var maMethod = newSettings.method || info.method || 'SMA';
            var maBase = rawData.map(function(p) { return { time: p.time, value: _tvIndicatorValue(p, maSource) }; });
            var maFn = maMethod === 'EMA' ? _computeEMA : (maMethod === 'WMA' ? _computeWMA : _computeSMA);
            var maVals = maFn(maBase, Math.max(1, newPeriod), 'value');
            var maSeries = entry.seriesMap[seriesId];
            if (maSeries) maSeries.setData(maVals.filter(function(v) { return v.value !== undefined; }));
            info.period = Math.max(1, newPeriod);
            info.source = maSource;
            info.method = maMethod;
        } else if (type === 'momentum') {
            var momSource = newSettings.source || info.source || 'close';
            var momSeries = entry.seriesMap[seriesId];
            if (momSeries) momSeries.setData(_tvComputeMomentum(rawData, Math.max(1, newPeriod), momSource).filter(function(v) { return v.value !== undefined; }));
            info.period = Math.max(1, newPeriod);
            info.source = momSource;
        } else if (type === 'percent-change') {
            var pcSource = newSettings.source || info.source || 'close';
            var pcSeries = entry.seriesMap[seriesId];
            if (pcSeries) pcSeries.setData(_tvComputePercentChange(rawData, pcSource).filter(function(v) { return v.value !== undefined; }));
            info.source = pcSource;
        } else if (type === 'correlation') {
            var secData = _tvSeriesRawData(entry, info.secondarySeriesId);
            var cSeries = entry.seriesMap[seriesId];
            var psrc = newSettings.primarySource || info.primarySource || 'close';
            var ssrc = newSettings.secondarySource || info.secondarySource || 'close';
            if (cSeries) cSeries.setData(_tvComputeCorrelation(rawData, secData, Math.max(2, newPeriod), psrc, ssrc).filter(function(v) { return v.value !== undefined; }));
            info.period = Math.max(2, newPeriod);
            info.primarySource = psrc;
            info.secondarySource = ssrc;
        } else if (type === 'spread' || type === 'ratio' || type === 'sum' || type === 'product') {
            var secData2 = _tvSeriesRawData(entry, info.secondarySeriesId);
            var biSeries = entry.seriesMap[seriesId];
            var psrc2 = newSettings.primarySource || info.primarySource || 'close';
            var ssrc2 = newSettings.secondarySource || info.secondarySource || 'close';
            if (biSeries) biSeries.setData(_tvComputeBinary(rawData, secData2, psrc2, ssrc2, type).filter(function(v) { return v.value !== undefined; }));
            info.primarySource = psrc2;
            info.secondarySource = ssrc2;
        } else if (type === 'average-price') {
            var apSeries = entry.seriesMap[seriesId];
            if (apSeries) apSeries.setData(_tvComputeAveragePrice(rawData).filter(function(v) { return v.value !== undefined; }));
        } else if (type === 'median-price') {
            var mpSeries = entry.seriesMap[seriesId];
            if (mpSeries) mpSeries.setData(_tvComputeMedianPrice(rawData).filter(function(v) { return v.value !== undefined; }));
        } else if (type === 'weighted-close') {
            var wcSeries = entry.seriesMap[seriesId];
            if (wcSeries) wcSeries.setData(_tvComputeWeightedClose(rawData).filter(function(v) { return v.value !== undefined; }));
        } else if (baseName === 'SMA' || baseName === 'EMA' || baseName === 'WMA') {
            var maSource2 = newSettings.source || info.source || 'close';
            var fn2 = baseName === 'SMA' ? _computeSMA : baseName === 'EMA' ? _computeEMA : _computeWMA;
            var s2 = entry.seriesMap[seriesId];
            var maBase2 = rawData.map(function(p) { return { time: p.time, value: _tvIndicatorValue(p, maSource2) }; });
            if (s2) s2.setData(fn2(maBase2, newPeriod, 'value').filter(function(v) { return v.value !== undefined; }));
            info.period = newPeriod;
            info.source = maSource2;
        } else if (info.group && type === 'bollinger-bands') {
            var bbSource = newSettings.source || info.source || 'close';
            var bbMaType = newSettings.maType || info.maType || 'SMA';
            var bbOffset = newSettings.offset !== undefined ? newSettings.offset : (info.offset || 0);
            var bbBase = rawData.map(function(p) { return { time: p.time, close: _tvIndicatorValue(p, bbSource) }; });
            var bb2 = _computeBollingerBands(bbBase, newPeriod, newMult, bbMaType, bbOffset);
            var gKeys = Object.keys(_activeIndicators);
            for (var gi = 0; gi < gKeys.length; gi++) {
                if (_activeIndicators[gKeys[gi]].group !== info.group) continue;
                _activeIndicators[gKeys[gi]].period = newPeriod;
                _activeIndicators[gKeys[gi]].multiplier = newMult;
                _activeIndicators[gKeys[gi]].source = bbSource;
                _activeIndicators[gKeys[gi]].maType = bbMaType;
                _activeIndicators[gKeys[gi]].offset = bbOffset;
                var gs2 = entry.seriesMap[gKeys[gi]];
                var bbD = gKeys[gi].indexOf('upper') >= 0 ? bb2.upper : gKeys[gi].indexOf('lower') >= 0 ? bb2.lower : bb2.middle;
                if (gs2) gs2.setData(bbD.filter(function(v) { return v.value !== undefined; }));
            }
        } else if (info.name === 'RSI') {
            var rsiSource = newSettings.source || info.source || 'close';
            var rsiBase = rawData.map(function(p) { return { time: p.time, close: _tvIndicatorValue(p, rsiSource) }; });
            var rsN = entry.seriesMap[seriesId];
            if (rsN) rsN.setData(_computeRSI(rsiBase, newPeriod).filter(function(v) { return v.value !== undefined; }));
            info.period = newPeriod;
            info.source = rsiSource;
        } else if (info.name === 'ATR') {
            var atN = entry.seriesMap[seriesId];
            if (atN) atN.setData(_computeATR(rawData, newPeriod).filter(function(v) { return v.value !== undefined; }));
            info.period = newPeriod;
        } else if (info.name === 'Volume SMA') {
            var vN = entry.seriesMap[seriesId];
            if (vN) vN.setData(_computeSMA(rawData, newPeriod, 'volume').filter(function(v) { return v.value !== undefined; }));
            info.period = newPeriod;
        }
    }
    _tvRebuildIndicatorLegend(info.chartId);
    // Re-render BB fills after settings change
    if (type === 'bollinger-bands') {
        _tvEnsureBBFillPrimitive(info.chartId);
        _tvUpdateBBFill(info.chartId);
    }
}

function _tvHideIndicatorsPanel() {
    if (_indicatorsOverlay && _indicatorsOverlay.parentNode) {
        _indicatorsOverlay.parentNode.removeChild(_indicatorsOverlay);
    }
    if (_indicatorsOverlayChartId) _tvSetChartInteractionLocked(_indicatorsOverlayChartId, false);
    _indicatorsOverlay = null;
    _indicatorsOverlayChartId = null;
    _tvRefreshLegendVisibility();
}

function _tvShowIndicatorsPanel(chartId) {
    _tvHideIndicatorsPanel();
    chartId = chartId || 'main';
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (!entry) { var keys = Object.keys(window.__PYWRY_TVCHARTS__); if (keys.length) { chartId = keys[0]; entry = window.__PYWRY_TVCHARTS__[chartId]; } }
    if (!entry) return;

    var ds = window.__PYWRY_DRAWINGS__[chartId] || _tvEnsureDrawingLayer(chartId);
    if (!ds) return;

    var overlay = document.createElement('div');
    overlay.className = 'tv-indicators-overlay';
    _indicatorsOverlay = overlay;
    _indicatorsOverlayChartId = chartId;
    _tvSetChartInteractionLocked(chartId, true);
    _tvRefreshLegendVisibility();
    overlay.addEventListener('click', function(e) {
        if (e.target === overlay) _tvHideIndicatorsPanel();
    });
    overlay.addEventListener('mousedown', function(e) { e.stopPropagation(); });
    overlay.addEventListener('wheel', function(e) { e.stopPropagation(); });

    var panel = document.createElement('div');
    panel.className = 'tv-indicators-panel';
    overlay.appendChild(panel);

    // Header
    var header = document.createElement('div');
    header.className = 'tv-indicators-header';
    var title = document.createElement('h3');
    title.textContent = 'Indicators';
    header.appendChild(title);
    var closeBtn = document.createElement('button');
    closeBtn.className = 'tv-settings-close';
    closeBtn.innerHTML = '<svg viewBox="0 0 16 16"><line x1="3" y1="3" x2="13" y2="13"/><line x1="13" y1="3" x2="3" y2="13"/></svg>';
    closeBtn.addEventListener('click', function() { _tvHideIndicatorsPanel(); });
    header.appendChild(closeBtn);
    panel.appendChild(header);

    // Search
    var searchWrap = document.createElement('div');
    searchWrap.className = 'tv-indicators-search pywry-search-wrapper pywry-search-inline';
    searchWrap.style.position = 'relative';
    var searchIcon = document.createElement('span');
    searchIcon.className = 'pywry-search-icon';
    searchIcon.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15.5 14h-.79l-.28-.27A6.47 6.47 0 0016 9.5 6.5 6.5 0 109.5 16a6.47 6.47 0 004.23-1.57l.27.28v.79L19 20.49 20.49 19 15.5 14zM9.5 14A4.5 4.5 0 119.5 5a4.5 4.5 0 010 9z"/></svg>';
    searchWrap.appendChild(searchIcon);
    var searchInp = document.createElement('input');
    searchInp.type = 'text';
    searchInp.className = 'pywry-search-input';
    searchInp.placeholder = 'Search';
    searchInp.addEventListener('keydown', function(e) { e.stopPropagation(); });
    searchWrap.appendChild(searchInp);
    panel.appendChild(searchWrap);

    // List
    var list = document.createElement('div');
    list.className = 'tv-indicators-list pywry-scroll-container';
    panel.appendChild(list);
    try {
        if (window.PYWRY_SCROLLBARS && typeof window.PYWRY_SCROLLBARS.setup === 'function') {
            window.PYWRY_SCROLLBARS.setup(list);
        }
    } catch(e) {}

    // Active indicators section
    function renderList(filter) {
        list.innerHTML = '';

        // Active indicators
        var activeKeys = Object.keys(_activeIndicators);
        if (activeKeys.length > 0) {
            var actSec = document.createElement('div');
            actSec.className = 'tv-indicators-section';
            actSec.textContent = 'ACTIVE';
            list.appendChild(actSec);

            var shown = {};
            for (var a = 0; a < activeKeys.length; a++) {
                var ai = _activeIndicators[activeKeys[a]];
                if (ai.group && shown[ai.group]) continue;
                if (ai.group) shown[ai.group] = true;

                (function(sid, info) {
                    var item = document.createElement('div');
                    item.className = 'tv-indicator-item';
                    var nameSpan = document.createElement('span');
                    nameSpan.className = 'ind-name';
                    // Extract base name (remove any trailing period in parentheses from the stored name)
                    var baseName = (info.name || '').replace(/\s*\(\d+\)\s*$/, '');
                    nameSpan.textContent = baseName + (info.period ? ' (' + info.period + ')' : '');
                    nameSpan.style.color = info.color;
                    item.appendChild(nameSpan);
                    var gearBtn = document.createElement('span');
                    gearBtn.innerHTML = '\u2699';
                    gearBtn.title = 'Settings';
                    gearBtn.style.cssText = 'cursor:pointer;font-size:14px;line-height:1;padding:0 3px;color:var(--pywry-tvchart-text-muted);border-radius:3px;';
                    gearBtn.addEventListener('mouseenter', function() { gearBtn.style.color = 'var(--pywry-tvchart-text)'; gearBtn.style.background = 'var(--pywry-tvchart-hover)'; });
                    gearBtn.addEventListener('mouseleave', function() { gearBtn.style.color = 'var(--pywry-tvchart-text-muted)'; gearBtn.style.background = ''; });
                    gearBtn.addEventListener('click', function(e) {
                        e.stopPropagation();
                        _tvHideIndicatorsPanel();
                        _tvShowIndicatorSettings(sid);
                    });
                    item.appendChild(gearBtn);
                    var removeBtn = document.createElement('span');
                    removeBtn.textContent = '\u00d7';
                    removeBtn.style.cssText = 'cursor:pointer;font-size:18px;color:' + _cssVar('--pywry-draw-danger', '#f44336') + ';';
                    removeBtn.addEventListener('click', function(e) {
                        e.stopPropagation();
                        _tvRemoveIndicator(sid);
                        renderList(searchInp.value);
                    });
                    item.appendChild(removeBtn);
                    list.appendChild(item);
                })(activeKeys[a], ai);
            }
        }

        // Catalog
        var secNames = {};
        var filtered = _INDICATOR_CATALOG.filter(function(ind) {
            if (!filter) return true;
            return ind.fullName.toLowerCase().indexOf(filter.toLowerCase()) !== -1 ||
                   ind.name.toLowerCase().indexOf(filter.toLowerCase()) !== -1;
        });

        var currentCat = '';
        for (var ci = 0; ci < filtered.length; ci++) {
            var ind = filtered[ci];
            if (ind.category !== currentCat) {
                currentCat = ind.category;
                if (currentCat !== 'Lightweight Examples') {
                    var sec = document.createElement('div');
                    sec.className = 'tv-indicators-section';
                    sec.textContent = currentCat.toUpperCase();
                    list.appendChild(sec);
                }
            }
            (function(indDef) {
                var item = document.createElement('div');
                item.className = 'tv-indicator-item';
                var nameSpan = document.createElement('span');
                nameSpan.className = 'ind-name';
                nameSpan.textContent = indDef.fullName;
                item.appendChild(nameSpan);
                item.addEventListener('click', function() {
                    _tvAddIndicator(indDef, chartId);
                    renderList(searchInp.value);
                });
                list.appendChild(item);
            })(ind);
        }
    }

    searchInp.addEventListener('input', function() { renderList(searchInp.value); });
    renderList('');

    _tvAppendOverlay(chartId, overlay);
    searchInp.focus();
}

