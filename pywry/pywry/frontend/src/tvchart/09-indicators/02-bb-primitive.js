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

// ---------------------------------------------------------------------------
// Ichimoku Kumo (cloud) fill — drawn as a series primitive between the two
// Senkou-Span line series, swapping fill colour bar-by-bar based on which
// span is on top.  Per chart: { primitive, seriesId, group }.
// ---------------------------------------------------------------------------
var _ichimokuCloudPrimitives = {};
