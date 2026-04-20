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
