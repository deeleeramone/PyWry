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

