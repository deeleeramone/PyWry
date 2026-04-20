function _tvDrawAnchors(chartId, d) {
    var s = _tvMainSeries(chartId);
    if (!s) return [];
    if (d.type === 'hline') {
        var yH = s.priceToCoordinate(d.price);
        var viewport = _tvGetDrawingViewport(chartId);
        return yH !== null ? [{ key: 'price', x: Math.min(viewport.right - 24, viewport.left + 40), y: yH }] : [];
    }
    if (d.type === 'vline') {
        var vA = _tvToPixel(chartId, d.t1, 0);
        return vA ? [{ key: 'p1', x: vA.x, y: vA.y || 40 }] : [];
    }
    if (d.type === 'crossline') {
        var clA = _tvToPixel(chartId, d.t1, d.p1);
        return clA ? [{ key: 'p1', x: clA.x, y: clA.y }] : [];
    }
    if (d.type === 'flat_channel') {
        var fcY1 = s.priceToCoordinate(d.p1);
        var fcY2 = s.priceToCoordinate(d.p2);
        var fcVp = _tvGetDrawingViewport(chartId);
        var fcPts = [];
        if (fcY1 !== null) fcPts.push({ key: 'p1', x: fcVp.left + 40, y: fcY1 });
        if (fcY2 !== null) fcPts.push({ key: 'p2', x: fcVp.left + 40, y: fcY2 });
        return fcPts;
    }
    if (d.type === 'brush' || d.type === 'highlighter') {
        // No draggable anchors for brush/highlighter strokes
        return [];
    }
    if (d.type === 'path' || d.type === 'polyline') {
        // Anchors at each vertex
        var mpts = d.points;
        var anchors = [];
        if (mpts) {
            for (var mi = 0; mi < mpts.length; mi++) {
                var mpp = _tvToPixel(chartId, mpts[mi].t, mpts[mi].p);
                if (mpp) anchors.push({ key: 'pt' + mi, x: mpp.x, y: mpp.y });
            }
        }
        return anchors;
    }
    // Single-point tools
    var singlePointTools = ['arrow_mark_up', 'arrow_mark_down', 'arrow_mark_left', 'arrow_mark_right', 'anchored_vwap'];
    if (singlePointTools.indexOf(d.type) !== -1) {
        var sp = _tvToPixel(chartId, d.t1, d.p1);
        return sp ? [{ key: 'p1', x: sp.x, y: sp.y }] : [];
    }
    var pts = [];
    if (d.t1 !== undefined) {
        var a = _tvToPixel(chartId, d.t1, d.p1);
        if (a) pts.push({ key: 'p1', x: a.x, y: a.y });
    }
    if (d.t2 !== undefined) {
        var b = _tvToPixel(chartId, d.t2, d.p2);
        if (b) pts.push({ key: 'p2', x: b.x, y: b.y });
    }
    var threePointAnchors = ['fib_extension', 'fib_channel', 'fib_wedge', 'pitchfan', 'fib_time',
                             'rotated_rect', 'triangle', 'shape_arc', 'double_curve'];
    if (d.t3 !== undefined && threePointAnchors.indexOf(d.type) !== -1) {
        var c = _tvToPixel(chartId, d.t3, d.p3);
        if (c) pts.push({ key: 'p3', x: c.x, y: c.y });
    }
    return pts;
}

// ---- Hit-testing: find drawing near pixel x,y ----
function _tvHitTest(chartId, mx, my) {
    var ds = window.__PYWRY_DRAWINGS__[chartId];
    if (!ds) return -1;
    var viewport = _tvGetDrawingViewport(chartId);
    if (mx < viewport.left || mx > viewport.right || my < viewport.top || my > viewport.bottom) return -1;
    var THRESH = 8;
    // Iterate in reverse so topmost drawing is picked first
    for (var i = ds.drawings.length - 1; i >= 0; i--) {
        var d = ds.drawings[i];
        if (d.hidden) continue;
        if (_tvDrawHit(chartId, d, mx, my, THRESH)) return i;
    }
    return -1;
}

function _tvDrawHit(chartId, d, mx, my, T) {
    var s = _tvMainSeries(chartId);
    if (!s) return false;
    var viewport = _tvGetDrawingViewport(chartId);

    if (mx < viewport.left - T || mx > viewport.right + T || my < viewport.top - T || my > viewport.bottom + T) {
        return false;
    }

    if (d.type === 'hline') {
        var yH = s.priceToCoordinate(d.price);
        return yH !== null && mx >= viewport.left && mx <= viewport.right && Math.abs(my - yH) < T;
    }
    if (d.type === 'trendline' || d.type === 'channel' || d.type === 'ray' || d.type === 'extended_line' || d.type === 'regression_channel') {
        var a = _tvToPixel(chartId, d.t1, d.p1);
        var b = _tvToPixel(chartId, d.t2, d.p2);
        if (!a || !b) return false;
        // For ray: extend from a through b
        if (d.type === 'ray') {
            var rdx = b.x - a.x, rdy = b.y - a.y;
            var rlen = Math.sqrt(rdx * rdx + rdy * rdy);
            if (rlen > 0) {
                var bExt = { x: a.x + (rdx / rlen) * 4000, y: a.y + (rdy / rlen) * 4000 };
                if (_distToSeg(mx, my, a.x, a.y, bExt.x, bExt.y) < T) return true;
            }
            return false;
        }
        // For extended_line: extend in both directions
        if (d.type === 'extended_line') {
            var edx = b.x - a.x, edy = b.y - a.y;
            var elen = Math.sqrt(edx * edx + edy * edy);
            if (elen > 0) {
                var aExt = { x: a.x - (edx / elen) * 4000, y: a.y - (edy / elen) * 4000 };
                var bExt2 = { x: b.x + (edx / elen) * 4000, y: b.y + (edy / elen) * 4000 };
                if (_distToSeg(mx, my, aExt.x, aExt.y, bExt2.x, bExt2.y) < T) return true;
            }
            return false;
        }
        if (_distToSeg(mx, my, a.x, a.y, b.x, b.y) < T) return true;
        if (d.type === 'channel') {
            var off = d.offset || 30;
            if (_distToSeg(mx, my, a.x, a.y + off, b.x, b.y + off) < T) return true;
            // Inside fill
            var minY = Math.min(a.y, b.y);
            var maxY = Math.max(a.y, b.y) + off;
            var minX = Math.min(a.x, b.x);
            var maxX = Math.max(a.x, b.x);
            if (mx >= minX && mx <= maxX && my >= minY && my <= maxY) return true;
        }
        if (d.type === 'regression_channel') {
            var rcOff = d.offset || 30;
            if (_distToSeg(mx, my, a.x, a.y - rcOff, b.x, b.y - rcOff) < T) return true;
            if (_distToSeg(mx, my, a.x, a.y + rcOff, b.x, b.y + rcOff) < T) return true;
        }
        return false;
    }
    if (d.type === 'hray') {
        var hrY = s.priceToCoordinate(d.p1);
        var hrA = _tvToPixel(chartId, d.t1, d.p1);
        if (hrY === null || !hrA) return false;
        // Hit if near the horizontal line from anchor to right edge
        if (Math.abs(my - hrY) < T && mx >= hrA.x - T) return true;
        return false;
    }
    if (d.type === 'vline') {
        var vA = _tvToPixel(chartId, d.t1, d.p1 || 0);
        if (!vA) return false;
        if (Math.abs(mx - vA.x) < T) return true;
        return false;
    }
    if (d.type === 'crossline') {
        var clA = _tvToPixel(chartId, d.t1, d.p1);
        var clY = s.priceToCoordinate(d.p1);
        if (!clA || clY === null) return false;
        if (Math.abs(mx - clA.x) < T || Math.abs(my - clY) < T) return true;
        return false;
    }
    if (d.type === 'flat_channel') {
        var fcY1 = s.priceToCoordinate(d.p1);
        var fcY2 = s.priceToCoordinate(d.p2);
        if (fcY1 === null || fcY2 === null) return false;
        if (Math.abs(my - fcY1) < T || Math.abs(my - fcY2) < T) return true;
        var fcMin = Math.min(fcY1, fcY2), fcMax = Math.max(fcY1, fcY2);
        if (my >= fcMin && my <= fcMax) return true;
        return false;
    }
    if (d.type === 'brush') {
        var bpts = d.points;
        if (!bpts || bpts.length < 2) return false;
        for (var bi = 0; bi < bpts.length - 1; bi++) {
            var bpA = _tvToPixel(chartId, bpts[bi].t, bpts[bi].p);
            var bpB = _tvToPixel(chartId, bpts[bi + 1].t, bpts[bi + 1].p);
            if (bpA && bpB && _distToSeg(mx, my, bpA.x, bpA.y, bpB.x, bpB.y) < T) return true;
        }
        return false;
    }
    if (d.type === 'highlighter') {
        var hpts = d.points;
        if (!hpts || hpts.length < 2) return false;
        for (var hi = 0; hi < hpts.length - 1; hi++) {
            var hpA = _tvToPixel(chartId, hpts[hi].t, hpts[hi].p);
            var hpB = _tvToPixel(chartId, hpts[hi + 1].t, hpts[hi + 1].p);
            if (hpA && hpB && _distToSeg(mx, my, hpA.x, hpA.y, hpB.x, hpB.y) < T + 5) return true;
        }
        return false;
    }
    if (d.type === 'path' || d.type === 'polyline') {
        var mpts = d.points;
        if (!mpts || mpts.length < 2) return false;
        for (var mi = 0; mi < mpts.length - 1; mi++) {
            var mpA = _tvToPixel(chartId, mpts[mi].t, mpts[mi].p);
            var mpB = _tvToPixel(chartId, mpts[mi + 1].t, mpts[mi + 1].p);
            if (mpA && mpB && _distToSeg(mx, my, mpA.x, mpA.y, mpB.x, mpB.y) < T) return true;
        }
        // For path, also check closing segment
        if (d.type === 'path' && mpts.length > 2) {
            var mpFirst = _tvToPixel(chartId, mpts[0].t, mpts[0].p);
            var mpLast = _tvToPixel(chartId, mpts[mpts.length - 1].t, mpts[mpts.length - 1].p);
            if (mpFirst && mpLast && _distToSeg(mx, my, mpFirst.x, mpFirst.y, mpLast.x, mpLast.y) < T) return true;
        }
        return false;
    }
    if (d.type === 'rect') {
        var r1 = _tvToPixel(chartId, d.t1, d.p1);
        var r2 = _tvToPixel(chartId, d.t2, d.p2);
        if (!r1 || !r2) return false;
        var lx = Math.min(r1.x, r2.x);
        var ly = Math.min(r1.y, r2.y);
        var rx = Math.max(r1.x, r2.x);
        var ry = Math.max(r1.y, r2.y);
        if (mx >= lx - T && mx <= rx + T && my >= ly - T && my <= ry + T) return true;
        return false;
    }
    if (d.type === 'fibonacci') {
        var fT = s.priceToCoordinate(d.p1);
        var fB = s.priceToCoordinate(d.p2);
        if (fT === null || fB === null) return false;
        var minFy = Math.min(fT, fB);
        var maxFy = Math.max(fT, fB);
        if (my >= minFy - T && my <= maxFy + T) return true;
        return false;
    }
    if (d.type === 'fib_extension') {
        var feA = _tvToPixel(chartId, d.t1, d.p1);
        var feB = _tvToPixel(chartId, d.t2, d.p2);
        if (!feA || !feB) return false;
        if (_distToSeg(mx, my, feA.x, feA.y, feB.x, feB.y) < T) return true;
        if (d.t3 !== undefined) {
            var feC = _tvToPixel(chartId, d.t3, d.p3);
            if (feC && _distToSeg(mx, my, feB.x, feB.y, feC.x, feC.y) < T) return true;
            // Hit on any visible extension level line
            if (feC) {
                var abR = d.p2 - d.p1;
                var fLvls = (d.fibLevelValues && d.fibLevelValues.length) ? d.fibLevelValues : _FIB_LEVELS.slice();
                for (var fi = 0; fi < fLvls.length; fi++) {
                    var yy = s.priceToCoordinate(d.p3 + abR * fLvls[fi]);
                    if (yy !== null && Math.abs(my - yy) < T) return true;
                }
            }
        }
        return false;
    }
    if (d.type === 'fib_channel') {
        var fcA = _tvToPixel(chartId, d.t1, d.p1);
        var fcB = _tvToPixel(chartId, d.t2, d.p2);
        if (!fcA || !fcB) return false;
        if (_distToSeg(mx, my, fcA.x, fcA.y, fcB.x, fcB.y) < T) return true;
        if (d.t3 !== undefined) {
            var fcC = _tvToPixel(chartId, d.t3, d.p3);
            if (fcC) {
                var abDx = fcB.x - fcA.x, abDy = fcB.y - fcA.y;
                var abLen = Math.sqrt(abDx * abDx + abDy * abDy);
                if (abLen > 0) {
                    var cOff = ((fcC.x - fcA.x) * (-abDy / abLen) + (fcC.y - fcA.y) * (abDx / abLen));
                    var px = -abDy / abLen, py = abDx / abLen;
                    if (_distToSeg(mx, my, fcA.x + px * cOff, fcA.y + py * cOff, fcB.x + px * cOff, fcB.y + py * cOff) < T) return true;
                }
            }
        }
        return false;
    }
    if (d.type === 'fib_timezone') {
        var ftzA = _tvToPixel(chartId, d.t1, d.p1);
        var ftzB = _tvToPixel(chartId, d.t2, d.p2);
        if (!ftzA || !ftzB) return false;
        if (_distToSeg(mx, my, ftzA.x, ftzA.y, ftzB.x, ftzB.y) < T) return true;
        var tDiff = d.t2 - d.t1;
        var fibNums = [0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144];
        for (var fi = 0; fi < fibNums.length; fi++) {
            var xPx = _tvToPixel(chartId, d.t1 + tDiff * fibNums[fi], d.p1);
            if (xPx && Math.abs(mx - xPx.x) < T) return true;
        }
        return false;
    }
    if (d.type === 'fib_fan' || d.type === 'pitchfan') {
        var ffA = _tvToPixel(chartId, d.t1, d.p1);
        var ffB = _tvToPixel(chartId, d.t2, d.p2);
        if (!ffA || !ffB) return false;
        if (_distToSeg(mx, my, ffA.x, ffA.y, ffB.x, ffB.y) < T) return true;
        if (d.t3 !== undefined) {
            var ffC = _tvToPixel(chartId, d.t3, d.p3);
            if (ffC && _distToSeg(mx, my, ffA.x, ffA.y, ffC.x, ffC.y) < T) return true;
        }
        return false;
    }
    if (d.type === 'fib_arc' || d.type === 'fib_circle') {
        var faA = _tvToPixel(chartId, d.t1, d.p1);
        var faB = _tvToPixel(chartId, d.t2, d.p2);
        if (!faA || !faB) return false;
        if (_distToSeg(mx, my, faA.x, faA.y, faB.x, faB.y) < T) return true;
        var dist = Math.sqrt(Math.pow(faB.x - faA.x, 2) + Math.pow(faB.y - faA.y, 2));
        var ctrX = d.type === 'fib_circle' ? (faA.x + faB.x) / 2 : faA.x;
        var ctrY = d.type === 'fib_circle' ? (faA.y + faB.y) / 2 : faA.y;
        var baseR = d.type === 'fib_circle' ? dist / 2 : dist;
        var mDist = Math.sqrt(Math.pow(mx - ctrX, 2) + Math.pow(my - ctrY, 2));
        var fLvls = (d.fibLevelValues && d.fibLevelValues.length) ? d.fibLevelValues : _FIB_LEVELS.slice();
        for (var fi = 0; fi < fLvls.length; fi++) {
            if (fLvls[fi] === 0) continue;
            if (Math.abs(mDist - baseR * fLvls[fi]) < T) return true;
        }
        return false;
    }
    if (d.type === 'fib_wedge') {
        var fwA = _tvToPixel(chartId, d.t1, d.p1);
        var fwB = _tvToPixel(chartId, d.t2, d.p2);
        if (!fwA || !fwB) return false;
        if (_distToSeg(mx, my, fwA.x, fwA.y, fwB.x, fwB.y) < T) return true;
        if (d.t3 !== undefined) {
            var fwC = _tvToPixel(chartId, d.t3, d.p3);
            if (fwC && _distToSeg(mx, my, fwA.x, fwA.y, fwC.x, fwC.y) < T) return true;
        }
        return false;
    }
    if (d.type === 'fib_time') {
        var ftA = _tvToPixel(chartId, d.t1, d.p1);
        var ftB = _tvToPixel(chartId, d.t2, d.p2);
        if (!ftA || !ftB) return false;
        if (_distToSeg(mx, my, ftA.x, ftA.y, ftB.x, ftB.y) < T) return true;
        if (d.t3 !== undefined) {
            var ftC = _tvToPixel(chartId, d.t3, d.p3);
            if (ftC && _distToSeg(mx, my, ftB.x, ftB.y, ftC.x, ftC.y) < T) return true;
            var tDiff = d.t2 - d.t1;
            var ftLevels = (d.fibLevelValues && d.fibLevelValues.length) ? d.fibLevelValues : [0, 0.382, 0.5, 0.618, 1, 1.382, 1.618, 2, 2.618, 4.236];
            for (var fi = 0; fi < ftLevels.length; fi++) {
                var xPx = _tvToPixel(chartId, d.t3 + tDiff * ftLevels[fi], d.p3);
                if (xPx && Math.abs(mx - xPx.x) < T) return true;
            }
        }
        return false;
    }
    if (d.type === 'fib_spiral') {
        var fsA = _tvToPixel(chartId, d.t1, d.p1);
        var fsB = _tvToPixel(chartId, d.t2, d.p2);
        if (!fsA || !fsB) return false;
        if (_distToSeg(mx, my, fsA.x, fsA.y, fsB.x, fsB.y) < T) return true;
        var fsDist = Math.sqrt(Math.pow(mx - fsA.x, 2) + Math.pow(my - fsA.y, 2));
        var fsR = Math.sqrt(Math.pow(fsB.x - fsA.x, 2) + Math.pow(fsB.y - fsA.y, 2));
        if (fsR > 0) {
            var fsAngle = Math.atan2(my - fsA.y, mx - fsA.x) - Math.atan2(fsB.y - fsA.y, fsB.x - fsA.x);
            var fsPhi = 1.6180339887;
            var fsB2 = Math.log(fsPhi) / (Math.PI / 2);
            var fsExpected = fsR * Math.exp(fsB2 * fsAngle);
            if (Math.abs(fsDist - fsExpected) < T * 2) return true;
        }
        return false;
    }
    if (d.type === 'gann_box' || d.type === 'gann_square_fixed' || d.type === 'gann_square') {
        var gbA = _tvToPixel(chartId, d.t1, d.p1);
        var gbB = _tvToPixel(chartId, d.t2, d.p2);
        if (!gbA || !gbB) return false;
        var gblx = Math.min(gbA.x, gbB.x), gbrx = Math.max(gbA.x, gbB.x);
        var gbty = Math.min(gbA.y, gbB.y), gbby = Math.max(gbA.y, gbB.y);
        if (mx >= gblx - T && mx <= gbrx + T && my >= gbty - T && my <= gbby + T) return true;
        return false;
    }
    if (d.type === 'gann_fan') {
        var gfA = _tvToPixel(chartId, d.t1, d.p1);
        var gfB = _tvToPixel(chartId, d.t2, d.p2);
        if (!gfA || !gfB) return false;
        if (_distToSeg(mx, my, gfA.x, gfA.y, gfB.x, gfB.y) < T) return true;
        var gfDx = gfB.x - gfA.x, gfDy = gfB.y - gfA.y;
        var gfAngles = [0.125, 0.25, 0.333, 0.5, 1, 2, 3, 4, 8];
        for (var gi = 0; gi < gfAngles.length; gi++) {
            var gRatio = gfAngles[gi];
            var gfEndX = gfA.x + gfDx;
            var gfEndY = gfA.y + gfDy * gRatio;
            if (_distToSeg(mx, my, gfA.x, gfA.y, gfEndX, gfEndY) < T) return true;
        }
        return false;
    }
    if (d.type === 'measure') {
        var mp1 = _tvToPixel(chartId, d.t1, d.p1);
        var mp2 = _tvToPixel(chartId, d.t2, d.p2);
        if (!mp1 || !mp2) return false;
        if (_distToSeg(mx, my, mp1.x, mp1.y, mp2.x, mp2.y) < T) return true;
        return false;
    }
    if (d.type === 'text') {
        var tp = _tvToPixel(chartId, d.t1, d.p1);
        if (!tp) return false;
        var tw = (d.text || 'Text').length * 8;
        if (mx >= tp.x - 4 && mx <= tp.x + tw + 4 && my >= tp.y - 16 && my <= tp.y + 4) return true;
        return false;
    }
    // Single-point text tools — bounding box hit test
    var _txtNoteTools = ['anchored_text', 'note', 'price_note', 'pin', 'comment', 'price_label', 'signpost', 'flag_mark'];
    if (_txtNoteTools.indexOf(d.type) !== -1) {
        var tnp = _tvToPixel(chartId, d.t1, d.p1);
        if (!tnp) return false;
        var tnR = 25;
        if (Math.abs(mx - tnp.x) < tnR + T && Math.abs(my - tnp.y) < tnR + T) return true;
        return false;
    }
    if (d.type === 'callout') {
        var clp1 = _tvToPixel(chartId, d.t1, d.p1);
        if (!clp1) return false;
        if (Math.abs(mx - clp1.x) < 60 && my >= clp1.y - 40 && my <= clp1.y + 4) return true;
        if (d.t2 !== undefined) {
            var clp2 = _tvToPixel(chartId, d.t2, d.p2);
            if (clp2 && _distToSeg(mx, my, clp1.x, clp1.y, clp2.x, clp2.y) < T) return true;
        }
        return false;
    }
    if (d.type === 'arrow_marker') {
        var ap1 = _tvToPixel(chartId, d.t1, d.p1);
        var ap2 = _tvToPixel(chartId, d.t2, d.p2);
        if (!ap1 || !ap2) return false;
        var amdx = ap2.x - ap1.x, amdy = ap2.y - ap1.y;
        var amLen = Math.sqrt(amdx * amdx + amdy * amdy);
        if (amLen < 1) return false;
        var amHeadW = Math.max(amLen * 0.22, 16);
        if (_distToSeg(mx, my, ap1.x, ap1.y, ap2.x, ap2.y) < amHeadW + T) return true;
        return false;
    }
    if (d.type === 'arrow') {
        var ap1 = _tvToPixel(chartId, d.t1, d.p1);
        var ap2 = _tvToPixel(chartId, d.t2, d.p2);
        if (!ap1 || !ap2) return false;
        return _distToSeg(mx, my, ap1.x, ap1.y, ap2.x, ap2.y) < T;
    }
    var arrowMarks = ['arrow_mark_up', 'arrow_mark_down', 'arrow_mark_left', 'arrow_mark_right'];
    if (arrowMarks.indexOf(d.type) !== -1) {
        var amp = _tvToPixel(chartId, d.t1, d.p1);
        if (!amp) return false;
        var amR = (d.size || 30) / 2;
        return Math.abs(mx - amp.x) < amR && Math.abs(my - amp.y) < amR;
    }
    if (d.type === 'circle') {
        var cp1 = _tvToPixel(chartId, d.t1, d.p1);
        var cp2 = _tvToPixel(chartId, d.t2, d.p2);
        if (!cp1 || !cp2) return false;
        var ccx = (cp1.x + cp2.x) / 2, ccy = (cp1.y + cp2.y) / 2;
        var cr = Math.sqrt(Math.pow(cp2.x - cp1.x, 2) + Math.pow(cp2.y - cp1.y, 2)) / 2;
        var cDist = Math.sqrt(Math.pow(mx - ccx, 2) + Math.pow(my - ccy, 2));
        return Math.abs(cDist - cr) < T;
    }
    if (d.type === 'ellipse') {
        var ep1 = _tvToPixel(chartId, d.t1, d.p1);
        var ep2 = _tvToPixel(chartId, d.t2, d.p2);
        if (!ep1 || !ep2) return false;
        var ecx = (ep1.x + ep2.x) / 2, ecy = (ep1.y + ep2.y) / 2;
        var erx = Math.abs(ep2.x - ep1.x) / 2, ery = Math.abs(ep2.y - ep1.y) / 2;
        if (erx < 1 || ery < 1) return false;
        var eNorm = Math.pow((mx - ecx) / erx, 2) + Math.pow((my - ecy) / ery, 2);
        return Math.abs(eNorm - 1) < 0.3;
    }
    if (d.type === 'triangle') {
        var tr1 = _tvToPixel(chartId, d.t1, d.p1);
        var tr2 = _tvToPixel(chartId, d.t2, d.p2);
        var tr3 = d.t3 !== undefined ? _tvToPixel(chartId, d.t3, d.p3) : null;
        if (!tr1 || !tr2 || !tr3) return false;
        if (_distToSeg(mx, my, tr1.x, tr1.y, tr2.x, tr2.y) < T) return true;
        if (_distToSeg(mx, my, tr2.x, tr2.y, tr3.x, tr3.y) < T) return true;
        if (_distToSeg(mx, my, tr3.x, tr3.y, tr1.x, tr1.y) < T) return true;
        return false;
    }
    if (d.type === 'rotated_rect') {
        var rr1 = _tvToPixel(chartId, d.t1, d.p1);
        var rr2 = _tvToPixel(chartId, d.t2, d.p2);
        var rr3 = d.t3 !== undefined ? _tvToPixel(chartId, d.t3, d.p3) : null;
        if (!rr1 || !rr2 || !rr3) return false;
        var rdx = rr2.x - rr1.x, rdy = rr2.y - rr1.y;
        var rlen = Math.sqrt(rdx * rdx + rdy * rdy);
        if (rlen < 1) return false;
        var rnx = -rdy / rlen, rny = rdx / rlen;
        var rprojW = (rr3.x - rr1.x) * rnx + (rr3.y - rr1.y) * rny;
        var rc = rr1, rd = rr2;
        var re = { x: rr2.x + rnx * rprojW, y: rr2.y + rny * rprojW };
        var rf = { x: rr1.x + rnx * rprojW, y: rr1.y + rny * rprojW };
        if (_distToSeg(mx, my, rc.x, rc.y, rd.x, rd.y) < T) return true;
        if (_distToSeg(mx, my, rd.x, rd.y, re.x, re.y) < T) return true;
        if (_distToSeg(mx, my, re.x, re.y, rf.x, rf.y) < T) return true;
        if (_distToSeg(mx, my, rf.x, rf.y, rc.x, rc.y) < T) return true;
        return false;
    }
    if (d.type === 'shape_arc' || d.type === 'curve') {
        var scp1 = _tvToPixel(chartId, d.t1, d.p1);
        var scp2 = _tvToPixel(chartId, d.t2, d.p2);
        if (!scp1 || !scp2) return false;
        if (_distToSeg(mx, my, scp1.x, scp1.y, scp2.x, scp2.y) < T + 10) return true;
        return false;
    }
    if (d.type === 'double_curve') {
        var dc1 = _tvToPixel(chartId, d.t1, d.p1);
        var dc2 = _tvToPixel(chartId, d.t2, d.p2);
        if (!dc1 || !dc2) return false;
        if (_distToSeg(mx, my, dc1.x, dc1.y, dc2.x, dc2.y) < T + 10) return true;
        return false;
    }
    if (d.type === 'long_position' || d.type === 'short_position') {
        var lp1 = _tvToPixel(chartId, d.t1, d.p1);
        var lp2 = _tvToPixel(chartId, d.t2, d.p2);
        if (!lp1 || !lp2) return false;
        var lpL = Math.min(lp1.x, lp2.x), lpR = Math.max(lp1.x, lp2.x);
        if (lpR - lpL < 20) lpR = lpL + 150;
        var lpStopY = lp1.y + (lp1.y - lp2.y);
        var lpTopY = Math.min(lp2.y, lpStopY), lpBotY = Math.max(lp2.y, lpStopY);
        if (mx >= lpL - T && mx <= lpR + T && my >= lpTopY - T && my <= lpBotY + T) return true;
        return false;
    }
    if (d.type === 'forecast' || d.type === 'ghost_feed') {
        var fg1 = _tvToPixel(chartId, d.t1, d.p1);
        var fg2 = _tvToPixel(chartId, d.t2, d.p2);
        if (!fg1 || !fg2) return false;
        return _distToSeg(mx, my, fg1.x, fg1.y, fg2.x, fg2.y) < T;
    }
    if (d.type === 'bars_pattern' || d.type === 'projection' || d.type === 'fixed_range_vol' || d.type === 'date_price_range') {
        var bx1 = _tvToPixel(chartId, d.t1, d.p1);
        var bx2 = _tvToPixel(chartId, d.t2, d.p2);
        if (!bx1 || !bx2) return false;
        var bxL = Math.min(bx1.x, bx2.x), bxR = Math.max(bx1.x, bx2.x);
        var bxT = Math.min(bx1.y, bx2.y), bxB = Math.max(bx1.y, bx2.y);
        if (mx >= bxL - T && mx <= bxR + T && my >= bxT - T && my <= bxB + T) return true;
        return false;
    }
    if (d.type === 'anchored_vwap') {
        var avp = _tvToPixel(chartId, d.t1, d.p1);
        if (!avp) return false;
        return Math.abs(mx - avp.x) < T;
    }
    if (d.type === 'price_range') {
        var prp1 = _tvToPixel(chartId, d.t1, d.p1);
        var prp2 = _tvToPixel(chartId, d.t2, d.p2);
        if (!prp1 || !prp2) return false;
        if (Math.abs(my - prp1.y) < T || Math.abs(my - prp2.y) < T) return true;
        if (Math.abs(mx - prp1.x) < T && my >= Math.min(prp1.y, prp2.y) && my <= Math.max(prp1.y, prp2.y)) return true;
        return false;
    }
    if (d.type === 'date_range') {
        var drp1 = _tvToPixel(chartId, d.t1, d.p1);
        var drp2 = _tvToPixel(chartId, d.t2, d.p2);
        if (!drp1 || !drp2) return false;
        if (Math.abs(mx - drp1.x) < T || Math.abs(mx - drp2.x) < T) return true;
        return false;
    }
    return false;
}

function _distToSeg(px, py, x1, y1, x2, y2) {
    var dx = x2 - x1, dy = y2 - y1;
    var len2 = dx * dx + dy * dy;
    if (len2 === 0) return Math.sqrt((px - x1) * (px - x1) + (py - y1) * (py - y1));
    var t = Math.max(0, Math.min(1, ((px - x1) * dx + (py - y1) * dy) / len2));
    var nx = x1 + t * dx, ny = y1 + t * dy;
    return Math.sqrt((px - nx) * (px - nx) + (py - ny) * (py - ny));
}

function _tvRoundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + r);
    ctx.lineTo(x + w, y + h - r);
    ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    ctx.lineTo(x + r, y + h);
    ctx.quadraticCurveTo(x, y + h, x, y + h - r);
    ctx.lineTo(x, y + r);
    ctx.quadraticCurveTo(x, y, x + r, y);
    ctx.closePath();
}

// ---- Helpers for Pearson's R ----
function _tvGetSeriesDataBetween(chartId, t1, t2) {
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (!entry || !entry.series) return null;
    var data = entry.series.data ? entry.series.data() : null;
    if (!data || !data.length) return null;
    var lo = Math.min(t1, t2), hi = Math.max(t1, t2);
    var result = [];
    for (var i = 0; i < data.length; i++) {
        var pt = data[i];
        if (pt.time >= lo && pt.time <= hi) {
            var v = pt.close !== undefined ? pt.close : pt.value;
            if (v !== undefined && v !== null) result.push({ idx: i, value: v });
        }
    }
    return result.length > 1 ? result : null;
}

function _tvPearsonsR(vals) {
    var n = vals.length;
    if (n < 2) return null;
    var sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0, sumY2 = 0;
    for (var i = 0; i < n; i++) {
        var x = i, y = vals[i].value;
        sumX += x; sumY += y; sumXY += x * y; sumX2 += x * x; sumY2 += y * y;
    }
    var denom = Math.sqrt((n * sumX2 - sumX * sumX) * (n * sumY2 - sumY * sumY));
    if (denom === 0) return 0;
    return (n * sumXY - sumX * sumY) / denom;
}

// ---- Rendering ----
function _tvRenderDrawings(chartId) {
    var ds = window.__PYWRY_DRAWINGS__[chartId];
    if (!ds) return;
    var ctx = ds.ctx;
    var w = ds.canvas.clientWidth;
    var h = ds.canvas.clientHeight;
    ctx.clearRect(0, 0, w, h);

    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (!entry || !entry.chart) return;

    var theme = entry.theme || 'dark';
    var defColor = _cssVar('--pywry-draw-default-color');
    var textColor = _cssVar('--pywry-tvchart-text');
    var viewport = _tvGetDrawingViewport(chartId);

    for (var i = 0; i < ds.drawings.length; i++) {
        if (ds.drawings[i].hidden) continue;
        var isSel = (_drawSelectedChart === chartId && _drawSelectedIdx === i);
        var isHov = (_drawHoverIdx === i && _drawSelectedChart === chartId && _drawSelectedIdx !== i);
        var isMouseOver = (_drawHoverIdx === i);
        _tvDrawOne(ctx, ds.drawings[i], chartId, defColor, textColor, w, h, isSel, isHov, isMouseOver, viewport);
    }
    if (_drawPending && _drawPending.chartId === chartId) {
        _tvDrawOne(ctx, _drawPending, chartId, defColor, textColor, w, h, false, false, false, viewport);
    }
}

