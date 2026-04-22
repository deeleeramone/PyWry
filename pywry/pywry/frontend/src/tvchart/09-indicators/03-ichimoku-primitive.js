
function _tvDrawIchimokuCloud(chartId, ctx, mediaSize) {
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (!entry || !entry.chart) return;

    // Find every Ichimoku group on this chart and draw their cloud.
    var groups = {};
    var keys = Object.keys(_activeIndicators);
    for (var i = 0; i < keys.length; i++) {
        var ind = _activeIndicators[keys[i]];
        if (ind.chartId !== chartId || ind.type !== 'ichimoku' || !ind.group) continue;
        if (!groups[ind.group]) {
            groups[ind.group] = {
                spanA: null, spanB: null,
                upColor: ind.cloudUpColor || _cssVar('--pywry-tvchart-ind-positive-dim'),
                downColor: ind.cloudDownColor || _cssVar('--pywry-tvchart-ind-negative-dim'),
                opacity: ind.cloudOpacity != null ? ind.cloudOpacity : 0.20,
            };
        }
        if (keys[i].indexOf('spanA') >= 0) groups[ind.group].spanA = keys[i];
        else if (keys[i].indexOf('spanB') >= 0) groups[ind.group].spanB = keys[i];
    }

    var timeScale = entry.chart.timeScale();
    var w = mediaSize.width;

    var groupKeys = Object.keys(groups);
    for (var gi = 0; gi < groupKeys.length; gi++) {
        var g = groups[groupKeys[gi]];
        if (!g.spanA || !g.spanB) continue;
        var sA = entry.seriesMap[g.spanA];
        var sB = entry.seriesMap[g.spanB];
        if (!sA || !sB) continue;

        var aData = sA.data();
        var bData = sB.data();
        if (!aData.length || !bData.length) continue;

        // Index span B by string-time so we can pair points fast.
        var bMap = {};
        for (var bi = 0; bi < bData.length; bi++) {
            if (bData[bi].value !== undefined) bMap[String(bData[bi].time)] = bData[bi].value;
        }

        // Build aligned point arrays in pixel coords.
        var pts = [];
        for (var ai = 0; ai < aData.length; ai++) {
            var pa = aData[ai];
            if (pa.value === undefined) continue;
            var bv = bMap[String(pa.time)];
            if (bv === undefined) continue;
            var x = timeScale.timeToCoordinate(pa.time);
            if (x === null || x === undefined) continue;
            if (x < -50 || x > w + 50) continue;
            var ya = sA.priceToCoordinate(pa.value);
            var yb = sA.priceToCoordinate(bv);
            if (ya === null || yb === null) continue;
            pts.push({ x: x, ya: ya, yb: yb, valA: pa.value, valB: bv });
        }
        if (pts.length < 2) continue;

        // Walk segments, splitting at A==B crossings so the fill flips
        // colour cleanly.  Each contiguous same-sign run is filled as
        // one polygon.
        var segments = [];
        var cur = { sign: pts[0].valA >= pts[0].valB ? 1 : -1, pts: [pts[0]] };
        for (var pi2 = 1; pi2 < pts.length; pi2++) {
            var prev = pts[pi2 - 1];
            var p = pts[pi2];
            var prevSign = prev.valA >= prev.valB ? 1 : -1;
            var sign = p.valA >= p.valB ? 1 : -1;
            if (sign === prevSign) {
                cur.pts.push(p);
                continue;
            }
            // Linear-interpolate the crossing X.
            var dPrev = prev.valA - prev.valB;
            var dCurr = p.valA - p.valB;
            var t = dPrev / (dPrev - dCurr);  // 0..1 along (prev, p)
            var xCross = prev.x + (p.x - prev.x) * t;
            var yCrossA = prev.ya + (p.ya - prev.ya) * t;
            // At the crossing, A == B (both lines meet).
            var crossPt = { x: xCross, ya: yCrossA, yb: yCrossA, valA: 0, valB: 0 };
            cur.pts.push(crossPt);
            segments.push(cur);
            cur = { sign: sign, pts: [crossPt, p] };
        }
        segments.push(cur);

        for (var si = 0; si < segments.length; si++) {
            var seg = segments[si];
            if (seg.pts.length < 2) continue;
            ctx.beginPath();
            ctx.moveTo(seg.pts[0].x, seg.pts[0].ya);
            for (var fi = 1; fi < seg.pts.length; fi++) ctx.lineTo(seg.pts[fi].x, seg.pts[fi].ya);
            for (var ri = seg.pts.length - 1; ri >= 0; ri--) ctx.lineTo(seg.pts[ri].x, seg.pts[ri].yb);
            ctx.closePath();
            var col = seg.sign >= 0 ? g.upColor : g.downColor;
            ctx.fillStyle = _tvHexToRgba(_tvColorToHex(col, '#26a69a'), g.opacity);
            ctx.fill();
        }
    }
}

function _tvEnsureIchimokuCloudPrimitive(chartId) {
    if (_ichimokuCloudPrimitives[chartId]) return;
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (!entry || !entry.chart) return;

    // Attach to any Span A series on this chart.
    var hostId = null;
    var aKeys = Object.keys(_activeIndicators);
    for (var i = 0; i < aKeys.length; i++) {
        var ai = _activeIndicators[aKeys[i]];
        if (ai.chartId === chartId && ai.type === 'ichimoku' && aKeys[i].indexOf('spanA') >= 0) {
            hostId = aKeys[i];
            break;
        }
    }
    if (!hostId || !entry.seriesMap[hostId]) return;

    var _requestUpdate = null;
    var renderer = {
        draw: function(target) {
            target.useMediaCoordinateSpace(function(scope) {
                _tvDrawIchimokuCloud(chartId, scope.context, scope.mediaSize);
            });
        },
    };
    var paneView = {
        zOrder: function() { return 'bottom'; },
        renderer: function() { return renderer; },
    };
    var primitive = {
        attached: function(p) { _requestUpdate = p.requestUpdate; if (_requestUpdate) _requestUpdate(); },
        detached: function() { _requestUpdate = null; },
        updateAllViews: function() {},
        paneViews: function() { return [paneView]; },
        triggerUpdate: function() { if (_requestUpdate) _requestUpdate(); },
    };

    entry.seriesMap[hostId].attachPrimitive(primitive);
    _ichimokuCloudPrimitives[chartId] = { primitive: primitive, seriesId: hostId };
}

function _tvRemoveIchimokuCloudPrimitive(chartId) {
    var ip = _ichimokuCloudPrimitives[chartId];
    if (!ip) return;
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (entry && entry.seriesMap[ip.seriesId]) {
        try { entry.seriesMap[ip.seriesId].detachPrimitive(ip.primitive); } catch (e) {}
    }
    delete _ichimokuCloudPrimitives[chartId];
}

function _tvUpdateIchimokuCloud(chartId) {
    var ip = _ichimokuCloudPrimitives[chartId];
    if (ip && ip.primitive && ip.primitive.triggerUpdate) ip.primitive.triggerUpdate();
}

// ---------------------------------------------------------------------------
// Volume Profile (VPVR / VPFR — volume-by-price histogram pinned to pane edge)
// ---------------------------------------------------------------------------

// Per-chart registry: { [indicatorId]: { primitive, seriesId, mode, bucketCount, vpData, opts } }
var _volumeProfilePrimitives = {};

