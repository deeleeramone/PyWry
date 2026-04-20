/** positionsBox — media→bitmap pixel alignment helper. */
function _tvPositionsBox(a, b, pixelRatio) {
    var lo = Math.min(a, b);
    var hi = Math.max(a, b);
    var scaled = Math.round(lo * pixelRatio);
    return {
        position: scaled,
        length: Math.max(1, Math.round(hi * pixelRatio) - scaled),
    };
}

/**
 * Bucket bars into a volume-by-price histogram with up/down split.
 *
 * @param {Array} bars - OHLCV bar objects with {time, open, high, low, close, volume}
 * @param {number} fromIdx - inclusive start index
 * @param {number} toIdx - inclusive end index
 * @param {Object} opts - { rowsLayout: 'rows'|'ticks', rowSize: number, valueAreaPct, withDeveloping }
 * @returns {{profile, minPrice, maxPrice, step, totalVolume, developing?}|null}
 */
function _tvComputeVolumeProfile(bars, fromIdx, toIdx, opts) {
    if (!bars || !bars.length) return null;
    opts = opts || {};
    var lo = Math.max(0, Math.min(fromIdx, toIdx, bars.length - 1));
    var hi = Math.min(bars.length - 1, Math.max(fromIdx, toIdx, 0));
    if (hi < lo) return null;

    var minP = Infinity, maxP = -Infinity;
    for (var i = lo; i <= hi; i++) {
        var b = bars[i];
        var h = b.high !== undefined ? b.high : b.close;
        var l = b.low !== undefined ? b.low : b.close;
        if (h === undefined || l === undefined) continue;
        if (h > maxP) maxP = h;
        if (l < minP) minP = l;
    }
    if (!isFinite(minP) || !isFinite(maxP) || maxP === minP) return null;

    // Resolve bucket count from layout option.
    var rowsLayout = opts.rowsLayout || 'rows';
    var rowSize = Math.max(0.0001, Number(opts.rowSize) || 24);
    var nBuckets;
    if (rowsLayout === 'ticks') {
        nBuckets = Math.max(2, Math.min(2000, Math.ceil((maxP - minP) / rowSize)));
    } else {
        nBuckets = Math.max(2, Math.floor(rowSize));
    }
    var step = (maxP - minP) / nBuckets;

    var up = new Array(nBuckets), down = new Array(nBuckets);
    for (var k = 0; k < nBuckets; k++) { up[k] = 0; down[k] = 0; }

    // Optional running snapshots (for Developing POC / VA).  Recorded
    // once per bar so the renderer can plot the running point of
    // control as a step line across time.
    var withDeveloping = opts.withDeveloping === true;
    var valueAreaPct = opts.valueAreaPct || 0.70;
    var developing = withDeveloping ? [] : null;

    var totalVol = 0;
    for (var j = lo; j <= hi; j++) {
        var bar = bars[j];
        var bH = bar.high !== undefined ? bar.high : bar.close;
        var bL = bar.low !== undefined ? bar.low : bar.close;
        var bO = bar.open !== undefined ? bar.open : bar.close;
        var bC = bar.close !== undefined ? bar.close : bar.value;
        var vol = bar.volume !== undefined && bar.volume !== null ? Number(bar.volume) : 0;
        if (!isFinite(vol) || vol <= 0) {
            if (withDeveloping) developing.push({ time: bar.time });
            continue;
        }
        if (bH === undefined || bL === undefined) {
            if (withDeveloping) developing.push({ time: bar.time });
            continue;
        }
        var loIdx = Math.max(0, Math.min(nBuckets - 1, Math.floor((bL - minP) / step)));
        var hiIdx = Math.max(0, Math.min(nBuckets - 1, Math.floor((bH - minP) / step)));
        var span = hiIdx - loIdx + 1;
        var share = vol / span;
        var isUp = bC !== undefined && bC >= bO;
        for (var bi = loIdx; bi <= hiIdx; bi++) {
            if (isUp) up[bi] += share; else down[bi] += share;
        }
        totalVol += vol;

        if (withDeveloping) {
            // Snapshot the running POC and Value Area edges so far.
            var snap = _tvDevelopingSnapshot(up, down, totalVol, minP, step, valueAreaPct);
            developing.push({
                time: bar.time,
                pocPrice: snap.pocPrice,
                vaHighPrice: snap.vaHighPrice,
                vaLowPrice: snap.vaLowPrice,
            });
        }
    }

    var profile = [];
    for (var p = 0; p < nBuckets; p++) {
        profile.push({
            price: minP + step * (p + 0.5),
            priceLo: minP + step * p,
            priceHi: minP + step * (p + 1),
            upVol: up[p],
            downVol: down[p],
            totalVol: up[p] + down[p],
        });
    }

    return {
        profile: profile,
        minPrice: minP,
        maxPrice: maxP,
        step: step,
        totalVolume: totalVol,
        developing: developing,
    };
}

/** Per-bar snapshot of the running POC + value-area edges. */
function _tvDevelopingSnapshot(up, down, totalVol, minP, step, vaPct) {
    var n = up.length;
    var pocIdx = 0;
    var pocVol = up[0] + down[0];
    for (var i = 1; i < n; i++) {
        var t = up[i] + down[i];
        if (t > pocVol) { pocVol = t; pocIdx = i; }
    }
    if (pocVol === 0) return { pocPrice: undefined, vaHighPrice: undefined, vaLowPrice: undefined };

    var target = totalVol * (vaPct || 0.70);
    var accumulated = pocVol;
    var loIdx = pocIdx, hiIdx = pocIdx;
    while (accumulated < target && (loIdx > 0 || hiIdx < n - 1)) {
        var nextLow = loIdx > 0 ? (up[loIdx - 1] + down[loIdx - 1]) : -1;
        var nextHigh = hiIdx < n - 1 ? (up[hiIdx + 1] + down[hiIdx + 1]) : -1;
        if (nextLow < 0 && nextHigh < 0) break;
        if (nextHigh >= nextLow) {
            hiIdx += 1;
            accumulated += up[hiIdx] + down[hiIdx];
        } else {
            loIdx -= 1;
            accumulated += up[loIdx] + down[loIdx];
        }
    }
    return {
        pocPrice: minP + step * (pocIdx + 0.5),
        vaHighPrice: minP + step * (hiIdx + 1),
        vaLowPrice: minP + step * loIdx,
    };
}

/** Compute the Point of Control (POC) and Value Area for a profile. */
function _tvComputePOCAndValueArea(profile, totalVolume, valueAreaPct) {
    if (!profile || !profile.length) return null;
    var pocIdx = 0;
    for (var i = 1; i < profile.length; i++) {
        if (profile[i].totalVol > profile[pocIdx].totalVol) pocIdx = i;
    }
    var target = totalVolume * (valueAreaPct || 0.70);
    var accumulated = profile[pocIdx].totalVol;
    var loIdx = pocIdx, hiIdx = pocIdx;
    while (accumulated < target && (loIdx > 0 || hiIdx < profile.length - 1)) {
        var nextLow = loIdx > 0 ? profile[loIdx - 1].totalVol : -1;
        var nextHigh = hiIdx < profile.length - 1 ? profile[hiIdx + 1].totalVol : -1;
        if (nextLow < 0 && nextHigh < 0) break;
        if (nextHigh >= nextLow) {
            hiIdx += 1;
            accumulated += profile[hiIdx].totalVol;
        } else {
            loIdx -= 1;
            accumulated += profile[loIdx].totalVol;
        }
    }
    return { pocIdx: pocIdx, vaLowIdx: loIdx, vaHighIdx: hiIdx };
}

/**
 * Build an ISeriesPrimitive that renders the volume profile as horizontal
 * rows pinned to one side of the price pane.  Each row is a horizontal
 * bar at a price bucket, split into up-volume (teal) and down-volume
 * (pink), with a POC line and translucent value-area band overlay.
 */
function _tvMakeVolumeProfilePrimitive(chartId, seriesId, getData, getOpts, getHidden) {
    var _requestUpdate = null;

    function draw(scope) {
        if (getHidden && getHidden()) return;
        var entry = window.__PYWRY_TVCHARTS__[chartId];
        if (!entry || !entry.chart) return;
        var series = entry.seriesMap[seriesId];
        if (!series) return;
        var vp = getData();
        if (!vp || !vp.profile || !vp.profile.length) return;
        var opts = (getOpts && getOpts()) || {};

        var ctx = scope.context;
        // bitmapSize is ALREADY in bitmap pixels (= mediaSize * pixelRatio).
        // priceToCoordinate returns MEDIA pixels — convert with vpr.
        var paneW = scope.bitmapSize.width;
        var hpr = scope.horizontalPixelRatio;
        var vpr = scope.verticalPixelRatio;

        var widthPct = Math.max(2, Math.min(60, opts.widthPercent || 15));
        var placement = opts.placement === 'left' ? 'left' : 'right';
        var volumeMode = opts.volumeMode || 'updown';   // 'updown' | 'total' | 'delta'
        var upColor = opts.upColor || _cssVar('--pywry-tvchart-vp-up');
        var downColor = opts.downColor || _cssVar('--pywry-tvchart-vp-down');
        var vaUpColor = opts.vaUpColor || _cssVar('--pywry-tvchart-vp-va-up');
        var vaDownColor = opts.vaDownColor || _cssVar('--pywry-tvchart-vp-va-down');
        var pocColor = opts.pocColor || _cssVar('--pywry-tvchart-vp-poc');
        var devPocColor = opts.developingPOCColor || _cssVar('--pywry-tvchart-ind-tertiary');
        var devVAColor = opts.developingVAColor || _cssVar('--pywry-tvchart-vp-va-up');
        var showPOC = opts.showPOC !== false;
        var showVA = opts.showValueArea !== false;
        var showDevPOC = opts.showDevelopingPOC === true;
        var showDevVA = opts.showDevelopingVA === true;
        var valueAreaPct = opts.valueAreaPct || 0.70;

        // For Delta mode the displayed magnitude is |upVol - downVol|.
        // Otherwise it's the total bucket volume.
        function bucketMagnitude(row) {
            return volumeMode === 'delta' ? Math.abs(row.upVol - row.downVol) : row.totalVol;
        }
        var maxVol = 0;
        for (var i = 0; i < vp.profile.length; i++) {
            var m = bucketMagnitude(vp.profile[i]);
            if (m > maxVol) maxVol = m;
        }
        if (maxVol <= 0) return;

        var poc = _tvComputePOCAndValueArea(vp.profile, vp.totalVolume, valueAreaPct);

        var maxBarBitmap = paneW * (widthPct / 100);

        // Row height: derive from bucket spacing (priceToCoordinate is media px).
        var y0 = series.priceToCoordinate(vp.profile[0].price);
        var y1 = vp.profile.length > 1 ? series.priceToCoordinate(vp.profile[1].price) : null;
        if (y0 === null) return;
        var pxPerBucket = (y1 !== null) ? Math.abs(y0 - y1) : 4;
        var rowHalfBitmap = Math.max(1, (pxPerBucket * vpr) / 2 - 1);
        var rowHeight = Math.max(1, rowHalfBitmap * 2 - 2);

        function drawSegment(x, w, color, yTop) {
            if (w <= 0) return;
            ctx.fillStyle = color;
            ctx.fillRect(x, yTop, w, rowHeight);
        }

        for (var r = 0; r < vp.profile.length; r++) {
            var row = vp.profile[r];
            if (row.totalVol <= 0) continue;
            var y = series.priceToCoordinate(row.price);
            if (y === null) continue;

            var yBitmap = y * vpr;
            var yTop = yBitmap - rowHalfBitmap;
            var inValueArea = poc && r >= poc.vaLowIdx && r <= poc.vaHighIdx;
            var curUp = inValueArea && showVA ? vaUpColor : upColor;
            var curDown = inValueArea && showVA ? vaDownColor : downColor;

            var barLenBitmap = maxBarBitmap * (bucketMagnitude(row) / maxVol);

            if (volumeMode === 'updown') {
                var upRatio = row.upVol / row.totalVol;
                var upLen = barLenBitmap * upRatio;
                var downLen = barLenBitmap - upLen;
                if (placement === 'right') {
                    drawSegment(paneW - upLen, upLen, curUp, yTop);
                    drawSegment(paneW - upLen - downLen, downLen, curDown, yTop);
                } else {
                    drawSegment(0, upLen, curUp, yTop);
                    drawSegment(upLen, downLen, curDown, yTop);
                }
            } else if (volumeMode === 'delta') {
                // Delta = upVol - downVol.  Positive bars use the up colour
                // (extending inward from the edge); negative use down.
                var net = row.upVol - row.downVol;
                var col = net >= 0 ? curUp : curDown;
                if (placement === 'right') {
                    drawSegment(paneW - barLenBitmap, barLenBitmap, col, yTop);
                } else {
                    drawSegment(0, barLenBitmap, col, yTop);
                }
            } else {
                // Total: single bar coloured by net direction (up bias = up colour).
                var totalCol = row.upVol >= row.downVol ? curUp : curDown;
                if (placement === 'right') {
                    drawSegment(paneW - barLenBitmap, barLenBitmap, totalCol, yTop);
                } else {
                    drawSegment(0, barLenBitmap, totalCol, yTop);
                }
            }
        }

        if (showPOC && poc) {
            var pocPrice = vp.profile[poc.pocIdx].price;
            var pocY = series.priceToCoordinate(pocPrice);
            if (pocY !== null) {
                ctx.save();
                ctx.strokeStyle = pocColor;
                ctx.lineWidth = Math.max(1, Math.round(vpr));
                ctx.setLineDash([4 * hpr, 3 * hpr]);
                ctx.beginPath();
                ctx.moveTo(0, pocY * vpr);
                ctx.lineTo(paneW, pocY * vpr);
                ctx.stroke();
                ctx.restore();
            }
        }

        // Developing POC / VA: step-line plots across time, computed
        // bar-by-bar in _tvComputeVolumeProfile when withDeveloping=true.
        if ((showDevPOC || showDevVA) && Array.isArray(vp.developing) && vp.developing.length > 0) {
            var timeScale = entry.chart.timeScale();
            function plotDevLine(field, color) {
                ctx.save();
                ctx.strokeStyle = color;
                ctx.lineWidth = Math.max(1, Math.round(vpr));
                ctx.beginPath();
                var moved = false;
                for (var di = 0; di < vp.developing.length; di++) {
                    var p = vp.developing[di];
                    var px = p[field];
                    if (px === undefined) { moved = false; continue; }
                    var dx = timeScale.timeToCoordinate(p.time);
                    var dy = series.priceToCoordinate(px);
                    if (dx === null || dy === null) { moved = false; continue; }
                    var dxB = dx * hpr;
                    var dyB = dy * vpr;
                    if (!moved) { ctx.moveTo(dxB, dyB); moved = true; }
                    else { ctx.lineTo(dxB, dyB); }
                }
                ctx.stroke();
                ctx.restore();
            }
            if (showDevPOC) plotDevLine('pocPrice', devPocColor);
            if (showDevVA) {
                plotDevLine('vaHighPrice', devVAColor);
                plotDevLine('vaLowPrice', devVAColor);
            }
        }
    }

    var renderer = {
        draw: function(target) {
            target.useBitmapCoordinateSpace(draw);
        },
    };

    var paneView = {
        zOrder: function() { return 'top'; },
        renderer: function() { return renderer; },
        update: function() {},
    };

    return {
        attached: function(params) {
            _requestUpdate = params.requestUpdate;
            // Kick the first paint — without this the primitive only renders
            // on the next user interaction (pan/zoom/resize).
            if (_requestUpdate) _requestUpdate();
        },
        detached: function() { _requestUpdate = null; },
        updateAllViews: function() {},
        paneViews: function() { return [paneView]; },
        triggerUpdate: function() { if (_requestUpdate) _requestUpdate(); },
    };
}

/** Format a volume number for the legend (1.23M / 4.56K / 789). */
function _tvFormatVolume(v) {
    var n = Number(v) || 0;
    var sign = n < 0 ? '-' : '';
    var a = Math.abs(n);
    if (a >= 1e9) return sign + (a / 1e9).toFixed(2) + 'B';
    if (a >= 1e6) return sign + (a / 1e6).toFixed(2) + 'M';
    if (a >= 1e3) return sign + (a / 1e3).toFixed(2) + 'K';
    return sign + a.toFixed(0);
}

/** Sum up, down, and total volume across a VP profile for the legend readout. */
function _tvVolumeProfileTotals(vp) {
    var totals = { up: 0, down: 0, total: 0 };
    if (!vp || !vp.profile) return totals;
    for (var i = 0; i < vp.profile.length; i++) {
        totals.up += vp.profile[i].upVol || 0;
        totals.down += vp.profile[i].downVol || 0;
    }
    totals.total = totals.up + totals.down;
    return totals;
}

/** Update the legend value span for a VP indicator with current totals. */
function _tvUpdateVolumeProfileLegendValues(seriesId) {
    var slot = _volumeProfilePrimitives[seriesId];
    if (!slot) return;
    var el = document.getElementById('tvchart-ind-val-' + seriesId);
    if (!el) return;
    var t = _tvVolumeProfileTotals(slot.vpData);
    el.textContent = _tvFormatVolume(t.up) + '  '
        + _tvFormatVolume(t.down) + '  '
        + _tvFormatVolume(t.total);
}

/**
 * Live-preview helper for the VP settings dialog: every Inputs/Style
 * row callback funnels through here so changes paint instantly without
 * waiting for the OK button.  Recomputes the bucket profile when a
 * compute-affecting field changed (rows layout, row size, value area,
 * developing toggles).  Cheap when only colours / placement / width
 * change — just updates the opts dict and triggers a redraw.
 */
function _tvApplyVPDraftLive(seriesId, draft) {
    var slot = _volumeProfilePrimitives[seriesId];
    var info = _activeIndicators[seriesId];
    if (!slot || !info) return;
    var entry = window.__PYWRY_TVCHARTS__[info.chartId];
    if (!entry) return;
    var prevOpts = slot.opts || {};
    var newRowsLayout = draft.vpRowsLayout || slot.rowsLayout || 'rows';
    var newRowSize = draft.vpRowSize != null ? Number(draft.vpRowSize) : slot.rowSize;
    var newVolumeMode = draft.vpVolumeMode || slot.volumeMode || 'updown';
    var newValueAreaPct = draft.vpValueAreaPct != null
        ? draft.vpValueAreaPct / 100
        : (prevOpts.valueAreaPct || 0.70);
    var newShowDevPOC = draft.vpShowDevelopingPOC === true;
    var newShowDevVA = draft.vpShowDevelopingVA === true;

    slot.opts = {
        rowsLayout: newRowsLayout,
        rowSize: newRowSize,
        volumeMode: newVolumeMode,
        widthPercent: draft.vpWidthPercent != null ? Number(draft.vpWidthPercent) : prevOpts.widthPercent,
        placement: draft.vpPlacement || prevOpts.placement || 'right',
        upColor: draft.vpUpColor || prevOpts.upColor,
        downColor: draft.vpDownColor || prevOpts.downColor,
        vaUpColor: draft.vpVAUpColor || prevOpts.vaUpColor,
        vaDownColor: draft.vpVADownColor || prevOpts.vaDownColor,
        pocColor: draft.vpPOCColor || prevOpts.pocColor,
        developingPOCColor: draft.vpDevelopingPOCColor || prevOpts.developingPOCColor,
        developingVAColor: draft.vpDevelopingVAColor || prevOpts.developingVAColor,
        showPOC: draft.vpShowPOC !== undefined ? draft.vpShowPOC : prevOpts.showPOC,
        showValueArea: draft.vpShowValueArea !== undefined ? draft.vpShowValueArea : prevOpts.showValueArea,
        showDevelopingPOC: newShowDevPOC,
        showDevelopingVA: newShowDevVA,
        valueAreaPct: newValueAreaPct,
    };

    var needsRecompute = newRowsLayout !== slot.rowsLayout
        || newRowSize !== slot.rowSize
        || newValueAreaPct !== (prevOpts.valueAreaPct || 0.70)
        || newShowDevPOC !== (prevOpts.showDevelopingPOC === true)
        || newShowDevVA !== (prevOpts.showDevelopingVA === true);
    if (needsRecompute) {
        slot.rowsLayout = newRowsLayout;
        slot.rowSize = newRowSize;
        var rawData = _tvSeriesRawData(entry, info.sourceSeriesId || 'main');
        var fromIdx = info.fromIndex != null ? info.fromIndex : 0;
        var toIdx = info.toIndex != null ? info.toIndex : (rawData.length - 1);
        var newVp = _tvComputeVolumeProfile(rawData, fromIdx, toIdx, {
            rowsLayout: newRowsLayout,
            rowSize: newRowSize,
            valueAreaPct: newValueAreaPct,
            withDeveloping: newShowDevPOC || newShowDevVA,
        });
        if (newVp) slot.vpData = newVp;
    }
    slot.volumeMode = newVolumeMode;

    info.rowsLayout = newRowsLayout;
    info.rowSize = newRowSize;
    info.volumeMode = newVolumeMode;
    info.valueAreaPct = newValueAreaPct;
    info.placement = slot.opts.placement;
    info.widthPercent = slot.opts.widthPercent;
    info.upColor = slot.opts.upColor;
    info.downColor = slot.opts.downColor;
    info.vaUpColor = slot.opts.vaUpColor;
    info.vaDownColor = slot.opts.vaDownColor;
    info.pocColor = slot.opts.pocColor;
    info.developingPOCColor = slot.opts.developingPOCColor;
    info.developingVAColor = slot.opts.developingVAColor;
    info.showPOC = slot.opts.showPOC;
    info.showValueArea = slot.opts.showValueArea;
    info.showDevelopingPOC = newShowDevPOC;
    info.showDevelopingVA = newShowDevVA;
    info.period = newRowsLayout === 'rows' ? newRowSize : 0;

    if (slot.primitive && slot.primitive.triggerUpdate) slot.primitive.triggerUpdate();
    _tvUpdateVolumeProfileLegendValues(seriesId);
    _tvRebuildIndicatorLegend(info.chartId);
}

/** Remove a volume-profile primitive by indicator id. */
function _tvRemoveVolumeProfilePrimitive(indicatorId) {
    var slot = _volumeProfilePrimitives[indicatorId];
    if (!slot) return;
    var entry = window.__PYWRY_TVCHARTS__[slot.chartId];
    if (entry && entry.seriesMap[slot.seriesId] && slot.primitive) {
        try { entry.seriesMap[slot.seriesId].detachPrimitive(slot.primitive); } catch (e) {}
    }
    delete _volumeProfilePrimitives[indicatorId];
}

/** Recompute all visible-range volume profiles on the given chart. */
function _tvRefreshVisibleVolumeProfiles(chartId) {
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (!entry || !entry.chart) return;
    var timeScale = entry.chart.timeScale();
    var range = typeof timeScale.getVisibleLogicalRange === 'function'
        ? timeScale.getVisibleLogicalRange()
        : null;
    var ids = Object.keys(_volumeProfilePrimitives);
    for (var i = 0; i < ids.length; i++) {
        var slot = _volumeProfilePrimitives[ids[i]];
        if (!slot || slot.chartId !== chartId || slot.mode !== 'visible') continue;
        var ai = _activeIndicators[ids[i]];
        if (!ai) continue;
        var bars = _tvSeriesRawData(entry, ai.sourceSeriesId || 'main');
        if (!bars || !bars.length) continue;
        var fromIdx, toIdx;
        if (range) {
            fromIdx = Math.max(0, Math.floor(range.from));
            toIdx = Math.min(bars.length - 1, Math.ceil(range.to));
        } else {
            fromIdx = 0;
            toIdx = bars.length - 1;
        }
        var vp = _tvComputeVolumeProfile(bars, fromIdx, toIdx, {
            rowsLayout: slot.rowsLayout || 'rows',
            rowSize: slot.rowSize || ai.rowSize || 24,
            valueAreaPct: (slot.opts && slot.opts.valueAreaPct) || 0.70,
            withDeveloping: (slot.opts && (slot.opts.showDevelopingPOC || slot.opts.showDevelopingVA)) === true,
        });
        if (!vp) continue;
        slot.vpData = vp;
        ai.fromIndex = fromIdx;
        ai.toIndex = toIdx;
        if (slot.primitive && slot.primitive.triggerUpdate) slot.primitive.triggerUpdate();
        _tvUpdateVolumeProfileLegendValues(ids[i]);
    }
}

